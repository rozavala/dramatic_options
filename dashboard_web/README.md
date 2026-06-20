# dashboard_web — React observability dashboard (additive, parallel to the Streamlit one)

A read-only, NO-FETCH, fail-soft command center over the live journal + PIT cache. It **never** trades,
writes, calls the broker, or edits config — same safety contract as the Streamlit dashboard (`dashboard.py`),
which stays the source of truth on `:8601` and is untouched by this. (We hold the 86xx block — `:8601`
Streamlit / `:8602` web — clear of real_options' 85xx dashboards.)

- `api/` — a tiny FastAPI service. `snapshot.build_snapshot()` mirrors `dashboard.load_all()` panel-for-panel
  (streamlit-free) + injects `system_status` + JSON-sanitizes; `server.py` serves `GET /api/snapshot` and,
  in production, the built SPA on the same port.
- `ui/` — Vite + React + TS + Tailwind. `data/` is the typed data layer (`types.ts`, the `fromBackend`
  adapter ported from the design's spec, `useSnapshot`). One responsive app: 252px-rail desktop console or
  bottom-tab mobile (`useIsMobile`, ≤760px).

## Dev (two processes, hot reload)
```bash
# 1) API (from the repo ROOT so themes.json/config.json resolve):
DRAMATIC_SKIP_DOTENV=1 DRAMATIC_DB=~/dramatic_options/data/dramatic_options.db \
  DRAMATIC_CACHE_DIR=~/dramatic_options/data/cache \
  ../venv/bin/uvicorn --app-dir dashboard_web/api server:app --port 8602   # run from repo root
# 2) UI (proxies /api → :8602):
cd ui && npm install && npm run dev    # add --host <tailnet-ip> to view over Tailscale
```
`npm run typecheck` · `npm run build` · `npm test` (vitest, the adapter contract).

## Prod (one process, one port) — managed systemd service
On DEV this is **automatic**: `deploy.sh` builds the SPA (`npm ci && npm run build`) and arms
`dramatic-options-web.service` (`scripts/systemd/`, rendered+installed by `install_units`; ExecStart =
`scripts/dashboard_web_run.sh`). It mirrors the Streamlit unit — tailnet IP **:8602**, keyless, fail-closed,
fail-soft + **outside** the verify/rollback gate (a dashboard hiccup never touches trading). PROD
installs-but-stops it until T4. Manual run:
```bash
cd ui && npm ci && npm run build       # produces ui/dist
scripts/dashboard_web_run.sh           # from the repo root: FastAPI serves dist + /api on the tailnet IP:8602
```

## Config knobs
- `DRAMATIC_DB` / `DRAMATIC_CACHE_DIR` — resolve the live DB + PIT cache (env wins, the worktree-vs-live guard).
- `VITE_POLL_MS` (UI build/env) — auto-refresh interval in ms (default 60000; `0` disables). Polls only while
  the tab is visible; the manual ↻ always bypasses the server cache.
- `DASHBOARD_TOKEN` (server env) — **optional** shared-token gate. **Off by default** (the tailnet ACL +
  localhost/tailnet bind are the primary control, so the live deploy is unchanged). When set, `/api/snapshot`
  requires `Authorization: Bearer <token>`. NOTE: the browser SPA does not send a token, so enabling this
  gates the **raw data API** (for an API-only / programmatic consumer), not the same-origin SPA — front the
  SPA with a tunnel that injects auth if you need both.
- `DASHBOARD_CORS_ORIGINS` (server env) — dev-only CORS allowlist (prod serves the SPA same-origin, no CORS).

The API caches each snapshot ~60s in-process (mirrors the Streamlit `@st.cache_data(ttl=60)`); `?nocache=1`
busts it. Fonts (Roboto / Roboto Mono) are **self-hosted** (bundled via `@fontsource`) — no Google Fonts CDN,
so the UI renders identically on a no-egress host.

## Safety invariants
Read-only DB (`?mode=ro`, a write raises) · NO-FETCH (`MarketData(client=None)`) · keyless
(`DRAMATIC_SKIP_DOTENV=1`; the venv holds no `.env`) · fail-soft (every panel; one failure never blanks the
page) · tailnet-bound only (the run script refuses a wildcard bind). It renders the whole book + cluster map,
so never expose it on a public port.
