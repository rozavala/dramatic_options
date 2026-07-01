"""Brain-off NULL shadow book (T3 PR3b) — the forward "does the LLM layer add value?" control.

A parallel, **simulated-only** book that runs the SAME deterministic pipeline the real book uses
(eligibility → IV/cheap-convexity gate → defined-risk structure → sizing → exits) over the SAME
candidate union the council sees (hand-seed ∪ active sentinels), but **BRAIN-OFF**: it books EVERY
gate-passer — no council include/exclude, no framer drop. Every deterministic gate, cap, and the
sentinel slot reservation are held IDENTICAL to the real book; the ONLY difference is the brain-off
selection. So the gap between this book's forward payoff **tail** (per origin) and the real book's is
exactly the council/framer's marginal contribution — the forward analog of the FSSD null≈signal test,
at the book level (guardrail §6: validated forward, never backtested).

**SAFETY — never the broker.** This module imports no broker and every entry point takes NO broker
argument: a shadow "fill" is booked directly at the chain mid, and exits close in-DB at the
mark/intrinsic. Physical isolation (its own table, no broker import, no submit path) makes "a shadow
position can never be submitted" structurally true, not merely intended. The orchestrator runs both
passes **fail-soft** — a shadow bug logs/pages but never halts the real trade cycle (a measurement
control must not be able to stop trading).

Reuses the real book's PURE decision functions (``select_structure`` / ``is_cheap_convexity`` /
``convexity_position_size`` / ``realized_vol``), so the GATE LOGIC cannot drift from the real book;
only the orchestration shell + the never-broker booking differ.

Scope: this isolates the **LLM layer** (does the council's include/exclude beat trading everything
surfaced). It does NOT answer "does the apparatus beat a fixed thematic basket" — that cheaper
fixed-basket null (the one the T4 real-money call hinges on) is a separate sibling on the near list.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

import clusters
import state
from clock import Clock
from convexity_data import ChainProvider, QuoteProvider
from convexity_gate import is_cheap_convexity, realized_vol
from convexity_sizing import convexity_position_size
from paper_loop import kill_rule_status
from risk import kill_switch_active
from sentinels import active_sentinel_candidates, union_candidates
from structure import contract_eligible, select_structure
from themes import Theme, active_themes, load_themes

log = logging.getLogger("shadow_book")

CONTRACT_MULTIPLIER = 100.0


@dataclass
class ShadowBookResult:
    booked: int = 0
    vetoed: int = 0
    skipped: int = 0
    errors: int = 0
    halted: bool = False
    by_origin: dict[str, int] = field(default_factory=dict)
    # Per-reason veto counts ("sentinel_slots" | "no_structure" | "not_cheap" | "cluster_cap" |
    # "sizing") — a booked=0 cycle is indistinguishable from a dead arm without them (the 2026-06/07
    # three-week silent-zero window).
    veto_reasons: dict[str, int] = field(default_factory=dict)


@dataclass
class ShadowMonitorResult:
    marked: int = 0
    closed: int = 0
    expired: int = 0
    profit_taken: int = 0
    time_stopped: int = 0
    unmarked: int = 0


def _origin_of(theme: Theme) -> str:
    """hand_seed vs sentinel — refinement #1, so the comparison can be decomposed by origin."""
    return "sentinel" if theme.sentinel_id is not None else "hand_seed"


def candidate_union(conn, config: dict) -> list[Theme]:
    """The SAME union the council sees: hand-seed (themes.json) ∪ active sentinels. Self-contained so
    the shadow pass is independent of the council branch's control flow (it runs even with the council
    disabled — it IS the brain-off book)."""
    hand_seed = active_themes(load_themes(config.get("themes_path", "themes.json")))
    return union_candidates(hand_seed, active_sentinel_candidates(conn))


def run_shadow_cycle(
    *,
    config: dict,
    conn,
    clock: Clock,
    provider: ChainProvider,
    run_id: int | None = None,
    candidates: list[Theme] | None = None,
) -> ShadowBookResult:
    """Brain-OFF booking: book a SIM position for EVERY candidate that clears the same deterministic
    gates the real book uses, over the SAME candidate union — no council, no framer. NEVER touches the
    broker (no broker arg, no broker import, no submit path). Mirrors run_paper_cycle's gate sequence
    (kill switch → kill rule → slot reservation → eligibility → IV gate → sizing) so the only
    difference is the selection."""
    result = ShadowBookResult()
    if kill_switch_active() or kill_rule_status(conn, config, clock).tripped:
        result.halted = True
        return result

    if candidates is None:
        candidates = candidate_union(conn, config)

    as_of_dt = clock.now()
    as_of = as_of_dt.date()
    as_of_iso = as_of_dt.isoformat()

    book = config.get("convexity_book", {})
    gate = config.get("convexity_gate", {})
    elig = config.get("eligibility", {}).get("live", {})
    account_equity = float(book.get("account_equity") or 0.0)
    cluster_fraction = float(book.get("cluster_fraction") or 0.0)
    cluster_map = clusters.load_cluster_map(config) if cluster_fraction > 0 else {}
    max_slots = config.get("discovery", {}).get("sentinel_max_slots")
    rv_window = int(gate.get("rv_window_days", 252))
    open_syms = state.shadow_open_symbols(conn)

    def _eligibility(c):
        return contract_eligible(
            c, max_spread_pct=float(elig.get("max_bid_ask_pct", 0.25)),
            min_contract_price=0.10, max_contract_price=100.0,
            min_oi=elig.get("min_option_open_interest"),
        )

    for theme in candidates:
        if not theme.active:
            continue
        if theme.symbol in open_syms:
            result.skipped += 1
            continue
        origin = _origin_of(theme)
        # The SAME slot reservation the real book applies (a deterministic cap, held fixed; only the
        # council include/exclude is removed): a sentinel-origin candidate cannot exceed sentinel_max_slots.
        if (origin == "sentinel" and max_slots is not None
                and state.count_open_shadow_sentinel_positions(conn) >= int(max_slots)):
            result.vetoed += 1
            result.veto_reasons["sentinel_slots"] = result.veto_reasons.get("sentinel_slots", 0) + 1
            continue
        try:
            reason = _eval_and_book(
                theme, origin=origin, conn=conn, provider=provider, eligibility=_eligibility,
                account_equity=account_equity, gate=gate, book=book, as_of=as_of,
                as_of_iso=as_of_iso, rv_window=rv_window, run_id=run_id,
                cluster_map=cluster_map, cluster_fraction=cluster_fraction,
            )
        except Exception as e:  # noqa: BLE001 — per-candidate fail-soft: never break the pass, but
            result.errors += 1  # log LOUDLY (WARNING) — debug-level here hid a class of dead-arm failures
            log.warning("shadow eval errored for %s: %s", theme.symbol, e)
            continue
        if reason == "booked":
            result.booked += 1
            result.by_origin[origin] = result.by_origin.get(origin, 0) + 1
            open_syms.add(theme.symbol)
        else:
            result.vetoed += 1
            result.veto_reasons[reason] = result.veto_reasons.get(reason, 0) + 1
    return result


def _eval_and_book(
    theme, *, origin, conn, provider, eligibility, account_equity, gate, book,
    as_of, as_of_iso, rv_window, run_id, cluster_map, cluster_fraction,
) -> str:
    """Deterministic pipeline for one candidate; book a SIM position at the chain mid if it passes.
    No broker — the real book's paper sim-fill uses this same mid, so entry premia are
    apples-to-apples. Returns "booked" iff a position was booked, else the veto reason
    ("no_structure" | "not_cheap" | "cluster_cap" | "sizing")."""
    underlying_price = provider.underlying_price(theme.symbol)
    chain = provider.chain(theme.symbol)
    closes = provider.closes(theme.symbol, window=rv_window)
    rv = realized_vol(closes, window=rv_window)

    structure, _ = select_structure(
        chain, direction=theme.direction, as_of=as_of, underlying_price=underlying_price,
        tenor_min_days=int(gate.get("tenor_min_days", 180)),
        tenor_max_days=int(gate.get("tenor_max_days", 365)),
        target_moneyness=float(gate.get("target_moneyness", 0.25)), eligibility=eligibility,
    )
    if structure is None:
        return "no_structure"
    verdict = is_cheap_convexity(
        chain, underlying_price=underlying_price, wing=structure.contract, rv=rv,
        iv_rv_max=float(gate.get("iv_rv_max", 1.2)),
        otm_skew_max_volpts=float(gate.get("otm_skew_max_volpts", 10.0)),
    )
    if not verdict.cheap:
        return "not_cheap"
    # The SAME deterministic cluster cap the real book applies (only the council selection differs).
    # Shadow books 'open' immediately (no broker → no 'pending'), so the open-only basis already counts
    # within-cycle cluster-mates — the real book's committed/pending fix (#12) isn't needed here.
    cluster = clusters.cluster_of(theme.symbol, cluster_map)
    cluster_remaining = None
    if cluster is not None:
        cluster_remaining = account_equity * cluster_fraction - state.shadow_cluster_open_premium(
            conn, clusters.members_of(cluster, cluster_map))
        if cluster_remaining < structure.entry_premium * CONTRACT_MULTIPLIER:
            return "cluster_cap"
    sizing = convexity_position_size(
        account_equity=account_equity,
        book_fraction=float(book.get("book_fraction", 0.10)),
        per_name_fraction=float(book.get("per_name_fraction", 0.01)),
        max_open_positions=int(book.get("max_open_positions", 15)),
        open_positions_count=state.count_open_shadow_positions(conn),
        open_premium_total=state.shadow_book_open_premium(conn),
        entry_premium_per_share=structure.entry_premium,
        cluster_remaining=cluster_remaining,
    )
    if sizing.contracts < 1:
        return "sizing"
    entry_pc = structure.entry_premium * CONTRACT_MULTIPLIER
    state.record_shadow_position(
        conn, run_id=run_id, origin=origin, opened_at=as_of_iso, theme=theme.name,
        symbol=theme.symbol, direction=theme.direction, structure_kind=structure.kind,
        contract_symbol=structure.contract.symbol, expiry=structure.contract.expiry.isoformat(),
        strike=structure.contract.strike, dte=structure.dte, moneyness=structure.moneyness,
        contracts=sizing.contracts, entry_premium_per_contract=entry_pc,
        total_premium=entry_pc * sizing.contracts, entry_spot=underlying_price,
    )
    return "booked"


def _intrinsic_value(kind: str, strike: float, underlying_price: float | None) -> float:
    """Per-share intrinsic at expiry. Local (not imported) to keep this module broker-import-free."""
    if underlying_price is None:
        return 0.0
    return max(0.0, underlying_price - strike) if kind == "C" else max(0.0, strike - underlying_price)


def mark_shadow_positions(
    *, conn, clock: Clock, quote_provider: QuoteProvider, config: dict, underlying_price_of=None,
) -> ShadowMonitorResult:
    """Mark + apply the SAME deterministic exits (profit-take / time-stop / expiry) to the shadow book.

    Always books in-DB at the mark/intrinsic — there is no broker (no real sell order, no proposal/
    sentinel resolution; those belong to the real book). Mirrors monitor.monitor_positions' exit rules
    and reads the same ``convexity_exits`` thresholds, so exits cannot drift from the real book."""
    exits = config.get("convexity_exits", {})
    profit_mult = float(exits.get("profit_take_multiple", 10.0))
    time_stop_dte = int(exits.get("time_stop_dte", 21))
    now = clock.now()
    today = now.date()
    as_of_iso = now.isoformat()
    res = ShadowMonitorResult()

    for pos in state.open_shadow_positions(conn):
        pid = int(pos["id"])
        kind = pos["structure_kind"]
        contracts = int(pos["contracts"])
        entry_pc = float(pos["entry_premium_per_contract"])
        total_premium = float(pos["total_premium"])
        expiry = _parse_date(pos["expiry"])
        dte = (expiry - today).days if expiry else None

        # 1. Expiry → close at intrinsic.
        if expiry is not None and today >= expiry:
            up = underlying_price_of(pos["symbol"]) if underlying_price_of else None
            intrinsic = _intrinsic_value(kind, float(pos["strike"]), up)
            _close(conn, pid, exit_price=intrinsic, entry_pc=entry_pc, contracts=contracts,
                   total_premium=total_premium, reason="expiry", as_of=as_of_iso)
            res.expired += 1
            res.closed += 1
            continue

        # 2. Mark to current mid.
        mid = quote_provider.option_mid(pos["contract_symbol"])
        if mid is None:
            res.unmarked += 1
            continue
        state.mark_shadow_position(conn, pid, mark=mid, as_of=as_of_iso)
        res.marked += 1

        # 3. Profit-take, then 4. time-stop — identical thresholds to the real monitor.
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
    state.close_shadow_position(conn, pid, exit_price=exit_price, realized_pnl=pnl,
                                realized_multiple=mult, reason=reason, as_of=as_of)


def tail_summary(multiples: list[float]) -> dict:
    """Per-position multiple TAIL stats (refinement #2 — the convex value is in the tail). Empty → zeros."""
    if not multiples:
        return {"n": 0, "mean": 0.0, "p50": 0.0, "p90": 0.0, "max": 0.0}
    xs = sorted(multiples)

    def _pct(p: float) -> float:
        i = min(len(xs) - 1, int(round(p * (len(xs) - 1))))
        return xs[i]

    return {"n": len(xs), "mean": sum(xs) / len(xs), "p50": _pct(0.5), "p90": _pct(0.9), "max": xs[-1]}


def tail_report(conn) -> dict[str, dict]:
    """Brain-off-vs-brain-on TAIL comparison: per-origin shadow multiples + the real book's, each
    summarized on the tail. The substrate for "does the LLM layer add value?" — read forward, never as
    a pass/fail (guardrail §6 / IMPLEMENTATION_PLAN §6)."""
    shadow = state.shadow_realized_multiples(conn)
    report = {f"shadow_{origin}": tail_summary(ms) for origin, ms in shadow.items()}
    report["shadow_all"] = tail_summary([m for ms in shadow.values() for m in ms])
    report["real"] = tail_summary(state.convexity_realized_multiples(conn))
    return report


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        s = str(value)
        return datetime.fromisoformat(s).date() if "T" in s else date.fromisoformat(s)
    except ValueError:
        return None
