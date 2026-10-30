"""Carry an unfilled L1 entry into the next session (#386; the operator's word on #349 §4, 2026-10-29).

The L1 submits a DAY limit at mid at 15:45 ET, about 12 minutes before the close (HL 10-26 and AG 10-29 both
went unfilled that way). With ``execution.carry_unfilled`` on:

1. **At reconcile** (the 16:00 L2, or any later tick) an L1 entry still resting or expired unfilled is cancelled
   and becomes a **carry intent** (status ``carried``): no order, no exposure, with a window on the next NYSE
   trading day, ``carry_start_et`` (10:00) to ``carry_cancel_et`` (15:30; 30 minutes before an early close).
   One carry per approval: an attempt is never carried again.
2. **Each tick in the window** (L2 every 30 minutes, market open, entries allowed), the intent is re-run through
   ``paper_loop.run_paper_cycle``, the SAME pipeline an L1 entry uses (KILL switch, kill rule, cluster cap,
   sentinel slots, side guard, the IV gate on the fresh chain, dual-read veto, sizing within every cap, the
   foreign-quantity check, the restricted list), with a walked limit: step ``k`` = hours since the start
   (capped at ``carry_walk_steps``, 3), limit = ``mid + k/3 × (ask − mid)``, so mid at 10:00 and the ask from
   13:00. Each attempt is its own ``pending`` row; a higher step cancels the previous one first.
3. **At the cancel time** a working attempt is cancelled and the intent ends ``carry_lapsed``. A veto ends it
   ``carry_veto:<decision>``; a fill ends it ``carry_filled``.

Safety: a cancel is always followed by a status read. A fill found there is confirmed, never dropped, and an
unknown state leaves everything as it is (no second order while one may still be working). Off by default.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import nyse_calendar
import state

log = logging.getLogger(__name__)
_ET = ZoneInfo("America/New_York")
CONTRACT_MULTIPLIER = 100
_WORKING = ("new", "accepted", "pending_new", "partially_filled", "pending_cancel", "pending_replace")
_TERMINAL = ("canceled", "cancelled", "expired", "rejected")


def settings(config: dict) -> dict | None:
    """The carry parameters, or None when ``execution.carry_unfilled`` is off."""
    ex = config.get("execution", {}) or {}
    if not ex.get("carry_unfilled", False):
        return None

    def hm(v: str, default: str) -> time:
        h, m = str(v or default).split(":")
        return time(int(h), int(m))
    return {"start": hm(ex.get("carry_start_et"), "10:00"), "cancel": hm(ex.get("carry_cancel_et"), "15:30"),
            "steps": max(int(ex.get("carry_walk_steps", 3)), 1),
            "step_minutes": max(int(ex.get("carry_step_minutes", 60)), 1),
            "close_buffer_min": int(ex.get("carry_close_buffer_min", 30))}


def window(opened_at: str, cfg: dict) -> dict:
    """The carry session: the first NYSE trading day strictly after the entry's ET date, from the start time to the
    cancel time (or the close minus the buffer on a half day, whichever is earlier). ISO UTC strings."""
    opened = datetime.fromisoformat(str(opened_at))
    opened = opened if opened.tzinfo else opened.replace(tzinfo=UTC)
    d: date = opened.astimezone(_ET).date() + timedelta(days=1)
    for _ in range(10):
        if nyse_calendar.is_trading_day(d):
            break
        d += timedelta(days=1)
    start = datetime.combine(d, cfg["start"], _ET)
    until = datetime.combine(d, cfg["cancel"], _ET)
    close = nyse_calendar.session_close(d)
    if close is not None:
        until = min(until, datetime.combine(d, close, _ET) - timedelta(minutes=cfg["close_buffer_min"]))
    return {"day": d.isoformat(), "start": start.astimezone(UTC).isoformat(),
            "until": until.astimezone(UTC).isoformat()}


def rationale(row) -> dict:
    """The row's rationale JSON as a dict ({} when absent, ``null`` or malformed)."""
    try:
        d = json.loads(row["rationale"] or "{}")
    except (TypeError, ValueError, KeyError, IndexError):
        return {}
    return d if isinstance(d, dict) else {}


def attempt_of(row) -> int | None:
    """The intent id a carry attempt belongs to, or None for an ordinary entry."""
    of = (rationale(row).get("carry") or {}).get("of")
    return int(of) if of is not None else None


def filled_qty(info: dict | None) -> int:
    """Contracts the venue reports filled on an order (alpaca-py gives a string or a number; missing → 0)."""
    try:
        return int(float((info or {}).get("filled_qty") or 0))
    except (TypeError, ValueError):
        return 0


def settle_terminal(info: dict) -> dict:
    """A terminal order (canceled / expired / rejected) that filled any contracts first is a (partial) FILL, never
    "unfilled": Alpaca reports a partially filled order that was then cancelled or expired as canceled/expired WITH
    ``filled_qty > 0``, and dropping it would leave a real position the journal doesn't hold."""
    q = filled_qty(info)
    if q > 0:
        return {"state": "filled", "filled_avg_price": info.get("filled_avg_price"), "filled_qty": q, "partial": True}
    return {"state": "canceled"}


def live_attempt(conn, pos) -> bool:
    """A carry attempt whose intent is still alive ('carried'). An attempt whose intent ended (lapse, veto, KILL,
    switch-off) is an ordinary order again, so reconcile settles it instead of leaving it to a worker that will
    never visit it."""
    of = attempt_of(pos)
    if of is None:
        return False
    row = conn.execute("SELECT status FROM convexity_positions WHERE id = ?", (of,)).fetchone()
    return row is not None and row["status"] == "carried"


def cancel_and_settle(broker, order_id: str) -> dict | None:
    """Cancel, then READ the order: ``{"state": "filled", …}`` if it filled (fully, or partly before the cancel),
    ``{"state": "canceled"}`` once it is gone with nothing filled, or None when the outcome isn't known yet
    (pending_cancel / unreadable). The caller must not drop a row or submit a new order on None."""
    if hasattr(broker, "cancel_order"):
        broker.cancel_order(order_id)
    info = broker.order_status(order_id) if hasattr(broker, "order_status") else None
    if info is None:
        return None
    st = str(info.get("state", "")).lower()
    if st == "filled":
        return info
    if st in _TERMINAL:
        return settle_terminal(info)
    return None


def confirm_fill(conn, pos, info: dict, now_iso: str) -> None:
    """Flip a 'pending' row to 'open' at the broker's fill price and filled quantity (a partial fill opens only what
    filled), and page it."""
    price = float(info.get("filled_avg_price") or pos["entry_premium_per_contract"] / CONTRACT_MULTIPLIER)
    per_contract = price * CONTRACT_MULTIPLIER
    q = filled_qty(info) or int(pos["contracts"])
    state.confirm_convexity_fill(conn, int(pos["id"]), entry_premium_per_contract=per_contract,
                                 total_premium=per_contract * q, opened_at=now_iso, contracts=q)
    part = f" (partial: {q} of {pos['contracts']})" if q != int(pos["contracts"]) else ""
    log.info("FILLED (reconciled) #%d %s @ %.2f x%d%s", pos["id"], pos["contract_symbol"], price, q, part)
    _page("REAL-BOOK FILL", f"#{pos['id']} {pos['contract_symbol']} filled @ {price:.2f} "
                            f"({q}x, ${per_contract * q:,.0f}){part}.")


def make_intent(conn, pos, config: dict, now: datetime) -> bool:
    """Turn an unfilled L1 entry (already cancelled at the broker) into a carry intent. False when the carry is
    off or the row is itself an attempt (one carry per approval)."""
    cfg = settings(config)
    if cfg is None or attempt_of(pos) is not None:
        return False
    win = window(pos["opened_at"], cfg)
    state.carry_convexity_position(conn, int(pos["id"]), carry={
        **win, "l1_order_id": pos["order_id"], "carried_at": now.isoformat(),
        "steps": cfg["steps"], "step_minutes": cfg["step_minutes"]})
    log.info("CARRIED #%d %s — re-gated and resubmitted %s from %s, walking to the ask; cancel %s",
             pos["id"], pos["contract_symbol"], win["day"], win["start"], win["until"])
    _page("REAL-BOOK ORDER CARRIED",
          f"#{pos['id']} {pos['symbol']} {pos['contracts']}x {pos['contract_symbol']} unfilled at the close: re-gated "
          f"and resubmitted {win['day']} from {cfg['start']:%H:%M} ET (mid, walking to the ask), cancel "
          f"{_et_hm(win['until'])} ET.")
    return True


def _attempts(conn, intent) -> list:
    rows = conn.execute("SELECT * FROM convexity_positions WHERE symbol = ? AND id > ? ORDER BY id",
                        (intent["symbol"], intent["id"])).fetchall()
    return [r for r in rows if attempt_of(r) == int(intent["id"])]


def work_carried(conn, *, config: dict, clock, provider, broker, run_id, chain_cache=None, shadow_provider=None,
                 market_open: bool, entries_ok: bool) -> int:
    """One pass over the carry intents (call after ``reconcile_pending``). Returns the number of attempts placed.
    ``shadow_provider`` is the INDICATIVE dual-read arm, passed exactly as the L1 path passes it."""
    cfg = settings(config)
    if cfg is None:
        _wind_down(conn, broker, clock)   # switched off with intents alive: cancel their attempts, end them
        return 0
    from paper_loop import run_paper_cycle
    from themes import Theme

    now = clock.now()
    now = now if now.tzinfo else now.replace(tzinfo=UTC)
    placed = 0
    for intent in state.carried_convexity_positions(conn):
        win = rationale(intent).get("carry_intent") or {}
        try:
            start, until = datetime.fromisoformat(win["start"]), datetime.fromisoformat(win["until"])
        except (KeyError, TypeError, ValueError):
            state.drop_convexity_position(conn, int(intent["id"]), reason="carry_invalid_window")
            continue
        attempts = _attempts(conn, intent)
        if any(a["status"] in ("open", "closing", "closed") for a in attempts):
            state.drop_convexity_position(conn, int(intent["id"]), reason="carry_filled")
            continue
        if any(a["status"] == "cancelled" and a["exit_reason"] == "order_rejected" for a in attempts):
            state.drop_convexity_position(conn, int(intent["id"]), reason="carry_rejected")   # never retry a rejection
            _page("REAL-BOOK ORDER NOT FILLED",
                  f"#{intent['id']} {intent['symbol']}: the venue rejected the carry attempt; not retried.")
            continue
        working = [a for a in attempts if a["status"] == "pending"]
        if now >= until or win.get("killed"):   # past its cancel time, or killed under KILL (#391): wind it down
            filled = False
            for a in working:
                info = cancel_and_settle(broker, a["order_id"]) if a["order_id"] else {"state": "canceled"}
                if info is None:
                    filled = None   # outcome unknown: keep everything, retry on the next tick
                    break
                if info["state"] == "filled":
                    confirm_fill(conn, a, info, now.isoformat())
                    filled = True
                else:
                    state.drop_convexity_position(conn, int(a["id"]), reason="carry_lapsed")
            if filled is None:
                continue
            end = "carry_filled" if filled else ("kill_cancelled" if win.get("killed") else "carry_lapsed")
            state.drop_convexity_position(conn, int(intent["id"]), reason=end)
            if not filled and not win.get("killed"):
                _page("REAL-BOOK ORDER NOT FILLED",
                      f"#{intent['id']} {intent['symbol']} {intent['contract_symbol']}: carry lapsed unfilled at "
                      f"{_et_hm(win['until'])} ET.")
            continue
        if now < start or not market_open or not entries_ok:
            continue
        k = min(cfg["steps"], int((now - start).total_seconds() // (cfg["step_minutes"] * 60)))
        if working:
            cur = working[-1]
            if int((rationale(cur).get("carry") or {}).get("step", 0)) >= k:
                continue                                    # this step's order is working
            info = cancel_and_settle(broker, cur["order_id"]) if cur["order_id"] else {"state": "canceled"}
            if info is None:
                continue                                    # can't confirm it's gone: never risk a second order
            if info["state"] == "filled":
                confirm_fill(conn, cur, info, now.isoformat())
                state.drop_convexity_position(conn, int(intent["id"]), reason="carry_filled")
                continue
            state.drop_convexity_position(conn, int(cur["id"]), reason=f"carry_step_{k}")
        rat = rationale(intent)
        sid = conn.execute("SELECT sentinel_id FROM council_proposals WHERE id = ?",
                           (intent["proposal_id"],)).fetchone() if intent["proposal_id"] else None
        sentinel_id = sid[0] if sid else None
        theme = Theme(name=intent["theme"], symbol=intent["symbol"], direction=intent["direction"],
                      thesis=str(rat.get("thesis") or ""), proposal_id=intent["proposal_id"],
                      source="sentinel" if sentinel_id is not None else "hand-seed", sentinel_id=sentinel_id)
        res = run_paper_cycle(config=config, conn=conn, clock=clock, provider=provider, broker=broker,
                              themes=[theme], run_id=run_id, chain_cache=chain_cache, shadow_provider=shadow_provider,
                              walk={theme.symbol: {"intent_id": int(intent["id"]), "step": k,
                                                   "fraction": k / cfg["steps"]}})
        if res.opened:
            placed += 1
            continue
        if res.errors:
            continue                                        # transient (feed, network): retry on the next tick
        row = conn.execute("SELECT decision FROM convexity_eval WHERE symbol = ? ORDER BY id DESC LIMIT 1",
                           (intent["symbol"],)).fetchone()
        why = ("halted" if res.halted else (row[0] if row else "vetoed"))
        state.drop_convexity_position(conn, int(intent["id"]), reason=f"carry_veto:{why}")
        _page("REAL-BOOK ORDER NOT FILLED",
              f"#{intent['id']} {intent['symbol']}: carry dropped at re-gate ({why}); nothing submitted.")
    return placed


def _wind_down(conn, broker, clock) -> None:
    """The switch went off with intents alive: cancel each working attempt (settled, so a fill is kept) and end the
    intent ``carry_disabled``. An attempt whose cancel can't be confirmed is left for the next tick."""
    now_iso = clock.now().isoformat()
    for intent in state.carried_convexity_positions(conn):
        unsure = False
        for a in _attempts(conn, intent):
            if a["status"] != "pending":
                continue
            info = cancel_and_settle(broker, a["order_id"]) if a["order_id"] else {"state": "canceled"}
            if info is None:
                unsure = True
            elif info["state"] == "filled":
                confirm_fill(conn, a, info, now_iso)
            else:
                state.drop_convexity_position(conn, int(a["id"]), reason="carry_disabled")
        if not unsure:
            state.drop_convexity_position(conn, int(intent["id"]), reason="carry_disabled")


def _et_hm(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone(_ET).strftime("%H:%M")
    except (TypeError, ValueError):
        return "?"


def _page(title: str, message: str) -> None:
    try:
        import notify

        notify.send(title, message)
    except Exception:  # noqa: BLE001 — paging must never break the cycle
        log.warning("carry page failed to send: %s", title)
