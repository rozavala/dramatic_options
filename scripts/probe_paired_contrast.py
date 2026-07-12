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
    PYTHONPATH=. venv/bin/python scripts/probe_paired_contrast.py \
        [--symbol SYM ...] [--themes FILE] [--render-only | --dry-run]
Default: every symbol that has ≥1 renderable pinned item AND a hand-seed theme.

**--themes FILE (the §0 option-(a) vehicle):** STAGED names are deliberately NOT in the live
themes.json — adding them there would be admission (the live L1 would judge them, and a flip
could walk to a paper entry as a side-effect of measurement). A probe-only themes file gives
them hand-seed-ORIGIN packs (all the §4 origin scope requires) without ever touching the live
candidate path.

**--render-only:** the true zero-spend preflight (--dry-run still runs BOTH LLM arms; it only
skips the ledger append). Prints the rendered block, §8 eligibility, and cite tokens. Use it
after every pin, before the first paid pair. TEE THE OUTPUT.
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
parser.add_argument("--dry-run", action="store_true",
                    help="run both arms (LIVE LLM SPEND) but skip the CSV append")
parser.add_argument("--render-only", action="store_true",
                    help="ZERO-spend preflight: build the channel-arm pack and print the "
                         "rendered FORWARD_CATALYSTS block + eligibility + cite tokens — no "
                         "router, no arms, no ledger")
parser.add_argument("--themes", default=None, metavar="FILE",
                    help="probe-only themes file (the §0 option-(a) vehicle for STAGED names: "
                         "candidates probed here never enter the live L1 candidate path — "
                         "presence in the LIVE themes.json is admission, this flag is not). "
                         "Default: the live themes_path.")
args = parser.parse_args()

if not args.render_only and kill_switch_active():
    print("KILL switch engaged — no LLM spend.")
    sys.exit(0)

config = load_config()

if args.render_only:
    # Preflight without the router OR the broker: the channel provider + packs only — no keys,
    # no LLM, no quotes. Confirms §2 validation, §3 expiry/staleness, the §7 char bound, §8
    # eligibility + cite tokens — for $0.00.
    from datetime import datetime  # noqa: E402

    from council.context import build_context_pack, catalyst_cite_tokens  # noqa: E402
    from council.paired_contrast import eligible_classes  # noqa: E402
    from data.forward_catalysts import ForwardCatalysts  # noqa: E402
    as_of = datetime.now()
    fc_cfg = config.get("forward_catalysts", {}) or {}
    catalysts = ForwardCatalysts(fc_cfg.get("path", "forward_catalysts.json"),
                                 max_items=int(fc_cfg.get("max_items", 3)),
                                 staleness_days=int(fc_cfg.get("staleness_days", 30)),
                                 max_block_chars=int(fc_cfg.get("max_block_chars", 1600)))
    themes_path = args.themes or config.get("themes_path", "themes.json")
    cands = {t.symbol.upper(): t for t in active_themes(load_themes(themes_path))
             if getattr(t, "sentinel_id", None) is None}
    want = {s.upper() for s in args.symbol} if args.symbol else None
    shown = 0
    for sym, theme in sorted(cands.items()):
        if want is not None and sym not in want:
            continue
        # Items read off the PACK (one items_asof call — the counters print true).
        pack = build_context_pack(theme, news=None, as_of=as_of, catalysts=catalysts)
        items = pack.forward_catalysts
        if not items:
            continue
        print(f"\n=== {sym} ({theme.direction}) — render-only preflight ===")
        print(f"eligible_classes: {eligible_classes(items, as_of)}")
        print(f"cite_tokens: {sorted(set(catalyst_cite_tokens(items)))}")
        block = pack.as_prompt_block()
        start = block.find("FORWARD_CATALYSTS")
        print(block[start:] if start >= 0 else "(block did NOT render — check origin/items)")
        shown += 1
    print(f"\n{shown} name(s) rendered. counters: {catalysts.counters()}  ($0.00 spent)")
    sys.exit(0)

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

themes_path = args.themes or config.get("themes_path", "themes.json")
if args.themes:
    print(f"probe-only themes file: {args.themes} (staged names — never the live candidate path)")
themes = {t.symbol.upper(): t for t in active_themes(load_themes(themes_path))
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
    # The strategist's actual words, per arm — proposals are ephemeral (never persisted), so
    # this print is the only surface where the operator can read WHY the arms agreed/differed.
    print(f"  channel strategist:   {(channel[0].strategist_summary or '(none)')[:300]}")
    print(f"  nochannel strategist: {(nochannel[0].strategist_summary or '(none)')[:300]}")
    if not args.dry_run:
        append_pair_row(LEDGER, row)
        print(f"  → appended to {LEDGER}")
    pairs += 1

print(f"\n{pairs} pair(s) probed. {router.ledger.summary()}")
if pairs and not args.dry_run:
    print("Reminder: commit the ledger append (records PR) — the M-sample accounting is the record.")
