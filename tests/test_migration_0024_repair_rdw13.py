"""#534: migration 0024 reverts the 2026-11-18 phantom close of real-book #13 (RDW), and nothing else.

The phantom state is produced by the incident's own writer, ``monitor._close_and_resolve`` (the in-DB close plus the
proposal and sentinel resolutions), on a fixture DB migrated through 0023. "Repaired exactly" means every row equals
its pre-close snapshot, except #13's mark/marked_at (NULL, for the next L2 to re-mark) and the dated rationale note.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

import monitor
import state

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "scripts" / "migrations"
MIGRATION = MIGRATIONS / "0024_repair_rdw13_phantom_close.py"
PHANTOM_AT = "2026-11-18T14:30:00.969652+00:00"
CONTRACT = "RDW270521P00006000"
RATIONALE = {"thesis": "t", "origin": "backfill", "paged": {f"venue_check:orphan:{CONTRACT}": "2026-11-18"}}


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _migrate_through_0023(conn) -> None:
    for p in sorted(MIGRATIONS.glob("0*.py")):
        if int(p.name[:4]) <= 23:
            _load(p).apply(conn)
    conn.commit()


def _seed(conn) -> None:
    """Sentinel #26 → proposal #1342 → position #13, opened and marked as on 11-17; plus neighbours on every table."""
    with conn:
        for sid, sym in ((25, "ASTS"), (26, "RDW")):
            conn.execute("INSERT INTO sentinel_candidates (id, lineage_key, symbol, direction, discovered_at) "
                         "VALUES (?, ?, ?, 'bearish', '2026-06-10T03:46:30+00:00')", (sid, f"{sym}|bearish", sym))
        for pid, sym, contract in ((12, "ASTS", "ASTS270521P00020000"), (13, "RDW", CONTRACT), (14, "RDW", CONTRACT)):
            conn.execute(
                "INSERT INTO convexity_positions (id, opened_at, theme, symbol, direction, structure_kind, "
                "contract_symbol, expiry, strike, dte, moneyness, contracts, entry_premium_per_contract, "
                "total_premium, status, rationale, order_id, entry_spot) VALUES (?, "
                "'2026-11-13T18:30:02.212756+00:00', 'space_smallcap_volatility_exhaustion', ?, 'bearish', 'P', ?, "
                "'2027-05-21', 6.0, 189, -0.2016, 10, 95.0, 950.0, 'open', ?, 'cfd062f1', 7.515)",
                (pid, sym, contract, json.dumps(RATIONALE)))
        for prop, pos, sid, sym in ((1341, 12, 25, "ASTS"), (1342, 13, 26, "RDW")):
            conn.execute("INSERT INTO council_proposals (id, as_of, theme, symbol, direction, conviction, status, "
                         "position_id, sentinel_id) VALUES (?, '2026-11-12T20:49:38+00:00', 'space_smallcap', ?, "
                         "'bearish', 'LOW', 'traded', ?, ?)", (prop, sym, pos, sid))
            conn.execute("UPDATE convexity_positions SET proposal_id = ? WHERE id = ?", (prop, pos))
            conn.execute("UPDATE sentinel_candidates SET proposal_id = ? WHERE id = ?", (prop, sid))
    for pid in (12, 13, 14):
        state.mark_convexity_position(conn, pid, mark=1.07, as_of="2026-11-17T21:00:00+00:00")


def _phantom_close(conn, pid: int = 13, as_of: str = PHANTOM_AT) -> None:
    pos = conn.execute("SELECT * FROM convexity_positions WHERE id = ?", (pid,)).fetchone()
    monitor._close_and_resolve(conn, pos, exit_price=10.1, realized_pnl=(10.1 * 100 - 95.0) * 10,
                               reason="profit_take_10x_unsellable", as_of=as_of, conv_map=None, exit_spot=7.2)


def _dump(conn) -> dict[str, dict[int, dict]]:
    out = {}
    for t in ("convexity_positions", "council_proposals", "sentinel_candidates"):
        out[t] = {r["id"]: dict(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY id")}
    return out


@pytest.fixture
def db(tmp_path):
    conn = state.connect(tmp_path / "t.db")
    _migrate_through_0023(conn)
    _seed(conn)
    try:
        yield conn
    finally:
        conn.close()


def _apply(conn) -> None:
    with conn:                                     # the runner's per-migration transaction
        _load(MIGRATION).apply(conn)


def test_phantom_fixture_matches_the_live_incident(db):
    _phantom_close(db)
    d = _dump(db)
    p, prop, s = d["convexity_positions"][13], d["council_proposals"][1342], d["sentinel_candidates"][26]
    assert (p["status"], p["mark"], p["realized_pnl"], p["exit_reason"], p["closed_at"], p["close_order_id"]) == (
        "closed", 10.1, 9150.0, "profit_take_10x_unsellable", PHANTOM_AT, None)
    assert (prop["outcome"], prop["resolved_at"]) == (1, PHANTOM_AT)
    assert (s["outcome"], s["terminal_event"], s["resolved_at"]) == (1, "traded", PHANTOM_AT)
    assert abs(s["realized_multiple"] - 10.631578947368421) < 1e-9


def test_repairs_exactly_what_the_close_wrote(db):
    before = _dump(db)
    _phantom_close(db)
    _apply(db)
    after = _dump(db)

    pos = after["convexity_positions"][13]
    rat = json.loads(pos.pop("rationale"))
    assert rat.pop("repaired_2026-11-19").startswith("phantom close reverted (#533/#534)")
    assert rat == RATIONALE                                            # the rest of the rationale untouched
    want = dict(before["convexity_positions"][13], mark=None, marked_at=None)
    want.pop("rationale")
    assert pos == want                                                 # status open, close fields cleared
    assert after["council_proposals"] == before["council_proposals"]   # #1342 back to unresolved
    assert after["sentinel_candidates"] == before["sentinel_candidates"]   # #26 back to unresolved
    for pid in (12, 14):                                               # the neighbours were never touched
        assert after["convexity_positions"][pid] == before["convexity_positions"][pid]


def test_second_run_is_a_noop(db, capsys):
    _phantom_close(db)
    _apply(db)
    once = _dump(db)
    capsys.readouterr()
    _apply(db)
    assert _dump(db) == once
    out = capsys.readouterr().out
    assert "position #13 left untouched" in out and "proposal #1342 left untouched" in out
    assert "sentinel #26 left untouched" in out


def test_a_db_without_these_rows_is_a_noop(tmp_path):
    conn = state.connect(tmp_path / "fresh.db")
    _migrate_through_0023(conn)
    _apply(conn)
    assert all(not rows for rows in _dump(conn).values())


@pytest.mark.parametrize("table, rid, column, value", [
    ("convexity_positions", 13, "realized_pnl", 9100.0),
    ("convexity_positions", 13, "close_order_id", "abc"),
    ("convexity_positions", 13, "contract_symbol", "RDW270521P00005000"),
    ("council_proposals", 1342, "resolved_at", "2026-11-19T14:30:00+00:00"),
    ("council_proposals", 1342, "outcome", 0),
    ("sentinel_candidates", 26, "resolved_at", "2026-11-19T14:30:00+00:00"),
    ("sentinel_candidates", 26, "terminal_event", "acquired"),
])
def test_a_row_off_the_phantom_state_is_left_alone_and_the_others_still_repaired(db, table, rid, column, value):
    before = _dump(db)
    _phantom_close(db)
    with db:
        db.execute(f"UPDATE {table} SET {column} = ? WHERE id = ?", (value, rid))
    off = _dump(db)[table][rid]
    _apply(db)
    after = _dump(db)
    assert after[table][rid] == off                                    # that row: untouched
    if table != "convexity_positions":
        assert after["convexity_positions"][13]["status"] == "open"
    if table != "council_proposals":
        assert after["council_proposals"][1342] == before["council_proposals"][1342]
    if table != "sentinel_candidates":
        assert after["sentinel_candidates"][26] == before["sentinel_candidates"][26]


def test_an_open_position_13_is_untouched(db):
    # A host whose #13 is some open position (or #13 already repaired): no change at all.
    before = _dump(db)
    _apply(db)
    assert _dump(db) == before


def test_the_runner_picks_it_up_once(tmp_path, monkeypatch, capsys):
    path = tmp_path / "runner.db"
    conn = state.connect(path)
    _migrate_through_0023(conn)
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
    conn.executemany("INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
                     [(v,) for v in range(1, 24)])
    conn.commit()
    _seed(conn)
    _phantom_close(conn)
    conn.close()

    runner = _load(ROOT / "scripts" / "run_migrations.py")
    monkeypatch.setattr(runner, "load_config", lambda: {"database": {"path": str(path)}})
    monkeypatch.setattr("sys.argv", ["run_migrations.py"])
    assert runner.main() == 0
    out = capsys.readouterr().out
    assert "Applying 0024_repair_rdw13_phantom_close.py" in out and "position #13 RDW270521P00006000 reopened" in out

    conn = state.connect(path)
    assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 24
    row = conn.execute("SELECT status, realized_pnl FROM convexity_positions WHERE id = 13").fetchone()
    assert (row["status"], row["realized_pnl"]) == ("open", None)
    conn.close()

    assert runner.main() == 0                                          # recorded: never applied twice
    assert "Migrations up to date (version 24)" in capsys.readouterr().out
