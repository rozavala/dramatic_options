# PREREG DRAFT — Council repeat-read probe, Arm A only (#456; for PREREG_COUNCIL_GATE_SEPARATION §10.12)

**Status: DRAFT, NOT FROZEN.** Nothing reads this file and no code exists for it. It revises the 2026-11-10 draft
(`records/2026-11-10_council_repeat_probe_PREREG_DRAFT.md`, draft PR #476) after the operator's 2026-11-12 word put
"#456, the cheaper arm" first among the #476 drafts (`records/2026-11-12_operator_decisions_roadmap.md`). Values
marked **[PIN]** are proposals; §9 lists the decisions. On the word, it is appended to
`PREREG_COUNCIL_GATE_SEPARATION.md` as **§10.12** and indexed in `records/STANDING_STATE.md`.

**Measurement only.** The verdict of record, the floor, the criteria, the prompts, the gates, sizing and every entry
stay exactly as they are. Probe reads are never written to `council_proposals` or `council_agent_outputs`.

## 1. Why

Every real entry so far reversed at the same name's next reads: HL #1816 and FLNC #1918 read LOW on all three next
reads, TITN's backfill reversed at #1952, and FLNC read above LOW on 1 of 11 reads of the same filing
(`records/2026-11-04_council_two_week_look.md`, `records/2026-11-09_persistence_watch_amendment.md`).

On 11-13, RDW #13 filled after a carry, and that night's first read of RDW said `include=false`
(L1 #2055 grade). Two open questions now wait on how stable one read is:
- whether a backfill `include=false` read reverses an entry (STANDING_STATE: "decided at #456's look");
- whether a carry should wait for the next L1's read.

The persistence watch reads across nights, where the evidence can move. This probe re-reads **the same night, on
the same pack, with the same debate**. So it measures the strategist's own run-to-run variation and nothing else.

## 2. What changed from the 11-10 draft

- **Arm A only:** the strategist is re-asked on the stored proposer and adversary outputs. Arm B (the full debate
  re-run) is dropped, as the operator's "cheaper arm".
- **Cost measured, no longer estimated.** `council_agent_outputs`, 20 L1 sessions 2026-10-19 → 11-13, read-only:

| Role | Calls | Spend | Per session | Per call |
|---|---|---|---|---|
| proposer (gemini-3.6-flash) | 240 | $0.99 | $0.049 | $0.0041 |
| adversary (grok-4.3) | 202 | $0.49 | $0.025 | $0.0024 |
| strategist (claude-opus-4-8) | 202 | $3.67 | $0.184 | $0.0182 |

  About 10 names reach the strategist per session (8–12). At k repeats, Arm A costs about k × $0.18 per session:
  **k = 5 is $0.92 per session and about $9.20 for 10 sessions; k = 3 is $0.55 and $5.50.** The 11-10 draft's "up
  to $27" was both arms, on estimates.
- **The start date follows boundary B** (#470, worded 2026-11-12).
- **A second pre-stated read** on `include`, which the RDW question needs and which is evaluable every night (§6).

## 3. What the code does today (re-verified on `main`@`ed4b64f`)

- **The pack.** `council.council.propose` builds one `ContextPack` per candidate (`council/context.py:429`
  `build_context_pack`; the rendered evidence is `ContextPack.as_prompt_block()`, `:96`). The strategist's user text
  is the block plus a FOR block and an AGAINST block (`agents.strategist_prompt(pack, praw, araw, for_first=…)`,
  called at `council/debate.py:113`).
- **Nothing persists the pack.** Rebuilding it later is not guaranteed to match: the corpus refetches on a new filing
  (#340/#495), and the analyst meter reads a live endpoint. So a replay needs a capture at L1 time (§4).
- **The strategist's other inputs are stored.**
  - The proposer and adversary outputs are in `council_agent_outputs.raw` (parsed JSON).
  - The presentation order is in `council_proposals.rationale["order"]`. It is drawn unseeded per call
    (`debate.py:73,112`), so it must be read back, not redrawn.
  - Checked on proposal 1364 (LHX, 11-13).
- **Sampling.** `council/router.py:29–31`: no provider sets `temperature`, intentionally. A repeat is a fresh draw;
  there is no response cache.
- **Cost controls.**
  - `council.cost_cap_usd = 5.0` is per L1 cycle, on one `CostLedger`.
  - `council.monthly_spend_page_usd.anthropic = 10.0` pages at 80% month-to-date.
  - Month-to-date is `state.provider_month_spend`, which sums `council_agent_outputs.cost_usd` only.
  - November MTD anthropic is $1.96 after 10 sessions (L1 #2055 grade).
- **The L1 unit.** `TimeoutStartSec=30min`. The 11-13 L1 ran 20:45:01 → 20:51:48 UTC. `runs` has no completion
  column.

## 4. The probe [PIN throughout]

- **Capture (the only loop change).** Behind `council.repeat_probe` (default off), the council path writes, for each
  candidate that reaches the strategist: the serialized `ContextPack`, the sha256 of the strategist's rendered user
  text, and the proposal id.
  - Fail-soft: a capture error is a WARNING and never touches the council of record.
  - Prompt bytes are unchanged, asserted by the existing prompt-pin tests.
  - Per boundary B's exempt list it ships default-off. It is switched on at a boundary.
- **When.** A separate unit, `dramatic-options-repeat-probe`, starts after the L1 unit finishes (`After=` the L1, on
  its own timer). It never runs inside the L1 process: 10 names × k calls is several minutes, and a stalled probe
  call must never time out the L1 or fire its `OnFailure` page.
- **Names.** Every captured candidate with a strategist verdict of record. A proposer drop (NEUTRAL) never reached
  the strategist and is not probed.
- **Repeats.** k strategist calls per name **[PIN: k = 5]** on:
  - the rebuilt strategist prompt (captured pack, stored proposer and adversary outputs, recorded order);
  - the pinned system prompt;
  - the same model as the record (the strategist role in `config.json` at the time).
- **Post-processing identical to the record.** The same `apply_filter` and the same §10.7 tri-criteria coercion.
  The coercion is inline in `run_candidate`, so it is extracted into a shared helper with a lock-step test, byte
  for byte **[PIN: helper, not a replica]**.
- **Exclusions, counted.** A repeat answered by the understudy model (`openai/gpt-5.2`), or ending in
  `parse_error`, is left out of agreement. A name whose rebuilt prompt hash differs from the captured one is
  skipped.
- **Length.** **[PIN: 10 L1 sessions]** with at least one probed name, then the probe stops itself. It counts its
  sessions in its own table and refuses an 11th, whatever the flag says.
- **Segment.** **[PIN: starts at the Mon 2026-12-07 L1]** (boundary B). If the model refresh rides 12-07, the probe
  reads the new models; if not, the current ones. Either way it is one segment: if `runs.model_mix` changes during
  the 10 sessions, the probe stops and reports the partial segment. 12-07 → 12-18 is 10 sessions with no NYSE
  holiday.

## 5. Storage

A new table, `council_repeat_reads` (its own migration): run id, proposal id, symbol, repeat index, provider,
model, parsed raw JSON, raw confidence, final conviction, `include`, the three criteria, `criteria_veto`, order,
prompt hash, cost, timestamp. Captured packs go in `council_repeat_packs` (run id, proposal id, pack JSON, prompt
hash).

**Never `council_proposals` or `council_agent_outputs`.** So Brier (`state.resolve_proposal`),
`scoring.agent_contribution`, the persistence count and the forward record are untouched.

## 6. Statistics and the pre-stated reads

**Statistics.** Per session and pooled over the segment, on final (post-filter) convictions:
- for each of `structural_vs_fad = structural`, `under_narrated`, `at_inflection`, `include` and "≥ floor"
  (conviction ≥ MODERATE):
  - the share of the k repeats equal to the verdict of record, averaged over names;
  - **majority match:** whether the verdict of record equals the majority of the k repeats;
- Fleiss' kappa per binary item, with a prevalence caveat: "≥ floor" is rare (3 of 240 proposals since 10-19), so
  its kappa is unstable.

**Read 1, the entry read (the 11-10 trigger, kept) [PIN].**
- **Floor-contact names:** a verdict of record ≥ floor, or at least 1 of k repeats ≥ floor.
- **Trigger:** if fewer than **70%** of floor-contact names have a verdict of record (≥ floor yes/no) equal to the
  k-repeat majority, a dated operator look at a **k-read entry rule** is owed.
- **Evaluability:** ≥ **5** floor-contact names; otherwise "not evaluable" and no trigger.
- **Pre-stated risk:** at 3 above-floor verdicts in 20 sessions, most floor-contact names would have to come from
  repeats reaching MODERATE. "Not evaluable" is a likely outcome and is itself the answer that the floor is rarely
  in play.

**Read 2, the include read (new) [PIN].** Pooled over all probed name-sessions:
- the share whose `include` of record equals the k-repeat majority, and the share of names with any `include`
  disagreement among their k repeats;
- **pre-stated reading:** if majority match on `include` is below **80%**, a single `include=false` read is not
  treated as reversing an entry, and the RDW question, as STANDING_STATE routed it, is decided against counting a
  lone read;
- **evaluable** with at least 30 probed name-sessions (about 3 sessions).

**One look.** Both reads, and the persistence watch's own trigger if it fires, are read in one dated look after
the segment. That look also settles the carry-confirmation question (whether a carry waits for the next L1's read).
Nothing here changes a rule; any k-read rule is its own pre-registration.

**Blind expectation [PIN].** Most names are LOW of record and stay LOW. At floor contact, 1–2 of 5 repeats reach
MODERATE. Read 1 majority match is 40–80%, or not evaluable. Read 2 `include` majority match is 75–95%.

## 7. Cost caps [PIN]

- The probe builds its own router and `CostLedger`: **$1.50 per session, $15 for the segment** (k = 5). Over either,
  the probe stops; the L1 is never affected.
- **The monthly page must see the probe.** `state.provider_month_spend` adds `council_repeat_reads.cost_usd`, so the
  anthropic MTD includes the probe.
- **Arithmetic for December at k = 5.**
  - Council: ~$0.18 × 14 sessions to 12-18 ≈ $2.60. Probe: $9.20. MTD ≈ $11.80 by 12-18.
  - Against the current anthropic page (80% of $10 = $8), the page fires around the 7th probe session, and a probe
    that refuses at 80% stops there.
  - **Proposed:** raise `monthly_spend_page_usd.anthropic` to **$20** for December (a dated edit; the 80% line moves
    to $16), and keep the refusal rule: the probe refuses a session that would take anthropic MTD past 80%.
  - At k = 3 (MTD ≈ $8.10 by 12-18), the page would still fire near the end of the segment without the raise.
- The anthropic key is shared (the 2026-08-26 cap exhaustion), so the operator should know the console-side cap
  before approving.

## 8. What it must never be used for

- Selecting, entering, sizing, holding or exiting any position.
- Re-reading, replacing or averaging a verdict of record.
- Tuning a prompt, the floor or the criteria.
- DSPy or any training signal; Brier or contribution scoring.
- Any comparison with prices or outcomes (guardrail 6).
- Surfacing names.

## 9. Decisions for the operator

| # | Decision | Recommendation |
|---|---|---|
| 1 | Run Arm A at all | Yes |
| 2 | k | 5 (~$9.20 over the segment); k = 3 if the shared key's console cap is tight (~$5.50) |
| 3 | Start and length | Mon 2026-12-07 L1, 10 sessions (→ 12-18), stop on a `model_mix` change |
| 4 | The capture in the council path, default-off, switched on at 12-07 | Yes |
| 5 | Separate unit after the L1, not in-process | Yes |
| 6 | Tri-criteria coercion: shared helper with a lock-step test | Yes |
| 7 | Read 1 trigger (70% majority match, ≥ 5 floor-contact names) and Read 2 (80% `include` majority match, ≥ 30 name-sessions) | As drafted |
| 8 | Caps $1.50 per session and $15 total; probe spend counted in MTD; anthropic page $20 for December | As drafted |
| 9 | The look also decides the RDW `include=false` question and carry confirmation | Yes |

**After the word:** this file becomes §10.12 and gets a STANDING_STATE entry. The code follows as one full-ceremony
PR, behind the default-off flag, merged before the 12-07 boundary weekend:
- the capture;
- the probe unit and timer;
- two tables (migration);
- the shared coercion helper;
- the MTD change;
- a report script;
- tests with `FakeRouter`.

`frame_version` does not move, because the probe changes nothing the council sees.
