"""AlpacaPaperBroker: DRY_RUN logs-not-sends, live builds the order, errors fail-closed."""

from types import SimpleNamespace

import broker as broker_mod
from broker import AlpacaLiveBroker, AlpacaPaperBroker, Fill, PaperBroker


class FakeTradingClient:
    """Stand-in for alpaca TradingClient — records submits, returns canned orders."""

    def __init__(self, *a, **k):
        self.submitted = []
        self.cancelled = []
        self._next = None
        self._raise = False

    def get_account(self):
        return SimpleNamespace(equity="100000.0")

    def submit_order(self, req):
        if self._raise:
            raise RuntimeError("boom-api")
        self.submitted.append(req)
        return self._next or SimpleNamespace(id="ord-1", filled_avg_price=None, status="new")

    def get_order_by_id(self, oid):
        return self._next

    def cancel_order_by_id(self, oid):
        self.cancelled.append(oid)


def _broker(monkeypatch, *, dry_run, fake=None):
    fake = fake or FakeTradingClient()
    monkeypatch.setattr(broker_mod, "TradingClient", lambda *a, **k: fake, raising=False)
    # AlpacaPaperBroker imports TradingClient inside __init__; patch the source module.
    import alpaca.trading.client as tc
    monkeypatch.setattr(tc, "TradingClient", lambda *a, **k: fake)
    b = AlpacaPaperBroker("k", "s", dry_run=dry_run, equity=100000.0)
    return b, fake


def test_paperbroker_sim_fill():
    b = PaperBroker(100000.0)
    f = b.submit_paper(contract_symbol="FCX270319C00080000", qty=1, side="buy", limit_price=7.58)
    assert f.filled and f.price == 7.58 and f.qty == 1 and not f.pending


def test_dry_run_logs_not_sends(monkeypatch):
    b, fake = _broker(monkeypatch, dry_run=True)
    f = b.submit_paper(contract_symbol="FCX270319C00080000", qty=2, side="buy", limit_price=7.581)
    assert f.filled and not f.pending
    assert f.price == 7.58  # rounded to cents
    assert fake.submitted == []  # nothing transmitted
    assert "DRY_RUN" in f.note


def test_live_submit_builds_limit_order(monkeypatch):
    fake = FakeTradingClient()
    fake._next = SimpleNamespace(id="ord-9", filled_avg_price=None, status="new")
    b, fake = _broker(monkeypatch, dry_run=False, fake=fake)
    f = b.submit_paper(contract_symbol="FCX270319C00080000", qty=3, side="buy", limit_price=7.58)
    assert len(fake.submitted) == 1
    req = fake.submitted[0]
    assert req.symbol == "FCX270319C00080000"
    assert int(req.qty) == 3
    assert abs(float(req.limit_price) - 7.58) < 1e-6  # rounded to cents (float repr)
    # resting (no immediate fill) → pending with order id
    assert f.filled and f.pending and f.order_id == "ord-9"


def test_live_immediate_fill(monkeypatch):
    fake = FakeTradingClient()
    fake._next = SimpleNamespace(id="ord-3", filled_avg_price="7.60", status="filled")
    b, fake = _broker(monkeypatch, dry_run=False, fake=fake)
    f = b.submit_paper(contract_symbol="FCX270319C00080000", qty=1, side="buy", limit_price=7.58)
    assert f.filled and not f.pending and f.price == 7.60 and f.order_id == "ord-3"


def test_api_error_fails_closed(monkeypatch):
    fake = FakeTradingClient()
    fake._raise = True
    b, fake = _broker(monkeypatch, dry_run=False, fake=fake)
    f = b.submit_paper(contract_symbol="FCX270319C00080000", qty=1, side="buy", limit_price=7.58)
    assert f.filled is False and f.qty == 0
    assert "FAILED" in f.note


def test_rejects_bad_qty_or_price(monkeypatch):
    b, _ = _broker(monkeypatch, dry_run=True)
    assert b.submit_paper(contract_symbol="X", qty=0, side="buy", limit_price=1.0).filled is False
    assert b.submit_paper(contract_symbol="X", qty=1, side="buy", limit_price=0.0).filled is False


def test_sell_to_close_side_intent_and_client_order_id(monkeypatch):
    from alpaca.trading.enums import OrderSide, PositionIntent

    b, fake = _broker(monkeypatch, dry_run=False)
    coid = "close-FCX270319C00080000-2026-06-01"
    b.submit_paper(contract_symbol="FCX270319C00080000", qty=2, side="sell",
                   limit_price=12.0, client_order_id=coid)
    req = fake.submitted[0]
    assert req.side == OrderSide.SELL
    assert req.position_intent == PositionIntent.SELL_TO_CLOSE
    assert req.client_order_id == coid


def test_make_client_order_id_stable_and_sanitized():
    from broker import make_client_order_id

    a = make_client_order_id("open", "FCX270319C00080000", "2026-06-01")
    assert a == make_client_order_id("open", "FCX270319C00080000", "2026-06-01")  # idempotent
    assert a == "open-FCX270319C00080000-2026-06-01" and a.startswith("open-")
    # open vs close differ → an open + a close on the same contract/day never collide
    assert make_client_order_id("close", "FCX270319C00080000", "2026-06-01") != a


def test_order_status_and_cancel(monkeypatch):
    fake = FakeTradingClient()
    fake._next = SimpleNamespace(status="filled", filled_avg_price="7.60", filled_qty="1", id="o")
    b, fake = _broker(monkeypatch, dry_run=False, fake=fake)
    st = b.order_status("o")
    assert st["state"] == "filled" and st["filled_avg_price"] == "7.60"
    b.cancel_order("o")
    assert fake.cancelled == ["o"]


def test_order_status_maps_enum_value_not_repr(monkeypatch):
    """Regression (live-only bug, 2026-06-09): alpaca-py returns an ``OrderStatus`` *enum*
    whose ``str()`` is "OrderStatus.FILLED", NOT "filled". ``order_status`` must emit the
    lowercase enum VALUE — monitor.reconcile_pending / _reconcile_closing compare
    ``state == "filled"`` / ``state in ("canceled", …)``, and "orderstatus.filled" matches
    none of them, silently stranding every real filled order as 'pending'. The other test
    feeds a plain "filled" string, so ``str()`` is a no-op and the enum bug stays invisible —
    this one grounds against the real enum. Caught by the first live fill→close round-trip.
    """
    from alpaca.trading.enums import OrderStatus

    b, fake = _broker(monkeypatch, dry_run=False)
    fake._next = SimpleNamespace(status=OrderStatus.FILLED, filled_avg_price="9.39", filled_qty="1", id="o")
    assert b.order_status("o")["state"] == "filled"
    fake._next = SimpleNamespace(status=OrderStatus.CANCELED, filled_avg_price=None, filled_qty="0", id="o2")
    assert b.order_status("o2")["state"] == "canceled"


def test_fill_dataclass_defaults():
    f = Fill(True, 1.0, 1, "n")
    assert f.order_id is None and f.pending is False


# ── AlpacaLiveBroker (the T4 real-money path — PREREG_REAL_MONEY_BROKER) ───────────────────────────
def _live_broker(monkeypatch, *, dry_run, max_order_notional, fake=None):
    fake = fake or FakeTradingClient()
    captured = {}

    def _mk(*a, **k):
        captured["paper"] = k.get("paper")
        return fake

    import alpaca.trading.client as tc
    monkeypatch.setattr(tc, "TradingClient", _mk)
    monkeypatch.setattr(broker_mod, "TradingClient", _mk, raising=False)
    b = AlpacaLiveBroker("k", "s", dry_run=dry_run, equity=100000.0, max_order_notional=max_order_notional)
    return b, fake, captured


def test_endpoint_paper_vs_real_money():
    # The endpoint is fixed per class — a PaperBroker can NEVER transmit real money.
    assert AlpacaPaperBroker._paper is True
    assert AlpacaLiveBroker._paper is False


def test_live_broker_targets_real_money_endpoint(monkeypatch):
    _, _, cap = _live_broker(monkeypatch, dry_run=True, max_order_notional=100000.0)
    assert cap["paper"] is False  # TradingClient built for the REAL-MONEY endpoint


def test_live_ceiling_allows_under_notional(monkeypatch):
    b, fake, _ = _live_broker(monkeypatch, dry_run=False, max_order_notional=5000.0)
    f = b.submit_paper(contract_symbol="FCX270319C00080000", qty=2, side="buy", limit_price=10.0)  # 2*10*100=2000
    assert f.filled and len(fake.submitted) == 1  # under the $5000 ceiling → transmitted
    assert "LIVE — REAL MONEY" in f.note


def test_live_ceiling_rejects_over_notional(monkeypatch):
    b, fake, _ = _live_broker(monkeypatch, dry_run=False, max_order_notional=1000.0)
    f = b.submit_paper(contract_symbol="FCX270319C00080000", qty=2, side="buy", limit_price=10.0)  # 2000 > 1000
    assert f.filled is False and f.qty == 0 and "exceeds" in f.note
    assert fake.submitted == []  # fail-closed: nothing transmitted


def test_live_absent_ceiling_rejects_fail_closed(monkeypatch):
    b, fake, _ = _live_broker(monkeypatch, dry_run=False, max_order_notional=None)
    f = b.submit_paper(contract_symbol="X", qty=1, side="buy", limit_price=1.0)
    assert f.filled is False and "no safety.live_max_order_notional" in f.note
    assert fake.submitted == []  # an unconfigured live broker transmits nothing


def test_live_ceiling_rejects_even_under_dry_run(monkeypatch):
    # The ceiling is checked BEFORE the DRY_RUN branch — a breach surfaces even in simulation.
    b, _, _ = _live_broker(monkeypatch, dry_run=True, max_order_notional=1000.0)
    f = b.submit_paper(contract_symbol="X", qty=2, side="buy", limit_price=10.0)  # 2000 > 1000
    assert f.filled is False and "exceeds" in f.note


def test_live_dry_run_simulates_under_ceiling(monkeypatch):
    b, fake, _ = _live_broker(monkeypatch, dry_run=True, max_order_notional=5000.0)
    f = b.submit_paper(contract_symbol="FCX270319C00080000", qty=1, side="buy", limit_price=10.0)
    assert f.filled and "DRY_RUN" in f.note and "[LIVE — REAL MONEY]" in f.note
    assert fake.submitted == []  # DRY_RUN → nothing transmitted


def test_select_broker_gates_real_money(monkeypatch):
    # The orchestrator picks AlpacaLiveBroker ONLY when is_live (the triple-gate); else the paper broker.
    import orchestrator
    fake = FakeTradingClient()
    import alpaca.trading.client as tc
    monkeypatch.setattr(tc, "TradingClient", lambda *a, **k: fake)
    monkeypatch.setattr(broker_mod, "TradingClient", lambda *a, **k: fake, raising=False)

    live = orchestrator._select_broker({"safety": {"live_max_order_notional": 1500.0}}, is_live=True,
                                       api_key="k", secret_key="s", dry_run=True, equity=100000.0)
    assert isinstance(live, AlpacaLiveBroker) and live._max_order_notional == 1500.0

    paper = orchestrator._select_broker({}, is_live=False, api_key="k", secret_key="s",
                                        dry_run=True, equity=100000.0)
    assert isinstance(paper, AlpacaPaperBroker) and not isinstance(paper, AlpacaLiveBroker)
