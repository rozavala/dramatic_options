#!/usr/bin/env python3
"""Survivor-card runner, STAGE A — OFFLINE OPERATOR TOOL (run by hand, never by systemd).

Governing spec: ``records/2026-07-14_reach_channels_charter_RATIFIED.md`` §3b. Consumes a
written weekly digest (``records/digests/<YYYY>-W<ww>.md`` — the artifact of record; see
``survivor_cards.parse_digest_markdown`` for why the document, not a re-fetch, is the input
seam), extracts tickers conservatively, drops restricted names (fail-CLOSED on a broken
``restricted.json``), runs the four-axis deterministic feasibility screen, pulls the
mechanical premise-currency numbers for survivors, and writes the card document to
``records/cards/<YYYY>-W<ww>.md``. Stage A only — NO LLM calls anywhere; the drafting layer
is Stage B behind ``survivor_cards.draft_thesis_section``.

Run (from the repo root):
    python scripts/survivor_cards_run.py [--digest records/digests/2026-W29.md]
        [--out records/cards] [--restricted restricted.json] [--skip-market] [--dry-run]

``--skip-market`` is the keyless mode (no Alpaca creds): every screen axis is marked
UNAVAILABLE — never passed. Market mode reads Alpaca creds via the existing
``config_loader.load_config()`` + ``require_alpaca_credentials`` pattern and the EDGAR
contact UA from ``config.edgar.user_agent`` (never ``os.environ`` directly), mirroring
``scripts/digest_weekly.py``. Premise-currency filings/analyst reads are CACHE-ONLY (the
PIT cache — no EDGAR/stockanalysis fetches; a cold cache renders "n/a", staleness-honest).

Exit codes: 0 = document produced (fail-soft per candidate, errors counted into the doc);
2 = restricted-list HALT (fail-closed); 1 = no usable digest input.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:  # `python scripts/survivor_cards_run.py` puts scripts/ first
    sys.path.insert(0, str(_ROOT))

import survivor_cards as sc  # noqa: E402
from digest import DIGEST_CACHE_DIR, iso_week_stamp  # noqa: E402

_WEEK_STEM_RE = re.compile(r"^\d{4}-W\d{2}$")


def _find_digest(arg: str | None, digests_dir: Path) -> Path | None:
    """The digest to consume: an explicit ``--digest`` path, else the newest week file."""
    if arg:
        p = Path(arg)
        return p if p.exists() else None
    if not digests_dir.is_dir():
        return None
    weeks = sorted(digests_dir.glob("*-W*.md"))
    return weeks[-1] if weeks else None


def _build_market(config: dict) -> sc.MarketAccess:
    """Live MarketAccess over the existing providers (deferred imports — the keyless
    ``--skip-market`` path never touches alpaca). Mirrors ``probe_basket_feasibility``:
    OPRA for the chain read (real quotes = real tradability), config equity feed for bars."""
    from datetime import timedelta

    from alpaca.trading.client import TradingClient

    from config_loader import require_alpaca_credentials
    from convexity_data import AlpacaChainProvider
    from data.alpaca_client import AlpacaClient
    from digest import options_class_exists
    from feeds import to_equity_feed, to_option_feed

    api_key, secret_key = require_alpaca_credentials(config)
    equity_feed = to_equity_feed(config["data_feed"]["equity_bars"])
    client = AlpacaClient(api_key, secret_key, paper=True)
    provider = AlpacaChainProvider(client, equity_feed=equity_feed,
                                   option_feed=to_option_feed("opra"))
    trading = TradingClient(api_key, secret_key, paper=bool(config["alpaca"]["paper"]))
    elig = config.get("eligibility", {}).get("live", {})
    adv_window = int(elig.get("adv_window_days", 20))

    def adv_usd(symbol: str) -> float | None:
        # Trailing average $ volume from bars (the probe_basket_feasibility basis).
        start = datetime.now(UTC) - timedelta(days=adv_window * 2 + 10)
        bars = client.get_stock_bars(symbol, start=start, feed=equity_feed)
        rows = (getattr(bars, "data", {}) or {}).get(symbol, [])
        rows = [b for b in rows if getattr(b, "close", None) and getattr(b, "volume", None)]
        if not rows:
            return None
        rows = rows[-adv_window:]
        return sum(float(b.close) * float(b.volume) for b in rows) / len(rows)

    return sc.MarketAccess(
        spot=provider.underlying_price,
        closes=lambda symbol, window: provider.closes(symbol, window=window),
        adv_usd=adv_usd,
        optionable=lambda symbol: options_class_exists(trading, symbol),
        chain=provider.chain,
    )


def _cached_records(cache, source: str, symbol: str, now: datetime) -> list[dict] | None:
    """CACHE-ONLY read of a PIT source (``read_between`` — no coverage-high-water raise, no
    fetch). ``None`` = nothing cached (rendered n/a, never a zero)."""
    try:
        records = cache.read_between(source, symbol.upper(), None, now)
        return records or None
    except Exception:  # noqa: BLE001 — a cache miss is honest n/a, never an error
        return None


def _premise_for(symbol: str, market: sc.MarketAccess | None, cache, event_forms,
                 now: datetime, errors: list[str]) -> sc.PremiseCurrency:
    closes: list[float] | None = None
    if market is not None:
        try:
            closes = market.closes(symbol, 260)  # ≥253 trading days → the 12m leg
        except Exception as e:  # noqa: BLE001 — fail-soft, counted
            errors.append(f"{symbol}/premise-closes: {type(e).__name__}: {e}")
    filings = _cached_records(cache, "filings", symbol, now) if cache is not None else None
    analyst = None
    if cache is not None:
        recs = _cached_records(cache, "analyst_coverage", symbol, now)
        analyst = recs[-1] if recs else None
    return sc.build_premise(closes, filings, analyst, event_forms)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--digest", help="digest markdown to consume "
                                         "(default: newest records/digests/*-W*.md)")
    parser.add_argument("--digests-dir", default="records/digests",
                        help="where weekly digests live (default-digest discovery)")
    parser.add_argument("--out", default="records/cards", help="output directory")
    parser.add_argument("--restricted", default="restricted.json",
                        help="restricted-list path (repo root; fail-CLOSED if malformed)")
    parser.add_argument("--ticker-cache",
                        default=str(DIGEST_CACHE_DIR / "company_tickers.json"),
                        help="cached SEC company_tickers.json (the digest's cache file)")
    parser.add_argument("--skip-market", action="store_true",
                        help="keyless mode: screen axes marked UNAVAILABLE, not passed")
    parser.add_argument("--dry-run", action="store_true", help="print instead of writing")
    args = parser.parse_args(argv)

    now = datetime.now(UTC)
    errors: list[str] = []
    notes: list[str] = []

    # ── digest input ──────────────────────────────────────────────────────────
    digest_path = _find_digest(args.digest, Path(args.digests_dir))
    if digest_path is None:
        print("[cards] no digest found (pass --digest or run scripts/digest_weekly.py first)")
        return 1
    items = sc.parse_digest_markdown(digest_path.read_text())
    week = digest_path.stem if _WEEK_STEM_RE.match(digest_path.stem) else iso_week_stamp(now)
    print(f"[cards] digest {digest_path} ({len(items)} item(s), week {week})")

    # ── restricted list: fail-CLOSED before anything else ─────────────────────
    try:
        restricted, restricted_note = sc.load_restricted(args.restricted)
    except sc.RestrictedListError as e:
        print(f"[cards] HALT: {e}")
        return 2
    if restricted is None:
        notes.append(restricted_note)  # the absent-file WARNING rides the card doc too
    print(f"[cards] {restricted_note}")

    # ── known-universe set (cache-first; fetched only in market mode) ─────────
    known = sc.load_known_tickers(args.ticker_cache)
    config: dict | None = None
    if not args.skip_market:
        from config_loader import load_config

        config = load_config()
        if known is None:
            ua = (config.get("edgar") or {}).get("user_agent")
            if ua:
                try:
                    from digest import sec_ticker_map

                    known = frozenset(sec_ticker_map(ua, cache_dir=Path(args.ticker_cache).parent)
                                      .values())
                except Exception as e:  # noqa: BLE001 — degrade to no-exact-match, counted
                    errors.append(f"known-universe: {type(e).__name__}: {e}")
    if known is None:
        notes.append("known-universe set unavailable — exact-match extraction pass SKIPPED "
                     "(cashtag/exchange/orphan patterns only)")

    # ── extraction (conservative, provenance-carrying) ────────────────────────
    candidates = sc.extract_candidates(items, known)
    n_extracted = len(candidates)
    candidates, n_restricted_dropped = sc.apply_restricted(candidates, restricted)
    print(f"[cards] extracted {n_extracted} candidate(s); "
          f"{n_restricted_dropped} restricted drop(s)")

    # ── screen + premise pulls ────────────────────────────────────────────────
    market: sc.MarketAccess | None = None
    cache = None
    params = sc.ScreenParams()
    event_forms = sc.allowed_forms(["424B5", "S-1", "S-3", "F-1", "F-3", "F-10", "SUPPL",
                                    "SC 13D", "SCHEDULE 13D"])
    if not args.skip_market and config is not None:
        params = sc.params_from_config(config)
        ev_forms = ((config.get("discovery") or {}).get("events") or {}).get("forms")
        if ev_forms:
            event_forms = sc.allowed_forms(ev_forms)
        try:
            market = _build_market(config)
        except Exception as e:  # noqa: BLE001 — a dead market arm is counted, run degrades
            errors.append(f"market-access: {type(e).__name__}: {e}")
            notes.append("market access FAILED — all screen axes UNAVAILABLE this run")
        try:
            from data.cache import PointInTimeCache

            cache = PointInTimeCache(config.get("cache", {}).get("dir", "data/cache"))
        except Exception as e:  # noqa: BLE001
            errors.append(f"pit-cache: {type(e).__name__}: {e}")
    else:
        notes.append("--skip-market: screen axes UNAVAILABLE (not passed); "
                     "premise pulls skipped")

    quotes_live = sc.quotes_are_live(now)
    survivors: list[sc.SurvivorCard] = []
    screened_out: list[sc.ScreenResult] = []
    for symbol in sorted(candidates):
        result = sc.run_screen(symbol, market=market, params=params, as_of=now.date(),
                               quotes_live=quotes_live, errors=errors)
        if result.passed:
            premise = _premise_for(symbol, market, cache, event_forms, now, errors)
            survivors.append(sc.SurvivorCard(
                symbol=symbol, surfaced_via=tuple(candidates[symbol]),
                screen=result, premise=premise))
        else:
            screened_out.append(result)
        print(f"[cards] {symbol}: "
              + " ".join(f"{a.axis}={a.status}" for a in result.axes))

    # ── assembly + output ─────────────────────────────────────────────────────
    document = sc.assemble_cards(
        survivors, screened_out, week=week, digest_path=str(digest_path),
        restricted_note=restricted_note, n_extracted=n_extracted,
        n_restricted_dropped=n_restricted_dropped, quotes_live=quotes_live,
        notes=notes, errors=errors, generated_at=now,
    )
    print(f"[cards] {len(survivors)} survivor(s), {len(screened_out)} screened out, "
          f"{len(errors)} error(s)")
    if args.dry_run:
        print(f"[cards] dry-run: not writing {week}.md")
        print(document)
    else:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{week}.md"
        out_path.write_text(document)
        print(f"[cards] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
