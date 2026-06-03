"""Live council acceptance (opt-in, real LLM calls) — codifies Step D of the #37 fix.

Deselected by default (pyproject ``addopts = -m 'not live'``) so CI / offline runs never spend or
need keys. Run on-host after a deploy or a google-genai / model bump — it is the repeatable
"is the council healthy?" check:

    pytest -m live tests/test_council_live.py

It proves all three roles parse+validate LIVE (the gemini-3.x thinking-starvation fix) and that the
xai adversary + anthropic strategist produce parseable JSON (they had never fired live before #37).
"""

from datetime import UTC, datetime

import pytest

from config_loader import load_config
from council import agents
from council.context import sentinel_context_pack
from council.debate import run_candidate
from council.router import build_router
from themes import Theme

pytestmark = pytest.mark.live

_MARKERS = {"momentum": 0.42, "rel_strength": 0.10, "rv_slope": 0.31, "has_event": False,
            "price_vs_200d": 0.22, "iv_rv": 0.95}


def _live_router():
    cfg = load_config()
    keys = cfg.get("llm_keys", {})
    if not all(keys.get(p) for p in ("gemini", "xai", "anthropic")):
        pytest.skip("live LLM keys not configured (.env) — on-host only")
    return cfg, build_router(cfg, keys)


def test_live_three_role_roundtrip_parses_and_validates():
    _cfg, router = _live_router()
    cand = Theme("ai_compute", "SMCI", "bullish", "discovery hypothesis: momentum +0.42",
                 source="sentinel", sentinel_id=1, markers=_MARKERS)
    pack = sentinel_context_pack(cand, as_of=datetime.now(UTC))
    assert pack.grounded

    # Direct per-role calls so the proof doesn't depend on the proposer's judgment short-circuit.
    sysm, user = agents.proposer_prompt(pack)
    pr = router.call(role="proposer", system=sysm, user=user)
    praw = agents.parse_proposer(pr.text, finish_reason=pr.finish_reason, thoughts_tokens=pr.thoughts_tokens)
    sysm, user = agents.adversary_prompt(pack, praw)
    ar = router.call(role="adversary", system=sysm, user=user)
    araw = agents.parse_adversary(ar.text, finish_reason=ar.finish_reason, thoughts_tokens=ar.thoughts_tokens)
    sysm, user = agents.strategist_prompt(pack, praw, araw)
    sr = router.call(role="strategist", system=sysm, user=user)
    sraw = agents.parse_strategist(sr.text, finish_reason=sr.finish_reason, thoughts_tokens=sr.thoughts_tokens)

    # The #37 fix: every role parses + validates, and the gemini proposer is no longer thinking-starved.
    assert not praw.get("parse_error"), f"proposer parse_error: {praw}"
    assert not araw.get("parse_error"), f"adversary (grok) parse_error: {araw}"
    assert not sraw.get("parse_error"), f"strategist (opus) parse_error: {sraw}"
    assert pr.text and "MAX_TOKENS" not in str(pr.finish_reason), "proposer thinking-starved again"
    assert praw["confidence"] in ("LOW", "MODERATE", "HIGH", "EXTREME", "NEUTRAL")

    # The integrated path runs end-to-end and spends (role count depends on the proposer's judgment).
    prop = run_candidate(cand, pack, router)
    assert prop.cost_usd > 0
