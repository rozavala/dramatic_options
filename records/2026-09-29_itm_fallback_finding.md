# 2026-09-29 — Finding: the structure selector can pick in-the-money contracts on thin chains (read-only investigation)

## Provenance

Surfaced by the L1 #1472 grade (2026-09-28): the brain-off shadow book and the no-gate 3A book each booked a deep
in-the-money put. The operator asked for verification before deciding (2026-09-29: "Sure"). Everything below is
read-only: the live option chain (last quotes from the 2026-09-28 close, a few minutes after the 19:45 UTC booking —
the only caveat), the selector source, and the book tables. **Nothing was changed.**

## What was booked

| book | contract | strike | spot at entry | moneyness | premium |
|---|---|---|---|---|---|
| shadow + 3A | STUB270416P00007500 | $7.50 | $5.265 | **+0.42 (in the money)** | 4 × $250 |
| shadow + 3A | KLAR270820P00017500 | $17.50 | $12.415 | **+0.41 (in the money)** | 1 × $620 |

All 15 earlier bearish null-book positions were proper puts about 25% out of the money (moneyness −0.17 to −0.29).

## The mechanism, verified on the chain

`structure.select_structure` targets a strike 25% out of the money (a put at 0.75 × spot) and then picks the
**eligible** contract whose strike is closest to that target. **It has no limit on which side of the money that
contract may be.** Eligibility (`contract_eligible`) requires a two-sided quote, a relative spread ≤ 25%, a mid ≥ $0.10
and OI ≥ 50 when reported.

- **STUB** (spot $5.30, target put strike $3.97). The tenor window holds only five puts, all April 2027, spaced
  $2.50 apart: $2.50 has no bid (and a $0.05 mid); $5.00 is 6% out of the money and was rejected at **exactly** the
  25% spread limit (see the float note below); $7.50, $10.00 and $12.50 are all in the money and all eligible. The
  nearest eligible strike to $3.97 is $7.50, 42% in the money.
- **KLAR** (spot $12.41, target $9.31). Every out-of-the-money put fails: $10.00 at spreads of 88% (May) and 157%
  (August), $7.50 at 187% or no bid, lower strikes no bid. On the August expiry the only eligible puts are $17.50
  (16% spread, 41% in the money) and $25.00. The selector took $17.50.

**The structural bias:** on a low-priced or thinly traded chain, out-of-the-money options cost tens of cents and
carry wide relative spreads, so a percentage-spread limit rejects them, while in-the-money options (bigger premium,
tighter relative spread) pass. The selector then takes the nearest survivor, which can be on the wrong side.

## Why it matters

- **It breaks the frozen frame.** `PREREG_THEMATIC_CONVEXITY` expresses theses with "long-dated (6–12 month),
  far-OTM, defined-risk options" and carves in-the-money positions out into a **separately pre-registered ITM
  sleeve** with its own financing / extrinsic gate, noting that the skew test "would mis-fire on ITM by put-call
  parity". These puts passed the cheapness gate the frame says does not apply to them.
- **It biases the null books, which are the yardstick for the council.** An in-the-money option has a far lower
  convex tail; the shadow/3A tails are pulled down, which flatters the real book in the real−shadow read.
- **The real book shares the path.** `paper_loop` calls the same selector with the same eligibility, so a council
  include on STUB or KLAR bearish would have bought the same put. Latent only because nothing has reached the gates.

## How widespread (every options book, 2026-09-29)

| book | positions | wrong side of the money | right side, under 15% out of the money |
|---|---|---|---|
| real (`convexity_positions`) | 1 | 0 | 0 |
| shadow | 42 | 2 (the two puts above) | 3 (HBM +0.11, FRO +0.11, TGB +0.15) |
| 3A + 3B (`fixed_basket_positions`) | 81 | **4**: the two puts above (3A), plus **UROY270115C00002500 −0.17 (3B, 2026-06-10)** and **STUB270416C00005000 −0.08 (3B, 2026-09-27)** | 5 |

So the class is recurring on low-priced / coarse chains (UROY in June, STUB on 09-27 and 09-28), not a one-night event.

## A separate small bug found on the way

STUB's $5.00 put quoted $0.70 / $0.90: a relative spread of exactly 25%, which computes as `0.25000000000000006` and
fails `sp > 0.25`. A contract at exactly the limit is rejected by floating-point rounding (the same class as the
spend-tripwire boundary fixed earlier with a `+ 1e-9` tolerance). It did not cause the in-the-money pick — that
put is only 6% out of the money anyway — but it is a real boundary defect.

## Options for the operator (2026-09-30 review) — nothing is changed without the word

1. **A side guard in `select_structure` (recommended, as a conformance fix):** never select a contract on the wrong
   side of the money; if no eligible out-of-the-money contract exists, return no structure (fail-closed). This only
   enforces what the frozen frame already says, and applies to every options book, the real one included.
2. **Optionally, the admission band on the live path too** (achieved 15–35% out of the money): stricter, would
   also have excluded the eight near-the-money positions, and reduces expressability on coarse chains. A judgment
   call beyond conformance.
3. **The floating-point tolerance** on the spread limit (`sp > max + 1e-9`).
4. **The six existing wrong-side positions:** tag them as outside the frame and report every tail read with and
   without them. Never delete a position.
5. **Record segmentation:** any change to selection is a segment boundary for the null books (stamp it, as the
   direction-coherence rule was).
