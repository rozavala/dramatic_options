"""Stage B — the bounded LLM thesis-drafting layer (``card_drafts.py``), charter §3b.

All offline: FakeRouter / stub routers only — no network, no keys, no SDKs, $0. The charter
laws under test: drafts trace to PRINTS with the surfacing item as a POINTER only (the §2
reconciliation), kill-before-spend, the hard per-run cost cap (counted, never silent), the
#37 parse discipline fail-closing to an UNDRAFTED card (never fabricated, never a crash),
and the per-thesis provenance guard (flip only on a validated draft).
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import card_drafts as cd
import survivor_cards as sc
from convexity_gate import Contract
from council.router import BudgetExceeded, CostEntry, CostLedger, FakeRouter, LLMResponse

AS_OF = datetime(2026, 7, 16, 15, 0, tzinfo=UTC)


# ── fixtures (mirror tests/test_survivor_cards.py's fakes) ────────────────────
def _chain(sym="FCX", spot=50.0, dte=270):
    strike = round(spot * 1.25, 1)
    exp = AS_OF.date() + timedelta(days=dte)
    osi = f"{sym}{exp:%y%m%d}C{int(round(strike * 1000)):08d}"
    return [Contract(symbol=osi, expiry=exp, kind="C", strike=strike,
                     bid=2.91, ask=3.09, iv=0.4, oi=500)]


def _market():
    return sc.MarketAccess(
        spot=lambda s: 50.0, closes=lambda s, w: [], adv_usd=lambda s: 10e6,
        optionable=lambda s: True, chain=lambda s: _chain(s),
    )


def _survivor(symbol="FCX"):
    screen = sc.run_screen(symbol, market=_market(), params=sc.ScreenParams(),
                           as_of=date(2026, 7, 16), quotes_live=True)
    premise = sc.build_premise(
        [float(i) for i in range(1, 301)],
        [{"ts": "2026-05-08T20:05:00+00:00", "form": "10-Q"},
         {"ts": "2026-06-30T12:00:00+00:00", "form": "424B5"}],
        {"ts": "2026-07-10T18:00:00+00:00", "analyst_count": 12},
        sc.allowed_forms(["424B5"]),
    )
    ex = sc.Extraction(symbol, "cashtag", "trade_press", "Wire",
                       f"story about ${symbol}", "https://x.example/1")
    return sc.SurvivorCard(symbol=symbol, surfaced_via=(ex,), screen=screen, premise=premise)


_FUNDAMENTALS = {
    "status": "partial",
    "n_lines": 1,
    "lines": [{"concept": "revenue", "metric": "ttm_yoy", "value": 0.234,
               "latest_musd": 1234.5, "base_musd": 1000.2,
               "period_end": "2026-03-31", "filed": "2026-05-08"}],
}
_HEADLINES = [
    {"ts": "2026-05-02T12:00:00+00:00", "headline": "Old copper story"},  # inside 90d, not 7d
    {"ts": "2026-07-12T09:30:00+00:00", "headline": "Freeport guides output higher"},
]


def _pack(card):
    return cd.build_grounding_pack(card, as_of=AS_OF, fundamentals=_FUNDAMENTALS,
                                   headlines=_HEADLINES)


_GOOD_DRAFT = {
    "direction": "bullish",
    "thesis": "Filed TTM revenue accelerated while coverage stayed thin. The 424B5 raise funds "
              "capacity. The structure read shows a cap-fittable far-OTM call.",
    "falsifier": "If the 10-Q due by 2026-08-15 prints TTM revenue growth below 10%, the "
                 "inflection claim fails.",
    "weakest_point": "One quarter of acceleration can be a one-off.",
    "evidence_cited": ["revenue ttm_yoy +23.4%", "424B5 2026-06-30"],
}


# ── the grounding pack: prints + the pointer-not-evidence header ──────────────
def test_grounding_pack_contains_prints_and_pointer_header():
    card = _survivor("FCX")
    pack = _pack(card)
    # the §2 reconciliation header, verbatim, with the surfacing item ONLY under it
    assert f"{cd.POINTER_HEADER}:" in pack
    pointer_block = pack.split(cd.POINTER_HEADER)[1].split("PRINTS")[0]
    assert "trade_press/Wire — story about $FCX — https://x.example/1" in pointer_block
    assert pack.count("story about $FCX") == 1  # the pointer never re-enters as a print
    # prints come BELOW the pointer ("the thesis must trace to the prints below")
    assert pack.index(cd.POINTER_HEADER) < pack.index("PREMISE NUMBERS")
    # premise numbers (Stage A's computed prints)
    assert "trailing return 1m / 12m: +7.5% / +525.0%" in pack
    assert "analyst count: 12 (cached 2026-07-10)" in pack
    assert "last 10-K/10-Q: 10-Q 2026-05-08" in pack
    assert "achieved OTM 25.0%" in pack  # the screen's structure read rides along
    # §9 fundamentals line, metric-aware render, staleness dates visible
    assert "FUNDAMENTALS (filed XBRL" in pack
    assert "revenue ttm_yoy +23.4% ($1234.5M vs $1000.2M); period 2026-03-31, filed 2026-05-08" in pack
    assert "(corpus status: partial)" in pack
    # headlines: counts + recent titles
    assert "count trailing 7d / 90d: 1 / 2" in pack
    assert "2026-07-12: Freeport guides output higher" in pack
    # structural filings (newest-first, from the premise pull)
    assert "RECENT STRUCTURAL FILINGS" in pack
    assert "- 424B5 2026-06-30" in pack
    assert f"CARD: {card.symbol}" in pack


def test_grounding_pack_honest_when_sources_unavailable():
    card = sc.SurvivorCard(symbol="XYZ", surfaced_via=(sc.Extraction(
        "XYZ", "cashtag", "trade_press", "Wire", "story", ""),),
        screen=sc.run_screen("XYZ", market=None, params=sc.ScreenParams(),
                             as_of=date(2026, 7, 16), quotes_live=False),
        premise=None)
    pack = cd.build_grounding_pack(card, as_of=AS_OF, fundamentals=None, headlines=None)
    assert "(unavailable — market/cache pulls skipped this run)" in pack
    assert "fundamentals unavailable this run, not zero" in pack
    assert "counts unknown, not zero" in pack  # a data gap is never rendered as a zero
    assert "- none in cache" in pack


# ── draft success: provenance flip + rendering ─────────────────────────────────
def test_draft_success_flips_provenance_and_renders():
    router = FakeRouter(responder=lambda role, system, user: json.dumps(_GOOD_DRAFT))
    run = cd.draft_survivors([_survivor("FCX")], router=router, pack_builder=_pack,
                             kill_check=lambda: False)
    assert (run.n_drafted, run.n_parse_failed, run.n_undrafted) == (1, 0, 0)
    (card,) = run.cards
    assert card.provenance == cd.PROVENANCE_DRAFTED == "machine_surfaced_machine_drafted"
    section = "\n".join(run.sections["FCX"])
    assert "- direction: bullish" in section
    assert "- thesis: Filed TTM revenue accelerated" in section
    assert "- falsifier: If the 10-Q due by 2026-08-15" in section
    assert "- weakest point: One quarter of acceleration" in section
    assert "- evidence cited: revenue ttm_yoy +23.4% · 424B5 2026-06-30" in section
    # the one-line provenance+model stamp
    assert "drafted by fake/fake-drafter · reach.drafter · $0.0000" in section
    # the document integration: provenance line + drafted section, no pending seam
    doc = sc.assemble_cards(
        run.cards, [], week="2026-W29", digest_path="d.md", restricted_note="n",
        n_extracted=1, n_restricted_dropped=0, quotes_live=True, notes=[], errors=[],
        generated_at=AS_OF, draft_sections=run.sections)
    assert "- provenance: machine_surfaced_machine_drafted" in doc
    assert "### Draft thesis\n" in doc
    assert sc.STAGE_B_SEAM not in doc  # no "(Stage B pending)" on a drafted card
    assert "- stage: A screen + B drafting" in doc


def test_drafting_preserves_input_order_no_ranking():
    router = FakeRouter(responder=cd.drafter_fake_responder)
    cards = [_survivor("AAAB"), _survivor("MMMM"), _survivor("ZZZT")]
    run = cd.draft_survivors(cards, router=router, pack_builder=_pack,
                             kill_check=lambda: False)
    assert [c.symbol for c in run.cards] == ["AAAB", "MMMM", "ZZZT"]
    assert run.n_drafted == 3
    # charter law: no score/rank field anywhere in the Stage-B schema
    banned = ("score", "rank", "relevance", "weight", "priority")
    for f in dataclasses.fields(cd.DraftRunResult):
        assert not any(b in f.name.lower() for b in banned), f.name


def test_fake_responder_demo_draft_is_schema_valid_and_labeled():
    router = FakeRouter(responder=cd.drafter_fake_responder)
    run = cd.draft_survivors([_survivor("FCX")], router=router, pack_builder=_pack,
                             kill_check=lambda: False)
    assert run.n_drafted == 1
    assert "(demo)" in "\n".join(run.sections["FCX"])  # offline drafts are clearly labeled


# ── parse failure: fail-soft, counted, provenance stays ────────────────────────
def test_parse_failure_ships_undrafted_counted_never_crashes():
    router = FakeRouter(responder=lambda role, system, user: "sorry, no JSON here")
    run = cd.draft_survivors([_survivor("FCX")], router=router, pack_builder=_pack,
                             kill_check=lambda: False)
    assert (run.n_drafted, run.n_parse_failed) == (0, 1)
    (card,) = run.cards
    assert card.provenance == sc.PROVENANCE_STAGE_A  # provenance stays machine_surfaced
    assert "draft failed (parse) — counted" in "\n".join(run.sections["FCX"])
    assert any("parse-fail" in n for n in run.notes)  # counted, never silent
    # no fabricated draft anywhere
    assert "thesis:" not in "\n".join(run.sections["FCX"])


def test_schema_validation_rejects_missing_falsifier():
    bad = {k: v for k, v in _GOOD_DRAFT.items() if k != "falsifier"}
    parsed = cd.parse_draft(json.dumps(bad))
    assert parsed["parse_error"] and "missing required keys: ['falsifier']" in parsed["validation_error"]
    # and through the run: the #37 "valid but empty shape" fails closed to an undrafted card
    router = FakeRouter(responder=lambda role, system, user: json.dumps(bad))
    run = cd.draft_survivors([_survivor("FCX")], router=router, pack_builder=_pack,
                             kill_check=lambda: False)
    assert run.n_parse_failed == 1 and run.cards[0].provenance == sc.PROVENANCE_STAGE_A


def test_schema_validation_edges():
    ok = cd.parse_draft(json.dumps(_GOOD_DRAFT), finish_reason="STOP")
    assert not ok["parse_error"] and ok["direction"] == "bullish"
    # direction outside the vocabulary
    p = cd.parse_draft(json.dumps({**_GOOD_DRAFT, "direction": "sideways"}))
    assert p["parse_error"] and "direction" in p["validation_error"]
    # empty thesis
    p = cd.parse_draft(json.dumps({**_GOOD_DRAFT, "thesis": "  "}))
    assert p["parse_error"] and "'thesis'" in p["validation_error"]
    # an evidence-free draft is untraceable → fail-closed
    p = cd.parse_draft(json.dumps({**_GOOD_DRAFT, "evidence_cited": []}))
    assert p["parse_error"] and "evidence_cited" in p["validation_error"]
    # forensics preserved (the #37 discipline)
    p = cd.parse_draft("garbage", finish_reason="MAX_TOKENS", thoughts_tokens=981)
    assert p["parse_error"] and p["raw_text"] == "garbage"
    assert p["finish_reason"] == "MAX_TOKENS" and p["thoughts_tokens"] == 981
    # the bounded bracket tail-repair (council.agents.extract_json) still validates
    truncated = json.dumps(_GOOD_DRAFT)[:-1]  # drop the final }
    repaired = cd.parse_draft(truncated)
    assert not repaired["parse_error"] and repaired["falsifier"].startswith("If the 10-Q")


# ── the cost cap: stop mid-run, counted, remaining ship undrafted ──────────────
class _CapRouter:
    """First call succeeds and lands exactly on the cap; the router boundary then raises
    BudgetExceeded before every further call (the real Router/FakeRouter semantics)."""

    def __init__(self, cap=0.5):
        self.ledger = CostLedger(cap_usd=cap)

    def call(self, *, role, system, user, max_tokens=None):
        if self.ledger.over_cap:
            raise BudgetExceeded(f"cost cap ${self.ledger.cap_usd:.2f} reached before {role}")
        self.ledger.record(CostEntry(role, "gemini", "gemini-3.1-flash-lite", 100, 50,
                                     self.ledger.cap_usd))
        return LLMResponse(json.dumps(_GOOD_DRAFT), "gemini", "gemini-3.1-flash-lite",
                           100, 50, self.ledger.cap_usd, finish_reason="STOP")


def test_cost_cap_stops_further_calls_mid_run_counted():
    router = _CapRouter(cap=0.5)
    cards = [_survivor("AAAB"), _survivor("MMMM"), _survivor("ZZZT")]
    run = cd.draft_survivors(cards, router=router, pack_builder=_pack,
                             kill_check=lambda: False)
    assert router.ledger.calls == 1  # ONE spend; the cap blocked the rest at the boundary
    assert (run.n_drafted, run.n_undrafted) == (1, 2)
    assert run.cards[0].provenance == cd.PROVENANCE_DRAFTED
    for sym in ("MMMM", "ZZZT"):
        assert "per-run drafter cost cap reached" in "\n".join(run.sections[sym])
    assert any("cost cap hit" in n and "2 survivor(s) shipped undrafted" in n
               for n in run.notes)
    # all three cards still ship — a cap never loses a card
    assert [c.symbol for c in run.cards] == ["AAAB", "MMMM", "ZZZT"]


# ── kill-before-spend ──────────────────────────────────────────────────────────
def test_kill_switch_blocks_all_calls():
    calls = []

    def _responder(role, system, user):
        calls.append(role)
        return json.dumps(_GOOD_DRAFT)

    router = FakeRouter(responder=_responder)
    run = cd.draft_survivors([_survivor("AAAB"), _survivor("ZZZT")], router=router,
                             pack_builder=_pack, kill_check=lambda: True)
    assert calls == [] and router.ledger.calls == 0  # ZERO spend, checked before any call
    assert run.n_undrafted == 2 and run.n_drafted == 0
    assert all(c.provenance == sc.PROVENANCE_STAGE_A for c in run.cards)
    assert any("kill switch ACTIVE" in n for n in run.notes)
    assert "kill switch active (no LLM spend)" in "\n".join(run.sections["AAAB"])


def test_kill_switch_default_reads_risk_module(monkeypatch):
    monkeypatch.setenv("KILL", "true")  # risk.kill_switch_active — the default kill_check
    router = FakeRouter(responder=cd.drafter_fake_responder)
    run = cd.draft_survivors([_survivor("FCX")], router=router, pack_builder=_pack)
    assert router.ledger.calls == 0 and run.n_undrafted == 1


# ── per-card fail-soft (provider error / grounding error) ─────────────────────
def test_provider_error_drops_only_that_card():
    from council.router import RouterError

    class _R(FakeRouter):
        def call(self, *, role, system, user, max_tokens=None):
            if "CARD: MMMM" in user:
                raise RouterError("provider 503")
            return super().call(role=role, system=system, user=user, max_tokens=max_tokens)

    run = cd.draft_survivors(
        [_survivor("AAAB"), _survivor("MMMM"), _survivor("ZZZT")],
        router=_R(responder=lambda role, system, user: json.dumps(_GOOD_DRAFT)),
        pack_builder=_pack, kill_check=lambda: False)
    assert (run.n_drafted, run.n_undrafted) == (2, 1)
    assert "draft failed (provider error) — counted" in "\n".join(run.sections["MMMM"])
    assert run.cards[1].provenance == sc.PROVENANCE_STAGE_A


def test_pack_builder_error_fails_soft():
    def _boom(card):
        raise OSError("cache exploded")

    router = FakeRouter(responder=cd.drafter_fake_responder)
    run = cd.draft_survivors([_survivor("FCX")], router=router, pack_builder=_boom,
                             kill_check=lambda: False)
    assert router.ledger.calls == 0  # no spend on an ungrounded card
    assert run.n_undrafted == 1
    assert "draft failed (grounding error) — counted" in "\n".join(run.sections["FCX"])


# ── router config wiring ───────────────────────────────────────────────────────
def test_drafter_config_defaults_and_overrides():
    dc = cd.drafter_config({})
    assert dc == {"provider": "gemini", "model": "gemini-3.1-flash-lite",
                  "max_tokens": 2048, "cost_cap_usd": 0.50}
    dc2 = cd.drafter_config({"reach": {"drafter": {"model": "gemini-9", "cost_cap_usd": 0.25}}})
    assert dc2["model"] == "gemini-9" and dc2["cost_cap_usd"] == 0.25
    assert dc2["provider"] == "gemini"  # defaults survive partial overrides


def test_build_drafter_router_fails_closed_without_key():
    from council.router import RouterError

    try:
        cd.build_drafter_router({"council": {}}, {})
        raise AssertionError("expected RouterError")
    except RouterError as e:
        assert "no API key" in str(e)


def test_repo_config_reach_drafter_block_is_wired():
    cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
    dc = cd.drafter_config(cfg)
    assert dc["provider"] == "gemini" and "flash" in dc["model"]
    assert dc["cost_cap_usd"] == 0.5 and dc["max_tokens"] == 2048


# ── the runner: --draft keyless path (FakeRouter fallback), default OFF ───────
def test_runner_draft_stage_keyless_falls_back_to_fakerouter(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    import scripts.survivor_cards_run as runner

    notes: list[str] = []
    errors: list[str] = []
    cards, sections = runner._draft_stage([_survivor("FCX")], None, None, AS_OF, notes, errors)
    assert any("FakeRouter DEMO drafts" in n for n in notes)  # keyless fallback is LOUD
    assert cards[0].provenance == cd.PROVENANCE_DRAFTED
    assert "(demo)" in "\n".join(sections["FCX"])
    assert errors == []


def test_runner_draft_flag_keyless_end_to_end(tmp_path, capsys):
    import scripts.survivor_cards_run as runner
    from digest import Item, assemble

    items = [Item(channel="trade_press", source="Wire", title="Copper squeeze: $FCX guides",
                  link="https://x.example/1",
                  published=datetime(2026, 7, 10, 12, 0, tzinfo=UTC), symbol=None)]
    doc = assemble(items, caps={}, week="2026-W29", dropped_notes=[],
                   generated_at=datetime(2026, 7, 14, tzinfo=UTC))
    p = tmp_path / "2026-W29.md"
    p.write_text(doc)
    rc = runner.main(["--digest", str(p), "--skip-market", "--draft", "--dry-run",
                      "--restricted", str(tmp_path / "restricted.json"),
                      "--ticker-cache", str(tmp_path / "company_tickers.json")])
    out = capsys.readouterr().out
    assert rc == 0  # --draft never breaks a keyless run
    # skip-market → no survivors → nothing drafted, but the stage line reflects the request
    assert "- stage: A screen + B drafting" in out
    assert "(no survivors this week)" in out


def test_runner_without_draft_flag_is_byte_stage_a(tmp_path, capsys):
    import scripts.survivor_cards_run as runner
    from digest import Item, assemble

    items = [Item(channel="trade_press", source="Wire", title="Copper squeeze: $FCX guides",
                  link="https://x.example/1",
                  published=datetime(2026, 7, 10, 12, 0, tzinfo=UTC), symbol=None)]
    doc = assemble(items, caps={}, week="2026-W29", dropped_notes=[],
                   generated_at=datetime(2026, 7, 14, tzinfo=UTC))
    p = tmp_path / "2026-W29.md"
    p.write_text(doc)
    rc = runner.main(["--digest", str(p), "--skip-market", "--dry-run",
                      "--restricted", str(tmp_path / "restricted.json"),
                      "--ticker-cache", str(tmp_path / "company_tickers.json")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "- stage: A (deterministic; no LLM calls). Stage B drafting pending." in out
