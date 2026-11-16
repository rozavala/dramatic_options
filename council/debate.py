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
from council.filters import FilterResult, apply_filter
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


def _fundamentals_telemetry(pack) -> dict:
    """§9 §5d fill telemetry that rides the proposal rationale on EVERY path (incl. early-exit, so
    an empty-corpus OR-leg MISS is visible to the grader). origin lets the grader split OR-leg
    health (hand-seed) from sentinel enrichment coverage."""
    return {"n_lines": len(getattr(pack, "fundamentals", []) or []),
            "status": getattr(pack, "fundamentals_status", None) or "empty",
            "origin": getattr(pack, "origin", "hand-seed")}


def _neutral_proposal(candidate: Theme, pack, *, reason: str, agent_outputs, model_mix, cost_usd
                      ) -> CouncilProposal:
    return CouncilProposal(
        theme=candidate.name, symbol=candidate.symbol, direction=candidate.direction,
        conviction="NEUTRAL", structural_vs_fad=None, weakest_point=reason,
        strategist_summary=f"dropped: {reason}",
        rationale={"dropped": reason, "fundamentals": _fundamentals_telemetry(pack)},
        agent_outputs=agent_outputs, cost_usd=cost_usd, model_mix=model_mix, include=False,
        sentinel_id=candidate.sentinel_id,
    )


def coerce_tri_criteria(sraw: dict, praw: dict, symbol: str) -> dict:
    """CGS §10.7 deterministic enforcement: the single coercion point, shared by the council of record
    (``run_candidate``) and the #456 repeat-read probe (PREREG_COUNCIL_GATE_SEPARATION §10.12) so both apply the
    identical rule (a lock-step test pins it to the pre-extraction inline code). Mutates and returns ``sraw``.

    Both raws are in scope, so the sanctioned strategist-or-proposer structural_vs_fad fallback applies, exactly as
    the §10.8 preview computed tri. Comparison semantics verbatim: exact string equality + ``is True`` identity (an
    explicit null/false is a deliberated NON-assertion → veto; an ABSENT key on an include row was already a
    parse_error upstream). Conviction is preserved (Brier substrate); the veto is recorded DISTINCT from parse_error,
    before AgentOutput captures sraw so it persists to council_agent_outputs.raw."""
    sf_resolved = sraw.get("structural_vs_fad") or praw.get("structural_vs_fad")
    tri_pass = (str(sf_resolved) == "structural"
                and sraw.get("under_narrated") is True and sraw.get("at_inflection") is True)
    if bool(sraw.get("include", False)) and not tri_pass:
        sraw["include"] = False
        sraw["criteria_veto"] = True
        sraw["criteria_veto_reason"] = (
            f"include=true but tri-criteria fail (s/f={sf_resolved} "
            f"u_narr={sraw.get('under_narrated')} at_infl={sraw.get('at_inflection')})")
        log.info("council criteria-veto %s: %s", symbol, sraw["criteria_veto_reason"])
    return sraw


def strategist_verdict(sraw: dict, praw: dict, pack, symbol: str) -> tuple[str, FilterResult]:
    """The strategist's post-processing of record: the quote-authenticity filter over its summary + weakest point
    (conviction dampened on a flag), then the §10.7 coercion. Returns ``(conviction, FilterResult)``; ``sraw`` is
    coerced in place. Shared with the #456 repeat-read probe so a repeat is post-processed exactly like the record."""
    sconf, sfr = apply_filter([str(sraw.get("summary", "")), str(sraw.get("weakest_point", ""))],
                              pack, confidence=sraw.get("conviction"),
                              accept_rendered_dates=True)
    coerce_tri_criteria(sraw, praw, symbol)
    return sconf, sfr


def run_candidate(candidate: Theme, pack, router, *, rng: random.Random | None = None,
                  repeat_capture: dict | None = None) -> CouncilProposal:
    """Run the three-role debate for one candidate. Returns a CouncilProposal (possibly NEUTRAL).

    May raise RouterError/BudgetExceeded from ``router.call`` — the caller (council.propose)
    handles those fail-closed.

    ``repeat_capture`` (#456, ``council.repeat_probe.enabled``; None = off, byte-identical): a dict the caller owns.
    For a candidate that reaches the strategist, ``repeat_capture[id(proposal)]`` receives the serialized pack + the
    sha256 of the strategist's user text, for the caller to persist beside the proposal row. Fail-soft: a capture
    error logs a WARNING and never touches the debate or the proposal.
    """
    rng = rng or random.Random()
    mix = _model_mix(router)

    # Early exit (no LLM spend): ungrounded evidence → NEUTRAL drop (SPEC §5).
    if not pack.grounded:
        return _neutral_proposal(candidate, pack, reason="ungrounded (no numeric evidence)",
                                 agent_outputs=[], model_mix=mix, cost_usd=0.0)

    # 1. Proposer — argues FOR the candidate's direction.
    sys, user = agents.proposer_prompt(pack)
    presp = router.call(role="proposer", system=sys, user=user)
    praw = _parsed("proposer", presp, agents.parse_proposer, candidate.symbol)
    pconf, pfr = apply_filter([str(praw.get("inflection_thesis", "")), *map(str, praw.get("cited", []))],
                              pack, confidence=praw.get("confidence"),
                              accept_rendered_dates=True)
    proposer_ao = AgentOutput(
        "proposer", presp.provider, presp.model, pconf, candidate.direction,
        None, praw, flagged_unsupported=pfr.flagged, cost_usd=presp.cost_usd,
        flagged_details=tuple(pfr.details),
    )
    if pconf == "NEUTRAL":  # proposer abstained → drop without spending on adversary/strategist
        return _neutral_proposal(candidate, pack, reason="proposer abstained (NEUTRAL)",
                                 agent_outputs=[proposer_ao], model_mix=mix, cost_usd=presp.cost_usd)

    # 2. Adversary — argues AGAINST the proposed direction (direction-relative).
    against_stance = agents.OPPOSITE.get(candidate.direction, "opposite")
    sys, user = agents.adversary_prompt(pack, praw)
    aresp = router.call(role="adversary", system=sys, user=user)
    araw = _parsed("adversary", aresp, agents.parse_adversary, candidate.symbol)
    aconf, afr = apply_filter([str(araw.get("counter_case", "")), str(araw.get("weakest_point", "")),
                               *map(str, araw.get("cited", []))], pack, confidence=araw.get("confidence"),
                              accept_rendered_dates=True)
    adversary_ao = AgentOutput(
        "adversary", aresp.provider, aresp.model, aconf, against_stance,
        str(araw.get("weakest_point", "")) or None, araw, flagged_unsupported=afr.flagged,
        cost_usd=aresp.cost_usd, flagged_details=tuple(afr.details),
    )

    # 3. Strategist — synthesize (randomized for/against order), conviction-dampened.
    for_first = rng.random() < 0.5
    sys, user = agents.strategist_prompt(pack, praw, araw, for_first=for_first)
    capture = _repeat_capture(pack, user, candidate.symbol) if repeat_capture is not None else None
    sresp = router.call(role="strategist", system=sys, user=user)
    sraw = _parsed("strategist", sresp, agents.parse_strategist, candidate.symbol)
    # The filter, then CGS §10.7 deterministic enforcement — the single coercion point (the only layer with BOTH
    # raws in scope). Both live in strategist_verdict / coerce_tri_criteria, shared with the #456 probe.
    sconf, sfr = strategist_verdict(sraw, praw, pack, candidate.symbol)

    strategist_ao = AgentOutput(
        "strategist", sresp.provider, sresp.model, sconf, str(sraw.get("direction", candidate.direction)),
        str(sraw.get("weakest_point", "")) or None, sraw, flagged_unsupported=sfr.flagged,
        cost_usd=sresp.cost_usd, flagged_details=tuple(sfr.details),
    )

    direction = str(sraw.get("direction", candidate.direction)).strip().lower()
    if direction not in VALID_DIRECTIONS:
        direction = candidate.direction
    total_cost = presp.cost_usd + aresp.cost_usd + sresp.cost_usd

    proposal = CouncilProposal(
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
                          "inflection_passed": araw.get("inflection_passed"), "confidence": aconf},
            "strategist": {"summary": sraw.get("summary"), "conviction": sconf, "include": sraw.get("include"),
                           "under_narrated": sraw.get("under_narrated"),
                           "at_inflection": sraw.get("at_inflection"),
                           "criteria_veto": bool(sraw.get("criteria_veto", False))},
            "fundamentals": _fundamentals_telemetry(pack),
        },
        agent_outputs=[proposer_ao, adversary_ao, strategist_ao],
        cost_usd=total_cost,
        model_mix=mix,
        include=bool(sraw.get("include", False)),
        sentinel_id=candidate.sentinel_id,
        under_narrated=sraw.get("under_narrated") if isinstance(sraw.get("under_narrated"), bool) else None,
        at_inflection=sraw.get("at_inflection") if isinstance(sraw.get("at_inflection"), bool) else None,
        criteria_veto=bool(sraw.get("criteria_veto", False)),
    )
    if capture is not None:
        repeat_capture[id(proposal)] = capture
    return proposal


def _repeat_capture(pack, strategist_user: str, symbol: str) -> dict | None:
    """The #456 capture for one candidate: the serialized pack (verified to round-trip) + the sha256 of the
    strategist's user text. Never raises: any error is a WARNING and the candidate is simply not captured."""
    try:
        from council.repeat_capture import capture_record

        return capture_record(pack, strategist_user)
    except Exception as e:  # noqa: BLE001 — measurement capture must never touch the council of record
        log.warning("repeat-probe capture failed for %s (non-fatal, not captured): %s", symbol, e)
        return None
