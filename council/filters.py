"""Quote-authenticity + numeric-grounding filter (T2) — re-implemented from Real Options.

Cheap, conservative guard against an agent manufacturing confidence: any **quoted span** or
**numeric figure** in an agent's prose that does NOT appear in the ContextPack evidence
(headlines + the operator thesis) is flagged as unsupported. Flagged claims **dampen** the
agent's confidence one level (and are counted into ``flagged_unsupported`` for the record).
Conservative by design — it only flags claims that appear *nowhere* in the evidence, so it does
not over-penalize legitimate reasoning. Full strip-from-prompt is an iterative upgrade.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_QUOTE = re.compile(r'"([^"]{4,})"')  # quoted spans of ≥4 chars (attributed claims)

_RANK = {"NEUTRAL": 0, "LOW": 1, "MODERATE": 2, "HIGH": 3, "EXTREME": 4}
_BY_RANK = {v: k for k, v in _RANK.items()}


@dataclass(frozen=True)
class FilterResult:
    flagged: int
    details: list[str]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _digits(s: str) -> str:
    return s.replace(",", "")


def authenticity_scan(texts: list[str], evidence: str) -> FilterResult:
    """Count quoted spans + numeric figures in ``texts`` that appear nowhere in ``evidence``."""
    ev = _norm(evidence)
    ev_compact = _digits(ev)
    flagged = 0
    details: list[str] = []
    for t in texts:
        if not t:
            continue
        for q in _QUOTE.findall(t):
            if _norm(q) not in ev:
                flagged += 1
                details.append(f'unsupported quote: "{q[:48]}"')
        for n in _NUM.findall(t):
            if _digits(n) not in ev_compact:
                flagged += 1
                details.append(f"unsupported figure: {n}")
    return FilterResult(flagged=flagged, details=details)


def dampen(confidence: str, levels: int = 1) -> str:
    """Lower a confidence by ``levels`` (clamped at NEUTRAL)."""
    r = _RANK.get(str(confidence or "").strip().upper(), 0)
    return _BY_RANK[max(0, r - levels)]


def evidence_text(pack) -> str:
    """The grounding corpus an agent's claims are checked against: the operator thesis + headlines
    + the §9 corpus numeric tokens (the formatted values + $M/margin figures + the trailing news
    counts — NOT the dates) + the FORWARD_CATALYSTS block's prose and §8 cite tokens (the channel
    prereg §3 extension — there the date IS the load-bearing figure; the asymmetry with the
    fundamentals no-dates rule is pinned, not an oversight). Without these pools, every figure an
    agent quotes from a rendered block — exactly the citations each corpus exists to enable —
    would flag as unsupported and dampen conviction (the PR #55 lesson, recursively)."""
    from council.context import catalyst_evidence_strings, fundamental_evidence_tokens
    return " ".join([pack.operator_thesis or "", *pack.headlines,
                     *fundamental_evidence_tokens(pack), *catalyst_evidence_strings(pack)])


def apply_filter(texts: list[str], pack, *, confidence: str) -> tuple[str, FilterResult]:
    """Returns (possibly-dampened confidence, FilterResult). Ungrounded pack → NEUTRAL backstop."""
    if not pack.grounded:
        return "NEUTRAL", FilterResult(0, ["ungrounded — early exit"])
    res = authenticity_scan(texts, evidence_text(pack))
    conf = dampen(confidence) if res.flagged > 0 else str(confidence or "").strip().upper()
    return conf, res
