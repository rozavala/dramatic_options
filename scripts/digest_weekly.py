#!/usr/bin/env python3
"""Weekly reach-digest runner — OFFLINE OPERATOR TOOL (run by hand, never by systemd).

Governing spec: ``records/2026-07-14_reach_channels_charter_DRAFT.md`` (§3, the digest).
Assembles the three reach channels (trade_press RSS · Federal Register agency pulls ·
the post-IPO orphan watch) into ONE chronological, source-grouped markdown file under
``records/digests/<YYYY>-W<ww>.md``. No ranking anywhere; overflow is per-source
chronological truncation (charter §3).

Fail-soft throughout: a dead feed / dead channel is COUNTED and printed, never kills the
digest (dead-arm vs quiet-arm). Exit 0 on partial failure; exit 1 only if EVERY attempted
channel produced nothing AND at least one error occurred.

Run (from the repo root):
    python scripts/digest_weekly.py [--feeds digest_feeds.json] [--out records/digests]
                                    [--skip-orphan] [--dry-run]

``--skip-orphan`` is the keyless mode (no Alpaca creds / EDGAR UA needed). The orphan
channel reads Alpaca creds via the existing ``config_loader.load_config()`` +
``require_alpaca_credentials`` pattern and the EDGAR contact UA from
``config.edgar.user_agent`` — never ``os.environ`` directly. ``--dry-run`` prints the
digest instead of writing it and does NOT update the orphan snapshot (a dry run must not
consume first-seen events).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:  # `python scripts/digest_weekly.py` puts scripts/ first
    sys.path.insert(0, str(_ROOT))

from digest import (  # noqa: E402
    ORPHAN_SNAPSHOT_PATH,
    Item,
    assemble,
    federal_register_items,
    fetch_rss,
    iso_week_stamp,
    last_closed_quarter_end,
    load_snapshot,
    months_ago,
    options_class_exists,
    orphan_cohort,
    orphan_new_listings,
    save_snapshot,
    sec_ticker_map,
)


def _cutoff_keep(items: list[Item], cutoff: datetime) -> list[Item]:
    """Drop dated items older than the lookback window; undated items are kept
    (missing dates are tolerated, never a reason to drop — that would be filtering)."""
    return [i for i in items if i.published is None or i.published >= cutoff]


def _one_source(
    label: str, fetch, *, errors: list[str], summary: list[str]
) -> list[Item]:
    """Per-SOURCE fail-soft: fetchers count their own failures into ``errors``; anything
    that still raises (a bug, a bad config entry) is caught here so one dead source never
    kills the digest. Every source gets a fetched/FAILED summary line — a dead arm is
    counted and printed, never mistaken for a quiet one."""
    before = len(errors)
    try:
        got = fetch()
    except Exception as e:  # noqa: BLE001 — the fail-soft boundary is the point
        errors.append(f"{label}: {type(e).__name__}: {e}")
        got = []
    if len(errors) > before:
        summary.append(f"{label}: FAILED ({errors[-1]})")
    else:
        summary.append(f"{label}: {len(got)} item(s)")
    return got


def run_trade_press(
    feeds: list[dict[str, str]], *, cutoff: datetime, errors: list[str], summary: list[str]
) -> list[Item]:
    out: list[Item] = []
    for feed in feeds:
        source, url = str(feed["source"]), str(feed["url"])
        out += _one_source(
            f"trade_press/{source}",
            lambda url=url, source=source: _cutoff_keep(
                fetch_rss(url, source=source, channel="trade_press", errors=errors), cutoff
            ),
            errors=errors,
            summary=summary,
        )
    return out


def run_agency(
    agency_cfg: dict[str, Any],
    *,
    lookback_days: int,
    cutoff: datetime,
    errors: list[str],
    summary: list[str],
) -> list[Item]:
    out: list[Item] = []
    for slug in agency_cfg.get("federal_register_agencies", []):
        out += _one_source(
            f"agency/federal_register/{slug}",
            lambda slug=slug: federal_register_items([slug], days=lookback_days, errors=errors),
            errors=errors,
            summary=summary,
        )
    for feed in agency_cfg.get("rss", []):
        source, url = str(feed["source"]), str(feed["url"])
        out += _one_source(
            f"agency/{source}",
            lambda url=url, source=source: _cutoff_keep(
                fetch_rss(url, source=source, channel="agency", errors=errors), cutoff
            ),
            errors=errors,
            summary=summary,
        )
    return out


def run_orphan(
    orphan_cfg: dict[str, Any],
    *,
    now: datetime,
    notes: list[str],
    errors: list[str],
    summary: list[str],
) -> tuple[list[Item], dict[str, str]]:
    """The 424B4 orphan watch (charter §3: IPO-age × options-class-existence ONLY).

    Deferred imports: this is the only path that needs alpaca-py / requests / the
    EDGAR contact UA — the keyless ``--skip-orphan`` mode never touches them."""
    from alpaca.trading.client import TradingClient

    from config_loader import ConfigError, load_config, require_alpaca_credentials
    from data.cache import PointInTimeCache
    from data.edgar_index import EdgarIndex
    from data.filings import EdgarClient

    config = load_config()
    api_key, secret_key = require_alpaca_credentials(config)
    user_agent = (config.get("edgar") or {}).get("user_agent")
    if not user_agent:
        raise ConfigError(
            "EDGAR user agent missing. Set EDGAR_USER_AGENT in .env "
            "(config.edgar.user_agent) — required for the orphan-watch channel."
        )

    # 424B4 IPO cohort from CLOSED quarters in [now-24mo, now-12mo] — EdgarIndex in its
    # sanctioned HISTORICAL role. Its own PIT namespace (digest_orphan) so the digest
    # never shares/collides with the FSSD enumeration; raw quarterly form.idx files are
    # reused from data/cache/full_index_raw (network-free on reruns).
    start = months_ago(now, int(orphan_cfg.get("ipo_age_months_max", 24)))
    end = min(months_ago(now, int(orphan_cfg.get("ipo_age_months_min", 12))),
              last_closed_quarter_end(now))
    index = EdgarIndex(
        PointInTimeCache("data/cache"),
        edgar=EdgarClient(user_agent),
        form="424B4",
        source="digest_orphan",
    )
    cohort = orphan_cohort(
        index,
        start=start,
        end=end,
        limit=int(orphan_cfg.get("cohort_limit", 40)),
        ticker_map=sec_ticker_map(user_agent),
        notes=notes,
    )

    trading = TradingClient(api_key, secret_key, paper=bool(config["alpaca"]["paper"]))
    snapshot = load_snapshot(ORPHAN_SNAPSHOT_PATH)
    items, updated = orphan_new_listings(
        cohort,
        snapshot,
        lambda symbol: options_class_exists(trading, symbol),
        now=now,
        errors=errors,
    )
    summary.append(
        f"orphan_watch: cohort {len(cohort)} (424B4 {start.date()}..{end.date()}), "
        f"{len(items)} newly-listed options class(es)"
    )
    return items, updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--feeds", default="digest_feeds.json", help="feeds config path")
    parser.add_argument("--out", default="records/digests", help="output directory")
    parser.add_argument(
        "--skip-orphan", action="store_true", help="skip the Alpaca/EDGAR channel (keyless mode)"
    )
    parser.add_argument("--dry-run", action="store_true", help="print instead of writing")
    args = parser.parse_args(argv)

    feeds_cfg = json.loads(Path(args.feeds).read_text())
    lookback_days = int(feeds_cfg.get("lookback_days", 8))
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=lookback_days)

    errors: list[str] = []
    notes: list[str] = []
    summary: list[str] = []
    items: list[Item] = []
    orphan_snapshot: dict[str, str] | None = None

    # Per-channel fail-soft: a raising channel is counted and the digest still ships.
    try:
        items += run_trade_press(
            feeds_cfg.get("trade_press", []), cutoff=cutoff, errors=errors, summary=summary
        )
    except Exception as e:  # noqa: BLE001 — the fail-soft boundary is the point
        errors.append(f"trade_press: {type(e).__name__}: {e}")
        summary.append(f"trade_press: CHANNEL FAILED ({errors[-1]})")
    try:
        items += run_agency(
            feeds_cfg.get("agency", {}),
            lookback_days=lookback_days,
            cutoff=cutoff,
            errors=errors,
            summary=summary,
        )
    except Exception as e:  # noqa: BLE001
        errors.append(f"agency: {type(e).__name__}: {e}")
        summary.append(f"agency: CHANNEL FAILED ({errors[-1]})")
    if args.skip_orphan:
        notes.append("orphan_watch: skipped (--skip-orphan) — not quiet, not run")
        summary.append("orphan_watch: skipped (--skip-orphan)")
    else:
        try:
            orphan_items, orphan_snapshot = run_orphan(
                feeds_cfg.get("orphan_watch", {}),
                now=now,
                notes=notes,
                errors=errors,
                summary=summary,
            )
            items += orphan_items
        except Exception as e:  # noqa: BLE001
            errors.append(f"orphan_watch: {type(e).__name__}: {e}")
            summary.append(f"orphan_watch: CHANNEL FAILED ({errors[-1]})")

    week = iso_week_stamp(now)
    document = assemble(
        items,
        caps=feeds_cfg.get("caps", {}),
        week=week,
        dropped_notes=notes + [f"FAILED — {e}" for e in errors],
        generated_at=now,
    )

    for line in summary:
        print(f"[digest] {line}")
    if args.dry_run:
        print(f"[digest] dry-run: not writing {week}.md, not updating the orphan snapshot")
        print(document)
    else:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{week}.md"
        out_path.write_text(document)
        if orphan_snapshot is not None:
            save_snapshot(orphan_snapshot, ORPHAN_SNAPSHOT_PATH)
        print(f"[digest] wrote {out_path} ({len(items)} item(s), {len(errors)} error(s))")

    if not items and errors:
        print("[digest] every channel produced nothing and at least one error occurred → exit 1")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
