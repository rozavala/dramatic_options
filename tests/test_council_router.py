"""Router + cost ledger + FakeRouter (T2). Fully offline — no SDKs, no keys, no network."""

import json

import pytest

from council.router import (
    BudgetExceeded,
    CostLedger,
    FakeRouter,
    Router,
    RouterError,
    build_router,
    price_call,
)

ROLES = {
    "proposer": {"provider": "gemini", "model": "gemini-2.5-pro"},
    "adversary": {"provider": "xai", "model": "grok-4"},
    "strategist": {"provider": "anthropic", "model": "claude-opus-4-8"},
}
PRICES = {"claude-opus-4-8": {"in": 15.0, "out": 75.0}}


def test_price_call_from_table():
    # 1M in @ $15 + 0.5M out @ $75 = 15 + 37.5
    assert price_call(PRICES, "claude-opus-4-8", 1_000_000, 500_000) == pytest.approx(52.5)
    # Unpriced model → 0 (ledger still records the call).
    assert price_call(PRICES, "unknown", 1000, 1000) == 0.0


def test_cost_ledger_total_and_cap():
    led = CostLedger(cap_usd=1.0)
    assert not led.over_cap and led.total_usd == 0.0
    from council.router import CostEntry

    led.record(CostEntry("strategist", "anthropic", "m", 100, 100, 0.6))
    assert not led.over_cap
    led.record(CostEntry("proposer", "gemini", "m", 100, 100, 0.6))
    assert led.over_cap  # 1.2 >= 1.0
    assert "1.20" in led.summary() or "$1.2" in led.summary()


class _StubProvider:
    """A provider whose .complete returns canned tokens (or raises N times first)."""

    def __init__(self, name, *, fail_times=0, text='{"ok": true}', in_tok=10, out_tok=5):
        self.name = name
        self._fail_times = fail_times
        self._calls = 0
        self._text, self._in, self._out = text, in_tok, out_tok

    def complete(self, *, model, system, user, timeout_s, max_tokens):
        self._calls += 1
        if self._calls <= self._fail_times:
            raise RuntimeError("transient")
        return self._text, self._in, self._out, {"finish_reason": "STOP", "thoughts_tokens": None}


def test_router_records_cost_and_returns_response():
    led = CostLedger(cap_usd=10.0)
    r = Router(providers={"anthropic": _StubProvider("anthropic", in_tok=1_000_000, out_tok=0)},
               roles={"strategist": ROLES["strategist"]}, prices=PRICES, ledger=led, max_retries=0)
    resp = r.call(role="strategist", system="s", user="u")
    assert resp.provider == "anthropic" and resp.cost_usd == pytest.approx(15.0)
    assert led.calls == 1 and led.total_usd == pytest.approx(15.0)


def test_router_retries_then_succeeds():
    led = CostLedger()
    prov = _StubProvider("anthropic", fail_times=1)
    r = Router(providers={"anthropic": prov}, roles={"strategist": ROLES["strategist"]},
               prices={}, ledger=led, max_retries=2)
    resp = r.call(role="strategist", system="s", user="u")
    assert json.loads(resp.text) == {"ok": True} and prov._calls == 2


def test_router_exhausts_retries_then_raises():
    led = CostLedger()
    r = Router(providers={"anthropic": _StubProvider("anthropic", fail_times=99)},
               roles={"strategist": ROLES["strategist"]}, prices={}, ledger=led, max_retries=1)
    with pytest.raises(RouterError):
        r.call(role="strategist", system="s", user="u")


def test_router_budget_exceeded_blocks_call_before_spending():
    led = CostLedger(cap_usd=0.0)  # already at cap
    prov = _StubProvider("anthropic")
    r = Router(providers={"anthropic": prov}, roles={"strategist": ROLES["strategist"]},
               prices={}, ledger=led, max_retries=0)
    with pytest.raises(BudgetExceeded):
        r.call(role="strategist", system="s", user="u")
    assert prov._calls == 0  # fail-closed: never reached the provider


def test_build_router_fails_closed_on_missing_key():
    config = {"council": {"roles": ROLES, "prices_per_mtok": PRICES, "cost_cap_usd": 5.0}}
    with pytest.raises(RouterError):
        build_router(config, llm_keys={"gemini": "g", "xai": "x"})  # anthropic key missing


def test_build_router_constructs_mapped_providers_without_sdk_import():
    # build_router only constructs adapter objects (SDKs are lazy) → no network/keys needed.
    config = {"council": {"roles": ROLES, "prices_per_mtok": PRICES, "cost_cap_usd": 5.0}}
    r = build_router(config, llm_keys={"gemini": "g", "xai": "x", "anthropic": "a"})
    assert r.provider_model("strategist") == ("anthropic", "claude-opus-4-8")
    assert r.provider_model("proposer") == ("gemini", "gemini-2.5-pro")
    assert r.ledger.cap_usd == 5.0


def test_fake_router_is_deterministic_and_free():
    fr = FakeRouter()
    user = "CANDIDATE: FCX bullish copper_electrification\n\nGround truth: ..."
    p = json.loads(fr.call(role="proposer", system="s", user=user).text)
    assert p["symbol"] == "FCX" and p["direction"] == "bullish"
    s = json.loads(fr.call(role="strategist", system="s", user=user).text)
    assert s["conviction"] in ("LOW", "MODERATE", "HIGH", "EXTREME") and s["include"] is True
    assert fr.ledger.total_usd == 0.0 and fr.ledger.calls == 2


def test_fake_router_custom_responder():
    fr = FakeRouter(responder=lambda role, system, user: json.dumps({"role": role}))
    assert json.loads(fr.call(role="adversary", system="s", user="u").text) == {"role": "adversary"}


# ── OpenAIProvider token-param swap (gpt-5 / o-series reject max_tokens) ──────────────────────
from types import SimpleNamespace  # noqa: E402


class _FakeOAIError(Exception):
    def __init__(self, msg, status_code=400):
        super().__init__(msg)
        self.status_code = status_code


class _FakeCompletions:
    """Records the create() kwargs; ``reject_max_tokens`` simulates gpt-5/o-series (400 on max_tokens)."""

    def __init__(self, *, reject_max_tokens):
        self.calls = []
        self._reject = reject_max_tokens

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._reject and "max_tokens" in kwargs:
            raise _FakeOAIError("Unsupported parameter: 'max_tokens' is not supported with this model. "
                                "Use 'max_completion_tokens' instead.")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=7))


def _oai_provider_with_fake(*, reject_max_tokens):
    from council.router import OpenAIProvider
    prov = OpenAIProvider("k", name="openai", json_mode=True)
    comp = _FakeCompletions(reject_max_tokens=reject_max_tokens)
    prov._client = SimpleNamespace(chat=SimpleNamespace(completions=comp))  # bypass lazy SDK import
    return prov, comp


def test_openai_provider_swaps_to_max_completion_tokens_on_400():
    # gpt-5/o-series: max_tokens 400s → swap to max_completion_tokens and retry, byte-for-byte same prompt.
    prov, comp = _oai_provider_with_fake(reject_max_tokens=True)
    text, intok, outtok, meta = prov.complete(
        model="gpt-5.4", system="reply with ONE json object", user="u", timeout_s=5, max_tokens=64)
    assert json.loads(text) == {"ok": True} and (intok, outtok) == (12, 7) and meta["finish_reason"] == "stop"
    assert len(comp.calls) == 2
    assert "max_tokens" in comp.calls[0] and "max_completion_tokens" not in comp.calls[0]
    assert comp.calls[1].get("max_completion_tokens") == 64 and "max_tokens" not in comp.calls[1]


def test_openai_provider_keeps_max_tokens_for_compatible_models():
    # grok/perplexity/gpt-4.x accept max_tokens → no swap, single call (the unchanged path).
    prov, comp = _oai_provider_with_fake(reject_max_tokens=False)
    text, *_ = prov.complete(model="grok-4.3", system="reply with json", user="u", timeout_s=5, max_tokens=64)
    assert json.loads(text) == {"ok": True}
    assert len(comp.calls) == 1 and comp.calls[0].get("max_tokens") == 64


def test_build_router_threads_gemini_thinking_knobs():
    # The P0 fix is config-driven: the gemini provider must receive thinking_level + json_mode so a 3.x
    # thinking model doesn't starve its output budget (SDKs lazy → no network).
    config = {"council": {"roles": {"proposer": {"provider": "gemini", "model": "gemini-3.5-flash"}},
                          "gemini": {"thinking_level": "minimal", "json_mode": True}}}
    prov = build_router(config, llm_keys={"gemini": "g"})._providers["gemini"]
    assert prov._thinking_level == "minimal" and prov._json_mode is True


def test_build_router_per_role_knob_overrides_provider_default():
    # P3-#11: a per-role knob overrides the council.<provider> default (the expansion path).
    config = {"council": {"roles": {"proposer": {"provider": "gemini", "model": "m",
                                                 "thinking_level": "low", "json_mode": False}},
                          "gemini": {"thinking_level": "minimal", "json_mode": True}}}
    prov = build_router(config, llm_keys={"gemini": "g"})._providers["gemini"]
    assert prov._thinking_level == "low" and prov._json_mode is False
