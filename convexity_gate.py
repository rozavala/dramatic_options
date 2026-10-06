"""The IV / cheap-convexity gate (T1) — the edge, as a hard deterministic veto.

PREREG_THEMATIC_CONVEXITY §4. We have **no historical options IV** (forward-only chains),
so "cheap" cannot be an IV-rank against the name's own IV history. Instead we measure
cheapness from one **current chain snapshot** plus the underlying's **trailing realized
vol** (computable from the bars we already hold):

  - **IV/RV ratio** ``IV_atm / RV_h`` ≤ ``iv_rv_max`` — ATM vol isn't richly bid over what
    the name actually realizes (a variance-risk-premium proxy).
  - **OTM skew premium** ``IV(wing) − IV_atm`` (vol points) ≤ ``otm_skew_max_volpts`` — the
    far-OTM wing we are *buying* isn't already bid up, even if ATM looks calm.

Pass ⇔ both hold. **Fail-closed:** any missing input (RV, ATM IV, wing IV) → NOT cheap →
veto. Pure functions — no I/O, offline-testable. The council can never override this.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Contract:
    """A normalized option contract from a current chain snapshot.

    ``iv`` is annualized implied vol as a decimal (e.g. 0.65 = 65%). ``oi`` (open interest)
    may be ``None`` when the feed omits it (Alpaca's chain snapshot does).
    """

    symbol: str
    expiry: date
    kind: str  # "C" or "P"
    strike: float
    bid: float | None = None
    ask: float | None = None
    iv: float | None = None
    oi: int | None = None
    delta: float | None = None


@dataclass(frozen=True)
class GateVerdict:
    cheap: bool
    iv_rv_ratio: float | None
    otm_skew_volpts: float | None
    atm_iv: float | None
    wing_iv: float | None
    rv: float | None
    reasons: tuple[str, ...]


def realized_vol(closes: list[float] | None, *, window: int, annualization: float = 252.0) -> float | None:
    """Annualized close-to-close realized vol over the trailing ``window`` returns.

    Returns ``None`` (→ gate fail-closed) if there aren't enough usable closes. Uses the
    last ``window + 1`` positive closes; sample std (ddof=1) of log returns × √annualization.
    """
    if not closes:
        return None
    px = [c for c in closes if c is not None and c > 0]
    if len(px) < 3:
        return None
    if window + 1 < len(px):
        px = px[-(window + 1):]
    rets = [math.log(px[i] / px[i - 1]) for i in range(1, len(px))]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(annualization)


def occ_root(contract_symbol: str) -> str:
    """The OCC option root: everything before the fixed 15-char tail (YYMMDD + C/P + 8-digit
    strike). A root that differs from the underlying ticker (e.g. ``CDE2``) is a
    corporate-action-ADJUSTED class: non-standard deliverables (a different payoff object —
    calibration finding #3) and unquotable on the loop's underlying-keyed endpoints (the
    2026-07-06 3A/CDE2 mark failure). Lives here (not ``structure``) because ``structure``
    imports from this module; ``structure.occ_root`` re-exports it."""
    return str(contract_symbol)[:-15].upper()


def atm_iv(chain: list[Contract], underlying_price: float | None, kind: str, expiry: date,
           *, root: str | None = None) -> float | None:
    """IV of the nearest-the-money contract of ``kind`` at ``expiry`` (or None).

    ``root``: when given, contracts whose OCC root differs are EXCLUDED before the
    nearest-strike scan — an adjusted class's nominal strike is a different payoff object, and
    its feed IV is computed against the WRONG deliverable, so one adjusted contract sitting
    nearest the money corrupts BOTH gate legs (iv_rv and skew). Live 2026-07-07 (dual-read
    material-flip page, run #458): CDE spot 16.04 → nearest 2027-01-15 call was
    ``CDE1270115C00017000`` iv=2.74 (274%) vs the standard-class ``CDE270115C00015000``
    iv=0.70 → OPRA read iv_rv 4.00 / skew −222vp on a clean 0.98 name."""
    if not underlying_price or underlying_price <= 0:
        return None
    cands = [c for c in chain if c.kind == kind and c.expiry == expiry and c.iv and c.iv > 0
             and (root is None or occ_root(c.symbol) == root)]
    if not cands:
        return None
    best = min(cands, key=lambda c: abs(c.strike - underlying_price))
    return best.iv


def is_cheap_convexity(
    chain: list[Contract],
    *,
    underlying_price: float | None,
    wing: Contract,
    rv: float | None,
    iv_rv_max: float,
    otm_skew_max_volpts: float,
) -> GateVerdict:
    """Evaluate the gate for a chosen ``wing`` contract against its ATM peer + realized vol.

    Fail-closed: any missing input → ``cheap=False``.
    """
    reasons: list[str] = []
    wing_iv = wing.iv
    # ATM peer restricted to the wing's own OCC class: the wing is always standard-class
    # (structure.select_structure filters adjusted roots), so this keeps adjusted-class contracts
    # out of the ATM read too — the 2026-07-07 residual of the CDE2 defect (#160 guarded
    # select_structure; the gate's ATM estimator was the remaining unfiltered chain reader).
    a_iv = atm_iv(chain, underlying_price, wing.kind, wing.expiry, root=occ_root(wing.symbol))

    if rv is None or rv <= 0:
        reasons.append("no_realized_vol")
    if a_iv is None:
        reasons.append("no_atm_iv")
    if wing_iv is None or wing_iv <= 0:
        reasons.append("no_wing_iv")
    if reasons:
        return GateVerdict(False, None, None, a_iv, wing_iv, rv, tuple(reasons))

    iv_rv = a_iv / rv
    skew_vp = (wing_iv - a_iv) * 100.0
    if iv_rv > iv_rv_max:
        reasons.append(f"iv/rv {iv_rv:.2f} > {iv_rv_max:.2f} (vol richly bid vs realized)")
    if skew_vp > otm_skew_max_volpts:
        reasons.append(f"otm_skew {skew_vp:.1f}vp > {otm_skew_max_volpts:.1f}vp (wing already bid up)")

    cheap = not reasons
    if cheap:
        reasons.append(f"cheap: iv/rv {iv_rv:.2f}≤{iv_rv_max:.2f} and skew {skew_vp:.1f}vp≤{otm_skew_max_volpts:.1f}vp")
    return GateVerdict(cheap, iv_rv, skew_vp, a_iv, wing_iv, rv, tuple(reasons))
