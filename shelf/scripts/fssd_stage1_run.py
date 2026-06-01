"""FSSD Stage-1 gross-CAR gate runner (PREREG §6 / FREEZE-B) — THE k=1 MEASUREMENT.

⚠ Running this **computes CAR** → it consumes Bonferroni **k=1** (and each subsequent distinct
run a further round). It is gated on: §8 audit PASS (done) + FREEZE-B recorded (done). It reads
the FROZEN `fssd` params from config.json; do not change them and re-run without incrementing k.

Pipeline (explore window only; lockbox stays sealed):
  enumerate 424B5 → resolve ticker → point-in-time friction inputs (SI/float/ADV/price) →
  TRAILING-window friction deciles (no lookahead) → forward CAR = stock_fwd − β·SPY_fwd at
  h=10td → top-decile monthly-mean series → block-bootstrap CI (α=0.05/k, must exclude 0 &
  be negative) → bands on |net CAR| (− cost stub). Plus the per-decile signed-CAR grid (#2),
  a NULL control (random in-name dates) and a POSITIVE control (unconditional drift).

Forward bars: unlike the coverage phases, MarketData here fetches PAST ``end`` by ~h·1.6
sessions so the forward-return label exists. Usage:
  python scripts/fssd_stage1_run.py --k 1                 # explore window from config
  python scripts/fssd_stage1_run.py --k 1 --max-events 60 # wiring smoke (still k=1!)
  python scripts/fssd_stage1_run.py --offline --k 1       # cache-only replay
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from config_loader import load_config  # noqa: E402
from data.cache import PointInTimeCache  # noqa: E402
from data.edgar_index import EdgarIndex  # noqa: E402
from fssd_stage1 import (  # noqa: E402
    assign_trailing_deciles,
    evaluate_stage1,
    forward_car,
    monthly_mean_series,
    per_decile_grid,
    result_text,
)
from scripts.fssd_audit import _cik_to_ticker_map, _edgar_user_agent  # noqa: E402

BANNER = "FSSD STAGE-1 GROSS-CAR GATE  ·  ⚠ COMPUTES CAR → CONSUMES BONFERRONI k"


def _dt(s: str | None, default: str) -> datetime:
    return datetime.fromisoformat(s or default).replace(tzinfo=UTC)


def _build_events(config, start, end, *, offline, max_events):
    """Enumerate + per-event point-in-time friction inputs and forward CAR. Returns the event
    list (each: ts, ticker, inputs, car) plus a funnel dict. Mirrors the corner phase's funnel
    but adds the forward-CAR label (needs forward bars)."""
    from data.finra_si import FinraShortInterest, si_pct_of_shares
    from data.market import MarketData
    from data.shares_out import SharesOutData
    from friction import friction_inputs
    from universe import check_eligibility

    fssd = config["fssd"]
    form = fssd.get("event", {}).get("forms", ["424B5"])[0]
    h = int(fssd.get("horizon_days", 10))
    elig_cfg = config.get("eligibility", {}).get("backtest", {})
    cache_dir = config.get("edgar", {}).get("cache_dir", "data/cache")
    benchmark = config.get("universe", {}).get("benchmarks", {}).get("broad", "SPY")

    cache = PointInTimeCache(cache_dir, offline=offline)
    edgar = alpaca = None
    if not offline:
        from data.filings import EdgarClient
        edgar = EdgarClient(_edgar_user_agent(config), cache_dir=cache_dir,
                            rate_limit_per_sec=config.get("edgar", {}).get("rate_limit_per_sec", 8.0))
        if config.get("alpaca", {}).get("api_key"):
            from data.alpaca_client import AlpacaClient
            alpaca = AlpacaClient(config["alpaca"]["api_key"], config["alpaca"]["secret_key"],
                                  paper=config["alpaca"]["paper"])

    idx = EdgarIndex(cache, edgar=edgar, cache_dir=cache_dir, form=form)
    events_raw = idx.enumerate_events(start, end)
    if max_events:
        events_raw = events_raw[:max_events]

    cik2tkr = _cik_to_ticker_map(cache_dir)
    # forward bars: extend fetch_end past the window so the h-day label exists.
    fetch_start = start - timedelta(days=120)
    fetch_end = end + timedelta(days=math.ceil(h * 1.6) + 10)
    market = MarketData(cache, client=alpaca, fetch_start=fetch_start, fetch_end=fetch_end)
    si = FinraShortInterest(cache, fetch_start=start - timedelta(days=400), fetch_end=end,
                            cache_dir=cache_dir)
    shares = SharesOutData(cache, edgar=edgar, fetch_end=fetch_end,
                           ua=config.get("edgar", {}).get("user_agent", ""), cache_dir=cache_dir)

    funnel = {"raw": len(events_raw), "no_ticker": 0, "no_bars": 0, "ineligible": 0,
              "no_car": 0, "eligible": 0}
    out = []
    for e in events_raw:
        as_of = datetime.fromisoformat(e["ts"])
        tkr = cik2tkr.get(e["cik"])
        if not tkr:
            funnel["no_ticker"] += 1
            continue
        try:
            price = market.latest_price(tkr, as_of)
            adv = market.adv_usd(tkr, as_of, window=int(elig_cfg.get("adv_window_days", 20)))
        except Exception:  # noqa: BLE001
            price = adv = None
        if price is None:
            funnel["no_bars"] += 1
            continue
        if not check_eligibility(tkr, as_of, price=price, adv_usd=adv, config=config,
                                 mode="backtest").eligible:
            funnel["ineligible"] += 1
            continue
        try:
            so, _ = shares.shares_out_asof(tkr, as_of, price=price)
        except Exception:  # noqa: BLE001
            so = None
        try:
            sirec = si.si_asof(tkr, as_of)
        except Exception:  # noqa: BLE001
            sirec = None
        si_shares = sirec.get("si_shares") if sirec else None
        dtc = sirec.get("days_to_cover") if sirec else None
        inp = friction_inputs(si_pct=si_pct_of_shares(si_shares, so), shares_out=so,
                              adv_usd=adv, price=price, days_to_cover=dtc)
        # forward CAR label (needs forward bars for both legs + beta)
        try:
            s_fwd = market.forward_return(tkr, as_of, h)
            b_fwd = market.forward_return(benchmark, as_of, h)
            beta = market.beta(tkr, benchmark, as_of)
        except Exception:  # noqa: BLE001
            s_fwd = b_fwd = beta = None
        car = forward_car(s_fwd, b_fwd, beta)
        if car is None:
            funnel["no_car"] += 1
            continue
        funnel["eligible"] += 1
        out.append({"ts": as_of, "ticker": tkr, "inputs": inp, "car": car})
    return out, funnel, h


def _null_series(events, deciles, top_decile, *, seed=11):
    """NULL control: keep the top-decile NAMES but shuffle their CARs across the same months
    (destroys the event→CAR link while preserving the name/month mix). If the edge is the
    EVENT, this vanishes; if it's a friction CHARACTERISTIC, it persists. Reuses the same
    monthly resampling."""
    rng = np.random.default_rng(seed)
    top = [e for e, d in zip(events, deciles, strict=True) if d == top_decile and e["car"] is not None]
    cars = np.array([e["car"] for e in top])
    if len(cars) < 2:
        return []
    shuffled = cars.copy()
    rng.shuffle(shuffled)
    fake = [{"ts": e["ts"], "car": float(c)} for e, c in zip(top, shuffled, strict=True)]
    return monthly_mean_series(fake)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="FSSD Stage-1 gross-CAR gate (computes CAR; uses k)")
    p.add_argument("--k", type=int, required=True, help="Bonferroni rounds consumed (first run = 1)")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--max-events", type=int, default=None, help="wiring smoke cap (still k!)")
    args = p.parse_args(argv)

    config = load_config()
    fssd = config["fssd"]
    start = _dt(args.start, fssd.get("explore_start", "2019-01-01"))
    end = _dt(args.end, fssd.get("explore_end", "2022-12-31"))
    n_deciles = int(fssd.get("friction", {}).get("deciles", 10))
    weights = fssd.get("friction", {}).get("weights", {})
    alpha = float(fssd.get("alpha_base", 0.05)) / max(1, args.k)

    print("=" * 78)
    print(BANNER)
    print("=" * 78)
    print(f"window={start.date()}→{end.date()} (EXPLORE; lockbox sealed)   k={args.k}   "
          f"config_hash={_fssd_hash(fssd)}")
    if args.max_events:
        print(f"  ⚠ --max-events {args.max_events}: WIRING SMOKE, not the real verdict (still uses k).")

    events, funnel, h = _build_events(config, start, end, offline=args.offline,
                                      max_events=args.max_events)
    print(f"  funnel: raw {funnel['raw']} → no_ticker {funnel['no_ticker']} · no_bars "
          f"{funnel['no_bars']} · ineligible {funnel['ineligible']} · no_car {funnel['no_car']} "
          f"→ eligible+labelled {funnel['eligible']}")
    if funnel["eligible"] < 30:
        print("  STOP: too few labelled events to assign trailing deciles. (widen window / check cache)")
        return 2

    deciles = assign_trailing_deciles(events, weights=weights, n_deciles=n_deciles)
    top = n_deciles - 1
    top_series = monthly_mean_series(events, deciles=deciles, only_decile=top)
    grid = per_decile_grid(events, deciles, n_deciles=n_deciles)
    null = _null_series(events, deciles, top)
    pos = monthly_mean_series(events)  # unconditional (all eligible) = positive control

    res = evaluate_stage1(top_series, k_iterations=args.k, config_fssd=fssd, per_decile=grid,
                          null_series=null or None, poscontrol_series=pos or None)
    print("-" * 78)
    print(result_text(res, horizon=h, k=args.k, alpha=alpha))
    print("=" * 78)

    out_dir = Path(config.get("backtest", {}).get("artifacts_dir", "data/backtest")) / \
        ("fssd_stage1_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stage1.json").write_text(json.dumps({
        "window": [start.isoformat(), end.isoformat()], "k": args.k, "horizon": h,
        "config_hash": _fssd_hash(fssd), "funnel": funnel,
        "result": {k: v for k, v in res.__dict__.items()},
    }, default=str, indent=2))
    print(f"Artifacts → {out_dir}")
    # exit 0 = ran cleanly (band is in the report); non-zero only on inability to run.
    return 0


def _fssd_hash(fssd: dict) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(fssd, sort_keys=True).encode()).hexdigest()[:16]


if __name__ == "__main__":
    raise SystemExit(main())
