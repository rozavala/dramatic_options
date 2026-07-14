"""Weekly reach-digest harness v0 (records/2026-07-14_reach_channels_charter_DRAFT.md §3).

No network anywhere: feed/API fetchers run over monkeypatched ``digest._http_get``; parsing
runs over inline XML/JSON fixtures; the orphan channel over a fake EDGAR + fake checker.
The Item schema guard is charter law — a future scoring/rank/relevance field must fail CI.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
from datetime import UTC, datetime

import pytest

import digest
from data.cache import PointInTimeCache
from data.edgar_index import EdgarIndex, parse_form_index
from digest import (
    Item,
    assemble,
    federal_register_items,
    fetch_rss,
    iso_week_stamp,
    last_closed_quarter_end,
    load_snapshot,
    months_ago,
    orphan_cohort,
    orphan_new_listings,
    parse_feed,
    save_snapshot,
)

# ── fixtures ──────────────────────────────────────────────────────────────────
RSS2 = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
  <title>Wire</title><link>https://wire.example</link>
  <atom:link href="https://wire.example/feed" rel="self"/>
  <item><title>Grid  order\nissued</title><link>https://wire.example/3</link>
    <pubDate>Fri, 10 Jul 2026 12:00:00 -0400</pubDate></item>
  <item><title>Old story</title><link>https://wire.example/1</link>
    <pubDate>Wed, 01 Jul 2026 08:00:00 GMT</pubDate></item>
  <item><title>Undated story</title><link>https://wire.example/2</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>AtomWire</title>
  <entry><title>Entry one</title>
    <link rel="alternate" href="https://atom.example/1"/>
    <published>2026-07-09T10:00:00Z</published></entry>
  <entry><title>Entry two</title><link href="https://atom.example/2"/>
    <updated>2026-07-08T10:00:00+00:00</updated></entry>
</feed>"""

# The real fixed-width-ish full-index layout (mirrors tests/test_edgar_index.py) with
# 424B4 IPO rows, a 424B5 row that must be ignored, and two filings by the same issuer
# (ticker dedupe: first filing wins).
_IDX_HEADER = (
    "Description:           Master Index of EDGAR Dissemination Feed by Form Type\n"
    "Form Type   Company Name                                                  CIK"
    "         Date Filed  File Name\n"
    "----------------------------------------------------------------------------\n"
)
_IDX_Q1 = _IDX_HEADER + (
    "424B4            NEWLIST ROBOTICS INC                                          "
    "111111      2024-08-05  edgar/data/111111/0001000000-24-000001.txt\n"
    "424B4            QUIET WATER CO                                                "
    "222222      2024-09-10  edgar/data/222222/0001000000-24-000002.txt\n"
    "424B5            SEASONED TAKEDOWN CORP                                        "
    "333333      2024-09-11  edgar/data/333333/0001000000-24-000003.txt\n"
    "424B4            NEWLIST ROBOTICS INC                                          "
    "111111      2024-09-20  edgar/data/111111/0001000000-24-000004.txt\n"
    "424B4            NO TICKER LTD                                                 "
    "444444      2024-09-25  edgar/data/444444/0001000000-24-000005.txt\n"
)

TICKER_MAP = {
    "0000111111": "NWLR",
    "0000222222": "QWTR",
    "0000333333": "STC",
}


class _FakeEdgar:
    def __init__(self, by_quarter):
        self._by_quarter = by_quarter

    def fetch_form_index(self, year, quarter):
        return self._by_quarter[(year, quarter)]


def _b4_index(tmp_path) -> EdgarIndex:
    return EdgarIndex(
        PointInTimeCache(tmp_path),
        edgar=_FakeEdgar({(2024, 3): _IDX_Q1}),
        cache_dir=tmp_path,
        form="424B4",
        source="digest_orphan",
    )


_WINDOW = dict(
    start=datetime(2024, 7, 1, tzinfo=UTC), end=datetime(2024, 9, 30, tzinfo=UTC)
)


# ── the Item schema guard (charter law: no scoring field, ever) ───────────────
def test_item_schema_has_no_scoring_field():
    # EXACT field set — adding ANY field (score/rank/relevance/weight/…) fails here first.
    assert {f.name for f in dataclasses.fields(Item)} == {
        "channel",
        "source",
        "title",
        "link",
        "published",
        "symbol",
    }


# ── RSS 2.0 / Atom parsing ────────────────────────────────────────────────────
def test_parse_rss2_titles_links_dates():
    items = parse_feed(RSS2, source="Wire", channel="trade_press")
    assert [i.title for i in items] == ["Grid order issued", "Old story", "Undated story"]
    assert [i.link for i in items] == [
        "https://wire.example/3",
        "https://wire.example/1",
        "https://wire.example/2",
    ]
    assert items[0].published == datetime(2026, 7, 10, 16, 0, tzinfo=UTC)  # -0400 → UTC
    assert items[1].published == datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    assert items[2].published is None  # missing date tolerated
    assert all(i.channel == "trade_press" and i.source == "Wire" for i in items)


def test_parse_atom_entries():
    items = parse_feed(ATOM, source="AtomWire", channel="agency")
    assert [i.title for i in items] == ["Entry one", "Entry two"]
    assert [i.link for i in items] == ["https://atom.example/1", "https://atom.example/2"]
    assert items[0].published == datetime(2026, 7, 9, 10, 0, tzinfo=UTC)
    assert items[1].published == datetime(2026, 7, 8, 10, 0, tzinfo=UTC)  # updated fallback


def test_parse_rss_nested_title_markup_and_loose_date():
    # Seen live (Fierce Network, Drupal): an <a> element INSIDE <title> and a
    # non-RFC-822 pubDate. Both must be tolerated, not dropped.
    xml = """<rss version="2.0"><channel><item>
      <title><a href="/x">Ericsson shares  tumble</a></title>
      <link>https://fn.example/x</link>
      <pubDate>Jul 14, 2026 12:41pm</pubDate>
    </item></channel></rss>"""
    (item,) = parse_feed(xml, source="FN", channel="trade_press")
    assert item.title == "Ericsson shares tumble"
    assert item.published == datetime(2026, 7, 14, 12, 41, tzinfo=UTC)


def test_fetch_rss_dead_feed_fails_soft_and_is_counted(monkeypatch):
    def _boom(url, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(digest, "_http_get", _boom)
    errors: list[str] = []
    assert fetch_rss("https://dead.example/rss", source="Dead", channel="trade_press",
                     errors=errors) == []
    assert len(errors) == 1 and "Dead" in errors[0]  # counted, never raises out


def test_fetch_rss_unparseable_body_fails_soft(monkeypatch):
    monkeypatch.setattr(digest, "_http_get", lambda url, **kw: b"<html>not a feed</html>")
    errors: list[str] = []
    assert fetch_rss("https://x.example/rss", source="X", channel="trade_press",
                     errors=errors) == []
    assert len(errors) == 1


# ── Federal Register (agency channel) ─────────────────────────────────────────
def test_federal_register_items_parses_and_scopes(monkeypatch):
    seen_urls: list[str] = []

    def _fake(url, **kwargs):
        seen_urls.append(url)
        return json.dumps(
            {"results": [
                {"title": "License  amendment", "html_url": "https://fr.example/doc",
                 "publication_date": "2026-07-10"},
                {"title": "No date doc", "html_url": "https://fr.example/doc2"},
            ]}
        ).encode()

    monkeypatch.setattr(digest, "_http_get", _fake)
    items = federal_register_items(
        ["nuclear-regulatory-commission"], days=8, now=datetime(2026, 7, 14, tzinfo=UTC)
    )
    assert len(items) == 2
    assert items[0].channel == "agency"
    assert items[0].source == "federal_register/nuclear-regulatory-commission"
    assert items[0].title == "License amendment"
    assert items[0].published == datetime(2026, 7, 10, tzinfo=UTC)
    assert items[1].published is None
    url = seen_urls[0]
    assert "conditions%5Bagencies%5D%5B%5D=nuclear-regulatory-commission" in url
    assert "conditions%5Bpublication_date%5D%5Bgte%5D=2026-07-06" in url
    assert "per_page=100" in url


def test_federal_register_failed_slug_counted(monkeypatch):
    def _boom(url, **kwargs):
        raise OSError("503")

    monkeypatch.setattr(digest, "_http_get", _boom)
    errors: list[str] = []
    assert federal_register_items(["internal-revenue-service"], days=8, errors=errors) == []
    assert len(errors) == 1 and "internal-revenue-service" in errors[0]


# ── assemble (no ranking; chronological; truncation-not-selection) ────────────
def _mk(channel, source, title, published, link="https://x.example"):
    return Item(channel=channel, source=source, title=title, link=link, published=published)


def test_assemble_groups_and_orders_chronologically():
    items = [
        _mk("trade_press", "Wire", "newest", datetime(2026, 7, 12, tzinfo=UTC)),
        _mk("agency", "federal_register/nrc", "notice", datetime(2026, 7, 9, tzinfo=UTC)),
        _mk("trade_press", "Wire", "undated-a", None),
        _mk("trade_press", "Wire", "oldest", datetime(2026, 7, 1, tzinfo=UTC)),
        _mk("trade_press", "Wire", "undated-b", None),
    ]
    doc = assemble(items, caps={}, week="2026-W29", dropped_notes=[],
                   generated_at=datetime(2026, 7, 14, tzinfo=UTC))
    # channel then source grouping
    assert doc.index("## trade_press") < doc.index("### Wire") < doc.index("## agency")
    assert "### federal_register/nrc" in doc
    # chronological within source; undated last, in input order
    assert (
        doc.index("oldest") < doc.index("newest")
        < doc.index("undated-a") < doc.index("undated-b")
    )


def test_assemble_caps_truncate_oldest_with_explicit_dropped_line():
    items = [
        _mk("trade_press", "Wire", f"story-{d:02d}", datetime(2026, 7, d, tzinfo=UTC))
        for d in range(1, 6)
    ]
    doc = assemble(items, caps={"trade_press": 3}, week="2026-W29", dropped_notes=[],
                   generated_at=datetime(2026, 7, 14, tzinfo=UTC))
    assert "… 2 older items dropped (per-source cap)" in doc
    assert "story-01" not in doc and "story-02" not in doc  # oldest truncated
    assert all(f"story-{d:02d}" in doc for d in (3, 4, 5))  # newest kept, still chronological
    assert "trade_press 3/5" in doc  # header count is shown/fetched honest


def test_assemble_header_week_counts_provenance_and_notes():
    items = [_mk("trade_press", "Wire", "one", datetime(2026, 7, 10, tzinfo=UTC))]
    doc = assemble(items, caps={}, week="2026-W29",
                   dropped_notes=["FAILED — trade_press/Dead: OSError: x"],
                   generated_at=datetime(2026, 7, 14, 15, 0, tzinfo=UTC))
    assert doc.startswith("# Reach digest — 2026-W29")
    assert "- generated: 2026-07-14T15:00:00+00:00" in doc
    assert "- provenance: trade_press/agency/orphan_watch" in doc
    assert "trade_press 1/1" in doc and "agency 0/0" in doc and "orphan_watch 0/0" in doc
    assert "## notes" in doc and "- FAILED — trade_press/Dead: OSError: x" in doc


def test_assemble_is_deterministic_for_fixed_inputs():
    items = [
        _mk("agency", "federal_register/irs", "b", None),
        _mk("agency", "federal_register/irs", "a", datetime(2026, 7, 9, tzinfo=UTC)),
    ]
    kwargs = dict(caps={"agency": 15}, week="2026-W29", dropped_notes=["n1"],
                  generated_at=datetime(2026, 7, 14, tzinfo=UTC))
    assert assemble(items, **kwargs) == assemble(items, **kwargs)


# ── orphan watch ──────────────────────────────────────────────────────────────
def test_orphan_cohort_dedupes_caps_and_counts(tmp_path):
    notes: list[str] = []
    cohort = orphan_cohort(
        _b4_index(tmp_path), **_WINDOW, limit=40, ticker_map=TICKER_MAP, notes=notes
    )
    # 424B5 ignored; NWLR deduped to its first filing; the unmapped CIK counted not silent
    assert [c["symbol"] for c in cohort] == ["NWLR", "QWTR"]
    assert cohort[0]["date_filed"] == "2024-08-05"
    assert any("no current ticker mapping" in n for n in notes)


def test_orphan_cohort_cap_drops_oldest_with_note(tmp_path):
    notes: list[str] = []
    cohort = orphan_cohort(
        _b4_index(tmp_path), **_WINDOW, limit=1, ticker_map=TICKER_MAP, notes=notes
    )
    assert [c["symbol"] for c in cohort] == ["QWTR"]  # chronological truncation: oldest dropped
    assert any("capped at 1; 1 older issuers dropped" in n for n in notes)


def test_orphan_new_listings_detects_only_new_listed_symbols():
    candidates = [
        {"symbol": "NWLR", "cik": "0000111111", "company": "NEWLIST", "date_filed": "2024-08-05"},
        {"symbol": "QWTR", "cik": "0000222222", "company": "QUIET", "date_filed": "2024-09-10"},
        {"symbol": "SEEN", "cik": "0000555555", "company": "SEEN CO", "date_filed": "2024-09-01"},
    ]
    snapshot = {"SEEN": "2026-07-07"}
    checked: list[str] = []

    def checker(symbol: str) -> bool:
        checked.append(symbol)
        return symbol == "NWLR"  # QWTR has no options class yet

    now = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    items, updated = orphan_new_listings(candidates, snapshot, checker, now=now)
    assert [i.symbol for i in items] == ["NWLR"]
    assert items[0].channel == "orphan_watch" and "NWLR" in items[0].title
    assert items[0].published == now
    # snapshot: new symbol stamped, prior entry preserved, unlisted symbol NOT marked seen
    assert updated == {"SEEN": "2026-07-07", "NWLR": "2026-07-14"}
    assert snapshot == {"SEEN": "2026-07-07"}  # input not mutated
    assert checked == ["NWLR", "QWTR"]  # already-seen symbols are not re-checked


def test_orphan_new_listings_checker_failure_counted_not_marked_seen():
    def checker(symbol: str) -> bool:
        raise RuntimeError("api down")

    errors: list[str] = []
    items, updated = orphan_new_listings(
        [{"symbol": "NWLR"}], {}, checker, now=datetime(2026, 7, 14, tzinfo=UTC), errors=errors
    )
    assert items == [] and updated == {}  # re-checked next run
    assert len(errors) == 1 and "NWLR" in errors[0]


def test_options_class_exists_true_iff_any_contract():
    # Offline: a fake TradingClient records the request and answers both response
    # shapes alpaca-py can return (model-like object and raw dict).
    from digest import options_class_exists

    class _FakeClient:
        def __init__(self, contracts, raw=False):
            self._contracts, self._raw = contracts, raw
            self.requests = []

        def get_option_contracts(self, request):
            self.requests.append(request)
            if self._raw:
                return {"option_contracts": self._contracts}
            import types

            return types.SimpleNamespace(option_contracts=self._contracts)

    listed = _FakeClient([object()])
    assert options_class_exists(listed, "NWLR") is True
    assert listed.requests[0].underlying_symbols == ["NWLR"]  # one cheap existence probe
    assert listed.requests[0].limit == 1
    assert options_class_exists(_FakeClient([]), "QWTR") is False
    assert options_class_exists(_FakeClient(None), "QWTR") is False  # None-shaped empties
    assert options_class_exists(_FakeClient([object()], raw=True), "NWLR") is True


def test_snapshot_roundtrip(tmp_path):
    path = tmp_path / "digest" / "orphan_seen.json"
    assert load_snapshot(path) == {}  # absent → empty, never raises
    save_snapshot({"B": "2026-07-14", "A": "2026-07-07"}, path)
    assert load_snapshot(path) == {"A": "2026-07-07", "B": "2026-07-14"}


# ── EdgarIndex form threading (existing param — the byte-compat guard) ────────
def test_edgar_index_form_defaults_to_424b5_and_424b4_threads(tmp_path):
    # default stays 424B5 — existing FSSD behavior byte-identical
    assert inspect.signature(parse_form_index).parameters["form"].default == "424B5"
    assert EdgarIndex(PointInTimeCache(tmp_path), edgar=None).form == "424B5"
    # 424B4 threads through parse_form_index (the digest's cohort form)
    recs = parse_form_index(_IDX_Q1, form="424B4")
    assert {r["form"] for r in recs} == {"424B4"}
    assert [r["cik"] for r in recs][:2] == ["0000111111", "0000222222"]


# ── date/window helpers ───────────────────────────────────────────────────────
def test_months_ago_and_closed_quarter_clamp():
    now = datetime(2026, 7, 14, tzinfo=UTC)
    assert months_ago(now, 12) == datetime(2025, 7, 14, tzinfo=UTC)
    assert months_ago(datetime(2026, 3, 31, tzinfo=UTC), 1) == datetime(2026, 2, 28, tzinfo=UTC)
    assert last_closed_quarter_end(now) == datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC)
    assert last_closed_quarter_end(datetime(2026, 2, 1, tzinfo=UTC)) == datetime(
        2025, 12, 31, 23, 59, 59, tzinfo=UTC
    )


def test_iso_week_stamp():
    assert iso_week_stamp(datetime(2026, 7, 14, tzinfo=UTC)) == "2026-W29"
    assert iso_week_stamp(datetime(2027, 1, 1, tzinfo=UTC)) == "2026-W53"  # ISO year


# ── runner path: fail-soft, counted, exit codes ───────────────────────────────
@pytest.fixture()
def feeds_file(tmp_path):
    cfg = {
        "trade_press": [
            {"source": "Dead Wire", "url": "https://dead.example/rss"},
            {"source": "Live Wire", "url": "https://live.example/rss"},
        ],
        "agency": {"federal_register_agencies": [], "rss": []},
        "orphan_watch": {"ipo_age_months_min": 12, "ipo_age_months_max": 24, "cohort_limit": 40},
        "caps": {"trade_press": 15, "agency": 15, "orphan_watch": 20},
        "lookback_days": 100000,  # fixtures carry fixed 2026 dates; keep them in-window
    }
    path = tmp_path / "digest_feeds.json"
    path.write_text(json.dumps(cfg))
    return path


def test_runner_dead_feed_degrades_and_digest_still_ships(feeds_file, capsys, monkeypatch):
    import scripts.digest_weekly as runner

    def fake_fetch(url, *, source, channel, timeout=20, errors=None):
        if "dead" in url:
            raise OSError("boom")  # raising INSIDE the runner path, not fetch_rss's own guard
        return parse_feed(RSS2, source=source, channel=channel)

    monkeypatch.setattr(runner, "fetch_rss", fake_fetch)
    rc = runner.main(["--feeds", str(feeds_file), "--skip-orphan", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0  # partial failure is fail-soft
    assert "trade_press/Dead Wire: FAILED" in out  # the dead arm is counted and printed
    assert "trade_press/Live Wire: 3 item(s)" in out  # …and never kills the live arms
    assert "orphan_watch: skipped (--skip-orphan)" in out
    assert "# Reach digest — " in out  # dry-run prints the document instead of writing


def test_runner_exit_1_only_when_all_empty_and_errored(feeds_file, capsys, monkeypatch):
    import scripts.digest_weekly as runner

    def all_dead(url, *, source, channel, timeout=20, errors=None):
        raise OSError("boom")

    monkeypatch.setattr(runner, "fetch_rss", all_dead)
    rc = runner.main(["--feeds", str(feeds_file), "--skip-orphan", "--dry-run"])
    assert rc == 1
    assert "exit 1" in capsys.readouterr().out


def test_runner_quiet_week_without_errors_exits_0(feeds_file, capsys, monkeypatch):
    import scripts.digest_weekly as runner

    monkeypatch.setattr(
        runner, "fetch_rss", lambda url, *, source, channel, timeout=20, errors=None: []
    )
    rc = runner.main(["--feeds", str(feeds_file), "--skip-orphan", "--dry-run"])
    assert rc == 0  # a quiet week is NOT a dead week
    assert "0 item(s)" in capsys.readouterr().out
