"""Survivor-card pipeline — STAGE B: the bounded LLM thesis-drafting layer (charter §3b).

Governing spec: ``records/2026-07-14_reach_channels_charter_RATIFIED.md`` §3b (ticker-bearing
item → deterministic screen → premise-currency pull → **draft thesis with falsifier attached**)
reconciled with §2's **no-LLM-thesis-synthesis-from-the-stream** rule. The reconciliation is
structural, not rhetorical: the draft GROUNDS ON PRINTS ONLY — the card's premise numbers
(already computed by Stage A), the §9 filed-XBRL fundamentals lines, cached headline
counts/titles, and the most recent structural filings. The surfacing item (the stream) enters
the grounding pack ONLY as a POINTER under an explicit header (:data:`POINTER_HEADER`) telling
the model it is NOT evidence — the thesis must trace to the prints below it.

Disciplines carried over from the council/framer lineage:

- **One bounded LLM call per survivor** through the council router infrastructure
  (``config["reach"]["drafter"]`` role config, default gemini flash-class), with the router's
  first-class cost ledger and a hard per-run cost cap (default $0.50). Cap hit → this and every
  remaining survivor ships UNDRAFTED with a counted note (never a silent stop).
- **Kill-before-spend** (:func:`risk.kill_switch_active` checked before ANY call — the
  discipline applies to ALL LLM spend, offline operator tools included).
- **The #37 parse discipline**: post-parse REQUIRED-KEY validation (a "valid but empty shape"
  JSON is a parse failure in a new costume), the bounded bracket tail-repair via
  ``council.agents.extract_json`` where importable, raw text + finish_reason preserved for
  forensics. A parse/validation failure ships that card with the Stage-B section reading
  "draft failed (parse) — counted" — NEVER a fabricated draft, NEVER a crash (fail-soft).
- **The per-thesis provenance guard** (charter §3b): a drafted card's provenance flips
  ``machine_surfaced`` → ``machine_surfaced_machine_drafted`` (the ratified tag); an undrafted
  or parse-failed card KEEPS ``machine_surfaced``. The draft section carries a one-line
  provenance+model stamp.
- **No ranking anywhere** (charter law): drafting preserves the caller's (alphabetical) card
  order; no score/rank/relevance field exists in this module's schema.

Everything here is pure / injection-driven (offline-testable via ``FakeRouter``); the runner
(``scripts/survivor_cards_run.py --draft``) wires the live router + cache-first grounding
sources. This is an operator tool: it never touches the orchestrator, the deterministic live
gates, the council, or any book. Nothing here can stale the §5 clock.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

import risk
from council.router import BudgetExceeded, RouterError, build_router
from survivor_cards import SurvivorCard, _pct

log = logging.getLogger("card_drafts")

try:  # the #37 discipline's bounded bracket tail-repair, where importable
    from council.agents import extract_json as _extract_json
except Exception:  # pragma: no cover — strict-parse fallback (still fail-closed)
    def _extract_json(text: str) -> dict:
        obj = json.loads(text)
        if not isinstance(obj, dict):
            raise ValueError("not a JSON object")
        return obj

try:  # reuse the council's metric-aware §9 line renderer (never-raise by contract)
    from council.context import _fmt_fundamental_line
except Exception:  # pragma: no cover — degrade to the raw dict (honest, ugly, never wrong)
    def _fmt_fundamental_line(ln: dict) -> str | None:
        return f"- {json.dumps(ln, sort_keys=True)}" if ln.get("value") is not None else None

# Charter §3b: the ratified tag a DRAFTED card carries (Stage A emits "machine_surfaced").
PROVENANCE_DRAFTED = "machine_surfaced_machine_drafted"

# The §2-reconciliation header, verbatim in every grounding pack: the surfacing item is a
# pointer, never evidence — the thesis must trace to the prints listed below it.
POINTER_HEADER = "SURFACED VIA (pointer — NOT evidence; the thesis must trace to the prints below)"

# Output schema (the #37 discipline: every key REQUIRED post-parse; absent → parse_error).
REQUIRED_KEYS = ("direction", "thesis", "falsifier", "weakest_point", "evidence_cited")

# Role-config defaults (config["reach"]["drafter"] overrides; gemini flash-class by default).
DEFAULT_DRAFTER = {
    "provider": "gemini",
    "model": "gemini-3.1-flash-lite",
    "max_tokens": 2048,
    "cost_cap_usd": 0.50,
}

DRAFTER_SYSTEM = (
    "You draft a candidate trade thesis for a long-dated far-OTM cheap-convexity options book. "
    "EVIDENCE DISCIPLINE (hard): reason ONLY from the PRINTS provided — filed fundamentals, "
    "filings, tape/premise numbers, headline counts. The 'SURFACED VIA' item at the top is a "
    "POINTER explaining why this name is in front of you; it is NOT evidence — never cite it, "
    "never quote it, and never build the thesis on it. A downstream deterministic IV gate "
    "decides CHEAPNESS — do not opine on it. A human operator judges admission — you DRAFT, "
    "you never decide. Be skeptical and concrete: the falsifier must be ONE falsifiable "
    "statement anchored to a print with a concrete date or metric threshold, and the weakest "
    "point must be stated honestly. If the prints are too thin to support a thesis, say so in "
    "the thesis and make the weakest point 'insufficient prints'. Reply with ONE JSON object "
    "and nothing else: {direction ('bullish'|'bearish'), thesis (2-4 sentences, each claim "
    "traceable to a print), falsifier (one print-anchored falsifiable statement with a date or "
    "metric), weakest_point (1 sentence), evidence_cited (array of strings, each naming a "
    "print used)}."
)


# ── the grounding pack (prints only; the surfacing item as pointer) ────────────
def _headline_block(headlines: list[dict] | None, as_of: datetime, max_titles: int) -> list[str]:
    """Cached headline counts/titles (``data/news.py`` records). ``None`` = cache unavailable —
    rendered as unknown, never as zero (staleness honesty)."""
    if headlines is None:
        return ["- (news cache unavailable this run — counts unknown, not zero)"]
    def _n(days: int) -> int:
        floor = (as_of - timedelta(days=days)).isoformat()
        return sum(1 for r in headlines if str(r.get("ts", "")) >= floor)
    lines = [f"- count trailing 7d / 90d: {_n(7)} / {_n(90)}"]
    recent = sorted(headlines, key=lambda r: str(r.get("ts", "")))[-max_titles:]
    for r in reversed(recent):
        lines.append(f"- {str(r.get('ts', ''))[:10]}: {r.get('headline', '')}")
    return lines


def build_grounding_pack(
    card: SurvivorCard,
    *,
    as_of: datetime,
    fundamentals: dict | None = None,
    headlines: list[dict] | None = None,
    max_titles: int = 5,
) -> str:
    """One survivor's grounding pack — PRINTS ONLY, with the surfacing item as a pointer.

    ``fundamentals`` is a ``FundamentalsData.corpus_asof`` result (``{"lines", "status", ...}``)
    or ``None`` (unavailable — rendered honestly, never invented). ``headlines`` is the cached
    ``data/news.py`` record list or ``None``. The premise numbers and the screen's band-fit
    detail are Stage A's already-computed prints. Order is load-bearing: the pointer header
    says "the prints below", so the pointer section comes FIRST."""
    lines = [f"CARD: {card.symbol}", f"AS_OF: {as_of.isoformat(timespec='seconds')}", ""]
    lines.append(f"{POINTER_HEADER}:")
    for ex in card.surfaced_via:
        link = f" — {ex.link}" if ex.link else ""
        lines.append(f"- {ex.channel}/{ex.source} — {ex.title}{link}")
    lines += ["", "PRINTS — the evidence; every thesis claim must trace here:", ""]

    lines.append("PREMISE NUMBERS (deterministic screen, this run):")
    p = card.premise
    if p is None:
        lines.append("- (unavailable — market/cache pulls skipped this run)")
    else:
        lines.append(f"- trailing return 1m / 12m: {_pct(p.ret_1m)} / {_pct(p.ret_12m)}")
        lines.append(f"- analyst count: {p.analyst_count} (cached {p.analyst_asof})"
                     if p.analyst_count is not None else "- analyst count: n/a (not in cache)")
        lines.append(f"- last 10-K/10-Q: {p.last_periodic_filing or 'n/a (not in cache)'}")
    try:  # the screen's quote-derived structure numbers are computed prints too
        band = card.screen.axis("band_fit")
        lines.append(f"- structure read ({band.status}"
                     f"{', PROVISIONAL quote' if band.provisional else ''}): {band.detail}")
    except StopIteration:  # pragma: no cover — a card always carries all four axes
        pass

    lines += ["", "FUNDAMENTALS (filed XBRL, point-in-time; period/filed dates on each line):"]
    fund_lines = (fundamentals or {}).get("lines") or []
    rendered = [r for r in (_fmt_fundamental_line(ln) for ln in fund_lines) if r]
    if rendered:
        status = (fundamentals or {}).get("status")
        if status and status != "ok":
            lines.append(f"- (corpus status: {status})")
        lines += rendered
    else:
        lines.append("- (none cached — fundamentals unavailable this run, not zero)")

    lines += ["", "RECENT HEADLINES (cache-first, titles only):"]
    lines += _headline_block(headlines, as_of, max_titles)

    lines += ["", "RECENT STRUCTURAL FILINGS (event-leg forms, newest first):"]
    filings = [s for s in (p.structural_filings if p else ()) if s]
    lines += [f"- {s}" for s in filings] or ["- none in cache"]
    return "\n".join(lines)


# ── the #37 parse discipline ───────────────────────────────────────────────────
def parse_draft(text: str, *, finish_reason=None, thoughts_tokens=None) -> dict:
    """Parse one drafter response → the validated draft dict, or a ``parse_error`` record.

    Post-parse REQUIRED-KEY validation (the #37 discipline: a syntactically valid JSON missing
    its required keys is JSON-mode's "valid but empty shape" — fail-closed); the raw text +
    provider finish_reason ride the failure record for forensics. NEVER fabricates a draft."""
    def _fail(reason: str) -> dict:
        return {"parse_error": True, "validation_error": reason,
                "raw_text": (text or "")[:2000],
                "finish_reason": finish_reason, "thoughts_tokens": thoughts_tokens}

    try:
        d = _extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        return _fail(f"extract_json: {e}")
    missing = [k for k in REQUIRED_KEYS if k not in d]
    if missing:
        return _fail(f"missing required keys: {missing}")
    direction = str(d.get("direction", "")).strip().lower()
    if direction not in ("bullish", "bearish"):
        return _fail(f"direction not bullish|bearish: {d.get('direction')!r}")
    for k in ("thesis", "falsifier", "weakest_point"):
        if not isinstance(d.get(k), str) or not d[k].strip():
            return _fail(f"{k!r} must be a non-empty string")
    ev = d.get("evidence_cited")
    if (not isinstance(ev, list) or not ev
            or not all(isinstance(s, str) and s.strip() for s in ev)):
        # an evidence-free draft is untraceable to the prints → fail-closed, same as absent
        return _fail("'evidence_cited' must be a non-empty array of strings")
    return {"parse_error": False, "direction": direction, "thesis": d["thesis"].strip(),
            "falsifier": d["falsifier"].strip(), "weakest_point": d["weakest_point"].strip(),
            "evidence_cited": [s.strip() for s in ev]}


# ── section rendering (consumed by survivor_cards.assemble_cards) ─────────────
def _status_section(status_line: str) -> list[str]:
    return ["### Draft thesis", "", f"_{status_line}_", ""]


def _draft_section(draft: dict, resp) -> list[str]:
    stamp = (f"drafted by {resp.provider}/{resp.model} · reach.drafter · "
             f"${resp.cost_usd:.4f}")
    return [
        "### Draft thesis",
        "",
        f"- direction: {draft['direction']}",
        f"- thesis: {draft['thesis']}",
        f"- falsifier: {draft['falsifier']}",
        f"- weakest point: {draft['weakest_point']}",
        "- evidence cited: " + " · ".join(draft["evidence_cited"]),
        f"- provenance: {PROVENANCE_DRAFTED} — _{stamp}_",
        "",
    ]


# ── the drafting run ───────────────────────────────────────────────────────────
@dataclass
class DraftRunResult:
    """Per-run outcome. ``cards`` preserves the input order (NO ranking — charter law) with
    provenance flipped only where a draft VALIDATED; ``sections[symbol]`` is the rendered
    Stage-B section for every input card. Deliberately no score/rank field."""

    cards: list[SurvivorCard] = field(default_factory=list)
    sections: dict[str, list[str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    n_drafted: int = 0
    n_parse_failed: int = 0
    n_undrafted: int = 0


def draft_survivors(
    cards: list[SurvivorCard],
    *,
    router,
    pack_builder: Callable[[SurvivorCard], str],
    kill_check: Callable[[], bool] | None = None,
) -> DraftRunResult:
    """ONE bounded LLM call per survivor, fail-soft everywhere (a draft failure never loses a
    card — it ships undrafted/parse-failed with its section saying so, counted).

    Kill-before-spend: ``kill_check`` (default :func:`risk.kill_switch_active`) runs BEFORE any
    call — active → zero LLM calls, every card ships undrafted. ``BudgetExceeded`` (the
    router's fail-closed per-run cap) → this and every remaining survivor ships undrafted with
    one counted note. A per-card provider failure (``RouterError``) or parse/validation failure
    drops only that card's draft — provenance stays ``machine_surfaced``."""
    out = DraftRunResult()
    if not cards:
        return out
    if (kill_check or risk.kill_switch_active)():
        out.notes.append(f"kill switch ACTIVE — Stage-B drafting skipped for all "
                         f"{len(cards)} survivor(s) (0 LLM calls; kill-before-spend)")
        for c in cards:
            out.cards.append(c)
            out.sections[c.symbol] = _status_section(
                "undrafted — kill switch active (no LLM spend); counted")
            out.n_undrafted += 1
        return out

    capped = False
    for c in cards:
        if capped:
            out.cards.append(c)
            out.sections[c.symbol] = _status_section(
                "undrafted — per-run drafter cost cap reached before this call; counted")
            out.n_undrafted += 1
            continue
        try:
            user = pack_builder(c)
        except Exception as e:  # noqa: BLE001 — fail-soft: a grounding bug never loses the card
            log.warning("drafter grounding failed for %s: %s", c.symbol, e)
            out.notes.append(f"{c.symbol}: draft failed (grounding: {type(e).__name__}: {e}) "
                             "— shipped undrafted")
            out.cards.append(c)
            out.sections[c.symbol] = _status_section("draft failed (grounding error) — counted")
            out.n_undrafted += 1
            continue
        try:
            resp = router.call(role="drafter", system=DRAFTER_SYSTEM, user=user)
        except BudgetExceeded as e:
            capped = True
            remaining = len(cards) - len(out.cards)
            out.notes.append(f"drafter cost cap hit ({e}) — {remaining} survivor(s) shipped "
                             "undrafted")
            out.cards.append(c)
            out.sections[c.symbol] = _status_section(
                "undrafted — per-run drafter cost cap reached before this call; counted")
            out.n_undrafted += 1
            continue
        except RouterError as e:
            log.warning("drafter provider error for %s: %s", c.symbol, e)
            out.notes.append(f"{c.symbol}: draft failed (provider: {e}) — shipped undrafted")
            out.cards.append(c)
            out.sections[c.symbol] = _status_section("draft failed (provider error) — counted")
            out.n_undrafted += 1
            continue
        d = parse_draft(resp.text, finish_reason=resp.finish_reason,
                        thoughts_tokens=resp.thoughts_tokens)
        if d["parse_error"]:
            log.warning("drafter parse-fail %s/%s for %s: %s (finish=%s, thoughts=%s)",
                        resp.provider, resp.model, c.symbol, d.get("validation_error"),
                        resp.finish_reason, resp.thoughts_tokens)
            out.notes.append(f"{c.symbol}: draft parse-fail "
                             f"({d.get('validation_error')}) — shipped undrafted")
            out.cards.append(c)  # provenance STAYS machine_surfaced (never a fabricated draft)
            out.sections[c.symbol] = _status_section("draft failed (parse) — counted")
            out.n_parse_failed += 1
            continue
        out.cards.append(replace(c, provenance=PROVENANCE_DRAFTED))
        out.sections[c.symbol] = _draft_section(d, resp)
        out.n_drafted += 1
    return out


# ── router wiring (reuses the council router/provider adapters + price table) ─
def drafter_config(config: dict) -> dict:
    """The reach.drafter role config with defaults overlaid (config-over-code)."""
    reach = ((config.get("reach") or {}).get("drafter")) or {}
    return {**DEFAULT_DRAFTER, **reach}


def build_drafter_router(config: dict, llm_keys: dict):
    """A Router for the ``reach.drafter`` role — the ``build_framer_router`` pattern.

    Reuses the council's provider adapters, price table, and generation knobs (a gemini-3.x
    drafter needs ``thinking_level=minimal`` for the same #37 starvation reason the framer
    does); the per-RUN cost cap is ``reach.drafter.cost_cap_usd`` (default $0.50), fail-closed
    at the router boundary. Raises ``RouterError`` if the mapped provider has no key — the
    caller may fall back to ``FakeRouter`` for keyless/offline runs (the council --demo
    pattern)."""
    dc = drafter_config(config)
    council = config.get("council", {})
    cfg = {"council": {
        "roles": {"drafter": {"provider": dc["provider"], "model": dc["model"]}},
        "prices_per_mtok": council.get("prices_per_mtok", {}),
        "cost_cap_usd": float(dc["cost_cap_usd"]),
        "timeout_s": dc.get("timeout_s", council.get("timeout_s", 60)),
        "max_retries": dc.get("max_retries", council.get("max_retries", 2)),
        "max_tokens": int(dc["max_tokens"]),
        "gemini": council.get("gemini", {}),
        "openai": council.get("openai", {}),
    }}
    return build_router(cfg, llm_keys)


def drafter_fake_responder(role: str, system: str, user: str) -> str:
    """Deterministic drafter output for keyless/offline runs (mirrors
    ``sentinel_fake_responder``): echoes the pack's ``CARD:`` symbol into a schema-valid,
    clearly ``(demo)``-labeled draft. No SDK, no network, $0."""
    sym = "UNKNOWN"
    for line in user.splitlines():
        if line.startswith("CARD:"):
            sym = line[len("CARD:"):].strip() or sym
            break
    return json.dumps({
        "direction": "bullish",
        "thesis": f"(demo) {sym} passed the deterministic screen; this offline draft is a "
                  "placeholder grounded on the premise prints only.",
        "falsifier": f"(demo) if {sym}'s next 10-Q (within 120 days) prints TTM revenue growth "
                     "<= 0%, the thesis fails.",
        "weakest_point": "(demo) offline responder — no live grounding was read.",
        "evidence_cited": ["premise: trailing returns", "filings: last periodic filing"],
    })
