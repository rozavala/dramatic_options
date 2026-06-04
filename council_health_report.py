"""Read-only council L1 health report — the operator's "what healthy looks like" checklist, CODIFIED.

The council's first confirmed live 3-role round-trip gates T4-unlock condition (1). L1 #37 silently
fail-closed (the Gemini-3.x thinking-starvation), so the xai adversary + anthropic strategist never fired.
This turns the prose checklist into a deterministic, re-runnable read over the journal so every L1 in the
healthy window is graded the SAME way (read-only — it never trades).

**The nuance the verdict encodes:** a clean-but-all-NEUTRAL cycle confirms only that the PROPOSER parses;
the full 3-role round-trip needs ≥1 above-floor proposal (the proposer short-circuits the adversary +
strategist on NEUTRAL — `debate.py`). And a **NO-ENTRY outcome is HEALTHY** (the IV gate disposing rich
convexity is the design) — this grades whether the council DELIBERATED parseably, not whether a position
appeared. "no parse-fail page" is a FALSE all-clear on its own: a proposer can fire while the adversary
returns a degenerate row, or the cost can be anomalous — both are graded here.

    python council_health_report.py [run_id]      # latest council run if run_id omitted

To grade the LIVE box from a worktree, pass a read-only connection to the live DB:
    council_l1_health(sqlite3.connect("file:/.../dramatic_options.db?mode=ro", uri=True), ...)
"""

from __future__ import annotations

import json

import state
from council.proposal import CONVICTION_LEVELS, normalize_conviction, passes_floor

OPPOSITE = {"bullish": "bearish", "bearish": "bullish"}
_ROLES = ("proposer", "adversary", "strategist")


def _is_parse_error(raw) -> bool:
    if not raw:
        return False
    try:
        return bool(json.loads(raw).get("parse_error")) if isinstance(raw, str) else bool(raw.get("parse_error"))
    except Exception:  # noqa: BLE001 — non-JSON raw can't be a structured parse_error
        return '"parse_error": true' in str(raw)


def latest_council_run(conn) -> int | None:
    row = conn.execute("SELECT MAX(run_id) AS r FROM council_proposals").fetchone()
    return int(row["r"]) if row and row["r"] is not None else None


def council_l1_health(conn, *, run_id: int | None = None, floor: str = "MODERATE", page_rate: float = 0.5) -> dict:
    """Grade one council run against the checklist. ``run_id`` defaults to the latest council run."""
    run_id = run_id if run_id is not None else latest_council_run(conn)
    if run_id is None:
        return {"run_id": None, "verdict": "NO_COUNCIL", "notes": ["no council run recorded"]}

    hr = conn.execute("SELECT council_health FROM runs WHERE id = ?", (run_id,)).fetchone()
    council_health = hr["council_health"] if hr else None
    parse = state.council_parse_health(conn, run_id)

    props = conn.execute(
        "SELECT id, symbol, direction, conviction FROM council_proposals WHERE run_id = ?", (run_id,)
    ).fetchall()
    aos = conn.execute(
        "SELECT ao.proposal_id, ao.role, ao.confidence, ao.stance, ao.cost_usd, ao.raw "
        "FROM council_agent_outputs ao JOIN council_proposals cp ON cp.id = ao.proposal_id "
        "WHERE cp.run_id = ?", (run_id,)
    ).fetchall()

    by_prop: dict = {}
    cost_by_role: dict = {r: 0.0 for r in _ROLES}
    for a in aos:
        by_prop.setdefault(a["proposal_id"], {})[a["role"]] = a
        if a["role"] in cost_by_role:
            cost_by_role[a["role"]] += float(a["cost_usd"] or 0.0)

    roundtrip, adv_dir_rel, strat_valid, any_parse_error = [], 0, 0, False
    for p in props:
        roles = by_prop.get(p["id"], {})
        if any(_is_parse_error(a["raw"]) for a in roles.values()):
            any_parse_error = True
        if {"proposer", "adversary", "strategist"} <= set(roles):   # the full round-trip fired for this name
            roundtrip.append(p["id"])
            if (roles["adversary"]["stance"] or "").lower() == OPPOSITE.get((p["direction"] or "").lower()):
                adv_dir_rel += 1                                     # bull case on a bearish name (direction-relative)
            if normalize_conviction(roles["strategist"]["confidence"]) in CONVICTION_LEVELS:
                strat_valid += 1

    cost = round(sum(cost_by_role.values()), 6)
    above_floor = sum(1 for p in props if passes_floor(p["conviction"], floor))

    if council_health == "parse_fail" or (parse["called"] >= 2 and parse["rate"] >= page_rate):
        verdict = "PARSE_FAIL"                       # the #37 bug — FAIL (do NOT start the window)
    elif not roundtrip:
        verdict = "PROPOSER_CLEAN_NO_ROUNDTRIP"      # proposer parses, but all NEUTRAL → adv/strat never fired
    elif any_parse_error or adv_dir_rel < len(roundtrip) or strat_valid < len(roundtrip) or cost <= 0:
        verdict = "ROUNDTRIP_DEGRADED"               # fired but off: degenerate row / not direction-relative / $0
    else:
        verdict = "ROUNDTRIP_CONFIRMED"              # PASS — a full, parseable, direction-relative 3-role round-trip

    return {
        "run_id": run_id,
        "council_health": council_health,
        "verdict": verdict,
        "proposer": {"called": parse["called"], "parse_failed": parse["parse_failed"],
                     "parse_fail_rate": round(parse["rate"], 4), "page_would_fire": parse["called"] >= 2
                     and parse["rate"] >= page_rate, "above_floor_proposals": above_floor},
        "roundtrip": {"n": len(roundtrip), "adversary_direction_relative": adv_dir_rel,
                      "strategist_valid_conviction": strat_valid, "any_role_parse_error": any_parse_error},
        "cost_usd": cost, "cost_by_role": {r: round(c, 6) for r, c in cost_by_role.items()},
        "notes": [
            "NO-ENTRY is HEALTHY — this grades parseable DELIBERATION, not a booked position.",
            "ROUNDTRIP_CONFIRMED on one L1 is necessary, not sufficient — the window needs >=2 clean L1s.",
            "PROPOSER_CLEAN_NO_ROUNDTRIP = the proposer parses but judged all NEUTRAL (reasoned); the "
            "adversary/strategist are still live-unconfirmed — needs an above-floor proposal to exercise them.",
        ],
    }


def main() -> int:
    import sys

    from config_loader import load_config
    conn = state.get_db(load_config())
    run_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print(json.dumps(council_l1_health(conn, run_id=run_id), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
