"""generator/score.py — the seeded-diagnostic SCORER (PREREG_SEEDED_GENERATOR_DIAGNOSTIC §4–§5).

Pre-committed **BLIND before any bounded-live run** — the operationalization of the frozen legs, frozen
here so no scoring choice is made with emissions visible (the same anti-HARK discipline as the criterion
pin). A reader-of-artifacts → a verdict: it computes the **Stage-1 (fully offline)** escalation verdict +
the exact **Stage-2 candidate list**. Stage-2's `under_narrated` council re-score is the ONE live input;
this module reduces it to a fixed candidate list and computes the yield around it once labels return.

PURE: every input is a param (artifacts, register keys, ETF holdings, second-order sources) so each
net-new number is hand-checkable. INERT: imports no market/live module; the trading loop never imports it
(the import-graph guard); any persisted report goes under ``GENERATOR_RECORDS_DIR``.

Operationalization pins (frozen with the legs — see the §8 appendix of the pre-reg):
- (i) names in the register (incl. *source-departed, retained*) count as IN-register → not novel (leg a);
- (ii) the (c) ETF-membership check reads the seed's ETF constituents **PIT as-of the run date** (the
  caller supplies that set);
- (iii) c2 — the entity must be ∉ the seed's ETF **regardless** of an ETF co-citation.
"""

from __future__ import annotations

from typing import Any

from corpus.content import read_coords, restrict_to_theme
from corpus.etf_constituents import SOURCE as ETF_SOURCE
from generator.entity import _norm


def assert_matched_version(artifacts: list[dict[str, Any]]) -> tuple[str, str]:
    """§3 matched-version, as an ASSERTION not an assumption: every artifact must carry ``model`` +
    ``prompt_sha`` and ALL must be equal. A missing field (a pre-stamp run) or a mixed set is REFUSED
    (fail-closed). Returns the shared (model, prompt_sha)."""
    if not artifacts:
        raise ValueError("no artifacts to score")
    versions: set[tuple[str, str]] = set()
    for a in artifacts:
        model, sha = a.get("model"), a.get("prompt_sha")
        if not model or not sha:
            raise ValueError(f"artifact as_of={a.get('as_of')} lacks model/prompt_sha — cannot count "
                             f"toward the matched k-set (pre-stamp runs are non-load-bearing references)")
        versions.add((model, sha))
    if len(versions) != 1:
        raise ValueError(f"mixed model/prompt versions across the k-set: {sorted(versions)} — refusing to score")
    return next(iter(versions))


def second_order_sources(seed_theme: str, *, content: dict[str, Any], config: dict[str, Any],
                         etf_source: str = ETF_SOURCE) -> set[str]:
    """Theme-general (§4): the seed slice's cited sources MINUS the ETF source (for ``nuclear_fuel`` →
    ``{nrc, eia}``). Derived from the routing — never hardcoded — so a new seed theme needs no edit."""
    sliced = read_coords(restrict_to_theme(content, seed_theme), config)
    return {src for src, _ in sliced if src != etf_source}


def _entities(artifact: dict[str, Any]) -> list[tuple[str, frozenset[str]]]:
    """Per kept thesis: each named entity's normalized key (ticker, else canonical) + the thesis's cited
    sources. Exact normalization only (`generator.entity._norm`) — NO fuzzy matching (frozen §4)."""
    out: list[tuple[str, frozenset[str]]] = []
    for claim in artifact.get("theses", []):
        srcs = frozenset(c.get("source") for c in (claim.get("citations") or []) if c.get("source"))
        for e in claim.get("named_entities", []):
            key = _norm(e.get("ticker") or e.get("canonical") or "")
            if key:
                out.append((key, srcs))
    return out


def score_arm(artifacts: list[dict[str, Any]], *, register_keys: set[str], second_order_srcs: set[str],
              etf_holdings: set[str], stability_min: int = 3) -> dict[str, Any]:
    """One arm's §4 read → the STABLE qualifying entity set. An entity QUALIFIES in a run iff
    (a) not in ``register_keys`` AND (c) the thesis cites a second-order source AND the entity ∉
    ``etf_holdings``. STABLE = qualifies in ≥ ``stability_min`` of the k runs (factors out variance)."""
    reg = {_norm(k) for k in register_keys}
    etf = {_norm(k) for k in etf_holdings}
    per_run: list[set[str]] = []
    for a in artifacts:
        q: set[str] = set()
        for key, cited in _entities(a):
            if key in reg:                                  # leg (a): already in the universe → not novel
                continue
            if (cited & second_order_srcs) and key not in etf:   # leg (c): second-order ∧ not-in-ETF (c2)
                q.add(key)
        per_run.append(q)
    counts: dict[str, int] = {}
    for q in per_run:
        for k in q:
            counts[k] = counts.get(k, 0) + 1
    stable = {k for k, n in counts.items() if n >= stability_min}
    drop = {
        "dropped_entity_unresolved": sum(a.get("dropped_entity_unresolved", 0) for a in artifacts),
        "dropped_fact_untraced": sum(a.get("dropped_fact_untraced", 0) for a in artifacts),
    }
    return {"stable_qualifying": stable, "per_run": [sorted(q) for q in per_run],
            "n_runs": len(artifacts), "stability_min": stability_min, "drop_split": drop}


def stage1(seeded: dict[str, Any], autonomous: dict[str, Any]) -> dict[str, Any]:
    """§5 Stage-1 (escalation — NECESSARY, not sufficient): a non-empty seeded stable set that is NOT a
    subset of the autonomous set. A subset ⇒ the slice isn't biting (training recall, not the corpus) — a
    plumbing-NEGATIVE, stop. ``stage2_candidates`` = BOTH arms' stable sets (the council labels both so
    the yields are comparable; leg (b) "different-from-autonomous" is NOT a success leg)."""
    s, a = seeded["stable_qualifying"], autonomous["stable_qualifying"]
    subset_plumbing_negative = bool(s) and s <= a
    return {
        "escalate": bool(s) and not subset_plumbing_negative,
        "subset_plumbing_negative": subset_plumbing_negative,
        "seeded_stable": sorted(s),
        "autonomous_stable": sorted(a),
        "stage2_candidates": sorted(s | a),
    }


def stage2_yield(stable: list[str], under_narrated: dict[str, bool]) -> int:
    """One arm's Stage-2 yield: of its stable-qualifying names, how many the council labeled
    ``under_narrated=True``. The ONE live input (the labels) is supplied; this is arithmetic around it."""
    return sum(1 for k in stable if under_narrated.get(k, False))


def final_verdict(seeded_stable: list[str], autonomous_stable: list[str],
                  under_narrated: dict[str, bool]) -> dict[str, Any]:
    """§5 confirmation: ``YIELD(seeded) > YIELD(autonomous)`` on the full bar (a)+(c)+``under_narrated``.
    A pass is an EXISTENCE PROOF for the seeded theme, not a validated accelerant (pre-reg §6)."""
    ys = stage2_yield(seeded_stable, under_narrated)
    ya = stage2_yield(autonomous_stable, under_narrated)
    return {"yield_seeded": ys, "yield_autonomous": ya, "confirmed": ys > ya}
