"""GET /api/hub tests (issue #357): the hub's stable, versioned status contract.

Guarded with importorskip like test_server.py: the plain CI `test` job (no fastapi/httpx) skips cleanly; the
`test-dashboard` job runs them via `pytest dashboard_web/api`.
"""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")  # dashboard-only dep
pytest.importorskip("httpx")    # fastapi.testclient.TestClient transport

_API = Path(__file__).resolve().parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

import hub  # noqa: E402 — after importorskip + sys.path
import server  # noqa: E402

import dashboard_data as dd  # noqa: E402

_ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_STARTED = "2026-10-27T13:00:00+00:00"


def _units(over: dict | None = None) -> dict:
    """systemctl-shaped props for all four jobs: timers armed + scheduled, services idle after a success."""
    out: dict[str, dict] = {}
    for name in hub.JOBS:
        out[f"{name}.timer"] = {"Id": f"{name}.timer", "ActiveState": "active",
                                "NextElapseUSecRealtime": "Tue 2026-10-27 19:45:00 UTC"}
        out[f"{name}.service"] = {"Id": f"{name}.service", "ActiveState": "inactive", "Result": "success"}
    for unit, props in (over or {}).items():
        out[unit] = {**out[unit], **props}
    return out


@pytest.fixture
def hub_db(convexity_db, monkeypatch, tmp_path):
    """A journal with one council run + one open (marked) position whose symbol must never leak, the server
    pointed at it, timers armed, heartbeats ONLINE, KILL off, and an empty records dir."""
    convexity_db.execute("INSERT INTO runs(started_at, mode, equity) VALUES(?, 'PAPER', 100000)", (_STARTED,))
    run_id = convexity_db.execute("SELECT MAX(id) FROM runs").fetchone()[0]
    convexity_db.execute(
        "INSERT INTO council_proposals(run_id, as_of, theme, symbol, direction, conviction) "
        "VALUES(?, ?, 'ai_compute', 'ZZQTEST', 'bullish', 'LOW')", (run_id, _STARTED))
    import state
    state.record_convexity_position(
        convexity_db, run_id=run_id, opened_at=_STARTED, theme="ai_compute", symbol="ZZQTEST",
        direction="bullish", structure_kind="long_call", contract_symbol="ZZQTESTC", expiry="2027-01-15",
        strike=100.0, dte=300, moneyness=0.25, contracts=2, entry_premium_per_contract=500.0,
        total_premium=1000.0, status="open")
    convexity_db.execute("UPDATE convexity_positions SET mark=6.0, marked_at='2026-10-27T14:00:00+00:00'")
    convexity_db.commit()
    monkeypatch.setenv("DRAMATIC_DB", convexity_db.execute("PRAGMA database_list").fetchone()[2])
    monkeypatch.delenv("KILL", raising=False)
    import risk
    monkeypatch.setattr(risk, "KILL_FILE", tmp_path / "no-such-KILL")
    monkeypatch.setattr(dd, "cycle_session_stale", lambda ts, *, now=None: "ONLINE")
    monkeypatch.setattr(dd, "council_session_stale", lambda ts, *, now=None: "ONLINE")
    monkeypatch.setattr(dd, "l2_session_stale", lambda ts, *, now=None: "ONLINE")
    monkeypatch.setattr(hub, "_read_units", lambda: _units())
    monkeypatch.setattr(server, "_RECORDS_DIR", tmp_path / "records")
    server._hub_cache.clear()
    yield convexity_db
    server._hub_cache.clear()


def _get(path: str = "/api/hub"):
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        return client.get(path)


def _job(body: dict, name: str) -> dict:
    return next(j for j in body["jobs"] if j["name"] == name)


def _check(body: dict, label: str) -> dict:
    return next(c for c in body["checks"] if c["label"] == label)


def test_hub_contract_shape_small_and_no_positions(hub_db) -> None:
    r = _get()
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    assert len(r.content) < 4 * 1024
    assert b"ZZQTEST" not in r.content and b"positions" not in r.content   # no position-level data
    body = r.json()
    assert set(body) == {"schema", "generated_at", "trading", "market", "checks", "jobs", "book", "versions"}
    assert body["schema"] == 1 and body["market"] is None and set(body["versions"]) == {"commit"}
    assert body["trading"] == {"state": "on", "why": None}
    assert _ISO_Z.match(body["generated_at"])
    assert [c["label"] for c in body["checks"]] == ["Kill switch", "Kill rule", "Cost cap", "Cycle"]
    for c in body["checks"]:
        assert set(c) == {"label", "ok", "detail", "blocking", "kind"}
        assert c["kind"] in {"switch", "fault", "session", "running"}
    assert _check(body, "Kill switch")["ok"] is True and _check(body, "Kill switch")["detail"] == "off"
    assert _check(body, "Kill rule")["blocking"] is True and _check(body, "Cost cap")["blocking"] is False
    assert _check(body, "Cycle")["kind"] == "running" and _check(body, "Cycle")["ok"] is True
    assert [j["name"] for j in body["jobs"]] == [
        "dramatic-options-l1", "dramatic-options-l2", "dramatic-options-l0", "dramatic-options-reach"]
    for j in body["jobs"]:
        assert set(j) == {"name", "last_ok", "last_status", "next_due", "enabled", "error"}
        assert j["next_due"] == "2026-10-27T19:45:00Z" and j["enabled"] is True
    assert _job(body, "dramatic-options-l1")["last_ok"] == "2026-10-27T13:00:00Z"
    assert _job(body, "dramatic-options-l1")["last_status"] == "ran"


def test_hub_book_is_frame_plus_realized_plus_unrealized_with_oldest_mark_as_of(hub_db) -> None:
    frame = float(server.load_config()["convexity_book"]["account_equity"])
    body = _get().json()
    # one position, 2 contracts, entry $500 each, mark 6.0 → (600 − 500) × 2 = +200 unrealized
    assert body["book"]["value"] == round(frame + 200.0, 2)
    assert body["book"]["as_of"] == "2026-10-27T14:00:00Z" and body["book"]["note"] is None
    assert body["book"]["label"]


def test_hub_book_is_null_with_a_reason_when_unmarked_or_no_cycle(hub_db) -> None:
    hub_db.execute("UPDATE convexity_positions SET mark=NULL, marked_at=NULL")
    hub_db.commit()
    book = _get().json()["book"]
    assert book["value"] is None and book["as_of"] is None and "unmarked" in book["note"]

    server._hub_cache.clear()
    hub_db.execute("DELETE FROM council_proposals")
    hub_db.execute("DELETE FROM convexity_positions")
    hub_db.execute("DELETE FROM runs")
    hub_db.commit()
    book = _get().json()["book"]
    assert book["value"] is None and book["note"] == "no cycle has run yet"


def test_hub_disabled_timer_is_idle_not_missed(hub_db, monkeypatch) -> None:
    stale = {"at": "2026-09-01T12:00:00", "status": "STALE", "age_hours": 900.0}
    real = dd.header_status
    monkeypatch.setattr(dd, "header_status", lambda conn, **kw: {**real(conn, **kw), "discovery": stale})
    # armed + stale → missed
    body = _get().json()
    assert _job(body, "dramatic-options-l0")["last_status"] == "missed"
    assert _job(body, "dramatic-options-l0")["last_ok"] == "2026-09-01T12:00:00Z"
    # the same staleness on a DISABLED timer (PROD) is idle: nothing is scheduled, so nothing was missed
    server._hub_cache.clear()
    monkeypatch.setattr(hub, "_read_units", lambda: _units(
        {"dramatic-options-l0.timer": {"ActiveState": "inactive", "NextElapseUSecRealtime": ""}}))
    j = _job(_get().json(), "dramatic-options-l0")
    assert j["enabled"] is False and j["last_status"] == "idle" and j["next_due"] is None


def test_hub_failed_and_running_services(hub_db, monkeypatch) -> None:
    monkeypatch.setattr(hub, "_read_units", lambda: _units({
        "dramatic-options-l2.service": {"ActiveState": "failed", "Result": "exit-code"},
        "dramatic-options-l1.service": {"ActiveState": "activating"}}))
    body = _get().json()
    l2 = _job(body, "dramatic-options-l2")
    assert l2["last_status"] == "failed" and "exit-code" in l2["error"]
    assert _job(body, "dramatic-options-l1")["last_status"] == "running"


def test_hub_systemd_unreadable_is_null_not_enabled(hub_db, monkeypatch) -> None:
    monkeypatch.setattr(hub, "_read_units", lambda: None)
    body = _get().json()
    for j in body["jobs"]:
        assert j["enabled"] is None and j["next_due"] is None
    assert _job(body, "dramatic-options-l1")["last_status"] == "ran"   # the journal still says it ran


def test_hub_reach_last_ok_comes_from_the_newest_cards_doc(hub_db, tmp_path) -> None:
    cards = tmp_path / "records" / "cards"
    cards.mkdir(parents=True)
    (cards / "2026-W30.md").write_text("# Survivor cards — 2026-W30\n\n- generated: 2026-10-25T13:40:00+00:00\n")
    j = _job(_get().json(), "dramatic-options-reach")
    assert j["last_ok"] == "2026-10-25T13:40:00Z" and j["last_status"] == "ran"


def test_hub_kill_switch_is_off_state_and_beats_the_cache(hub_db, monkeypatch) -> None:
    assert _get().json()["trading"]["state"] == "on"   # populates the cache
    monkeypatch.setenv("KILL", "1")                      # engaged within the TTL
    body = _get().json()
    assert body["trading"] == {"state": "off", "why": "kill switch engaged"}
    assert _check(body, "Kill switch")["ok"] is False and _check(body, "Kill switch")["detail"] == "ENGAGED"


def test_hub_kill_rule_tripped_is_blocked(hub_db) -> None:
    # entry $1000, mark $0.05 → ~95% of the position lost; against a $10k book budget that clears the 20% halt
    hub_db.execute("UPDATE convexity_positions SET mark=0.05, total_premium=3000")
    hub_db.commit()
    body = _get().json()
    assert _check(body, "Kill rule")["ok"] is False
    assert body["trading"]["state"] == "blocked" and "TRIPPED" in body["trading"]["why"]


def test_hub_stale_cycle_is_stopped(hub_db, monkeypatch) -> None:
    monkeypatch.setattr(dd, "cycle_session_stale", lambda ts, *, now=None: "STALE")
    body = _get().json()
    assert _check(body, "Cycle")["ok"] is False
    assert body["trading"]["state"] == "stopped" and "STALE" in body["trading"]["why"]


def test_hub_no_database_is_unknown_never_ok(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DRAMATIC_DB", str(tmp_path / "missing.db"))
    monkeypatch.delenv("KILL", raising=False)
    import risk
    monkeypatch.setattr(risk, "KILL_FILE", tmp_path / "no-such-KILL")
    monkeypatch.setattr(hub, "_read_units", lambda: None)
    monkeypatch.setattr(server, "_RECORDS_DIR", tmp_path / "records")
    server._hub_cache.clear()
    body = _get().json()
    assert body["trading"]["state"] == "unknown" and "no database" in body["trading"]["why"]
    assert _check(body, "Kill switch")["ok"] is True          # a file/env read: still knowable
    assert _check(body, "Kill rule")["ok"] is None and _check(body, "Cycle")["ok"] is None
    assert body["book"]["value"] is None and "no database" in body["book"]["note"]
    assert all(j["last_status"] is None for j in body["jobs"][:3])   # unreadable ≠ "ran"
    server._hub_cache.clear()


def test_hub_is_ttl_cached_and_nocache_busts_it(hub_db, monkeypatch) -> None:
    calls = {"n": 0}
    real = hub.build_hub

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(server, "build_hub", counting)
    _get()
    _get()
    assert calls["n"] == 1
    _get("/api/hub?nocache=1")
    assert calls["n"] == 2


def test_hub_requires_the_token_when_one_is_set(hub_db, monkeypatch) -> None:
    monkeypatch.setattr(server, "_DASHBOARD_TOKEN", "s3cret")
    assert _get().status_code == 401
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        assert client.get("/api/hub", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_hub_is_get_only() -> None:
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        assert client.post("/api/hub").status_code == 405


def test_read_units_parses_one_systemctl_call_and_fails_soft() -> None:
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout=(
            "Id=dramatic-options-l1.timer\nActiveState=active\nNextElapseUSecRealtime=Wed 2026-10-28 19:45:00 UTC\n"
            "Result=\n\nId=dramatic-options-l1.service\nActiveState=inactive\nResult=success\n"))

    units = hub._read_units(run=fake_run)
    assert len(calls) == 1 and calls[0][:2] == ["systemctl", "show"]
    assert hub._next_due(units["dramatic-options-l1.timer"]) == "2026-10-28T19:45:00Z"
    assert units["dramatic-options-l1.service"]["Result"] == "success"

    def boom(*_a, **_k):
        raise FileNotFoundError("systemctl")

    assert hub._read_units(run=boom) is None
    assert hub._read_units(run=lambda *_a, **_k: SimpleNamespace(returncode=1, stdout="")) is None
    assert hub._next_due({"NextElapseUSecRealtime": ""}) is None


# ── #374: disabled loop timers are "stopped" whatever the heartbeat says; not-installed is unknown ─────────────

_OFF = {"ActiveState": "inactive", "NextElapseUSecRealtime": ""}


def test_hub_disabled_loop_timers_are_stopped_even_with_an_online_heartbeat(hub_db, monkeypatch) -> None:
    # PROD's shape: L1/L2 timers installed but disabled; off-hours the Cycle heartbeat still reads ONLINE (the
    # fixture pins it ONLINE), which alone left the hub saying "on" overnight and at weekends.
    monkeypatch.setattr(hub, "_read_units", lambda: _units(
        {"dramatic-options-l1.timer": _OFF, "dramatic-options-l2.timer": _OFF}))
    body = _get().json()
    assert _check(body, "Cycle")["ok"] is True
    assert body["trading"] == {"state": "stopped", "why": "timers disabled: L1, L2"}
    # one loop timer is enough: L2 off means no marks or exits
    server._hub_cache.clear()
    monkeypatch.setattr(hub, "_read_units", lambda: _units({"dramatic-options-l2.timer": _OFF}))
    assert _get().json()["trading"] == {"state": "stopped", "why": "timer disabled: L2"}
    # a disabled weekly job (L0) is not the trading loop
    server._hub_cache.clear()
    monkeypatch.setattr(hub, "_read_units", lambda: _units({"dramatic-options-l0.timer": _OFF}))
    assert _get().json()["trading"]["state"] == "on"


def test_hub_kill_switch_and_kill_rule_outrank_disabled_timers() -> None:
    jobs = [{"name": "dramatic-options-l1", "enabled": False}, {"name": "dramatic-options-l2", "enabled": False}]
    ok = {"ok": True, "blocking": True, "detail": "x"}
    base = [{**ok, "label": "Kill switch"}, {**ok, "label": "Kill rule"}, {**ok, "label": "Cycle"}]
    assert hub._trading(base, None, jobs)["state"] == "stopped"
    assert hub._trading([{**base[0], "ok": False}, *base[1:]], None, jobs)["state"] == "off"
    assert hub._trading([base[0], {**base[1], "ok": False}, base[2]], None, jobs)["state"] == "blocked"
    # an unreadable check does not hide the definite fact that the loop's timers are off
    assert hub._trading([base[0], {**base[1], "ok": None}, base[2]], None, jobs)["state"] == "stopped"
    # unreadable timers (enabled None) never count as disabled: fall back to the checks
    assert hub._trading(base, None, [{**j, "enabled": None} for j in jobs])["state"] == "on"


def test_hub_systemd_unreadable_falls_back_to_the_heartbeat(hub_db, monkeypatch) -> None:
    monkeypatch.setattr(hub, "_read_units", lambda: None)
    assert _get().json()["trading"]["state"] == "on"


def test_hub_not_installed_unit_is_unknown_not_disabled(hub_db, monkeypatch) -> None:
    # systemctl show exits 0 for a unit that doesn't exist: LoadState=not-found, ActiveState=inactive
    monkeypatch.setattr(hub, "_read_units", lambda: _units(
        {"dramatic-options-l0.timer": {"LoadState": "not-found", **_OFF}}))
    body = _get().json()
    j = _job(body, "dramatic-options-l0")
    assert j["enabled"] is None and j["last_status"] is None and j["error"] == "timer not installed"
    assert body["trading"]["state"] == "on"


def test_hub_no_cost_cap_configured_is_unknown_not_zero() -> None:
    hdr = {"cycle": {"status": "ONLINE", "age_hours": 1.0}}
    risk = {"kill_rule": {"tripped": False, "book_drawdown": 0.05, "drawdown_halt": 0.2, "have_marks": True}}
    for cc in ({}, {"cap_usd": None, "tripped": False}, {"cap_usd": 0, "tripped": False}):
        c = {x["label"]: x for x in hub._checks(hdr, {**risk, "cost_cap": cc})}["Cost cap"]
        assert c["ok"] is None and c["detail"] == "no cost cap configured" and c["blocking"] is False
    c = {x["label"]: x for x in hub._checks(hdr, {**risk, "cost_cap": {"cap_usd": 1.5, "tripped": False}})}["Cost cap"]
    assert c["ok"] is True and c["detail"] == "within the $1.5/run cap"
    # a trip is reported from the last run's health even if the cap was since removed from config
    for cap in (1.5, 0, None):
        c = {x["label"]: x for x in hub._checks(hdr, {**risk, "cost_cap": {"cap_usd": cap, "tripped": True}})}["Cost cap"]
        assert c["ok"] is False and c["detail"].startswith("last council run hit the cost cap")


# ── #376: the loop jobs read their OWN runs; the KILL switch reads paused, not missed ──────────────────────────

def _run(conn, started_at: str, health: str | None) -> None:
    conn.execute("INSERT INTO runs(started_at, mode, equity, council_health) VALUES(?, 'PAPER', 100000, ?)",
                 (started_at, health))


def test_loop_beats_split_l1_from_l2_by_council_and_the_1545_band(convexity_db):
    now = datetime(2026, 10, 27, 21, 0, tzinfo=UTC)              # Tue 17:00 ET (EDT)
    _run(convexity_db, "2026-10-27 15:00:02", None)               # 11:00 ET L2 tick
    _run(convexity_db, "2026-10-27 19:45:02", "ok")               # 15:45 ET L1 with a council
    _run(convexity_db, "2026-10-27 19:30:01", None)               # 15:30 ET L2 tick — the last one
    beats = hub._loop_beats(convexity_db, now)
    assert beats["l1"]["at"].startswith("2026-10-27T19:45:02")
    assert beats["l2"]["at"].startswith("2026-10-27T19:30:01")   # the L1 run never refreshes L2
    assert beats["l2"]["status"] == "STALE"                       # 16:00 and 16:30 ticks are missing


def test_a_kill_rule_skipped_l1_still_counts_as_ran(convexity_db):
    now = datetime(2026, 10, 27, 21, 0, tzinfo=UTC)
    _run(convexity_db, "2026-10-26 19:45:02", "ok")               # Monday's council
    _run(convexity_db, "2026-10-27 19:45:03", None)               # Tuesday 15:45: council skipped (kill rule)
    beats = hub._loop_beats(convexity_db, now)
    assert beats["l1"]["at"].startswith("2026-10-27T19:45:03") and beats["l1"]["status"] == "ONLINE"
    assert beats["l2"]["at"] is None or not beats["l2"]["at"].startswith("2026-10-27T19:45")


def test_kill_switch_reads_paused_not_missed(hub_db, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(dd, "l2_session_stale", lambda ts, *, now=None: "STALE")
    assert _job(_get().json(), "dramatic-options-l2")["last_status"] == "missed"    # armed + stale, no KILL
    server._hub_cache.clear()
    kill = tmp_path / "KILL"
    kill.write_text("")
    import risk
    monkeypatch.setattr(risk, "KILL_FILE", kill)
    body = _get().json()
    assert body["trading"]["state"] == "off"
    j = _job(body, "dramatic-options-l2")
    assert j["last_status"] == "idle" and j["error"] == "paused: kill switch engaged"


def test_loop_read_failure_leaves_the_loop_jobs_unknown(hub_db, monkeypatch) -> None:
    def boom(conn, now=None):
        raise RuntimeError("runs unreadable")
    monkeypatch.setattr(hub, "_loop_beats", boom)
    body = _get().json()
    for name in ("dramatic-options-l1", "dramatic-options-l2"):
        assert _job(body, name)["last_status"] is None and _job(body, name)["error"] == "last run unreadable"


def test_an_l2_dead_longer_than_the_read_window_is_stale_not_never_ran(convexity_db):
    _run(convexity_db, "2026-10-01 15:00:02", None)               # an L2 tick 26 days earlier, nothing since
    beats = hub._loop_beats(convexity_db, datetime(2026, 10, 27, 21, 0, tzinfo=UTC))
    assert beats["l2"]["at"].startswith("2026-10-01") and beats["l2"]["status"] == "STALE"


def test_the_1545_band_follows_et_across_the_dst_change(convexity_db):
    # 11-02 is EST: the 15:45 L1 run starts at 20:45Z, and 19:45Z is an off-grid run (14:45 EST), not L1
    _run(convexity_db, "2026-11-02 20:45:02", None)
    _run(convexity_db, "2026-11-02 19:45:02", None)
    beats = hub._loop_beats(convexity_db, datetime(2026, 11, 2, 22, 0, tzinfo=UTC))
    assert beats["l1"]["at"].startswith("2026-11-02T20:45:02")
    assert beats["l2"]["at"].startswith("2026-11-02T19:45:02")
