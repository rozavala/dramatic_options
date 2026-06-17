"""Stage-0 corpus: the capital-raise (424B5/S-1) adapter + the §2 no-price import guard.

The §2 guard is package-level (audits every ``corpus/*.py``) — it covers future source modules too.
"""

import ast
import os
import pathlib
from datetime import UTC, datetime, timedelta

from corpus.assemble import assemble_corpus
from corpus.bls_series import BLSSeries, _period_end, parse_bls_series
from corpus.capital_raises import enumerate_capital_raises
from corpus.customer_concentration import (
    CustomerConcentration,
    extract_concentration,
    strip_html,
)
from corpus.eia_series import EIASeries, _eia_period_end, parse_eia_series
from corpus.federal_awards import enumerate_federal_awards, parse_federal_awards
from data.cache import PointInTimeCache


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


class _FakeSession:
    """Minimal requests.Session stand-in: records calls, replays canned JSON (offline tests)."""

    def __init__(self, *, get=None, posts=None):
        self._get_payload = get
        self._posts = list(posts or [])
        self.get_urls: list[str] = []
        self.post_bodies: list[dict] = []

    def get(self, url, **kw):
        self.get_urls.append(url)
        return _FakeResp(self._get_payload)

    def post(self, url, json=None, **kw):
        self.post_bodies.append(json)
        payload = self._posts.pop(0) if self._posts else {"results": [], "page_metadata": {}}
        return _FakeResp(payload)

# Synthetic quarterly full-index in the real whitespace-anchored layout (form / company / CIK /
# ISO date / edgar path). Includes an S-1/A (must be EXCLUDED for form=S-1 — exact match) and a
# non-registration form (ignored).
_HEADER = (
    "Description:           Master Index of EDGAR Dissemination Feed by Form Type\n"
    "Form Type   Company Name                       CIK      Date Filed  File Name\n"
    "----------------------------------------------------------------------------\n"
)
_Q1 = _HEADER + (
    "424B5   ACME CAPITAL CORP   899629   2026-03-02   edgar/data/899629/0001104659-26-028897.txt\n"
    "S-1   NEWCO BIO INC   333333   2026-03-10   edgar/data/333333/0001000000-26-000010.txt\n"
    "S-1/A   NEWCO BIO INC   333333   2026-03-12   edgar/data/333333/0001000000-26-000012.txt\n"
    "8-K   SOME OTHER CO   111111   2026-02-01   edgar/data/111111/0000000000-26-000001.txt\n"
)


class _FakeEdgar:
    def __init__(self, by_quarter):
        self._by_quarter = by_quarter

    def fetch_form_index(self, year, quarter):
        return self._by_quarter[(year, quarter)]


def test_enumerate_merges_424b5_and_exact_s1(tmp_path):
    cache = PointInTimeCache(tmp_path)
    recs = enumerate_capital_raises(
        datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC),
        edgar=_FakeEdgar({(2026, 1): _Q1}), cache=cache, cache_dir=tmp_path,
    )
    # 424B5 + EXACT S-1 only (S-1/A excluded, 8-K ignored), sorted by (date_filed, form, accession)
    assert [(r["form"], r["cik"]) for r in recs] == [
        ("424B5", "0000899629"),   # 2026-03-02
        ("S-1", "0000333333"),     # 2026-03-10
    ]
    # structural-only fields — NO price/IV/momentum keys
    assert set(recs[0]) == {"ts", "cik", "company", "accession", "file", "date_filed", "form"}


def test_enumerate_fail_soft_without_edgar(tmp_path):
    # A corpus-source hiccup (no edgar client / offline) must yield [] — never raise (the scheduled
    # Stage-0 assembly fail-soft, mirroring data/ adapters).
    cache = PointInTimeCache(tmp_path)
    assert enumerate_capital_raises(
        datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC),
        edgar=None, cache=cache, cache_dir=tmp_path,
    ) == []


def test_corpus_forbids_price_imports():
    # §2 (PREREG_THEME_GENERATION_STUB Stage 0): corpus modules carry NO prices/IV/momentum/sentiment,
    # enforced at the INPUT layer (auditable, not prompt-hopeful) → they import no market/price source.
    forbidden = ("data.market", "data.alpaca_client", "data.convexity_data", "alpaca")
    pkg = pathlib.Path(__file__).resolve().parents[1] / "corpus"
    for f in sorted(pkg.glob("*.py")):
        mods: list[str] = []
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, ast.Import):
                mods += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
        bad = [m for m in mods if any(m == p or m.startswith(p + ".") for p in forbidden)]
        assert not bad, f"{f.name}: §2 corpus prohibition — forbidden import(s) {bad}"


# ── corpus/federal_awards.py (USASpending / DoD) ─────────────────────────────────────────────

# Shapes mirror live-probed api.usaspending.gov spending_by_award results (Action Date is null on
# award summaries — the reason PIT comes from the window, not a per-award date).
_AWARDS_P1 = {
    "results": [
        {"Award ID": "HT001", "Recipient Name": "VERTIV CORP", "Award Amount": 5_000_000.0,
         "Awarding Agency": "Department of Defense", "Action Date": None, "recipient_id": "a-C",
         "NAICS": {"code": "335999", "description": "MISC ELECTRICAL EQUIPMENT MFG"}},
        {"Award ID": "HT002", "Recipient Name": "KRATOS DEFENSE", "Award Amount": 12_000_000.0,
         "Awarding Agency": "Department of Defense", "Action Date": None, "recipient_id": "b-C",
         "NAICS": {"code": "336414", "description": "GUIDED MISSILE & SPACE VEHICLE MFG"}},
        {"Award ID": "", "Recipient Name": "NO ID CO", "Award Amount": 999.0,  # dropped: no id
         "NAICS": None, "recipient_id": None},
    ],
    "page_metadata": {"page": 1, "hasNext": True},
}
_AWARDS_P2 = {
    "results": [
        {"Award ID": "HT003", "Recipient Name": "GE VERNOVA", "Award Amount": 8_000_000.0,
         "Awarding Agency": "Department of Defense", "recipient_id": "c-C",
         "NAICS": {"code": "335312", "description": "MOTOR & GENERATOR MFG"}},
    ],
    "page_metadata": {"page": 2, "hasNext": False},
}


def test_parse_federal_awards_structural_and_sorted():
    recs = parse_federal_awards(_AWARDS_P1["results"], as_of_ts="2026-06-15T00:00:00+00:00")
    # no-id row dropped; sorted by amount desc
    assert [r["award_id"] for r in recs] == ["HT002", "HT001"]
    assert [r["amount"] for r in recs] == [12_000_000.0, 5_000_000.0]
    assert recs[0]["naics_code"] == "336414" and recs[0]["recipient"] == "KRATOS DEFENSE"
    # structural-only keys — NO price/IV/momentum/sentiment
    assert set(recs[0]) == {"ts", "award_id", "recipient", "recipient_id", "amount",
                            "naics_code", "naics_desc", "agency"}
    assert all(r["ts"] == "2026-06-15T00:00:00+00:00" for r in recs)


def test_enumerate_federal_awards_paginates_caches_and_reuses(tmp_path):
    start, end = datetime(2026, 4, 1, tzinfo=UTC), datetime(2026, 6, 15, tzinfo=UTC)
    sess = _FakeSession(posts=[_AWARDS_P1, _AWARDS_P2])
    cache = PointInTimeCache(tmp_path)
    recs = enumerate_federal_awards(start, end, session=sess, cache=cache, cache_dir=tmp_path,
                                    rate_limit_per_sec=0)
    # both pages walked (hasNext stops on page 2), merged + amount-desc
    assert len(sess.post_bodies) == 2
    assert [r["award_id"] for r in recs] == ["HT002", "HT003", "HT001"]
    assert all(r["ts"] == end.isoformat() for r in recs)  # stamped at the window end (== coverage)
    # network-free reuse: a later call with NO session reads the point-in-time cache
    recs2 = enumerate_federal_awards(start, end, session=None, cache=cache, cache_dir=tmp_path)
    assert [r["award_id"] for r in recs2] == ["HT002", "HT003", "HT001"]


def test_enumerate_federal_awards_fail_soft(tmp_path):
    # Offline + nothing cached → [] (no network attempt; a corpus hiccup never breaks assembly).
    assert enumerate_federal_awards(
        datetime(2026, 4, 1, tzinfo=UTC), datetime(2026, 6, 15, tzinfo=UTC),
        session=None, cache=PointInTimeCache(tmp_path, offline=True), cache_dir=tmp_path,
    ) == []


# ── corpus/bls_series.py (BLS publicAPI v1) ──────────────────────────────────────────────────

_BLS_OK = {
    "status": "REQUEST_SUCCEEDED",
    "Results": {"series": [{"seriesID": "CUUR0000SEHF01", "data": [
        {"year": "2026", "period": "M05", "periodName": "May", "value": "289.4", "latest": "true"},
        {"year": "2026", "period": "M04", "periodName": "April", "value": "288.0"},
        {"year": "2025", "period": "A01", "periodName": "Annual", "value": "280.0"},
        {"year": "2026", "period": "M03", "periodName": "March", "value": "-"},  # dropped: non-num
    ]}]},
}


def test_bls_period_end():
    assert _period_end(2026, "M05") == (2026, 5, 31)
    assert _period_end(2024, "M02") == (2024, 2, 29)  # leap
    assert _period_end(2026, "Q02") == (2026, 6, 30)
    assert _period_end(2026, "A01") == (2026, 12, 31)
    assert _period_end(2026, "S01") == (2026, 6, 30)
    assert _period_end(2026, "M13") == (2026, 12, 31)  # annual average
    assert _period_end(2026, "Z99") is None and _period_end(2026, "MZZ") is None


def test_parse_bls_series_pit_and_numeric():
    recs = parse_bls_series(_BLS_OK, pub_lag_days=30)
    assert [r["period"] for r in recs] == ["A01", "M04", "M05"]  # ascending by pub-lagged ts
    assert [r["value"] for r in recs] == [280.0, 288.0, 289.4]
    exp_m05 = (datetime(2026, 5, 31, 20, 0, 0, tzinfo=UTC) + timedelta(days=30)).isoformat()
    assert recs[-1]["ts"] == exp_m05 and recs[-1]["series_id"] == "CUUR0000SEHF01"
    assert set(recs[0]) == {"ts", "series_id", "year", "period", "value"}


def test_bls_series_asof_and_fail_soft(tmp_path):
    cache = PointInTimeCache(tmp_path)
    bls = BLSSeries(cache, fetch_end=datetime(2026, 7, 1, tzinfo=UTC), session=_FakeSession(get=_BLS_OK),
                    cache_dir=tmp_path, rate_limit_per_sec=0)
    recs = bls.series_asof("CUUR0000SEHF01", datetime(2026, 7, 1, tzinfo=UTC))
    assert [r["period"] for r in recs] == ["A01", "M04", "M05"]
    # an earlier as-of hides not-yet-published prints (publication lag)
    early = bls.series_asof("CUUR0000SEHF01", datetime(2026, 2, 1, tzinfo=UTC))
    assert [r["period"] for r in early] == ["A01"]
    # offline + uncached → [] (transient-safe, no network, never raises)
    bls2 = BLSSeries(PointInTimeCache(tmp_path / "x", offline=True),
                     fetch_end=datetime(2026, 7, 1, tzinfo=UTC))
    assert bls2.series_asof("CUUR0000SEHF01", datetime(2026, 7, 1, tzinfo=UTC)) == []


# ── corpus/eia_series.py (EIA Open Data v2) ──────────────────────────────────────────────────

_EIA_OK = {
    "response": {
        "total": 3, "dateFormat": "YYYY-MM", "frequency": "monthly",
        "data": [
            {"period": "2026-03", "stateid": "CA", "stateDescription": "California",
             "sectorid": "IND", "sectorName": "industrial", "price": "18.5",
             "price-units": "cents per kilowatt-hour"},
            {"period": "2026-02", "stateid": "CA", "sectorid": "IND", "price": "18.0",
             "price-units": "cents per kilowatt-hour"},
            {"period": "2026-01", "stateid": "CA", "sectorid": "IND", "price": None,  # dropped
             "price-units": "cents per kilowatt-hour"},
        ],
        "description": "Retail sales of electricity",
    }
}


def test_eia_period_end():
    assert _eia_period_end("2026") == (2026, 12, 31)
    assert _eia_period_end("2026-03") == (2026, 3, 31)
    assert _eia_period_end("2026-Q2") == (2026, 6, 30)
    assert _eia_period_end("2026-03-15") == (2026, 3, 15)
    assert _eia_period_end("garbage") is None


def test_parse_eia_series_dims_units_and_pit():
    recs = parse_eia_series(_EIA_OK, value_field="price", pub_lag_days=75)
    assert [r["period"] for r in recs] == ["2026-02", "2026-03"]  # None row dropped, ts-ascending
    assert [r["value"] for r in recs] == [18.0, 18.5]
    assert recs[0]["units"] == "cents per kilowatt-hour"
    # dims preserve structural facets, never the value/units/period
    assert recs[-1]["dims"]["stateid"] == "CA" and recs[-1]["dims"]["sectorName"] == "industrial"
    assert "price" not in recs[-1]["dims"] and "price-units" not in recs[-1]["dims"]
    exp_mar = (datetime(2026, 3, 31, 20, 0, 0, tzinfo=UTC) + timedelta(days=75)).isoformat()
    assert recs[-1]["ts"] == exp_mar


def test_eia_cache_key_excludes_secret_api_key(tmp_path):
    cache = PointInTimeCache(tmp_path)
    a = EIASeries(cache, api_key="SECRET_AAA", fetch_end=datetime(2026, 7, 1, tzinfo=UTC))
    b = EIASeries(cache, api_key="SECRET_BBB", fetch_end=datetime(2026, 7, 1, tzinfo=UTC))
    # identity is route×metric×facets — the secret never enters the cache key
    assert a._key("electricity/retail-sales", "price", {"frequency": "monthly"}) == \
        b._key("electricity/retail-sales", "price", {"frequency": "monthly"})


def test_eia_series_asof_keyed_and_secret_not_on_disk(tmp_path):
    sess = _FakeSession(get=_EIA_OK)
    eia = EIASeries(PointInTimeCache(tmp_path), api_key="TESTKEY",
                    fetch_end=datetime(2026, 7, 1, tzinfo=UTC), session=sess,
                    cache_dir=tmp_path, rate_limit_per_sec=0)
    recs = eia.series_asof("electricity/retail-sales", value_field="price",
                           as_of=datetime(2026, 7, 1, tzinfo=UTC), params={"frequency": "monthly"})
    assert [r["period"] for r in recs] == ["2026-02", "2026-03"]
    assert recs[-1]["dims"]["stateid"] == "CA"
    # the key rode the request URL but is NOT written to any cache filename
    assert any("api_key=TESTKEY" in u for u in sess.get_urls)
    raw_files = os.listdir(tmp_path / "eia_raw")
    assert raw_files and all("TESTKEY" not in f for f in raw_files)


def test_eia_no_key_fail_soft(tmp_path):
    # A session is present but no api_key → no fetch → [] (fail-soft like the fundamentals UA).
    eia = EIASeries(PointInTimeCache(tmp_path), api_key=None,
                    fetch_end=datetime(2026, 7, 1, tzinfo=UTC), session=_FakeSession(get=_EIA_OK),
                    cache_dir=tmp_path, rate_limit_per_sec=0)
    assert eia.series_asof("electricity/retail-sales", value_field="price",
                           as_of=datetime(2026, 7, 1, tzinfo=UTC)) == []


# ── corpus/assemble.py (the pinned as-of union) + the capital_raises namespace fix ───────────

def test_assemble_corpus_unions_as_of(tmp_path):
    cache = PointInTimeCache(tmp_path)
    cov = dict(coverage_from=datetime(2026, 1, 1, tzinfo=UTC),
               coverage_through=datetime(2026, 12, 31, tzinfo=UTC))
    cache.write("corpus_a", "k1", [{"ts": "2026-01-10T00:00:00+00:00", "v": 1},
                                   {"ts": "2026-03-10T00:00:00+00:00", "v": 2}], **cov)
    cache.write("corpus_b", "k2", [{"ts": "2026-02-10T00:00:00+00:00", "v": 3}], **cov)
    out = assemble_corpus(cache, datetime(2026, 2, 15, tzinfo=UTC),
                          [("corpus_a", "k1"), ("corpus_b", "k2"), ("corpus_missing", "kx")])
    # as-of 2026-02-15: corpus_a's Jan rec only (Mar is future); corpus_b's Feb rec; missing → []
    assert [r["v"] for r in out["corpus_a"]] == [1]
    assert [r["v"] for r in out["corpus_b"]] == [3]
    assert out["corpus_missing"] == []  # requested-but-empty is distinguishable from not-requested


def test_capital_raises_uses_corpus_namespace(tmp_path):
    # Corpus filings persist under their OWN PIT-cache source — decoupled from the FSSD harness's
    # shared ``fssd_events`` namespace (the storage-pin cleanup, 2026-06-17).
    cache = PointInTimeCache(tmp_path)
    enumerate_capital_raises(
        datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC),
        edgar=_FakeEdgar({(2026, 1): _Q1}), cache=cache, cache_dir=tmp_path,
    )
    assert (tmp_path / "corpus_capital_raises").is_dir()
    assert not (tmp_path / "fssd_events").exists()


# ── corpus/customer_concentration.py (10-K text extraction) ──────────────────────────────────

def test_strip_html_drops_script_style_and_unescapes():
    raw = ("<html><head><style>.a{color:red}</style></head><body><p>Foo&nbsp;&amp; bar</p>"
           "<script>evil()</script>   baz</body></html>")
    t = strip_html(raw)
    assert "Foo" in t and "& bar" in t and "baz" in t
    assert "color:red" not in t and "evil()" not in t  # style/script content dropped


def test_extract_concentration_positive_revenue_and_ar():
    text = ("As of October 3, 2025, three customers represented 82% of our aggregate gross accounts "
            "receivable. One customer accounted for approximately 60.5% of our net revenue in 2025.")
    by = {r["benchmark"]: r for r in extract_concentration(text)}
    assert by["accounts_receivable"]["percentage"] == 82.0
    assert by["accounts_receivable"]["n_customers"] == 3
    assert by["revenue"]["percentage"] == 60.5
    assert by["revenue"]["n_customers"] == 1
    assert set(by["revenue"]) == {"percentage", "benchmark", "n_customers", "snippet"}


def test_extract_concentration_skips_negative_disclosure():
    # The standard "no single customer …" disclosure is the OPPOSITE of concentration → not recorded.
    assert extract_concentration(
        "No single customer accounted for more than 10% of our net revenue.") == []


def test_extract_concentration_requires_revenue_or_ar_benchmark():
    # A customer + a percentage but no revenue/sales/receivable benchmark → too noisy → dropped.
    assert extract_concentration(
        "One customer is critical to us, representing 40% of unit shipments.") == []


class _FakeEdgar10K:
    def __init__(self, cik, filings, docs):
        self._cik, self._filings, self._docs = cik, filings, docs

    def ticker_to_cik(self, ticker, overrides=None):
        return self._cik

    def fetch_filings(self, cik):
        return self._filings

    def fetch_document(self, cik, accession, primary_document):
        return self._docs[accession]


def test_concentration_asof_full_path_and_pit(tmp_path):
    cik = "0000004127"
    filings = [
        {"ts": "2024-02-01T20:00:00+00:00", "form": "8-K", "items": [],
         "accession": "x-8k", "primary_document": "d.htm", "cik": cik},
        {"ts": "2025-11-07T20:00:00+00:00", "form": "10-K", "items": [],
         "accession": "0000004127-25-000085", "primary_document": "swks.htm", "cik": cik},
    ]
    doc = ("<html><body><p>As of October 3, 2025, three customers represented 82% of our aggregate "
           "gross accounts receivable. Our largest customer accounted for 66% of net revenue.</p>"
           "<script>x()</script></body></html>")
    edgar = _FakeEdgar10K(cik, filings, {"0000004127-25-000085": doc})
    cache = PointInTimeCache(tmp_path)
    cc = CustomerConcentration(cache, edgar=edgar, fetch_end=datetime(2026, 1, 1, tzinfo=UTC),
                               cache_dir=tmp_path)
    recs = cc.concentration_asof("SWKS", datetime(2026, 1, 1, tzinfo=UTC))
    # both narrative disclosures from the LATEST 10-K (not the 8-K), stamped at its filing ts
    assert sorted(r["percentage"] for r in recs) == [66.0, 82.0]
    assert {r["benchmark"] for r in recs} == {"revenue", "accounts_receivable"}
    assert all(r["ts"] == "2025-11-07T20:00:00+00:00" and r["form"] == "10-K" for r in recs)
    assert [r["n_customers"] for r in recs if r["benchmark"] == "accounts_receivable"] == [3]
    # PIT: nothing visible before the 10-K was filed
    assert cc.concentration_asof("SWKS", datetime(2025, 1, 1, tzinfo=UTC)) == []


def test_concentration_prefers_base_10k_over_partial_amendment(tmp_path):
    # Regression (caught live on SWKS): a newer 10-K/A is often partial (Part III, no financials);
    # it must not shadow the complete base 10-K that carries the concentration note.
    cik = "0000004127"
    filings = [
        {"ts": "2025-11-07T20:00:00+00:00", "form": "10-K", "items": [],
         "accession": "base", "primary_document": "full.htm", "cik": cik},
        {"ts": "2026-01-30T20:00:00+00:00", "form": "10-K/A", "items": [],
         "accession": "amend", "primary_document": "partiii.htm", "cik": cik},
    ]
    docs = {"base": "<html><body><p>One customer accounted for 66% of net revenue.</p></body></html>",
            "amend": "<html><body><p>Part III - director compensation tables.</p></body></html>"}
    cc = CustomerConcentration(PointInTimeCache(tmp_path), edgar=_FakeEdgar10K(cik, filings, docs),
                               fetch_end=datetime(2026, 6, 1, tzinfo=UTC), cache_dir=tmp_path)
    recs = cc.concentration_asof("SWKS", datetime(2026, 6, 1, tzinfo=UTC))
    assert len(recs) == 1 and recs[0]["percentage"] == 66.0
    assert recs[0]["accession"] == "base" and recs[0]["ts"] == "2025-11-07T20:00:00+00:00"


def test_concentration_asof_fail_soft(tmp_path):
    cc = CustomerConcentration(PointInTimeCache(tmp_path, offline=True), edgar=None,
                               fetch_end=datetime(2026, 1, 1, tzinfo=UTC), cache_dir=tmp_path)
    assert cc.concentration_asof("SWKS", datetime(2026, 1, 1, tzinfo=UTC)) == []
