"""READ-ONLY vertical feasibility probe (D3 step 1; calibration v2 Rule V).

For each name whose ONE naked contract of the production-selected 25%-OTM 180-365d call exceeds the per-name cap,
can the Rule V debit vertical (short the call nearest +75% OTM, same expiry) fit under it, on real OPRA quotes?
Prints the naked and spread debits, the premium ratio, the achieved short wing and the max multiple. With no
symbols it reads every universe name. Cheapness is deliberately absent (the gate's job at decision time).

    PYTHONPATH=. venv/bin/python scripts/probe_vertical_feasibility.py            # the whole universe
    PYTHONPATH=. venv/bin/python scripts/probe_vertical_feasibility.py NVDA LHX   # named
Read-only market-data calls; never imported by the loop.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from _live_env import load_live_env

load_live_env()

from config_loader import load_config, require_alpaca_credentials  # noqa: E402
from convexity_data import AlpacaChainProvider  # noqa: E402
from data.alpaca_client import AlpacaClient  # noqa: E402
from feeds import to_equity_feed, to_option_feed  # noqa: E402
from structure import contract_eligible, select_structure  # noqa: E402
from verticals import select_vertical  # noqa: E402

config = load_config()
api_key, secret_key = require_alpaca_credentials(config)
client = AlpacaClient(api_key, secret_key, paper=True)
gate, book, elig_c = config["convexity_gate"], config["convexity_book"], config["eligibility"]["live"]
PER_NAME = float(book.get("account_equity", 100000)) * float(book["per_name_fraction"])
prov = AlpacaChainProvider(client, equity_feed=to_equity_feed(config["data_feed"]["equity_bars"]),
                           option_feed=to_option_feed("opra"))


def _elig(c):
    return contract_eligible(c, max_spread_pct=float(elig_c.get("max_bid_ask_pct", 0.25)),
                             min_contract_price=0.10, max_contract_price=100.0,
                             min_oi=elig_c.get("min_option_open_interest"))


syms = [s.upper() for s in sys.argv[1:]] or sorted(
    {s for m in config["universe"]["themes"].values() if isinstance(m, list) for s in m})
today = datetime.now(ZoneInfo("America/New_York")).date()
print(f"=== vertical feasibility (Rule V) @ {datetime.now(UTC):%Y-%m-%d %H:%M} UTC · per-name cap ${PER_NAME:.0f} ===")
print(f"{'sym':6} {'naked$':>7} {'vert$':>7} {'ratio':>6} {'short':22} {'wing%':>6} {'maxX':>5} {'fits?':6} note")
for sym in syms:
    try:
        spot = prov.underlying_price(sym)
        chain = prov.chain(sym)
        s, why = select_structure(chain, direction="bullish", as_of=today, underlying_price=spot,
                                  underlying_symbol=sym, tenor_min_days=int(gate["tenor_min_days"]),
                                  tenor_max_days=int(gate["tenor_max_days"]),
                                  target_moneyness=float(gate["target_moneyness"]), eligibility=_elig,
                                  require_otm_side=bool(gate.get("otm_side_guard", False)),
                                  min_otm_moneyness=float(gate.get("min_otm_moneyness", 0.0) or 0.0))
        if s is None:
            print(f"{sym:6} {'-':>7} {'-':>7} {'-':>6} {'-':22} {'-':>6} {'-':>5} {'-':6} no naked structure: {why[0]}")
            continue
        naked = s.entry_premium * 100.0
        if naked <= PER_NAME:
            continue   # fits naked: the vertical is not for this name
        v, vwhy = select_vertical(chain, s, underlying_price=spot, eligibility=_elig, underlying_symbol=sym)
        if v is None:
            print(f"{sym:6} {naked:7.0f} {'-':>7} {'-':>6} {'-':22} {'-':>6} {'-':>5} {'no':6} {vwhy[0]}")
            continue
        print(f"{sym:6} {naked:7.0f} {v.debit_per_contract:7.0f} {v.debit_per_contract / naked:6.2f} "
              f"{v.short.symbol:22} {v.short_moneyness:6.0%} {v.max_multiple:5.1f} "
              f"{'YES' if v.debit_per_contract <= PER_NAME else 'no':6} {s.contract.symbol} {s.dte}d")
    except Exception as e:  # noqa: BLE001 — a probe row, never a crash
        print(f"{sym:6} ERR {e}")
