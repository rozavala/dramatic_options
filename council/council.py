"""Top-level council entry point (T2): candidates → proposals (the hard-seam boundary).

``propose`` runs the three-role debate over the operator's candidate watchlist and returns ALL
proposals (traded or dropped) for recording — the forward-scoring substrate. The orchestrator
persists them, then ``proposal.select_for_trade`` picks the survivors (strategist-include AND
conviction ≥ floor) and projects them to ``Theme``s for the *unchanged* deterministic loop.

Fail-closed, three ways:
  - the always-on KILL switch is checked **first**, before any LLM spend (real guard, not a
    downstream backstop);
  - a per-cycle cost cap is enforced at the router boundary — a blocked call aborts the whole
    cycle to **zero proposals** (over-budget → no entries);
  - a per-candidate provider error drops *that* candidate (it never trades) and the cycle continues.
"""

from __future__ import annotations

import logging

from council.context import build_context_pack, synthetic_context_pack
from council.debate import run_candidate
from council.proposal import CouncilProposal
from council.router import BudgetExceeded, RouterError
from risk import kill_switch_active

log = logging.getLogger("council")


def compose_judged_set(candidates, *, max_candidates: int, reserve_k: int,
                       cheap_eligible: dict, last_judged: dict,
                       fairness_m: int = 0, fresh_event: frozenset | set = frozenset()):
    """The gate-cheap RESERVE composition (PREREG gate_cheap_reserve, FROZEN 2026-07-02 §2/§4).

    Replaces the plain ``[:max_candidates]`` union truncation with a reserved composition, same
    total (zero marginal LLM cost): hand-seeds (protected, first, unchanged) + top-(slots−K)
    sentinels by the existing ``inflection_score`` order + K RESERVE slots for gate-cheap union
    sentinels that the motion rank would truncate out. Membership-only — prompts, gates, sizing,
    and every candidate object are untouched (the §10 seam guard).

    ``cheap_eligible``: {SYMBOL: iv_rv} for names with a fresh gate-of-record cheap read (§3 —
    built by ``state.gate_cheap_reads``; fail-closed: absent ⇒ not reserve-eligible).
    ``last_judged``: {SYMBOL: last council as_of ISO} (§4 — never-judged sorts FIRST).

    Within-reserve rank (§4): least-recently-judged → lowest iv_rv → symbol asc.
    Fewer than K eligible ⇒ the unfilled slots FAIL CLOSED to the motion rank (backfill in
    inflection order — the pre-change composition), so ``reserve_k=0`` or an empty
    ``cheap_eligible`` reproduces the old ``[:max_candidates]`` slice byte-for-byte.

    FAIRNESS reserve (the 2026-08-11 amendment, operator-decided; STAGED build): ``fairness_m``
    additional reserved slots for sentinels the salience rank STARVES regardless of cheapness —
    the detect-but-never-judge class (IRDM 0-for-14 with a fresh structural filing; VIAV admitted
    2026-08-03, surfaced 08-09, never judged; 34 active candidates vs 12 slots). Eligibility =
    any remaining sentinel (deliberately NO cheapness gate — cheapness stays the cheap-reserve's
    job); rank = fresh-event-on-active-lineage FIRST (``fresh_event``, a set of SYMBOLs — a new
    structural filing gets judged the next L1, the LUNR-gap close) → least-recently-judged
    (never-judged sorts first) → symbol asc. Unfilled ⇒ the same fail-closed motion backfill.
    ``fairness_m=0`` (the default) is byte-identical to the pre-amendment composition.

    Returns ``(selected, selection, displaced)`` where ``selection`` maps
    ``(SYMBOL, direction)`` → ``"reserve" | "fairness" | "rank"`` (per-proposal provenance, §6)
    and ``displaced`` lists the motion-ranked sentinel symbols that yielded their slots (§5 — the
    displacement is observable, never silent).
    """
    cands = list(candidates)
    hand = [c for c in cands if getattr(c, "sentinel_id", None) is None][:max_candidates]
    sent = [c for c in cands if getattr(c, "sentinel_id", None) is not None]
    slots = max_candidates - len(hand)
    k = min(max(int(reserve_k), 0), slots)
    m = min(max(int(fairness_m), 0), slots - k)
    motion_n = slots - k - m
    top_motion = sent[:motion_n]
    rest = sent[motion_n:]

    def _rkey(c):
        sym = c.symbol.upper()
        # never-judged ⇒ "" sorts before any ISO timestamp = least-recently-judged FIRST
        return (last_judged.get(sym, ""), float(cheap_eligible[sym]), sym)

    eligible = sorted((c for c in rest if c.symbol.upper() in cheap_eligible), key=_rkey)
    reserve = eligible[:k]
    reserve_ids = {id(c) for c in reserve}

    def _fkey(c):
        sym = c.symbol.upper()
        # fresh structural filing first (False<True inverted), then least-recently-judged, then symbol
        return (sym not in fresh_event, last_judged.get(sym, ""), sym)

    fair_pool = sorted((c for c in rest if id(c) not in reserve_ids), key=_fkey)
    fairness = fair_pool[:m]
    fairness_ids = {id(c) for c in fairness}

    taken = reserve_ids | fairness_ids
    backfill = [c for c in rest if id(c) not in taken][: (k - len(reserve)) + (m - len(fairness))]

    selected = hand + top_motion + reserve + fairness + backfill
    selected_ids = {id(c) for c in selected}
    displaced = [c.symbol for c in (hand + sent[:slots]) if id(c) not in selected_ids]
    selection = {
        (c.symbol.upper(), str(getattr(c, "direction", "")).lower()):
            ("reserve" if id(c) in reserve_ids
             else "fairness" if id(c) in fairness_ids
             else "rank")
        for c in selected
    }
    return selected, selection, displaced


def _error_proposal(candidate, *, reason: str, model_mix: dict) -> CouncilProposal:
    return CouncilProposal(
        theme=candidate.name, symbol=candidate.symbol, direction=candidate.direction,
        conviction="NEUTRAL", structural_vs_fad=None, weakest_point=reason,
        strategist_summary=f"dropped: {reason}", rationale={"error": reason},
        agent_outputs=[], cost_usd=0.0, model_mix=model_mix, include=False,
        sentinel_id=candidate.sentinel_id,
    )


def propose(
    candidates,
    *,
    router,
    config: dict,
    clock,
    news=None,
    fundamentals=None,
    analyst=None,
    catalysts=None,
    demo: bool = False,
    rng=None,
) -> list[CouncilProposal]:
    """Run the council over ``candidates`` (a list of ``themes.Theme``). Returns ALL proposals.

    The cost ledger lives on ``router.ledger`` (the caller reports it). Raises nothing — every
    failure mode is handled fail-closed (KILL / budget → empty; per-candidate error → dropped).
    """
    # 1. KILL switch FIRST — never spend on the council when halted.
    if kill_switch_active():
        log.warning("KILL switch engaged — council not invoked (no LLM spend).")
        return []

    council = config.get("council", {})
    max_candidates = int(council.get("max_candidates", 12))
    lookback = int(council.get("news_lookback_days", 90))
    as_of = clock.now()

    proposals: list[CouncilProposal] = []
    for candidate in list(candidates)[:max_candidates]:
        pack = (
            synthetic_context_pack(candidate, as_of=as_of)
            if demo
            else build_context_pack(candidate, news=news, as_of=as_of, lookback_days=lookback,
                                    fundamentals=fundamentals, analyst=analyst, catalysts=catalysts)
        )
        try:
            proposals.append(run_candidate(candidate, pack, router, rng=rng))
        except BudgetExceeded as e:
            # Over-budget → fail closed to ZERO proposals for the whole cycle (no entries).
            log.warning("Council over budget (%s) — proposing NOTHING this cycle (fail-closed).", e)
            return []
        except RouterError as e:
            # A single provider failed after retries → drop THIS candidate (it never trades).
            log.warning("Council dropped %s (%s) — provider error.", candidate.symbol, e)
            mix = {r: "/".join(router.provider_model(r)) for r in ("proposer", "adversary", "strategist")}
            proposals.append(_error_proposal(candidate, reason=f"provider_error: {e}", model_mix=mix))

    return proposals
