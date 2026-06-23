#!/usr/bin/env python3
"""Phase-0 corpus-reach diagnostic — the "quieter-corpus lever" measure-first step.

READ-ONLY · NO-LLM · NO-FETCH. Measures what entities the Stage-0 corpus surfaces per source over the
warm point-in-time cache, splits them **universe (narrated) vs non-universe**, and reports a §2-clean
name-level narratedness proxy (trailing-90d news count, computed the council's way — uncapped, NEVER
``coverage_count``) where the news cache is resident. It writes ONE analysis artifact to ``records/``
and reads nothing live.

Why it is compliant (PREREG_THEME_GENERATOR §5/§6):
- **§2-clean:** this is ANALYSIS *over* the corpus — news is never fed back as a corpus INPUT — and it
  lives OUTSIDE ``corpus/`` so it is off the package §2 AST import guard.
- **§5-exempt:** no generator LLM is invoked → no thesis / ``dropped_*`` count → it cannot un-blind the
  §10 yield band (the explicit Phase-0 exemption).
- **anti-HARK:** the low-news "quiet" cut is DESCRIPTIVE; nothing here is wired into a probe / verifier /
  council threshold. News is used to DESCRIBE corpus reach, never to gate a thesis.
- **NO-FETCH:** the PIT cache is opened ``offline=True`` (a read it cannot satisfy RAISES, never
  fetches); ``NewsData`` is built with ``client=None`` (``_ensure`` is a no-op); ``EdgarClient`` only
  reads the cached ``company_tickers.json``. No router is imported.

Output: ``records/<as_of-date>_corpus_reach_diagnostic.json`` + a stdout summary table.

Run (from the repo root):  ``python -m scripts.corpus_reach_diagnostic``
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# EdgarClient needs a contact UA to construct; the ticker→CIK read is OFFLINE (cached
# company_tickers.json), so a placeholder is fine and triggers no fetch.
os.environ.setdefault("EDGAR_USER_AGENT", "dramatic-options-diagnostic dev@example.com")

from config_loader import load_config  # noqa: E402
from corpus.assemble import assemble_corpus  # noqa: E402
from corpus.bls_series import SOURCE as BLS_SOURCE  # noqa: E402
from corpus.capital_raises import SOURCE as CAP_SOURCE  # noqa: E402
from corpus.content import all_basket_symbols, load_content, read_coords  # noqa: E402
from corpus.customer_concentration import SOURCE as CC_SOURCE  # noqa: E402
from corpus.eia_series import SOURCE as EIA_SOURCE  # noqa: E402
from corpus.etf_constituents import SOURCE as ETF_SOURCE  # noqa: E402
from corpus.federal_awards import SOURCE as AWARDS_SOURCE  # noqa: E402
from corpus.nrc_dockets import SOURCE as NRC_SOURCE  # noqa: E402
from data.cache import PointInTimeCache  # noqa: E402
from data.filings import EdgarClient  # noqa: E402
from data.news import NewsData  # noqa: E402

NEWS_WINDOW_DAYS = 90
QUIET_NEWS_CUT = 3          # descriptive only: trailing-90d articles ≤ this ⇒ "structurally quiet"
SAMPLE_PER_SOURCE = 40      # entities sampled into the JSON artifact (counts are always full)

ENTITY_FREE = {BLS_SOURCE, EIA_SOURCE, NRC_SOURCE}   # macro series / fleet — no tradeable entity
SYMBOL_KEYED = {CC_SOURCE, ETF_SOURCE}               # the coord key / a record field IS the entity


def _norm_name(s: Any) -> str:
    return " ".join(str(s or "").upper().split())


def _entities_for(source: str, records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-source typed-entity extraction (NOT the flat _identity_tokens union — we want clean
    symbol/cik/recipient identifiers). Returns {entity_id: {symbol, cik, name, n_records}}.

    The coord-key handling is the plan's P2-#3 fix: the coord key is the ENTITY only for symbol-keyed
    sources (CC); for capital_raises (key=form) / federal_awards (key=hash) the key is NOT an entity.
    """
    ents: dict[str, dict[str, Any]] = {}

    def _add(key: str, *, symbol: str | None = None, cik: str | None = None, name: str | None = None):
        if not key:
            return
        e = ents.setdefault(key, {"symbol": symbol, "cik": cik, "name": name, "n_records": 0})
        e["n_records"] += 1
        # fill any identifier we learn later
        for f, v in (("symbol", symbol), ("cik", cik), ("name", name)):
            if v and not e.get(f):
                e[f] = v

    for r in records:
        if source == CAP_SOURCE:                       # {ts, cik, company, ...} — key=form (stripped)
            cik = str(r.get("cik") or "").strip() or None
            if cik:
                _add(cik, cik=cik, name=r.get("company"))
        elif source == CC_SOURCE:                      # coord key = symbol (the entity)
            sym = str(r.get("_coord_key") or r.get("symbol") or "").upper().strip() or None
            if sym:
                _add(sym, symbol=sym, cik=str(r.get("cik") or "").strip() or None)
        elif source == ETF_SOURCE:                     # each record is a holding; entity = its symbol
            sym = str(r.get("symbol") or "").upper().strip() or None
            nm = r.get("name")
            key = sym or _norm_name(nm)
            if key:
                _add(key, symbol=sym, name=nm)
        elif source == AWARDS_SOURCE:                  # free-text recipient; key=hash (stripped)
            nm = _norm_name(r.get("recipient"))
            if nm:
                _add(nm, name=r.get("recipient"))
    return ents


def main() -> int:
    config = load_config()
    content = load_content()
    cache_dir = config.get("cache_dir", "data/cache")
    as_of = datetime.now(UTC)
    cutoff = as_of - timedelta(days=NEWS_WINDOW_DAYS)

    cache = PointInTimeCache(cache_dir, offline=True)            # NO-FETCH (a stray read RAISES)
    universe = set(all_basket_symbols(config))

    # ── curated → CIK map (previews lever #1's frozen map + its coverage/staleness read) ──
    edgar = EdgarClient(os.environ["EDGAR_USER_AGENT"], cache_dir=cache_dir)
    cik_map: dict[str, str | None] = {}
    for t in sorted(universe):
        try:
            cik_map[t] = edgar.ticker_to_cik(t)                 # offline read of cached ticker map
        except Exception:                                       # noqa: BLE001
            cik_map[t] = None
    curated_ciks = {c for c in cik_map.values() if c}
    unresolved = sorted(t for t, c in cik_map.items() if not c)
    # cik → ticker inverse (for capital_raises news lookup); offline, from the cached map
    try:
        tmap = edgar._load_ticker_map()                         # {ticker: cik}
        cik2tk = {cik: tk for tk, cik in tmap.items()}
    except Exception:                                           # noqa: BLE001
        cik2tk = {}

    # ── news_90d (NO-FETCH; cache-resident symbols only; uncapped; the council's 90d axis) ──
    news = NewsData(cache, client=None, fetch_start=as_of - timedelta(days=400), fetch_end=as_of)

    def news_90d(symbol: str | None) -> int | None:
        if not symbol:
            return None
        try:
            recs = news.headlines_asof(symbol.upper(), as_of)   # raises in offline mode if uncached
        except Exception:                                       # noqa: BLE001 — uncached ⇒ unknown
            return None
        n = 0
        for r in recs:
            try:
                if datetime.fromisoformat(r["ts"]) >= cutoff:
                    n += 1
            except Exception:                                   # noqa: BLE001
                continue
        return n

    # ── assemble the corpus union (read-only) ──
    coords = read_coords(content, config)
    corpus = assemble_corpus(cache, as_of, coords, tag_key=True)

    per_source: dict[str, Any] = {}
    for source in sorted(corpus):
        records = corpus[source]
        if source in ENTITY_FREE:
            per_source[source] = {"class": "entity_free_macro", "n_records": len(records),
                                  "n_coords": len({r.get("_coord_key") for r in records})}
            continue

        ents = _entities_for(source, records)
        rows: list[dict[str, Any]] = []
        n_in = n_non = n_unknown = 0
        for eid, e in ents.items():
            sym, cik = e.get("symbol"), e.get("cik")
            # in_universe by the TYPED key available for this source-class
            if sym:
                in_uni: bool | None = sym.upper() in universe
            elif cik:
                in_uni = cik in curated_ciks
            else:
                in_uni = None                                   # free-text recipient: not deterministic
            # a symbol for news: the entity's own, else cik→ticker inverse (capital_raises)
            news_sym = sym or (cik2tk.get(cik) if cik else None)
            n90 = news_90d(news_sym)
            rows.append({"id": eid, "symbol": sym, "cik": cik, "name": e.get("name"),
                         "in_universe": in_uni, "news_sym": news_sym, "news_90d": n90,
                         "n_records": e["n_records"]})
            if in_uni is True:
                n_in += 1
            elif in_uni is False:
                n_non += 1
            else:
                n_unknown += 1

        nonuni = [r for r in rows if r["in_universe"] is False]
        nonuni_news = [r for r in nonuni if r["news_90d"] is not None]
        quiet = [r for r in nonuni_news if r["news_90d"] <= QUIET_NEWS_CUT]
        block: dict[str, Any] = {
            "class": "symbol_keyed" if source in SYMBOL_KEYED else (
                "free_text_recipient" if source == AWARDS_SOURCE else "cik_bearing"),
            "n_records": len(records), "n_entities": len(ents),
            "n_in_universe": n_in, "n_nonuniverse": n_non, "n_unknown": n_unknown,
            "nonuniverse_with_news": len(nonuni_news),
            "nonuniverse_quiet": len(quiet),                    # news_90d ≤ QUIET_NEWS_CUT (descriptive)
            "quiet_examples": sorted(r["id"] for r in quiet)[:25],
        }
        if source == AWARDS_SOURCE:
            top = Counter({r["id"]: r["n_records"] for r in rows}).most_common(12)
            block["top_recipients_by_record_count"] = top
        block["sample"] = sorted(rows, key=lambda r: (-r["n_records"], r["id"]))[:SAMPLE_PER_SOURCE]
        per_source[source] = block

    report: dict[str, Any] = {
        "as_of": as_of.isoformat(),
        "cache_dir": cache_dir,
        "no_fetch": True, "no_llm": True,
        "news_window_days": NEWS_WINDOW_DAYS, "quiet_news_cut": QUIET_NEWS_CUT,
        "universe": {"n": len(universe), "symbols": sorted(universe)},
        "curated_cik_map": {
            "n_resolved": len(curated_ciks), "n_universe": len(universe),
            "unresolved_no_us_cik": unresolved,                 # lever-#1 coverage/staleness preview
            "map": cik_map,
        },
        "per_source": per_source,
    }

    out_dir = Path("records")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{as_of.date().isoformat()}_corpus_reach_diagnostic.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=False))

    # ── stdout summary ──
    print(f"\nCorpus-reach diagnostic — as_of {as_of.date()}  (NO-FETCH, NO-LLM)\n")
    print(f"  universe: {len(universe)} names · curated→CIK resolved {len(curated_ciks)}/{len(universe)}"
          f"  unresolved(no-US-CIK): {', '.join(unresolved) or '—'}\n")
    hdr = f"  {'source':<32} {'class':<19} {'recs':>6} {'ents':>6} {'in_uni':>7} {'non_uni':>8} {'unk':>5} {'quiet':>6}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for source in sorted(per_source):
        b = per_source[source]
        if b.get("class") == "entity_free_macro":
            print(f"  {source:<32} {'entity_free_macro':<19} {b['n_records']:>6} {'—':>6} {'—':>7} {'—':>8} {'—':>5} {'—':>6}")
        else:
            print(f"  {source:<32} {b['class']:<19} {b['n_records']:>6} {b['n_entities']:>6} "
                  f"{b['n_in_universe']:>7} {b['n_nonuniverse']:>8} {b['n_unknown']:>5} {b['nonuniverse_quiet']:>6}")
    print(f"\n  wrote {out_path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
