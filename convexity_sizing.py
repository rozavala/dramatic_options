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
) -> SizingDecision:
    """Number of contracts for one new shot under the frozen caps.

    Caps (all hard): per-name ≤ ``per_name_fraction``·equity; total open premium ≤
    ``book_fraction``·equity (the book); concurrent count ≤ ``max_open_positions``. The bet is
    sized greedily to ``min(per_name_cap, book_remaining)``. Returns 0 contracts (with a
    reason) if any cap or the minimum-one-contract threshold blocks the trade.
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

    # Greedy-to-cap: take the per-name cap, bounded by what's left in the book.
    alloc = min(per_name_cap, book_remaining)

    premium_per_contract = entry_premium_per_share * CONTRACT_MULTIPLIER
    n = int(alloc // premium_per_contract)
    if n < 1:
        return SizingDecision(
            0, premium_per_contract, 0.0,
            (f"alloc ${alloc:.0f} < one contract ${premium_per_contract:.0f} "
             f"(per-name cap ${per_name_cap:.0f}, book left ${book_remaining:.0f})",),
        )
    total = n * premium_per_contract
    return SizingDecision(
        n, premium_per_contract, total,
        (f"greedy-to-cap: {n} contract(s), ${total:.0f} "
         f"(per-name cap ${per_name_cap:.0f}, book left ${book_remaining:.0f})",),
    )
