"""P0 tests — corpus-read + citation-anchored entity RESOLUTION (no LLM, fixtures only).

``PREREG_THEME_GENERATOR §3`` (the entity check) + §5 (Phase 0 is the no-LLM, fixture-exempt
read). Fixture-inert: a real ``PointInTimeCache`` populated with canned corpus records — NO
network, NO keys, NO LLM. Covers the three required cases (present-in-cited → resolves;
missing-source coord → fail-soft ``[]``; fabricated → unresolved) plus the worked examples the
pre-reg names: the foreign-listed NXE (US-CIK-absent yet cited), the symbol-keyed
customer_concentration disclosure, the §11 same-ts collision, and the OPTIONAL ticker_to_cik
secondary that never substitutes for the citation anchor.
"""

from __future__ import annotations

from datetime import UTC, datetime

from corpus.capital_raises import SOURCE as CAP_SOURCE
from corpus.customer_concentration import SOURCE as CC_SOURCE
from corpus.etf_constituents import SOURCE as ETF_SOURCE
from data.cache import PointInTimeCache
from generator import entity, read

_EARLY = datetime(1990, 1, 1, tzinfo=UTC)
_NOW = datetime(2026, 6, 1, tzinfo=UTC)
_TS = "2026-03-02T20:00:00+00:00"


def _cache(tmp_path):
    """A PIT cache seeded with a small, realistic corpus slice (the shapes the adapters write)."""
    c = PointInTimeCache(tmp_path)
    # capital_raises: {ts, cik, company, accession, file, date_filed, form}
    c.write(CAP_SOURCE, "424B5", [
        {"ts": _TS, "cik": "0000899629", "company": "ACME CAPITAL CORP",
         "accession": "0001104659-26-028897", "file": "x.txt", "date_filed": "2026-03-02",
         "form": "424B5"},
        {"ts": _TS, "cik": "0000123456", "company": "BETA URANIUM INC",  # §11: same (source,key,ts)
         "accession": "0001000000-26-000099", "file": "y.txt", "date_filed": "2026-03-02",
         "form": "424B5"},
    ], coverage_from=_EARLY, coverage_through=_NOW)
    # etf_constituents: {ts, etf, rank, name, symbol, exchange, us_listed, weight_pct, shares}
    c.write(ETF_SOURCE, "URNM", [
        {"ts": _TS, "etf": "URNM", "rank": 1, "name": "Cameco Corp", "symbol": "CCJ",
         "exchange": None, "us_listed": True, "weight_pct": 12.3, "shares": 100},
        {"ts": _TS, "etf": "URNM", "rank": 2, "name": "NexGen Energy", "symbol": "NXE",
         "exchange": "tsx", "us_listed": False, "weight_pct": 8.1, "shares": 50},  # foreign worked-ex
    ], coverage_from=_EARLY, coverage_through=_NOW)
    # customer_concentration: keyed by SYMBOL; record carries cik only (symbol lives in the key)
    c.write(CC_SOURCE, "AAOI", [
        {"ts": _TS, "cik": "0000666666", "accession": "a-1", "form": "10-K",
         "percentage": 45.0, "benchmark": "revenue", "n_customers": 1, "snippet": "one customer 45%"},
    ], coverage_from=_EARLY, coverage_through=_NOW)
    return c


# ── read.py ──────────────────────────────────────────────────────────────────────────────────

def test_read_corpus_unions_by_source_and_is_failsoft(tmp_path):
    cache = _cache(tmp_path)
    content = {"universe": {"capital_raises": {"forms": ["424B5"]},
                            "customer_concentration": {"symbols": ["AAOI"]}},
               "themes": {"uranium": {"etfs": ["URNM"]}}}
    config: dict = {"universe": {"themes": {}}}
    corpus = read.read_corpus(cache, _NOW, content, config)
    assert set(corpus) == {CAP_SOURCE, CC_SOURCE, ETF_SOURCE}
    assert len(corpus[CAP_SOURCE]) == 2 and len(corpus[ETF_SOURCE]) == 2
    # a requested coord with NO coverage appears as [] (fail-soft, never raises)
    content2 = {"themes": {"uranium": {"etfs": ["URNM", "NLR"]}}}  # NLR uncached
    corpus2 = read.read_corpus(cache, _NOW, content2, {"universe": {"themes": {}}})
    assert corpus2[ETF_SOURCE]  # URNM present; NLR contributed nothing, no error
    flat = read.iter_records(corpus)
    assert ("corpus_etf_constituents", corpus[ETF_SOURCE][0]) in flat


# ── entity.py — the three REQUIRED cases ──────────────────────────────────────────────────────

def test_entity_present_in_cited_record_resolves(tmp_path):
    cache = _cache(tmp_path)
    cit = [entity.Citation(CAP_SOURCE, "424B5", _TS)]
    # by name (company), by ticker-against-name, by cik
    assert entity.resolve_entity({"canonical": "ACME Capital Corp", "ticker": "ACME"}, cit, cache)
    assert entity.resolve_entity({"canonical": "Acme", "aliases": ["ACME CAPITAL CORP"]}, cit, cache)
    assert entity.resolve_entity({"canonical": "Acme", "cik": "899629"}, cit, cache)  # zero-stripped


def test_missing_source_coord_is_failsoft_empty(tmp_path):
    cache = _cache(tmp_path)
    # a citation to a source/key with no coverage → resolves nothing, never raises
    cit = [entity.Citation("corpus_does_not_exist", "WHATEVER", _TS)]
    assert entity.resolve_entity({"canonical": "ACME CAPITAL CORP"}, cit, cache) is False
    cit2 = [entity.Citation(CAP_SOURCE, "S-1", _TS)]  # source exists, key uncovered
    assert entity.resolve_entity({"canonical": "ACME CAPITAL CORP"}, cit2, cache) is False


def test_fabricated_entity_not_in_any_cited_record_is_unresolved(tmp_path):
    cache = _cache(tmp_path)
    cit = [entity.Citation(CAP_SOURCE, "424B5", _TS), entity.Citation(ETF_SOURCE, "URNM", _TS)]
    # ALDP — the pre-reg's fictional issuer — appears in no cited record
    assert entity.resolve_entity(
        {"canonical": "Aldermarsh Photonics", "ticker": "ALDP", "aliases": ["Aldermarsh"]},
        cit, cache) is False


# ── entity.py — the worked examples the pre-reg names ──────────────────────────────────────────

def test_foreign_listed_nxe_resolves_on_cited_name_not_us_cik(tmp_path):
    # §3 NXE: us_listed=False/"tsx" in the cited URNM record — a US-CIK-mandatory gate would
    # wrongly DROP it though the cited evidence names it explicitly. Citation-anchored resolves it.
    cache = _cache(tmp_path)
    cit = [entity.Citation(ETF_SOURCE, "URNM", _TS)]
    assert entity.resolve_entity({"canonical": "NexGen Energy", "ticker": "NXE"}, cit, cache)


def test_symbol_keyed_source_resolves_via_coord_key(tmp_path):
    # customer_concentration record carries cik only; the SYMBOL identity lives in the coord key.
    cache = _cache(tmp_path)
    cit = [entity.Citation(CC_SOURCE, "AAOI", _TS)]
    assert entity.resolve_entity({"canonical": "Applied Optoelectronics", "ticker": "AAOI"}, cit, cache)
    assert entity.resolve_entity({"canonical": "Beta", "cik": "666666"}, cit, cache)  # cik in record


def test_citation_ts_collision_unions_all_same_ts_records(tmp_path):
    # §11: (source,key,ts) maps to MULTIPLE records (two 424B5s same day). A claim citing that
    # exact coord can resolve an entity from EITHER colliding record.
    cache = _cache(tmp_path)
    cit = [entity.Citation(CAP_SOURCE, "424B5", _TS)]
    assert entity.resolve_entity({"canonical": "BETA URANIUM INC", "ticker": "BURI"}, cit, cache)


def test_ts_anchoring_excludes_other_ts_records(tmp_path):
    # A citation ts that matches NO record resolves nothing even if the key has other-ts records.
    cache = _cache(tmp_path)
    cit = [entity.Citation(CAP_SOURCE, "424B5", "2025-01-01T20:00:00+00:00")]
    assert entity.resolve_entity({"canonical": "ACME CAPITAL CORP"}, cit, cache) is False
    # whole-key citation (ts=None) sees the whole key's coverage → resolves
    cit2 = [entity.Citation(CAP_SOURCE, "424B5", None)]
    assert entity.resolve_entity({"canonical": "ACME CAPITAL CORP"}, cit2, cache)


def test_optional_ticker_to_cik_secondary_never_substitutes_for_citation(tmp_path):
    cache = _cache(tmp_path)

    class _Edgar:
        def ticker_to_cik(self, ticker, **kw):
            return {"ACME": "0000899629", "GHOST": "0009999999"}.get(ticker.upper())

    # secondary: ticker→CIK lands on a CITED record's cik → resolves (assist, still anchored)
    cit = [entity.Citation(CAP_SOURCE, "424B5", _TS)]
    ent = {"canonical": "Acme Renamed Co", "ticker": "ACME"}  # name not in record; ticker is the assist
    assert entity.resolve_entity(ent, cit, cache, edgar=_Edgar()) is True
    # but a ticker whose CIK is NOT in any cited record stays UNRESOLVED (the gaming channel §3 shuts)
    ghost = {"canonical": "Ghost Corp", "ticker": "GHOST"}
    assert entity.resolve_entity(ghost, cit, cache, edgar=_Edgar()) is False


def test_resolve_named_entities_map_and_as_citations_coercion(tmp_path):
    cache = _cache(tmp_path)
    raw_cits = [(CAP_SOURCE, "424B5", _TS), {"source": ETF_SOURCE, "key": "URNM", "ts": _TS},
                ("bad",), {"no": "key"}]  # last two malformed → skipped fail-soft
    cits = entity.as_citations(raw_cits)
    assert len(cits) == 2 and cits[0] == entity.Citation(CAP_SOURCE, "424B5", _TS)
    res = entity.resolve_named_entities(
        [{"canonical": "ACME CAPITAL CORP"}, {"canonical": "NexGen Energy", "ticker": "NXE"},
         {"canonical": "Aldermarsh Photonics", "ticker": "ALDP"}],
        cits, cache)
    assert res == {"ACME CAPITAL CORP": True, "NexGen Energy": True, "Aldermarsh Photonics": False}
