# 2026-07-06 — the CDE2 adjusted-class defect: one bad 3A row, the guard it bought, the void

**What paged:** `Fixed-basket 3A mark failed (non-fatal): {"message":"invalid underlying
symbol: CDE2"}` — every L2 cycle from 20:00 UTC (the first monitor pass after tonight's
vintage-2b burst) until the timers' daily window closed.

**Root cause (verified):** tonight's 3A booking selected `CDE2270115P00012000` — an
**OCC corporate-action-ADJUSTED class** (root `CDE2` ≠ ticker `CDE`). Adjusted classes carry
non-standard deliverables — a *different payoff object* (calibration finding #3's category),
which the gate/sizing math silently misprices — and the L2 quote path rejects the root as an
underlying, so the row could never be marked (and at exit would have stranded). Nothing in
`select_structure` excluded adjusted roots; the class was selectable in EVERY book including
the real one. 3B's standard-rooted CDE call (id 34) is unaffected and marks fine.

**Fixes (this PR):**
1. `structure.occ_root()` + an `underlying_symbol` filter in `select_structure` — a contract
   whose root ≠ the ticker is never selectable. Threaded through **all seven** library call
   sites: the REAL book (`paper_loop`), shadow, 3A, 3B, shares, the cheapness watch, and the
   dual-read arm.
2. **Per-position mark fail-soft** in all three monitors (real / shadow / fixed-basket): one
   unquotable row logs a WARNING and is skipped; the pass tail survives; the batch-level page
   fires only on genuine batch failures (ends the 16-pages/day storm this would have produced).

**The defective row (id 55, `union_nogate`) is VOIDED** — `status='voided'`,
`exit_reason='adjusted_class_selection_defect'` — a data-maintenance action on a SIMULATED
book, documented here before execution: the row was booked on a mis-specified instrument by a
selection defect, was never markable, and would contaminate the per-position tail with a
non-standard deliverable. It is excluded from every read (reads filter `open`/`closed`); its
attempt-telemetry row (booked, #37-walk) stays — history is not rewritten, the position is
retired as defective. 3A therefore holds CDE **not at all** in vintage 2b (the standard-rooted
put was second-nearest; the guard will let the booker re-book CDE cleanly at the next cycle
if it still qualifies).

**Real-book relevance, stated plainly:** without this guard, a future real include whose
nearest-to-target wing happened to be an adjusted class would have produced a REAL order on a
non-standard deliverable. The null book found the landmine first — the control arms doing
exactly their job.

---

## 2026-07-07 residual — the gate's ATM estimator was the remaining unfiltered chain reader

**Found by the dual-read flip wire, not by chance:** the 19:45 UTC L1 (#458) post-entries sweep
paged `material cheap-flip` on CDE — OPRA read iv_rv **4.0005** / otm_skew **−222.4vp**
(cheap=0) while INDICATIVE read **0.9756** / **−1.4vp** (cheap=1) on the same wing
(`CDE270115C00020000`). Live chain forensics (after close, quotes present, roots inspectable):
the CDE chain carries **three OCC roots — CDE (536), CDE2 (160), CDE1 (14)** — and at the wing
expiry the nearest-the-money call to the 16.04 spot is **`CDE1270115C00017000` iv=2.7433
(274%)**, an adjusted class, vs the standard `CDE270115C00015000` iv=0.7014. `convexity_gate.
atm_iv()` scanned the raw chain (no root filter), so the OPRA arm's ATM-of-record was the CDE1
garbage IV: 2.7433/RV 0.686 = **iv_rv 4.0005 exactly**, skew (0.52−2.74)×100 ≈ **−222vp
exactly**. The INDICATIVE feed carried no IV for that contract → its nearest-with-IV was the
standard class → the clean 0.976 read → the disagreement → the page. (#160 guarded
`select_structure`; the ATM estimator reads the chain independently and was missed.)

**Pollution is bidirectional and touched a second surface:** the same run's cheapness-watch row
for CDE (put side, spot 16.04) read **iv_rv 0.403 / atm_iv 0.2946** against RV 0.73 — an
adjusted-class put with an implausibly LOW IV won the nearest-the-money scan, halving the
recorded iv_rv. That row feeds `state.gate_cheap_reads` = the reserve's §4 ranking substrate
(CDE stayed out of the reserve pool only because the +40.8vp skew leg — itself an artifact of
the same polluted ATM — read cheap=0). Both directions happened to fail closed here; neither is
guaranteed to (a mid-range polluted ATM could pass both legs).

**Fix (same-night, the #160 idiom):** `occ_root` moved into `convexity_gate` (import direction;
`structure` re-exports it) and `atm_iv()` gains a `root` filter, threaded by
`is_cheap_convexity` as the WING's own OCC class — zero call-site changes, so every consumer
(real gate `paper_loop`, shadow, dual-read sweep, cheapness watch, probe scripts) inherits the
clean read. Regression tests pin the live-confirmed numbers (unfiltered read reproduces 2.7433;
filtered reads 0.7014 / iv_rv 1.023 / skew −18.2vp). 846 tests.

**Verification watch (post-deploy):** the next sweeps (Wed 07-08 L2/L1) should show CDE's two
arms re-agreeing near iv_rv ≈ 0.98–1.0 and the flip wire quiet; the cheapness-watch CDE row
should read atm_iv ≈ 0.70-class, not 0.29. **Bearing on the 2026-07-10 dual-read lapse:
none against lapsing** — this flip class was a code artifact one arm happened to expose, not
feed-quality divergence; the wire's job here (surface a bad read before anything trades on it)
is exactly what it did, and the guard now removes the class at the source.

## 2026-07-08 verification — CONFIRMED at L1 #475 (watch CLOSED)

Both predictions landed exactly. **Dual-read CDE:** opra iv_rv **0.9787** / indicative
**0.9711**, both cheap=1 on the same standard-class wing `CDE270115C00020000`, skews
−0.29/−0.01vp — arms re-agreeing, flip wire quiet, no page. **Cheapness-watch CDE:** contract
`CDE270115P00012500`, **atm_iv 0.708** (vs 0.2946 polluted at #458 / 0.2704 CDE2-selected at
#441), iv_rv 0.969, cheap=1 — the 0.70-class read the regression fixture pinned.

**Consequence, not just quiet:** with the true read, the CDE Jan-27 12.5 put entered the
brain-off shadow book same-run (6 × $152.50, origin=sentinel) — pre-fix, the polluted ATM had
been silently gate-blocking CDE from the null books. The three-run cheapness-watch progression
(0.372 CDE2-contract → 0.403 polluted-ATM → 0.969 clean) is the defect's full arc on one
surface. **2026-07-10 lapse bearing unchanged: LET IT LAPSE.**

Logged for completeness (unrelated class): VRT's first-ever boundary straddle — opra 1.2004
(cheap=0) vs indicative 1.1865 (cheap=1), |Δ|=0.014 at the 1.2 threshold, first flip in its
last 5 runs. OPRA-is-record disposes (not cheap → no entry either book); the rolling-5
materiality wire owns recurrence.
