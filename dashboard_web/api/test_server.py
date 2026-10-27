"""Server tests: the /api routes win over the SPA catch-all (I2) and the snapshot TTL cache (D1).

Guarded with importorskip so the plain CI `test` job (no fastapi/httpx) skips cleanly; the `test-dashboard`
job installs the dashboard deps and runs them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")  # dashboard-only dep
pytest.importorskip("httpx")    # fastapi.testclient.TestClient transport

_API = Path(__file__).resolve().parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

import server  # noqa: E402 — after importorskip + sys.path


def test_api_routes_declared_before_spa_mount() -> None:
    """I2: /api/* must be registered BEFORE the SPA catch-all Mount, else the static mount shadows the API.
    (In CI there is no built dist/, so the Mount may be absent — then there is nothing to shadow.)"""
    from starlette.routing import Mount

    routes = server.app.routes
    api_idx = [i for i, r in enumerate(routes) if str(getattr(r, "path", "")).startswith("/api")]
    mount_idx = [i for i, r in enumerate(routes) if isinstance(r, Mount) and getattr(r, "path", "") == ""]
    assert api_idx, "no /api routes registered"
    if mount_idx:
        assert max(api_idx) < min(mount_idx), "the SPA '/' mount must come AFTER the /api routes"


def test_health_is_json_not_static() -> None:
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        r = client.get("/api/health")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() == {"ok": True}


def test_version_reports_head_start_and_env(monkeypatch) -> None:
    """Issue #307: GET /api/version in the alpha_options shape — the commit the process started from, when it
    started, and its env. Read once at import, so a restart onto a new commit is visible to the hub."""
    import re

    from fastapi.testclient import TestClient

    monkeypatch.setenv("DRAMATIC_ENV", "PROD")
    with TestClient(server.app) as client:
        r = client.get("/api/version")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert set(body) == {"head", "started_at", "env"} and body["env"] == "prod"
    assert body["head"] is None or re.fullmatch(r"[0-9a-f]{40}", body["head"])
    assert body["started_at"].endswith("+00:00")


def test_checkout_head_fails_soft(monkeypatch) -> None:
    def boom(*_a, **_k):
        raise FileNotFoundError("git")
    monkeypatch.setattr(server.subprocess, "run", boom)
    assert server._checkout_head() is None


def test_snapshot_route_serves_json() -> None:
    """/api/snapshot is handled by the API (returns a JSON dict), not swallowed by a static file."""
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        r = client.get("/api/snapshot")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert isinstance(r.json(), dict)


def test_snapshot_ttl_cache_and_nocache(monkeypatch) -> None:
    """D1: a 2nd call within the TTL is served from cache (no rebuild); ?nocache=1 forces a rebuild."""
    from fastapi.testclient import TestClient

    calls = {"n": 0}

    def fake_build(db_path, cache_dir, db_exists):  # noqa: ANN001 — test stub
        calls["n"] += 1
        return {"ok": calls["n"]}

    monkeypatch.setattr(server, "build_snapshot", fake_build)
    server._snapshot_cache.clear()

    with TestClient(server.app) as client:
        first = client.get("/api/snapshot").json()
        second = client.get("/api/snapshot").json()
        assert first == second
        assert calls["n"] == 1  # the 2nd call hit the cache

        client.get("/api/snapshot?nocache=1")
        assert calls["n"] == 2  # nocache forced a rebuild

    server._snapshot_cache.clear()


def test_curation_draft_screen_sanitizes() -> None:
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        r = client.post("/api/curation/draft", json={"kind": "screen", "tickers": "amba, mbly, $(x), /etc"})
        assert r.status_code == 200
        body = r.json()
        assert body["kind"] == "screen" and body["tickers"] == ["AMBA", "MBLY"]   # shell-meta dropped
        assert body["command"].endswith("probe_basket_feasibility.py AMBA MBLY")


def test_curation_draft_theme_shape() -> None:
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        r = client.post("/api/curation/draft", json={
            "kind": "theme", "name": "AV Autonomy", "cluster": "ai_compute",
            "thesis": "robotaxi inflection", "falsifier": "IV stays rich", "source": "https://x/h.csv"})
        assert r.status_code == 200
        body = r.json()
        assert body["kind"] == "theme" and body["valid"] is True and body["key"] == "av_autonomy"
        assert body["entry"]["provenance"] == "operator" and "av_autonomy" in body["json"]


def test_curation_draft_theme_warns_on_unknown_cluster() -> None:
    # the API passes known_clusters=cluster_names(config) → an unknown cluster surfaces the cap warning
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        r = client.post("/api/curation/draft", json={
            "kind": "theme", "name": "zz_new", "cluster": "totally_new_cluster_xyz",
            "thesis": "t", "falsifier": "f", "source": "s"})
        assert r.status_code == 200
        assert any("per-name cap" in w for w in r.json()["warnings"])


def test_curation_draft_bad_kind_is_400() -> None:
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        assert client.post("/api/curation/draft", json={"kind": "nope"}).status_code == 400


# ── GET /api/status (issue #353): the light, cached status read ────────────────────────────────────────

def _status_db(convexity_db, monkeypatch):
    """A fixture journal with one council run (01:30Z → the ET date is the DAY BEFORE), one open position
    whose symbol must never appear in the status, and the server pointed at it (no systemd, no .env)."""
    import dashboard_data as dd
    import state

    started = "2026-10-27T01:30:00+00:00"
    run_id = convexity_db.execute(
        "INSERT INTO runs(started_at, mode) VALUES(?, 'PAPER')", (started,)).lastrowid
    convexity_db.execute(
        "INSERT INTO council_proposals(run_id, as_of, theme, symbol, direction, conviction) "
        "VALUES(?, ?, 'ai_compute', 'ZZQTEST', 'bullish', 'LOW')", (run_id, started))
    state.record_convexity_position(
        convexity_db, run_id=run_id, opened_at=started, theme="ai_compute", symbol="ZZQTEST",
        direction="bullish", structure_kind="long_call", contract_symbol="ZZQTESTC", expiry="2027-01-15",
        strike=100.0, dte=300, moneyness=0.25, contracts=1, entry_premium_per_contract=500.0,
        total_premium=500.0, status="open")
    convexity_db.commit()
    db_path = convexity_db.execute("PRAGMA database_list").fetchone()[2]
    monkeypatch.setenv("DRAMATIC_DB", db_path)
    # header_status binds its systemd reader as a default arg, so swap the default (restored by monkeypatch)
    monkeypatch.setattr(dd.header_status, "__kwdefaults__",
                        {**dd.header_status.__kwdefaults__, "next_at": lambda unit: "2026-10-27 19:45:00"})
    server._status_cache.clear()
    server._snapshot_cache.clear()
    return run_id


def test_status_is_small_has_no_positions_and_the_expected_facts(convexity_db, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    run_id = _status_db(convexity_db, monkeypatch)
    with TestClient(server.app) as client:
        r = client.get("/api/status")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    assert len(r.content) < 5 * 1024
    assert b"ZZQTEST" not in r.content and b"positions" not in r.content   # no position data
    body = r.json()
    assert {"system_status", "heartbeats", "kill", "drawdown", "book", "last_council", "t4", "commit"} <= set(body)
    assert set(body["heartbeats"]) == {"cycle", "council", "discovery"}
    assert body["heartbeats"]["cycle"]["next_at"] == "2026-10-27T19:45:00+00:00"
    assert set(body["heartbeats"]["cycle"]) == {"status", "at", "age_hours", "next_at"}
    assert body["book"]["open"] == 1 and body["book"]["max"] == 15
    assert body["drawdown"]["halt"] == 0.2          # display of the existing halt, unchanged
    assert body["kill"]["rule_tripped"] is False
    # 2026-10-27T01:30Z is the evening of 10-26 in New York
    assert body["last_council"] == {"run_id": run_id, "et_date": "2026-10-26"}
    assert [c["id"] for c in body["t4"]] == [1, 2, 3, 4, 5]
    assert all(c["name"] and c["detail"] for c in body["t4"])
    # conditions 2 and 4 carry no verdict ON PURPOSE — they must read as deferred, not as missing data
    for c in (body["t4"][1], body["t4"][3]):
        assert c["verdict"] is None and c["detail"] == "deferred to operator"
    assert body["system_status_as_of"] == body["as_of"] and body["basis"] == "light"
    server._status_cache.clear()


def test_status_level_and_headline_match_the_snapshot(convexity_db, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    _status_db(convexity_db, monkeypatch)
    with TestClient(server.app) as client:
        light = client.get("/api/status").json()
        snap = client.get("/api/snapshot").json()
        assert light["basis"] == "light"
        assert (light["system_status"]["level"], light["system_status"]["headline"]) == (
            snap["system_status"]["level"], snap["system_status"]["headline"])
        # with a fresh snapshot cached, the status reuses its verdict outright
        server._status_cache.clear()
        again = client.get("/api/status").json()
    assert again["basis"] == "snapshot" and again["system_status"] == snap["system_status"]
    server._status_cache.clear()
    server._snapshot_cache.clear()


def test_status_kill_engaged_overrides_a_green_snapshot_verdict(convexity_db, monkeypatch) -> None:
    """The cached snapshot verdict can be ~a minute old while KILL is read fresh: a just-engaged KILL must
    never sit under the snapshot's green headline."""
    from fastapi.testclient import TestClient

    import dashboard_data as dd

    _status_db(convexity_db, monkeypatch)
    green = {"level": "success", "headline": "🟢 All systems nominal", "issues": []}
    real_header = dd.header_status

    def killed_header(conn, **kw):
        return {**real_header(conn, **kw), "kill_switch_engaged": True}

    monkeypatch.setattr(dd, "header_status", killed_header)
    server._snapshot_cache[(str(dd.resolve_paths(server.load_config())["db_path"]),
                            str(dd.resolve_paths(server.load_config())["cache_dir"]))] = (
        server.time.monotonic(), {"system_status": green})
    with TestClient(server.app) as client:
        body = client.get("/api/status").json()
    assert body["kill"]["switch_engaged"] is True
    assert body["system_status"]["level"] == "error" and "KILL" in " ".join(body["system_status"]["issues"])
    assert body["basis"] == "light" and body["system_status_as_of"] == body["as_of"]
    server._status_cache.clear()
    server._snapshot_cache.clear()


def test_status_reused_verdict_is_stamped_and_not_cached_past_the_snapshot(convexity_db, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    import dashboard_data as dd

    _status_db(convexity_db, monkeypatch)
    paths = dd.resolve_paths(server.load_config())
    key = (str(paths["db_path"]), str(paths["cache_dir"]))
    green = {"level": "success", "headline": "🟢 All systems nominal", "issues": []}
    snap_t = server.time.monotonic() - 40.0          # the snapshot is already 40s into its 60s TTL
    server._snapshot_cache[key] = (snap_t, {"system_status": green})
    with TestClient(server.app) as client:
        body = client.get("/api/status").json()
    assert body["basis"] == "snapshot" and body["system_status"] == green
    assert body["system_status_as_of"] < body["as_of"]
    assert server._status_cache[key][0] == snap_t + server._CACHE_TTL_S   # expires with the snapshot, not +60s
    server._status_cache.clear()
    server._snapshot_cache.clear()


def test_status_one_failing_panel_is_a_warn_not_a_500(convexity_db, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    import dashboard_data as dd

    _status_db(convexity_db, monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("panel exploded")

    monkeypatch.setattr(dd, "council_panel", boom)
    with TestClient(server.app) as client:
        r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["system_status"]["level"] == "warn"
    assert "council" in " ".join(body["system_status"]["issues"])
    server._status_cache.clear()


def test_status_ttl_cache_and_nocache(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    calls = {"n": 0}

    def fake_build(db_path, db_exists, **_k):  # noqa: ANN001 — test stub
        calls["n"] += 1
        return {"n": calls["n"]}

    monkeypatch.setattr(server, "build_status", fake_build)
    server._status_cache.clear()
    server._snapshot_cache.clear()
    with TestClient(server.app) as client:
        assert client.get("/api/status").json() == client.get("/api/status").json()
        assert calls["n"] == 1
        client.get("/api/status?nocache=1")
        assert calls["n"] == 2
    server._status_cache.clear()


def test_status_has_the_same_token_gate_as_snapshot(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setattr(server, "_DASHBOARD_TOKEN", "s3cret")
    monkeypatch.setattr(server, "build_status", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(server, "build_snapshot", lambda *a, **k: {"ok": True})
    server._status_cache.clear()
    server._snapshot_cache.clear()
    with TestClient(server.app) as client:
        for path in ("/api/status", "/api/snapshot"):
            assert client.get(path).status_code == 401
            assert client.get(path, headers={"Authorization": "Bearer nope"}).status_code == 401
            assert client.get(path, headers={"Authorization": "Bearer s3cret"}).status_code == 200
        assert client.get("/api/health").status_code == 200   # liveness stays open
    server._status_cache.clear()
    server._snapshot_cache.clear()


def test_status_without_a_database_fails_soft(monkeypatch, tmp_path) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("DRAMATIC_DB", str(tmp_path / "absent.db"))
    server._status_cache.clear()
    with TestClient(server.app) as client:
        r = client.get("/api/status")
    assert r.status_code == 200 and "error" in r.json()
    server._status_cache.clear()


def test_docs_mention_8601_only_as_retired() -> None:
    """Issue #353: the Streamlit dashboard on :8601 was retired 2026-10-06 — no operator doc may call it live."""
    root = Path(__file__).resolve().parents[2]
    for rel in ("dashboard_web/README.md", "DEPLOYMENT.md", "records/STANDING_STATE.md",
                "scripts/systemd/dramatic-options-web.service"):
        lines = (root / rel).read_text().splitlines()
        for i, ln in enumerate(lines):
            if "8601" in ln:
                near = " ".join(lines[max(0, i - 2): i + 3]).lower()
                assert "retire" in near, f"{rel}:{i + 1} mentions :8601 without saying it is retired"
