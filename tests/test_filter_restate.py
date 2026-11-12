"""#421 restate_v1 (operator word 2026-11-04, from the 11-12 boundary): faithful restatements of rendered figures no
longer dampen a council role — A: a rendered signed 3-decimal figure as a percent (−0.628 → 62.8%); B: a rendered $M
figure as $B to 3 decimals; C: the bare year of a rendered date. D (rounding, bps) is not adopted. The discovery
framer's scan is unchanged."""

from __future__ import annotations

import dataclasses

from council.context import restated_percent_tokens, synthetic_context_pack
from council.filters import apply_filter
from themes import Theme

FLNC = Theme("grid", "FLNC", "bearish", "grid storage")


def _pack(headlines=(), fundamentals=()):
    return dataclasses.replace(synthetic_context_pack(FLNC), headlines=list(headlines), fundamentals=list(fundamentals))


def _council(texts, pack):
    return apply_filter(texts, pack, confidence="MODERATE", accept_rendered_dates=True)


MARKERS = ["momentum_12m -0.628", "relative_strength_12m -0.773", "momentum_recent_3m +0.042"]


def test_a_rendered_marker_restated_as_a_percent_passes():
    conf, res = _council(["12-month momentum of -62.8% and relative strength -77.3%, 3m +4.2%"], _pack(MARKERS))
    assert (conf, res.flagged) == ("MODERATE", 0)


def test_the_framer_scan_is_unchanged_for_the_same_text():
    conf, res = apply_filter(["12-month momentum of -62.8%"], _pack(MARKERS), confidence="MODERATE")
    assert conf == "LOW" and res.details == ["unsupported figure: 62.8"]


def test_only_signed_three_decimal_figures_are_restated():
    # a news headline's plain numbers add nothing: "0.5%" is not the rendered marker shape
    assert restated_percent_tokens(_pack(["Fed holds at 0.5% as orders rise 12"])) == []
    conf, _ = _council(["orders up 50.0%"], _pack(["Fed holds at 0.5% as orders rise 12"]))
    assert conf == "LOW"


def test_a_news_headline_with_a_signed_three_decimal_figure_adds_nothing():
    assert restated_percent_tokens(_pack(["EPS came in at -0.125 vs est -0.110"])) == []      # not the marker shape


def test_an_unrendered_percent_still_flags():
    conf, res = _council(["momentum of -55.0%"], _pack(MARKERS))
    assert conf == "LOW" and res.details == ["unsupported figure: 55.0"]


def test_a_unitless_fundamentals_value_restated_as_a_percent_passes():
    accel = {"concept": "revenue", "metric": "qtr_yoy_accel", "value": -0.161, "latest_musd": None,
             "base_musd": None, "period_end": "2026-09-30", "filed": "2026-11-02"}
    conf, res = _council(["revenue acceleration of -16.1 points"], _pack(MARKERS, [accel]))
    assert (conf, res.flagged) == ("MODERATE", 0)


def test_a_billions_figure_to_three_decimals_passes():
    rev = {"concept": "revenue", "metric": "ttm_yoy", "value": 0.12, "latest_musd": 11855.0, "base_musd": 1246.0,
           "period_end": "2026-06-30", "filed": "2026-08-05"}
    conf, res = _council(["revenue reached $11.855B"], _pack(MARKERS, [rev]))
    assert (conf, res.flagged) == ("MODERATE", 0)


def test_the_bare_year_of_a_rendered_date_passes_and_another_year_flags():
    ln = {"concept": "revenue", "metric": "rev_annual_yoy", "value": -0.088, "latest_musd": 1971.2,
          "base_musd": 2162.5, "period_end": "2025-12-31", "filed": "2026-03-27"}
    pack = _pack(MARKERS, [ln])
    assert _council(["the 2025 annual period shows revenue -8.8%"], pack)[1].flagged == 0
    assert _council(["In 2025, revenue fell -8.8%"], pack)[1].flagged == 0              # the comma form (review)
    assert _council(["2,025 vessels"], pack)[0] == "LOW"                                # a count is not a year
    conf, res = _council(["the 2023 annual period"], pack)
    assert conf == "LOW" and res.details == ["unsupported figure: 2023"]


def test_rounding_is_not_adopted():
    ln = {"concept": "revenue", "metric": "ttm_yoy", "value": 6.987, "latest_musd": 120.0, "base_musd": 15.0,
          "period_end": "2026-09-30", "filed": "2026-11-01"}
    conf, res = _council(["revenue up +699%"], _pack(MARKERS, [ln]))                   # rendered +698.7% (option D)
    assert conf == "LOW" and res.details == ["unsupported figure: 699"]
