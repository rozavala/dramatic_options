"""EDGAR filings: acceptanceDateTime lookahead guard, CIK identity, item parse, UA, Form 4."""

from datetime import UTC, datetime

import pytest

from dramatic_options.data.cache import PointInTimeCache
from dramatic_options.data.filings import (
    EdgarClient,
    FilingsData,
    _normalize_filing_block,
    form4_net_shares,
)


def test_normalize_uses_acceptance_datetime_and_parses_items():
    block = {
        "form": ["8-K", "4"],
        "acceptanceDateTime": ["2024-01-05T16:30:21.000Z", "2024-01-06T18:00:00.000Z"],
        "filingDate": ["2024-01-05", "2024-01-06"],
        "items": ["1.01,9.01", ""],
        "accessionNumber": ["0001-24-000001", "0001-24-000002"],
        "primaryDocument": ["a.htm", "f4.xml"],
    }
    recs = _normalize_filing_block(block, "0000000001")
    assert recs[0]["form"] == "8-K"
    assert recs[0]["items"] == ["1.01", "9.01"]
    # acceptance time (16:30 ET-ish, stored UTC) — NOT midnight of the filing date
    assert recs[0]["ts"].startswith("2024-01-05T16:30:21")


def test_filing_date_fallback_is_post_close():
    block = {"form": ["8-K"], "filingDate": ["2024-02-02"], "items": ["2.02"],
             "accessionNumber": ["x"], "primaryDocument": ["d.htm"]}
    recs = _normalize_filing_block(block, "1")
    assert recs[0]["ts"] == "2024-02-02T20:00:00+00:00"


class _FakeEdgar:
    """Stands in for EdgarClient with a fixed CIK + filing set."""

    def __init__(self, cik, records):
        self._cik = cik
        self._records = records

    def ticker_to_cik(self, ticker, overrides=None):
        return self._cik

    def fetch_filings(self, cik):
        return list(self._records)


def test_filings_asof_lookahead_guard(tmp_path):
    end = datetime(2024, 12, 31, tzinfo=UTC)
    cache = PointInTimeCache(tmp_path)
    fd = FilingsData(cache, edgar=_FakeEdgar("0000000007", [
        {"ts": "2024-01-01T16:30:00+00:00", "form": "8-K", "items": ["1.01"], "cik": "7"},
        {"ts": "2024-01-10T16:30:00+00:00", "form": "8-K", "items": ["2.02"], "cik": "7"},
    ]), fetch_end=end)
    as_of = datetime(2024, 1, 5, tzinfo=UTC)  # between the two filings
    got = fd.filings_asof("JOBY", as_of)
    assert [r["items"] for r in got] == [["1.01"]]  # the 2024-01-10 filing is in the future


def test_ticker_to_cik_overrides_win_and_pad():
    ec = EdgarClient("ua you@example.com")
    ec._ticker_map = {"OLD": "0000123456"}
    assert ec.ticker_to_cik("OLD") == "0000123456"
    # a de-SPAC ticker not in the current map resolved via explicit override
    assert ec.ticker_to_cik("NEWSPAC", overrides={"NEWSPAC": "789"}) == "0000000789"


def test_edgar_requires_user_agent():
    with pytest.raises(ValueError):
        EdgarClient("")


def test_edgar_sends_user_agent_header():
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    class _Session:
        def get(self, url, headers=None, timeout=None):
            captured["headers"] = headers
            return _Resp()

    ec = EdgarClient("dramatic-options you@example.com", rate_limit_per_sec=0, session=_Session())
    ec._get_json("https://data.sec.gov/x.json")
    assert captured["headers"]["User-Agent"] == "dramatic-options you@example.com"


FORM4_XML = """<ownershipDocument>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>1000</value></transactionShares></transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>250</value></transactionShares></transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


def test_form4_net_shares_signed():
    assert form4_net_shares(FORM4_XML) == 750.0  # 1000 bought − 250 sold
    assert form4_net_shares("<not xml") == 0.0
