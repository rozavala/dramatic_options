"""Miss base-rate ledger — the pure, tested core (PREREG_MISS_BASERATE.md).

Does the curated universe catch cheap-then-moved names at a better rate than a frozen random slice of
the options-enabled market? Forward, base-rated, sealed per name, counts-only, report-not-gate.
Never imported by the trading loop; the probe in ``scripts/`` is the only caller.
"""
from __future__ import annotations

import csv
import hashlib
import math
import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sentinel_scoring import reference_return_from_bars

SEAL_PREFIX = "miss_baserate_v1:"
DRAW_SEED = 20260914
DRAW_POOL = 300
DENOMINATOR_N = 150
HORIZONS = (63, 126, 250)
BIG_MOVE = 0.50
BIG_MOVE_2X = 1.00
MIN_CELL_N = 20
LEDGER_COLUMNS = ("date", "key", "cohort", "direction", "structured", "gate_cheap", "entry_close", "feed")
_FUND_RE = re.compile(r"\b(ETF|ETN|Fund|Trust|Preferred|Warrant|Warrants|Right|Rights|Unit|Units)\b", re.I)


def seal(symbol: str) -> str:
    """The sealed per-name key: the ledger never carries a symbol beside a gate verdict."""
    return hashlib.sha256((SEAL_PREFIX + symbol.upper()).encode()).hexdigest()[:12]


def is_fund_like(name: str | None) -> bool:
    return bool(_FUND_RE.search(name or ""))


def draw_denominator(pool: list[str], universe: set[str], *, seed: int = DRAW_SEED,
                     k: int = DRAW_POOL) -> list[str]:
    """The frozen draw: exclude the universe, sort, sample ``k`` in seeded order (deterministic)."""
    cands = sorted({s.upper() for s in pool} - {u.upper() for u in universe})
    return random.Random(seed).sample(cands, min(k, len(cands)))


@dataclass(frozen=True)
class SweepRow:
    date: str
    key: str
    cohort: str          # 'universe' | 'market'
    direction: str       # 'bullish' | 'bearish'
    structured: int
    gate_cheap: int | None
    entry_close: float | None
    feed: str

    def as_csv(self) -> tuple:
        return (self.date, self.key, self.cohort, self.direction, self.structured,
                "" if self.gate_cheap is None else self.gate_cheap,
                "" if self.entry_close is None else f"{self.entry_close:.4f}", self.feed)


def append_rows(path: Path, rows: list[SweepRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(LEDGER_COLUMNS)
        w.writerows(r.as_csv() for r in rows)


def read_rows(path: Path) -> list[SweepRow]:
    if not path.exists():
        return []
    out: list[SweepRow] = []
    with path.open(newline="") as fh:
        for r in csv.DictReader(fh):
            out.append(SweepRow(
                date=r["date"], key=r["key"], cohort=r["cohort"], direction=r["direction"],
                structured=int(r["structured"] or 0),
                gate_cheap=None if r["gate_cheap"] in ("", None) else int(r["gate_cheap"]),
                entry_close=None if r["entry_close"] in ("", None) else float(r["entry_close"]),
                feed=r["feed"]))
    return out


def directional_return(raw: float, direction: str) -> float:
    return raw if direction == "bullish" else -raw


# fwd_closes(key, date) -> (closes after the sweep date, terminated) — the only market touch, injected.
FwdCloses = Callable[[str, str], tuple[list[float], bool]]


@dataclass
class Cell:
    n_matured: int = 0
    n_accruing: int = 0
    n_cheap: int = 0
    n_big: int = 0
    n_cheap_big: int = 0
    n_notcheap: int = 0
    n_notcheap_big: int = 0
    n_big_2x: int = 0

    def rate(self, num: int, den: int) -> float | None:
        return None if den < MIN_CELL_N else num / den


def aggregate(rows: list[SweepRow], fwd: FwdCloses, *, horizons=HORIZONS,
              big_move: float = BIG_MOVE) -> dict[tuple[str, int], Cell]:
    """Maturity-gated counts per (cohort, horizon). Rows without a gate read are skipped entirely."""
    cells: dict[tuple[str, int], Cell] = {}
    for r in rows:
        if r.gate_cheap is None or r.entry_close is None:
            continue
        closes, terminated = fwd(r.key, r.date)
        for h in horizons:
            c = cells.setdefault((r.cohort, h), Cell())
            ret, tag = reference_return_from_bars(r.entry_close, closes, h, terminated=terminated)
            if ret is None:
                c.n_accruing += 1
                continue
            c.n_matured += 1
            d = directional_return(ret, r.direction)
            big = d >= big_move
            c.n_big += int(big)
            c.n_big_2x += int(d >= BIG_MOVE_2X)
            if r.gate_cheap:
                c.n_cheap += 1
                c.n_cheap_big += int(big)
            else:
                c.n_notcheap += 1
                c.n_notcheap_big += int(big)
    return cells


def two_proportion_z(x1: int, n1: int, x2: int, n2: int) -> float | None:
    if n1 < MIN_CELL_N or n2 < MIN_CELL_N:
        return None
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return None if se == 0 else (x1 / n1 - x2 / n2) / se


GUARD = f"n<{MIN_CELL_N}"


def _fmt(r: float | None) -> str:
    return GUARD if r is None else f"{r:.3f}"


def render(cells: dict[tuple[str, int], Cell], *, horizons=HORIZONS) -> str:
    """Counts and guarded rates only — never a key, symbol, or per-row verdict."""
    lines = ["miss base-rate ledger — counts only (PREREG_MISS_BASERATE §3); big move = directional "
             f"return >= +{BIG_MOVE:.2f} (2x companion >= +{BIG_MOVE_2X:.2f})"]
    for h in horizons:
        lines.append(f"\nh={h} bars")
        for cohort in ("universe", "market"):
            c = cells.get((cohort, h), Cell())
            lines.append(
                f"  {cohort:9} matured={c.n_matured:4} accruing={c.n_accruing:4} cheap={c.n_cheap:4} "
                f"big={c.n_big:4} big2x={c.n_big_2x:4} cheap&big={c.n_cheap_big:4} | "
                f"P(big|cheap)={_fmt(c.rate(c.n_cheap_big, c.n_cheap))} "
                f"P(big|not-cheap)={_fmt(c.rate(c.n_notcheap_big, c.n_notcheap))} "
                f"P(big)={_fmt(c.rate(c.n_big, c.n_matured))}")
        u, m = cells.get(("universe", h), Cell()), cells.get(("market", h), Cell())
        z = two_proportion_z(u.n_cheap_big, u.n_cheap, m.n_cheap_big, m.n_cheap)
        lines.append(f"  R1 z (universe vs market, P(big|cheap)): {GUARD if z is None else f'{z:+.2f}'}")
    return "\n".join(lines)
