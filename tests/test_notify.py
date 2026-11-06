"""notify.send: no-op without keys, posts with keys, NEVER raises. CLI smoke (hermetic)."""

import pytest

import notify


def test_send_noop_without_keys(monkeypatch):
    monkeypatch.delenv("PUSHOVER_API_TOKEN", raising=False)
    monkeypatch.delenv("PUSHOVER_USER_KEY", raising=False)
    # No network call should be attempted at all → False, no exception.
    assert notify.send("title", "msg") is False


def test_send_posts_with_keys(monkeypatch):
    monkeypatch.setenv("PUSHOVER_API_TOKEN", "tok")
    monkeypatch.setenv("PUSHOVER_USER_KEY", "usr")
    captured = {}

    class _Resp:
        status_code = 200
        text = "ok"

    def _fake_post(url, data=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return _Resp()

    import requests

    monkeypatch.setattr(requests, "post", _fake_post)
    assert notify.send("Kill rule", "halted", priority=1) is True
    assert captured["url"] == notify.PUSHOVER_URL
    assert captured["data"]["token"] == "tok"
    assert captured["data"]["user"] == "usr"
    assert captured["data"]["priority"] == 1
    assert "Kill rule" in captured["data"]["title"]


def test_send_never_raises_on_transport_error(monkeypatch):
    monkeypatch.setenv("PUSHOVER_API_TOKEN", "tok")
    monkeypatch.setenv("PUSHOVER_USER_KEY", "usr")
    import requests

    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(requests, "post", _boom)
    # The whole point: a paging failure must never propagate into a trade cycle.
    assert notify.send("t", "m") is False


def test_send_non_2xx_returns_false(monkeypatch):
    monkeypatch.setenv("PUSHOVER_API_TOKEN", "tok")
    monkeypatch.setenv("PUSHOVER_USER_KEY", "usr")

    class _Resp:
        status_code = 500
        text = "err"

    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp())
    assert notify.send("t", "m") is False


def test_cli_systemd_failure_smoke(monkeypatch):
    """`notify.py --systemd-failure UNIT` exits 0 and never raises, even with no keys/journal."""
    # Hermetic: don't load the developer's real .env (which carries PUSHOVER_* here).
    monkeypatch.setattr(notify, "_load_env", lambda: None)
    monkeypatch.delenv("PUSHOVER_API_TOKEN", raising=False)
    monkeypatch.delenv("PUSHOVER_USER_KEY", raising=False)
    assert notify.main(["--systemd-failure", "dramatic-options-l1.service"]) == 0


def test_cli_requires_a_title(monkeypatch):
    monkeypatch.setattr(notify, "_load_env", lambda: None)
    with pytest.raises(SystemExit):
        notify.main([])


def test_a_sent_page_logs_its_title_and_never_the_body_or_keys(monkeypatch, caplog):
    # #430: a successful push left no journal line, so a debounced page (LHX coverage-feasibility, 11-05)
    # could not be confirmed from journald.
    monkeypatch.setenv("PUSHOVER_API_TOKEN", "tok-secret")
    monkeypatch.setenv("PUSHOVER_USER_KEY", "usr-secret")

    class _Resp:
        status_code = 200
        text = "ok"

    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp())
    with caplog.at_level("INFO", logger="notify"):
        assert notify.send("OPRA dual-read: coverage-feasibility", "LHX: body text", priority=0) is True
    lines = [r.getMessage() for r in caplog.records if r.name == "notify"]
    assert lines == ["notify: sent 'OPRA dual-read: coverage-feasibility'"]
    assert not any(s in m for m in lines for s in ("LHX: body text", "tok-secret", "usr-secret"))
