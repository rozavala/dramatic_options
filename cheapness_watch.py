"""Cheapness-watch (PREREG_CHEAPNESS_WATCH) — finding #1's gating instrument, the LIVE arm.

Read-only MEASUREMENT, never a trade, never wired into ``at_inflection`` (the hard seam). Two parts:

- ``record_cheapness`` — per active sentinel, per day, the gate-`cheap` read on the **real tradeable
  structure** (the live real-extractor: ``select_structure`` → ``is_cheap_convexity``) + the marker
  state + ``marker_age_days`` (the migration-0016 staleness stamp). Fail-soft per name; the dynamic
  active-sentinel cohort (§3). Append-only to ``cheapness_watch`` (migration 0017).
- ``cheapness_report`` — the §2.1 state machine over the daily history: debounced break-onset, sustained
  (2-consecutive) close, the three ``cheap_window``/``never_cheap`` states, the ``marker_age_at_break``
  SELECTION dimension, and the §7.1 JOINT trigger with the N-floor (``insufficient_N`` until ≥
  ``n_qualify_floor`` qualifying stale∧catchable breaks — no verdict off noise). The §2.1.7 rate-clock is
  fail-CLOSED: ``observed_days`` (→ ``qualifying_per_quarter``) starts only once the cohort holds a
  COUNCIL-CONFIRMED-QUIET name (strategist ``under_narrated=True`` at first judgment), never at first
  observation — a not-yet-break-capable cohort reads a ``None`` rate, not a diluted false negative.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import state
from convexity_gate import is_cheap_convexity, realized_vol
from structure import contract_eligible, select_structure

log = logging.getLogger("cheapness_watch")

FRESH_RV_FLOOR = 0.10    # §2.1.1 break-onset (mirrors discovery.MarkerParams.fresh_rv_rising_floor)
FRESH_MOM_FLOOR = 0.20   # §2.1.1
# §2.1.7 — the fail-CLOSED clock-start basis (record-segmentation key; stamped onto runs.model_mix). A
# change here means rate values from the prior basis are NOT comparable (segments the record).
CLOCK_BASIS = "council_confirmed_under_narrated_v1"
DEFAULT_STALENESS_LAG_DAYS = 20.0   # the §7.1 comparator (live 16.7d median / 23.7d max, run #337)
DEFAULT_N_QUALIFY_FLOOR = 5          # §2.1.6 — no fire/hold verdict below this many qualifying breaks
DEGEN_SUSTAINED_RUN = 2              # §2.1.8 — a SUSTAINED unreadable run (≥2, mirroring the §2.1.2 close) truncates

# §2.1.8 degenerate_iv bounds — the operator-pinned defaults (mirror config.convexity_gate; pinned BLIND,
# once, from physics + the live gate-pass distribution). The three clip-axis disjuncts (skew_abs_max,
# iv_floor, wing_atm_ratio_min_k) are a SINGLE cheap-wing-clip budget; iv_rv_sanity_max (high-side) is the
# only clip-free disjunct. Report-time MEASUREMENT only — these never touch the live gate (that is §2.4).
DEFAULT_DEGEN_BOUNDS: dict[str, float] = {
    "skew_abs_max_volpts": 100.0,
    "iv_rv_sanity_max": 5.0,
    "iv_floor_annualized": 0.03,
    "wing_atm_ratio_min_k": 0.15,
}


def bounds_from_config(config: dict | None) -> dict[str, float]:
    """The §2.1.8 degenerate bounds from ``config.convexity_gate`` (new keys), falling back to the pinned
    defaults key-by-key (config-over-code; a partial/absent config still measures with the frozen pins)."""
    gate = (config or {}).get("convexity_gate", {})
    return {k: float(gate.get(k, v)) for k, v in DEFAULT_DEGEN_BOUNDS.items()}


def _age_days(as_of: datetime, markers_asof: str | None) -> float | None:
    if not markers_asof:
        return None
    try:
        return (as_of - datetime.fromisoformat(markers_asof)).total_seconds() / 86400.0
    except (ValueError, TypeError):
        return None


def _fresh_freshness(closes: list[float] | None, *, mom_lookback: int = 63, rv_recent: int = 21,
                     rv_mid: int = 63) -> tuple[float | None, float | None]:
    """Recompute the funnel's fresh-leg markers from CURRENT bars (mirrors discovery.compute_markers's
    ``mom_recent``/``rv_rising``): ``mom_recent`` = the recent 63d return (skip 0), ``rv_rising`` =
    ``(rv_21 − rv_63)/rv_63``. FRESH each day so a real break is DETECTED — the persisted snapshot is
    constant between L0s (the silent no-op this avoids). Returns (mom_recent, rv_rising); None on thin bars."""
    if not closes or len(closes) <= mom_lookback:
        return None, None
    mom = closes[-1] / closes[-(mom_lookback + 1)] - 1.0
    r_recent = realized_vol(closes[-(rv_recent + 1):], window=rv_recent)
    r_mid = realized_vol(closes[-(rv_mid + 1):], window=rv_mid)
    rising = ((r_recent - r_mid) / r_mid) if (r_recent and r_mid and r_mid > 0) else None
    return mom, rising


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
    last_seen = row["last_seen_at"]
    underlying_price = provider.underlying_price(symbol)
    chain = provider.chain(symbol)
    closes = provider.closes(symbol, window=rv_window)
    rv = realized_vol(closes, window=rv_window)
    # FRESH freshness markers — recomputed from CURRENT bars each day, NOT row["markers"] (the persisted
    # snapshot is constant between L0 re-surfaces → break-onset could never fire = a silent no-op on the
    # exact stale-marker break this watch exists to catch). marker_age_days (below) still uses the
    # PERSISTED last_seen_at — THAT measures the council's staleness; the fresh markers DETECT the break.
    mom_recent, rv_rising = _fresh_freshness(closes)

    def _eligibility(c):  # the live entry's contract gate (paper_loop._eligibility), real-extractor
        return contract_eligible(
            c, max_spread_pct=float(elig.get("max_bid_ask_pct", 0.25)),
            min_contract_price=0.10, max_contract_price=100.0,
            min_oi=elig.get("min_option_open_interest"),
        )

    structure, _reasons = select_structure(
        chain, direction=row["direction"], as_of=as_of.date(), underlying_price=underlying_price,
        underlying_symbol=symbol,
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
             rv_rising, mom_recent, last_seen, _age_days(as_of, last_seen)),
        )


# ── §2.1.8 the degenerate_iv / unmeasurable classifier (None-safe; report-time MEASUREMENT only) ──


def _degenerate_trip(row, bounds: dict[str, float]) -> tuple[str, float] | None:
    """The §2.1.8.A per-session disjunction over the persisted raw IV columns. Returns the FIRST tripping
    ``(which_bound, offending_value)`` or ``None`` (sane). None-safe per-disjunct — a stray ``None`` never
    raises and never spuriously trips. Disjuncts (any → degenerate): ``|otm_skew| > skew_abs_max`` (a leg
    diverges hard; absolute → both tails), ``iv_rv > iv_rv_sanity_max`` (ATM ≫ trailing RV; the only
    clip-FREE disjunct), ``atm_iv < iv_floor`` OR ``wing_iv < iv_floor`` (either leg implausibly low),
    ``wing_iv < k·atm_iv`` (wing implausibly low RELATIVE to ATM — the moderate seam, the load-bearing
    catch for a clean-ATM / garbage-wing name whose skew sits below the |skew| ceiling)."""
    atm_iv, wing_iv = row["atm_iv"], row["wing_iv"]
    iv_rv, otm_skew = row["iv_rv"], row["otm_skew"]
    skew_abs_max = bounds["skew_abs_max_volpts"]
    iv_rv_max = bounds["iv_rv_sanity_max"]
    iv_floor = bounds["iv_floor_annualized"]
    k = bounds["wing_atm_ratio_min_k"]
    if otm_skew is not None and abs(otm_skew) > skew_abs_max:
        return ("otm_skew_abs", otm_skew)
    if iv_rv is not None and iv_rv > iv_rv_max:          # the clip-free high-side disjunct
        return ("iv_rv_sanity", iv_rv)
    if atm_iv is not None and atm_iv < iv_floor:
        return ("atm_iv_floor", atm_iv)
    if wing_iv is not None and wing_iv < iv_floor:
        return ("wing_iv_floor", wing_iv)
    if wing_iv is not None and atm_iv is not None and wing_iv < k * atm_iv:
        return ("wing_atm_ratio", wing_iv)
    return None


def _classify(row, bounds: dict[str, float]) -> str:
    """One session → ``cheap`` / ``not_cheap`` / ``degenerate_iv`` / ``unmeasurable`` / ``no_structure``
    (§2.1.8). None-safe, never raises. Order (load-bearing): the missing-input fail-close
    (``cheap==0 ∧ iv_rv IS None``) is ``unmeasurable`` BEFORE the bound check (degenerate needs IVs
    present); then a present-and-bound-tripping read is ``degenerate_iv`` (this re-routes a FALSE
    ``cheap=1`` out of qualifying — the R2 verdict-corruptor); else map the gate boolean
    ``1/0/None`` → ``cheap`` / ``not_cheap`` / ``no_structure``."""
    cheap = row["cheap"]
    if cheap == 0 and row["iv_rv"] is None:     # the missing-input fail-close (P2a) — distinct from rich
        return "unmeasurable"
    if _degenerate_trip(row, bounds) is not None:
        return "degenerate_iv"
    if cheap == 1:
        return "cheap"
    if cheap == 0:
        return "not_cheap"
    return "no_structure"                        # cheap IS None


# ── §2.1.7 the fail-closed clock-start gate (council-confirmed-quiet) ─────────────────────────────


def _parse_iso(s: str | None) -> datetime | None:
    """Parse an ISO timestamp → a tz-NORMALIZED naive datetime (UTC wall-clock), so the council judgment's
    tz-aware ``as_of`` and the watch's (often naive, date-only) ``as_of`` compare without a naive-vs-aware
    TypeError (the migration-0016 tz-offset hazard). None on an unparseable/empty value (fail-soft)."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _clock_start(conn, by_sym: dict[str, list]) -> dict:
    """The §2.1.7 fail-CLOSED clock-start. ``observed_days`` (→ ``qualifying_per_quarter``) counts only from
    the day the active-sentinel cohort first held ≥1 **council-confirmed-quiet** name — the strategist's
    ``under_narrated=True`` at FIRST judgment with ``parse_error=false`` (the binding tri-criteria role).
    Replaces the fail-OPEN ``max−min(as_of)`` over all rows (which started the clock at first observation,
    diluting the rate over uninterpretable not-yet-break-capable days).

    Mapping (cohort-name → council-read): a watched ``symbol`` is confirmed-quiet iff
    ``state.council_first_judgment_under_narrated`` reports ``confirmed_quiet`` for it; the clock-start DATE
    is the first watch ``as_of`` at/after that name's first-judgment ``as_of`` (so the clock starts when the
    name is BOTH judged-quiet AND being watched). The earliest such date across confirmed-quiet names is the
    clock-start; ``observed_days`` = last watch ``as_of`` − clock-start.

    Anti-survivorship (pinned): the confirmation is FROZEN at first judgment. A name that narrates LATER stays
    in the cohort and keeps its clock-start (during-window narration is the break-rate signal being measured,
    not a disqualifier — dropping narrators biases the break-rate toward zero).

    Returns the audit block folded into the report (clock-start basis + per-role composition). Read-only;
    fail-soft (an unparseable timestamp drops that name from the gate, never raises)."""
    reads = state.council_first_judgment_under_narrated(conn)
    confirmed = {sym: rd for sym, rd in reads.items() if rd.get("confirmed_quiet")}

    all_asof = [a for rows in by_sym.values() for r in rows if (a := _parse_iso(r["as_of"])) is not None]
    last_obs = max(all_asof) if all_asof else None

    # Per confirmed-quiet name actually being watched: clock-start = first watch obs at/after its first
    # judgment. (A name confirmed-quiet but never watched cannot start the clock — no break-capable OBS.)
    candidates: list[tuple[datetime, str]] = []
    composition: dict[str, dict] = {}
    for sym, rd in confirmed.items():
        rows = by_sym.get(sym)
        if not rows:
            continue
        judged = _parse_iso(rd.get("as_of"))
        obs = sorted(a for r in rows if (a := _parse_iso(r["as_of"])) is not None)
        if judged is None or not obs:
            continue
        start = next((o for o in obs if o >= judged), None)
        if start is None:  # judged AFTER the last observation of this name → not yet clock-capable here
            continue
        candidates.append((start, sym))
        composition[sym] = {"first_judgment_as_of": rd.get("as_of"), "clock_start_obs": start.isoformat(),
                            "under_narrated": rd.get("under_narrated"), "parse_error": rd.get("parse_error"),
                            "per_role": rd.get("per_role", {})}

    clock_start: datetime | None = min((c[0] for c in candidates), default=None)
    observed_days = None
    if clock_start is not None and last_obs is not None and last_obs > clock_start:
        observed_days = (last_obs - clock_start).total_seconds() / 86400.0

    return {
        "observed_days": observed_days,
        "clock_started": clock_start is not None,
        "clock_start": clock_start.isoformat() if clock_start else None,
        "clock_start_symbol": (min(candidates)[1] if candidates else None),
        "n_confirmed_quiet": len(confirmed),
        "n_confirmed_quiet_watched": len(candidates),
        "confirmed_quiet_symbols": sorted(confirmed),
        "composition": composition,
        "clock_basis": CLOCK_BASIS,
    }


# ── the §2.1 state machine + the §7.1 JOINT trigger ──────────────────────────────────────────────


def _window_len(rows: list, onset_i: int, bounds: dict[str, float]) -> tuple[int, str]:
    """§2.1.8 three-input debounce → ``(cheap_window_days, end_reason)``. Inputs collapse to cheap /
    not_cheap / ``unreadable`` (= ``degenerate_iv`` ∨ ``unmeasurable``; ``no_structure`` stays the
    not_cheap column, as in the original 2-state machine). end_reason ∈ {``closed``, ``truncated``,
    ``open_at_end``}:

    - CLOSED = 2 consecutive not_cheap (the §2.1.2 sustained close) — an EXACT length.
    - TRUNCATE = a SUSTAINED unreadable run (≥2, mirroring the §2.1.2 threshold) → lost visibility; the
      window is right-censored at the last clean cheap (unreadable sessions never increment ``window``).
    - an isolated unreadable BLIP is TRANSPARENT (neither advances nor resets the close-run).
    - ``open_at_end`` = ran off the end still cheap / mid-close (right-censored; the COMMON recent-break case).
    """
    window = 0
    notcheap_run = 0   # 0 = IN_WINDOW, 1 = CLOSING (the §2.1.2 macro-state), 2 = CLOSED
    degen_run = 0
    for j in range(onset_i, len(rows)):
        label = _classify(rows[j], bounds)
        unreadable = label in ("degenerate_iv", "unmeasurable")
        if unreadable:                       # transparent blip OR sustained-truncate; close-run untouched
            degen_run += 1
            if degen_run >= DEGEN_SUSTAINED_RUN:
                return window, "truncated"
            continue                          # window & notcheap_run unchanged (run transparent)
        degen_run = 0                         # any cheap/not_cheap resets the unreadable run
        if label == "cheap":
            window += 1
            notcheap_run = 0                  # IN_WINDOW (a cheap session clears a 1-session close blip)
        else:                                 # not_cheap (or no_structure) — toward the sustained close
            notcheap_run += 1
            if notcheap_run >= 2:
                return window, "closed"       # CLOSED — finalize (the 2nd not_cheap is not counted)
    return window, "open_at_end"             # ran to the end without a sustained close → right-censored


def _detect_breaks(symbol: str, rows: list, fresh_rv: float, fresh_mom: float,
                   bounds: dict[str, float]) -> list[dict]:
    """One name's break events (§2.1.1 debounced onset → §2.1.2/.3/.8 state). ``rows`` ordered by as_of.

    §2.1.8: the onset session is CLASSIFIED. ``degenerate_iv`` and ``unmeasurable`` are onset states
    EXCLUDED from BOTH ``qualifying`` and ``never_cheap`` (parallel to ``no_structure``); ``_window_len``
    is not called for them. The break is never hidden — only re-attributed off a mis-bucketed read."""
    breaks: list[dict] = []
    prev_fresh = False
    for i, r in enumerate(rows):
        rvr, mom = r["rv_rising"], r["mom_recent"]
        is_fresh = (rvr is not None and rvr >= fresh_rv and mom is not None and abs(mom) >= fresh_mom)
        if is_fresh and not prev_fresh:  # break-onset (debounced: prior session was BELOW the fresh leg)
            age = r["marker_age_days"]
            label = _classify(r, bounds)
            if label in ("degenerate_iv", "unmeasurable"):  # §2.1.8 onset states — out of qualifying & never_cheap
                breaks.append({"symbol": symbol, "state": label, "cheap_window_days": None,
                               "marker_age_at_break": age, "end_reason": None, "row": r})
            elif label == "no_structure":   # no eligible structure at onset → not a state
                breaks.append({"symbol": symbol, "state": "no_structure",
                               "cheap_window_days": None, "marker_age_at_break": age, "end_reason": None})
            elif label == "not_cheap":      # not cheap AT onset → never_cheap (§2.1.3, IV already popped)
                breaks.append({"symbol": symbol, "state": "never_cheap",
                               "cheap_window_days": None, "marker_age_at_break": age, "end_reason": None})
            else:                           # cheap at onset → measure the window (with the end-reason)
                wlen, end_reason = _window_len(rows, i, bounds)
                breaks.append({"symbol": symbol, "state": "cheap_window", "cheap_window_days": wlen,
                               "marker_age_at_break": age, "end_reason": end_reason})
        prev_fresh = is_fresh
    return breaks


def cheapness_report(conn, *, staleness_lag_days: float = DEFAULT_STALENESS_LAG_DAYS,
                     n_qualify_floor: int = DEFAULT_N_QUALIFY_FLOOR,
                     fresh_rv: float = FRESH_RV_FLOOR, fresh_mom: float = FRESH_MOM_FLOOR,
                     bounds: dict[str, float] | None = None) -> dict:
    """The §7.1 JOINT trigger over the recorded history, with the N-floor (§2.1.6) and the §2.1.8
    degenerate/unmeasurable reclassification + right-censoring.

    QUALIFYING = stale-markers (``marker_age_at_break ≥ staleness_lag``) ∧ catchable (a `cheap_window`
    state). §2.1.8: a window that ended ``truncated``/``open_at_end`` is RIGHT-CENSORED — at ``V ≥ lag`` it
    is a definitive HOLD vote (kept); at ``V < lag`` it is uninformative (``censored_short`` — excluded from
    BOTH the verdict median AND the N-floor). Verdict ``insufficient_N`` below the floor (no decision off
    noise); else ``fire`` iff the decision-set ``cheap_window_days`` median sits below the lag, else ``hold``.
    ``degenerate_iv`` / ``unmeasurable`` / ``never_cheap`` / ``no_structure`` / fresh-marker breaks are
    reported separately, never folded in. ``bounds`` defaults to the pinned §2.1.8 degenerate bounds.

    §2.1.7 (fail-CLOSED clock-start): ``qualifying_per_quarter`` = ``n_qualifying / observed_days``, and
    ``observed_days`` counts only from the day the cohort first held a COUNCIL-CONFIRMED-QUIET name (the
    strategist's ``under_narrated=True`` at first judgment, ``parse_error=false``) — NOT from first
    observation. Before that the rate is ``None`` (uninterpretable, not a clean negative): a feasibility-fresh
    but not-yet-break-capable cohort cannot dilute the rate toward a false negative. The ``clock`` block in
    the result carries the basis + per-role quietness composition (audit). See ``_clock_start``."""
    bounds = bounds or DEFAULT_DEGEN_BOUNDS
    by_sym: dict[str, list] = {}
    for r in conn.execute(
        "SELECT symbol, as_of, cheap, rv_rising, mom_recent, marker_age_days, "
        "atm_iv, wing_iv, iv_rv, otm_skew "
        "FROM cheapness_watch ORDER BY symbol, as_of"
    ):
        by_sym.setdefault(r["symbol"], []).append(r)

    breaks: list[dict] = []
    for sym, rows in by_sym.items():
        breaks.extend(_detect_breaks(sym, rows, fresh_rv, fresh_mom, bounds))

    never_cheap = [b for b in breaks if b["state"] == "never_cheap"]
    no_structure = [b for b in breaks if b["state"] == "no_structure"]
    degenerate_iv = [b for b in breaks if b["state"] == "degenerate_iv"]
    unmeasurable = [b for b in breaks if b["state"] == "unmeasurable"]
    catchable = [b for b in breaks if b["state"] == "cheap_window"]
    # the §7.1 SELECTION join: fresh-marker breaks are benign-by-construction (at_inflection saw them)
    fresh = [b for b in catchable if (b["marker_age_at_break"] or 0.0) < staleness_lag_days]
    qualifying = [b for b in catchable if (b["marker_age_at_break"] or 0.0) >= staleness_lag_days]

    # §2.1.8 right-censoring: a CLOSED window has an exact length; a truncated/open_at_end window's true
    # length is ≥ V. V ≥ lag ⇒ a definitive HOLD vote (kept in the decision set, its V votes hold);
    # V < lag ⇒ uninformative for median-vs-lag ⇒ OUT of both the median and the N-floor (censored_short).
    decision_windows: list[int] = []
    censored_short: list[dict] = []
    for b in qualifying:
        v = b["cheap_window_days"]
        if b["end_reason"] == "closed" or v >= staleness_lag_days:
            decision_windows.append(v)        # exact, or censored-but-already-past-the-lag (HOLD vote)
        else:
            censored_short.append(b)          # censored at V < lag — excluded from median AND N-floor
    windows = sorted(decision_windows)

    # the RATE (§2.1.7) — the decision-relevant signal that reads in MONTHS, not the years-away window N≥5.
    # The persist's value = rate × value-per-catch; a near-zero qualifying rate de-prioritizes on the rate
    # alone. The operator's rate-close (spec §2.1.7) reads this against a materiality floor over T months.
    # The rate counts ALL qualifying breaks (the harm OCCURRED even where the window is censored-short).
    #
    # FAIL-CLOSED clock-start (§2.1.7): observed_days counts ONLY from the point the cohort became
    # break-CAPABLE — defined as the first day the active cohort held ≥1 name the council read
    # `under_narrated=True` at FIRST judgment (parse_error=false). A feasibility-fresh-but-not-council-
    # confirmed cohort sees a zero rate UNINTERPRETABLY (no break-capable names) — counting those days
    # would dilute the rate toward a false negative. So the clock does not start until ``clock_start``.
    # Anti-survivorship: the confirmation is timestamped at clock-start; a name that NARRATES during the
    # window STAYS in the cohort (during-window narration is the signal, not a disqualifier).
    clock = _clock_start(conn, by_sym)
    observed_days = clock["observed_days"]
    qualifying_per_quarter = (len(qualifying) / observed_days * 90.0) if observed_days else None
    if len(windows) < n_qualify_floor:        # the N-floor counts the DECISION set (censored_short excluded)
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
        "n_degenerate_iv": len(degenerate_iv),
        "n_unmeasurable": len(unmeasurable),
        "n_fresh_marker": len(fresh),
        "n_qualifying": len(qualifying),
        "n_censored_short": len(censored_short),
        "observed_days": observed_days,
        "qualifying_per_quarter": qualifying_per_quarter,
        "qualifying_windows": windows,
        "reclassified_rows": _reclassified_rows(degenerate_iv, unmeasurable, bounds),
        "clock": clock,   # §2.1.7 fail-closed clock-start basis + per-role quietness composition (audit)
        "note": "verdict gated by the N-floor over the DECISION set (§2.1.8 censored-short excluded); "
                "QUALIFYING = stale-markers ∧ catchable-cheap (the §7.1 JOINT — what the persist would "
                "fix). fresh-marker breaks benign-by-construction; never_cheap = catchability-not-the-race; "
                "degenerate_iv/unmeasurable reclassified OUT of qualifying & never_cheap (the break is "
                "re-attributed, never hidden); insufficient_N is the EXPECTED long-term state (conjunctive "
                "filters make qualifying breaks rare) — a sustained one is itself the finding. The RATE "
                "(qualifying_per_quarter) is fail-CLOSED: observed_days counts only from the §2.1.7 "
                "council-confirmed-quiet clock-start (None until the cohort holds a name read "
                "under_narrated=True at first judgment), so a not-yet-break-capable cohort reads None, "
                "never a diluted false-negative rate.",
    }


def _reclassified_rows(degenerate_iv: list[dict], unmeasurable: list[dict],
                       bounds: dict[str, float]) -> list[dict]:
    """The §2.1.8 audit list — per reclassified ONSET row, the offending raw inputs + WHICH bound tripped
    (load-bearing: a future false-positive must be DIAGNOSABLE, not just countable). ``unmeasurable`` rows
    carry ``which_bound='missing_iv_rv'`` (the missing-input fail-close, no offending value)."""
    out: list[dict] = []
    for b in degenerate_iv:
        r = b["row"]
        trip = _degenerate_trip(r, bounds)
        which, offending = trip if trip is not None else (None, None)
        out.append({"symbol": b["symbol"], "as_of": r["as_of"], "state": "degenerate_iv",
                    "iv_rv": r["iv_rv"], "otm_skew": r["otm_skew"], "atm_iv": r["atm_iv"],
                    "wing_iv": r["wing_iv"], "which_bound": which, "offending_value": offending})
    for b in unmeasurable:
        r = b["row"]
        out.append({"symbol": b["symbol"], "as_of": r["as_of"], "state": "unmeasurable",
                    "iv_rv": r["iv_rv"], "otm_skew": r["otm_skew"], "atm_iv": r["atm_iv"],
                    "wing_iv": r["wing_iv"], "which_bound": "missing_iv_rv", "offending_value": None})
    return out
