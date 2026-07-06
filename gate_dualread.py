"""The OPRA/INDICATIVE gate dual-read (PREREG_DATA_FEED_OPRA_SEQUENCING §5–§6).

The gate-of-record is OPRA; INDICATIVE runs as the additive SHADOW arm. Two duties:

1. **Inline** (an evaluated candidate, pre-entry): re-evaluate the exact gate inputs on the
   shadow feed and record BOTH arms; if the arms DISAGREE on ``cheap`` for a would-enter name,
   the date-gated ``veto-dualread-disagree`` applies (§5 response 1 — the shadow can only
   TIGHTEN, never authorize, and the rule AUTO-LAPSES at
   ``config.data_feed.dualread_disagree_veto_until``; renewal is a dated edit).
2. **Sweep** (post-entries, fail-soft): the rest of the option-eligible universe on both feeds —
   the §5 tripwire population (coverage gaps, |Δ iv/rv| median/max, cheap-flips).

Everything here is fail-SOFT: a shadow failure writes a structured=0 row with the error note
(the both-arms coverage guard — a silently-empty arm must never masquerade as agreement) and
never blocks the cycle. Pure helpers + an injected provider → offline-testable.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import state
from convexity_gate import is_cheap_convexity
from structure import select_structure

log = logging.getLogger("gate_dualread")


def disagree_veto_active(config: dict, as_of: date) -> bool:
    """The §5 disagree-veto is date-gated: active until ``dualread_disagree_veto_until``
    (inclusive), then inert unless renewed by a dated config edit."""
    until = (config.get("data_feed", {}) or {}).get("dualread_disagree_veto_until")
    if not until:
        return False
    try:
        return as_of <= date.fromisoformat(str(until))
    except ValueError:
        return False  # a malformed date never grants the shadow arm veto power


def shadow_gate_eval(provider, *, symbol: str, direction: str, rv, underlying_price,
                     gate: dict, eligibility) -> dict:
    """One arm's gate read with the SAME rv/spot as the of-record evaluation (isolates the option
    feed). Returns a row dict; an exception is the CALLER's to catch (it becomes a note row)."""
    chain = provider.chain(symbol)
    s, why = select_structure(
        chain, direction=direction, as_of=datetime.now().astimezone().date(),
        underlying_price=underlying_price,
        underlying_symbol=symbol,
        tenor_min_days=int(gate.get("tenor_min_days", 180)),
        tenor_max_days=int(gate.get("tenor_max_days", 365)),
        target_moneyness=float(gate.get("target_moneyness", 0.25)),
        eligibility=eligibility,
    )
    if s is None:
        return {"structured": False, "note": (why[0] if why else "no_structure")}
    v = is_cheap_convexity(
        chain, underlying_price=underlying_price, wing=s.contract, rv=rv,
        iv_rv_max=float(gate.get("iv_rv_max", 1.2)),
        otm_skew_max_volpts=float(gate.get("otm_skew_max_volpts", 10.0)),
    )
    return {"structured": True, "iv_rv": v.iv_rv_ratio, "otm_skew": v.otm_skew_volpts,
            "cheap": bool(v.cheap), "wing": s.contract.symbol}


def classify_error_note(exc: BaseException) -> str:
    """A sweep-arm fetch error → a CLASSIFIED ``note`` prefix (#72, §5 close-out / decision #1).

    Mirrors ``paper_loop``'s ``f"{kind}: {e}"`` (the §7 inline entry-veto) so the sweep population
    carries the SAME entitlement/transient signal §7 records only for evaluated names. The prefix is
    what the §5 coverage-gap partition reads to route an OPRA ``¬structured`` row to its class
    (``entitlement:`` → feed-wide hold; ``transient:`` → per-name escalation; anything else, i.e. a
    structural ``select_structure`` reason, → structural-absence). No migration — it rides ``note``."""
    from feeds import classify_feed_error

    return f"{classify_feed_error(exc)}: {exc}"


def record_arm(conn, *, run_id, as_of_iso: str, symbol: str, feed: str, source: str,
               row: dict | None = None, error: str | None = None) -> None:
    """Persist one arm (fail-soft at the call site). A failed arm is a structured=0 + note row."""
    if row is None:
        row = {"structured": False, "note": (error or "error")[:300]}
    state.record_gate_dualread(
        conn, run_id=run_id, as_of=as_of_iso, symbol=symbol, feed=feed, source=source,
        structured=row.get("structured"), iv_rv=row.get("iv_rv"), otm_skew=row.get("otm_skew"),
        cheap=row.get("cheap"), wing=row.get("wing"), note=row.get("note"),
    )


def sweep_universe(conn, *, run_id, as_of_iso: str, symbols, provider_record, provider_shadow,
                   market_closes, gate: dict, eligibility, skip: set[str] | None = None) -> dict:
    """The §5 tripwire-population sweep (post-entries, fail-soft). ``market_closes(sym)`` supplies
    the closes for RV; ``skip`` = names already dual-read inline this run. Returns counts."""
    from convexity_gate import realized_vol

    skip = {s.upper() for s in (skip or set())}
    counts = {"swept": 0, "record_ok": 0, "shadow_ok": 0, "errors": 0}
    rv_window = int(gate.get("rv_window_days", 252))
    for sym in symbols:
        sym = sym.upper()
        if sym in skip:
            continue
        counts["swept"] += 1
        try:
            closes = market_closes(sym)
            rv = realized_vol(closes, window=rv_window)
            spot = closes[-1] if closes else None
            mom = (closes[-22] / closes[-253] - 1.0) if closes and len(closes) >= 253 else None
            direction = "bullish" if (mom is None or mom > 0) else "bearish"
            if not spot or rv is None:
                counts["errors"] += 1
                record_arm(conn, run_id=run_id, as_of_iso=as_of_iso, symbol=sym, feed="opra",
                           source="sweep", error="no rv/spot")
                continue
        except Exception as e:  # noqa: BLE001 — the sweep is measurement, never a cycle blocker
            counts["errors"] += 1
            record_arm(conn, run_id=run_id, as_of_iso=as_of_iso, symbol=sym, feed="opra",
                       source="sweep", error=classify_error_note(e))
            continue
        for feed, prov, ok_key in (("opra", provider_record, "record_ok"),
                                   ("indicative", provider_shadow, "shadow_ok")):
            try:
                row = shadow_gate_eval(prov, symbol=sym, direction=direction, rv=rv,
                                       underlying_price=spot, gate=gate, eligibility=eligibility)
                record_arm(conn, run_id=run_id, as_of_iso=as_of_iso, symbol=sym, feed=feed,
                           source="sweep", row=row)
                if row.get("structured"):
                    counts[ok_key] += 1
            except Exception as e:  # noqa: BLE001
                counts["errors"] += 1
                record_arm(conn, run_id=run_id, as_of_iso=as_of_iso, symbol=sym, feed=feed,
                           source="sweep", error=classify_error_note(e))
    return counts
