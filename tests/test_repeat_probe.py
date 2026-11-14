"""#456 council repeat-read probe, Arm A (PREREG_COUNCIL_GATE_SEPARATION §10.12): the default-off capture in the
council path, the shared §10.7 coercion, the probe's refusals/caps/exclusions, the MTD change and the unit. Offline:
FakeRouter (subclassed only to price calls / answer as the understudy), FixedClock, no network, no wall clock."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import logging
import random
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import risk
import state
from clock import FixedClock
from council import repeat_probe as rp
from council.context import ContextPack, synthetic_context_pack
from council.debate import coerce_tri_criteria, run_candidate
from council.repeat_capture import capture_record, pack_from_json, pack_to_json, prompt_sha256
from council.router import CostEntry, FakeRouter, LLMResponse, _default_fake_responder
from council.wiring import council_to_themes
from themes import Theme

REPO = Path(__file__).resolve().parent.parent
MIX_BASE = {"proposer": "fake/fake-proposer", "adversary": "fake/fake-adversary",
            "strategist": "fake/fake-strategist", "quote_filter": "musd_billions_v1+iso_dates_v1+restate_v1"}
PROBE = {"enabled": True, "k": 5, "sessions": 10, "segment_start_et": "2026-12-07", "cap_session_usd": 1.5,
         "cap_total_usd": 15.0, "page_refusal_fraction": 0.8}
CANDS = [Theme("copper_electrification", "FCX", "bullish", "unloved industrial tailwind"),
         Theme("grid_buildout", "PWR", "bullish", "grid capex"),
         Theme("legacy_rollover", "XYZ", "bearish", "secular demand rollover")]
# Mon 2026-12-07 → Fri 2026-12-18: the pinned 10-session segment (no NYSE holiday), then the 11th weekday.
SEGMENT_DAYS = ["2026-12-07", "2026-12-08", "2026-12-09", "2026-12-10", "2026-12-11",
                "2026-12-14", "2026-12-15", "2026-12-16", "2026-12-17", "2026-12-18"]


def _config(probe: dict | None = None, **council) -> dict:
    c = {"enabled": True, "conviction_floor": "MODERATE", "max_candidates": 50, "news_lookback_days": 90,
         "roles": {"proposer": {"provider": "fake", "model": "fake-proposer"},
                   "adversary": {"provider": "fake", "model": "fake-adversary"},
                   "strategist": {"provider": "fake", "model": "fake-strategist"}},
         "roles_fallback": {"strategist": {"provider": "under", "model": "understudy-1"}},
         "monthly_spend_page_usd": {"fake": 100.0},
         "repeat_probe": dict(PROBE if probe is None else probe)}
    c.update(council)
    return {"council": c}


def _mix(**over) -> dict:
    return {**MIX_BASE, "prompts": f"aaaa/bbbb/{rp.strategist_prompt_hash16()}", **over}


@pytest.fixture(autouse=True)
def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


class _Recording(FakeRouter):
    """FakeRouter that records every (role, system, user) it is sent."""

    def __init__(self, responder=None):
        super().__init__(responder)
        self.sent: list[tuple[str, str, str]] = []

    def call(self, *, role, system, user, max_tokens=None):
        self.sent.append((role, system, user))
        return super().call(role=role, system=system, user=user, max_tokens=max_tokens)


class _ProbeRouter(FakeRouter):
    """The probe's router in tests: the repo's FakeRouter on the probe's OWN ledger, pricing each call and optionally
    answering a given call index as the understudy or with unparseable text."""

    def __init__(self, ledger, *, cost=0.02, understudy_at=(), garbage_at=(), responder=None):
        super().__init__(responder)
        self.ledger = ledger
        self.cost, self.understudy_at, self.garbage_at = cost, set(understudy_at), set(garbage_at)
        self.sent: list[tuple[str, str, str]] = []

    def provider_model(self, role):
        return ("fake", f"fake-{role}")

    def call(self, *, role, system, user, max_tokens=None):
        if self.ledger.over_cap:
            from council.router import BudgetExceeded
            raise BudgetExceeded(f"cap {self.ledger.cap_usd} reached")
        i = len(self.sent)
        self.sent.append((role, system, user))
        prov, model = ("under", "understudy-1") if i in self.understudy_at else ("fake", f"fake-{role}")
        text = "no json at all" if i in self.garbage_at else self._responder(role, system, user)
        self.ledger.record(CostEntry(role, prov, model, 0, 0, self.cost))
        return LLMResponse(text, prov, model, 0, 0, self.cost)


def _l1(conn, day: str, *, config: dict, cands=CANDS, mix: dict | None = None, responder=None, seed=7):
    """One L1 council of record on ET ``day`` (20:45 UTC = 15:45 ET in December) + its runs stamps. Returns
    (run_id, the L1 router)."""
    clock = FixedClock(datetime.fromisoformat(f"{day}T20:45:00+00:00"))
    run_id = state.record_run(conn, mode="PAPER", equity=100_000.0, note="paper cycle")
    router = _Recording(responder)
    council_to_themes(conn, candidates=list(cands), router=router, config=config, clock=clock, demo=True,
                      run_id=run_id, rng=random.Random(seed))
    with conn:
        conn.execute("UPDATE runs SET started_at = ?, model_mix = ?, council_health = 'ok' WHERE id = ?",
                     (f"{day} 20:45:00", json.dumps(mix or _mix()), run_id))
    return run_id, router


_EXITED = object()


def _probe(conn, day: str, *, config: dict, unit=_EXITED, routers: list | None = None, notify=None, **router_kw):
    clock = FixedClock(datetime.fromisoformat(f"{day}T21:10:00+00:00"))
    unit = ("inactive", f"{day} 20:52:00") if unit is _EXITED else unit
    built = routers if routers is not None else []

    def factory(cfg, ledger):
        r = _ProbeRouter(ledger, **router_kw)
        r.cfg = cfg
        built.append(r)
        return r

    return rp.run_probe(conn, config=config, clock=clock, router_factory=factory, unit_state=lambda: unit,
                        notify_send=notify or (lambda *a, **k: True))


def _fresh_db(path, skip=()):
    """A second migrated DB, built exactly like conftest's ``convexity_db`` (optionally without some migrations)."""
    import conftest

    conn = state.connect(path)
    for name in ("0001_initial.py", "0003_convexity.py", "0004_convexity_mtm.py", "0005_council.py",
                 "0006_close_side.py", "0007_sentinels.py", "0008_shadow_book.py", "0009_frame_version.py",
                 "0010_fixed_basket.py", "0011_council_health.py", "0012_shares_basket.py", "0013_data_feed.py",
                 "0014_gate_dualread.py", "0015_discovery_funnel.py", "0016_marker_asof.py",
                 "0017_cheapness_watch.py", "0018_null_book_attempts.py", "0020_agent_flag_details.py",
                 "0021_vertical_legs.py", "0022_council_repeat_probe.py"):
        if name not in skip:
            conftest._apply_migration(conn, name)
    return conn


def _rows(conn, table: str) -> list[tuple]:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})") if r[1] != "created_at"]
    return [tuple(r) for r in conn.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY id")]


# ── 1. the capture: default off is byte-identical; on, it writes only council_repeat_packs ─────────────────────────

def test_flag_off_council_is_byte_identical_and_captures_nothing(tmp_path, convexity_db, monkeypatch):
    off = _config(probe={**PROBE, "enabled": False})
    on = _config()
    # Flag off never reaches the capture code at all: a capture that would raise is never called.
    import council.repeat_capture as rc

    calls = []
    real = rc.capture_record
    monkeypatch.setattr(rc, "capture_record", lambda *a: calls.append(a) or real(*a))
    rid_off, r_off = _l1(convexity_db, "2026-12-08", config=off)
    assert calls == []

    conn_on = _fresh_db(tmp_path / "on.db")
    rid_on, r_on = _l1(conn_on, "2026-12-08", config=on)
    try:
        # Every prompt byte the council sent is identical with the capture on or off.
        assert r_off.sent == r_on.sent and len(r_on.sent) == 9
        # The council of record is identical row for row.
        for table in ("council_proposals", "council_agent_outputs"):
            assert _rows(convexity_db, table) == _rows(conn_on, table), table
        assert convexity_db.execute("SELECT COUNT(*) FROM council_repeat_packs").fetchone()[0] == 0
        packs = conn_on.execute("SELECT * FROM council_repeat_packs ORDER BY proposal_id").fetchall()
        assert [p["symbol"] for p in packs] == ["FCX", "PWR", "XYZ"]
        assert len(calls) == 3
        # The captured hash is the sha256 of the exact strategist user text the L1 sent.
        sent_strat = [u for role, _s, u in r_on.sent if role == "strategist"]
        assert [p["prompt_sha256"] for p in packs] == [hashlib.sha256(u.encode()).hexdigest() for u in sent_strat]
        assert all(p["run_id"] == rid_on for p in packs)
    finally:
        conn_on.close()


def test_flag_off_needs_no_probe_table(tmp_path, monkeypatch):
    """A DB without migration 0022 runs the council exactly as before when the flag is off."""
    conn = _fresh_db(tmp_path / "old.db", skip=("0022_council_repeat_probe.py",))
    try:
        _l1(conn, "2026-12-08", config=_config(probe={**PROBE, "enabled": False}))
        assert conn.execute("SELECT COUNT(*) FROM council_proposals").fetchone()[0] == 3
    finally:
        conn.close()


def test_capture_error_is_fail_soft(convexity_db, monkeypatch, caplog):
    import council.repeat_capture as rc

    monkeypatch.setattr(rc, "capture_record", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    with caplog.at_level(logging.WARNING):
        _l1(convexity_db, "2026-12-08", config=_config())
    assert convexity_db.execute("SELECT COUNT(*) FROM council_proposals").fetchone()[0] == 3
    assert convexity_db.execute("SELECT COUNT(*) FROM council_agent_outputs").fetchone()[0] == 9
    assert convexity_db.execute("SELECT COUNT(*) FROM council_repeat_packs").fetchone()[0] == 0
    assert sum("repeat-probe capture failed" in r.getMessage() for r in caplog.records) == 3


def test_capture_persist_error_is_fail_soft(convexity_db, caplog):
    with convexity_db:
        convexity_db.execute("DROP TABLE council_repeat_packs")
    with caplog.at_level(logging.WARNING):
        _rid, _r = _l1(convexity_db, "2026-12-08", config=_config())
    assert convexity_db.execute("SELECT COUNT(*) FROM council_proposals").fetchone()[0] == 3
    assert convexity_db.execute("SELECT COUNT(*) FROM council_agent_outputs").fetchone()[0] == 9
    assert sum("capture not persisted" in r.getMessage() for r in caplog.records) == 3


def test_capture_skips_a_proposer_abstention():
    """A proposer NEUTRAL never reaches the strategist: no capture (it is not probed)."""

    def responder(role, system, user):
        if role == "proposer":
            return json.dumps({"confidence": "NEUTRAL"})
        return _default_fake_responder(role, system, user)

    sink: dict = {}
    pack = synthetic_context_pack(CANDS[0], as_of=datetime(2026, 12, 8, 20, 45, tzinfo=UTC))
    p = run_candidate(CANDS[0], pack, FakeRouter(responder), rng=random.Random(1), repeat_capture=sink)
    assert p.conviction == "NEUTRAL" and sink == {}


def _rich_pack() -> ContextPack:
    return ContextPack(
        symbol="FCX", theme="copper", direction="bullish", operator_thesis="copper is short",
        headlines=["FCX up 3% on grid demand", "momentum_12m +0.412"], coverage_count=2, has_numeric=True,
        as_of=datetime(2026, 12, 8, 15, 45, tzinfo=ZoneInfo("America/New_York")), notes=["n1"],
        fundamentals=[{"concept": "revenue", "metric": "ttm_yoy", "value": 0.123, "latest_musd": 33550.0,
                       "base_musd": 29870.5, "period_end": "2026-09-30", "filed": "2026-11-05"},
                      {"concept": "revenue", "metric": "qtr_yoy_accel", "value": -0.0412, "latest_musd": None,
                       "base_musd": None, "period_end": "2026-09-30", "filed": "2026-11-05"}],
        fundamentals_status="ok", analyst_count=0, origin="sentinel",
        forward_catalysts=[{"class": "a", "claim": "IRA credit", "source": "IRS", "event_date": "2027-01-01",
                            "as_of": "2026-11-01", "symbol": "FCX"}],
        framer_summary="skeptic says ü", register_theme="grid", operator_falsifier="by 2027-06-30",
        coverage_unknown=True)


def test_pack_round_trips_losslessly():
    pack = _rich_pack()
    back = pack_from_json(pack_to_json(pack))
    assert back == pack
    assert back.as_prompt_block() == pack.as_prompt_block()
    assert back.as_of.isoformat() == "2026-12-08T15:45:00-05:00"
    for f in dataclasses.fields(ContextPack):
        assert getattr(back, f.name) == getattr(pack, f.name), f.name
    # The capture checks the round trip and hashes the exact text it was given.
    cap = capture_record(pack, "user text")
    assert cap["prompt_sha256"] == hashlib.sha256(b"user text").hexdigest()
    assert pack_from_json(cap["pack_json"]) == pack


def test_capture_refuses_a_pack_that_does_not_round_trip():
    bad = dataclasses.replace(_rich_pack(), fundamentals=[{"concept": "revenue", "metric": "ttm_yoy",
                                                          "value": 0.1, "period_end": ("2026", "09")}])
    with pytest.raises(ValueError):
        capture_record(bad, "u")


def test_stored_capture_rebuilds_the_record_prompt(convexity_db):
    """The probe's rebuild (captured pack + stored raws + recorded order) is the L1's strategist text, byte for byte."""
    rid, router = _l1(convexity_db, "2026-12-08", config=_config())
    sent = {u.splitlines()[0]: u for role, _s, u in router.sent if role == "strategist"}
    from collections import Counter

    names, captured = rp._eligible_names(convexity_db, rid, "fake/fake-strategist", Counter())
    assert captured == 3 and len(names) == 3
    for n in names:
        assert n.user == sent[n.user.splitlines()[0]]
        assert prompt_sha256(n.user) == n.prompt_sha256


# ── 2. the shared §10.7 coercion is byte-neutral for the record ───────────────────────────────────────────────────

def _reference_inline(sraw: dict, praw: dict, symbol: str, log) -> None:
    """The pre-extraction inline block of run_candidate (main@ed4b64f council/debate.py:122-136), verbatim."""
    sf_resolved = sraw.get("structural_vs_fad") or praw.get("structural_vs_fad")
    tri_pass = (str(sf_resolved) == "structural"
                and sraw.get("under_narrated") is True and sraw.get("at_inflection") is True)
    if bool(sraw.get("include", False)) and not tri_pass:
        sraw["include"] = False
        sraw["criteria_veto"] = True
        sraw["criteria_veto_reason"] = (
            f"include=true but tri-criteria fail (s/f={sf_resolved} "
            f"u_narr={sraw.get('under_narrated')} at_infl={sraw.get('at_inflection')})")
        log.info("council criteria-veto %s: %s", symbol, sraw["criteria_veto_reason"])


_ABSENT = object()


def _cases():
    vals_bool = (True, False, None, "true", 1, _ABSENT)
    for inc in (True, False, None, "true", _ABSENT):
        for s_sf in ("structural", "fad", None, "", _ABSENT):
            for p_sf in ("structural", "fad", None, _ABSENT):
                for un in vals_bool:
                    for ai in vals_bool:
                        sraw = {"conviction": "MODERATE", "summary": "s"}
                        for k, v in (("include", inc), ("structural_vs_fad", s_sf), ("under_narrated", un),
                                     ("at_inflection", ai)):
                            if v is not _ABSENT:
                                sraw[k] = v
                        praw = {} if p_sf is _ABSENT else {"structural_vs_fad": p_sf}
                        yield sraw, praw


def test_coercion_helper_is_lock_step_with_the_inline_record_code(caplog):
    ref_log = logging.getLogger("council.debate")
    n = vetoes = 0
    for sraw, praw in _cases():
        a, b = copy.deepcopy(sraw), copy.deepcopy(sraw)
        caplog.clear()
        with caplog.at_level(logging.INFO, logger="council.debate"):
            _reference_inline(a, praw, "SYM", ref_log)
        ref_msgs = [r.getMessage() for r in caplog.records]
        caplog.clear()
        with caplog.at_level(logging.INFO, logger="council.debate"):
            out = coerce_tri_criteria(b, praw, "SYM")
        assert out is b
        assert json.dumps(b, sort_keys=True, default=repr) == json.dumps(a, sort_keys=True, default=repr), (sraw, praw)
        assert [r.getMessage() for r in caplog.records] == ref_msgs
        n += 1
        vetoes += bool(a.get("criteria_veto"))
    assert n == 5 * 5 * 4 * 6 * 6 and 0 < vetoes < n   # both branches exercised, criteria_veto cases included


# ── 3. the probe ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_probe_writes_only_its_own_tables_and_replays_the_record_prompt(convexity_db):
    cfg = _config()
    rid, l1 = _l1(convexity_db, "2026-12-08", config=cfg)
    before = {t: _rows(convexity_db, t) for t in ("council_proposals", "council_agent_outputs", "runs")}
    routers: list = []
    o = _probe(convexity_db, "2026-12-08", config=cfg, routers=routers)
    assert o.status == "done" and o.names_probed == 3 and o.repeats == 15 and o.excluded == {}
    for t, rows in before.items():
        assert _rows(convexity_db, t) == rows, t
    reads = convexity_db.execute("SELECT * FROM council_repeat_reads ORDER BY id").fetchall()
    assert len(reads) == 15 and {r["repeat_idx"] for r in reads} == {0, 1, 2, 3, 4}
    assert all(r["excluded_reason"] is None and r["conviction"] == "HIGH" and r["include"] == 1 for r in reads)
    # The probe sent the record's exact system + user text, strategist only, via its own strategist-only router.
    l1_strat = [(s, u) for role, s, u in l1.sent if role == "strategist"]
    assert routers[0].sent == [("strategist", s, u) for s, u in l1_strat for _ in range(5)]
    assert set(routers[0].cfg["council"]["roles"]) == {"strategist"}
    assert routers[0].ledger.cap_usd == pytest.approx(1.5)
    sess = convexity_db.execute("SELECT * FROM council_repeat_sessions").fetchall()
    assert len(sess) == 1 and sess[0]["status"] == "done" and sess[0]["repeats"] == 15
    assert sess[0]["cost_usd"] == pytest.approx(0.30)
    # Re-running the same evening refuses (one probe session per council of record).
    assert _probe(convexity_db, "2026-12-08", config=cfg).reason == f"run #{rid} already probed"


def test_probe_applies_the_record_post_processing(convexity_db):
    """A repeat claiming include=true with a criterion false is coerced (criteria_veto), like the record."""
    cfg = _config()
    _l1(convexity_db, "2026-12-08", config=cfg, cands=CANDS[:1])

    def resp(role, system, user):
        d = json.loads(_default_fake_responder(role, system, user))
        d["at_inflection"] = False
        return json.dumps(d)

    o = _probe(convexity_db, "2026-12-08", config=cfg, responder=resp)
    assert o.status == "done"
    r = convexity_db.execute("SELECT * FROM council_repeat_reads LIMIT 1").fetchone()
    assert r["include"] == 0 and r["criteria_veto"] == 1 and r["at_inflection"] == 0
    assert json.loads(r["raw"])["criteria_veto_reason"].startswith("include=true but tri-criteria fail")


def test_hash_mismatch_is_skipped_and_counted(convexity_db):
    cfg = _config()
    rid, _ = _l1(convexity_db, "2026-12-08", config=cfg)
    pid = convexity_db.execute("SELECT proposal_id FROM council_repeat_packs WHERE symbol='PWR'").fetchone()[0]
    with convexity_db:
        convexity_db.execute("UPDATE council_repeat_packs SET prompt_sha256 = ? WHERE proposal_id = ?", ("0" * 64, pid))
    o = _probe(convexity_db, "2026-12-08", config=cfg)
    assert o.skipped == {"hash_mismatch": 1} and o.names_probed == 2 and o.repeats == 10
    assert convexity_db.execute("SELECT COUNT(*) FROM council_repeat_reads WHERE proposal_id = ?",
                                (pid,)).fetchone()[0] == 0


def test_understudy_and_parse_error_repeats_are_excluded(convexity_db):
    cfg = _config()
    _l1(convexity_db, "2026-12-08", config=cfg, cands=CANDS[:1])
    o = _probe(convexity_db, "2026-12-08", config=cfg, understudy_at={1}, garbage_at={3})
    assert o.status == "done" and o.repeats == 5
    assert o.excluded == {"understudy": 1, "parse_error": 1}
    rows = {r["repeat_idx"]: r for r in convexity_db.execute("SELECT * FROM council_repeat_reads")}
    assert rows[1]["excluded_reason"] == "understudy" and rows[1]["provider"] == "under"
    assert rows[3]["excluded_reason"] == "parse_error" and rows[3]["conviction"] == "NEUTRAL"
    assert [rows[i]["excluded_reason"] for i in (0, 2, 4)] == [None, None, None]


def test_record_by_the_understudy_is_not_probed(convexity_db):
    cfg = _config()
    _l1(convexity_db, "2026-12-08", config=cfg, cands=CANDS[:2])
    with convexity_db:
        convexity_db.execute("UPDATE council_agent_outputs SET provider='under', model='understudy-1' "
                             "WHERE role='strategist' AND proposal_id = (SELECT MIN(proposal_id) "
                             "FROM council_repeat_packs)")
    o = _probe(convexity_db, "2026-12-08", config=cfg)
    assert o.skipped == {"record_understudy": 1} and o.names_probed == 1


def test_per_session_cap_stops_the_session(convexity_db):
    cfg = _config()
    _l1(convexity_db, "2026-12-08", config=cfg)
    o = _probe(convexity_db, "2026-12-08", config=cfg, cost=0.4)   # 0, .4, .8, 1.2 → the 5th call is over $1.50
    assert o.status == "stopped_session_cap" and o.repeats == 4 and o.cost_usd == pytest.approx(1.6)
    assert convexity_db.execute("SELECT status FROM council_repeat_sessions").fetchone()[0] == "stopped_session_cap"


def test_segment_cap_bounds_the_session_and_then_refuses(convexity_db):
    cfg = _config(probe={**PROBE, "cap_total_usd": 1.0})
    _l1(convexity_db, "2026-12-08", config=cfg)
    routers: list = []
    o = _probe(convexity_db, "2026-12-08", config=cfg, cost=0.4, routers=routers)
    assert routers[0].ledger.cap_usd == pytest.approx(1.0)
    assert o.status == "stopped_segment_cap" and o.repeats == 3
    _l1(convexity_db, "2026-12-09", config=cfg)
    o2 = _probe(convexity_db, "2026-12-09", config=cfg, cost=0.4)
    assert o2.status == "refused" and "segment cap $1.00 spent" in o2.reason


def test_the_11th_session_is_refused(convexity_db):
    cfg = _config(probe={**PROBE, "k": 1})
    for day in SEGMENT_DAYS:
        _l1(convexity_db, day, config=cfg, cands=CANDS[:1])
        assert _probe(convexity_db, day, config=cfg).status == "done", day
    assert len(rp.counted_sessions(convexity_db)) == 10
    _l1(convexity_db, "2026-12-21", config=cfg, cands=CANDS[:1])
    routers: list = []
    o = _probe(convexity_db, "2026-12-21", config=cfg, routers=routers)
    assert o.status == "refused" and o.reason == "segment complete (10/10 sessions)" and routers == []


def test_a_session_with_no_counted_repeat_does_not_count(convexity_db):
    cfg = _config(probe={**PROBE, "k": 1})
    _l1(convexity_db, "2026-12-07", config=cfg, cands=CANDS[:1])
    assert _probe(convexity_db, "2026-12-07", config=cfg, understudy_at={0}).status == "done"
    assert rp.counted_sessions(convexity_db) == []


def test_model_mix_change_stops_the_segment_for_good(convexity_db):
    cfg = _config()
    _l1(convexity_db, "2026-12-07", config=cfg, cands=CANDS[:1])
    assert _probe(convexity_db, "2026-12-07", config=cfg).status == "done"
    _l1(convexity_db, "2026-12-08", config=cfg, cands=CANDS[:1], mix=_mix(quote_filter="restate_v2"))
    routers: list = []
    o = _probe(convexity_db, "2026-12-08", config=cfg, routers=routers)
    assert o.status == "stopped_model_mix" and "quote_filter" in o.reason and routers == []
    _l1(convexity_db, "2026-12-09", config=cfg, cands=CANDS[:1])            # back to the original mix: still stopped
    o3 = _probe(convexity_db, "2026-12-09", config=cfg)
    assert o3.status == "refused" and o3.reason.startswith("segment stopped on a model_mix change")


def test_strategist_not_the_record_one_refuses(convexity_db):
    cfg = _config()
    _l1(convexity_db, "2026-12-08", config=cfg, mix=_mix(strategist="anthropic/claude-opus-4-8"))
    o = _probe(convexity_db, "2026-12-08", config=cfg)
    assert o.status == "refused" and "is not the record's" in o.reason
    _l1(convexity_db, "2026-12-09", config=cfg, mix=_mix(prompts="a/b/0000000000000000"))
    assert "system prompt differs" in _probe(convexity_db, "2026-12-09", config=cfg).reason


# ── refusals: disabled (quiet), segment start, L1 not finished, page rule ──────────────────────────────────────────

def test_disabled_refusal_is_a_quiet_info_line(convexity_db, caplog):
    cfg = _config(probe={**PROBE, "enabled": False})
    _l1(convexity_db, "2026-12-08", config=cfg)
    with caplog.at_level(logging.DEBUG, logger="council.repeat_probe"):
        o = _probe(convexity_db, "2026-12-08", config=cfg)
    assert o.status == "refused" and o.reason == "council.repeat_probe.enabled is false"
    recs = [r for r in caplog.records if r.name == "council.repeat_probe"]
    assert [r.levelno for r in recs] == [logging.INFO]
    assert convexity_db.execute("SELECT COUNT(*) FROM council_repeat_sessions").fetchone()[0] == 0


def test_main_with_the_flag_off_exits_zero_without_touching_the_db(monkeypatch, caplog):
    import config_loader
    import orchestrator

    monkeypatch.setattr(config_loader, "load_config", lambda: _config(probe={**PROBE, "enabled": False}))
    monkeypatch.setattr(state, "get_db", lambda *_a, **_k: pytest.fail("the disabled probe opened the DB"))
    with caplog.at_level(logging.INFO, logger="council.repeat_probe"):
        assert orchestrator.main(["--repeat-probe"]) == 0
    assert [r.levelno for r in caplog.records if r.name == "council.repeat_probe"] == [logging.INFO]


def test_before_the_segment_start_refuses(convexity_db):
    cfg = _config()
    _l1(convexity_db, "2026-12-04", config=cfg)
    o = _probe(convexity_db, "2026-12-04", config=cfg)
    assert o.status == "refused" and o.reason.startswith("before the segment start 2026-12-07")


def test_no_council_today_refuses(convexity_db):
    cfg = _config()
    _l1(convexity_db, "2026-12-07", config=cfg)
    assert _probe(convexity_db, "2026-12-08", config=cfg).reason == "no council of record for 2026-12-08 ET"


@pytest.mark.parametrize("unit, why", [
    (("activating", "2026-12-07 20:52:00"), "L1 unit is activating"),
    (("active", "2026-12-07 20:52:00"), "L1 unit is active"),
    (("inactive", "2026-12-07 20:52:00"), "before run started"),    # yesterday's exit
    (("inactive", None), "no exit timestamp"),
    (None, "unreadable"),
])
def test_l1_not_finished_refuses(convexity_db, unit, why):
    cfg = _config()
    _l1(convexity_db, "2026-12-08", config=cfg)
    o = _probe(convexity_db, "2026-12-08", config=cfg, unit=unit)
    assert o.status == "refused" and "has not finished" in o.reason and why in o.reason
    assert convexity_db.execute("SELECT COUNT(*) FROM council_repeat_sessions").fetchone()[0] == 0


def test_read_unit_state_parses_systemctl():
    class _Out:
        returncode = 0
        stdout = "ActiveState=inactive\nExecMainExitTimestamp=Tue 2026-12-08 20:52:01 UTC\n"

    seen = []
    assert rp.read_unit_state(run=lambda cmd, **k: seen.append(cmd) or _Out()) == ("inactive", "2026-12-08 20:52:01")
    assert seen[0][:3] == ["systemctl", "show", "dramatic-options-l1.service"] and "--timestamp=utc" in seen[0]

    class _Bad:
        returncode = 1
        stdout = ""

    assert rp.read_unit_state(run=lambda *a, **k: _Bad()) is None
    assert rp.read_unit_state(run=lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError())) is None
    assert rp.l1_finished("2026-12-08 20:45:00", ("inactive", "2026-12-08 20:52:01"))[0] is True


def test_page_refusal_counts_council_and_probe_spend(convexity_db):
    # page $1.00 × 0.8 = $0.80. Record strategist cost $0.02/name × 3 names × k=5 = $0.30 estimate.
    cfg = _config(monthly_spend_page_usd={"fake": 1.0})
    rid, _ = _l1(convexity_db, "2026-12-08", config=cfg)
    with convexity_db:
        convexity_db.execute("UPDATE council_agent_outputs SET cost_usd = 0.02 WHERE role = 'strategist'")
        convexity_db.execute("UPDATE council_agent_outputs SET created_at = '2026-12-08 20:46:00'")
    # MTD council $0.06 + probe rows $0.43 earlier this month = $0.49; + $0.30 = $0.79 < $0.80 → runs.
    with convexity_db:
        convexity_db.execute(
            "INSERT INTO council_repeat_reads (run_id, proposal_id, symbol, repeat_idx, provider, model, cost_usd, "
            "created_at) VALUES (0, 0, 'OLD', 0, 'fake', 'fake-strategist', 0.43, '2026-12-01 21:00:00')")
    assert _probe(convexity_db, "2026-12-08", config=cfg, cost=0.0).status == "done"
    # A cent more MTD and the same estimate reaches the line → refused.
    _l1(convexity_db, "2026-12-09", config=cfg)
    with convexity_db:
        convexity_db.execute("UPDATE council_agent_outputs SET cost_usd = 0.02, created_at = '2026-12-09 20:46:00' "
                             "WHERE role = 'strategist' AND cost_usd = 0")
        convexity_db.execute("UPDATE council_repeat_reads SET cost_usd = 0.40 WHERE symbol = 'OLD'")
    # MTD = council 0.06 + 0.06 + probe 0.40 = 0.52; + 0.30 = 0.82 >= 0.80.
    o = _probe(convexity_db, "2026-12-09", config=cfg, cost=0.0)
    assert o.status == "refused" and "MTD $0.52 + session estimate $0.30" in o.reason


def test_probe_spend_crossing_the_line_pages_once(convexity_db):
    cfg = _config(monthly_spend_page_usd={"fake": 2.0})        # line 0.8 × $2 = $1.60; refusal line also $1.60
    _l1(convexity_db, "2026-12-08", config=cfg)
    with convexity_db:
        convexity_db.execute("UPDATE council_agent_outputs SET cost_usd = 0.01, created_at = '2026-12-08 20:46:00' "
                             "WHERE role = 'strategist'")
        convexity_db.execute(
            "INSERT INTO council_repeat_reads (run_id, proposal_id, symbol, repeat_idx, provider, model, cost_usd, "
            "created_at) VALUES (0, 0, 'OLD', 0, 'fake', 'fake-strategist', 1.30, '2026-12-01 21:00:00')")
    pages = []
    # MTD 1.33 + estimate 0.15 = 1.48 < 1.60 → runs; actual spend 15 × $0.02 = $0.30 → MTD 1.63 crosses $1.60.
    o = _probe(convexity_db, "2026-12-08", config=cfg, cost=0.02, notify=lambda t, m, **k: pages.append((t, m)))
    assert o.status == "done" and len(pages) == 1 and "repeat probe" in pages[0][1]


def test_month_spend_includes_the_probe(convexity_db, tmp_path):
    now = datetime(2026, 12, 15, tzinfo=UTC)
    rid = state.record_run(convexity_db, mode="PAPER", equity=1)
    pid = state.record_council_proposal(convexity_db, run_id=rid, as_of="x", theme="t", symbol="A",
                                        direction="bullish", conviction="LOW")
    state.record_agent_output(convexity_db, proposal_id=pid, role="strategist", provider="anthropic", model="m",
                              confidence="LOW", cost_usd=1.25)
    convexity_db.execute("UPDATE council_agent_outputs SET created_at = '2026-12-03 20:50:00'")
    for prov, cost, ts in (("anthropic", 0.5, "2026-12-08 21:10:00"), ("anthropic", 9.0, "2026-11-30 21:10:00"),
                           ("openai", 0.7, "2026-12-08 21:10:00")):
        convexity_db.execute(
            "INSERT INTO council_repeat_reads (run_id, proposal_id, symbol, repeat_idx, provider, model, cost_usd, "
            "created_at) VALUES (?, ?, 'A', 0, ?, 'm', ?, ?)", (rid, pid, prov, cost, ts))
    convexity_db.commit()
    assert state.provider_month_spend(convexity_db, "anthropic", now=now) == pytest.approx(1.75)
    assert state.provider_month_spend(convexity_db, "openai", now=now) == pytest.approx(0.7)
    # A DB without the probe table (pre-0022) reads the council rows only.
    old = state.connect(tmp_path / "old.db")
    import conftest

    for name in ("0001_initial.py", "0003_convexity.py", "0005_council.py"):
        conftest._apply_migration(old, name)
    assert state.provider_month_spend(old, "anthropic", now=now) == 0.0
    old.close()


def test_migration_is_idempotent(convexity_db):
    import conftest

    conftest._apply_migration(convexity_db, "0022_council_repeat_probe.py")
    names = {r[0] for r in convexity_db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"council_repeat_packs", "council_repeat_reads", "council_repeat_sessions"} <= names


def test_shipped_config_is_off_with_the_pinned_values():
    cfg = json.loads((REPO / "config.json").read_text())["council"]
    s = rp.settings({"council": cfg})
    assert s["enabled"] is False
    assert (s["k"], s["sessions"], s["segment_start_et"], s["cap_session_usd"], s["cap_total_usd"],
            s["page_refusal_fraction"]) == (5, 10, "2026-12-07", 1.5, 15.0, 0.8)
    assert "§10.12" in cfg["repeat_probe"]["_comment"] and "2026-11-14" in cfg["repeat_probe"]["_comment"]
    assert cfg["monthly_spend_page_usd"]["anthropic"] == 10.0   # the $20 December raise rides the 12-07 switch-on edit
