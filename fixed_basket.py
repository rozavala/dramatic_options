"""No-gate / fixed-basket NULL books (PREREG_FIXED_BASKET_NULL.md) — test the IV GATE itself.

The existing real/shadow pair isolates the **council** (both keep the IV gate). These books drop the
gate, so `shadow − 3A` is the FSSD null≈signal control on the part that IS the claimed edge — "trade
only when convexity is *cheap*." If a book that trades the **same names with the gate OFF** earns the
same realized-multiple **tail** as the gate-ON shadow, cheapness is not an edge over eligibility.

This module ships **PR2a — book 3A** (`book='union_nogate'`): gate-OFF over the SAME candidate union
the shadow book sees (hand-seed ∪ active sentinels), **cap-ON** (the frozen frame, incl. the cluster
cap — EXCEPT the sentinel slot reservation, relieved symmetrically with the shadow book by the FBN
§4 dated amendment 2026-07-02), so it is a clean one-variable step from the shadow book — only the
gate differs. (PR2b
adds `basket_nogate` = the whole basket, equal-weight, + the shares null.)

Reuses the real book's PURE decision functions (`select_structure` — confirmed gate-INDEPENDENT —
`convexity_position_size`, `realized_vol`, the cluster cap) so the gate-off pipeline cannot drift from
the gated one; only the orchestration shell differs. Mirrors `shadow_book.py` field-for-field (PR3b),
so the eventual unification of the null books is a mechanical union.

**SAFETY — never the broker.** Imports no broker; every entry point takes NO broker argument; a "fill"
is booked directly at the chain mid; exits close in-DB at mark/intrinsic. Physical isolation (its own
table + no broker import) makes "a no-gate position can never be submitted" structurally true. The
orchestrator runs it **fail-soft** (a null bug logs/pages but never halts the real trade cycle).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

import clusters
import state
from clock import Clock
from convexity_data import ChainProvider, QuoteProvider
from convexity_sizing import convexity_position_size, equal_weight_contracts
from discovery import compute_markers, direction_of
from paper_loop import kill_rule_status
from risk import kill_switch_active
from sentinels import active_sentinel_candidates, union_candidates
from shadow_book import tail_summary
from structure import contract_eligible, select_structure
from themes import Theme, active_themes, load_themes

log = logging.getLogger("fixed_basket")

CONTRACT_MULTIPLIER = 100.0
BOOK_UNION_NOGATE = "union_nogate"    # 3A — gate-off over the candidate union, cap-ON
BOOK_BASKET_NOGATE = "basket_nogate"  # 3B — gate-off, equal-weight, motion-derived dir, whole basket


@dataclass
class FixedBasketResult:
    book: str = BOOK_UNION_NOGATE
    booked: int = 0
    vetoed: int = 0
    skipped: int = 0
    errors: int = 0
    halted: bool = False
    by_origin: dict[str, int] = field(default_factory=dict)
    # Per-reason veto counts (3A: "sentinel_slots" | "no_structure" | "cluster_cap" | "sizing";
    # 3B: "no_structure" | "sizing") — mirrors ShadowBookResult.veto_reasons (dead-arm visibility).
    veto_reasons: dict[str, int] = field(default_factory=dict)


@dataclass
class FixedBasketMonitorResult:
    marked: int = 0
    closed: int = 0
    expired: int = 0
    profit_taken: int = 0
    time_stopped: int = 0
    unmarked: int = 0


def _origin_of(theme: Theme) -> str:
    return "sentinel" if theme.sentinel_id is not None else "hand_seed"


def candidate_union(conn, config: dict) -> list[Theme]:
    """The SAME union the shadow book + council see: hand-seed (themes.json) ∪ active sentinels.
    Self-contained (replicated, not imported) so this book runs independent of the council branch."""
    hand_seed = active_themes(load_themes(config.get("themes_path", "themes.json")))
    return union_candidates(hand_seed, active_sentinel_candidates(conn))


def run_fixed_basket_3a_cycle(
    *,
    config: dict,
    conn,
    clock: Clock,
    provider: ChainProvider,
    run_id: int | None = None,
    candidates: list[Theme] | None = None,
) -> FixedBasketResult:
    """Book 3A: a SIM position for every candidate in the union that clears eligibility + sizing with
    the **IV GATE OFF** (no `is_cheap_convexity`), under the full cap-ON frame. NEVER touches the broker.
    Mirrors `shadow_book.run_shadow_cycle`'s gate sequence (kill → slot reservation → eligibility →
    [GATE SKIPPED] → cluster cap → sizing) so the only difference vs the shadow book is the missing gate."""
    result = FixedBasketResult(book=BOOK_UNION_NOGATE)
    if kill_switch_active() or kill_rule_status(conn, config, clock).tripped:
        result.halted = True
        return result

    if candidates is None:
        candidates = candidate_union(conn, config)

    as_of_dt = clock.now()
    as_of = as_of_dt.date()
    as_of_iso = as_of_dt.isoformat()

    book_cfg = config.get("convexity_book", {})
    gate = config.get("convexity_gate", {})
    elig = config.get("eligibility", {}).get("live", {})
    account_equity = float(book_cfg.get("account_equity") or 0.0)
    # Null-book cap knobs (2026-07-02, BEHAVIOR-NEUTRAL by default) — symmetric with
    # shadow_book.run_shadow_cycle so the shadow−3A contrast stays clean; see the comment there.
    disc = config.get("discovery", {})
    if disc.get("null_book_fraction") is not None:
        book_cfg = {**book_cfg, "book_fraction": float(disc["null_book_fraction"])}
    if disc.get("null_cluster_fraction") is not None:
        cluster_fraction = float(disc["null_cluster_fraction"])
    else:
        cluster_fraction = float(book_cfg.get("cluster_fraction") or 0.0)
    cluster_map = clusters.load_cluster_map(config) if cluster_fraction > 0 else {}
    # FBN §4 amendment (2026-07-02): slot relief, symmetric with the shadow book (see
    # shadow_book.run_shadow_cycle) — the shadow−3A contrast stays clean.
    max_slots = disc.get("null_sentinel_max_slots")
    open_syms = state.fixed_basket_open_symbols(conn, BOOK_UNION_NOGATE)

    def _eligibility(c):
        return contract_eligible(
            c, max_spread_pct=float(elig.get("max_bid_ask_pct", 0.25)),
            min_contract_price=0.10, max_contract_price=100.0,
            min_oi=elig.get("min_option_open_interest"),
        )

    for theme in candidates:
        if not theme.active or theme.symbol in open_syms:
            if theme.active:
                result.skipped += 1
            continue
        origin = _origin_of(theme)
        # Null-book slot reservation (FBN §4 amendment 2026-07-02): only when
        # discovery.null_sentinel_max_slots is set — symmetric with the shadow book.
        if (origin == "sentinel" and max_slots is not None
                and state.count_open_fixed_basket_sentinel_positions(conn, BOOK_UNION_NOGATE) >= int(max_slots)):
            result.vetoed += 1
            result.veto_reasons["sentinel_slots"] = result.veto_reasons.get("sentinel_slots", 0) + 1
            continue
        try:
            reason = _eval_and_book_nogate(
                theme, origin=origin, conn=conn, provider=provider, eligibility=_eligibility,
                account_equity=account_equity, gate=gate, book_cfg=book_cfg, as_of=as_of,
                as_of_iso=as_of_iso, run_id=run_id,
                cluster_map=cluster_map, cluster_fraction=cluster_fraction,
            )
        except Exception as e:  # noqa: BLE001 — per-candidate fail-soft: never break the pass, but
            result.errors += 1  # log LOUDLY (WARNING) — debug-level here hid a class of dead-arm failures
            log.warning("3A eval errored for %s: %s", theme.symbol, e)
            continue
        if reason == "booked":
            result.booked += 1
            result.by_origin[origin] = result.by_origin.get(origin, 0) + 1
            open_syms.add(theme.symbol)
        else:
            result.vetoed += 1
            result.veto_reasons[reason] = result.veto_reasons.get(reason, 0) + 1
    return result


def _eval_and_book_nogate(
    theme, *, origin, conn, provider, eligibility, account_equity, gate, book_cfg,
    as_of, as_of_iso, run_id, cluster_map, cluster_fraction,
) -> bool:
    """The deterministic pipeline for one candidate **with the IV gate OFF** — book a SIM position at
    the chain mid if it clears eligibility + the (cap-ON) caps. The ONLY difference vs
    `shadow_book._eval_and_book` is the missing `is_cheap_convexity` veto (and the realized-vol it fed,
    now unused). Returns "booked" iff booked, else the veto reason ("no_structure" | "cluster_cap" |
    "sizing")."""
    underlying_price = provider.underlying_price(theme.symbol)
    chain = provider.chain(theme.symbol)

    structure, _ = select_structure(
        chain, direction=theme.direction, as_of=as_of, underlying_price=underlying_price,
        tenor_min_days=int(gate.get("tenor_min_days", 180)),
        tenor_max_days=int(gate.get("tenor_max_days", 365)),
        target_moneyness=float(gate.get("target_moneyness", 0.25)), eligibility=eligibility,
    )
    if structure is None:
        return "no_structure"
    # >>> NO is_cheap_convexity here — that veto is exactly what 3A removes (the gate test). <<<

    # The SAME cap-ON cluster cap the real/shadow books apply (3A holds the full frame).
    cluster = clusters.cluster_of(theme.symbol, cluster_map)
    cluster_remaining = None
    if cluster is not None:
        cluster_remaining = account_equity * cluster_fraction - state.fixed_basket_cluster_open_premium(
            conn, clusters.members_of(cluster, cluster_map), BOOK_UNION_NOGATE)
        if cluster_remaining < structure.entry_premium * CONTRACT_MULTIPLIER:
            return "cluster_cap"
    sizing = convexity_position_size(
        account_equity=account_equity,
        book_fraction=float(book_cfg.get("book_fraction", 0.10)),
        per_name_fraction=float(book_cfg.get("per_name_fraction", 0.01)),
        max_open_positions=int(book_cfg.get("max_open_positions", 15)),
        open_positions_count=state.count_open_fixed_basket_positions(conn, BOOK_UNION_NOGATE),
        open_premium_total=state.fixed_basket_book_open_premium(conn, BOOK_UNION_NOGATE),
        entry_premium_per_share=structure.entry_premium,
        cluster_remaining=cluster_remaining,
    )
    if sizing.contracts < 1:
        return "sizing"
    entry_pc = structure.entry_premium * CONTRACT_MULTIPLIER
    state.record_fixed_basket_position(
        conn, run_id=run_id, book=BOOK_UNION_NOGATE, origin=origin, opened_at=as_of_iso, theme=theme.name,
        symbol=theme.symbol, direction=theme.direction, structure_kind=structure.kind,
        contract_symbol=structure.contract.symbol, expiry=structure.contract.expiry.isoformat(),
        strike=structure.contract.strike, dte=structure.dte, moneyness=structure.moneyness,
        contracts=sizing.contracts, entry_premium_per_contract=entry_pc,
        total_premium=entry_pc * sizing.contracts, entry_spot=underlying_price,
    )
    return "booked"


def basket_symbols(config: dict) -> dict[str, str]:
    """Flatten ``config.universe.themes`` → ``{symbol: basket_name}`` — the WHOLE curated basket (3B's
    universe). First basket wins on overlap; ``_comment`` keys skipped."""
    out: dict[str, str] = {}
    for basket, members in (config.get("universe", {}).get("themes", {}) or {}).items():
        if str(basket).startswith("_"):
            continue
        for s in members:
            out.setdefault(s.strip().upper(), basket)
    return out


def run_fixed_basket_3b_cycle(
    *, config: dict, conn, clock: Clock, provider: ChainProvider, market, benchmark, params,
    run_id: int | None = None,
) -> FixedBasketResult:
    """Book 3B: gate-OFF, **EQUAL-WEIGHT** over the WHOLE eligible basket (``config.universe.themes``),
    with the **MOTION-derived** direction (``discovery.direction_of`` — mechanical, no judgment) and **NO
    book/cluster/slot truncation** (PREREG_FIXED_BASKET_NULL §4). ``real − 3B`` = the bundled apparatus-
    vs-basket read. Weekly (L0 cadence). NEVER the broker. ``market``/``benchmark``/``params`` are the
    discovery context (the motion read); ``provider`` supplies the option chains."""
    result = FixedBasketResult(book=BOOK_BASKET_NOGATE)
    if kill_switch_active() or kill_rule_status(conn, config, clock).tripped:
        result.halted = True
        return result
    as_of_dt = clock.now()
    as_of = as_of_dt.date()
    as_of_iso = as_of_dt.isoformat()
    book_cfg = config.get("convexity_book", {})
    gate = config.get("convexity_gate", {})
    elig = config.get("eligibility", {}).get("live", {})
    account_equity = float(book_cfg.get("account_equity") or 0.0)
    per_name_fraction = float(book_cfg.get("per_name_fraction", 0.01))
    open_syms = state.fixed_basket_open_symbols(conn, BOOK_BASKET_NOGATE)

    def _eligibility(c):
        return contract_eligible(
            c, max_spread_pct=float(elig.get("max_bid_ask_pct", 0.25)),
            min_contract_price=0.10, max_contract_price=100.0, min_oi=elig.get("min_option_open_interest"),
        )

    for sym, basket in basket_symbols(config).items():
        if sym in open_syms:
            result.skipped += 1
            continue
        try:
            m = compute_markers(sym, as_of_dt, market=market, benchmark=benchmark, params=params, basket=basket)
            reason = _eval_and_book_3b(
                sym=sym, basket=basket, direction=direction_of(m), conn=conn, provider=provider,
                eligibility=_eligibility, account_equity=account_equity,
                per_name_fraction=per_name_fraction, gate=gate, as_of=as_of, as_of_iso=as_of_iso, run_id=run_id,
            )
        except Exception as e:  # noqa: BLE001 — per-name fail-soft: never break the pass, but
            result.errors += 1  # log LOUDLY (WARNING) — debug-level here hid a class of dead-arm failures
            log.warning("3B eval errored for %s: %s", sym, e)
            continue
        if reason == "booked":
            result.booked += 1
            result.by_origin["basket"] = result.by_origin.get("basket", 0) + 1
            open_syms.add(sym)
        else:
            result.vetoed += 1
            result.veto_reasons[reason] = result.veto_reasons.get(reason, 0) + 1
    return result


def _eval_and_book_3b(
    *, sym, basket, direction, conn, provider, eligibility, account_equity, per_name_fraction, gate,
    as_of, as_of_iso, run_id,
) -> str:
    """Gate-off, EQUAL-WEIGHT booking for one basket name (no book/cluster/slot caps). Returns
    "booked" iff booked, else the veto reason ("no_structure" | "sizing")."""
    underlying_price = provider.underlying_price(sym)
    chain = provider.chain(sym)
    structure, _ = select_structure(
        chain, direction=direction, as_of=as_of, underlying_price=underlying_price,
        tenor_min_days=int(gate.get("tenor_min_days", 180)), tenor_max_days=int(gate.get("tenor_max_days", 365)),
        target_moneyness=float(gate.get("target_moneyness", 0.25)), eligibility=eligibility,
    )
    if structure is None:
        return "no_structure"
    n = equal_weight_contracts(account_equity=account_equity, per_name_fraction=per_name_fraction,
                               entry_premium_per_share=structure.entry_premium)
    if n < 1:
        return "sizing"
    entry_pc = structure.entry_premium * CONTRACT_MULTIPLIER
    state.record_fixed_basket_position(
        conn, run_id=run_id, book=BOOK_BASKET_NOGATE, origin="basket", opened_at=as_of_iso, theme=basket,
        symbol=sym, direction=direction, structure_kind=structure.kind,
        contract_symbol=structure.contract.symbol, expiry=structure.contract.expiry.isoformat(),
        strike=structure.contract.strike, dte=structure.dte, moneyness=structure.moneyness,
        contracts=n, entry_premium_per_contract=entry_pc, total_premium=entry_pc * n, entry_spot=underlying_price,
    )
    return "booked"


def _intrinsic_value(kind: str, strike: float, underlying_price: float | None) -> float:
    """Per-share intrinsic at expiry. Local (not imported) to keep this module broker-import-free."""
    if underlying_price is None:
        return 0.0
    return max(0.0, underlying_price - strike) if kind == "C" else max(0.0, strike - underlying_price)


def mark_fixed_basket_positions(
    *, conn, clock: Clock, quote_provider: QuoteProvider, config: dict, underlying_price_of=None,
    book: str | None = None,
) -> FixedBasketMonitorResult:
    """Mark + apply the SAME deterministic exits (profit-take / time-stop / expiry) as the real/shadow
    monitors (identical `convexity_exits` thresholds, so exits cannot drift). Always books in-DB at the
    mark/intrinsic — there is no broker. `book=None` marks every no-gate book."""
    exits = config.get("convexity_exits", {})
    profit_mult = float(exits.get("profit_take_multiple", 10.0))
    time_stop_dte = int(exits.get("time_stop_dte", 21))
    now = clock.now()
    today = now.date()
    as_of_iso = now.isoformat()
    res = FixedBasketMonitorResult()

    for pos in state.open_fixed_basket_positions(conn, book):
        pid = int(pos["id"])
        kind = pos["structure_kind"]
        contracts = int(pos["contracts"])
        entry_pc = float(pos["entry_premium_per_contract"])
        total_premium = float(pos["total_premium"])
        expiry = _parse_date(pos["expiry"])
        dte = (expiry - today).days if expiry else None

        if expiry is not None and today >= expiry:
            up = underlying_price_of(pos["symbol"]) if underlying_price_of else None
            intrinsic = _intrinsic_value(kind, float(pos["strike"]), up)
            _close(conn, pid, exit_price=intrinsic, entry_pc=entry_pc, contracts=contracts,
                   total_premium=total_premium, reason="expiry", as_of=as_of_iso)
            res.expired += 1
            res.closed += 1
            continue

        mid = quote_provider.option_mid(pos["contract_symbol"])
        if mid is None:
            res.unmarked += 1
            continue
        state.mark_fixed_basket_position(conn, pid, mark=mid, as_of=as_of_iso)
        res.marked += 1

        if entry_pc > 0 and mid * CONTRACT_MULTIPLIER >= profit_mult * entry_pc:
            _close(conn, pid, exit_price=mid, entry_pc=entry_pc, contracts=contracts,
                   total_premium=total_premium, reason=f"profit_take_{profit_mult:g}x", as_of=as_of_iso)
            res.profit_taken += 1
            res.closed += 1
            continue
        if dte is not None and dte <= time_stop_dte:
            _close(conn, pid, exit_price=mid, entry_pc=entry_pc, contracts=contracts,
                   total_premium=total_premium, reason=f"time_stop_{time_stop_dte}dte", as_of=as_of_iso)
            res.time_stopped += 1
            res.closed += 1
    return res


def _close(conn, pid, *, exit_price, entry_pc, contracts, total_premium, reason, as_of) -> None:
    pnl = (exit_price * CONTRACT_MULTIPLIER - entry_pc) * contracts
    mult = (exit_price * CONTRACT_MULTIPLIER * contracts) / total_premium if total_premium > 0 else 0.0
    state.close_fixed_basket_position(conn, pid, exit_price=exit_price, realized_pnl=pnl,
                                      realized_multiple=mult, reason=reason, as_of=as_of)


def tail_report(conn) -> dict[str, dict]:
    """Per-no-gate-book realized-multiple TAIL summaries (reuses `shadow_book.tail_summary`). Keyed
    `nogate_<book>` so the orchestrator can sit them beside the real + shadow tails for the
    `shadow − 3A` (gate) read — forward, never a pass/fail (PREREG §5 / guardrail §6)."""
    return {f"nogate_{book}": tail_summary(ms)
            for book, ms in state.fixed_basket_realized_multiples(conn).items()}


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        s = str(value)
        return datetime.fromisoformat(s).date() if "T" in s else date.fromisoformat(s)
    except ValueError:
        return None
