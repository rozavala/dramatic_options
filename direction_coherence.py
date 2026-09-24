"""Direction coherence (PREREG_DIRECTION_COHERENCE) — composition-only union filter.

A SENTINEL candidate framed **bearish** (a motion-derived direction) is withheld from the candidate union
when its latest filed quarter shows revenue **growing** (``revenue.qtr_yoy > 0``) **and accelerating**
(``revenue.qtr_yoy_accel > 0``). Both thresholds are the natural zero — nothing is tuned.

Discipline (the pre-registration's §2-§4):

- **Deterministic.** Filed XBRL lines only (``FundamentalsData.corpus_asof``, point-in-time as of the run).
  Never an LLM label, never the framer, never price.
- **Composition-only.** It changes which names are shown; it never changes how they are judged, gated or
  sized. Hand-seed themes (operator conviction) and bullish framings are never touched.
- **Fail-soft, and never withholds on absence.** A missing revenue line, a missing acceleration line, no
  fundamentals provider, or any read error ⇒ the candidate is KEPT (and counted). A withholding rule must
  act only on filed evidence.
- **One withheld set, three consumers.** The set is computed ONCE per cycle, against the union the
  council sees, and the SAME lineage keys are removed from the brain-off shadow book's and the no-gate 3A
  book's unions (:meth:`CoherenceFilter.exclude`) — so real-vs-shadow and shadow-vs-3A stay paired.
- **The lineage is not deleted.** A withheld sentinel stays in ``sentinel_candidates`` and is scored forward
  by the reference-return sweep; that is what the harm falsifier (F1) reads.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

STAMP = "dircoherence_v1"  # the runs.model_mix union_rank suffix (record-segmenting)


def _key(theme) -> tuple[str, str]:
    return (str(theme.symbol).upper(), str(theme.direction).lower())


def is_candidate_for_rule(theme) -> bool:
    """Only a SENTINEL (discovery-origin, motion-derived direction) framed BEARISH is ever checked."""
    return getattr(theme, "source", "hand-seed") == "sentinel" and str(theme.direction).lower() == "bearish"


def revenue_growing_and_accelerating(lines: Iterable[dict] | None) -> bool | None:
    """``True`` iff filed quarterly revenue y/y > 0 AND its acceleration > 0; ``None`` if either is missing."""
    yoy = accel = None
    for ln in lines or ():
        if not isinstance(ln, dict) or ln.get("concept") != "revenue":
            continue
        if ln.get("metric") == "qtr_yoy":
            yoy = ln.get("value")
        elif ln.get("metric") == "qtr_yoy_accel":
            accel = ln.get("value")
    if yoy is None or accel is None:
        return None
    return float(yoy) > 0.0 and float(accel) > 0.0


@dataclass
class CoherenceFilter:
    """Computes the withheld set once per cycle and applies it to every consumer's union.

    ``lines_of(symbol)`` returns the corpus lines as of the run, or ``None`` when no fundamentals provider
    exists (then nothing is ever withheld). Results are memoized per symbol for the cycle."""

    lines_of: Callable[[str], list[dict] | None] | None
    withheld: dict[tuple[str, str], str] = field(default_factory=dict)
    kept_no_accel: list[str] = field(default_factory=list)
    errors: int = 0
    _memo: dict[str, list[dict] | None] = field(default_factory=dict)

    @classmethod
    def from_fundamentals(cls, fundamentals, as_of) -> CoherenceFilter:
        if fundamentals is None:
            return cls(lines_of=None)

        def lines_of(symbol: str) -> list[dict] | None:
            return (fundamentals.corpus_asof(symbol, as_of) or {}).get("lines")

        return cls(lines_of=lines_of)

    def _lines(self, symbol: str) -> list[dict] | None:
        if symbol not in self._memo:
            self._memo[symbol] = self.lines_of(symbol) if self.lines_of is not None else None
        return self._memo[symbol]

    def apply(self, union: list) -> list:
        """The council's union minus the withheld candidates (order preserved). Records the withheld set."""
        out = []
        for t in union:
            if self.lines_of is not None and is_candidate_for_rule(t):
                try:
                    verdict = revenue_growing_and_accelerating(self._lines(str(t.symbol).upper()))
                except Exception as e:  # noqa: BLE001 — fail-soft: a read error KEEPS the candidate
                    self.errors += 1
                    log.warning("direction-coherence: corpus read failed for %s (kept): %s", t.symbol, e)
                    verdict = None
                if verdict is True:
                    self.withheld[_key(t)] = "bearish framing vs filed revenue growing and accelerating"
                    continue
                if verdict is None:
                    self.kept_no_accel.append(str(t.symbol).upper())
            out.append(t)
        return out

    def exclude(self, union: list) -> list:
        """Remove exactly the already-withheld lineage keys from another consumer's union (no re-read)."""
        if not self.withheld:
            return list(union)
        return [t for t in union if _key(t) not in self.withheld]

    def summary(self) -> str:
        """One line for the journal and ``runs.note`` — the durable record of what was withheld."""
        if self.lines_of is None:
            return "direction-coherence: fundamentals unavailable — nothing withheld"
        withheld = sorted(s for (s, _d) in self.withheld)
        return (f"direction-coherence: withheld={withheld} "
                f"kept_no_accel={sorted(set(self.kept_no_accel))} errors={self.errors}")
