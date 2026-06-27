"""Read-only DATA layer for the §5b observability dashboard.

Deliberately **imports no streamlit** — this is the whole testable surface (the `st.*` shell lives in
`dashboard.py`). Every function is read-only over the SQLite journal + the PIT cache; the SAFETY contract:

  - the journal is opened STRICTLY read-only (`connect_ro` → `file:…?mode=ro`; a write RAISES — the
    never-broker analog), and connections are short-lived (the caller opens per query, closes promptly, so
    an open read txn can't block a deploy-time WAL migration);
  - market reads are NO-FETCH (`MarketData(client=None)` — a cache miss raises `CacheMiss`, surfaced as
    "accruing", never a network call);
  - every panel is fail-soft via :func:`safe` (one panel's error never blanks the page);
  - it RENDERS the existing reports (`shadow_book.tail_report`, `fixed_basket.tail_report`,
    `council_health_report.council_l1_health`, `cluster_diagnostic`, `basket_quality`,
    `scoring.agent_contribution`) and adds only read-only AGGREGATIONS — each pinned to an exact
    DEFINITION and a hand-checked value test (anti-HARK; PREREG_CONVEXITY_CALIBRATION §6).

It is observation only: it never edits clusters/themes/config, never proposes/sizes/authorizes (the hard seam).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

import breach_audit
import clusters
import fixed_basket
import shadow_book
import state
from council.proposal import passes_floor
from council.scoring import agent_contribution
from council_health_report import council_l1_health, latest_council_run

SCHEMA_EXPECTED = 16  # the highest migration whose data a panel RENDERS — bump ONLY then (not every migration).
#                       Warns only if the DB is BEHIND this (a DB ahead is fine; see header_status schema_ok).
# Rendered through 16: 0013 runs.data_feed (regime_panel) + 0014 gate_dualread (gate_dualread_report)
#                      + 0016 council_proposals.markers_asof (council_l1_health.marker_staleness). 0015 is
#                      NOT rendered, but the high-water mark is the DB version, and rendering 0016 needs ≥16.
# Staleness thresholds (hours) — documented, generous enough to not false-alarm over a normal weekend/holiday.
STALE_HOURS = {"cycle": 26.0, "council": 96.0, "discovery": 8.0 * 24.0}
MIN_CI_N = 8  # below this, a percentile bootstrap is degenerate → suppress the CI (operator R2: n=3 reads tight)
RECENT_COUNCIL_N = 4  # trailing council-run window for the Health strip + T4 cond-1 (single-sourced)

# Market-aware staleness (pure datetime — NEVER LiveClock.is_market_open, which fetches via Alpaca). The live
# cadence comes from the systemd timers: L1/council = Mon–Fri 15:45 ET; L2 monitor = every 30 min across
# 09:00–16:00 ET weekdays. Anchoring on these means a weekend (nothing scheduled) never false-alarms.
# Holidays are NOT modeled (a holiday weekday → a one-evening benign false-STALE, raw age shown beside); a
# static holiday set is deferred.
_ET = ZoneInfo("America/New_York")
_L1_SLOT_HM = (15, 45)              # council/L1 daily slot (ET)
_L1_GRACE_MIN = 20                  # a slot counts as "due" only once now ≥ slot + this (start/record latency)
_L2_WINDOW_HM = ((9, 0), (16, 0))  # L2 monitor cadence window (ET)
_L2_STALE_MIN = 50                 # one 30-min L2 interval + 20 slack before calling an intraday stall


# ── connection / paths ────────────────────────────────────────────────────────────────────────
def connect_ro(db_path: str | Path) -> sqlite3.Connection:
    """Open the journal STRICTLY read-only (a write raises ``OperationalError`` — the asserted backstop).
    WAL ⇒ this reader runs concurrently with the live L1/L2 writers. Open short-lived; close promptly."""
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def resolve_paths(config: dict) -> dict:
    """Resolve the absolute LIVE db + cache dirs. Env overrides (``DRAMATIC_DB`` / ``DRAMATIC_CACHE_DIR``)
    WIN — so the dashboard, run from the worktree, points at the live checkout's DB, not the worktree's stale
    one (the `.env` footgun analog). Default relative paths resolve against CWD (run from ~/dramatic_options)."""
    db = os.environ.get("DRAMATIC_DB") or config.get("database", {}).get("path", "data/dramatic_options.db")
    cache = os.environ.get("DRAMATIC_CACHE_DIR") or config.get("cache", {}).get("dir", "data/cache")
    return {
        "db_path": str(Path(db).resolve()),
        "cache_dir": str(Path(cache).resolve()),
        "db_exists": Path(db).exists(),
        "from_env": bool(os.environ.get("DRAMATIC_DB")),
    }


def safe(fn: Callable, *args, **kwargs) -> Any:
    """Call a panel loader fail-soft: return its result, or ``{"error": …}`` on ANY exception (incl. a
    NO-FETCH ``CacheMiss``). The dashboard renders the error in-panel so one failure never blanks the page."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 — a monitoring surface must degrade, never crash
        return {"error": f"{type(e).__name__}: {e}"}


# ── small helpers ─────────────────────────────────────────────────────────────────────────────
def _rows(conn, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _scalar(conn, sql: str, params: tuple = ()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def _parse_dt(s: Any) -> datetime | None:
    """Parse an ISO timestamp (tz-aware or the naive ``datetime('now')`` form) → tz-aware UTC, or None."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s))
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _age_hours(s: Any, *, now: datetime) -> float | None:
    dt = _parse_dt(s)
    return None if dt is None else (now - dt).total_seconds() / 3600.0


def _bootstrap_p95_ci(xs: list[float], *, iters: int = 2000, seed: int = 0, min_n: int = MIN_CI_N) -> dict:
    """Per-book p95 + a single-sample bootstrap 90% CI (the §5 descriptive read — NOT a gap verdict). Below
    ``min_n`` the CI is SUPPRESSED + flagged (a small-n percentile bootstrap reads deceptively tight; the real
    arm matures LAST). ``n`` is always shown alongside."""
    arr = np.asarray([float(x) for x in xs], dtype=float)
    n = arr.size
    if n == 0:
        return {"n": 0, "p95": None, "ci90": None, "flag": "accruing — n=0"}
    p95 = float(np.percentile(arr, 95))
    if n < min_n:
        return {"n": n, "p95": round(p95, 4), "ci90": None, "flag": f"small-n (<{min_n}) — CI suppressed"}
    rng = np.random.default_rng(seed)
    boots = [float(np.percentile(rng.choice(arr, n), 95)) for _ in range(iters)]
    lo, hi = np.percentile(boots, [5, 95])
    return {"n": n, "p95": round(p95, 4), "ci90": [round(float(lo), 4), round(float(hi), 4)], "flag": None}


# ── market-aware staleness (pure datetime; the two beats have different cadences) ───────────────
def _et_date(ts):
    """ET calendar date of a timestamp, or None."""
    dt = _parse_dt(ts)
    return None if dt is None else dt.astimezone(_ET).date()


def _most_recent_due_l1_date(now_et: datetime):
    """ET date of the most recent weekday 15:45-ET L1 slot already DUE (now ≥ slot + grace), walking back
    across weekends/long weekends; None if none in the last ~8 days."""
    grace = timedelta(minutes=_L1_GRACE_MIN)
    day = now_et
    for _ in range(8):
        if day.weekday() < 5:
            slot = day.replace(hour=_L1_SLOT_HM[0], minute=_L1_SLOT_HM[1], second=0, microsecond=0)
            if now_et >= slot + grace:
                return slot.date()
        day -= timedelta(days=1)
    return None


def council_session_stale(last_council_ts, *, now: datetime | None = None) -> str:
    """Market-aware staleness for the daily L1/council cadence (Mon–Fri 15:45 ET). OFFLINE if never run;
    STALE iff a weekday 15:45-ET slot has come DUE on a date strictly after the last council run's date;
    else ONLINE. ``last_council_ts`` is the run started_at — a same-day catch-up before the slot still counts
    (date-based), so a Persistent catch-up doesn't false-alarm. Pure datetime (no fetch)."""
    now = now or datetime.now(UTC)
    last_date = _et_date(last_council_ts)
    if last_date is None:
        return "OFFLINE"
    due_date = _most_recent_due_l1_date(now.astimezone(_ET))
    if due_date is None:
        return "ONLINE"
    return "STALE" if last_date < due_date else "ONLINE"


def cycle_session_stale(last_cycle_ts, *, now: datetime | None = None) -> str:
    """Market-aware staleness for the L1∪L2 loop liveness (L2 monitor every ~30 min across 09:00–16:00 ET
    weekdays). OFFLINE if never run; ONLINE outside the RTH cadence window / weekends (nothing scheduled);
    inside it, STALE iff the last loop run is older than one L2 interval + slack — the intraday-stall the flat
    age threshold never caught. Pure datetime (no fetch)."""
    now = now or datetime.now(UTC)
    last = _parse_dt(last_cycle_ts)
    if last is None:
        return "OFFLINE"
    now_et = now.astimezone(_ET)
    (oh, om), (ch, cm) = _L2_WINDOW_HM
    open_dt = now_et.replace(hour=oh, minute=om, second=0, microsecond=0)
    close_dt = now_et.replace(hour=ch, minute=cm, second=0, microsecond=0)
    # don't expect freshness on weekends, in the first interval+slack of the window, or after close
    if now_et.weekday() >= 5 or now_et < open_dt + timedelta(minutes=_L2_STALE_MIN) or now_et >= close_dt:
        return "ONLINE"
    return "STALE" if (now - last).total_seconds() / 60.0 > _L2_STALE_MIN else "ONLINE"


def system_status(snap: dict) -> dict:
    """Collapse the snapshot's health signals into ONE glanceable verdict + the things that want a look.
    Defensive: a missing/errored panel is handled, and an errored panel is ITSELF flagged (a green banner
    must never sit above fail-soft error boxes). Returns {level: success|warn|error, headline, issues}."""
    issues: list[str] = []
    critical = False
    header = snap.get("header") or {}
    risk = snap.get("risk") or {}
    council = snap.get("council") or {}

    if isinstance(header, dict) and not header.get("error"):
        if header.get("kill_switch_engaged"):
            issues.append("🛑 KILL switch ENGAGED")
            critical = True
        if header.get("schema_warning"):
            issues.append(f"schema {header.get('schema_version')}≠{header.get('schema_expected')}")
        for key in ("cycle", "council", "discovery"):
            beat = header.get(key) or {}
            if beat.get("status") and beat["status"] != "ONLINE":
                issues.append(f"{key} heartbeat {beat['status']}")
    if isinstance(risk, dict) and not risk.get("error"):
        kr = risk.get("kill_rule") or {}
        if kr.get("tripped"):
            issues.append(f"🚨 kill rule TRIPPED ({', '.join(kr.get('reasons') or [])})")
            critical = True
        if (risk.get("cost_cap") or {}).get("tripped"):
            issues.append("cost-cap tripped")
    if isinstance(council, dict) and not council.get("error"):
        v = (council.get("health") or {}).get("verdict")
        if v in ("PARSE_FAIL", "ROUNDTRIP_DEGRADED"):
            issues.append(f"council {v}")
            if v == "PARSE_FAIL":
                critical = True

    errored = sorted(k for k, val in snap.items() if isinstance(val, dict) and val.get("error"))
    if errored:
        issues.append(f"{len(errored)} panel(s) unavailable (fail-soft): {', '.join(errored)}")

    if critical:
        return {"level": "error", "headline": "🔴 Attention required", "issues": issues}
    if issues:
        return {"level": "warn", "headline": "🟡 A few things to check", "issues": issues}

    bits: list[str] = []
    if isinstance(risk, dict) and not risk.get("error"):
        bk = risk.get("book") or {}
        bits.append(f"book {bk.get('open', '?')}/{bk.get('max', '?')}")
    if isinstance(header, dict) and not header.get("error"):
        age = (header.get("cycle") or {}).get("age_hours")
        bits.append("last cycle " + ("—" if age is None else f"{age:.0f}h ago"))
    if isinstance(council, dict) and not council.get("error"):
        v = (council.get("health") or {}).get("verdict")
        if v:
            bits.append(f"council {v}")
    bits.append("KILL off")
    return {"level": "success",
            "headline": "🟢 All systems nominal — " + " · ".join(bits) + " · nothing to action", "issues": []}


# ── A · header / heartbeat / op-health ──────────────────────────────────────────────────────────
def header_status(conn, *, now: datetime | None = None) -> dict:
    """Schema + heartbeats + KILL. NOTE: L1 (full cycle) and L2 (monitor) BOTH record mode='PAPER'
    note='paper cycle' (orchestrator.py:488), so they are NOT distinguishable by mode. We surface
    ``last_cycle`` (the L1/L2 loop liveness — a runs row fires even on an empty book) separately from
    ``last_council`` (the run behind the latest council_proposals = the last L1 that actually deliberated)
    and ``mark_staleness`` (max marked_at — null on an empty book). Different questions, kept distinct."""
    now = now or datetime.now(UTC)
    from risk import kill_switch_active

    schema = state.schema_version(conn)
    last_disc = _scalar(conn, "SELECT MAX(started_at) FROM runs WHERE mode='DISCOVERY'")
    last_cycle = _scalar(conn, "SELECT MAX(started_at) FROM runs WHERE mode IN ('PAPER','LIVE')")
    last_council_run = _scalar(conn, "SELECT MAX(run_id) FROM council_proposals")
    last_council = (
        _scalar(conn, "SELECT started_at FROM runs WHERE id=?", (last_council_run,))
        if last_council_run is not None else None
    )
    last_mark = _scalar(conn, "SELECT MAX(marked_at) FROM convexity_positions WHERE marked_at IS NOT NULL")
    mark_age = _age_hours(last_mark, now=now)

    def _beat(ts, key):
        # Tri-state (borrowed from the real_options heartbeat): OFFLINE = never ran (a config/deploy
        # problem) is a DIFFERENT diagnosis from STALE = ran but the timer has gone quiet past its cadence.
        # cycle/council use MARKET-AWARE rules (weekends/holidays don't false-alarm); discovery keeps the flat
        # age threshold (weekly L0). `stale` (= not ONLINE) is kept for back-compat.
        age = _age_hours(ts, now=now)
        if key == "council":
            status = council_session_stale(ts, now=now)
        elif key == "cycle":
            status = cycle_session_stale(ts, now=now)
        elif ts is None:
            status = "OFFLINE"
        elif age is not None and age > STALE_HOURS[key]:
            status = "STALE"
        else:
            status = "ONLINE"
        return {"at": ts, "age_hours": None if age is None else round(age, 1),
                "status": status, "stale": status != "ONLINE"}

    return {
        "schema_version": schema,
        "schema_expected": SCHEMA_EXPECTED,
        # Warn ONLY if the DB is BEHIND what a panel renders (schema < expected → the rendered data is
        # missing). A DB AHEAD is fine — a landed-but-unrendered migration doesn't break older panels.
        # (The prior `== ` over-warned on any DB-ahead, e.g. a standing false alarm at schema 15 vs 14
        # after 0015 landed unrendered — 2026-06-26 fix.)
        "schema_ok": schema >= SCHEMA_EXPECTED,
        "schema_warning": (None if schema >= SCHEMA_EXPECTED else
                           f"DB at schema {schema} is BEHIND the {SCHEMA_EXPECTED} a panel renders — "
                           "panels may be stale"),
        "kill_switch_engaged": kill_switch_active(),
        "discovery": _beat(last_disc, "discovery"),
        "cycle": _beat(last_cycle, "cycle"),
        "council": _beat(last_council, "council"),
        "mark_staleness": {"at": last_mark, "age_hours": None if mark_age is None else round(mark_age, 1),
                           "stale": mark_age is not None and mark_age > STALE_HOURS["cycle"]},
        "now": now.isoformat(),
    }


def risk_panel(conn, config: dict) -> dict:
    """Book drawdown vs the kill threshold, open slots vs the cap, per-cluster premium vs the cluster cap, and
    KILL/cost-cap TRIP state (distinct from raw threshold values). Reuses the canonical kill rule."""
    from clock import FixedClock
    from paper_loop import kill_rule_status
    from risk import kill_switch_active

    book = config.get("convexity_book", {})
    equity = float(book.get("account_equity", 0.0))
    book_budget = equity * float(book.get("book_fraction", 0.0))
    krs = kill_rule_status(conn, config, FixedClock(datetime.now(UTC)))
    _dd, have_marks = state.convexity_book_drawdown(conn, book_budget)

    cmap = clusters.load_cluster_map(config)
    cluster_cap = equity * float(book.get("cluster_fraction", 0.0))
    cluster_rows = [
        {"cluster": name, "premium": round(state.cluster_open_premium(conn, members), 2),
         "cap": round(cluster_cap, 2), "frac": (round(state.cluster_open_premium(conn, members) / cluster_cap, 3)
                                                if cluster_cap else None),
         "directions": sorted(state.cluster_open_directions(conn, members))}
        for name, members in sorted(cmap.items())
    ]
    last_health = _scalar(conn, "SELECT council_health FROM runs WHERE council_health IS NOT NULL ORDER BY id DESC LIMIT 1")
    return {
        "kill_switch_engaged": kill_switch_active(),
        "kill_rule": {"tripped": krs.tripped, "reasons": list(krs.reasons),
                      "book_drawdown": round(krs.book_drawdown, 4), "have_marks": have_marks,
                      "drawdown_halt": float(config.get("kill_rule", {}).get("book_drawdown_halt", 0.20))},
        "cost_cap": {"last_council_health": last_health, "tripped": last_health == "cost_cap",
                     "cap_usd": float(config.get("council", {}).get("cost_cap_usd", 0.0))},
        "book": {"open": state.count_open_convexity_positions(conn),
                 "max": int(book.get("max_open_positions", 15)),
                 "open_premium": round(state.convexity_book_open_premium(conn), 2),
                 "budget": round(book_budget, 2)},
        "clusters": cluster_rows,
    }


def account_panel(conn, config: dict, *, now: datetime | None = None) -> dict:
    """Journal-sourced account/balance visibility (PR-C). KEYLESS by design: the broker number is
    ``runs.equity`` (the live loop records ``client.get_equity()`` every L1/L2 cycle) — never a
    broker/client call from the dashboard. The risk frame is OPERATOR-FROZEN (PREREG §5):
    ``delta_vs_frame`` is informational (render with delta_color='off') and the broker number
    never resizes the frame. ``equity_series`` = per-UTC-day LAST equity (value at MAX(id) among
    that day's non-null-equity PAPER/LIVE rows), date-bounded to the trailing 120 UTC days."""
    now = now or datetime.now(UTC)
    book = config.get("convexity_book", {})
    frame_equity = float(book.get("account_equity", 0.0))
    book_budget = frame_equity * float(book.get("book_fraction", 0.0))
    latest = _rows(conn, "SELECT id, started_at, equity FROM runs WHERE mode IN ('PAPER','LIVE') "
                         "AND equity IS NOT NULL ORDER BY id DESC LIMIT 1")
    broker = latest[0] if latest else None
    series = _rows(conn,
                   "SELECT date(started_at) AS day, equity FROM runs r "
                   "WHERE mode IN ('PAPER','LIVE') AND equity IS NOT NULL "
                   "AND date(started_at) >= date(?, '-120 days') "
                   "AND id = (SELECT MAX(id) FROM runs r2 WHERE r2.mode IN ('PAPER','LIVE') "
                   "          AND r2.equity IS NOT NULL AND date(r2.started_at) = date(r.started_at)) "
                   "ORDER BY day", (now.date().isoformat(),))
    open_premium = state.convexity_book_open_premium(conn)
    age = _age_hours(broker["started_at"], now=now) if broker else None
    return {
        "broker_equity": None if broker is None else round(float(broker["equity"]), 2),
        "as_of": None if broker is None else broker["started_at"],
        "run_id": None if broker is None else broker["id"],
        "age_hours": None if age is None else round(age, 1),
        "delta_vs_frame": None if broker is None else round(float(broker["equity"]) - frame_equity, 2),
        "equity_series": [{"day": r["day"], "equity": round(float(r["equity"]), 2)} for r in series],
        "frame": {"frame_equity": round(frame_equity, 2), "book_budget": round(book_budget, 2),
                  "per_name_cap": round(frame_equity * float(book.get("per_name_fraction", 0.0)), 2),
                  "cluster_cap": round(frame_equity * float(book.get("cluster_fraction", 0.0) or 0.0), 2),
                  "max_open": int(book.get("max_open_positions", 15))},
        "headroom": round(book_budget - open_premium, 2),
    }


_MIX_ROLES = ("proposer", "adversary", "strategist")


def regime_panel(conn, config: dict, *, now: datetime | None = None) -> dict:
    """The configuration-of-record readout (the record-segmentation keys), TWO provenance anchors
    SPLIT-READ: ``feeds`` (data_feed/frame_version — stamped on EVERY run) from the latest
    PAPER/LIVE row; ``council`` (council_health/model_mix — stamped only by L1 council cycles)
    from the latest ``council_health IS NOT NULL`` row (L2 fires ~every 30min with NULL council
    fields, so a single-row read would render empty nearly all day). model_mix non-role keys pass
    through GENERICALLY (this panel owns no other PR's stamp schema). The disagree-veto boolean is
    single-sourced through the canonical ``gate_dualread.disagree_veto_active`` applied to the
    STAMPED date (inclusive end; malformed → inert); days_remaining is display-only and never
    negative. No verdicts — a readout."""
    from gate_dualread import disagree_veto_active

    now = now or datetime.now(UTC)
    feed_row = (_rows(conn, "SELECT id, started_at, frame_version, data_feed FROM runs "
                            "WHERE mode IN ('PAPER','LIVE') ORDER BY id DESC LIMIT 1") or [None])[0]
    council_row = (_rows(conn, "SELECT id, started_at, council_health, model_mix FROM runs "
                               "WHERE council_health IS NOT NULL ORDER BY id DESC LIMIT 1") or [None])[0]

    feeds = {"run_id": None, "as_of": None, "frame_version": None, "equity_bars": None,
             "option_gate": None, "option_monitor": None, "dualread_veto_until": None}
    if feed_row is not None:
        feeds["run_id"], feeds["as_of"] = feed_row["id"], feed_row["started_at"]
        feeds["frame_version"] = feed_row["frame_version"]
        try:
            df = json.loads(feed_row["data_feed"]) if feed_row["data_feed"] else {}
        except (TypeError, ValueError):
            df = {}
        if isinstance(df, dict):
            feeds["equity_bars"] = df.get("equity_bars")
            feeds["option_gate"] = df.get("option_gate")
            feeds["option_monitor"] = df.get("option_monitor")
            feeds["dualread_veto_until"] = df.get("dualread_disagree_veto_until")

    until = feeds["dualread_veto_until"]
    active = disagree_veto_active({"data_feed": {"dualread_disagree_veto_until": until}}, now.date())
    days = None
    if active and until:
        try:
            days = (date.fromisoformat(str(until)) - now.date()).days
        except ValueError:
            days = None

    council = {"run_id": None, "as_of": None, "council_health": None, "models": {}, "extras": {}}
    if council_row is not None:
        council["run_id"], council["as_of"] = council_row["id"], council_row["started_at"]
        council["council_health"] = council_row["council_health"]
        try:
            mix = json.loads(council_row["model_mix"]) if council_row["model_mix"] else {}
        except (TypeError, ValueError):
            mix = {}
        if isinstance(mix, dict):
            # str(v) tolerates a future nested per-role shape (ugly-but-rendered, never a panel error)
            council["models"] = {r: str(mix[r]) for r in _MIX_ROLES if r in mix}
            council["extras"] = {k: str(v) for k, v in mix.items() if k not in _MIX_ROLES}

    return {
        "feeds": feeds,
        "dualread_veto": {"until": until, "active": active, "days_remaining": days},
        "council": council,
        "config": {"conviction_floor": config.get("council", {}).get("conviction_floor", "MODERATE"),
                   "max_candidates": config.get("council", {}).get("max_candidates")},
    }


# ── B/C/E · performance, the null hierarchy, drivers ────────────────────────────────────────────
def _real_multiples_by_origin(conn) -> dict[str, list[float]]:
    """Real-book closed realized multiples split by ORIGIN via a LEFT join (a hand-seed predates sentinels
    and may have NO proposal row / a null sentinel_id ⇒ 'hand_seed'; only a non-null sentinel_id ⇒ 'sentinel')."""
    out: dict[str, list[float]] = {"hand_seed": [], "sentinel": []}
    for r in conn.execute(
        "SELECT p.total_premium AS tp, p.realized_pnl AS pnl, cp.sentinel_id AS sid "
        "FROM convexity_positions p LEFT JOIN council_proposals cp ON p.proposal_id = cp.id "
        "WHERE p.status='closed' AND p.realized_pnl IS NOT NULL AND p.total_premium > 0"
    ):
        origin = "sentinel" if r["sid"] is not None else "hand_seed"
        out[origin].append((float(r["tp"]) + float(r["pnl"])) / float(r["tp"]))
    return out


def premium_bled(conn) -> dict:
    """Premium PAID vs BLED (PREREG §7), shown REALIZED and RUNNING — closed-only is n=0 for months, so the
    running figure (realized + mark-decay-on-open) is the live read. DEFINITIONS (hand-checked):
      paid          = Σ total_premium over booked (open/closing/closed; pending not yet paid, cancelled excluded)
      realized_bled = Σ max(0, −realized_pnl) over CLOSED      (premium lost on a closed bet)
      running_bled  = realized_bled + Σ max(0, total_premium − mark·contracts·100) over OPEN/closing (decay so far)
      running_fraction = running_bled / paid
    """
    paid = float(_scalar(conn, "SELECT COALESCE(SUM(total_premium),0) FROM convexity_positions "
                               "WHERE status IN ('open','closing','closed')") or 0.0)
    realized = 0.0
    for r in conn.execute("SELECT realized_pnl FROM convexity_positions WHERE status='closed' AND realized_pnl IS NOT NULL"):
        realized += max(0.0, -float(r["realized_pnl"]))
    running = realized
    for r in conn.execute("SELECT total_premium, mark, contracts FROM convexity_positions WHERE status IN ('open','closing')"):
        if r["mark"] is not None:
            mark_val = float(r["mark"]) * int(r["contracts"]) * 100.0
            running += max(0.0, float(r["total_premium"]) - mark_val)
    return {
        "paid": round(paid, 2),
        "realized_bled": round(realized, 2),
        "running_bled": round(running, 2),
        "running_fraction": (round(running / paid, 4) if paid > 0 else None),
        "realized_fraction": (round(realized / paid, 4) if paid > 0 else None),
    }


def hit_rate(conn) -> dict:
    """Fraction of CLOSED real positions with realized_pnl > 0 (cheap; pairs with the calibration break-even p*)."""
    closed = int(_scalar(conn, "SELECT COUNT(*) FROM convexity_positions WHERE status='closed' AND realized_pnl IS NOT NULL") or 0)
    hits = int(_scalar(conn, "SELECT COUNT(*) FROM convexity_positions WHERE status='closed' AND realized_pnl > 0") or 0)
    return {"closed": closed, "hits": hits, "hit_rate": (round(hits / closed, 4) if closed else None)}


def performance_panel(conn) -> dict:
    """Per-book realized-multiple tails (REUSE) + per-book p95+CI + per-origin real split + bled + hit-rate.
    All accruing-aware (empty → n=0). The null GAP VERDICT is NOT computed here — deferred to the blind/mature
    null layer (PREREG §5); this surfaces the substrate (per-book p95+CI side-by-side) the eye reads."""
    tails = shadow_book.tail_report(conn)        # {real, shadow_<origin>, shadow_all}
    tails.update(fixed_basket.tail_report(conn))  # {nogate_union_nogate, nogate_basket_nogate}
    cis = {
        "real": _bootstrap_p95_ci(state.convexity_realized_multiples(conn)),
        "shadow_all": _bootstrap_p95_ci([m for ms in state.shadow_realized_multiples(conn).values() for m in ms]),
    }
    for book, ms in state.fixed_basket_realized_multiples(conn).items():
        cis[f"nogate_{book}"] = _bootstrap_p95_ci(ms)
    return {
        "tails": tails,
        "p95_ci": cis,  # the §5 "see the overlap" substrate; no gap verdict
        "real_by_origin": {o: shadow_book.tail_summary(ms) for o, ms in _real_multiples_by_origin(conn).items()},
        "premium_bled": premium_bled(conn),
        "hit_rate": hit_rate(conn),
        "caveat": "Tails/CIs are FORWARD calibration substrate, never a pass-gate (§6). "
                  "parse_fail runs are censored from the council-marginal (real−shadow) read.",
    }


def null_hierarchy(conn) -> dict:
    """The inferential chain made legible (PREREG_FIXED_BASKET_NULL §2): which contrasts are CLEAN one-variable
    steps vs BUNDLED — rendered as side-by-side per-book p95+CIs + resolved counts + the censored-run count, so
    the operator sees maturity and which step is clean. No gap is computed."""
    real_ms = state.convexity_realized_multiples(conn)
    shadow_ms = [m for ms in state.shadow_realized_multiples(conn).values() for m in ms]
    fb = state.fixed_basket_realized_multiples(conn)
    censored = int(_scalar(conn, "SELECT COUNT(*) FROM runs WHERE council_health='parse_fail'") or 0)
    return {
        "steps": [
            {"name": "gate (shadow − 3A)", "clean": True,
             "arms": {"shadow": _bootstrap_p95_ci(shadow_ms),
                      "3A": _bootstrap_p95_ci(fb.get("union_nogate", []))}},
            {"name": "council (real − shadow)", "clean": True, "censored_parse_fail_runs": censored,
             "arms": {"real": _bootstrap_p95_ci(real_ms), "shadow": _bootstrap_p95_ci(shadow_ms)}},
            {"name": "apparatus (real − 3B)", "clean": False, "bundled": "universe AND caps differ",
             "arms": {"real": _bootstrap_p95_ci(real_ms),
                      "3B": _bootstrap_p95_ci(fb.get("basket_nogate", []))}},
        ],
        "note": "CLEAN steps differ in ONE variable; the bundled read is descriptive. The VERDICT (significance) "
                "belongs to the blind/mature null layer — this is plumbing (T4 #2: 'plumbing, not significance').",
    }


def cheapness_watch_panel(conn) -> dict:
    """Finding #1's cheapness-watch (PREREG_CHEAPNESS_WATCH) — the §2.1 break/window/never_cheap state
    machine + the §7.1 verdict (N-floor + rate-close) + per-name latest cheap state. DIAGNOSTIC:
    ``insufficient_N`` is the EXPECTED reading (qualifying stale∧catchable breaks are conjunctively rare),
    interpretable only once curation gives the cohort break-CAPABLE names (the §2.1.7 precondition)."""
    import cheapness_watch

    rep = cheapness_watch.cheapness_report(conn)
    rep["latest_by_name"] = _rows(
        conn,
        "SELECT cw.symbol, cw.as_of, cw.cheap, cw.iv_rv, cw.marker_age_days FROM cheapness_watch cw "
        "JOIN (SELECT symbol, MAX(as_of) m FROM cheapness_watch GROUP BY symbol) t "
        "ON cw.symbol = t.symbol AND cw.as_of = t.m ORDER BY cw.symbol",
    )
    return rep


# ── curation tools (the keyless dashboard panel — DRAFTS only, never fetches/writes) ──────────────

_TICKER_RE = re.compile(r"^[A-Z][A-Z.]{0,6}$")
_THEME_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


def _sanitize_tickers(raw: str) -> list[str]:
    """Free-text → clean uppercase tickers only (deduped, order-preserving). The rendered screen command is
    pasted into a shell, so any token that isn't a clean ticker (letters/dot) is DROPPED — no shell
    metacharacter (`;`, `|`, `$`, `/`, `-`, space, quote) can survive into the command."""
    out: list[str] = []
    seen: set[str] = set()
    for tok in re.split(r"[\s,]+", (raw or "").strip().upper()):
        if tok and _TICKER_RE.match(tok) and tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def build_screen_command(raw_tickers: str) -> dict:
    """Build the box-side feasibility-screen command from free-text tickers (the keyless curation panel).
    PURE — no fetch, no write, no keys; the operator runs the returned command on the box (where keys live).
    Returns {tickers, command, dropped}."""
    tickers = _sanitize_tickers(raw_tickers)
    raw_count = len([t for t in re.split(r"[\s,]+", (raw_tickers or "").strip()) if t])
    command = ("cd ~/dramatic_options && PYTHONPATH=. venv/bin/python "
               "scripts/probe_basket_feasibility.py " + " ".join(tickers)) if tickers else ""
    return {"tickers": tickers, "command": command, "dropped": max(0, raw_count - len(tickers))}


def cluster_names(config: dict) -> list[str]:
    """The existing cluster keys (for the new-theme cluster picker). Static config map; no fetch/keys."""
    try:
        return sorted(clusters.load_cluster_map(config).keys())
    except Exception:  # noqa: BLE001 — the picker degrades to free-text on any config issue
        return []


def build_theme_entry(*, name: str, cluster: str, thesis: str, falsifier: str, source: str,
                      today: str | None = None, known_clusters: list[str] | None = None) -> dict:
    """Draft a ``universe_register.json`` theme entry (the §11 ingestion shape) from form input. PURE; the
    dashboard DISPLAYS this JSON for a PR — it NEVER writes the register (admission runs source∩screen∩OTM
    + the gate disposes on cheapness). Returns {key, entry, json, valid, problems, warnings}.

    ``known_clusters`` (the enforcement-map keys, i.e. ``cluster_names(config)``): when given and the chosen
    ``cluster_default`` is NOT among them, a WARNING (not a blocker — a new cluster is allowed) flags that
    the names will get the $1k per-name cap, NOT the $2k cluster cap, until ``clusters.py`` is also wired —
    the silent risk-frame divergence a PR reviewer would otherwise miss because the entry *looks* correct."""
    key = (name or "").strip().lower().replace(" ", "_")
    today = today or datetime.now(UTC).date().isoformat()
    problems: list[str] = []
    if not _THEME_NAME_RE.match(key):
        problems.append("name must be snake_case (a-z, then a-z/0-9/_)")
    if not (thesis or "").strip():
        problems.append("thesis required")
    if not (falsifier or "").strip():
        problems.append("falsifier required (what would kill the thesis)")
    if not (source or "").strip():
        problems.append("source required (the mechanical constituent source, e.g. an ETF holdings file)")
    cluster_default = (cluster or "").strip() or key
    warnings: list[str] = []
    if known_clusters is not None and cluster_default not in known_clusters:
        warnings.append(
            f"cluster '{cluster_default}' is NOT in the enforcement map (clusters.py) — its names get the "
            f"$1k per-name cap, NOT the $2k cluster correlation cap, until clusters.py is wired.")
    entry = {
        "provenance": "operator",
        "added": f"{today} (dashboard draft)",
        "thesis": (thesis or "").strip(),
        "falsifier": (falsifier or "").strip(),
        "sources": [(source or "").strip()],
        "cluster_default": cluster_default,
    }
    return {"key": key, "entry": entry, "valid": not problems, "problems": problems,
            "warnings": warnings, "json": json.dumps({key: entry}, indent=2)}


def attribution_panel(conn, config: dict) -> dict:
    """Drivers (E): per-origin tails (above) + per-theme/cluster realized & RUNNING P&L + Brier (strategist
    final, REUSE the column) + per-role CONTRIBUTION Brier (REUSE scoring.agent_contribution, recomputed
    read-only). All resolved-gated ⇒ accruing."""
    cmap = clusters.load_cluster_map(config)
    by_theme: dict[str, dict] = {}
    by_cluster: dict[str, dict] = {}

    def _acc(d: dict, key: str, realized: float, running: float):
        slot = d.setdefault(key, {"realized": 0.0, "running": 0.0, "n": 0})
        slot["realized"] += realized
        slot["running"] += running
        slot["n"] += 1

    for r in conn.execute(
        "SELECT theme, symbol, status, total_premium, realized_pnl, mark, contracts FROM convexity_positions "
        "WHERE status IN ('open','closing','closed')"
    ):
        if r["status"] == "closed" and r["realized_pnl"] is not None:
            realized = float(r["realized_pnl"])
            running = realized
        else:
            realized = 0.0
            mark_val = (float(r["mark"]) * int(r["contracts"]) * 100.0) if r["mark"] is not None else float(r["total_premium"])
            running = mark_val - float(r["total_premium"])
        _acc(by_theme, r["theme"] or "?", realized, running)
        cl = clusters.cluster_of(r["symbol"], cmap) or "(unclustered)"
        _acc(by_cluster, cl, realized, running)

    for d in (by_theme, by_cluster):
        for v in d.values():
            v["realized"] = round(v["realized"], 2)
            v["running"] = round(v["running"], 2)

    # Brier: strategist FINAL conviction (the persisted column) + per-role contribution (recompute).
    proposal_briers = [float(r["brier"]) for r in conn.execute(
        "SELECT brier FROM council_proposals WHERE brier IS NOT NULL")]
    ctp = config.get("council", {}).get("conviction_to_prob")
    role_acc: dict[str, list[float]] = {}
    for p in conn.execute("SELECT id, direction, outcome FROM council_proposals WHERE outcome IS NOT NULL"):
        aos = [SimpleNamespace(role=a["role"], stance=a["stance"], confidence=a["confidence"])
               for a in conn.execute("SELECT role, stance, confidence FROM council_agent_outputs WHERE proposal_id=?", (p["id"],))]
        for role, b in agent_contribution(aos, int(p["outcome"]), p["direction"], ctp).items():
            role_acc.setdefault(role, []).append(b)
    return {
        "pnl_by_theme": by_theme,
        "pnl_by_cluster": by_cluster,
        "proposal_brier": {"n": len(proposal_briers),
                           "mean": round(sum(proposal_briers) / len(proposal_briers), 4) if proposal_briers else None},
        "role_contribution_brier": {role: {"n": len(bs), "mean": round(sum(bs) / len(bs), 4)}
                                    for role, bs in role_acc.items()},
    }


# ── F · funnel / bottleneck / cost ──────────────────────────────────────────────────────────────
_VETO_ORDER = ("veto-cluster-cap", "veto-sentinel-slots", "veto-eligibility", "veto-iv-gate",
               "veto-sizing", "veto-fill")
_OPENED = ("open", "submit-pending")


def funnel_panel(conn, *, run_id: int | None = None) -> dict:
    """The L1 DECISION funnel (the SPEC §4 bottleneck view) for the latest full cycle: proposed → evaluated →
    by veto stage → opened, plus WASTED LLM SPEND (proposals later vetoed at eligibility/iv-gate — the council
    runs BEFORE the gate, verified paper_loop.py:252-304). The L0 discovery funnel surfaces the DB-persisted
    stages (surfaced/controls/framed); scanned/cleared are journal-only (noted)."""
    if run_id is None:
        run_id = _scalar(conn, "SELECT MAX(run_id) FROM convexity_eval")
    decisions = {r["decision"]: r["n"] for r in conn.execute(
        "SELECT decision, COUNT(*) AS n FROM convexity_eval WHERE run_id=? GROUP BY decision", (run_id,))} if run_id else {}
    proposed = int(_scalar(conn, "SELECT COUNT(*) FROM council_proposals WHERE run_id=?", (run_id,)) or 0) if run_id else 0
    evaluated = sum(decisions.values())
    opened = sum(decisions.get(d, 0) for d in _OPENED)
    wasted_llm = int(_scalar(
        conn,
        "SELECT COUNT(*) FROM convexity_eval WHERE run_id=? AND proposal_id IS NOT NULL "
        "AND decision IN ('veto-eligibility','veto-iv-gate')", (run_id,)) or 0) if run_id else 0

    last_disc_run = _scalar(conn, "SELECT MAX(run_id) FROM sentinel_candidates")
    discovery = {
        "run_id": last_disc_run,
        "surfaced": int(_scalar(conn, "SELECT COUNT(*) FROM sentinel_candidates WHERE run_id=? AND kind='sentinel'", (last_disc_run,)) or 0) if last_disc_run else 0,
        "controls": int(_scalar(conn, "SELECT COUNT(*) FROM sentinel_candidates WHERE run_id=? AND kind='control'", (last_disc_run,)) or 0) if last_disc_run else 0,
        "note": "scanned/cleared are journal-only (not persisted) — partial funnel by design",
    }
    return {
        "l1_decision": {"run_id": run_id, "proposed": proposed, "evaluated": evaluated,
                        "by_decision": decisions, "opened": opened, "wasted_llm_spend": wasted_llm,
                        "veto_order": list(_VETO_ORDER)},
        "l0_discovery": discovery,
    }


def _rationale(raw) -> dict:
    """Parse a council_proposals.rationale JSON cell → dict, fail-soft ({} on any error — never raises)."""
    if not raw:
        return {}
    try:
        d = json.loads(raw) if isinstance(raw, str) else raw
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def council_stage_funnel(conn, config: dict, *, run_id: int | None = None) -> dict:
    """The COUNCIL-STAGE breakout — where INSIDE the 3-role debate names die (upstream of
    ``funnel_panel``'s deterministic-gate funnel; the binding constraint on a first entry). Reconstructs
    the PRE-coercion include: ``debate.run_candidate`` mutates the strategist dict in place so a
    criteria-veto persists as ``include=False ∧ criteria_veto=True`` — so the veto + floor are real,
    visible stages. Anchored on the latest COUNCIL run (NOT ``convexity_eval`` — an L2 run has no
    proposals). Read-only; never raises.

    The tri-criteria LEGS are mixed-source by design: the structural leg reads the RESOLVED
    ``structural_vs_fad`` COLUMN (matches the §10.7 enforcement's strategist-or-proposer fallback);
    ``under_narrated``/``at_inflection`` read the rationale JSON (no columns exist). Legs are counted
    OVER the deliberated set only (the booleans are meaningless on a pre-strategist drop)."""
    if run_id is None:
        run_id = latest_council_run(conn)
    if run_id is None:
        return {"run_id": None, "empty": True}
    floor = (config.get("council", {}) or {}).get("conviction_floor", "MODERATE")
    rows = _rows(conn, "SELECT conviction, structural_vs_fad, status, rationale "
                       "FROM council_proposals WHERE run_id=?", (run_id,))
    proposed = len(rows)
    ungrounded = abstained = asserted = 0
    include_raw = criteria_vetoed = post_veto_include = below_floor = to_gate = 0
    structural = under_narrated = at_inflection = 0
    for r in rows:
        rat = _rationale(r["rationale"])
        strat = rat.get("strategist")
        if isinstance(strat, dict):                     # reached the strategist (deliberated)
            asserted += 1
            inc = strat.get("include") is True
            veto = strat.get("criteria_veto") is True
            if inc or veto:
                include_raw += 1                        # the PRE-coercion include
            if veto:
                criteria_vetoed += 1
            if inc:
                post_veto_include += 1
                if passes_floor(r["conviction"], floor):
                    to_gate += 1
                else:
                    below_floor += 1
            if str(r["structural_vs_fad"]) == "structural":
                structural += 1
            if strat.get("under_narrated") is True:
                under_narrated += 1
            if strat.get("at_inflection") is True:
                at_inflection += 1
        elif rat.get("dropped") == "ungrounded (no numeric evidence)":
            ungrounded += 1
        elif rat.get("dropped") == "proposer abstained (NEUTRAL)":
            abstained += 1
    other = proposed - asserted - ungrounded - abstained
    # The TRUE consistency bridge (a self-check on the reconstruction): the reconstructed survivors must
    # equal the status-recorded survivors (both from the SAME select_for_trade call in wiring.py),
    # independent of whether the cycle ran. NOT to_gate==evaluated (that breaks on a post-council close).
    survivors_by_status = int(_scalar(
        conn, "SELECT COUNT(*) FROM council_proposals WHERE run_id=? AND status IN ('proposed','traded')",
        (run_id,)) or 0)
    return {
        "run_id": run_id, "empty": False, "floor": floor,
        "stages": {"proposed": proposed, "asserted": asserted, "ungrounded": ungrounded,
                   "proposer_abstained": abstained, "other": other,
                   "strategist_include_raw": include_raw, "criteria_vetoed": criteria_vetoed,
                   "post_veto_include": post_veto_include, "below_floor": below_floor, "to_gate": to_gate},
        "bridge": {"to_gate": to_gate, "survivors_by_status": survivors_by_status,
                   "ok": to_gate == survivors_by_status},
        "legs": {"n_deliberated": asserted, "structural": structural,
                 "under_narrated": under_narrated, "at_inflection": at_inflection},
    }


def gate_reasons(conn, *, run_id: int | None = None) -> dict:
    """Veto-reason distribution + the FAIL-CLOSED-on-missing-DATA rate, keyed on STRUCTURED columns (decision
    + iv_rv null-ness), NOT free-text reasons (robust). A veto-iv-gate row with iv_rv IS NULL = fail-closed on
    missing input; with iv_rv present = a real (too-rich) veto. Over all evals unless run_id given."""
    where = "WHERE run_id=?" if run_id is not None else ""
    params = (run_id,) if run_id is not None else ()
    iv_total = int(_scalar(conn, f"SELECT COUNT(*) FROM convexity_eval {where} {'AND' if where else 'WHERE'} decision='veto-iv-gate'", params) or 0)
    iv_failclosed = int(_scalar(conn, f"SELECT COUNT(*) FROM convexity_eval {where} {'AND' if where else 'WHERE'} decision='veto-iv-gate' AND iv_rv IS NULL", params) or 0)
    elig = int(_scalar(conn, f"SELECT COUNT(*) FROM convexity_eval {where} {'AND' if where else 'WHERE'} decision='veto-eligibility'", params) or 0)
    return {
        "by_decision": {r["decision"]: r["n"] for r in conn.execute(
            f"SELECT decision, COUNT(*) AS n FROM convexity_eval {where} GROUP BY decision", params)},
        "iv_gate": {"total": iv_total, "fail_closed_missing_data": iv_failclosed,
                    "real_veto": iv_total - iv_failclosed},
        "eligibility_vetoes": elig,
    }


def cap_binding_flow(conn) -> dict:
    """How often the CLUSTER cap REJECTED an otherwise-passing candidate (eligible + cheap but cluster-full).
    Readable from decision codes. NOTE: partial-TIGHTENING on admits is NOT reconstructable from the current
    cluster_state stamp (carries cluster remaining only, not all three) — flagged as a 1-field upstream gap."""
    rejected = int(_scalar(
        conn, "SELECT COUNT(*) FROM convexity_eval WHERE decision='veto-cluster-cap' "
              "AND eligible=1 AND gate_cheap=1") or 0)
    return {"cluster_cap_rejections_of_passing": rejected,
            "tightening_note": "partial-admit tightening not reconstructable (upstream 1-field stamp gap)"}


def cost_ledger(conn) -> dict:
    """Per-stage + cumulative LLM spend: L0 framer (sentinel_candidates.cost_usd) + L1 council
    (council_proposals.cost_usd). The cost-as-argument lens (SPEC §4)."""
    framer = float(_scalar(conn, "SELECT COALESCE(SUM(cost_usd),0) FROM sentinel_candidates WHERE cost_usd IS NOT NULL") or 0.0)
    council = float(_scalar(conn, "SELECT COALESCE(SUM(cost_usd),0) FROM council_proposals WHERE cost_usd IS NOT NULL") or 0.0)
    return {"l0_framer_usd": round(framer, 4), "l1_council_usd": round(council, 4),
            "cumulative_usd": round(framer + council, 4)}


# ── D · market context (DB-only, NO-FETCH) ──────────────────────────────────────────────────────
def market_context(conn) -> dict:
    """Per-position option mark÷entry (the ROBUST live "is the thesis playing out" signal) + universe IV/RV-skew
    regime (re-lens convexity_eval). Distance-to-strike from the cached snapshot is DEFERRED (caveated: a dormant
    name's spot lags; needs cache parsing) — mark÷entry is the robust one."""
    positions = []
    for r in conn.execute(
        "SELECT symbol, contract_symbol, dte, moneyness, entry_premium_per_contract AS entry, mark, marked_at, opened_at "
        "FROM convexity_positions WHERE status IN ('open','closing') ORDER BY id"
    ):
        # mark is per-SHARE, entry_premium_per_contract is per-contract dollars (=per-share·100):
        # the live multiple = (mark·100) / entry_per_contract.
        mult = (float(r["mark"]) * 100.0 / float(r["entry"])) if (r["mark"] is not None and r["entry"]) else None
        positions.append({"symbol": r["symbol"], "contract": r["contract_symbol"], "dte": r["dte"],
                          "moneyness": r["moneyness"], "mark_over_entry": None if mult is None else round(mult, 3),
                          "marked_at": r["marked_at"]})
    iv = [float(r["iv_rv"]) for r in conn.execute("SELECT iv_rv FROM convexity_eval WHERE iv_rv IS NOT NULL")]
    skew = [float(r["otm_skew"]) for r in conn.execute("SELECT otm_skew FROM convexity_eval WHERE otm_skew IS NOT NULL")]

    def _dist(xs):
        if not xs:
            return {"n": 0}
        return {"n": len(xs), "p50": round(float(np.percentile(xs, 50)), 3),
                "p90": round(float(np.percentile(xs, 90)), 3), "max": round(max(xs), 3)}

    return {"open_positions": positions, "universe_iv_rv": _dist(iv), "universe_otm_skew": _dist(skew)}


# ── scanning / sentinels / positions / council / curation / data ────────────────────────────────
def sentinels_panel(conn) -> dict:
    """Active sentinels (ranked), recent controls, recent DISCOVERY runs, framer verdicts + markers."""
    active = [dict(r) for r in state.active_sentinel_rows(conn)]
    controls = _rows(conn, "SELECT symbol, direction, basket, discovered_at FROM sentinel_candidates "
                           "WHERE kind='control' ORDER BY id DESC LIMIT 20")
    dormant = int(_scalar(conn, "SELECT COUNT(*) FROM sentinel_candidates WHERE kind='sentinel' AND status='dormant'") or 0)
    runs = _rows(conn, "SELECT id, started_at, frame_version FROM runs WHERE mode='DISCOVERY' ORDER BY id DESC LIMIT 10")
    return {"active": active, "active_n": len(active), "controls": controls, "dormant": dormant, "discovery_runs": runs}


def _book_table(conn, sql: str, params: tuple = ()) -> list[dict]:
    return _rows(conn, sql, params)


def positions_panel(conn, *, stale_pending_cycles: int = 6) -> dict:
    """All 5 books — open + recent closed. Surfaces pending/closing distinctly + STALE-PENDING (a resting limit
    unfilled across many cycles = the v2 analog of a missed order; a dedicated queue is unbuilt in v2)."""
    real_open = _book_table(conn, "SELECT p.id, p.symbol, p.direction, p.contract_symbol, p.status, p.dte, "
                                  "p.contracts, p.total_premium, p.mark, p.marked_at, p.opened_at, p.theme, "
                                  "cp.run_id AS origin_run, cp.conviction AS origin_conviction "
                                  "FROM convexity_positions p LEFT JOIN council_proposals cp "
                                  "ON p.proposal_id = cp.id WHERE p.status IN ('open','closing','pending') "
                                  "ORDER BY p.id DESC")
    real_closed = _book_table(conn, "SELECT id, symbol, direction, status, total_premium, realized_pnl, "
                                    "exit_reason, closed_at FROM convexity_positions WHERE status='closed' "
                                    "ORDER BY closed_at DESC LIMIT 25")
    pending = _book_table(conn, "SELECT id, symbol, opened_at FROM convexity_positions WHERE status='pending'")
    return {
        "real_open": real_open,
        "real_closed": real_closed,
        "pending": pending,
        "stale_pending_cycles": stale_pending_cycles,
        "shadow_open": _book_table(conn, "SELECT id, origin, symbol, direction, contracts, total_premium, mark, opened_at "
                                         "FROM shadow_positions WHERE status='open' ORDER BY id DESC"),
        "nogate_3A_open": _book_table(conn, "SELECT id, origin, symbol, direction, total_premium, opened_at "
                                            "FROM fixed_basket_positions WHERE status='open' AND book='union_nogate' ORDER BY id DESC"),
        "nogate_3B_open": _book_table(conn, "SELECT id, origin, symbol, direction, total_premium, opened_at "
                                            "FROM fixed_basket_positions WHERE status='open' AND book='basket_nogate' ORDER BY id DESC"),
        "shares": _book_table(conn, "SELECT id, basket, symbol, direction, entry_spot, entry_at "
                                    "FROM shares_positions ORDER BY id DESC LIMIT 50"),
        "counts": {"real": state.count_open_convexity_positions(conn),
                   "shadow": state.count_open_shadow_positions(conn)},
    }


def recent_council_health(conn, n: int = RECENT_COUNCIL_N) -> list[dict]:
    """Trailing window of COUNCIL-deliberated runs (``council_health`` stamped — NOT the L2 monitor passes,
    which never stamp a health), OLDEST→NEWEST so ``window[-1]`` is the latest. The SINGLE source for the
    Health strip, T4 cond-1, and ``council_panel.by_provider`` — so they can't disagree at a glance. Per run:
    ``run_id``, ``started_at``, the stamped ``council_health``, the richer ``council_l1_health`` round-trip
    ``verdict`` (the stamp is proposer-parse-only and can read 'ok' on a DEGRADED run), the proposer
    parse-rate, and per-provider parse counts in the SAME shape ({calls, parse_error, parse_error_rate})."""
    rows = conn.execute(
        "SELECT id, started_at, council_health FROM runs WHERE council_health IS NOT NULL "
        "ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    out: list[dict] = []
    for r in reversed(rows):  # oldest → newest, so window[-1] is the latest run
        rid = r["id"]
        by_provider: dict[str, dict] = {}
        for a in conn.execute(
            "SELECT ao.provider AS provider, ao.raw AS raw FROM council_agent_outputs ao "
            "JOIN council_proposals cp ON cp.id = ao.proposal_id WHERE cp.run_id = ? AND ao.provider IS NOT NULL",
            (rid,)):
            slot = by_provider.setdefault(a["provider"], {"calls": 0, "parse_error": 0})
            slot["calls"] += 1
            slot["parse_error"] += 1 if state._is_parse_error(a["raw"]) else 0
        for p in by_provider.values():
            p["parse_error_rate"] = round(p["parse_error"] / p["calls"], 4) if p["calls"] else None
        parse = state.council_parse_health(conn, rid)
        out.append({
            "run_id": rid, "started_at": r["started_at"], "council_health": r["council_health"],
            "verdict": council_l1_health(conn, run_id=rid).get("verdict"),
            "proposer_parse_rate": round(parse["rate"], 4), "proposer_called": parse["called"],
            "proposer_parse_failed": parse["parse_failed"], "by_provider": by_provider,
        })
    return out


def council_panel(conn, config: dict) -> dict:
    """Latest L1 health verdict (REUSE council_l1_health) + per-provider parse rate scoped to the LATEST run
    (via recent_council_health — so it can't show all-time #37 contamination beside a CONFIRMED verdict) +
    the recent-runs window for the strip + model_mix + cost."""
    window = recent_council_health(conn, RECENT_COUNCIL_N)
    by_provider = window[-1]["by_provider"] if window else {}
    model_mix = _scalar(conn, "SELECT model_mix FROM runs WHERE model_mix IS NOT NULL ORDER BY id DESC LIMIT 1")
    return {"health": council_l1_health(conn), "by_provider": by_provider, "recent": window,
            "model_mix": model_mix, "cost": cost_ledger(conn)}


def latest_run_deliberation(conn) -> list[dict]:
    """The latest council run's per-name reasoning (the 'why' — bounded to the FORWARD record, no §6 backtest):
    proposer direction, adversary stance, strategist final conviction. Empty list if no council has run."""
    rid = _scalar(conn, "SELECT MAX(run_id) FROM council_proposals")
    if rid is None:
        return []
    out: list[dict] = []
    for p in conn.execute(
        "SELECT id, symbol, direction, conviction FROM council_proposals WHERE run_id = ? ORDER BY symbol", (rid,)):
        roles = {a["role"]: a for a in conn.execute(
            "SELECT role, stance, confidence FROM council_agent_outputs WHERE proposal_id = ?", (p["id"],))}
        adv = roles.get("adversary")
        out.append({
            "run_id": rid, "symbol": p["symbol"], "proposer_direction": p["direction"],
            "adversary_stance": adv["stance"] if adv else None,
            "strategist_conviction": p["conviction"],
        })
    return out


def curation_panel(conn, config: dict, market=None) -> dict:
    """The two curation reports (REUSE). Market-touching → caller passes a NO-FETCH MarketData; a cache miss
    raises CacheMiss → surfaced 'accruing' by :func:`safe`. ``market=None`` → skip (accruing)."""
    if market is None:
        return {"cluster": {"error": "no market (accruing)"}, "basket": {"error": "no market (accruing)"}}
    import basket_quality
    import cluster_diagnostic

    as_of = datetime.now(UTC)
    return {
        "cluster": cluster_diagnostic.cluster_curation_report(conn, config, as_of, market),
        "basket": basket_quality.basket_quality_report(conn, config, as_of, market),
    }


def data_gathered_panel(cache_dir: str | Path) -> dict:
    """Chain-snapshot coverage (the forward IV baseline) by listing ``<cache>/option_chain_snapshot/`` + bar
    coverage. Read-only filesystem listing; never fetches."""
    root = Path(cache_dir)
    out: dict[str, Any] = {"cache_dir": str(root), "exists": root.exists()}
    snap = root / "option_chain_snapshot"
    if snap.exists():
        files = sorted(snap.glob("*.json"))
        latest = max((f.stat().st_mtime for f in files), default=None)
        out["chain_snapshots"] = {"symbols": len(files),
                                  "latest": (datetime.fromtimestamp(latest, UTC).isoformat() if latest else None),
                                  "names": [f.stem for f in files][:50]}
    else:
        out["chain_snapshots"] = {"symbols": 0, "latest": None, "names": []}
    bars = root / "alpaca_bars"
    out["bar_coverage_symbols"] = len(list(bars.glob("*.json"))) if bars.exists() else 0
    return out


# ── the T4-readiness scoreboard (the spine) ─────────────────────────────────────────────────────
def t4_scoreboard(conn, config: dict, *, recent_council: int = RECENT_COUNCIL_N) -> dict:
    """Map the pre-committed unlock conditions → live state. ASYMMETRY IS STRUCTURAL: only (1),(3),(5) can be
    binary; (2),(4) render state with NO verdict (deferred to the blind/mature null layer + the human). (1) is
    re-derived LIVE from trailing council_health (NOT frozen — it flips if the council regresses). (3) reports
    breaches over N admissions (0/0 = vacuous, not a pass)."""
    # cond-1: censor the pre-fix parse_fail (bug) runs, then require ≥2 remaining AND all ROUNDTRIP_CONFIRMED
    # (the prereg "adversary+strategist firing, ≥2 clean L1s" + the parse-fix censoring discipline). The
    # stamped 'ok' is proposer-parse-only — a run can be 'ok'-but-DEGRADED, so we key on the round-trip verdict.
    window = recent_council_health(conn, recent_council)
    non_bug = [w for w in window if w["council_health"] != "parse_fail"]
    c1_confirmed = [w for w in non_bug if w["verdict"] == "ROUNDTRIP_CONFIRMED"]
    c1_ok = len(non_bug) >= 2 and len(c1_confirmed) == len(non_bug)
    c1_detail = " · ".join(
        f"#{w['run_id']} {w['verdict']}" + (" (pre-fix, censored)" if w["council_health"] == "parse_fail" else "")
        for w in window) or "no council runs yet"
    # Legibility: cond-1 reads NOT_OK at 3-of-4 confirmed because the rule is WHOLE-window-confirmed, NOT "≥2
    # confirmed exist" — so name what blocks it (a non-censored run that isn't a round-trip, else too-few-clean).
    c1_blockers = [f"#{w['run_id']} {w['verdict']}" for w in non_bug if w["verdict"] != "ROUNDTRIP_CONFIRMED"]
    c1_why = ("" if c1_ok
              else f"; blocked by {', '.join(c1_blockers)}" if c1_blockers
              else f"; only {len(non_bug)} clean run(s) so far (need ≥2)")

    breach = breach_audit.audit_cluster_breaches(conn, config)

    real_n = len(state.convexity_realized_multiples(conn))
    shadow_n = sum(len(v) for v in state.shadow_realized_multiples(conn).values())
    fb = state.fixed_basket_realized_multiples(conn)
    fb3a_n = len(fb.get("union_nogate", []))

    return {
        "conditions": [
            {"id": 1, "name": "council healthy (live, ≥2 round-trips confirmed)", "checkable": True,
             "verdict": "MET" if c1_ok else "NOT_OK",
             "detail": (f"need the last {recent_council} council runs ALL ROUNDTRIP_CONFIRMED "
                        f"(≥2, parse_fail censored){c1_why} — {c1_detail}")},
            {"id": 2, "name": "null reads live-plumbed (resolved counts + CIs)", "checkable": False,
             "verdict": None, "detail": f"resolved — real={real_n}, shadow={shadow_n}, 3A={fb3a_n} "
                                        "(accruing; verdict deferred to the null layer)"},
            {"id": 3, "name": "cluster-cap breach audit (zero breaches)", "checkable": True,
             "verdict": ("VACUOUS" if breach["vacuous"] else ("PASS" if breach["n_breaches"] == 0 else "BREACH")),
             "detail": f"{breach['n_breaches']} breaches over {breach['n_clustered_admissions']} clustered admissions"},
            {"id": 4, "name": "payoff shape vs calibration venture profile", "checkable": False,
             "verdict": None, "detail": f"resolved real positions={real_n} (accruing; descriptive sanity)"},
            {"id": 5, "name": "pre-T4 items (incl. this dashboard)", "checkable": True,
             "verdict": "IN_PROGRESS", "detail": "reports merged; dashboard = this surface"},
        ],
        "note": "A scoreboard, NOT a graduation verdict. Conditions 2/4 are plumbing/accruing (no checkmark); "
                "T4 is the operator's process decision (IMPLEMENTATION_PLAN.md).",
        "breach_audit": breach,
    }


GATE_FLIP_MATERIALITY_FLOOR = 0.02  # §5 amendment 2026-06-12: a flip trips only at |Δ iv/rv| ≥ this


def _gap_note_class(note: str | None) -> str:
    """Classify an OPRA ``¬structured`` row's ``note`` into the §5 coverage-gap partition class
    (#72 / the 2026-07-10 close-out). The sweep stores a CLASSIFIED prefix on a fetch error
    (``gate_dualread.classify_error_note``); a structural ``select_structure`` reason has no prefix.

      - ``entitlement`` — a subscription/permission lapse (``feeds.classify_feed_error``) ⇒ feed-wide.
      - ``transient``   — a per-name fetch blip ⇒ log/escalate.
      - ``structural``  — OPRA legitimately has no tradeable wing (``no_eligible_contract_in_tenor_window``
                          and the other selection reasons), OR an unrecognized/empty note (fail-safe:
                          an unknown absence is treated as OPRA-correct, never as a feed outage)."""
    msg = (note or "").strip().lower()
    if msg.startswith("entitlement:"):
        return "entitlement"
    if msg.startswith("transient:"):
        return "transient"
    return "structural"


def gate_dualread_report(conn, config: dict | None = None) -> dict:
    """The §5 named surface (PREREG_DATA_FEED_OPRA_SEQUENCING): per-session dual-read stats,
    both-arms coverage (a silently-empty shadow arm must not read as agreement), the rolling-5
    tripwire status against the PINNED thresholds (|Δ iv/rv| median>0.05 OR max>0.10 in ≥3 of 5;
    coverage-gap or cheap-flip in ≥2 of 5 — per the dated 2026-06-12 §5 amendment a flip COUNTS
    only when the flipped name's |Δ iv/rv| ≥ GATE_FLIP_MATERIALITY_FLOOR; sub-floor flips stay
    reported, an uncomputable delta counts fail-closed), and the disagree-veto's dated auto-lapse."""
    import statistics

    rows = _rows(conn, "SELECT run_id, symbol, feed, source, structured, iv_rv, cheap, note "
                       "FROM gate_dualread ORDER BY run_id, symbol, feed")
    sessions: dict[int, dict[str, dict[str, dict]]] = {}
    for r in rows:
        sessions.setdefault(r["run_id"], {}).setdefault(r["symbol"], {})[r["feed"]] = r
    out_sessions: list[dict] = []
    for rid, by_sym in sorted(sessions.items()):
        n = len(by_sym)
        deltas: list[float] = []
        flips: list[str] = []
        material_flips: list[str] = []
        gaps: list[str] = []
        gap_structural: list[str] = []   # §5 coverage-gap split (#72): OPRA-correct absence
        gap_transient: list[str] = []    #   per-name fetch instability
        entitlement = False              #   feed-wide OPRA-trust failure (any ¬structured note)
        opra_wing: list[str] = []        #   names with a durable OPRA wing (the debounce re-arm)
        opra_ok = ind_ok = 0
        for sym, arms in sorted(by_sym.items()):
            o, i = arms.get("opra"), arms.get("indicative")
            if o and o.get("structured"):
                opra_ok += 1
                opra_wing.append(sym)
            if i and i.get("structured"):
                ind_ok += 1
            # The §5 coverage-gap class is read off the OPRA ¬structured row's NOTE (#72 / the
            # 2026-07-10 close-out): entitlement is FEED-WIDE (a subscription lapse fails every
            # OPRA fetch — detect per session, not per name, and decoupled from the gap subset);
            # structural-absence / transient classify the GAP names (INDICATIVE structures, OPRA
            # cannot) by whether the absence is OPRA-correct vs a per-name fetch blip.
            if o is not None and not o.get("structured") and _gap_note_class(o.get("note")) == "entitlement":
                entitlement = True
            if i and i.get("structured") and (not o or not o.get("structured")):
                gaps.append(sym)  # INDICATIVE structures, OPRA cannot — the §5 coverage gap
                cls = _gap_note_class(o.get("note") if o else None)
                if cls == "transient":
                    gap_transient.append(sym)
                elif cls != "entitlement":
                    gap_structural.append(sym)  # structural / unknown ⇒ OPRA-correct absence
            if o and i and o.get("structured") and i.get("structured"):
                d = None
                if o.get("iv_rv") is not None and i.get("iv_rv") is not None:
                    d = abs(o["iv_rv"] - i["iv_rv"])
                    deltas.append(d)
                if int(o.get("cheap") or 0) != int(i.get("cheap") or 0):
                    flips.append(sym)
                    # only a MEASURED-small disagreement is exempt from the wire
                    if d is None or d >= GATE_FLIP_MATERIALITY_FLOOR:
                        material_flips.append(sym)
        out_sessions.append({
            "run_id": rid, "names": n,
            "median_d_ivrv": round(statistics.median(deltas), 4) if deltas else None,
            "max_d_ivrv": round(max(deltas), 4) if deltas else None,
            "flips": flips, "material_flips": material_flips, "coverage_gaps": gaps,
            "gap_structural": gap_structural, "gap_transient": gap_transient,
            "entitlement": entitlement, "opra_wing": opra_wing,
            "opra_coverage": round(opra_ok / n, 3) if n else None,
            "indicative_coverage": round(ind_ok / n, 3) if n else None,
        })
    last5 = out_sessions[-5:]
    delta_breaches = sum(1 for s in last5
                         if (s["median_d_ivrv"] or 0) > 0.05 or (s["max_d_ivrv"] or 0) > 0.10)
    flip_sessions = sum(1 for s in last5 if s["material_flips"])
    gap_sessions = sum(1 for s in last5 if s["coverage_gaps"])
    # The §5 coverage-gap partition (#72 / the 2026-07-10 close-out): the legacy gap wire splits by
    # breach MECHANISM. Each class trips on its OWN per-class rolling-5 count — heterogeneous reasons
    # do NOT aggregate (1 structural + 1 transient + 1 entitlement-session trips nothing on
    # absence/transient). structural-absence ⇒ feasibility page (no revert); transient ≥2/5 ⇒ per-name
    # escalate; entitlement ⇒ feed-wide hold + one page/session (no rolling threshold, never debounced).
    structural_sessions = sum(1 for s in last5 if s["gap_structural"])
    transient_sessions = sum(1 for s in last5 if s["gap_transient"])
    entitlement_sessions = sum(1 for s in last5 if s["entitlement"])
    gap_partition = {
        "window": len(last5),
        "structural_sessions": structural_sessions, "structural_tripped": structural_sessions >= 2,
        "transient_sessions": transient_sessions, "transient_escalate": transient_sessions >= 2,
        "entitlement_sessions": entitlement_sessions,
        "entitlement_active": bool(last5 and last5[-1]["entitlement"]),
    }
    until = ((config or {}).get("data_feed", {}) or {}).get("dualread_disagree_veto_until")
    veto_active = None
    if until:
        try:
            from datetime import date

            veto_active = date.today() <= date.fromisoformat(str(until))
        except ValueError:
            veto_active = False
    return {
        "sessions": out_sessions[-10:],
        "n_sessions_total": len(out_sessions),
        "tripwires": {
            "window": len(last5),
            "delta_breach_sessions": delta_breaches, "delta_tripped": delta_breaches >= 3,
            "flip_sessions": flip_sessions, "flip_tripped": flip_sessions >= 2,
            "flip_floor": GATE_FLIP_MATERIALITY_FLOOR,
            "gap_sessions": gap_sessions, "gap_tripped": gap_sessions >= 2,
        },
        "gap_partition": gap_partition,
        "disagree_veto": {"until": until, "active": veto_active},
        "note": "shadow arm = INDICATIVE; it never authorizes (veto-only, date-gated). "
                "A tripped wire ⇒ the §5 fail-closed response (investigate / revert+page).",
    }


def dualread_runtime_panel(conn, config: dict | None = None) -> dict:
    """The #72 RUNTIME view of the now-live ``dualread_executor`` — the per-class §5 VERDICT, the
    Phase-3 revert-latch state, and the page/debounce summary, made legible alongside the existing
    soak surface (which shows the rolling sessions). READ-ONLY: it derives nothing of its own; it
    SINGLE-SOURCES ``gate_dualread_report`` (the rolling-5 / gap-partition math) and runs the
    executor's PURE ``dualread_executor.evaluate`` over that report — so the dashboard shows EXACTLY
    the branch the live post-cycle hook would take (the executor's single-source-of-truth discipline,
    mirrored here). No paging, no sentinel write — observation only.

    Shape (every count hand-checked in the tests):
      • ``classes`` — the five §5 wires, each {tripped, sessions (rolling-5 count where applicable),
        pages (names on the rising edge this session), revert (does THIS class ever revert?)}. Only
        the Δ wire can revert; structural/transient/flip/entitlement never do (the safety invariant).
      • ``revert_latch`` — {enabled (``config.data_feed.dualread_revert_enabled``, Phase-3 default
        false), latched (the ``OPRA_REVERTED`` sentinel is present ⇒ next cycle forced indicative),
        authorized (Δ-tripped ∧ enabled — what the executor WOULD write), sentinel_path}.
      • ``debounce`` — the ≥4-consecutive re-arm in effect: the names PAGING this session (rising
        edge) vs SUPPRESSED (currently tripped but already alerted), per debounced class.
      • ``window`` / ``last_run`` — the rolling window length + the latest session's run_id."""
    import dualread_executor as dx

    report = gate_dualread_report(conn, config)
    verdict = dx.evaluate(report, config or {})
    tw = report.get("tripwires", {}) or {}
    gp = report.get("gap_partition", {}) or {}
    sessions = report.get("sessions", []) or []
    window = gp.get("window", tw.get("window", 0))

    # Per-class debounce split: the names that are TRIPPED in the latest session, partitioned into
    # those PAGING now (rising edge — in the executor's page set) vs SUPPRESSED (tripped but already
    # alerted under the ≥4-consecutive re-arm). Single-sourced from the report's last session + the
    # executor's page sets; no re-derivation of the rolling math.
    last = sessions[-1] if sessions else {}

    def _split(active_names: list, page_names: list) -> dict:
        active = sorted(active_names or [])
        paging = sorted(n for n in active if n in set(page_names or []))
        return {"active": active, "paging": paging,
                "suppressed": sorted(n for n in active if n not in set(page_names or []))}

    classes = {
        # the SOLE revert trigger — feed-wide |Δ iv/rv| breach (no per-name page list; it's a session wire)
        "delta": {"tripped": verdict["delta"]["tripped"], "sessions": tw.get("delta_breach_sessions"),
                  "pages": [], "revert": True},
        # material cheap-flip — investigate + page (debounced); NEVER reverts
        "material_flip": {"tripped": verdict["material_flip"]["tripped"], "sessions": tw.get("flip_sessions"),
                          "pages": verdict["material_flip"]["pages"], "revert": False},
        # coverage-gap · structural absence — feasibility page (debounced); NEVER reverts
        "gap_structural": {"tripped": verdict["gap_structural"]["tripped"], "sessions": gp.get("structural_sessions"),
                           "pages": verdict["gap_structural"]["pages"], "revert": False},
        # coverage-gap · transient — per-name page once it recurs to ≥2/5 (escalate); NEVER reverts
        "gap_transient": {"tripped": bool(gp.get("transient_escalate")), "sessions": gp.get("transient_sessions"),
                          "pages": verdict["gap_transient"]["pages"], "revert": False},
        # entitlement — feed-wide OPRA-trust failure, per-session (never debounced, never reverts)
        "entitlement": {"tripped": verdict["entitlement"]["active"], "sessions": gp.get("entitlement_sessions"),
                        "pages": [], "revert": False},
    }

    return {
        "window": window,
        "last_run": last.get("run_id"),
        "classes": classes,
        "revert_latch": {
            "enabled": verdict["delta"]["revert_enabled"],
            "latched": dx.revert_latched(),
            "authorized": verdict["delta"]["revert_authorized"],
            "sentinel_path": str(dx.REVERT_SENTINEL),
        },
        "debounce": {
            "rearm_consecutive": dx.DEBOUNCE_REARM,
            "material_flip": _split(last.get("material_flips", []), verdict["material_flip"]["pages"]),
            "gap_structural": _split(last.get("gap_structural", []), verdict["gap_structural"]["pages"]),
            "gap_transient": _split(last.get("gap_transient", []), verdict["gap_transient"]["pages"]),
        },
        "note": "Single-sources gate_dualread_report + dualread_executor.evaluate (the live hook's "
                "branch). Phase 3 (revert) is default-OFF; only the Δ wire can ever revert. "
                "Observation only — no paging, no sentinel write.",
    }
