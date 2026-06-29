# DRAFT amendment — PREREG_CHEAPNESS_WATCH §2.1: the `degenerate_iv` + `unmeasurable` states

**Status: DRAFT for operator BLIND bound-pinning (2026-06-29, rev 3 — full red-team folded incl.
the clip-budget correction, window right-censoring, and the open-at-end generalization). NOT in
force.** Frozen-PREREG class → staged for explicit merge, never self-merged. This `records/` file is
the **shape-review** artifact (a dated record, like the #117 precedent); committing it ≠ making it
in-force. The in-force step — folding §2.1.8 into `PREREG_CHEAPNESS_WATCH.md` — is the later explicit
merge, gated on pinned bounds. **Sequencing: the predicate SHAPE is settled here; bounds are pinned
BLIND in one pass against the settled rationale AFTER; then the build runs against synthetic
fixtures. Pinning before the shape settled would force a re-pin = the re-tune pin-once forbids.**

## Why (the finding)

The cheapness-watch gate (`is_cheap_convexity`, `convexity_gate.py:103–110`) fails closed **only**
on a *missing* IV. Two failure classes both launder into `never_cheap` = "IV already popped (the
move got priced before we could catch it)" when the truth is "we couldn't read it":

1. **Present-but-degenerate IV** (CDE): `atm_iv ≈ 200%` → `iv_rv 3.7`, `skew −202vp`. The wing IV
   stayed positive, so no fail-close fired; the gate returned a confident `cheap=0` ("rich").
2. **Missing-input fail-close** (P2a, *more common on thin names*): a wing that **passed
   eligibility** (spread/price/OI — never IV) but lacks an IV, or whose ATM-strike contract lacks
   one → `GateVerdict(False, None, …)` (`convexity_gate.py:107–110`) → `record_cheapness` writes
   `cheap=int(False)=0, iv_rv=None` → `_detect_breaks` buckets `cheap==0` → `never_cheap`.

**This is the instrument *under* the read, not a lever gated *on* it.** Report-time measurement
only → **holds at zero additional trades** → passes the legitimacy test; not gated on the cheapness
read or the funnel redesign. It is a **precondition** for the read being trustworthy once §2.1.7's
break-capable cohort arrives.

**The break is never hidden, only reclassified.** Onset detection is marker-based
(`rv_rising`/`mom_recent`, independent of the gate IV), so a degenerate/missing session cannot
suppress a break — it moves the break from a mis-attributed bucket to an honest one. `n_breaks` is
invariant; only the attribution is corrected.

## The complete `(cheap, iv_rv)` partition (the organizing frame)

| `(cheap, iv_rv)` | state | in qualifying? |
|---|---|---|
| `None`, — | `no_structure` | no |
| **`0`, `None`** | **`unmeasurable`** (missing-input fail-close) — **NEW (P2a)** | no |
| `0`, present & sane-rich | `never_cheap` | no (separate) |
| **`0`, present & degenerate** | **`degenerate_iv`** | no — **NEW** |
| `1`, present & sane | `cheap_window` | yes (if stale) |
| **`1`, present & degenerate** | **`degenerate_iv`** (the R2 verdict-corruptor) | no — **NEW** |

`(1, None)` is **impossible** — a passing gate (`cheap=1`) always computed `iv_rv` (`convexity_gate.py:112,119`).
The two NEW states sit out of both `qualifying` and `never_cheap`. (Doc fix, same PR: migration-0017's
docstring says "`cheap` is NULL … a fail-closed gate" — wrong; a fail-closed gate *with a structure
present* writes **`0`**, not NULL. NULL = `no_structure` only; `cheap=0 ∧ iv_rv IS NULL` is the
missing-input marker.)

## The verdict-corruption seam (R2 — the one that matters)

The gate's skew check is **one-sided**: `convexity_gate.py:116` vetoes only `skew_vp > +10` (wing
*richer* than ATM), because a cheap wing is "good." So the dangerous case is the **clean-ATM /
garbage-wing** name: ATM ~50%, rv ~45% → `iv_rv 1.11` (passes); wing stale → large *negative* skew
(passes the one-sided gate) → false **`cheap=1`** → into **`qualifying`**, the verdict-bearing set —
a **single degenerate leg with a fine ATM** (CDE only escaped into `never_cheap` because its *second*
leg, the ~200% ATM, tripped `iv_rv`; a clean-ATM/garbage-wing name has no such backstop).

## §2.1.8 — the predicate SHAPE (BLIND pins; bounds pinned later, in one pass)

Report-time reclassification over the **already-persisted** raw IV columns (`atm_iv`, `wing_iv`,
`iv_rv`, `otm_skew` — migration `0017:33–38`). **No migration, no record-segmentation** — raw inputs
unchanged; only the interpretation changes, applied uniformly across all history. (Segmentation here
would be *incorrect*: splitting a homogeneous dataset on a non-event.)

**A. The disjunction (per-leg).** A session is `degenerate_iv` iff *any* bound trips:

| Disjunct | Failure it guards | Note |
|---|---|---|
| `\|otm_skew\|` > `skew_abs_max` | a leg diverges hard (CDE-high −202; the garbage-low wing) | **absolute** value → catches both tails (gate bounds only *positive* skew); ⚠️ its negative tail is on the clip axis (below) |
| `iv_rv` > `iv_rv_sanity_max` | ATM ≫ trailing RV (both-legs-high; skew small) | must be **≫ 1.2** or it launders *legitimately-rich* names; the **only** clip-free disjunct |
| `atm_iv` < `iv_floor` **OR** `wing_iv` < `iv_floor` | **either leg** implausibly low (absolute) | **PER-LEG / disjunctive** — headline job is the **single-low-WING** seam, NOT "both low together" (a conjunctive `AND` reopens R2: the clean-ATM/garbage-wing case has a *fine* ATM) |
| `wing_iv` < `k · atm_iv` | wing implausibly low **relative** to ATM (the *moderate* seam) | scales with ATM → separates wing 8%@ATM50% (0.16, caught) from 20% (0.40, spared); shrinks the P1(b) band |

**⚠️ Three disjuncts share ONE clip axis — pin `skew_abs_max`, `iv_floor`, `k` as a single
cheap-wing-clip budget.** The edge *is* a cheap wing: the gate (`skew ≤ 10`) admits and rewards a
wing IV at or below ATM, so low-wing-IV-relative-to-ATM is the **signal**. Three disjuncts fire on
that same low-wing direction and can clip *genuine signal*: `wing_iv < iv_floor`, `wing_iv < k·atm_iv`,
**and `|otm_skew| > skew_abs_max` on its NEGATIVE tail** (an absolute value fires on a wing far
*below* ATM = the cheap-wing signal, not richness; its positive tail is clip-free, its negative tail
is not). They are **not independent defense-in-depth on the clip axis — the effective clip is
whichever is tightest.** A spectacularly-cheap-but-real wing reads "degenerate" if *any* of the three
is too loose → the watch **suppresses the exact cheap break it exists to catch** (the symmetric-but-
**more-dangerous** partner to the `iv_rv`-ceiling caution, which only clips legitimately-*rich* names
the strategy discards anyway). Pin all three to fire **only** on near-zero/stale quotes (a wing at a
few % annualized while ATM/RV run tens of %), never on a real low-IV wing. **Only `iv_rv` (high-side)
is genuinely clip-free.**

**B. The irreducible band — and the SCOPED claim (P1b).** "Thin-but-real low-IV wing" and
"degenerate low-IV wing" are a continuum with no physical bright line: a `skew_abs_max` generous
enough not to clip real OTM-call skew (tens of vp negative) and a low absolute floor together **miss
a moderately-degenerate wing** (ATM 50%, wing 8–20% → skew −42…−30, above a generous ceiling, above a
5% floor) → it slips in as false-cheap. The relative disjunct shrinks this band; it does not close
it. **Therefore the invariance claim is SCOPED:**

> §2.1.8 reclassifies **bound-detectable** degeneracy out of `qualifying`/`never_cheap`. It does
> **not** protect the verdict against *all* degenerate-low input; the moderate thin-wing band is an
> acknowledged residual (the common case on the anti-quietness cohort, not just CDE's −202 extreme).

Unqualified, "protects the verdict against degenerate-low" is an overclaim (drafter's *and* operator's
round-2 framing) — explicitly retracted.

## §2.1.8 — the two consumption sites (both report-time)

**Wiring (P2c):** both sites consume the rows from the **`by_sym` query** at the top of
`cheapness_report` (`cheapness_watch.py:175–178`), which today selects only
`symbol, as_of, cheap, rv_rising, marker_age_days, mom_recent`. The four IV columns are added
**there** (not a separate SELECT). One shared classifier `_classify(row, bounds)`, **None-safe**:
`iv_rv IS None ∧ cheap==0` → `unmeasurable`; present-and-bound-tripping → `degenerate_iv`; never
raises, never silently passes.

**Site 1 — onset (`_detect_breaks`):** before the `cheap is None / ==0` branches, classify; an onset
that is `unmeasurable`/`degenerate_iv` gets that state (parallel to `no_structure`), excluded from
both `qualifying` and `never_cheap`. `_window_len` is not called for it.

**Site 2 — mid-window (`_window_len`, `cheapness_watch.py:127–140`) — the load-bearing fix.** It reads
`rows[j]["cheap"]` **directly**, so an onset-only fix leaves `cheap_window_days` (the verdict-bearing
quantity) corrupted by mid-window degenerate sessions. It becomes a **three-input** machine;
`degenerate_iv` and `unmeasurable` collapse to one **`unreadable`** input class. The FULL table (every
cell pinned + a test each — the rigor the original 2-state debounce got):

| macro-state ↓ \ session → | `cheap` | `not_cheap` | `unreadable` (degenerate ∨ missing) |
|---|---|---|---|
| **IN_WINDOW** (`notcheap_run=0`) | `window++`; `degen_run:=0`; stay | `notcheap_run:=1`; `degen_run:=0`; → CLOSING | `degen_run++`; if `≥2` → **TRUNCATE**; else stay (window & run unchanged) |
| **CLOSING** (`notcheap_run=1`) | `window++`; `notcheap_run:=0`; `degen_run:=0`; → IN_WINDOW | `notcheap_run:=2`; → **CLOSED** (finalize) | `degen_run++`; if `≥2` → **TRUNCATE**; else stay CLOSING (run **transparent**) |

- `degen_run` resets on any `cheap`/`not_cheap`. **Isolated unreadable blip = transparent** (neither
  advances nor resets the close-run); **sustained unreadable run (≥2, mirroring §2.1.2) = TRUNCATE**.
  CDE's real #285→#337 alternating pattern exercises the `cheap`/`unreadable` cells.
- *Pinnable:* the sustained-truncate threshold (default **2** = the §2.1.2 close threshold).

## §2.1.8 — RIGHT-CENSORED windows must not feed the verdict at face value (Edit 2, generalized)

A §2.1.2 window **CLOSED** by 2 genuine not-cheap sessions has an *exact* length. A window that ends
any other way is **right-censored** (true length ≥ observed `V`):

- **`truncated`** — ended on 2 consecutive *unreadable* sessions (lost visibility); and
- **`open_at_end`** — still cheap at the last observation, no close seen. *[pre-existing in
  `_window_len` (runs to end of rows, returns the count); SAME bias, folded in because the fix is
  identical — and it is the COMMON case for a RECENT break, exactly the case the watch cares about.]*

The verdict medians `cheap_window_days` and fires if the median `< staleness_lag`, so a censored-
*short* window read at face value pulls the median down → **biases toward FIRE** — worst on the
target cohort (thin under-narrated wings are where unreadable/recent breaks cluster, so censoring is
most frequent where the watch decides). Handle as censored (the discipline the shares/grounding
reports already apply via their terminal guard — `terminated=`, `test_report_terminal_guard_and_unresolved`):

- censored at **`V ≥ lag`** → true length ≥ V ≥ lag → a **definitive HOLD vote** (keep it; informative).
- censored at **`V < lag`** → uninformative for median-vs-lag (true length could be either side) →
  **EXCLUDE from the decision set** (median *and* N-floor), report separately as `censored_short`.

Keeps `insufficient_N` longer when wings are flaky / breaks are fresh — the **honest** outcome (can't
measure the window ⇒ can't decide), not a regression. **Data flow:** `_window_len` returns a window
**end-reason** (`closed` | `truncated` | `open_at_end`); `cheapness_report` applies the censoring rule.

## §2.1.8 — make the blindness visible (P3 + audit)

- **Report:** `n_degenerate_iv`, `n_unmeasurable`, `n_censored_short`, and the **reclassified-rows
  list** (`symbol / as_of / iv_rv / otm_skew / atm_iv / wing_iv / which-disjunct`) — auditable proof
  it is eating garbage, not legitimate names.
- **Per-name panel (P3):** `latest_by_name` (`dashboard_data.py:565`) renders raw `cw.cheap` → after
  reclassification a degenerate row still shows `cheap=1`, contradicting the verdict. Surface the
  per-name **state** beside the `iv_rv` the panel already carries, so row and verdict agree.

## §2.1.8 — pin-once / apply-once (discipline)

Bounds pinned **once** from physics, applied to history **once**, result recorded **as-is**. A
surprising reclassification is a **finding**, not a license to re-tune. The *build* still iterates —
against **synthetic fixtures with known answers**, never the live historical verdict; the single
retroactive application is one recorded event after bounds are pinned and code is correct.

## §2.4 — STUB (deferred companion): live-gate fail-closed on degenerate IV

The **same predicate** belongs at the live gate (`is_cheap_convexity` → `cheap=False`, reason
`degenerate_iv`) — a **safety** fix stopping a degenerate-low false-`cheap=1` from reaching a real
entry. It **changes what trades** → its **own pre-registration**. **PRECONDITION (not "deferred"): it
lands BEFORE the funnel first produces a council include** (mirroring §2.1.8 landing before the
break-capable cohort). The hole is real now, masked only by the empty book + 0-includes (transient);
a safety hole masked by a transient closes before the transient lifts, not after it bites. (Third
companion, own pre-reg, gated on thin names clearing: `select_structure` re-picking a quotable strike.
Out of scope.)

## Build checklist (after bounds pinned — separate staged PR)

1. `_classify(row, bounds)` helper, None-safe; bounds from `config.convexity_gate` (new keys).
2. Add `atm_iv, wing_iv, iv_rv, otm_skew` to the **`by_sym` query** (`cheapness_watch.py:175–178`).
3. `_detect_breaks`: `degenerate_iv` + `unmeasurable` onset states (excluded from qualifying *and*
   never_cheap).
4. `_window_len`: the full transition table (3-input; truncate-on-sustained; transparent blip) **and
   a window end-reason return** (`closed`/`truncated`/`open_at_end`).
5. `cheapness_report`: the censoring rule (`V≥lag` → hold vote; `V<lag` → out of median+N-floor,
   counted `censored_short`); report `n_degenerate_iv`/`n_unmeasurable`/`n_censored_short` +
   reclassified-rows. Panel: per-name state.
6. Migration-0017 docstring fix (NULL vs 0).
7. **Tests — assert the VERDICT, not the label:**
   - **The seam-exposing degenerate-LOW (load-bearing):** clean ATM + a wing whose skew sits **below
     the `\|skew\|` ceiling** (the relative disjunct must catch it) that *would* be `cheap=1` and enter
     `qualifying` → assert reclassified out, `n_qualifying`/`verdict` unchanged vs baseline.
   - `unmeasurable`: `cheap=0, iv_rv=None` → not `never_cheap`, not `qualifying`.
   - mid-window degenerate-LOW: clean onset + injected mid-window unreadable → `cheap_window_days` not
     inflated. degenerate-HIGH mid-window: not a false early close.
   - **censoring:** a `censored_short` window does **not** enter the median (verdict unchanged vs a
     clean baseline without it); a `V ≥ lag` censored window votes **hold**; an `open_at_end` short
     window is treated as censored, not a face-value short.
   - every `_window_len` cell (6) has a case; alternating `cheap`/`unreadable`; sustained truncate.
   - CDE-high onset → `degenerate_iv`, not `never_cheap`.
   - **negative control:** a *legitimately rich* name (iv_rv just above 1.2, sane skew) stays
     `never_cheap`, is **not** swept into `degenerate_iv`; a *spectacularly-cheap-but-real* wing (low
     wing IV, skew above −`skew_abs_max`) stays `cheap_window`, is **not** clipped.

## Bounds to pin BLIND (one pass, AFTER this shape is ratified)

Pin from physics, not from CDE — the physics derivation is the entire anti-HARK protection (we have
both seen 3.7/−202; concealment does no real work). The three clip-axis bounds are a **single budget**
(§2.1.8.A ⚠️):

```
skew_abs_max_volpts  = ___  # vp a real far-OTM smile can sit from ATM; NEGATIVE tail is clip-axis
iv_rv_sanity_max     = ___  # ATM-IV ÷ trailing-RV multiple certainly degenerate (>> 1.2); clip-free
iv_floor_annualized  = ___  # per-leg annualized IV floor; clip-axis — fire only on near-zero
wing_atm_ratio_min_k = ___  # wing/atm ratio floor (≈0.2 candidate); clip-axis, the delicate one
iv_ceiling_annualized= ___  # (optional) upper IV bound; keep generous (a micro-cap can run 150%+)
```
