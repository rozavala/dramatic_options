# PREREG — the structural-filing surface leg (the event provider)

**Status: FROZEN by the merge of this PR (2026-06-10).** Fulfills `PREREG_UNIVERSE_CURATION §7`
resolution **(a)** (operator-picked at the §11 freeze): the event-provider wiring is the next
session, and **the §5 universe-sizing clock counts only scans run on the FINAL funnel
configuration — this merge is that anchor** (auditable from git, the per-scan `runs.note` stamp,
and per-name `markers.has_event`; not dependent on journald retention). Converged over a relayed
advisor red-team round (P1.1–P1.4 + P2.5–P2.8 + the final refinement round) with a pre-merge
EDGAR smoke that pinned the literal form strings.

**Funnel-freeze pre-commitment:** the funnel configuration then HOLDS through the §5 four-scan
read — the §9(a) per-basket quotas, §9(c) fit-aware door, and the grounding leg are sequenced
AFTER that read completes (or restarting the clock is a documented, dated decision).

## 1. What this is (and is not)

The disjunctive surface gate (`|momentum|≥floor` OR `rv_slope≥floor` OR **a structural filing**)
shipped with its event arm built and tested but **dormant live** (no `event_provider` passed).
This PR wires it. The event leg is the **only quiet-compatible door** — it can surface a
capital-raising small-cap *before* it moves, the exact profile of the window-#1 universe.

**FSSD honesty (the grave restated):** `PREREG_FSSD.md` graded the 424B5 event ≈ a random-date
null for DRIFT — conditioning on the filing added ~nothing over the characteristic. The event
here carries **no alpha/drift claim**: it is a REACHABILITY trigger under the §2 prescreen
doctrine ("something is happening"; cheapness stays the IV gate's job; the rank is a funnel,
never a signal). A dead week still surfaces nothing — the floors stay absolute.

## 2. Data path — a dated deviation from the frozen §7(a) wording

`PREREG_UNIVERSE_CURATION §7(a)` (frozen 2026-06-10) reads: *"reuses the shelved FSSD EDGAR
plumbing `data/edgar_index`/`data/prospectus` in exactly the sanctioned non-authorizing role."*
**This pre-reg supersedes the vehicle by dated amendment:** the leg runs on the per-company
SUBMISSIONS path — `data/filings.py` (`EdgarClient` + `FilingsData.filings_asof`: PIT-cached,
ticker→CIK via `company_tickers.json`, SEC-throttled, offline-safe). Reason:
`data/edgar_index._quarter_text` (data/edgar_index.py:102–112) returns a disk-cached quarterly
index **without ever re-fetching the in-progress quarter** — correct for the closed-quarter
historical studies it served, disqualifying for a weekly LIVE leg (new filings would be invisible
until the quarter closed). Submissions are **fresh by construction** (coverage re-extends with
`fetch_end` each scan). The non-authorizing role is unchanged; `edgar_index`/`prospectus` remain
the historical tools. Recorded bonus: submissions carry the 8-K `items` field the quarterly index
never had (see §6c). Cost: ~33 submissions JSONs per weekly scan at the existing throttle
(~4–5s, $0), inside L0's `TimeoutStartSec=900`.

## 3. The pinned event set — exact membership, both listing regimes

- **Bases (config `discovery.events.forms`):** domestic raises **424B5, S-1, S-3**; the
  foreign-issuer mirror — the universe holds Canadian MJDS/FPI names (HBM/ERO/TGB/NXE) whose
  raises do NOT flow through S-forms — **F-1, F-3, F-10, SUPPL**; ownership **SC 13D** and
  **SCHEDULE 13D** (BOTH literals pinned: the 13D/G modernization renamed the form mid-record —
  the 2026-06-10 smoke observed legacy `SC 13D`/`SC 13D/A` AND current `SCHEDULE 13D`/
  `SCHEDULE 13D/A` in-universe, e.g. UEC 2026-01-16, NXE 2025-06-26; subject-side visibility in
  the submissions stream CONFIRMED on UEC/RDW/HBM/TGB/NXE/PL/SMR).
- **Matching = set membership** `form ∈ {base, base + "/A"}` per base — **never a prefix**.
  Excluded near-misses, enumerated on BOTH sides: domestic **S-11** (REIT registrations),
  S-1MEF/S-3MEF, S-3D/S-3DPOS, and **S-3ASR deliberately** (the WKSI automatic shelf —
  $700M+-float routine, the opposite cohort; observed on PL 2026-06-05 and correctly NOT an
  event); foreign **F-3ASR/F-3MEF/F-10EF/F-10POS**; **424B1/B2/B3/B4** (424B3 is resale-spam on
  exactly these small-caps — UEC has 28). The symmetry that makes the set coherent:
  **routine-shelf REGISTRATIONS are excluded on both sides (S-3ASR / F-10EF-class); their
  TAKEDOWNS are caught on both sides (424B5 / SUPPL).**
- The uniform `/A` rule means an `SC 13D/A` reflecting a **stake reduction** also surfaces the
  name — acceptable under reachability-no-alpha-claim, stated so an exit filing surfacing a name
  never reads as a bug.
- **Lookback: a CLOSED `[as_of − 14d, as_of]` window** (day-14 IN, day-15 OUT; ≈ two weekly
  scans, so a filing cannot slip between doors). `event_kind` = the base form — it flows into the
  markers JSON and `marker_summary` ("event 424B5") and thence the framer/council grounding,
  unchanged code.
- These are **funnel knobs** (the `MarkerParams` doctrine): changed only by dated operator edit;
  the **form-set hash** is stamped per scan (§4) so the record is self-describing across any
  future set change.

## 4. Fail-SOFT, never invisible (the anti-silent-dormancy apparatus)

This leg was invisible-dormant once; its failure modes must never be. The provider counts
**checked / cik_resolved / no_cik / fresh / errors** (no_cik split from errors — ticker-map gaps
are the likelier failure on new small-caps). Every scan emits a structured status —
`events:ON ev=<form-set-hash> checked=33 cik=31 no_cik=2 fresh=2 err=0 [fresh_names=…]` or
`events:OFF reason=<disabled|no EDGAR_USER_AGENT|client error>` — to the journal AND, because
`record_run` fires BEFORE the scan, stamped post-scan into the existing `runs.note` via the new
atomic `state.append_run_note` (DB-durable; journald rotates). **Systemic failure** (errors ≈
checked on a non-trivial scan, or zero CIK resolution) → `log.warning` + a `notify.send` in-app
page (the soft-trip precedent): `ON, 0 fresh` is never byte-identical to a broken leg. Per-name
failures degrade that name only (the existing `compute_markers` brace + the provider's own).
The factory reads the EXISTING `config.edgar.user_agent` seam (config_loader.py:96–98 maps
`EDGAR_USER_AGENT`; already present in the live `.env`) — never `os.environ` directly.

## 5. The pinned falsifiable (blind, directional, maturity-gated) + its persistence artifact

**Prediction, committed before any data exists:** among SURFACED sentinels,
**P(gate-cheap | event-origin) > P(gate-cheap | motion-origin).** Motion-surfacers arrive
post-move with repriced IV almost by definition; a pre-move filing surfacer is the one cohort
where the gate should still find cheap convexity. If event-origin names do NOT pass the gate more
often, the quiet-door reachability story weakens — recorded now so it is evidence, not rescue.

**Permission isn't persistence:** the §6 sweep as frozen records aggregates + a fit count only,
and `convexity_eval` cannot serve (only post-council names reach it — the surfaced-but-damped
cohort never appears). So the sweep (`scripts/probe_basket_gate_baserate.py`) gains a
**sealing-compliant surfaced-subset extension recording from scan #1**: per-name
`{date, symbol, basket, surface_origin(event|motion from markers.has_event), gate_cheap,
fits_one, per_contract_usd, gate_feed}` printed AND appended to
`records/gate_baserate_surfaced.csv`. Surfaced names are public under the
`PREREG_UNIVERSE_CURATION §6` sealing boundary (non-surfaced names stay sealed/aggregate-only).
**Source pinned uniformly: the sweep's rows on the gate-of-record feed** — the comparison never
mixes sweep and real-loop evaluations. **Read when n_event ≥ 5**; direction only, no threshold.

## 6. Known-opens (named so they don't vanish)

- **(a) Direction.** `Theme.direction` is FIXED at surfacing (frozen dataclass; the adversary is
  validated direction-relative against it; `direction_of` is motion-signed with a bullish
  default): the council can DAMP a near-noise-direction event-surfacer to NEUTRAL/LOW but can
  never FLIP it — conviction suppression is the only disposal. An event→direction map (e.g.
  424B5 = dilution = bearish?) would be new latitude on a question FSSD answered "no drift
  either way": deferred, its own pre-reg if ever.
- **(b) The motion-fades-then-files seam.** `revalidate_active` already exempts event-origin
  sentinels from motion-dormancy (sentinels.py:123 — by design). A MOTION-origin sentinel whose
  motion fades and who files mid-week goes dormant until the next scan's event arm re-surfaces it
  (lineage updates in place): one-scan latency, self-healing, accepted.
- **(c) The 8-K pinned-item subset** (items 1.01 material agreements / 2.01 completed
  acquisitions — quiet-small-cap catalysts): the submissions path carries the `items` field, so
  this is nearly free later — but it is new latitude and raw 8-K would collapse the floor:
  its own future pre-reg.
- **(d) Form 4 / news events: excluded** (always-on collapse; Form 4 is graveyard-adjacent — the
  divergence insider leg).

## 7. Evaluation

By the existing forward instruments only: the surface-reason split (motion vs rv vs event,
reconstructable read-only from `sentinel_candidates.markers` vs the config floors), the §6 sweep
+ the new §5 CSV, sentinel forward-scoring (traded → Brier + realized multiple; never-traded →
the reference sweep), and the null books — **never entry count**. Honest expectation: fresh
pinned-form filings are rare; most scans the leg contributes zero surfacers. (At the pre-merge
smoke, two universe names had in-window filings — RDW 424B5 filed 2026-06-09, PL 424B5
2026-06-05 — so the verification fire should read `fresh≥2`: a live check, not a yield claim.)
