#!/usr/bin/env python3
"""Exit fire drill (#466): every exit path, end to end, on the Alpaca PAPER endpoint. OUT OF BAND.

No real position has ever been closed by the system. This drill buys ONE short-dated, liquid, cheap option per path
on the paper account, records it in a SCRATCH journal through the real ``state`` writers, and runs the real
``monitor.monitor_positions`` (wired through ``orchestrator.monitor_mode``, exactly as the L2 tick wires it) with
drill-local thresholds so each exit path fires in turn. Every step prints a block, the venue's view beside the
journal's, that pastes straight into the dated record.

Safety (all fail-closed; each refusal exits 2 and places nothing):
  * Without ``--send`` a step is a PLAN: it runs against an in-memory copy of the scratch DB (discarded) and the
    drill broker answers every order with a simulated fill; nothing reaches the venue. The inner Alpaca broker is
    also built with ``dry_run=True`` (the repo's own DRY_RUN gate), a second, independent layer.
  * Paper endpoint only: the broker is the paper class and its trading URL must be paper-api.alpaca.markets.
  * Any ``ALPACA_LIVE_*`` key, ``LIVE_TRADING_ENABLED=true`` or ``PAPER=false`` in the environment refuses (checked
    before and after ``config_loader.load_config`` reads ``.env``); so does a KILL switch for any step that trades.
  * Scratch journal only: ``--db`` (or a temp file) must not resolve to the production journal (``config.json``
    ``database.path`` from the CWD, the repo or the main checkout, or ``$DRAMATIC_DB``), must not share its file
    name, and an existing file must hold only drill rows (no ``runs``, no untagged positions). One DB per path.
  * The drill broker only trades the drill's own contract, qty 1, a buy at most ``--budget``; every client order
    id is rewritten to ``do-drill-<path tag>-...``. Pages (``notify.send``) are suppressed for the run.
  * Shared-account rule (tests/test_shared_account.py, PREREG_REAL_MONEY_BROKER §3a): the venue is read per
    contract (``broker.venue_quantity``) and per order id (``broker.order_status``), never by listing the account.
    Nothing here cancels an order: a resting drill order is left to its DAY expiry (or cancelled by hand).
  * ``config.json`` is never edited: the thresholds come from a deep copy of the loaded config.

Paths (``--path``) and steps (``--step open|tick|observe|flatten|record``):
  profit-take    profit_take_multiple 0.01 → SELL_TO_CLOSE at the bid → reconcile to closed.
  time-stop      the real time_stop_dte (21) on a ≤7-DTE contract → SELL_TO_CLOSE → closed.
  unsellable     min_close_bid above any bid → the in-DB ``_unsellable`` close, nothing sent; observe shows the venue
                 still holds the contract (#444's shape). Then ``flatten`` it, or let it ride to expiry and observe.
  resting-close  the first tick's sell limit is the ask × ``--rest-markup`` so it rests through the session close
                 (#449's shape); the next session's tick reconciles the expired order (reopen) and re-sells at the bid.
                 A 1-lot cannot partly fill, so this rehearses the expired-unfilled branch, not #449's partial one.
  pre-market     a closed-market tick → ``orchestrator.monitor_mode(dry_run=False, market_open=False, demo=False)``
                 = (True, True): the time-stop must be DEFERRED, row open, nothing sent (#451's shape); the next
                 open-market tick sells it.
  expiry-otm     hold through expiry (no profit-take, no time-stop); tick + observe daily; record what the venue
  expiry-itm     shows (contract gone? exercised into shares?) and when, beside the journal's intrinsic close.

DEV run order (operator's word first; ~2 weeks; from the LIVE checkout so ``.env`` is the paper one). Run each
command once without ``--send`` to read the plan, then again with ``--send``. Append every block to the record with
``--out``. The two shell variables below shorten the lines. Paths that are open at the same time need different
contracts (the pre-open venue check refuses a contract the venue already holds), hence the different symbols.

  cd ~/dramatic_options && mkdir -p ~/drill466
  D=~/drill466; R="--out $D/record.md"
  # Week 1, Mon, in session (after 10:00 ET). Pick: a liquid ≤7-DTE call (F, SOFI, BAC, INTC, PLTR ...).
  python scripts/drill_exit_paths.py --path profit-take --db $D/profit-take.db --step open --pick --symbol F
  python scripts/drill_exit_paths.py --path profit-take --db $D/profit-take.db --step open --pick --symbol F --send $R
  python scripts/drill_exit_paths.py --path profit-take --db $D/profit-take.db --step tick --send $R
  python scripts/drill_exit_paths.py --path profit-take --db $D/profit-take.db --step observe $R
  python scripts/drill_exit_paths.py --path time-stop   --db $D/time-stop.db   --step open --pick --symbol F --send $R
  python scripts/drill_exit_paths.py --path time-stop   --db $D/time-stop.db   --step tick --send $R
  python scripts/drill_exit_paths.py --path time-stop   --db $D/time-stop.db   --step observe $R
  python scripts/drill_exit_paths.py --path unsellable  --db $D/unsellable.db  --step open --pick --symbol F --send $R
  python scripts/drill_exit_paths.py --path unsellable  --db $D/unsellable.db  --step tick --send $R
  python scripts/drill_exit_paths.py --path unsellable  --db $D/unsellable.db  --step observe $R   # venue still 1
  python scripts/drill_exit_paths.py --path unsellable  --db $D/unsellable.db  --step flatten --send $R
  python scripts/drill_exit_paths.py --path pre-market  --db $D/pre-market.db  --step open --pick --symbol SOFI --send $R
  python scripts/drill_exit_paths.py --path resting-close --db $D/resting.db   --step open --pick --symbol BAC --send $R
  python scripts/drill_exit_paths.py --path resting-close --db $D/resting.db   --step tick --send $R  # rests
  # Week 1, Tue
  python scripts/drill_exit_paths.py --path pre-market  --db $D/pre-market.db  --step tick --send $R  # 08:45-09:25 ET
  python scripts/drill_exit_paths.py --path pre-market  --db $D/pre-market.db  --step tick --send $R  # after 09:35 ET
  python scripts/drill_exit_paths.py --path pre-market  --db $D/pre-market.db  --step observe $R
  python scripts/drill_exit_paths.py --path resting-close --db $D/resting.db   --step observe $R      # order expired
  python scripts/drill_exit_paths.py --path resting-close --db $D/resting.db   --step tick --send $R  # reopen+resell
  python scripts/drill_exit_paths.py --path resting-close --db $D/resting.db   --step observe $R
  # Week 2, Mon-Wed: contracts expiring that Friday (a call ~5-10% OTM; a call ~5-10% ITM on a cheap name).
  python scripts/drill_exit_paths.py --path expiry-otm --db $D/expiry-otm.db --step open --pick --symbol F --send $R
  python scripts/drill_exit_paths.py --path expiry-itm --db $D/expiry-itm.db --step open --pick --symbol SOFI \
      --moneyness itm --send $R
  # Every day until the venue settles (Fri after 16:00 ET, Sat, Mon, Tue): for each of the two DBs
  python scripts/drill_exit_paths.py --path expiry-otm --db $D/expiry-otm.db --step tick --send $R
  python scripts/drill_exit_paths.py --path expiry-otm --db $D/expiry-otm.db --step observe $R
  #   (the same two for expiry-itm; then flatten any exercised paper shares BY HAND in the Alpaca paper dashboard)
  # Compose the dated record (records/YYYY-MM-DD_exit_fire_drill.md) from each DB's log:
  python scripts/drill_exit_paths.py --path profit-take --db $D/profit-take.db --step record

The real DEV loop keeps running beside the drill on the same paper account: its journal never holds a drill row,
the drill never touches a real-book contract (the pre-open venue check refuses a contract the venue already holds),
and the real book holds only long-dated contracts.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import json
import logging
import os
import re
import sqlite3
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from broker import (  # noqa: E402
    CLIENT_ORDER_ID_PREFIX,
    AlpacaPaperBroker,
    Fill,
    make_client_order_id,
    shared_account_reject,
)

ET = ZoneInfo("America/New_York")
CONTRACT_MULTIPLIER = 100
DRILL_PREFIX = CLIENT_ORDER_ID_PREFIX + "drill-"        # "do-drill-": still the project's own prefix (#279)
PAPER_TRADING_URL = "https://paper-api.alpaca.markets"
NEVER = 1e9                                             # a profit-take multiple no mark reaches
TERMINAL = ("filled", "canceled", "cancelled", "expired", "rejected")
log = logging.getLogger("drill")


@dataclass(frozen=True)
class PathSpec:
    tag: str            # in every client order id: do-drill-<tag>-...
    exits: dict         # overrides on the drill-local copy of convexity_exits
    issue: str          # what the path rehearses


PATHS: dict[str, PathSpec] = {
    "profit-take": PathSpec("pt", {"profit_take_multiple": 0.01, "time_stop_dte": -1},
                            "profit-take → SELL_TO_CLOSE → reconcile"),
    "time-stop": PathSpec("ts", {"profit_take_multiple": NEVER}, "time-stop → SELL_TO_CLOSE → reconcile"),
    "unsellable": PathSpec("us", {"profit_take_multiple": NEVER, "min_close_bid": 1e6},
                           "time-stop with the bid under min_close_bid → in-DB close, venue still holds it (#444)"),
    "resting-close": PathSpec("rc", {"profit_take_multiple": NEVER},
                              "a SELL_TO_CLOSE left resting through the session close → reconcile next session (#449)"),
    "pre-market": PathSpec("pm", {"profit_take_multiple": NEVER},
                           "a closed-market tick defers the time-stop; the next open tick sells it (#451)"),
    "expiry-otm": PathSpec("eo", {"profit_take_multiple": NEVER, "time_stop_dte": -1},
                           "hold an OTM contract through expiry; the venue's view day by day (#444)"),
    "expiry-itm": PathSpec("ei", {"profit_take_multiple": NEVER, "time_stop_dte": -1},
                           "hold an ITM contract through expiry; exercise into shares? (#444)"),
}
TRADING_STEPS = ("open", "tick", "flatten")


class Refused(Exception):
    """A fail-closed refusal: nothing was placed."""


# ── guards ───────────────────────────────────────────────────────────────────────────────────────

def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def live_env_refusal(environ=None) -> str | None:
    """Refuse when anything live-shaped is loaded: an ALPACA_LIVE_* key, LIVE_TRADING_ENABLED true, PAPER false."""
    environ = os.environ if environ is None else environ
    live = sorted(k for k in environ if k.upper().startswith("ALPACA_LIVE_"))
    if live:
        return (f"REFUSED: {', '.join(live)} set in the environment; the drill runs only where no live key is "
                "loaded (fail-closed).")
    if _truthy(environ.get("LIVE_TRADING_ENABLED", "")):
        return "REFUSED: LIVE_TRADING_ENABLED is true in the environment (fail-closed)."
    if environ.get("PAPER") not in (None, "") and not _truthy(environ.get("PAPER")):
        return "REFUSED: PAPER is false in the environment (fail-closed)."
    return None


def config_refusal(config: dict) -> str | None:
    safety = config.get("safety", {})
    if safety.get("paper") is not True:
        return "REFUSED: config safety.paper is not true (fail-closed)."
    if safety.get("live_trading_enabled") is True:
        return "REFUSED: config safety.live_trading_enabled is true (fail-closed)."
    return None


def production_db_paths(config: dict, environ=None) -> set[Path]:
    """Every path the production journal can resolve to."""
    environ = os.environ if environ is None else environ
    rel = Path(config.get("database", {}).get("path", "data/dramatic_options.db")).expanduser()
    roots = {Path.cwd(), REPO}
    try:
        from scripts._live_env import main_checkout
        roots.add(main_checkout(REPO))
    except Exception:  # noqa: BLE001 — the CWD and repo candidates still apply
        pass
    out: set[Path] = set()
    for r in roots:
        for p in (rel, Path("data/dramatic_options.db")):
            out.add((p if p.is_absolute() else r / p).resolve())
    if environ.get("DRAMATIC_DB"):
        out.add(Path(environ["DRAMATIC_DB"]).expanduser().resolve())
    return out


def db_refusal(db_path: Path, config: dict, environ=None) -> str | None:
    """None iff ``db_path`` is safe to use as a drill scratch journal."""
    p = Path(db_path).expanduser().resolve()
    prod_name = Path(config.get("database", {}).get("path", "data/dramatic_options.db")).name
    for c in production_db_paths(config, environ):
        same = p == c
        if not same and p.exists() and c.exists():
            with contextlib.suppress(OSError):
                same = os.path.samefile(p, c)
        if same:
            return f"REFUSED: --db {p} is the production journal (fail-closed)."
    if p.name in (prod_name, "dramatic_options.db"):
        return f"REFUSED: --db {p} has the production journal's file name; use a scratch name (fail-closed)."
    if p.exists():
        try:
            conn = sqlite3.connect(str(p))
            try:
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "runs" in tables and conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]:
                    return f"REFUSED: --db {p} holds loop runs; it is not a drill scratch DB (fail-closed)."
                if "convexity_positions" in tables:
                    for (rat,) in conn.execute("SELECT rationale FROM convexity_positions"):
                        if not _is_drill_rationale(rat):
                            return (f"REFUSED: --db {p} holds a position that is not a drill row; it is not a "
                                    "drill scratch DB (fail-closed).")
            finally:
                conn.close()
        except sqlite3.Error as e:
            return f"REFUSED: --db {p} cannot be verified as a scratch DB ({e}) (fail-closed)."
    return None


def _is_drill_rationale(raw) -> bool:
    try:
        d = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return False
    return isinstance(d, dict) and d.get("drill") is True


def endpoint_refusal(broker) -> str | None:
    """The broker must be the paper class, pointed at the paper trading URL."""
    if not isinstance(broker, AlpacaPaperBroker) or getattr(broker, "_paper", None) is not True:
        return "REFUSED: the drill broker is not the Alpaca paper broker (fail-closed)."
    url = getattr(getattr(broker, "_trading", None), "_base_url", None)
    url = str(getattr(url, "value", url) or "")
    if url.rstrip("/") != PAPER_TRADING_URL:
        return f"REFUSED: the trading endpoint is {url or 'unknown'!r}, not {PAPER_TRADING_URL} (fail-closed)."
    return None


# ── the drill broker ─────────────────────────────────────────────────────────────────────────────

def drill_order_id(client_order_id: str | None, *, tag: str, fallback: str) -> str:
    """``do-close-X-date`` → ``do-drill-<tag>-close-X-date`` (Alpaca's id charset, ≤128)."""
    raw = client_order_id or fallback
    if not raw.startswith(DRILL_PREFIX):
        if raw.startswith(CLIENT_ORDER_ID_PREFIX):
            raw = raw[len(CLIENT_ORDER_ID_PREFIX):]
        raw = f"{DRILL_PREFIX}{tag}-{raw}"
    return re.sub(r"[^A-Za-z0-9._-]", "", raw)[:128]


class DrillBroker(AlpacaPaperBroker):
    """The paper broker with the drill's limits on top. Without ``send`` nothing reaches the parent's submit.

    Inherits the paper endpoint, the shared-account guard, ``venue_quantity`` (one contract) and ``order_status``
    (one order id). Every client order id is rewritten to ``do-drill-<tag>-...``; only the drill contract trades,
    qty ≤ ``max_qty``, a buy's premium ≤ ``budget``."""

    def __init__(self, api_key: str, secret_key: str, *, send: bool, tag: str, contract: str | None,
                 budget: float, max_qty: int = 1) -> None:
        super().__init__(api_key, secret_key, dry_run=not send)
        self._send = bool(send)
        self.tag, self.contract, self.budget, self.max_qty = tag, contract, float(budget), int(max_qty)
        self.intents: list[dict] = []

    def submit_paper(self, *, contract_symbol: str, qty: int, side: str, limit_price: float,
                     client_order_id: str | None = None) -> Fill:
        coid = drill_order_id(client_order_id, tag=self.tag,
                              fallback=f"{side}-{contract_symbol}-{datetime.now(UTC).date()}")
        intent = {"side": side, "contract": contract_symbol, "qty": int(qty), "limit": round(float(limit_price), 2),
                  "client_order_id": coid, "sent": False}
        self.intents.append(intent)
        why = None
        if self.contract is None or contract_symbol != self.contract:
            why = f"not the drill contract ({self.contract})"
        elif int(qty) < 1 or int(qty) > self.max_qty:
            why = f"qty {qty} outside 1..{self.max_qty}"
        elif str(side).lower() == "buy" and float(limit_price) * CONTRACT_MULTIPLIER * int(qty) > self.budget:
            why = f"premium ${float(limit_price) * CONTRACT_MULTIPLIER * int(qty):,.0f} > budget ${self.budget:,.0f}"
        if why:
            intent["note"] = f"REFUSED by the drill broker: {why}"
            return Fill(False, 0.0, 0, intent["note"])
        if not self._send:   # the --send guard: a plan never reaches the parent's submit
            intent["note"] = (f"PLAN (not sent): {side} {qty}x {contract_symbol} LIMIT {intent['limit']:.2f} "
                              f"id {coid}")
            return Fill(True, intent["limit"], int(qty), intent["note"])
        fill = super().submit_paper(contract_symbol=contract_symbol, qty=qty, side=side, limit_price=limit_price,
                                    client_order_id=coid)
        intent.update(sent=True, note=fill.note, order_id=fill.order_id, filled=fill.filled, pending=fill.pending)
        return fill


def make_drill_broker(api_key: str, secret_key: str, *, send: bool, tag: str, contract: str | None,
                      budget: float) -> DrillBroker:
    b = DrillBroker(api_key, secret_key, send=send, tag=tag, contract=contract, budget=budget)
    why = endpoint_refusal(b)
    if why:
        raise Refused(why)
    return b


# ── market (quotes, prices, chain, clock) ───────────────────────────────────────────────────────

class AlpacaMarket:
    """Read-only market data over the repo's own providers (the L2 monitor's quote feed)."""

    def __init__(self, config: dict, api_key: str, secret_key: str) -> None:
        from clock import LiveClock
        from convexity_data import AlpacaChainProvider
        from data.alpaca_client import AlpacaClient
        from feeds import to_equity_feed, to_option_feed

        df = config.get("data_feed", {})
        self._client = AlpacaClient(api_key, secret_key, paper=True)
        self._provider = AlpacaChainProvider(self._client, equity_feed=to_equity_feed(df.get("equity_bars", "iex")),
                                             option_feed=to_option_feed(df.get("option_gate", "indicative")))
        self._monitor_feed = to_option_feed(df.get("option_monitor", "indicative"))
        self.clock = LiveClock(self._client)

    def quotes(self):
        from convexity_data import AlpacaQuoteProvider
        return AlpacaQuoteProvider(self._client, option_feed=self._monitor_feed)

    def underlying_price(self, symbol: str) -> float | None:
        return self._provider.underlying_price(symbol)

    def chain(self, symbol: str) -> list:
        return self._provider.chain(symbol)


class RestingQuotes:
    """resting-close's first tick: marks are honest; the sell limit (the monitor's "bid") is the ask × markup, so the
    DAY SELL_TO_CLOSE rests unfilled through the session close."""

    def __init__(self, inner, markup: float) -> None:
        self._inner, self._markup = inner, float(markup)

    def option_mid(self, s):
        return self._inner.option_mid(s)

    def option_bid(self, s):
        mid, bid = self._inner.option_mid(s), self._inner.option_bid(s)
        if mid is None or bid is None:
            return None
        return round(max(2.0 * float(mid) - float(bid), 0.05) * self._markup, 2)


def _ask(quotes, contract: str) -> float | None:
    mid, bid = quotes.option_mid(contract), quotes.option_bid(contract)
    if mid is None or bid is None:
        return None
    return round(2.0 * float(mid) - float(bid), 2)


def pick_short_dated(chain, *, underlying_price: float, today: date, max_dte: int, budget: float,
                     moneyness: str = "otm", min_bid: float = 0.05, max_spread_pct: float = 0.30):
    """The drill contract: a CALL expiring in 1..max_dte days, a real bid, a sane spread, ask×100 ≤ budget; OTM
    0-15% (``otm``) or ITM 2-15% (``itm``). Nearest expiry, then tightest spread, then cheapest. None = fail-closed."""
    best, best_key = None, None
    for c in chain:
        if str(getattr(c, "kind", "")) not in ("C", "call", "CALL"):
            continue
        exp = getattr(c, "expiry", None)
        if not isinstance(exp, date):
            continue
        dte = (exp - today).days
        if not 1 <= dte <= max_dte:
            continue
        bid, ask = float(getattr(c, "bid", 0) or 0), float(getattr(c, "ask", 0) or 0)
        if bid < min_bid or ask <= 0 or ask < bid:
            continue
        mid = (bid + ask) / 2
        spread = (ask - bid) / mid
        if spread > max_spread_pct or ask * CONTRACT_MULTIPLIER > budget:
            continue
        m = (float(c.strike) - underlying_price) / underlying_price
        if moneyness == "otm" and not 0.0 < m <= 0.15:
            continue
        if moneyness == "itm" and not -0.15 <= m <= -0.02:
            continue
        key = (dte, spread, ask)
        if best_key is None or key < best_key:
            best, best_key = c, key
    return best


# ── scratch journal ──────────────────────────────────────────────────────────────────────────────

_DRILL_TABLES = (
    "CREATE TABLE IF NOT EXISTS drill_meta (key TEXT PRIMARY KEY, value TEXT)",
    "CREATE TABLE IF NOT EXISTS drill_orders (id INTEGER PRIMARY KEY, at TEXT, side TEXT, contract_symbol TEXT, "
    "qty INTEGER, limit_price REAL, client_order_id TEXT, order_id TEXT, note TEXT)",
    "CREATE TABLE IF NOT EXISTS drill_log (id INTEGER PRIMARY KEY, at TEXT, step TEXT, sent INTEGER, rc INTEGER, "
    "block TEXT)",
)


def open_scratch(db_path: Path) -> sqlite3.Connection:
    import orchestrator
    import state

    conn = state.connect(db_path)
    orchestrator._ensure_schema(conn)     # the repo's real migrations
    with conn:
        for ddl in _DRILL_TABLES:
            conn.execute(ddl)
    return conn


def plan_copy(conn: sqlite3.Connection) -> sqlite3.Connection:
    mem = sqlite3.connect(":memory:")
    conn.backup(mem)
    mem.row_factory = sqlite3.Row
    return mem


def meta_get(conn, key: str) -> str | None:
    r = conn.execute("SELECT value FROM drill_meta WHERE key = ?", (key,)).fetchone()
    return None if r is None else r[0]


def meta_set(conn, key: str, value) -> None:
    with conn:
        conn.execute("INSERT OR REPLACE INTO drill_meta (key, value) VALUES (?, ?)", (key, str(value)))


def drill_rows(conn) -> list:
    return [r for r in conn.execute("SELECT * FROM convexity_positions ORDER BY id") if _is_drill_rationale(r["rationale"])]


# ── one step ─────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Ctx:
    path: str
    step: str
    conn: sqlite3.Connection
    broker: DrillBroker
    market: object
    config: dict
    send: bool
    db_path: Path
    contract: str | None
    limit: float | None
    budget: float
    rest_markup: float = 2.0
    poll_s: float = 90.0
    sleep: object = time.sleep
    lines: list = field(default_factory=list)
    logs: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    monitor_lines: list = field(default_factory=list)

    @property
    def spec(self) -> PathSpec:
        return PATHS[self.path]

    def check(self, ok: bool, what: str) -> None:
        self.checks.append((bool(ok), what))


def drill_config(base: dict, path: str, *, multiple: float | None = None) -> dict:
    """A deep copy of the loaded config with the path's thresholds; the real config.json is never edited."""
    cfg = copy.deepcopy(base)
    real = dict(cfg.get("convexity_exits", {}))
    exits = {"profit_take_multiple": float(real.get("profit_take_multiple", 10.0)),
             "time_stop_dte": int(real.get("time_stop_dte", 21)),
             "min_close_bid": float(real.get("min_close_bid", 0.05))}
    exits.update(PATHS[path].exits)
    if multiple is not None and path == "profit-take":
        exits["profit_take_multiple"] = float(multiple)
    cfg["convexity_exits"] = exits
    ex = cfg.setdefault("execution", {})
    ex["cancel_unfilled"] = False      # a resting drill order is never cancelled by the drill
    ex["carry_unfilled"] = False
    return cfg


def _now(ctx) -> datetime:
    return ctx.market.clock.now()


def _market_open(ctx) -> bool:
    try:
        return bool(ctx.market.clock.is_market_open())
    except Exception as e:  # noqa: BLE001 — unknown ⇒ closed, as orchestrator._safe_market_open
        ctx.logs.append(f"market-state check failed ({e}); treated as CLOSED")
        return False


def _monitor(ctx, quotes, *, dry_run: bool, mark_only: bool):
    import monitor

    res = monitor.monitor_positions(conn=ctx.conn, clock=ctx.market.clock, quote_provider=quotes, config=ctx.config,
                                    underlying_price_of=ctx.market.underlying_price, broker=ctx.broker,
                                    dry_run=dry_run, mark_only=mark_only)
    ctx.monitor_lines.append(
        f"marked={res.marked} closed={res.closed} closing={res.closing} profit_taken={res.profit_taken} "
        f"time_stopped={res.time_stopped} expired={res.expired} deferred={res.deferred} unmarked={res.unmarked} "
        f"realized=${res.realized_pnl:,.2f}")
    return res


def _record_intents(ctx, start: int) -> None:
    at = _now(ctx).isoformat()
    with ctx.conn:
        for it in ctx.broker.intents[start:]:
            ctx.conn.execute(
                "INSERT INTO drill_orders (at, side, contract_symbol, qty, limit_price, client_order_id, order_id, "
                "note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (at, it["side"], it["contract"], it["qty"], it["limit"], it["client_order_id"], it.get("order_id"),
                 it.get("note")))


def _live_rows(ctx) -> list:
    return [r for r in drill_rows(ctx.conn) if r["status"] in ("pending", "open", "closing")]


def step_open(ctx) -> int:
    import monitor
    import state
    from options_tradability import parse_osi

    rows = drill_rows(ctx.conn)
    if any(r["status"] == "pending" for r in rows):       # a resting entry from an earlier run: reconcile only
        ctx.lines.append("entry still pending from an earlier run: reconciling it (no new order)")
        monitor.reconcile_pending(conn=ctx.conn, broker=ctx.broker, clock=ctx.market.clock, config=ctx.config)
        return 0
    if rows:
        raise Refused(f"this scratch DB already holds the {ctx.path} drill position (#{rows[0]['id']}, "
                      f"{rows[0]['status']}); use --step tick / observe, or a fresh --db")
    c = ctx.contract
    info = parse_osi(c or "")
    if info is None:
        raise Refused(f"not an OCC option symbol: {c!r}")
    why = shared_account_reject(c, is_buy=True) or shared_account_reject(c, is_buy=False)
    if why:
        raise Refused(f"REFUSED: {why}")
    now = _now(ctx)
    today = now.astimezone(ET).date()
    dte = (info["expiry"] - today).days
    if not 1 <= dte <= ctx.config.get("_drill_max_dte", 7):
        raise Refused(f"{c} expires in {dte} days; the drill needs 1..{ctx.config.get('_drill_max_dte', 7)}")
    if ctx.path in ("time-stop", "unsellable", "resting-close", "pre-market") and \
            dte > int(ctx.config["convexity_exits"]["time_stop_dte"]):
        raise Refused(f"{c} at {dte} DTE would not trigger the time-stop ({ctx.config['convexity_exits']})")
    market_open = _market_open(ctx)
    if ctx.send and not market_open:
        raise Refused("the market is closed: open the drill position in session")
    quotes = ctx.market.quotes()
    limit = ctx.limit if ctx.limit is not None else _ask(quotes, c)
    if limit is None or limit <= 0:
        raise Refused(f"no quote for {c}; pass --limit")
    if limit * CONTRACT_MULTIPLIER > ctx.budget:
        raise Refused(f"REFUSED: limit {limit:.2f}×100 exceeds the drill budget ${ctx.budget:.0f}")
    venue_qty = ctx.broker.venue_quantity(c)
    journal_qty = state.journal_contract_quantity(ctx.conn, c)
    if venue_qty is None or venue_qty != journal_qty:
        raise Refused(f"REFUSED: the venue holds {venue_qty} of {c} but this drill journal explains {journal_qty} "
                      "(foreign-quantity check, fail-closed)")
    spot = None
    with contextlib.suppress(Exception):
        spot = ctx.market.underlying_price(info["root"])
    if ctx.path == "expiry-itm":
        shares = ctx.broker.venue_quantity(info["root"])
        if shares is None:
            raise Refused(f"the venue's {info['root']} share quantity is unreadable (fail-closed)")
        meta_set(ctx.conn, "shares_baseline", shares)
    start = len(ctx.broker.intents)
    fill = ctx.broker.submit_paper(contract_symbol=c, qty=1, side="buy", limit_price=limit,
                                   client_order_id=make_client_order_id("open", c, today.isoformat()))
    _record_intents(ctx, start)
    ctx.lines.append(f"BUY_TO_OPEN 1x {c} LIMIT {limit:.2f}: {fill.note}")
    if not fill.filled:
        ctx.check(False, "the drill entry was accepted")
        return 3
    pending = bool(getattr(fill, "pending", False))
    px = float(fill.price)
    pid = state.record_convexity_position(
        ctx.conn, run_id=None, opened_at=now.isoformat(), theme="drill-466", symbol=info["root"],
        direction="bullish" if info["kind"] == "C" else "bearish", structure_kind=info["kind"], contract_symbol=c,
        expiry=info["expiry"].isoformat(), strike=info["strike"], dte=dte,
        moneyness=(None if not spot else (info["strike"] - spot) / spot), contracts=1,
        entry_premium_per_contract=px * CONTRACT_MULTIPLIER, total_premium=px * CONTRACT_MULTIPLIER,
        rationale={"drill": True, "issue": 466, "path": ctx.path, "outside_frame": True},
        status="pending" if pending else "open", order_id=fill.order_id, entry_spot=spot)
    ctx.lines.append(f"recorded drill position #{pid} ({'pending' if pending else 'open'}) via state writers")
    deadline = time.monotonic() + ctx.poll_s
    while pending and time.monotonic() < deadline:
        ctx.sleep(3)
        monitor.reconcile_pending(conn=ctx.conn, broker=ctx.broker, clock=ctx.market.clock, config=ctx.config)
        pending = ctx.conn.execute("SELECT status FROM convexity_positions WHERE id = ?",
                                   (pid,)).fetchone()["status"] == "pending"
    st = ctx.conn.execute("SELECT status FROM convexity_positions WHERE id = ?", (pid,)).fetchone()["status"]
    ctx.check(st == "open", f"the entry filled and the journal holds it open (status {st})")
    if st == "pending":
        ctx.lines.append("entry still resting: rerun --step open to reconcile (the drill never cancels; a DAY order "
                         "expires at the close)")
    return 0 if st == "open" else 3


def step_tick(ctx) -> int:
    import orchestrator

    live = _live_rows(ctx)
    if not live:
        raise Refused("no open drill position in this scratch DB (run --step open first, or --step observe)")
    before = {r["id"]: r["status"] for r in live}
    market_open = _market_open(ctx)
    deferred_before = meta_get(ctx.conn, "deferred_at")
    if ctx.path == "pre-market" and deferred_before is None and market_open:
        raise Refused("the pre-market path's first tick must run with the market CLOSED (e.g. 08:45-09:25 ET)")
    dry, mark_only = orchestrator.monitor_mode(dry_run=False, market_open=market_open, demo=False)
    ctx.lines.append(f"market_open={market_open} → orchestrator.monitor_mode(dry_run=False, "
                     f"market_open={market_open}, demo=False) = (dry_run={dry}, mark_only={mark_only})")
    import monitor
    start = len(ctx.broker.intents)
    n = monitor.reconcile_pending(conn=ctx.conn, broker=ctx.broker, clock=ctx.market.clock, config=ctx.config)
    if n:
        ctx.lines.append(f"reconcile_pending settled {n} entry row(s)")
    resting_first = (ctx.path == "resting-close" and meta_get(ctx.conn, "rest_submitted_at") is None
                     and any(s == "open" for s in before.values()))
    quotes = ctx.market.quotes()
    if resting_first:
        quotes = RestingQuotes(quotes, ctx.rest_markup)
        ctx.lines.append(f"resting-close: sell limit = ask × {ctx.rest_markup:g}, so the DAY close rests")
    res = _monitor(ctx, quotes, dry_run=dry, mark_only=mark_only)
    deadline = time.monotonic() + ctx.poll_s
    while (not resting_first and not dry and any(r["status"] == "closing" for r in drill_rows(ctx.conn))
           and time.monotonic() < deadline):
        ctx.sleep(3)
        _monitor(ctx, ctx.market.quotes(), dry_run=dry, mark_only=mark_only)
    _record_intents(ctx, start)
    sent = list(ctx.broker.intents[start:])      # every order the monitor asked for this tick (sent or planned)
    for i in sent:
        ctx.lines.append(f"order `{i['client_order_id']}`: {i.get('note')}")
    after = {r["id"]: r for r in drill_rows(ctx.conn)}
    row = next(iter(after.values()))
    st, why = row["status"], row["exit_reason"] or ""
    p = ctx.path
    expired_today = date.fromisoformat(row["expiry"]) <= _now(ctx).date()
    if p == "pre-market" and not market_open:
        ctx.check((dry, mark_only) == (True, True), "monitor_mode on a closed market = (dry_run=True, mark_only=True)")
        ctx.check(res.deferred >= 1, f"the triggered time-stop was DEFERRED (deferred={res.deferred})")
        ctx.check(st == "open", f"the journal row stays open (status {st})")
        ctx.check(not sent, f"nothing was sent on the closed-market tick ({len(sent)} order(s))")
        if res.deferred >= 1 and st == "open" and not sent and ctx.send:
            meta_set(ctx.conn, "deferred_at", _now(ctx).isoformat())
    elif not market_open and not expired_today:
        ctx.lines.append("market closed: mark-only, exits deferred; rerun in session")
        ctx.check(not sent, f"nothing was sent on a closed-market tick ({len(sent)} order(s))")
    elif p in ("profit-take", "time-stop", "pre-market") or (p == "resting-close" and not resting_first):
        want = "profit_take_" if p == "profit-take" else "time_stop_"
        ctx.check(any(i["side"] == "sell" for i in sent) or st == "closing" or "reopen" in " ".join(ctx.logs),
                  f"a SELL_TO_CLOSE was submitted or is still working ({len(sent)} order(s) this tick)")
        ctx.check(st in ("closed", "closing"), f"the journal row is closed or closing (status {st}, reason {why})")
        if st == "closed":
            ctx.check(why.startswith(want) and not why.endswith("_unsellable"),
                      f"exit_reason {why!r} is the {want}… sell, not an in-DB close")
    elif p == "resting-close":
        ctx.check(st == "closing", f"the close is resting (status {st})")
        lim = next((i["limit"] for i in sent if i["side"] == "sell"), None)
        ctx.check(lim is not None, f"a SELL_TO_CLOSE above the market was submitted (limit {lim})")
        if st == "closing" and ctx.send:
            meta_set(ctx.conn, "rest_submitted_at", _now(ctx).isoformat())
    elif p == "unsellable":
        ctx.check(st == "closed" and why.endswith("_unsellable"), f"the in-DB unsellable close (status {st}, {why!r})")
        ctx.check(not sent, f"nothing was sent ({len(sent)} order(s))")
    elif p in ("expiry-otm", "expiry-itm"):
        if expired_today:
            ctx.check(st == "closed" and why == "expiry", f"booked at intrinsic on/after expiry (status {st}, {why!r})")
        else:
            ctx.check(st == "open", f"held through the tick (status {st}); no exit before expiry")
        ctx.check(not sent, f"nothing was sent ({len(sent)} order(s))")
    return 0


def step_flatten(ctx) -> int:
    import state

    rows = drill_rows(ctx.conn)
    if not rows:
        raise Refused("no drill position in this scratch DB")
    c = rows[0]["contract_symbol"]
    if _live_rows(ctx):
        raise Refused("the journal still holds the drill position: exit it with --step tick, not flatten")
    venue_qty = ctx.broker.venue_quantity(c)
    if venue_qty is None:
        raise Refused(f"the venue quantity of {c} is unreadable (fail-closed)")
    if venue_qty <= 0:
        raise Refused(f"the venue holds {venue_qty} of {c}: nothing to flatten")
    if ctx.send and not _market_open(ctx):
        raise Refused("the market is closed: flatten in session")
    qty = min(int(venue_qty), sum(int(r["contracts"]) for r in rows), ctx.broker.max_qty)
    limit = ctx.limit if ctx.limit is not None else ctx.market.quotes().option_bid(c)
    if limit is None or limit < 0.01:
        raise Refused(f"no bid for {c}: let it ride to expiry and observe it (#444), or pass --limit")
    start = len(ctx.broker.intents)
    fill = ctx.broker.submit_paper(contract_symbol=c, qty=qty, side="sell", limit_price=float(limit),
                                   client_order_id=make_client_order_id("flatten", c,
                                                                        _now(ctx).astimezone(ET).date().isoformat()))
    _record_intents(ctx, start)
    ctx.lines.append(f"SELL_TO_CLOSE {qty}x {c} LIMIT {float(limit):.2f} (journal row untouched): {fill.note}")
    st = "filled" if (fill.filled and not fill.pending) else ("rejected" if not fill.filled else "new")
    deadline = time.monotonic() + ctx.poll_s
    while st not in TERMINAL and fill.order_id and time.monotonic() < deadline:
        ctx.sleep(3)
        st = str((ctx.broker.order_status(fill.order_id) or {}).get("state", "")).lower()
    ctx.check(st == "filled", f"the orphaned contract was sold (order state {st})")
    ctx.lines.append(f"journal quantity after flatten: {state.journal_contract_quantity(ctx.conn, c)} (unchanged)")
    return 0 if st == "filled" else 3


# ── the block ────────────────────────────────────────────────────────────────────────────────────

def _fmt_ts(dt: datetime) -> str:
    return f"{dt.astimezone(ET):%Y-%m-%d %H:%M:%S} ET ({dt.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ})"


def _row_text(r) -> str:
    parts = [f"#{r['id']} {r['status']}", f"{r['contracts']}x", f"entry ${float(r['entry_premium_per_contract']):,.2f}"]
    if r["mark"] is not None:
        parts.append(f"mark {float(r['mark']):.2f} @ {r['marked_at']}")
    if r["exit_reason"]:
        parts.append(f"exit_reason {r['exit_reason']}")
    if r["realized_pnl"] is not None:
        parts.append(f"P&L ${float(r['realized_pnl']):,.2f}")
    if r["closed_at"]:
        parts.append(f"closed {r['closed_at']}")
    return " · ".join(parts)


def venue_and_journal(ctx) -> tuple[list[str], dict]:
    """The side-by-side table. The venue is read per contract and per order id, never by listing the account."""
    import state
    from options_tradability import parse_osi

    rows = drill_rows(ctx.conn)
    c = rows[0]["contract_symbol"] if rows else ctx.contract
    root = (parse_osi(c or "") or {}).get("root")
    v_at = _now(ctx)
    venue_qty = ctx.broker.venue_quantity(c) if c else None
    journal_qty = state.journal_contract_quantity(ctx.conn, c) if c else 0
    j_at = _now(ctx)
    out = ["| | venue (paper; read per contract / per order id) | journal (scratch DB) |", "|---|---|---|",
           f"| read at | {_fmt_ts(v_at)} | {_fmt_ts(j_at)} |",
           f"| `{c}` qty | {venue_qty if venue_qty is not None else 'UNREADABLE'} | {journal_qty} (open+closing) |"]
    for r in rows:
        out.append(f"| position | — | {_row_text(r)} |")
    states: dict[str, str] = {}
    for o in ctx.conn.execute("SELECT * FROM drill_orders ORDER BY id"):
        if o["order_id"]:
            info = ctx.broker.order_status(o["order_id"]) or {}
            states[o["order_id"]] = str(info.get("state", "")).lower()
            v = (f"{info.get('state', 'UNREADABLE')} · filled {info.get('filled_qty')} @ "
                 f"{info.get('filled_avg_price')}") if info else "UNREADABLE"
        else:
            v = "not sent"
        out.append(f"| order `{o['client_order_id']}` | {v} | {o['side']} {o['qty']} @ {o['limit_price']:.2f} "
                   f"(at {o['at']}; id {o['order_id']}) |")
    shares = None
    if ctx.path == "expiry-itm" and root:
        shares = ctx.broker.venue_quantity(root)
        out.append(f"| `{root}` shares | {shares if shares is not None else 'UNREADABLE'} "
                   f"(baseline {meta_get(ctx.conn, 'shares_baseline')}) | — (the journal models no shares) |")
    return out, {"venue_qty": venue_qty, "journal_qty": journal_qty, "shares": shares, "order_states": states}


def verdict(ctx, view: dict) -> str:
    v, j = view["venue_qty"], view["journal_qty"]
    if v is None:
        return "UNKNOWN: the venue quantity is unreadable"
    text = "MATCH" if v == j else f"MISMATCH: venue {v} vs journal {j}"
    if v != j and ctx.path == "unsellable":
        text += " (expected: #444's shape, the journal closed in-DB while the venue holds the contract)"
    elif v != j and any(r["status"] == "pending" for r in drill_rows(ctx.conn)):
        text += " (the entry is still pending)"
    elif v != j and ctx.path.startswith("expiry"):
        text += " (the journal booked the expiry; record when the venue settles it)"
    for r in drill_rows(ctx.conn):
        st = view.get("order_states", {}).get(r["close_order_id"] or "")
        if r["status"] == "closing" and st in TERMINAL and st != "filled":
            text += (f"; the venue's close order is {st} while the journal still says closing (the next open-market "
                     "tick reconciles it)")
    base = meta_get(ctx.conn, "shares_baseline")
    if view.get("shares") is not None and base is not None and int(view["shares"]) != int(float(base)):
        text += (f"; the venue holds {int(view['shares']) - int(float(base)):+d} shares vs the baseline, which the "
                 "journal models nowhere (#444: auto-exercise). Flatten them by hand.")
    return text


def render(ctx, rc: int) -> str:
    rows = drill_rows(ctx.conn)
    c = rows[0]["contract_symbol"] if rows else ctx.contract
    exp = rows[0]["expiry"] if rows else None
    head = (f"### #466 drill · {ctx.path} · {ctx.step} · {_fmt_ts(_now(ctx))} · "
            + ("OBSERVE: read-only, nothing sent" if ctx.step == "observe" else
               "SENT (paper)" if ctx.send else "PLAN: nothing sent; journal changes made on a discarded copy"))
    ex = ctx.config.get("convexity_exits", {})
    out = [head, "",
           f"- path: {ctx.spec.issue}",
           f"- contract `{c}`" + (f" (expiry {exp})" if exp else "") + f" · scratch DB `{ctx.db_path}`",
           f"- thresholds (drill-local copy; config.json untouched): profit_take_multiple={ex.get('profit_take_multiple')}"
           f", time_stop_dte={ex.get('time_stop_dte')}, min_close_bid={ex.get('min_close_bid')}"]
    out += [f"- {ln}" for ln in ctx.lines]
    out += [f"- monitor pass: {ln}" for ln in ctx.monitor_lines]
    if ctx.step != "record":
        table, view = venue_and_journal(ctx)
        out += ["", *table, ""]
        out.append(f"- verdict: {verdict(ctx, view)}")
    for ok, what in ctx.checks:
        out.append(f"- CHECK {'ok' if ok else 'FAIL'}: {what}")
    if ctx.logs:
        out.append("- log:")
        out += [f"    {ln}" for ln in ctx.logs]
    out.append(f"- exit code {rc}")
    return "\n".join(out) + "\n"


class _Capture(logging.Handler):
    def __init__(self, sink: list) -> None:
        super().__init__(logging.INFO)
        self._sink = sink

    def emit(self, record) -> None:
        self._sink.append(f"{record.levelname} {record.name}: {record.getMessage()}")


@contextlib.contextmanager
def _captured(ctx):
    """Capture the monitor/carry/broker log lines into the block, and suppress pages for the drill's run."""
    import notify

    names = ("monitor", "carry", "broker", "state", "drill")
    h = _Capture(ctx.logs)
    saved = []
    for n in names:
        lg = logging.getLogger(n)
        saved.append((lg, lg.level))
        lg.addHandler(h)
        if lg.getEffectiveLevel() > logging.INFO:
            lg.setLevel(logging.INFO)
    real_send = notify.send

    def _no_page(title, message, *, priority=0):
        ctx.logs.append(f"PAGE suppressed in the drill: {title}: {message}")
        return False
    notify.send = _no_page
    try:
        yield
    finally:
        notify.send = real_send
        for lg, lvl in saved:
            lg.removeHandler(h)
            lg.setLevel(lvl)


def run_step(ctx) -> int:
    from risk import kill_switch_active

    rc = 0
    with _captured(ctx):
        try:
            if ctx.step in TRADING_STEPS and kill_switch_active():
                raise Refused("REFUSED: the KILL switch is engaged")
            if ctx.step == "open":
                rc = step_open(ctx)
            elif ctx.step == "tick":
                rc = step_tick(ctx)
            elif ctx.step == "flatten":
                rc = step_flatten(ctx)
            elif ctx.step == "observe":
                rc = 0
            if any(not ok for ok, _ in ctx.checks):
                rc = rc or 3
        except Refused as e:
            ctx.lines.append(str(e) if str(e).startswith("REFUSED") else f"REFUSED: {e}")
            rc = 2
    return rc


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────

def _emit(text: str, out: str | None) -> None:
    print(text)
    if out:
        with open(Path(out).expanduser(), "a", encoding="utf-8") as f:
            f.write(text + "\n")


def main(argv=None, *, config: dict | None = None, market=None, credentials: tuple[str, str] | None = None,
         sleep=time.sleep) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", required=True, choices=sorted(PATHS))
    ap.add_argument("--step", required=True, choices=("open", "tick", "observe", "flatten", "record"))
    ap.add_argument("--db", default=None, help="the scratch journal for THIS path (default: a new temp file)")
    ap.add_argument("--contract", help="OCC symbol of the drill contract (≤ --max-dte days to expiry)")
    ap.add_argument("--limit", type=float, default=None, help="buy limit for open (default: the ask), sell for flatten")
    ap.add_argument("--pick", action="store_true", help="pick a liquid short-dated call on --symbol")
    ap.add_argument("--symbol", help="the liquid underlying for --pick")
    ap.add_argument("--moneyness", choices=("otm", "itm"), default=None, help="for --pick (default: itm for "
                    "expiry-itm, else otm)")
    ap.add_argument("--max-dte", type=int, default=7)
    ap.add_argument("--budget", type=float, default=250.0, help="hard cap on the buy premium, $ (qty is always 1)")
    ap.add_argument("--multiple", type=float, default=None, help="profit-take's low multiple (default 0.01)")
    ap.add_argument("--rest-markup", type=float, default=2.0, help="resting-close: sell limit = ask × this")
    ap.add_argument("--poll-s", type=float, default=90.0, help="seconds to wait for a fill / reconcile")
    ap.add_argument("--out", default=None, help="also append every block to this file")
    ap.add_argument("--send", action="store_true", help="actually place paper orders (else PLAN only)")
    args = ap.parse_args(argv)

    def refuse(msg: str) -> int:
        _emit(f"### #466 drill · {args.path} · {args.step} · {msg}\n", args.out)
        return 2

    why = live_env_refusal()
    if why:
        return refuse(why)
    if args.max_dte < 1 or args.max_dte > 14:
        return refuse("REFUSED: --max-dte must be 1..14 (a short-dated drill contract)")
    if config is None:
        from config_loader import ConfigError, load_config
        try:
            config = load_config()
        except ConfigError as e:
            return refuse(f"REFUSED: {e}")
    why = live_env_refusal() or config_refusal(config)      # again: load_config has read .env into the environ
    if why:
        return refuse(why)
    if args.db:
        db_path = Path(args.db).expanduser()
    else:
        fd, tmp = tempfile.mkstemp(prefix="drill466_", suffix=".db")
        os.close(fd)
        db_path = Path(tmp)
        print(f"(no --db: scratch journal {db_path}; multi-day paths need a persistent --db)")
    why = db_refusal(db_path, config)
    if why:
        return refuse(why)

    cfg = drill_config(config, args.path, multiple=args.multiple)
    cfg["_drill_max_dte"] = args.max_dte
    conn = open_scratch(db_path)
    try:
        bound = meta_get(conn, "path")
        if bound is not None and bound != args.path:
            return refuse(f"REFUSED: {db_path} is the {bound} drill's DB; one scratch DB per path")
        rows = drill_rows(conn)
        if args.step == "record":
            blocks = [r["block"] for r in conn.execute("SELECT block FROM drill_log ORDER BY id")]
            _emit("\n".join(blocks) if blocks else f"(no logged steps in {db_path})", args.out)
            return 0
        contract = rows[0]["contract_symbol"] if rows else args.contract
        if args.contract and rows and args.contract != contract:
            return refuse(f"REFUSED: this DB's drill contract is {contract}, not {args.contract}")
        if credentials is None:
            from config_loader import ConfigError, require_alpaca_credentials
            try:
                credentials = require_alpaca_credentials(config)
            except ConfigError as e:
                return refuse(f"REFUSED: {e}")
        if market is None:
            market = AlpacaMarket(config, *credentials)
        if contract is None and args.step == "open":
            if not (args.pick and args.symbol):
                return refuse("REFUSED: pass --contract, or --pick --symbol <liquid underlying>")
            spot = market.underlying_price(args.symbol)
            if not spot:
                return refuse(f"REFUSED: no price for {args.symbol}")
            mny = args.moneyness or ("itm" if args.path == "expiry-itm" else "otm")
            pick = pick_short_dated(market.chain(args.symbol), underlying_price=float(spot),
                                    today=market.clock.now().astimezone(ET).date(), max_dte=args.max_dte,
                                    budget=args.budget, moneyness=mny)
            if pick is None:
                return refuse(f"NO qualifying ≤{args.max_dte}-DTE {mny} call on {args.symbol} under "
                              f"${args.budget:.0f} (fail-closed)")
            contract = pick.symbol
            if args.limit is None:
                args.limit = round(float(pick.ask), 2)
            print(f"picked {contract} (spot {float(spot):.2f}, strike {pick.strike}, bid {pick.bid}/ask {pick.ask})")
        try:
            broker = make_drill_broker(*credentials, send=args.send, tag=PATHS[args.path].tag, contract=contract,
                                       budget=args.budget)
        except Refused as e:
            return refuse(str(e))
        work = conn if args.send else plan_copy(conn)
        ctx = Ctx(path=args.path, step=args.step, conn=work, broker=broker, market=market, config=cfg,
                  send=args.send, db_path=db_path.resolve(), contract=contract, limit=args.limit,
                  budget=args.budget, rest_markup=args.rest_markup, poll_s=args.poll_s, sleep=sleep)
        rc = run_step(ctx)
        block = render(ctx, rc)
        _emit(block, args.out)
        if (args.send or args.step == "observe") and rc != 2:
            if bound is None and args.send:
                meta_set(conn, "path", args.path)
            with conn:
                conn.execute("INSERT INTO drill_log (at, step, sent, rc, block) VALUES (?, ?, ?, ?, ?)",
                             (_now(ctx).isoformat(), args.step, int(args.send), rc, block))
        if work is not conn:
            work.close()
        return rc
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
