"""424B5 deal-size parse: shares×price, gross fallback, recall (parseable vs not)."""

from data.prospectus import offering_vs_float, parse_offering_size

_PARSEABLE = """
PROSPECTUS SUPPLEMENT
We are offering 12,500,000 shares of our common stock.
The public offering price is $8.00 per share.
"""

_GROSS_ONLY = """
We are offering shares of common stock in an at-the-market offering with an
aggregate offering price of $50,000,000.
"""

_NOT_PARSEABLE = """
This prospectus supplement relates to the resale of certain securities. See "Risk Factors".
"""


def test_parse_shares_and_price_and_gross():
    out = parse_offering_size(_PARSEABLE)
    assert out["shares"] == 12_500_000
    assert out["price"] == 8.0
    assert out["gross_usd"] == 100_000_000.0


def test_parse_gross_fallback_with_million_scale():
    out = parse_offering_size(_GROSS_ONLY)
    assert out["shares"] is None
    assert out["gross_usd"] == 50_000_000.0


def test_unparseable_returns_none():
    assert parse_offering_size(_NOT_PARSEABLE) is None


def test_offering_vs_float():
    assert offering_vs_float(2_000_000, 10_000_000) == 0.2
    assert offering_vs_float(None, 10) is None
    assert offering_vs_float(2_000_000, 0) is None
