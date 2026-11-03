"""Execution ledger (D0, records/2026-11-03_profit_program_DRAFTS.md) — telemetry only.

One row per council approval (a proposal that cleared the floor: ``status`` 'proposed' or 'traded'), following it
from the gates to the broker:

    approved → gate outcome → L1 order → filled | carried → carry attempts → filled | lapsed | vetoed

It answers the question the HL/AG cancels raised: when the council says yes, does the book actually get the
contract? Read-only over existing tables (council_proposals, convexity_eval, convexity_positions); no schema change,
no frame change, never touches the trade path.

    python -m execution_ledger            # the table + the fill-rate summary
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")

# Carry-over (#386) went on after AG's 10-29 cancel, so the first approval it covers is the 10-30 session.
CARRY_ON_ET_DATE = "2026-10-30"
# The D0 read: after this many approvals under carry-over that reached an order.
READ_AFTER_N = 5

_FILLED = ("open", "closing", "closed")
_ORDER_DECISIONS = ("open", "submit-pending")


def _json(raw) -> dict:
    try:
        v = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return v if isinstance(v, dict) else {}


def _et_date(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso))
    except ValueError:
        return str(iso)[:10]
    dt = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return dt.astimezone(_ET).date().isoformat()


def _px(row) -> float | None:
    v = row["entry_premium_per_contract"] if row is not None else None
    return round(float(v) / 100.0, 4) if v is not None else None


def _outcome(orig, attempts: list) -> str:
    """Classify the order chain that started at the L1 row ``orig``."""
    st, why = orig["status"], (orig["exit_reason"] or "")
    if st in _FILLED:
        return "filled_l1"
    if st == "pending":
        return "working"
    if st == "carried":
        return "carry_in_progress"
    if st == "cancelled":
        if why == "carry_filled" or any(a["status"] in _FILLED for a in attempts):
            return "filled_carry"
        if why == "cancelled_unfilled":
            return "unfilled_no_carry"
        if why == "carry_lapsed":
            return "carry_lapsed"
        if why.startswith("carry_veto"):
            return "carry_veto"
        if why == "kill_cancelled":
            return "kill_cancelled"
        return f"cancelled:{why or '?'}"
    return st


def build_ledger(conn: sqlite3.Connection) -> list[dict]:
    """Every approval, oldest first, with its execution chain."""
    conn.row_factory = sqlite3.Row
    props = conn.execute(
        "SELECT id, run_id, as_of, symbol, direction, conviction, status, position_id FROM council_proposals "
        "WHERE status IN ('proposed', 'traded') ORDER BY id").fetchall()
    # Carry attempts point at the L1 row they carry (rationale.carry.of); index them once.
    attempts_of: dict[int, list] = {}
    for r in conn.execute("SELECT * FROM convexity_positions WHERE rationale LIKE '%\"carry\"%' ORDER BY id"):
        of = (_json(r["rationale"]).get("carry") or {}).get("of")
        if of is not None:
            attempts_of.setdefault(int(of), []).append(r)
    out = []
    for p in props:
        evals = conn.execute("SELECT decision, position_id, reasons FROM convexity_eval WHERE proposal_id = ? "
                             "ORDER BY id", (p["id"],)).fetchall()
        l1 = next((e for e in evals if e["decision"] in _ORDER_DECISIONS and e["position_id"] is not None), None)
        row = {
            "proposal_id": p["id"], "run_id": p["run_id"], "date": _et_date(p["as_of"]), "symbol": p["symbol"],
            "direction": p["direction"], "conviction": p["conviction"],
            "under_carry": (_et_date(p["as_of"]) or "") >= CARRY_ON_ET_DATE,
            "position_id": None, "contract": None, "contracts": None, "limit": None, "mid": None, "ask": None,
            "spread_pct": None, "attempts": [], "fill_px": None, "outcome": None,
        }
        if l1 is None:
            first = evals[0]["decision"] if evals else None
            row["outcome"] = f"gate:{first}" if first else "not_evaluated"
            out.append(row)
            continue
        orig = conn.execute("SELECT * FROM convexity_positions WHERE id = ?", (l1["position_id"],)).fetchone()
        if orig is None:
            row["outcome"] = "position_missing"
            out.append(row)
            continue
        rat = _json(orig["rationale"])
        q = rat.get("quote") or {}
        atts = attempts_of.get(int(orig["id"]), [])
        row.update({
            "position_id": orig["id"], "contract": orig["contract_symbol"], "contracts": orig["contracts"],
            "limit": _px(orig), "mid": q.get("mid"), "ask": q.get("ask"), "spread_pct": q.get("spread_pct"),
            "attempts": [{"id": a["id"], "step": (_json(a["rationale"]).get("carry") or {}).get("step"),
                          "limit": _px(a), "status": a["status"], "exit_reason": a["exit_reason"]} for a in atts],
            "outcome": _outcome(orig, atts),
        })
        filled = orig if orig["status"] in _FILLED else next((a for a in atts if a["status"] in _FILLED), None)
        row["fill_px"] = _px(filled) if filled is not None else None
        out.append(row)
    return out


def summarize(ledger: list[dict]) -> dict:
    """Fill rates, overall and under carry-over. 'Reached an order' excludes gate vetoes; 'decided' also excludes
    chains still working, so a resting order never counts as a miss."""
    def block(rows: list[dict]) -> dict:
        ordered = [r for r in rows if r["position_id"] is not None]
        decided = [r for r in ordered if r["outcome"] not in ("working", "carry_in_progress")]
        filled = [r for r in decided if r["outcome"] in ("filled_l1", "filled_carry")]
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
        return {"approvals": len(rows), "reached_order": len(ordered), "decided": len(decided),
                "filled": len(filled), "fill_rate": (round(len(filled) / len(decided), 4) if decided else None),
                "outcomes": counts}

    carry_rows = [r for r in ledger if r["under_carry"]]
    carry = block(carry_rows)
    n = carry["decided"]
    if n < READ_AFTER_N:
        read = f"accruing: {n} of {READ_AFTER_N} decided orders under carry-over"
    elif carry["filled"] >= READ_AFTER_N - 1:
        read = f"carry-over is filling ({carry['filled']} of {n})"
    else:
        read = (f"fewer than {READ_AFTER_N - 1} of {n} filled under carry-over: consider submitting every "
                "approval at the next session's open (D0)")
    return {"all": block(ledger), "under_carry": carry, "read": read, "carry_on_et_date": CARRY_ON_ET_DATE}


def panel(conn: sqlite3.Connection, n_recent: int = 12) -> dict:
    """The dashboard panel: the summary plus the most recent approvals."""
    led = build_ledger(conn)
    return {"summary": summarize(led), "rows": led[-n_recent:][::-1]}


def main(argv: list[str] | None = None) -> int:
    import argparse

    from config_loader import load_config
    from state import get_db

    ap = argparse.ArgumentParser(description="Execution ledger: does an approval become a filled contract?")
    ap.add_argument("--db", default=None, help="SQLite path (default: config database.path)")
    args = ap.parse_args(argv)
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True) if args.db else get_db(load_config())
    conn.row_factory = sqlite3.Row
    led = build_ledger(conn)
    print(f"{'date':10} {'prop':>5} {'sym':6} {'conv':9} {'outcome':20} {'limit':>7} {'mid':>7} {'ask':>7} "
          f"{'fill':>7}  attempts")
    for r in led:
        atts = " ".join(f"{a['step']}@{a['limit']}:{a['status']}" for a in r["attempts"]) or "-"
        f = lambda v: "-" if v is None else f"{v:.2f}"  # noqa: E731
        print(f"{r['date'] or '-':10} {r['proposal_id']:>5} {r['symbol']:6} {str(r['conviction']):9} "
              f"{r['outcome']:20} {f(r['limit']):>7} {f(r['mid']):>7} {f(r['ask']):>7} {f(r['fill_px']):>7}  {atts}")
    print(json.dumps(summarize(led), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
