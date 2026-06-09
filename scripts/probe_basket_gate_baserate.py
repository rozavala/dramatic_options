"""READ-ONLY weekly gate base-rate sweep — AGGREGATE-ONLY by construction (PREREG_UNIVERSE_CURATION §6).

Runs the production IV/cheap-convexity gate over the WHOLE `config.universe.themes` basket on the
**gate-of-record option feed** (`config.data_feed.option_gate` — tracks a future OPRA flip
automatically) and emits **basket-level aggregates only**: n, structures, gate-cheap count, and
veto-reason counts. **Per-name gate results for non-surfaced names are SEALED — never written or
printed** (per-name visibility would teach which name-types pass the gate and reverse-select the
next curation window — the CGS §7 channel reopened at curation time). The sealing is a discipline
boundary on the recorded artifact (the only thing curation may consult), not cryptography.

Exception (public-record subset): names that are CURRENTLY SURFACED active sentinels are already
public in the council/eval record, so their one-contract cap-fit is printed BY NAME — that is §5's
slot-occupancy-by-cap-unfittable read. Pass --db to enable it (read-only ?mode=ro), e.g.
    PYTHONPATH=. venv/bin/python scripts/probe_basket_gate_baserate.py \
        --db /home/rodrigo/dramatic_options/data/dramatic_options.db

Run weekly (Sundays, beside L0). Wiring into L0 as a fail-soft step is deferred (§6, named).
Read-only; never imported by the loop.
"""
from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv("/home/rodrigo/dramatic_options/.env")

from config_loader import load_config, require_alpaca_credentials  # noqa: E402
from convexity_data import AlpacaChainProvider  # noqa: E402
from convexity_gate import is_cheap_convexity, realized_vol  # noqa: E402
from convexity_sizing import convexity_position_size  # noqa: E402
from data.alpaca_client import AlpacaClient  # noqa: E402
from feeds import to_equity_feed, to_option_feed  # noqa: E402
from structure import contract_eligible, select_structure  # noqa: E402

ap = argparse.ArgumentParser(description="Aggregate-only gate base-rate sweep (PREREG_UNIVERSE_CURATION §6)")
ap.add_argument("--db", help="live DB path (read-only) for the surfaced-sentinel subset (§5 slot-occupancy)")
args = ap.parse_args()

config = load_config()
api_key, secret_key = require_alpaca_credentials(config)
client = AlpacaClient(api_key, secret_key, paper=True)
gate = config["convexity_gate"]
book = config["convexity_book"]
elig_c = config["eligibility"]["live"]
EQ = float(book.get("account_equity", 100000))
baskets = {b: [s.upper() for s in members]
           for b, members in config["universe"]["themes"].items() if not b.startswith("_")}
gate_feed = config["data_feed"]["option_gate"]  # the gate-of-record feed, by construction

prov = AlpacaChainProvider(client, equity_feed=to_equity_feed(config["data_feed"]["equity_bars"]),
                           option_feed=to_option_feed(gate_feed))


def _elig(c):
    return contract_eligible(c, max_spread_pct=float(elig_c.get("max_bid_ask_pct", 0.25)),
                             min_contract_price=0.10, max_contract_price=100.0,
                             min_oi=elig_c.get("min_option_open_interest"))


def _surfaced_symbols(db_path: str) -> set[str]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT DISTINCT symbol FROM sentinel_candidates WHERE kind='sentinel' AND status='candidate'"
        ).fetchall()
        return {r[0].upper() for r in rows}
    finally:
        con.close()


surfaced = _surfaced_symbols(args.db) if args.db else None
today = datetime.now(ZoneInfo("America/New_York")).date()
print(f"=== gate base-rate sweep @ {datetime.now(UTC):%Y-%m-%d %H:%M} UTC | "
      f"feed-of-record: {gate_feed} | AGGREGATES ONLY (per-name sealed, §6) ===\n")

# Per-name verdicts live only in this loop's locals for non-surfaced names — aggregated, then dropped.
grand = Counter()
surf_fit_lines: list[str] = []
for basket, members in baskets.items():
    agg: Counter = Counter()
    for sym in members:
        agg["n"] += 1
        try:
            spot = prov.underlying_price(sym)
            closes = prov.closes(sym, window=300)
            rv = realized_vol(closes, window=int(gate["rv_window_days"]))
            if not spot or rv is None:
                agg["no_data"] += 1
                continue
            mom = (closes[-22] / closes[-253] - 1.0) if len(closes) >= 253 else None
            direction = "bullish" if (mom is None or mom > 0) else "bearish"
            chain = prov.chain(sym)
            s, _why = select_structure(chain, direction=direction, as_of=today, underlying_price=spot,
                                       tenor_min_days=int(gate["tenor_min_days"]),
                                       tenor_max_days=int(gate["tenor_max_days"]),
                                       target_moneyness=float(gate["target_moneyness"]), eligibility=_elig)
            if s is None:
                agg["no_structure"] += 1
                continue
            agg["structured"] += 1
            v = is_cheap_convexity(chain, underlying_price=spot, wing=s.contract, rv=rv,
                                   iv_rv_max=float(gate["iv_rv_max"]),
                                   otm_skew_max_volpts=float(gate["otm_skew_max_volpts"]))
            if v.cheap:
                agg["gate_cheap"] += 1
            else:
                # coarsen to the reason CLASS — the value-bearing string would leak the
                # per-name distribution the §6 seal exists to withhold
                for r in (v.reasons or ("veto_unspecified",)):
                    agg[f"veto:{r.split()[0] if r.split() else r}"] += 1
            # §5 slot-occupancy: surfaced names are public record — their cap-fit prints BY NAME.
            if surfaced is not None and sym in surfaced:
                sizing = convexity_position_size(
                    account_equity=EQ, book_fraction=float(book["book_fraction"]),
                    per_name_fraction=float(book["per_name_fraction"]),
                    max_open_positions=int(book["max_open_positions"]),
                    open_positions_count=0, open_premium_total=0.0,
                    entry_premium_per_share=s.entry_premium)
                fit = "fits-1" if sizing.contracts >= 1 else f"UNFITTABLE (${s.entry_premium * 100:.0f}/contract)"
                surf_fit_lines.append(f"  {sym:6} [{basket}] {fit}")
        except Exception:  # noqa: BLE001 — a per-name error is a count, never a per-name verdict line
            agg["error"] += 1
    grand.update(agg)
    parts = " ".join(f"{k}={v}" for k, v in sorted(agg.items()))
    print(f"{basket:16} {parts}")

print(f"\n{'TOTAL':16} " + " ".join(f"{k}={v}" for k, v in sorted(grand.items())))
if surfaced is not None:
    print(f"\nsurfaced active sentinels (public record, §5 slot-occupancy) — {len(surf_fit_lines)} "
          f"of {len(surfaced)} surfaced names are in the basket:")
    for line in surf_fit_lines:
        print(line)
else:
    print("\n(no --db given: surfaced-subset slot-occupancy skipped)")
print("\n(per-name gate verdicts for non-surfaced names are deliberately not emitted — "
      "curation may consult ONLY these aggregates, PREREG_UNIVERSE_CURATION §6)")
