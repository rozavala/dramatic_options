# 2026-09-21 — Window #9 (off-cycle): NTSK + STUB admission under the operator's 2026-09-21 word

## Decision provenance (TRUE form)

**Operator word (2026-09-21 ~04:10 UTC):** "Let's include both survivors and let's fix the issues we are
getting from the incorrect feeds." — given on the W38 reach survivors presented 2026-09-20
(`records/cards/2026-W38.md`, both `machine_surfaced_machine_drafted`). The in-window screen
(13:30–20:00 UTC) is the read of record; two reads are pre-declared for **Mon 2026-09-21: 13:37 UTC**
(admit whichever prints in band) and **15:07 UTC — the LAST read of the day** (anti-camping, no re-reads
after). Theses below are CC-drafted in true form from the cards' cited evidence; the operator adopts by
not amending before execution (the 2026-07-14 convention: AI-drafted, operator-adopted — never a blind pin).

Both names reached the operator through the **orphan new-listings watch** (a 424B4 plus a newly listed
options class) — the same door as FIG and KLAR, and on the evidence so far the one reach channel that
yields. Both are 2025 IPOs, so the filed-XBRL corpus is thin: the council will ground on markers plus the
lines below until 10-Q coverage fills. An evidence-thin council read is expected and is a datum about the
seam, not a verdict on the thesis (the FIG/MRK/KLAR precedent).

## NTSK — Netskope Inc · basket/cluster `cyber_sase` (NEW theme #15)

- **How it surfaced:** `orphan_watch/424B4` — Netskope's 2025-09-18 IPO prospectus (CIK 2063196); the
  options class is now listed, which is what made the tenor expressible. Item-symbol corroborated.
- **Thesis (structural, bullish):** the security perimeter is being rebuilt around the identity-and-edge
  model (SASE/SSE), and Netskope is compounding through that shift while the market still prices it as one
  more post-IPO security name. Quarterly revenue $220.5M, **+29.1% y/y**, with gross margin expanding
  **+1.7pts to 73.9%** — growth that is not being bought with unit economics (period 2026-07-31, filed
  2026-09-02). Quarterly capex rose to $13.0M from $1.6M, a platform build-out rather than a maintenance
  spend. A security platform re-rates discontinuously when the market accepts that its growth is a
  category shift rather than a displacement trade, and the long-dated call is runway for that acceptance.
- **Falsifier (as drafted, adopted):** quarterly revenue growth in the next 10-Q falls below +20% y/y
  against the 2026-07-31 baseline.
- **Pinned caveats (honest):** (1) **`under_narrated` will very likely FAIL** — a 2025 IPO in the most
  covered category in enterprise software is not a quiet name (the FIG precedent; that is the seam working);
  (2) the capex surge is read here as a build-out, but it can equally be the start of a margin problem —
  the falsifier keys on revenue, so this caveat is not falsifiable by the pinned test and must be watched
  separately; (3) one filed quarter in the corpus, no analyst count, no 12-month price history;
  (4) lock-up and secondary supply from a September-2025 IPO.
- **Cluster routing:** `cyber_sase` = a network-security platform driver shared with **no** existing
  cluster. Not `design_software_ai` (an AI-design-tool bet), not `ai_capex_power` (the power-demand bet) —
  routing it into either would misprice the correlation budget.

## STUB — StubHub Holdings, Inc. · basket/cluster `live_events_marketplace` (NEW theme #16)

- **How it surfaced:** `orphan_watch/424B4` — StubHub's 2025-09-17 IPO prospectus (CIK 1337634); options
  class now listed. Item-symbol corroborated.
- **Thesis (structural, bullish):** a two-sided live-events marketplace whose volume keeps compounding
  while the equity has round-tripped its IPO. Quarterly revenue **$573.1M, +33.2% y/y** (period
  2026-06-30, filed 2026-08-13) against a **−73.1% twelve-month** price return and −14.7% over the last
  month. Marketplace economics are convex when they turn: fixed platform cost against take-rate on rising
  volume, so the market's re-rating of a marketplace it has written off is discontinuous rather than
  gradual. The price/fundamentals divergence is the convexity setup.
- **Falsifier (as drafted, adopted):** the quarter reported after 2026-09-30 shows revenue growth below
  +10% y/y.
- **Pinned caveats (honest):** (1) a −73% tape is **information, not only sentiment** — the market may be
  pricing take-rate compression, the competitive squeeze from Ticketmaster/SeatGeek, or regulatory
  attention to ticketing fees, none of which the revenue line refutes; (2) live events are consumer
  discretionary, so the thesis carries a cycle risk the growth number does not show; (3) one filed quarter
  in the corpus, no analyst count; (4) post-IPO insider supply.
- **Cluster routing:** `live_events_marketplace` = a live-events/ticketing marketplace driver shared with
  **no** existing cluster. Not `bnpl_payments` (KLAR is a consumer-credit network; STUB's driver is event
  demand and take rate, not credit), not `design_software_ai`.

## The screen — pre-declared in-window reads (the LAST read governs only if the first is out of band)

| read (UTC) | symbol | contract | spot | achieved OTM | dte | $/contract | spread | ADV | band | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-20 provisional (card, outside the window) | NTSK | NTSK270416C00022500 | $17.49 | 28.6% | 208 | $288 | — | $110.1M | in | provisional only |
| 2026-09-20 provisional (card, outside the window) | STUB | STUB270416C00007500 | $5.92 | 26.7% | 208 | $75 | — | $39.6M | in | provisional only |
| 2026-09-21 13:37 | NTSK | _pending_ | | | | | | | | |
| 2026-09-21 13:37 | STUB | _pending_ | | | | | | | | |
| 2026-09-21 15:07 (LAST) | _only for a name whose 13:37 read is out of band_ | | | | | | | | | |

## Decision

_pending the in-window read._

## Changes at execution (additive-only)

- `config.json` `universe.themes` += `_comment_window9` + `cyber_sase: ["NTSK"]` + `live_events_marketplace: ["STUB"]`;
  `convexity_book.clusters` += both (#15, #16) + the by-driver `_comment` WINDOW #9 sentence.
- `universe_register.json` += `themes.cyber_sase`, `themes.live_events_marketplace` (provenance operator)
  + `windows.9`, string-spliced (NEVER json.dump).
- This record.
