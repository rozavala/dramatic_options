"""Option-tradability ceiling: OSI parse, spread math, near-money put filtering, empty case."""

from datetime import date

from dramatic_options.options_tradability import parse_osi, spread_pct, summarize_put_tradability


def test_parse_osi():
    info = parse_osi("LCID260618P00001000")
    assert info["root"] == "LCID"
    assert info["expiry"] == date(2026, 6, 18)
    assert info["kind"] == "P"
    assert info["strike"] == 1.0
    # a 5-digit-root call with a fractional strike
    c = parse_osi("AAPL240119C00150000")
    assert c["kind"] == "C" and c["strike"] == 150.0
    assert parse_osi("garbage") is None


def test_spread_pct():
    assert spread_pct(0.95, 1.05) == (1.05 - 0.95) / 1.0
    assert spread_pct(0.0, 0.05) is None     # one-sided (no bid)
    assert spread_pct(1.0, 0.5) is None      # crossed
    assert spread_pct(None, 1.0) is None


def test_summarize_filters_to_near_money_short_dated_puts():
    asof = date(2024, 1, 1)
    quotes = [
        # near-money puts, ~30 DTE — counted
        {"symbol": "ZZZ240131P00010000", "bid": 0.90, "ask": 1.10},  # strike 10, spread .2
        {"symbol": "ZZZ240131P00011000", "bid": 1.40, "ask": 1.60},  # strike 11, spread .133
        # a call near money — ignored (puts only)
        {"symbol": "ZZZ240131C00010000", "bid": 0.5, "ask": 0.6},
        # a put far from money (strike 30 vs px 10) — excluded by moneyness band
        {"symbol": "ZZZ240131P00030000", "bid": 19.0, "ask": 21.0},
        # a long-dated put (2026) — excluded by max_expiry_days
        {"symbol": "ZZZ261218P00010000", "bid": 2.0, "ask": 2.2},
    ]
    out = summarize_put_tradability(quotes, underlying_price=10.0, as_of=asof)
    assert out.tradable is True
    assert out.n_puts_quoted == 2
    assert out.median_put_spread_pct is not None
    # median of {0.2, 0.1333} = mean of the two
    assert abs(out.median_put_spread_pct - (0.2 + (0.2 / 1.5)) / 2) < 1e-6


def test_summarize_untradable_when_no_two_sided_quote():
    asof = date(2024, 1, 1)
    quotes = [
        {"symbol": "ZZZ240131P00010000", "bid": 0.0, "ask": 0.10},  # no bid
        {"symbol": "ZZZ240131P00011000", "bid": 0.0, "ask": 0.05},
    ]
    out = summarize_put_tradability(quotes, underlying_price=10.0, as_of=asof)
    assert out.tradable is False
    assert out.median_put_spread_pct is None
    assert "snapshot" in out.note
