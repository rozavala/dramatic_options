# Proposer model upgrade: gemini-3.5-flash → gemini-3.6-flash (2026-07-22)

**Authorization (operator, dated 2026-07-22, TRUE form):** "I would check if the switch makes
sense and if so, do it. it probably is a better model and cheaper"

**Segment note:** this is a RECORD-SEGMENTING event by design — `runs.model_mix` stamps the
proposer model per run, so the council-marginal / Brier / agent-contribution reads segment at
the first live 3.6 cycle (expected L1 2026-07-23). No backfill, no censoring: the 3.5-flash
segment (runs #37→#646-era) stands as-is; comparisons across the seam are labeled, never pooled.

## Why

1. **The JSON-mangle family lives on gemini-3.5-flash.** Sustained ~1–3 bracket tail-mangles
   per L1 night (07-15→07-22) plus one hard invalid-`\'` escape fail (run #612, NVDA) — all
   absorbed losslessly by the bounded repair layer (PRs from 07-09 + #210), but the rate is
   elevated vs the pre-07-07 zero baseline. This upgrade is the provider-side lever, pulled
   deliberately (not forced by a hard failure).
2. **Cheaper:** $1.50/$7.50 per Mtok vs $1.50/$9.00 (out −17%), and Google claims ~17% fewer
   output tokens for the same work; the probe measured −25% output tokens on our prompt.
3. Released 2026-07-21 (verified live on our key via models.list the same week: the name
   `gemini-3.6-flash` resolves; no dated snapshot variants exist — the family name is the
   tightest available pin; we never use `-latest` aliases).

## The pre-switch probe (ephemeral, scratchpad; parse/knob/cost evidence ONLY — §6 leash:
## synthetic packs, NO judgment-quality claim; judgment is forward-scored in the new segment)

Real router path (`build_router` → GeminiProvider: `thinking_level=minimal`, `json_mode=true`,
`max_tokens=2048`) + the real sha-pinned proposer prompt over 6 synthetic context packs
(`synthetic_context_pack`, the FakeRouter fixture shape). Raw parse = balanced-scan WITHOUT
the repair layer (the raw mangle signal); schema = `parse_proposer` clean.

| arm | raw mangles | schema fails | finish | thoughts | avg out tok | cost (6 calls) |
|---|---|---|---|---|---|---|
| gemini-3.5-flash (control) | **1/6** (KMT, `unbalanced JSON object` — the live family, reproduced in-probe) | 0/6 (repair caught it) | STOP ×6 | None ×6 | 209 | $0.0150 |
| gemini-3.6-flash | **0/6** | 0/6 | STOP ×6 | None ×6 | 157 (−25%) | $0.0108 (−28%) |

Knob compatibility confirmed: 3.6 accepts the 3.x `thinking_level` API (no `thinking_budget`
regression), honors `response_mime_type=application/json`, natural STOPs, no thinking-token
starvation (the #37 class).

## The change

- `config.json`: `council.roles.proposer.model` → `gemini-3.6-flash`; `prices_per_mtok` gains
  `gemini-3.6-flash {in: 1.5, out: 7.5}` (the 3.5-flash entry is KEPT — ledger accuracy on
  rollback, per the config comment's own rule).
- Nothing else: prompts byte-identical (sha-pinned), knobs unchanged, repair layer stays
  (it is model-agnostic armor, not 3.5-specific).
- Rollback = revert the one config line (the old price entry never left).

## Post-switch watch (first 3.6 segment nights)

- The `@pytest.mark.live` acceptance test re-run on-host after deploy (its docstring names
  "a model bump" as its trigger).
- Repair-rate by night (expect ~0; any recurrence is a NEW datum against the 3.6 segment).
- Conviction-distribution continuity is NOT expected (new segment; the 3.5 segment's
  1→4→7 LOW-widening trend does not carry a baseline across the seam).
- Cost ledger per cycle (expect proposer leg ≈ −25–30%).
