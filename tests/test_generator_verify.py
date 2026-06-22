"""P2 tests — the §3 citation VERIFIER (deterministic DROP gate, no LLM, fixtures only).

``PREREG_THEME_GENERATOR §3/§11``. Fixture-inert: a real ``PointInTimeCache`` seeded with canned
corpus records spanning the three source-classes — NO network, NO keys, NO LLM. Covers:

  - entity-in-cited-record → passes; entity in NO cited record → DROP + ``dropped_entity_unresolved``;
  - real entity, untraced figure → DROP + ``dropped_fact_untraced``;
  - the fact trace per source-class — (a) entity-bearing record-keyed, (b) entity-free macro
    source+key+value, (c) free-text-recipient name-normalization;
  - a ``ts=None`` (whole-key) citation REJECTED for an emitted claim (the entity then unresolves);
  - the ±1-bucket match (in-bucket + one-off pass, two-off fail);
  - over-citation telemetry surfaces coords-per-entity;
  - **the split-counter exact-value tests** — hand-checked integers (anti-HARK §9).

The canonical claim+corpus exemplars under the two split-counter tests are the ones surfaced to the
operator for ratification (see the build report).
"""

from __future__ import annotations

from datetime import UTC, datetime

from corpus.bls_series import SOURCE as BLS_SOURCE
from corpus.capital_raises import SOURCE as CAP_SOURCE
from corpus.customer_concentration import SOURCE as CC_SOURCE
from corpus.eia_series import SOURCE as EIA_SOURCE
from corpus.etf_constituents import SOURCE as ETF_SOURCE
from corpus.federal_awards import SOURCE as AWARDS_SOURCE
from data.cache import PointInTimeCache
from generator import verify

_EARLY = datetime(1990, 1, 1, tzinfo=UTC)
_NOW = datetime(2026, 6, 1, tzinfo=UTC)
_TS = "2026-03-02T20:00:00+00:00"


def _cache(tmp_path):
    """A PIT cache seeded with one record per source-class (the shapes the adapters write)."""
    c = PointInTimeCache(tmp_path)
    # (a) entity-bearing — capital_raises (NO magnitude field), etf_constituents (weight_pct=12.3),
    #     customer_concentration (percentage=45.0, n_customers=1; keyed by SYMBOL).
    c.write(CAP_SOURCE, "424B5", [
        {"ts": _TS, "cik": "0000899629", "company": "ACME CAPITAL CORP",
         "accession": "a-1", "file": "x.txt", "date_filed": "2026-03-02", "form": "424B5"},
    ], coverage_from=_EARLY, coverage_through=_NOW)
    c.write(ETF_SOURCE, "URNM", [
        {"ts": _TS, "etf": "URNM", "rank": 1, "name": "Cameco Corp", "symbol": "CCJ",
         "exchange": None, "us_listed": True, "weight_pct": 12.3, "shares": 100},
    ], coverage_from=_EARLY, coverage_through=_NOW)
    c.write(CC_SOURCE, "AAOI", [
        {"ts": _TS, "cik": "0000666666", "accession": "c-1", "form": "10-K",
         "percentage": 45.0, "benchmark": "revenue", "n_customers": 1, "snippet": "one customer 45%"},
    ], coverage_from=_EARLY, coverage_through=_NOW)
    # (b) entity-free macro — eia {value} (a 55.0 print) + nrc (no magnitude). bls similar to eia.
    c.write(EIA_SOURCE, "eia_abc123def456", [
        {"ts": _TS, "period": "2026-01", "value": 55.0, "units": "percent", "dims": {}},
    ], coverage_from=_EARLY, coverage_through=_NOW)
    c.write(BLS_SOURCE, "CUUR0000SEHF01", [
        {"ts": _TS, "series_id": "CUUR0000SEHF01", "year": 2026, "period": "M01", "value": 270.0},
    ], coverage_from=_EARLY, coverage_through=_NOW)
    # (c) free-text recipient — federal_awards {recipient, amount=2.5e9}.
    c.write(AWARDS_SOURCE, "awards_xyz", [
        {"ts": _TS, "award_id": "W912-26-C-0001", "recipient": "Lockheed Martin Corporation",
         "recipient_id": "abc", "amount": 2.5e9, "naics_code": "336414",
         "naics_desc": "Guided Missile and Space Vehicle Manufacturing", "agency": "DoD"},
    ], coverage_from=_EARLY, coverage_through=_NOW)
    return c


def _claim(cid, entities, citations, *, quantities=None, vocab="shortage", sign="+"):
    """A well-formed §3 claim (the verifier ignores statement/provenance — shape is the parser's job)."""
    return {
        "claim_id": cid,
        "statement": "driver -> effect -> entity class",
        "named_entities": entities,
        "mechanism_direction": {"vocab": vocab, "sign": sign},
        "headline_quantities": quantities or [],
        "provenance": "generated",
        "citations": citations,
    }


# ── entity leg: present-in-cited → keep; absent → DROP ─────────────────────────────────────────

def test_entity_in_cited_record_passes(tmp_path):
    cache = _cache(tmp_path)
    c = _claim("u1", [{"canonical": "Cameco Corp", "ticker": "CCJ"}],
               [{"source": ETF_SOURCE, "key": "URNM", "ts": _TS}])
    v = verify.verify_claim(c, cache)
    assert not v.dropped and v.reason is None


def test_entity_in_no_cited_record_drops_entity_unresolved(tmp_path):
    cache = _cache(tmp_path)
    # Aldermarsh Photonics / ALDP — appears in no cited record → confabulation → DROP.
    c = _claim("u2", [{"canonical": "Aldermarsh Photonics", "ticker": "ALDP"}],
               [{"source": ETF_SOURCE, "key": "URNM", "ts": _TS}])
    v = verify.verify_claim(c, cache)
    assert v.dropped and v.reason == "entity_unresolved"
    assert v.unresolved_entities == ["Aldermarsh Photonics"]


# ── fact leg: real entity, untraced figure → DROP ─────────────────────────────────────────────

def test_real_entity_untraced_figure_drops_fact_untraced(tmp_path):
    cache = _cache(tmp_path)
    # Cameco RESOLVES in URNM, but the asserted pct_300plus is four buckets from URNM's pct_10_25
    # (weight_pct=12.3) and traces to no other cited record → fact_untraced (the figure is invented).
    c = _claim("u3", [{"canonical": "Cameco Corp", "ticker": "CCJ"}],
               [{"source": ETF_SOURCE, "key": "URNM", "ts": _TS}],
               quantities=[{"metric": "fleet share", "value": "400%", "bucket": "pct_300plus"}])
    v = verify.verify_claim(c, cache)
    assert v.dropped and v.reason == "fact_untraced"
    assert v.untraced_quantities == ["fleet share"]


# ── fact leg per source-class ─────────────────────────────────────────────────────────────────

def test_fact_trace_class_a_entity_bearing_record_keyed(tmp_path):
    cache = _cache(tmp_path)
    # customer_concentration percentage=45.0 → pct_25_50; the claim asserts pct_25_50 (in-bucket).
    c = _claim("a", [{"canonical": "Applied Optoelectronics", "ticker": "AAOI"}],
               [{"source": CC_SOURCE, "key": "AAOI", "ts": _TS}],
               quantities=[{"metric": "customer share", "value": "45%", "bucket": "pct_25_50"}])
    v = verify.verify_claim(c, cache)
    assert not v.dropped, v.reason


def test_fact_trace_class_b_entity_free_macro_value(tmp_path):
    cache = _cache(tmp_path)
    # entity-free macro: eia value=55.0 classified into the claim's pct_ family → pct_50_100.
    # Class-(b) is fact-WHERE-PRESENT, so this also verifies the trace WORKS when the value matches.
    # The claim cites the macro source AND names an entity that resolves there via the coord key.
    c = _claim("b", [{"canonical": "eia_abc123def456"}],
               [{"source": EIA_SOURCE, "key": "eia_abc123def456", "ts": _TS}],
               quantities=[{"metric": "capacity factor", "value": "55%", "bucket": "pct_50_100"}])
    v = verify.verify_claim(c, cache)
    assert not v.dropped, v.reason


def test_class_b_untraced_figure_is_tolerated_where_present(tmp_path):
    cache = _cache(tmp_path)
    # Class-(b)-only citation: an untraced figure does NOT drop (fact-where-present, not mandatory).
    c = _claim("b2", [{"canonical": "eia_abc123def456"}],
               [{"source": EIA_SOURCE, "key": "eia_abc123def456", "ts": _TS}],
               quantities=[{"metric": "nameplate", "value": "9000 MW", "bucket": "usd_billions"}])
    v = verify.verify_claim(c, cache)
    assert not v.dropped, "class-(b) untraced figure must be tolerated (where-present, not mandatory)"


def test_fact_trace_class_c_free_text_recipient_name_normalization(tmp_path):
    cache = _cache(tmp_path)
    # (c) federal_awards: the claim names Lockheed (resolves on recipient) and the figure's TEXT
    # overlaps the cited award recipient — the name-normalization tolerance traces it.
    c = _claim("c", [{"canonical": "Lockheed Martin Corporation", "ticker": "LMT"}],
               [{"source": AWARDS_SOURCE, "key": "awards_xyz", "ts": _TS}],
               quantities=[{"metric": "Lockheed Martin contract", "value": "award", "bucket": ""}])
    v = verify.verify_claim(c, cache)
    assert not v.dropped, v.reason
    # and the award amount (2.5e9 → usd_billions) traces a usd_ figure within ±1 (usd_tens_of_billions).
    c2 = _claim("c2", [{"canonical": "Lockheed Martin Corporation", "ticker": "LMT"}],
                [{"source": AWARDS_SOURCE, "key": "awards_xyz", "ts": _TS}],
                quantities=[{"metric": "obligation", "value": "$2.5B", "bucket": "usd_billions"}])
    assert not verify.verify_claim(c2, cache).dropped


# ── ts=None (whole-key) citation REJECTED for an emitted claim ─────────────────────────────────

def test_whole_key_ts_none_citation_rejected_entity_unresolves(tmp_path):
    cache = _cache(tmp_path)
    # The entity exists in the key's records, but the claim cites ts=None (whole-key) — REJECTED, so
    # resolution sees NO concrete-ts citation and the entity unresolves (the ratified P2 rule / §11).
    c = _claim("nk", [{"canonical": "Cameco Corp", "ticker": "CCJ"}],
               [{"source": ETF_SOURCE, "key": "URNM"}])  # no ts → whole-key
    v = verify.verify_claim(c, cache)
    assert v.dropped and v.reason == "entity_unresolved"
    assert v.citation_count == 0  # the ts=None coord was rejected → zero trace anchors


# ── ±1-bucket match: in-bucket + one-off pass, two-off fail ────────────────────────────────────

def test_pm_one_bucket_in_bucket_passes(tmp_path):
    cache = _cache(tmp_path)
    # URNM weight_pct=12.3 → pct_10_25; claim asserts pct_10_25 (exact).
    c = _claim("in", [{"canonical": "Cameco Corp", "ticker": "CCJ"}],
               [{"source": ETF_SOURCE, "key": "URNM", "ts": _TS}],
               quantities=[{"metric": "weight", "value": "12%", "bucket": "pct_10_25"}])
    assert not verify.verify_claim(c, cache).dropped


def test_pm_one_bucket_one_off_passes(tmp_path):
    cache = _cache(tmp_path)
    # pct_25_50 is one ordinal above the record's pct_10_25 → within ±1 → traces.
    c = _claim("off1", [{"canonical": "Cameco Corp", "ticker": "CCJ"}],
               [{"source": ETF_SOURCE, "key": "URNM", "ts": _TS}],
               quantities=[{"metric": "weight", "value": "~30%", "bucket": "pct_25_50"}])
    assert not verify.verify_claim(c, cache).dropped


def test_pm_one_bucket_two_off_fails(tmp_path):
    cache = _cache(tmp_path)
    # pct_50_100 is TWO ordinals above pct_10_25 → outside ±1 → fact_untraced DROP.
    c = _claim("off2", [{"canonical": "Cameco Corp", "ticker": "CCJ"}],
               [{"source": ETF_SOURCE, "key": "URNM", "ts": _TS}],
               quantities=[{"metric": "weight", "value": "70%", "bucket": "pct_50_100"}])
    v = verify.verify_claim(c, cache)
    assert v.dropped and v.reason == "fact_untraced"


# ── over-citation telemetry ────────────────────────────────────────────────────────────────────

def test_over_citation_telemetry_surfaces_coords_per_entity(tmp_path):
    cache = _cache(tmp_path)
    # One entity, THREE concrete-ts citations → coords_per_entity = 3.0 (the over-citation tell).
    c = _claim("oc", [{"canonical": "Cameco Corp", "ticker": "CCJ"}],
               [{"source": ETF_SOURCE, "key": "URNM", "ts": _TS},
                {"source": CAP_SOURCE, "key": "424B5", "ts": _TS},
                {"source": CC_SOURCE, "key": "AAOI", "ts": _TS}])
    v = verify.verify_claim(c, cache)
    assert v.citation_count == 3
    assert v.coords_per_entity == 3.0
    res = verify.verify_claims([c], cache)
    assert res.mean_coords_per_entity == 3.0 and res.mean_citation_count == 3.0


# ── the SPLIT-COUNTER exact-value tests (hand-checked integers; operator-ratify) ────────────────

def test_dropped_entity_unresolved_exact_value(tmp_path):
    """EXEMPLAR (operator-ratify): a 3-claim batch where EXACTLY ONE entity is unresolved.

    - keep:  Cameco/CCJ — resolves in the cited URNM record.
    - keep:  ACME CAPITAL CORP — resolves in the cited 424B5 record.
    - DROP:  Aldermarsh/ALDP — in NO cited record (confabulation).
    ⇒ dropped_entity_unresolved == 1, dropped_fact_untraced == 0, kept == 2, dropped_total == 1.
    """
    cache = _cache(tmp_path)
    keep_a = _claim("keepA", [{"canonical": "Cameco Corp", "ticker": "CCJ"}],
                    [{"source": ETF_SOURCE, "key": "URNM", "ts": _TS}])
    keep_b = _claim("keepB", [{"canonical": "ACME CAPITAL CORP"}],
                    [{"source": CAP_SOURCE, "key": "424B5", "ts": _TS}])
    drop = _claim("dropC", [{"canonical": "Aldermarsh Photonics", "ticker": "ALDP"}],
                  [{"source": ETF_SOURCE, "key": "URNM", "ts": _TS}])
    res = verify.verify_claims([keep_a, keep_b, drop], cache)
    assert res.dropped_entity_unresolved == 1
    assert res.dropped_fact_untraced == 0
    assert res.dropped_total == 1
    assert res.n_kept == 2
    assert [c["claim_id"] for c in res.kept] == ["keepA", "keepB"]


def test_dropped_fact_untraced_exact_value(tmp_path):
    """EXEMPLAR (operator-ratify): a 2-claim batch, BOTH entity-resolved, EXACTLY ONE figure untraced.

    - keep:  AAOI customer share 45% → cited customer_concentration percentage=45.0 = pct_25_50 (in).
    - DROP:  Cameco/CCJ (resolves in URNM) asserts pct_300plus, four buckets from URNM's pct_10_25 and
             traceable to no cited record ⇒ a fabricated figure on a real entity.
    ⇒ dropped_fact_untraced == 1, dropped_entity_unresolved == 0, kept == 1, dropped_total == 1.
    """
    cache = _cache(tmp_path)
    keep = _claim("keepFact", [{"canonical": "Applied Optoelectronics", "ticker": "AAOI"}],
                  [{"source": CC_SOURCE, "key": "AAOI", "ts": _TS}],
                  quantities=[{"metric": "customer share", "value": "45%", "bucket": "pct_25_50"}])
    drop = _claim("dropFact", [{"canonical": "Cameco Corp", "ticker": "CCJ"}],
                  [{"source": ETF_SOURCE, "key": "URNM", "ts": _TS}],
                  quantities=[{"metric": "share", "value": "400%", "bucket": "pct_300plus"}])
    res = verify.verify_claims([keep, drop], cache)
    assert res.dropped_fact_untraced == 1
    assert res.dropped_entity_unresolved == 0
    assert res.dropped_total == 1
    assert res.n_kept == 1
    assert [c["claim_id"] for c in res.kept] == ["keepFact"]


def test_verify_claims_failsoft_on_uncovered_citation(tmp_path):
    cache = _cache(tmp_path)
    # A citation to an uncovered source resolves nothing (fail-soft) → the entity unresolves, never raises.
    c = _claim("fs", [{"canonical": "Ghost Co"}],
               [{"source": "corpus_does_not_exist", "key": "WHO", "ts": _TS}])
    res = verify.verify_claims([c], cache)
    assert res.dropped_entity_unresolved == 1 and res.n_kept == 0
