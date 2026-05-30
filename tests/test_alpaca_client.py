"""Alpaca client wrapper — constructed with mocked SDK clients (no network)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import data.alpaca_client as ac


def _client(monkeypatch):
    trading = MagicMock(name="TradingClient")
    dataclient = MagicMock(name="StockHistoricalDataClient")
    monkeypatch.setattr(ac, "TradingClient", MagicMock(return_value=trading))
    monkeypatch.setattr(ac, "StockHistoricalDataClient", MagicMock(return_value=dataclient))
    return ac.AlpacaClient("k", "s", paper=True), trading, dataclient


def test_construction_passes_paper_flag(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        ac, "TradingClient", lambda *a, **kw: captured.update(kw) or MagicMock()
    )
    monkeypatch.setattr(ac, "StockHistoricalDataClient", MagicMock())
    ac.AlpacaClient("k", "s", paper=True)
    assert captured.get("paper") is True


def test_get_equity_returns_float(monkeypatch):
    client, trading, _ = _client(monkeypatch)
    trading.get_account.return_value = SimpleNamespace(equity="98765.43")
    assert client.get_equity() == 98765.43


def test_is_market_open(monkeypatch):
    client, trading, _ = _client(monkeypatch)
    trading.get_clock.return_value = SimpleNamespace(is_open=True)
    assert client.is_market_open() is True


def test_no_order_submission_surface(monkeypatch):
    """Phase 0 guardrail: the read-only wrapper exposes no order-submit method."""
    client, _, _ = _client(monkeypatch)
    for forbidden in ("submit_order", "place_order", "submit_mleg", "buy", "sell"):
        assert not hasattr(client, forbidden), f"{forbidden} must not exist in Phase 0"
