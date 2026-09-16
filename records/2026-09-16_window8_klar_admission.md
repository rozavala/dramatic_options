# 2026-09-16 — Window #8 (off-cycle): KLAR admission under the operator's 2026-09-16 word

## Decision provenance (TRUE form)

**Operator word (2026-09-16 ~00:15 UTC):** "I would merge 245, admit KLAR, register the 143 name
bench table, and do #4 and 5 too. If that's your recommendation." — given on the W37 reach survivor
card (`records/cards/2026-W37.md`, machine_surfaced_machine_drafted) presented 2026-09-13, and on
the 2026-09-15 open-items list where KLAR was named as awaiting a thesis window. The in-window screen
(13:30–20:00 UTC) is the read of record; two reads pre-declared for Wed 2026-09-16: **13:37 UTC**
(admit if in band) and **15:07 UTC** (the LAST read of the day — anti-camping, no re-reads after).
Thesis below is CC-drafted in true form; the operator adopts by not amending before execution (the
2026-07-14 convention: AI-drafted, operator-adopted — never presented as a blind pin).

## KLAR — Klarna Group plc · basket/cluster `bnpl_payments` (NEW theme #14 — no thesis was on file; KLAR entered via the orphan new-listings watch, W37)

- **How it surfaced:** `orphan_watch/424B4` — Klarna's 2025-09-10 IPO prospectus (CIK 2003292); the
  options class is now listed, which is what made the tenor expressible. Single authoritative
  channel (a filing), corroborated by the item symbol — not a homonym artifact (the PG/ROAD class
  the #245 guard now blocks).
- **Thesis (structural, bullish):** a consumer-payments network whose top line is compounding while
  the equity has been de-rated as a busted IPO. FY-2025 revenue $3,509M vs $2,811M, **+24.8% y/y**
  (annual filing, period 2025-12-31, filed 2026-02-26 — the only filed-XBRL line in the corpus for
  this name so far). Trailing return −69.8% over 12 months and −27.7% over the last month against
  that growth is the price/fundamentals divergence the mandate looks for: a payments-network
  business with merchant-side scale re-rates discontinuously when growth durability is believed,
  and the US options chain on a ~$14 stock makes the 15–35% OTM 6–12mo call expressible at one
  contract inside the frozen $1,000 per-name cap.
- **Convexity setup:** a 6–12mo far-OTM call as runway for the re-rate; hold-the-tail (OTM sleeve
  rules unchanged).
- **Falsifier (as drafted on the card, adopted):** the thesis is invalidated if the first quarterly
  report dated after 2026-09-13 shows quarterly revenue growth below +10% y/y.
- **Pinned caveats (honest):** (1) the corpus carries ONE fundamentals line — the council will
  ground on markers + this line until 10-Q coverage fills, so `under_narrated`/`at_inflection` may
  fail for evidence-thinness rather than on the merits (a datum about the seam, as with FIG/MRK);
  (2) BNPL is a credit business in a consumer-credit cycle — losses, funding cost and regulation are
  the exogenous risks a payments-network framing understates; (3) heavy post-IPO sponsor/insider
  supply; (4) the card's own draft leaned on "cheap participation ($142 vs $1,000)" — **that clause
  is struck**: cheapness is the IV gate's job and is FORBIDDEN as an admission criterion; admission
  is feasibility-only (band fit, cap fit, tenor, spread, ADV).
- **Cluster routing:** `bnpl_payments` = a consumer-payments/BNPL network driver shared with NO
  existing cluster (not alt_capital_deployment — KKR is a capital-deployment platform, not a
  consumer-credit network; not design_software_ai). FOURTEEN clusters; the book still fills at most
  5; cluster_fraction 0.02 unchanged.

## The screen — pre-declared in-window reads (the LAST read governs if the first is out of band)

| read (UTC) | contract | spot | achieved OTM | dte | $/contract | spread | ADV | band | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-13 provisional (card, outside the window) | KLAR270319C00017500 | $13.83 | 26.5% | 187 | $142 | — | $138.5M | in | provisional only |
| 2026-09-16 13:37 | _pending_ | | | | | | | | |
| 2026-09-16 15:07 (LAST) | _only if 13:37 is out of band_ | | | | | | | | |

## Decision

_pending the in-window read._

## Changes in this PR (additive-only) — filled at execution

- `config.json` `universe.themes` += `_comment_window8` + `bnpl_payments: ["KLAR"]`;
  `convexity_book.clusters` += `bnpl_payments: ["KLAR"]` + the by-driver `_comment` WINDOW #8 sentence.
- `universe_register.json` += `themes.bnpl_payments` (provenance operator) + `windows.8` (string-spliced).
- This record.
