"""#458 listing guard: the ATKR replay, exact-membership forms, held-name paging debounce, null-book silence,
fail-soft-not-fail-silent, and the lookahead probe. The EDGAR source is the REAL ``FilingsData`` over a
``PointInTimeCache`` (offline: CIKs from overrides), holding records in the shape ``_normalize_filing_block`` emits."""

import json
import logging
from datetime import UTC, datetime, timedelta

import listing_guard as lg
import state
from data.cache import PointInTimeCache
from data.filings import _EARLY, SOURCE, FilingsData

ATKR_CIK = "0001666138"
COVERED_THROUGH = datetime(2028, 1, 1, tzinfo=UTC)


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
    late = lg.check_names(["ATKR"], f, _at(2026, 10, 30))      # the proxy (51 days old) is still a pending deal
    assert {h.form for h in late.hits} == {"DEFM14A", "25-NSE", "15-12G"}


def test_per_class_windows_are_closed_deal_365_delisting_90(tmp_path):
    f = _filings(tmp_path, {"ATKR": [ATKR_DEFM14A, ATKR_25NSE]})
    deal_ts, delist_ts = (datetime.fromisoformat(r["ts"]) for r in (ATKR_DEFM14A, ATKR_25NSE))
    edge = timedelta(seconds=1)

    def forms(as_of):
        return {h.form for h in lg.check_names(["ATKR"], f, as_of).hits}

    assert "25-NSE" in forms(delist_ts + timedelta(days=lg.DELISTING_WINDOW_DAYS))
    assert "25-NSE" not in forms(delist_ts + timedelta(days=lg.DELISTING_WINDOW_DAYS) + edge)
    assert "DEFM14A" in forms(deal_ts + timedelta(days=lg.DEAL_WINDOW_DAYS))
    assert "DEFM14A" not in forms(deal_ts + timedelta(days=lg.DEAL_WINDOW_DAYS) + edge)


def test_a_position_opened_months_into_a_regulatory_review_still_pages(tmp_path, convexity_db):
    _open_real(convexity_db)                                  # opened ~200 days after the merger proxy
    pager = Pager()
    _run(convexity_db, _filings(tmp_path, {"ATKR": [ATKR_DEFM14A]}), _at(2027, 3, 28), pager)
    assert len(pager.calls) == 1 and "DEFM14A" in pager.calls[0][1]


# ── exact membership ─────────────────────────────────────────────────────────────────────────────────────────────
def test_form_matching_is_exact_membership_never_prefix():
    for form in ("25", "25/A", "25-NSE", "25-NSE/A", "15-12G", "15-12B/A", "15-15D", "15F-12G", "15F-12B/A",
                 "15F-15D"):
        assert lg.classify_form(form) == "delisting", form
    for form in ("DEFM14A", "PREM14A/A", "DEFM14C", "PREM14C/A", "SC TO-T", "SC TO-T/A", "SC TO-I", "SC 13E3",
                 "SC 14D9/A"):
        assert lg.classify_form(form) == "deal", form
    for form in ("25-X", "250", "2", "25-NSE/B", "15-12", "15-12G/AA", "15F-12", "15F-12GX", "SC TO-C",
                 "SC 14D9C", "SC 13E4", "DEFA14A", "DEFA14C", "DEFR14C", "8-K", "SC TO-T ", "sc to-t", ""):
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
    assert res.no_cik == 1 and res.errors == 0 and res.unknown == ["ATKR"] and res.mostly_failed()


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


def _parents(tree):
    import ast

    out = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            out[child] = node
    return out


def _is_not_name(test, name):
    import ast

    return isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) and \
        isinstance(test.operand, ast.Name) and test.operand.id == name


def test_orchestrator_wiring_is_structurally_inside_l1_after_entries_in_a_non_raising_try():
    import ast
    from pathlib import Path

    tree = ast.parse(Path(__file__).resolve().parents[1].joinpath("orchestrator.py").read_text())
    run_once = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_once")
    calls = [n for n in ast.walk(run_once) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "run_nightly" and getattr(n.func.value, "id", None) == "listing_guard"]
    assert len(calls) == 1
    call, parents = calls[0], _parents(run_once)
    chain, node = [], call
    while node in parents:
        node, child = parents[node], node
        chain.append((node, child))
    ifs = [(n, c) for n, c in chain if isinstance(n, ast.If)]
    assert any(_is_not_name(n.test, "monitor_only") and c in n.body for n, c in ifs)
    assert any(_is_not_name(n.test, "demo") and c in n.body for n, c in ifs)
    tries = [(n, c) for n, c in chain if isinstance(n, ast.Try) and c in n.body]
    assert tries, "the call must sit in a try body"
    for handler in tries[0][0].handlers:
        assert handler.type is not None and getattr(handler.type, "id", "") == "Exception"
        assert not any(isinstance(x, ast.Raise) for x in ast.walk(handler))
    paper = [n for n in ast.walk(run_once) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "run_paper_cycle"]
    assert paper and all(p.lineno < call.lineno for p in paper)
    notes = [n for h in tries[0][0].handlers for n in ast.walk(h)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "append_run_note"]
    assert notes, "a whole-guard failure must leave a run note"


# ── review fixes: budget, ordering, honest unknowns, copy, note bounds, shares, run_nightly, smoke ──────────────────
class StepClock:
    """Each read 'takes' ``step`` seconds on an injected monotonic clock."""

    def __init__(self, step):
        self.t, self.step = 0.0, step

    def __call__(self):
        return self.t


class SlowFilings:
    def __init__(self, clock):
        self.clock, self.read = clock, []

    def _cik(self, symbol):
        return "1"

    def filings_asof(self, symbol, as_of):
        self.clock.t += self.clock.step
        self.read.append(symbol)
        return []


def test_budget_stops_reading_and_counts_the_rest_as_unknown(caplog, convexity_db):
    clock = StepClock(100.0)
    src = SlowFilings(clock)
    names = [f"N{i}" for i in range(10)]
    res = lg.check_names(names, src, _at(2026, 10, 20), budget_s=250, monotonic=clock)
    assert src.read == ["N0", "N1", "N2"]              # 0, 100, 200 elapsed start ≤ 250; at 300 it stops
    assert res.budget_skipped == 7 and res.errors == 0 and res.checked == 10
    assert res.unknown == names[3:] and res.mostly_failed()
    with caplog.at_level(logging.INFO, logger="listing_guard"):
        line = lg.dispose(convexity_db, res, {}, as_of=_at(2026, 10, 20), run_id=None, notify_send=Pager())
    assert "budget_skipped=7" in line
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_one_budget_skip_alone_still_warns(convexity_db, caplog):
    res = lg.GuardResult(checked=10, budget_skipped=1, unknown=["Z"])
    with caplog.at_level(logging.INFO, logger="listing_guard"):
        lg.dispose(convexity_db, res, {}, as_of=_at(2026, 10, 20), run_id=None, notify_send=Pager())
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_order_names_real_first_then_sentinel_and_universe_then_null_only():
    roles = {"A": {"null"}, "B": {"universe"}, "C": {"real", "null"}, "D": {"sentinel"}, "E": {"universe", "real"}}
    assert lg.order_names(roles) == ["C", "E", "B", "D", "A"]


def test_run_nightly_reads_held_names_first_under_the_budget(tmp_path, convexity_db, monkeypatch):
    _open_real(convexity_db, "ZZZ")
    clock = StepClock(400.0)
    src = SlowFilings(clock)
    monkeypatch.setattr(lg, "_filings_source", lambda config, cache, as_of: src)
    config = {"universe": {"themes": {"a": ["AAA", "BBB"]}}}
    line = lg.run_nightly(convexity_db, config, run_id=None, cache=None, client=None, as_of=_at(2026, 10, 20),
                          notify_send=Pager(), monotonic=clock)
    assert src.read == ["ZZZ"] and "budget_skipped=2" in line


def test_mostly_failed_counts_no_cik_and_venue_failures(tmp_path):
    f = _filings(tmp_path, {"A": [], "B": [], "C": []}, ciks={"C": "1"})
    res = lg.check_names(["A", "B", "C"], f, _at(2026, 10, 20))
    assert res.no_cik == 2 and res.errors == 0 and res.mostly_failed()

    def boom(sym):
        raise RuntimeError("venue down")

    f2 = _filings(tmp_path / "2", {"C": []}, ciks={"C": "1"})
    res2 = lg.check_names(["C"], f2, _at(2026, 10, 20), asset_of=boom)
    assert res2.venue_errors == 1 and res2.errors == 0 and res2.unknown == ["C"]


def test_page_copy_is_neutral_and_class_specific():
    hits = [lg.Hit("X", "deal", "SC TO-I", "acc-1", "2026-10-01T00:00:00+00:00"),
            lg.Hit("X", "delisting", "25", "acc-2", "2026-10-02T00:00:00+00:00"),
            lg.Hit("X", "venue", "status=inactive tradable=False", "venue:inactive:False", "2026-10-03T00:00:00+00:00")]
    body = lg.page_body("X", "#1", hits)
    assert "cash" not in body.lower()
    for label in ("pending deal or tender offer: SC TO-I", "delisting / deregistration: 25", "venue status: status="):
        assert label in body
    assert body.endswith("Nothing was closed; the call is the operator's.")


def test_run_note_shows_latest_hit_per_class_and_caps_symbols(convexity_db):
    hits = [lg.Hit("S00", "deal", "PREM14A", "a1", "2026-03-01T00:00:00+00:00"),
            lg.Hit("S00", "deal", "DEFM14A", "a2", "2026-05-01T00:00:00+00:00")]
    hits += [lg.Hit(f"S{i:02d}", "delisting", "25", f"d{i}", "2026-10-01T00:00:00+00:00") for i in range(1, 13)]
    roles = {h.symbol: {"universe"} for h in hits}
    res = lg.GuardResult(checked=13, hits=hits)
    line = lg.dispose(convexity_db, res, roles, as_of=_at(2026, 10, 20), run_id=None, notify_send=Pager())
    assert "S00(universe) deal:DEFM14A@2026-05-01" in line and "PREM14A" not in line
    assert line.count("(universe)") == 10 and line.endswith("; +3")


def test_shares_horizon_trading_bars_are_converted_to_calendar_days(convexity_db):
    as_of = _at(2026, 10, 20)
    for sym, days in (("IN", 500), ("OUT", 540)):          # 365 bars ≈ 530 calendar days
        state.record_shares_position(convexity_db, run_id=None, basket="b", symbol=sym, direction="bullish",
                                     entry_spot=10.0, entry_at=(as_of - timedelta(days=days)).isoformat())
    roles = lg.names_to_check({}, convexity_db, as_of=as_of)
    assert roles == {"IN": {"null"}}


def test_filings_source_without_ua_makes_every_name_unknown_never_no_events(convexity_db, caplog):
    assert lg._filings_source({}, None, _at(2026, 10, 20)) is None
    run_id = state.record_run(convexity_db, mode="PAPER", equity=None, note="paper cycle")
    config = {"universe": {"themes": {"a": ["AAA", "BBB"]}}}
    with caplog.at_level(logging.INFO, logger="listing_guard"):
        line = lg.run_nightly(convexity_db, config, run_id=run_id, cache=None, client=None,
                              as_of=_at(2026, 10, 20), notify_send=Pager())
    assert "err=2" in line and "unknown=AAA,BBB" in line and "venue=off" in line
    assert any(r.levelno == logging.WARNING and "fail-soft is not fail-silent" in r.getMessage()
               for r in caplog.records)
    assert "listing_guard: checked=2" in convexity_db.execute(
        "SELECT note FROM runs WHERE id=?", (run_id,)).fetchone()["note"]


def test_filings_source_with_ua_builds_the_submissions_path(tmp_path):
    f = lg._filings_source({"edgar": {"user_agent": "dramatic-options test"}, "cache": {"dir": str(tmp_path)}},
                           PointInTimeCache(tmp_path), _at(2026, 10, 20))
    assert isinstance(f, FilingsData) and f.fetch_end == _at(2026, 10, 20) and f.edgar.ua == "dramatic-options test"


def test_run_nightly_uses_the_clients_get_asset_and_pages_a_held_inactive_name(tmp_path, convexity_db, monkeypatch):
    _open_real(convexity_db, "ATKR")
    monkeypatch.setattr(lg, "_filings_source",
                        lambda config, cache, as_of: _filings(tmp_path, {"ATKR": []}))

    class Client:
        def __init__(self):
            self.asked = []

        def get_asset(self, sym):
            self.asked.append(sym)
            return {"status": "inactive", "tradable": False}

    client, pager = Client(), Pager()
    for _ in range(2):
        line = lg.run_nightly(convexity_db, {}, run_id=None, cache=None, client=client,
                              as_of=_at(2026, 10, 20), notify_send=pager)
    assert client.asked == ["ATKR", "ATKR"] and "venue=1" in line and "venue_err=0" in line
    assert len(pager.calls) == 1 and "venue status: status=inactive" in pager.calls[0][1]


def test_smoke_report_lists_hits_and_every_form_seen(tmp_path):
    f = _filings(tmp_path, {"ATKR": [ATKR_DEFM14A, ATKR_8K, ATKR_25NSE, ATKR_15_12G]})
    out = lg.smoke_report("ATKR", f, _at(2026, 10, 20))
    assert "hits: 2" in out and "15-12G" not in out             # 10-29 is after as_of
    for form in ("DEFM14A", "8-K", "25-NSE"):
        assert f"  {form}" in out
