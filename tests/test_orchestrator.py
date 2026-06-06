"""Orchestrator pre-council guard (PR2): entries_allowed + fail-closed market-open.

These are the two pure pieces of the FORWARD_ENABLED + market-open gate that decides — BEFORE
any LLM spend — whether a cycle evaluates new entries, and that fails CLOSED if the market-state
call errors. The heavier wiring (monitor mark-only when closed, post-council re-check) is
exercised by the offline `--demo` run.
"""

from datetime import UTC, datetime

from dramatic_options import orchestrator


class _Clock:
    def __init__(self, *, raises: bool = False, open_: bool = False) -> None:
        self._raises = raises
        self._open = open_

    def is_market_open(self) -> bool:
        if self._raises:
            raise RuntimeError("alpaca clock unreachable")
        return self._open

    def now(self) -> datetime:
        return datetime.now(UTC)


def test_safe_market_open_fail_closed_on_error():
    # An outage/partial failure must read as CLOSED — never act on an unconfirmed state.
    assert orchestrator._safe_market_open(_Clock(raises=True)) is False


def test_safe_market_open_passthrough():
    assert orchestrator._safe_market_open(_Clock(open_=True)) is True
    assert orchestrator._safe_market_open(_Clock(open_=False)) is False


def test_entries_allowed_demo_always_runs():
    ok, _ = orchestrator.entries_allowed(forward_enabled=False, market_open=False, demo=True)
    assert ok is True


def test_entries_allowed_inert_env_blocks():
    ok, why = orchestrator.entries_allowed(forward_enabled=False, market_open=True, demo=False)
    assert ok is False
    assert "FORWARD_ENABLED" in why


def test_entries_allowed_closed_market_blocks():
    ok, why = orchestrator.entries_allowed(forward_enabled=True, market_open=False, demo=False)
    assert ok is False
    assert "closed" in why.lower()


def test_entries_allowed_open_and_enabled():
    ok, _ = orchestrator.entries_allowed(forward_enabled=True, market_open=True, demo=False)
    assert ok is True
