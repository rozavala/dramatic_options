# 2026-11-03 — Literature review: what the research says about cheap convexity, slow narratives, and a book of small bets

**Status: reference record (no rule change).** Written for the operator's question "how do we raise the
odds of a big win while keeping losses small?". Each paper maps to a design implication and, where one
exists, a DRAFT in `records/2026-11-03_profit_program_DRAFTS.md` or the calibration v2 amendment
(`PREREG_CONVEXITY_CALIBRATION` §4, 2026-11-03). Nothing here changes the frozen frame.

**Citation discipline.** `[v]` = bibliographic facts and headline finding checked against a published
abstract or index on 2026-11-03. `[m]` = cited from memory, not re-checked this session; check before
quoting a number. Effect sizes are in-sample, mostly short-horizon, and mostly pre-cost. None of them is an
edge for this book; each is a reason to measure something, not to trade it.

---

## 0. The one-line synthesis

The research supports both halves of the mandate and warns about one thing. **Long options lose on
average** (the variance risk premium), so unconditional OTM buying is negative-EV and the cheapness gate is
load-bearing. **Investors under-react to slow, forecastable, distant information** (demographics, supply
chains, quiet filings, low coverage), which is where "copper-not-rockets" lives. And **single-stock outcomes
are so skewed** that the book's payoff is set by a few names: the number of independent shots is what
matters, and every filter that cuts shots must earn its keep.

---

## 1. Is the convexity cheap? (the gate)

| Paper | Finding | Implication for us |
|---|---|---|
| Coval & Shumway (2001), "Expected Option Returns", *JF* 56(3) `[m]` | OTM calls earn large negative average returns; the further OTM, the worse. | Buying far-OTM without a filter is a donation. The gate is the strategy; never relax it to raise throughput. |
| Goyal & Saretto (2009), "Cross-section of option returns and volatility", *JFE* 91 `[v]` | Sorting on historical-minus-implied vol: options whose IV is low against the stock's realized vol earn higher returns (straddles, delta-hedged). Costs eat much of it (Do, Foster & Gray 2016, Australia). | Direct support for `IV_atm/RV ≤ 1.2`. Their IV is 1-month ATM vs 12-month HV; ours is 6–12-month. The mean-reversion logic carries; the magnitude doesn't. |
| Vasquez (2017), "Equity Volatility Term Structures and the Cross Section of Option Returns", *JFQA* 52(6) `[v]` | The slope of the IV term structure (long-dated minus short-dated ATM IV) predicts option returns; high-slope names' straddles outperform. Fragile to spreads above quoted. | Our chain snapshots already hold every expiry. **Record the term-structure slope per name** (draft D4). Its sign for 6–12-month buys is not established, so measure it; don't gate on it. |
| Boyer & Vorkink (2014), "Stock Options as Lotteries", *JF* 69(4) `[v]` | Options with high ex-ante total skewness earn much lower returns: a lottery premium paid to market makers. Strongest for short-dated OTM. | Supports long tenor and the skew cap: the 6–12-month wing sidesteps the worst of the lottery premium. A name whose wing is bid (`OTM − ATM > 10`) is where the lottery buyers already are. |
| An, Ang, Bali & Cakici (2014), "The Joint Cross Section of Stocks and Options", *JF* 69(5) `[v]` | Rising call IV over the past month predicts higher next-month stock returns; rising put IV predicts lower. Persists up to ~6 months. | Our own snapshots can compute 1-month ΔIV per side. A **direction-confirming** feature for the council pack (draft D4). It works against cheapness (rising IV = pricier), so it ranks within the gate; it never overrides it. |

## 2. Is the story under-narrated? (where slow information lives)

| Paper | Finding | Implication for us |
|---|---|---|
| DellaVigna & Pollet (2007), "Demographics and Industry Returns", *AER* 97(5) `[v]` | Forecastable demand shifts 5–10 years out predict industry returns (~6%/yr risk-adjusted strategy); short-horizon shifts are already priced. Stronger where barriers to entry are high. | The cleanest academic statement of "copper-not-rockets": **distant, forecastable, physical demand** is under-priced. Prefer drivers with a measurable multi-year demand path and supply that can't respond fast (draft D5). |
| Hong & Stein (1999), *JF*; Hong, Lim & Stein (2000), "Bad News Travels Slowly", *JF* `[m]` | Information diffuses gradually; momentum is stronger in low-analyst-coverage firms. | Supports `under_narrated` and the restored analyst meter (`analyst_v2`). Coverage is the right instrument; the 10-24 outage cost three months of it. |
| Fang & Peress (2009), "Media Coverage and the Cross-section of Stock Returns", *JF* 64(5) `[v]` | No-media stocks beat heavily-covered ones by ~3%/yr; larger in small, low-coverage names. Contested later (Hillert & Ungeheuer 2016, long-run NYT data). | A quantitative **narration meter** belongs in the pack (draft D6). The effect is modest and contested, so it's a filter, not a 10× engine. |
| Cohen & Frazzini (2008), "Economic Links and Predictable Returns", *JF* `[m]` | Customer-firm returns predict supplier returns; investors are slow to carry news across the link. | **Supply-chain propagation:** a large customer's capex move reaches the under-covered supplier late. `corpus/customer_concentration.py` already maps links; render the customer-side move as driver evidence (draft D5). |
| Cohen, Malloy & Nguyen (2020), "Lazy Prices", *JF* `[m]` | Year-over-year changes in 10-K/10-Q language predict returns; markets don't notice quiet filing changes. | §10.11 now demands *name-level* evidence from the latest filing. A **filing-diff** (what changed in risk factors / MD&A since last period) is exactly that evidence, deterministic and dated (draft D5). |
| Hoberg & Phillips (2016), "Text-Based Network Industries and Endogenous Product Differentiation", *JPE* `[m]` | Industry membership from 10-K product-description similarity beats SIC/NAICS. | **Better classification:** score each universe name's Item 1 text against each cluster's driver description; flag names whose exposure doesn't match their cluster (a report-not-gate backstop beside `cluster_diagnostic.py`). |
| Da, Engelberg & Gao (2011), "In Search of Attention", *JF* `[m]` | Search-volume spikes predict a short-term rise and a reversal within the year. | Retail attention is a **late-stage** marker. A spike says "narrated", not "buy". Use it in the narration meter as a disqualifier signal. |

## 3. When is a theme already priced? (stage-3 markers, and the bear side)

| Paper | Finding | Implication for us |
|---|---|---|
| Ben-David, Franzoni, Kim & Moussawi (2023), "Competition for Attention in the ETF Space", *RFS* 36(3) `[v]` | Specialized/thematic ETFs launch after a theme is hot, hold attention-grabbing overvalued stocks, and underperform badly after launch. | **A thematic-ETF launch is a dated consensus marker.** A new ETF on a cluster's driver ⇒ that cluster is narrated (stage 3). `corpus/etf_constituents.py` already reads holdings (draft D6). |
| Greenwood, Shleifer & You (2019), "Bubbles for Fama", *JFE* `[v]` | Industry run-ups don't predict lower average returns, but sharply raise crash odds (40% drawdown within 2 years: ~20% → ~53% as the 2-year market-relative run-up goes 50% → 100%; ~80% at 150%). Volatility, turnover, **issuance** and an accelerating run-up raise it further. | The **bear side** gets a deterministic classifier: put structures on run-up baskets with heavy issuance (we already parse 424Bs, `data/prospectus.py`). And a caution for the bull side: a cluster up 100%+ is crash-prone even when the story is right. |
| Greenwood & Hanson (2015), "Waves in Ship Prices and Investment", *QJE*; Chancellor (2015), *Capital Returns* `[m]` | Competition neglect: high prices bring an industry capex boom that crushes later returns. The capital cycle. | A **capex-cycle classifier** from XBRL we already hold: tight supply plus falling industry capex = bullish inflection; capex boom = bearish. Fits silver/uranium/copper especially (draft D5). |
| Gorton, Hayashi & Rouwenhorst (2013), "The Fundamentals of Commodity Futures Returns", *RoF* `[m]` | Low inventories go with backwardation and higher commodity risk premia. | **Inventories as the driver series** for the mining clusters (COMEX/LME stocks; draft D5). |

## 4. Getting the big win: the shape of the book

| Paper | Finding | Implication for us |
|---|---|---|
| Bessembinder (2018), "Do Stocks Outperform Treasury Bills?", *JFE* `[m]` | ~4% of listed stocks account for all net US wealth creation; most stocks underperform T-bills. | Single-name outcomes are extremely skewed. The book's result is set by a handful of names, so **the number of independent shots dominates**. A filter that cuts N must show it raises the hit-rate by more (draft D1). |
| Kaminski & Lo (2014), "When Do Stop-Loss Rules Stop Losses?", *JFM* 18 `[v]` | Under a random walk a stop-loss always lowers expected return; under momentum or regime switching it can add value. | A **price** stop on a far-OTM option is wrong for us. An **information** stop (the thesis's falsifier fires) is a regime-switch exit, which is the case where they show value. Tested in calibration v2 (salvage cells) before any draft. |

## 5. The council: forecasting with LLMs

| Paper | Finding | Implication for us |
|---|---|---|
| Tetlock & Gardner (2015), *Superforecasting*; Mellers et al. (2014), *Psych. Sci.* `[m]` | Granular probabilities, reference classes (base rates first), teaming and training beat raw expertise. | Ask the council for a probability with a stated reference class, not only a 4-level label. Feed the base rate (the miss-baserate ledger, the gate's pass rate) into the pack. |
| Satopää et al. (2014), "Combining multiple probability predictions using a simple logit model", *IJF* `[m]` | Averaged forecasts are under-confident; extremizing the aggregate improves Brier. | When the three roles each give a probability, aggregate and extremize, then score that (forward only). |
| Schoenegger et al. (2024), "Wisdom of the silicon crowd", *Science Advances* `[v]` | A 12-LLM ensemble matched a 925-human crowd on 31 questions; LLMs show acquiescence bias; seeing the human median improved them 17–28%. | Ensembles beat single judges, and role biases are real (our adversary's falsifier-misuse tally). Heterogeneous models stay; a strategist-only verdict is the weakest form. |
| Halawi et al. (2024), "Approaching Human-Level Forecasting with Language Models" `[m]` | Retrieval plus LLM ensembling approaches crowd accuracy on live questions. | The pack *is* the retrieval layer; its quality (fresh markers, filings, pins) is where effort pays, as the 07-10 → 10-23 coverage outage showed. |
| Glasserman & Lin (2023), look-ahead bias in GPT-based return prediction `[m]` | LLM "predictions" on historical text leak training-data knowledge. | Confirms guardrail §6: never backtest the council. |

---

## 6. What this changes, in priority order

1. **More independent shots** (Bessembinder): top-K slot filling inside the gate, measured against the
   brain-off shadow book → draft D1.
2. **Keep names expressible**: the $1,000 cap → draft D3 (wide verticals; calibration v2 Rule V passed).
   The 540-day tenor failed Rule T and is not drafted.
3. **Losses smaller without capping the tail** (Kaminski & Lo): calibration v2 found neither falsifier
   salvage (at a = 0.7 accuracy) nor house-money rolls met their rules; the forward falsifier-accuracy
   ledger (D3b) measures what salvage would need.
4. **Our own IV history** (Goyal & Saretto, Vasquez, An et al.): graduate the gate's baseline and record
   term structure and ΔIV → draft D4.
5. **Deterministic driver and narration evidence** (DellaVigna & Pollet, Cohen & Frazzini, Lazy Prices,
   Ben-David et al., Greenwood et al.) → drafts D5 and D6.

**What the literature argues against:** relaxing the gate for throughput (Coval & Shumway), short-dated
lottery wings (Boyer & Vorkink), price stop-losses on the tail (Kaminski & Lo), buying a theme once its ETF
exists (Ben-David et al.), and any historical council replay (Glasserman & Lin).

## Sources checked on 2026-11-03
- Goyal & Saretto: https://academicnewsletter.sufe.edu.cn/info/357238
- Vasquez: https://ideas.repec.org/a/cup/jfinqa/v52y2017i06p2727-2754_00.html
- Ben-David et al.: https://nber.org/papers/w28369
- DellaVigna & Pollet: https://eml.berkeley.edu/~sdellavi/wp/demogr07-08-23AER.pdf
- Greenwood, Shleifer & You: https://www.nber.org/system/files/working_papers/w23191/w23191.pdf
- An, Ang, Bali & Cakici: https://ideas.repec.org/p/nbr/nberwo/19590.html
- Schoenegger et al.: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11800985/
- Kaminski & Lo: https://dspace.mit.edu/handle/1721.1/114876
- Boyer & Vorkink: https://ideas.repec.org/a/bla/jfinan/v69y2014i4p1485-1527.html
- Fang & Peress: https://ideas.repec.org/a/bla/jfinan/v64y2009i5p2023-2052.html
