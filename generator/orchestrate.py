"""P3 — the ``--generate`` entry (kill + cost gates DEFAULT-CLOSED; ``PREREG_THEME_GENERATOR §6``).

The generator's runnable entry point. It mirrors ``orchestrator.py --discover`` exactly where it
matters: **kill-before-spend**, FakeRouter the DEFAULT (a live run is an explicit, gated act), and
**fail-closed to ZERO theses** on an over-budget / provider failure. It is INERT by default —
``forward_enabled`` AND ``generator.enabled`` must BOTH be set for a live (real-corpus, real-LLM)
run; otherwise only ``--demo`` (FakeRouter + a fixture corpus) proceeds. Pre-freeze, even a live run
stays fixture-bound by §5; the live-corpus wiring is held behind these gates.

Write isolation (§6.4): the ONLY artifact is ``records/generator/<date>_generated_theses.json`` —
routed through :data:`generator.GENERATOR_RECORDS_DIR`. It writes NO register, NO config, NO
universe, and nothing under ``records/`` outside the generator subtree (the merge-blocker
``tests/test_generator_isolation.py`` asserts this statically).

Entry: ``python -m generator.orchestrate`` (``--demo`` for the offline FakeRouter path). This module
is part of ``generator/`` and the live loop never imports it (the import-graph guard).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from council.router import BudgetExceeded, FakeRouter, RouterError
from generator import GENERATOR_RECORDS_DIR
from generator.prompts import synthesis_prompt_sha
from generator.synthesize import synthesize

log = logging.getLogger("generator.orchestrate")


@dataclass(frozen=True)
class GenerateResult:
    """The outcome of one ``--generate`` run: the verified theses + the split DROP counters + the
    written artifact path (None when nothing was written — kill / over-budget / inert)."""

    theses: list[dict[str, Any]]
    n_parsed: int
    dropped_entity_unresolved: int
    dropped_fact_untraced: int
    artifact_path: str | None
    note: str

    @property
    def n_theses(self) -> int:
        return len(self.theses)


def _build_router(config: dict, *, demo: bool) -> Any | None:
    """The synthesis router. ``demo`` → deterministic FakeRouter (no keys/network, the §5 default).

    Live → a CONFIG-DRIVEN router for the generator role (``council.router.build_router`` over
    ``config.generator.roles`` overlaid onto the council scaffolding). Returns ``None`` (fail-closed)
    when a mapped provider has no key — the run then generates nothing this pass. The cost cap rides
    the ledger (``generator.cost_cap_usd``), enforced fail-closed at the router boundary.
    """
    gen = config.get("generator", {})
    cap = gen.get("cost_cap_usd")
    if demo:
        return FakeRouter(cap_usd=float(cap) if cap is not None else None)
    # Live: the generator roster (§2 / §10) lives in config.generator.roles; build via the council
    # router so the cost ledger + fail-closed missing-key behavior are shared. Held behind the
    # forward_enabled/generator.enabled gates in run_generate — never reached by --demo or tests.
    from council.router import CostLedger, build_router
    cfg = dict(config)
    # Route build_router at the generator roster while keeping council prices/knobs for the ledger.
    council = dict(config.get("council", {}))
    council["roles"] = gen.get("roles", {})
    if "cost_cap_usd" in gen:
        council["cost_cap_usd"] = gen["cost_cap_usd"]
    cfg["council"] = council
    try:
        return build_router(cfg, config.get("llm_keys", {}),
                            ledger=CostLedger(cap_usd=float(cap) if cap is not None else None))
    except RouterError as e:
        log.error("Generator router unavailable (%s) — generating NOTHING this run (fail-closed).", e)
        return None


def _artifact_path(as_of: datetime) -> Path:
    """``records/generator/<YYYY-MM-DD>_generated_theses.json`` — the SOLE write target (§6.4)."""
    return Path(GENERATOR_RECORDS_DIR) / f"{as_of.date().isoformat()}_generated_theses.json"


def _write_artifact(path: Path, payload: dict[str, Any]) -> None:
    """Persist the generated-theses artifact (the only generator write). Creates the
    ``records/generator/`` subtree; never writes anywhere else."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))


def run_generate(
    *,
    demo: bool = False,
    corpus: dict[str, list[dict[str, Any]]] | None = None,
    cache: Any | None = None,
    as_of: datetime | None = None,
    config: dict[str, Any] | None = None,
    write: bool = True,
    seed_theme: str | None = None,
) -> GenerateResult:
    """One generation pass: kill-gate → router → synthesize → §3 VERIFY → write ``records/generator/``.

    Kill-before-spend (the FIRST check) and over-budget fail-closed are honored exactly like
    ``--discover``. ``corpus`` / ``cache`` are injectable for the fixture-inert tests (and the
    Phase-0 corpus read in the live path); when omitted on a live run they are read via
    ``generator.read`` against the PIT cache. Returns a :class:`GenerateResult` (the verified theses +
    split DROP counters + the artifact path, or a no-write note for a halted/inert run).
    """
    # ── kill-before-spend (mirrors orchestrator.run_discover) ──
    from risk import kill_switch_active
    if kill_switch_active():
        log.warning("KILL switch engaged — generation halted (no synthesis, no spend).")
        return GenerateResult([], 0, 0, 0, None, "killed")

    if config is None:
        from config_loader import load_config
        config = load_config()
    gen = config.get("generator", {})

    # ── INERT by default: a live run needs BOTH forward_enabled AND generator.enabled ──
    if not demo:
        if not bool(config.get("forward_enabled", False)):
            log.info("FORWARD_ENABLED=false — generator inert (no synthesis, no spend).")
            return GenerateResult([], 0, 0, 0, None, "forward_disabled")
        if not gen.get("enabled", False):
            log.info("generator.enabled=false — generator inert (no synthesis, no spend).")
            return GenerateResult([], 0, 0, 0, None, "generator_disabled")

    # ── seed-slice feasibility (PREREG_SEEDED_GENERATOR_DIAGNOSTIC P1): a slice with no non-ETF
    #    entity-RESOLVABLE source cannot satisfy leg (c) — fail closed BEFORE any router build / spend,
    #    rather than filing a misattributed negative. Live path only (demo injects its own corpus). ──
    if seed_theme and not demo and corpus is None:
        from corpus.content import load_content
        from generator.score import slice_feasible
        if not slice_feasible(seed_theme, content=load_content(), config=config):
            log.warning("seed theme '%s' slice has no non-ETF entity-resolvable source — leg (c) is "
                        "unsatisfiable; refusing to spend (PREREG_SEEDED_GENERATOR_DIAGNOSTIC P1).", seed_theme)
            return GenerateResult([], 0, 0, 0, None, "seed_slice_infeasible")

    as_of = as_of or datetime.now(UTC)
    router = _build_router(config, demo=demo)
    if router is None:
        return GenerateResult([], 0, 0, 0, None, "router_failclosed")

    # Live Phase-0 corpus read (fixture path injects corpus+cache). §5: pre-freeze a live run is still
    # fixture-bound; the read here is the explicit, gated wiring.
    if cache is None or corpus is None:
        if demo:
            corpus = corpus or {}
        else:
            from corpus.content import load_content, restrict_to_theme
            from data.cache import PointInTimeCache
            from generator.read import read_corpus
            cache = cache or PointInTimeCache(config.get("cache_dir", "data/cache"))
            content = load_content()
            if seed_theme:  # the seeded slice (PREREG_SEEDED_GENERATOR_DIAGNOSTIC) — restrict to one theme
                content = restrict_to_theme(content, seed_theme)
            corpus = corpus if corpus is not None else read_corpus(cache, as_of, content, config)

    # ── synthesize → §3 VERIFY (fail-closed to ZERO on over-budget / provider error) ──
    coercion_map = gen.get("vocab_coercion_map") or {}
    try:
        result = synthesize(corpus, router=router, coercion_map=coercion_map,
                            verify_against=cache)
    except BudgetExceeded as e:
        log.warning("Generator over budget (%s) — generating NOTHING this run (fail-closed).", e)
        return GenerateResult([], 0, 0, 0, None, "over_budget")
    except RouterError as e:
        log.warning("Generator router error (%s) — generating NOTHING this run (fail-closed).", e)
        return GenerateResult([], 0, 0, 0, None, "router_error")

    vr = result.verify
    de = vr.dropped_entity_unresolved if vr else 0
    df = vr.dropped_fact_untraced if vr else 0
    log.info(
        "Generator: parsed=%d kept=%d dropped(entity=%d, fact=%d) · over-citation mean=%0.2f coords/entity",
        len(result.parsed), len(result.claims), de, df,
        vr.mean_coords_per_entity if vr else 0.0,
    )

    artifact = None
    if write:
        path = _artifact_path(as_of)
        payload = {
            "as_of": as_of.isoformat(),
            "provenance": "generated",
            "seed_theme": seed_theme,
            "model": result.model,            # §3 matched-version stamp (the scorer asserts these match)
            "prompt_sha": synthesis_prompt_sha(),
            "n_parsed": len(result.parsed),
            "n_theses": len(result.claims),
            "dropped_entity_unresolved": de,
            "dropped_fact_untraced": df,
            "dropped_total": de + df,
            "over_citation": {
                "mean_coords_per_entity": round(vr.mean_coords_per_entity, 4) if vr else 0.0,
                "mean_citation_count": round(vr.mean_citation_count, 4) if vr else 0.0,
            },
            "theses": result.claims,
        }
        _write_artifact(path, payload)
        artifact = str(path)
        log.info("Wrote %d generated thesis(es) → %s", len(result.claims), artifact)

    return GenerateResult(
        theses=result.claims, n_parsed=len(result.parsed),
        dropped_entity_unresolved=de, dropped_fact_untraced=df,
        artifact_path=artifact, note="ok",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dramatic Options theme GENERATOR (Stage 1; --generate). PROPOSER only — the "
        "council judges and the deterministic gate disposes (the hard seam).")
    parser.add_argument("--demo", action="store_true",
                        help="Offline FakeRouter + fixture corpus (no creds/network/live-corpus).")
    parser.add_argument("--seed-theme", default=None,
                        help="Restrict synthesis to ONE routed theme's corpus slice "
                             "(PREREG_SEEDED_GENERATOR_DIAGNOSTIC; e.g. nuclear_fuel).")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    res = run_generate(demo=args.demo, seed_theme=args.seed_theme)
    log.info("generate done: %d thesis(es), note=%s, artifact=%s",
             res.n_theses, res.note, res.artifact_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
