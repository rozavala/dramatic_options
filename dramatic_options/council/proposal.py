"""Council proposal types + the proposal→Theme adapter (T2).

A ``CouncilProposal`` is the strategist's synthesized verdict for one candidate, carrying the
per-agent contributions for forward scoring. ``to_theme()`` is the hard-seam boundary: it
projects a proposal down to a ``themes.Theme`` that the *unchanged* deterministic paper loop
consumes. Conviction rides along on the Theme for **recording only** — the loop never reads it
for sizing (PREREG §5: flat-by-slots) and it can never defeat a deterministic veto.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dramatic_options.themes import VALID_DIRECTIONS, Theme

# Strict confidence/conviction vocabulary (CLAUDE.md). NEUTRAL is the early-exit / abstain value.
CONVICTION_LEVELS = ("LOW", "MODERATE", "HIGH", "EXTREME")
_RANK = {"NEUTRAL": 0, "LOW": 1, "MODERATE": 2, "HIGH": 3, "EXTREME": 4}


def normalize_conviction(value: str | None) -> str:
    """Coerce to the strict vocabulary; anything unrecognized → NEUTRAL (fail-safe abstain)."""
    v = str(value or "").strip().upper()
    return v if v in _RANK else "NEUTRAL"


def passes_floor(conviction: str | None, floor: str) -> bool:
    """True if conviction is at or above the inclusion floor. NEUTRAL/None never passes."""
    return _RANK.get(normalize_conviction(conviction), 0) >= _RANK.get(normalize_conviction(floor), 2)


@dataclass(frozen=True)
class AgentOutput:
    role: str                       # proposer | adversary | strategist
    provider: str
    model: str
    confidence: str                 # LOW | MODERATE | HIGH | EXTREME | NEUTRAL
    stance: str | None              # the direction this agent argued (for/against the proposal)
    weakest_point: str | None
    raw: dict
    flagged_unsupported: int = 0    # # of claims the authenticity filter stripped
    cost_usd: float = 0.0


@dataclass(frozen=True)
class CouncilProposal:
    theme: str
    symbol: str
    direction: str                  # bullish | bearish
    conviction: str                 # LOW | MODERATE | HIGH | EXTREME | NEUTRAL
    structural_vs_fad: str | None
    weakest_point: str | None
    strategist_summary: str
    rationale: dict                 # per-role summaries + the for/against case
    agent_outputs: list[AgentOutput] = field(default_factory=list)
    cost_usd: float = 0.0
    model_mix: dict = field(default_factory=dict)
    include: bool = True            # the strategist's own keep/drop call (separate from the floor)
    sentinel_id: int | None = None  # T3: set when the judged candidate came from discovery (provenance)

    def to_theme(self, proposal_id: int) -> Theme:
        """Project to a deterministic-loop Theme. ``thesis`` carries the strategist's summary.

        Carries the discovery provenance (``source``/``sentinel_id``) so the deterministic loop can
        apply the sentinel slot reservation and resolve the sentinel at close (T3)."""
        direction = self.direction if self.direction in VALID_DIRECTIONS else "bullish"
        return Theme(
            name=self.theme, symbol=self.symbol, direction=direction,
            thesis=self.strategist_summary or "", active=True,
            proposal_id=proposal_id, conviction=normalize_conviction(self.conviction),
            source="sentinel" if self.sentinel_id is not None else "hand-seed",
            sentinel_id=self.sentinel_id,
        )


def select_for_trade(proposals: list[CouncilProposal], *, floor: str) -> list[CouncilProposal]:
    """The proposals that survive to the deterministic gates: strategist said include AND
    conviction ≥ floor. This can only *reduce* the set — it never expands trading or overrides
    a gate (PREREG §2). Dropped proposals are still recorded (forward-scoring substrate)."""
    return [p for p in proposals if p.include and passes_floor(p.conviction, floor)]
