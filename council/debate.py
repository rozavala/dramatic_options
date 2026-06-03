"""Debate orchestration (T2): Proposer → Adversary → Strategist → one CouncilProposal.

Per candidate: the Proposer argues for the candidate's direction, the Adversary argues against
it (direction-relative), the Strategist synthesizes a verdict + conviction. The
quote-authenticity filter dampens any agent that cites unsupported figures/quotes. The order in
which the strategist sees the for/against cases is randomized (position-bias guard) and recorded.

Cost discipline + the early-exit rule are honored by **not calling the LLM** when the pack is
ungrounded or the proposer itself abstains (NEUTRAL) — the candidate is dropped having spent the
minimum. Router/budget errors propagate to ``council.propose`` (fail-closed).
"""

from __future__ import annotations

import logging
import random

from council import agents
from council.filters import apply_filter
from council.proposal import AgentOutput, CouncilProposal, normalize_conviction
from themes import VALID_DIRECTIONS, Theme

log = logging.getLogger("council.debate")


def _parsed(role: str, resp, parser, symbol: str) -> dict:
    """Parse a role response, threading the forensic finish_reason/thoughts into the fallback and
    logging LOUD on a parse/shape failure (the per-call signal; the cycle-level page is in the
    orchestrator). A failure still resolves NEUTRAL → fail-closed, never traded."""
    raw = parser(resp.text, finish_reason=resp.finish_reason, thoughts_tokens=resp.thoughts_tokens)
    if raw.get("parse_error"):
        log.warning("council %s parse-fail %s/%s for %s: %s (finish=%s, thoughts=%s)", role,
                    resp.provider, resp.model, symbol, raw.get("validation_error"),
                    resp.finish_reason, resp.thoughts_tokens)
    return raw


def _model_mix(router) -> dict:
    mix = {}
    for role in ("proposer", "adversary", "strategist"):
        prov, model = router.provider_model(role)
        mix[role] = f"{prov}/{model}"
    return mix


def _neutral_proposal(candidate: Theme, *, reason: str, agent_outputs, model_mix, cost_usd) -> CouncilProposal:
    return CouncilProposal(
        theme=candidate.name, symbol=candidate.symbol, direction=candidate.direction,
        conviction="NEUTRAL", structural_vs_fad=None, weakest_point=reason,
        strategist_summary=f"dropped: {reason}", rationale={"dropped": reason},
        agent_outputs=agent_outputs, cost_usd=cost_usd, model_mix=model_mix, include=False,
        sentinel_id=candidate.sentinel_id,
    )


def run_candidate(candidate: Theme, pack, router, *, rng: random.Random | None = None) -> CouncilProposal:
    """Run the three-role debate for one candidate. Returns a CouncilProposal (possibly NEUTRAL).

    May raise RouterError/BudgetExceeded from ``router.call`` — the caller (council.propose)
    handles those fail-closed.
    """
    rng = rng or random.Random()
    mix = _model_mix(router)

    # Early exit (no LLM spend): ungrounded evidence → NEUTRAL drop (SPEC §5).
    if not pack.grounded:
        return _neutral_proposal(candidate, reason="ungrounded (no numeric evidence)",
                                 agent_outputs=[], model_mix=mix, cost_usd=0.0)

    # 1. Proposer — argues FOR the candidate's direction.
    sys, user = agents.proposer_prompt(pack)
    presp = router.call(role="proposer", system=sys, user=user)
    praw = _parsed("proposer", presp, agents.parse_proposer, candidate.symbol)
    pconf, pfr = apply_filter([str(praw.get("inflection_thesis", "")), *map(str, praw.get("cited", []))],
                              pack, confidence=praw.get("confidence"))
    proposer_ao = AgentOutput(
        "proposer", presp.provider, presp.model, pconf, candidate.direction,
        None, praw, flagged_unsupported=pfr.flagged, cost_usd=presp.cost_usd,
    )
    if pconf == "NEUTRAL":  # proposer abstained → drop without spending on adversary/strategist
        return _neutral_proposal(candidate, reason="proposer abstained (NEUTRAL)",
                                 agent_outputs=[proposer_ao], model_mix=mix, cost_usd=presp.cost_usd)

    # 2. Adversary — argues AGAINST the proposed direction (direction-relative).
    against_stance = agents.OPPOSITE.get(candidate.direction, "opposite")
    sys, user = agents.adversary_prompt(pack, praw)
    aresp = router.call(role="adversary", system=sys, user=user)
    araw = _parsed("adversary", aresp, agents.parse_adversary, candidate.symbol)
    aconf, afr = apply_filter([str(araw.get("counter_case", "")), str(araw.get("weakest_point", "")),
                               *map(str, araw.get("cited", []))], pack, confidence=araw.get("confidence"))
    adversary_ao = AgentOutput(
        "adversary", aresp.provider, aresp.model, aconf, against_stance,
        str(araw.get("weakest_point", "")) or None, araw, flagged_unsupported=afr.flagged,
        cost_usd=aresp.cost_usd,
    )

    # 3. Strategist — synthesize (randomized for/against order), conviction-dampened.
    for_first = rng.random() < 0.5
    sys, user = agents.strategist_prompt(pack, praw, araw, for_first=for_first)
    sresp = router.call(role="strategist", system=sys, user=user)
    sraw = _parsed("strategist", sresp, agents.parse_strategist, candidate.symbol)
    sconf, sfr = apply_filter([str(sraw.get("summary", "")), str(sraw.get("weakest_point", ""))],
                              pack, confidence=sraw.get("conviction"))
    strategist_ao = AgentOutput(
        "strategist", sresp.provider, sresp.model, sconf, str(sraw.get("direction", candidate.direction)),
        str(sraw.get("weakest_point", "")) or None, sraw, flagged_unsupported=sfr.flagged,
        cost_usd=sresp.cost_usd,
    )

    direction = str(sraw.get("direction", candidate.direction)).strip().lower()
    if direction not in VALID_DIRECTIONS:
        direction = candidate.direction
    total_cost = presp.cost_usd + aresp.cost_usd + sresp.cost_usd

    return CouncilProposal(
        theme=str(sraw.get("theme", candidate.name)) or candidate.name,
        symbol=candidate.symbol,
        direction=direction,
        conviction=normalize_conviction(sconf),
        structural_vs_fad=sraw.get("structural_vs_fad") or praw.get("structural_vs_fad"),
        weakest_point=str(sraw.get("weakest_point", "")) or araw.get("weakest_point"),
        strategist_summary=str(sraw.get("summary", "")),
        rationale={
            "order": "for_first" if for_first else "against_first",
            "proposer": {"thesis": praw.get("inflection_thesis"), "confidence": pconf,
                         "structural_vs_fad": praw.get("structural_vs_fad")},
            "adversary": {"counter_case": araw.get("counter_case"), "weakest_point": araw.get("weakest_point"),
                          "already_consensus": araw.get("already_consensus"), "is_fad": araw.get("is_fad"),
                          "confidence": aconf},
            "strategist": {"summary": sraw.get("summary"), "conviction": sconf, "include": sraw.get("include")},
        },
        agent_outputs=[proposer_ao, adversary_ao, strategist_ao],
        cost_usd=total_cost,
        model_mix=mix,
        include=bool(sraw.get("include", False)),
        sentinel_id=candidate.sentinel_id,
    )
