"""#470: the read-only segment register check (scripts/ops/segment_register.py) on synthetic runs rows."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("segreg", ROOT / "scripts/ops/segment_register.py")
segreg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(segreg)

MIX_A = {"proposer": "g/a", "adversary": "x/a", "strategist": "an/a", "prompts": "p1", "quote_filter": "q1"}
MIX_B = {**MIX_A, "quote_filter": "q2"}
MIX_C = {k: v for k, v in MIX_B.items() if k != "prompts"} | {"markers": "m1"}


def _db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE runs (id INTEGER PRIMARY KEY, started_at TEXT, mode TEXT, equity REAL, note TEXT, "
                 "frame_version TEXT, council_health TEXT, model_mix TEXT, data_feed TEXT, discovery_funnel TEXT)")
    conn.execute("CREATE TABLE convexity_positions (id INTEGER PRIMARY KEY, run_id INTEGER, status TEXT, "
                 "rationale TEXT)")
    rows = [
        # id, started_at, mode, frame, model_mix, data_feed, funnel
        (1, "2026-11-02 14:00:00", "PAPER", "frame-a", None, "df1", None),        # L2: frame + feed first seen
        (2, "2026-11-02 20:45:00", "PAPER", "frame-a", json.dumps(MIX_A), "df1", None),   # council L1
        (3, "2026-11-03 13:00:00", "DISCOVERY", "frame-a", None, "df1", "fresh_v2"),       # L0
        (4, "2026-11-03 14:00:00", "PAPER", "frame-b", None, "df1", None),        # frame moves on an L2
        (5, "2026-11-03 15:00:00", "PAPER", "frame-b", json.dumps({"clock_basis": "cb1"}), "df1", None),  # not council
        (6, "2026-11-03 20:45:00", "PAPER", "frame-b", json.dumps(MIX_A), "df1", None),   # first L1 under frame-b
        (7, "2026-11-04 15:00:00", "PAPER", "frame-b", None, "df1", None),        # carry fill run
        (8, "2026-11-04 20:45:00", "PAPER", "frame-b", json.dumps(MIX_A), "df1", None),
        (9, "2026-11-05 20:45:00", "PAPER", "frame-b", json.dumps(MIX_B), "df1", None),   # quote_filter move
        (10, "2026-11-06 20:45:00", "PAPER", "frame-b", json.dumps(MIX_C), "df1", None),  # prompts gone, markers in
        (11, "2026-11-07 20:45:00", "PAPER", "frame-b", "not json", "df1", None),          # unparseable: ignored
    ]
    conn.executemany("INSERT INTO runs (id, started_at, mode, frame_version, model_mix, data_feed, discovery_funnel) "
                     "VALUES (?,?,?,?,?,?,?)", rows)
    conn.executemany("INSERT INTO convexity_positions (id, run_id, status, rationale) VALUES (?,?,?,?)", [
        (1, 6, "cancelled", "{}"),                                   # cancelled: never counts
        (2, 7, "open", '{"origin": "backfill"}'),                     # carry fill → the L1 at or before run 7 (run 6)
        (3, 9, "open", "{}"),
    ])
    conn.commit()
    conn.close()


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "runs.db"
    _db(p)
    return p


def _runs(db):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return segreg.load_runs(conn), segreg.load_entries(conn)
    finally:
        conn.close()


def test_boundaries_see_every_stamp_and_only_council_mixes(db):
    runs, _ = _runs(db)
    got = [(b["run_id"], b["key"], b["old"], b["new"]) for b in segreg.boundaries(runs)]
    assert (1, "frame_version", None, "frame-a") in got and (1, "data_feed", None, "df1") in got
    assert (3, "discovery_funnel", None, "fresh_v2") in got
    assert (4, "frame_version", "frame-a", "frame-b") in got          # a frame move is dated at the run that carries it
    assert (2, "prompts", None, "p1") in got                           # first council stamp = an introduction
    assert (9, "quote_filter", "q1", "q2") in got
    assert (10, "prompts", "p1", None) in got and (10, "markers", None, "m1") in got   # removals and additions
    assert not any(b[0] in (5, 11) for b in got)                       # clock_basis-only and bad JSON are not L1s
    assert not any(b[0] in (6, 8) for b in got)                        # unchanged L1s move nothing


def test_segments_cut_on_any_stamp_and_place_carry_fills(db):
    runs, entries = _runs(db)
    segs = segreg.segments(runs, entries)
    assert [(s["first_run"], s["last_run"], s["sessions"]) for s in segs] == [(2, 2, 1), (6, 8, 2), (9, 9, 1),
                                                                               (10, 10, 1)]
    assert segs[1]["changed"] == ["frame_version"]
    assert segs[3]["changed"] == ["markers", "prompts"]
    assert (segs[1]["entries"], segs[1]["backfill"]) == (1, 1)         # the run-7 carry fill lands in run 6's segment
    assert (segs[2]["entries"], segs[0]["entries"]) == (1, 0)          # cancelled never counts


def test_register_check_needs_run_id_and_stamp_on_one_line(db):
    runs, _ = _runs(db)
    bounds = segreg.boundaries(runs)
    rows = "\n".join(f"| run #{b['run_id']} | `{b['key']}` |" for b in bounds)
    assert segreg.missing_from_register(bounds, rows) == []
    partial = rows.replace("| run #9 | `quote_filter` |", "| run #9 | quote filter, no backticks |")
    assert [(b["run_id"], b["key"]) for b in segreg.missing_from_register(bounds, partial)] == [(9, "quote_filter")]
    assert segreg.missing_from_register(bounds, rows.replace("run #10 ", "run #100 "))  # #10 ≠ #100


def test_main_exit_codes(db, tmp_path, capsys):
    runs, _ = _runs(db)
    reg = tmp_path / "register.md"
    reg.write_text("\n".join(f"| run #{b['run_id']} | `{b['key']}` |" for b in segreg.boundaries(runs)))
    assert segreg.main(["--db", str(db), "--register", str(reg), "--check"]) == 0
    reg.write_text("")
    assert segreg.main(["--db", str(db), "--register", str(reg), "--check"]) == 1
    assert "DRIFT" in capsys.readouterr().out
    assert segreg.main(["--db", str(tmp_path / "absent.db"), "--check"]) == 2


def test_the_db_is_opened_read_only(db, tmp_path, monkeypatch):
    calls = []
    real = sqlite3.connect
    monkeypatch.setattr(segreg.sqlite3, "connect", lambda *a, **k: calls.append((a, k)) or real(*a, **k))
    assert segreg.main(["--db", str(db)]) == 0
    assert calls and all("mode=ro" in str(a[0]) and k.get("uri") for a, k in calls)


def test_the_sunday_review_runs_the_check():
    text = (ROOT / "scripts/ops/prompts/sunday_review.md").read_text()
    assert "scripts/ops/segment_register.py" in text and "--check" in text


def test_the_committed_register_is_well_formed():
    # Every row the register cites is in the `run #<id>` + backticked-stamp form the check reads.
    text = (ROOT / "records/segment_register.md").read_text()
    assert "run #1938" in text and "`frame_version`" in text and "`quote_filter`" in text
