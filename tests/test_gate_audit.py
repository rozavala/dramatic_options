"""#454 gate pass-reason audit: pass-rate arithmetic, the elevated-RV flag both ways, the binding veto leg, unknown
bars, and the point-in-time (lookahead) probe. Dates derive from fixed constants, never from the wall clock."""

from __future__ import annotations

import importlib.util
import json
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

import gate_audit
import state
from data.cache import PointInTimeCache

ROOT = Path(__file__).resolve().parents[1]
SWEEP = date(2026, 11, 6)                              # a Friday
AS_OF = f"{SWEEP.isoformat()}T20:45:00+00:00"
CONFIG = {"convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0},
          "universe": {"themes": {"_comment": "ignored", "copper": ["FCX", "SCCO"], "grid": ["ETN", "PWR"]}}}


def _sessions(n: int, end: date = SWEEP) -> list[date]:
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out[::-1]


def _series(old_step: float, recent_step: float, *, n: int = 300, recent: int = 63) -> list[tuple[datetime, float]]:
    """Alternating ±step log returns (std ≈ step): ``old_step`` before the last ``recent`` returns, then
    ``recent_step``. Bars at 05:00 UTC, as Alpaca dates daily bars (midnight New York)."""
    px, out = 100.0, []
    for i, d in enumerate(_sessions(n)):
        if i:
            step = recent_step if i >= n - recent else old_step
            px *= math.exp(step if i % 2 else -step)
        out.append((datetime(d.year, d.month, d.day, 5, tzinfo=UTC), px))
    return out


CALM_NOW = _series(0.04, 0.01)      # RV252 >> RV63: a big old move still in the 252-day window
HOT_NOW = _series(0.01, 0.04)       # RV63 >> RV252: the move is recent
FLAT = _series(0.02, 0.02)


def _closes(data: dict[str, list[tuple[datetime, float]]]):
    """A deliberately LEAKY source: returns every bar it holds, future ones included. The audit must filter."""
    def closes_for(sym: str, _d: date):
        if sym not in data:
            raise LookupError(sym)
        return list(data[sym])
    return closes_for


def _row(conn, sym, *, structured=True, iv_rv=None, skew=None, cheap=False, note=None, as_of=AS_OF):
    rid = state.record_run(conn, mode="TEST", equity=None, note="t")
    state.record_gate_dualread(conn, run_id=rid, as_of=as_of, symbol=sym, feed="opra", source="sweep",
                               structured=structured, iv_rv=iv_rv, otm_skew=skew, cheap=cheap, note=note)
    state.record_gate_dualread(conn, run_id=rid, as_of=as_of, symbol=sym, feed="indicative", source="sweep",
                               structured=True, iv_rv=0.1, otm_skew=0.0, cheap=True)  # the shadow arm: ignored


def _cohort(rep, c="universe", i=0):
    return rep["sweeps"][i]["cohorts"][c]


def test_pass_rate_distribution_and_last_read_wins(convexity_db):
    _row(convexity_db, "FCX", iv_rv=2.0, skew=3.0, cheap=False, as_of=f"{SWEEP}T15:00:00+00:00")  # superseded
    _row(convexity_db, "FCX", iv_rv=0.8, skew=2.0, cheap=True)
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=4.0, cheap=True)
    _row(convexity_db, "ETN", iv_rv=1.1, skew=12.0, cheap=False)
    _row(convexity_db, "PWR", structured=False, note="no rv/spot")
    _row(convexity_db, "ZZZ", iv_rv=0.5, skew=1.0, cheap=True)                      # outside the universe
    rep = gate_audit.audit(convexity_db, CONFIG, _closes({}))
    u = _cohort(rep)
    assert (u["n_read"], u["n_structured"], u["n_pass"], u["pass_rate"]) == (4, 3, 2, round(2 / 3, 4))
    assert u["iv_rv"] == {"n": 3, "min": 0.8, "q1": 0.9, "median": 1.0, "q3": 1.05, "max": 1.1}
    assert u["pass_headroom"] == {"iv_rv": round(1.2 - 0.9, 4), "otm_skew": 7.0}
    o = _cohort(rep, "other")
    assert (o["n_read"], o["n_pass"], o["pass_rate"]) == (1, 1, 1.0)
    assert "not in gate_dualread" in rep["market_sample"]


def test_elevated_rv_flag_both_ways(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)     # cheap only because RV252 holds an old move
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=2.0, cheap=True)    # flat vol: a pass for the right reason
    _row(convexity_db, "ETN", iv_rv=1.5, skew=2.0, cheap=False)    # vetoed on RV252, cheap on RV63
    rep = gate_audit.audit(convexity_db, CONFIG, _closes({"FCX": CALM_NOW, "SCCO": FLAT, "ETN": HOT_NOW}))
    u = _cohort(rep)
    by = {n["symbol"]: n["rv"] for n in u["names"]}
    assert by["FCX"]["status"] == "ok" and by["FCX"]["iv_rv63"] > 1.2 and by["FCX"]["elevated_rv_pass"] is True
    assert by["FCX"]["iv_rv252"] == 1.0 and by["FCX"]["atm_iv"] == by["FCX"]["rv252"]
    assert by["SCCO"]["elevated_rv_pass"] is False and by["SCCO"]["recent_rv_cheap_veto"] is False
    assert by["ETN"]["iv_rv63"] <= 1.2 and by["ETN"]["recent_rv_cheap_veto"] is True
    assert by["ETN"]["elevated_rv_pass"] is False
    assert (u["rv"]["elevated_rv_pass"], u["rv"]["recent_rv_cheap_veto"], u["rv"]["passes_known"]) == (1, 1, 2)
    assert u["rv"]["elevated_rv21_pass"] == 1


def test_binding_leg_classification(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.5, skew=2.0, cheap=False)
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=15.0, cheap=False)
    _row(convexity_db, "ETN", iv_rv=1.5, skew=15.0, cheap=False)
    _row(convexity_db, "PWR", structured=True, iv_rv=None, skew=None, cheap=False)
    _row(convexity_db, "AAA", structured=False, note="entitlement: subscription does not permit")
    _row(convexity_db, "BBB", structured=False, note="no_eligible_contract")
    _row(convexity_db, "CCC", iv_rv=1.0, skew=1.0, cheap=True)
    rep = gate_audit.audit(convexity_db, CONFIG, _closes({}))
    assert _cohort(rep)["veto_leg"] == {"both": 1, "fail_closed_structured": 1, "iv_rv": 1, "skew": 1}
    o = _cohort(rep, "other")
    assert o["veto_leg"] == {"not_structured": 2}
    assert o["not_structured_notes"] == {"entitlement": 1, "no_eligible_contract": 1}


def test_unknown_bars_are_counted_never_substituted(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)     # no bars at all
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=2.0, cheap=True)    # 100 closes: RV252 would be a short window
    _row(convexity_db, "ETN", iv_rv=1.0, skew=2.0, cheap=True)     # fine
    rep = gate_audit.audit(convexity_db, CONFIG, _closes({"SCCO": FLAT[-100:], "ETN": FLAT}))
    u = _cohort(rep)
    assert u["rv"]["unknown"] == 2
    assert u["rv"]["status"] == {"ok": 1, "unknown_no_bars": 1, "unknown_short_history": 1}
    assert u["rv"]["passes_known"] == 1 and u["rv"]["iv_rv63"]["n"] == 1
    assert [n["rv"].get("iv_rv63") for n in u["names"] if n["symbol"] != "ETN"] == [None, None]


def test_lookahead_probe_a_future_bar_changes_nothing(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)
    before = gate_audit.audit(convexity_db, CONFIG, _closes({"FCX": CALM_NOW}))
    leaked = CALM_NOW + [(datetime(2026, 11, 9, 5, tzinfo=UTC), CALM_NOW[-1][1] * 3.0),
                         # the next session's bar dated 04:00Z (EDT-style stamp) is still a FUTURE trading date
                         (datetime(2026, 11, 7, 4, tzinfo=UTC) + timedelta(days=3), 1.0)]
    after = gate_audit.audit(convexity_db, CONFIG, _closes({"FCX": leaked}))
    assert after == before
    # and the sweep date's own bar IS used: dropping it changes the reading
    trimmed = gate_audit.audit(convexity_db, CONFIG, _closes({"FCX": CALM_NOW[:-1]}))
    assert trimmed != before


def test_hypothetical_cutoffs(convexity_db):
    for i, (ivrv, skew) in enumerate([(0.5, 1.0), (0.7, 20.0), (0.9, 1.0), (1.1, 1.0)]):
        _row(convexity_db, f"N{i}", iv_rv=ivrv, skew=skew, cheap=skew <= 10)
    hyp = _cohort(gate_audit.audit(convexity_db, CONFIG, _closes({})), "other")["hypothetical_cutoffs"]
    assert [(h["admitted_by_iv_rv"], h["iv_rv_cut"], h["pass_count"]) for h in hyp] == \
        [(1, 0.5, 1), (2, 0.7, 1), (3, 0.9, 2)]


def test_date_selection_and_render(convexity_db):
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True, as_of=f"{SWEEP - timedelta(days=1)}T20:45:00+00:00")
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)
    rep = gate_audit.audit(convexity_db, CONFIG, _closes({"FCX": CALM_NOW}), last=1)
    assert [s["date"] for s in rep["sweeps"]] == [SWEEP.isoformat()]
    rep2 = gate_audit.audit(convexity_db, CONFIG, _closes({}), dates=["2026-01-01"])
    assert rep2["sweeps"] == [] and rep2["missing_dates"] == ["2026-01-01"]
    text = gate_audit.render(rep, names=True)
    assert "HYPOTHETICAL" in text and "ELEVATED-RV PASS" in text and "not in gate_dualread" in text
    json.dumps(rep)  # the --json path must serialize


def _probe_module():
    spec = importlib.util.spec_from_file_location("probe_gate_pass_reasons",
                                                  ROOT / "scripts" / "probe_gate_pass_reasons.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cli_reads_the_offline_cache_and_never_writes(convexity_db, tmp_path, monkeypatch, capsys):
    cache_dir = tmp_path / "cache"
    recs = [{"ts": ts.isoformat(), "open": c, "high": c, "low": c, "close": c, "volume": 1e6} for ts, c in CALM_NOW]
    PointInTimeCache(cache_dir).write("bars", "FCX", recs, coverage_from=CALM_NOW[0][0],
                                      coverage_through=datetime(2026, 11, 8, tzinfo=UTC))
    _row(convexity_db, "FCX", iv_rv=1.0, skew=2.0, cheap=True)
    _row(convexity_db, "SCCO", iv_rv=1.0, skew=2.0, cheap=True)   # no cache payload → unknown, never a fetch
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
    assert u["rv"]["status"] == {"ok": 1, "unknown_no_bars": 1} and u["rv"]["elevated_rv_pass"] == 1
    assert (Path(db_path).read_bytes(), sorted(p.name for p in cache_dir.rglob("*"))) == before


def test_no_fetch_closes_is_point_in_time(tmp_path):
    cache_dir = tmp_path / "cache"
    recs = [{"ts": ts.isoformat(), "open": c, "high": c, "low": c, "close": c, "volume": 1e6} for ts, c in FLAT]
    PointInTimeCache(cache_dir).write("bars", "FCX", recs, coverage_from=FLAT[0][0],
                                      coverage_through=datetime(2026, 11, 8, tzinfo=UTC))
    closes_for = _probe_module().no_fetch_closes(str(cache_dir))
    got = closes_for("FCX", SWEEP - timedelta(days=1))
    assert got[-1][0].date() == SWEEP - timedelta(days=1) and len(got) == len(FLAT) - 1
    with pytest.raises(Exception):  # noqa: B017 — any miss is the audit's "unknown"; the type is the cache's
        closes_for("SCCO", SWEEP)
