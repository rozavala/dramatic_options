"""Sentinel framer (T3 PR2) — the bounded LLM that frames the prescreen's top-K, grounded on markers.

A **framer / novelty judge**, not a trade proposer (the council still proposes the trade). It
adjudicates the three confounds behind "a name moved" — real un-priced **inflection** vs a quote/data
**artifact** vs justified **mean-reversion** — from the deterministic MARKERS (origin-aware grounding,
never news; cheapness is the IV gate's job and is out of scope here), and emits a candidate framing.
A skeptic, not a narrator. Its model is **decorrelated** from the three council roles (else the
council just ratifies it), and its thesis enters the council labeled a "discovery hypothesis".

Fail-closed (the council-build discipline): over-budget / router error → frame **NOTHING** this scan
(never add unframed names); a per-candidate provider error drops that one; an ungrounded pack (no
markers) or a NEUTRAL / 'artifact' verdict **drops** the candidate (the skeptic abstains). `--demo`
/ tests use a deterministic `FakeRouter` responder (no keys/SDKs).
"""

from __future__ import annotations

import json
import logging

from council.agents import extract_json
from council.context import sentinel_context_pack
from council.filters import apply_filter
from council.proposal import normalize_conviction
from council.router import BudgetExceeded, RouterError, build_router
from sentinels import markers_dict
from themes import Theme

log = logging.getLogger("council.sentinel")

CONFOUNDS = ("real_inflection", "artifact", "mean_reversion")

FRAMER_SYSTEM = (
    "You are a disciplined discovery analyst for a long-dated far-OTM cheap-convexity options book. "
    "A deterministic prescreen flagged that SOMETHING IS MOVING in this name; the EVIDENCE is the "
    "numeric markers provided (not news). Your job is NOT to tell a bullish story — it is to "
    "ADJUDICATE, skeptically and from the markers alone, WHY it moved: a REAL un-priced secular "
    "inflection, a quote/DATA ARTIFACT (thin/stale far-OTM quote, a bad print), or JUSTIFIED "
    "MEAN-REVERSION (vol rose for a transient reason the market correctly expects to fade). A "
    "downstream IV gate decides CHEAPNESS — do not opine on it. Reason ONLY from the markers; if "
    "they are insufficient, return NEUTRAL. Reply with ONE JSON object and nothing else: {confound "
    "('real_inflection'|'artifact'|'mean_reversion'), direction ('bullish'|'bearish'), theme (short "
    "slug), structural_vs_fad ('structural'|'fad'|'unclear'), seed_thesis (one sentence citing a "
    "marker), confidence (LOW|MODERATE|HIGH|EXTREME|NEUTRAL)}."
)


def framer_prompt(pack) -> tuple[str, str]:
    return FRAMER_SYSTEM, pack.as_prompt_block()


def parse_framer(text: str) -> dict:
    """Defensive parse → strict confidence + a confound in the controlled vocabulary (else None).
    A parse failure resolves to NEUTRAL (fail-closed → the candidate is dropped, never surfaced)."""
    try:
        d = extract_json(text)
    except (ValueError, json.JSONDecodeError):
        return {"confidence": "NEUTRAL", "confound": None, "parse_error": True}
    d["confidence"] = normalize_conviction(d.get("confidence"))
    c = str(d.get("confound", "")).strip().lower()
    d["confound"] = c if c in CONFOUNDS else None
    return d


def frame_candidates(surfaced, router, *, as_of) -> dict[str, dict]:
    """Run the framer over the surfaced top-K → ``{symbol: framing}`` for the INCLUDED ones only.

    The skeptic disposes: ungrounded / NEUTRAL / 'artifact' candidates are dropped (absent from the
    result). Over-budget or a router-level failure returns ``{}`` (frame nothing this scan)."""
    framings: dict[str, dict] = {}
    for s in surfaced:
        m = s.markers
        cand = Theme(name=m.basket or "discovered", symbol=m.symbol, direction=s.direction,
                     thesis="", source="sentinel", markers=markers_dict(m))
        pack = sentinel_context_pack(cand, as_of=as_of)
        if not pack.grounded:
            continue  # no markers → nothing to adjudicate → drop (no spend on this one)
        sys, user = framer_prompt(pack)
        try:
            resp = router.call(role="framer", system=sys, user=user)
        except BudgetExceeded as e:
            log.warning("Framer over budget (%s) — framing NOTHING this scan (fail-closed).", e)
            return {}
        except RouterError as e:
            log.warning("Framer dropped %s (%s) — provider error.", m.symbol, e)
            continue
        raw = parse_framer(resp.text)
        conf, _fr = apply_filter([str(raw.get("seed_thesis", "")), str(raw.get("theme", ""))],
                                 pack, confidence=raw.get("confidence"))
        if conf == "NEUTRAL" or raw.get("confound") == "artifact":
            continue  # skeptic: abstain or a data artifact → DROP (don't surface)
        direction = str(raw.get("direction", s.direction)).strip().lower()
        if direction not in ("bullish", "bearish"):
            direction = s.direction
        framings[m.symbol] = {
            "direction": direction,
            "theme": str(raw.get("theme") or m.basket),
            "seed_thesis": str(raw.get("seed_thesis") or ""),
            "structural_vs_fad": raw.get("structural_vs_fad"),
            "conviction": conf,
            "confound_label": raw.get("confound"),
            "cost_usd": resp.cost_usd, "provider": resp.provider, "model": resp.model,
        }
    return framings


def build_framer_router(config: dict, llm_keys: dict):
    """A Router for the framer role (decorrelated from the council), with the discovery cost cap.
    Reuses the council router/provider adapters; raises RouterError (fail-closed) if the mapped
    provider has no key."""
    disc = config.get("discovery", {})
    council = config.get("council", {})
    cfg = {"council": {
        "roles": {"framer": disc.get("framer", {})},
        "prices_per_mtok": council.get("prices_per_mtok", {}),
        "cost_cap_usd": disc.get("cost_cap_usd"),
        "timeout_s": disc.get("timeout_s", council.get("timeout_s", 60)),
        "max_retries": disc.get("max_retries", council.get("max_retries", 2)),
    }}
    return build_router(cfg, llm_keys)


def sentinel_fake_responder(role: str, system: str, user: str) -> str:
    """Deterministic framer output for ``--demo`` / tests (mirrors SyntheticChainProvider). Echoes
    the candidate parsed from the prompt's ``CANDIDATE:`` header into a 'real_inflection' framing."""
    sym, direction, theme = "UNKNOWN", "bullish", "discovered"
    for line in user.splitlines():
        if line.startswith("CANDIDATE:"):
            parts = line[len("CANDIDATE:"):].strip().split(maxsplit=2)
            if len(parts) >= 2:
                sym, direction = parts[0], parts[1]
            if len(parts) >= 3:
                theme = parts[2]
            break
    return json.dumps({
        "confound": "real_inflection", "direction": direction, "theme": theme,
        "structural_vs_fad": "structural",
        "seed_thesis": f"(demo) {sym} markers show motion consistent with {theme}.",
        "confidence": "HIGH",
    })
