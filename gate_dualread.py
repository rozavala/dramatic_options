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
                     gate: dict, eligibility, as_of: date | None = None, chain_sink=None) -> dict:
    """One arm's gate read with the SAME rv/spot as the of-record evaluation (isolates the option
    feed). Returns a row dict; an exception is the CALLER's to catch (it becomes a note row).

    ``as_of`` is the tenor anchor for ``select_structure`` (dte = expiry − as_of). The sweep passes
    its own ``as_of_iso`` date so the read is anchored on the cycle's clock, not the wall clock —
    live they coincide; under a fixed test clock the wall-clock default silently aged every
    synthetic contract out of the tenor window (the 2026-09-13 CI failure, 95 days after the
    fixture's AS_OF). Default (None) keeps the wall-clock behaviour for legacy callers.

    ``chain_sink`` (D4, 2026-11-03): called with the fetched chain before the gate read, so the sweep can record
    the IV term structure without a second fetch. Telemetry: a sink error never changes the gate read."""
    chain = provider.chain(symbol)
    if chain_sink is not None:
        try:
            chain_sink(chain)
        except Exception as e:  # noqa: BLE001 — telemetry never touches the gate read
            log.warning("chain sink failed for %s (non-fatal): %s", symbol, e)
    s, why = select_structure(
        chain, direction=direction, as_of=as_of or datetime.now().astimezone().date(),
        underlying_price=underlying_price,
        underlying_symbol=symbol,
        tenor_min_days=int(gate.get("tenor_min_days", 180)),
        tenor_max_days=int(gate.get("tenor_max_days", 365)),
        target_moneyness=float(gate.get("target_moneyness", 0.25)),
        require_otm_side=bool(gate.get("otm_side_guard", False)), min_otm_moneyness=float(gate.get("min_otm_moneyness", 0.0) or 0.0),
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


UNIT_WING_SESSIONS = 70   # PREREG_CHEAP_THEN_REPRICED §4.1 [PIN]: unit-date wings tracked for 70 sweep sessions


def tracked_contracts(conn, *, as_of: date, sessions: int = UNIT_WING_SESSIONS) -> dict[str, set[str]]:
    """The #455 tracked set per symbol, minus tonight's wing (added per name after its gate read):

    - the wing the OPRA sweep selected on each UNIT DATE (an ISO week's first sweep date) among the last ``sessions``
      sweep sessions, tonight included (so the ``sessions - 1`` sweep dates before ``as_of``);
    - the contract (and a vertical's short leg) of every open/closing position on the name in the real, shadow and
      fixed-basket (3A/3B) books. The shares book holds no option.

    Read-only, one pass over ``gate_dualread`` and the three position tables per sweep. The caller runs it inside the
    term sink's try/except: an error here only drops the ``quotes`` field."""
    day = as_of.isoformat()
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT substr(evaluated_at, 1, 10) AS d FROM gate_dualread WHERE feed = 'opra' AND source = 'sweep' "
        "AND substr(evaluated_at, 1, 10) < ? ORDER BY d", (day,))]
    weeks: dict[tuple[int, int], str] = {}
    for d in dates:   # the unit date of a week is its FIRST sweep date, over the whole history (not the window)
        weeks.setdefault(date.fromisoformat(d).isocalendar()[:2], d)
    window = set(dates[-(sessions - 1):]) if sessions > 1 else set()
    unit_dates = sorted(d for d in weeks.values() if d in window)
    out: dict[str, set[str]] = {}
    if unit_dates:
        marks = ",".join("?" for _ in unit_dates)
        last: dict[tuple[str, str], str | None] = {}
        for r in conn.execute(
                f"SELECT substr(evaluated_at, 1, 10) AS d, upper(symbol), structured, wing FROM gate_dualread "
                f"WHERE feed = 'opra' AND source = 'sweep' AND substr(evaluated_at, 1, 10) IN ({marks}) ORDER BY id",
                unit_dates):
            last[(r[0], r[1])] = r[3] if r[2] and r[3] else None   # the LAST sweep row of the date wins
        for (_d, sym), wing in last.items():
            if wing:
                out.setdefault(sym, set()).add(str(wing))
    for table in ("convexity_positions", "shadow_positions", "fixed_basket_positions"):
        for r in conn.execute(f"SELECT upper(symbol), contract_symbol, short_contract_symbol FROM {table} "
                              f"WHERE status IN ('open', 'closing')"):
            for occ in (r[1], r[2]):
                if occ:
                    out.setdefault(r[0], set()).add(str(occ))
    return out


def sweep_universe(conn, *, run_id, as_of_iso: str, symbols, provider_record, provider_shadow,
                   market_closes, gate: dict, eligibility, skip: set[str] | None = None,
                   term_cache=None) -> dict:
    """The §5 tripwire-population sweep (post-entries, fail-soft). ``market_closes(sym)`` supplies
    the closes for RV; ``skip`` = names already dual-read inline this run. Returns counts.

    ``term_cache`` (D4, 2026-11-03): when given, the OPRA arm's chain is summarized into the compact
    ``iv_term_snapshot`` record (iv_history.py) for every swept name. Fail-soft; counted as ``term_ok``.

    #455/#462 capture (PREREG_CHEAP_THEN_REPRICED §4.1): the record also carries ``rv63`` / ``rv21`` (on the same
    closes the sweep already holds) and ``quotes`` for the tracked contracts (tonight's selected wing, the unit-date
    wings of the last 70 sessions, every open/closing book contract on the name), read from the SAME chain the OPRA
    arm fetched — no extra fetch. The chain sink now only KEEPS the chain; the record is built and persisted after
    both arms of the name have been read and recorded, so tonight's wing is known. Every step of it (the tracked-set
    read, the rv computation, the quote lookup, the write) sits inside one try/except: an error leaves the record
    without the failing new field (or, at worst, unwritten for that name) and can never change, delay or skip a gate
    read or a ``gate_dualread`` row."""
    sweep_as_of = date.fromisoformat(str(as_of_iso)[:10])  # the cycle's clock anchors the tenor read
    from convexity_gate import realized_vol

    skip = {s.upper() for s in (skip or set())}
    counts = {"swept": 0, "record_ok": 0, "shadow_ok": 0, "errors": 0}
    if term_cache is not None:
        counts["term_ok"] = 0
    rv_window = int(gate.get("rv_window_days", 252))
    tracked: dict | None = None    # the #455 tracked set: read once per sweep, lazily, inside the term try/except
    tracked_failed = False
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
        sink = None
        kept: dict = {}
        if term_cache is not None:
            def sink(chain, _kept=kept):
                _kept["chain"] = chain       # keep only; the record is built after the gate reads (below)
        opra_row: dict | None = None
        for feed, prov, ok_key in (("opra", provider_record, "record_ok"),
                                   ("indicative", provider_shadow, "shadow_ok")):
            try:
                row = shadow_gate_eval(prov, symbol=sym, direction=direction, rv=rv,
                                       underlying_price=spot, gate=gate, eligibility=eligibility, as_of=sweep_as_of,
                                       chain_sink=(sink if feed == "opra" else None))
                record_arm(conn, run_id=run_id, as_of_iso=as_of_iso, symbol=sym, feed=feed,
                           source="sweep", row=row)
                if feed == "opra":
                    opra_row = row
                if row.get("structured"):
                    counts[ok_key] += 1
            except Exception as e:  # noqa: BLE001
                counts["errors"] += 1
                record_arm(conn, run_id=run_id, as_of_iso=as_of_iso, symbol=sym, feed=feed,
                           source="sweep", error=classify_error_note(e))
        if term_cache is not None and "chain" in kept:
            # The term record, after both arms of this name are read and recorded. EVERYTHING here is inside this
            # try/except (PREREG_CHEAP_THEN_REPRICED §4.1 build requirement): it cannot reach a gate read or a row.
            try:
                import iv_history

                extras: dict = {}
                try:
                    extras["rv63"] = realized_vol(closes, window=63)
                    extras["rv21"] = realized_vol(closes, window=21)
                except Exception as e:  # noqa: BLE001 — the record keeps its old fields
                    log.warning("term capture: rv63/rv21 failed for %s (non-fatal): %s", sym, e)
                    extras = {}
                try:
                    if tracked is None and not tracked_failed:
                        try:
                            tracked = tracked_contracts(conn, as_of=sweep_as_of)
                        except Exception as e:  # noqa: BLE001 — logged once; no quotes field tonight
                            tracked_failed = True
                            log.warning("term capture: tracked-set read failed (no quotes tonight): %s", e)
                    if tracked is not None:
                        want = set(tracked.get(sym, set()))
                        if opra_row and opra_row.get("structured") and opra_row.get("wing"):
                            want.add(str(opra_row["wing"]))
                        extras["quotes"] = iv_history.tracked_quotes(kept["chain"], want)
                except Exception as e:  # noqa: BLE001 — the record keeps its old fields
                    log.warning("term capture: quotes failed for %s (non-fatal): %s", sym, e)
                    extras.pop("quotes", None)
                as_of_dt = datetime.fromisoformat(str(as_of_iso))
                iv_history.persist_term_record(
                    term_cache, iv_history.term_record(sym, kept["chain"], spot=spot, rv=rv, as_of_dt=as_of_dt,
                                                       extras=extras), as_of_dt)
                counts["term_ok"] += 1
            except Exception as e:  # noqa: BLE001 — telemetry never touches the sweep
                log.warning("term record failed for %s (non-fatal): %s", sym, e)
    return counts
