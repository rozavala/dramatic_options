"""The §6 paired-contrast harness + §8 detectors (forward-catalyst channel, PR3). Offline.

Every §8 rule pinned mechanical: per-class eligibility bounds (hand-checked dates), BOTH flip
disjuncts, reverse_conversion, the shared-tokenizer cite detector, void-on-malformed (the #37
discipline: a failure never reads as an abstention), and the ledger append shape.
"""

import csv
from datetime import datetime

from council.paired_contrast import (
    LEDGER_FIELDS,
    append_pair_row,
    classify_arm,
    eligible_classes,
    pair_verdict,
)
from council.proposal import AgentOutput, CouncilProposal

AS_OF = datetime(2026, 7, 15, 19, 45)


def _ao(role="proposer", raw=None):
    return AgentOutput(role, "fake", "fake-m", "LOW", "bullish", None, raw or {})


def _prop(*, kind="deliberated", at_inflection=False, conviction="LOW", include=False,
          parse_error=False, summary="s", weakest="w", cost=0.05):
    if kind == "deliberated":
        rat = {"proposer": {}, "adversary": {}, "strategist": {"at_inflection": at_inflection}}
        outs = [_ao("proposer"), _ao("adversary"),
                _ao("strategist", {"parse_error": True} if parse_error else {})]
    elif kind == "abstained":
        rat = {"dropped": "proposer abstained (NEUTRAL)", "fundamentals": {}}
        outs = [_ao("proposer", {"parse_error": True} if parse_error else {})]
        conviction, at_inflection = "NEUTRAL", None
    elif kind == "ungrounded":
        rat = {"dropped": "ungrounded (no numeric evidence)", "fundamentals": {}}
        outs, conviction, at_inflection = [], "NEUTRAL", None
    else:  # error
        rat = {"error": "provider_error: boom"}
        outs, conviction, at_inflection = [], "NEUTRAL", None
    return CouncilProposal(
        theme="t", symbol="ADTN", direction="bullish", conviction=conviction,
        structural_vs_fad=None, weakest_point=weakest, strategist_summary=summary,
        rationale=rat, agent_outputs=outs, cost_usd=cost, include=include,
        at_inflection=at_inflection,
    )


def _item(cls="c", event_date="2026-09-15", claim="BEAD start 2026-09-15", **kw):
    base = {"symbol": "ADTN", "class": cls, "claim": claim,
            "source": "state office", "as_of": "2026-07-01", "expires": "2027-01-01",
            "event_date": event_date if cls in ("a", "c") else None, "provenance": "operator"}
    base.update(kw)
    return base


# ── classify_arm ──────────────────────────────────────────────────────────────

def test_classify_arm_kinds():
    assert classify_arm(_prop(kind="deliberated"))["kind"] == "deliberated"
    assert classify_arm(_prop(kind="abstained"))["kind"] == "abstained"
    assert classify_arm(_prop(kind="ungrounded"))["kind"] == "ungrounded"
    assert classify_arm(_prop(kind="error"))["kind"] == "error"
    # The #37 discipline: parse_error dominates — a failure NEVER reads as an abstention.
    assert classify_arm(_prop(kind="abstained", parse_error=True))["kind"] == "parse_error"
    assert classify_arm(_prop(kind="deliberated", parse_error=True))["kind"] == "parse_error"


# ── §8 per-class eligibility (hand-checked dates against AS_OF=2026-07-15) ────

def test_eligibility_dated_classes_bounds():
    # 62d out → eligible; 366d out → beyond the 365d bound; same-day → lower bound ZERO exclusive.
    assert eligible_classes([_item(event_date="2026-09-15")], AS_OF) == ["c"]
    assert eligible_classes([_item(cls="a", event_date="2027-07-17")], AS_OF) == []
    assert eligible_classes([_item(event_date="2026-07-15")], AS_OF) == []
    # 365d exactly (2027-07-15) → inclusive upper bound.
    assert eligible_classes([_item(cls="a", event_date="2027-07-15")], AS_OF) == ["a"]


def test_eligibility_class_d_rendered_is_eligible():
    # (d) carries no forward date — rendered ⇒ eligible (freshness is upstream §3 expiry).
    assert eligible_classes([_item(cls="d", event_date=None)], AS_OF) == ["d"]


def test_eligibility_accepts_tz_aware_as_of():
    # The LIVE clock is tz-aware; item dates are naive calendar dates. Found by the first live
    # probe run (2026-07-10): the naive/aware comparison raised TypeError.
    from datetime import UTC
    aware = AS_OF.replace(tzinfo=UTC)
    assert eligible_classes([_item(event_date="2026-09-15")], aware) == ["c"]


def test_eligibility_unparseable_event_date_not_eligible():
    assert eligible_classes([_item(event_date="soon")], AS_OF) == []


# ── the two flip disjuncts + reverse conversion ───────────────────────────────

def test_flip_value_change():
    v = pair_verdict(_prop(at_inflection=True), _prop(at_inflection=False), [_item()], AS_OF)
    assert v["flip"] is True and v["flip_via"] == "value_change" and v["eligible"] is True


def test_flip_conversion_the_kmt_face():
    # No-channel abstained ∧ channel deliberated = adjudicability, verdict-sign-INDEPENDENT
    # (the channel arm read at_inflection=False and it still counts — a judgment, not a wall).
    v = pair_verdict(_prop(at_inflection=False), _prop(kind="abstained"), [_item()], AS_OF)
    assert v["flip"] is True and v["flip_via"] == "conversion"


def test_no_flip_when_arms_agree():
    v = pair_verdict(_prop(at_inflection=False), _prop(at_inflection=False), [_item()], AS_OF)
    assert v["flip"] is False and v["flip_via"] == ""


def test_reverse_conversion_telemetry():
    # Channel abstained ∧ no-channel deliberated — the channel-HARM signature; telemetry only.
    v = pair_verdict(_prop(kind="abstained"), _prop(at_inflection=False), [_item()], AS_OF)
    assert v["reverse_conversion"] is True and v["flip"] is False


def test_void_pairs_excluded_never_silently():
    # A parse_error arm voids the pair (malformed judgment ≠ judgment) — recorded with reason.
    v = pair_verdict(_prop(parse_error=True), _prop(), [_item()], AS_OF)
    assert v["void"] is True and "parse_error" in v["void_reason"] and v["eligible"] is False
    assert v["flip"] is False  # detectors never fire on a void pair
    v2 = pair_verdict(_prop(), _prop(kind="ungrounded"), [_item()], AS_OF)
    assert v2["void"] is True and "ungrounded" in v2["void_reason"]


def test_pair_not_eligible_when_block_never_rendered():
    # §4: "channel-grounded judgment" requires the block to have RENDERED.
    v = pair_verdict(_prop(), _prop(), [], AS_OF)
    assert v["eligible"] is False and v["classes_rendered"] == ""


def test_pair_not_eligible_when_only_item_is_out_of_horizon():
    v = pair_verdict(_prop(), _prop(), [_item(event_date="2028-01-01")], AS_OF)
    assert v["eligible"] is False and v["eligible_classes"] == ""


# ── the cite detector (the ONE shared tokenizer) ──────────────────────────────

def test_cite_detects_block_tokens_in_channel_rationale():
    ch = _prop(summary="the dated 2026-09-15 start is the inflection")
    v = pair_verdict(ch, _prop(), [_item()], AS_OF)
    assert v["cite"] is True and "2026-09-15" in v["cited_tokens"]


def test_cite_searches_agent_raws_too():
    ch = _prop(kind="deliberated")
    ch.agent_outputs[0].raw["inflection_thesis"] = "grounded on the 2026-09-15 milestone"
    v = pair_verdict(ch, _prop(), [_item()], AS_OF)
    assert v["cite"] is True


def test_no_cite_when_rationale_never_uses_block_tokens():
    v = pair_verdict(_prop(summary="momentum thesis only"), _prop(), [_item()], AS_OF)
    assert v["cite"] is False and v["cited_tokens"] == ""


def test_bare_year_in_rationale_is_not_a_cite():
    # §8 distinctiveness end-to-end: "2026" alone must not register (the (i)→(ii) misroute guard).
    v = pair_verdict(_prop(summary="sometime in 2026 things change"), _prop(),
                     [_item(claim="BEAD start", event_date="2026-09-15")], AS_OF)
    assert v["cite"] is False


# ── end-to-end: both arms through the REAL propose() wiring (FakeRouter) ──────

def test_pair_through_propose_offline(tmp_path):
    import json as _json
    import random

    from council.council import propose
    from council.router import FakeRouter
    from data.forward_catalysts import ForwardCatalysts
    from themes import Theme

    class _Clock:
        def now(self):
            return AS_OF

    pin = tmp_path / "fc.json"
    pin.write_text(_json.dumps({"items": [_item()]}))
    fc = ForwardCatalysts(str(pin))
    theme = Theme("bead_buildout", "ADTN", "bullish", "BEAD construction-start expression")
    cfg = {"council": {"max_candidates": 12}}

    # demo=False + news=None exercises the REAL build_context_pack path offline; FakeRouter
    # answers all three roles. Identical seeded rng per arm (the probe's discipline).
    ch = propose([theme], router=FakeRouter(), config=cfg, clock=_Clock(), news=None,
                 catalysts=fc, rng=random.Random(0))
    nc = propose([theme], router=FakeRouter(), config=cfg, clock=_Clock(), news=None,
                 catalysts=None, rng=random.Random(0))
    # No news + no fundamentals → both arms ungrounded early-exit — the pair VOIDS (the §1
    # invariant seen end-to-end: the channel never grounds, so it cannot create a judgment
    # where no other evidence exists).
    v = pair_verdict(ch[0], nc[0], fc.items_asof("ADTN", AS_OF), AS_OF)
    assert v["void"] is True and "ungrounded" in v["void_reason"]
    assert v["classes_rendered"] == "c"  # the block DID render — §4's rendered-vs-judged split


# ── the ledger ────────────────────────────────────────────────────────────────

def test_ledger_append_and_shape(tmp_path):
    path = str(tmp_path / "pairs.csv")
    v = pair_verdict(_prop(at_inflection=True), _prop(kind="abstained"), [_item()], AS_OF)
    append_pair_row(path, v)
    append_pair_row(path, v)
    rows = list(csv.DictReader(open(path)))
    assert len(rows) == 2 and list(rows[0].keys()) == LEDGER_FIELDS
    assert rows[0]["flip"] == "True" and rows[0]["flip_via"] == "conversion"
    assert rows[0]["symbol"] == "ADTN" and rows[0]["cost_usd"] == "0.1"
