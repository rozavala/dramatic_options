"""Server tests: the /api routes win over the SPA catch-all (I2) and the snapshot TTL cache (D1).

Guarded with importorskip so the plain CI `test` job (no fastapi/httpx) skips cleanly; the `test-dashboard`
job installs the dashboard deps and runs them.
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


def test_api_routes_declared_before_spa_mount() -> None:
    """I2: /api/* must be registered BEFORE the SPA catch-all Mount, else the static mount shadows the API.
    (In CI there is no built dist/, so the Mount may be absent — then there is nothing to shadow.)"""
    from starlette.routing import Mount

    routes = server.app.routes
    api_idx = [i for i, r in enumerate(routes) if str(getattr(r, "path", "")).startswith("/api")]
    mount_idx = [i for i, r in enumerate(routes) if isinstance(r, Mount) and getattr(r, "path", "") == ""]
    assert api_idx, "no /api routes registered"
    if mount_idx:
        assert max(api_idx) < min(mount_idx), "the SPA '/' mount must come AFTER the /api routes"


def test_health_is_json_not_static() -> None:
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        r = client.get("/api/health")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() == {"ok": True}


def test_snapshot_route_serves_json() -> None:
    """/api/snapshot is handled by the API (returns a JSON dict), not swallowed by a static file."""
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        r = client.get("/api/snapshot")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert isinstance(r.json(), dict)


def test_snapshot_ttl_cache_and_nocache(monkeypatch) -> None:
    """D1: a 2nd call within the TTL is served from cache (no rebuild); ?nocache=1 forces a rebuild."""
    from fastapi.testclient import TestClient

    calls = {"n": 0}

    def fake_build(db_path, cache_dir, db_exists):  # noqa: ANN001 — test stub
        calls["n"] += 1
        return {"ok": calls["n"]}

    monkeypatch.setattr(server, "build_snapshot", fake_build)
    server._snapshot_cache.clear()

    with TestClient(server.app) as client:
        first = client.get("/api/snapshot").json()
        second = client.get("/api/snapshot").json()
        assert first == second
        assert calls["n"] == 1  # the 2nd call hit the cache

        client.get("/api/snapshot?nocache=1")
        assert calls["n"] == 2  # nocache forced a rebuild

    server._snapshot_cache.clear()
