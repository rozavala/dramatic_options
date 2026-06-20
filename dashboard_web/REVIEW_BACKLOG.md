# Dashboard Web — Review & Implementation Backlog (for Claude Code)

**Scope.** A thorough audit of `dashboard_web/` (the new React/Vite/Tailwind + FastAPI observability
UI) against (a) the design intent we agreed on, (b) the authoritative Streamlit reference
(`dashboard.py` + `dashboard_data.py`), and (c) general production-readiness.

**Verdict.** The implementation is high quality and faithful: tokens match the hi-fi spec exactly, the
`fromBackend` adapter ports the data contract (with four documented reconciliations), the API preserves
the read-only / NO-FETCH / fail-soft posture, and the adapter is unit-tested. The items below are gaps
and improvements, not a rewrite. They are organized **MECE** by concern, each with **severity**, exact
**location**, the **problem**, and a concrete **fix**. A suggested sequence is at the end (§J).

Severity legend: **P0** correctness/safety (wrong or misleading numbers) · **P1** material gap ·
**P2** polish/robustness · **P3** nice-to-have.

> Paths below are repo-relative (`dashboard_web/...`). Where a fix touches the Python data layer it is
> called out explicitly, since that is shared with the live Streamlit dashboard and must stay behavior-
> compatible (the data layer is pure + tested; never add fetch/write/broker calls).

---

> **AUDITOR'S NOTE (verification pass, 2026-06-20).** Every finding below was checked against the live
> code at `4156e84` (schema 14). The audit stands — the high-severity findings (A1, B1, D1, H1) are real
> and well-located. **Four corrections were folded in**, each marked `↳ FINE-TUNE`:
> - **A5 downgraded P1→P3 (the only substantive reversal).** `positions_panel` *already* SELECTs
>   `p.theme` (`dashboard_data.py:804`, shipped in PR #75). The claimed "missing one-line SELECT" does not
>   exist; what remains is stale code-comments. The Theme column is fully plumbed (untestable only because
>   the book is empty).
> - **A1's example sharpened.** The "condition 4 · `checkable:false` · verdict `BREACH`" case is the
>   *test fixture* (`adapter.test.ts:70`), not the live scoreboard — live condition 4 carries
>   `verdict:None` (`dashboard_data.py:972`). The *live* divergence is driven by condition 3 = `VACUOUS`.
>   The headline fraction is wrong **right now**: Streamlit shows **1/3**, the web UI shows **1/2**.
>   Severity (P0) and the fix are unchanged.
> - **H1 strengthened.** No parity test exists, *and* `snapshot.py` already advertises one it doesn't
>   have (docstring line 77 says "parity-tested"; line 36 says "so a parity test can assert"). Fix both.
> - **H3 sharpened from a hedge to a fact.** The web UI is **not in CI at all** — `ci.yml` has only
>   `test` / `test-dashboard` / `secrets`; nothing runs `vitest` / `tsc` / `vite build`. Adding RTL tests
>   also needs new devDeps (`@testing-library/react` + `jsdom`); only `vitest` is present today.
>
> Smaller clarifications (`↳ FINE-TUNE`) were added to A2, A3, C, and H2. Everything else verified as
> written.

---

## A. Data correctness — numbers that can be wrong or misleading (P0–P1)

### A1. T4 "readiness" denominator diverges from the backend's `checkable` flag — **P0**
**Where:** `ui/src/data/adapter.ts` (the `cond`/`able`/`readiness` block, lines ~84–88 and ~142–146) and
`ui/src/data/status.ts` (`t4State`).
**Problem:** the backend already emits a per-condition `checkable: boolean` for exactly this purpose, and
the Streamlit reference uses it directly (`dashboard.py:555–557`):
```python
checkable = [c for c in t4["conditions"] if c["checkable"]]
met       = [c for c in checkable if c["verdict"] in ("MET", "PASS")]
accruing  = [c for c in t4["conditions"] if not c["checkable"]]
```
The web adapter ignores `c.checkable` and **re-derives** "checkable" from the verdict→state map
(`pass|blocked|inprogress`). These disagree whenever a condition's `checkable` flag and its verdict don't
line up.

`↳ FINE-TUNE — what actually diverges, verified against the live `t4_scoreboard` (`dashboard_data.py:959–975`):`

The five live conditions today are: (1) `MET`·checkable, (2) `None`·not-checkable, (3) `VACUOUS`·checkable
(cluster-cap before any admissions — the book is empty), (4) `None`·not-checkable, (5) `IN_PROGRESS`·checkable.

- **The live driver is condition 3 (`VACUOUS`, checkable).** The web `able` filter keeps only
  `pass|blocked|inprogress`, so `VACUOUS` is dropped from the denominator entirely; the backend keeps it
  (it's `checkable:true`). **Net, right now:** Streamlit renders **"1/3 automatable checks pass · 2 accruing"**;
  the web UI renders **"1/2"**. That is the central KPI showing a different fraction than the source of
  truth — hence P0.
- **A non-checkable condition that carries a verdict is a *latent* second divergence, not a current one.**
  The doc's original "condition 4 · `checkable:false` · verdict `BREACH`" example is the **test fixture**
  (`adapter.test.ts:70`), *not* the live scoreboard — live condition 4 is `verdict:None`
  (`dashboard_data.py:972`). Under that fixture the web UI counts the `BREACH` row as a blocked checkable
  gate (`checkable:3, accruing:1`) while the backend treats it as accruing (`checkable:3, accruing:2`) —
  the denominator coincidentally matches but the accruing count diverges. This would bite for real only if
  a non-checkable condition ever gains a non-null verdict, so it's worth fixing defensively but it is not
  the number that's wrong today.

**Fix:** drive readiness off the backend flag, not the verdict:
```ts
const conds = P.t4?.conditions ?? [];
const checkable = conds.filter(c => c.checkable);
const readiness = {
  pass: checkable.filter(c => c.verdict === "MET" || c.verdict === "PASS").length,
  checkable: checkable.length,
  accruing: conds.filter(c => !c.checkable).length,
};
```
Keep the verdict→state map **only** for the per-row icon/tag in the T4 list. Add a `deferred` display
state (or reuse `accruing`) for `!checkable` rows so a non-checkable `BREACH`/`VACUOUS` row renders as
"accruing — verdict deferred" rather than a hard ✕/◯, matching the Streamlit tag `(accruing — verdict
deferred)` (`dashboard.py:561`). After the fix the live headline moves from **1/2 → 1/3**. Update the
adapter test (see H2 — the divergent cases already exist in the fixture).

### A2. Mission "phase" progress bar and subtitle are hardcoded stubs — **P1**
**Where:** `ui/src/data/adapter.ts:147` → `phasePct: "50%"`, `phaseSub: "first null reads ~Mo 6"`.
**Problem:** the calibration progress bar in `MissionStrip` and its caption are fabricated constants; they
never move with reality, so they read as a real metric but aren't.
**Fix:** derive from a real quantity. Cheapest faithful option: progress = resolved-bets toward the edge
target, i.e. `phasePct = clamp(edgeAccrual.n / edgeAccrual.target) * 100`, with `phaseSub` like
`"${n}/${target} resolved bets"`. Better: compute calendar progress from the first cycle timestamp vs the
~6-month calibration window — but `↳ FINE-TUNE:` no `first_cycle_at` exists on the wire today (`header`/
`account` carry no such field), so that path requires a small backend addition (e.g. surface
`MIN(started_at)` from `runs`). Until a real source exists, label it honestly (e.g. "Calibration ·
accruing") rather than a fixed 50%.

### A3. "Recent run streak" is always "—" — **P1**
**Where:** `ui/src/data/adapter.ts:115` → `council.streak: "—"`; rendered in `Safety` and mobile `MSafety`.
**Problem:** the field is permanently a dash, which looks broken/empty. The backend already provides the
data: `council.recent[]` is emitted by `council_panel` (`dashboard_data.py:871`) as the trailing window
(oldest→newest, each with a `verdict`).
**Fix:** type `council.recent` in `types.ts` (the `council` interface currently types `health`/`model_mix`/
`cost`/`by_provider` but **not** `recent`) and compute a streak in the adapter, e.g. count trailing
`ROUNDTRIP_CONFIRMED` runs and phrase as `"3 clean"` / `"3 clean, then #287"`. `↳ FINE-TUNE:` the window
is capped at `RECENT_COUNCIL_N = 4` (`dashboard_data.py:48`), so the streak saturates at 4 — phrase it as
"≥4 clean" at the cap, or read all-time from the health verdict, rather than implying an unbounded count.
If `recent` is empty, fall back to a single-run phrasing from `health.verdict`.

### A4. `edgeAccrual.target` is a magic constant (30) — **P2**
**Where:** `ui/src/data/adapter.ts:147`.
**Problem:** the "first null read" sample-size target is hardcoded; if the prereg threshold differs it will
mislead.
**Fix:** source it from `config.json` (exposed via a small `t4`/`performance` field) or, at minimum, define
it as a single named constant with a comment citing the prereg. Low effort, removes a silent assumption.

### A5. Position `theme` plumbing — stale comments only (the SELECT already shipped) — **P3** *(was P1)*
`↳ FINE-TUNE — the original P1 finding is no longer correct.`
**Where:** `dashboard_data.py:804` (the live query), and stale comments at `ui/src/data/adapter.ts:8` and
`ui/src/data/types.ts:30`.
**Problem (corrected):** `positions_panel`'s real-open query **already SELECTs `p.theme`**
(`dashboard_data.py:803–804`, added in PR #75), and the adapter already maps it (`adapter.ts:79`,
`theme: p.theme`). So the Theme column **is** fully wired and will light up the moment a real position
carries a theme — it only reads "—" today because the book is empty. The remaining issue is purely
cosmetic: two comments still claim the SELECT is "pending" —
- `adapter.ts:8`: *"`theme` is not yet emitted by positions_panel (pending a 1-line SELECT add)"*
- `types.ts:30`: *"⚠ NOT yet emitted by positions_panel — pending a 1-line SELECT add"*

**Fix:** delete/correct both stale comments, and consider tightening `PositionRow.theme` from optional
(`theme?: string`) to a definite `string | null` to match the column. No data-layer change is needed.
(There is therefore nothing to add to `tests/test_dashboard_data.py` for this — the column is already
covered by the panel's existing row shape.)

### A6. Direction vocabulary coupling is implicit (and duplicated) — **P2**
**Where:** `ui/src/components/Book.tsx:10` & `ui/src/mobile/MobileApp.tsx:19` — `dirLabel`
(`bullish→CALL`, `bearish→PUT`, else `.toUpperCase()`), copy-pasted in both files.
**Problem:** the CALL/PUT label is inferred from a `direction` string; if the data layer ever emits
`long/short` or already-mapped `CALL/PUT`, the label silently passes through `.toUpperCase()`. The logic
is also duplicated in two places (drift risk).
**Fix:** centralize the mapping in `status.ts` (one `directionLabel()`), assert the known vocabulary in a
test, and have the adapter normalize `direction` once so components don't each re-map.

---

## B. Fail-soft & error visibility — a regression vs Streamlit (P1)

### B1. Per-panel failures are swallowed (look identical to "accruing") — **P1**
**Where:** `ui/src/data/adapter.ts` (every `P.<panel> ?? ({} as …)`), surfaced nowhere in the components.
**Problem:** `dd.safe` wraps a failed panel as `{"error": "..."}` (`dashboard_data.py:85–91`). The
Streamlit shell renders a visible `st.warning("<panel> unavailable (fail-soft): <error>")` per panel
(`dashboard.py:89–93`, `_show`). The web adapter treats `{error}` as a present-but-empty object (it's
truthy, so it doesn't even hit the `?? {}` fallback) and renders dashes/zeros. **The operator can no
longer distinguish "this panel crashed" from "this metric is genuinely accruing" — which is precisely the
distinction the whole design is built around.**
**Fix:** in the adapter, detect `panel?.error` and carry a per-section `errors: Record<string,string>` (or
a `degraded: string[]`) onto the ViewModel. In each section render a small inline "unavailable (fail-soft):
…" banner using the existing `bad`/`warn` tonal container, exactly like Streamlit's `_show`. Don't let a
single failed panel blank a section.

### B2. `header.schema_warning` is never shown — **P2**
**Where:** typed in `types.ts:44` (`schema_warning: string | null`), used by neither console (grep of
`ui/src/` finds it only in the type and the test fixture).
**Problem:** schema drift between the DB and the dashboard's expectation is surfaced by Streamlit
(`st.warning(f"⚠ {schema_warning}")`, `dashboard.py:516–517`); in the web UI only the "Schema" heartbeat
pill changes color, and the actual message (which says what's wrong / what to migrate) is dropped.
**Fix:** when `schema_warning` is non-null, render a top-of-page warning strip (above the status banner) on
both desktop and mobile.

### B3. `_fatal` path is handled but untested and slightly hidden on mobile — **P3**
**Where:** `App.tsx:13–15` → `fatal`; `DesktopConsole.tsx:88` / `MobileApp.tsx:367` render it.
**Problem:** good that it exists; but it's only a small red card. For a missing-DB fatal the operator
should see an unmistakable full-bleed message (this is the "you pointed at the wrong DB" footgun — the
backend even returns the resolution hint in the string, `snapshot.py:80`).
**Fix:** make the fatal state a centered full-panel message with the resolution hint (it already contains
the path); add a test for the `_fatal` branch.

---

## C. Missing panels / sections — coverage vs the Streamlit reference (P1–P3)

The redesign deliberately **consolidated** the 7 Streamlit tabs into 5 sections — correct. But several
panels are **fetched by the API and never rendered** (`PANEL_KEYS` lists 21; `types.ts:90` documents the
unrendered set). Some are material observability; decide per item whether to surface (recommended for the
first four) or explicitly drop.

| Panel (API key) | What it is | Recommendation | Severity |
|---|---|---|---|
| `nulls` (null hierarchy) | The per-step null **contrasts** — the actual statistical "does the brain help" plumbing (each step = one clean/bundled contrast with CI). | **Add to The Edge**, below the p95 summary, as a compact stepped table. This is the heart of the calibration thesis; Edge currently shows only the summary tails. | **P1** |
| `cost` (LLM cost ledger) | L0 framer / L1 council / cumulative USD. | **Add a small card** to Pipeline or Safety. Cheap, operationally useful (cost creep is a real signal). `↳ FINE-TUNE:` the same ledger is **already on the wire under `council.cost`** (`dashboard_data.py:872`), so the card can be wired from the existing `council` panel — the top-level `cost` key is redundant for this and could even be dropped (see the "drop" action below). | **P1** |
| `dualread` (OPRA gate dual-read) | Tripwires (Δiv/rv, material-flip, gap sessions) + disagree-veto window — a §5 **fail-closed safety** mechanism. | **Add to Safety & Risk** as a tripwire row (clear/⚠ TRIPPED). Safety-relevant. | **P1** |
| `council.by_provider` + `council.recent` | Per-provider parse health + recent-runs regression strip (catches a degradation *before* it flips a checkmark). | **Add to Safety** under council health. Feeds A3 (streak) too. Both are already emitted by `council_panel`. | **P1** |
| `deliberation` (latest run) | Per-name proposer→adversary→strategist — the "why" (`latest_run_deliberation`). | **Add to Pipeline** as an expandable table (or a "latest decisions" list). | **P2** |
| `cap_flow` | Cluster-cap rejections of otherwise-passing candidates. | **One line in Pipeline** ("cluster-cap rejected N otherwise-passing"). | **P2** |
| `regime` | Feeds/models config-of-record (run ids, model mix, frame version). | **Optional** small caption under the header, or drop. | **P3** |
| `curation` | Cluster diagnostic + basket-quality blobs. | **Optional** deep-dive (expander); low priority. | **P3** |

**Action:** for each "drop" decision, remove the unused key from `PANEL_KEYS` (`snapshot.py:38–42`) and the
build call so the payload and the type surface stay honest; for each "add", extend `types.ts` +
`adapter.ts` + the relevant section. `↳ FINE-TUNE:` dropping a `PANEL_KEYS` entry must be done in lock-step
with the H1 parity test (and with `dashboard.load_all`, if you want strict parity) — otherwise the parity
test you add will fail by construction.

---

## D. Performance & serving (P1–P2)

### D1. The API recomputes all 21 panels on every request — no cache — **P1**
**Where:** `dashboard_web/api/server.py:50–55` `snapshot()` → `build_snapshot(...)` (no memoization);
`dashboard_web/api/snapshot.py:73`.
**Problem:** the Streamlit `load_all` is wrapped in `@st.cache_data(ttl=60)` (`dashboard.py:49–51`). The
FastAPI route has **no caching**, so every poll/refresh/extra browser tab opens a fresh RO connection and
recomputes everything — including the heavy paths (bootstrap CIs, cluster diagnostics, basket quality,
curation). On an always-on wall display or with a couple of viewers this is needless load and slower
refreshes.
**Fix:** add a tiny in-process TTL cache (≈60s) around `build_snapshot` keyed by `(db_path, cache_dir)` —
e.g. a timestamped memo or `cachetools.TTLCache`. Have the UI's manual Refresh bypass via a `?nocache=1`
(mirrors Streamlit's `_nonce`). Keep the short-lived per-call connection.

### D2. No concurrency guard / connection reuse note — **P2**
**Where:** `snapshot.py` (RO connection per call).
**Problem:** RO connections are cheap and `?mode=ro` is safe under WAL, but with D1's cache most calls
won't touch the DB at all — implement D1 first, then this is moot. If D1 is declined, at least guard
against thundering-herd recompute (single-flight) so simultaneous requests share one build.
**Fix:** single-flight the build (a lock + "in-progress" promise) or simply rely on the TTL cache from D1.

---

## E. Freshness & live-ness (P1–P2)

### E1. No auto-refresh / polling — **P1 for a wall display, P2 otherwise**
**Where:** `ui/src/data/useSnapshot.ts` (fetch on mount + manual `refresh()` only).
**Problem:** the snapshot is static until someone clicks ↻. For an observability surface meant to sit open,
this is a real gap — a degradation won't appear until a human refreshes.
**Fix:** add an opt-in polling interval (e.g. `setInterval` every 60s, aligned with the server cache TTL),
pausing when the tab is hidden (`document.visibilitychange`) and resuming on focus. Make the interval a
prop/env so a wall display can poll and a casual viewer needn't.

### E2. No staleness emphasis on "as of" — **P2**
**Where:** `DesktopConsole.tsx:15,75–77` header (`asOf` = a plain `slice(0,16)` timestamp, no "ago", no
color); `MobileApp.tsx` header renders **no timestamp at all** (confirmed — no `asOf` reference).
**Problem:** the heartbeat pills encode loop liveness, but the top-line "as of" is a plain timestamp with no
"Nh ago" and no color when stale; the mobile header shows no timestamp.
**Fix:** render "as of <ts> · <Nh ago>" and tint it warn/bad past thresholds (reuse the heartbeat age you
already compute). Show the timestamp on mobile too (compact).

---

## F. UX & polish (P2–P3)

### F1. No loading skeletons — initial load is a blank content area — **P2**
**Where:** `DesktopConsole`/`MobileApp` (only the 3px bar shows; content is empty until the first fetch
resolves — `DesktopConsole.tsx:99` shows "No snapshot." once not-loading).
**Fix:** render lightweight skeleton cards (gray blocks at the real card sizes) while `vm == null && loading`.
Keeps layout stable and signals "loading," not "empty."

### F2. Number count-ups not implemented — **P3**
**Where:** KPI values, ring, big mono numbers (confirmed — no `useCountUp`/rAF hook anywhere in `ui/src/`).
**Problem:** this was an agreed polish item; currently values snap in.
**Fix:** a small `useCountUp(value)` hook (rAF, ~400ms, respects `prefers-reduced-motion`) for the four KPI
values + the ring. Keep it off the per-row tables (noise).

### F3. Pipeline funnel mixes a count into a flow — **P3**
**Where:** `Pipeline`/`MPipeline` "Wasted calls" as the 4th funnel step (`adapter.ts:129` — `wasted` is a
COUNT, not a flow stage).
**Problem:** proposed→evaluated→opened is a flow; "wasted calls" is a different unit shown in the same row,
which can read as a 4th flow stage.
**Fix:** visually separate "Wasted calls" (e.g. a caption under the funnel, or a divider) so it's clearly a
side-metric, not a funnel stage.

### F4. Refresh affordance lacks disabled/feedback state — **P3**
**Where:** the ↻ button spins via `animation` but stays clickable during load.
**Fix:** disable it while `loading` and drop the opacity slightly, so rapid double-clicks don't queue
fetches.

---

## G. Accessibility & responsive (P2–P3)

### G1. Nav/tabs missing ARIA semantics — **P2**
**Where:** `DesktopConsole` rail buttons; `MobileApp` bottom tabs.
**Problem:** section nav is a set of `<button>`s with no `aria-current`/selected semantics; the mobile tab
bar isn't a `tablist`. Desktop refresh uses `title` (mobile uses `aria-label` — good; make both consistent).
**Fix:** add `aria-current="page"` to the active rail item; give the tab bar `role="tablist"` and each tab
`role="tab" aria-selected`; ensure focus-visible styles exist (currently relies on UA default).

### G2. Faint text contrast is borderline — **P3**
**Where:** `inkFaint #8b919b` on white for ~10–11px captions (~3.5:1).
**Fix:** for the smallest captions use `ink4 #5f6675` (≈5.8:1) or bump size; reserve `inkFaint` for ≥12px.

### G3. Mid-width desktop crowding — **P3**
**Where:** `grid-cols-4` KPI row / `grid-cols-2` detail grids between the 760px mobile breakpoint and ~1000px.
**Fix:** add a `lg:` breakpoint so KPIs drop to 2×2 and detail grids stack below ~960px (the content
max-width is 1180, so this only bites on smaller laptops/split screens).

---

## H. Testing & CI (P1–P2)

### H1. No parity test for `PANEL_KEYS` vs `dashboard.load_all` — **P1**
**Where:** `snapshot.py:36–37` and the `build_snapshot` docstring (`snapshot.py:77`) both advertise a
parity test, but no such test exists under `dashboard_web/api/` (the only test in the whole UI tree is
`ui/src/data/adapter.test.ts`).
**Problem:** if the live Streamlit `load_all` gains/renames/loses a panel, `snapshot.py` silently diverges
and the UI quietly loses data — and the code *claims* this is already guarded ("parity-tested"), which is
worse than silence.
**Fix:** add `dashboard_web/api/test_snapshot_parity.py` asserting `set(snapshot.PANEL_KEYS) ==
set(dashboard.load_all signature keys)` (introspect the dict literal or refactor both to share one
`PANEL_BUILDERS` table — the cleaner option: define the panel list once and import it into both). Then
correct the two comments so the claim matches reality. `↳ FINE-TUNE:` place it where CI will actually run
it — the `test-dashboard` job installs the dashboard deps, so a pytest under `dashboard_web/api/` is
collected there; `system_status` is injected (not a `load_all` key), so the assertion is over `PANEL_KEYS`
vs `load_all`'s 21 panels, not the snapshot's 22.

### H2. Adapter test encodes the A1 divergence — **P1 (tied to A1)**
**Where:** `ui/src/data/adapter.test.ts:65–71` (fixture) + `:133–135` (the "computes readiness" assertion,
currently `{ pass: 1, checkable: 3, accruing: 1 }`).
**Fix:** after A1, update the expectation to the backend `checkable`-based composition. `↳ FINE-TUNE:` the
two edge cases the original doc said to "add" **already exist** in the fixture — condition 3 is `VACUOUS`
(checkable) and condition 4 is `checkable:false` with verdict `BREACH`. So only the *expectation* changes:
with `checkable`-driven readiness the fixture yields `{ pass: 1, checkable: 3, accruing: 2 }` (the two
`checkable:false` rows — conditions 2 and 4 — both count as accruing; `VACUOUS` stays in the denominator).
No new fixture rows are required.

### H3. The web UI is not in CI; no component / render tests, no e2e — **P2**
`↳ FINE-TUNE — sharpened from "verify it covers" to a confirmed finding.`
**Where:** `.github/workflows/ci.yml` has exactly three jobs — `test` (pytest + ruff), `test-dashboard`
(pytest with streamlit), `secrets` (gitleaks). **None of them touch `dashboard_web/ui`**: there is no Node
setup, no `npm ci`, no `vitest`, no `tsc --noEmit`, no `vite build`. So the 12 vitest cases and the
type-check run **only locally** — a TS error or a red adapter test cannot fail CI today.
**Fix:**
1. Add a Node CI job: `npm ci && npm run test && npm run typecheck && npm run build` against
   `dashboard_web/ui` (the scripts already exist in `package.json`: `test`=`vitest run`, `typecheck`,
   `build`). This is the highest-leverage item in H — it makes A1/H2/B1 regressions catchable.
2. Add React Testing Library smoke tests per section (renders with the synthetic VM; asserts the accruing
   empty-state, a degraded council, and a fail-soft panel banner). `↳ FINE-TUNE:` this needs new devDeps —
   `@testing-library/react` + `jsdom` (and a `jsdom` vitest environment); today only `vitest` is installed,
   and `adapter.test.ts` is a pure-function test that needs no DOM.
3. Optionally one Playwright happy-path against a fixture API.

---

## I. Security & deployment hardening (P2–P3)

### I1. No auth on the API (by design, but make it deliberate) — **P2**
**Where:** `server.py` — relies on localhost/tailnet bind + GET-only CORS; renders the whole book + cluster
map. `↳ FINE-TUNE:` note the live deploy binds the **tailnet IP**, not pure localhost (`:8602`), and after
the 2026-06-20 ACL change any tailnet *member* can reach the port — so the "wide open to anyone who reaches
the port" risk is now concrete for tailnet members, not just hypothetical.
**Fix:** keep localhost/tunnel as the default, but add an optional shared-token gate
(`DASHBOARD_TOKEN` → `Authorization: Bearer`) so a tailnet/remote deploy isn't wide open to anyone who
reaches the port. Document it in `dashboard_web/README.md`.

### I2. CORS + static-mount ordering — confirm prod path — **P3**
**Where:** `server.py:64–71` mounts `StaticFiles` at `/` last (only if `dist/` exists); CORS allowlist is
dev-only (`server.py:39–47`).
**Status:** verified correct (API routes are declared before the catch-all mount, so `/api/*` wins; SPA
served same-origin in prod; `VITE_API_BASE` defaults to `""` = same-origin, `useSnapshot.ts:6`).
**Action:** add a one-line test that `/api/snapshot` resolves before the SPA catch-all (a regression guard
if the mount ever moves above the routes).

### I3. Font dependency on Google Fonts CDN — **P3**
**Where:** `ui/index.html:7–10` loads Roboto/Roboto Mono from `fonts.googleapis.com`.
**Problem:** an air-gapped/locked-down host (this is operator-confidential, tailnet-bound) may block the
CDN, dropping to system fonts.
**Fix:** self-host the two font families (woff2 in the build) so the UI is fully offline-capable, matching
the no-public-egress posture.

---

## J. Suggested sequence (highest value first)

1. **A1** (readiness off `checkable`) + **H2** (update the existing assertion) — the headline metric is
   wrong today (1/2 vs 1/3); fix it first. *(P0)*
2. **B1** (per-panel fail-soft banners) + **B2** (schema warning) — restore the observability the Streamlit
   shell had; this is the core "broken vs accruing" distinction. *(P1)*
3. **A3** (council streak, data already on the wire) + **A2** (real phase progress) — kill the visible
   stubs/“—”. `↳ FINE-TUNE:` A5 dropped out of this step — the `theme` SELECT already shipped; A5 is now
   just a P3 comment cleanup. *(P1)*
4. **H3 step 1** (put the web UI in CI) — do this *with* step 1 so A1/H2 can't silently regress again. *(P2)*
5. **D1** (TTL cache) + **E1** (opt-in polling) — make it a real always-on surface. *(P1)*
6. **C** additions in priority order: `nulls` → `dualread` → `cost` (from `council.cost`) →
   `by_provider/recent`. *(P1)*
7. **H1** (panel-parity test + correct the overclaiming comments) + **H3 steps 2–3** (section smoke tests).
   *(P1–P2)*
8. **F1** (skeletons) → **E2** (staleness) → **G1** (a11y) → **F2/F3/F4** polish → **A5** (comment
   cleanup) → **A4/A6** (de-magic the constants, centralize `dirLabel`). *(P2–P3)*
9. **I1/I3** (token + self-hosted fonts) for a hardened remote deploy. *(P2–P3)*

### Guardrails for every change
- The data layer (`dashboard_data.py`) stays **pure, read-only, NO-FETCH, fail-soft**; any addition is
  additive and behavior-compatible with the Streamlit shell (run `tests/test_dashboard_data.py`).
- The API stays keyless + GET-only + localhost/tailnet-default; never introduce a write/broker/auth-to-broker path.
- Keep the design tokens in `theme/tokens.ts` (+ `tailwind.config.js`) as the single source of truth — no
  ad-hoc hex in components beyond what's already there; ideally migrate the remaining inline literals to the
  token objects over time.
- When in doubt about a metric's meaning, the **Streamlit panel + its `help=` text in `dashboard.py`** is
  the canonical definition — match it.
