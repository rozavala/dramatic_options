"""424B5 deal-size parse: shares×price, gross fallback, recall (parseable vs not)."""

from data.prospectus import (
    classify_offering,
    is_atm_offering,
    offering_vs_float,
    parse_offering_size,
)

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


# ── offering-type classification (real-grounded fixtures, excerpted from live 424B5 covers
# 2026-06; the funnel's keep-biased routine-takedown drop) ────────────────────────────────────

# Clean ATM / continuous offerings → DROP (routine shelf take-down)
_ATM_REDHILL = (
    "Our common stock will be issued and sold from time to time under the At The Market "
    "Offering Agreement, that we entered into with H.C. Wainwright & Co., LLC, as sales agent."
)
_ATM_ASCENT = (
    "Common Stock We have entered into an at the market offering agreement (the Offering "
    "Agreement), dated May 16, 2024, with our sales agent, relating to shares of our common stock."
)
_ATM_REDWIRE = (
    "Common Stock We have entered into an equity distribution agreement (the Sales Agreement), "
    "dated May 6, 2026, under which we may offer and sell shares of our common stock."
)

# Keep-bias NEGATIVES — an ATM keyword/phrase appears but this is NOT a clean ATM offering, so it
# must NOT be dropped (a false drop = a wrongly-discarded candidate = toward a false World-2).
_FIRM_FROM_TIME = (  # firm-commitment + risk-factor 'from time to time' (Creative Realities)
    "Per Share Total Public offering price $ $ Underwriting discounts and commissions (1) $ $ "
    "Proceeds to us. New factors emerge from time to time, and it is not possible for us to "
    "predict which factors will affect our business."
)
_CONFLICT_REIT_FORWARD = (  # ATM-program mention BUT a forward underwritten deal (Curbline)
    "We are offering shares of our common stock on a forward basis under its at-the-market "
    "offering program (the ATM Program). Per Share Total Public offering price $ $ Underwriting "
    "discount(1) $ $. We will not receive any proceeds from the sale of shares of our common stock."
)
_NOTES_WITH_ATM_LIST = (  # 'at-the-market offerings' in a risk-factor LIST of a NOTES deal (Jefferies)
    "Capital markets transactions (notes, debt, equity participation units, at-the-market "
    "offerings, or other recapitalizations) are made weekly. The Aggregate Principal Amount of "
    "the Notes is $2,525,000. The Notes will mature on July 1, 2030."
)

# Other kinds → all KEPT for step-3, most noise-flagged
_NOTES_REALTY = (
    "% Notes due 2032 We are offering aggregate principal amount of our % Notes due 2032 (the "
    "notes). The notes will mature on March 1, 2032."
)
_CONVERT_NUVATION = (
    "We are offering $300,000,000 aggregate principal amount of our 3.50% Convertible Senior "
    "Notes due 2031, plus up to an additional $37,500,000 aggregate principal amount of notes to "
    "cover over-allotments."
)
_RD_GOLDMINING = (
    "Under this prospectus, we are offering in a registered direct offering to a certain "
    "purchaser 522,876 shares of our common stock."
)
_RD_XCHG = (
    "We have entered into a Securities Purchase Agreement (the Securities Purchase Agreement), "
    "dated as of June 25, 2026, with the purchaser identified on the signature pages thereto."
)
_SELLING_LIVEONE = (
    "We will not receive any cash proceeds from the offering of the Shares, however we will "
    "receive proceeds upon exercise of the warrants."
)
_FIRM_MAMAS = (
    "Per Share Total Public offering price $ $ Underwriting discounts and commissions (1) $ $ "
    "Proceeds, before expenses, to us."
)

# the labeled keep-bias-negative set (ATM keyword may appear, but none is a clean ATM offering)
_NON_ATM = [
    _FIRM_FROM_TIME, _CONFLICT_REIT_FORWARD, _NOTES_WITH_ATM_LIST, _NOTES_REALTY,
    _CONVERT_NUVATION, _RD_GOLDMINING, _RD_XCHG, _SELLING_LIVEONE, _FIRM_MAMAS,
]


def test_is_atm_clean_positives_recall():
    # recall on the labeled clean-ATM set = 3/3
    for txt in (_ATM_REDHILL, _ATM_ASCENT, _ATM_REDWIRE):
        assert is_atm_offering(txt) is True
        assert classify_offering(txt)["kind"] == "atm"
        assert classify_offering(txt)["routine_drop"] is True


def test_is_atm_keepbias_precision_no_false_drops():
    # PINNED: zero false ATM-positives on the labeled non-ATM set (the keep-bias property — a
    # false drop is the only error this gate must never make). The three load-bearing cases:
    # 'from time to time' in risk factors, an existing ATM-program mention in a forward deal,
    # and 'at-the-market offerings' in a notes risk-factor list.
    for txt in _NON_ATM:
        assert is_atm_offering(txt) is False, txt[:60]
        assert classify_offering(txt)["routine_drop"] is False


def test_classify_kinds_and_noise_flags():
    assert classify_offering(_NOTES_REALTY)["kind"] == "debt_notes"
    assert classify_offering(_CONVERT_NUVATION)["kind"] == "convertible_notes"
    assert classify_offering(_RD_GOLDMINING)["kind"] == "registered_direct"
    assert classify_offering(_RD_XCHG)["kind"] == "registered_direct"
    assert classify_offering(_SELLING_LIVEONE)["kind"] == "selling_holder"
    assert classify_offering(_FIRM_MAMAS)["kind"] == "firm_commitment"
    # firm-commitment is the clean candidate (kept, NOT noise-flagged)
    assert classify_offering(_FIRM_MAMAS)["noise_flag"] is False
    # likely-noise kinds are kept-but-flagged for step-3 triage
    for txt in (_NOTES_REALTY, _CONVERT_NUVATION, _RD_GOLDMINING, _SELLING_LIVEONE):
        assert classify_offering(txt)["noise_flag"] is True


def test_classify_unknown_when_no_structural_signal():
    out = classify_offering("This prospectus supplement relates to certain securities. See Risk Factors.")
    assert out["kind"] == "unknown"
    assert out["routine_drop"] is False
    assert out["noise_flag"] is False
