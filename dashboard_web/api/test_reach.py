"""/api/reach tests: endpoint shape, newest-file selection, and the fail-soft absent-state.

Guarded with importorskip like test_server.py: the plain CI `test` job (no fastapi/httpx) skips
cleanly; the `test-dashboard` job runs them via `pytest dashboard_web/api`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")  # dashboard-only dep
pytest.importorskip("httpx")    # fastapi.testclient.TestClient transport

_API = Path(__file__).resolve().parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

import server  # noqa: E402 — after importorskip + sys.path
from reach import build_reach, newest_week_doc  # noqa: E402

_CARDS_DOC = """# Survivor cards — 2026-W29

- generated: 2026-07-15T18:00:00+00:00
- digest: records/digests/2026-W29.md
- ordering: alphabetical (no ranking anywhere — charter §3b)

## FCX

- provenance: machine_surfaced
"""


def _records_tree(tmp_path: Path) -> Path:
    records = tmp_path / "records"
    (records / "cards").mkdir(parents=True)
    (records / "digests").mkdir(parents=True)
    (records / "cards" / "2026-W28.md").write_text("# Survivor cards — 2026-W28\n(old)\n")
    (records / "cards" / "2026-W29.md").write_text(_CARDS_DOC)
    (records / "digests" / "2026-W29.md").write_text(
        "# Reach digest — 2026-W29\n\n- generated: 2026-07-15T01:04:39+00:00\n"
    )
    return records


def test_newest_week_doc_picks_latest_week_and_parses_generated(tmp_path) -> None:
    doc = newest_week_doc(_records_tree(tmp_path) / "cards")
    assert doc["available"] is True
    assert doc["filename"] == "2026-W29.md" and doc["week"] == "2026-W29"
    assert doc["content"] == _CARDS_DOC                       # verbatim — never reordered
    assert doc["generated"] == "2026-07-15T18:00:00+00:00"    # doc stamp, not mtime
    assert doc["mtime"]                                       # present, ISO string


def test_newest_week_doc_ignores_non_week_stems(tmp_path) -> None:
    d = tmp_path / "cards"
    d.mkdir()
    (d / "notes-W1.md").write_text("not a weekly doc")
    doc = newest_week_doc(d)
    assert doc == {"available": False,
                   "reason": "no <YYYY>-W<ww>.md documents in cards/ yet"}


def test_build_reach_absent_state_is_fail_soft(tmp_path) -> None:
    payload = build_reach(tmp_path / "records")  # directory doesn't exist at all
    for side in ("cards", "digest"):
        assert payload[side]["available"] is False
        assert "not found" in payload[side]["reason"]


def test_endpoint_shape_and_absent_state(monkeypatch, tmp_path) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setattr(server, "_RECORDS_DIR", _records_tree(tmp_path))
    with TestClient(server.app) as client:
        r = client.get("/api/reach")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert body["cards"]["week"] == "2026-W29" and body["cards"]["available"] is True
    assert body["digest"]["available"] is True
    assert "## FCX" in body["cards"]["content"]

    # absent-state through the endpoint: still 200, never an error (the panel renders it)
    monkeypatch.setattr(server, "_RECORDS_DIR", tmp_path / "nowhere")
    with TestClient(server.app) as client:
        r = client.get("/api/reach")
    assert r.status_code == 200
    assert r.json()["cards"]["available"] is False and r.json()["digest"]["available"] is False


def test_reach_endpoint_respects_token_gate(monkeypatch) -> None:
    """If the optional DASHBOARD_TOKEN gate is armed, /api/reach requires the bearer token."""
    from fastapi.testclient import TestClient

    monkeypatch.setattr(server, "_DASHBOARD_TOKEN", "s3cret")
    with TestClient(server.app) as client:
        assert client.get("/api/reach").status_code == 401
        ok = client.get("/api/reach", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
