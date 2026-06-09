"""READ-ONLY OPRA-vs-INDICATIVE dual-read on the ACTUAL gate inputs (the OPRA sequencing decision).

COMMITTED COPY of the /tmp/opra_dualread.py probe cited by the OPRA-sequencing work (2026-06-09
13:00 ET mid-day read: 12/16 IND vs 10/16 OPRA cheap, 0 coverage gaps, |Δ iv/rv| med 0.014 / max
0.024, GEV cheap on both 1.155/1.135). Committing it preserves the evidence script; it does NOT
freeze the (unfrozen) OPRA pre-reg. Differences vs the ephemeral original: this docstring,
unused-import removal, `statistics` import moved to top, and the GEV-detail print's invalid
format-spec fixed (ruff/runtime); logic otherwise unchanged.

For each universe name, runs the exact production gate pipeline (select_structure -> is_cheap_convexity)
on BOTH option feeds, same instant, and reports: pass/veto per feed, FLIPS, the wing IVs, the
iv/rv + skew deltas, and OPRA coverage gaps (a name OPRA can't structure but INDICATIVE can = a
false-veto-under-acceleration). RV + underlying are SIP (feed-independent), fetched once.

Caveat: a SINGLE mid-day snapshot — cannot see the open / stressed / close wing-firming the
multi-session dual-read (PR2) would. Necessary, not sufficient, for 'accelerate'.
"""
from __future__ import annotations

import statistics as st
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv("/home/rodrigo/dramatic_options/.env")

from config_loader import load_config, require_alpaca_credentials  # noqa: E402
from convexity_data import AlpacaChainProvider  # noqa: E402
from convexity_gate import is_cheap_convexity, realized_vol  # noqa: E402
from data.alpaca_client import AlpacaClient  # noqa: E402
from feeds import to_equity_feed, to_option_feed  # noqa: E402
from structure import contract_eligible, select_structure  # noqa: E402

UNIVERSE = ["NVDA", "SMCI", "VRT", "ETN", "GEV", "CEG", "CCJ", "FCX",
            "NEE", "PWR", "RKLB", "LMT", "NOC", "LHX", "RTX", "KTOS"]

config = load_config()
api_key, secret_key = require_alpaca_credentials(config)
client = AlpacaClient(api_key, secret_key, paper=True)

gate = config["convexity_gate"]
elig_c = config["eligibility"]["live"]
IV_RV_MAX = float(gate["iv_rv_max"])
SKEW_MAX = float(gate["otm_skew_max_volpts"])
RV_WIN = int(gate["rv_window_days"])
TMIN, TMAX, TMNY = int(gate["tenor_min_days"]), int(gate["tenor_max_days"]), float(gate["target_moneyness"])

eq_feed = to_equity_feed(config["data_feed"]["equity_bars"])  # SIP — same on both option feeds
prov_ind = AlpacaChainProvider(client, equity_feed=eq_feed, option_feed=to_option_feed("indicative"))
prov_opra = AlpacaChainProvider(client, equity_feed=eq_feed, option_feed=to_option_feed("opra"))

def _eligibility(c):
    return contract_eligible(c, max_spread_pct=float(elig_c.get("max_bid_ask_pct", 0.25)),
                             min_contract_price=0.10, max_contract_price=100.0,
                             min_oi=elig_c.get("min_option_open_interest"))

now_et = datetime.now(ZoneInfo("America/New_York"))
today = now_et.date()
print(f"=== OPRA vs INDICATIVE dual-read @ {now_et:%Y-%m-%d %H:%M ET} (single mid-day snapshot) ===")
print(f"gate: iv/rv<={IV_RV_MAX}  skew<={SKEW_MAX}vp  {int(TMNY*100)}%OTM  {TMIN}-{TMAX}d\n")


def eval_feed(prov, sym, direction, rv, spot):
    chain = prov.chain(sym)
    s, why = select_structure(chain, direction=direction, as_of=today, underlying_price=spot,
                              tenor_min_days=TMIN, tenor_max_days=TMAX, target_moneyness=TMNY,
                              eligibility=_eligibility)
    if s is None:
        return {"ok": False, "why": why[0] if why else "no_structure"}
    v = is_cheap_convexity(chain, underlying_price=spot, wing=s.contract, rv=rv,
                           iv_rv_max=IV_RV_MAX, otm_skew_max_volpts=SKEW_MAX)
    return {"ok": True, "cheap": v.cheap, "iv_rv": v.iv_rv_ratio, "skew": v.otm_skew_volpts,
            "atm_iv": v.atm_iv, "wing_iv": v.wing_iv, "wing": s.contract.symbol,
            "bid": s.contract.bid, "ask": s.contract.ask}


rows = []
for sym in UNIVERSE:
    try:
        spot = prov_ind.underlying_price(sym)
        closes = prov_ind.closes(sym, window=300)
        rv = realized_vol(closes, window=RV_WIN)
        mom = (closes[-22] / closes[-253] - 1.0) if len(closes) >= 253 else None
        direction = "bullish" if (mom is None or mom > 0) else "bearish"
        ind = eval_feed(prov_ind, sym, direction, rv, spot)
        opra = eval_feed(prov_opra, sym, direction, rv, spot)
        rows.append((sym, direction, spot, rv, mom, ind, opra))
    except Exception as e:  # noqa: BLE001
        rows.append((sym, "?", None, None, None, {"ok": False, "why": f"ERR {e}"}, {"ok": False, "why": "ERR"}))

def vstr(d):
    if not d.get("ok"):
        return f"n/a({d.get('why','')[:22]})"
    tag = "CHEAP" if d.get("cheap") else "veto "
    return f"{tag} ivrv={d['iv_rv']:.3f} skew={d['skew']:.1f} atm={d['atm_iv']:.3f} wing={d['wing_iv']:.3f}"

print(f"{'sym':5} {'dir':4} {'INDICATIVE':46} {'OPRA':46} flip")
n_ind = n_opra = n_flip = n_cov_gap = 0
flips, cov_gaps, drv, dskew = [], [], [], []
for sym, direction, _spot, _rv, _mom, ind, opra in rows:
    ip = ind.get("ok") and ind.get("cheap")
    op = opra.get("ok") and opra.get("cheap")
    n_ind += int(bool(ip))
    n_opra += int(bool(op))
    flip = ""
    if bool(ip) != bool(op):
        n_flip += 1
        flip = "IND→OPRA LOSES" if ip else "IND→OPRA GAINS"
        flips.append((sym, flip, ind, opra))
    if ind.get("ok") and not opra.get("ok"):
        n_cov_gap += 1
        cov_gaps.append((sym, opra.get("why")))
    if ind.get("ok") and opra.get("ok"):
        drv.append(abs((opra["iv_rv"] or 0) - (ind["iv_rv"] or 0)))
        dskew.append(abs((opra["skew"] or 0) - (ind["skew"] or 0)))
    star = " *GEV*" if sym == "GEV" else ""
    print(f"{sym:5} {direction[:4]:4} {vstr(ind):46} {vstr(opra):46} {flip}{star}")

print("\n=== SUMMARY ===")
print(f"gate-CHEAP: INDICATIVE={n_ind}/16   OPRA={n_opra}/16   flips={n_flip}")
print(f"OPRA coverage gaps (IND structures, OPRA cannot): {n_cov_gap}  {cov_gaps}")
if drv:
    print(f"|Δ iv/rv| median={st.median(drv):.4f} max={max(drv):.4f}   "
          f"|Δ skew(vp)| median={st.median(dskew):.3f} max={max(dskew):.3f}")
for sym, flip, ind, opra in flips:
    print(f"  FLIP {sym} {flip}:\n     IND : {vstr(ind)}\n     OPRA: {vstr(opra)}")
gev = next((r for r in rows if r[0] == "GEV"), None)
if gev:
    rv_s = f"{gev[3]:.3f}" if gev[3] else "n/a"
    print(f"\nGEV detail: dir={gev[1]} spot={gev[2]} rv={rv_s}")
    print(f"  IND : {vstr(gev[5])}  wing={gev[5].get('wing')} bid/ask={gev[5].get('bid')}/{gev[5].get('ask')}")
    print(f"  OPRA: {vstr(gev[6])}  wing={gev[6].get('wing')} bid/ask={gev[6].get('bid')}/{gev[6].get('ask')}")
