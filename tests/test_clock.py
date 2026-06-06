"""Injectable clock: FixedClock determinism (the backtest/no-lookahead foundation)."""

from datetime import UTC, datetime

from dramatic_options.clock import Clock, FixedClock, LiveClock


def test_fixedclock_is_deterministic():
    t = datetime(2026, 1, 2, 15, 30, tzinfo=UTC)
    c = FixedClock(t, market_open=True)
    assert c.now() == t
    assert c.now() == t  # does not advance on its own
    assert c.is_market_open() is True


def test_fixedclock_naive_input_is_utc():
    c = FixedClock(datetime(2026, 1, 2, 15, 30))
    assert c.now().tzinfo == UTC


def test_fixedclock_advance_and_toggle():
    c = FixedClock(datetime(2026, 1, 2, 15, 30, tzinfo=UTC))
    assert c.is_market_open() is False
    c.set_market_open(True)
    assert c.is_market_open() is True
    c.advance(60)
    assert c.now() == datetime(2026, 1, 2, 15, 31, tzinfo=UTC)


def test_fixedclock_satisfies_protocol():
    assert isinstance(FixedClock(datetime.now(UTC)), Clock)


def test_liveclock_without_client_is_closed():
    c = LiveClock(None)
    assert c.is_market_open() is False
    assert c.now().tzinfo == UTC


def test_liveclock_delegates_market_state():
    class _Stub:
        def is_market_open(self):
            return True

    assert LiveClock(_Stub()).is_market_open() is True
