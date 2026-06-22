"""Heterogeneous LLM router + cost ledger (T2) — re-implemented from Real Options, not imported.

Routes each council role to a (possibly) different provider/model so the debate yields
genuinely decorrelated errors (SPEC §5 / §9). Three SDKs cover all SPEC providers: `anthropic`,
`openai` (also serves xAI/Grok + Perplexity via `base_url`), and `google-genai`. **SDKs are
lazy-imported inside each adapter**, so CI / `orchestrator.py --demo` / tests (which use
``FakeRouter``) need none of them installed and no API keys.

Cost is **first-class** (SPEC §"observability"): every call is priced from a config table and
appended to a ``CostLedger``. The provisional per-cycle cap is enforced fail-closed at the router
boundary (``BudgetExceeded``) — the operator sets the real ceiling after seeing the printed ledger.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

log = logging.getLogger("council.router")

# OpenAI-compatible providers reachable through the `openai` SDK with a different base_url.
_OPENAI_COMPATIBLE_BASE_URLS = {
    "openai": None,
    "xai": "https://api.x.ai/v1",
    "perplexity": "https://api.perplexity.ai",
}

# NOTE (forward-record determinism): no provider sets ``temperature`` — each uses the SDK default.
# For a Brier-scored forward council that is INTENTIONAL (run-to-run variation is expected; a pinned
# temperature is a separate, pre-registered decision), not an oversight.


class RouterError(RuntimeError):
    """A provider call failed after retries (fail-closed → the council proposes nothing)."""


class BudgetExceeded(RouterError):
    """The per-cycle cost cap was reached before this call (fail-closed)."""


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    finish_reason: str | None = None   # provider stop reason (MAX_TOKENS ⇒ truncation/thinking-starvation)
    thoughts_tokens: int | None = None  # gemini thinking-token count (forensic; None when not a thinking model)


@dataclass
class CostEntry:
    role: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class CostLedger:
    """Per-cycle running cost. ``cap_usd`` is the provisional fail-closed ceiling (or None)."""

    cap_usd: float | None = None
    entries: list[CostEntry] = field(default_factory=list)

    @property
    def total_usd(self) -> float:
        return sum(e.cost_usd for e in self.entries)

    @property
    def calls(self) -> int:
        return len(self.entries)

    @property
    def over_cap(self) -> bool:
        return self.cap_usd is not None and self.total_usd >= self.cap_usd

    def record(self, entry: CostEntry) -> None:
        self.entries.append(entry)

    def summary(self) -> str:
        if not self.entries:
            return "Council cost ledger: 0 calls, $0.0000"
        by_model: dict[str, float] = {}
        for e in self.entries:
            by_model[f"{e.provider}/{e.model}"] = by_model.get(f"{e.provider}/{e.model}", 0.0) + e.cost_usd
        parts = ", ".join(f"{k} ${v:.4f}" for k, v in sorted(by_model.items()))
        cap = f" (cap ${self.cap_usd:.2f})" if self.cap_usd is not None else ""
        return f"Council cost ledger: {self.calls} calls, ${self.total_usd:.4f}{cap} — {parts}"


def price_call(prices: dict, model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost from the config `prices_per_mtok` table ($ per million tokens). 0 if unpriced."""
    p = prices.get(model)
    if not p:
        return 0.0
    return (input_tokens / 1e6) * float(p.get("in", 0.0)) + (output_tokens / 1e6) * float(p.get("out", 0.0))


# ── Provider adapters (SDKs lazy-imported) ──────────────────────────────────────────────────


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None

    def _ensure(self):
        if self._client is None:
            import anthropic  # lazy

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete(self, *, model: str, system: str, user: str, timeout_s: float, max_tokens: int) -> tuple[str, int, int, dict]:
        client = self._ensure()
        resp = client.messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}], timeout=timeout_s,
        )
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        meta = {"finish_reason": getattr(resp, "stop_reason", None), "thoughts_tokens": None}
        return text, int(resp.usage.input_tokens), int(resp.usage.output_tokens), meta


class OpenAIProvider:
    """Serves OpenAI, xAI/Grok, and Perplexity (chat-completions compatible) via base_url."""

    def __init__(self, api_key: str, *, name: str = "openai", base_url: str | None = None,
                 json_mode: bool = True) -> None:
        self.name = name
        self._api_key = api_key
        self._base_url = base_url
        self._json_mode = json_mode
        self._client = None

    def _ensure(self):
        if self._client is None:
            from openai import OpenAI  # lazy

            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def complete(self, *, model: str, system: str, user: str, timeout_s: float, max_tokens: int) -> tuple[str, int, int, dict]:
        client = self._ensure()
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        # JSON mode REQUIRES the literal "json" in the messages (OpenAI/xAI precondition) — without it the
        # API 400s, or worse streams unbounded whitespace to the token cap. Our role prompts all say
        # "Reply with ONE JSON object", so the gate passes; if a compat endpoint rejects response_format we
        # retry WITHOUT it (loud) — the prompt + the Part-2 schema validation still elicit/guard JSON.
        use_json = self._json_mode and ("json" in system.lower() or "json" in user.lower())
        # Token-limit param: OpenAI's gpt-5 / o-series models REJECT `max_tokens` (400 — they require
        # `max_completion_tokens`); xAI/Grok + Perplexity still take `max_tokens`. Start with max_tokens
        # (so grok/perplexity/gpt-4.x are byte-unchanged) and SWAP on the specific 400, mirroring the
        # response_format retry — one provider class serves both without a hardcoded model-family list
        # (which would drift as new reasoning models ship). Verified live 2026-06-22 against gpt-5.4.
        token_param = "max_tokens"

        def _kwargs() -> dict:
            kw = dict(model=model, timeout=timeout_s, messages=messages, **{token_param: max_tokens})
            if use_json:
                kw["response_format"] = {"type": "json_object"}
            return kw

        resp = None
        for _ in range(3):  # at most two corrective swaps: the token param and/or response_format
            try:
                resp = client.chat.completions.create(**_kwargs())
                break
            except Exception as e:  # noqa: BLE001
                if getattr(e, "status_code", None) != 400:
                    raise
                emsg = str(e).lower()
                if token_param == "max_tokens" and "max_completion_tokens" in emsg:
                    log.warning("openai %s/%s: max_tokens unsupported — retrying with max_completion_tokens",
                                self.name, model)
                    token_param = "max_completion_tokens"
                    continue
                if use_json:
                    log.warning("openai %s/%s: response_format rejected (%s) — retrying without json_object",
                                self.name, model, e)
                    use_json = False
                    continue
                raise
        if resp is None:  # defensive — the loop returns a resp or re-raises inside
            raise RouterError(f"openai {self.name}/{model}: 400 after corrective retries")
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        meta = {"finish_reason": getattr(resp.choices[0], "finish_reason", None), "thoughts_tokens": None}
        return text, int(usage.prompt_tokens), int(usage.completion_tokens), meta


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, *, json_mode: bool = True,
                 thinking_level: str | None = "minimal", thinking_budget: int | None = None) -> None:
        self._api_key = api_key
        self._json_mode = json_mode
        # Gemini 3.x uses thinking_LEVEL (minimal/low/medium/high); 2.5 used thinking_BUDGET. They are
        # mutually exclusive (the API 400s if both are set), and on a 3.x thinking model the DEFAULT
        # thinking eats max_output_tokens → truncated/empty JSON (the #37 bug). We default to
        # thinking_level="minimal" (the documented 3.x "as little thinking as possible" knob).
        self._thinking_level = thinking_level
        self._thinking_budget = thinking_budget
        self._client = None

    def _ensure(self):
        if self._client is None:
            from google import genai  # lazy

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def _thinking_config(self, types):
        """thinking_level XOR thinking_budget (never both). Prefer level (the 3.x knob). Fail LOUD on a
        bad level rather than silently dropping it back to default thinking (which re-creates the bug)."""
        if self._thinking_level:
            member = getattr(types.ThinkingLevel, str(self._thinking_level).upper(), None)
            if member is None:
                raise RouterError(f"unknown gemini thinking_level {self._thinking_level!r}")
            return types.ThinkingConfig(thinking_level=member)
        if self._thinking_budget is not None:
            return types.ThinkingConfig(thinking_budget=int(self._thinking_budget))
        return None

    def complete(self, *, model: str, system: str, user: str, timeout_s: float, max_tokens: int) -> tuple[str, int, int, dict]:
        client = self._ensure()
        from google.genai import types  # lazy

        cfg_kwargs = dict(
            system_instruction=system, max_output_tokens=max_tokens,
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
        )
        # Gate JSON mode on the prompt asking for JSON (mirrors OpenAIProvider) — so a free-PROSE
        # caller (e.g. the Stage-2 probe describer) gets prose, while every JSON caller (council
        # proposer, framer — both say "Reply with ONE JSON object") keeps the response_mime_type.
        if self._json_mode and ("json" in system.lower() or "json" in user.lower()):
            cfg_kwargs["response_mime_type"] = "application/json"
        tcfg = self._thinking_config(types)
        if tcfg is not None:
            cfg_kwargs["thinking_config"] = tcfg

        resp = client.models.generate_content(
            model=model, contents=user, config=types.GenerateContentConfig(**cfg_kwargs),
        )
        text = resp.text or ""
        um = resp.usage_metadata
        finish_reason = None
        try:
            finish_reason = str(resp.candidates[0].finish_reason)
        except Exception:  # noqa: BLE001 — finish_reason is forensic only
            pass
        thoughts = getattr(um, "thoughts_token_count", None)
        if not text:
            # Loud (not silent): an empty body on a billed call is the #37 failure mode — surface it.
            log.warning("gemini %s returned EMPTY text (finish_reason=%s, thoughts_tokens=%s, max_tokens=%s)",
                        model, finish_reason, thoughts, max_tokens)
        return (text, int(um.prompt_token_count or 0), int(um.candidates_token_count or 0),
                {"finish_reason": finish_reason, "thoughts_tokens": thoughts})


# ── The router ──────────────────────────────────────────────────────────────────────────────


class Router:
    """Resolves a role → (provider, model), calls it with retries, prices it, records the cost."""

    def __init__(
        self,
        *,
        providers: dict[str, object],
        roles: dict[str, dict],
        prices: dict,
        ledger: CostLedger,
        timeout_s: float = 60.0,
        max_retries: int = 2,
        max_tokens: int = 2048,
    ) -> None:
        self._providers = providers
        self._roles = roles
        self._prices = prices
        self.ledger = ledger
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._max_tokens = max_tokens

    def provider_model(self, role: str) -> tuple[str, str]:
        spec = self._roles.get(role) or {}
        return str(spec.get("provider", "")), str(spec.get("model", ""))

    def call(self, *, role: str, system: str, user: str, max_tokens: int | None = None) -> LLMResponse:
        if self.ledger.over_cap:
            raise BudgetExceeded(
                f"cost cap ${self.ledger.cap_usd:.2f} reached (${self.ledger.total_usd:.4f}) before {role} call"
            )
        provider_name, model = self.provider_model(role)
        provider = self._providers.get(provider_name)
        if provider is None:
            raise RouterError(f"no provider configured for role {role!r} (provider={provider_name!r})")

        last_err: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                text, in_tok, out_tok, meta = provider.complete(
                    model=model, system=system, user=user,
                    timeout_s=self._timeout_s, max_tokens=max_tokens or self._max_tokens,
                )
                cost = price_call(self._prices, model, in_tok, out_tok)
                self.ledger.record(CostEntry(role, provider_name, model, in_tok, out_tok, cost))
                meta = meta or {}
                return LLMResponse(text, provider_name, model, in_tok, out_tok, cost,
                                   finish_reason=meta.get("finish_reason"),
                                   thoughts_tokens=meta.get("thoughts_tokens"))
            except Exception as e:  # noqa: BLE001 — provider/transport errors → retry then fail-closed
                last_err = e
                log.warning("router %s/%s call failed (attempt %d/%d): %s",
                            provider_name, model, attempt + 1, self._max_retries + 1, e)
                if attempt < self._max_retries:
                    time.sleep(min(2.0 ** attempt, 5.0))
        raise RouterError(f"{role} ({provider_name}/{model}) failed after {self._max_retries + 1} attempts: {last_err}")


_PROVIDER_KNOB_KEYS = ("thinking_level", "thinking_budget", "json_mode")


def _provider_knobs(provider_name: str, roles: dict, provider_default: dict) -> dict:
    """Resolve generation knobs for a provider: the ``council.<provider>`` default overlaid by any
    per-role override (``roles.<role>.thinking_level`` / ``json_mode`` …) for the role(s) using it.
    One role per provider in practice (proposer→gemini, adversary→xai, strategist→anthropic,
    framer→gemini); the per-role hook is the expansion path (P3-#11 — a future thinking-wanting role)."""
    knobs = dict(provider_default)
    for spec in roles.values():
        if spec.get("provider") == provider_name:
            for k in _PROVIDER_KNOB_KEYS:
                if k in spec:
                    knobs[k] = spec[k]
    return knobs


def build_router(config: dict, llm_keys: dict, *, ledger: CostLedger | None = None) -> Router:
    """Construct a live Router from config.council + the .env-sourced llm_keys.

    Builds ONLY the providers actually mapped to a role. Raises RouterError (fail-closed) if a
    mapped provider has no API key — the council then proposes nothing this cycle.
    """
    council = config.get("council", {})
    roles = council.get("roles", {})
    prices = council.get("prices_per_mtok", {})
    needed = {str(spec.get("provider")) for spec in roles.values() if spec.get("provider")}

    providers: dict[str, object] = {}
    for name in needed:
        key = llm_keys.get(name)
        if not key:
            raise RouterError(f"council role mapped to provider {name!r} but no API key is set (.env)")
        if name == "anthropic":
            providers[name] = AnthropicProvider(key)
        elif name == "gemini":
            knobs = _provider_knobs(name, roles, council.get("gemini", {}))
            providers[name] = GeminiProvider(
                key, json_mode=bool(knobs.get("json_mode", True)),
                thinking_level=knobs.get("thinking_level", "minimal"),
                thinking_budget=knobs.get("thinking_budget"))
        elif name in _OPENAI_COMPATIBLE_BASE_URLS:
            knobs = _provider_knobs(name, roles, council.get("openai", {}))
            providers[name] = OpenAIProvider(
                key, name=name, base_url=_OPENAI_COMPATIBLE_BASE_URLS[name],
                json_mode=bool(knobs.get("json_mode", True)))
        else:
            raise RouterError(f"unknown council provider {name!r}")

    if ledger is None:
        cap = council.get("cost_cap_usd")
        ledger = CostLedger(cap_usd=float(cap) if cap is not None else None)
    return Router(
        providers=providers, roles=roles, prices=prices, ledger=ledger,
        timeout_s=float(council.get("timeout_s", 60)),
        max_retries=int(council.get("max_retries", 2)),
        max_tokens=int(council.get("max_tokens", 2048)),
    )


class FakeRouter:
    """Deterministic offline router for ``--demo`` and tests (mirrors SyntheticChainProvider).

    No SDK, no network, no keys, $0 cost. ``responder(role, system, user) -> str`` lets a test
    script scenario-specific outputs (e.g. EXTREME conviction on a given name); the default
    responder echoes the candidate parsed from the prompt's ``CANDIDATE:`` header (see
    ``council.agents``) into minimal valid JSON, so the full pipeline runs end-to-end offline.
    """

    def __init__(self, responder=None, *, cap_usd: float | None = None) -> None:
        self._responder = responder or _default_fake_responder
        self.ledger = CostLedger(cap_usd=cap_usd)

    def provider_model(self, role: str) -> tuple[str, str]:
        return ("fake", f"fake-{role}")

    def call(self, *, role: str, system: str, user: str, max_tokens: int | None = None) -> LLMResponse:
        if self.ledger.over_cap:
            raise BudgetExceeded(f"fake cap ${self.ledger.cap_usd} reached before {role}")
        text = self._responder(role, system, user)
        self.ledger.record(CostEntry(role, "fake", f"fake-{role}", 0, 0, 0.0))
        return LLMResponse(text, "fake", f"fake-{role}", 0, 0, 0.0)


def _parse_candidate_header(user: str) -> dict:
    """Read the ``CANDIDATE: SYMBOL DIRECTION THEME...`` header the agents embed in prompts."""
    for line in user.splitlines():
        if line.startswith("CANDIDATE:"):
            rest = line[len("CANDIDATE:"):].strip().split(maxsplit=2)
            if len(rest) >= 2:
                return {"symbol": rest[0], "direction": rest[1],
                        "theme": rest[2] if len(rest) > 2 else rest[0].lower()}
    return {"symbol": "UNKNOWN", "direction": "bullish", "theme": "unknown"}


def _default_fake_responder(role: str, system: str, user: str) -> str:
    """Minimal valid JSON per role echoing the candidate — enough for an offline end-to-end run."""
    import json

    c = _parse_candidate_header(user)
    if role == "proposer":
        return json.dumps({
            "theme": c["theme"], "symbol": c["symbol"], "direction": c["direction"],
            "structural_vs_fad": "structural",
            "inflection_thesis": f"(demo) {c['theme']} appears at inflection; convexity may be unpriced.",
            "confidence": "HIGH", "cited": [],
        })
    if role == "adversary":
        return json.dumps({
            "counter_case": f"(demo) the {c['direction']} case on {c['symbol']} may already be consensus.",
            "weakest_point": "narrative may already be priced; IV gate will arbitrate.",
            "is_fad": False, "already_consensus": False, "inflection_passed": False,
            "confidence": "MODERATE", "cited": [],
        })
    # strategist — carries the §10.7 tri-criteria assertions (lock-step with
    # agents._STRATEGIST_INCLUDE_BOOL_KEYS + select_for_trade's tri rule, so demo includes
    # still reach the gates).
    return json.dumps({
        "include": True, "theme": c["theme"], "symbol": c["symbol"], "direction": c["direction"],
        "conviction": "HIGH", "structural_vs_fad": "structural",
        "under_narrated": True, "at_inflection": True,
        "weakest_point": "narrative may already be priced; deterministic IV gate arbitrates.",
        "summary": f"(demo) propose {c['direction']} {c['symbol']} on {c['theme']}; gate decides cheapness.",
    })
