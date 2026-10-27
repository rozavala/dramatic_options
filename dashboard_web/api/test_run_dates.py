"""#354: the snapshot carries run_id -> started_at for every run id a panel shows (read-only)."""

from __future__ import annotations

import sys
from pathlib import Path

_API = Path(__file__).resolve().parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

import snapshot  # noqa: E402


def test_collect_run_ids_finds_every_run_reference() -> None:
    snap = {
        "council": {"health": {"run_id": 5}, "recent": [{"run_id": 3}, {"run_id": 4}]},
        "forward_catalysts": {"counters_run_id": 6},
        "dualread_runtime": {"last_run": 7},
        "session": {"run_id": 5, "low_history": [{"run_id": 2, "low": 1}]},
        "account": {"equity_series": [{"day": "10-01", "equity": 1}], "n": True},
        "null": {"run_id": None},
        "flag": {"run_id": True},
    }
    assert snapshot.collect_run_ids(snap) == {2, 3, 4, 5, 6, 7}


def test_collect_run_ids_empty() -> None:
    assert snapshot.collect_run_ids({}) == set()
    assert snapshot.collect_run_ids({"error": "boom"}) == set()
