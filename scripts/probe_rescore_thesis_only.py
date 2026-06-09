"""STEP 0 — the §5-compliant thesis-only re-score (ephemeral, live router, NO live-record).

COMMITTED COPY of the /tmp/rescore.py harness that produced the PREREG_COUNCIL_GATE_SEPARATION §10
run of record (2026-06-09 21:52 UTC, 5/16 ≥MODERATE → SELECTIVITY FLAG). UNIVERSE below is the
§5-pinned population — the §10.4 re-tightened re-score MUST run on this same list. Differences vs
the ephemeral original: this docstring + unused-import removal (ruff); logic unchanged.

Scores the FULL §5 population (the 16-name universe; the 8 harm-quadrant names are a subset) under
the EXACT previewed all-roles thesis-only config (the edited council/agents.py _COMMON + adversary),
grounded on each name's deterministic markers (origin-aware). Captures per-name verdicts + count +
band + cost + models for the §10 append. Writes nothing to the live DB.

Run from the repo root with the worktree venv (PYTHONPATH=. venv/bin/python
scripts/probe_rescore_thesis_only.py); spends ~$0.2 of live LLM calls. TEE THE OUTPUT TO A FILE.
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv("/home/rodrigo/dramatic_options/.env")

import discovery  # noqa: E402
import orchestrator  # noqa: E402
import sentinels  # noqa: E402
from clock import LiveClock  # noqa: E402
from config_loader import load_config, require_alpaca_credentials  # noqa: E402
from council import agents  # noqa: E402
from council.council import propose  # noqa: E402
from council.proposal import select_for_trade  # noqa: E402
from data.alpaca_client import AlpacaClient  # noqa: E402
from data.cache import PointInTimeCache  # noqa: E402
from data.market import MarketData, default_fetch_window  # noqa: E402
from feeds import to_equity_feed  # noqa: E402
from themes import Theme  # noqa: E402

UNIVERSE = ["NVDA", "SMCI", "VRT", "ETN", "GEV", "CEG", "CCJ", "FCX",
            "NEE", "PWR", "RKLB", "LMT", "NOC", "LHX", "RTX", "KTOS"]

config = load_config()
config["council"]["max_candidates"] = 20  # score ALL 16 (no truncation; default is 12)
api_key, secret_key = require_alpaca_credentials(config)
client = AlpacaClient(api_key, secret_key, paper=config["alpaca"]["paper"])
clock = LiveClock(client)
as_of = clock.now()
cache = PointInTimeCache(config.get("cache", {}).get("dir", "data/cache"))
fetch_start, _ = default_fetch_window(as_of)
market = MarketData(cache, client=client, fetch_start=fetch_start, fetch_end=as_of,
                    feed=to_equity_feed(config["data_feed"]["equity_bars"]))
baskets, benchmark = orchestrator._scan_universe(config)
sym2basket = {s: b for b, members in baskets.items() for s in members}
params = discovery.MarkerParams(**dict(config["discovery"].get("markers", {})))

print("=== PREVIEWED THESIS-ONLY CONFIG (the exact prompts this run used) ===")
print("_COMMON:\n", agents._COMMON, "\n")
print("ADVERSARY_SYSTEM:\n", agents.ADVERSARY_SYSTEM, "\n")

# Build the 16 candidates, FORCED (no motion floor — §5 scores the full universe), marker-grounded.
candidates, mk_by_sym = [], {}
for sym in UNIVERSE:
    m = discovery.compute_markers(sym, as_of, market=market, benchmark=benchmark, params=params,
                                  basket=sym2basket.get(sym, ""))
    mk = sentinels.markers_dict(m)
    mk_by_sym[sym] = mk
    candidates.append(Theme(name=sym2basket.get(sym, "theme"), symbol=sym,
                            direction=discovery.direction_of(m), thesis="discovery hypothesis (markers-grounded)",
                            source="sentinel", markers=mk))

router, _news = orchestrator._build_council_io(config, demo=False, client=client, cache=cache, clock=clock)
print("models:", {r: "/".join(router.provider_model(r)) for r in ("proposer", "adversary", "strategist")})
print(f"scoring {len(candidates)} names (as_of {as_of.isoformat()}) ...\n")

proposals = propose(candidates, router=router, config=config, clock=clock, news=None, demo=False)
survivors = {id(p) for p in select_for_trade(proposals, floor=config["council"].get("conviction_floor", "MODERATE"))}

print(f"{'sym':5} {'dir':5} {'conv':9} {'incl':5} {'s/f':10} mom/rvslope/rel | weakest_point")
ge_mod = 0
for p in proposals:
    mk = mk_by_sym.get(p.symbol, {})
    g = f"{mk.get('momentum')}/{mk.get('rv_slope')}/{mk.get('rel_strength')}"
    incl = id(p) in survivors
    if incl:
        ge_mod += 1
    wp = (p.weakest_point or "")[:70]
    print(f"{p.symbol:5} {p.direction[:5]:5} {str(p.conviction):9} {str(incl):5} "
          f"{str(p.structural_vs_fad):10} {g} | {wp}")

band = "0=SCARCITY (proceed on principle, no trade)" if ge_mod == 0 else (
    "1=CONFIRMS (proceed)" if ge_mod == 1 else f"{ge_mod}>=2=SELECTIVITY-FLAG (investigate)")
print(f"\n=== RESULT: {ge_mod} of {len(proposals)} reached >=MODERATE (include) -> {band} ===")
print("cost:", router.ledger.summary())
gev = next((p for p in proposals if p.symbol == "GEV"), None)
if gev:
    print(f"\nGEV: conviction={gev.conviction} include={id(gev) in survivors} s/f={gev.structural_vs_fad}")
    print("  strategist_summary:", (gev.strategist_summary or "")[:300])
