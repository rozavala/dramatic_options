"""Forward falsifier-accuracy ledger (D3b; calibration v2 Rule S) — telemetry only.

Calibration v2 found that selling on a fired falsifier lowers the break-even hit-rate in every cell, and fails
only on false alarms: at 70% accuracy, false alarms cost the strongest winners 17%; at 90% it passes everywhere
(records/2026-11-03_calibration_v2_finding.md). So the deciding number is how accurate our falsifiers really are.
This ledger measures it forward:

1. **Read** (once per spec × name, at the first L1 where the named quarter is visible in XBRL): the falsifier's
   value, threshold and ``fired``, plus the close that day. Appended to ``records/falsifier_ledger.csv`` and never
   rewritten (the seal is the append-only file). The L1 writes it in the live checkout, so it is gitignored:
   a deploy's ``git clean -fd`` / ``reset --hard`` never touches it and no commit can overwrite it (#429).
2. **Outcome** (report time, 250 trading bars later): the directional return from that close; "big move" uses the
   miss ledger's +50% bar (PREREG_MISS_BASERATE §3). Accuracy = P(fired | no big move); false-alarm rate =
   P(fired | big move).

A fired falsifier never sells, gates or vetoes anything. Specs are in ``falsifier_specs.json`` (operator-editable).
"""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger("falsifier_ledger")

ROOT = Path(__file__).resolve().parent
SPEC_PATH = ROOT / "falsifier_specs.json"
LEDGER_PATH = ROOT / "records" / "falsifier_ledger.csv"
FIELDS = ["read_at", "spec_id", "theme", "symbol", "direction", "metric", "threshold", "period_end", "filed",
          "value", "fired", "entry_close"]
HORIZON_BARS = 250
BIG_MOVE = 0.50


def load_specs(path: Path | str = SPEC_PATH) -> list[dict]:
    """The specs; ``[]`` on any error (logged) — telemetry never raises."""
    try:
        return [s for s in (json.loads(Path(path).read_text()).get("specs") or []) if isinstance(s, dict)]
    except Exception as e:  # noqa: BLE001
        log.warning("falsifier specs unreadable (ledger idle): %s", e)
        return []


def _d(s: str) -> datetime:
    return datetime.fromisoformat(str(s)[:10])


def first_quarter_after(points: list[dict], filed_after: str) -> dict | None:
    """The quarter REPORTED by the first filing strictly after ``filed_after``: the newest period end on the
    earliest such filing date. A 10-Q also carries its year-ago comparative, and the extractor keeps the
    latest-filed value per period, so that comparative shares the filing date; the earliest end would be last
    year's quarter (#429: FIG's 11-04 10-Q sealed Q3-25 at +38.0% instead of Q3-26 at +42.8%)."""
    later = [p for p in points if str(p["filed"])[:10] > filed_after]
    if not later:
        return None
    first = min(str(p["filed"])[:10] for p in later)
    return max((p for p in later if str(p["filed"])[:10] == first), key=lambda p: p["end"])


def quarter_yoy(points: list[dict], q: dict) -> float | None:
    """Single-quarter revenue vs the quarter ending ~one year earlier (±45 days); None without a positive base."""
    target = _d(q["end"]) - timedelta(days=365)
    base = [p for p in points if abs((_d(p["end"]) - target).days) <= 45 and str(p["filed"])[:10] <= str(q["filed"])[:10]]
    if not base:
        return None
    b = min(base, key=lambda p: abs((_d(p["end"]) - target).days))
    return None if b["val"] <= 0 else q["val"] / b["val"] - 1.0


def evaluate(spec: dict, points: list[dict], as_of: datetime) -> dict | None:
    """The spec's read for one name as of ``as_of``, or None while its quarter isn't visible or readable."""
    if spec.get("metric") != "quarterly_revenue_yoy":
        return None
    visible = [p for p in points if str(p["filed"])[:10] <= as_of.date().isoformat()]
    q = first_quarter_after(visible, str(spec["first_filed_after"]))
    if q is None:
        return None
    yoy = quarter_yoy(visible, q)
    if yoy is None:
        return None
    thr = float(spec["threshold"])
    return {"period_end": q["end"], "filed": str(q["filed"])[:10], "value": round(yoy, 4),
            "threshold": thr, "fired": int(yoy < thr)}


def _read_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def record_due(*, symbols_of: Callable[[str], list[str]], points_of: Callable[[str], list[dict]],
               close_of: Callable[[str], float | None], as_of: datetime, specs: list[dict] | None = None,
               ledger_path: Path | str = LEDGER_PATH) -> list[dict]:
    """Append a read for every (spec, name) whose quarter has become visible and isn't yet in the ledger.
    Idempotent: run it every L1. Per-name errors are logged and skipped."""
    path = Path(ledger_path)
    specs = load_specs() if specs is None else specs
    done = {(r["spec_id"], r["symbol"]) for r in _read_ledger(path)}
    new: list[dict] = []
    unreadable: list[str] = []
    for spec in specs:
        for sym in symbols_of(str(spec.get("theme", ""))):
            sym = sym.upper()
            if (spec["id"], sym) in done:
                continue
            try:
                points = points_of(sym)
                if not points:
                    unreadable.append(f"{spec['id']}/{sym}")
                    continue
                res = evaluate(spec, points, as_of)
                if res is None:
                    continue
                close = close_of(sym)
            except Exception as e:  # noqa: BLE001 — telemetry never breaks the cycle
                log.warning("falsifier read %s/%s failed (non-fatal): %s", spec.get("id"), sym, e)
                continue
            new.append({"read_at": as_of.date().isoformat(), "spec_id": spec["id"], "theme": spec.get("theme"),
                        "symbol": sym, "direction": spec.get("direction", "bullish"), "metric": spec["metric"],
                        "threshold": res["threshold"], "period_end": res["period_end"], "filed": res["filed"],
                        "value": res["value"], "fired": res["fired"],
                        "entry_close": None if close is None else round(float(close), 4)})
    if unreadable:
        # Fail-soft, not fail-silent (#429): a name with no us-gaap quarterly revenue (KLAR files as a foreign
        # issuer) can never read, so its spec measures nothing until the operator re-encodes or drops it.
        log.warning("falsifier ledger: no quarterly revenue points, so these can never read: %s", unreadable)
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        fresh = not path.exists()
        with path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if fresh:
                w.writeheader()
            w.writerows(new)
    return new


def directional(ret: float | None, direction: str) -> float | None:
    if ret is None:
        return None
    return -ret if str(direction).lower() == "bearish" else ret


def report(rows: list[dict], *, outcome_of: Callable[[dict], float | None] | None = None) -> dict:
    """Counts. ``outcome_of(row)`` returns the raw 250-bar return once matured (None while accruing)."""
    fired = sum(1 for r in rows if str(r["fired"]) == "1")
    out: dict[str, Any] = {"reads": len(rows), "fired": fired, "not_fired": len(rows) - fired,
                           "matured": 0, "accuracy": None, "false_alarm": None, "cells": {}}
    if outcome_of is None:
        return out
    cells = {"fired_big": 0, "fired_not_big": 0, "quiet_big": 0, "quiet_not_big": 0}
    for r in rows:
        d = directional(outcome_of(r), r["direction"])
        if d is None:
            continue
        out["matured"] += 1
        big = d >= BIG_MOVE
        cells[("fired_" if str(r["fired"]) == "1" else "quiet_") + ("big" if big else "not_big")] += 1
    not_big = cells["fired_not_big"] + cells["quiet_not_big"]
    big = cells["fired_big"] + cells["quiet_big"]
    out["cells"] = cells
    out["accuracy"] = round(cells["fired_not_big"] / not_big, 4) if not_big else None
    out["false_alarm"] = round(cells["fired_big"] / big, 4) if big else None
    return out


def panel(*, ledger_path: Path | str = LEDGER_PATH, specs: list[dict] | None = None,
          symbols_of: Callable[[str], list[str]] | None = None) -> dict:
    """Dashboard panel (read-only, no fetch): the reads so far and the specs still waiting for their quarter."""
    rows = _read_ledger(Path(ledger_path))
    specs = load_specs() if specs is None else specs
    done = {(r["spec_id"], r["symbol"]) for r in rows}
    waiting = []
    for s in specs:
        syms = symbols_of(str(s.get("theme", ""))) if symbols_of else []
        for sym in syms or ["?"]:
            if (s["id"], sym.upper()) not in done:
                waiting.append({"spec_id": s["id"], "symbol": sym.upper(), "threshold": s.get("threshold"),
                                "first_filed_after": s.get("first_filed_after")})
    return {"rows": rows[::-1], "waiting": waiting, "summary": report(rows),
            "note": f"Outcomes mature {HORIZON_BARS} trading bars after each read; big move = +{BIG_MOVE:.0%} "
                    "directional. Telemetry only: a fired falsifier never sells or vetoes."}


def basket_symbols_of(config: dict) -> Callable[[str], list[str]]:
    themes = (config.get("universe", {}) or {}).get("themes", {}) or {}
    return lambda key: [s for s in (themes.get(key) or []) if isinstance(s, str)]


def main(argv: list[str] | None = None) -> int:
    import argparse

    from config_loader import load_config

    ap = argparse.ArgumentParser(description="Forward falsifier-accuracy ledger (D3b)")
    ap.add_argument("--report", action="store_true", help="resolve matured outcomes from the bars cache")
    args = ap.parse_args(argv)
    config = load_config()
    rows = _read_ledger(LEDGER_PATH)
    outcome_of = None
    if args.report:
        from data.cache import PointInTimeCache
        from data.market import MarketData
        from sentinel_scoring import resolve_reference

        now = datetime.now().astimezone()
        market = MarketData(PointInTimeCache(config.get("cache", {}).get("dir", "data/cache"), offline=True),
                            fetch_start=now - timedelta(days=800), fetch_end=now)
        outcome_of = lambda r: resolve_reference(  # noqa: E731
            market, r["symbol"], datetime.fromisoformat(r["read_at"]).astimezone(), HORIZON_BARS, now=now)[0]
    print(json.dumps(panel(symbols_of=basket_symbols_of(config)) | {"summary": report(rows, outcome_of=outcome_of)},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
