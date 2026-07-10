"""The §6 paired-contrast instrument + §8 detectors — forward-catalyst channel, PR3.

PREREG_FORWARD_CATALYST_GROUNDING (frozen 2026-07-09). For each channel-grounded judgment
among the first M=8 eligible pairs, an ephemeral no-channel re-score of the SAME candidate
(block withheld, all else identical) gives the counterfactual. This module is the PURE logic —
arm classification, per-class eligibility, the two pinned detectors — so every §8 rule is
testable offline; the runnable probe (``scripts/probe_paired_contrast.py``) owns the live LLM
calls and the operator surface.

The §8 pins implemented here VERBATIM:

- **eligibility, per class** — a judgment counts iff the block RENDERED and: (a)/(c):
  ``0 < event_date − as_of ≤ 365d`` (or ≤ structure expiry when one exists — the probe has no
  structure, so 365d applies); (d): rendered ⇒ eligible (freshness is upstream §3 expiry).
- **flip** := at_inflection changes value between the arms ∨ (proposer abstention in the
  no-channel arm ∧ a deliberated tri-criteria judgment in the channel arm). The second disjunct
  IS adjudicability — the KMT-class conversion registers regardless of the verdict's sign.
- **cite** := ≥1 block-derived token in the channel arm's rationale text — detected with the
  SAME tokenizer the §3 filter extension carries (``context.catalyst_cite_tokens``; one
  definition, two consumers, zero drift).
- **reverse_conversion** (telemetry, §4/§8 completeness): deliberation in the no-channel arm ∧
  abstention in the CHANNEL arm — the one channel-HARM signature a flip count can't see.
  Counted, never a rule input.
- A pair where either arm is a parse_error / provider error / ungrounded early-exit is VOID —
  a malformed judgment is not a judgment; void pairs are recorded and excluded from the
  eligible-M denominator (never silently).

The M-rule disposition itself ((i)/(ii)/(iii) at M=8) is the OPERATOR's mechanical read over
the accrued ledger rows — this module records per-pair facts and never auto-acts (§6).
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

from council.context import catalyst_cite_tokens

ELIGIBLE_HORIZON_DAYS = 365  # §8 (a)/(c) upper bound; lower bound is ZERO (exclusive)

LEDGER_FIELDS = [
    "as_of", "symbol", "direction", "classes_rendered", "eligible", "eligible_classes",
    "void", "void_reason",
    "channel_kind", "channel_conviction", "channel_include", "channel_at_inflection",
    "nochannel_kind", "nochannel_conviction", "nochannel_include", "nochannel_at_inflection",
    "flip", "flip_via", "reverse_conversion", "cite", "cited_tokens", "cost_usd",
]


def classify_arm(proposal) -> dict:
    """One arm's §8-relevant facts from an in-memory ``CouncilProposal``.

    kind: ``deliberated`` (full tri-criteria roundtrip) · ``abstained`` (deliberated proposer
    NEUTRAL — the KMT face) · ``ungrounded`` (early-exit, no LLM) · ``error`` (provider error) ·
    ``parse_error`` (a malformed judgment — voids the pair; the #37/§10.9 discipline: never read
    a failure as an abstention)."""
    rat = proposal.rationale if isinstance(proposal.rationale, dict) else {}
    parse_error = any(isinstance(ao.raw, dict) and ao.raw.get("parse_error")
                      for ao in (proposal.agent_outputs or []))
    if parse_error:
        kind = "parse_error"
    elif "error" in rat:
        kind = "error"
    elif "strategist" in rat:
        kind = "deliberated"
    elif "ungrounded" in str(rat.get("dropped", "")):
        kind = "ungrounded"
    elif "abstained" in str(rat.get("dropped", "")):
        kind = "abstained"
    else:
        kind = "error"
    return {"kind": kind, "conviction": proposal.conviction, "include": proposal.include,
            "at_inflection": proposal.at_inflection}


def eligible_classes(items: list[dict], as_of: datetime) -> list[str]:
    """The §8 per-class eligibility over the RENDERED items. (d): rendered ⇒ eligible.
    (a)/(c): ``0 < event_date − as_of ≤ 365d`` (both bounds pinned; lower bound ZERO exclusive —
    a same-day event has no forward runway; near-dated stays in, v1's regression stays fixed)."""
    out: set[str] = set()
    for it in items:
        cls = it.get("class")
        if cls == "d":
            out.add("d")
        elif cls in ("a", "c"):
            try:
                ed = datetime.fromisoformat(it["event_date"])
            except (KeyError, TypeError, ValueError):
                continue
            delta = ed - as_of
            if timedelta(0) < delta <= timedelta(days=ELIGIBLE_HORIZON_DAYS):
                out.add(cls)
    return sorted(out)


def _rationale_text(proposal) -> str:
    """The channel arm's citable text: every agent raw + the strategist summary/weakest point.
    The cite detector searches THIS surface for block-derived tokens."""
    parts = [str(proposal.strategist_summary or ""), str(proposal.weakest_point or "")]
    for ao in (proposal.agent_outputs or []):
        parts.append(str(ao.raw))
    return " ".join(parts)


def pair_verdict(channel, nochannel, items: list[dict], as_of: datetime) -> dict:
    """The §8 detectors over one (channel, no-channel) proposal pair. Pure + mechanical —
    no textual judgment. Returns the per-pair facts the ledger records."""
    ch, nc = classify_arm(channel), classify_arm(nochannel)
    void_kinds = ("parse_error", "error", "ungrounded")
    void = ch["kind"] in void_kinds or nc["kind"] in void_kinds
    void_reason = ""
    if void:
        void_reason = f"channel={ch['kind']} nochannel={nc['kind']}"

    rendered = bool(items)
    elig = eligible_classes(items, as_of) if rendered else []
    eligible = rendered and bool(elig) and not void

    flip = False
    flip_via = ""
    if not void:
        if (ch["kind"] == "deliberated" and nc["kind"] == "deliberated"
                and ch["at_inflection"] != nc["at_inflection"]):
            flip, flip_via = True, "value_change"
        elif nc["kind"] == "abstained" and ch["kind"] == "deliberated":
            # The second disjunct IS adjudicability (verdict-sign-independent) — the KMT face.
            flip, flip_via = True, "conversion"
    reverse_conversion = (not void and nc["kind"] == "deliberated" and ch["kind"] == "abstained")

    tokens = catalyst_cite_tokens(items)
    text = _rationale_text(channel)
    cited = sorted({t for t in tokens if t in text})

    return {
        "as_of": as_of.isoformat(), "symbol": channel.symbol, "direction": channel.direction,
        "classes_rendered": "|".join(sorted({str(i.get("class")) for i in items})),
        "eligible": eligible, "eligible_classes": "|".join(elig),
        "void": void, "void_reason": void_reason,
        "channel_kind": ch["kind"], "channel_conviction": ch["conviction"],
        "channel_include": ch["include"], "channel_at_inflection": ch["at_inflection"],
        "nochannel_kind": nc["kind"], "nochannel_conviction": nc["conviction"],
        "nochannel_include": nc["include"], "nochannel_at_inflection": nc["at_inflection"],
        "flip": flip, "flip_via": flip_via, "reverse_conversion": reverse_conversion,
        "cite": bool(cited), "cited_tokens": "|".join(cited),
        "cost_usd": round(float(channel.cost_usd or 0) + float(nochannel.cost_usd or 0), 4),
    }


def append_pair_row(path: str, row: dict) -> None:
    """Append one pair to the durable ledger (``records/forward_catalyst_pairs.csv`` — the
    gate_baserate_surfaced.csv precedent: a git-tracked CSV the operator reads at M, never a DB
    migration). Header written once; fields pinned by ``LEDGER_FIELDS``."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in LEDGER_FIELDS})
