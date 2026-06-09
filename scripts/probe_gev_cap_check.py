"""READ-ONLY: can the gate-cheap names (esp. GEV, the re-score survivor) open ONE contract under
the frozen caps? Determines the honest near-term-yield language for the pre-reg.

COMMITTED COPY of the /tmp/gev_cap_check.py probe behind PREREG_COUNCIL_GATE_SEPARATION §10.5
(2026-06-09: GEV ≈ $8,125/contract vs the $1,000 per-name cap → un-enterable; every cap-fitting
cheap name is a thesis-reject → re-arch near-term yield = ZERO). Differences vs the ephemeral
original: this docstring + unused-import removal (ruff); logic unchanged.

per-name cap = 1% = $1000; cluster cap (ai_capex_power / space_defense) = 2% = $2000; book = $10000.
A single-contract premium over the binding cap => structurally un-enterable (like RKLB $2866 at L1 #111).
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv("/home/rodrigo/dramatic_options/.env")

import clusters  # noqa: E402
from config_loader import load_config, require_alpaca_credentials  # noqa: E402
from convexity_data import AlpacaChainProvider  # noqa: E402
from convexity_gate import is_cheap_convexity, realized_vol  # noqa: E402
from convexity_sizing import convexity_position_size  # noqa: E402
from data.alpaca_client import AlpacaClient  # noqa: E402
from feeds import to_equity_feed, to_option_feed  # noqa: E402
from structure import contract_eligible, select_structure  # noqa: E402

UNIVERSE = ["NVDA", "SMCI", "VRT", "ETN", "GEV", "CEG", "CCJ", "FCX",
            "NEE", "PWR", "RKLB", "LMT", "NOC", "LHX", "RTX", "KTOS"]

config = load_config()
api_key, secret_key = require_alpaca_credentials(config)
client = AlpacaClient(api_key, secret_key, paper=True)
gate = config["convexity_gate"]
book = config["convexity_book"]
elig_c = config["eligibility"]["live"]
EQ = float(book.get("account_equity", 100000))
PER_NAME = EQ * float(book["per_name_fraction"])
CLUSTER = EQ * float(book.get("cluster_fraction", 0.02))
cmap = clusters.load_cluster_map(config)

prov = AlpacaChainProvider(client, equity_feed=to_equity_feed(config["data_feed"]["equity_bars"]),
                           option_feed=to_option_feed("opra"))  # OPRA = the gate-of-record post-flip

def _elig(c):
    return contract_eligible(c, max_spread_pct=float(elig_c.get("max_bid_ask_pct", 0.25)),
                             min_contract_price=0.10, max_contract_price=100.0,
                             min_oi=elig_c.get("min_option_open_interest"))

today = datetime.now(ZoneInfo("America/New_York")).date()
print(f"caps: per-name ${PER_NAME:.0f}  cluster ${CLUSTER:.0f}  book ${EQ*float(book['book_fraction']):.0f}\n")
print(f"{'sym':5} {'cheap':5} {'wing':24} {'$/contract':>11} {'cluster':14} {'fits1?':7}")
for sym in UNIVERSE:
    try:
        spot = prov.underlying_price(sym)
        rv = realized_vol(prov.closes(sym, window=300), window=int(gate["rv_window_days"]))
        s, _ = select_structure(prov.chain(sym), direction="bullish", as_of=today, underlying_price=spot,
                                tenor_min_days=int(gate["tenor_min_days"]), tenor_max_days=int(gate["tenor_max_days"]),
                                target_moneyness=float(gate["target_moneyness"]), eligibility=_elig)
        if s is None:
            print(f"{sym:5} {'-':5} {'(no structure)':24}")
            continue
        v = is_cheap_convexity(prov.chain(sym), underlying_price=spot, wing=s.contract, rv=rv,
                               iv_rv_max=float(gate["iv_rv_max"]), otm_skew_max_volpts=float(gate["otm_skew_max_volpts"]))
        per_contract = s.entry_premium * 100.0
        sizing = convexity_position_size(account_equity=EQ, book_fraction=float(book["book_fraction"]),
                                         per_name_fraction=float(book["per_name_fraction"]),
                                         max_open_positions=int(book["max_open_positions"]),
                                         open_positions_count=0, open_premium_total=0.0,
                                         entry_premium_per_share=s.entry_premium)
        contracts = sizing.contracts
        cl = clusters.cluster_of(sym, cmap)
        cl_ok = (cl is None) or (per_contract <= CLUSTER)
        fits = "YES" if (contracts >= 1 and cl_ok) else "no"
        why = "" if fits == "YES" else ("per-name/size" if contracts < 1 else "cluster")
        star = " <-GEV" if sym == "GEV" else ""
        print(f"{sym:5} {('Y' if v.cheap else 'n'):5} {s.contract.symbol:24} {per_contract:>11.0f} "
              f"{str(cl or '-'):14} {fits:4}{why}{star}")
    except Exception as e:  # noqa: BLE001
        print(f"{sym:5} ERR {e}")
