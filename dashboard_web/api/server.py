"""Read-only FastAPI endpoint serving the observability snapshot as JSON.

ONE data route — ``GET /api/snapshot`` — returns ``dashboard.load_all()``'s panels + ``system_status``
(see ``snapshot.build_snapshot``). The React UI fetches this; Refresh re-requests it.

SAFETY: keyless (``DRAMATIC_SKIP_DOTENV=1`` is set BEFORE any config import — ``config_loader.load_config``
calls ``load_dotenv`` itself, so the env var is the opt-out), and read-only + NO-FETCH + fail-soft are
inherited from ``dashboard_data`` via ``build_snapshot``. It never trades, never writes, never calls the
broker, never edits config/clusters/themes. It renders the whole book + the cluster map, so bind to
localhost or a trusted tunnel — never a public port.

    pip install -r requirements.txt
    DRAMATIC_DB=~/dramatic_options/data/dramatic_options.db \
    DRAMATIC_CACHE_DIR=~/dramatic_options/data/cache \
    uvicorn server:app --host 127.0.0.1 --port 8503
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DRAMATIC_SKIP_DOTENV", "1")  # keyless — must precede any config_loader import

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from snapshot import build_snapshot  # noqa: E402

import dashboard_data as dd  # noqa: E402
from config_loader import load_config  # noqa: E402

app = FastAPI(title="Dramatic Options — observability API", docs_url=None, redoc_url=None)

# CORS: the Vite dev server origin (UI dev only). In production the built UI is served same-origin, so this
# allowlist is dev-only and GET-only. Override via DASHBOARD_CORS_ORIGINS (comma-separated).
_DEV_ORIGINS = os.environ.get(
    "DASHBOARD_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
app.add_middleware(
    CORSMiddleware, allow_origins=[o.strip() for o in _DEV_ORIGINS if o.strip()],
    allow_methods=["GET"], allow_headers=["*"],
)


@app.get("/api/snapshot")
def snapshot() -> dict:
    """The whole read-only snapshot, one fetch. Paths resolve via DRAMATIC_DB / DRAMATIC_CACHE_DIR (env
    wins, matching the dashboard's worktree-vs-live footgun guard)."""
    paths = dd.resolve_paths(load_config())
    return build_snapshot(paths["db_path"], paths["cache_dir"], paths["db_exists"])


@app.get("/api/health")
def health() -> dict:
    """Liveness only — never touches the DB or the broker."""
    return {"ok": True}


# Production: serve the built SPA same-origin so the UI and /api share ONE port (no Vite/CORS in prod).
# Mounted LAST so the /api/* routes above win; only mounted if a build exists (dev has no dist → uses the
# Vite proxy instead). StaticFiles is read-only; html=True serves index.html at "/".
_DIST = _REPO_ROOT / "dashboard_web" / "ui" / "dist"
if _DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="ui")
