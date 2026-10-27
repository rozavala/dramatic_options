"""The light status read behind ``GET /api/status`` (issue #353).

``/api/snapshot`` rebuilds ~31 panels; ``/api/health`` only says the process is up. This is the middle: the
handful of facts a status read needs — the ``system_status`` verdict, the three heartbeats (age + next fire),
KILL, drawdown vs the halt, book open/max, the last council run with its ET date, the T4 verdicts and the
serving commit — from FOUR panels (``header``, ``risk``, ``council``, ``t4``) instead of 31.

SAFETY — same contract as ``snapshot.py``: read-only (``dd.connect_ro``), NO-FETCH, fail-soft (``dd.safe``),
keyless, short-lived connection. DISPLAY ONLY: it reports the kill rule's state, it never changes it.
It carries NO position data (the book is an open/max count only; no symbols, no premium) and stays well
under 5 KB — ``MAX_BYTES`` is enforced: an over-size body sheds the per-condition T4 ``detail`` text first.
"""

from __future__ import annotations

import sys
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from snapshot import to_jsonable  # noqa: E402

import dashboard_data as dd  # noqa: E402
from config_loader import load_config  # noqa: E402

# Hard ceiling the acceptance criteria set for the response body.
MAX_BYTES = 5 * 1024

_BEATS = ("cycle", "council", "discovery")


def _utc(next_at: Any) -> Any:
    """``timer_next_at`` yields ``YYYY-MM-DD HH:MM:SS`` in UTC with no zone marker; mark it ISO-8601 UTC."""
    if isinstance(next_at, str) and len(next_at) == 19 and next_at[10] == " ":
        return next_at.replace(" ", "T") + "+00:00"
    return next_at


def _beat(h: dict, key: str) -> dict:
    b = h.get(key) or {}
    return {"status": b.get("status"), "at": b.get("at"), "age_hours": b.get("age_hours"),
            "next_at": _utc(b.get("next_at"))}


def _last_council(conn) -> dict:
    """The newest council run id and the ET calendar date it ran on (the same ET-date the L1 run ids carry)."""
    rid = dd._scalar(conn, "SELECT MAX(run_id) FROM council_proposals")
    if rid is None:
        return {"run_id": None, "et_date": None}
    started = dd._scalar(conn, "SELECT started_at FROM runs WHERE id=?", (rid,))
    d = dd._et_date(started)
    return {"run_id": int(rid), "et_date": None if d is None else d.isoformat()}


def _t4(t4: Any) -> list[dict] | dict:
    if not isinstance(t4, dict) or t4.get("error"):
        return {"error": (t4 or {}).get("error", "unavailable") if isinstance(t4, dict) else "unavailable"}
    return [{"id": c.get("id"), "name": c.get("name"), "verdict": c.get("verdict"),
             "detail": _t4_detail(c)} for c in t4.get("conditions") or []]


_DETAIL_MAX = 110


def _t4_detail(c: dict) -> str:
    """A short reason line. A condition with NO verdict is deliberate (conditions 2 and 4 are descriptive and
    left to the human), so say so rather than leave a bare null that reads as missing data."""
    if c.get("verdict") is None:
        return "deferred to operator"
    d = str(c.get("detail") or "")
    return d if len(d) <= _DETAIL_MAX else d[:_DETAIL_MAX - 1].rstrip() + "…"


def build_status(db_path: str, db_exists: bool, *, head: str | None, started_at: str | None,
                 snapshot_status: dict | None = None, snapshot_as_of: str | None = None) -> dict:
    """The light status payload. ``snapshot_status`` — when a fresh full snapshot is already cached, its
    ``system_status`` is reused so level/headline are the snapshot's own by construction; otherwise
    ``dd.system_status`` runs over the four light panels (``basis`` says which). The reused verdict can be up
    to a snapshot-TTL older than the kill/heartbeat facts read here, so it is dropped (the light verdict runs
    on the fresh panels) whenever the fresh KILL switch or kill rule is set — a just-engaged KILL never sits
    under a green headline. ``system_status_as_of`` stamps when the verdict was computed."""
    now = datetime.now(UTC)
    out: dict[str, Any] = {"as_of": now.isoformat(timespec="seconds"), "commit": head, "started_at": started_at}
    if not db_exists:
        out["error"] = "no database — set DRAMATIC_DB to the live checkout's DB"
        return out
    config = load_config()
    conn = dd.connect_ro(db_path)
    try:
        snap = {
            "header": dd.safe(dd.header_status, conn),
            "risk": dd.safe(dd.risk_panel, conn, config),
            "council": dd.safe(dd.council_panel, conn, config),
            "t4": dd.safe(dd.t4_scoreboard, conn, config),
        }
        last_council = dd.safe(_last_council, conn)
    finally:
        conn.close()

    header, risk = snap["header"], snap["risk"]
    h = header if isinstance(header, dict) and not header.get("error") else {}
    r = risk if isinstance(risk, dict) and not risk.get("error") else {}
    kr, bk = r.get("kill_rule") or {}, r.get("book") or {}

    if snapshot_status is not None and not (h.get("kill_switch_engaged") or kr.get("tripped")):
        status, basis, status_as_of = snapshot_status, "snapshot", snapshot_as_of
    else:
        status, basis, status_as_of = dd.safe(dd.system_status, snap), "light", out["as_of"]

    out.update({
        "system_status": status,
        "system_status_as_of": status_as_of,
        "basis": basis,
        "mode": h.get("mode"),
        "heartbeats": {k: _beat(h, k) for k in _BEATS},
        "kill": {"switch_engaged": h.get("kill_switch_engaged"), "rule_tripped": kr.get("tripped")},
        "drawdown": {"book_drawdown": kr.get("book_drawdown"), "halt": kr.get("drawdown_halt"),
                     "have_marks": kr.get("have_marks")},
        "book": {"open": bk.get("open"), "max": bk.get("max")},
        "last_council": last_council,
        "t4": _t4(snap["t4"]),
    })
    body = to_jsonable(out)
    if len(json.dumps(body).encode()) > MAX_BYTES:
        if isinstance(body["t4"], list):
            body["t4"] = [{k: v for k, v in c.items() if k != "detail"} for c in body["t4"]]
    return body
