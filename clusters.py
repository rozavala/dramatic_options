"""Correlation-cluster exposure taxonomy (pre-T4) — PREREG_THEMATIC_CONVEXITY §5 amendment 2026-06-03.

The per-name 1% cap treats every underlying as independent, so a basket of correlated names reads as
"diversified" when it is one bet. The first live L0 scan (2026-06-03) surfaced exactly this: 7 of 8
sentinels were one AI-capex-into-power bet (VRT/PWR/GEV/ETN/CCJ/CEG/NEE) spanning two scan baskets. A
**cluster** is an operator-curated, *deterministic* partition of symbols into correlation-budget
groups — each name in **≤1** cluster — and the sizing path caps the aggregate **entry**-premium-at-risk
per cluster at ``convexity_book.cluster_fraction`` of account equity.

Three deliberately-distinct concepts:
  - **theme** (``themes.json``)            — one bet: an underlying + direction + thesis.
  - **basket** (``config.universe.themes``) — a discovery *scan* list; names overlap; a name in many.
  - **cluster** (here)                      — a correlation *budget* partition; a name in ≤1; deterministic.

Keyed ONLY on the symbol → cluster map in config — NEVER on a theme/basket *label*, because a
sentinel's ``theme.name`` can be set by the LLM framer (``sentinels.discovered_to_theme``) and letting
that move a risk cap would breach the hard seam (PREREG §2). Direction-agnostic: premium-at-risk is
additive regardless of direction (a netting model would need clean beta the free feed can't give), so
the operator curates each cluster to be *directionally coherent*. Pure functions — offline-testable.
"""

from __future__ import annotations


class ClusterConfigError(ValueError):
    """Raised when the cluster taxonomy is malformed (overlap, bad types, or cap < per-name)."""


def load_cluster_map(config: dict) -> dict[str, frozenset[str]]:
    """Parse + validate ``config.convexity_book.clusters`` → ``{cluster_name: frozenset(symbols)}``.

    Fail-closed asymmetry (PREREG §5): an **absent/empty** map → ``{}`` (the cap is then inert — every
    name is its own singleton; this is the pre-amendment behaviour, never a halt). A **malformed** map
    raises ``ClusterConfigError``: a symbol in >1 cluster (overlap), bad types, or
    ``cluster_fraction < per_name_fraction`` (a cluster must be able to hold ≥1 full-size name, else
    every clustered name is un-openable — a misconfiguration, not an intent).
    """
    book = config.get("convexity_book", {}) or {}
    raw = book.get("clusters") or {}
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise ClusterConfigError(f"convexity_book.clusters must be an object, got {type(raw).__name__}")

    cmap: dict[str, frozenset[str]] = {}
    seen: dict[str, str] = {}  # symbol → first cluster it appeared in (uniqueness check)
    for name, members in raw.items():
        if name.startswith("_"):  # a "_comment" key is allowed, not a cluster
            continue
        if not isinstance(members, list) or not all(isinstance(s, str) for s in members):
            raise ClusterConfigError(f"cluster {name!r} members must be a list of symbol strings")
        syms = frozenset(s.strip().upper() for s in members if s.strip())
        for s in syms:
            if s in seen:
                raise ClusterConfigError(
                    f"symbol {s} is in two clusters ({seen[s]!r} and {name!r}); a symbol must be in ≤1 cluster"
                )
            seen[s] = name
        cmap[name] = syms

    cf, pnf = book.get("cluster_fraction"), book.get("per_name_fraction")
    if cmap and cf is not None and pnf is not None and float(cf) < float(pnf):
        raise ClusterConfigError(
            f"cluster_fraction ({cf}) < per_name_fraction ({pnf}); a cluster must hold ≥1 full-size name"
        )
    return cmap


def cluster_of(symbol: str, cluster_map: dict[str, frozenset[str]]) -> str | None:
    """The cluster a symbol belongs to, or ``None`` (an unclustered name = its own singleton → the
    cluster cap is inert for it; the per-name cap still binds)."""
    s = symbol.strip().upper()
    for name, members in cluster_map.items():
        if s in members:
            return name
    return None


def members_of(cluster: str, cluster_map: dict[str, frozenset[str]]) -> frozenset[str]:
    """The symbols in a cluster (empty frozenset if the name is unknown)."""
    return cluster_map.get(cluster, frozenset())
