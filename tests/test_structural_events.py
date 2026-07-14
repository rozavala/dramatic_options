"""The structural-event leg (PREREG_EVENT_LEG): exact-membership matching, the closed lookback,
counters/fail-soft, the factory's config seam, and the runs.note append helper."""

from datetime import UTC, datetime, timedelta

import state
from data.structural_events import (
    EdgarEventProvider,
    allowed_forms,
    build_event_provider,
    event_status_line,
    form_set_hash,
)

AS_OF = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
BASES = ["424B5", "S-1", "S-3", "F-10", "SUPPL", "SC 13D", "SCHEDULE 13D"]


class FakeFilings:
    """Duck-types the two FilingsData calls the provider makes."""

    def __init__(self, records_by_symbol, ciks=None, raise_for=()):
        self._records = records_by_symbol
        self._ciks = ciks if ciks is not None else {s: "0000000001" for s in records_by_symbol}
        self._raise_for = set(raise_for)

    def _cik(self, symbol):
        return self._ciks.get(symbol.upper())

    def filings_asof(self, symbol, as_of):
        if symbol.upper() in self._raise_for:
            raise RuntimeError("boom")
        return [r for r in self._records.get(symbol.upper(), [])
                if r["ts"] <= as_of.isoformat()]


def _rec(form, days_ago, as_of=AS_OF):
    return {"form": form, "ts": (as_of - timedelta(days=days_ago)).isoformat()}


def _provider(records, **kw):
    return EdgarEventProvider(FakeFilings(records, **kw.pop("filings_kw", {})),
                              forms=allowed_forms(BASES), **kw)


# ── exact membership (P1.2 — never a prefix) ────────────────────────────────────────────────────

def test_allowed_forms_is_base_plus_amendment_only():
    allowed = allowed_forms(["S-1", "SC 13D"])
    assert allowed == {"S-1", "S-1/A", "SC 13D", "SC 13D/A"}


def test_overmatch_near_misses_do_not_surface():
    # S-11 (REIT), S-1MEF, S-3ASR (WKSI routine — deliberately excluded), 424B3 spam,
    # F-10POS: ALL present and fresh, NONE may match.
    p = _provider({"X": [_rec("S-11", 1), _rec("S-1MEF", 1), _rec("S-3ASR", 1),
                         _rec("424B3", 1), _rec("F-10POS", 1), _rec("424B4", 2)]})
    assert p.has_structural_event("X", AS_OF) == (False, None)


def test_pinned_forms_and_amendments_match():
    for form, base in [("424B5", "424B5"), ("S-1/A", "S-1"), ("SUPPL", "SUPPL"),
                       ("F-10/A", "F-10"), ("SC 13D/A", "SC 13D"),
                       ("SCHEDULE 13D", "SCHEDULE 13D")]:
        p = _provider({"X": [_rec(form, 3)]})
        assert p.has_structural_event("X", AS_OF) == (True, base), form


# ── the closed lookback window ──────────────────────────────────────────────────────────────────

def test_lookback_day14_in_day15_out():
    p14 = _provider({"X": [_rec("424B5", 14)]}, lookback_days=14)
    assert p14.has_structural_event("X", AS_OF)[0] is True   # closed: day-14 IN
    p15 = _provider({"X": [_rec("424B5", 15)]}, lookback_days=14)
    assert p15.has_structural_event("X", AS_OF)[0] is False  # day-15 OUT


def test_no_lookahead_future_filing_invisible():
    # filings_asof filters ts <= as_of (mirrors FilingsData) — a tomorrow filing never matches.
    p = _provider({"X": [_rec("424B5", -1)]})
    assert p.has_structural_event("X", AS_OF) == (False, None)


def test_newest_match_wins():
    p = _provider({"X": [_rec("S-1", 10), _rec("424B5", 2)]})
    assert p.has_structural_event("X", AS_OF) == (True, "424B5")


# ── counters + fail-soft (P1.3 — never invisible) ──────────────────────────────────────────────

def test_counters_split_no_cik_from_errors():
    p = _provider({"A": [_rec("424B5", 2)], "B": [], "C": []},
                  filings_kw={"ciks": {"A": "1", "B": None, "C": "3"},
                              "raise_for": ("C",)})
    assert p.has_structural_event("A", AS_OF)[0] is True
    assert p.has_structural_event("B", AS_OF) == (False, None)   # no CIK
    assert p.has_structural_event("C", AS_OF) == (False, None)   # error, swallowed
    c = p.counters
    assert (c.checked, c.cik_resolved, c.no_cik, c.fresh, c.errors) == (3, 2, 1, 1, 1)
    assert c.fresh_names == ["A"]
    assert "checked=3" in c.status() and "no_cik=1" in c.status()


def test_systemic_failure_thresholds():
    from data.structural_events import EventCounters
    assert EventCounters(checked=3, errors=3).systemic_failure() is False      # too small to judge
    assert EventCounters(checked=10, errors=8).systemic_failure() is True      # errors ≈ checked
    assert EventCounters(checked=10, cik_resolved=0).systemic_failure() is True  # ticker-map dead
    assert EventCounters(checked=10, cik_resolved=9, errors=1).systemic_failure() is False


def test_form_set_hash_stable_and_order_insensitive():
    h = form_set_hash(["S-1", "424B5"])
    assert h == form_set_hash(["424B5", "S-1"]) and len(h) == 6
    assert h != form_set_hash(["424B5", "S-1", "SC 13D"])  # a set change re-stamps the record


# ── the factory's config seam ───────────────────────────────────────────────────────────────────

def test_factory_disabled_and_missing_ua_fail_soft():
    base = {"discovery": {"events": {"enabled": False}}, "edgar": {}}
    assert build_event_provider(base, cache=None, as_of=AS_OF) == (None, "disabled")
    on = {"discovery": {"events": {"enabled": True, "forms": ["424B5"]}}, "edgar": {}}
    provider, reason = build_event_provider(on, cache=None, as_of=AS_OF)
    assert provider is None and reason == "no EDGAR_USER_AGENT"
    nf = {"discovery": {"events": {"enabled": True, "forms": []}},
          "edgar": {"user_agent": "x y@z"}}
    assert build_event_provider(nf, cache=None, as_of=AS_OF)[0] is None


def test_factory_builds_provider_with_injected_client():
    cfg = {"discovery": {"events": {"enabled": True, "forms": ["424B5", "S-1"],
                                    "lookback_days": 7}},
           "edgar": {"user_agent": "x y@z"}, "cache": {"dir": "data/cache"}}
    provider, reason = build_event_provider(cfg, cache=object(), as_of=AS_OF,
                                            edgar_client=object())
    assert reason == "on" and provider is not None
    assert provider.lookback_days == 7
    assert provider.allowed == {"424B5", "424B5/A", "S-1", "S-1/A"}


# ── the post-scan note stamp (P2-B) ─────────────────────────────────────────────────────────────

def test_append_run_note_is_post_scan_durable(convexity_db):
    run_id = state.record_run(convexity_db, mode="DISCOVERY", equity=None, note="weekly scan")
    state.append_run_note(convexity_db, run_id, "events:ON ev=abc123 checked=33 fresh=2 err=0")
    note = convexity_db.execute("SELECT note FROM runs WHERE id=?", (run_id,)).fetchone()[0]
    assert note == "weekly scan · events:ON ev=abc123 checked=33 fresh=2 err=0"


# ── the status line + the fresh-on-active-lineage stamp (2026-07-13 additive amendment) ────────

def _counters(fresh_names=()):
    from data.structural_events import EventCounters
    c = EventCounters(checked=33, cik_resolved=31, no_cik=2, fresh=len(fresh_names), errors=0)
    c.fresh_names = list(fresh_names)
    return c


def test_event_status_line_byte_identical_without_blocked():
    """The historical format is untouched when no fresh name sits on an active lineage."""
    line = event_status_line("abc123", _counters(["LUNR"]), active_lineage={"PL", "FLNC"})
    assert line == "events:ON ev=abc123 checked=33 cik=31 no_cik=2 fresh=1 err=0 fresh_names=LUNR"
    # and with no fresh names at all, no fresh_names field either
    assert event_status_line("abc123", _counters()) == (
        "events:ON ev=abc123 checked=33 cik=31 no_cik=2 fresh=0 err=0")


def test_event_status_line_stamps_fresh_on_active_lineage():
    """A fresh-event name the SAME scan's novelty dedup excludes (live lineage) is stamped —
    detected-but-unjudgeable must never read byte-identically to detected-and-riding (the LUNR
    13D/A gap)."""
    line = event_status_line("abc123", _counters(["LUNR", "CC"]), active_lineage={"LUNR", "PL"})
    assert "fresh_names=CC,LUNR" in line
    assert line.endswith("fresh_on_active_lineage=LUNR")


def test_event_status_line_blocked_requires_fresh():
    """An active-lineage name with NO fresh event is not stamped (the field is the intersection)."""
    line = event_status_line("abc123", _counters(["CC"]), active_lineage={"LUNR", "PL"})
    assert "fresh_on_active_lineage" not in line
    # case-insensitive on the lineage side (DB symbols are upper, but don't depend on it)
    line2 = event_status_line("abc123", _counters(["LUNR"]), active_lineage={"lunr"})
    assert line2.endswith("fresh_on_active_lineage=LUNR")
