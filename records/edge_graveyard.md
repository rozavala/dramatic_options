# Edge graveyard — dead deterministic-edge hypotheses + the grave each died on

**Purpose.** The stub promises dead candidates a graveyard ("Themes get a graveyard, like edges" —
`PREREG_THEME_GENERATION_STUB.md:74-75`). This file records deterministic *edge* hypotheses that have
been killed, with the specific grave, so a future hypothesis fan-out **does not re-derive them and
burn another multi-agent run**. Feed this file into the generation prompts of any future
edge-vetting run.

**The graves** (from `dramatic-options-edge-toolkit` memory): **power** (too few independent periods
AFTER clustering for any null to reach significance) · **null≈signal / FSSD-redux** (conditioning on
the event adds ~nothing over the underlying characteristic — a characteristic dressed as an event) ·
**council-backtestability** (alpha is LLM judgment → forward-only, guardrail §6) · **universe** (the
test lab is one correlated beta blob) · **crowdedness** (the clean dated public version is already
arbitraged) · **two-stage spend-gate** (the gross/free null can't be proven before paying for
options/IV/borrow data) · **cheap-convexity-gate infeasibility** (the only vehicles sit in the
rich-IV / steep-call-skew corner the gate exists to reject).

---

## Canonical (the lineage — fully written up elsewhere)

- **divergence v1** — insider-buying / fundamentals "delivery" signal. UNPROVEN across 4
  Bonferroni-penalized iterations; primary-horizon rank-IC ≈ 0. Gate table and write-up below.
- **FSSD v2** — 424B5 forced-supply × short-sale friction. §8 audit PASSED but Stage-1 k=1 FAILED:
  event CAR −1.91% ≈ random-date null −1.78% (the decisive null≈signal kill). See `PREREG_FSSD.md`.

---

## From the 2026-06-21 hypothesis-backlog fan-out (7/7 edges killed)

### Power grave — too few independent episodes for the (correctly pre-stated) null
- **Byproduct-supply-inelasticity selector** — thin cross-sectional residual over ~5 names + a
  handful of deficit episodes; AND the mechanism runs backwards (byproduct exposure = *diluted*, not
  concentrated, equity leverage).
- **Pre-renewal cheap-convexity window in reinsurers** — annual renewal-season clustering →
  single-digit independent periods across 3 cat-correlated names; the null also sits behind the
  historical-IV paywall (two-stage spend-gate violation).
- **Index-deletion forced-sell** — deletions wave-cluster on drawdowns; ~10 independent
  reconstitution clusters per decade.
- **Post-Chapter-11 emergence** — credit-cycle clustering → single-digit independent episodes; the
  gross null is underpowered before any options spend.

### Null≈signal / FSSD-redux — a characteristic dressed as an event
- **Reshored-pharma onshoring-filing drift** — ~0 resolved approval events; the FSSD null test is
  literally un-runnable now and for years.
- **Spinoff IV-orphan** — elevated forced-seller RV makes IV/RV read "cheap" for the wrong reason;
  the no-pre-history structure means the null control can't even be constructed in the window claimed.
- **Major-customer-concentration shock** — where the silo is real the chain is un-tradeable; where
  it's tradeable the silo is already arbitraged. Already housed correctly in-codebase as a discovery
  source (`corpus/customer_concentration.py`) — demote, don't backtest.

### Meta-finding
**The deterministic-edge well is dry for this player.** A fresh fan-out independently re-derived
exactly the two graves that killed divergence and FSSD. **Stop generating event-conditioned harness
edges** — they keep landing here. Invest in the theme layer (the Stage-1 generator) where theme-level
alpha legitimately lives, and route theme survivors to the council→gate FORWARD path.

---

## Companion — theme vehicles that die at the cheap-convexity gate (don't re-propose as-is)
Not edges, but recorded to avoid re-proposing the same gate-infeasible expressions:
- **Central-bank gold → unrepriced miners** (GDX/GDXJ/NEM/AEM) — consensus thesis + rich call skew.
- **Climate-driven reinsurance hard market** — permanent calendar-anchored cat-tail premium; also a
  linear book-value grind, not an OTM-convex jump.
- **Equity spin-off completion** — no-history thin chains priced RICH (uncertainty premium); the gate
  rejects by construction.

---

## Lineage write-ups (moved from `CLAUDE.md`)

**Divergence (v1) history:** The point-in-time data layer (Alpaca + EDGAR + bulk insider + XBRL fundamentals), divergence signal, and walk-forward backtest harness are built, tested, and green. **The edge gate FAILED across four Bonferroni-penalized iterations** (substance: event-presence → signed insider net-buy → reported revenue YoY) on a properly-powered, multi-regime, momentum-neutral test (44–47 periods, 61 names, 2020–24): primary-horizon (h=21) rank-IC stayed ≈0, every Bonferroni CI spans 0. An early +0.075 on a narrow 30-period window did not survive added power/regimes — fragile. Verified the null is real (substance density 96–100%; real-data momentum positive control IC ≈ +0.10), not a measurement artifact. Per the pre-committed stopping rule the deterministic divergence approach is set aside (no k=5); per guardrail §5 **no live-shaped behavior is built on the unvalidated edge**; the lockbox was never opened. See the §"Phase 1 gate result" below. The fork now is: a *new* edge hypothesis on the (working) harness, OR forward-test divergence via the un-backtestable Phase-3 council, OR reconsider the greenfield system. ← update this line as phases complete.

**FSSD (Forced-Supply Secondary Drift, 424B5 × short-sale friction) — see `PREREG_FSSD.md`:** the §8 eligible-N audit PASSED (friction∩optionable∩tradable corner 28≥24 months) but the Stage-1 gross-CAR gate FAILED at k=1 (explore 2019–22, h=10td): top-friction-decile mean CAR −1.91%, Bonferroni CI [−4.64%, +0.67%] spans 0, and — decisively — the **null control (random in-name dates) −1.78% ≈ the signal −1.91%**, so conditioning on the 424B5 event adds ~nothing over the friction characteristic (the drift belongs to high-SI/low-float small-caps generally, not the supply event). STOPPED per the pre-registered rule (no k=2, no Stage-2 options-data spend). The §8b corner also showed a ~52% median put bid/ask spread (borrow-in-the-puts), which would have sunk Stage-2 net-of-borrow regardless. Harness extended & reusable: `data/edgar_index` · `data/finra_si` · `data/shares_out` · `data/prospectus` · `friction` · `options_tradability` · `fssd_stage1` (survivorship-clean event-study CAR with trailing-decile, period-bootstrap, null+positive controls). **Two graded negatives confirm the harness is the durable asset; the fork is unchanged — a *new* edge hypothesis, OR forward-test divergence via the Phase-3 council, OR reconsider greenfield.**

### Phase 1 gate result (2026-05-30) — v1 divergence edge UNPROVEN

Pre-registered, banded, multiple-testing-aware gate (SPEC §2a). Primary horizon h=21td.

| Run | periods | h=21 rank-IC | Bonferroni CI | verdict |
|---|---|---|---|---|
| 34 names, 2022–24 (k=1) | 30 | +0.075 | spans 0 | fragile (didn't replicate) |
| 61 names, 2020–24 (k=2) | 47 | +0.023 | spans 0 | FAIL |
| + insider net-buy substance (k=3) | 47 | −0.048 | spans 0 | FAIL |
| + revenue-YoY substance (k=4) | 44 | −0.057 | spans 0 | FAIL |

Four iterations (k=1→4), each Bonferroni-penalized; substance evolved event-presence → signed
insider net-buy → reported revenue YoY (the strongest deterministic "delivery" proxy). The
h=21 IC never escaped 0; the only positive (+0.075) was the narrow-window artifact that didn't
replicate. Per the pre-committed stopping rule the **deterministic divergence approach is set
aside** (no k=5); the lockbox was never opened. Diagnostics holding across all four runs:
substance density 96–100% (not thin), real-data positive control alive (momentum→fwd IC
≈ +0.10), divergence decorrelated from momentum — so the null is real, not a plumbing artifact.
The harness (point-in-time, no-lookahead, pre-registration, period-bootstrap, momentum-
neutralization, null + real-data positive controls) is the durable deliverable — reusable for
a *new* edge hypothesis, or for forward-testing divergence via the Phase-3 council.
