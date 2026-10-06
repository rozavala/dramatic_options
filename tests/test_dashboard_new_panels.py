"""The two post-reserve dashboard panels (read-only aggregation over migration-0018 +
rationale-JSON provenance) — every net-new number pinned to a HAND-CHECKED value
(the PR-A anti-HARK discipline, PREREG_CONVEXITY_CALIBRATION §6)."""

from __future__ import annotations

import json

import dashboard_data
import state


def _run(conn, rid, started="2026-07-06 19:45:00", model_mix=None):
    conn.execute("INSERT OR IGNORE INTO runs (id, started_at, mode, model_mix) VALUES (?,?,'PAPER',?)",
                 (rid, started, json.dumps(model_mix) if model_mix else None))


def _attempt(conn, rid, book, idx, sym, outcome, pc=None):
    state.record_null_attempt(conn, run_id=rid, book=book, attempt_idx=idx, symbol=sym,
                              direction="bullish", origin="sentinel", outcome=outcome,
                              entry_premium_per_contract=pc, as_of="2026-07-06T19:48:00+00:00")


def test_null_attempts_panel_hand_checked(convexity_db):
    _run(convexity_db, 500)
    _attempt(convexity_db, 500, "shadow", 0, "PAAS", "booked", 315.0)
    _attempt(convexity_db, 500, "shadow", 1, "UROY", "no_structure", None)
    _attempt(convexity_db, 500, "shadow", 2, "NVDA", "not_cheap", 1455.0)
    _attempt(convexity_db, 500, "3A", 0, "PAAS", "booked", 315.0)
    p = dashboard_data.null_attempts_panel(convexity_db)
    assert p["run_id"] == 500
    sh = p["books"]["shadow"]
    # HAND-CHECKED: 3 shadow rows in walk order; counts booked=1, no_structure=1, not_cheap=1.
    assert [r["symbol"] for r in sh["rows"]] == ["PAAS", "UROY", "NVDA"]
    assert sh["counts"] == {"booked": 1, "no_structure": 1, "not_cheap": 1}
    assert sh["rows"][0]["entry_premium_per_contract"] == 315.0
    assert sh["rows"][1]["entry_premium_per_contract"] is None
    assert p["books"]["3A"]["counts"] == {"booked": 1}


def test_null_attempts_panel_empty_is_explicit(convexity_db):
    p = dashboard_data.null_attempts_panel(convexity_db)
    assert p["run_id"] is None and p["books"] == {} and "no attempt rows" in p["note"]


def test_reserve_panel_hand_checked(convexity_db):
    _run(convexity_db, 501, model_mix={"proposer": "x", "union_rank": "cheap_reserve_v1"})
    for sym, sel, conv in (("IRDM", "reserve", "NEUTRAL"), ("FRO", "reserve", "LOW"),
                           ("RKLB", "rank", "NEUTRAL")):
        state.record_council_proposal(
            convexity_db, run_id=501, as_of="2026-07-06T19:47:00+00:00", theme="t", symbol=sym,
            direction="bullish", conviction=conv, structural_vs_fad=None, weakest_point=None,
            rationale={"selection": sel}, strategist_summary=None, cost_usd=0.0, model_mix={},
            status="dropped")
    p = dashboard_data.reserve_panel(convexity_db)
    # HAND-CHECKED: stamp present; 2 reserve (IRDM, FRO), 1 rank (RKLB), 0 unlabeled.
    assert p["run_id"] == 501 and p["stamp"] == "cheap_reserve_v1"
    assert [e["symbol"] for e in p["reserve"]] == ["IRDM", "FRO"]
    assert [e["symbol"] for e in p["rank"]] == ["RKLB"]
    assert p["unlabeled"] == []


def test_reserve_panel_pre_reserve_run_reads_off(convexity_db):
    # A pre-deploy run: no stamp, no selection keys → everything 'unlabeled', stamp None —
    # the panel must read OFF, not invent provenance.
    _run(convexity_db, 502, model_mix={"proposer": "x"})
    state.record_council_proposal(
        convexity_db, run_id=502, as_of="2026-07-01T19:47:00+00:00", theme="t", symbol="PL",
        direction="bullish", conviction="MODERATE", structural_vs_fad=None, weakest_point=None,
        rationale={"order": "for_first"}, strategist_summary=None, cost_usd=0.0, model_mix={},
        status="traded")
    p = dashboard_data.reserve_panel(convexity_db, run_id=502)
    assert p["stamp"] is None and p["reserve"] == [] and p["rank"] == []
    assert [e["symbol"] for e in p["unlabeled"]] == ["PL"]


# ── the forward-catalyst channel panel (frozen prereg §4/§6/§8 observability) ──────────────────

def _note_run(conn, rid, note, model_mix=None):
    conn.execute("INSERT OR IGNORE INTO runs (id, started_at, mode, note, model_mix) "
                 "VALUES (?,?,'PAPER',?,?)",
                 (rid, "2026-07-13 19:45:00", note,
                  json.dumps(model_mix) if model_mix else None))


def test_forward_catalyst_panel_hand_checked(convexity_db, tmp_path):
    _note_run(convexity_db, 600,
              "paper cycle · fwd_catalysts: rendered=1 expired=0 malformed=2 stale_flagged=1",
              model_mix={"forward_catalysts": "forward_catalyst_v1"})
    pin = tmp_path / "fc.json"
    pin.write_text(json.dumps({"items": [
        {"symbol": "KMT", "class": "d", "claim": "c", "source": "s", "event_date": None,
         "as_of": "2026-07-12", "expires": "2026-07-19", "provenance": "operator"}]}))
    csvp = tmp_path / "pairs.csv"
    csvp.write_text(
        "as_of,symbol,eligible,void,flip,cite,reverse_conversion\n"
        "2026-07-10T06:13:52+00:00,KMT,True,False,False,True,False\n"
        "2026-07-12T21:30:12+00:00,KMT,True,False,False,True,False\n"
        "2026-07-13T10:00:00+00:00,ADTN,False,True,False,False,False\n")
    p = dashboard_data.forward_catalyst_panel(
        convexity_db, {"forward_catalysts": {"path": str(pin)}}, pairs_csv=csvp)
    # HAND-CHECKED: stamp + the 1/0/2/1 counters off the note; 1 pin; ledger 3 rows =
    # 2 eligible + 1 void, 0 flips, 2 cites, by_symbol KMT=2/ADTN=1; M target 8 (frozen).
    assert p["stamp"] == "forward_catalyst_v1"
    assert p["counters"] == {"rendered": 1, "expired": 0, "malformed": 2, "stale_flagged": 1}
    assert p["counters_run_id"] == 600
    assert p["pins"] == [{"symbol": "KMT", "class": "d", "event_date": None,
                          "as_of": "2026-07-12", "expires": "2026-07-19"}]
    led = p["ledger"]
    assert led["rows"] == 3 and led["eligible"] == 2 and led["void"] == 1
    assert led["flips"] == 0 and led["cites"] == 2 and led["reverse_conversions"] == 0
    assert led["by_symbol"] == {"KMT": 2, "ADTN": 1}
    assert led["last_as_of"] == "2026-07-13T10:00:00+00:00"
    assert p["m_target"] == 8


def test_forward_catalyst_panel_absent_everything_is_explicit(convexity_db, tmp_path):
    # No note-carrying run, no pin file, no CSV — every absence renders as a flag, never raises.
    p = dashboard_data.forward_catalyst_panel(
        convexity_db, {"forward_catalysts": {"path": str(tmp_path / "nope.json")}},
        pairs_csv=tmp_path / "no.csv")
    assert p["stamp"] is None and p["counters"] is None
    assert p["pins"] == [] and p["pins_file_missing"] is True
    assert p["ledger"] is None and p["ledger_missing"] is True
