# 2026-10-16 — PROPOSAL: refresh the council's price markers at each L1 (for the F4 review; nothing adopted)

**Status: PROPOSAL for the operator. Nothing is built or switched on by this record.** Changing what the council
sees is a dated amendment that re-segments the record. CC's recommendation is to decide it **at the F4 review
(≈ 2026-11-04)**, not before (§5).

## 1. The problem

The council judges `at_inflection` (the criterion that binds; F4 evidence pack §2) partly on the sentinel's
price markers: 12-month momentum, relative strength, 3-month momentum, realized-vol slope. Those markers are the
ones persisted when the weekly L0 last surfaced the name. They are never recomputed at the daily L1, while news
and fundamentals refresh every L1. This asymmetry is already on record (PREREG_FRESH_INFLECTION_FUNNEL §7.1).

Ages at judgment (`markers_asof`): median 31.3 days and max 38.3 (NXE) on L1 #1678 (10-14); KKR's was 39 days on
L1 #1695 (10-15).

## 2. The pre-registered trigger does not fire, and this proposal does not claim it does

§7.1 deferred the L1 marker refresh with a pre-committed re-open trigger: re-open **iff** the cheapness watch
measures a cheap-entry window shorter than the staleness lag (a catch-the-entry-in-time question).
`dashboard_data.cheapness_watch_panel` reads **`hold`** today: 13 qualifying breaks over 108 observed days,
median cheap window 37 days against a 20-day lag. On that pre-registered ground the refresh is not needed.

This proposal rests on a **different ground**, and says so: the quality of the input to the binding judgment.
§7.1 judged staleness "mostly harmless" because stale-quiet ≈ still-quiet. The council's live failure is the other
case: **"the move has already happened"** is the most common rejection reason (70 of 118 since 09-24), and it is
read off markers that are weeks old.

## 3. Evidence: stale vs today, L1 #1695 (2026-10-15)

3-month momentum as the council saw it (persisted marker) vs the same measure recomputed tonight by the
cheapness watch (`cheapness_watch.mom_recent`):

| Name | Marker age (d) | 3m momentum, shown | 3m momentum, today | What the strategist leaned on |
|---|---|---|---|---|
| KKR | 39 | +0.16 | **−0.13** | "the positive signal is a 3-month momentum/RV reversal … tactical rotation" |
| FIG | 32 | +0.20 | **−0.04** | "modest 3m flip +0.200 … a corrective bounce" |
| TITN | 11 | +0.39 | +0.18 | "12m momentum is already +45.9%" (12-month; the 3-month halved) |
| HL | 25 | +0.19 | +0.08 | "sharply cooled 3-month momentum (+0.185 …)" |
| ERO | 32 | +0.28 | **+0.44** | "3m momentum decelerating to +0.281" |
| STUB | 18 | −0.56 | −0.37 | (abstained) |

The errors run both ways. KKR's and FIG's cited "reversal" or "bounce" has since gone. ERO's cited "deceleration"
has reversed into acceleration. CC does **not** claim any verdict would have flipped: each of these also failed on
fundamentals or narration. The claim is narrower. The binding criterion is being judged on numbers up to five
weeks old, and some of the specific numbers quoted in the rejections are no longer true.

## 4. The change, if adopted

- At each L1, recompute the price markers for every sentinel in the council union from the bars the L1 already
  pulls (the cheapness watch already recomputes the fresh leg; `discovery.compute_markers` is the function), and
  render those in the council pack with their as-of date.
- The L0-surfacing markers stay persisted unchanged (the funnel record, `sentinel_candidates.markers`).
- **Optional, CC's lean: show both.** "At surfacing (date)" next to "today": the move *since surfacing* is exactly
  what `at_inflection` asks about. The cost is one more line per marker in the pack.
- Stamp: `runs.model_mix.markers = l1_refresh_v1` (or `l1_refresh_both_v1`) from the first L1 after deploy.
  Never pool strategist Brier or the council-marginal read across it.
- Fail-soft: a name whose bars can't be pulled renders its persisted markers with their age, as today.
- Not touched: the gate, sizing, the risk frame, the prompts, the L0 funnel rank.

## 5. Timing: decide at F4, build behind a switch now

- The F4 window runs on one record segment (direction coherence, A2.1). Changing the pack at session 14 splits
  that read in half three weeks before it is owed.
- The change speaks directly to the F4 question as the evidence pack reframes it (`at_inflection` binds). It
  belongs on the review's table as a candidate remedy within the mandate, beside admissions.
- So: CC can build it **behind a config switch, default off** (byte-identical pack while off, a test pinning
  that), so that on 11-04 adopting it is one word and one config change, not a build.

## 6. What the operator decides

1. Build it behind the off switch now (no record change), yes or no.
2. At F4: adopt it, and if so, fresh-only or both.

## Addendum (2026-10-16, after the switch was built): the 12-month marker moves too

Running the switch's own code path read-only against live bars (scratch cache, nothing written) reproduces the
cheapness watch's 3-month values exactly (ERO +0.44, KKR −0.13, FIG −0.04, HL +0.09, TITN +0.19). It also shows
the **12-month** momentum, the number most "the move has already happened" rejections cite, has moved further:

| Name | 12m momentum, shown (surfacing date) | 12m momentum, 2026-10-16 | Price then → now |
|---|---|---|---|
| ERO | +1.218 (09-13) | **+0.370** | $35.47 → $34.75 |
| HL | +0.86 (09-20) | **+0.355** | $18.92 → $15.56 |
| KKR | −0.24 (09-06) | −0.226 | — |
| FIG | −0.53 (09-13) | −0.621 | — |
| TITN | +0.46 (10-04) | +0.521 | — |

The same function computed as of 2026-09-13 gives ERO +1.218, so the stored value was right for its date. Since
then the 12-month window has rolled past the base a year ago, with the price flat. ERO's council packs have
quoted "+1.218 12m momentum shows the large move has already happened" in all 14 sessions since 09-24; on
current bars the figure is +37%. As in §3, CC does not claim the verdict would flip (ERO's revenue print is also
eight months old), only that the binding judgment is quoting a number that is no longer true.
