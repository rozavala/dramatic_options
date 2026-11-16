"""The post-L1 measurement runner (post_l1.py, ``--post-l1``): passes are independent and the exit code is 1 only if
one raised (PREREG_COUNCIL_GATE_SEPARATION §10.12/§10.13 share one unit)."""

from __future__ import annotations

import logging

import post_l1


def test_one_pass_raising_does_not_stop_the_next_and_exits_one(caplog):
    ran = []

    def boom(cfg):
        ran.append("a")
        raise RuntimeError("pass a broke")

    passes = [("a", boom), ("b", lambda cfg: ran.append("b"))]
    with caplog.at_level(logging.ERROR, logger="post_l1"):
        assert post_l1.run({}, passes) == 1
    assert ran == ["a", "b"]
    assert any("pass a failed" in r.getMessage() for r in caplog.records)


def test_all_passes_returning_exit_zero():
    ran = []
    assert post_l1.run({"x": 1}, [("a", lambda c: ran.append(c)), ("b", lambda c: ran.append(c))]) == 0
    assert ran == [{"x": 1}, {"x": 1}]


def test_the_repeat_probe_is_the_first_registered_pass():
    assert post_l1.PASSES[0][0] == "repeat_probe"


def test_post_l1_flag_dispatches_and_a_disabled_probe_is_quiet(monkeypatch, caplog):
    import config_loader
    import orchestrator
    import state

    monkeypatch.setattr(config_loader, "load_config",
                        lambda: {"council": {"repeat_probe": {"enabled": False}, "held_reads": {"enabled": False}}})
    monkeypatch.setattr(state, "get_db", lambda *a, **k: (_ for _ in ()).throw(AssertionError("DB opened")))
    with caplog.at_level(logging.INFO):
        assert orchestrator.main(["--post-l1"]) == 0
    assert any(r.name == "council.repeat_probe" and r.levelno == logging.INFO for r in caplog.records)
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_post_l1_exits_one_when_a_pass_raises(monkeypatch):
    import config_loader
    import orchestrator

    monkeypatch.setattr(config_loader, "load_config", lambda: {})
    monkeypatch.setattr(post_l1, "PASSES", [("x", lambda c: 1 / 0), ("y", lambda c: None)])
    assert orchestrator.main(["--post-l1"]) == 1
