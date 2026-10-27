"""The hub contract behind ``GET /api/hub`` (issue #357): one small, versioned status shape.

The hub (rozavala/hub) reads Dramatic Options, Real Options and Alpha the same way. ``/api/snapshot`` is ~31
UI-shaped panels (a panel change breaks the hub card); ``/api/status`` (#353) is app-shaped. This is the
hub-shaped view: ``trading`` (one verdict + why), ``market``, ``checks``, ``jobs`` (one row per systemd timer),
``book`` (frame equity + realized + unrealized) and ``versions``. ``schema`` bumps only on a BREAKING change;
adding fields is not breaking.

SAFETY — same contract as ``snapshot.py`` / ``status.py``: read-only (``dd.connect_ro``), NO-FETCH, fail-soft
(``dd.safe``), keyless, short-lived connection, nothing written. DISPLAY ONLY: it reports the kill switch and
kill rule, it never changes them. No position-level data (the book is one number), no secrets, no account ids.
UNKNOWN IS ``null`` — never ``0``, ``true`` or ``"ok"``: an unreadable check is ``ok: null`` and a blocking
unknown makes ``trading.state`` ``unknown``.

Decisions the issue left open (kept here so the contract is auditable):
  * ``market`` is ``null`` — Dramatic reports no market hours today — so ``trading.state`` is never ``closed``.
  * The cost cap is a per-run council cap, not an app-wide halt: ``blocking: false`` (a tripped cap warns, it
    does not take the app to ``blocked``).
  * A job's ``enabled`` is "the timer is armed" (systemd ``ActiveState=active``) — what actually decides
    whether it fires. PROD's installed-but-disabled timers are ``enabled: false`` / ``last_status: "idle"``,
    never ``missed``. ``missed`` needs an armed timer AND a last good run older than its cadence allows.
  * ``last_ok`` comes from the journal / the reach documents (durable), not systemd (which forgets a
    success the moment the next run fails). L2 and L1 both record a PAPER run, so ``-l2``'s ``last_ok`` is the
    latest trading-loop run of either kind (the ``cycle`` heartbeat); ``-l1``'s is the last council run.
  * A disabled L1 or L2 timer means the trading loop is not running whatever the heartbeat says, so
    ``trading.state`` is ``stopped`` (#374). The Cycle heartbeat reads ONLINE off-hours however old the last run
    is, so it alone left an inert box (PROD) reading ``on`` overnight and at weekends. A timer systemd can't
    read (``enabled: null``) falls back to the heartbeat; it never counts as disabled.
  * A unit that isn't installed (``LoadState=not-found``) is unknown — ``enabled: null``, ``last_status:
    null`` with an error — never "disabled" (#374).
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from reach import newest_week_doc  # noqa: E402

import dashboard_data as dd  # noqa: E402
from config_loader import load_config  # noqa: E402

SCHEMA = 1

# job (= systemd unit stem) -> which journal heartbeat / document says it last succeeded
JOBS: dict[str, str] = {
    "dramatic-options-l1": "council",     # the Mon–Fri 15:45 ET cycle (the only run that deliberates)
    "dramatic-options-l2": "cycle",       # the intraday monitor; the cycle heartbeat is L1 ∪ L2
    "dramatic-options-l0": "discovery",   # Sun 08:00 ET
    "dramatic-options-reach": "reach",    # Sun 09:40 ET — a weekly document, not a journal row
}
_REACH_STALE = timedelta(days=8)          # weekly + a day of slack (Persistent=false: a miss is not replayed)

_PROPS = "Id,LoadState,ActiveState,NextElapseUSecRealtime,Result"
_LOOP_JOBS = ("dramatic-options-l1", "dramatic-options-l2")   # the trading loop: entries + marks/exits


def _iso(ts: Any) -> str | None:
    """Any journal / systemd / document timestamp → ISO-8601 UTC ``…Z``, or None when absent / unparseable."""
    dt = dd._parse_dt(ts)
    return None if dt is None else dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_units(*, run: Callable = subprocess.run) -> dict[str, dict[str, str]] | None:
    """``{unit: {property: value}}`` for every job's timer + service, in ONE ``systemctl show``; ``None`` when
    systemd can't be read (CI box, no systemd, any error) — a monitoring read, it degrades, never raises."""
    units = [f"{n}.{kind}" for n in JOBS for kind in ("timer", "service")]
    try:
        out = run(["systemctl", "show", *units, f"--property={_PROPS}", "--timestamp=utc"],
                  capture_output=True, text=True, timeout=3)
    except Exception:  # noqa: BLE001 — fail-soft
        return None
    if getattr(out, "returncode", 1) != 0:
        return None
    by_unit: dict[str, dict[str, str]] = {}
    for block in str(out.stdout).split("\n\n"):
        props = dict(ln.split("=", 1) for ln in block.splitlines() if "=" in ln)
        if props.get("Id"):
            by_unit[props["Id"]] = props
    return by_unit or None


def _next_due(props: dict[str, str]) -> str | None:
    """``NextElapseUSecRealtime`` is ``Tue 2026-10-27 19:45:00 UTC`` (or empty when nothing is scheduled)."""
    raw = props.get("NextElapseUSecRealtime", "")
    parts = raw.split()
    if len(parts) >= 3 and parts[-1] == "UTC":
        return _iso(f"{parts[-3]} {parts[-2]}")
    return None


def _job_last_ok(name: str, hdr: dict, records_dir: Path) -> tuple[str | None, bool | None]:
    """``(last_ok, stale)`` for one job. ``stale`` is None when the source can't be read; a never-run job is
    ``(None, False)`` — nothing has gone quiet, it has not started."""
    key = JOBS[name]
    if key == "reach":
        doc = newest_week_doc(records_dir / "cards")
        ts = doc.get("generated") or doc.get("mtime") if doc.get("available") else None
        dt = dd._parse_dt(ts)
        return (None, False) if dt is None else (_iso(ts), datetime.now(UTC) - dt > _REACH_STALE)
    beat = hdr.get(key) if isinstance(hdr, dict) else None
    if not isinstance(beat, dict):
        return None, None
    # the heartbeat's own market-aware verdict: STALE = ran, then missed a due slot; OFFLINE = never ran
    return _iso(beat.get("at")), beat.get("status") == "STALE"


def _job(name: str, hdr: dict, units: dict | None, records_dir: Path) -> dict:
    last_ok, stale = _job_last_ok(name, hdr, records_dir)
    timer = (units or {}).get(f"{name}.timer")
    svc = (units or {}).get(f"{name}.service") or {}
    if timer is not None and timer.get("LoadState") == "not-found":
        # not installed: systemctl show still exits 0 with ActiveState=inactive — that is unknown, not disabled
        return {"name": name, "last_ok": last_ok, "last_status": None, "next_due": None, "enabled": None,
                "error": "timer not installed"}
    enabled = None if timer is None else timer.get("ActiveState") == "active"
    err: str | None = None
    if svc.get("ActiveState") in ("activating", "active", "reloading"):
        status = "running"
    elif svc.get("ActiveState") == "failed":
        status, err = "failed", f"last run failed ({svc.get('Result') or 'unknown'})"
    elif stale is None:
        status, err = None, "last run unreadable"      # unknown is null, never "ran"
    elif enabled is False:
        status = "idle"                                 # timer disabled ≠ missed
    elif stale and enabled:
        status, err = "missed", "last good run is older than its cadence"
    elif stale:                                         # enabled unknown: can't tell missed from disabled
        status, err = "idle", "timer state unreadable — cannot tell missed from disabled"
    else:
        status = "ran" if last_ok else "idle"
    return {"name": name, "last_ok": last_ok, "last_status": status,
            "next_due": _next_due(timer) if timer and enabled else None, "enabled": enabled, "error": err}


def _check(label: str, kind: str, ok: bool | None, detail: str, *, blocking: bool) -> dict:
    return {"label": label, "ok": ok, "detail": detail, "blocking": blocking, "kind": kind}


def _checks(hdr: dict, risk: dict) -> list[dict]:
    """The four contract checks. A panel that errored leaves ITS checks ``ok: null`` (unknown)."""
    h_ok = isinstance(hdr, dict) and bool(hdr) and not hdr.get("error")
    r_ok = isinstance(risk, dict) and bool(risk) and not risk.get("error")
    out: list[dict] = []

    # The kill switch is a file/env read; the journal being down doesn't make it unknowable.
    from risk import kill_switch_active
    engaged = kill_switch_active()
    out.append(_check("Kill switch", "switch", not engaged, "ENGAGED" if engaged else "off", blocking=True))

    if r_ok:
        kr = risk.get("kill_rule") or {}
        tripped = bool(kr.get("tripped"))
        bd, halt = kr.get("book_drawdown"), kr.get("drawdown_halt")
        text = (f"drawdown {bd:.1%} vs {halt:.0%} halt" if isinstance(bd, (int, float)) and isinstance(halt, (int, float))
                else "drawdown unavailable")
        if tripped:
            text = f"TRIPPED — {', '.join(kr.get('reasons') or []) or text}"
        elif not kr.get("have_marks"):
            text += " (no marks yet)"
        out.append(_check("Kill rule", "fault", not tripped, text, blocking=True))
        cc = risk.get("cost_cap") or {}
        capped, cap = bool(cc.get("tripped")), cc.get("cap_usd")
        if not cap:   # no cap configured: unknown, never a made-up "$0 cap" (#374)
            out.append(_check("Cost cap", "fault", None, "no cost cap configured", blocking=False))
        else:
            out.append(_check("Cost cap", "fault", not capped,
                              f"last council run hit the ${cap:g} cap" if capped else f"within the ${cap:g}/run cap",
                              blocking=False))
    else:
        out.append(_check("Kill rule", "fault", None, "risk panel unavailable", blocking=True))
        out.append(_check("Cost cap", "fault", None, "risk panel unavailable", blocking=False))

    beat = (hdr.get("cycle") or {}) if h_ok else {}
    if beat.get("status"):
        age = beat.get("age_hours")
        out.append(_check("Cycle", "running", beat["status"] == "ONLINE",
                          f"{beat['status']}" + ("" if age is None else f" · last run {age:g}h ago"), blocking=True))
    else:
        out.append(_check("Cycle", "running", None, "heartbeat unavailable", blocking=True))
    return out


def _trading(checks: list[dict], note: str | None, jobs: list[dict] | None = None) -> dict:
    """One verdict from the blocking checks and the loop's timers. Precedence: a deliberate stop (``off``) wins;
    then a known fault (``blocked``); then the loop's timers disabled (``stopped``, a definite fact about the loop,
    so it outranks an unreadable check); then an unreadable blocking check (``unknown``); then a stale cycle
    heartbeat (``stopped``)."""
    by = {c["label"]: c for c in checks}
    if by["Kill switch"]["ok"] is False:
        return {"state": "off", "why": "kill switch engaged"}
    if by["Kill rule"]["ok"] is False:
        return {"state": "blocked", "why": by["Kill rule"]["detail"]}
    disabled = [j["name"].removeprefix("dramatic-options-").upper() for j in jobs or []
                if j["name"] in _LOOP_JOBS and j.get("enabled") is False]
    if disabled:
        return {"state": "stopped", "why": f"timer{'s' if len(disabled) > 1 else ''} disabled: {', '.join(disabled)}"}
    unknown = [c["label"] for c in checks if c["blocking"] and c["ok"] is None]
    if unknown:
        return {"state": "unknown", "why": note or f"could not read: {', '.join(unknown)}"}
    if by["Cycle"]["ok"] is False:
        return {"state": "stopped", "why": f"trading loop not running ({by['Cycle']['detail']})"}
    return {"state": "on", "why": None}


def _book(conn, config: dict, mode: Any) -> dict:
    """Frame equity + realized + unrealized (the book's OWN journal, never the shared broker account) with its
    as-of, or ``value: null`` with the reason. One number — no position data."""
    label = f"{(mode or 'paper').lower()} book: frame equity + realized + unrealized"
    base = {"value": None, "label": label, "as_of": None}
    last_run = dd._scalar(conn, "SELECT MAX(started_at) FROM runs WHERE mode IN ('PAPER','LIVE')")
    if last_run is None:
        return {**base, "note": "no cycle has run yet"}
    frame = float((config.get("convexity_book") or {}).get("account_equity") or 0.0)
    if frame <= 0:
        return {**base, "note": "no frame equity configured"}
    pnl = dd.book_pnl(conn)
    if pnl["unmarked"]:
        return {**base, "note": f"{pnl['unmarked']} open position(s) unmarked — unrealized P&L unknown"}
    # the value is only as fresh as its OLDEST mark; with nothing open it is as fresh as the last cycle
    oldest = dd._scalar(conn, "SELECT MIN(marked_at) FROM convexity_positions "
                              "WHERE status IN ('open','closing') AND marked_at IS NOT NULL")
    return {"value": round(frame + pnl["realized_usd"] + pnl["unrealized_usd"], 2), "label": label,
            "as_of": _iso(oldest or last_run), "note": None}


def build_hub(db_path: str, db_exists: bool, *, head: str | None, records_dir: Path) -> dict:
    now = datetime.now(UTC)
    units = _read_units()
    note: str | None = None
    hdr: dict = {}
    risk: dict = {}
    book: dict
    if db_exists:
        config = load_config()
        conn = dd.connect_ro(db_path)
        try:
            # next_at is stubbed: the hub reads every timer itself in ONE systemctl call (_read_units)
            hdr = dd.safe(dd.header_status, conn, next_at=lambda _u: None)
            risk = dd.safe(dd.risk_panel, conn, config)
            book = dd.safe(_book, conn, config, hdr.get("mode") if isinstance(hdr, dict) else None)
        finally:
            conn.close()
        if isinstance(book, dict) and book.get("error"):
            book = {"value": None, "label": "book", "as_of": None, "note": "book unreadable"}
    else:
        note = "no database — set DRAMATIC_DB to the live checkout's DB"
        book = {"value": None, "label": "book", "as_of": None, "note": note}

    checks = _checks(hdr, risk)
    good_hdr = hdr if isinstance(hdr, dict) and not hdr.get("error") else {}
    jobs = [_job(n, good_hdr, units, records_dir) for n in JOBS]
    return {"schema": SCHEMA, "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "trading": _trading(checks, note, jobs), "market": None, "checks": checks,
            "jobs": jobs, "book": book, "versions": {"commit": head}}
