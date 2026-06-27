"""Cheapness-watch (PREREG_CHEAPNESS_WATCH) — finding #1's gating instrument, the LIVE arm.

Read-only MEASUREMENT, never a trade, never wired into ``at_inflection`` (the hard seam). Two parts:

- ``record_cheapness`` — per active sentinel, per day, the gate-`cheap` read on the **real tradeable
  structure** (the live real-extractor: ``select_structure`` → ``is_cheap_convexity``) + the marker
  state + ``marker_age_days`` (the migration-0016 staleness stamp). Fail-soft per name; the dynamic
  active-sentinel cohort (§3). Append-only to ``cheapness_watch`` (migration 0017).
- ``cheapness_report`` — the §2.1 state machine over the daily history: debounced break-onset, sustained
  (2-consecutive) close, the three ``cheap_window``/``never_cheap`` states, the ``marker_age_at_break``
  SELECTION dimension, and the §7.1 JOINT trigger with the N-floor (``insufficient_N`` until ≥
  ``n_qualify_floor`` qualifying stale∧catchable breaks — no verdict off noise).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

import state
from convexity_gate import is_cheap_convexity, realized_vol
from structure import contract_eligible, select_structure

log = logging.getLogger("cheapness_watch")

FRESH_RV_FLOOR = 0.10    # §2.1.1 break-onset (mirrors discovery.MarkerParams.fresh_rv_rising_floor)
FRESH_MOM_FLOOR = 0.20   # §2.1.1
DEFAULT_STALENESS_LAG_DAYS = 20.0   # the §7.1 comparator (live 16.7d median / 23.7d max, run #337)
DEFAULT_N_QUALIFY_FLOOR = 5          # §2.1.6 — no fire/hold verdict below this many qualifying breaks


def _age_days(as_of: datetime, markers_asof: str | None) -> float | None:
    if not markers_asof:
        return None
    try:
        return (as_of - datetime.fromisoformat(markers_asof)).total_seconds() / 86400.0
    except (ValueError, TypeError):
        return None


def record_cheapness(conn, *, provider, config: dict, as_of: datetime, run_id: int | None = None) -> int:
    """Record one daily cheapness observation per active sentinel. Returns the count recorded.

    ``provider`` is duck-typed (``underlying_price``/``chain``/``closes`` — the live OPRA provider, or a
    synthetic one offline). Fail-soft: a per-name error logs + skips that name, never blocks the sweep."""
    gate = config.get("convexity_gate", {})
    elig = config.get("eligibility", {}).get("live", {})
    rv_window = int(gate.get("rv_window_days", 252))
    as_of_iso = as_of.isoformat()
    n = 0
    for row in state.active_sentinel_rows(conn):
        try:
            _record_one(conn, row, provider=provider, gate=gate, elig=elig, rv_window=rv_window,
                        as_of=as_of, as_of_iso=as_of_iso, run_id=run_id)
            n += 1
        except Exception as e:  # noqa: BLE001 — a per-name failure never blocks the sweep (fail-soft)
            log.warning("cheapness_watch: %s skipped: %s", row["symbol"], e)
    return n


def _record_one(conn, row, *, provider, gate, elig, rv_window, as_of, as_of_iso, run_id) -> None:
    symbol = row["symbol"]
    try:
        markers = json.loads(row["markers"]) if row["markers"] else {}
    except (ValueError, TypeError):
        markers = {}
    last_seen = row["last_seen_at"]
    underlying_price = provider.underlying_price(symbol)
    chain = provider.chain(symbol)
    closes = provider.closes(symbol, window=rv_window)
    rv = realized_vol(closes, window=rv_window)

    def _eligibility(c):  # the live entry's contract gate (paper_loop._eligibility), real-extractor
        return contract_eligible(
            c, max_spread_pct=float(elig.get("max_bid_ask_pct", 0.25)),
            min_contract_price=0.10, max_contract_price=100.0,
            min_oi=elig.get("min_option_open_interest"),
        )

    structure, _reasons = select_structure(
        chain, direction=row["direction"], as_of=as_of.date(), underlying_price=underlying_price,
        tenor_min_days=int(gate.get("tenor_min_days", 180)),
        tenor_max_days=int(gate.get("tenor_max_days", 365)),
        target_moneyness=float(gate.get("target_moneyness", 0.25)),
        eligibility=_eligibility,
    )
    contract_symbol = iv_rv = otm_skew = cheap = atm_iv = wing_iv = None
    if structure is not None:
        # the SAME gate the live entry runs — real-extractor, never a proxy wing (§2.2)
        v = is_cheap_convexity(
            chain, underlying_price=underlying_price, wing=structure.contract, rv=rv,
            iv_rv_max=float(gate.get("iv_rv_max", 1.2)),
            otm_skew_max_volpts=float(gate.get("otm_skew_max_volpts", 10.0)),
        )
        contract_symbol = structure.contract.symbol
        iv_rv, otm_skew, cheap = v.iv_rv_ratio, v.otm_skew_volpts, int(v.cheap)
        atm_iv, wing_iv = v.atm_iv, v.wing_iv
    with conn:
        conn.execute(
            "INSERT INTO cheapness_watch (run_id, as_of, symbol, contract_symbol, iv_rv, otm_skew, "
            "cheap, atm_iv, wing_iv, rv, rv_rising, mom_recent, markers_asof, marker_age_days, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (run_id, as_of_iso, symbol, contract_symbol, iv_rv, otm_skew, cheap, atm_iv, wing_iv, rv,
             markers.get("rv_rising"), markers.get("mom_recent"), last_seen, _age_days(as_of, last_seen)),
        )


# ── the §2.1 state machine + the §7.1 JOINT trigger ──────────────────────────────────────────────


def _window_len(rows: list, onset_i: int) -> int:
    """Count of CHEAP sessions from onset until SUSTAINED close = 2 consecutive not-cheap (§2.1.2);
    a 1-session not-cheap blip does NOT close it (the run resets on the next cheap session)."""
    window = 0
    notcheap_run = 0
    for j in range(onset_i, len(rows)):
        if rows[j]["cheap"] == 1:
            window += 1
            notcheap_run = 0
        else:  # 0 (not cheap) or None (no structure) — both count toward the sustained-close run
            notcheap_run += 1
            if notcheap_run >= 2:
                break
    return window


def _detect_breaks(symbol: str, rows: list, fresh_rv: float, fresh_mom: float) -> list[dict]:
    """One name's break events (§2.1.1 debounced onset → §2.1.2/.3 state). ``rows`` ordered by as_of."""
    breaks: list[dict] = []
    prev_fresh = False
    for i, r in enumerate(rows):
        rvr, mom = r["rv_rising"], r["mom_recent"]
        is_fresh = (rvr is not None and rvr >= fresh_rv and mom is not None and abs(mom) >= fresh_mom)
        if is_fresh and not prev_fresh:  # break-onset (debounced: prior session was BELOW the fresh leg)
            age = r["marker_age_days"]
            if r["cheap"] is None:        # no eligible structure at onset → unmeasurable, not a state
                breaks.append({"symbol": symbol, "state": "no_structure",
                               "cheap_window_days": None, "marker_age_at_break": age})
            elif r["cheap"] == 0:         # not cheap AT onset → never_cheap (§2.1.3, distinct from ==0)
                breaks.append({"symbol": symbol, "state": "never_cheap",
                               "cheap_window_days": None, "marker_age_at_break": age})
            else:                          # cheap at onset → measure the window
                breaks.append({"symbol": symbol, "state": "cheap_window",
                               "cheap_window_days": _window_len(rows, i), "marker_age_at_break": age})
        prev_fresh = is_fresh
    return breaks


def cheapness_report(conn, *, staleness_lag_days: float = DEFAULT_STALENESS_LAG_DAYS,
                     n_qualify_floor: int = DEFAULT_N_QUALIFY_FLOOR,
                     fresh_rv: float = FRESH_RV_FLOOR, fresh_mom: float = FRESH_MOM_FLOOR) -> dict:
    """The §7.1 JOINT trigger over the recorded history, with the N-floor (§2.1.6).

    QUALIFYING = stale-markers (``marker_age_at_break ≥ staleness_lag``) ∧ catchable (a `cheap_window`
    state) — the harm the persist would fix. Verdict ``insufficient_N`` below the floor (no decision off
    noise); else ``fire`` iff the qualifying ``cheap_window_days`` median sits below the lag, else ``hold``.
    ``never_cheap`` / ``no_structure`` / fresh-marker breaks are reported separately, never folded in."""
    by_sym: dict[str, list] = {}
    for r in conn.execute(
        "SELECT symbol, as_of, cheap, rv_rising, mom_recent, marker_age_days "
        "FROM cheapness_watch ORDER BY symbol, as_of"
    ):
        by_sym.setdefault(r["symbol"], []).append(r)

    breaks: list[dict] = []
    for sym, rows in by_sym.items():
        breaks.extend(_detect_breaks(sym, rows, fresh_rv, fresh_mom))

    never_cheap = [b for b in breaks if b["state"] == "never_cheap"]
    no_structure = [b for b in breaks if b["state"] == "no_structure"]
    catchable = [b for b in breaks if b["state"] == "cheap_window"]
    # the §7.1 SELECTION join: fresh-marker breaks are benign-by-construction (at_inflection saw them)
    fresh = [b for b in catchable if (b["marker_age_at_break"] or 0.0) < staleness_lag_days]
    qualifying = [b for b in catchable if (b["marker_age_at_break"] or 0.0) >= staleness_lag_days]

    windows = sorted(b["cheap_window_days"] for b in qualifying)
    if len(qualifying) < n_qualify_floor:
        verdict = "insufficient_N"
    else:
        median = windows[len(windows) // 2]
        verdict = "fire" if median < staleness_lag_days else "hold"

    return {
        "verdict": verdict,
        "n_qualify_floor": n_qualify_floor,
        "staleness_lag_days": staleness_lag_days,
        "n_obs": sum(len(v) for v in by_sym.values()),
        "n_names": len(by_sym),
        "n_breaks": len(breaks),
        "n_never_cheap": len(never_cheap),
        "n_no_structure": len(no_structure),
        "n_fresh_marker": len(fresh),
        "n_qualifying": len(qualifying),
        "qualifying_windows": windows,
        "note": "verdict gated by the N-floor; QUALIFYING = stale-markers ∧ catchable-cheap (the §7.1 "
                "JOINT — what the persist would fix). fresh-marker breaks benign-by-construction; "
                "never_cheap = catchability-not-the-race; insufficient_N is the EXPECTED long-term state "
                "(conjunctive filters make qualifying breaks rare) — a sustained one is itself the finding.",
    }
