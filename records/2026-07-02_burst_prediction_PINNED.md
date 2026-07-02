# 2026-07-02 — BLIND expected-vs-actual pin for tonight's L1 (19:45 UTC): the first post-relief null-book cycle

**Status: PINNED BEFORE OBSERVATION** (committed to main the morning of 2026-07-02; tonight's
L1 has not run). This is the calibration test of the whole 2026-07-01 diagnostic chain — slot
mechanism, cluster arithmetic, probe methodology — against reality running the same
computation. Actual result to be appended AFTER the run, graded against these bands.

## The correction made before observation (supersedes the probe's headline as a forecast)

The probe's "**16/29 WOULD BOOK**" (DIAGNOSIS §5) was a **capacity** measure: each name
evaluated independently against the book state as-of the probe (open premium $5,519). Tonight's
booking is **sequential** — each booking consumes book budget, and the frozen frame's book cap
(10% × $100k = $10,000) leaves only **$4,481** of headroom. Booked in union order
(`inflection_score` DESC) with greedy-to-cap sizing, the burst self-limits long before 16.
Walking the probe's own premiums sequentially (with cluster caps at $2,000 entry-premium):

| # | name | cluster | books | book remaining after |
|---|---|---|---|---|
| 1 | UUUU | nuclear | ~$944 (4×$236) | ~$3,537 |
| 2 | NXE | nuclear | ~$910 (7×$130) | ~$2,627 |
| 3 | HBM | copper ($1,138 headroom) | ~$940 (2×$470) | ~$1,687 |
| 4 | AG | silver | ~$948 (6×$158) | ~$739 |
| 5 | HL | silver | ~$678 (6×$113, book-remainder-clipped) | ~$61 |
| — | UEC/NNE | nuclear | **cluster_cap** ($146 left) | |
| — | everything cheap after | | **sizing** (book ~exhausted) or **cluster_cap** | |

## The pinned bands

- **HARD (mechanism falsifiers — a miss here reopens the diagnosis):**
  - `sentinel_slots` vetoes = **0** (the relief is live; any nonzero = deploy/config failure).
  - shadow `booked ≥ 1` (first booking since run 130).
- **Expected bands (quote-drift tolerated — iv_rv boundary names like NXE 1.16 can flip;
  premiums move overnight; the greedy path reorders on price changes):**
  - shadow **booked = 4–7** (modal 5; modal composition UUUU/NXE/HBM/AG/HL — nuclear/copper/
    silver first, by union rank), new premium ≈ **$4.0–4.5k** (book-cap-bound).
  - residual cheap names veto **`sizing`** (book exhausted) and **`cluster_cap`**;
    `not_cheap` ≈ 3–5 (NVDA/PWR/NOC/CDE class); UROY `no_structure`; `skip_open` = 7.
  - 3A (own book, similar ~$4.5k headroom, gate-OFF): **booked ≈ 3–7**; its big-premium names
    (RKLB $2,440 / VRT $5,025 / NVDA $1,455 / PWR / NOC $1,090) veto `sizing` at the $1,000
    per-name cap; CDE ($120, silver) books in 3A only (gate-off).
- **The new steady state (subsequent L1s):** shadow/3A log `booked=0` with **`sizing`-dominant
  vetoes** (book full at ~$10k) — HEALTHY and now visible via the veto-reasons line. The book
  cap replaces the slot cap as the binding constraint until closes free budget.

**Material deviation** (outside every band, esp. the HARD lines, or booked ≈ 16 — which would
mean the sequential-cap model itself is wrong) = **the diagnosis missed something; say so and
reopen** rather than explain post-hoc.

---

## Addendum (2026-07-02, pre-run — the advisor's P1/P2, pinned before observation)

**1. PAAS misses tonight — FORESEEN, not discovered.** The booker walks the union in
`inflection_score` DESC order, so the $4,481 is spent on the **highest-motion** cheap names
first; PAAS (union rank ~31) sits below the exhaustion point. **Composition-bias note:** the
control arm allocates its scarce budget by salience — the anti-quietness bias operating inside
the very instrument built to catch what salience-ranking starves. Vintage 2a is therefore not
just small but **skewed toward the least quiet of the cheap cohort.** AG/HL make the cut
(partial, not total).

**2. The relief RE-CENSORS tonight — pinned as a LIVE decision, not a discovery-in-waiting.**
By this record's own arithmetic the burst lands the shadow book at ~$9.9k of its $10k cap:
slots freed → **book cap binds tomorrow** → nothing resolves until ~Nov → the arm re-censors
one mechanism up. The §8(b) decision was scoped to slots; the book cap was not in that fork.
**The follow-on fork (decision owner: the OPERATOR; the advisor leans extend — a lean is not a
pin):**
- **(i) KEEP** — vintage 2 is a one-burst ~5-name cohort **by recorded design** (this
  addendum), not by silence.
- **(ii) BOOK-relief only (the advisor's lean)** — sequential arithmetic says this buys
  **~4 more names (FLY/FRO/RDW/TGB, ~$2.2k)** before the **CLUSTER caps** bind (nuclear full
  at UUUU+NXE; silver at AG+HL; copper at HBM+TGB) → the arm goes cluster-static, and **PAAS
  still misses (`cluster_cap`: silver $148 remaining < $315)**. The claim "if relief extends,
  everything cheap books" is **falsified by the cluster layer** — (ii) is a bounded
  half-measure, stated plainly before it is chosen.
- **(iii) BOOK+CLUSTER relief (per-name cap only)** — the full representative gate-passer
  sample (~16 names, ~$14k notional-premium, per-name $1k intact). This is what FBN §5's
  per-position p95 metric actually wants (a representative sample, not budget parity); it is
  also the largest departure from cap-parity and further segments the record.
- Under EVERY option, **PAAS's only channel is the #139 judgment reserve** — the null books
  cannot reach it while cluster caps stand (and cluster relief beyond (iii) was excluded by
  everyone).

**Sequencing pin:** tonight runs under the CURRENT regime regardless (the bands above stay
gradeable); any chosen relief deploys AFTER tonight's grade → vintage 2a (tonight's burst) /
vintage 2b (post-choice) are separable by `opened_at`. The anti-HARK cost of deciding tomorrow
instead of today is composition-knowledge only (outcomes stay blind until ~Nov); deciding
before the first resolution retains the essential blindness. Implementation staged
behavior-neutral (`null_book_fraction` / `null_cluster_fraction` knobs, default = inherit the
frozen frame): **the operator's config pin + amendment merge selects (i)/(ii)/(iii) — nothing
changes until they do.**

---

## Fork PICKED (2026-07-02, PRE-BURST; operator-delegated)

The operator delegated the choice explicitly ("go ahead with whatever you feel is correct").
**Pick: (iii)-COMPLETE — book + cluster + COUNT relief for the null books; the per-name cap
($1k) is RETAINED** (it is the per-position sizing normalizer the FBN §5 per-position metric
needs for comparability).

**Correction discovered during the pick, before observation:** `max_open_positions=15` is a
THIRD cap layer (`convexity_sizing.py:54` — a hard count check). Option (iii) as previously
written (book+cluster only) would still stop at 8 new bookings (15 total) and **still miss
PAAS** — the censoring recurses a third time (slots → book → count). The (iii) description
above is superseded; the full representative gate-passer sample requires all three reliefs. A
third behavior-neutral knob (`null_max_open_positions`, same inherit-by-default pattern +
tests) ships with this note.

**Activation (unchanged):** the three config keys are applied AFTER tonight's graded burst,
with the dated FBN §4 activation note. Tonight's bands above remain the graded prediction.
Post-activation expectation (pinned now): the remaining cheap union names book at the next L1
(~11 more incl. PAAS/CDE-if-cheap/UEC/NNE/CCJ/SMR/ERO/RDW/TGB/LUNR-class, per-name-capped),
after which the arm's binding constraint is the market (cheapness itself) — the intended
steady state for a control arm.
