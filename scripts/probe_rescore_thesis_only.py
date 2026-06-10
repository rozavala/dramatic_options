"""STEP 0 — the §5-compliant thesis-only re-score (ephemeral, live router, NO live-record).

COMMITTED COPY of the /tmp/rescore.py harness that produced the PREREG_COUNCIL_GATE_SEPARATION §10
run of record (2026-06-09 21:52 UTC, 5/16 ≥MODERATE → SELECTIVITY FLAG). UNIVERSE below is the
§5-pinned population — the §10.4 re-tightened re-score MUST run on this same list.
EXTENDED 2026-06-10 for the §10.7 re-tightened preview: prints all three prompt sha256/16s (the
run must hash-match the §10.7 pins), captures the strategist's tri-criteria booleans
(under_narrated / at_inflection, keyed by the schema's own symbol field), and applies the §10.7
ENFORCEMENT rule — survivors = include ∧ ≥MODERATE ∧ (structural ∧ under_narrated ∧ at_inflection);
an include failing the tri-criteria is a recorded CRITERIA-VETO, distinct from parse_error.

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
import hashlib  # noqa: E402

for _name, _s in (("_COMMON", agents._COMMON), ("ADVERSARY_SYSTEM", agents.ADVERSARY_SYSTEM),
                  ("STRATEGIST_SYSTEM", agents.STRATEGIST_SYSTEM)):
    print(f"sha256/16 {_name}: {hashlib.sha256(_s.encode()).hexdigest()[:16]}")
print("_COMMON:\n", agents._COMMON, "\n")
print("ADVERSARY_SYSTEM:\n", agents.ADVERSARY_SYSTEM, "\n")
print("STRATEGIST_SYSTEM:\n", agents.STRATEGIST_SYSTEM, "\n")

# Capture the strategist RAW verdicts (the §10.7 tri-criteria booleans live there, keyed by the
# schema's own 'symbol' field) so the enforcement rule can be applied post-pass.
_strat_raw: dict[str, dict] = {}
_orig_parse_strategist = agents.parse_strategist

def _capturing_parse_strategist(text, **kw):
    d = _orig_parse_strategist(text, **kw)
    sym = str(d.get("symbol", "")).upper()
    if sym:
        _strat_raw[sym] = d
    return d

agents.parse_strategist = _capturing_parse_strategist

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

print(f"{'sym':5} {'dir':5} {'conv':9} {'incl':5} {'s/f':10} {'u_narr':6} {'at_infl':7} "
      f"{'tri':4} mom/rvslope/rel | weakest_point")
ge_mod = 0          # the §10.7 ENFORCED survivor count: include ∧ >=MODERATE ∧ tri-criteria-pass
raw_includes = 0    # the pre-enforcement count, reported for the criteria-veto delta
for p in proposals:
    mk = mk_by_sym.get(p.symbol, {})
    g = f"{mk.get('momentum')}/{mk.get('rv_slope')}/{mk.get('rel_strength')}"
    incl = id(p) in survivors
    raw = _strat_raw.get(p.symbol.upper(), {})
    u_narr = raw.get("under_narrated")
    at_infl = raw.get("at_inflection")
    tri = (str(p.structural_vs_fad) == "structural" and u_narr is True and at_infl is True)
    if incl:
        raw_includes += 1
    if incl and tri:
        ge_mod += 1
    elif incl and not tri:
        print(f"  CRITERIA-VETO {p.symbol}: include=true but tri-criteria fail "
              f"(s/f={p.structural_vs_fad} u_narr={u_narr} at_infl={at_infl}) -> include coerced false")
    wp = (p.weakest_point or "")[:60]
    print(f"{p.symbol:5} {p.direction[:5]:5} {str(p.conviction):9} {str(incl):5} "
          f"{str(p.structural_vs_fad):10} {str(u_narr):6} {str(at_infl):7} "
          f"{('YES' if tri else 'no'):4} {g} | {wp}")

band = "0=SCARCITY (proceed on principle, no trade)" if ge_mod == 0 else (
    "1=CONFIRMS (proceed)" if ge_mod == 1 else f"{ge_mod}>=2=SELECTIVITY-FLAG (investigate)")
print(f"\n=== RESULT: {ge_mod} of {len(proposals)} survive the ENFORCED rule "
      f"(include ∧ >=MODERATE ∧ tri-criteria) -> {band} ===")
print(f"(raw include∧>=MODERATE before enforcement: {raw_includes}; "
      f"criteria-vetoes: {raw_includes - ge_mod})")
print("cost:", router.ledger.summary())
gev = next((p for p in proposals if p.symbol == "GEV"), None)
if gev:
    print(f"\nGEV: conviction={gev.conviction} include={id(gev) in survivors} s/f={gev.structural_vs_fad}")
    print("  strategist_summary:", (gev.strategist_summary or "")[:300])
