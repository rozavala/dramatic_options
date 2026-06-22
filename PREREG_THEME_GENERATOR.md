# PRE-REG — the Stage-1 thesis GENERATOR (theme-generation layer)

**STATUS: FROZEN via this merge 2026-06-22.** This is the parameter-freeze document the
`PREREG_THEME_GENERATION_STUB.md` deferred. It freezes the four generator parameters (C.2 roster · C.3
citation predicate · C.5 blind yield band · C.6 the red-team) and the build posture. The §10
confirm-set is FILLED (operator-ratified, pinned blind); the operator's MERGE of this branch is the
freeze act.

**Freeze preconditions — ALL MET (was the parked gate):** (a) the **7/10 close-out bandwidth blocker is
CLEARED** — `PREREG_COUNCIL_GATE_SEPARATION §5` is frozen and L1 #72 is live, so the freeze no longer
contends with the close-out for the binding operator/red-team bandwidth (§6); (b) the **§10 confirm-set
values are written into this text by the operator, blind**, as the merge act; (c) the final operator
sign-off rides this merge. Deploy stays **September-gated regardless** (§6) — the freeze gates the
judgment-grade run, not the fixture-INERT build.

**Red-team status:** round 1 = the 5-lens MECE pass (2026-06-22); round 2 = the operator pass
(2026-06-22, landed almost entirely on §3); both folded into v3, then frozen here. Dated 2026-06-22.

Text only — **§5-safe**: touches no live config/loop/council/gate, not the §5 funnel window. Drafting
(through v3) is **author bandwidth**, not operator bandwidth, so it does not contend with the
close-out; the FREEZE does, and is parked.

---

## 0. What this freezes, what it inherits frozen, what stays out

**Freezes here (params + posture):** C.2 roster (secondary, partial decorrelation, §2) · C.3 citation
verification (**citation-anchored** entity check + fact-by-source-class, DROP, §3) · C.5 the blind band
(§5, values in §10) · C.6 the red-team (this doc) · the build posture (build offline now against
fixtures, INERT; hold the judgment-grade run on §5; hold the deploy on the curation window; §6).

**Inherited FROZEN (not re-litigated):** the **§3 output schema** is the generator's hard output
contract, frozen `PREREG_NARRATION_PROBE.md:73-83` — including sub-structures: `statement` = "<driver>
→ <effect> → <entity class>"; `named_entities[{canonical, ticker, aliases}]`; `mechanism_direction
{vocab ∈ the pinned enum, sign}`; `headline_quantities[{metric, value, bucket}]` + bucket taxonomy;
`provenance:"generated"`. §4 restates it + the reopen path. **C.1** register unit = **mechanism-claim**
(`:68-71`) — confirm only. The **ordering condition** — **MET** (`:22-24`).

**Stays OUT (the July PROBE build's, pinned blind THERE):** **C.4** the `mechanism_direction`
classifier-agreement bar (`:117-119`). Pinning it here HARKs the probe. The §3 generator
citation-verifier shares **no tunable** with the §4 probe classifier (no back-door pin; §6). Note too
that the generator's §3 entity *verification* is distinct from the probe's §4 entity *narration-
scoring* (which legitimately uses `company_tickers` to measure recall) — do not conflate them.

---

## 1. The generator's job + the structural obstacle

Stage 1 reads the Stage-0 deterministic corpus (the in-memory PIT union from `corpus/assemble.py`,
routed by `corpus/content.py` coords) and **synthesizes falsifiable secular theses as mechanism
claims** in the frozen §3 schema, each **citing** the supporting corpus records it draws from.

PROPOSER only — never authorizes capital, never sizes, never sees a gate outcome, **never historically
backtested** (guardrail §6). Hard seam: generation proposes → council judges → the deterministic gate
disposes. A generated theme's only live-book path is a future curation-window admission, evaluated by
the existing FORWARD apparatus — never an event-conditioned deterministic backtest (§8).

**The binding obstacle (stub:12-15):** LLM free recall samples the *narrated* corpus — a
**training-data property** (the fifth, worst-placed anti-quietness instance). Defenses, by load:
**(1) the §3 citation DROP gate** (the LOAD-BEARING defense) and **(2) roster decorrelation (§2), a
secondary architecture hedge.** Because §3 is the defense, a *directional bias inside §3* is the most
dangerous thing in this document — P1 (round 2) found and removed one.

---

## 2. C.2 — Roster: a SECONDARY, partial decorrelation (the §3 DROP gate is the primary defense)

**Pin:** the generator runs on a **distinct provider→role assignment** from the live council
(gemini=proposer / xai=adversary / anthropic=strategist), heterogeneous (≥2 vendors), each model
exact-version-pinned via `runs.model_mix`. The realistic move brings **OpenAI (council-contingency)**
into a generator role.

**What it buys / does NOT.** The probe roster IS the council (`:154-156, 220-226`), so probe+council
are **one shared narration node** and the generator is the second — C.2 keeps the generator
architecturally distinct (**two effective nodes, not three layers**). But a provider→role reshuffle
reduces only **provider-architecture-correlated error**; it does NOT reduce the dominant shared-error
source — **narrated-corpus recall bias**, a training-data property two distinct frontier vendors share
on the same theme. **C.2 is therefore a secondary hedge; the §3 DROP gate is the defense against the
binding obstacle.**

**Directional payload.** A generator that recall-correlates with the council means a confabulated-but-
plausible theme is likelier *also* waved through the council — the council is a **weaker-than-
independent backstop**, which is why the deterministic, corpus-grounded §3 DROP gate, not the council,
is the load-bearing protection.

**Bounded claim.** With a finite frontier set and the probe roster fixed to the council, decorrelation
is **PARTIAL** — a distinct assignment, not a disjoint provider set (mirrors `:220-226`).

**One-way door.** Freezing C.2 is record-segmenting (a roster/role change stamps `runs.model_mix`), so
it is a one-way door for the generator's forward record. **Residual sub-decision (§10):** single-
synthesis vs an *additional LLM self-critique* pass (distinct from the deterministic §3 verifier, which
is kept regardless); recommend single-synthesis.

---

## 3. C.3 — Citation verification: CITATION-ANCHORED entity check + fact-by-source-class, DROP

A deterministic, **no-LLM** gate (the backstop on the LLM's recall). The generator emits a
**`citations` field** — a list of corpus coords `(source, key, ts)` it drew from — **additive to and
OUTSIDE the probe-scored §3 contract** (the probe scores only `named_entities`/`mechanism_direction`/
`headline_quantities`), so emitting it triggers no schema reopen; the stub already requires Stage-1 to
"cite supporting documents" (stub:26-28). A claim is admitted only if it verifies against **the records
it cites**:

- **Entity-level — MANDATORY, CITATION-ANCHORED (the P1 fix, round 2).** Each `named_entities[]` must
  appear — by **cik / symbol / name** — in at least one corpus record the claim **CITES**.
  `EdgarClient.ticker_to_cik` is **demoted to OPTIONAL secondary confirmation, never the primary gate.**
  - *Why not ticker_to_cik-as-primary:* its map is keyed by **current US ticker** (`data/filings.py:
    98-108`, title discarded → no name→CIK reverse lookup), so it false-drops **renamed / de-SPAC'd /
    foreign-listed** issuers — the **quiet end of the distribution** — a *sixth* anti-quietness instance
    **inside the load-bearing defense.** The project's own FSSD harness documents this exact drop as a
    known survivorship cost (`shelf/scripts/fssd_audit.py:106-113, 306`: "delisted/renamed names with
    no current ticker… the survivorship-honest cost"). Worked example: a uranium thesis citing **NXE**
    — a real name flagged `us_listed=False, "tsx"` in the cited URNM constituent record
    (`corpus/etf_constituents.py:_parse_symbol`) — would be wrongly dropped by a US-CIK-mandatory gate
    though the **cited evidence names it explicitly.** That is **US-optionability screening disguised as
    citation-verification**, and optionability is a downstream curation-Rule-1 concern
    (`PREREG_UNIVERSE_CURATION §11`), never this gate's job.
  - *Why citation-anchoring is STRICTER on the axis that counts:* it closes the gaming channel where a
    model cites doc A but names entity B that merely exists in some external map. Fail-closed: an entity
    in **no cited record** DROPs — that is genuine confabulation.
- **Fact-level — split by SOURCE-CLASS** (round-1 catch; verified against the adapters 2026-06-22),
  traced to the cited records' coords:
  - **(a) entity-bearing → record-keyed trace** (cik/symbol): `capital_raises {cik, company}`,
    `customer_concentration {cik, symbol}`, `etf_constituents {symbol, name}`.
  - **(b) entity-free macro → SOURCE+KEY+value trace** against the `(source, key)` coord
    `corpus/content.py:read_coords` exposes: `bls_series {series_id, value}`, `eia_series
    {metric, value}`, `nrc_dockets {name, docket}`.
  - **(c) free-text recipient → name-normalization tolerance:** `federal_awards {recipient}`
    (`recipient_id` is a USAspending id, not a ticker/cik).
  - **Which classes are fact-MANDATORY vs fact-where-present = operator's blind call (§10)**, ideally
    tied to the sparse-tolerant precedent (`:146-150`). Every trace keyed to a deterministic
    `(source, key, ts)` tuple, never list position.
- **Failure action = DROP, never dampen** (synthesis-device-never-memory; the quote-authenticity
  pattern `council/filters.py:37-54` re-implemented HARD).
- **Two split forensic counters:** `dropped_entity_unresolved` (named entity in no cited record) +
  `dropped_fact_untraced` (real entity, untraced figure) + total — the §5 band needs the split to read
  a degenerate yield (high `_fact_untraced` ⇒ corpus; high `_entity_unresolved` ⇒ model). Each carries
  a hand-checked exact-value test (§9).

---

## 4. The frozen §3 output schema (inherited) + the reopen PATH

The generator MUST emit the schema + sub-structures named in §0; freezing the probe locked it as the
generator↔probe **schema contract** (`:88-93`).

**Reopen PATH (P2a, round 2 — it crosses a document boundary).** The §3 schema is frozen in
`PREREG_NARRATION_PROBE §3` (merged 2026-06-17). The generator **cannot unilaterally reopen it** — a
reopen is a **dated amendment to the PROBE pre-reg**, carrying the probe's own record re-segmentation
and, arguably, its own re-red-team. This generator pre-reg only *flags* the trigger; the probe owns the
contract. The probe's pre-freeze instruction to "settle any doubt the generator can cleanly emit the
buckets/vocab before freezing" (`:88-93`) is **discharged by design-judgment** (the schema has been
stable since rev-2 and is inspectable); the **Phase-1 emit-cleanliness gate is the empirical backstop,
and its failure mode IS exactly the probe-schema amendment above.**

**Phase-1 emit-cleanliness gate — predicate SHAPE pinned, ambiguity resolved (P2b, round 2).** Over
**≥N sample claims** (N in §10): **100% of emitted `mechanism_direction` vocab RESOLVES to the frozen
vocab set AND 100% of non-empty `headline_quantities` resolve to a frozen bucket.** Because the probe
enum is written `shortage|surplus|backlog_growth|…` with a trailing `…` that reads extensible, a
verbatim-only check would trip on legitimate-but-novel directions (e.g. `margin_compression`,
`substitution`) and force needless reopens. **"RESOLVES" therefore means: matches an explicit enum
member OR a pinned synonym/coercion map frozen ALONGSIDE this doc** (a design artifact, not a
build-time addition). The operator's choice at freeze (§10): adopt the coercion-map resolution
(recommended — does not touch the probe) OR close the probe enum (drop the `…` = a dated probe
amendment, the P2a path). Any **unresolved** miss = a schema-REOPEN escalation, never a build-time add.

---

## 5. C.5 — The blind freeze-gate yield band (gates the judgment-grade run)

**Band shape (frozen by stub:72-75; VALUES blind in §10):** **0 theses** = sources/corpus too thin →
**do NOT loosen the probe**, investigate the corpus; **small-n** = proceed; **large-n** =
**selectivity-flag** (investigate, don't bank). Dead themes get a graveyard, like edges (§8).

**Read over the cumulative N-floor; no re-roll channel (P2c, round 2).** The band is read over the
cumulative N-floor (§10). The generator is stochastic — a per-run "0" at the stub's ~1–5 claims/run is
routine sampling noise, **resolved by ACCUMULATING to the floor, never by re-rolling.** A re-run is
permitted **ONLY for infrastructure nondeterminism** (a transient failure that dropped everything
*before the verifier ran*); such re-runs **do not count toward N.** There is no
re-roll-until-the-count-looks-right channel — the one thing this document exists to forbid.

**"Band before yield" is STRUCTURAL (P3a-scoped, round 2).** Two things enforce it: (1) the band values
live in §10, written at the merge; (2) **any run that invokes the generator LLM (Phase 1+) runs against
FakeRouter / a pinned fixture corpus ONLY pre-freeze — never the live corpus** (a live-corpus run emits
the thesis count + `dropped_*` counts the band gates). The blinding boundary is precisely "invokes the
generator LLM": **Phase 0 (corpus-read + entity-resolution smoke, no LLM) emits no yield/`dropped_*`
count and is exempt** — it cannot un-blind a generator-yield band.

---

## 6. Build posture + the anti-HARK / §6 guardrails + sequencing

**Build offline NOW against fixtures (additive + INERT); HOLD the deploy.** Building plumbing against an
*already-frozen* schema is the opposite of HARK. Architecture (GenScope scoping): a new top-level
**`generator/`** package (parallel to `corpus/`/`council/`), reusing the council router + FakeRouter +
the quote-authenticity pattern; no migration.

**Guardrails:**
1. **Don't pin the §4 classifier bar here** (probe's); the §3 verifier shares no tunable with it.
2. **Don't tune the generator against probe / admission / gate outcomes** (the pair is §10.4-bound
   jointly, stub:60-65; the generator sees only dormancy flags, stub:62-65).
3. **Pre-freeze, any generator-LLM-invoking run (Phase 1+) is FIXTURE-only** (§5); Phase 0 (no LLM) is
   exempt.
4. **Write isolation:** the generator writes ONLY to `records/generator/` — `records/` co-houses BLIND
   artifacts the 7/10 review consumes (`gate_baserate_surfaced.csv`, the dated `*_closeout_*` /
   window-screen reads). A merge-blocker test asserts the generator never writes outside
   `records/generator/`; a **generator-specific** CI import-graph test (net-new) asserts the live path
   never imports `generator/`.

**Sequencing — the BINDING scarce resource is operator/red-team BANDWIDTH, not compute.** The build is
parallel-safe now (no compute/Bonferroni-k/paid-data; fixture-inert). The **FREEZE is NOT** — the §10
blind pins + final sign-off compete for the same operator attention as the **7/10 close-out**. **Rule:
the freeze does not begin until the 7/10 close-out is merged.** The DEPLOY (Phase 4) sits downstream of
the **§5 four-scan funnel read** (early-to-mid July) and **curation window #2** (`PREREG_UNIVERSE_
CURATION §3` — the next quarterly window after window #1, ~Sept estimate).

**Build phases (INERT; FakeRouter/fixtures throughout):** P0 corpus-read + entity-resolution smoke
(no LLM, fixture-exempt) · P1 pinned synthesis prompt + strict parser + the §4 emit-cleanliness gate ·
P2 the §3 citation verifier (deterministic, DROP, split counters) · P3 the `--generate` entry,
kill+cost gates before spend, writes only `records/generator/` · **P4 = HOLD** (deploy at the window).

---

## 7. (consolidated into §10) — the operator's blind calls

All operator-only picks are gathered in the §10 confirm-set so freezing = filling it.

---

## 8. Discipline companions

**Edge graveyard (`records/edge_graveyard.md`).** The 2026-06-21 fan-out killed **7/7 deterministic
edge candidates** on two pre-known graves (power: event-clustering → too few independent periods;
null≈signal/FSSD-redux), recorded with the grave each died on so a future fan-out does not re-derive
them. **Meta-finding: the deterministic-edge well is dry for this player — stop generating
event-conditioned harness edges; invest in the theme layer (this generator).**

**Survivors route forward, never backtested.** The same fan-out surfaced decorrelated *theme*
survivors (silver-deficit / seaborne-freight / pharma-reshoring). **They are recorded here ONLY as that
meta-finding's corollary; their admission is governed by `PREREG_UNIVERSE_CURATION`, not this doc.** As
curation-window candidates they are evaluated by the council→gate FORWARD apparatus (no Bonferroni-k);
they are a factor-diversification / 3B-null benefit, **NOT** a fix for the binding quietness constraint
(`under_narrated ∧ at_inflection`) — that is the generator's job. When curated, **weight under-
narration at the EXPRESSION level** (e.g. HL/AG/CDE's specific operating leverage), not decorrelation +
cap-fit.

---

## 9. Verification / acceptance

- Freezes on the operator's merge per the status line (7/10 close-out merged · §10 values written ·
  final sign-off).
- Build acceptance per phase: offline, no keys/network/loop-import, FakeRouter/fixture-defaulted, ruff
  clean; the split `dropped_*` counters each pinned to a hand-checked exact-value test (anti-HARK); a
  generator-specific CI import-graph keyless invariant (net-new); the `records/generator/`-only
  merge-blocker; doc-status-line as a per-PR merge gate.
- No judgment-grade yield reading banked before the §10 band is frozen; pre-freeze generator-LLM runs
  are fixture-only (Phase 0 exempt).
- No deploy before curation window #2; the build is subordinate to the 7/10 close-out and the §5 read.

---

## 10. CONFIRM-SET — FILLED at the freezing merge 2026-06-22 (operator-RATIFIED, pinned BLIND)

> Mirrors `PREREG_NARRATION_PROBE.md §9/§10`: the freezing merge is the act of writing these in, before
> any generator output is seen. The 7/10 close-out bandwidth blocker (status line + §6) is now CLEARED
> — `PREREG_COUNCIL_GATE_SEPARATION §5` frozen + L1 #72 live — so the operator filled these as the
> merge act. Each was pinned blind (no generator output seen). Deploy stays September-gated (§6); these
> values gate only the judgment-grade run, not the build (which was fixture-INERT throughout).

- **C.5 — expected per-run yield/rejection range:** **~[1 – 12] theses/run** *(operator-ratified)* —
  the proceed band; a per-run "0" is sampling noise, resolved by ACCUMULATING to the N-floor, never by
  re-rolling (§5).
- **C.5 — large-n selectivity-flag threshold (a number):** **>~25/run** *(operator-ratified)* — above
  this, selectivity-flag (investigate the corpus/prompt; do NOT bank the yield, do NOT loosen the
  probe).
- **C.5 — cumulative N-floor** (cf. the probe's ≥20): **20** *(operator-ratified)* — the cumulative
  count before "0% / degenerate" is actionable (mirrors the probe's ≥20).
- **C.3 — fact-level match rule + tolerance**, tied to the sparse-tolerant precedent (`:146-150`):
  **the sparse-tolerant precedent — a ±1-bucket (same-OOM) numeric trace WITHIN a family; failure =
  DROP** *(operator-ratified)*. An unfiled value is omitted (never fabricated/zeroed), so an
  absent-but-traceable figure is tolerated where the class allows.
- **C.3 — which source-classes are fact-MANDATORY vs fact-where-present** (entity-bearing /
  entity-free-macro / free-text-recipient): **fact-MANDATORY for the ENTITY-BEARING class**
  (`capital_raises` / `customer_concentration` / `etf_constituents`); **fact-WHERE-PRESENT for
  entity-free macro** (`bls` / `eia` / `nrc`) **and free-text recipient** (`federal_awards`)
  *(operator-ratified)*. **AND — by taxonomy-family (the e1 carve-out, ratified 2026-06-22):** the
  `dur_` / `x_` families are **WHERE-PRESENT even under an entity-bearing citation** (no traceable
  corpus magnitude → narrative-ungroundable → the §3 trace does not apply; the probe's narration
  scoring is their check); only `pct_` / `usd_` / `cnt_` stay fact-MANDATORY there. The ENTITY leg is
  mandatory regardless. Implemented in `generator/verify.py` (`FACT_MANDATORY_FAMILIES = {pct_, usd_,
  cnt_}`) + the `PREREG_NARRATION_PROBE §4` 2026-06-22 amendment.
- **C.2 — generator provider→role roster assignment** (council-distinct; OpenAI off contingency) — a
  one-way door: **OpenAI (off the council contingency) as the generator SYNTHESIZER**
  *(operator-ratified)*, a distinct provider→role assignment from the live council (gemini=proposer /
  xai=adversary / anthropic=strategist); exact-version-pinned via `runs.model_mix`.
- **C.2 — single-synthesis vs an additional LLM self-critique pass** (recommend single-synthesis):
  **single-synthesis** *(operator-ratified)* — the deterministic §3 verifier is the backstop; no extra
  LLM self-critique pass.
- **§4 — vocab-resolution choice:** the pinned synonym/coercion map (recommended, probe-untouching) OR
  close the probe enum (a dated probe amendment): **the coercion-map resolution** *(operator-ratified)*
  — probe-untouching (the map defaults EMPTY, an operator artifact; an unresolved miss is a
  schema-REOPEN, never a build-time add).
- **§4 — N in the Phase-1 emit-cleanliness sample** (predicate shape pinned in §4; N may stay blind):
  **~20** *(operator-ratified)*.
- **Stage-D — off-cycle deploy-warrant bar** (when an off-cycle generator deploy is warranted, vs
  waiting for curation window #2): **warranted iff a run yields ≥3 probe-passing QUIET theses, of which
  ≥2 are CAP-FITTABLE** (≤$1k/contract) *(operator-ratified)*. Below that bar, the generated theses
  wait for the next quarterly curation window (§6 / `PREREG_UNIVERSE_CURATION`).

C.1 (mechanism-claim unit) and C.4 (classifier bar) are confirm-only / out-of-scope (§0). The C.5
noise rule is a fixed rule in §5 (infrastructure-nondeterminism re-runs only), not a blind value.

**Split-counter EXEMPLARS — RATIFIED 2026-06-22.** The two hand-checked exact-value tests (§3 / §9,
anti-HARK) ship with the operator-ratified canonical exemplars: `dropped_entity_unresolved` via
**Aldermarsh/ALDP in no cited record** (confabulation), and `dropped_fact_untraced` via **Cameco/CCJ
asserting `pct_300plus` (400%) four buckets off the cited URNM `pct_10_25`** (an invented figure on a
real entity). See `tests/test_generator_verify.py` (`test_dropped_entity_unresolved_exact_value` /
`test_dropped_fact_untraced_exact_value`), and the e1 carve-out tests (`dur_`/`x_` where-present).

---

## 11. P2 verifier build notes (NON-freeze-gating — operator round-2 cautions, for the build)

These do NOT affect the §10 freeze; they are implementation cautions to honor when the §3 verifier is
built (Phase 2):

- **The entity leg is necessary-not-sufficient.** A model that OVER-cites (lists many corpus coords)
  can make most `named_entities` resolve, so the leg's discrimination is bounded by citation
  *relevance* — which is the **council's** axis (relevance-of-entity-to-mechanism), per the hard seam,
  NOT §3's job. Fine by design; but if `dropped_entity_unresolved` ever reads *suspiciously low*,
  over-citation is the thing to check.
- **A citation coord `(source, key, ts)` can map to MULTIPLE records.** `ts` is not unique within a
  key — e.g. `capital_raises` stamps filings at post-close 20:00 UTC, so same-day 424B5s collide on
  `(source, key, ts)`. Nail the coord→record resolution semantics in Phase 2 (the tie-break /
  set-membership rule); do NOT assume one-to-one.
- **Split-counter exemplars — RATIFIED 2026-06-22 (the as-built P2).** The two anti-HARK exact-value
  tests ship with the operator-ratified canonical exemplars (mirrored in §10): `entity_unresolved` via
  **ALDP in no cited record**; `fact_untraced` via **Cameco 400% → `pct_300plus`** off the cited URNM
  `pct_10_25`. The e1 carve-out (`dur_`/`x_` where-present even under a class-(a) citation) ships with
  its own KEPT tests (`generator/verify.py:FACT_MANDATORY_FAMILIES`). Coord→record resolution uses the
  ts-collision-aware `generator.entity._coord_records` (the caution above, discharged).
