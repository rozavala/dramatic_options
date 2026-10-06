"""Installable-app pieces for the web dashboard: manifest, icons, service worker.

Display only, and the same shape as alpha_options' console (so the operator's three installed apps look and
behave alike). The dashboard runs on two hosts — ``all-options-dev`` (paper) and ``all-options-prod``
(real-money, inert until T4) — so every piece is keyed by ``DRAMATIC_ENV`` (``PROD`` | ``DEV``; anything else
is DEV). The two installs carry distinct manifest ids and names, so they never collide on one device, and the
icon's band says which one is open (PROD red, DEV grey). No keys, no data, no fetch: pure presentation.
"""

from __future__ import annotations

import os
import struct
import zlib
from functools import lru_cache

ICON_SIZES = (192, 512)

_ENVS = {
    "prod": {"name": "Dramatic Options PROD", "short": "DO PROD", "color": (0xB4, 0x2B, 0x2B),
             "theme": "#b42b2b"},
    "dev": {"name": "Dramatic Options DEV", "short": "DO DEV", "color": (0x6B, 0x6A, 0x64),
            "theme": "#6b6a64"},
}

# 5x7 glyphs: the icon needs two letters, not a font.
_GLYPHS = {
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
}
_INK = (0x1C, 0x1B, 0x18)
_WHITE = (0xFF, 0xFF, 0xFF)


def dramatic_env() -> str:
    """``prod`` or ``dev`` (the default, and the answer for anything unknown — never PROD by accident)."""
    return "prod" if os.getenv("DRAMATIC_ENV", "").strip().lower() == "prod" else "dev"


def manifest(env: str | None = None) -> dict:
    env = env or dramatic_env()
    info = _ENVS[env]
    return {
        # Distinct per environment so a PROD and a DEV install are two apps.
        "id": f"/?app=dramatic-options-{env}",
        "name": info["name"],
        "short_name": info["short"],
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "theme_color": info["theme"],
        "background_color": "#1c1b18",
        "icons": [
            {"src": f"/icons/icon-{size}.png", "sizes": f"{size}x{size}", "type": "image/png",
             "purpose": "any maskable"}
            for size in ICON_SIZES
        ],
    }


@lru_cache(maxsize=8)
def icon_png(size: int, env: str) -> bytes:
    """A full-bleed maskable icon: ink ground, the environment's colour band across the bottom, white "DO"
    inside the central safe zone."""
    band_color = _ENVS[env]["color"]
    band_top = int(size * 0.72)
    cell = max(1, int(size * 0.5 / 11))  # "DO" = 5 + 1 + 5 columns, half the width
    text_w, text_h = 11 * cell, 7 * cell
    x0, y0 = (size - text_w) // 2, int(size * 0.42) - text_h // 2
    lit: set[tuple[int, int]] = set()
    for i, ch in enumerate("DO"):
        for r, row in enumerate(_GLYPHS[ch]):
            for c, on in enumerate(row):
                if on == "#":
                    lit.add((r, c + 6 * i))
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter: none
        base = band_color if y >= band_top else _INK
        gy = (y - y0) // cell if y0 <= y < y0 + text_h else None
        for x in range(size):
            gx = (x - x0) // cell if x0 <= x < x0 + text_w else None
            raw.extend(_WHITE if gy is not None and gx is not None and (gy, gx) in lit else base)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


# Network-first for the app shell (an install still opens if the box blips); /api is never intercepted or
# cached, so live data stays live and a stale snapshot is never shown as current.
SERVICE_WORKER_JS = """\
const CACHE = "do-shell-v1";
const isApi = (url) => url.pathname === "/api" || url.pathname.startsWith("/api/");
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || isApi(url)) {
    return;  // the browser handles it: never cached, never served stale
  }
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
"""
