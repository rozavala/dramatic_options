"""KEYED un-confounding corpus-REACH measurement (PREREG_SEEDED_GENERATOR_DIAGNOSTIC §12).

The keyed companion to the NO-FETCH ``corpus_reach_diagnostic.py``. That one measures *which* entities a
source surfaces but reads news only where it is already cached (so non-universe quiet is unmeasured — the
``no_fetch`` confound §11 hit). This one FETCHES, so it answers the §12 fork: does a financing-event source
(``capital_raises``) reach genuinely-quiet, optionable, **basket-able quality** non-universe names a theme's
ETF would miss — i.e. is a SIC-scoped source worth building as a §11 curation source?

READ-ONLY market data (Alpaca bars + news + OPRA chain reads); NO universe edit, NO discovery scan → it does
not re-stale the §5 read. Run from the repo root; live keys are read from the live checkout's ``.env`` at
runtime (the ``probe_basket_feasibility`` pattern). Never imported by the loop.

The funnel (cost-ordered; ``Q`` = quiet ∧ §11-admissible — the conjunction is order-independent):
  P  = non-universe ``capital_raises`` filers, CIK→ticker-resolvable
  L  = P ∩ {price ≥ floor ∧ ADV ≥ floor}                     (batched SIP bars — the cheap §11 floors first)
  Qn = L ∩ {raise-aware trailing-90d news ≤ cut}             (the un-confound; raise-aware = pre-filing baseline)
  Q  = Qn ∩ {§11 structure ∧ eligible ∧ fits 1 contract ≤ per-name cap}   (OPRA, on the small Qn set)
  Stage-2a: SIC sector geometry on Q (≥1 sector with ≥3 = basket-able; else scattered → no source build)

**IPO guard (§12 result, the raise-aware fix):** a never-previously-public S-1 filer has no pre-filing news
because it was not trading — it reads FALSE-quiet (Fervo at 37 articles/90d, Cerebras at 80, both scored
quiet=0 in the 2026-06-28 run). The raise-aware baseline is therefore used ONLY when the name was already
public before the filing (it has equity bars predating the filing); otherwise the name is classified by its
current (naive-90d) narration. The guard only ever *raises* the news count for IPOs (never lowers a genuine
quiet read), so it can only tighten ``Q``.

Usage (repo root, worktree venv; live keys from the live checkout's .env):
    PYTHONPATH=. venv/bin/python scripts/corpus_reach_measure.py            # full population
    PYTHONPATH=. venv/bin/python scripts/corpus_reach_measure.py --limit 150 --tag smoke
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv("/home/rodrigo/dramatic_options/.env")  # live keys (live checkout); never committed
os.environ.setdefault("EDGAR_USER_AGENT", "dramatic-options-reach rozavala@gmail.com")

import requests  # noqa: E402

from config_loader import load_config, require_alpaca_credentials  # noqa: E402
from convexity_data import AlpacaChainProvider  # noqa: E402
from convexity_sizing import convexity_position_size  # noqa: E402
from corpus.assemble import assemble_corpus  # noqa: E402
from corpus.capital_raises import SOURCE as CAP  # noqa: E402
from corpus.content import all_basket_symbols, load_content, read_coords  # noqa: E402
from data.alpaca_client import AlpacaClient  # noqa: E402
from data.cache import PointInTimeCache  # noqa: E402
from data.filings import EdgarClient  # noqa: E402
from data.news import NewsData  # noqa: E402
from feeds import to_equity_feed, to_option_feed  # noqa: E402
from structure import contract_eligible, select_structure  # noqa: E402

QUIET_NEWS_CUT = 3
NEWS_WINDOW = 90


def _sic_for(edgar: EdgarClient, ua: str, ticker: str) -> tuple[str | None, str | None]:
    """(sic, sicDescription) from the EDGAR submissions JSON (top-level, keyless+UA)."""
    try:
        cik = edgar.ticker_to_cik(ticker)
    except Exception:  # noqa: BLE001
        cik = None
    if not cik:
        return (None, None)
    try:
        j = requests.get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json",
                         headers={"User-Agent": ua}, timeout=30).json()
        return (j.get("sic"), j.get("sicDescription"))
    except Exception:  # noqa: BLE001
        return (None, None)


def main() -> int:
    ap = argparse.ArgumentParser(description="Keyed corpus-reach measurement (PREREG §12)")
    ap.add_argument("--limit", type=int, default=0, help="cap population (smoke); 0 = all")
    ap.add_argument("--tag", default="full", help="output record tag")
    args = ap.parse_args()

    config = load_config()
    content = load_content()
    cache_dir = config.get("cache_dir", "data/cache")
    as_of = datetime.now(UTC)
    cutoff90 = as_of - timedelta(days=NEWS_WINDOW)
    ua = os.environ["EDGAR_USER_AGENT"]

    gate = config["convexity_gate"]
    book = config["convexity_book"]
    elig_c = config["eligibility"]["live"]
    EQ = float(book.get("account_equity", 100000))
    PER_NAME = EQ * float(book["per_name_fraction"])
    ADV_FLOOR = float(elig_c.get("min_adv_usd", 3_000_000))
    PRICE_FLOOR = float(elig_c.get("min_price", 3.0))
    ADV_WINDOW = int(elig_c.get("adv_window_days", 20))
    eq_feed = to_equity_feed(config["data_feed"]["equity_bars"])

    api_key, secret_key = require_alpaca_credentials(config)
    client = AlpacaClient(api_key, secret_key, paper=True)
    cache_ro = PointInTimeCache(cache_dir, offline=True)
    cache_rw = PointInTimeCache(cache_dir, offline=False)
    universe = set(all_basket_symbols(config))
    edgar = EdgarClient(ua, cache_dir=cache_dir)
    curated_ciks = {c for c in (edgar.ticker_to_cik(t) for t in universe) if c}
    cik2tk = {cik: tk for tk, cik in edgar._load_ticker_map().items()}

    # ── P: non-universe capital_raises filers, CIK→ticker, latest filing date ──
    corpus = assemble_corpus(cache_ro, as_of, read_coords(content, config), tag_key=True)
    filers: dict[str, dict[str, Any]] = {}
    for r in corpus.get(CAP, []):
        cik = str(r.get("cik") or "").strip()
        if not cik or cik in curated_ciks:
            continue
        tk = cik2tk.get(cik)
        if not tk:
            continue
        d = str(r.get("date_filed") or r.get("ts") or "")[:10]
        f = filers.setdefault(cik, {"ticker": tk.upper(), "company": r.get("company"), "last_filed": d})
        f["last_filed"] = max(f["last_filed"], d)
    fmap = {f["ticker"]: f for f in filers.values()}  # dedupe by ticker
    all_tk = sorted(fmap)
    syms = [t for t in all_tk if "-" not in t and "." not in t]  # drop warrant/pfd/when-issued shapes
    if args.limit:
        syms = syms[: args.limit]
    print(f"[P] non-universe capital_raises CIK→ticker: {len(all_tk)} "
          f"(→ {len(syms)} common-shaped; dropped {len(all_tk) - len(syms)} -/. tickers)", flush=True)

    # ── L: batched SIP bars (≥1y so the IPO guard can see pre-filing history) → price, ADV, first-bar ──
    start = as_of - timedelta(days=400)
    price: dict[str, float] = {}
    adv: dict[str, float] = {}
    first_bar: dict[str, datetime] = {}
    invalid: list[str] = []

    def fetch_bars(chunk: list[str]) -> None:
        if not chunk:
            return
        try:
            bars = client.get_stock_bars(chunk, start=start, feed=eq_feed)
        except Exception:  # noqa: BLE001 — one bad symbol 400s the whole batch → split & retry
            if len(chunk) == 1:
                invalid.append(chunk[0])
                return
            mid = len(chunk) // 2
            fetch_bars(chunk[:mid])
            fetch_bars(chunk[mid:])
            return
        data = getattr(bars, "data", {}) or {}
        for s in chunk:
            rows = [b for b in data.get(s, []) if getattr(b, "close", None) and getattr(b, "volume", None)]
            if not rows:
                continue
            price[s] = float(rows[-1].close)
            adv[s] = sum(float(b.close) * float(b.volume) for b in rows[-ADV_WINDOW:]) / len(rows[-ADV_WINDOW:])
            first_bar[s] = rows[0].timestamp

    for i in range(0, len(syms), 200):
        fetch_bars(syms[i : i + 200])
        print(f"  [L] bars {min(i + 200, len(syms))}/{len(syms)} (invalid {len(invalid)})", flush=True)
    L = [t for t in syms if price.get(t, 0) >= PRICE_FLOOR and adv.get(t, 0) >= ADV_FLOOR]
    print(f"[L] price ≥ ${PRICE_FLOOR:g} ∧ ADV ≥ ${ADV_FLOOR / 1e6:g}M: {len(L)}", flush=True)

    # ── Qn: raise-aware trailing-90d news ≤ cut, with the IPO guard ──
    news = NewsData(cache_rw, client=client, fetch_start=as_of - timedelta(days=480), fetch_end=as_of)
    rows_out: dict[str, dict[str, Any]] = {}
    Qn = []
    for j, s in enumerate(L):
        try:
            recs = news.headlines_asof(s, as_of)
        except Exception:  # noqa: BLE001
            recs = []
        ts = []
        for r in recs:
            try:
                ts.append(datetime.fromisoformat(r["ts"]))
            except Exception:  # noqa: BLE001
                continue
        naive90 = sum(1 for t in ts if t >= cutoff90)
        score, ipo_confound = naive90, False
        lf = fmap[s].get("last_filed") or ""
        try:
            fdt = datetime.fromisoformat(lf).replace(tzinfo=UTC) if lf else None
        except Exception:  # noqa: BLE001
            fdt = None
        if fdt is not None and (as_of - fdt).days <= NEWS_WINDOW:
            fb = first_bar.get(s)
            if fb is not None and fb < fdt - timedelta(days=7):       # public BEFORE the filing → trust baseline
                hi = fdt - timedelta(days=7)
                lo = hi - timedelta(days=NEWS_WINDOW)
                score = sum(1 for t in ts if lo <= t < hi)
            else:                                                     # not public pre-filing → IPO false-quiet guard
                ipo_confound = True                                   # keep naive90 (current narration)
        rows_out[s] = {"ticker": s, "company": fmap[s].get("company"), "naive90": naive90,
                       "raise_aware": score, "ipo_confound": ipo_confound, "last_filed": lf,
                       "price": round(price.get(s, 0), 2), "adv_usd_m": round(adv.get(s, 0) / 1e6, 1)}
        if score <= QUIET_NEWS_CUT:
            Qn.append(s)
        if (j + 1) % 50 == 0:
            print(f"  [Qn] news {j + 1}/{len(L)}", flush=True)
    print(f"[Qn] raise-aware 90d news ≤ {QUIET_NEWS_CUT} (IPO-guarded): {len(Qn)}", flush=True)

    # ── Q: §11 admission (OPRA structure ∧ eligible ∧ fits 1 contract ≤ per-name cap) on Qn ──
    prov = AlpacaChainProvider(client, equity_feed=eq_feed, option_feed=to_option_feed("opra"))

    def _elig(c):
        return contract_eligible(c, max_spread_pct=float(elig_c.get("max_bid_ask_pct", 0.25)),
                                 min_contract_price=0.10, max_contract_price=100.0,
                                 min_oi=elig_c.get("min_option_open_interest"))

    Q = []
    today = as_of.date()
    for k, s in enumerate(Qn):
        rec = rows_out[s]
        try:
            spot = prov.underlying_price(s)
            if not spot:
                rec["admit"] = "no_spot"
            else:
                st, why = select_structure(prov.chain(s), direction="bullish", as_of=today,
                                           underlying_price=spot, tenor_min_days=int(gate["tenor_min_days"]),
                                           tenor_max_days=int(gate["tenor_max_days"]),
                                           target_moneyness=float(gate["target_moneyness"]), eligibility=_elig)
                if st is None:
                    rec["admit"] = f"no_structure:{why[0] if why else '?'}"
                else:
                    sizing = convexity_position_size(
                        account_equity=EQ, book_fraction=float(book["book_fraction"]),
                        per_name_fraction=float(book["per_name_fraction"]),
                        max_open_positions=int(book["max_open_positions"]),
                        open_positions_count=0, open_premium_total=0.0,
                        entry_premium_per_share=st.entry_premium)
                    rec.update({"per_contract": round(st.entry_premium * 100, 0),
                                "achieved_otm_pct": round(st.moneyness * 100, 1)})
                    if sizing.contracts >= 1:
                        rec["admit"] = "ADMIT"
                        Q.append(s)
                    else:
                        rec["admit"] = f"over_cap(>{PER_NAME:.0f})"
        except Exception as e:  # noqa: BLE001
            rec["admit"] = f"err:{e}"
        print(f"  [Q] opra {k + 1}/{len(Qn)} {s}: {rec.get('admit')}", flush=True)

    # ── Stage-2a: SIC sector geometry on Q (≥1 sector with ≥3 = basket-able) ──
    sic_counts: dict[str, int] = {}
    for s in Q:
        sic, desc = _sic_for(edgar, ua, s)
        rows_out[s]["sic"] = sic
        rows_out[s]["sic_desc"] = desc
        if sic:
            sic_counts[f"{sic} {desc}"] = sic_counts.get(f"{sic} {desc}", 0) + 1
        time.sleep(0.15)
    max_sector = max(sic_counts.values()) if sic_counts else 0

    out = {
        "as_of": as_of.isoformat(), "tag": args.tag,
        "thresholds": {"price_floor": PRICE_FLOOR, "adv_floor_usd": ADV_FLOOR, "per_name_cap": PER_NAME,
                       "quiet_cut": QUIET_NEWS_CUT, "tenor": [gate["tenor_min_days"], gate["tenor_max_days"]]},
        "funnel": {"P_resolvable": len(all_tk), "P_common": len(syms), "invalid_symbols": len(invalid),
                   "L": len(L), "Qn": len(Qn), "Q": len(Q)},
        "stage2a_sic": {"max_sector_count": max_sector, "basket_able": max_sector >= 3, "by_sector": sic_counts},
        "Q_admitted": [rows_out[s] for s in sorted(Q)],
        "Qn_detail": {s: rows_out[s] for s in Qn},
    }
    out_path = Path("records") / f"{as_of.date().isoformat()}_corpus_reach_measure_{args.tag}.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n=== FUNNEL  P={len(syms)} → L={len(L)} → Qn={len(Qn)} → Q={len(Q)} ===")
    print(f"  Stage-2a SIC: max sector count {max_sector} → basket-able={max_sector >= 3} ({sic_counts})")
    print(f"  Q (quiet ∧ §11-admissible): {sorted(Q)}")
    print(f"  wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
