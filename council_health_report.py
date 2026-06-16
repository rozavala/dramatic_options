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
returns a degenerate row, or the cost can be anomalous — both are graded here. A genuine strategist NEUTRAL
**abstention** (a reasoned exclude — full schema, no parse_error) is a VALID round-trip outcome (the Master
Strategist declining a weak name), surfaced as ``strategist_abstained`` and distinct from a fail-closed
coercion (which carries parse_error and IS degraded).

    python council_health_report.py [run_id]      # latest council run if run_id omitted

To grade the LIVE box from a worktree, pass a read-only connection to the live DB:
    council_l1_health(sqlite3.connect("file:/.../dramatic_options.db?mode=ro", uri=True), ...)
"""

from __future__ import annotations

import json
import statistics

import state
from council.proposal import CONVICTION_LEVELS, normalize_conviction, passes_floor

OPPOSITE = {"bullish": "bearish", "bearish": "bullish"}
_ROLES = ("proposer", "adversary", "strategist")
# A strategist verdict is VALID if it DELIBERATED: a real conviction (LOW-EXTREME) or a genuine NEUTRAL
# abstention (a reasoned exclude — full schema, no parse_error). A fail-closed coercion carries parse_error
# (caught by any_parse_error) and is NOT credited here. (normalize_conviction maps anything unrecognized →
# NEUTRAL, so the parse_error flag — not the vocab — is the real abstention-vs-failure discriminator.)
_STRATEGIST_VALID = CONVICTION_LEVELS + ("NEUTRAL",)


def _is_parse_error(raw) -> bool:
    if not raw:
        return False
    try:
        return bool(json.loads(raw).get("parse_error")) if isinstance(raw, str) else bool(raw.get("parse_error"))
    except Exception:  # noqa: BLE001 — non-JSON raw can't be a structured parse_error
        return '"parse_error": true' in str(raw)


def _fundamentals_telemetry(rationale) -> dict | None:
    """Pull the §9 fill telemetry ({n_lines, status, origin}) that rides every proposal's rationale."""
    if not rationale:
        return None
    try:
        d = json.loads(rationale) if isinstance(rationale, str) else rationale
        f = d.get("fundamentals")
        return f if isinstance(f, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _fundamentals_summary(props) -> dict:
    """§9 §5d: per-run fill health SPLIT BY ORIGIN — a hand-seed median near 0 = a SEC outage
    starving the OR-leg (real); a sentinel median near 0 = thin sentinel corpus (cosmetic — they're
    markers-grounded regardless). Pooled, those are indistinguishable; split, the OR-leg-band miss
    is interpretable."""
    buckets: dict[str, dict] = {}
    for p in props:
        f = _fundamentals_telemetry(p["rationale"])
        if not f:
            continue
        b = buckets.setdefault(str(f.get("origin", "hand-seed")),
                               {"lines": [], "ok": 0, "partial": 0, "empty": 0})
        b["lines"].append(int(f.get("n_lines", 0) or 0))
        st = str(f.get("status") or "empty")
        if st in ("ok", "partial", "empty"):
            b[st] += 1
    return {o: {"n": len(b["lines"]),
                "median_lines": statistics.median(b["lines"]) if b["lines"] else None,
                "ok": b["ok"], "partial": b["partial"], "empty": b["empty"]}
            for o, b in buckets.items()}


def _is_criteria_veto(raw) -> bool:
    """A strategist include coerced false for violating its own asserted §10.7 tri-criteria —
    a DELIBERATED outcome (valid conviction, no parse_error), recorded distinct from parse_error."""
    if not raw:
        return False
    try:
        return bool(json.loads(raw).get("criteria_veto")) if isinstance(raw, str) else bool(raw.get("criteria_veto"))
    except Exception:  # noqa: BLE001
        return '"criteria_veto": true' in str(raw)


def latest_council_run(conn) -> int | None:
    row = conn.execute("SELECT MAX(run_id) AS r FROM council_proposals").fetchone()
    return int(row["r"]) if row and row["r"] is not None else None


def _config_floor() -> str:
    """The live conviction floor (config-driven; mirrors the gate + dashboard funnel). Fail-soft to MODERATE."""
    try:
        from config_loader import load_config
        return (load_config().get("council", {}) or {}).get("conviction_floor", "MODERATE")
    except Exception:  # noqa: BLE001 — a config-read hiccup must never crash the read-only grader
        return "MODERATE"


def council_l1_health(conn, *, run_id: int | None = None, floor: str | None = None, page_rate: float = 0.5) -> dict:
    """Grade one council run against the checklist. ``run_id`` defaults to the latest council run.

    ``floor`` defaults to config ``council.conviction_floor`` (NOT a hardcoded MODERATE) so the grade can
    never silently diverge from the gate/dashboard funnel if the mandate floor is ever retightened (#37 class).
    """
    run_id = run_id if run_id is not None else latest_council_run(conn)
    if run_id is None:
        return {"run_id": None, "verdict": "NO_COUNCIL", "notes": ["no council run recorded"]}
    if floor is None:
        floor = _config_floor()

    hr = conn.execute("SELECT council_health FROM runs WHERE id = ?", (run_id,)).fetchone()
    council_health = hr["council_health"] if hr else None
    parse = state.council_parse_health(conn, run_id)

    props = conn.execute(
        "SELECT id, symbol, direction, conviction, rationale FROM council_proposals WHERE run_id = ?",
        (run_id,)
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

    roundtrip, adv_dir_rel, strat_valid, strat_abstained, strat_criteria_vetoed, any_parse_error = [], 0, 0, 0, 0, False
    for p in props:
        roles = by_prop.get(p["id"], {})
        if any(_is_parse_error(a["raw"]) for a in roles.values()):
            any_parse_error = True
        if {"proposer", "adversary", "strategist"} <= set(roles):   # the full round-trip fired for this name
            roundtrip.append(p["id"])
            if (roles["adversary"]["stance"] or "").lower() == OPPOSITE.get((p["direction"] or "").lower()):
                adv_dir_rel += 1                                     # bull case on a bearish name (direction-relative)
            strat = roles["strategist"]
            strat_conv = normalize_conviction(strat["confidence"])
            if not _is_parse_error(strat["raw"]) and strat_conv in _STRATEGIST_VALID:
                strat_valid += 1                                    # a real conviction OR a reasoned NEUTRAL abstain
                if strat_conv == "NEUTRAL":
                    strat_abstained += 1
            if _is_criteria_veto(strat["raw"]):
                strat_criteria_vetoed += 1                          # deliberated; valid, never degrades

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
                      "strategist_valid_conviction": strat_valid, "strategist_abstained": strat_abstained,
                      "strategist_criteria_vetoed": strat_criteria_vetoed,
                      "any_role_parse_error": any_parse_error},
        "cost_usd": cost, "cost_by_role": {r: round(c, 6) for r, c in cost_by_role.items()},
        "fundamentals": _fundamentals_summary(props),
        "notes": [
            "NO-ENTRY is HEALTHY — this grades parseable DELIBERATION, not a booked position.",
            "ROUNDTRIP_CONFIRMED on one L1 is necessary, not sufficient — the window needs >=2 clean L1s.",
            "PROPOSER_CLEAN_NO_ROUNDTRIP = the proposer parses but judged all NEUTRAL (reasoned); the "
            "adversary/strategist are still live-unconfirmed — needs an above-floor proposal to exercise them.",
            "strategist_criteria_vetoed > 0 is anomalous-but-non-degrading (deliberated; the §10.7 prompt "
            "makes the criteria HARD, so the §10.8 expected shape is ~0 — repeated include∧tri-false = model "
            "prompt-compliance drift the deterministic rule masks from the trade path; monitor-only).",
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
