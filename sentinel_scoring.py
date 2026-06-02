"""Forward-only sentinel scoring (T3) — reuse council.scoring; never backtested (guardrail §6).

A sentinel is a forward prediction ("this discovered name is a real cheap-convexity inflection in
the framed direction"). It resolves three ways, months later:

  - **traded → closed:** outcome + Brier (direction) AND the **realized multiple** (magnitude —
    binary Brier alone is wrong for a tail-finder), via :func:`resolve_traded_sentinel`.
  - **never traded (council-dropped / gate-vetoed) + the random control cohort:** a label-only
    **reference forward-return** (:func:`resolve_reference`), the only way to score the prescreen
    *independent of the IV gate's filtering*.
  - genuinely unresolved → **None** (never fabricated).

**Survivorship guard:** :func:`reference_return_from_bars` — if the bar series terminates early
(an acquisition = the far-OTM jackpot, or a delisting), it returns the realized return **to the
last available bar** with a ``terminal`` tag, NOT None — else the upper-tail test the controls
exist for is structurally blind to the fattest part of the tail (``Adjustment.ALL`` covers
splits/divs, not M&A/delisting). *(Caveat: a delisting's last bar can overstate vs a true zero —
refine later from the tag.)*
"""

from __future__ import annotations

from datetime import datetime, timedelta

from council.scoring import brier, conviction_prob, outcome_from_close


def reference_return_from_bars(
    entry_close: float | None, fwd_closes: list[float], horizon_days: int, *, terminated: bool
) -> tuple[float | None, str | None]:
    """Pure core of the reference return + survivorship guard. Returns (return, terminal_event).

    'horizon' = the full window elapsed; 'terminated' = the series ended early (return to the last
    bar, not None); (None, None) = not enough data yet AND not terminated → genuinely unresolved.
    """
    if entry_close is None or entry_close <= 0:
        return None, None
    if len(fwd_closes) >= horizon_days:
        return fwd_closes[horizon_days - 1] / entry_close - 1.0, "horizon"
    if fwd_closes and terminated:
        return fwd_closes[-1] / entry_close - 1.0, "terminated"
    return None, None


def resolve_reference(
    market, symbol: str, as_of: datetime, horizon_days: int, *, now: datetime
) -> tuple[float | None, str | None]:
    """Reference forward-return for a name from ``as_of`` over ``horizon_days``, resolved at ``now``.

    Uses the tested label-only ``MarketData.forward_return`` for the common (full-horizon) case,
    then adds the survivorship guard when the series ended early."""
    r = market.forward_return(symbol, as_of, horizon_days)
    if r is not None:
        return r, "horizon"
    entry = market.latest_price(symbol, as_of)
    fwd = [b for b in market.cache.read_between("bars", symbol, as_of, now)
           if datetime.fromisoformat(b["ts"]) > as_of]
    horizon_cal_end = as_of + timedelta(days=int(horizon_days * 1.6) + 4)
    terminated = now >= horizon_cal_end and 0 < len(fwd) < horizon_days
    fwd_closes = [b["close"] for b in fwd]
    return reference_return_from_bars(entry, fwd_closes, horizon_days, terminated=terminated)


def resolve_traded_sentinel(
    *,
    reason: str,
    direction: str,
    conviction: str | None,
    intrinsic: float | None = None,
    exit_spot: float | None = None,
    entry_spot: float | None = None,
    entry_premium: float | None = None,
    realized_pnl: float | None = None,
    conviction_to_prob: dict | None = None,
) -> tuple[int | None, float | None, float | None]:
    """A traded sentinel's close → (outcome, brier, realized_multiple).

    ``realized_multiple`` = exit value ÷ entry premium (0.0 = total loss, ~10 = a 10× winner) —
    the tail-aware magnitude binary Brier discards. (None, None, mult) when direction is genuinely
    unresolved (spot unavailable) — never fabricated.
    """
    outcome = outcome_from_close(
        reason, direction=direction, intrinsic=intrinsic, exit_spot=exit_spot, entry_spot=entry_spot
    )
    b = brier(conviction_prob(conviction, conviction_to_prob), outcome) if outcome is not None else None
    mult = None
    if entry_premium and entry_premium > 0 and realized_pnl is not None:
        mult = (entry_premium + realized_pnl) / entry_premium
    return outcome, b, mult


def resolve_due_references(conn, market, *, now: datetime, horizon_days: int) -> int:
    """Sweep: resolve never-traded sentinels + controls whose reference horizon has elapsed.

    A row is due if it never traded (``proposal_id`` NULL), is unresolved (``resolved_at`` NULL),
    and its ``discovered_at`` is ≥ ``horizon_days`` ago. Resolves the reference return from
    ``discovered_at`` and records it (NULL stays NULL — unresolved is never fabricated). Returns
    the count resolved. The forward analog of the FSSD null test (controls included).
    """
    import state

    rows = conn.execute(
        "SELECT id, symbol, discovered_at FROM sentinel_candidates "
        "WHERE proposal_id IS NULL AND resolved_at IS NULL"
    ).fetchall()
    n = 0
    for r in rows:
        try:
            anchor = datetime.fromisoformat(r["discovered_at"])
        except (ValueError, TypeError):
            continue
        if now < anchor + timedelta(days=int(horizon_days * 1.6) + 4):
            continue  # horizon window hasn't elapsed yet
        ref, terminal = resolve_reference(market, r["symbol"], anchor, horizon_days, now=now)
        if ref is None:
            continue  # genuinely unresolved (e.g. no bars) → leave NULL, never fabricate
        state.resolve_sentinel(conn, int(r["id"]), resolved_at=now.isoformat(),
                               reference_return=ref, terminal_event=terminal)
        n += 1
    return n
