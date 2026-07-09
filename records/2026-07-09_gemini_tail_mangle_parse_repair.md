# 2026-07-09 — Gemini JSON-mode tail-mangling: a second parse-failure family, and the bounded bracket repair

## The finding

Three proposer parse-failures across three nights, all `gemini/gemini-3.5-flash`, all
`finish=STOP` (natural stop — NOT the #37 `MAX_TOKENS` thinking-starvation), all with the JSON
mangled at the very tail, immediately after the `evidence_cited` array:

| run | date | symbol | damage | recovered confidence |
|---|---|---|---|---|
| #458 | 2026-07-07 | RKLB | stray duplicate `]` before the final `}` | HIGH |
| #491 | 2026-07-09 | RKLB | final `}` dropped entirely | MODERATE |
| #491 | 2026-07-09 | AMSC | final `}` dropped entirely | HIGH |

Every night before 07-07 was clean (0 fails back through mid-June) — the abrupt onset suggests a
silent provider-side model update. The #37 apparatus worked exactly as designed: fail-closed to
NEUTRAL, full forensic raw persisted (which is what made this diagnosis and the replay test
possible), parse-health computed (2/12 = 17% < the 50% page threshold → `council_health=ok`).

## Why it matters beyond the rate

The censoring is **selective, not random**. Long, evidence-rich proposals carry long
`evidence_cited` arrays — exactly where the tail mangling strikes — and the replay shows all
three lost proposals were the proposer's *highest-conviction* outputs of those nights (MODERATE,
HIGH, HIGH — everything that parsed on those nights was ≤LOW or NEUTRAL). RKLB lost its proposer
judgment 2 of 3 nights running. A recovered ≥MODERATE proposer confidence does not mean the
candidate survives the strategist's tri-criteria — but the full adversary/strategist round-trip
never happened, and that biases the forward record against precisely the candidates the council
found most interesting.

## The fix (PR: `parse-tail-repair`)

`council/agents.py extract_json` gains one bounded, structural second chance (`_repair_tail`):

- **Bracket-level ONLY** — a string-aware scan; characters inside strings are never altered.
- **Bounded** — at most 3 stray closers dropped, at most 4 missing closers appended; anything
  beyond raises and the **original** error is re-raised (`raise err from None`), so forensics
  keep the true signature.
- **Fail-closed preserved** — a repaired object still flows through the #37 post-parse schema
  validation (`parse_proposer`/`parse_adversary`/`parse_strategist` required-key checks), so a
  bad repair fails closed exactly like a parse failure. This is parse *robustness*, not gate or
  mandate loosening — no floor, cap, or criterion moved.
- **Observable** — each successful repair logs a WARNING with the original error, so the
  underlying model-flakiness rate stays visible in the journal even as parse-health goes clean.

Tests: the two live damage shapes as fixtures, strings-with-brackets inviolate, valid JSON
byte-identical behavior, and the bounded-repair refusals (garbage, unterminated string, >3 stray
closers, >4 missing closers). All three REAL captured raw_texts replayed clean through the
repaired parser before merge. 850 tests green, ruff clean, no schema change.

## Watch

If the tail-mangling rate keeps climbing, the next lever is provider-side (a `gemini` point
release or a `response_schema` pin), not more parser leniency — the repair budget stays frozen
at 3-dropped/4-appended.
