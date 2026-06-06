"""Insider adapter: bulk Form-345 parse (signed net-buy, 10b5-1 filtering), as-of read."""

import io
import zipfile
from datetime import UTC, datetime

from dramatic_options.data.cache import PointInTimeCache
from dramatic_options.data.insider import (
    SOURCE,
    InsiderData,
    parse_quarter_netbuy,
    quarters_between,
)


def _tsv(cols, rows):
    out = ["\t".join(cols)]
    for r in rows:
        out.append("\t".join(str(r.get(c, "")) for c in cols))
    return ("\n".join(out)).encode("utf-8")


def _zip(submission_rows, trans_rows):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("SUBMISSION.tsv", _tsv(
            ["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK", "AFF10B5ONE"],
            submission_rows))
        z.writestr("NONDERIV_TRANS.tsv", _tsv(
            ["ACCESSION_NUMBER", "TRANS_CODE", "TRANS_SHARES"], trans_rows))
    return buf.getvalue()


def test_parse_quarter_netbuy_signs_and_10b5_1():
    submissions = [
        # A1: a real open-market purchase
        {"ACCESSION_NUMBER": "A1", "FILING_DATE": "15-MAR-2023", "DOCUMENT_TYPE": "4",
         "ISSUERCIK": "7", "AFF10B5ONE": "0"},
        # A2: a 10b5-1 sale → should be EXCLUDED → no record
        {"ACCESSION_NUMBER": "A2", "FILING_DATE": "16-MAR-2023", "DOCUMENT_TYPE": "4",
         "ISSUERCIK": "7", "AFF10B5ONE": "1"},
        # A3: a discretionary sale → counted (negative)
        {"ACCESSION_NUMBER": "A3", "FILING_DATE": "17-MAR-2023", "DOCUMENT_TYPE": "4",
         "ISSUERCIK": "7", "AFF10B5ONE": "0"},
        # A4: different issuer, not in our set → ignored
        {"ACCESSION_NUMBER": "A4", "FILING_DATE": "18-MAR-2023", "DOCUMENT_TYPE": "4",
         "ISSUERCIK": "999", "AFF10B5ONE": "0"},
    ]
    trans = [
        {"ACCESSION_NUMBER": "A1", "TRANS_CODE": "P", "TRANS_SHARES": "1000"},
        {"ACCESSION_NUMBER": "A2", "TRANS_CODE": "S", "TRANS_SHARES": "500"},
        {"ACCESSION_NUMBER": "A3", "TRANS_CODE": "S", "TRANS_SHARES": "300"},
        {"ACCESSION_NUMBER": "A4", "TRANS_CODE": "P", "TRANS_SHARES": "9999"},
    ]
    out = parse_quarter_netbuy(_zip(submissions, trans), {"0000000007"})
    recs = sorted(out["0000000007"], key=lambda r: r["ts"])
    assert [r["net_buy"] for r in recs] == [1000.0, -300.0]  # buy +1000, discretionary sale −300
    assert "0000000999" not in out  # outside our CIK set


def test_quarters_between():
    qs = quarters_between(datetime(2022, 2, 1, tzinfo=UTC), datetime(2023, 1, 5, tzinfo=UTC))
    assert qs == [(2022, 1), (2022, 2), (2022, 3), (2022, 4), (2023, 1)]


class _FakeEdgar:
    def ticker_to_cik(self, ticker, overrides=None):
        return "0000000007" if ticker == "JOBY" else None


def test_netbuy_asof_reads_cache(tmp_path):
    cache = PointInTimeCache(tmp_path)
    end = datetime(2023, 12, 31, tzinfo=UTC)
    cache.write(SOURCE, "0000000007", [
        {"ts": "2023-03-15T20:00:00+00:00", "net_buy": 1000.0},
        {"ts": "2023-09-01T20:00:00+00:00", "net_buy": -300.0},
    ], coverage_from=datetime(2022, 1, 1, tzinfo=UTC), coverage_through=end)
    ins = InsiderData(cache, edgar=_FakeEdgar(), fetch_start=datetime(2022, 1, 1, tzinfo=UTC),
                      fetch_end=end)
    got = ins.netbuy_asof("JOBY", datetime(2023, 6, 1, tzinfo=UTC))
    assert [r["net_buy"] for r in got] == [1000.0]      # the Sept sale is in the future
    assert ins.netbuy_asof("NOPE", datetime(2023, 6, 1, tzinfo=UTC)) == []  # no CIK → empty
