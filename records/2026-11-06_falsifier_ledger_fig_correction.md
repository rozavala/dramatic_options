# Falsifier ledger — correction note for the FIG read (2026-11-06, #429)

**What the ledger says.** The first sealed read of the D3b forward falsifier-accuracy ledger (L1 #1952,
2026-11-05) is:

```
2026-11-05,design_software_ai.q3_2026_rev,design_software_ai,FIG,bullish,quarterly_revenue_yoy,0.3,2025-09-30,2026-11-04,0.3803,0,18.53
```

**What it should say.** The spec names FIG's Q3-2026 revenue growth, threshold 30%. The 11-04 10-Q reports
Q3-2026 at $391.415M against $274.173M a year earlier, so the read is:

| field | sealed | correct |
|---|---|---|
| `period_end` | 2025-09-30 | **2026-09-30** |
| `value` | 0.3803 | **0.4276** |
| `fired` | 0 | 0 (unchanged) |
| `read_at`, `filed`, `entry_close` | 2026-11-05, 2026-11-04, 18.53 | unchanged |

**Why.** That 10-Q also carries the year-ago comparative quarter (Q3-2025). The XBRL extractor keeps the
latest filing per period, so both quarters read as filed 2026-11-04. `first_quarter_after` then broke the
filing-date tie by the earliest period end and picked the comparative. #429 fixes the selection to the newest
period on the first qualifying filing date, so later reads (KKR, STUB, NTSK) take the reported quarter.

**The row stays as sealed.** The ledger is append-only and read once per spec × name, so the row is not
rewritten. Read the FIG row with this note.

**What this does not change.** The accuracy and false-alarm counts use only `fired`, the direction and the
250-bar outcome from `entry_close`. `fired` is 0 under both values (both are above 0.30) and the close is the
same, so no count moves. No spec, threshold or frozen number changes; `falsifier_specs.json` is untouched.

**Found by** the 2026-11-05 nightly grade (F1), reproduced from the cached companyfacts
(`CIK0001579878.json`), and filed as #429 by /triage on 2026-11-06.
