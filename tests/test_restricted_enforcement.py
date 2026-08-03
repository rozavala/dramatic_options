"""Restricted-list enforcement (records/2026-07-14_restricted_list_RATIFIED.md) — fail-closed.

The MERGE-BLOCKER half: no restricted ticker may appear in any curation surface
(universe_register.json, config.universe.themes, themes.json, probe_themes.json) — a future
curation PR admitting a restricted name fails CI right here. The runtime half: the union
choke point drops restricted symbols (any origin), every book cycle including ALL null books
vetoes them belt-and-suspenders, the forward-catalyst pin loader refuses them, and an
absent/malformed restricted.json HALTS (fail-closed — never mistaken for an empty list).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import fixed_basket
import restricted
import risk
import sentinels
import shadow_book
import shares_basket
from broker import PaperBroker
from clock import FixedClock
from convexity_data import SyntheticChainProvider
from data.forward_catalysts import ForwardCatalysts
from paper_loop import run_paper_cycle
from themes import Theme

REPO = Path(__file__).resolve().parents[1]
CLOCK = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
CONFIG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10,
                       "per_name_fraction": 0.01, "max_open_positions": 15},
    "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                       "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
    "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
    "themes_path": "themes.json",
}


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def _provider():
    return SyntheticChainProvider(as_of=CLOCK.now().date())


def _theme(symbol="LIFE", direction="bullish", source="sentinel", **kw):
    return Theme("restricted_theme", symbol, direction, "thesis", source=source,
                 sentinel_id=(1 if source == "sentinel" else None), **kw)


# ── the CI merge-blocker: no restricted ticker in any curation surface ─────────────────────


def _register_hits(node, restricted_set: frozenset[str]) -> set[str]:
    """Recursive full-string scan of universe_register.json: dict KEYS (per-symbol screen
    records) + every string value (admitted/vetoed lists etc.). Exact-match only, so thesis
    prose can never false-positive."""
    hits: set[str] = set()
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str) and k.strip().upper() in restricted_set:
                hits.add(k.strip().upper())
            hits |= _register_hits(v, restricted_set)
    elif isinstance(node, list):
        for v in node:
            hits |= _register_hits(v, restricted_set)
    elif isinstance(node, str) and node.strip().upper() in restricted_set:
        hits.add(node.strip().upper())
    return hits


def test_restricted_json_ships_and_loads():
    r = restricted.load_restricted()
    assert "LIFE" in r  # R-001's derived ticker (the ID→person mapping is NOT in the repo)


def test_no_restricted_ticker_in_config_universe_themes():
    r = restricted.load_restricted()
    cfg = json.loads((REPO / "config.json").read_text())
    for basket, members in (cfg.get("universe", {}).get("themes", {}) or {}).items():
        if str(basket).startswith("_"):
            continue
        bad = {str(s).strip().upper() for s in members} & r
        assert not bad, f"restricted ticker(s) {sorted(bad)} in config.universe.themes[{basket!r}]"


@pytest.mark.parametrize("fname", ["themes.json", "probe_themes.json"])
def test_no_restricted_ticker_in_themes_files(fname):
    p = REPO / fname
    if not p.exists():
        pytest.skip(f"{fname} not present")
    r = restricted.load_restricted()
    for t in json.loads(p.read_text()).get("themes", []):
        if not isinstance(t, dict) or t.get("_comment"):
            continue
        sym = str(t.get("symbol", "")).strip().upper()
        assert sym not in r, f"restricted ticker {sym} in {fname}"


def test_no_restricted_ticker_in_universe_register():
    r = restricted.load_restricted()
    reg = json.loads((REPO / "universe_register.json").read_text())
    hits = _register_hits(reg, r)
    assert not hits, f"restricted ticker(s) {sorted(hits)} in universe_register.json"


def test_no_restricted_ticker_pinned_in_forward_catalysts():
    r = restricted.load_restricted()
    p = REPO / "forward_catalysts.json"
    if not p.exists():
        pytest.skip("no pin file")
    items = json.loads(p.read_text()).get("items", []) or []
    bad = {str(i.get("symbol", "")).strip().upper() for i in items} & r
    assert not bad, f"restricted ticker(s) {sorted(bad)} pinned in forward_catalysts.json"


# ── restricted.py: load semantics (fail-closed) + case-insensitivity ───────────────────────


def test_load_restricted_absent_raises(tmp_path):
    with pytest.raises(restricted.RestrictedListError):
        restricted.load_restricted(tmp_path / "nope.json")


@pytest.mark.parametrize("content", [
    "not json {",
    '{"entries": "not-a-list"}',
    '{"entries": [{"id": "R-9"}]}',                      # missing tickers array
    '{"entries": [{"id": "R-9", "tickers": [""]}]}',     # empty ticker
    '{"entries": [{"id": "R-9", "tickers": [1]}]}',      # non-string ticker
])
def test_load_restricted_malformed_raises(tmp_path, content):
    p = tmp_path / "restricted.json"
    p.write_text(content)
    with pytest.raises(restricted.RestrictedListError):
        restricted.load_restricted(p)


def test_load_restricted_accepts_bare_list_and_uppercases(tmp_path):
    p = tmp_path / "restricted.json"
    p.write_text('[{"id": "R-9", "tickers": [" life ", "xyz"]}]')
    assert restricted.load_restricted(p) == frozenset({"LIFE", "XYZ"})


def test_is_restricted_case_insensitive():
    r = frozenset({"LIFE"})
    assert restricted.is_restricted("life", r)
    assert restricted.is_restricted(" Life ", r)
    assert restricted.is_restricted("LIFE", r)
    assert not restricted.is_restricted("LIF", r)
    assert not restricted.is_restricted("", r)


# ── (b) union construction: the choke point all three consumers share ──────────────────────


def test_union_drops_restricted_any_origin(caplog):
    hand = _theme(source="hand-seed")
    sent = _theme(source="sentinel", direction="bearish")
    keep = Theme("copper", "FCX", "bullish", "thesis")
    with caplog.at_level("WARNING", logger="sentinels"):
        out = sentinels.union_candidates([hand, keep], [sent],
                                         restricted=frozenset({"LIFE"}))
    assert [t.symbol for t in out] == ["FCX"]
    assert sum("restricted-list drop" in m for m in caplog.messages) == 2


def test_union_default_loads_the_repo_list():
    # No restricted= passed → the shipped restricted.json governs (R-001 → LIFE dropped).
    out = sentinels.union_candidates([_theme(source="hand-seed")], [])
    assert out == []


def test_union_fail_closed_on_broken_list(tmp_path, monkeypatch):
    bad = tmp_path / "restricted.json"
    bad.write_text("not json {")
    monkeypatch.setattr(restricted, "DEFAULT_PATH", bad)
    with pytest.raises(restricted.RestrictedListError):
        sentinels.union_candidates([Theme("copper", "FCX", "bullish", "t")], [])


def test_union_fail_closed_on_absent_list(tmp_path, monkeypatch):
    monkeypatch.setattr(restricted, "DEFAULT_PATH", tmp_path / "gone.json")
    with pytest.raises(restricted.RestrictedListError):
        sentinels.union_candidates([Theme("copper", "FCX", "bullish", "t")], [])


# ── (c) book cycles, belt-and-suspenders: counted veto reason 'restricted' ─────────────────


def test_shadow_book_vetoes_restricted_counted(convexity_db, monkeypatch, caplog):
    _no_kill(monkeypatch)
    with caplog.at_level("WARNING", logger="shadow_book"):
        res = shadow_book.run_shadow_cycle(
            config=CONFIG, conn=convexity_db, clock=CLOCK, provider=_provider(),
            run_id=None, candidates=[_theme()])
    assert res.booked == 0 and res.vetoed == 1
    assert res.veto_reasons == {"restricted": 1}
    assert any("restricted-list veto" in m for m in caplog.messages)
    n = convexity_db.execute("SELECT COUNT(*) FROM shadow_positions WHERE symbol='LIFE'").fetchone()[0]
    assert n == 0


def test_fixed_basket_3a_vetoes_restricted_counted(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    res = fixed_basket.run_fixed_basket_3a_cycle(
        config=CONFIG, conn=convexity_db, clock=CLOCK, provider=_provider(),
        run_id=None, candidates=[_theme()])
    assert res.booked == 0 and res.veto_reasons == {"restricted": 1}


def test_fixed_basket_3b_vetoes_restricted_counted(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    cfg = {**CONFIG, "universe": {"themes": {"basket_x": ["LIFE"]}}}
    # market/benchmark/params are never touched — the restricted veto fires before the motion read.
    res = fixed_basket.run_fixed_basket_3b_cycle(
        config=cfg, conn=convexity_db, clock=CLOCK, provider=_provider(),
        market=None, benchmark="SPY", params=None, run_id=None)
    assert res.booked == 0 and res.veto_reasons == {"restricted": 1}


def test_shares_basket_vetoes_restricted_counted(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    cfg = {**CONFIG, "universe": {"themes": {"basket_x": ["LIFE"]}}}
    res = shares_basket.run_shares_basket_cycle(
        config=cfg, conn=convexity_db, clock=CLOCK, provider=_provider(),
        market=None, benchmark="SPY", params=None, run_id=None)
    assert res.booked == 0 and res.vetoed == 1  # no per-reason dict on this book — counted
    n = convexity_db.execute("SELECT COUNT(*) FROM shares_positions WHERE symbol='LIFE'").fetchone()[0]
    assert n == 0


def test_book_cycles_fail_closed_on_broken_list(convexity_db, monkeypatch, tmp_path):
    _no_kill(monkeypatch)
    bad = tmp_path / "restricted.json"
    bad.write_text("{}")
    monkeypatch.setattr(restricted, "DEFAULT_PATH", bad)
    with pytest.raises(restricted.RestrictedListError):
        shadow_book.run_shadow_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK,
                                     provider=_provider(), run_id=None, candidates=[])


# ── (d) the forward-catalyst pin loader refuses a restricted pin ───────────────────────────


def _pin(symbol="LIFE"):
    return {"symbol": symbol, "class": "c", "claim": "some dated milestone",
            "event_date": "2026-09-15", "source": "somewhere public",
            "as_of": "2026-07-01", "expires": "2026-09-22", "provenance": "operator"}


def test_forward_catalyst_pin_refused_for_restricted_symbol(tmp_path, caplog):
    p = tmp_path / "fc.json"
    p.write_text(json.dumps({"items": [_pin("LIFE"), _pin("ADTN")]}))
    with caplog.at_level("ERROR"):
        fc = ForwardCatalysts(str(p))
    assert fc.malformed_n == 1  # counted where a counter exists (the F-b refusal pattern)
    assert any("RESTRICTED" in m for m in caplog.messages)
    assert fc.items_asof("LIFE", datetime(2026, 7, 15)) == []
    assert len(fc.items_asof("ADTN", datetime(2026, 7, 15))) == 1  # the clean pin still renders


def test_forward_catalyst_pin_refusal_is_case_insensitive(tmp_path):
    p = tmp_path / "fc.json"
    p.write_text(json.dumps({"items": [_pin("life")]}))
    fc = ForwardCatalysts(str(p))
    assert fc.malformed_n == 1 and fc.items_asof("life", datetime(2026, 7, 15)) == []


def test_forward_catalysts_fail_closed_on_broken_list(tmp_path, monkeypatch):
    bad = tmp_path / "restricted.json"
    bad.write_text("[]junk")
    monkeypatch.setattr(restricted, "DEFAULT_PATH", bad)
    p = tmp_path / "fc.json"
    p.write_text(json.dumps({"items": [_pin("ADTN")]}))
    # The channel constructor HALTS (the orchestrator's fail-soft wrapper then renders no block).
    with pytest.raises(restricted.RestrictedListError):
        ForwardCatalysts(str(p))


# ── the hard-seam guard: EXTREME conviction on a restricted name reaches NO book ───────────


def test_extreme_restricted_conviction_never_reaches_any_book(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    boom = _theme(conviction="EXTREME")          # restricted, strongest conviction the system allows
    cheap = Theme("copper", "FCX", "bullish", "thesis", conviction="EXTREME",
                  source="sentinel", sentinel_id=2)
    # (b) the union the council/books judge never contains it, whatever the conviction says …
    union = sentinels.union_candidates([], [boom, cheap])
    assert [t.symbol for t in union] == ["FCX"]
    # … so the REAL book never even evaluates it (the gates dispose only over the union) …
    res = run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0), themes=union, run_id=None)
    assert res.opened == 1  # FCX (cheap) trades via the gate; LIFE was never in the running
    evaluated = {r["symbol"] for r in conn.execute("SELECT symbol FROM convexity_eval")}
    assert "LIFE" not in evaluated
    # … and (c) even a RAW candidate list handed straight to the null books is vetoed.
    sres = shadow_book.run_shadow_cycle(config=CONFIG, conn=conn, clock=CLOCK,
                                        provider=_provider(), run_id=None, candidates=[boom])
    fres = fixed_basket.run_fixed_basket_3a_cycle(config=CONFIG, conn=conn, clock=CLOCK,
                                                  provider=_provider(), run_id=None,
                                                  candidates=[boom])
    assert sres.veto_reasons == {"restricted": 1} and fres.veto_reasons == {"restricted": 1}
    for table in ("convexity_positions", "shadow_positions", "fixed_basket_positions",
                  "shares_positions"):
        n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE symbol='LIFE'").fetchone()[0]  # noqa: S608
        assert n == 0, f"restricted symbol reached {table}"
