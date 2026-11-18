"""Injectable clock + market-state provider.

All app code reads "now" and market open/closed through a Clock, never via a bare
``datetime.now()``. This is what makes Phase 1's point-in-time backtest possible
without lookahead: production uses ``LiveClock`` (wrapping the Alpaca clock), tests
and the replay harness use ``FixedClock``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Protocol, runtime_checkable
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def et_date(now: datetime) -> date:
    """The US-Eastern calendar date of ``now`` (a naive ``now`` is read as UTC, as ``Clock`` promises).

    Every schedule-anchored date decision (expiry, DTE, the daily page debounce) uses this, never ``now.date()``:
    ``LiveClock.now()`` is UTC, whose date is already tomorrow after 19:00 ET (20:00 ET under EDT) (#480)."""
    return (now if now.tzinfo is not None else now.replace(tzinfo=UTC)).astimezone(ET).date()


@runtime_checkable
class Clock(Protocol):
    """Time + market-state source."""

    def now(self) -> datetime:
        """Current time, timezone-aware (UTC)."""
        ...

    def is_market_open(self) -> bool:
        """True if the equity market is currently open."""
        ...


class FixedClock:
    """Deterministic clock for tests and the backtest replay harness."""

    def __init__(self, now: datetime, market_open: bool = False) -> None:
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        self._now = now
        self._market_open = market_open

    def now(self) -> datetime:
        return self._now

    def is_market_open(self) -> bool:
        return self._market_open

    # Test/replay helpers — never used in production paths.
    def advance(self, seconds: float) -> None:
        self._now = self._now + timedelta(seconds=seconds)

    def set_market_open(self, is_open: bool) -> None:
        self._market_open = is_open


class LiveClock:
    """Production clock. Wraps an Alpaca client for authoritative market state.

    ``alpaca_client`` is duck-typed: it only needs ``is_market_open()`` (the
    AlpacaClient wrapper provides it). Kept optional so a LiveClock can still report
    wall-clock time before a broker connection exists.
    """

    def __init__(self, alpaca_client=None) -> None:
        self._client = alpaca_client

    def now(self) -> datetime:
        return datetime.now(UTC)

    def is_market_open(self) -> bool:
        if self._client is None:
            return False
        return bool(self._client.is_market_open())
