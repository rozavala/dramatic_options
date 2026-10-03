# 2026-10-03 — Shared live account: capital, reserve and coordination (operator decision)

**Operator's word (2026-10-03):** *"Let's document that for a 100k base we need around 10k funds, but for
now we don't need funds as it's still paper trading. And let's keep moving and coordinating with the rest
of the projects."*

## Decision
- **Capital base:** unchanged, `convexity_book.account_equity = $100,000` (frozen frame, PREREG_THEMATIC_CONVEXITY §5).
- **Live funding when armed:** about **$10,000**, the frame's maximum premium-at-risk (10% book). It is a
  separate, disjoint slice of the shared account, added at T4 arming, never overlapping alpha_options'
  allocation.
- **Now:** no funding. Dramatic Options is paper-only (live trading gated; PROD inert until T4).
- **Reserve left for alpha_options:** `safety.shared_account_reserve_usd = $5,250` (its declared max risk).
  The live broker enforces it on every buy.

## Why $10k, not "a couple of thousand"
| Capital base | Funding (10% book) | Per-name cap | Contracts booked to date that fit |
|---|---|---|---|
| $100k (kept) | $10,000 | $1,000 | all (by construction: the books never took a contract over $1,000) |
| $50k | $5,000 | $500 | ~60% |
| $20k | $2,000 | $200 | ~30% |

The book's use today is one open position (PL, $690), but the frame allows up to 15 positions and $10k.
A smaller base would be a frozen-frame amendment that segments the record. Below ~$50k most contracts
stop fitting the per-name cap and the book stops being a portfolio of small convex bets.

## Why disjoint, not shared, cash
Our premium spend and alpha_options' spread margin draw on the same buying-power pool. Overlapping
allocations would let a joint drawdown cause a buying-power rejection, possibly on one of alpha_options'
closes. Disjoint slices satisfy: our book cap + alpha_options' $5,250 ≤ the account's cash.

## Coordination
Contract: rozavala/finance#947. This project's row: prefix `do-`; single-name options on its thematic
universe only; never SPY/XSP/SPX/SPXW; pre-open foreign-quantity check; $5,250 reserve respected;
base $100k / ~$10k funding at arming. Code: PR #281 (PREREG_REAL_MONEY_BROKER §3a). Open: venue-named env
keys (finance#947 §5), a separate coordinated deploy.
