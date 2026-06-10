"""The OPRA dual-read (PREREG_DATA_FEED_OPRA_SEQUENCING): migration 0014, the date-gated
disagree-veto (shadow can only TIGHTEN, and it lapses), shadow fail-soft (a broken arm never
blocks), the entitlement merge-blocker (veto + ONE page, never a downgrade), the sweep, and the
report's hand-checked values."""

from datetime import UTC, date, datetime

import gate_dualread
import notify
import paper_loop
import state
from broker import PaperBroker
from clock import FixedClock
from convexity_data import SyntheticChainProvider
from dashboard_data import gate_dualread_report
from themes import Theme

AS_OF = datetime(2026, 6, 10, 15, 45, tzinfo=UTC)


def _cfg(**data_feed_extra):
    return {
        "themes_path": "themes.json",
        "convexity_book": {"account_equity": 100000.0, "book_fraction": 0.10,
                           "per_name_fraction": 0.01, "max_open_positions": 15},
        "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                           "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
        "eligibility": {"live": {"max_bid_ask_pct": 0.25}},
        "data_feed": {"equity_bars": "sip", "option_gate": "opra",
                      "option_monitor": "indicative", **data_feed_extra},
    }


def _cheap_theme():
    return [Theme(name="copper", symbol="FCX", direction="bullish", thesis="t", active=True)]


def _cycle(convexity_db, *, shadow_provider, veto_until=None, monkeypatch=None):
    cfg = _cfg(**({"dualread_disagree_veto_until": veto_until} if veto_until else {}))
    provider = SyntheticChainProvider(as_of=AS_OF.date())
    broker = PaperBroker(100000.0)
    run_id = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    return paper_loop.run_paper_cycle(
        config=cfg, conn=convexity_db, clock=FixedClock(AS_OF), provider=provider, broker=broker,
        themes=_cheap_theme(), run_id=run_id, shadow_provider=shadow_provider,
    )


class EmptyChainProvider:
    """A shadow arm that structures NOTHING (disagrees with a cheap of-record read)."""

    def chain(self, symbol):
        return []


class BoomProvider:
    """A shadow arm that fails outright (the fail-soft case)."""

    def chain(self, symbol):
        raise RuntimeError("shadow boom")


# ── the date gate ───────────────────────────────────────────────────────────────────────────────

def test_disagree_veto_date_gate():
    on = {"data_feed": {"dualread_disagree_veto_until": "2026-07-10"}}
    assert gate_dualread.disagree_veto_active(on, date(2026, 7, 10)) is True   # inclusive
    assert gate_dualread.disagree_veto_active(on, date(2026, 7, 11)) is False  # lapsed
    assert gate_dualread.disagree_veto_active({"data_feed": {}}, date(2026, 6, 10)) is False
    bad = {"data_feed": {"dualread_disagree_veto_until": "soon"}}
    assert gate_dualread.disagree_veto_active(bad, date(2026, 6, 10)) is False  # malformed ⇒ no veto power


# ── the disagree veto fires, then lapses ────────────────────────────────────────────────────────

def test_disagree_veto_blocks_entry_pre_lapse(convexity_db):
    res = _cycle(convexity_db, shadow_provider=EmptyChainProvider(), veto_until="2099-01-01")
    assert res.opened == 0 and res.vetoed == 1
    row = convexity_db.execute(
        "SELECT decision FROM convexity_eval WHERE symbol='FCX' ORDER BY id DESC LIMIT 1").fetchone()
    assert row[0] == "veto-dualread-disagree"
    # both arms recorded: the of-record verdict + the disagreeing shadow (structured=0)
    arms = {r[0]: r[1] for r in convexity_db.execute(
        "SELECT feed, structured FROM gate_dualread WHERE symbol='FCX'").fetchall()}
    assert arms == {"opra": 1, "indicative": 0}


def test_disagree_veto_lapses_after_dated_closeout(convexity_db):
    res = _cycle(convexity_db, shadow_provider=EmptyChainProvider(), veto_until="2026-06-01")
    assert res.opened == 1  # the lapsed rule grants the shadow arm NO veto power


# ── shadow fail-soft: a broken arm records a note row and never blocks ─────────────────────────

def test_shadow_failure_never_blocks_entry(convexity_db):
    res = _cycle(convexity_db, shadow_provider=BoomProvider(), veto_until="2099-01-01")
    assert res.opened == 1  # an erroring shadow ≠ a disagreeing shadow
    row = convexity_db.execute(
        "SELECT structured, note FROM gate_dualread WHERE symbol='FCX' AND feed='indicative'").fetchone()
    assert row[0] == 0 and "boom" in row[1]


def test_no_shadow_provider_means_no_dualread_rows(convexity_db):
    res = _cycle(convexity_db, shadow_provider=None)
    assert res.opened == 1
    assert convexity_db.execute("SELECT COUNT(*) FROM gate_dualread").fetchone()[0] == 0


# ── the entitlement merge-blocker (§7): veto + ONE page, never a silent downgrade ──────────────

class EntitlementProvider:
    def underlying_price(self, symbol):
        raise RuntimeError("subscription does not permit querying premium option data")

    def chain(self, symbol):
        raise RuntimeError("subscription does not permit querying premium option data")

    def closes(self, symbol, *, window):
        return [50.0] * window


def test_entitlement_lapse_vetoes_and_pages_once(convexity_db, monkeypatch):
    pages = []
    monkeypatch.setattr(notify, "send", lambda title, msg, **k: pages.append(title) or True)
    cfg = _cfg()
    themes = [Theme(name="a", symbol="FCX", direction="bullish", thesis="t", active=True),
              Theme(name="b", symbol="NVDA", direction="bullish", thesis="t", active=True)]
    run_id = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    res = paper_loop.run_paper_cycle(
        config=cfg, conn=convexity_db, clock=FixedClock(AS_OF), provider=EntitlementProvider(),
        broker=PaperBroker(100000.0), themes=themes, run_id=run_id)
    assert res.opened == 0 and res.errors == 2
    decisions = [r[0] for r in convexity_db.execute(
        "SELECT decision FROM convexity_eval ORDER BY id").fetchall()]
    assert decisions == ["veto-feed-entitlement", "veto-feed-entitlement"]
    assert len(pages) == 1  # ONE page per run, not per name


def test_transient_error_keeps_plain_error_decision(convexity_db, monkeypatch):
    pages = []
    monkeypatch.setattr(notify, "send", lambda title, msg, **k: pages.append(title) or True)

    class FlakyProvider(EntitlementProvider):
        def underlying_price(self, symbol):
            raise TimeoutError("connection timed out")

    run_id = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    res = paper_loop.run_paper_cycle(
        config=_cfg(), conn=convexity_db, clock=FixedClock(AS_OF), provider=FlakyProvider(),
        broker=PaperBroker(100000.0), themes=_cheap_theme(), run_id=run_id)
    assert res.errors == 1 and not pages
    row = convexity_db.execute("SELECT decision FROM convexity_eval ORDER BY id DESC LIMIT 1").fetchone()
    assert row[0] == "error"


# ── the sweep ───────────────────────────────────────────────────────────────────────────────────

def test_sweep_writes_both_arms_and_counts(convexity_db):
    provider = SyntheticChainProvider(as_of=AS_OF.date())
    run_id = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    counts = gate_dualread.sweep_universe(
        convexity_db, run_id=run_id, as_of_iso=AS_OF.isoformat(), symbols=["FCX", "NVDA"],
        provider_record=provider, provider_shadow=provider,
        market_closes=lambda s: provider.closes(s, window=300),
        gate=_cfg()["convexity_gate"],
        eligibility=lambda c: (True, None), skip=set())
    assert counts["swept"] == 2 and counts["record_ok"] == 2 and counts["shadow_ok"] == 2
    n = convexity_db.execute("SELECT COUNT(*) FROM gate_dualread WHERE source='sweep'").fetchone()[0]
    assert n == 4  # two names × two arms


# ── the report — hand-checked values (the §5b anti-HARK discipline) ────────────────────────────

def test_gate_dualread_report_hand_checked(convexity_db):
    rid = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    rows = [
        # AAA: both structured, iv_rv 1.10 vs 1.18 → Δ .08; cheap 1 vs 0 → FLIP
        dict(symbol="AAA", feed="opra", structured=True, iv_rv=1.10, cheap=True),
        dict(symbol="AAA", feed="indicative", structured=True, iv_rv=1.18, cheap=False),
        # BBB: both structured, Δ .01, both cheap → clean pair
        dict(symbol="BBB", feed="opra", structured=True, iv_rv=1.00, cheap=True),
        dict(symbol="BBB", feed="indicative", structured=True, iv_rv=1.01, cheap=True),
        # CCC: INDICATIVE structures, OPRA cannot → a §5 coverage GAP
        dict(symbol="CCC", feed="opra", structured=False, note="no_structure"),
        dict(symbol="CCC", feed="indicative", structured=True, iv_rv=1.05, cheap=True),
    ]
    for r in rows:
        state.record_gate_dualread(convexity_db, run_id=rid, as_of=AS_OF.isoformat(),
                                   source="sweep", **r)
    rep = gate_dualread_report(convexity_db, {"data_feed": {"dualread_disagree_veto_until": "2099-01-01"}})
    s = rep["sessions"][-1]
    assert s["names"] == 3
    assert s["median_d_ivrv"] == 0.045 and s["max_d_ivrv"] == 0.08  # median(.08,.01), max
    assert s["flips"] == ["AAA"] and s["coverage_gaps"] == ["CCC"]
    assert s["opra_coverage"] == round(2 / 3, 3) and s["indicative_coverage"] == 1.0
    tw = rep["tripwires"]
    assert tw["flip_sessions"] == 1 and tw["gap_sessions"] == 1
    assert tw["delta_breach_sessions"] == 0 and not tw["delta_tripped"]  # .08 max ≤ .10, med .045 ≤ .05
    assert rep["disagree_veto"]["active"] is True
