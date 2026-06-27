"""P3 tests — the ``--generate`` entry (kill + cost gates DEFAULT-CLOSED, write isolation).

``PREREG_THEME_GENERATOR §6``. Fixture-inert: FakeRouter / a scripted spy router + a seeded
``PointInTimeCache`` in a tmp cwd — NO network, NO keys, NO real LLM. Covers the gated invariants:

  - KILL present → ZERO LLM calls + zero theses + nothing written (kill-before-spend);
  - over-budget → fail-closed (no theses, no artifact);
  - INERT by default — a non-demo run with forward/generator disabled spends nothing;
  - a happy-path demo run synthesizes → §3-verifies → writes ONE artifact;
  - the RUNTIME write-isolation merge-blocker: the entry writes ONLY under ``records/generator/``.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import pytest

from corpus.etf_constituents import SOURCE as ETF_SOURCE
from data.cache import PointInTimeCache
from generator import orchestrate

_EARLY = datetime(1990, 1, 1, tzinfo=UTC)
_NOW = datetime(2026, 6, 1, tzinfo=UTC)
_TS = "2026-03-02T20:00:00+00:00"

# A synthesis-shaped §3 claim that RESOLVES against the seeded URNM record (so the happy path keeps it).
_GOOD = {
    "claim_id": "uranium_supply_squeeze",
    "statement": "Reactor restarts -> primary uranium deficit -> uranium miners.",
    "named_entities": [{"canonical": "Cameco Corp", "ticker": "CCJ", "aliases": ["Cameco"]}],
    "mechanism_direction": {"vocab": "shortage", "sign": "+"},
    "headline_quantities": [{"metric": "fund weight", "value": "12%", "bucket": "pct_10_25"}],
    "provenance": "generated",
    "citations": [{"source": ETF_SOURCE, "key": "URNM", "ts": _TS}],
}


class _SpyRouter:
    """A router that records every ``call`` so a kill/over-budget test can assert ZERO spend."""

    def __init__(self, payload=None):
        self.calls = 0
        self._text = json.dumps(payload) if payload is not None else json.dumps({"claims": []})

    def call(self, *, role, system, user, max_tokens=None):
        self.calls += 1
        from council.router import LLMResponse
        return LLMResponse(self._text, "fake", "fake-gen", 0, 0, 0.0)


def _cache(tmp_path):
    c = PointInTimeCache(tmp_path / "cache")
    c.write(ETF_SOURCE, "URNM", [
        {"ts": _TS, "etf": "URNM", "rank": 1, "name": "Cameco Corp", "symbol": "CCJ",
         "exchange": None, "us_listed": True, "weight_pct": 12.3, "shares": 100},
    ], coverage_from=_EARLY, coverage_through=_NOW)
    return c


def _records_tree(root):
    import glob
    return sorted(glob.glob(os.path.join(root, "records", "**"), recursive=True))


# ── KILL present → zero LLM calls, zero theses, nothing written ─────────────────────────────────

def test_kill_switch_halts_before_any_llm_call(tmp_path, monkeypatch):
    monkeypatch.setattr("risk.kill_switch_active", lambda: True)
    spy = _SpyRouter({"claims": [_GOOD]})
    monkeypatch.setattr(orchestrate, "_build_router", lambda config, *, demo: spy)
    monkeypatch.chdir(tmp_path)
    res = orchestrate.run_generate(demo=True, corpus={}, cache=_cache(tmp_path),
                                   config={"generator": {}}, as_of=_NOW)
    assert res.note == "killed"
    assert spy.calls == 0                       # kill-before-spend — the router was NEVER called
    assert res.n_theses == 0 and res.artifact_path is None
    assert _records_tree(tmp_path) == []        # nothing written


# ── over-budget → fail-closed (no theses, no artifact) ─────────────────────────────────────────

def test_over_budget_fails_closed_to_zero_theses(tmp_path, monkeypatch):
    monkeypatch.setattr("risk.kill_switch_active", lambda: False)
    # cap_usd=0.0 ⇒ the ledger is over_cap before the first call ⇒ BudgetExceeded on call().
    from council.router import FakeRouter
    monkeypatch.setattr(orchestrate, "_build_router",
                        lambda config, *, demo: FakeRouter(cap_usd=0.0))
    monkeypatch.chdir(tmp_path)
    res = orchestrate.run_generate(demo=True, corpus={}, cache=_cache(tmp_path),
                                   config={"generator": {}}, as_of=_NOW)
    assert res.note == "over_budget"
    assert res.n_theses == 0 and res.artifact_path is None
    assert _records_tree(tmp_path) == []


# ── INERT by default — non-demo with forward/generator disabled spends nothing ─────────────────

def test_inert_when_forward_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr("risk.kill_switch_active", lambda: False)
    spy = _SpyRouter()
    monkeypatch.setattr(orchestrate, "_build_router", lambda config, *, demo: spy)
    res = orchestrate.run_generate(demo=False, config={"forward_enabled": False, "generator": {}},
                                   corpus={}, cache=_cache(tmp_path), as_of=_NOW)
    assert res.note == "forward_disabled"
    assert spy.calls == 0 and res.artifact_path is None


def test_inert_when_generator_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr("risk.kill_switch_active", lambda: False)
    spy = _SpyRouter()
    monkeypatch.setattr(orchestrate, "_build_router", lambda config, *, demo: spy)
    res = orchestrate.run_generate(
        demo=False, config={"forward_enabled": True, "generator": {"enabled": False}},
        corpus={}, cache=_cache(tmp_path), as_of=_NOW)
    assert res.note == "generator_disabled"
    assert spy.calls == 0 and res.artifact_path is None


# ── happy path: synthesize → §3-verify → write ONE artifact ────────────────────────────────────

def test_demo_synthesizes_verifies_and_writes_one_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("risk.kill_switch_active", lambda: False)
    monkeypatch.setattr(orchestrate, "_build_router",
                        lambda config, *, demo: _SpyRouter({"claims": [_GOOD]}))
    monkeypatch.chdir(tmp_path)
    res = orchestrate.run_generate(demo=True, corpus={}, cache=_cache(tmp_path),
                                   config={"generator": {}}, as_of=_NOW)
    assert res.note == "ok" and res.n_theses == 1
    assert res.dropped_entity_unresolved == 0 and res.dropped_fact_untraced == 0
    # the artifact exists, under records/generator/, dated, with the verified thesis + counters.
    assert res.artifact_path == "records/generator/2026-06-01_generated_theses.json"
    payload = json.loads((tmp_path / res.artifact_path).read_text())
    assert payload["provenance"] == "generated" and payload["n_theses"] == 1
    assert payload["theses"][0]["claim_id"] == "uranium_supply_squeeze"
    assert payload["dropped_total"] == 0 and "over_citation" in payload


def test_restrict_to_theme_slices_coords():
    # the seeded slice (PREREG_SEEDED_GENERATOR_DIAGNOSTIC): restricting content to one theme yields a
    # non-empty PROPER SUBSET of the full coords, drawn only from that theme's routed sources.
    from corpus.content import load_content, read_coords, restrict_to_theme
    content = load_content()
    cfg = {"universe": {"themes": {}}}
    full = set(read_coords(content, cfg))
    sliced = set(read_coords(restrict_to_theme(content, "nuclear_fuel"), cfg))
    assert sliced and sliced < full              # the slice bites: a non-empty, STRICT subset of the full coords
    with pytest.raises(KeyError):
        restrict_to_theme(content, "not_a_routed_theme")   # a typo fails loud, not silently over everything


def test_demo_seed_theme_stamped_in_artifact(tmp_path, monkeypatch):
    # step-0 plumbing smoke: --seed-theme flows through run_generate into the artifact (the live slice
    # RESTRICTION itself is covered by test_restrict_to_theme_slices_coords).
    monkeypatch.setattr("risk.kill_switch_active", lambda: False)
    monkeypatch.setattr(orchestrate, "_build_router",
                        lambda config, *, demo: _SpyRouter({"claims": [_GOOD]}))
    monkeypatch.chdir(tmp_path)
    res = orchestrate.run_generate(demo=True, corpus={}, cache=_cache(tmp_path),
                                   config={"generator": {}}, as_of=_NOW, seed_theme="nuclear_fuel")
    assert res.note == "ok"
    payload = json.loads((tmp_path / res.artifact_path).read_text())
    assert payload["seed_theme"] == "nuclear_fuel"
    assert payload["model"] == "fake-gen" and len(payload["prompt_sha"]) == 16   # §3 matched-version stamp


def test_run_generate_restricts_corpus_to_seed_theme_in_live_read(tmp_path, monkeypatch):
    # P3 seam: the LIVE corpus read receives content RESTRICTED to the seed theme — the slicing the whole
    # experiment runs through (the demo/injected-corpus tests skip it).
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent
    monkeypatch.setattr("corpus.content.load_content",                       # CWD-robust real content
                        lambda *a, **k: json.loads((repo / "corpus_content.json").read_text()))
    captured = {}

    def _spy_read(cache, as_of, content, config):
        captured["content"] = content
        return {}

    monkeypatch.setattr("generator.read.read_corpus", _spy_read)
    monkeypatch.setattr("risk.kill_switch_active", lambda: False)
    monkeypatch.setattr(orchestrate, "_build_router", lambda config, *, demo: _SpyRouter({"claims": []}))
    # space_smallcap is FEASIBLE (federal_awards) so it passes the guard and reaches the read; nuclear_fuel
    # would be short-circuited by the feasibility guard (its own test below).
    orchestrate.run_generate(demo=False, seed_theme="space_smallcap", cache=object(), as_of=_NOW, write=False,
                             config={"forward_enabled": True, "generator": {"enabled": True}})
    assert list(captured["content"]["themes"].keys()) == ["space_smallcap"]   # restricted to the one theme


def test_run_generate_fails_closed_on_infeasible_seed_slice(tmp_path, monkeypatch):
    # P0/P1: nuclear_fuel's non-ETF sources (nrc/eia) are entity-FREE → leg (c) unsatisfiable → the
    # feasibility guard refuses to spend BEFORE the router build (never a misattributed negative).
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent
    monkeypatch.setattr("corpus.content.load_content",
                        lambda *a, **k: json.loads((repo / "corpus_content.json").read_text()))
    monkeypatch.setattr("risk.kill_switch_active", lambda: False)
    built = {"n": 0}
    monkeypatch.setattr(orchestrate, "_build_router",
                        lambda config, *, demo: built.__setitem__("n", built["n"] + 1) or _SpyRouter())
    res = orchestrate.run_generate(demo=False, seed_theme="nuclear_fuel", cache=object(), as_of=_NOW,
                                   write=False, config={"forward_enabled": True, "generator": {"enabled": True}})
    assert res.note == "seed_slice_infeasible" and built["n"] == 0   # refused BEFORE the router build (no spend)


def test_demo_drops_confabulated_entity_through_the_full_entry(tmp_path, monkeypatch):
    # End-to-end DROP: a fabricated entity flows synthesize → verify → DROP, and the artifact records it.
    bad = {**_GOOD, "claim_id": "ghost",
           "named_entities": [{"canonical": "Aldermarsh Photonics", "ticker": "ALDP"}],
           "headline_quantities": []}
    monkeypatch.setattr("risk.kill_switch_active", lambda: False)
    monkeypatch.setattr(orchestrate, "_build_router",
                        lambda config, *, demo: _SpyRouter({"claims": [_GOOD, bad]}))
    monkeypatch.chdir(tmp_path)
    res = orchestrate.run_generate(demo=True, corpus={}, cache=_cache(tmp_path),
                                   config={"generator": {}}, as_of=_NOW)
    assert res.n_parsed == 2 and res.n_theses == 1
    assert res.dropped_entity_unresolved == 1
    assert [t["claim_id"] for t in res.theses] == ["uranium_supply_squeeze"]


# ── RUNTIME write-isolation merge-blocker: writes ONLY under records/generator/ ─────────────────

def test_entry_writes_only_under_records_generator(tmp_path, monkeypatch):
    monkeypatch.setattr("risk.kill_switch_active", lambda: False)
    monkeypatch.setattr(orchestrate, "_build_router",
                        lambda config, *, demo: _SpyRouter({"claims": [_GOOD]}))
    monkeypatch.chdir(tmp_path)
    orchestrate.run_generate(demo=True, corpus={}, cache=_cache(tmp_path),
                             config={"generator": {}}, as_of=_NOW)
    tree = _records_tree(tmp_path)
    assert tree, "expected an artifact to be written"
    # EVERY records/ path the entry created is under records/generator/ — nothing else.
    offenders = [p for p in tree
                 if os.path.normpath(p).startswith("records" + os.sep)
                 and not os.path.normpath(p).startswith(os.path.join("records", "generator"))
                 and os.path.normpath(p) != "records"]
    assert not offenders, f"entry wrote outside records/generator/: {offenders}"
