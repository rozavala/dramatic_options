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


def _error_proposal(candidate, *, reason: str, model_mix: dict) -> CouncilProposal:
    return CouncilProposal(
        theme=candidate.name, symbol=candidate.symbol, direction=candidate.direction,
        conviction="NEUTRAL", structural_vs_fad=None, weakest_point=reason,
        strategist_summary=f"dropped: {reason}", rationale={"error": reason},
        agent_outputs=[], cost_usd=0.0, model_mix=model_mix, include=False,
    )


def propose(
    candidates,
    *,
    router,
    config: dict,
    clock,
    news=None,
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
            else build_context_pack(candidate, news=news, as_of=as_of, lookback_days=lookback)
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
