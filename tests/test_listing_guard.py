"""#458 listing guard: the ATKR replay, exact-membership forms, held-name paging debounce, null-book silence,
fail-soft-not-fail-silent, and the lookahead probe. The EDGAR source is the REAL ``FilingsData`` over a
``PointInTimeCache`` (offline: CIKs from overrides), holding records in the shape ``_normalize_filing_block`` emits."""

import json
import logging
from datetime import UTC, datetime

import listing_guard as lg
import state
from data.cache import PointInTimeCache
from data.filings import _EARLY, SOURCE, FilingsData

ATKR_CIK = "0001666138"
COVERED_THROUGH = datetime(2027, 1, 1, tzinfo=UTC)


def _rec(form, ts, acc, items=()):
    return {"ts": ts, "form": form, "items": list(items), "accession": acc,
            "primary_document": "doc.htm", "cik": ATKR_CIK}


# ATKR's real filings (records/2026-11-09_atkr_removal.md, data/cache/filings/ATKR.json).
ATKR_DEFM14A = _rec("DEFM14A", "2026-09-09T10:05:00+00:00", "0001193125-26-000901")
ATKR_8K = _rec("8-K", "2026-10-19T12:00:00+00:00", "0001193125-26-001019",
               ("1.02", "2.01", "3.01", "3.03", "5.01", "5.02", "5.03", "9.01"))
ATKR_25NSE = _rec("25-NSE", "2026-10-19T13:30:00+00:00", "0000876661-26-001019")
ATKR_15_12G = _rec("15-12G", "2026-10-29T16:00:00+00:00", "0001193125-26-001029")


def _filings(tmp_path, by_symbol, ciks=None):
    cache = PointInTimeCache(tmp_path / "cache")
    for sym, recs in by_symbol.items():
        cache.write(SOURCE, sym, recs, coverage_from=_EARLY, coverage_through=COVERED_THROUGH)
    overrides = ciks if ciks is not None else {s: ATKR_CIK for s in by_symbol}
    return FilingsData(cache, edgar=None, fetch_end=COVERED_THROUGH, cik_overrides=overrides)


def _at(y, m, d):
    return datetime(y, m, d, 21, 0, tzinfo=UTC)


def _classes(res, sym="ATKR"):
    return {h.klass for h in res.hits if h.symbol == sym}


# ── the ATKR replay ──────────────────────────────────────────────────────────────────────────────────────────────
def test_atkr_delisting_flagged_the_day_after_the_25nse_not_before(tmp_path):
    f = _filings(tmp_path, {"ATKR": [ATKR_25NSE, ATKR_15_12G]})
    before = lg.check_names(["ATKR"], f, _at(2026, 10, 18))
    assert before.hits == [] and before.errors == 0 and before.checked == 1
    after = lg.check_names(["ATKR"], f, _at(2026, 10, 20))
    assert [(h.klass, h.form, h.accession) for h in after.hits] == [
        ("delisting", "25-NSE", ATKR_25NSE["accession"])]


def test_atkr_with_full_history_the_merger_proxy_warns_before_the_delisting(tmp_path):
    f = _filings(tmp_path, {"ATKR": [ATKR_DEFM14A, ATKR_8K, ATKR_25NSE, ATKR_15_12G]})
    assert _classes(lg.check_names(["ATKR"], f, _at(2026, 10, 18))) == {"deal"}
    res = lg.check_names(["ATKR"], f, _at(2026, 10, 20))
    assert {h.form for h in res.hits} == {"DEFM14A", "25-NSE"}   # the 8-K is not a signal (module docstring)
    late = lg.check_names(["ATKR"], f, _at(2026, 10, 30))      # the proxy (51 days old) has left the window
    assert {h.form for h in late.hits} == {"25-NSE", "15-12G"}


def test_window_is_closed_45_days(tmp_path):
    f = _filings(tmp_path, {"ATKR": [ATKR_25NSE]})
    ts = datetime.fromisoformat(ATKR_25NSE["ts"])
    from datetime import timedelta

    assert lg.check_names(["ATKR"], f, ts + timedelta(days=lg.WINDOW_DAYS)).hits
    assert not lg.check_names(["ATKR"], f, ts + timedelta(days=lg.WINDOW_DAYS, seconds=1)).hits


# ── exact membership ─────────────────────────────────────────────────────────────────────────────────────────────
def test_form_matching_is_exact_membership_never_prefix():
    for form in ("25", "25/A", "25-NSE", "25-NSE/A", "15-12G", "15-12B/A", "15-15D"):
        assert lg.classify_form(form) == "delisting", form
    for form in ("DEFM14A", "PREM14A/A", "SC TO-T", "SC TO-T/A", "SC TO-I", "SC 13E3", "SC 14D9/A"):
        assert lg.classify_form(form) == "deal", form
    for form in ("25-X", "250", "2", "25-NSE/B", "15-12", "15-12G/AA", "15F-12G", "SC TO-C", "SC 14D9C",
                 "SC 13E4", "DEFA14A", "PREM14C", "DEFM14C", "8-K", "SC TO-T ", "sc to-t", ""):
        assert lg.classify_form(form) is None, form


# ── paging: held real name once per accession; null-only never ───────────────────────────────────────────────────
def _open_real(conn, symbol="ATKR", rationale=None):
    return state.record_convexity_position(
        conn, run_id=None, opened_at="2026-09-01T00:00:00+00:00", theme="t", symbol=symbol, direction="bullish",
        structure_kind="long_call", contract_symbol=f"{symbol}270115C00100000", expiry="2027-01-15",
        strike=100.0, dte=300, moneyness=0.2, contracts=1, entry_premium_per_contract=150.0,
        total_premium=150.0, rationale=rationale or {"why": "thesis"})


def _open_shadow(conn, symbol="ATKR"):
    return state.record_shadow_position(
        conn, run_id=None, origin="hand_seed", opened_at="2026-09-01T00:00:00+00:00", theme="t", symbol=symbol,
        direction="bullish", structure_kind="long_call", contract_symbol=f"{symbol}270115C00100000",
        expiry="2027-01-15", strike=100.0, dte=300, moneyness=0.2, contracts=1,
        entry_premium_per_contract=150.0, total_premium=150.0)


class Pager:
    def __init__(self):
        self.calls = []

    def __call__(self, title, message, *, priority=0):
        self.calls.append((title, message, priority))
        return True


def _run(conn, f, as_of, pager, config=None):
    roles = lg.names_to_check(config or {}, conn, as_of=as_of)
    res = lg.check_names(roles, f, as_of)
    return lg.dispose(conn, res, roles, as_of=as_of, run_id=None, notify_send=pager)


def test_pending_deal_on_held_name_pages_once_not_on_the_next_run(tmp_path, convexity_db):
    pid = _open_real(convexity_db)
    f = _filings(tmp_path, {"ATKR": [ATKR_DEFM14A]})
    pager = Pager()
    _run(convexity_db, f, _at(2026, 9, 10), pager)
    assert len(pager.calls) == 1 and pager.calls[0][2] == 1 and "ATKR" in pager.calls[0][0]
    _run(convexity_db, f, _at(2026, 9, 11), pager)
    assert len(pager.calls) == 1
    rat = json.loads(convexity_db.execute("SELECT rationale FROM convexity_positions WHERE id=?",
                                          (pid,)).fetchone()["rationale"])
    assert rat["why"] == "thesis" and rat["paged"] == {"listing_guard:" + ATKR_DEFM14A["accession"]: "2026-09-10"}


def test_a_new_accession_on_the_same_held_name_pages_again(tmp_path, convexity_db):
    _open_real(convexity_db)
    pager = Pager()
    _run(convexity_db, _filings(tmp_path / "a", {"ATKR": [ATKR_DEFM14A]}), _at(2026, 10, 18), pager)
    _run(convexity_db, _filings(tmp_path / "b", {"ATKR": [ATKR_DEFM14A, ATKR_25NSE]}), _at(2026, 10, 20), pager)
    assert len(pager.calls) == 2 and "25-NSE" in pager.calls[1][1] and "DEFM14A" not in pager.calls[1][1]


def test_null_book_only_hit_is_logged_not_paged(tmp_path, convexity_db, caplog):
    _open_shadow(convexity_db)
    pager = Pager()
    with caplog.at_level(logging.INFO, logger="listing_guard"):
        line = _run(convexity_db, _filings(tmp_path, {"ATKR": [ATKR_25NSE]}), _at(2026, 10, 20), pager)
    assert pager.calls == []
    assert "delisting=1" in line and "paged=0" in line and " hits=" not in line   # not on the run note either
    assert any("ATKR [null]" in r.getMessage() for r in caplog.records)


def test_universe_hit_is_noted_on_the_run_and_nothing_is_edited(tmp_path, convexity_db):
    run_id = state.record_run(convexity_db, mode="PAPER", equity=None, note="paper cycle")
    config = {"universe": {"themes": {"_comment": "x", "grid_equipment": ["ATKR", "AMSC"]}}}
    before = json.dumps(config, sort_keys=True)
    f = _filings(tmp_path, {"ATKR": [ATKR_25NSE], "AMSC": []}, ciks={"ATKR": ATKR_CIK, "AMSC": "0000880807"})
    roles = lg.names_to_check(config, convexity_db, as_of=_at(2026, 10, 20))
    lg.dispose(convexity_db, lg.check_names(roles, f, _at(2026, 10, 20)), roles, as_of=_at(2026, 10, 20),
               run_id=run_id, notify_send=Pager())
    note = convexity_db.execute("SELECT note FROM runs WHERE id=?", (run_id,)).fetchone()["note"]
    assert "listing_guard: checked=2 delisting=1" in note and "ATKR(universe) delisting:25-NSE@2026-10-19" in note
    assert json.dumps(config, sort_keys=True) == before


# ── fail-soft is not fail-silent ─────────────────────────────────────────────────────────────────────────────────
def test_a_failing_source_is_an_unknown_and_a_counted_error_never_no_events(tmp_path, convexity_db, caplog):
    _open_real(convexity_db)
    cache = PointInTimeCache(tmp_path / "empty")          # no payload → CacheMiss on read
    f = FilingsData(cache, edgar=None, fetch_end=COVERED_THROUGH, cik_overrides={"ATKR": ATKR_CIK})
    pager = Pager()
    with caplog.at_level(logging.INFO, logger="listing_guard"):
        line = _run(convexity_db, f, _at(2026, 10, 20), pager)
    assert "err=1" in line and "unknown=ATKR" in line and pager.calls == []
    assert any(r.levelno == logging.WARNING and "fail-soft is not fail-silent" in r.getMessage()
               for r in caplog.records)


def test_no_edgar_source_counts_every_name_as_an_error(convexity_db):
    res = lg.check_names(["ATKR", "AMSC"], None, _at(2026, 10, 20))
    assert res.errors == 2 and res.hits == [] and res.mostly_failed()


def test_no_cik_is_distinguished_from_an_error(tmp_path):
    f = _filings(tmp_path, {"ATKR": [ATKR_25NSE]}, ciks={})
    res = lg.check_names(["ATKR"], f, _at(2026, 10, 20))
    assert res.no_cik == 1 and res.errors == 0 and res.unknown == ["ATKR"] and not res.mostly_failed()


def test_venue_leg_flags_inactive_and_counts_its_own_failures(tmp_path):
    f = _filings(tmp_path, {"ATKR": [], "AMSC": [], "FLNC": []},
                 ciks={"ATKR": ATKR_CIK, "AMSC": "1", "FLNC": "2"})
    assets = {"ATKR": {"status": "inactive", "tradable": False}, "AMSC": {"status": "active", "tradable": True}}

    def asset_of(sym):
        return assets[sym]                                   # FLNC raises KeyError

    res = lg.check_names(["ATKR", "AMSC", "FLNC"], f, _at(2026, 10, 20), asset_of=asset_of)
    assert [(h.symbol, h.klass) for h in res.hits] == [("ATKR", "venue")]
    assert res.venue_errors == 1 and res.errors == 0 and "venue_err=1" in res.status()
    assert "venue=off" in lg.check_names(["ATKR"], f, _at(2026, 10, 20)).status()


# ── point-in-time ────────────────────────────────────────────────────────────────────────────────────────────────
def test_lookahead_probe_nothing_after_as_of_influences_the_result(tmp_path):
    f = _filings(tmp_path, {"ATKR": [ATKR_25NSE, ATKR_15_12G]})
    res = lg.check_names(["ATKR"], f, _at(2026, 10, 20))
    assert ATKR_15_12G["accession"] not in {h.accession for h in res.hits}

    class Leaky:                                             # a source that ignores as_of entirely
        def _cik(self, symbol):
            return ATKR_CIK

        def filings_asof(self, symbol, as_of):
            return [ATKR_25NSE, ATKR_15_12G]

    leaky = lg.check_names(["ATKR"], Leaky(), _at(2026, 10, 18))
    assert leaky.hits == []
    assert [h.form for h in lg.check_names(["ATKR"], Leaky(), _at(2026, 10, 20)).hits] == ["25-NSE"]


def test_names_cover_universe_sentinels_real_and_null_books(convexity_db):
    _open_real(convexity_db, "NVDA")
    _open_shadow(convexity_db, "ATKR")
    roles = lg.names_to_check({"universe": {"themes": {"_c": ["ZZZ"], "a": ["fcx", "NVDA"]}}}, convexity_db,
                              as_of=_at(2026, 10, 20))
    assert roles == {"FCX": {"universe"}, "NVDA": {"universe", "real"}, "ATKR": {"null"}}


def test_orchestrator_wiring_is_one_fail_soft_block_after_entries_and_skipped_in_demo():
    from pathlib import Path

    src = Path(__file__).resolve().parents[1].joinpath("orchestrator.py").read_text()
    call = "listing_guard.run_nightly(conn, config, run_id=run_id, cache=chain_cache, client=client,"
    assert src.count(call) == 1
    i = src.index(call)
    assert src.index("result = run_paper_cycle(") < src.index("cheapness_watch.record_cheapness(") < i
    assert i < src.index("_print_book_summary(conn, config)\n        return 0")
    block = src[src.rindex("if not demo:", 0, i): src.index("\n\n", i)]
    assert "try:" in block and 'log.warning("listing guard failed (non-fatal): %s", e)' in block
