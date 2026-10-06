"""The web dashboard as an installable app: PROD and DEV never collide (2026-10-06; alpha_options parity)."""

from __future__ import annotations

import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pwa  # noqa: E402
import server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(("value", "env", "name", "short"), [
    ("PROD", "prod", "Dramatic Options PROD", "DO PROD"),
    ("prod", "prod", "Dramatic Options PROD", "DO PROD"),
    ("DEV", "dev", "Dramatic Options DEV", "DO DEV"),
    (None, "dev", "Dramatic Options DEV", "DO DEV"),          # unset defaults to dev
    ("staging", "dev", "Dramatic Options DEV", "DO DEV"),     # unknown is never prod
])
def test_manifest_varies_by_env(monkeypatch, value, env, name, short):
    if value is None:
        monkeypatch.delenv("DRAMATIC_ENV", raising=False)
    else:
        monkeypatch.setenv("DRAMATIC_ENV", value)
    r = TestClient(server.app).get("/manifest.webmanifest")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/manifest+json")
    m = r.json()
    assert (m["id"], m["name"], m["short_name"]) == (f"/?app=dramatic-options-{env}", name, short)
    assert (m["start_url"], m["scope"], m["display"]) == ("/", "/", "standalone")
    assert m["theme_color"] == ("#b42b2b" if env == "prod" else "#6b6a64")
    assert [i["sizes"] for i in m["icons"]] == ["192x192", "512x512"]
    assert all("maskable" in i["purpose"] for i in m["icons"])


def test_prod_and_dev_never_share_an_identity_and_never_collide_with_alpha_options():
    prod, dev = pwa.manifest("prod"), pwa.manifest("dev")
    assert prod["id"] != dev["id"] and prod["name"] != dev["name"]
    assert "alpha-options" not in prod["id"] + dev["id"]


@pytest.mark.parametrize("size", pwa.ICON_SIZES)
def test_icons_are_valid_pngs_of_the_declared_size(size):
    r = TestClient(server.app).get(f"/icons/icon-{size}.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    png = r.content
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = struct.unpack(">II", png[16:24])
    assert (w, h) == (size, size)
    idat_len = struct.unpack(">I", png[33:37])[0]
    raw = zlib.decompress(png[41:41 + idat_len])
    assert len(raw) == size * (1 + 3 * size)


def test_prod_and_dev_icons_differ():
    assert pwa.icon_png(192, "prod") != pwa.icon_png(192, "dev")


def test_unknown_icon_size_is_404():
    assert TestClient(server.app).get("/icons/icon-64.png").status_code == 404


def test_service_worker_never_touches_the_api():
    r = TestClient(server.app).get("/sw.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    assert r.headers["service-worker-allowed"] == "/" and r.headers["cache-control"] == "no-cache"
    js = r.text
    assert 'url.pathname.startsWith("/api/")' in js and "isApi(url)" in js   # /api is passed through


def test_pwa_routes_win_over_the_spa_mount():
    paths = [getattr(r, "path", None) for r in server.app.routes]
    mount_at = next((i for i, r in enumerate(server.app.routes) if type(r).__name__ == "Mount"), len(paths))
    for p in ("/manifest.webmanifest", "/icons/icon-{size}.png", "/sw.js"):
        assert p in paths and paths.index(p) < mount_at


def test_index_html_links_the_manifest_and_main_registers_the_worker():
    html = (REPO / "dashboard_web/ui/index.html").read_text()
    assert '<link rel="manifest" href="/manifest.webmanifest" />' in html
    assert 'rel="apple-touch-icon" href="/icons/icon-192.png"' in html
    main = (REPO / "dashboard_web/ui/src/main.tsx").read_text()
    assert 'navigator.serviceWorker.register("/sw.js"' in main


def test_web_unit_carries_the_env_identity_and_deploy_renders_it():
    unit = (REPO / "scripts/systemd/dramatic-options-web.service").read_text()
    assert "Environment=DRAMATIC_ENV=__ENV_NAME__" in unit
    assert not any(ln.startswith("EnvironmentFile") for ln in unit.splitlines())   # still keyless
    deploy = (REPO / "deploy.sh").read_text()
    assert 's|__ENV_NAME__|${ENV_NAME}|g' in deploy
    json.dumps(pwa.manifest())                              # serializable


def test_web_dashboard_binds_localhost_only_behind_the_tailnet_https_proxy():
    run = (REPO / "scripts/dashboard_web_run.sh").read_text()
    assert "--host 127.0.0.1 --port 8602" in run
    assert "0.0.0.0" not in run and "tailscale ip" not in run   # never a wildcard; the proxy owns the tailnet port


def test_web_dashboard_is_armed_on_every_env():
    deploy = (REPO / "deploy.sh").read_text()
    body = deploy[deploy.index("apply_web_dashboard() {"):]
    body = body[:body.index("\n}\n")]
    assert 'sudo systemctl enable --now "$WEB_SERVICE"' in body
    assert "disable --now \"$WEB_SERVICE\"" not in body.split("npm or dashboard_web/ui missing")[-1]
