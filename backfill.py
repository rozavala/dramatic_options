"""Ranked backfill for an idle book — PREREG_THEMATIC_CONVEXITY §5 amendment 2026-11-03 (draft D1).

When the real book has sat mostly empty, one labelled entry per week may come from the council's own ranking of the
proposals that did not clear the floor, inside every unchanged gate and cap. This module is the deterministic part:
the trigger, the weekly quota, the ranking and the pre-stated stop rule. ``council.wiring`` asks it for candidates;
``paper_loop`` enforces the quota at entry. **Inert unless ``convexity_book.backfill.enabled`` is true** (an absent
block is off, so the code ships without moving ``frame_version``).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

log = logging.getLogger("backfill")

ORIGIN = "backfill"
_RANK = {"NEUTRAL": 0, "LOW": 1, "MODERATE": 2, "HIGH": 3, "EXTREME": 4}
_HOLDING = ("open", "closing", "closed", "pending", "carried")


@dataclass(frozen=True)
class Settings:
    empty_slots_min: int = 10
    lookback_days: int = 28
    per_week: int = 1
    candidates: int = 3
    stop_min_aged: int = 8
    stop_age_days: int = 90
    stop_excess_pp: float = 0.25


def settings(config: dict) -> Settings | None:
    """The backfill settings, or None when off (absent block, or ``enabled`` not true)."""
    b = (config.get("convexity_book") or {}).get("backfill")
    if not isinstance(b, dict) or b.get("enabled") is not True:
        return None
    d = Settings()
    return Settings(**{k: type(getattr(d, k))(b[k]) for k in d.__dataclass_fields__ if k in b})


def _dt(s) -> datetime | None:
    try:
        v = datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return v if v.tzinfo else v.replace(tzinfo=datetime.now().astimezone().tzinfo)


def _origin(rationale) -> str | None:
    try:
        r = json.loads(rationale) if isinstance(rationale, str) else (rationale or {})
    except (TypeError, ValueError):
        return None
    return r.get("origin") if isinstance(r, dict) else None


# ── trigger ───────────────────────────────────────────────────────────────────────────────────
def committed_on(conn: sqlite3.Connection, day: str) -> int:
    """Real-book slots committed at the end of ET-ish calendar ``day`` (YYYY-MM-DD): rows that held exposure or a
    working order then. A cancelled row never held exposure (a carry's filled attempt is its own row)."""
    n = 0
    for r in conn.execute("SELECT opened_at, closed_at, status FROM convexity_positions"):
        if r["status"] not in _HOLDING or str(r["opened_at"])[:10] > day:
            continue
        if r["closed_at"] and str(r["closed_at"])[:10] <= day:
            continue
        n += 1
    return n


def trigger(conn: sqlite3.Connection, cfg: Settings, *, max_open: int, now: datetime) -> tuple[bool, str]:
    """(fires, why). Fires when committed slots now AND on every day of the lookback are ≤ max_open − empty_min."""
    ceiling = max_open - cfg.empty_slots_min
    days = [(now - timedelta(days=i)).date().isoformat() for i in range(cfg.lookback_days + 1)]
    peak = max(committed_on(conn, d) for d in days)
    if peak > ceiling:
        return False, f"book not idle: peak {peak} committed in {cfg.lookback_days}d > {ceiling}"
    return True, f"book idle: peak {peak} committed in {cfg.lookback_days}d ≤ {ceiling}"


def used_this_week(conn: sqlite3.Connection, *, now: datetime) -> int:
    """Distinct backfill approvals that hold or held exposure or a working order in the trailing 7 days."""
    since = (now - timedelta(days=7)).isoformat()
    props: set = set()
    for r in conn.execute("SELECT proposal_id, status, exit_reason, rationale, opened_at FROM convexity_positions "
                          "WHERE opened_at >= ?", (since,)):
        if _origin(r["rationale"]) != ORIGIN:
            continue
        if r["status"] in _HOLDING or (r["status"] == "cancelled" and r["exit_reason"] == "carry_filled"):
            props.add(r["proposal_id"] if r["proposal_id"] is not None else f"pos{r['opened_at']}")
    return len(props)


# ── ranking ───────────────────────────────────────────────────────────────────────────────────
def criteria_true(p) -> int:
    return int(str(p.structural_vs_fad) == "structural") + int(p.under_narrated is True) + int(p.at_inflection is True)


def eligible(p) -> bool:
    """Pool rule: structural, and a real conviction (NEUTRAL = abstain / parse failure)."""
    conv = str(p.conviction or "").upper()
    return str(p.structural_vs_fad) == "structural" and _RANK.get(conv, 0) >= 1


def rank(dropped: list, *, cheap_reads: dict[str, float]) -> list:
    """Deterministic order: criteria true ↓, conviction ↓, fresh cheap IV/RV ↑ (none ⇒ last), symbol ↑."""
    def key(p):
        ivrv = cheap_reads.get(str(p.symbol).upper())
        return (-criteria_true(p), -_RANK.get(str(p.conviction or "").upper(), 0),
                (0, ivrv) if ivrv is not None else (1, 0.0), str(p.symbol).upper())
    return sorted([p for p in dropped if eligible(p)], key=key)


# ── the stop rule ─────────────────────────────────────────────────────────────────────────────
def bled_fraction(rows) -> float | None:
    """Running premium bled ÷ premium paid over ``rows`` (closed at realized, open at mark, unmarked = 0 bled)."""
    paid = bled = 0.0
    for r in rows:
        tp = float(r["total_premium"] or 0.0)
        if tp <= 0:
            continue
        paid += tp
        if r["realized_pnl"] is not None and r["status"] == "closed":
            value = tp + float(r["realized_pnl"])
        elif r["mark"] is not None:
            value = float(r["mark"]) * int(r["contracts"]) * 100.0
        else:
            value = tp
        bled += max(0.0, tp - value)
    return (bled / paid) if paid > 0 else None


def stop_status(conn: sqlite3.Connection, cfg: Settings, *, now: datetime) -> tuple[bool, str]:
    """(suspended, why) per the pre-stated stop rule."""
    cutoff = (now - timedelta(days=cfg.stop_age_days)).isoformat()
    real = conn.execute("SELECT * FROM convexity_positions WHERE status IN ('open','closing','closed') "
                        "AND opened_at <= ?", (cutoff,)).fetchall()
    bf = [r for r in real if _origin(r["rationale"]) == ORIGIN]
    if len(bf) < cfg.stop_min_aged:
        return False, f"stop rule not readable yet: {len(bf)} of {cfg.stop_min_aged} aged backfill entries"
    floor = [r for r in real if _origin(r["rationale"]) != ORIGIN]
    if len(floor) >= 3:
        comp, comp_name = bled_fraction(floor), "above-floor"
    else:
        comp = bled_fraction(conn.execute("SELECT * FROM shadow_positions WHERE opened_at <= ?", (cutoff,)).fetchall())
        comp_name = "shadow book"
    mine = bled_fraction(bf)
    if mine is None or comp is None:
        return False, "stop rule not readable: no comparator premium"
    excess = mine - comp
    if excess > cfg.stop_excess_pp:
        return True, f"SUSPENDED: backfill bled {mine:.0%} vs {comp_name} {comp:.0%} (+{excess:.0%} > {cfg.stop_excess_pp:.0%})"
    return False, f"backfill bled {mine:.0%} vs {comp_name} {comp:.0%}"


def select(conn: sqlite3.Connection, config: dict, *, dropped: list, cheap_reads: dict[str, float],
           now: datetime) -> tuple[list, str]:
    """The ranked candidates to send to the gates this L1 (possibly none) and a one-line reason for the log."""
    cfg = settings(config)
    if cfg is None:
        return [], "off"
    max_open = int((config.get("convexity_book") or {}).get("max_open_positions", 15))
    suspended, why = stop_status(conn, cfg, now=now)
    if suspended:
        try:
            import notify

            notify.send("Backfill suspended (stop rule)", why)
        except Exception:  # noqa: BLE001 — paging never breaks the cycle
            log.warning("backfill stop page failed to send")
        return [], why
    if used_this_week(conn, now=now) >= cfg.per_week:
        return [], f"weekly quota used ({cfg.per_week})"
    fires, why = trigger(conn, cfg, max_open=max_open, now=now)
    if not fires:
        return [], why
    ranked = rank(dropped, cheap_reads=cheap_reads)[: cfg.candidates]
    return ranked, f"{why}; {len(ranked)} candidate(s): {[p.symbol for p in ranked]}"


def stamp_proposal(conn: sqlite3.Connection, proposal_id: int, *, rank: int) -> None:
    """Record on the (dropped) proposal that it went to the gates as backfill candidate ``rank``. Status unchanged:
    it did not clear the floor, and the record says so; a fill links it to its position as usual."""
    row = conn.execute("SELECT rationale FROM council_proposals WHERE id = ?", (proposal_id,)).fetchone()
    try:
        rat = json.loads(row["rationale"]) if row and row["rationale"] else {}
    except (TypeError, ValueError):
        rat = {}
    rat = rat if isinstance(rat, dict) else {"raw": rat}
    rat["backfill"] = {"rank": rank}
    with conn:
        conn.execute("UPDATE council_proposals SET rationale = ? WHERE id = ?",
                     (json.dumps(rat, default=str), proposal_id))
