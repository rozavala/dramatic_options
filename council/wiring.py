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
from council.council import compose_judged_set, propose
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
    fundamentals=None,
    analyst=None,
    catalysts=None,
    demo: bool = False,
    run_id: int | None = None,
    rng=None,
):
    """Returns ``list[Theme]`` (the tradeable survivors, each carrying its proposal_id).

    Side effects: persists all proposals + agent outputs. The cost ledger is on ``router.ledger``
    (the caller reports it).
    """
    # Gate-cheap RESERVE (PREREG gate_cheap_reserve, FROZEN 2026-07-02) — composition-only:
    # replaces the plain [:max_candidates] motion-rank truncation with hand-seeds + top-(slots−K)
    # motion + K reserve slots for gate-cheap names the salience rank starves. OFF (byte-identical
    # to the old slice) unless council.cheap_reserve_slots > 0. Membership changes; prompts, gate
    # values, and sizing inputs never do (the §10 seam guard).
    council_cfg = config.get("council", {})
    reserve_k = int(council_cfg.get("cheap_reserve_slots", 0) or 0)
    selection: dict = {}
    if reserve_k > 0 and conn is not None:
        cheap = state.gate_cheap_reads(
            conn, now=clock.now(),
            max_age_td=int(council_cfg.get("cheap_reserve_staleness_td", 5)),
        )
        candidates, selection, displaced = compose_judged_set(
            candidates,
            max_candidates=int(council_cfg.get("max_candidates", 12)),
            reserve_k=reserve_k,
            cheap_eligible=cheap,
            last_judged=state.council_last_judged(conn),
        )
        n_res = sum(1 for v in selection.values() if v == "reserve")
        # §5: the displacement is observable, never silent — logged every cycle, even at zero.
        log.info(
            "Cheap-reserve: k=%d filled=%d eligible=%d reserve=%s displaced=%s",
            reserve_k, n_res, len(cheap),
            sorted(sym for (sym, _d), v in selection.items() if v == "reserve"),
            displaced,
        )
    proposals = propose(candidates, router=router, config=config, clock=clock,
                        news=news, fundamentals=fundamentals, analyst=analyst,
                        catalysts=catalysts, demo=demo, rng=rng)
    floor = config.get("council", {}).get("conviction_floor", "MODERATE")
    tradeable_ids = {id(p) for p in select_for_trade(proposals, floor=floor)}
    as_of_iso = clock.now().isoformat()

    themes = []
    n_dropped = 0
    for p in proposals:
        is_trade = id(p) in tradeable_ids
        # finding #1 / §7.1: stamp when the markers the binding at_inflection leg judged were last
        # recomputed (the sentinel's last_seen_at AT JUDGMENT — same cycle, so it matches the markers
        # actually read). Frozen on the row so marker-age is non-corruptible; None for hand-seeds.
        markers_asof = None
        if p.sentinel_id is not None:
            srow = state.sentinel_by_id(conn, p.sentinel_id)
            markers_asof = srow["last_seen_at"] if srow else None
        # §6 per-proposal provenance: selection = "reserve" | "rank" rides the rationale JSON
        # (the §9-integration telemetry channel) ONLY when the reserve is active — the persisted
        # rationale stays byte-identical with the reserve off.
        rationale = p.rationale
        if selection and isinstance(rationale, dict):
            sel = selection.get((p.symbol.upper(), str(p.direction).lower()), "rank")
            rationale = {**rationale, "selection": sel}
        proposal_id = state.record_council_proposal(
            conn, run_id=run_id, as_of=as_of_iso, theme=p.theme, symbol=p.symbol,
            direction=p.direction, conviction=p.conviction, structural_vs_fad=p.structural_vs_fad,
            weakest_point=p.weakest_point, rationale=rationale,
            strategist_summary=p.strategist_summary, cost_usd=p.cost_usd, model_mix=p.model_mix,
            status="proposed" if is_trade else "dropped", sentinel_id=p.sentinel_id,
            markers_asof=markers_asof,
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

    n_criteria_vetoed = sum(1 for p in proposals if p.criteria_veto)
    log.info("Council: %d proposal(s) → %d to gates, %d dropped (floor=%s, criteria-vetoed=%d)",
             len(proposals), len(themes), n_dropped, floor, n_criteria_vetoed)
    return themes
