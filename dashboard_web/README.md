# dashboard_web — React observability dashboard (additive, parallel to the Streamlit one)

A read-only, NO-FETCH, fail-soft command center over the live journal + PIT cache. It **never** trades,
writes, calls the broker, or edits config — same safety contract as the Streamlit dashboard (`dashboard.py`),
which stays the source of truth on `:8502` and is untouched by this.

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
  ../venv/bin/uvicorn --app-dir dashboard_web/api server:app --port 8503   # run from repo root
# 2) UI (proxies /api → :8503):
cd ui && npm install && npm run dev    # add --host <tailnet-ip> to view over Tailscale
```
`npm run typecheck` · `npm run build` · `npm test` (vitest, the adapter contract).

## Prod (one process, one port)
```bash
cd ui && npm ci && npm run build       # produces ui/dist
dashboard_web/deploy/run.sh            # FastAPI serves dist + /api on the tailnet IP:8503, keyless, fail-closed
```
Or install `deploy/dramatic-options-web.service` (mirrors the Streamlit unit; on-failure restart). NOTE: this
is **not yet wired into the live `deploy.sh`** — installing/arming it on the box is a deliberate operator step.

## Safety invariants
Read-only DB (`?mode=ro`, a write raises) · NO-FETCH (`MarketData(client=None)`) · keyless
(`DRAMATIC_SKIP_DOTENV=1`; the venv holds no `.env`) · fail-soft (every panel; one failure never blanks the
page) · tailnet-bound only (the run script refuses a wildcard bind). It renders the whole book + cluster map,
so never expose it on a public port.
