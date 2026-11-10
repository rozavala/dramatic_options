# 2026-11-10 — Roadmap protocol drafts: index and the decisions owed

> **Status: an index of DRAFTS. Nothing here or in the nine files it lists is in force.** Each draft was written
> for one issue under tracker #452, by a drafting agent, and checked by the main session against the code and the
> records. Merging these files ratifies nothing (PREREG_THEMATIC_CONVEXITY §6 ownership addendum: merge-as-
> ratification is a named failure mode). The operator rules on each draft separately; the code for an item is
> written only after its word. No existing file is changed by this PR.

## The nine drafts

| Issue | Draft | The first decision it asks for |
|---|---|---|
| #465 R1 | `2026-11-10_kill_rule_dry_leg_conformance_DRAFT.md` | Clock start A (first real fill, binds 2027-04-01) or B (go-live, binds 2027-03-02); payoff = a realized profitable close |
| #460 C1 | `2026-11-10_calibration_v3_amendment_DRAFT.md` | Freeze the four cells and rules P, T2, A, X as written, change a pin, or strike a cell |
| #456 M4 | `2026-11-10_council_repeat_probe_PREREG_DRAFT.md` | Run the probe at up to ~$27 over 10 sessions, a cheaper arm, or not at all |
| #453 M1 | `2026-11-10_layer_scoreboard_PREREG_DRAFT.md` | Adopt a daily mark snapshot (no mark history exists today), and whether the build is worth it |
| #455 M3 | `2026-11-10_cheap_then_repriced_PREREG_DRAFT.md` | Where the weekly writer runs, and its horizons (4 and 13 weekly sweeps) |
| #470 G1 | `2026-11-10_scheduled_change_boundary_DRAFT.md` | A monthly boundary (first Monday L1), starting 2026-12-07 |
| #468 R4 | `2026-11-10_t4_go_no_go_checklist_DRAFT.md` | Numbers for T4 conditions (2) and (4); the PROD rehearsal settings |
| #462 X2 | `2026-11-10_convexity_regime_series_DRAFT.md` | A fixed reference set of names vs the live universe |
| #464 P1 | `2026-11-10_held_name_thesis_tracking_DRAFT.md` | Option B: a separate post-entry pass in its own table |

Each draft ends with its full list of decisions.

## Where a draft corrected its issue
The drafting agents read the code, and several premises in the issues filed the same morning were wrong. The
drafts are written to the corrected facts; the main session verified each correction at the cited code.

- **#453:** marks are overwritten (`state.mark_*_position` is an UPDATE), so no mark history exists and an interim
  read needs a new daily capture first. The books enter names independently (`skip_open` in `shadow_book` and
  `fixed_basket`), so "paired" cannot mean the same entry. The null books' first resolutions are about 2026-12-25
  with the expiry wall on 2027-01-15 (`records/2026-07-14_min_n_pins_RATIFIED.md`), not mid-2027.
- **#455:** the issue said the outcomes come "all from data we already store". The selected contract's mid and IV
  are stored nowhere (`gate_dualread` keeps `iv_rv`, `otm_skew`, `cheap` and the wing's symbol), so the ledger
  needs its own weekly capture.
- **#456:** the issue called the cost small. The estimate is up to ~$27 over 10 sessions, five to six times
  October's $4.78 council spend, and `provider_month_spend` would not see it. The pack is never persisted, so a
  same-pack replay needs a capture step, the only change to the council path.
- **#462:** `dashboard_data.market_context` pools every `convexity_eval` row ever written (names the council sent
  to the gates), not the universe on the latest run.
- **#464:** a held lineage cannot be kept alive on the slate: `run_discover` excludes open-position symbols
  (`orchestrator.py`, the `exclude` set), so its `last_seen_at` freezes and it goes dormant within 35 days.
- **#465:** a kill-rule trip also stops the shadow, 3A, 3B and shares books, the council build and the L0 scan
  (each calls `kill_rule_status(...).tripped`), so "the null books are unaffected" is not what the wiring does.
  `records/2026-07-04_first_real_entry_ERRATUM.md` §4 says the 9-month clock is live; it has never been in code.
- **#470:** the issue's table listed 8 of 12 stamp moves and dated `quote_filter` at the word (10-24), not the
  first stamped L1 (10-26, #1816).

## The main session's own review notes
- **Calibration v3, Rule T2 part (i) is not blind.** v2 already published the 540-day unconditional mean M at
  μ = 10% and 25% (all above 1.0). A disclosure is added inside the draft; part (ii) is the deciding half.
- **Commit trailers on the draft commits name Claude Opus 5.5:** the drafting agents ran on that model.

## Issues filed from what the drafts found
- **#471** — backfill: a held name can take one of the 3 candidate slots and is then skipped at the gate.
- **#472** — kill rule: the 20% drawdown leg counts only open positions; a realized loss leaves the figure when
  the position closes. With #465, neither frozen leg responds to realized bleed.
- **#473** — live broker: the per-order notional ceiling also rejects closes, so a 10× profit-take could never be
  sold under a ceiling near the per-name cap.

## Not drafted in this pass
- #457 (gate graduation), #459 (cheapness-first discovery), #461 (ITM sleeve), #469 (capital ladder): each waits
  on evidence from #454, #455, #453 or #468.
- #463, #466, #467: need DEV, market hours or the operator's go.
