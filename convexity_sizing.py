"""Greedy-to-per-name-cap convexity sizing (T1) — PREREG_THEMATIC_CONVEXITY §5.

**Not Kelly.** A far-OTM lotto Kelly-sizes to ~0 (low win probability); that is the wrong
instrument here. Each shot is sized to the **per-name cap** (a small fixed % of the account),
bounded by the book remaining and refused once the concurrent-position cap is hit — so the
book fills first-come at per-name size rather than being pre-divided into equal slots. (The
earlier flat-by-slots rule divided the book into ``max_open_positions`` equal slices, which
sized a single mid-priced/high-vol long-dated wing below one contract and vetoed otherwise-
cheap names; greedy-to-cap fixes that while keeping every hard bound.) The book itself caps
the count — at 1%/name on a 10% book at most ~10 full-size bets fit before it's exhausted.
Aggression comes from convex *structure* and the *number* of small shots — never from size on
an unproven view. Pure function — offline-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

CONTRACT_MULTIPLIER = 100.0  # US equity options: 1 contract = 100 shares


@dataclass(frozen=True)
class SizingDecision:
    contracts: int
    premium_per_contract: float  # entry mid × 100
    total_premium: float
    reasons: tuple[str, ...]


def convexity_position_size(
    *,
    account_equity: float,
    book_fraction: float,
    per_name_fraction: float,
    max_open_positions: int,
    open_positions_count: int,
    open_premium_total: float,
    entry_premium_per_share: float,
    cluster_remaining: float | None = None,
) -> SizingDecision:
    """Number of contracts for one new shot under the frozen caps.

    Caps (all hard): per-name ≤ ``per_name_fraction``·equity; total open premium ≤
    ``book_fraction``·equity (the book); concurrent count ≤ ``max_open_positions``; and — when the
    name belongs to a correlation cluster (PREREG §5 amendment) — the cluster's remaining
    entry-premium budget, passed as ``cluster_remaining`` (``None`` = unclustered → no cluster
    bound). The bet is sized greedily to ``min(per_name_cap, book_remaining[, cluster_remaining])``.
    Returns 0 contracts (with a reason) if any cap or the minimum-one-contract threshold blocks it.
    """
    if account_equity <= 0:
        return SizingDecision(0, 0.0, 0.0, ("nonpositive_equity",))
    if entry_premium_per_share <= 0:
        return SizingDecision(0, 0.0, 0.0, ("nonpositive_premium",))
    if open_positions_count >= max_open_positions:
        return SizingDecision(
            0, 0.0, 0.0,
            (f"max_open_positions reached ({open_positions_count}>={max_open_positions})",),
        )

    book_budget = account_equity * book_fraction
    per_name_cap = account_equity * per_name_fraction
    book_remaining = book_budget - open_premium_total
    if book_remaining <= 0:
        return SizingDecision(0, 0.0, 0.0, (f"book budget exhausted ({open_premium_total:.0f}>={book_budget:.0f})",))

    # Optional per-cluster correlation budget (PREREG §5 amendment): an exhausted cluster blocks the
    # shot outright; otherwise it just tightens the greedy allocation alongside the per-name + book caps.
    if cluster_remaining is not None and cluster_remaining <= 0:
        return SizingDecision(
            0, 0.0, 0.0, (f"cluster cap exhausted (${cluster_remaining:.0f} left)",),
        )

    # Greedy-to-cap: take the per-name cap, bounded by what's left in the book (and the cluster, if any).
    bounds = [per_name_cap, book_remaining]
    if cluster_remaining is not None:
        bounds.append(cluster_remaining)
    alloc = min(bounds)
    cluster_note = "" if cluster_remaining is None else f", cluster left ${cluster_remaining:.0f}"

    premium_per_contract = entry_premium_per_share * CONTRACT_MULTIPLIER
    n = int(alloc // premium_per_contract)
    if n < 1:
        return SizingDecision(
            0, premium_per_contract, 0.0,
            (f"alloc ${alloc:.0f} < one contract ${premium_per_contract:.0f} "
             f"(per-name cap ${per_name_cap:.0f}, book left ${book_remaining:.0f}{cluster_note})",),
        )
    total = n * premium_per_contract
    return SizingDecision(
        n, premium_per_contract, total,
        (f"greedy-to-cap: {n} contract(s), ${total:.0f} "
         f"(per-name cap ${per_name_cap:.0f}, book left ${book_remaining:.0f}{cluster_note})",),
    )


def equal_weight_contracts(*, account_equity: float, per_name_fraction: float,
                           entry_premium_per_share: float) -> int:
    """Contracts at the per-name cap with **NO book / cluster / concurrency truncation** — the 3B
    fixed-basket null's equal-weight sizing (PREREG_FIXED_BASKET_NULL §4: equal-weight the WHOLE basket,
    because a cap-ON 3B would book only the ~10 names that fit the 10% book, which isn't "the basket").
    Returns 0 if equity/premium are nonpositive or the per-name cap can't afford one contract."""
    if account_equity <= 0 or entry_premium_per_share <= 0:
        return 0
    per_name_cap = account_equity * per_name_fraction
    return int(per_name_cap // (entry_premium_per_share * CONTRACT_MULTIPLIER))
