"""#454 gate pass-reason audit: pass-rate arithmetic, the elevated-RV flag both ways, the binding veto leg, unknown
bars, cohorts as of date, and the point-in-time (lookahead) boundary. Dates derive from fixed constants, never from
the wall clock."""

from __future__ import annotations

import importlib.util
import json
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

import gate_audit
import state
from data.cache import CacheMiss, PointInTimeCache

ROOT = Path(__file__).resolve().parents[1]
SWEEP = date(2026, 11, 4)                              # a Wednesday, EST: the next session (Thu) is one day on
AS_OF = f"{SWEEP.isoformat()}T20:45:00+00:00"
CONFIG = {"convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252},
          "universe": {"themes": {"_comment": "ignored", "copper": ["FCX", "SCCO"], "grid": ["ETN", "PWR"]}}}


def _sessions(n: int, end: date = SWEEP) -> list[date]:
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out[::-1]


def _stamp(d: date) -> datetime:
    """Alpaca's daily-bar stamp as the cache stores it: midnight New York (05:00Z in EST, 04:00Z in EDT)."""
    return datetime(d.year, d.month, d.day, 5 if d >= date(2026, 11, 1) else 4, tzinfo=UTC)


def _series(old_step: float, recent_step: float, *, n: int = 300, recent: int = 63) -> list[tuple[datetime, float]]:
    """Alternating ±step log returns (std ≈ step): ``old_step`` before the last ``recent`` returns, then
    ``recent_step``."""
    px, out = 100.0, []
    for i, d in enumerate(_sessions(n)):
        if i:
            step = recent_step if i >= n - recent else old_step
            px *= math.exp(step if i % 2 else -step)
        out.append((_stamp(d), px))
    return out


CALM_NOW = _series(0.04, 0.01)      # RV252 >> RV63: a big old move still in the 252-day window
HOT_NOW = _series(0.01, 0.04)       # RV63 >> RV252: the move is recent
FLAT = _series(0.02, 0.02)


def _closes(data: dict[str, list[tuple[datetime, float]]], errors: dict[str, Exception] | None = None):
    """A deliberately LEAKY source: returns every bar it holds, future ones included. The audit must filter."""
    def closes_for(sym: str, _d: date):
        if errors and sym in errors:
            raise errors[sym]
        return list(data[sym]) if sym in data else None
    return closes_for


def _row(conn, sym, *, structured=True, iv_rv=None, skew=None, cheap=False, note=None, as_of=AS_OF, source="sweep"):
    rid = state.record_run(conn, mode="TEST", equity=None, note="t")
    state.record_gate_dualread(conn, run_id=rid, as_of=as_of, symbol=sym, feed="opra", source=source,
                               structured=structured, iv_rv=iv_rv, otm_skew=skew, cheap=cheap, note=note)
    state.record_gate_dualread(conn, run_id=rid, as_of=as_of, symbol=sym, feed="indicative", source=source,
                               structured=True, iv_rv=0.1, otm_skew=0.0, cheap=True)  # the shadow arm: ignored


def _cohort(rep, c="universe", i=0):
    return rep["sweeps"][i]["cohorts"][c]


def test_pass_rate_distribution_and_last_read_wins(convexity_db):
    _row(convexity_db, "FCX", iv_rv=2.0, skew=3.0, cheap=False, as_of=f"{SWEEP}T15:00:00+00:00")  # superseded
    _row(convexity_db, "FCX", iv_rv=0.8, skew=2.0, cheap=True)
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=4.0, cheap=True)
    _row(convexity_db, "ETN", iv_rv=1.1, skew=12.0, cheap=False)
    _row(convexity_db, "PWR", structured=False, note="no rv/spot")
    _row(convexity_db, "ZZZ", iv_rv=0.5, skew=1.0, cheap=True, source="inline")      # read only inline
    rep = gate_audit.audit(convexity_db, CONFIG, _closes({}))
    u = _cohort(rep)
    assert (u["n_read"], u["n_structured"], u["n_pass"], u["pass_rate"]) == (4, 3, 2, round(2 / 3, 4))
    assert u["iv_rv"] == {"n": 3, "min": 0.8, "q1": 0.9, "median": 1.0, "q3": 1.05, "max": 1.1}
    assert u["pass_headroom"] == {"iv_rv": round(1.2 - 0.9, 4), "otm_skew": 7.0}
    o = _cohort(rep, "other")
    assert (o["n_read"], o["n_pass"], o["pass_rate"]) == (1, 1, 1.0)
    assert "not in gate_dualread" in rep["market_sample"]


def test_a_later_error_row_does_not_replace_the_days_structured_read(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=2.0, cheap=True)
    _row(convexity_db, "SCCO", structured=False, note="transient: timeout", as_of=f"{SWEEP}T21:30:00+00:00")
    u = _cohort(gate_audit.audit(convexity_db, CONFIG, _closes({})))
    assert (u["n_structured"], u["pass_rate"]) == (2, 1.0)
    assert u["not_structured_notes"] == {}


def test_cohort_is_taken_as_of_the_sweep_date(convexity_db):
    # ATKR left the config universe later but was SWEPT this date → universe that date; ZZZ only inline → other
    _row(convexity_db, "ATKR", structured=False, note="no_eligible_contract")
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)
    _row(convexity_db, "ZZZ", iv_rv=1.0, skew=2.0, cheap=True, source="inline")
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=2.0, cheap=True, source="inline")   # inline AND swept
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=2.0, cheap=True)
    # a date with no sweep rows at all: today's config is the labelled fallback
    prev = f"{SWEEP - timedelta(days=1)}T15:00:00+00:00"
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True, as_of=prev, source="inline")
    _row(convexity_db, "ZZZ", iv_rv=1.0, skew=2.0, cheap=True, as_of=prev, source="inline")
    rep = gate_audit.audit(convexity_db, CONFIG, _closes({}))
    old, new = rep["sweeps"]
    assert new["cohort_basis"] == "sweep_rows"
    assert [n["symbol"] for n in new["cohorts"]["universe"]["names"]] == ["FCX", "SCCO"]
    assert (new["cohorts"]["universe"]["n_read"], new["cohorts"]["universe"]["veto_leg"]) == (3, {"not_structured": 1})
    assert new["cohorts"]["other"]["n_read"] == 1
    assert old["cohort_basis"] == "config_fallback"
    assert (old["cohorts"]["universe"]["n_read"], old["cohorts"]["other"]["n_read"]) == (1, 1)
    text = gate_audit.render(rep)
    assert "cohort as of date" in text and "TODAY's config universe (fallback)" in text


def test_elevated_rv_flag_both_ways(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)     # cheap only because RV252 holds an old move
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=2.0, cheap=True)    # flat vol: a pass for the right reason
    _row(convexity_db, "ETN", iv_rv=1.5, skew=2.0, cheap=False)    # vetoed on RV252, cheap on RV63
    rep = gate_audit.audit(convexity_db, CONFIG, _closes({"FCX": CALM_NOW, "SCCO": FLAT, "ETN": HOT_NOW}))
    u = _cohort(rep)
    by = {n["symbol"]: n["rv"] for n in u["names"]}
    assert by["FCX"]["status"] == "ok" and by["FCX"]["iv_rv63"] > 1.2 and by["FCX"]["elevated_rv_pass"] is True
    assert by["FCX"]["iv_rv_long"] == 1.0 and by["FCX"]["atm_iv"] == by["FCX"]["rv_long"]
    assert by["FCX"]["rv_window"] == 252
    assert by["SCCO"]["elevated_rv_pass"] is False and by["SCCO"]["recent_rv_cheap_veto"] is False
    assert by["ETN"]["iv_rv63"] <= 1.2 and by["ETN"]["recent_rv_cheap_veto"] is True
    assert by["ETN"]["elevated_rv_pass"] is False
    assert (u["rv"]["elevated_rv_pass"], u["rv"]["recent_rv_cheap_veto"], u["rv"]["passes_known"]) == (1, 1, 2)
    assert u["rv"]["elevated_rv21_pass"] == 1


def test_elevated_rv_flag_needs_the_recorded_pass(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.0, skew=15.0, cheap=False)   # iv leg inside, vetoed on skew
    rep = gate_audit.audit(convexity_db, CONFIG, _closes({"FCX": CALM_NOW}))
    u = _cohort(rep)
    assert u["names"][0]["rv"]["iv_rv63"] > 1.2
    assert u["names"][0]["rv"]["elevated_rv_pass"] is False and u["rv"]["elevated_rv_pass"] == 0
    assert "ELEVATED-RV PASS" not in gate_audit.render(rep, names=True)


def test_long_rv_window_comes_from_config(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)
    cfg = {**CONFIG, "convexity_gate": {**CONFIG["convexity_gate"], "rv_window_days": 126}}
    rep = gate_audit.audit(convexity_db, cfg, _closes({"FCX": FLAT[-200:]}))   # too short for 252, enough for 126
    x = _cohort(rep)["names"][0]["rv"]
    assert (x["status"], x["rv_window"]) == ("ok", 126)
    assert "IV/RV126" in gate_audit.render(rep)


def test_binding_leg_classification(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.5, skew=2.0, cheap=False)
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=15.0, cheap=False)
    _row(convexity_db, "ETN", iv_rv=1.5, skew=15.0, cheap=False)
    _row(convexity_db, "PWR", structured=True, iv_rv=None, skew=None, cheap=False)
    _row(convexity_db, "AAA", structured=False, note="entitlement: subscription does not permit", source="inline")
    _row(convexity_db, "BBB", structured=False, note="no_eligible_contract", source="inline")
    _row(convexity_db, "CCC", iv_rv=1.0, skew=1.0, cheap=True, source="inline")
    rep = gate_audit.audit(convexity_db, CONFIG, _closes({}))
    assert _cohort(rep)["veto_leg"] == {"both": 1, "fail_closed_structured": 1, "iv_rv": 1, "skew": 1}
    o = _cohort(rep, "other")
    assert o["veto_leg"] == {"not_structured": 2}
    assert o["not_structured_notes"] == {"entitlement": 1, "no_eligible_contract": 1}


def test_unknown_bars_are_counted_by_kind_never_substituted(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)     # no bars at all
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=2.0, cheap=True)    # 100 closes: RV252 would be a short window
    _row(convexity_db, "ETN", iv_rv=1.0, skew=2.0, cheap=True)     # fine
    _row(convexity_db, "PWR", iv_rv=1.0, skew=2.0, cheap=True)     # cache coverage miss
    _row(convexity_db, "AAA", iv_rv=1.0, skew=2.0, cheap=True)     # any other read error
    src = _closes({"SCCO": FLAT[-100:], "ETN": FLAT},
                  errors={"PWR": CacheMiss("bars/PWR covered through …"), "AAA": ValueError("bad json")})
    rep = gate_audit.audit(convexity_db, CONFIG, src)
    rv = _cohort(rep)["rv"]
    assert rv["unknown"] == 4
    assert rv["status"] == {"ok": 1, "unknown_cache_miss": 1, "unknown_error": 1, "unknown_no_bars": 1,
                            "unknown_short_history": 1}
    assert rv["passes_known"] == 1 and rv["iv_rv63"]["n"] == 1
    assert [n["rv"].get("iv_rv63") for n in _cohort(rep)["names"] if n["symbol"] != "ETN"] == [None] * 4
    assert rv["unknown_caveat"] is True and "right after the Sunday L0" in gate_audit.render(rep)


def test_no_caveat_when_unknowns_are_a_quarter_or_less(convexity_db):
    for s in ("FCX", "SCCO", "ETN", "PWR"):
        _row(convexity_db, s, iv_rv=1.0, skew=2.0, cheap=True)
    rep = gate_audit.audit(convexity_db, CONFIG, _closes({"FCX": FLAT, "SCCO": FLAT, "ETN": FLAT}))
    assert _cohort(rep)["rv"]["unknown_caveat"] is False and "CAVEAT" not in gate_audit.render(rep)


def test_pit_boundary_is_the_new_york_bar_date():
    d = SWEEP
    on_d = (_stamp(d), 1.0)                                          # D's own bar, 05:00Z
    late_d = (datetime(d.year, d.month, d.day, 23, 30, tzinfo=UTC), 2.0)                 # D 18:30 ET
    late_d_utc_next = (datetime(d.year, d.month, d.day, 3, tzinfo=UTC) + timedelta(days=1), 3.0)  # D 22:00 ET
    next_session = (_stamp(d + timedelta(days=1)), 4.0)              # D+1 05:00Z (EST)
    got = gate_audit.closes_on_or_before([next_session, late_d_utc_next, late_d, on_d], d)
    assert got == [1.0, 2.0, 3.0]
    # the EDT stamp: D+1 at 04:00Z is the next session, not D
    edt = date(2026, 10, 14)
    assert gate_audit.closes_on_or_before([(_stamp(edt), 1.0), (_stamp(edt + timedelta(days=1)), 2.0)], edt) == [1.0]


def test_lookahead_probe_the_next_session_bar_changes_nothing(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)
    before = gate_audit.audit(convexity_db, CONFIG, _closes({"FCX": CALM_NOW}))
    leaked = CALM_NOW + [(_stamp(SWEEP + timedelta(days=1)), CALM_NOW[-1][1] * 3.0)]   # Thursday, the very next one
    assert gate_audit.audit(convexity_db, CONFIG, _closes({"FCX": leaked})) == before
    # and the sweep date's own bar IS used: dropping it changes the reading
    assert gate_audit.audit(convexity_db, CONFIG, _closes({"FCX": CALM_NOW[:-1]})) != before


def test_hypothetical_cutoffs_only_tighten_the_gate(convexity_db):
    for i, ivrv in enumerate([0.5, 1.3, 1.5, 2.0]):                  # skew fine; the gate passes only N0
        _row(convexity_db, f"N{i}", iv_rv=ivrv, skew=1.0, cheap=ivrv <= 1.2, source="inline")
    _row(convexity_db, "N4", iv_rv=0.6, skew=20.0, cheap=False, source="inline")   # cheap iv, vetoed on skew
    o = _cohort(gate_audit.audit(convexity_db, CONFIG, _closes({})), "other")
    assert o["n_pass"] == 1
    assert [(h["admitted_by_iv_rv"], h["iv_rv_cut"], h["still_pass"]) for h in o["hypothetical_cutoffs"]] == \
        [(2, 0.6, 1), (3, 1.3, 1), (4, 1.5, 1)]
    assert all(h["still_pass"] <= o["n_pass"] for h in o["hypothetical_cutoffs"])


def test_date_selection_and_render(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True, as_of=f"{SWEEP - timedelta(days=1)}T20:45:00+00:00")
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)
    rep = gate_audit.audit(convexity_db, CONFIG, _closes({"FCX": CALM_NOW}), last=1)
    assert [s["date"] for s in rep["sweeps"]] == [SWEEP.isoformat()]
    rep2 = gate_audit.audit(convexity_db, CONFIG, _closes({}), dates=["2026-01-01"])
    assert rep2["sweeps"] == [] and rep2["missing_dates"] == ["2026-01-01"]
    text = gate_audit.render(rep, names=True)
    assert "HYPOTHETICAL" in text and "still pass" in text and "ELEVATED-RV PASS" in text
    assert "not in gate_dualread" in text
    json.dumps(rep)  # the --json path must serialize


def _probe_module():
    spec = importlib.util.spec_from_file_location("probe_gate_pass_reasons",
                                                  ROOT / "scripts" / "probe_gate_pass_reasons.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_bars(cache_dir, sym, series):
    recs = [{"ts": ts.isoformat(), "open": c, "high": c, "low": c, "close": c, "volume": 1e6} for ts, c in series]
    PointInTimeCache(cache_dir).write("bars", sym, recs, coverage_from=series[0][0],
                                      coverage_through=datetime(2026, 11, 8, tzinfo=UTC))


def test_cli_reads_the_offline_cache_and_never_writes(convexity_db, tmp_path, monkeypatch, capsys):
    cache_dir = tmp_path / "cache"
    _write_bars(cache_dir, "FCX", CALM_NOW)
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=2.0, cheap=True)   # no cache payload → a cache miss, never a fetch
    db_path = convexity_db.execute("PRAGMA database_list").fetchone()[2]
    convexity_db.commit()
    before = (Path(db_path).read_bytes(), sorted(p.name for p in cache_dir.rglob("*")))
    monkeypatch.setenv("DRAMATIC_DB", db_path)
    monkeypatch.setenv("DRAMATIC_CACHE_DIR", str(cache_dir))
    probe = _probe_module()
    monkeypatch.setattr(probe, "load_config", lambda: CONFIG)
    assert probe.main(["--json"]) == 0
    rep = json.loads(capsys.readouterr().out)
    u = rep["sweeps"][0]["cohorts"]["universe"]
    assert u["rv"]["status"] == {"ok": 1, "unknown_cache_miss": 1} and u["rv"]["elevated_rv_pass"] == 1
    assert (Path(db_path).read_bytes(), sorted(p.name for p in cache_dir.rglob("*"))) == before


def test_no_fetch_closes_is_point_in_time(tmp_path):
    cache_dir = tmp_path / "cache"
    _write_bars(cache_dir, "FCX", FLAT)
    closes_for = _probe_module().no_fetch_closes(str(cache_dir))
    got = closes_for("FCX", SWEEP - timedelta(days=1))
    assert got[-1][0].date() == SWEEP - timedelta(days=1) and len(got) == len(FLAT) - 1
    with pytest.raises(CacheMiss):
        closes_for("SCCO", SWEEP)
