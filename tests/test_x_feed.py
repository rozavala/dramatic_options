"""The x_lists ingestion leg (charter §2 + the 2026-07-16 amendment) — NO network anywhere.

Every fetcher runs over a monkeypatched ``data.x_feed._bearer_get_json``; the runner path
over a monkeypatched ``config_loader.load_config`` / ``data.x_feed.fetch_x_channel``. The
no-engagement guard is charter law: the request field-set literals are pinned so a future
``public_metrics`` (any engagement field) fails CI before it can fail the charter. No key
material anywhere — tokens in fixtures are obviously fake."""

from __future__ import annotations

import email.message
import json
import urllib.error
import urllib.parse
from datetime import UTC, datetime

import pytest

import data.x_feed as x_feed
from data.x_feed import (
    XChannelOff,
    fetch_x_channel,
    load_since_ids,
    resolve_user_ids,
    save_since_ids,
    timeline_items,
    timeline_url,
    tweet_title,
    users_by_url,
)
from digest import assemble

FAKE_TOKEN = "not-a-real-token"

ACCOUNTS_CFG = {
    "enabled": True,
    "verticals": {
        "fiber": [
            {"handle": "DougDawson_CCG", "name": "Doug Dawson"},
            {"handle": "jaredmauch", "name": "Jared Mauch"},
        ],
        "nuclear": [{"handle": "whatisnuclear", "name": "Nick Touran"}],
    },
    "caps": {"per_account_per_week": 10, "per_vertical_per_week": 25},
}

USERS_BY_PAYLOAD = {
    "data": [
        {"id": "101", "name": "Doug Dawson", "username": "dougdawson_ccg"},  # case-insensitive
        {"id": "102", "name": "Jared Mauch", "username": "jaredmauch"},
        {"id": "103", "name": "Nick Touran", "username": "whatisnuclear"},
    ]
}

TIMELINE_PAYLOAD = {
    "data": [
        {
            "id": "9002",
            "text": "Middle-mile  builds\nare stalling on pole attachments",
            "created_at": "2026-07-15T14:00:00.000Z",
        },
        {"id": "9001", "text": "BEAD round two", "created_at": "2026-07-14T09:30:00.000Z"},
    ],
    "meta": {"newest_id": "9002", "oldest_id": "9001", "result_count": 2},
}


def _http_error(code: int, headers: dict[str, str] | None = None) -> urllib.error.HTTPError:
    msg = email.message.Message()
    for k, v in (headers or {}).items():
        msg[k] = v
    return urllib.error.HTTPError("https://api.x.com/2/x", code, "err", msg, None)


# ── the no-engagement schema guard (charter §2: no engagement math anywhere) ──
def test_request_field_set_contains_no_engagement_fields():
    # The ENTIRE per-tweet field set, pinned as a literal — adding public_metrics (or any
    # engagement field) must fail HERE first.
    assert x_feed.TWEET_FIELDS == "created_at,text"
    assert x_feed.TIMELINE_EXCLUDE == "retweets,replies"
    url = timeline_url("42", since_id="7", max_results=10)
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert set(params) == {"tweet.fields", "exclude", "max_results", "since_id"}
    assert params["tweet.fields"] == "created_at,text"
    assert params["exclude"] == "retweets,replies"
    assert "public_metrics" not in url and "metrics" not in url
    # users/by: ONLY the usernames param — no user.fields, no follower counts.
    u = users_by_url(["a", "b"])
    uparams = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(u).query))
    assert set(uparams) == {"usernames"} and uparams["usernames"] == "a,b"
    assert "metrics" not in u


def test_timeline_url_without_since_id_omits_the_param():
    url = timeline_url("42", since_id=None, max_results=10)
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert set(params) == {"tweet.fields", "exclude", "max_results"}
    assert url.startswith("https://api.x.com/2/users/42/tweets?")


# ── Item mapping ──────────────────────────────────────────────────────────────
def test_timeline_items_mapping():
    items = timeline_items(TIMELINE_PAYLOAD, handle="DougDawson_CCG", vertical="fiber")
    assert [i.channel for i in items] == ["x_lists", "x_lists"]
    assert [i.source for i in items] == ["x/fiber/DougDawson_CCG"] * 2
    assert items[0].title == "Middle-mile builds are stalling on pole attachments"
    assert items[0].link == "https://x.com/DougDawson_CCG/status/9002"
    assert items[0].published == datetime(2026, 7, 15, 14, 0, tzinfo=UTC)
    assert items[1].published == datetime(2026, 7, 14, 9, 30, tzinfo=UTC)


def test_tweet_title_truncates_to_140_chars_with_ellipsis():
    long = "word " * 60  # 300 chars
    title = tweet_title(long)
    assert len(title) <= 140 and title.endswith("…")
    assert tweet_title("short post") == "short post"
    assert tweet_title("  spaced\n\nout  ") == "spaced out"
    assert tweet_title("") == "(empty post)"


# ── since_id state round-trip ─────────────────────────────────────────────────
def test_since_id_state_roundtrip(tmp_path):
    path = tmp_path / "digest" / "x_since_ids.json"
    assert load_since_ids(path) == {}  # absent → empty, never raises
    save_since_ids({"b": "9002", "a": "9001"}, path)
    assert load_since_ids(path) == {"a": "9001", "b": "9002"}


# ── ID cache with display-name recording (the eyeball surface) ────────────────
def test_resolve_user_ids_caches_display_names_and_notes(tmp_path, monkeypatch):
    calls: list[str] = []

    def fake(url, token, *, timeout=20):
        calls.append(url)
        return USERS_BY_PAYLOAD, {}

    monkeypatch.setattr(x_feed, "_bearer_get_json", fake)
    notes: list[str] = []
    out = resolve_user_ids(
        ["DougDawson_CCG", "jaredmauch"], FAKE_TOKEN, cache_dir=tmp_path, notes=notes
    )
    assert out == {
        "DougDawson_CCG": {"id": "101", "name": "Doug Dawson"},
        "jaredmauch": {"id": "102", "name": "Jared Mauch"},
    }
    # one batch request; the cache file records id AND display name per handle
    assert len(calls) == 1 and "usernames=DougDawson_CCG%2Cjaredmauch" in calls[0]
    cached = json.loads((tmp_path / "x_user_ids.json").read_text())
    assert cached["DougDawson_CCG"] == {"id": "101", "name": "Doug Dawson"}
    # the one-time verification table: header + one handle→display-name line each
    assert any("VERIFY each display name" in n for n in notes)
    assert "x_lists:   @DougDawson_CCG → Doug Dawson" in notes
    assert "x_lists:   @jaredmauch → Jared Mauch" in notes

    # second run: network-free (cache hit), and the verification table does NOT re-fire
    calls.clear()
    notes2: list[str] = []
    out2 = resolve_user_ids(
        ["DougDawson_CCG", "jaredmauch"], FAKE_TOKEN, cache_dir=tmp_path, notes=notes2
    )
    assert out2 == out and calls == [] and notes2 == []


def test_resolve_user_ids_unresolved_handle_counted_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(x_feed, "_bearer_get_json", lambda url, token, **kw: (USERS_BY_PAYLOAD, {}))
    errors: list[str] = []
    out = resolve_user_ids(
        ["DougDawson_CCG", "gone_handle"], FAKE_TOKEN, cache_dir=tmp_path, errors=errors
    )
    assert "DougDawson_CCG" in out and "gone_handle" not in out
    assert len(errors) == 1 and "gone_handle" in errors[0]
    # NOT cached → retried next run
    assert "gone_handle" not in json.loads((tmp_path / "x_user_ids.json").read_text())


def test_resolve_user_ids_401_is_channel_off(tmp_path, monkeypatch):
    def boom(url, token, **kw):
        raise _http_error(401)

    monkeypatch.setattr(x_feed, "_bearer_get_json", boom)
    with pytest.raises(XChannelOff, match="401"):
        resolve_user_ids(["DougDawson_CCG"], FAKE_TOKEN, cache_dir=tmp_path)


# ── the channel fetch: mapping, since_id threading, fail-soft per account ─────
def _fake_http(seen_urls: list[str], *, fail_handle_ids: dict[str, int] | None = None):
    """users/by → the fixture; /users/<id>/tweets → the timeline fixture (or an HTTP
    error for ids in ``fail_handle_ids``)."""

    def fake(url, token, *, timeout=20):
        seen_urls.append(url)
        if "/users/by" in url:
            return USERS_BY_PAYLOAD, {}
        for uid, code in (fail_handle_ids or {}).items():
            if f"/users/{uid}/tweets" in url:
                raise _http_error(code)
        return TIMELINE_PAYLOAD, {}

    return fake


def test_fetch_x_channel_maps_threads_since_ids_and_updates_state(tmp_path, monkeypatch):
    urls: list[str] = []
    monkeypatch.setattr(x_feed, "_bearer_get_json", _fake_http(urls))
    save_since_ids({"jaredmauch": "8000"}, tmp_path / "x_since_ids.json")
    notes: list[str] = []
    errors: list[str] = []
    items, updated = fetch_x_channel(
        ACCOUNTS_CFG, FAKE_TOKEN, cache_dir=tmp_path, rate_limit_per_sec=0,
        errors=errors, notes=notes,
    )
    # 3 accounts × 2 fixture posts, all mapped
    assert len(items) == 6 and errors == []
    assert {i.source for i in items} == {
        "x/fiber/DougDawson_CCG", "x/fiber/jaredmauch", "x/nuclear/whatisnuclear"
    }
    # since_id: threaded into the URL for the handle that HAS state, absent otherwise;
    # max_results capped at the per-account cap (billing is per post returned)
    (jared_url,) = [u for u in urls if "/users/102/tweets" in u]
    assert "since_id=8000" in jared_url and "max_results=10" in jared_url
    (doug_url,) = [u for u in urls if "/users/101/tweets" in u]
    assert "since_id" not in doug_url
    # state advanced to the fixture's newest_id for every pulled account
    assert updated == {
        "DougDawson_CCG": "9002", "jaredmauch": "9002", "whatisnuclear": "9002"
    }


def test_fetch_x_channel_fail_soft_per_account_keeps_since_id(tmp_path, monkeypatch):
    urls: list[str] = []
    # jaredmauch (id 102) is protected/gone → 403; the others must still flow
    monkeypatch.setattr(
        x_feed, "_bearer_get_json", _fake_http(urls, fail_handle_ids={"102": 403})
    )
    save_since_ids({"jaredmauch": "8000"}, tmp_path / "x_since_ids.json")
    errors: list[str] = []
    items, updated = fetch_x_channel(
        ACCOUNTS_CFG, FAKE_TOKEN, cache_dir=tmp_path, rate_limit_per_sec=0, errors=errors
    )
    assert len(items) == 4  # the two live accounts
    assert len(errors) == 1 and "@jaredmauch" in errors[0] and "403" in errors[0]
    assert updated["jaredmauch"] == "8000"  # NOT advanced — nothing lost, retried next run


def test_fetch_x_channel_401_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        x_feed, "_bearer_get_json", _fake_http([], fail_handle_ids={"101": 401})
    )
    with pytest.raises(XChannelOff, match="401"):
        fetch_x_channel(ACCOUNTS_CFG, FAKE_TOKEN, cache_dir=tmp_path, rate_limit_per_sec=0)
    with pytest.raises(XChannelOff, match="no bearer token"):
        fetch_x_channel(ACCOUNTS_CFG, "", cache_dir=tmp_path, rate_limit_per_sec=0)


def test_fetch_x_channel_request_budget_defers_with_counted_note(tmp_path, monkeypatch):
    monkeypatch.setattr(x_feed, "_bearer_get_json", _fake_http([]))
    notes: list[str] = []
    items, updated = fetch_x_channel(
        ACCOUNTS_CFG, FAKE_TOKEN, cache_dir=tmp_path, rate_limit_per_sec=0,
        max_requests=2, notes=notes,
    )
    assert len(items) == 4  # only 2 timeline pulls fit the budget
    assert any("request budget (2) exhausted; 1 account(s) deferred" in n for n in notes)
    assert "whatisnuclear" not in updated  # the deferred account's state is untouched


def test_fetch_x_channel_rate_limit_headers_stop_the_run(tmp_path, monkeypatch):
    def fake(url, token, *, timeout=20):
        if "/users/by" in url:
            return USERS_BY_PAYLOAD, {}
        return TIMELINE_PAYLOAD, {"x-rate-limit-remaining": "0", "x-rate-limit-reset": "1799999999"}

    monkeypatch.setattr(x_feed, "_bearer_get_json", fake)
    notes: list[str] = []
    items, _updated = fetch_x_channel(
        ACCOUNTS_CFG, FAKE_TOKEN, cache_dir=tmp_path, rate_limit_per_sec=0, notes=notes
    )
    assert len(items) == 2  # the first pull came back rate-capped → the rest deferred
    assert any("rate-limited (reset 1799999999); 2 account(s) deferred" in n for n in notes)


def test_fetch_x_channel_per_vertical_cap_truncates_oldest_with_note(tmp_path, monkeypatch):
    monkeypatch.setattr(x_feed, "_bearer_get_json", _fake_http([]))
    cfg = json.loads(json.dumps(ACCOUNTS_CFG))
    cfg["caps"]["per_vertical_per_week"] = 3  # fiber fetches 2 accounts × 2 posts = 4
    notes: list[str] = []
    items, _ = fetch_x_channel(
        cfg, FAKE_TOKEN, cache_dir=tmp_path, rate_limit_per_sec=0, notes=notes
    )
    fiber = [i for i in items if i.source.startswith("x/fiber/")]
    assert len(fiber) == 3
    assert any("fiber capped at 3/week; 1 older item(s) dropped" in n for n in notes)
    # chronological truncation: a NEWEST post from each account survives
    assert {i.link.rsplit("/", 1)[-1] for i in fiber} >= {"9002"}
    assert len([i for i in items if i.source.startswith("x/nuclear/")]) == 2  # untouched


# ── through assemble: own channel group, per-ACCOUNT cap = per-source cap ─────
def test_x_items_flow_through_assemble_with_chronological_truncation():
    payload = {
        "data": [
            {"id": str(9000 + d), "text": f"post-{d:02d}",
             "created_at": f"2026-07-{d:02d}T12:00:00.000Z"}
            for d in range(5, 0, -1)  # newest-first, like the API
        ],
        "meta": {"newest_id": "9005", "result_count": 5},
    }
    items = timeline_items(payload, handle="DougDawson_CCG", vertical="fiber")
    doc = assemble(items, caps={"x_lists": 3}, week="2026-W29", dropped_notes=[],
                   generated_at=datetime(2026, 7, 16, tzinfo=UTC))
    assert "## x_lists" in doc and "### x/fiber/DougDawson_CCG" in doc
    assert "… 2 older items dropped (per-source cap)" in doc
    assert "post-01" not in doc and "post-02" not in doc  # oldest truncated
    assert doc.index("post-03") < doc.index("post-04") < doc.index("post-05")  # chronological
    assert "x_lists 3/5" in doc  # shown/fetched honest
    assert "- provenance: trade_press/newsletters/x_lists/agency/orphan_watch" in doc


# ── runner wiring: OFF states are loud counted notes, never a silent dead arm ─
@pytest.fixture()
def feeds_file(tmp_path):
    path = tmp_path / "digest_feeds.json"
    path.write_text(json.dumps({
        "trade_press": [], "agency": {"federal_register_agencies": [], "rss": []},
        "caps": {}, "lookback_days": 8,
    }))
    return path


def _run(runner, feeds_file, accounts_path, capsys):
    rc = runner.main([
        "--feeds", str(feeds_file), "--skip-orphan", "--dry-run",
        "--x-accounts", str(accounts_path),
    ])
    return rc, capsys.readouterr().out


def test_runner_x_off_when_accounts_file_missing(feeds_file, tmp_path, capsys):
    import scripts.digest_weekly as runner

    rc, out = _run(runner, feeds_file, tmp_path / "nope.json", capsys)
    assert rc == 0  # OFF is a counted note, never a raise/exit
    assert "x_lists: OFF" in out and "not found" in out
    assert "- x_lists: OFF" in out  # the note rides the digest document too


def test_runner_x_off_when_config_disabled(feeds_file, tmp_path, capsys):
    import scripts.digest_weekly as runner

    accounts = tmp_path / "x_accounts.json"
    accounts.write_text(json.dumps({**ACCOUNTS_CFG, "enabled": False}))
    rc, out = _run(runner, feeds_file, accounts, capsys)
    assert rc == 0
    assert "x_lists: OFF (disabled in x_accounts.json" in out
    assert "x_probe.py" in out  # the note points at the retained §2(b) gate


def test_runner_x_off_when_no_token_fail_closed(feeds_file, tmp_path, capsys, monkeypatch):
    import scripts.digest_weekly as runner

    accounts = tmp_path / "x_accounts.json"
    accounts.write_text(json.dumps(ACCOUNTS_CFG))
    monkeypatch.setattr("config_loader.load_config", lambda: {"x_api": {}})
    rc, out = _run(runner, feeds_file, accounts, capsys)
    assert rc == 0  # counted note, no raise
    assert "x_lists: OFF (no X_BEARER_TOKEN)" in out


def test_runner_x_channel_off_is_loud_and_counted(feeds_file, tmp_path, capsys, monkeypatch):
    import scripts.digest_weekly as runner

    accounts = tmp_path / "x_accounts.json"
    accounts.write_text(json.dumps(ACCOUNTS_CFG))
    monkeypatch.setattr(
        "config_loader.load_config", lambda: {"x_api": {"bearer_token": FAKE_TOKEN}}
    )

    def off(cfg, token, **kw):
        raise XChannelOff("users/by HTTP 403 — token rejected or tier lacks user lookup")

    monkeypatch.setattr("data.x_feed.fetch_x_channel", off)
    rc, out = _run(runner, feeds_file, accounts, capsys)
    # A runtime channel-off is counted as an ERROR (unlike the config-OFF states above);
    # with every other channel empty too, the existing all-empty+errored policy exits 1.
    assert rc == 1
    assert "x_lists: OFF (users/by HTTP 403" in out
    assert "FAILED — x_lists: OFF" in out  # counted as an error in the notes tail


def test_runner_x_items_flow_end_to_end(feeds_file, tmp_path, capsys, monkeypatch):
    import scripts.digest_weekly as runner

    accounts = tmp_path / "x_accounts.json"
    accounts.write_text(json.dumps(ACCOUNTS_CFG))
    monkeypatch.setattr(
        "config_loader.load_config", lambda: {"x_api": {"bearer_token": FAKE_TOKEN}}
    )
    monkeypatch.setattr("data.x_feed._bearer_get_json", _fake_http([]))
    # keep the fetcher network-free caches inside tmp: point the module paths there
    monkeypatch.setattr(x_feed, "DIGEST_CACHE_DIR", tmp_path)
    rc, out = _run(runner, feeds_file, accounts, capsys)
    assert rc == 0
    assert "x_lists: 6 item(s) from 3 account(s)" in out
    assert "## x_lists" in out and "### x/fiber/DougDawson_CCG" in out
    assert "https://x.com/DougDawson_CCG/status/9002" in out
    assert "VERIFY each display name" in out  # first-resolution eyeball table rides the notes


def test_runner_skip_x_flag(feeds_file, tmp_path, capsys):
    import scripts.digest_weekly as runner

    rc = runner.main([
        "--feeds", str(feeds_file), "--skip-orphan", "--skip-x", "--dry-run",
        "--x-accounts", str(tmp_path / "unused.json"),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "x_lists: skipped (--skip-x)" in out
