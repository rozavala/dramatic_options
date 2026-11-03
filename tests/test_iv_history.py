"""D4 IV history telemetry: the nightly term record, own-history percentiles, term slope, ΔIV."""

from datetime import UTC, date, datetime, timedelta

import gate_dualread
import iv_history
import state
from convexity_data import SyntheticChainProvider
from convexity_gate import Contract
from data.cache import PointInTimeCache

AS_OF = datetime(2026, 6, 10, 20, 45, tzinfo=UTC)
GATE = {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
        "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25}


def _c(sym, exp, kind, k, iv):
    return Contract(symbol=f"{sym}{exp:%y%m%d}{kind}{int(k * 1000):08d}", expiry=exp, kind=kind, strike=k, iv=iv)


def test_term_record_keeps_standard_class_and_window():
    d = AS_OF.date()
    near, far, too_far = d + timedelta(days=45), d + timedelta(days=400), d + timedelta(days=700)
    chain = [_c("FCX", near, "C", 100, 0.40), _c("FCX", near, "P", 100, 0.42),
             _c("FCX", far, "C", 100, 0.50), _c("FCX", far, "C", 125, 0.48), _c("FCX", far, "P", 75, 0.60),
             _c("FCX", too_far, "C", 100, 0.55),
             # an adjusted class nearest the money must be ignored
             Contract(symbol=f"FCX1{far:%y%m%d}C00100500", expiry=far, kind="C", strike=100.5, iv=2.5)]
    rec = iv_history.term_record("FCX", chain, spot=100.0, rv=0.45, as_of_dt=AS_OF)
    assert [e["dte"] for e in rec["expiries"]] == [45, 400]
    e_far = rec["expiries"][1]
    assert e_far["atm_c"] == 0.50 and e_far["otm_c"] == 0.48 and e_far["otm_p"] == 0.60 and e_far["atm_p"] == 0.60
    assert iv_history.term_slope_volpts(rec) == round(((0.50 + 0.60) / 2 - 0.41) * 100, 2)


def test_sweep_writes_the_term_record_without_changing_the_gate_rows(convexity_db, tmp_path):
    provider = SyntheticChainProvider(as_of=AS_OF.date())
    cache = PointInTimeCache(tmp_path / "cache")
    run_id = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    counts = gate_dualread.sweep_universe(
        convexity_db, run_id=run_id, as_of_iso=AS_OF.isoformat(), symbols=["FCX", "NVDA"],
        provider_record=provider, provider_shadow=provider,
        market_closes=lambda s: provider.closes(s, window=300), gate=GATE,
        eligibility=lambda c: (True, None), skip=set(), term_cache=cache)
    assert counts["record_ok"] == 2 and counts["term_ok"] == 2
    recs = cache.read_between(iv_history.TERM_SOURCE, "FCX", None, AS_OF)
    assert len(recs) == 1 and recs[0]["expiries"]
    # A same-day re-run replaces the day's record rather than stacking it.
    gate_dualread.sweep_universe(
        convexity_db, run_id=run_id, as_of_iso=AS_OF.isoformat(), symbols=["FCX"],
        provider_record=provider, provider_shadow=provider,
        market_closes=lambda s: provider.closes(s, window=300), gate=GATE,
        eligibility=lambda c: (True, None), skip=set(), term_cache=cache)
    assert len(cache.read_between(iv_history.TERM_SOURCE, "FCX", None, AS_OF)) == 1


def test_a_broken_sink_never_changes_the_gate_read(convexity_db):
    provider = SyntheticChainProvider(as_of=AS_OF.date())

    def boom(_chain):
        raise RuntimeError("disk full")
    a = gate_dualread.shadow_gate_eval(provider, symbol="FCX", direction="bullish", rv=0.5,
                                       underlying_price=provider.underlying_price("FCX"), gate=GATE,
                                       eligibility=lambda c: (True, None), as_of=AS_OF.date())
    b = gate_dualread.shadow_gate_eval(provider, symbol="FCX", direction="bullish", rv=0.5,
                                       underlying_price=provider.underlying_price("FCX"), gate=GATE,
                                       eligibility=lambda c: (True, None), as_of=AS_OF.date(), chain_sink=boom)
    assert a == b


def test_percentiles_wait_for_enough_sessions(convexity_db):
    rid = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    d0 = date(2026, 6, 10)
    n = iv_history.MIN_PCTILE_SESSIONS
    for i in range(n):
        state.record_gate_dualread(convexity_db, run_id=rid, as_of=f"{d0 + timedelta(days=i)}T20:45:00+00:00",
                                   symbol="FCX", feed="opra", source="sweep", structured=True,
                                   iv_rv=1.0 + i / 1000.0, otm_skew=float(i % 10), cheap=True, wing="w", note=None)
        if i == n - 2:
            early = iv_history.panel(convexity_db)["rows"][0]
    assert early["iv_rv_pct"] is None and early["sessions"] == n - 1
    row = iv_history.panel(convexity_db)["rows"][0]
    assert row["sessions"] == n and row["iv_rv_pct"] == 1.0      # the latest is the highest so far
    assert row["skew_pct"] is not None
    # the indicative arm and unstructured rows never enter the history
    assert set(iv_history.gate_history(convexity_db)) == {"FCX"}


def test_delta_iv_over_21_sessions():
    def rec(c, p):
        return {"expiries": [{"dte": 175, "atm_c": c, "atm_p": p}, {"dte": 400, "atm_c": 0.9, "atm_p": 0.9}]}
    recs = [rec(0.40, 0.50)] + [rec(0.41, 0.50)] * 20 + [rec(0.45, 0.47)]
    assert iv_history.delta_iv_volpts(recs, "atm_c") == 5.0
    assert iv_history.delta_iv_volpts(recs, "atm_p") == -3.0
    assert iv_history.delta_iv_volpts(recs[:21], "atm_c") is None
