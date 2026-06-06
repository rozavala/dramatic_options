"""Forward-only scoring (T2): Brier + per-agent contribution. PREREG §7, guardrail §6.

**The council is validated FORWARD, never backtested** (training-data lookahead) — there is no
replay-on-history entry point here, by design. A proposal is a forward prediction ("the proposed
direction works over the hold"); it resolves only at position close, months later, so these are
*substrate* functions — live Brier/contribution numbers need years of resolved holds to mean
anything (PREREG §7).

**Outcome resolution is corrected for how the monitor actually closes** (`underlying_price_of`
is consulted only at expiry today): derive the outcome from data on hand where unambiguous, and
only require spot where it isn't —
  - profit-take  → favorable (a 10× far-OTM mark IS the move),
  - expiry       → favorable iff intrinsic > 0,
  - time-stop    → needs the underlying: favorable iff it moved in the proposed direction,
  - otherwise / spot unavailable → **None (unresolved)** — never fabricate an outcome.

**Caveat (in code on purpose):** this binary directional Brier is a *coarse proxy* — it scores a
10× winner and a one-cent drift identically and is noisy across the many expire-worthless losers.
It under-measures the real "cheap convexity paid off" claim; it is adequate only as a T2 substrate.
"""

from __future__ import annotations

from dramatic_options.council.proposal import normalize_conviction

DEFAULT_CONVICTION_TO_PROB = {"LOW": 0.55, "MODERATE": 0.65, "HIGH": 0.75, "EXTREME": 0.85}


def conviction_prob(conviction: str | None, mapping: dict | None = None) -> float:
    """Map a conviction to a probability the proposed direction works. NEUTRAL/unknown → 0.5."""
    m = mapping or DEFAULT_CONVICTION_TO_PROB
    return float(m.get(normalize_conviction(conviction), 0.5))


def brier(prob: float, outcome: int) -> float:
    """Brier score = (prob − outcome)². Lower is better."""
    return (float(prob) - float(outcome)) ** 2


def outcome_from_close(
    reason: str,
    *,
    direction: str,
    intrinsic: float | None = None,
    exit_spot: float | None = None,
    entry_spot: float | None = None,
) -> int | None:
    """Binary forward outcome at close: 1 favorable / 0 unfavorable / None unresolved.

    ``reason`` is the monitor's close reason (``profit_take_*`` / ``time_stop_*`` / ``expiry``).
    """
    r = (reason or "").lower()
    if r.startswith("profit_take"):
        return 1
    if r.startswith("expiry"):
        return 1 if (intrinsic is not None and intrinsic > 0) else 0
    # time-stop and anything else: need the underlying move.
    if exit_spot is not None and entry_spot is not None and entry_spot > 0:
        moved_up = exit_spot > entry_spot
        return int(moved_up) if direction == "bullish" else int(not moved_up)
    return None


def resolve(
    reason: str,
    *,
    direction: str,
    conviction: str | None,
    intrinsic: float | None = None,
    exit_spot: float | None = None,
    entry_spot: float | None = None,
    conviction_to_prob: dict | None = None,
) -> tuple[int | None, float | None]:
    """Resolve a closed proposal → (outcome, brier). (None, None) when genuinely unresolved."""
    outcome = outcome_from_close(
        reason, direction=direction, intrinsic=intrinsic, exit_spot=exit_spot, entry_spot=entry_spot,
    )
    if outcome is None:
        return None, None
    return outcome, brier(conviction_prob(conviction, conviction_to_prob), outcome)


def agent_contribution(
    agent_outputs, outcome: int, proposed_direction: str, conviction_to_prob: dict | None = None
) -> dict[str, float]:
    """Per-agent forward Brier: each agent's confident stance vs the realized outcome.

    An agent's predicted probability that the PROPOSED direction works = its confidence-prob if it
    argued *for* that direction, else (1 − that). Lower Brier = the agent's stance was the better
    forecast. (Substrate — not persisted per-agent in T2; see module docstring.)
    """
    out: dict[str, float] = {}
    for a in agent_outputs:
        toward_stance = conviction_prob(a.confidence, conviction_to_prob)
        pred = toward_stance if a.stance == proposed_direction else (1.0 - toward_stance)
        out[a.role] = brier(pred, outcome)
    return out
