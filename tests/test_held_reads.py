"""#464 held-name thesis tracking, Option B (PREREG_COUNCIL_GATE_SEPARATION §10.13): the post-L1 held pass. Offline:
the repo's FakeRouter on the pass's own ledger, FixedClock, injected providers, no network, no wall clock."""

from __future__ import annotations

import dataclasses
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

import post_l1
import risk
import state
from clock import FixedClock
from council import held_reads as hr
from council.context import ContextPack
from council.router import CostEntry, FakeRouter, LLMResponse, RouterError
from themes import Theme

DAY = "2026-12-08"
MARKERS = {"momentum": 0.412, "mom_recent": 0.153, "rel_strength": 0.21, "rv": 0.55, "price": 12.34,
           "adv_usd": 9_876_543.0}


def _config(**held) -> dict:
    return {"council": {"enabled": True, "conviction_floor": "MODERATE", "news_lookback_days": 90,
                        "held_reads": {"enabled": True, "cap_pass_usd": 1.0, **held}},
            "themes_path": "UNUSED"}


@pytest.fixture(autouse=True)
def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


@pytest.fixture
def themes_file(tmp_path):
    p = tmp_path / "themes.json"
    p.write_text(json.dumps({"themes": [
        {"name": "grid_storage", "symbol": "HSDA", "direction": "bullish",
         "thesis": "grid storage demand inflects", "active": False},      # inactive: still read for a held name
        {"name": "other", "symbol": "HSDA", "direction": "bearish", "thesis": "wrong direction", "active": True},
    ]}))
    return str(p)


class _News:
    """A hand-seed's news provider: numeric headlines so the pack is grounded."""

    def headlines_asof(self, symbol, as_of):
        return [{"headline": f"{symbol} orders up 18% on grid demand", "ts": "2026-12-01T12:00:00+00:00"}]


class _Router(FakeRouter):
    """The repo's FakeRouter on the pass's OWN ledger, pricing each call; records every (role, user)."""

    def __init__(self, ledger, *, cost=0.01, fail_symbol=None):
        super().__init__()
        self.ledger, self.cost, self.fail_symbol = ledger, cost, fail_symbol
        self.sent: list[tuple[str, str]] = []

    def call(self, *, role, system, user, max_tokens=None):
        if self.ledger.over_cap:
            from council.router import BudgetExceeded
            raise BudgetExceeded("cap")
        if self.fail_symbol and f"CANDIDATE: {self.fail_symbol} " in user:
            raise RouterError("provider down")
        self.sent.append((role, user))
        text = self._responder(role, system, user)
        self.ledger.record(CostEntry(role, "fake", f"fake-{role}", 0, 0, self.cost))
        return LLMResponse(text, "fake", f"fake-{role}", 0, 0, self.cost)


def _seed(conn, *, status="dormant"):
    """Today's L1 (one of-record proposal) + four positions: a dormant-lineage sentinel, a hand-seed, one with no
    proposal (no_lineage) and a closed one (not tracked). Returns (run_id, {name: position_id})."""
    old_run = state.record_run(conn, mode="PAPER", equity=1)
    sid = state.record_sentinel_candidate(conn, run_id=old_run, as_of="2026-10-01T12:00:00+00:00", symbol="HSDB",
                                          direction="bearish", basket="grid", inflection_score=1.0,
                                          markers=MARKERS, theme="grid_rollover", seed_thesis="skeptic: fading")
    with conn:
        conn.execute("UPDATE sentinel_candidates SET status = ? WHERE id = ?", (status, sid))
    p_sent = state.record_council_proposal(conn, run_id=old_run, as_of="2026-10-02T20:45:00+00:00", theme="g",
                                           symbol="HSDB", direction="bearish", conviction="MODERATE",
                                           sentinel_id=sid)
    p_hand = state.record_council_proposal(conn, run_id=old_run, as_of="2026-10-02T20:45:00+00:00", theme="h",
                                           symbol="HSDA", direction="bullish", conviction="MODERATE")
    pos = {}
    for name, sym, d, pid, st, entry, mark in (("sent", "HSDB", "bearish", p_sent, "open", 1.00, 2.50),
                                               ("hand", "HSDA", "bullish", p_hand, "closing", 4.00, 1.00),
                                               ("nolin", "HSDC", "bullish", None, "open", 2.00, 2.00),
                                               ("closed", "HSDD", "bullish", p_hand, "closed", 2.00, 2.00)):
        pos[name] = state.record_convexity_position(
            conn, run_id=old_run, opened_at="2026-10-03", theme="t", symbol=sym, direction=d, structure_kind="C",
            contract_symbol=f"{sym}270521C00010000", expiry="2027-05-21", strike=10.0, dte=230, moneyness=0.25,
            contracts=1, entry_premium_per_contract=entry, total_premium=entry * 100, status=st, proposal_id=pid)
        with conn:
            conn.execute("UPDATE convexity_positions SET mark = ? WHERE id = ?", (mark, pos[name]))
    run = state.record_run(conn, mode="PAPER", equity=1)
    state.record_council_proposal(conn, run_id=run, as_of=f"{DAY}T20:45:00+00:00", theme="x", symbol="ZZZ",
                                  direction="bullish", conviction="LOW")
    with conn:
        conn.execute("UPDATE runs SET started_at = ?, model_mix = ? WHERE id = ?",
                     (f"{DAY} 20:45:00", json.dumps({"strategist": "fake/fake-strategist", "prompts": "a/b/c"}),
                      run))
    return run, pos


_EXITED = object()


def _pass(conn, *, config, themes_file, unit=_EXITED, routers=None, refresh=None, **router_kw):
    built = routers if routers is not None else []

    def factory(cfg, ledger):
        r = _Router(ledger, **router_kw)
        r.cfg = cfg
        built.append(r)
        return r

    return hr.run_pass(conn, config=config, clock=FixedClock(datetime.fromisoformat(f"{DAY}T21:10:00+00:00")),
                       router_factory=factory, inputs=lambda as_of: hr.PackInputs(news=_News()),
                       refresh=refresh or (lambda cands, as_of: cands),
                       unit_state=lambda: ("inactive", f"{DAY} 20:52:00") if unit is _EXITED else unit,
                       themes_path=themes_file)


def _record_rows(conn):
    return {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY id")]
            for t in ("council_proposals", "council_agent_outputs", "runs", "sentinel_candidates",
                      "convexity_positions", "council_repeat_packs", "council_repeat_reads",
                      "council_repeat_sessions")}


def test_tracked_set_dormant_lineage_hand_seed_and_no_lineage(convexity_db, themes_file):
    run, pos = _seed(convexity_db)
    before = _record_rows(convexity_db)
    routers: list = []
    o = _pass(convexity_db, config=_config(), themes_file=themes_file, routers=routers)
    assert o.status == "done" and o.tracked == 3 and o.read == 2 and o.skipped == {"no_lineage": 1}
    assert _record_rows(convexity_db) == before          # the council of record, runs, sentinels, positions untouched
    rows = {r["position_id"]: r for r in convexity_db.execute("SELECT * FROM held_reads")}
    assert set(rows) == {pos["sent"], pos["hand"]}
    s, h = rows[pos["sent"]], rows[pos["hand"]]
    assert (s["origin"], s["lineage_status"], s["symbol"], s["direction"]) == ("sentinel", "dormant", "HSDB", "bearish")
    assert (h["origin"], h["lineage_status"]) == ("hand-seed", "hand-seed")
    assert s["run_id"] == run and s["as_of"] == f"{DAY}T20:45:00+00:00"
    assert s["conviction"] == "HIGH" and s["include"] == 1 and s["structural_vs_fad"] == "structural"
    assert (s["under_narrated"], s["at_inflection"], s["criteria_veto"]) == (1, 1, 0)
    assert s["strategist_provider"] == "fake" and s["strategist_cost_usd"] == pytest.approx(0.01)
    assert s["cost_usd"] == pytest.approx(0.03) and json.loads(s["model_mix"])["strategist"] == "fake/fake-strategist"
    assert s["mark_multiple"] == pytest.approx(2.5) and h["mark_multiple"] == pytest.approx(0.25)
    assert s["dte"] == (datetime(2027, 5, 21) - datetime(2026, 12, 8)).days
    # the dormant lineage renders as-is (markers, no "dormant" label); the hand-seed uses its INACTIVE themes.json entry
    users = [u for role, u in routers[0].sent if role == "proposer"]
    assert users[0].startswith("CANDIDATE: HSDB bearish grid_rollover") and "momentum_12m +0.412" in users[0]
    assert "dormant" not in users[0].lower()
    assert users[1].startswith("CANDIDATE: HSDA bullish grid_storage") and "grid storage demand inflects" in users[1]
    # the pass's own full-council router, capped at cap_pass_usd
    assert routers[0].ledger.cap_usd == pytest.approx(1.0)


def test_one_pass_per_l1_run(convexity_db, themes_file):
    _seed(convexity_db)
    assert _pass(convexity_db, config=_config(), themes_file=themes_file).read == 2
    routers: list = []
    o = _pass(convexity_db, config=_config(), themes_file=themes_file, routers=routers)
    assert o.status == "refused" and o.skipped == {"already_read": 2, "no_lineage": 1} and routers == []
    assert convexity_db.execute("SELECT COUNT(*) FROM held_reads").fetchone()[0] == 2


def test_markers_are_refreshed_with_the_l1_function(convexity_db, themes_file):
    _seed(convexity_db, status="candidate")
    seen = []

    def refresh(cands, as_of):
        seen.append((tuple(c.symbol for c in cands), as_of))
        return [dataclasses.replace(c, markers={**c.markers, "momentum": -0.999}) if c.source == "sentinel" else c
                for c in cands]

    routers: list = []
    _pass(convexity_db, config=_config(), themes_file=themes_file, routers=routers, refresh=refresh)
    assert seen == [(("HSDB", "HSDA"), datetime.fromisoformat(f"{DAY}T20:45:00+00:00"))]
    assert "momentum_12m -0.999" in routers[0].sent[0][1]
    assert convexity_db.execute("SELECT lineage_status FROM held_reads WHERE symbol='HSDB'").fetchone()[0] == \
        "candidate"


def test_cap_stops_the_pass(convexity_db, themes_file):
    _seed(convexity_db)
    o = _pass(convexity_db, config=_config(cap_pass_usd=0.5), themes_file=themes_file, cost=0.2)
    # 0, .2, .4 → three calls (one full debate), then the next call is over $0.50
    assert o.status == "stopped_cap" and o.read == 1 and o.cost_usd == pytest.approx(0.6)
    assert convexity_db.execute("SELECT COUNT(*) FROM held_reads").fetchone()[0] == 1


def test_provider_error_drops_only_that_name(convexity_db, themes_file):
    _seed(convexity_db)
    o = _pass(convexity_db, config=_config(), themes_file=themes_file, fail_symbol="HSDB")
    assert o.status == "done" and o.read == 1 and o.skipped["provider_error"] == 1


@pytest.mark.parametrize("unit", [("activating", f"{DAY} 20:45:00"), ("inactive", "2026-12-07 20:52:00"), None])
def test_refuses_until_todays_l1_finished(convexity_db, themes_file, unit):
    _seed(convexity_db)
    routers: list = []
    o = _pass(convexity_db, config=_config(), themes_file=themes_file, unit=unit, routers=routers)
    assert o.status == "refused" and "has not finished" in o.reason and routers == []
    assert convexity_db.execute("SELECT COUNT(*) FROM held_reads").fetchone()[0] == 0


def test_skipped_under_kill(convexity_db, themes_file, monkeypatch):
    _seed(convexity_db)
    monkeypatch.setenv("KILL", "1")
    routers: list = []
    o = _pass(convexity_db, config=_config(), themes_file=themes_file, routers=routers)
    assert o.status == "refused" and "KILL" in o.reason and routers == []


def test_disabled_and_no_council_today_refuse(convexity_db, themes_file):
    _seed(convexity_db)
    assert _pass(convexity_db, config=_config(enabled=False), themes_file=themes_file).reason == \
        "council.held_reads.enabled is false"
    with convexity_db:
        convexity_db.execute("UPDATE council_proposals SET as_of = '2026-12-07T20:45:00+00:00' WHERE symbol='ZZZ'")
    assert _pass(convexity_db, config=_config(), themes_file=themes_file).reason == "no council of record for " \
        "2026-12-08 ET"


def test_the_pack_never_says_the_name_is_held(convexity_db, themes_file):
    names = {f.name.lower() for f in dataclasses.fields(ContextPack)}
    forbidden = re.compile(r"held|position|entry|mark(?!er)|pnl|p_l|premium|multiple|dte|expir|contract|strike|cost")
    assert not [n for n in names if forbidden.search(n)], names
    _seed(convexity_db)
    with convexity_db:   # distinctive position numbers that must never reach a prompt
        convexity_db.execute("UPDATE convexity_positions SET entry_premium_per_contract = 7.7123, mark = 3.1987, "
                             "total_premium = 771.23, strike = 13.579")
    routers: list = []
    _pass(convexity_db, config=_config(), themes_file=themes_file, routers=routers)
    sent = "\n".join(u for _r, u in routers[0].sent)
    for token in ("7.7123", "3.1987", "771.23", "13.579", "0.4147", "270521", "2027-05-21"):
        assert token not in sent, token
    # The pack block (the proposer's whole user text) says nothing about holding; the adversary template's own
    # "AGAINST a <direction> position" wording is the same on every of-record read, so it is not checked here.
    packs = "\n".join(u for r, u in routers[0].sent if r == "proposer")
    assert packs and not re.search(r"\b(held|holding|position|entry price|P&L|mark)\b", packs, re.I)


def test_month_spend_includes_held_reads(convexity_db, themes_file, tmp_path):
    _seed(convexity_db)
    _pass(convexity_db, config=_config(), themes_file=themes_file)
    now = datetime(2026, 12, 20, tzinfo=UTC)
    # two reads × 3 roles × $0.01, all attributed to provider "fake" (the council of record's rows cost nothing here)
    assert state.provider_month_spend(convexity_db, "fake", now=now) == pytest.approx(0.06)
    with convexity_db:
        convexity_db.execute("UPDATE held_reads SET strategist_provider = 'anthropic'")
    assert state.provider_month_spend(convexity_db, "fake", now=now) == pytest.approx(0.04)
    assert state.provider_month_spend(convexity_db, "anthropic", now=now) == pytest.approx(0.02)
    assert state.provider_month_spend(convexity_db, "anthropic", now=datetime(2027, 1, 2, tzinfo=UTC)) == 0.0


def test_lineage_candidate_hand_seed_without_an_entry_is_no_lineage(convexity_db):
    _run, pos = _seed(convexity_db)
    row = convexity_db.execute("SELECT * FROM convexity_positions WHERE id = ?", (pos["hand"],)).fetchone()
    assert hr.lineage_candidate(convexity_db, row, []) == "no_lineage"
    got = hr.lineage_candidate(convexity_db, row, [Theme("n", "hsda", "bullish", "t", active=False)])
    assert got[1:] == ("hand-seed", "hand-seed")


def test_held_pass_is_registered_after_the_probe_and_independent(monkeypatch, caplog):
    """In --post-l1 a raising repeat probe does not stop the held pass (and vice versa); exit 1 either way."""
    ran = []

    def probe_boom(cfg):
        ran.append("probe")
        raise RuntimeError("probe broke")

    monkeypatch.setattr("council.repeat_probe.run_live", probe_boom)
    monkeypatch.setattr("council.held_reads.run_live", lambda cfg: ran.append("held"))
    with caplog.at_level(logging.ERROR, logger="post_l1"):
        assert post_l1.run({}) == 1
    assert ran == ["probe", "held"]

    ran.clear()
    monkeypatch.setattr("council.repeat_probe.run_live", lambda cfg: ran.append("probe"))
    monkeypatch.setattr("council.held_reads.run_live", lambda cfg: (_ for _ in ()).throw(RuntimeError("held")))
    assert post_l1.run({}) == 1 and ran == ["probe"]
    monkeypatch.setattr("council.held_reads.run_live", lambda cfg: ran.append("held"))
    assert post_l1.run({}) == 0


def test_shipped_config_is_on_with_the_pinned_cap():
    cfg = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text())["council"]["held_reads"]
    assert cfg["enabled"] is True and cfg["cap_pass_usd"] == 1.0
    assert "§10.13" in cfg["_comment"] and "2026-11-16" in cfg["_comment"]


def test_migration_is_idempotent(convexity_db):
    import conftest

    conftest._apply_migration(convexity_db, "0023_held_reads.py")
    assert convexity_db.execute("SELECT name FROM sqlite_master WHERE name='held_reads'").fetchone()


# ── run_live: the real wiring, external clients faked ──────────────────────────────────────────────────────────

class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class _AnalystSession:
    """stockanalysis.com's __data.json shape: analystChart buckets summing to 7."""

    calls: list = []

    def get(self, url, **kw):
        _AnalystSession.calls.append(url)
        flat = [{"analystChart": 1}, {"strongBuy": 2, "buy": 3, "hold": 4, "sell": 5}, 2, 3, 1, 1]
        return _Resp({"type": "data", "nodes": [{"type": "data", "data": flat}]})


def _live_setup(convexity_db, tmp_path, monkeypatch, themes_file):
    """run_live on the test DB with only the external edges faked: Alpaca client, the analyst HTTP session, the
    LLM router. Returns (config, built routers)."""
    import requests

    import data.alpaca_client

    _seed(convexity_db, status="dormant")
    with convexity_db:   # only the sentinel position is held (its pack carries the analyst line)
        convexity_db.execute("UPDATE convexity_positions SET status = 'closed' WHERE symbol != 'HSDB'")
    cfg = _config()
    cfg.update({"themes_path": themes_file, "cache": {"dir": str(tmp_path / "cache")},
                "alpaca": {"api_key": "k", "secret_key": "s", "paper": True}, "data_feed": {"equity_bars": "iex"},
                "llm_keys": {}})
    built: list = []
    monkeypatch.setattr(data.alpaca_client, "AlpacaClient", lambda *a, **k: object())
    monkeypatch.setattr(requests, "Session", _AnalystSession)
    monkeypatch.setattr("council.router.build_router",
                        lambda c, keys, ledger=None: built.append(_Router(ledger)) or built[-1])

    class _NoClose:
        def __init__(self, c):
            self._c = c

        def __getattr__(self, k):
            return getattr(self._c, k)

        def close(self):
            pass

        def __enter__(self):
            return self._c.__enter__()

        def __exit__(self, *a):
            return self._c.__exit__(*a)

    monkeypatch.setattr(state, "get_db", lambda c: _NoClose(convexity_db))
    monkeypatch.setattr(hr, "read_unit_state", lambda: ("inactive", f"{DAY} 20:52:00"))
    return cfg, built


def test_run_live_pack_carries_the_analyst_count(convexity_db, tmp_path, monkeypatch, themes_file):
    """#507 blocker: the providers must be built at the L1 council's as_of. Built at the pass's own time (16:10 ET)
    the analyst snapshot is stamped after the 15:45 as_of, the read finds nothing and the pack says "unknown"."""
    cfg, built = _live_setup(convexity_db, tmp_path, monkeypatch, themes_file)
    before = _record_rows(convexity_db)
    o = hr.run_live(cfg, clock=FixedClock(datetime.fromisoformat(f"{DAY}T21:10:00+00:00")))
    assert o.status == "done" and o.read == 1
    pack = next(u for role, u in built[0].sent if role == "proposer")
    assert "ANALYST_COVERAGE: 7 analyst(s) covering" in pack, pack
    assert "ANALYST_COVERAGE: unknown" not in pack
    assert built[0].ledger.cap_usd == pytest.approx(1.0) and len(built) == 1   # only the pass's own router
    assert _record_rows(convexity_db) == before                                 # writes held_reads only
    row = convexity_db.execute("SELECT * FROM held_reads").fetchone()
    assert row["as_of"] == f"{DAY}T20:45:00+00:00" and row["lineage_status"] == "dormant"


def test_run_live_refuses_before_building_anything(convexity_db, tmp_path, monkeypatch, themes_file):
    cfg, built = _live_setup(convexity_db, tmp_path, monkeypatch, themes_file)
    import data.alpaca_client

    monkeypatch.setattr(data.alpaca_client, "AlpacaClient",
                        lambda *a, **k: pytest.fail("Alpaca client built before the refusals"))
    for clock_day, unit, why in (("2026-12-09", ("inactive", f"{DAY} 20:52:00"), "no council of record"),
                                 (DAY, ("activating", f"{DAY} 20:45:00"), "has not finished")):
        monkeypatch.setattr(hr, "read_unit_state", lambda u=unit: u)
        o = hr.run_live(cfg, clock=FixedClock(datetime.fromisoformat(f"{clock_day}T21:10:00+00:00")))
        assert o.status == "refused" and why in o.reason
    monkeypatch.setenv("KILL", "1")
    assert "KILL" in hr.run_live(cfg, clock=FixedClock(datetime.fromisoformat(f"{DAY}T21:10:00+00:00"))).reason
    assert built == []


def test_run_live_marker_refresh_is_the_l1_function_without_a_run_note(convexity_db, tmp_path, monkeypatch,
                                                                        themes_file):
    import orchestrator

    cfg, built = _live_setup(convexity_db, tmp_path, monkeypatch, themes_file)
    seen = []
    real = orchestrator._refresh_council_markers

    def spy(conn, cands, **kw):
        seen.append(kw["run_id"])
        return real(conn, cands, **kw)

    monkeypatch.setattr(orchestrator, "_refresh_council_markers", spy)
    notes = [r[0] for r in convexity_db.execute("SELECT note FROM runs ORDER BY id")]
    hr.run_live({**cfg, "council": {**cfg["council"], "marker_refresh": "both"}},
                clock=FixedClock(datetime.fromisoformat(f"{DAY}T21:10:00+00:00")))
    assert seen == [None]
    assert [r[0] for r in convexity_db.execute("SELECT note FROM runs ORDER BY id")] == notes


def test_l1_marker_refresh_with_run_id_none_writes_no_note(convexity_db):
    import orchestrator

    rid = state.record_run(convexity_db, mode="PAPER", equity=1, note="n")
    cfg = {"council": {"marker_refresh": "both"}, "data_feed": {"equity_bars": "iex"}}
    out = orchestrator._refresh_council_markers(convexity_db, [], config=cfg, client=object(), cache=object(),
                                                as_of=datetime(2026, 12, 8, tzinfo=UTC), run_id=None)
    assert out == []
    assert convexity_db.execute("SELECT note FROM runs WHERE id = ?", (rid,)).fetchone()[0] == "n"


def test_hand_seed_with_two_matching_entries_warns(convexity_db, caplog):
    _run, pos = _seed(convexity_db)
    row = convexity_db.execute("SELECT * FROM convexity_positions WHERE id = ?", (pos["hand"],)).fetchone()
    two = [Theme("first", "HSDA", "bullish", "t1"), Theme("second", "HSDA", "bullish", "t2")]
    with caplog.at_level(logging.WARNING, logger="council.held_reads"):
        got = hr.lineage_candidate(convexity_db, row, two)
    assert got[0].name == "first" and any("2 themes.json entries match" in r.getMessage() for r in caplog.records)
