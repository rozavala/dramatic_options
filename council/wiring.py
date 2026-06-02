"""Council → deterministic-loop glue (T2): propose, persist, select, project to Themes.

This is the orchestrator's single entry into the council. It runs ``council.propose``, records
EVERY proposal + its per-agent outputs (the forward-scoring substrate — guardrail §6), then
applies the conviction floor to pick the survivors and projects them to ``Theme``s the
*unchanged* deterministic paper loop consumes. Persistence + selection are separated so the
record is complete (dropped proposals included) while only survivors reach the gates.
"""

from __future__ import annotations

import logging

import state
from council.council import propose
from council.proposal import select_for_trade

log = logging.getLogger("council.wiring")


def council_to_themes(
    conn,
    *,
    candidates,
    router,
    config: dict,
    clock,
    news=None,
    demo: bool = False,
    run_id: int | None = None,
    rng=None,
):
    """Returns ``list[Theme]`` (the tradeable survivors, each carrying its proposal_id).

    Side effects: persists all proposals + agent outputs. The cost ledger is on ``router.ledger``
    (the caller reports it).
    """
    proposals = propose(candidates, router=router, config=config, clock=clock,
                        news=news, demo=demo, rng=rng)
    floor = config.get("council", {}).get("conviction_floor", "MODERATE")
    tradeable_ids = {id(p) for p in select_for_trade(proposals, floor=floor)}
    as_of_iso = clock.now().isoformat()

    themes = []
    n_dropped = 0
    for p in proposals:
        is_trade = id(p) in tradeable_ids
        proposal_id = state.record_council_proposal(
            conn, run_id=run_id, as_of=as_of_iso, theme=p.theme, symbol=p.symbol,
            direction=p.direction, conviction=p.conviction, structural_vs_fad=p.structural_vs_fad,
            weakest_point=p.weakest_point, rationale=p.rationale,
            strategist_summary=p.strategist_summary, cost_usd=p.cost_usd, model_mix=p.model_mix,
            status="proposed" if is_trade else "dropped", sentinel_id=p.sentinel_id,
        )
        for ao in p.agent_outputs:
            state.record_agent_output(
                conn, proposal_id=proposal_id, role=ao.role, provider=ao.provider, model=ao.model,
                confidence=ao.confidence, stance=ao.stance, weakest_point=ao.weakest_point,
                raw=ao.raw, flagged_unsupported=ao.flagged_unsupported, cost_usd=ao.cost_usd,
            )
        if is_trade:
            themes.append(p.to_theme(proposal_id))
        else:
            n_dropped += 1

    log.info("Council: %d proposal(s) → %d to gates, %d dropped (floor=%s)",
             len(proposals), len(themes), n_dropped, floor)
    return themes
