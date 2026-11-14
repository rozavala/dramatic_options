"""#456 council repeat-read probe, Arm A (PREREG_COUNCIL_GATE_SEPARATION §10.12;
records/2026-11-14_council_repeat_probe_armA_PREREG.md).

After the L1 has finished, a SEPARATE process (``python -m orchestrator --repeat-probe``, the
``dramatic-options-repeat-probe`` unit) re-asks the **strategist only** k times per name, on the same night's
captured ``ContextPack`` (``council_repeat_packs``), the stored proposer and adversary outputs
(``council_agent_outputs.raw``) and the recorded presentation order (``council_proposals.rationale["order"]``), with
the record's post-processing (``council.debate.strategist_verdict``: the same quote filter + the shared §10.7
coercion). It measures the strategist's run-to-run agreement with its own verdict of record, evidence drift excluded.

MEASUREMENT ONLY. Writes ``council_repeat_reads`` / ``council_repeat_sessions`` and nothing else: never
``council_proposals`` or ``council_agent_outputs`` (Brier, contribution scoring, the persistence count and the forward
record are untouched). It never selects, enters, sizes, holds or exits anything (prereg §8).

Refusals (each one log line; the disabled refusal is a quiet INFO, exit 0):
- KILL engaged; ``council.repeat_probe.enabled`` false; before ``segment_start_et`` (ET date);
- the segment is complete (``sessions`` sessions with a probed name — whatever the flag says) or was stopped by a
  ``runs.model_mix`` change (the stop is recorded and permanent);
- no council of record today, or today's L1 has not finished (see ``l1_finished``), or this run was already probed;
- the strategist the probe would call (config role + system-prompt hash) is not the one of record;
- the segment cap is spent, or the strategist provider's month-to-date spend (council + probe) plus this session's
  estimate reaches ``page_refusal_fraction`` × ``monthly_spend_page_usd[provider]``.

Caps: the probe builds its OWN router on its OWN ``CostLedger`` (cap = min(per-session cap, segment remaining)); over
it the session stops (``BudgetExceeded``), fail-closed on the probe only. The L1 is never affected.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import sqlite3
import subprocess
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import state
from clock import et_date
from council import agents
from council.debate import _parsed, strategist_verdict
from council.proposal import normalize_conviction
from council.repeat_capture import pack_from_json, prompt_sha256
from council.router import BudgetExceeded, CostLedger, RouterError

log = logging.getLogger("council.repeat_probe")

L1_UNIT = "dramatic-options-l1.service"
SPEND_PAGE_LINE = 0.8   # the L1 tripwire's crossing line (orchestrator._stamp_council_health), mirrored for the probe
_RUNNING_STATES = frozenset({"active", "activating", "deactivating", "reloading", "refreshing"})
_TS = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")

DEFAULTS = {"enabled": False, "k": 5, "sessions": 10, "segment_start_et": "2026-12-07", "cap_session_usd": 1.5,
            "cap_total_usd": 15.0, "page_refusal_fraction": 0.8}


@dataclass
class ProbeOutcome:
    """What one invocation did. ``status`` is ``refused`` or the session's final status."""

    status: str
    reason: str = ""
    run_id: int | None = None
    names_captured: int = 0
    names_probed: int = 0
    repeats: int = 0
    excluded: dict = field(default_factory=dict)
    skipped: dict = field(default_factory=dict)
    cost_usd: float = 0.0


@dataclass
class _Name:
    proposal_id: int
    symbol: str
    pack: object
    praw: dict
    araw: dict
    for_first: bool
    order: str
    prompt_sha256: str
    user: str
    record_cost: float


def settings(config: dict) -> dict:
    """``council.repeat_probe`` over the defaults (``_comment`` keys ignored)."""
    cfg = ((config.get("council", {}) or {}).get("repeat_probe") or {})
    return {**DEFAULTS, **{k: v for k, v in cfg.items() if not str(k).startswith("_")}}


# ── "today's L1 has finished" ────────────────────────────────────────────────────────────────────────────────────
def read_unit_state(unit: str = L1_UNIT, *, run: Callable = subprocess.run) -> tuple[str, str | None] | None:
    """``(ActiveState, ExecMainExitTimestamp as 'YYYY-MM-DD HH:MM:SS' UTC or None)`` from systemd, or None when
    systemd cannot be read (no systemctl, an error, a non-zero exit) — which ``l1_finished`` treats as NOT finished."""
    try:
        out = run(["systemctl", "show", unit, "--property=ActiveState,ExecMainExitTimestamp", "--timestamp=utc"],
                  capture_output=True, text=True, timeout=5)
    except Exception:  # noqa: BLE001 — unreadable ⇒ not finished (fail-closed on the probe)
        return None
    if getattr(out, "returncode", 1) != 0:
        return None
    props = dict(ln.split("=", 1) for ln in str(out.stdout).splitlines() if "=" in ln)
    m = _TS.search(props.get("ExecMainExitTimestamp", "") or "")
    return props.get("ActiveState", ""), (m.group(1) if m else None)


def l1_finished(run_started_at: str, unit_state: tuple[str, str | None] | None) -> tuple[bool, str]:
    """Today's L1 has finished iff its run row exists (the caller found it), the L1 unit is not running, and the unit's
    main process exited AT OR AFTER that run started (so the exit is that run's, not yesterday's). ``runs`` has no
    completion column; the unit's exit is the only signal that entries are done (the issue: "never before entries"),
    the same one ``scripts/ops/scheduled_review.sh`` waits on. Unreadable systemd ⇒ not finished."""
    if unit_state is None:
        return False, "L1 unit state unreadable (systemctl)"
    active, exited = unit_state
    if active in _RUNNING_STATES:
        return False, f"L1 unit is {active}"
    if not exited:
        return False, "L1 unit has no exit timestamp"
    if exited < str(run_started_at)[:19]:
        return False, f"L1 unit last exited {exited} UTC, before run started {run_started_at}"
    return True, f"L1 exited {exited} UTC"


# ── DB reads ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _tables_present(conn: sqlite3.Connection) -> bool:
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {"council_repeat_packs", "council_repeat_reads", "council_repeat_sessions"} <= names


def counted_sessions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Sessions that count toward the segment length: those with ≥1 name holding ≥1 repeat that counts toward
    agreement (not excluded). Oldest first; the first one anchors the segment's model_mix."""
    return conn.execute(
        "SELECT s.* FROM council_repeat_sessions s WHERE EXISTS ("
        " SELECT 1 FROM council_repeat_reads r WHERE r.session_id = s.id AND r.excluded_reason IS NULL)"
        " ORDER BY s.id").fetchall()


def segment_spend(conn: sqlite3.Connection) -> float:
    row = conn.execute("SELECT SUM(cost_usd) FROM council_repeat_reads").fetchone()
    return float(row[0] or 0.0)


def todays_l1_run(conn: sqlite3.Connection, today: date) -> sqlite3.Row | None:
    """The latest run that holds a council of record judged on ET date ``today`` (``council_proposals.as_of`` is the
    L1 clock's ISO timestamp)."""
    from datetime import datetime

    rows = conn.execute(
        "SELECT cp.run_id AS run_id, MAX(cp.as_of) AS as_of FROM council_proposals cp "
        "WHERE cp.run_id IS NOT NULL GROUP BY cp.run_id ORDER BY cp.run_id DESC LIMIT 20").fetchall()
    for r in rows:
        try:
            if et_date(datetime.fromisoformat(r["as_of"])) == today:
                return conn.execute("SELECT * FROM runs WHERE id = ?", (r["run_id"],)).fetchone()
        except (TypeError, ValueError):
            continue
    return None


def _json(text) -> dict:
    try:
        v = json.loads(text) if isinstance(text, str) else (text or {})
        return v if isinstance(v, dict) else {}
    except (TypeError, ValueError):
        return {}


def strategist_prompt_hash16() -> str:
    """The strategist component of the L1's ``model_mix["prompts"]`` stamp (sha256[:16] of STRATEGIST_SYSTEM)."""
    return hashlib.sha256(agents.STRATEGIST_SYSTEM.encode()).hexdigest()[:16]


def _eligible_names(conn: sqlite3.Connection, run_id: int, primary: str, skipped: Counter) -> tuple[list[_Name], int]:
    """The captured names with a strategist verdict of record, rebuilt and hash-verified. Returns (names, captured).
    Skips, counted by reason: a record answered by the understudy or ending in parse_error (no verdict of the probed
    model to agree with), missing stored inputs, an undecodable pack, a rebuilt prompt whose hash differs."""
    caps = conn.execute(
        "SELECT * FROM council_repeat_packs WHERE run_id = ? ORDER BY proposal_id", (run_id,)).fetchall()
    out: list[_Name] = []
    for c in caps:
        pid = int(c["proposal_id"])
        aos = {r["role"]: r for r in conn.execute(
            "SELECT role, provider, model, raw, cost_usd FROM council_agent_outputs WHERE proposal_id = ? "
            "ORDER BY id", (pid,))}
        srow = aos.get("strategist")
        if srow is None:
            skipped["no_strategist_record"] += 1
            continue
        if f"{srow['provider']}/{srow['model']}" != primary:
            skipped["record_understudy"] += 1
            continue
        if _json(srow["raw"]).get("parse_error"):
            skipped["record_parse_error"] += 1
            continue
        prop = conn.execute("SELECT rationale FROM council_proposals WHERE id = ?", (pid,)).fetchone()
        order = _json(prop["rationale"] if prop else None).get("order")
        if "proposer" not in aos or "adversary" not in aos or order not in ("for_first", "against_first"):
            skipped["missing_inputs"] += 1
            continue
        try:
            pack = pack_from_json(c["pack_json"])
        except Exception:  # noqa: BLE001 — an undecodable capture is skipped, counted
            skipped["pack_decode_error"] += 1
            continue
        praw, araw = _json(aos["proposer"]["raw"]), _json(aos["adversary"]["raw"])
        for_first = order == "for_first"
        _sys, user = agents.strategist_prompt(pack, praw, araw, for_first=for_first)
        if prompt_sha256(user) != c["prompt_sha256"]:
            skipped["hash_mismatch"] += 1
            continue
        out.append(_Name(pid, str(c["symbol"]), pack, praw, araw, for_first, order, str(c["prompt_sha256"]), user,
                         float(srow["cost_usd"] or 0.0)))
    return out, len(caps)


# ── DB writes (the probe's own tables only) ──────────────────────────────────────────────────────────────────────
def _insert_session(conn, *, run_id: int, today: date, model_mix: str | None, status: str, k: int, now) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO council_repeat_sessions (run_id, session_date_et, model_mix, status, k, names_captured, "
            "names_probed, repeats, summary, cost_usd, started_at) VALUES (?, ?, ?, ?, ?, 0, 0, 0, '{}', 0.0, ?)",
            (run_id, today.isoformat(), model_mix, status, k, state.sql_utc(now)))
    return int(cur.lastrowid)


def _finish_session(conn, session_id: int, o: ProbeOutcome, now) -> None:
    with conn:
        conn.execute(
            "UPDATE council_repeat_sessions SET status = ?, names_captured = ?, names_probed = ?, repeats = ?, "
            "summary = ?, cost_usd = ?, finished_at = ? WHERE id = ?",
            (o.status, o.names_captured, o.names_probed, o.repeats,
             json.dumps({"excluded": o.excluded, "skipped": o.skipped}, sort_keys=True), o.cost_usd,
             state.sql_utc(now), session_id))


def _bool_or_none(v) -> int | None:
    return int(v) if isinstance(v, bool) else None


def _write_read(conn, *, session_id: int, run_id: int, n: _Name, idx: int, resp, sraw: dict | None, conviction,
                flagged: int | None, excluded: str | None, now) -> None:
    sraw = sraw or {}
    with conn:
        conn.execute(
            "INSERT INTO council_repeat_reads (session_id, run_id, proposal_id, symbol, repeat_idx, provider, model, "
            "raw, raw_confidence, conviction, include, structural_vs_fad, under_narrated, at_inflection, "
            "criteria_veto, flagged_unsupported, order_shown, prompt_sha256, cost_usd, excluded_reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, run_id, n.proposal_id, n.symbol, idx,
             getattr(resp, "provider", None), getattr(resp, "model", None),
             json.dumps(sraw, default=str) if resp is not None else None,
             (str(sraw.get("conviction")) if sraw.get("conviction") is not None else None),
             conviction,
             (int(bool(sraw.get("include", False))) if resp is not None else None),
             ((sraw.get("structural_vs_fad") or n.praw.get("structural_vs_fad")) if resp is not None else None),
             _bool_or_none(sraw.get("under_narrated")), _bool_or_none(sraw.get("at_inflection")),
             (int(bool(sraw.get("criteria_veto", False))) if resp is not None else None),
             flagged, n.order, n.prompt_sha256, float(getattr(resp, "cost_usd", 0.0) or 0.0), excluded,
             state.sql_utc(now)))


# ── the probe ────────────────────────────────────────────────────────────────────────────────────────────────────
def strategist_only_config(config: dict) -> dict:
    """A config copy whose council maps ONLY the strategist (and its understudy): the probe's router can call nothing
    else and needs no proposer/adversary key."""
    cfg = copy.deepcopy(config)
    council = cfg.setdefault("council", {})
    council["roles"] = {"strategist": dict((council.get("roles") or {}).get("strategist") or {})}
    fb = (council.get("roles_fallback") or {}).get("strategist")
    council["roles_fallback"] = {"strategist": dict(fb)} if fb else {}
    return cfg


def _refuse(reason: str, *, level: int = logging.INFO, **kw) -> ProbeOutcome:
    log.log(level, "Repeat probe: not run — %s", reason)
    return ProbeOutcome(status="refused", reason=reason, **kw)


def run_probe(conn: sqlite3.Connection, *, config: dict, clock, router_factory: Callable,
              unit_state: Callable[[], tuple[str, str | None] | None] = read_unit_state,
              notify_send: Callable | None = None) -> ProbeOutcome:
    """One probe invocation for today's L1 (ET date). ``router_factory(config, ledger) -> router`` builds the probe's
    OWN strategist router on its OWN ledger. Never raises for a refusal; an unexpected error propagates to ``main``."""
    from risk import kill_switch_active

    if kill_switch_active():
        return _refuse("KILL switch engaged (no LLM spend)")
    s = settings(config)
    if not bool(s["enabled"]):
        return _refuse("council.repeat_probe.enabled is false")
    now = clock.now()
    today = et_date(now)
    if today < date.fromisoformat(str(s["segment_start_et"])):
        return _refuse(f"before the segment start {s['segment_start_et']} (today ET {today})")
    if not _tables_present(conn):
        return _refuse("probe tables missing (migration 0022 not applied)", level=logging.WARNING)
    stopped = conn.execute(
        "SELECT run_id, session_date_et FROM council_repeat_sessions WHERE status = 'stopped_model_mix' "
        "ORDER BY id LIMIT 1").fetchone()
    counted = counted_sessions(conn)
    if stopped is not None:
        return _refuse(f"segment stopped on a model_mix change at run #{stopped['run_id']} "
                       f"({stopped['session_date_et']}); partial segment of {len(counted)} session(s)")
    if len(counted) >= int(s["sessions"]):
        return _refuse(f"segment complete ({len(counted)}/{int(s['sessions'])} sessions)")

    run = todays_l1_run(conn, today)
    if run is None:
        return _refuse(f"no council of record for {today} ET")
    run_id = int(run["id"])
    if not run["model_mix"]:
        return _refuse(f"L1 run #{run_id} has no model_mix stamp (council did not complete)",
                       level=logging.WARNING, run_id=run_id)
    done, why = l1_finished(run["started_at"], unit_state())
    if not done:
        return _refuse(f"today's L1 (run #{run_id}) has not finished: {why}", level=logging.WARNING, run_id=run_id)
    if conn.execute("SELECT 1 FROM council_repeat_sessions WHERE run_id = ?", (run_id,)).fetchone():
        return _refuse(f"run #{run_id} already probed", run_id=run_id)

    mix = _json(run["model_mix"])
    if counted:
        anchor = _json(counted[0]["model_mix"])
        if mix != anchor:
            _insert_session(conn, run_id=run_id, today=today, model_mix=run["model_mix"],
                            status="stopped_model_mix", k=int(s["k"]), now=now)
            changed = sorted(k for k in set(mix) | set(anchor) if mix.get(k) != anchor.get(k))
            log.warning("Repeat probe: SEGMENT STOPPED — runs.model_mix of run #%d differs from the segment's first "
                        "session (run #%s) on %s; partial segment of %d session(s), reported as such.",
                        run_id, counted[0]["run_id"], changed, len(counted))
            return ProbeOutcome(status="stopped_model_mix", reason=f"model_mix changed: {changed}", run_id=run_id)

    roles = (config.get("council", {}) or {}).get("roles") or {}
    sspec = roles.get("strategist") or {}
    primary = f"{sspec.get('provider')}/{sspec.get('model')}"
    provider = str(sspec.get("provider"))
    if mix.get("strategist") != primary:
        return _refuse(f"configured strategist {primary} is not the record's {mix.get('strategist')}",
                       level=logging.WARNING, run_id=run_id)
    prompts = str(mix.get("prompts") or "").split("/")
    if len(prompts) != 3 or prompts[2] != strategist_prompt_hash16():
        return _refuse("the strategist system prompt differs from the record's (model_mix.prompts)",
                       level=logging.WARNING, run_id=run_id)

    skipped: Counter = Counter()
    names, captured = _eligible_names(conn, run_id, primary, skipped)
    if not names:
        return _refuse(f"nothing to probe for run #{run_id} (captured={captured}, skipped={dict(skipped)})",
                       run_id=run_id, names_captured=captured, skipped=dict(skipped))

    k = int(s["k"])
    remaining = float(s["cap_total_usd"]) - segment_spend(conn)
    if remaining <= 0:
        return _refuse(f"segment cap ${float(s['cap_total_usd']):.2f} spent", level=logging.WARNING, run_id=run_id)
    page_cap = ((config.get("council", {}) or {}).get("monthly_spend_page_usd") or {}).get(provider)
    if page_cap is None:
        return _refuse(f"no council.monthly_spend_page_usd for {provider} (refusal rule unevaluable)",
                       level=logging.WARNING, run_id=run_id)
    mtd_before = state.provider_month_spend(conn, provider, now=now)
    estimate = k * sum(n.record_cost for n in names)
    line = float(s["page_refusal_fraction"]) * float(page_cap)
    if mtd_before + estimate >= line:
        return _refuse(f"{provider} MTD ${mtd_before:.2f} + session estimate ${estimate:.2f} >= "
                       f"{float(s['page_refusal_fraction']):.0%} of the ${float(page_cap):.2f} page",
                       level=logging.WARNING, run_id=run_id)

    session_cap = min(float(s["cap_session_usd"]), remaining)
    cap_kind = "stopped_session_cap" if float(s["cap_session_usd"]) <= remaining else "stopped_segment_cap"
    try:
        router = router_factory(strategist_only_config(config), CostLedger(cap_usd=session_cap))
    except RouterError as e:
        return _refuse(f"probe router unavailable: {e}", level=logging.WARNING, run_id=run_id)

    try:
        session_id = _insert_session(conn, run_id=run_id, today=today, model_mix=run["model_mix"], status="running",
                                     k=k, now=now)
    except sqlite3.IntegrityError:
        return _refuse(f"run #{run_id} already probed (concurrent)", run_id=run_id)

    o = ProbeOutcome(status="done", run_id=run_id, names_captured=captured, skipped=dict(skipped))
    excluded: Counter = Counter()
    probed: set[int] = set()
    for n in names:
        if o.status != "done":
            break
        for idx in range(k):
            try:
                resp = router.call(role="strategist", system=agents.STRATEGIST_SYSTEM, user=n.user)
            except BudgetExceeded as e:
                o.status, o.reason = cap_kind, str(e)
                break
            except RouterError as e:
                _write_read(conn, session_id=session_id, run_id=run_id, n=n, idx=idx, resp=None, sraw=None,
                            conviction=None, flagged=None, excluded="provider_error", now=clock.now())
                excluded["provider_error"] += 1
                o.repeats += 1
                o.status, o.reason = "stopped_provider_error", str(e)
                break
            sraw = _parsed("strategist", resp, agents.parse_strategist, n.symbol)
            sconf, sfr = strategist_verdict(sraw, n.praw, n.pack, n.symbol)
            reason = ("understudy" if f"{resp.provider}/{resp.model}" != primary
                      else "parse_error" if sraw.get("parse_error") else None)
            if reason:
                excluded[reason] += 1
            _write_read(conn, session_id=session_id, run_id=run_id, n=n, idx=idx, resp=resp, sraw=sraw,
                        conviction=normalize_conviction(sconf), flagged=sfr.flagged, excluded=reason,
                        now=clock.now())
            if not reason:  # "probed" = at least one COUNTED repeat, the report's definition (#456 review S2)
                probed.add(n.proposal_id)
            o.repeats += 1
    o.names_probed = len(probed)
    o.excluded = dict(excluded)
    o.cost_usd = router.ledger.total_usd
    _finish_session(conn, session_id, o, clock.now())

    session_no = len(counted_sessions(conn))
    log.info("Repeat probe run #%d (%s ET): status=%s names probed=%d/%d captured (skipped %s), repeats=%d "
             "(k=%d), excluded %s, cost $%.4f (session cap $%.2f), segment %d/%d sessions, $%.2f/$%.2f%s",
             run_id, today, o.status, o.names_probed, captured, dict(skipped) or "none", o.repeats, k,
             dict(excluded) or "none", o.cost_usd, session_cap, session_no, int(s["sessions"]),
             segment_spend(conn), float(s["cap_total_usd"]), f" — {o.reason}" if o.reason else "")
    if o.status != "done":
        log.warning("Repeat probe stopped early (%s): %s", o.status, o.reason)

    # The monthly page sees the probe (prereg §7): page on the crossing, like the L1's tripwire, if this session's
    # actual spend (not its estimate) carried MTD over the 80% line.
    mtd_after = state.provider_month_spend(conn, provider, now=clock.now())
    page_line = SPEND_PAGE_LINE * float(page_cap)
    if mtd_before < page_line <= mtd_after:
        log.warning("Council spend tripwire: %s MTD $%.2f crossed 80%% of $%.2f/mo (repeat probe).",
                    provider, mtd_after, float(page_cap))
        send = notify_send
        if send is None:
            import notify

            send = notify.send
        send("Council spend tripwire",
             f"{provider} spend ${mtd_after:.2f} MTD (council + repeat probe) crossed 80% of the "
             f"${float(page_cap):.2f}/mo budget. If the key is shared, check the provider console's own limit too.")
    return o


def _live_router(config: dict, ledger: CostLedger):
    from council.router import build_router

    return build_router(config, config.get("llm_keys", {}), ledger=ledger)


def main() -> int:
    """``python -m orchestrator --repeat-probe``: one probe invocation against the live DB. Exit 0 for a probe that ran
    or refused (refusals are log lines, never a page); 1 only on an unexpected error (the unit's OnFailure pages)."""
    from clock import LiveClock
    from config_loader import load_config

    try:
        config = load_config()
        if not bool(settings(config)["enabled"]):    # the quiet path: no DB, no network
            _refuse("council.repeat_probe.enabled is false")
            return 0
        conn = state.get_db(config)
    except Exception:  # noqa: BLE001 — the probe's own failure; the L1 is a different process
        log.exception("Repeat probe failed before starting")
        return 1
    try:
        run_probe(conn, config=config, clock=LiveClock(), router_factory=_live_router)
        return 0
    except Exception:  # noqa: BLE001 — measurement only: report loudly, never retry or touch the record
        log.exception("Repeat probe failed")
        return 1
    finally:
        conn.close()
