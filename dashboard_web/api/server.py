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
    uvicorn server:app --host 127.0.0.1 --port 8602
"""

from __future__ import annotations

import hmac
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("DRAMATIC_SKIP_DOTENV", "1")  # keyless — must precede any config_loader import

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import Depends, FastAPI, Header, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from reach import build_reach  # noqa: E402
from snapshot import build_snapshot  # noqa: E402

import dashboard_data as dd  # noqa: E402
from config_loader import load_config  # noqa: E402

app = FastAPI(title="Dramatic Options — observability API", docs_url=None, redoc_url=None)

# I1: an OPTIONAL shared-token gate. OFF by default (localhost/tailnet bind is the primary control), so the
# live deploy is unchanged. If DASHBOARD_TOKEN is set, /api/snapshot requires `Authorization: Bearer <token>`
# — intended for an API-only / programmatic deployment (the browser SPA does not send a token, so enabling
# this gates the raw data API, not the same-origin SPA). See dashboard_web/README.md.
_DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN", "").strip()


def _require_token(authorization: str | None = Header(default=None)) -> None:
    if not _DASHBOARD_TOKEN:
        return
    expected = f"Bearer {_DASHBOARD_TOKEN}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")

# CORS: the Vite dev server origin (UI dev only). In production the built UI is served same-origin, so this
# allowlist is dev-only and GET-only. Override via DASHBOARD_CORS_ORIGINS (comma-separated).
_DEV_ORIGINS = os.environ.get(
    "DASHBOARD_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
app.add_middleware(
    CORSMiddleware, allow_origins=[o.strip() for o in _DEV_ORIGINS if o.strip()],
    allow_methods=["GET", "POST"], allow_headers=["*"],  # POST = the pure /api/curation/draft (no write)
)


# A tiny in-process TTL cache (D1) — mirrors the Streamlit shell's @st.cache_data(ttl=60). Every panel
# rebuild is read-only but heavy (bootstrap CIs, cluster diagnostics, basket quality, curation), so without
# this each poll / extra tab / refresh recomputes everything. Keyed by the resolved (db, cache) paths; the
# UI's manual Refresh bypasses with ?nocache=1 (mirrors Streamlit's _nonce). Small dict — at most a couple keys.
_CACHE_TTL_S = 60.0
_snapshot_cache: dict[tuple[str, str], tuple[float, dict]] = {}


@app.get("/api/snapshot", dependencies=[Depends(_require_token)])
def snapshot(nocache: int = 0) -> dict:
    """The whole read-only snapshot, one fetch. Paths resolve via DRAMATIC_DB / DRAMATIC_CACHE_DIR (env
    wins, matching the dashboard's worktree-vs-live footgun guard). Cached ~60s; ?nocache=1 busts it."""
    paths = dd.resolve_paths(load_config())
    key = (str(paths["db_path"]), str(paths["cache_dir"]))
    now = time.monotonic()
    if not nocache:
        hit = _snapshot_cache.get(key)
        if hit is not None and now - hit[0] < _CACHE_TTL_S:
            return hit[1]
    snap = build_snapshot(paths["db_path"], paths["cache_dir"], paths["db_exists"])
    _snapshot_cache[key] = (now, snap)
    return snap


@app.get("/api/health")
def health() -> dict:
    """Liveness only — never touches the DB or the broker."""
    return {"ok": True}


# Repo-relative reach documents (records/cards + records/digests). Module-level so tests can
# point it at a tmp tree; never resolved from user input.
_RECORDS_DIR = _REPO_ROOT / "records"


@app.get("/api/reach", dependencies=[Depends(_require_token)])
def reach() -> dict:
    """RENDER-ONLY: the newest weekly survivor-cards document + the newest weekly digest
    (raw markdown, verbatim — no ranking/reordering). Fail-soft: an absent document is
    ``{available: false, reason}``, never a 500 — the panel renders an explicit absent-state.
    No DB, no fetch, no keys, no write path (picks happen in the operator's session)."""
    return build_reach(_RECORDS_DIR)


class CurationDraftRequest(BaseModel):
    kind: str
    tickers: str | None = None
    name: str | None = None
    cluster: str | None = None
    thesis: str | None = None
    falsifier: str | None = None
    source: str | None = None


@app.post("/api/curation/draft", dependencies=[Depends(_require_token)])
def curation_draft(req: CurationDraftRequest) -> dict:
    """PURE drafting: input → text (a box feasibility-screen command, or a universe_register theme entry).
    Reuses the SAME tested dashboard_data builders (single source of truth). NO DB, NO fetch, NO write, NO
    keys — drafting is not writing, so the read-only / never-writes safety contract holds: the operator
    runs the screen on the box, and a new theme lands via a PR + the §11 admission rule + the gate."""
    if req.kind == "screen":
        return {"kind": "screen", **dd.build_screen_command(req.tickers or "")}
    if req.kind == "theme":
        return {"kind": "theme", **dd.build_theme_entry(
            name=req.name or "", cluster=req.cluster or "", thesis=req.thesis or "",
            falsifier=req.falsifier or "", source=req.source or "",
            known_clusters=dd.cluster_names(load_config()))}
    raise HTTPException(status_code=400, detail="kind must be 'screen' or 'theme'")


# Production: serve the built SPA same-origin so the UI and /api share ONE port (no Vite/CORS in prod).
# Mounted LAST so the /api/* routes above win; only mounted if a build exists (dev has no dist → uses the
# Vite proxy instead). StaticFiles is read-only; html=True serves index.html at "/".
_DIST = _REPO_ROOT / "dashboard_web" / "ui" / "dist"
if _DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="ui")
