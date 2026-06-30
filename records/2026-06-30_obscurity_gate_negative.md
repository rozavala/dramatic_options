# The obscurity-gate prototype — a clean NULL (the inverted pipeline's core mechanism fails)

**Date:** 2026-06-30 · **Status:** measured negative. The most promising forward lead from the
list-thread (the "Inverted Pipeline" — let microstructure surface candidates, then apply judgment)
was prototyped READ-ONLY and **collapsed**. This closes the lead on measurement, not argument.

## What was tested (seam-clean, read-only)
A mechanical **obscurity gate**: over a BROAD optionable universe (not the curated themes), select on
`feasibility ∩ obscurity ∩ motion` — **no cheapness at the input** (§2/CGS §7 held throughout;
survivors were never treated as admits). Instruments verified to exist: `data/news.py
.headlines_asof` works for arbitrary tickers (the frozen `QUIET_NEWS_CUT=3` reused); the universe via
`AlpacaClient.get_all_assets()` (6,134 optionable equities); feasibility via
`probe_basket_feasibility`; motion via `discovery.compute_markers`.

## The funnel (cheap-first)
| Stage | Filter | Survivors |
|---|---|---|
| Universe | optionable + tradable US equities | 6,134 |
| Price | spot < $50 | 3,901 |
| (sample) | random 800 (per-symbol news = the API bottleneck) | 800 |
| **Obscurity** | trailing-90d news ≤ 3 | 333 |
| **Motion** | `discovery.clears_gate` | 218 |
| (equity filter) | exclude funds/ETPs | **47 (78% of motion survivors were funds/ETPs)** |
| **Feasibility** | 15–35% OTM, 180–365d, ≤ $1k, OPRA | **7 cap-fit, 0 in a real OTM band → 0 tradeable** |

## Why it collapses — three structural failure modes
1. **The broad optionable universe is dominated by FUNDS.** quietness (no per-ticker news) + motion
   (leverage) preferentially select leveraged/inverse single-stock ETFs and crypto/index ETPs — 78%
   of motion survivors. The obscurity signal is **anti-discriminating**: it rewards exactly the
   instruments that have no thesis.
2. **Obscurity ⊥ liquidity.** Genuinely-quiet companies are quiet largely *because* they are small/
   illiquid → they fail the ADV floor; the few liquid "quiet" names are large foreign ADRs (IBN, NMR,
   GLNG) "quiet" only as a US-newswire artifact, not genuine under-narration.
3. **Feasibility is the hard wall.** Even the liquid survivors have coarse, low-priced chains that
   cannot express a far-OTM 6–12mo structure under the cap — the same constraint that gates the
   curated universe, biting *harder* on quiet small-caps.

## Conclusion
**Mechanical direct-narration obscurity is NOT an independent edge over thematic brainstorming.** It
surfaces a *different, untradeable* population (illiquid micro-caps + ETF noise), which the
feasibility/liquidity floor then rejects wholesale → yield ~0, mirroring the §10.8 SCARCITY finding
and the curation-exhaustion conclusion (~75 names, 6 lists, zero admits). **The anti-quietness funnel
redesign's core mechanism fails in prototype → de-prioritize the funnel redesign.** The would-be
fixes (a name-based fund exclusion + an ADV pre-floor; redefining "obscurity" as *under-narrated
relative to fundamentals* via the §9 corpus rather than absolutely-quiet) are recorded, but on this
universe the liquidity/feasibility floor caps the yield at ~0 regardless.

## Lineage (feed this into future fan-outs so it isn't re-derived)
The **4th idea-supply negative**, after the autonomous-corpus generator (2026-06-23), the
seeded-source / financing-event surface (2026-06-28), and the divergence/FSSD edge graves. The
durable principle holds: a tradeable name must be **quiet ∧ feasible ∧ fresh** simultaneously, and
that intersection is structurally near-empty + market-timed — no mechanical filter (corpus, seeded,
or microstructure-obscurity) manufactures it. **WATCH is the measured equilibrium.**
