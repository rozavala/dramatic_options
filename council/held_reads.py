"""#464 held-name thesis tracking, Option B (PREREG_COUNCIL_GATE_SEPARATION §10.13;
records/2026-11-16_held_name_thesis_tracking_optionB_PREREG.md).

Held names cannot re-surface (``run_discover`` excludes open positions from the scan), so their lineages go dormant
and the council stops reading them. After each L1 has finished, this pass (``python -m orchestrator --post-l1``, after
the §10.12 repeat probe) runs the full debate ONCE for every real position with status ``open``/``closing`` and a
``proposal_id``:

- the candidate is built from the position's OWN lineage: the entry proposal's sentinel row via
  ``sentinels.discovered_to_theme`` (active or dormant — rendered as-is, no "dormant" label), or, for a hand-seed, its
  ``themes.json`` entry by (symbol, direction), active or not;
- its markers are refreshed by the L1's own ``orchestrator._refresh_council_markers`` (``run_id=None``: no run note);
- the pack is ``council.council.council_pack`` — the one construction the L1's ``propose`` uses — with the same
  news / fundamentals / analyst / catalyst providers (``orchestrator._build_council_io``) and the L1 council's as_of.
  The providers are built with a clock whose ``now()`` IS that as_of, so every provider's fetch_end equals the pack's
  as_of. (The analyst meter stamps its snapshot at fetch_end and reads at ``min(as_of, fetch_end)``: built at the
  pass's own 16:10 time it would find nothing at the 15:45 as_of and render "coverage unknown", breaking
  ``under_narrated`` comparability. So the analyst count is a ~16:10 pull labelled with the L1's as_of — a
  ~25-minute label on a count that changes weekly.)
- ``council.debate.run_candidate`` runs once, on this pass's OWN router + ``CostLedger`` (``cap_pass_usd``).

**The pack never says the name is held**: nothing about the position (entry, mark, P&L, DTE) is passed to the pack
builder; ``ContextPack`` has no such field (a test asserts it). The mark multiple and DTE at read time are stored for
the timeline only.

MEASUREMENT ONLY (§5): writes ``held_reads`` and nothing else — never ``council_proposals`` /
``council_agent_outputs``; never triggers or delays an exit, add, re-strike or carry; never vetoes or sizes; never
enters a council prompt; never feeds the backfill rank, the gates or the persistence watch.

Refusals (log lines, return normally), all checked BEFORE any client, provider or router is built (a KILL,
holiday or missing-key night refuses quietly instead of paging): KILL, disabled, no council of record today (a day
whose L1 wrote zero council proposals counts as none — held names go unread that night), today's L1 not finished
(the §10.12 probe's ``l1_finished``), nothing to read (every tracked position already read for this run — one pass
per L1 run, UNIQUE run_id × position — or without lineage). A cap hit stops the pass (that night's remaining reads
are lost); a provider error drops that name with no row. Segments split on ``runs.model_mix``, stored per row.

Side effects worth knowing: the pass refetches into the shared point-in-time cache for the held symbols (news,
analyst, markers' bars, fundamentals), rewriting those payloads; harmless (the next L1 refetches). Fundamentals'
filed-date PIT rule is day-granular, so a filing made between the L1 (15:45 ET) and this pass (~16:10 ET) could be
visible to a held read though the L1 could not have had it — inherent to the record's rule.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime

import state
from clock import et_date
from council.repeat_probe import l1_finished, read_unit_state, todays_l1_run
from council.router import BudgetExceeded, CostLedger, RouterError

log = logging.getLogger("council.held_reads")

DEFAULTS = {"enabled": False, "cap_pass_usd": 1.0}


def settings(config: dict) -> dict:
    cfg = ((config.get("council", {}) or {}).get("held_reads") or {})
    return {**DEFAULTS, **{k: v for k, v in cfg.items() if not str(k).startswith("_")}}


@dataclass
class PackInputs:
    """The providers the L1 hands ``build_context_pack`` (``orchestrator._build_council_io``)."""

    news: object = None
    fundamentals: object = None
    analyst: object = None
    catalysts: object = None


@dataclass
class HeldOutcome:
    status: str                              # refused | done | stopped_cap
    reason: str = ""
    run_id: int | None = None
    tracked: int = 0
    read: int = 0
    skipped: dict = field(default_factory=dict)   # no_lineage / already_read / restricted / provider_error ...
    cost_usd: float = 0.0


@dataclass
class _Held:
    position: sqlite3.Row
    candidate: object
    origin: str
    lineage_status: str


def _refuse(reason: str, *, level: int = logging.INFO, **kw) -> HeldOutcome:
    log.log(level, "Held reads: not run — %s", reason)
    return HeldOutcome(status="refused", reason=reason, **kw)


def tracked_positions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every real position the pass tracks or reports: status open/closing (the no-lineage ones are reported)."""
    return conn.execute(
        "SELECT * FROM convexity_positions WHERE status IN ('open', 'closing') ORDER BY id").fetchall()


def lineage_candidate(conn: sqlite3.Connection, pos: sqlite3.Row, themes_all: list) -> tuple[object, str, str] | str:
    """``(Theme, origin, lineage_status)`` for a held position built from its own lineage, or a skip reason string.

    Sentinel origin: the entry proposal's ``sentinel_id`` row, whatever its status (dormant included), via
    ``sentinels.discovered_to_theme``. Hand-seed: the ``themes.json`` entry with the position's (symbol, direction),
    active or not."""
    import sentinels

    if pos["proposal_id"] is None:
        return "no_lineage"
    prop = state.council_proposal_by_id(conn, int(pos["proposal_id"]))
    if prop is None:
        return "no_lineage"
    sym, direction = str(pos["symbol"]).upper(), str(pos["direction"]).lower()
    if prop["sentinel_id"] is not None:
        row = state.sentinel_by_id(conn, int(prop["sentinel_id"]))
        if row is None:
            return "no_lineage"
        return sentinels.discovered_to_theme(row), "sentinel", str(row["status"])
    matches = [t for t in themes_all if t.symbol.upper() == sym and str(t.direction).lower() == direction]
    if len(matches) > 1:
        log.warning("Held reads: %d themes.json entries match %s %s; reading the first (%s)", len(matches), sym,
                    direction, matches[0].name)
    if matches:
        return matches[0], "hand-seed", "hand-seed"
    return "no_lineage"


def _role(p, role: str):
    for ao in p.agent_outputs:
        if ao.role == role:
            return ao
    return None


def _mark_multiple(pos) -> float | None:
    try:
        entry, mark = float(pos["entry_premium_per_contract"]), pos["mark"]
        # mark is the per-SHARE option price; entry_premium_per_contract is dollars per contract (#511: the ×100,
        # as dashboard_data's multiples and the monitor's realized multiple use it).
        return float(mark) * 100.0 / entry if mark is not None and entry > 0 else None
    except (TypeError, ValueError):
        return None


def _dte(pos, today: date) -> int | None:
    try:
        return (date.fromisoformat(str(pos["expiry"])[:10]) - today).days
    except (TypeError, ValueError):
        return None


def _bool_or_none(v) -> int | None:
    return int(v) if isinstance(v, bool) else None


def _write(conn, *, h: _Held, run_id: int, as_of: str, p, model_mix: str | None, today: date, now) -> None:
    pos = h.position
    sao = _role(p, "strategist")
    cols: dict = {
        "position_id": int(pos["id"]), "run_id": run_id, "proposal_id": pos["proposal_id"],
        "symbol": str(pos["symbol"]), "direction": str(pos["direction"]), "as_of": as_of, "origin": h.origin,
        "sentinel_id": getattr(h.candidate, "sentinel_id", None), "lineage_status": h.lineage_status,
        "conviction_raw": (str(sao.raw.get("conviction")) if sao is not None and sao.raw.get("conviction") is not None
                           else None),
        "conviction": p.conviction, "include": int(bool(p.include)), "structural_vs_fad": p.structural_vs_fad,
        "under_narrated": _bool_or_none(p.under_narrated), "at_inflection": _bool_or_none(p.at_inflection),
        "criteria_veto": int(bool(p.criteria_veto)) if sao is not None else None,
        "weakest_point": p.weakest_point, "dropped": (p.rationale or {}).get("dropped"),
        "rationale": json.dumps(p.rationale, default=str), "model_mix": model_mix, "cost_usd": float(p.cost_usd),
        "mark_multiple": _mark_multiple(pos), "dte": _dte(pos, today), "created_at": state.sql_utc(now),
    }
    for role in ("proposer", "adversary", "strategist"):
        ao = _role(p, role)
        cols[f"{role}_provider"] = ao.provider if ao else None
        cols[f"{role}_model"] = ao.model if ao else None
        cols[f"{role}_cost_usd"] = float(ao.cost_usd) if ao else None
    with conn:
        conn.execute(f"INSERT INTO held_reads ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                     tuple(cols.values()))


def run_pass(conn: sqlite3.Connection, *, config: dict, clock, router_factory: Callable,
             inputs: Callable[[datetime], PackInputs],
             refresh: Callable[[list, datetime], list] = lambda cands, as_of: cands,
             unit_state: Callable[[], tuple[str, str | None] | None] | None = None,
             themes_path: str | None = None) -> HeldOutcome:
    """One held pass for today's L1 (ET date). Every refusal is decided first; only then are ``inputs(as_of)`` (the
    pack providers, built at the L1 council's as_of), ``refresh(candidates, as_of)`` (the L1's marker refresh) and
    ``router_factory(config, ledger)`` (the pass's OWN full-council router) called. Refusals return; unexpected errors
    raise."""
    from risk import kill_switch_active

    if kill_switch_active():
        return _refuse("KILL switch engaged (no LLM spend)")
    s = settings(config)
    if not bool(s["enabled"]):
        return _refuse("council.held_reads.enabled is false")
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='held_reads'").fetchone() is None:
        return _refuse("held_reads table missing (migration 0023 not applied)", level=logging.WARNING)
    now = clock.now()
    today = et_date(now)
    run = todays_l1_run(conn, today)
    if run is None:
        return _refuse(f"no council of record for {today} ET")
    run_id = int(run["id"])
    done, why = l1_finished(run["started_at"], (unit_state or read_unit_state)())
    if not done:
        return _refuse(f"today's L1 (run #{run_id}) has not finished: {why}", level=logging.WARNING, run_id=run_id)
    as_of_iso = conn.execute("SELECT MAX(as_of) FROM council_proposals WHERE run_id = ?", (run_id,)).fetchone()[0]
    as_of = datetime.fromisoformat(as_of_iso)

    import restricted as restricted_list
    from themes import load_themes

    themes_all = load_themes(themes_path or config.get("themes_path", "themes.json"))
    restricted = restricted_list.load_restricted()
    skipped: Counter = Counter()
    positions = tracked_positions(conn)
    already = {int(r[0]) for r in conn.execute("SELECT position_id FROM held_reads WHERE run_id = ?", (run_id,))}
    held: list[_Held] = []
    for pos in positions:
        if int(pos["id"]) in already:
            skipped["already_read"] += 1
            continue
        if restricted_list.is_restricted(str(pos["symbol"]), restricted):
            skipped["restricted"] += 1
            continue
        got = lineage_candidate(conn, pos, themes_all)
        if isinstance(got, str):
            skipped[got] += 1
            log.info("Held reads: #%s %s %s not read (%s)", pos["id"], pos["symbol"], pos["direction"], got)
            continue
        held.append(_Held(pos, *got))
    if not held:
        return _refuse(f"nothing to read for run #{run_id} (positions={len(positions)}, skipped={dict(skipped)})",
                       run_id=run_id, tracked=len(positions), skipped=dict(skipped))

    # Only now build anything external: the providers at the L1's as_of, the marker refresh, the router.
    deps = inputs(as_of)
    # The L1's marker refresh, on the held candidates (markers recomputed at as_of; hand-seeds pass through).
    refreshed = refresh([h.candidate for h in held], as_of)
    for h, c in zip(held, refreshed, strict=True):
        h.candidate = c

    from council.council import council_pack, load_register_theses
    from council.debate import run_candidate

    reg = load_register_theses(config)
    router = router_factory(config, CostLedger(cap_usd=float(s["cap_pass_usd"])))
    o = HeldOutcome(status="done", run_id=run_id, tracked=len(positions))
    for h in held:
        pack = council_pack(h.candidate, config=config, as_of=as_of, news=deps.news,
                            fundamentals=deps.fundamentals, analyst=deps.analyst, catalysts=deps.catalysts,
                            register_theses=reg)
        try:
            p = run_candidate(h.candidate, pack, router)
        except BudgetExceeded as e:
            o.status, o.reason = "stopped_cap", str(e)
            break
        except RouterError as e:
            skipped["provider_error"] += 1
            log.warning("Held reads: %s dropped (provider error): %s", h.position["symbol"], e)
            continue
        _write(conn, h=h, run_id=run_id, as_of=as_of_iso, p=p, model_mix=run["model_mix"], today=today,
               now=clock.now())
        o.read += 1
    o.skipped = dict(skipped)
    o.cost_usd = router.ledger.total_usd
    log.info("Held reads run #%d (%s ET): status=%s read %d of %d open/closing position(s), skipped %s, cost $%.4f "
             "(cap $%.2f)%s", run_id, today, o.status, o.read, len(positions), dict(skipped) or "none", o.cost_usd,
             float(s["cap_pass_usd"]), f" — {o.reason}" if o.reason else "")
    if o.status != "done":
        log.warning("Held reads stopped early (%s): %s", o.status, o.reason)
    return o


# ── live wiring (the post-L1 pass) ──────────────────────────────────────────────────────────────────────────────
def _live_router(config: dict, ledger: CostLedger):
    from council.router import build_router

    return build_router(config, config.get("llm_keys", {}), ledger=ledger)


class _LiveDeps:
    """The L1's external dependencies, built lazily — only once ``run_pass`` has decided to read."""

    def __init__(self, config: dict, conn) -> None:
        self.config, self.conn = config, conn
        self._client = self._cache = None

    def _ensure(self) -> None:
        if self._client is None:
            from config_loader import require_alpaca_credentials
            from data.alpaca_client import AlpacaClient
            from data.cache import PointInTimeCache

            api_key, secret_key = require_alpaca_credentials(self.config)
            self._client = AlpacaClient(api_key, secret_key, paper=self.config["alpaca"]["paper"])
            self._cache = PointInTimeCache(self.config.get("cache", {}).get("dir", "data/cache"))

    def inputs(self, as_of: datetime) -> PackInputs:
        """The L1's providers, with fetch_end = the pack's as_of (a clock fixed at it); no router built."""
        import orchestrator
        from clock import FixedClock

        self._ensure()
        _none, news, fundamentals, analyst, catalysts = orchestrator._build_council_io(
            self.config, demo=False, client=self._client, cache=self._cache, clock=FixedClock(as_of),
            with_router=False)
        return PackInputs(news, fundamentals, analyst, catalysts)

    def refresh(self, cands: list, as_of: datetime) -> list:
        import orchestrator

        self._ensure()
        return orchestrator._refresh_council_markers(self.conn, cands, config=self.config, client=self._client,
                                                     cache=self._cache, as_of=as_of, run_id=None)


def run_live(config: dict, *, clock=None) -> HeldOutcome:
    """The ``post_l1`` pass against the live DB, with the L1's own data providers and marker refresh. ``clock``
    (tests) defaults to the wall clock; nothing external is built until every refusal has been checked."""
    if not bool(settings(config)["enabled"]):
        return _refuse("council.held_reads.enabled is false")
    from clock import LiveClock

    conn = state.get_db(config)
    try:
        deps = _LiveDeps(config, conn)
        return run_pass(conn, config=config, clock=clock or LiveClock(), router_factory=_live_router,
                        inputs=deps.inputs, refresh=deps.refresh)
    finally:
        conn.close()
