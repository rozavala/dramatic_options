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
