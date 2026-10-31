"""Council proposal types + the proposal→Theme adapter (T2).

A ``CouncilProposal`` is the strategist's synthesized verdict for one candidate, carrying the
per-agent contributions for forward scoring. ``to_theme()`` is the hard-seam boundary: it
projects a proposal down to a ``themes.Theme`` that the *unchanged* deterministic paper loop
consumes. Conviction rides along on the Theme for **recording only** — the loop never reads it
for sizing (PREREG §5: flat-by-slots) and it can never defeat a deterministic veto.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from themes import VALID_DIRECTIONS, Theme

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
    flagged_details: tuple[str, ...] = ()  # #402: WHICH claims were flagged (one per count), for the record


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
    # CGS §10.7 tri-criteria, as ASSERTED by the strategist (None = not asserted → fails closed
    # in select_for_trade). structural_vs_fad above carries the sanctioned strategist-or-proposer
    # fallback (debate.py) — the preview's survivor edge case is preserved.
    under_narrated: bool | None = None
    at_inflection: bool | None = None
    # True when the strategist claimed include=true but violated its own asserted criteria → the
    # include was coerced false (a recorded criteria-veto, DISTINCT from parse_error). Conviction
    # is preserved: criteria-veto rows are recorded-never-traded forward-scoring substrate (Brier),
    # the same class as floor-dropped includes.
    criteria_veto: bool = False

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


def _tri_criteria_pass(p: CouncilProposal) -> bool:
    """The CGS §10.7 tri-criteria, comparison semantics VERBATIM from the §10.8 preview harness
    (scripts/probe_rescore_thesis_only.py): exact string equality + ``is True`` identity, NO
    normalization — a JSON-mode model emitting the string ``"true"`` fails by design (fail-closed,
    preview-identical). ``None`` (never asserted) fails closed."""
    return str(p.structural_vs_fad) == "structural" and p.under_narrated is True and p.at_inflection is True


def select_for_trade(proposals: list[CouncilProposal], *, floor: str) -> list[CouncilProposal]:
    """The proposals that survive to the deterministic gates: strategist said include AND
    conviction ≥ floor AND the §10.7 tri-criteria hold (survivor = include ∧ ≥floor ∧ tri-pass).
    This can only *reduce* the set — it never expands trading or overrides a gate (PREREG §2).
    Dropped proposals are still recorded (forward-scoring substrate). The tri check here is the
    belt-and-suspenders second layer of the rule debate.run_candidate already coerced — §10.7
    names both functions; the rule is in effect at the selection point either way."""
    return [p for p in proposals
            if p.include and passes_floor(p.conviction, floor) and _tri_criteria_pass(p)]
