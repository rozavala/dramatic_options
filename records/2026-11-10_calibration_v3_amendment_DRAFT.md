# 2026-11-10 — Calibration v3 amendment DRAFT (puts, tenor fallback, add-to-winners, re-strike)

> **Status: DRAFT, not frozen. Issue #460.** Written blind: no v3 code exists, no harness was run, and no
> payoff number was computed for this draft. The only numbers quoted are v2's published results
> (`records/2026-11-03_calibration_v2_finding.md`) and the live config values.
> Every proposed number is marked `[PIN]`. Each `[PIN]` stands as written unless the operator changes it.
>
> **What the operator decides:** (1) freeze the block below verbatim into `PREREG_CONVEXITY_CALIBRATION.md`
> §4, inserted after the 2026-11-03 v2 FINDING, with `XX` replaced by the freeze date; (2) change any `[PIN]`
> before freezing; or (3) strike a cell (strike it whole, never only its rule). Freezing comes before any v3
> code (`calibration/v3.py`, the engine additions named per cell). The commit that freezes it is the blind
> anchor the finding cites, as `51d9b7d` was for v2.
>
> Payoff mechanics only (PREREG §1, the three walls). Nothing here is an edge claim. No cell changes a live
> parameter, and no cell moves the gate, the risk frame or §6a.

---

## Proposed text (paste verbatim on the operator's word)

**Amendment 2026-11-XX — calibration v3: puts, tenor fallback, add-to-winners, re-strike at the time stop
(written BLIND, committed before any v3 code or number exists).** Motivation: issue #460 and v2's reading 5
(Rule T did not answer the fallback question). Every cell answers a *structure* question. None is an edge
claim, and none changes a live parameter. A cell that meets its rule earns only the right to **DRAFT** a
live amendment, and that draft still needs the operator's word.

*Common settings (v2's, unchanged unless stated):* σ_entry = 1.0 × σ_real, σ_real = 50%, r = 4%. The live
exit is the 10× profit-take backstop OR the time stop at 21 DTE, else expiry; it runs per leg on that leg's
own entry premium. Round-trip cost is 5% of premium on every close (none on a worthless expiry). Seed 7,
5,000 paths per cell `[PIN]`. Both path models run: GBM and Merton (λ = 2/yr, log-jump N(0, 0.20),
variance-matched, drift-compensated). Paths are **paired**: the same seed gives the same price paths and
the same thesis and falsifier draws in every cell being compared. **Two changes from v2, and why.**
(a) Cells 3 and 4 hold a leg past day 270, so their paths are simulated for `path_days` longer than the
first contract's tenor. Every comparator in those cells runs on the same extended paths and ignores the
days after its own expiry. (b) The new confirmation reads (cells 3 and 4) are drawn from a **second RNG
stream** (`default_rng([seed, 1])`), so the v1 and v2 draw order is untouched. **Reproducibility check:**
the v3 suite re-runs v2's GBM hold cell and must reproduce mean M 1.22, p99 14.4 and p* 0.1867 exactly,
or the run is void.

*Thesis-state p\* with variable capital (cells 3 and 4, and the single-leg cells as a special case).* Take
one tranche premium P₁ as the unit. Per path, Π = (total exit value − total deployed)/P₁. Then
E[Π] = p·E_r[Π] + (1 − p)·E_w[Π], and p* = −E_w[Π]/(E_r[Π] − E_w[Π]). With one leg this reduces to v2's
(1 − E_w)/(E_r − E_w). A cell's "mean M" is the ratio of means E[value]/E[deployed], the book view.

1. **Puts (`kind = "P"`).** The live cell mirrored: put, 15/25/40% OTM `[PIN]`, 270 d. The long leg is
   priced and marked at σ_entry + s, with s ∈ {0, +5, +10} vol pts `[PIN]`. Equity downside wings are
   priced rich, and s = +10 is the live skew gate's edge (`otm_skew_max_volpts = 10`).
   *Drift:* the rule uses `ThesisModel`, with μ_right ∈ {−40%, −80%} `[PIN]` and μ_wrong = +10% `[PIN]`,
   each the sign mirror of v2's call grid. Mirroring μ makes E[S_T]/S₀ exactly the reciprocal of the call
   cell's, so the thesis move matches in expectation. We chose this over a plain μ sweep because it gives
   the exact p* (a sweep only gives the M > 1 proxy) and it is the form Rule S used. A μ sweep
   {0, −10%, −25%} `[PIN]` is reported alongside as description only.
   *Matched call cell:* call, 25% OTM, 270 d, s = 0, μ_right ∈ {+40%, +80%}, μ_wrong = −10%, on the same
   paired draws.
   *Reported per cell:* mean M, p99, P(M ≥ 1), E_r, E_w, p*. Also the put's **hard cap**: the stock cannot
   go below zero, so M_max = (K − cost)/premium. This is computed analytically and printed beside p99.
   Where M_max < 10, the 10× backstop can never fire, and the report says so.
   **Rule P:** a **dated operator look at the bearish sleeve** opens iff, at 25% OTM and s = +5, under
   **both** path models and **both** μ_right, p*(put) − p*(call) > 5 pp `[PIN]`. The look covers whether
   bearish theses keep the call sleeve's admission and sizing. Otherwise the result is "no put penalty at
   this bar", reported and closed. Either verdict also reports p*(put) − p*(call) at s = 0 and s = +10.
   *What GBM and Merton cannot represent for puts, and the direction of each bias:*
   - **No leverage effect.** Real IV rises as the stock falls. Here a winning put is marked at constant
     vol, so mid-life marks (the 10× check, the 21-DTE close) understate winners. This biases the cell
     *against* puts.
   - **Symmetric jumps.** N(0, 0.20) jumps have no crash skew. Real equity jumps are negatively skewed, so
     the put's tail is under-represented. This biases *against* puts.
   - **No skew dynamics.** Neither sticky-strike nor sticky-delta behaviour is modelled.
   - **No borrow and no dividends.** Hard-to-borrow names carry put premia that parity inflates; s
     proxies for that only crudely. Ignoring dividends prices puts slightly cheap, which biases slightly
     *for* puts.
   - **Net:** the harness most likely **overstates** the put penalty. A Rule P flag is therefore an upper
     bound on that penalty, and a clean pass is a stronger statement than a flag.
   - *Engine:* `Structure.long_skew_volpts: float = 0.0` (the long leg at σ_entry + s, entry and marks);
     `max_multiple(structure, *, spot, r, sigma_entry, cost)`; `ThesisModel` used with μ_wrong > 0 (already
     legal). `_strike` and `bs_price` already handle `"P"`.
2. **Tenor fallback.** The question: when no eligible contract exists in [180, 365] d, is the nearest
   expiry in (365, 550] d better than no bet?
   *Cell:* call, 25% OTM, 540 d `[PIN]` (the far edge of the window, so the most expensive case), live
   exits. The cell sits above the 15% floor by construction. A 15%-OTM companion at 540 d is reported as
   description only, because a fallback expiry's nearest-to-target strike can sit at the floor.
   *Grid:* both path models; `ThesisModel` μ_right ∈ {40%, 80%}, μ_wrong = −10%; and the unconditional
   μ ∈ {0, 10%, 25%}.
   *Comparator: no bet = M of 1.0 on cash held* (no interest; a 1 + r·T bar is reported alongside). We
   chose this over the opportunity cost of an empty slot for two reasons. The fallback fires only when
   this name has no in-window contract, and any eligible alternative name is already admitted by the
   ranked selection, so the cash sits until the next cycle. And an opportunity-cost comparator would have
   to assume another thesis's M distribution, which puts a judgment input into a mechanics cell (§1).
   The live 270-d cell is reported as the *reference hurdle*, not as the comparator.
   **Rule T2:** a drafting candidate iff, under **both** path models:
   (i) unconditional mean M(540) ≥ 1.0 at μ = 10% and at μ = 25%; and
   (ii) for **both** μ_right, p*(540) ≤ p*(270 live) + 2 pp `[PIN]`. The fallback may not demand
   materially more judgment than the bet the book already accepts.
   μ = 0 is reported but not ruled on: at zero drift every long option loses to cash by construction.
   *Blindness disclosure (added by the main session's review, 2026-11-10):* part (i) is **not blind**. v2's
   published Rule T table already reports the 540-d unconditional mean M at μ = 10% (1.27 GBM, 1.23 jumps) and
   at μ = 25% (2.10, 2.04), all above 1.0, so (i) is known to pass. The deciding part is (ii), which v2 did
   not compute (v2's p* was the M > 1 proxy, not the thesis-state p*, and its reference was 365 d, not 270 d).
   The operator may keep (i) as a stated sanity floor or strike it; it must not be counted as evidence.
   *Why Rule T's NOT A CANDIDATE does not settle this:* Rule T compared 540 d against 365 d as a
   *replacement*, with both available. Here 365 d does not exist by premise, so the comparator is cash.
   A contract can lose to 365 d and still beat cash. Rule T also failed only at μ = 0, which T2
   deliberately does not rule on.
   *Engine:* none. The suite adds the cash comparator and the 270-d reference. The report adds the 540-d
   premium per name relative to the per-name cap, since a 1.38× premium fits under the cap less often.
3. **Add-to-winners.** Tranche 1 is the live cell. On the first day d in the add window where the tranche-1
   mark is ≥ X × its entry, one confirmation read is taken per path. It fires with probability a when the
   thesis is right and 1 − a when it is wrong. If it fires, tranche 2 is bought with dollars equal to P₁:
   a **fresh 270-d `[PIN]`** call, 25% OTM from the then-current spot, running its own live exit. If it does
   not fire, there is no add, and there is never a second read.
   *Grid:* X ∈ {1.5, 2, 3} `[PIN]`; window ∈ {[30, 90], [30, 180]} d `[PIN]`; a ∈ {0.7, 0.9} `[PIN]`;
   μ_right ∈ {40%, 80%}, μ_wrong = −10%; both path models. `path_days` = 180 + 270 = 450.
   *Expiry choice:* fresh 270 d rather than the same expiry. A live add is a new entry, and the selector
   enforces the [180, 365] tenor window on every entry. A same-expiry add at day 180 would have 90 DTE, so
   it would need a frame exception just to be modelled. *Cost of the choice:* the thesis drift is assumed
   to persist past day 270 on the add's leg, which flatters the add in the right state.
   *Cap:* modelled **within one per-name cap split in two**, each tranche ½ of the 1% cap. A cap-exceeding
   add would be a frame change (PREREG_THEMATIC_CONVEXITY §5) and is not modelled.
   *Comparators (paired):* **one tranche only** (½ cap at risk, the other half held as cash); **two
   tranches both at entry** (the full cap in the live contract). Both have the same M per dollar, so they
   differ only in capital at risk.
   *Reported:* mean M on total premium deployed, p99, P(M ≥ 1), the add rate split by state (right and
   wrong), E_r[Π], E_w[Π], p*, and right-state P&L per cap.
   **Rule A:** a drafting candidate iff, for **one X** (the same X in all four corner cells: a = 0.7,
   window [30, 180], both μ_right, both path models):
   (i) p*(add) ≤ p*(one tranche) − 2 pp `[PIN]`; and
   (ii) right-state P&L per cap(add) ≥ 0.75 × both-at-entry's `[PIN]`. The add must capture most of the
   full-cap upside while committing the second half only on confirmation.
   If more than one X passes, all are reported, and the operator picks the X for the draft.
   *Engine:*
   - `run_cell_mc(..., path_days=None)`.
   - `simulate_option_on_path` walks to the leg's own tenor step, not to `len(path)`. This is a no-op for
     v1 and v2, where the two are equal.
   - `Structure.add_trigger_mult: float | None`, `add_window_days: tuple[int, int]`,
     `add_moneyness = 0.25`, `add_tenor_days = 270`, `add_size = 1.0` (× P₁).
   - `ThesisModel.confirm_accuracy` on the second stream.
   - A two-leg position state with independent per-leg exits.
   - `CellResult.deployed: np.ndarray` (units of P₁).
4. **Re-strike at the time stop.** At 21 DTE on the live cell, a thesis-intact read fires with probability
   a when right and 1 − a when wrong. If it fires, the residual mark (net of cost) plus a fresh slice of
   1.0 × P₁ `[PIN]` buys a new 270-d, 25%-OTM call from the current spot, which runs the live exit. If it
   does not fire, the position closes at the time stop, which is the comparator: the live rule as written.
   *Grid:* μ_right ∈ {40%, 80%}, μ_wrong = −10%, a ∈ {0.7, 0.9}, both path models; `path_days` = 249 + 270
   = 519. Results are on total *new* premium deployed (P₁, or 2 × P₁ on a re-strike). The recycled residual
   is not new money.
   *Cap:* P₁ is set at ½ the per-name cap, as in cell 3. Re-strikes where residual + P₁ exceeds the cap
   (a mark above 1× at 21 DTE) are reported separately as **cap-exceeding**: a frame question, not a pass.
   *Not v2's house-money roll:*
   - v2's roll fired on *winners* (mark ≥ R×), banked the stake, kept the *same expiry*, added no new
     money and used no information read.
   - This re-strike fires at the *time stop* on any path that has not already exited, adds *new* money,
     buys a *new expiry*, and is conditioned on a read of stated accuracy. It re-ups the thesis; it does
     not lock gains.
   - The roll failed on P(M ≥ 1). That failure is no evidence either way here.
   *Reported:* mean M on deployed, p99, P(M ≥ 1), the re-strike rate split by state, E_r[Π], E_w[Π], p*,
   the residual's share of the new leg's cost, and the cap-exceeding count.
   **Rule X:** a drafting candidate iff, at a = 0.7, for **both** μ_right and **both** path models:
   (i) p*(re-strike) ≤ p*(live) − 2 pp `[PIN]`; and
   (ii) E[M on deployed | right](re-strike) ≥ E[M | right](live). The second dollar may not dilute the
   winners per dollar.
   *Engine:* `Structure.restrike_at_time_stop: bool`, `restrike_fresh_mult = 1.0`,
   `restrike_tenor_days = 270`, `restrike_moneyness = 0.25`; the intact read on the second stream;
   `path_days`; `CellResult.deployed`.

*Labelled expectations (written blind; they may be wrong, and v2's was):*
- **Cell 1:** the put needs a higher p* than the matched call, mostly from the skew premium s and the
  zero bound, with little gap at s = 0.
- **Cell 2:** the 540-d p* sits close to the 270-d p* (v2's 540-d and 365-d p* were within about 1 pp).
- **Cell 3:** Rule A(i) is likelier to pass at a = 0.9 than at a = 0.7.
- **Cell 4:** at 21 DTE most far-OTM residuals are near zero, so most re-strikes are mostly fresh money.

None of these expectations moves a rule.

*Standing caveats (as in §3 and v2):*
- **Constant σ_entry through every leg's life.** There is no vol path and no IV re-rating.
  - Winning puts are under-marked (cell 1, against puts).
  - The add and the re-strike are priced at σ_entry, while a live add into a working theme, or a
    re-strike after a move, would usually pay a re-rated IV. This **flatters cells 3 and 4**.
- **The cheapness gate is not modelled for the add or the re-strike.** Each is assumed to pass, which
  overstates how often they would happen live.
- **The right-state drift is assumed to persist past day 270** (cells 3 and 4), which flatters both.
- Passing cells 3 or 4 therefore earns a draft *and* a forward check, never a frame change on the
  harness alone.

Outputs go to `data/calibration/<ts>/calibration_v3.{json,md}`. The finding is appended below this
amendment with the date, the commit and the four rule verdicts (P, T2, A, X).

---

## What the operator decides

1. **Freeze as written.** Paste the block above into PREREG_CONVEXITY_CALIBRATION §4 after the v2 FINDING,
   set the date, and commit before any v3 code.
2. **Change any `[PIN]` first.** The most consequential pins:
   - Rule P's 5-pp bar and its s = +5 matched cell.
   - T2's +2-pp tolerance and the cash comparator. The alternative is the empty-slot opportunity cost.
   - The add's fresh-270-d expiry versus the same expiry.
   - The split-cap model, which keeps the frame unchanged.
   - The 0.75 and 2-pp bars in Rules A and X.
3. **Strike a cell.** Cells are independent. Striking one deletes its text, its rule and its engine
   additions from the v3 build.
