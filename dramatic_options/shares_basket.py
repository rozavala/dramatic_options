"""SHARES descriptive null (PREREG_FIXED_BASKET_NULL.md §2/§5, PR2c) — convexity vs LINEAR.

The last, secondary book of the fixed-basket null hierarchy. The option null books (real / shadow / 3A /
3B) all hold convex OPTIONS; this book asks the orthogonal question: **would just holding the SHARES**
(linear, no premium bleed) of the same option-eligible basket names have returned comparably? It is the
context for whether the convex book's bounded-downside / fat-upside is worth the premium bleed.

**Design (operator red-team):** an **append-only ENTRY LOG** (`shares_positions`) — only the forward entry
(spot / as-of / MOTION-derived direction) is stored. Signed returns are computed **at report time from
bars at a horizon SET {180, 270, 365}** (the calibration tenor sweep) with the §6 terminal-event
survivorship guard, so the read is horizon-comparable to the option lifecycle (~250d median hold) and an
event the fixed-180d resolve would miss (a day-200 buyout) is captured at the longer horizons. No stored
return, no resolve-and-store sweep.

**Two pinned caveats (§5):** the distribution is DESCRIPTIVE — shown ALONGSIDE the option tails, NEVER
scored against them; and the signed short side is a FRICTIONLESS short, so it is a deliberately
CONSERVATIVE benchmark. **NEVER the broker** (imports none; pure data) and run **fail-soft**.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from dramatic_options import state
from dramatic_options.clock import Clock
from dramatic_options.convexity_data import ChainProvider
from dramatic_options.discovery import compute_markers, direction_of
from dramatic_options.fixed_basket import basket_symbols
from dramatic_options.paper_loop import kill_rule_status
from dramatic_options.risk import kill_switch_active
from dramatic_options.sentinel_scoring import reference_return_from_bars
from dramatic_options.structure import contract_eligible, select_structure

log = logging.getLogger("shares_basket")

DEFAULT_HORIZONS = (180, 270, 365)
# PINNED (§7 — never tuned to a gap): drop the single largest signed return for the robust "without the
# top-k outliers" read — one buyout can dominate the event-enriched basket. The options tail report should
# adopt the SAME k when it gains the with/without-top-k variant (prereg §5/§6).
TOP_K_OUTLIERS = 1

CAVEATS = (
    "DESCRIPTIVE — shown ALONGSIDE the option tails, NEVER scored against them (cannot tail-compare an "
    "option multiple to a share return); forward, never a pass-gate (PREREG §5/§7).",
    "The signed short side is a FRICTIONLESS short (no borrow/margin/unbounded-loss/dividends) → a "
    "deliberately CONSERVATIVE benchmark: 'shares look comparable' does NOT mean 'abandon convexity'.",
)


@dataclass
class SharesBasketResult:
    booked: int = 0
    vetoed: int = 0
    skipped: int = 0
    errors: int = 0
    halted: bool = False


def run_shares_basket_cycle(
    *, config: dict, conn, clock: Clock, provider: ChainProvider, market, benchmark, params,
    run_id: int | None = None,
) -> SharesBasketResult:
    """Log a SIM shares entry for every option-eligible basket name (gate-OFF, equal-weight = one unit),
    MOTION-derived direction, weekly (L0). Time-dedups within the longest horizon (≈ the option books'
    skip-already-open). NEVER the broker. Kill-guarded + per-name fail-soft."""
    result = SharesBasketResult()
    if kill_switch_active() or kill_rule_status(conn, config, clock).tripped:
        result.halted = True
        return result

    as_of_dt = clock.now()
    as_of = as_of_dt.date()
    as_of_iso = as_of_dt.isoformat()
    gate = config.get("convexity_gate", {})
    elig = config.get("eligibility", {}).get("live", {})
    horizons = config.get("shares_basket", {}).get("horizons") or list(DEFAULT_HORIZONS)
    dedup_days = int(max(horizons))
    recent = state.shares_recent_symbols(conn, since_iso=(as_of_dt - timedelta(days=dedup_days)).isoformat())

    def _eligibility(c):
        return contract_eligible(
            c, max_spread_pct=float(elig.get("max_bid_ask_pct", 0.25)),
            min_contract_price=0.10, max_contract_price=100.0, min_oi=elig.get("min_option_open_interest"))

    for sym, basket in basket_symbols(config).items():
        if sym in recent:
            result.skipped += 1
            continue
        try:
            underlying_price = provider.underlying_price(sym)
            if not underlying_price or underlying_price <= 0:
                result.skipped += 1  # missing data → SKIP-and-count, never a degenerate (null-spot) row
                continue
            booked = _eval_and_book_shares(
                sym=sym, basket=basket, underlying_price=underlying_price, conn=conn, provider=provider,
                market=market, benchmark=benchmark, params=params, eligibility=_eligibility, gate=gate,
                as_of=as_of, as_of_dt=as_of_dt, as_of_iso=as_of_iso, run_id=run_id)
        except Exception as e:  # noqa: BLE001 — per-name fail-soft: log, never break the pass
            result.errors += 1
            log.debug("shares eval errored for %s: %s", sym, e)
            continue
        if booked:
            result.booked += 1
            recent.add(sym)
        else:
            result.vetoed += 1
    return result


def _eval_and_book_shares(
    *, sym, basket, underlying_price, conn, provider, market, benchmark, params, eligibility, gate,
    as_of, as_of_dt, as_of_iso, run_id,
) -> bool:
    """Book one shares entry iff the name clears OPTION eligibility (so the universe matches 3B's tradable
    names — a linear book otherwise needs no chain). ``underlying_price`` is the SAME spot the entry stores.
    True iff booked."""
    # MOTION-derived direction FIRST, so the eligibility check below uses the SAME contract (call/put) 3B
    # would — making shares-eligible ≡ 3B-eligible. benchmark feeds compute_markers' rel_strength (the
    # motion read), NOT the return metric (a raw signed underlying return, deliberately not beta-adj CAR).
    m = compute_markers(sym, as_of_dt, market=market, benchmark=benchmark, params=params, basket=basket)
    direction = direction_of(m)
    structure, _ = select_structure(
        provider.chain(sym), direction=direction, as_of=as_of, underlying_price=underlying_price,
        tenor_min_days=int(gate.get("tenor_min_days", 180)), tenor_max_days=int(gate.get("tenor_max_days", 365)),
        target_moneyness=float(gate.get("target_moneyness", 0.25)), eligibility=eligibility)
    if structure is None:
        return False
    state.record_shares_position(
        conn, run_id=run_id, basket=basket, symbol=sym, direction=direction,
        entry_spot=underlying_price, entry_at=as_of_iso)  # entry_spot = the SAME spot eligibility saw
    return True


# ── report-time, multi-horizon DESCRIPTIVE distribution (never a tail contest) ────────────────────


def _pct(xs_sorted: list[float], p: float) -> float:
    if not xs_sorted:
        return 0.0
    i = min(len(xs_sorted) - 1, int(round(p * (len(xs_sorted) - 1))))
    return xs_sorted[i]


def _distribution(returns: list[float]) -> dict:
    if not returns:
        return {"n": 0, "mean": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0,
                "p_loss": 0.0, "min": 0.0, "max": 0.0}
    xs = sorted(returns)
    n = len(xs)
    return {"n": n, "mean": sum(xs) / n, "p25": _pct(xs, 0.25), "p50": _pct(xs, 0.5),
            "p75": _pct(xs, 0.75), "p90": _pct(xs, 0.9), "p_loss": sum(1 for r in xs if r < 0) / n,
            "min": xs[0], "max": xs[-1]}


def _drop_top_k(returns: list[float], k: int) -> list[float]:
    if k <= 0:
        return list(returns)
    return sorted(returns)[:-k] if len(returns) > k else []


def shares_return_report(conn, market, *, now: datetime, horizons=DEFAULT_HORIZONS, k: int = TOP_K_OUTLIERS) -> dict:
    """Compute the per-horizon DESCRIPTIVE signed-return distribution from bars (the §6 terminal guard is
    REUSED per horizon, fed the STORED entry_spot for exact convex/linear reconciliation). Genuinely
    unresolved (horizon not elapsed AND not terminated) → excluded from that horizon's N (never
    fabricated). Returns a dict with the two pinned caveats. NEVER scored against the option tails."""
    horizons = list(horizons)
    per_h: dict[int, dict] = {h: {"returns": [], "n_terminal": 0} for h in horizons}
    for pos in state.all_shares_positions(conn):
        try:
            entry_at = datetime.fromisoformat(pos["entry_at"])
        except (ValueError, TypeError):
            continue
        entry_spot = float(pos["entry_spot"])
        is_bull = pos["direction"] == "bullish"
        fwd_closes = [b["close"] for b in market.cache.read_between("bars", pos["symbol"], entry_at, now)
                      if _bar_after(b, entry_at)]
        for h in horizons:
            terminated = now >= entry_at + timedelta(days=int(h * 1.6) + 4) and 0 < len(fwd_closes) < h
            raw, tag = reference_return_from_bars(entry_spot, fwd_closes, h, terminated=terminated)
            if raw is None:
                continue
            per_h[h]["returns"].append(raw if is_bull else -raw)
            if tag == "terminated":
                per_h[h]["n_terminal"] += 1
    out: dict = {"caveats": list(CAVEATS), "horizons": {}}
    for h in horizons:
        rs = per_h[h]["returns"]
        out["horizons"][f"h{h}"] = {
            "full": _distribution(rs),
            f"ex_top{k}": _distribution(_drop_top_k(rs, k)),
            "n_terminal": per_h[h]["n_terminal"],
        }
    return out


def _bar_after(bar, entry_at: datetime) -> bool:
    try:
        return datetime.fromisoformat(bar["ts"]) > entry_at
    except (ValueError, TypeError, KeyError):
        return False
