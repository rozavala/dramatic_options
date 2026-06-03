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
