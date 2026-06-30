"""424B5 prospectus deal-size extractor (FSSD plan §8b, #3 — recall-measured, best-effort).

The supply-shock *magnitude* (shares offered ÷ float) is arguably the core FSSD variable, but
it lives in the free-text prospectus supplement (heterogeneous HTML/text), so extraction is
**best-effort with imperfect recall** — which is exactly why the audit *measures* recall against
``deal_size.min_recall`` and cross-checks against the deterministic XBRL shares-out delta
(:func:`data.shares_out.shares_out_delta`). If neither path clears the recall floor, size-
conditioning is dropped for v1 and friction carries the gate (PREREG §3).

Pure parsing here (``parse_offering_size``) so it is offline-testable on fixtures; the fetch
side reuses :class:`data.filings.EdgarClient` HTTP discipline. No returns computed.
"""

from __future__ import annotations

import re
from typing import Any

# "12,500,000 shares" / "up to 4,000,000 shares of common stock"
_SHARES = re.compile(
    r"(?:up to\s+)?([0-9][0-9,]{3,})\s+shares\s+of\s+(?:our\s+)?common\s+stock",
    re.IGNORECASE,
)
# "$15.00 per share" / "public offering price of $7.25 per share"
_PRICE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,4})?)\s*per\s+share", re.IGNORECASE)
# "aggregate offering price of $50,000,000" / "gross proceeds of $25.0 million"
_GROSS = re.compile(
    r"(?:aggregate offering price|gross proceeds|aggregate principal amount)[^$]{0,40}"
    r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(million|billion)?",
    re.IGNORECASE,
)


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_offering_size(text: str) -> dict[str, Any] | None:
    """Best-effort {shares, price, gross_usd} from prospectus text, or None if nothing found.

    Recall over precision (the audit only needs presence/absence to score recall): takes the
    first plausible shares count and per-share price near the top of the document; computes
    gross = shares×price when both present, else falls back to an explicit aggregate/gross line.
    """
    head = text[:200_000]  # the cover/summary carries the terms; cap work on huge filings
    shares = price = gross = None

    m = _SHARES.search(head)
    if m:
        shares = _num(m.group(1))
    m = _PRICE.search(head)
    if m:
        price = _num(m.group(1))
    if shares is not None and price is not None:
        gross = shares * price
    else:
        mg = _GROSS.search(head)
        if mg:
            val = _num(mg.group(1))
            scale = {"million": 1e6, "billion": 1e9}.get((mg.group(2) or "").lower(), 1.0)
            gross = val * scale

    if shares is None and price is None and gross is None:
        return None
    return {"shares": shares, "price": price, "gross_usd": gross}


def offering_vs_float(shares: float | None, shares_out: float | None) -> float | None:
    """Offered shares as a fraction of shares outstanding (the supply-shock magnitude). None if
    either is missing or shares_out ≤ 0."""
    if shares is None or shares_out is None or shares_out <= 0:
        return None
    return shares / shares_out


# ── offering-TYPE classification (FSSD §3's v1.1 "primary/secondary/ATM split", built here for
# the EDGAR-event funnel's routine-takedown drop) ─────────────────────────────────────────────
# KEEP-BIASED, COVER-LOCALIZED. The discriminating signal is the cover OFFERING DESCRIPTION, not
# document-wide keyword presence: grounded on real 424B5 covers (2026-06), a lone-keyword OR has
# terrible precision — risk-factor "from time to time" (Creative Realities/Mizuho), a passing
# mention of an *existing* ATM program (Curbline/American Homes REIT forwards), and notes-prospectus
# list items ("…at-the-market offerings, or other recapitalizations…", Jefferies) all false-fire.
# The funnel's only DROP is a clean, conflict-free ATM cover; everything ambiguous is KEPT for the
# human (step-3). A false "routine" = a wrongly-dropped candidate = toward a false World-2, the very
# error this asymmetry exists to prevent — so the ATM drop errs hard toward False.
_COVER_CHARS = 22_000  # the offering summary lives near the top; cap work + dodge risk-factor noise

_OFF_ATM = re.compile(
    r"at[- ]the[- ]market\s+offering"
    r"|equity distribution agreement"
    r"|open market sale agreement"
    r"|controlled equity offering"
    r"|sales agreement[^.]{0,90}(?:sales agent|acting as (?:our )?(?:sales )?agent|as (?:our )?agent)",
    re.IGNORECASE,
)
_OFF_FIRM_UW = re.compile(
    r"underwrit(?:er|ing)[^.]{0,170}(?:agreed to purchase|severally(?: and not jointly)? agreed)"
    r"|per\s+(?:share|pre[- ]funded warrant)[^.]{0,110}total[^.]{0,140}underwriting",
    re.IGNORECASE,
)
_OFF_NOTES = re.compile(
    r"aggregate principal amount[^.]{0,90}(?:notes|debentures|bonds)"
    r"|\$[\d,]+[^.]{0,40}%\s+(?:senior |subordinated )?notes due"
    r"|%\s+notes due\s+20",
    re.IGNORECASE,
)
_OFF_CONVERT = re.compile(r"convertible (?:senior |subordinated )?notes", re.IGNORECASE)
_OFF_SELLING = re.compile(
    r"selling (?:stock|security)holders?[^.]{0,150}(?:resale|may (?:offer|sell|resell)|from time to time)"
    r"|we will not receive any[^.]{0,50}proceeds",
    re.IGNORECASE,
)
_OFF_RDPIPE = re.compile(
    r"registered direct offering"
    r"|securities purchase agreement[^.]{0,150}(?:investors?|purchasers?|accredited)"
    r"|private placement[^.]{0,90}(?:pre[- ]funded|warrant|investor)",
    re.IGNORECASE,
)


def _offering_cover(text: str) -> str:
    """The cover/offering-summary region as plain text — strips tags (idempotent on already-plain
    text) and caps to the cover, where the offering DESCRIPTION lives."""
    t = re.sub(r"<[^>]+>", " ", text)
    t = re.sub(r"&[a-z#0-9]+;", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t)
    return t[:_COVER_CHARS]


def classify_offering(text: str) -> dict[str, Any]:
    """Classify a 424B5/S-1 cover into an offering kind, for the funnel's routine-takedown drop.

    Returns ``{kind, routine_drop, noise_flag, signals}`` where ``kind`` ∈ {``atm``,
    ``debt_notes``, ``convertible_notes``, ``selling_holder``, ``registered_direct``,
    ``firm_commitment``, ``unknown``}. ``routine_drop`` is True ONLY for a clean ``atm`` (the one
    keep-biased drop); ``noise_flag`` marks likely-noise kinds kept for step-3 triage. See the
    module note for why this is cover-localized and conflict-gated.
    """
    cover = _offering_cover(text)
    sig = {
        "atm": bool(_OFF_ATM.search(cover)),
        "firm_uw": bool(_OFF_FIRM_UW.search(cover)),
        "notes": bool(_OFF_NOTES.search(cover)),
        "convertible": bool(_OFF_CONVERT.search(cover)),
        "selling_holder": bool(_OFF_SELLING.search(cover)),
        "reg_direct_pipe": bool(_OFF_RDPIPE.search(cover)),
    }
    # A clean, conflict-free ATM cover is the ONLY routine DROP. Any conflicting structural signal
    # (an underwriting table, a notes offering, or a selling-holder/forward) means the ATM phrase is
    # a passing mention of an existing program, not THIS offering → keep for step-3.
    if sig["atm"] and not (sig["firm_uw"] or sig["notes"] or sig["selling_holder"]):
        kind = "atm"
    elif sig["notes"] and sig["convertible"]:
        kind = "convertible_notes"
    elif sig["notes"]:
        kind = "debt_notes"
    elif sig["selling_holder"] and not sig["firm_uw"]:
        kind = "selling_holder"
    elif sig["reg_direct_pipe"]:
        kind = "registered_direct"
    elif sig["firm_uw"]:
        kind = "firm_commitment"
    else:
        kind = "unknown"
    return {
        "kind": kind,
        "routine_drop": kind == "atm",
        "noise_flag": kind in ("debt_notes", "convertible_notes", "selling_holder", "registered_direct"),
        "signals": sig,
    }


def is_atm_offering(text: str) -> bool:
    """Keep-biased ATM / continuous-offering detector — the funnel's routine-takedown DROP gate.

    True ONLY on a clean, conflict-free cover ATM signal. A False keeps the name for step-3; a
    false-True wrongly drops a candidate (toward a false World-2), so this errs hard toward False.
    See :func:`classify_offering`.
    """
    return classify_offering(text)["kind"] == "atm"
