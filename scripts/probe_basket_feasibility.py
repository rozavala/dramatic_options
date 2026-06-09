"""READ-ONLY feasibility screen for universe-curation candidates (PREREG_UNIVERSE_CURATION §2).

Deterministic TRADEABILITY screen — the existing frozen floors + cap-fit arithmetic only, NO new
thresholds. Per candidate it answers: can ONE contract of the production-selected 25%-OTM 180-365d
structure fit the frozen $1,000 per-name cap, on real (OPRA) quotes? Info columns (never selection
thresholds, §2): cluster-budget fit, achieved OTM% + neighbor-strike interval (coarse low-priced
chains -> a far-from-25% achieved structure is a different payoff object, calibration finding #3),
half-spread as % of premium (round-trip drag, paid again at the 21-DTE time-stop).

**Deliberately ABSENT (forbidden curation criteria, §2): IV/RV cheapness and momentum/rv_slope.**
Cheapness is the IV gate's job at decision time; printing it here would invite reverse-selection
(CGS §7). The call side is screened as the canonical structure (put premiums are same-scale;
feasibility, not direction).

Usage (repo root, worktree venv; live keys read from the live checkout's .env):
    PYTHONPATH=. venv/bin/python scripts/probe_basket_feasibility.py NNE UUUU ...
    PYTHONPATH=. venv/bin/python scripts/probe_basket_feasibility.py --file candidates.txt
Read-only market-data calls; never imported by the loop.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv("/home/rodrigo/dramatic_options/.env")

import clusters  # noqa: E402
from config_loader import load_config, require_alpaca_credentials  # noqa: E402
from convexity_data import AlpacaChainProvider  # noqa: E402
from convexity_sizing import convexity_position_size  # noqa: E402
from data.alpaca_client import AlpacaClient  # noqa: E402
from feeds import to_equity_feed, to_option_feed  # noqa: E402
from structure import contract_eligible, select_structure  # noqa: E402


def _symbols() -> list[str]:
    p = argparse.ArgumentParser(description="Feasibility screen (PREREG_UNIVERSE_CURATION §2)")
    p.add_argument("symbols", nargs="*", help="candidate symbols")
    p.add_argument("--file", help="file with one symbol per line ('#' comments allowed)")
    a = p.parse_args()
    syms = [s.upper() for s in a.symbols]
    if a.file:
        with open(a.file) as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if line:
                    syms.append(line.upper())
    if not syms:
        p.error("no symbols given (positional or --file)")
    return syms


config = load_config()
api_key, secret_key = require_alpaca_credentials(config)
client = AlpacaClient(api_key, secret_key, paper=True)
gate = config["convexity_gate"]
book = config["convexity_book"]
elig_c = config["eligibility"]["live"]
EQ = float(book.get("account_equity", 100000))
PER_NAME = EQ * float(book["per_name_fraction"])
CLUSTER = EQ * float(book.get("cluster_fraction", 0.02))
ADV_FLOOR = float(elig_c.get("min_adv_usd", 3_000_000))
PRICE_FLOOR = float(elig_c.get("min_price", 3.0))
ADV_WINDOW = int(elig_c.get("adv_window_days", 20))
cmap = clusters.load_cluster_map(config)

prov = AlpacaChainProvider(client, equity_feed=to_equity_feed(config["data_feed"]["equity_bars"]),
                           option_feed=to_option_feed("opra"))  # real quotes = real tradability


def _elig(c):
    return contract_eligible(c, max_spread_pct=float(elig_c.get("max_bid_ask_pct", 0.25)),
                             min_contract_price=0.10, max_contract_price=100.0,
                             min_oi=elig_c.get("min_option_open_interest"))


def _adv_usd(symbol: str) -> float | None:
    """Trailing ~ADV_WINDOW-day average $ volume from SIP bars (the discovery floor's basis)."""
    start = datetime.now(UTC) - timedelta(days=ADV_WINDOW * 2 + 10)
    bars = client.get_stock_bars(symbol, start=start,
                                 feed=to_equity_feed(config["data_feed"]["equity_bars"]))
    rows = (getattr(bars, "data", {}) or {}).get(symbol, [])
    rows = [b for b in rows if getattr(b, "close", None) and getattr(b, "volume", None)]
    if not rows:
        return None
    rows = rows[-ADV_WINDOW:]
    return sum(float(b.close) * float(b.volume) for b in rows) / len(rows)


def _strike_interval(chain, sel) -> str:
    """Gap to the listed neighbor strikes (same expiry/kind) around the selected strike."""
    ks = sorted({c.strike for c in chain if c.kind == sel.kind and c.expiry == sel.expiry})
    if sel.strike not in ks or len(ks) < 2:
        return "n/a"
    i = ks.index(sel.strike)
    below = (ks[i] - ks[i - 1]) if i > 0 else None
    above = (ks[i + 1] - ks[i]) if i < len(ks) - 1 else None
    fmt = lambda v: f"{v:g}" if v is not None else "-"  # noqa: E731
    return f"{fmt(below)}/{fmt(above)}"


today = datetime.now(ZoneInfo("America/New_York")).date()
print(f"=== feasibility screen (PREREG_UNIVERSE_CURATION §2) @ {datetime.now(UTC):%Y-%m-%d %H:%M} UTC ===")
print(f"floors (existing only): 1 contract <= ${PER_NAME:.0f} | tenor {gate['tenor_min_days']}-{gate['tenor_max_days']}d "
      f"| spread <= {float(elig_c.get('max_bid_ask_pct', 0.25)):.0%} | OI >= {elig_c.get('min_option_open_interest')} "
      f"(when present) | price >= ${PRICE_FLOOR:g} | ADV >= ${ADV_FLOOR / 1e6:.0f}M")
print(f"info-only columns: cluster-fit (${CLUSTER:.0f}), achieved OTM%, strike interval, half-spread % of premium\n")

hdr = (f"{'sym':6} {'spot':>8} {'$/contr':>8} {'fits1?':6} {'cl-fit':6} {'wing':22} {'dte':>4} "
       f"{'achOTM%':>8} {'strk-gap':>9} {'hspr%':>6} {'spr%':>5} {'OI':>6} {'ADV$M':>6} {'floors':8}")
print(hdr)
n_fit = 0
for sym in _symbols():
    try:
        spot = prov.underlying_price(sym)
        if not spot:
            print(f"{sym:6} ERR no underlying price")
            continue
        adv = _adv_usd(sym)
        chain = prov.chain(sym)
        s, why = select_structure(chain, direction="bullish", as_of=today, underlying_price=spot,
                                  tenor_min_days=int(gate["tenor_min_days"]),
                                  tenor_max_days=int(gate["tenor_max_days"]),
                                  target_moneyness=float(gate["target_moneyness"]), eligibility=_elig)
        floors = []
        if spot < PRICE_FLOOR:
            floors.append("price")
        if adv is not None and adv < ADV_FLOOR:
            floors.append("ADV")
        adv_s = f"{adv / 1e6:6.1f}" if adv is not None else "   n/a"
        if s is None:
            reason = why[0] if why else "no_structure"
            print(f"{sym:6} {spot:8.2f} {'-':>8} {'no':6} {'-':6} {('(' + reason + ')'):22} {'-':>4} "
                  f"{'-':>8} {'-':>9} {'-':>6} {'-':>5} {'-':>6} {adv_s} {','.join(floors) or 'ok':8}")
            continue
        c = s.contract
        per_contract = s.entry_premium * 100.0
        sizing = convexity_position_size(
            account_equity=EQ, book_fraction=float(book["book_fraction"]),
            per_name_fraction=float(book["per_name_fraction"]),
            max_open_positions=int(book["max_open_positions"]),
            open_positions_count=0, open_premium_total=0.0,
            entry_premium_per_share=s.entry_premium)
        fits = sizing.contracts >= 1
        n_fit += int(fits)
        cl = clusters.cluster_of(sym, cmap)
        cl_fit = "YES" if per_contract <= CLUSTER else "no"
        dte = (c.expiry - today).days
        ach_otm = s.moneyness * 100.0
        half_spr = (((c.ask - c.bid) / 2.0) / s.entry_premium * 100.0) if (c.bid is not None and c.ask) else None
        spr = ((c.ask - c.bid) / ((c.ask + c.bid) / 2.0) * 100.0) if (c.bid and c.ask) else None
        print(f"{sym:6} {spot:8.2f} {per_contract:8.0f} {('YES' if fits else 'no'):6} {cl_fit:6} "
              f"{c.symbol:22} {dte:>4} {ach_otm:8.1f} {_strike_interval(chain, c):>9} "
              f"{(f'{half_spr:6.1f}' if half_spr is not None else '   n/a')} "
              f"{(f'{spr:5.0f}' if spr is not None else '  n/a')} "
              f"{(str(c.oi) if c.oi is not None else 'n/a'):>6} {adv_s} "
              f"{','.join(floors) or 'ok':8}{' [' + cl + ']' if cl else ''}")
    except Exception as e:  # noqa: BLE001
        print(f"{sym:6} ERR {e}")

print(f"\n=== SUMMARY: {n_fit} candidate(s) fit one contract under the ${PER_NAME:.0f} per-name cap ===")
print("(cheapness deliberately not shown — the IV gate disposes at decision time, CGS §7)")
