# §5 Amendment (DRAFT) — dual-read tripwire response, split by breach mechanism

> **STATUS: FROZEN 2026-06-22 — merged into `PREREG_DATA_FEED_OPRA_SEQUENCING §5` +
> `PREREG_UNIVERSE_CURATION §2.3` (brought forward from the planned 2026-07-10 close-out;
> anti-HARK-clean — the text was committed BLIND 2026-06-17/18 and is unchanged). #72
> (`dualread_executor.py`) now builds against this frozen table; its Phase-3 Δ-wire revert latch
> stays `config.data_feed.dualread_revert_enabled=false` until the OPRA deploy-gates clear. The
> `veto-dualread-disagree` auto-lapse (§5 response 1) is UNCHANGED — still 2026-07-10; the
> lapse-vs-extend decision remains the dated near-deadline call.**
>
> Anti-HARK pre-commitment: the amendment text is committed now, weeks before the close-out, so the
> close-out's Δ / material-flip population cannot reshape the response table after the fact. It governs
> nothing until merged into `PREREG_DATA_FEED_OPRA_SEQUENCING.md §5` on 2026-07-10.
>
> Drafted 2026-06-17/18; set after the coverage-gap wire fired (runs #199/#216, UROY) — disclosed at
> firing, like the 2026-06-12 flip-materiality floor. Converged over a multi-round operator red-team;
> final read passed (every delta landed where it edits; internally consistent; no content changes).

## Problem

§5 binds one response — `revert option_gate→indicative + page` — to three structurally different
rolling-wire breaches. Coherent for a feed-*trust* breach (OPRA noisy → fall back to the validated prior
feed); **incoherent for a coverage gap** (`indicative.structured ∧ ¬opra.structured` = OPRA has *no
tradeable wing*; reverting would restore the phantom coverage the gate correctly refuses, authorizing
entries on a wing with no real market).

## Trip rule (per class, evaluated independently)

A name's heterogeneous gap reasons across the window do **not** aggregate into one trip:

- **structural-absence** — ≥2/5 sessions whose gap `note` is structural (`no_eligible_contract_in_tenor_window` / `select_structure` reasons).
- **entitlement** — per-session, feed-wide (below); no rolling threshold.
- **transient** — ≤1/5 log-only; escalates only if its own reason-sessions reach ≥2/5.
- 1+1+1 across reasons trips nothing on absence/transient; the entitlement session pages on its own per-session rule.

## Response table

| Wire | Trip | Mechanism | Response |
|---|---|---|---|
| **\|Δ iv/rv\|** | med>0.05 ∨ max>0.10, ≥3/5 | OPRA diverges on a wing that *exists* → feed-trust | `revert option_gate→indicative` + page. **The sole revert trigger.** |
| **cheap-flip (material)** | ≥2/5, \|Δ\|≥0.02 | discrete disagreement on an existing wing | **investigate + page; no revert** (magnitude is the Δ wire's exclusive job). Rising-edge page, debounced (below). |
| **coverage-gap** | per class (above), on `note` ↓ | OPRA can't structure — *why* decides the class | ↓ |

### Coverage-gap partition (reason is in the dual-read `note`)

| OPRA `¬structured`, `note` | Class | Response |
|---|---|---|
| `no_eligible_contract_in_tenor_window` / selection reasons | **structural absence** (OPRA-correct) | coverage-feasibility: page (debounced); **no revert**; name stays in basket (PREREG_UNIVERSE_CURATION §3) — gate fail-closes it. The sweep's `structured=0 + note` row **is** the per-session feasibility record (no separate §2.3 re-run for this class). |
| fetch error → `entitlement` (`feeds.classify_feed_error`) | **OPRA-trust failure (feed-wide)** | a subscription lapse fails *every* OPRA fetch → detect/page per **session, feed-wide, not per name**: **one page/session** for the entitlement state while it persists. §7's inline per-name entry-veto is the entry backstop (each candidate's premium fetch fails-closed-and-drops, §7). Hold per §7 ("never a silent downgrade"); decoupled from the rolling wire (pages on the session, not after recurrence). |
| fetch error → `transient` | **per-name fetch instability** | log + re-check while ≤1/5. A transient that recurs to ≥2/5 has falsified "transient" → **escalate to a per-name page** (no feed-wide state, no hold, no revert). |

*"Feed-health" is two distinct responses — keep them separate downstream:* (i) **entitlement = feed-wide
outage** → feed-wide state + §7 hold + one page/session; (ii) **recurring transient = per-name instability**
→ per-name page only. **One name's flaky chain must never raise the feed-wide entitlement state.**

*Coherence:* the Δ wire **reverts** (OPRA working-but-noisy → a deliberate, paged, segmented downgrade); an
entitlement gap **holds** (OPRA unavailable → §7 veto, never a silent downgrade). Distinct triggers, distinct
responses.

## Debounce (look-once-disposition signals must not re-page while parked)

- **Structural-absence:** rising-edge page; suppress until the name regains a durable wing — **≥4 consecutive
  wing-sessions** — or is dispositioned. Pinned as the **concrete consecutive count**, *not* "the rolling-5
  would no longer trip": those diverge on flickering names — `[absent,wing,wing,wing,absent]` →
  `[wing,wing,wing,absent,wing]` reaches ≤1 absence on a *single* consecutive wing, then re-trips on the next
  flicker (UROY: present #130/#147, absent #164, present #182, absent #199/#216). The 4 is *derived* from the
  wire (4-in-a-row ⇒ ≤1 absence in the rolling-5, so a lift can't immediately re-trip); the implementation
  target is the consecutive count.
- **Material cheap-flip:** identical — rising-edge page; suppress until the flip clears (**≥4 consecutive
  non-flip sessions**, same logic) or is dispositioned. (Without it, the table's demotion of flip from
  one-shot revert to recurring "investigate + page" re-pages a near-threshold-parked name nightly.)
- **Never debounced:** the entitlement state (re-pages once/session while down — an outage is
  ongoing-actionable). In all cases the sweep's per-session record stays **continuous**; only the alert is debounced.

## Consequence (neutral — disclosed, not a justification)

UROY's current `gap_tripped` reclassifies as coverage-feasibility and exits the revert-trigger population;
whatever the remaining Δ / material-flip population then reads is a separate empirical fact.

## Carve-out ledger + reserved revert-trigger space

(Tracks what the *revert trigger* reserves — post-amendment the gap and flip wires still fire, they just don't revert.)

- 2026-06-12 — flip-materiality floor (\|Δ\|≥0.02): sub-floor flips → not counted.
- 2026-07-10 — coverage-gap split: structural-absence → feasibility; entitlement → feed-wide hold; transient → log/escalate. None revert.
- 2026-07-10 — **cheap-flip demotion**: material flip → investigate + page; **revert is the \|Δ iv/rv\| wire's exclusive job**.
- **Reserved revert-trigger space at this amendment: the \|Δ iv/rv\| wire alone.** All other wires route to
  investigate / feasibility / feed-wide hold / monitor. Each close-out states whether this space has narrowed
  toward ∅ (the erosion signal).

## Sequencing with #72

#72 wires the runtime mechanism that executes this response (currently neither — the rolling wires live only
in the dashboard read). **#72 must not land before this freezes** (else it wires the old
coverage-gap→revert = phantom-authorizing), or it builds against this table. Scope: per-class trip counting;
the partition (incl. **classifying the sweep arm's error** — it stores raw `str(e)` today — and extending
**entitlement detection to the sweep population**, which §7 covers only for *evaluated* names); both debounce
resets at the **≥4-consecutive** count; and never raising the feed-wide entitlement state for one name's flaky chain.

## Feasibility re-run (record-only)

Where invoked, a §2.3 re-run *records* (in)feasibility for the audit trail; PREREG_UNIVERSE_CURATION §3
forbids acting on it. A structural-absence name has **no separate re-run** — the sweep's per-session
`structured=0` row is that record.

---

## The 7/10 freeze is THREE artifacts (not just this §5 prose)

1. **§5 consolidated amendment** (this file's body) → `PREREG_DATA_FEED_OPRA_SEQUENCING.md §5`.
2. **§2.3 OI reconcile** — *companion edit, different document* → `PREREG_UNIVERSE_CURATION.md §2.3`:
   `"OI ≥ 50"` → `"OI ≥ 50 (when present)"` (match `structure.py:contract_eligible`); record window #1's OI
   floor was vacuous cohort-wide (every 6/9 name `OI: n/a`); log **UROY = N=1** toward a future-window
   decision on tag-flagging OI-absent admissions marginal-liquidity.
3. **#72 contract** — runtime code the freeze can't contain: held until the freeze; implements the partition,
   per-class counting, the two ≥4-consecutive resets, sweep error-classification + sweep-population
   entitlement detection.

## #72 deployment (process — NOT amendment text)

7/10 freezes the **doc**. #72's **deployment** is a separate event in the OPRA workstream and inherits its
deployment preconditions (the freeze-gate re-score, the boundary confirmations). **"Frozen" authorizes #72 to
be built against this table, not shipped.** Confirm which of the OPRA-workstream gates bind #72 specifically
before it deploys.
