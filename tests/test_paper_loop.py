"""End-to-end paper loop (offline): cheap theme opens, rich theme vetoes, fail-closed."""

from datetime import UTC, datetime
from pathlib import Path

import risk
import state
from broker import PaperBroker
from clock import FixedClock
from convexity_data import SyntheticChainProvider
from paper_loop import run_paper_cycle
from themes import Theme

CONFIG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10,
                       "per_name_fraction": 0.01, "max_open_positions": 15},
    "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                       "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
    "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
    "themes_path": "themes.json",
}
CLOCK = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
THEMES = [
    Theme("copper_electrification", "FCX", "bullish", "cheap industrial tailwind"),
    Theme("hype_rich", "NVDA", "bullish", "crowded, richly-priced"),
]


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def _provider():
    return SyntheticChainProvider(as_of=CLOCK.now().date())


def test_cycle_opens_cheap_and_vetoes_rich(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    res = run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0), themes=THEMES, run_id=None)
    assert res.opened == 1
    assert res.vetoed == 1
    assert res.errors == 0
    assert not res.halted

    positions = state.open_convexity_positions(conn)
    assert len(positions) == 1
    p = positions[0]
    assert p["symbol"] == "FCX" and p["structure_kind"] == "C" and p["contracts"] >= 1
    assert p["total_premium"] > 0

    evals = conn.execute("SELECT symbol, decision FROM convexity_eval ORDER BY id").fetchall()
    decisions = {e["symbol"]: e["decision"] for e in evals}
    assert decisions["FCX"] == "open"
    assert decisions["NVDA"] == "veto-iv-gate"


def test_kill_switch_halts_entries(convexity_db, monkeypatch):
    monkeypatch.setenv("KILL", "1")
    res = run_paper_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0), themes=THEMES, run_id=None)
    assert res.halted is True
    assert res.opened == 0
    assert state.count_open_convexity_positions(convexity_db) == 0


def test_provider_error_is_logged_not_raised(convexity_db, monkeypatch):
    _no_kill(monkeypatch)

    class BoomProvider:
        def underlying_price(self, s):
            return 50.0

        def chain(self, s):
            raise RuntimeError("boom")

        def closes(self, s, *, window):
            return [50.0] * (window + 1)

    res = run_paper_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK, provider=BoomProvider(),
                          broker=PaperBroker(100_000.0),
                          themes=[Theme("boom", "BOOM", "bullish", "x")], run_id=None)
    assert res.errors == 1
    assert res.opened == 0
    row = convexity_db.execute("SELECT decision, reasons FROM convexity_eval").fetchone()
    assert row["decision"] == "error" and "boom" in row["reasons"]


def test_dedup_skips_already_open_theme(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    # FCX already has an open position → re-running must not stack a duplicate.
    state.record_convexity_position(
        conn, run_id=None, opened_at="2026-01-01T00:00:00+00:00", theme="copper_electrification",
        symbol="FCX", direction="bullish", structure_kind="C", contract_symbol="FCX_x",
        expiry="2026-09-30", strike=56.0, dte=270, moneyness=0.25, contracts=1,
        entry_premium_per_contract=200.0, total_premium=200.0,
    )
    res = run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0), themes=[THEMES[0]], run_id=None)
    assert res.skipped == 1 and res.opened == 0
    assert state.count_open_convexity_positions(conn) == 1  # unchanged
    row = conn.execute("SELECT decision FROM convexity_eval ORDER BY id DESC LIMIT 1").fetchone()
    assert row["decision"] == "skip-already-open"


def test_book_sized_off_config_not_broker_equity(convexity_db, monkeypatch):
    """The convexity book uses the config notional, not the (arbitrary) broker paper equity."""
    _no_kill(monkeypatch)
    # Broker reports a tiny equity that would size the book to ~nothing; config says 100k.
    res = run_paper_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(500.0), themes=[THEMES[0]], run_id=None)
    assert res.opened == 1  # used config 100k, so FCX still sizes to ≥1 contract


def test_chain_cache_accrual(convexity_db, monkeypatch, tmp_path):
    from convexity_data import SNAPSHOT_SOURCE
    from data.cache import PointInTimeCache

    _no_kill(monkeypatch)
    cache = PointInTimeCache(tmp_path)
    run_paper_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK, provider=_provider(),
                    broker=PaperBroker(100_000.0), themes=THEMES, run_id=None, chain_cache=cache)
    # Both evaluated themes' chains are persisted (even NVDA, which the IV gate vetoes).
    fcx = cache.read_between(SNAPSHOT_SOURCE, "FCX", None, CLOCK.now())
    nvda = cache.read_between(SNAPSHOT_SOURCE, "NVDA", None, CLOCK.now())
    assert len(fcx) == 1 and len(nvda) == 1
    assert fcx[0]["surface"]


def test_sizing_veto_when_concurrency_full(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    for i in range(15):  # fill the max-open slots
        state.record_convexity_position(
            conn, run_id=None, opened_at="2026-01-02T00:00:00+00:00", theme="f", symbol="F",
            direction="bullish", structure_kind="C", contract_symbol=f"F{i}", expiry="2026-09-30",
            strike=1.0, dte=270, moneyness=0.25, contracts=1, entry_premium_per_contract=10.0,
            total_premium=10.0,
        )
    res = run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0),
                          themes=[THEMES[0]], run_id=None)
    assert res.opened == 0 and res.vetoed == 1
    row = conn.execute("SELECT decision FROM convexity_eval ORDER BY id DESC LIMIT 1").fetchone()
    assert row["decision"] == "veto-sizing"


# ── cluster exposure cap (PREREG §5 amendment 2026-06-03) ────────────────────────────────────────

# Arbitrary symbols use the cheap DEFAULT synthetic profile → they clear the IV gate, so the CLUSTER
# cap (not the gate) is the binding constraint — exactly the §C "correlated names look diversified" case.
_BASKET = ["AAA", "BBB", "CCC", "DDD"]


def _config_with_cluster(*, cluster_fraction, members, name="power", discovery=None):
    book = {**CONFIG["convexity_book"], "cluster_fraction": cluster_fraction,
            "clusters": {name: list(members)}}
    cfg = {**CONFIG, "convexity_book": book}
    if discovery is not None:
        cfg["discovery"] = discovery
    return cfg


def _seed_open(conn, *, symbol, total_premium, direction="bullish", status="open"):
    state.record_convexity_position(
        conn, run_id=None, opened_at="2026-01-02T00:00:00+00:00", theme="seed", symbol=symbol,
        direction=direction, structure_kind="C", contract_symbol=f"{symbol}_x", expiry="2026-09-30",
        strike=60.0, dte=270, moneyness=0.25, contracts=1, entry_premium_per_contract=total_premium,
        total_premium=total_premium, status=status,
    )


def test_per_name_cap_alone_opens_the_whole_correlated_basket(convexity_db, monkeypatch):
    # Baseline: with NO cluster, the per-name cap reads 4 correlated names as 4 "diversified" bets.
    _no_kill(monkeypatch)
    themes = [Theme(f"t_{s}", s, "bullish", "cheap") for s in _BASKET]
    res = run_paper_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0), themes=themes, run_id=None)
    assert res.opened == 4  # the false diversification the cluster cap exists to fix


def test_cluster_cap_admits_only_a_subset(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    cfg = _config_with_cluster(cluster_fraction=0.02, members=_BASKET)  # cap = $2000 ≈ 2 full names
    themes = [Theme(f"t_{s}", s, "bullish", "cheap") for s in _BASKET]
    res = run_paper_cycle(config=cfg, conn=convexity_db, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0), themes=themes, run_id=None)
    assert 0 < res.opened < 4                                            # the cap reduced the count
    assert state.cluster_open_premium(convexity_db, set(_BASKET)) <= 100_000.0 * 0.02 + 1e-6
    vetoes = convexity_db.execute(
        "SELECT COUNT(*) AS n FROM convexity_eval WHERE decision = 'veto-cluster-cap'").fetchone()["n"]
    assert vetoes >= 1                                                   # the rest were cluster-capped


def test_cluster_premium_counts_pending_but_book_does_not(convexity_db):
    # #12: a same-cycle just-submitted PENDING mate counts toward the CLUSTER budget (else a tight
    # cluster over-admits its next mate under DRY_RUN=false) but NOT the book cap (deliberate divergence).
    _seed_open(convexity_db, symbol="AAA", total_premium=900.0, status="pending")
    assert state.cluster_open_premium(convexity_db, {"AAA"}) == 900.0   # committed basis counts pending
    assert state.convexity_book_open_premium(convexity_db) == 0.0       # open/closing basis does not


def test_same_cycle_pending_mate_caps_the_next_mate(convexity_db, monkeypatch):
    # #12 end-to-end: a PENDING cluster-mate near the cap → the next cheap mate is cluster-capped THIS
    # cycle. Without counting pending (the bug) FCX would open; with the fix it is veto-cluster-cap.
    _no_kill(monkeypatch)
    cfg = _config_with_cluster(cluster_fraction=0.01, members=["FCX", "AAA"])  # cap = $1000
    _seed_open(convexity_db, symbol="AAA", total_premium=950.0, status="pending")
    res = run_paper_cycle(config=cfg, conn=convexity_db, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0),
                          themes=[Theme("t", "FCX", "bullish", "cheap")], run_id=None)
    assert res.opened == 0
    row = convexity_db.execute("SELECT decision FROM convexity_eval ORDER BY id DESC LIMIT 1").fetchone()
    assert row["decision"] == "veto-cluster-cap"


def test_cluster_capped_sentinel_does_not_consume_a_reserved_slot(convexity_db, monkeypatch):
    # R2 2b: a sentinel in a FULL cluster records the structural veto-cluster-cap (cluster-veto fires
    # BEFORE slot accounting) and consumes NO reserved sentinel slot (the reservation is occupancy-based).
    _no_kill(monkeypatch)
    cfg = _config_with_cluster(cluster_fraction=0.01, members=["FCX", "AAA"],
                               discovery={"sentinel_max_slots": 6})
    _seed_open(convexity_db, symbol="AAA", total_premium=1000.0)  # cluster full at the $1000 cap
    sentinel = Theme("disc", "FCX", "bullish", "cheap", source="sentinel", sentinel_id=1)
    res = run_paper_cycle(config=cfg, conn=convexity_db, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0), themes=[sentinel], run_id=None)
    assert res.opened == 0
    row = convexity_db.execute("SELECT decision FROM convexity_eval ORDER BY id DESC LIMIT 1").fetchone()
    assert row["decision"] == "veto-cluster-cap"                       # NOT veto-sentinel-slots
    assert state.count_open_sentinel_positions(convexity_db) == 0       # reserved slot still free


def test_mixed_direction_cluster_logs_warning(convexity_db, monkeypatch, caplog):
    import logging
    _no_kill(monkeypatch)
    cfg = _config_with_cluster(cluster_fraction=0.02, members=["AAA", "BBB"])
    _seed_open(convexity_db, symbol="AAA", total_premium=100.0, direction="bullish")
    _seed_open(convexity_db, symbol="BBB", total_premium=100.0, direction="bearish")
    with caplog.at_level(logging.WARNING, logger="paper_loop"):
        run_paper_cycle(config=cfg, conn=convexity_db, clock=CLOCK, provider=_provider(),
                        broker=PaperBroker(100_000.0), themes=[], run_id=None)
    assert any("mixed directions" in r.getMessage() for r in caplog.records)


def test_open_eval_carries_the_per_decision_cluster_snapshot(convexity_db, monkeypatch):
    # R4 2a: the breach-audit substrate — recompute within-cap-ness at the admission, never trust code.
    import json
    _no_kill(monkeypatch)
    cfg = _config_with_cluster(cluster_fraction=0.05, members=["FCX"])  # room → FCX opens
    res = run_paper_cycle(config=cfg, conn=convexity_db, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0),
                          themes=[Theme("t", "FCX", "bullish", "cheap")], run_id=None)
    assert res.opened == 1
    row = convexity_db.execute("SELECT reasons FROM convexity_eval WHERE decision='open'").fetchone()
    cs = json.loads(row["reasons"])["cluster_state"]
    assert cs["cluster"] == "power" and cs["cap"] == 5000.0 and cs["equity"] == 100_000.0


def test_unclustered_name_eval_keeps_the_plain_list_shape(convexity_db, monkeypatch):
    # Converse: an unclustered name is unaffected and its eval reasons stay a plain list (byte-identical).
    import json
    _no_kill(monkeypatch)
    cfg = _config_with_cluster(cluster_fraction=0.02, members=["AAA"])  # FCX not in the cluster
    res = run_paper_cycle(config=cfg, conn=convexity_db, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0),
                          themes=[Theme("t", "FCX", "bullish", "cheap")], run_id=None)
    assert res.opened == 1
    row = convexity_db.execute("SELECT reasons FROM convexity_eval WHERE decision='open'").fetchone()
    assert isinstance(json.loads(row["reasons"]), list)
