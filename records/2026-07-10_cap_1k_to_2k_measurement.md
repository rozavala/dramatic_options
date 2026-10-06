# 2026-07-10 — The $1k→$2k per-name cap question, MEASURED (verdict: does not make sense on today's data)

## The question and the instrument

Operator (2026-07-10): *"should we increase the cap from $1k to $2k to make it easier? I'm not
sure that artificial cap adds much value and it could potentially (to be confirmed) open a whole
universe of options."* The pre-committed process: decide on the POPULATION, not on any wanted
name (the idea surfaced minutes after KMT's cap-block was named — anti-HARK).

Instrument: `scripts/probe_basket_feasibility.py` (the frozen §2 screen — floors + cap-fit
arithmetic only, cheapness deliberately absent), run MID-SESSION 2026-07-10 16:12 UTC (the
after-hours instrument is banned for this question — the KMT bidirectional lesson) over the full
38-name universe + the staged names (ADTN/CLFD/KMT/TROX/TITN/LNN) + every recorded cap-death
(GEV/HCC/AIR/TDW/VAL/NE/HLIT). Raw output: `records/2026-07-10_cap_sweep_raw.txt`.

## The population: a $1k→$2k transition opens exactly THREE names — none of the motivating ones

**In the $1k–$2k band with a CLEAN 15–35% achieved-OTM structure (the only names any cap change
unlocks):**

| name | 1 contract | achieved OTM | the catch |
|---|---|---|---|
| CCJ | $1,335 | 25.3% | nuclear_fuel already has NXE $118 / UEC $176 / SMR $216 / UUUU $220 / NNE $350 fittable; CCJ would consume 67% of the $2k cluster budget |
| NVDA | $1,522 | 24.3% | the gate-rich canary — expected IV-vetoed every cycle; $29B ADV mega-cap, the opposite of quiet convexity |
| RKLB | $1,900 | 24.2% | the one real case (its lone gate-pass died at the cluster cap, L1 #111) — but $1,900 = 95% of the space_smallcap cluster budget, and the cluster already holds FLY/LUNR/PL/RDW at $222–$610 |

**The names that motivated the intuition are NOT cap-blocked — they are BAND-broken, which no
cap change touches:**

| name | 1 contract | achieved OTM | actual binding constraint |
|---|---|---|---|
| KMT | $1,370 | **−40.2% (ITM fallback)** | no eligible 15–35% OTM wing in tenor — chain structure, not dollars |
| TDW | $1,335 | −8.8% ITM | same |
| VAL | $1,550 | −5.7% ITM | same |
| HCC | $1,120 | +7.3% | below the 15% band floor |
| AIR | $1,300 | +14.0% | just below the band floor |
| GEV | $9,915 | 27.0% | out of reach at any sane cap |
| CLFD/TITN/LNN | — | — | no eligible contract at all |

⭐ **KMT — the name whose $1,370 sparked the question — would still be untradeable at $2k**: its
selected structure today is 40% ITM. The 07-08 finding ("the after-hours '$400 fits' was the
optimistic error") extends: KMT's problem is its strike grid and wing liquidity, full stop.

**Slot-supply context:** 31 of 50 screened names fit ONE contract under the frozen $1k cap —
against 15 max open positions and a book holding 1. The binding constraint on activity is
judgment/mandate scarcity, not cap-fittability. (Side observation, logged: ADTN read $625 at
−40.3% ITM-fallback today vs $192 at +24.6% in-band on 07-08 — thin-chain expression is
UNSTABLE across days; its probe-layer status is unaffected.)

## Verdict (recommendation to the operator)

**Leave the cap frozen.** The flat $1k→$2k raise buys 3 low-marginal-value names while (a)
making per-name equal the per-cluster budget (one name can consume a cluster's whole
correlation allowance) and (b) re-wiring the 20% book-DD kill (one $2k position marking to zero
= the full halt threshold — a hair-trigger on the strategy's EXPECTED base case). The
single-contract exception (per-name ≤$1k OR exactly 1 contract ≤$2k) buys the SAME 3 names —
the shape is better but the population doesn't justify any amendment today.

**The door that stays open (dated):** if a future §11 window admits names whose clean-band
contracts cluster in $1k–$2k, re-run this measurement — the population, not the principle,
was the decider. And the REAL unlock this sweep points at is upstream of any cap: the
achieved-OTM band on coarse/thin chains (KMT/TDW/VAL/HCC/AIR all die there) — that is a chain-
structure fact about the names, not a knob this system should bend (a different payoff object
is a different strategy).
