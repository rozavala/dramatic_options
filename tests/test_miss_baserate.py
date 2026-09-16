"""Miss base-rate ledger — the pure core (PREREG_MISS_BASERATE.md): sealing, the frozen draw, the
maturity-gated aggregation, the small-n guard, and the never-a-symbol report."""
from __future__ import annotations

import tempfile
from pathlib import Path

import miss_baserate as mb


def _row(key, cohort, direction, cheap, *, date="2026-09-20", close=100.0):
    return mb.SweepRow(date, key, cohort, direction, 1, cheap, close, "opra")


def _fwd_factory(series: dict[str, tuple[list[float], bool]]):
    return lambda key, date: series.get(key, ([], False))


def test_seal_is_stable_case_insensitive_and_symbol_free():
    assert mb.seal("nvda") == mb.seal("NVDA")
    assert len(mb.seal("NVDA")) == 12
    assert "NVDA" not in mb.seal("NVDA").upper()
    assert mb.seal("NVDA") != mb.seal("NVDB")


def test_draw_is_deterministic_and_excludes_universe():
    pool = [f"S{i:03}" for i in range(500)] + ["NVDA", "KKR"]
    a = mb.draw_denominator(pool, {"NVDA", "KKR"}, k=300)
    b = mb.draw_denominator(list(reversed(pool)), {"nvda", "kkr"}, k=300)
    assert a == b and len(a) == 300
    assert "NVDA" not in a and "KKR" not in a
    assert mb.draw_denominator(pool, set(), seed=1, k=300) != a


def test_fund_like_filter():
    assert mb.is_fund_like("iShares Silver Trust")
    assert mb.is_fund_like("Global X Uranium ETF")
    assert mb.is_fund_like("Acme Corp Warrants")
    assert not mb.is_fund_like("NVIDIA Corporation Common Stock")
    assert not mb.is_fund_like("Trustmark Corporation")  # word boundary: not 'Trust'


def test_ledger_roundtrip_preserves_blank_gate(tmp_path=None):
    d = Path(tempfile.mkdtemp(prefix="mb_"))
    p = d / "ledger.csv"
    rows = [_row("k1", "universe", "bullish", 1), _row("k2", "market", "bearish", None, close=None)]
    mb.append_rows(p, rows)
    mb.append_rows(p, [_row("k3", "market", "bullish", 0)])
    back = mb.read_rows(p)
    assert [r.key for r in back] == ["k1", "k2", "k3"]
    assert back[1].gate_cheap is None and back[1].entry_close is None
    assert back[0].gate_cheap == 1 and back[0].entry_close == 100.0
    assert p.read_text().splitlines()[0] == ",".join(mb.LEDGER_COLUMNS)


def test_aggregate_maturity_gate_and_direction():
    rows = [
        _row("up", "universe", "bullish", 1),      # +60% at 63 → big
        _row("dn", "universe", "bearish", 1),      # −60% raw, bearish → directional +60% → big
        _row("wrongway", "universe", "bullish", 1),  # −60% raw, bullish → not big
        _row("young", "universe", "bullish", 1),   # only 10 bars, not terminated → accruing
        _row("dead", "market", "bullish", 0),      # terminated after 5 bars at +80% → matured, big
        _row("nogate", "market", "bullish", None),  # skipped entirely
    ]
    series = {
        "up": ([100.0] * 62 + [160.0], False),
        "dn": ([100.0] * 62 + [40.0], False),
        "wrongway": ([100.0] * 62 + [40.0], False),
        "young": ([101.0] * 10, False),
        "dead": ([120.0] * 4 + [180.0], True),
    }
    cells = mb.aggregate(rows, _fwd_factory(series), horizons=(63,))
    u = cells[("universe", 63)]
    assert (u.n_matured, u.n_accruing, u.n_cheap, u.n_big, u.n_cheap_big) == (3, 1, 3, 2, 2)
    m = cells[("market", 63)]
    assert (m.n_matured, m.n_cheap, m.n_notcheap, m.n_notcheap_big, m.n_big) == (1, 0, 1, 1, 1)
    assert ("market", 126) not in cells  # horizons argument respected


def test_small_n_guard_blocks_rates_and_z():
    c = mb.Cell(n_matured=10, n_cheap=10, n_cheap_big=9)
    assert c.rate(c.n_cheap_big, c.n_cheap) is None
    assert mb.two_proportion_z(9, 10, 1, 10) is None
    assert mb.two_proportion_z(15, 20, 5, 20) is not None and mb.two_proportion_z(15, 20, 5, 20) > 0


def test_render_never_emits_a_key_or_symbol():
    keys = [mb.seal(s) for s in ("NVDA", "KKR", "FIG")]
    rows = [_row(k, "universe", "bullish", 1) for k in keys]
    series = {k: ([100.0] * 62 + [200.0], False) for k in keys}
    out = mb.render(mb.aggregate(rows, _fwd_factory(series), horizons=(63,)), horizons=(63,))
    for k in keys:
        assert k not in out
    for s in ("NVDA", "KKR", "FIG"):
        assert s not in out
    assert "matured=   3" in out and "n<20" in out and "R1 z" in out
