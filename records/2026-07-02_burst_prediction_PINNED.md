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
