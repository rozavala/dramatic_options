# PREREG DRAFT — Council repeat-read reliability probe (a dated note proposed for PREREG_COUNCIL_GATE_SEPARATION)

**Status: DRAFT — NOT FROZEN.** Issue #456 (M4). Written 2026-11-10, before the planned ~2026-11-12 model refresh
and before any probe run. Nothing reads this file and no code exists for it. The operator decides whether the
probe runs at all (it spends LLM budget and creates a new record), its two arms, its cost ceiling, and every value
marked **[PIN]**. **Numbers marked [PIN] are proposals.** On the operator's word it is appended to
`PREREG_COUNCIL_GATE_SEPARATION.md` as a new dated § after §10.11. Measurement only: the verdict of record, the
floor, the criteria, the prompts, the gates, sizing and every entry stay exactly as they are.

## 1. Why

Every entry so far reversed at the same name's next reads (`records/2026-11-04_council_two_week_look.md`;
`records/2026-11-09_persistence_watch_amendment.md`): HL #1816 and FLNC #1918 read LOW on all three next reads,
TITN's backfill reversed at #1952, and FLNC read above LOW on 1 of 11 reads of the same filing. Presentation
order was ruled out for FLNC and TITN. The persistence watch reads across nights, where evidence can drift. This
probe measures test-retest agreement **on the same night, on the same pack**, so drift is excluded by design.

## 2. What the code does today (verified)

- **The pack.** `council.council.propose` builds one `ContextPack` per candidate (`council.context.build_context_pack`,
  as of `clock.now()`), from the news, fundamentals, analyst-coverage and catalyst adapters, and passes it to
  `council.debate.run_candidate`. The rendered evidence is `ContextPack.as_prompt_block()`. The proposer's user text
  is that block (`agents.proposer_prompt`); the adversary's is the block plus the proposer's thesis
  (`agents.adversary_prompt`); the strategist's is the block plus a FOR block and an AGAINST block
  (`agents.strategist_prompt`). System prompts are the pinned constants (§10.11 shas).
- **Nothing persists the pack or the rendered text.** `council_proposals` stores the verdict and a `rationale` JSON;
  `council_agent_outputs.raw` stores each role's **parsed output** (migration 0005), not its prompt. Rebuilding the
  pack later by calling the adapters again is not guaranteed to reproduce it (the fundamentals corpus can refetch
  on a new filing, #340; the analyst meter reads a live endpoint). So **byte-identical replay needs a new capture**
  at L1 time (§4).
- **The strategist's inputs are recoverable once the pack is.** The FOR/AGAINST blocks read only
  `inflection_thesis`, `structural_vs_fad`, `confidence` (proposer) and `counter_case`, `weakest_point`,
  `already_consensus`, `is_fad`, `confidence` (adversary), all present in `council_agent_outputs.raw`.
- **The quote filter needs the pack object, not just its text.** `council.filters.apply_filter(…, pack, …)` builds
  its evidence pool from the pack's fields, so the capture must serialize the `ContextPack` (a frozen dataclass of
  strings, lists of dicts and one datetime).
- **Presentation order.** `run_candidate` draws `for_first = rng.random() < 0.5` and records
  `rationale["order"]`. The orchestrator calls `council_to_themes(…)` without `rng`, and `propose` passes `rng=None`
  down, so `run_candidate` uses an unseeded `random.Random()`. The order is random per call and recoverable only
  from the recorded `rationale["order"]`.
- **Sampling settings.** `council/router.py` sets no `temperature` on any provider ("each uses the SDK default …
  INTENTIONAL"). Roles today (`config.json:council.roles`): proposer `gemini/gemini-3.6-flash` with
  `thinking_level = minimal`, `json_mode = true`; adversary `xai/grok-4.3` (OpenAI-compatible, `json_mode`);
  strategist `anthropic/claude-opus-4-8` with `council.anthropic = {}` (no effort or max-tokens knobs; the router
  notes opus-4-8 runs without thinking when they are omitted). Understudy: strategist → `openai/gpt-5.2-2025-12-11`
  after the primary exhausts retries. UNVERIFIED: each provider's default temperature (set by the SDK, not here).
- **No response cache.** `Router.call` → `_attempt_loop` → `provider.complete` on every call; a repeat is a fresh draw.
- **Cost controls.** `council.cost_cap_usd = 5.0` is a **per-cycle** ceiling on one `CostLedger`
  (`build_router`); over it, `Router.call` raises `BudgetExceeded` and `propose` returns zero proposals.
  `council.monthly_spend_page_usd = {anthropic: 10, gemini: 10, xai: 10}` pages at 80% MTD, and MTD is
  `state.provider_month_spend`, which sums `council_agent_outputs.cost_usd` only.
- **Brier and persistence read `council_proposals`.** `state.resolve_proposal` writes `outcome`/`brier` there at
  close (via `monitor`); the persistence watch counts the next 3 `council_proposals` reads of the same name.

## 3. The probe [PIN throughout]

- **When.** After the L1's council of record has run and the L1 has finished (entries, null books, dual-read
  sweep), as a separate process. It reads only captured packs and the stored outputs. UNVERIFIED: `runs` has no
  completion column (migration 0001: `started_at, mode, equity, note`, plus later stamps), so "L1 finished" must
  be defined, e.g. the probe runs from a timer ordered after the L1 unit.
- **Names.** Every name whose pack was captured and that reached the LLM (grounded). Arm A also requires a
  strategist verdict of record; Arm B includes proposer abstentions (verdict of record = NEUTRAL drop).
- **k = 5 repeats per name per arm.**
- **Arm A — strategist only.** The captured pack, the stored proposer and adversary outputs, the recorded order,
  and the strategist system prompt; 5 strategist calls. Isolates the strategist's sampling variation.
- **Arm B — full debate.** The captured pack through `debate.run_candidate` 5 times, with an rng stub that forces
  the recorded order. Measures end-to-end variation, early exits included.
- **Post-processing identical to the record.** The same `apply_filter` and the same §10.7 tri-criteria coercion.
  The coercion is inline in `run_candidate`, so Arm A needs either a byte-neutral extraction of that block into a
  shared helper (with a lock-step test) or a pinned replica; the operator chooses.
- **Exclusions.** A repeat answered by the understudy model, or ending in `parse_error`, is excluded from
  agreement and counted. A name whose reconstructed `as_prompt_block()` hash differs from the captured hash is
  skipped and counted.
- **Length.** 10 L1 sessions with at least one probed name, then the probe stops itself: it counts its own
  sessions in its table and refuses an 11th, whatever the config flag says.
- **Segment.** It starts at the first L1 after the ~11-12 model refresh deploys (all roles, plus the #421 filter
  changes the operator tied to that boundary), and is one segment. If `runs.model_mix` (models, `prompts`,
  `quote_filter`) changes during the 10 sessions, the probe stops and reports the partial segment. Nothing pools
  across a stamp change.

## 4. The capture (precondition)

- At L1, for each candidate that reaches the LLM: the serialized `ContextPack`, the sha256 of each role's
  rendered user text, and the proposal id. Written by the council path behind `council.repeat_probe` (default
  off), fail-soft, with no change to any prompt byte (asserted by the existing prompt-pin tests).
- This is the only change to a loop module the probe needs. It adds a write; it never changes what a role sees.

## 5. Statistics

Per arm, per session and pooled over the segment, on raw and final (post-filter) convictions:
- **Per-criterion agreement.** For `structural_vs_fad = structural`, `under_narrated`, `at_inflection`: the share of
  the 5 repeats equal to the verdict of record, averaged over names.
- **Agreement on `include`** and on **"≥ floor"** (conviction ≥ `council.conviction_floor`, MODERATE), the same way.
- **Fleiss' kappa** per binary item, subjects = name-sessions, raters = the 5 repeats (the verdict of record
  excluded). Prevalence caveat printed: with ≥ floor near 0% of reads, kappa is unstable and raw agreement is
  inflated by the easy LOW names.
- **Majority match.** The share of names whose verdict of record equals the majority (≥ 3 of 5) of the repeats, per
  item, and for the conviction label itself (the verdict of record vs the modal label).
- **Floor-contact names.** Names whose verdict of record is ≥ floor, or with ≥ 1 of 5 repeats ≥ floor. The trigger
  is read on these only, because the LOW majority would otherwise dominate any agreement figure.

## 6. The pre-stated reading and trigger

- **Trigger [PIN].** Over the segment, in Arm A, if fewer than **70%** of floor-contact names have a verdict of
  record (≥ floor: yes/no) that equals the 5-repeat majority, a dated operator look at a **k-read entry rule** is
  owed. That look must also settle the persistence watch's open question (whether a carry waits for the next L1).
- **Evaluability.** The trigger needs ≥ **5** floor-contact names. Below that the probe reports "not evaluable"
  and triggers nothing; the persistence watch's own trigger stands.
- **One look, not two.** If the persistence watch's pinned trigger (fewer than half of the first 5 real entries
  persist) also fires, both are read in the same dated look. Neither trigger changes a rule.
- **Expectation, pinned blind [PIN].** From the records (FLNC above LOW on 1 of 11 same-filing reads; 0 of 2
  measurable entries persisted): most floor-contact names will be LOW of record with 1–2 of 5 repeats at
  MODERATE; Arm A majority match on ≥ floor among floor-contact names 40–80%; Arm B lower than Arm A.

## 7. Storage

A new table, `council_repeat_reads` (its own migration): run id, proposal id, arm, repeat index, role, provider,
model, parsed raw JSON, raw confidence, final conviction, `include`, the three criteria, `criteria_veto`, order,
pack hash, cost, timestamp. **Never `council_proposals` or `council_agent_outputs`.** So Brier
(`state.resolve_proposal`), `scoring.agent_contribution`, the persistence count and the forward record are
untouched. Consequence: `state.provider_month_spend` does not see probe spend (§8).

## 8. Cost

- **Real numbers in the records.** October council spend $4.78 (`records/2026-11-01_sunday_w44.md`), over ~22 L1
  sessions ≈ $0.22 per session. W45: L1 $1.37 for 11-02 → 11-06 ≈ $0.27 per session; cumulative L1 $19.60
  (`records/2026-11-08_sunday_w45.md`). 9–12 names reached the strategist per session (two-week look).
- **UNVERIFIED:** the per-role split. It is in `council_agent_outputs.cost_usd` (by `role`), not stated in any
  record. Also UNVERIFIED: the post-refresh models' cost per call; the ~11-03 shadow check measured it, but no
  record of its result exists.
- **Estimate.** Arm B ≈ 5 × a session ≈ $1.1–1.4 per session. Arm A ≤ 5 × the strategist's share of a session,
  so at most the same. Both arms: up to ~$2.7 per session, **up to ~$27 for the 10 sessions — about five to six
  times October's whole council spend.** The issue's "cost is small" understates it. Price notes: config prices
  `claude-opus-5-5` at $4/$20 per Mtok against opus-4-8's $5/$25, but the router notes opus-5-5's thinking cannot be
  disabled and counts as output, so per-call cost after the refresh may rise.
- **Caps [PIN].** The probe builds its own router and `CostLedger`: $3.00 per session, $30.00 for the segment;
  over either, it stops (fail-closed on the probe, never on the L1). Because the monthly page cannot see the
  probe, the probe refuses to start a session if council MTD + probe MTD + that session's estimate reaches 80% of
  any provider's `monthly_spend_page_usd`. The probe never shares the L1's ledger, so it cannot consume the L1's
  $5 cap.

## 9. What it must never be used for

Selecting, entering, sizing, holding or exiting any position; re-reading a position's verdict; replacing or
averaging the verdict of record; tuning a prompt, the floor or the criteria; DSPy or any training signal; Brier or
contribution scoring; any comparison with prices or outcomes (guardrail 6); surfacing names. A k-read entry rule,
if the look ever proposes one, is its own pre-registration.

## 10. Open decisions for the operator

1. Run the probe at all, at up to ~$27 over 10 sessions, or run Arm A only (about half), or k = 3.
2. Add the pack capture to the council path (§4), the only loop change the probe needs.
3. How Arm A reproduces the tri-criteria coercion: extract a shared helper or pin a replica.
4. The trigger (70% majority match among floor-contact names, ≥ 5 such names) and the blind expectation.
5. The caps ($3 per session, $30 total) and the 80%-of-page refusal rule.
