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
from collections.abc import Collection
from dataclasses import dataclass

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
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


def authenticity_scan(texts: list[str], evidence: str, *, dates: Collection[str] | None = None) -> FilterResult:
    """Count quoted spans + numeric figures in ``texts`` that appear nowhere in ``evidence``.

    ``dates`` (#403, the council roles): each full ISO date in the text is checked WHOLE — accepted iff it is one of
    the dates the agent was shown, else ONE ``unsupported date`` flag — and taken out before the figure scan, so a
    cited filing date no longer sheds year/month/day fragments that miss the pool. The digit pool itself stays
    date-free (``fundamental_evidence_tokens``), so a fabricated bare number still flags. ``None`` keeps the
    pre-#403 scan unchanged (the discovery framer, whose runs carry no quote_filter stamp)."""
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
        body = t
        if dates is not None:
            for d in _ISO_DATE.findall(t):
                if d not in dates:
                    flagged += 1
                    details.append(f"unsupported date: {d}")
            body = _ISO_DATE.sub(" ", t)
        for n in _NUM.findall(body):
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
    return " ".join([pack.operator_thesis or "", getattr(pack, "framer_summary", None) or "",
                     getattr(pack, "operator_falsifier", None) or "", *pack.headlines,
                     *fundamental_evidence_tokens(pack), *catalyst_evidence_strings(pack)])


def rendered_dates(pack) -> frozenset[str]:
    """Every full ISO date in the prompt block the agent was shown (fundamentals period/filed, catalyst event and
    pin dates, dated marker lines, the falsifier's deadline, ...) — what a council role may cite as a date (#403)."""
    return frozenset(_ISO_DATE.findall(pack.as_prompt_block()))


def apply_filter(texts: list[str], pack, *, confidence: str,
                 accept_rendered_dates: bool = False) -> tuple[str, FilterResult]:
    """Returns (possibly-dampened confidence, FilterResult). Ungrounded pack → NEUTRAL backstop.
    ``accept_rendered_dates`` (#403): the council's three roles pass True — see ``authenticity_scan``."""
    if not pack.grounded:
        return "NEUTRAL", FilterResult(0, ["ungrounded — early exit"])
    res = authenticity_scan(texts, evidence_text(pack),
                            dates=rendered_dates(pack) if accept_rendered_dates else None)
    conf = dampen(confidence) if res.flagged > 0 else str(confidence or "").strip().upper()
    return conf, res
