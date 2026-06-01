"""FSSD eligible-N audit CLI (PREREG_FSSD.md §8) — the cheap stop-or-go.

COVERAGE ONLY. This computes **no CAR / no returns** and **consumes no Bonferroni k-round**
(exactly like backtest.engine.Backtest.audit). Its sole job is to decide whether the FSSD
event population — and, in --phase corner, the friction ∩ optionable ∩ tradable corner — is
powered enough (≥ fssd.audit.n_min_months distinct calendar months) to justify building the
Stage-1 CAR gate. A STOP here is a valid, cheap finding (PREREG §12).

Phases:
  count   §8a — enumerate 424B5 events, count distinct calendar months. Free, no bulk fetch.
  corner  §8b — (only after 8a PASS) friction/optionability/tradability corner audit.

Usage:
  python scripts/fssd_audit.py --phase count --start 2019-01-01 --end 2024-12-31
  python scripts/fssd_audit.py --phase count --offline      # cache-only replay

Not run in CI (needs network). Parsers/logic are unit-tested offline against fixtures.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config_loader import load_config  # noqa: E402
from data.cache import PointInTimeCache  # noqa: E402
from data.edgar_index import EdgarIndex, month_key  # noqa: E402

BANNER = "FSSD ELIGIBLE-N AUDIT — coverage only · NO CAR computed · NO Bonferroni k consumed"


def _dt(s: str | None, default: str) -> datetime:
    return datetime.fromisoformat(s or default).replace(tzinfo=UTC)


def _edgar_user_agent(config: dict) -> str:
    """EDGAR contact UA: config edgar.user_agent, else EDGAR_USER_AGENT from env/.env."""
    ua = config.get("edgar", {}).get("user_agent") or os.environ.get("EDGAR_USER_AGENT", "")
    if not ua:
        raise SystemExit(
            "ERROR: EDGAR contact User-Agent required. Set EDGAR_USER_AGENT in .env "
            "(e.g. 'dramatic-options you@example.com')."
        )
    return ua


def phase_count(config: dict, start: datetime, end: datetime, *, offline: bool) -> int:
    fssd = config.get("fssd", {})
    forms = fssd.get("event", {}).get("forms", ["424B5"])
    form = forms[0]
    n_min_months = int(fssd.get("audit", {}).get("n_min_months", 24))
    cache_dir = config.get("edgar", {}).get("cache_dir", "data/cache")

    cache = PointInTimeCache(cache_dir, offline=offline)
    edgar = None
    if not offline:
        from data.filings import EdgarClient

        edgar = EdgarClient(
            _edgar_user_agent(config),
            cache_dir=cache_dir,
            rate_limit_per_sec=config.get("edgar", {}).get("rate_limit_per_sec", 8.0),
        )
    idx = EdgarIndex(cache, edgar=edgar, cache_dir=cache_dir, form=form)
    events = idx.enumerate_events(start, end)

    months = Counter(month_key(e["ts"]) for e in events)
    distinct_months = len(months)
    distinct_ciks = len({e["cik"] for e in events})

    print("=" * 78)
    print(BANNER)
    print("=" * 78)
    print(f"PHASE 8a — event count   form={form}   window={start.date()}→{end.date()}"
          f"   {'OFFLINE' if offline else 'online'}")
    print(f"  total {form} events        : {len(events)}")
    print(f"  distinct issuers (CIK)     : {distinct_ciks}")
    print(f"  distinct calendar months   : {distinct_months}   (FSSD resampling unit)")
    print(f"  n_min_months (frozen gate) : {n_min_months}")
    print("  events per calendar month:")
    for ym in sorted(months):
        n = months[ym]
        print(f"    {ym}: {'#' * min(n, 60)} {n}")

    passed = distinct_months >= n_min_months
    print("-" * 78)
    if passed:
        print(f"  RESULT: PASS — {distinct_months} ≥ {n_min_months} distinct months. "
              "Phase 8a power floor cleared; 8b corner audit is justified.")
        print("  NOTE: 8a counts the RAW event population. The binding test is 8b's "
              "friction ∩ optionable ∩ tradable corner × distinct months.")
    else:
        print(f"  RESULT: STOP — only {distinct_months} < {n_min_months} distinct months. "
              "Underpowered at the raw level; do not build 8b. (PREREG §8/§12)")
    print("=" * 78)
    return 0 if passed else 1


def _cik_to_ticker_map(cache_dir: str) -> dict[str, str]:
    """Invert EDGAR's company_tickers.json → {cik(10): TICKER} (current snapshot).

    CIKs absent here are delisted/renamed names with no *current* ticker — those events drop
    out of the corner audit, and that drop is COUNTED and reported (the survivorship-honest
    cost, PREREG §4/§8b). Reverse-mapping by current ticker is itself an approximation for the
    historical event date; it is acceptable for a coverage ceiling, never for point-in-time CAR.
    """
    path = Path(cache_dir) / "edgar" / "company_tickers.json"
    if not path.exists():
        return {}
    import json
    raw = json.loads(path.read_text())
    out: dict[str, str] = {}
    for row in raw.values():
        cik = str(row["cik_str"]).zfill(10)
        # Alpaca uses a dot for share-class tickers (BRK.B), EDGAR uses a hyphen (BRK-B).
        ticker = str(row["ticker"]).upper().replace("-", ".")
        # first ticker for a CIK wins (deterministic by file order)
        out.setdefault(cik, ticker)
    return out


def phase_corner(config: dict, start: datetime, end: datetime, *, offline: bool,
                 max_events: int | None) -> int:
    """§8b corner audit — COVERAGE ONLY (no CAR, no k). Builds the friction cross-section over
    the window's events, identifies the high-friction corner, then audits optionability,
    current option-tradability (#1), deal-size recall (#3), friction collinearity (#4), and
    serial-diluter / SI-staleness diagnostics (#5). Prints PASS/STOP on the tradable corner."""
    from datetime import timedelta

    fssd = config.get("fssd", {})
    form = fssd.get("event", {}).get("forms", ["424B5"])[0]
    n_min_months = int(fssd.get("audit", {}).get("n_min_months", 24))
    corner_q = float(fssd.get("friction", {}).get("corner_quantile", 0.8))
    fr_weights = fssd.get("friction", {}).get("weights")
    min_recall = float(fssd.get("deal_size", {}).get("min_recall", 0.70))
    elig_cfg = config.get("eligibility", {}).get("backtest", {})
    cache_dir = config.get("edgar", {}).get("cache_dir", "data/cache")

    from data.finra_si import FinraShortInterest, si_pct_of_shares
    from data.market import MarketData
    from data.prospectus import parse_offering_size
    from data.shares_out import SharesOutData
    from friction import friction_inputs, score_cross_section
    from options_tradability import summarize_put_tradability
    from universe import check_eligibility

    cache = PointInTimeCache(cache_dir, offline=offline)
    edgar = alpaca = None
    if not offline:
        from data.filings import EdgarClient
        edgar = EdgarClient(_edgar_user_agent(config), cache_dir=cache_dir,
                            rate_limit_per_sec=config.get("edgar", {}).get("rate_limit_per_sec", 8.0))

    idx = EdgarIndex(cache, edgar=edgar, cache_dir=cache_dir, form=form)
    events = idx.enumerate_events(start, end)
    if max_events:
        events = events[:max_events]

    cik2tkr = _cik_to_ticker_map(cache_dir)
    if not offline and config.get("alpaca", {}).get("api_key"):
        from data.alpaca_client import AlpacaClient
        alpaca = AlpacaClient(config["alpaca"]["api_key"], config["alpaca"]["secret_key"],
                              paper=config["alpaca"]["paper"])
    # bars only need trailing data (ADV/price) — no forward bars (no CAR). Modest warmup.
    # MarketData needs the Alpaca client to FETCH bars online (offline → cache-only reads).
    fetch_start = start - timedelta(days=90)
    market = MarketData(cache, client=alpaca, fetch_start=fetch_start, fetch_end=end)
    si = FinraShortInterest(cache, fetch_start=start - timedelta(days=400), fetch_end=end,
                            cache_dir=cache_dir)
    shares = SharesOutData(cache, edgar=edgar, fetch_end=end,
                           ua=config.get("edgar", {}).get("user_agent", ""), cache_dir=cache_dir)

    # ── per-event friction inputs (point-in-time at the event ts) ─────────────
    rows: list[dict] = []        # friction-input dicts (cross-section)
    meta: list[dict] = []        # parallel: per-event context
    n_no_ticker = n_no_bars = n_ineligible = 0
    for e in events:
        as_of = datetime.fromisoformat(e["ts"])
        tkr = cik2tkr.get(e["cik"])
        if not tkr:
            n_no_ticker += 1
            continue
        # Fail-closed per event: a symbol Alpaca rejects (e.g. BRK-B vs BRK.B, units/warrants,
        # delisted) or any fetch error drops the name into n_no_bars — it never aborts the
        # whole audit. (A coverage audit must survive the long tail of messy tickers.)
        try:
            price = market.latest_price(tkr, as_of)
            adv = market.adv_usd(tkr, as_of, window=int(elig_cfg.get("adv_window_days", 20)))
        except Exception:  # noqa: BLE001 — bad/uncached symbol → drop, count, continue
            price = adv = None
        if price is None:
            n_no_bars += 1
            continue
        elig = check_eligibility(tkr, as_of, price=price, adv_usd=adv, config=config, mode="backtest")
        if not elig.eligible:
            n_ineligible += 1
            continue
        try:
            so, so_src = shares.shares_out_asof(tkr, as_of, price=price)
        except Exception:  # noqa: BLE001 — XBRL gap → no float; friction input just missing
            so, so_src = None, None
        try:
            sirec = si.si_asof(tkr, as_of)
        except Exception:  # noqa: BLE001 — no SI coverage → input missing (mean-imputed)
            sirec = None
        si_shares = sirec.get("si_shares") if sirec else None
        dtc = sirec.get("days_to_cover") if sirec else None
        si_pct = si_pct_of_shares(si_shares, so)
        rows.append(friction_inputs(si_pct=si_pct, shares_out=so, adv_usd=adv, price=price,
                                    days_to_cover=dtc))
        meta.append({"event": e, "ticker": tkr, "as_of": as_of, "price": price,
                     "shares_out": so, "so_src": so_src, "si": sirec})

    fr = score_cross_section(rows, weights=fr_weights, corner_quantile=corner_q)
    corner = [m for m, c in zip(meta, fr.in_corner, strict=True) if c]

    # ── deal-size recall (#3) + option tradability (#1) on the CORNER ─────────
    n_size_prospectus = n_size_xbrl = 0
    subtypes: Counter = Counter()
    tradable_results = []
    for m in corner:
        # XBRL shares-out delta (deterministic supply validator + subtype)
        d = shares.delta_around(m["ticker"], m["as_of"]) if not offline else None
        if d:
            n_size_xbrl += 1
            subtypes[d["subtype"]] += 1
        # prospectus parse (best-effort; corner only, cost control)
        if edgar is not None:
            txt = _fetch_submission_text(edgar, m["event"]["file"])
            if txt and parse_offering_size(txt):
                n_size_prospectus += 1
        # current option-tradability ceiling
        if alpaca is not None:
            try:
                quotes = alpaca.option_quote_tuples(m["ticker"])
                pt = summarize_put_tradability(quotes, underlying_price=m["price"])
                tradable_results.append((m, pt))
            except Exception:  # noqa: BLE001 — no chain today (likely delisted) → untradable
                tradable_results.append((m, None))

    _print_corner_report(
        form=form, start=start, end=end, offline=offline, n_min_months=n_min_months,
        corner_q=corner_q, events=events, rows=rows, meta=meta, fr=fr, corner=corner,
        n_no_ticker=n_no_ticker, n_no_bars=n_no_bars, n_ineligible=n_ineligible,
        n_size_prospectus=n_size_prospectus, n_size_xbrl=n_size_xbrl, min_recall=min_recall,
        subtypes=subtypes, tradable_results=tradable_results,
    )
    # PASS requires a non-empty tradable corner spanning ≥ n_min_months distinct months
    tradable_months = {
        month_key(m["event"]["ts"]) for m, pt in tradable_results if pt and pt.tradable
    }
    passed = len(tradable_months) >= n_min_months
    return 0 if passed else 1


def _fetch_submission_text(edgar, file_path: str) -> str | None:
    """Fetch a filing's full submission text via EDGAR archives (corner deal-size parse)."""
    url = f"https://www.sec.gov/Archives/{file_path}"
    try:
        return edgar._get_text(url)  # reuse UA + throttle  # noqa: SLF001
    except Exception:  # noqa: BLE001
        return None


def _print_corner_report(**k) -> None:
    form, start, end = k["form"], k["start"], k["end"]
    events, meta, fr, corner = k["events"], k["meta"], k["fr"], k["corner"]
    n_min_months = k["n_min_months"]
    tradable_results = k["tradable_results"]

    corner_months = {month_key(m["event"]["ts"]) for m in corner}
    tradable = [(m, pt) for m, pt in tradable_results if pt and pt.tradable]
    tradable_months = {month_key(m["event"]["ts"]) for m, pt in tradable}
    spreads = [pt.median_put_spread_pct for _, pt in tradable if pt.median_put_spread_pct is not None]

    # #4 friction-input collinearity
    corr = fr.input_corr
    # #5 serial-diluter concentration over the eligible cross-section
    names = [m["ticker"] for m in meta]
    name_counts = Counter(names)
    top_share = (max(name_counts.values()) / len(names)) if names else 0.0
    hhi = sum((c / len(names)) ** 2 for c in name_counts.values()) if names else 0.0
    # #5 SI staleness (days between SI publication and event)
    stale = []
    for m in meta:
        if m["si"]:
            pub = datetime.fromisoformat(m["si"]["ts"])
            stale.append((m["as_of"] - pub).days)
    # float-source coverage
    src_counts = Counter(m["so_src"] for m in meta if m["so_src"])

    print("=" * 78)
    print(BANNER)
    print("=" * 78)
    print(f"PHASE 8b — friction corner   form={form}   window={start.date()}→{end.date()}"
          f"   {'OFFLINE' if k['offline'] else 'online'}")
    print("  ── funnel (events → eligible cross-section) ──")
    print(f"    enumerated events           : {len(events)}")
    print(f"    dropped: no current ticker  : {k['n_no_ticker']}   (delisted/renamed — survivorship cost)")
    print(f"    dropped: no bars            : {k['n_no_bars']}")
    print(f"    dropped: ineligible (px/ADV): {k['n_ineligible']}")
    print(f"    eligible cross-section      : {len(meta)}")
    print(f"  ── friction corner (top {1 - k['corner_q']:.0%} by composite) ──")
    print(f"    high-friction corner events : {len(corner)}   over {len(corner_months)} distinct months")
    print("  ── #1 option-tradability CEILING (current snapshot; upper bound, NOT point-in-time) ──")
    print(f"    corner names probed         : {len(tradable_results)}")
    print(f"    with a tradable near-money put: {len(tradable)}   over {len(tradable_months)} distinct months")
    if spreads:
        print(f"    median put bid/ask spread   : {statistics.median(spreads):.1%}  "
              f"(min {min(spreads):.1%} / max {max(spreads):.1%})")
    else:
        print("    median put bid/ask spread   : n/a (no tradable corner puts)")
    print("  ── #3 deal-size coverage (recall vs frozen min_recall) ──")
    nc = max(1, len(corner))
    print(f"    prospectus-parsed size      : {k['n_size_prospectus']}/{len(corner)} = {k['n_size_prospectus']/nc:.0%}")
    print(f"    XBRL shares-out delta       : {k['n_size_xbrl']}/{len(corner)} = {k['n_size_xbrl']/nc:.0%}")
    best_recall = max(k['n_size_prospectus'], k['n_size_xbrl']) / nc
    print(f"    best-of recall              : {best_recall:.0%}   (min_recall={k['min_recall']:.0%} → "
          f"{'size-conditioning SURVIVES' if best_recall >= k['min_recall'] else 'DROP size, friction carries v1'})")
    if k["subtypes"]:
        print(f"    subtype split (XBRL delta)  : {dict(k['subtypes'])}  (primary=dilutive, secondary=flat shares-out)")
    print("  ── #4 friction-input collinearity (FREEZE-B reweighting evidence) ──")
    if corr:
        for pair, v in sorted(corr.items(), key=lambda x: -abs(x[1])):
            print(f"    corr({pair:>22}) = {v:+.2f}")
    print("  ── #5 data-realism diagnostics ──")
    print(f"    distinct names (eligible)   : {len(name_counts)}   top-name share {top_share:.0%}  HHI {hhi:.3f}")
    if stale:
        print(f"    SI staleness at event (days): median {int(statistics.median(stale))}  "
              f"(bi-monthly + ~8td pub lag → key input is weeks stale)")
    print(f"    float source breakdown      : {dict(src_counts)}")
    print("    NOTE: 424B5 is a LATE marker (announcement/8-K precedes) → entry-timing caveat for Stage-1.")
    print("-" * 78)
    # Months physically available in the queried window — the n_min_months floor (24) is for
    # the FULL pre-registered explore window; a shorter slice cannot clear it by construction, so
    # report the artifact rather than mis-declaring a STOP.
    months_available = len({month_key(e["ts"]) for e in events})
    passed = len(tradable_months) >= n_min_months
    if passed:
        print(f"  RESULT: PASS — tradable friction corner spans {len(tradable_months)} ≥ "
              f"{n_min_months} distinct months. Stage-1 CAR gate is justified (→ FREEZE-B).")
    elif months_available < n_min_months:
        print(f"  RESULT: INCONCLUSIVE (window too short) — tradable corner spans "
              f"{len(tradable_months)} months, but only {months_available} calendar months exist "
              f"in this window (floor={n_min_months}). Re-run the FULL explore window for a verdict.")
    else:
        print(f"  RESULT: STOP — tradable friction corner spans only {len(tradable_months)} < "
              f"{n_min_months} distinct months. The profitable-and-tradable corner is too thin "
              "(borrow-in-the-puts / optionability hollowing, PREREG §12). Do not build Stage-1.")
    print("  (coverage only — NO CAR computed, NO Bonferroni k consumed)")
    print("=" * 78)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="FSSD eligible-N audit (coverage only)")
    p.add_argument("--phase", choices=["count", "corner"], default="count")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--offline", action="store_true", help="cache-only, no network")
    p.add_argument("--max-events", type=int, default=None,
                   help="cap events processed (corner phase cost control; slice-first)")
    args = p.parse_args(argv)

    config = load_config()
    fssd = config.get("fssd", {})
    start = _dt(args.start, fssd.get("explore_start", "2019-01-01"))
    # default end = lockbox_end (full pre-registered window) so the audit sees all events
    end = _dt(args.end, fssd.get("lockbox_end") or "2024-12-31")

    if args.phase == "count":
        return phase_count(config, start, end, offline=args.offline)
    return phase_corner(config, start, end, offline=args.offline, max_events=args.max_events)


if __name__ == "__main__":
    raise SystemExit(main())
