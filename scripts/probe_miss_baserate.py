"""READ-ONLY miss base-rate ledger (PREREG_MISS_BASERATE.md) — forward, base-rated, sealed, counts-only.

    init    draw + FREEZE the market denominator (refuses to overwrite)
    sweep   weekly: the production gate over universe ∪ denominator → sealed rows appended
    report  maturity-gated counts per cohort × horizon — never a symbol or a per-row verdict

    PYTHONPATH=. venv/bin/python scripts/probe_miss_baserate.py sweep

Run from the WORKTREE on Sundays beside the L0 review. Read-only market-data calls; appends only to
records/miss_baserate/; never imported by the loop; no LLM calls; no write path into any gate.
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv("/home/rodrigo/dramatic_options/.env")

import miss_baserate as mb  # noqa: E402
from config_loader import load_config, require_alpaca_credentials  # noqa: E402
from convexity_data import AlpacaChainProvider  # noqa: E402
from convexity_gate import is_cheap_convexity, realized_vol  # noqa: E402
from data.alpaca_client import AlpacaClient  # noqa: E402
from feeds import to_equity_feed, to_option_feed  # noqa: E402
from structure import contract_eligible, select_structure  # noqa: E402

REC = Path("records/miss_baserate")
DENOM = REC / "denominator.txt"
LEDGER = REC / "ledger.csv"

ap = argparse.ArgumentParser(description="Miss base-rate ledger (PREREG_MISS_BASERATE)")
ap.add_argument("cmd", choices=["init", "sweep", "report"])
args = ap.parse_args()

config = load_config()
api_key, secret_key = require_alpaca_credentials(config)
client = AlpacaClient(api_key, secret_key, paper=True)
gate = config["convexity_gate"]
elig_c = config["eligibility"]["live"]
universe = sorted({s.upper() for b, ms in config["universe"]["themes"].items()
                   if not b.startswith("_") for s in ms})
gate_feed = config["data_feed"]["option_gate"]
prov = AlpacaChainProvider(client, equity_feed=to_equity_feed(config["data_feed"]["equity_bars"]),
                           option_feed=to_option_feed(gate_feed))
PRICE_FLOOR = float(elig_c.get("min_price", 3.0))
ADV_FLOOR = float(elig_c.get("min_adv_usd", 3_000_000))
ADV_WINDOW = int(elig_c.get("adv_window_days", 20))


def _elig(c):
    return contract_eligible(c, max_spread_pct=float(elig_c.get("max_bid_ask_pct", 0.25)),
                             min_contract_price=0.10, max_contract_price=100.0,
                             min_oi=elig_c.get("min_option_open_interest"))


def _bars(sym: str, start: datetime, end: datetime | None = None) -> list[tuple[float, float]]:
    """(close, dollar volume) per daily bar, oldest first."""
    from alpaca.data.enums import DataFeed
    res = client.get_stock_bars(sym, start, end, feed=DataFeed.SIP)
    data = getattr(res, "data", {}) or {}
    rows = data.get(sym, []) if isinstance(data, dict) else []
    return [(float(b.close), float(b.close) * float(b.volume)) for b in rows]


def _passes_floors(sym: str) -> bool:
    bars = _bars(sym, datetime.now(UTC) - timedelta(days=ADV_WINDOW * 2 + 10))[-ADV_WINDOW:]
    if len(bars) < ADV_WINDOW // 2:
        return False
    px = bars[-1][0]
    adv = sum(v for _, v in bars) / len(bars)
    return px >= PRICE_FLOOR and adv >= ADV_FLOOR


def cmd_init() -> None:
    if DENOM.exists():
        sys.exit(f"REFUSED: {DENOM} exists — the denominator is drawn once and frozen (§3)")
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import AssetClass, AssetExchange, AssetStatus
    from alpaca.trading.requests import GetAssetsRequest
    tc = TradingClient(api_key, secret_key, paper=True)
    assets = tc.get_all_assets(GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY))
    ok_ex = {AssetExchange.NASDAQ, AssetExchange.NYSE, AssetExchange.AMEX}
    pool = [a.symbol for a in assets
            if a.tradable and a.exchange in ok_ex and "has_options" in (a.attributes or [])
            and not mb.is_fund_like(a.name) and a.symbol.isalpha()]
    drawn = mb.draw_denominator(pool, set(universe))
    print(f"pool={len(pool)} options-enabled common names outside the {len(universe)}-name universe; "
          f"drawn {len(drawn)} (seed {mb.DRAW_SEED}); applying floors price>=${PRICE_FLOOR:g} "
          f"ADV>=${ADV_FLOOR/1e6:.0f}M in draw order until {mb.DENOMINATOR_N} pass ...")
    kept: list[str] = []
    for sym in drawn:
        try:
            if _passes_floors(sym):
                kept.append(sym)
        except Exception:  # noqa: BLE001 — a data error is a floor fail, not a crash
            pass
        if len(kept) >= mb.DENOMINATOR_N:
            break
    REC.mkdir(parents=True, exist_ok=True)
    DENOM.write_text(
        f"# market denominator — drawn ONCE {datetime.now(UTC):%Y-%m-%d} (PREREG_MISS_BASERATE §3), "
        f"seed={mb.DRAW_SEED} pool={len(pool)} drawn={len(drawn)} kept={len(kept)}; never re-drawn\n"
        + "\n".join(kept) + "\n")
    print(f"frozen {len(kept)} names → {DENOM}")


def _denominator() -> list[str]:
    if not DENOM.exists():
        sys.exit(f"{DENOM} missing — run `init` first")
    return [ln.strip().upper() for ln in DENOM.read_text().splitlines()
            if ln.strip() and not ln.startswith("#")]


def cmd_sweep() -> None:
    denom = _denominator()
    today = datetime.now(ZoneInfo("America/New_York")).date()
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    rows: list[mb.SweepRow] = []
    counts = {"universe": [0, 0, 0], "market": [0, 0, 0]}  # n, structured, cheap
    for cohort, syms in (("universe", universe), ("market", denom)):
        for sym in syms:
            key = mb.seal(sym)
            counts[cohort][0] += 1
            try:
                spot = prov.underlying_price(sym)
                closes = prov.closes(sym, window=300)
                rv = realized_vol(closes, window=int(gate["rv_window_days"]))
                if not spot or rv is None:
                    rows.append(mb.SweepRow(stamp, key, cohort, "bullish", 0, None, None, gate_feed))
                    continue
                mom = (closes[-22] / closes[-253] - 1.0) if len(closes) >= 253 else None
                direction = "bullish" if (mom is None or mom > 0) else "bearish"
                chain = prov.chain(sym)
                s, _why = select_structure(chain, direction=direction, as_of=today, underlying_price=spot,
                                           tenor_min_days=int(gate["tenor_min_days"]),
                                           tenor_max_days=int(gate["tenor_max_days"]),
                                           target_moneyness=float(gate["target_moneyness"]),
                                           eligibility=_elig)
                if s is None:
                    rows.append(mb.SweepRow(stamp, key, cohort, direction, 0, None, float(spot), gate_feed))
                    continue
                counts[cohort][1] += 1
                v = is_cheap_convexity(chain, underlying_price=spot, wing=s.contract, rv=rv,
                                       iv_rv_max=float(gate["iv_rv_max"]),
                                       otm_skew_max_volpts=float(gate["otm_skew_max_volpts"]))
                counts[cohort][2] += int(v.cheap)
                rows.append(mb.SweepRow(stamp, key, cohort, direction, 1, int(v.cheap), float(spot), gate_feed))
            except Exception:  # noqa: BLE001 — a per-name error is a blank row, never a printed verdict
                rows.append(mb.SweepRow(stamp, key, cohort, "bullish", 0, None, None, gate_feed))
    mb.append_rows(LEDGER, rows)
    for cohort, (n, st, ch) in counts.items():
        print(f"{cohort:9} n={n} structured={st} gate_cheap={ch}")
    print(f"appended {len(rows)} sealed rows → {LEDGER} (per-name verdicts sealed, §3)")


def cmd_report() -> None:
    rows = mb.read_rows(LEDGER)
    key_to_sym = {mb.seal(s): s for s in universe + _denominator()}
    cache: dict[tuple[str, str], tuple[list[float], bool]] = {}
    now = datetime.now(UTC)

    def fwd(key: str, date: str) -> tuple[list[float], bool]:
        if (key, date) in cache:
            return cache[(key, date)]
        sym = key_to_sym.get(key)
        if sym is None:
            out: tuple[list[float], bool] = ([], False)
        else:
            start = datetime.fromisoformat(date).replace(tzinfo=UTC) + timedelta(days=1)
            try:
                bars = _bars(sym, start)
            except Exception:  # noqa: BLE001
                bars = []
            closes = [c for c, _ in bars]
            # terminated = the series stopped ≥ 10 calendar days before now (delisted/halted)
            last = None
            if bars:
                res = None
                try:
                    res = client.get_stock_bars(sym, now - timedelta(days=14))
                    last = (getattr(res, "data", {}) or {}).get(sym, [])
                except Exception:  # noqa: BLE001
                    last = None
            terminated = bool(bars) and not last
            out = (closes, terminated)
        cache[(key, date)] = out
        return out

    print(mb.render(mb.aggregate(rows, fwd)))
    print(f"\n(rows={len(rows)}, sweeps={len({r.date for r in rows})}; no symbol or key is printed, §3)")


{"init": cmd_init, "sweep": cmd_sweep, "report": cmd_report}[args.cmd]()
