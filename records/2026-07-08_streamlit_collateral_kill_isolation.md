# 2026-07-08 — sibling-system collateral kill: real_options' deploy pkill took down our dashboard

**What happened (journal-verified):** at 20:56:01–20:56:06 UTC the operator ran a real_options
deploy (`sudo systemctl stop trading-bot`, `stop coffee-dashboard` from `~/real_options`); at
20:56:08 our `dramatic-options-dashboard.service` Streamlit got a SIGTERM ("Stopping…"), exited
**0** (graceful shutdown), and — under `Restart=on-failure` — stayed **dead**. Found ~1 minute
later by a routine post-restart surface check (curl 8601 → 000), restarted by hand.

**Root cause, both halves:**
1. `real_options/deploy.sh` (lines 91/207) runs `pkill -f "streamlit run dashboard.py"` — an
   **unqualified pattern** that matches ANY repo's relative-path Streamlit invocation. Ours
   (`exec venv/bin/streamlit run dashboard.py`) matched.
2. Streamlit's graceful SIGTERM shutdown is an **exit-0**, so `Restart=on-failure` treats an
   external kill as a clean stop and never restarts — the surface silently stays down with the
   unit still `enabled`.

Blast radius: observability only. The trading path (oneshot L1/L2/L0 timers) has no long-running
process to kill; the web dashboard (uvicorn :8602, pattern-distinct) survived; fail-soft held
(no page — by design, the dashboard must not page).

**Fixes (this PR, our side only — defensive regardless of sibling behavior):**
1. `scripts/dashboard_run.sh`: `streamlit run "$PWD/dashboard.py"` — the cmdline no longer
   contains the substring `streamlit run dashboard.py`, so the sibling's pattern (and any future
   unqualified variant of it) cannot match this process.
2. Unit template: `Restart=on-failure` → `Restart=always` — self-heals ANY external kill class
   (RestartSec=10, StartLimit 5/900s unchanged); an operator `systemctl stop` is still respected
   (systemd never auto-restarts an explicitly stopped unit).
3. Both invariants pinned in `tests/test_systemd_units.py`.

**Audit of the reverse direction (clean):** our `deploy.sh` pkills were already
pattern-qualified — `streamlit.*server.port 8601` (port-scoped; real_options holds the 85xx
block) and `uvicorn.*dashboard_web/api` (path-scoped) — we cannot hit their processes.

**Recommendation to the operator (their codebase, not touched here):** tighten
`real_options/deploy.sh` to a qualified pattern (its own port/path, e.g.
`streamlit.*server.port 8501` or an absolute app path) — the CLAUDE.md isolation mandate cuts
both ways, and today the unqualified side was theirs.
