#!/usr/bin/env python3
"""The PREREG_REAL_MONEY_BROKER §5 smoke — OUT OF BAND, never the council/loop.

One 1-contract BUY_TO_OPEN → reconcile (order_status) → SELL_TO_CLOSE round-trip, proving
endpoint → fill → reconcile → close on a chosen endpoint. This script NEVER touches the
journal DB (no position rows, no proposals — the loop's record stays clean); its output is the
record, to be pasted into a dated records/ note.

Endpoints (explicit, safe-by-default):
  --endpoint sim    (default) keyless in-process simulator (PaperBroker) — offline rehearsal.
  --endpoint paper  Alpaca PAPER endpoint (paper keys; DRY_RUN unless --send).
  --endpoint live   Alpaca LIVE endpoint — requires the full triple-gate in config/env AND
                    --operator-go (the pre-reg's contemporaneous authorization; the freeze does
                    NOT imply it), AND the notional ceiling (absent ⇒ the live class rejects
                    all). Real dollars.

Every mode enforces the smoke budget in the SCRIPT too (independent of the live class's
ceiling): qty is hard-coded 1 and an order whose limit×100 exceeds --budget is refused.

Contract selection: pass --contract (OCC symbol) + --limit explicitly, or --symbol + --pick to
choose from the live chain: 15–35%-OTM call, bid ≥ 0.05, spread ≤ 25%, ask×100 ≤ budget —
"far-OTM per the pre-reg but with a real bid + sane spread so SELL_TO_CLOSE can complete."

Usage (Monday's paper rehearsal):
  LIVE_MAX_ORDER_NOTIONAL=250 python scripts/smoke_order_roundtrip.py \
      --endpoint paper --symbol PL --pick --send
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CONTRACT_MULTIPLIER = 100


def pick_contract(chain, *, underlying_price: float, budget: float,
                  otm_lo: float = 0.15, otm_hi: float = 0.35,
                  min_bid: float = 0.05, max_spread_pct: float = 0.25):
    """Pick the cheapest qualifying far-OTM CALL: OTM in [lo,hi], bid ≥ min_bid, spread ≤ cap,
    ask×100 ≤ budget. Returns the contract or None (fail-closed)."""
    best = None
    for c in chain:
        if getattr(c, "kind", getattr(c, "type", "C")) not in ("C", "call", "CALL"):
            continue
        bid, ask = float(getattr(c, "bid", 0) or 0), float(getattr(c, "ask", 0) or 0)
        if bid < min_bid or ask <= 0:
            continue
        mid = (bid + ask) / 2
        if mid <= 0 or (ask - bid) / mid > max_spread_pct:
            continue
        otm = (float(c.strike) - underlying_price) / underlying_price
        if not (otm_lo <= otm <= otm_hi):
            continue
        if ask * CONTRACT_MULTIPLIER > budget:
            continue
        if best is None or ask < float(best.ask):
            best = c
    return best


def run_roundtrip(broker, *, contract_symbol: str, buy_limit: float, sell_limit: float | None,
                  budget: float, poll_s: int = 90, sleep_s: float = 3.0, log=print) -> int:
    """BUY_TO_OPEN 1 → reconcile → SELL_TO_CLOSE 1 → reconcile. Returns 0 iff the round-trip
    completed (or simulated). The budget guard is enforced HERE, independent of any broker."""
    if buy_limit * CONTRACT_MULTIPLIER > budget:
        log(f"REFUSED: buy limit {buy_limit:.2f}×100 exceeds the smoke budget ${budget:.0f}")
        return 2

    def _await_fill(fill, side):
        if not fill.filled:
            log(f"{side} REJECTED/FAILED: {fill.note}")
            return None
        log(f"{side}: {fill.note}")
        if not getattr(fill, "pending", False):
            return fill.price
        oid = fill.order_id
        deadline = time.time() + poll_s
        while time.time() < deadline:
            info = broker.order_status(oid)
            st = str((info or {}).get("state", "")).lower()
            if st == "filled":
                px = float(info.get("filled_avg_price") or 0.0)
                log(f"{side} FILLED @ {px:.2f}")
                return px
            if st in ("canceled", "cancelled", "expired", "rejected"):
                log(f"{side} terminal without fill: {st}")
                return None
            time.sleep(sleep_s)
        log(f"{side} NOT FILLED within {poll_s}s — cancelling")
        if hasattr(broker, "cancel_order") and fill.order_id:
            broker.cancel_order(fill.order_id)
        return None

    import datetime as _dt

    from broker import make_client_order_id
    today = _dt.date.today().isoformat()

    buy_px = _await_fill(
        broker.submit_paper(contract_symbol=contract_symbol, qty=1, side="buy",
                            limit_price=buy_limit,
                            client_order_id=make_client_order_id("smokebuy", contract_symbol, today)),
        "BUY_TO_OPEN")
    if buy_px is None:
        return 3

    sl = sell_limit if sell_limit is not None else max(0.01, round(buy_px * 0.5, 2))
    sell_px = _await_fill(
        broker.submit_paper(contract_symbol=contract_symbol, qty=1, side="sell",
                            limit_price=sl,
                            client_order_id=make_client_order_id("smokesell", contract_symbol, today)),
        "SELL_TO_CLOSE")
    if sell_px is None:
        log("ROUND-TRIP INCOMPLETE: bought but not closed — CLOSE MANUALLY, then record.")
        return 4

    cost = (buy_px - sell_px) * CONTRACT_MULTIPLIER
    log(f"ROUND-TRIP COMPLETE: bought @ {buy_px:.2f}, sold @ {sell_px:.2f} — "
        f"friction cost ${cost:,.2f} (bounded by budget ${budget:.0f}).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--endpoint", choices=("sim", "paper", "live"), default="sim")
    ap.add_argument("--symbol", help="underlying for --pick")
    ap.add_argument("--pick", action="store_true", help="auto-pick a qualifying far-OTM call")
    ap.add_argument("--contract", help="explicit OCC contract symbol (skips --pick)")
    ap.add_argument("--limit", type=float, help="explicit buy limit (per share)")
    ap.add_argument("--sell-limit", type=float, default=None)
    ap.add_argument("--budget", type=float, default=None,
                    help="hard smoke budget in $ (default: the notional ceiling, else 250)")
    ap.add_argument("--send", action="store_true", help="actually transmit (else DRY_RUN)")
    ap.add_argument("--operator-go", action="store_true",
                    help="the operator's contemporaneous authorization (REQUIRED for --endpoint live)")
    args = ap.parse_args(argv)

    from config_loader import load_config
    config = load_config()
    ceiling = config.get("safety", {}).get("live_max_order_notional")
    budget = args.budget if args.budget is not None else float(ceiling or 250.0)

    # ── broker selection (explicit; safe-by-default) ────────────────────────────────────────
    if args.endpoint == "sim":
        from broker import PaperBroker
        broker = PaperBroker(100_000.0)
        print(f"endpoint=sim (keyless simulator) budget=${budget:.0f}")
    else:
        from config_loader import require_alpaca_credentials
        api_key, secret_key = require_alpaca_credentials(config)
        dry = not args.send
        if args.endpoint == "paper":
            from broker import AlpacaPaperBroker
            broker = AlpacaPaperBroker(api_key, secret_key, dry_run=dry)
        else:
            from config_loader import live_allowed
            if not live_allowed(config, cli_live=True):
                print("REFUSED: the triple-gate (paper=false ∧ live_trading_enabled ∧ --live) "
                      "is not satisfied in config/env.")
                return 2
            if not args.operator_go:
                print("REFUSED: --endpoint live requires --operator-go (the pre-reg's "
                      "contemporaneous authorization; the freeze does not imply it).")
                return 2
            if not ceiling:
                print("REFUSED: no safety.live_max_order_notional (set LIVE_MAX_ORDER_NOTIONAL).")
                return 2
            from broker import AlpacaLiveBroker
            broker = AlpacaLiveBroker(api_key, secret_key, dry_run=dry,
                                      max_order_notional=float(ceiling))
        print(f"endpoint={args.endpoint} dry_run={dry} budget=${budget:.0f}")

    # ── contract ────────────────────────────────────────────────────────────────────────────
    if args.contract:
        contract_symbol, buy_limit = args.contract, args.limit
        if buy_limit is None:
            print("REFUSED: --contract requires --limit.")
            return 2
    else:
        if not (args.symbol and args.pick):
            print("REFUSED: pass --contract + --limit, or --symbol with --pick.")
            return 2
        from config_loader import require_alpaca_credentials
        from convexity_data import AlpacaChainProvider
        api_key, secret_key = require_alpaca_credentials(config)
        provider = AlpacaChainProvider(
            api_key, secret_key,
            option_feed=config.get("data_feed", {}).get("option_gate", "indicative"))
        px = provider.underlying_price(args.symbol)
        c = pick_contract(provider.chain(args.symbol), underlying_price=px, budget=budget)
        if c is None:
            print(f"NO qualifying contract for {args.symbol} under ${budget:.0f} (fail-closed).")
            return 2
        contract_symbol, buy_limit = c.symbol, round(float(c.ask), 2)
        print(f"picked {contract_symbol} (spot {px:.2f}, strike {c.strike}, "
              f"bid {c.bid:.2f}/ask {c.ask:.2f})")

    return run_roundtrip(broker, contract_symbol=contract_symbol, buy_limit=buy_limit,
                         sell_limit=args.sell_limit, budget=budget)


if __name__ == "__main__":
    raise SystemExit(main())
