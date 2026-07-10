"""The §6 paired-contrast probe — forward-catalyst channel PR3 (ephemeral, live router).

For each hand-seed symbol carrying pinned forward-catalyst items, run the council TWICE:
the CHANNEL arm (block rendered) and the NO-CHANNEL arm (block withheld, all else identical —
same as_of, same news/fundamentals/analyst, same models, same seeded for/against order), then
apply the §8 detectors and append the pair to ``records/forward_catalyst_pairs.csv`` (the
durable M-sample ledger — ephemeral probes COUNT toward M per §6, so the accounting must
outlive the session; the disposition read at M=8 stays the operator's).

NO live-record: nothing touches the journal DB — proposals stay in memory; the only write is
the CSV append (pass --dry-run to skip even that). Kill-before-spend honored. §7: the pair is
the sanctioned 2× deliberation; cost prints per pair.

Run from the repo root with the worktree venv:
    PYTHONPATH=. venv/bin/python scripts/probe_paired_contrast.py [--symbol SYM ...] [--dry-run]
Default: every symbol that has ≥1 renderable pinned item AND a hand-seed theme. TEE THE OUTPUT.
"""
from __future__ import annotations

import argparse
import random
import sys

from dotenv import load_dotenv

load_dotenv("/home/rodrigo/dramatic_options/.env")

import orchestrator  # noqa: E402
from clock import LiveClock  # noqa: E402
from config_loader import load_config, require_alpaca_credentials  # noqa: E402
from council.council import propose  # noqa: E402
from council.paired_contrast import LEDGER_FIELDS, append_pair_row, pair_verdict  # noqa: E402
from data.alpaca_client import AlpacaClient  # noqa: E402
from data.cache import PointInTimeCache  # noqa: E402
from risk import kill_switch_active  # noqa: E402
from themes import active_themes, load_themes  # noqa: E402

LEDGER = "records/forward_catalyst_pairs.csv"

parser = argparse.ArgumentParser()
parser.add_argument("--symbol", action="append", default=None,
                    help="probe only these symbols (repeatable); default = all pinned hand-seeds")
parser.add_argument("--dry-run", action="store_true", help="print verdicts, skip the CSV append")
args = parser.parse_args()

if kill_switch_active():
    print("KILL switch engaged — no LLM spend.")
    sys.exit(0)

config = load_config()
api_key, secret_key = require_alpaca_credentials(config)
client = AlpacaClient(api_key, secret_key, paper=config["alpaca"]["paper"])
clock = LiveClock(client)
as_of = clock.now()
cache = PointInTimeCache(config.get("cache", {}).get("dir", "data/cache"))

router, news, fundamentals, analyst, catalysts = orchestrator._build_council_io(
    config, demo=False, client=client, cache=cache, clock=clock)
if catalysts is None:
    print("forward-catalyst channel disabled/unavailable — nothing to pair.")
    sys.exit(0)

themes = {t.symbol.upper(): t for t in active_themes(load_themes(config.get("themes_path", "themes.json")))
          if getattr(t, "sentinel_id", None) is None}
want = {s.upper() for s in args.symbol} if args.symbol else None

pairs = 0
for sym, theme in sorted(themes.items()):
    if want is not None and sym not in want:
        continue
    items = catalysts.items_asof(sym, as_of)
    if not items:
        continue
    print(f"\n=== {sym} ({theme.direction}) — {len(items)} pinned item(s) ===")
    # Identical seeded rng per arm → the strategist for/against presentation order matches
    # across arms ("all else identical", §6).
    channel = propose([theme], router=router, config=config, clock=clock, news=news,
                      fundamentals=fundamentals, analyst=analyst, catalysts=catalysts,
                      rng=random.Random(0))
    nochannel = propose([theme], router=router, config=config, clock=clock, news=news,
                        fundamentals=fundamentals, analyst=analyst, catalysts=None,
                        rng=random.Random(0))
    if not channel or not nochannel:
        print("  arm failed fail-closed (budget/kill) — no pair recorded.")
        continue
    row = pair_verdict(channel[0], nochannel[0], items, as_of)
    for k in LEDGER_FIELDS:
        print(f"  {k}: {row[k]}")
    if not args.dry_run:
        append_pair_row(LEDGER, row)
        print(f"  → appended to {LEDGER}")
    pairs += 1

print(f"\n{pairs} pair(s) probed. {router.ledger.summary()}")
if pairs and not args.dry_run:
    print("Reminder: commit the ledger append (records PR) — the M-sample accounting is the record.")
