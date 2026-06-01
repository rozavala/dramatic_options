"""Divergence: sign convention, N_min skip, cross-sectional z, theme aggregation."""

from datetime import UTC, datetime, timedelta

from divergence import FADE, LONG, build_panel

AS_OF = datetime(2024, 1, 1, tzinfo=UTC)

CONFIG = {
    "signal": {
        "narrative": {"count_window_days": 21, "baseline_window_days": 126,
                      "ewma_span_days": 10, "lexicon_weight": 0.15},
        "substance": {"ewma_span_days": 30, "lookback_days": 120,
                      "event_weights": {"8-K:1.01": 1.0, "8-K:3.02": -1.0, "FORM4": 0.4}},
        "divergence": {"neutral_threshold": 0.4, "n_min_cross_section": 3},
    }
}


def _news(n):
    return [{"ts": (AS_OF - timedelta(days=i + 1)).isoformat(), "headline": "h",
             "source": "x", "symbols": []} for i in range(n)]


def _filing(form, items):
    return [{"ts": (AS_OF - timedelta(days=3)).isoformat(), "form": form, "items": items}]


class _StubNews:
    def __init__(self, m):
        self.m = m

    def headlines_asof(self, sym, as_of):
        return self.m.get(sym, [])


class _StubFilings:
    def __init__(self, m):
        self.m = m

    def filings_asof(self, sym, as_of):
        return self.m.get(sym, [])


def test_sign_convention_hype_fades_quiet_longs():
    news = _StubNews({"HYPE": _news(15), "QUIET": _news(1), "MIDA": _news(6), "MIDB": _news(7)})
    filings = _StubFilings({
        "HYPE": _filing("8-K", ["3.02"]),     # dilution → low substance
        "QUIET": _filing("8-K", ["1.01"]),    # contract → high substance
        "MIDA": _filing("4", []),
        "MIDB": _filing("4", []),
    })
    theme_of = {"HYPE": "alpha", "QUIET": "alpha", "MIDA": "beta", "MIDB": "beta"}
    panel = build_panel(AS_OF, list(theme_of), theme_of, news=news, filings=filings, config=CONFIG)

    assert not panel.skipped
    by = {n.symbol: n for n in panel.names}
    assert by["HYPE"].divergence > 0 > by["QUIET"].divergence
    assert by["HYPE"].direction == FADE
    assert by["QUIET"].direction == LONG
    # HYPE's dilution filing is a weighted event → density flag set
    assert by["HYPE"].has_substance_event is True


def test_n_min_skips_thin_cross_section():
    news = _StubNews({"A": _news(3), "B": _news(4)})
    filings = _StubFilings({"A": _filing("4", []), "B": _filing("4", [])})
    panel = build_panel(AS_OF, ["A", "B"], {"A": "t", "B": "t"},
                        news=news, filings=filings, config=CONFIG)
    assert panel.skipped and panel.n_valid == 2


def test_theme_aggregation_present():
    news = _StubNews({s: _news(i + 1) for i, s in enumerate(["A", "B", "C", "D"])})
    filings = _StubFilings({s: _filing("4", []) for s in ["A", "B", "C", "D"]})
    theme_of = {"A": "x", "B": "x", "C": "y", "D": "y"}
    panel = build_panel(AS_OF, list(theme_of), theme_of, news=news, filings=filings, config=CONFIG)
    themes = {t.theme: t for t in panel.themes}
    assert set(themes) == {"x", "y"}
    assert all(t.n_members == 2 for t in panel.themes)
    # rationale populated on names
    assert panel.names[0].rationale["narrative"]["count_recent"] >= 0
