"""Survivor-card pipeline, Stage A (records/2026-07-14_reach_channels_charter_RATIFIED.md §3b).

No network anywhere: extraction/screen/premise/assembly run over inline fixtures and
injected fakes; the runner path runs keyless (``--skip-market``) over tmp files. The
no-scoring-field schema guard is charter law — a future scoring/rank/relevance field on any
pipeline dataclass must fail CI (the ``digest.Item`` discipline)."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, date, datetime, timedelta

import pytest

import survivor_cards as sc
from convexity_gate import Contract
from digest import Item, assemble

AS_OF = date(2026, 7, 16)
RTH = datetime(2026, 7, 15, 15, 0, tzinfo=UTC)  # Wednesday, inside 13:30–20:00 UTC


def _item(title, channel="trade_press", source="Wire", link="https://x.example/1",
          published=datetime(2026, 7, 10, 12, 0, tzinfo=UTC), symbol=None):
    return Item(channel=channel, source=source, title=title, link=link,
                published=published, symbol=symbol)


# ── the schema guard (charter law: no scoring field, anywhere, ever) ──────────
def test_no_scoring_field_schema_guard():
    # EXACT field sets — adding ANY field (score/rank/relevance/weight/…) fails here first.
    expected = {
        sc.Extraction: {"symbol", "method", "channel", "source", "title", "link"},
        sc.AxisResult: {"axis", "status", "detail", "provisional"},
        sc.ScreenResult: {"symbol", "axes"},
        sc.PremiseCurrency: {"ret_1m", "ret_12m", "analyst_count", "analyst_asof",
                             "last_periodic_filing", "structural_filings"},
        sc.SurvivorCard: {"symbol", "surfaced_via", "screen", "premise", "provenance"},
        sc.MarketAccess: {"spot", "closes", "adv_usd", "optionable", "chain"},
    }
    for cls, fields in expected.items():
        assert {f.name for f in dataclasses.fields(cls)} == fields, cls.__name__
    # belt-and-suspenders: no field NAME smells like a rank on any pipeline dataclass
    banned = ("score", "rank", "relevance", "weight", "priority")
    for cls in (*expected, sc.ScreenParams):
        for f in dataclasses.fields(cls):
            assert not any(b in f.name.lower() for b in banned), f"{cls.__name__}.{f.name}"


# ── stage 1a: the digest-input seam (markdown → Items) ────────────────────────
def test_parse_digest_markdown_roundtrip():
    items = [
        _item("Grid order issued"),
        _item("Opinion: the ghost — why 2G persists", link="https://x.example/2",
              published=datetime(2026, 7, 11, 9, 30, tzinfo=UTC)),
        _item("undated story", published=None, link=""),
        _item("License amendment", channel="agency", source="federal_register/nrc",
              link="https://fr.example/doc"),
        Item(channel="orphan_watch", source="orphan_watch/424B4",
             title="NWLR: options class now listed (424B4 2024-08-05, NEWLIST ROBOTICS INC)",
             link="https://sec.example/nwlr",
             published=datetime(2026, 7, 14, tzinfo=UTC), symbol="NWLR"),
    ]
    doc = assemble(items, caps={}, week="2026-W29", dropped_notes=["some note"],
                   generated_at=datetime(2026, 7, 14, tzinfo=UTC))
    parsed = sc.parse_digest_markdown(doc)
    assert len(parsed) == 5  # header bullets + notes section never parse as items
    by_title = {i.title: i for i in parsed}
    assert by_title["Grid order issued"].channel == "trade_press"
    assert by_title["Grid order issued"].source == "Wire"
    assert by_title["Grid order issued"].link == "https://x.example/1"
    assert by_title["Grid order issued"].published == datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    # an em-dash INSIDE the title survives (only a trailing http tail is split off as link)
    assert "Opinion: the ghost — why 2G persists" in by_title
    assert by_title["undated story"].published is None and by_title["undated story"].link == ""
    assert by_title["License amendment"].source == "federal_register/nrc"
    orphan = next(i for i in parsed if i.channel == "orphan_watch")
    assert orphan.symbol == "NWLR"  # re-derived from the machine-generated title
    assert "some note" not in by_title


def test_parse_digest_markdown_skips_dropped_lines_and_preamble():
    doc = "\n".join([
        "# Reach digest — 2026-W29", "",
        "- generated: 2026-07-14T00:00:00+00:00",  # header bullet: not an item
        "", "## trade_press", "", "### Wire", "",
        "… 2 older items dropped (per-source cap)",
        "- 2026-07-10 12:00Z — Real story — https://x.example/1", "",
        "## notes", "", "- FAILED — trade_press/Dead: OSError: x", "",
    ])
    parsed = sc.parse_digest_markdown(doc)
    assert [i.title for i in parsed] == ["Real story"]


# ── stage 1b: conservative ticker extraction ──────────────────────────────────
def test_extract_cashtag_high_precision():
    (ex,) = sc.extract_from_item(_item("Copper squeeze: $FCX guides higher"), known=None)
    assert (ex.symbol, ex.method) == ("FCX", "cashtag")
    # provenance rides every extraction
    assert ex.channel == "trade_press" and ex.source == "Wire"
    assert ex.title.startswith("Copper squeeze") and ex.link == "https://x.example/1"
    # dollar AMOUNTS never match; lowercase never matches
    assert sc.extract_from_item(_item("raises $100 million"), known=None) == []
    assert sc.extract_from_item(_item("worth $4bn to $fcx"), known=None) == []


def test_extract_exchange_parenthetical():
    (ex,) = sc.extract_from_item(_item("Rocket Lab (NASDAQ: RKLB) wins contract"), known=None)
    assert (ex.symbol, ex.method) == ("RKLB", "exchange_paren")
    (ex2,) = sc.extract_from_item(_item("Freeport (NYSE: FCX) output up"), known=None)
    assert ex2.symbol == "FCX"
    # an unpinned exchange label never matches (precision over recall)
    assert sc.extract_from_item(_item("Acme (WEIRD: ABC) thing"), known=None) == []
    # a non-exchange parenthetical never matches
    assert sc.extract_from_item(_item("the ratio (EBITDA: 4x) improved"), known=None) == []


def test_extract_exact_match_rejects_common_word_false_positives():
    # "A" (Agilent), "IT" (Gartner), "ALL" (Allstate) are REAL tickers — and exactly the
    # false positives that poison the screen. The exact-match pass must reject them.
    known = frozenset({"A", "IT", "ALL", "FCX", "KTOS"})
    exs = sc.extract_from_item(
        _item("IT spending at ALL time high as FCX and A start KTOS-era buildout"), known=known
    )
    assert {e.symbol for e in exs} == {"FCX", "KTOS"}
    assert all(e.method == "exact_match" for e in exs)
    # title-case / lowercase words never match ("It", "all")
    assert sc.extract_from_item(_item("It was all fine"), known=known) == []
    # unknown all-caps words never match (NATO ∉ known universe)
    assert sc.extract_from_item(_item("NATO expands"), known=known) == []


def test_extract_exact_match_skipped_without_known_universe():
    # known=None (no cached company_tickers.json) → the exact-match pass is OFF entirely.
    assert sc.extract_from_item(_item("FCX output up"), known=None) == []


def test_extract_orphan_title_and_item_symbol():
    title = "NWLR: options class now listed (424B4 2024-08-05, NEWLIST ROBOTICS INC)"
    (ex,) = sc.extract_from_item(
        _item(title, channel="orphan_watch", source="orphan_watch/424B4"), known=None)
    assert (ex.symbol, ex.method) == ("NWLR", "orphan_title")
    (ex2,) = sc.extract_from_item(
        _item(title, channel="orphan_watch", source="orphan_watch/424B4", symbol="NWLR"),
        known=None)
    assert (ex2.symbol, ex2.method) == ("NWLR", "item_symbol")  # the Item field wins


def test_extract_candidates_dedupes_per_item_and_keeps_multi_item_provenance():
    items = [
        _item("Freeport (NYSE: FCX) and $FCX both in one title"),
        _item("FCX mine expansion", channel="agency", source="federal_register/nrc"),
    ]
    out = sc.extract_candidates(items, known=frozenset({"FCX"}))
    assert set(out) == {"FCX"}
    assert len(out["FCX"]) == 2  # one extraction per item, both provenances kept
    assert out["FCX"][0].method == "cashtag"  # highest-priority method wins within an item
    assert out["FCX"][1].channel == "agency"


def test_load_known_tickers_cache_first(tmp_path):
    p = tmp_path / "company_tickers.json"
    assert sc.load_known_tickers(p) is None  # absent → None → exact-match pass skipped
    p.write_text(json.dumps({"0": {"cik_str": 831259, "ticker": "fcx", "title": "FREEPORT"},
                             "1": {"cik_str": 1819994, "ticker": "RKLB", "title": "ROCKET"}}))
    assert sc.load_known_tickers(p) == frozenset({"FCX", "RKLB"})
    p.write_text("not json{{")
    assert sc.load_known_tickers(p) is None  # corrupt cache degrades, never raises


# ── stage 2: restricted list (fail-CLOSED) ────────────────────────────────────
def test_restricted_absent_file_warns_and_proceeds(tmp_path):
    tickers, note = sc.load_restricted(tmp_path / "restricted.json")
    assert tickers is None
    assert "WARNING" in note and "UNCHECKED" in note


def test_restricted_malformed_halts_fail_closed(tmp_path):
    p = tmp_path / "restricted.json"
    for bad in ("not json{{", '{"entries": "LIFE"}', '[{"id": "R-001"}]',
                '[{"id": "R-001", "tickers": [42]}]'):
        p.write_text(bad)
        with pytest.raises(sc.RestrictedListError, match="fail-closed"):
            sc.load_restricted(p)


def test_restricted_valid_both_shapes_and_drop_before_screen(tmp_path):
    p = tmp_path / "restricted.json"
    p.write_text(json.dumps([{"id": "R-001", "tickers": ["LIFE"]}]))
    tickers, note = sc.load_restricted(p)
    assert tickers == frozenset({"LIFE"}) and "enforced" in note
    p.write_text(json.dumps({"entries": [{"id": "R-001", "tickers": ["life", "XYZ"]}]}))
    tickers2, _ = sc.load_restricted(p)
    assert tickers2 == frozenset({"LIFE", "XYZ"})

    candidates = {"LIFE": [], "FCX": []}
    kept, dropped = sc.apply_restricted(candidates, frozenset({"LIFE"}))
    assert set(kept) == {"FCX"} and dropped == 1
    kept2, dropped2 = sc.apply_restricted(candidates, None)  # absent list → nothing dropped
    assert set(kept2) == {"LIFE", "FCX"} and dropped2 == 0


# ── stage 3: the four-axis screen (injected fakes; REUSED selection machinery) ─
def _chain(sym="FCX", spot=50.0, strike=None, mid=3.0, dte=270, oi=500):
    strike = strike if strike is not None else round(spot * 1.25, 1)
    exp = AS_OF + timedelta(days=dte)
    osi = f"{sym}{exp:%y%m%d}C{int(round(strike * 1000)):08d}"
    return [Contract(symbol=osi, expiry=exp, kind="C", strike=strike,
                     bid=round(mid * 0.97, 2), ask=round(mid * 1.03, 2), iv=0.4, oi=oi)]


def _market(spot=50.0, adv=10e6, optionable=True, chain=None, closes=None):
    return sc.MarketAccess(
        spot=lambda s: spot,
        closes=lambda s, w: closes or [],
        adv_usd=lambda s: adv,
        optionable=lambda s: optionable,
        chain=lambda s: chain if chain is not None else _chain(s, spot),
    )


def test_screen_all_pass_records_all_four_axes():
    r = sc.run_screen("FCX", market=_market(), params=sc.ScreenParams(), as_of=AS_OF,
                      quotes_live=True)
    assert [a.axis for a in r.axes] == list(sc.AXES)
    assert all(a.status == sc.PASS for a in r.axes) and r.passed
    band = r.axis("band_fit")
    assert not band.provisional
    assert "achieved OTM 25.0%" in band.detail and "$300/contract" in band.detail


def test_screen_axis_failures_are_per_axis_and_recorded():
    assert sc.run_screen("X", market=_market(spot=2.0, chain=_chain(spot=2.0, mid=0.2)),
                         params=sc.ScreenParams(), as_of=AS_OF,
                         quotes_live=True).axis("price").status == sc.FAIL
    r = sc.run_screen("X", market=_market(adv=1e6), params=sc.ScreenParams(), as_of=AS_OF,
                      quotes_live=True)
    assert r.axis("adv").status == sc.FAIL and not r.passed
    assert "$1.0M < $3.0M" in r.axis("adv").detail
    assert sc.run_screen("X", market=_market(optionable=False), params=sc.ScreenParams(),
                         as_of=AS_OF, quotes_live=True).axis("optionable").status == sc.FAIL


def test_screen_band_fit_over_cap_and_out_of_band_fail():
    over_cap = sc.run_screen("FCX", market=_market(chain=_chain(mid=30.0)),
                             params=sc.ScreenParams(), as_of=AS_OF, quotes_live=True)
    assert over_cap.axis("band_fit").status == sc.FAIL
    assert "over per-name cap" in over_cap.axis("band_fit").detail
    # only listed strike is 10% OTM → outside the §11 15–35% achieved-OTM band
    near_atm = sc.run_screen("FCX", market=_market(chain=_chain(strike=55.0)),
                             params=sc.ScreenParams(), as_of=AS_OF, quotes_live=True)
    assert near_atm.axis("band_fit").status == sc.FAIL
    assert "achieved OTM outside band" in near_atm.axis("band_fit").detail
    # no contract in the tenor window at all → FAIL (dispositive), not UNAVAILABLE
    no_tenor = sc.run_screen("FCX", market=_market(chain=_chain(dte=30)),
                             params=sc.ScreenParams(), as_of=AS_OF, quotes_live=True)
    assert no_tenor.axis("band_fit").status == sc.FAIL
    assert "no structure" in no_tenor.axis("band_fit").detail
    # an adjusted OCC class (root ≠ underlying, the CDE2 defect) is never selectable
    adjusted = sc.run_screen("CDE", market=_market(chain=_chain(sym="CDE2")),
                             params=sc.ScreenParams(), as_of=AS_OF, quotes_live=True)
    assert adjusted.axis("band_fit").status == sc.FAIL
    assert "no structure" in adjusted.axis("band_fit").detail


def test_screen_skip_market_marks_unavailable_never_passed():
    r = sc.run_screen("FCX", market=None, params=sc.ScreenParams(), as_of=AS_OF,
                      quotes_live=False)
    assert [a.status for a in r.axes] == [sc.UNAVAILABLE] * 4
    assert not r.passed  # UNAVAILABLE is never a pass
    assert all("NOT passed" in a.detail for a in r.axes)


def test_screen_axis_exception_fails_soft_and_is_counted():
    m = _market()
    m.spot = lambda s: (_ for _ in ()).throw(OSError("feed down"))
    errors: list[str] = []
    r = sc.run_screen("FCX", market=m, params=sc.ScreenParams(), as_of=AS_OF,
                      quotes_live=True, errors=errors)
    assert r.axis("price").status == sc.UNAVAILABLE
    assert r.axis("band_fit").status == sc.UNAVAILABLE  # no spot → no band read
    assert r.axis("adv").status == sc.PASS  # other axes still measured
    assert len(errors) == 1 and "FCX/price" in errors[0]  # dead arm counted, never quiet
    assert not r.passed


def test_screen_provisional_flags_only_the_quote_dependent_axis():
    r = sc.run_screen("FCX", market=_market(), params=sc.ScreenParams(), as_of=AS_OF,
                      quotes_live=False)
    assert r.axis("band_fit").provisional and r.axis("band_fit").status == sc.PASS
    assert not any(r.axis(a).provisional for a in ("price", "adv", "optionable"))


def test_quotes_are_live_window():
    wed = datetime(2026, 7, 15, tzinfo=UTC)
    assert not sc.quotes_are_live(wed.replace(hour=13, minute=29))
    assert sc.quotes_are_live(wed.replace(hour=13, minute=30))
    assert sc.quotes_are_live(wed.replace(hour=19, minute=59))
    assert not sc.quotes_are_live(wed.replace(hour=20, minute=0))
    assert not sc.quotes_are_live(datetime(2026, 7, 18, 15, 0, tzinfo=UTC))  # Saturday


# ── stage 4: premise-currency (mechanical numbers, cache-honest) ──────────────
def test_trailing_returns():
    closes = [float(i) for i in range(1, 301)]  # 1..300
    r1, r12 = sc.trailing_returns(closes)
    assert r1 == pytest.approx(300.0 / 279.0 - 1.0)
    assert r12 == pytest.approx(300.0 / 48.0 - 1.0)
    r1s, r12s = sc.trailing_returns(closes[:30])
    assert r1s is not None and r12s is None  # insufficient history → None, not a guess
    assert sc.trailing_returns(closes[:10]) == (None, None)
    assert sc.trailing_returns(None) == (None, None)


def test_latest_periodic_filing_and_structural_filings_exact_membership():
    records = [
        {"ts": "2024-01-05T20:00:00+00:00", "form": "S-1"},
        {"ts": "2025-02-20T21:10:00+00:00", "form": "10-K"},
        {"ts": "2026-05-08T20:05:00+00:00", "form": "10-Q/A"},
        {"ts": "2026-05-12T18:00:00+00:00", "form": "SC 13D/A"},
        {"ts": "2026-06-30T12:00:00+00:00", "form": "424B5"},
        {"ts": "2026-07-01T12:00:00+00:00", "form": "S-1MEF"},  # prefix trap: never matches
        {"ts": "2026-07-02T12:00:00+00:00", "form": "8-K"},
    ]
    assert sc.latest_periodic_filing(records) == "10-Q/A 2026-05-08"
    forms = sc.allowed_forms(["424B5", "S-1", "SC 13D"])
    got = sc.recent_structural_filings(records, forms)
    assert got == ("424B5 2026-06-30", "SC 13D/A 2026-05-12", "S-1 2024-01-05")
    assert sc.latest_periodic_filing(None) is None
    assert sc.recent_structural_filings(None, forms) == ()


def test_build_premise_none_handling():
    p = sc.build_premise(None, None, None, sc.allowed_forms(["424B5"]))
    assert p == sc.PremiseCurrency(None, None, None, None, None, ())
    p2 = sc.build_premise(
        [float(i) for i in range(1, 301)],
        [{"ts": "2026-05-08T20:05:00+00:00", "form": "10-Q"}],
        {"ts": "2026-07-10T18:00:00+00:00", "analyst_count": 12},
        sc.allowed_forms(["424B5"]),
    )
    assert p2.analyst_count == 12 and p2.analyst_asof == "2026-07-10"
    assert p2.last_periodic_filing == "10-Q 2026-05-08"
    assert p2.structural_filings == ()  # no event-leg forms cached → empty, not invented


# ── stage 5: card assembly (deterministic, alphabetical, never silent) ────────
def _survivor(symbol, quotes_live=True):
    screen = sc.run_screen(symbol, market=_market(), params=sc.ScreenParams(), as_of=AS_OF,
                           quotes_live=quotes_live)
    premise = sc.build_premise([float(i) for i in range(1, 301)], None, None,
                               sc.allowed_forms(["424B5"]))
    ex = sc.Extraction(symbol, "cashtag", "trade_press", "Wire",
                       f"story about ${symbol}", "https://x.example/1")
    return sc.SurvivorCard(symbol=symbol, surfaced_via=(ex,), screen=screen, premise=premise)


def _failed(symbol):
    return sc.run_screen(symbol, market=_market(adv=1e6), params=sc.ScreenParams(),
                         as_of=AS_OF, quotes_live=True)


_ASSEMBLE_KW = dict(week="2026-W29", digest_path="records/digests/2026-W29.md",
                    restricted_note="restricted list enforced (1 entry/ies, 1 ticker(s))",
                    n_extracted=4, n_restricted_dropped=1, quotes_live=True,
                    notes=["a note"], errors=["boom"], generated_at=RTH)


def test_assemble_cards_deterministic_and_alphabetical():
    survivors = [_survivor("ZZZT"), _survivor("AAAB")]
    out = [_failed("MMMM"), _failed("BBBB")]
    doc = sc.assemble_cards(survivors, out, **_ASSEMBLE_KW)
    assert doc == sc.assemble_cards(survivors, out, **_ASSEMBLE_KW)  # byte-deterministic
    # NO ranking anywhere: survivors AND screen-failures ordered alphabetically
    assert doc.index("## AAAB") < doc.index("## ZZZT")
    assert doc.index("- BBBB") < doc.index("- MMMM")
    assert "- ordering: alphabetical (no ranking anywhere — charter §3b)" in doc


def test_assemble_cards_card_contents_and_stage_b_seam():
    doc = sc.assemble_cards([_survivor("FCX")], [], **_ASSEMBLE_KW)
    assert "- provenance: machine_surfaced" in doc  # the charter §3b tag, Stage A value
    assert "- trade_press/Wire [cashtag] — story about $FCX — https://x.example/1" in doc
    for axis in sc.AXES:
        assert f"  - {axis}: PASS" in doc  # all four axes with values
    assert "trailing return 1m / 12m: +7.5% / +525.0%" in doc
    assert "analyst count: n/a (not in cache)" in doc
    # the Stage-B seam: one EMPTY draft-thesis section per card, clearly named
    assert doc.count("### Draft thesis (Stage B pending)") == 1
    assert "Stage B, the thesis-drafting layer, is not built" in doc
    assert "- funnel: 4 extracted -> 1 screened -> 1 survivor(s)" in doc
    assert "- restricted drops: 1 candidate(s)" in doc
    assert "## notes" in doc and "- a note" in doc and "- FAILED — boom" in doc


def test_assemble_cards_screened_out_never_silent():
    doc = sc.assemble_cards([], [_failed("QWTR")], **_ASSEMBLE_KW)
    assert "(no survivors this week)" in doc
    assert "## Screened out" in doc
    line = next(ln for ln in doc.splitlines() if ln.startswith("- QWTR"))
    assert "failed adv" in line  # the failing axis is named
    # every axis state visible on the compact line
    for frag in ("price PASS", "adv FAIL", "optionable PASS", "band_fit PASS"):
        assert frag in line


def test_assemble_cards_provisional_and_absent_restricted_warnings():
    kw = dict(_ASSEMBLE_KW, quotes_live=False,
              restricted_note=sc.load_restricted("does/not/exist.json")[1])
    doc = sc.assemble_cards([_survivor("FCX", quotes_live=False)], [], **kw)
    assert "PROVISIONAL — generated outside 13:30-20:00 UTC" in doc  # header flag
    assert "band_fit: PASS (PROVISIONAL — quotes read outside 13:30-20:00 UTC)" in doc
    assert "WARNING: restricted.json ABSENT" in doc  # the absent-file warning rides the doc
    assert f"- generated: {RTH.isoformat(timespec='seconds')}" in doc  # timestamp on the card


def test_screened_out_line_distinguishes_unavailable_from_fail():
    r = sc.run_screen("XX", market=None, params=sc.ScreenParams(), as_of=AS_OF,
                      quotes_live=False)
    line = sc._screened_out_line(r)
    assert "screen unavailable" in line and "FAIL" not in line  # dead arm ≠ failed arm


# ── the runner (keyless paths only — no network, no keys) ─────────────────────
@pytest.fixture()
def digest_file(tmp_path):
    items = [
        _item("Copper squeeze: $FCX guides higher"),
        _item("Rocket Lab (NASDAQ: RKLB) wins contract",
              published=datetime(2026, 7, 11, tzinfo=UTC)),
        _item("Ethos milestone: $LIFE expands", published=datetime(2026, 7, 12, tzinfo=UTC)),
    ]
    doc = assemble(items, caps={}, week="2026-W29", dropped_notes=[],
                   generated_at=datetime(2026, 7, 14, tzinfo=UTC))
    p = tmp_path / "2026-W29.md"
    p.write_text(doc)
    return p


def test_runner_skip_market_dry_run_end_to_end(digest_file, tmp_path, capsys):
    import scripts.survivor_cards_run as runner

    rc = runner.main(["--digest", str(digest_file), "--skip-market", "--dry-run",
                      "--restricted", str(tmp_path / "restricted.json"),
                      "--ticker-cache", str(tmp_path / "company_tickers.json")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "# Survivor cards — 2026-W29" in out  # week from the digest filename stem
    assert "WARNING" in out and "UNCHECKED" in out  # absent restricted.json is loud
    assert "--skip-market: screen axes UNAVAILABLE (not passed)" in out
    assert "(no survivors this week)" in out  # UNAVAILABLE is never a pass
    # both extracted candidates land in Screened out — nothing silently dropped
    assert "- FCX — screen unavailable" in out
    assert "- LIFE — screen unavailable" in out
    assert "- RKLB — screen unavailable" in out


def test_runner_restricted_malformed_halts_with_exit_2(digest_file, tmp_path, capsys):
    import scripts.survivor_cards_run as runner

    bad = tmp_path / "restricted.json"
    bad.write_text("not json{{")
    rc = runner.main(["--digest", str(digest_file), "--skip-market", "--dry-run",
                      "--restricted", str(bad),
                      "--ticker-cache", str(tmp_path / "company_tickers.json")])
    assert rc == 2  # fail-CLOSED: a broken restricted list halts the run
    assert "HALT" in capsys.readouterr().out


def test_runner_restricted_drops_before_screen(digest_file, tmp_path, capsys):
    import scripts.survivor_cards_run as runner

    restricted = tmp_path / "restricted.json"
    restricted.write_text(json.dumps([{"id": "R-001", "tickers": ["LIFE"]}]))
    rc = runner.main(["--digest", str(digest_file), "--skip-market", "--dry-run",
                      "--restricted", str(restricted),
                      "--ticker-cache", str(tmp_path / "company_tickers.json")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "- restricted drops: 1 candidate(s)" in out
    assert "LIFE" not in out.split("## Screened out")[1]  # dropped BEFORE the screen…
    assert "tickers withheld from this document" in out   # …and counted, never named


def test_runner_no_digest_exits_1(tmp_path, capsys):
    import scripts.survivor_cards_run as runner

    rc = runner.main(["--digests-dir", str(tmp_path / "nowhere"), "--skip-market",
                      "--dry-run"])
    assert rc == 1
    assert "no digest found" in capsys.readouterr().out


def test_runner_writes_week_file(digest_file, tmp_path):
    import scripts.survivor_cards_run as runner

    out_dir = tmp_path / "cards"
    rc = runner.main(["--digest", str(digest_file), "--skip-market", "--out", str(out_dir),
                      "--restricted", str(tmp_path / "restricted.json"),
                      "--ticker-cache", str(tmp_path / "company_tickers.json")])
    assert rc == 0
    written = out_dir / "2026-W29.md"
    assert written.exists()
    assert written.read_text().startswith("# Survivor cards — 2026-W29")
