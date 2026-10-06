# PROPOSAL — the `headline_quantities` bucket taxonomy (a probe §4 amendment)

**STATUS: PROPOSAL for operator review — NOT applied.** Completing the bucket taxonomy is a **probe
pre-reg amendment** (`PREREG_NARRATION_PROBE §4`), because the buckets are part of the FROZEN
generator↔probe schema contract (the schema-REOPEN routes through the probe doc, per
`PREREG_THEME_GENERATOR §4`). Dated 2026-06-22.

## The gap
`PREREG_NARRATION_PROBE §4` marks the `headline_quantities` buckets **FROZEN** but only names **three
by example**: `weeks_x2plus`, `usd_tens_of_billions`, `pct_25_50`. The taxonomy was never enumerated.
`GenBuild` honestly pinned exactly those three as `HEADLINE_BUCKETS` and flags anything else for
schema-reopen — so today the generator can only emit quantities that fall in those three bins; every
other real figure (a +180% growth, a $400M capex, a 30-week lead time) trips a reopen. This is a
*coverage* gap, not a synonym problem — so unlike the vocab enum (which the coercion-map resolves),
the buckets must be **enumerated**.

## Design principles
- **OOM-spaced magnitude bins per dimension-family.** The probe match rule is "±1 bucket / same-OOM"
  (`PREREG_NARRATION_PROBE §4`), so each bucket is an order-of-magnitude band; the tolerance is one
  adjacent bin. The metric string (e.g. "transformer lead time") carries the dimension context.
- **Buckets are UNSIGNED magnitude bins.** Direction (+/-) is already carried by
  `mechanism_direction.sign`, so a decline and a rise of the same magnitude share a bucket; the sign
  field disambiguates. (Avoids doubling the taxonomy.)
- **Five families** cover the headline quantities these theses circulate: percent, USD, duration,
  multiplier, count/capacity.

## Proposed taxonomy
| Family | Buckets (low→high) | Notes |
|---|---|---|
| **pct_** (rates/changes/share) | `pct_0_10` · `pct_10_25` · `pct_25_50` · `pct_50_100` · `pct_100_300` · `pct_300plus` | unsigned; sign from `mechanism_direction`. **`pct_25_50` = the frozen example.** |
| **usd_** ($ amounts) | `usd_millions` · `usd_tens_of_millions` · `usd_hundreds_of_millions` · `usd_billions` · `usd_tens_of_billions` · `usd_hundreds_of_billions_plus` | **`usd_tens_of_billions` = the frozen example.** |
| **dur_** (lead times / time-to-event) | `dur_weeks_lt10` · `dur_weeks_10_50` · `dur_weeks_50plus` · `dur_months_12_36` · `dur_years_3plus` | absolute durations |
| **x_** (multipliers, "N×") | `x_lt2` · `x_2plus` · `x_5plus` · `x_10plus` | **`weeks_x2plus` generalizes to `x_2plus`** (a 2×+ change); the metric carries "weeks". *See open choice (a).* |
| **cnt_** (counts / physical capacity: units, MW, GW, tons, reactors) | `cnt_lt100` · `cnt_100_10k` · `cnt_10k_1m` · `cnt_1m_plus` | generic OOM ladder; the metric carries the unit (least-precise family — open choice (b)) |

The three frozen examples map in: `pct_25_50` (direct), `usd_tens_of_billions` (direct),
`weeks_x2plus` → `x_2plus` (the multiplier reading; the absolute reading would be `dur_weeks_50plus`).

## Open choices for the operator (at the probe amendment)
- **(a) `weeks_x2plus`.** Keep it as a named bucket (preserve the frozen literal), or generalize to the
  `x_` multiplier family + `dur_` absolute family (recommended — more expressive, the literal becomes
  `x_2plus`). If you keep the literal, P2/P1 pin it as an alias.
- **(b) The `cnt_`/capacity family.** Worth including (nuclear MW, grid GW, tons), or fold physical
  capacity into pct/usd expressions and drop it? Recommend keep, flagged least-precise.
- **(c) Granularity.** Is six pct-bins / six usd-bins the right resolution for a "±1 bucket" tolerance,
  or coarser? (Coarser = more lenient matching in the probe's narration overlap.)
- **(d) Negative-direction buckets.** Confirm the unsigned-magnitude + sign-from-`mechanism_direction`
  design (vs. dedicated `pct_neg_*` buckets).

## How P2/P1 consume it
`generator/prompts.py:HEADLINE_BUCKETS` becomes this enumerated set; `generator/synthesize.py`'s
emit-cleanliness check resolves a non-empty quantity to one of these (else flags schema-REOPEN, never
auto-adds); P2's fact-level trace matches a claim's quantity bucket against the cited corpus record
within ±1 bucket. **P2 is being built against THIS proposed set** — if you amend it, P2's
`HEADLINE_BUCKETS` syncs (a one-line change), no structural rebuild.
