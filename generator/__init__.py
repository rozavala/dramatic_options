"""Stage-1 thesis GENERATOR — the theme-generation layer (``PREREG_THEME_GENERATOR.md``).

Reads the Stage-0 deterministic corpus (the in-memory PIT union from ``corpus/assemble.py``,
routed by ``corpus/content.py`` coords) and **synthesizes falsifiable secular theses as mechanism
claims** in the FROZEN §3 schema (``PREREG_NARRATION_PROBE.md:73-83``), each **citing** the
supporting corpus records it drew from.

**Hard seam (§1):** PROPOSER only — generation proposes → council judges → the deterministic gate
disposes. Never authorizes capital, never sizes, never sees a gate outcome, **never historically
backtested** (guardrail §6). A generated theme's only live-book path is a future curation-window
admission evaluated by the existing FORWARD apparatus.

**Build posture (§6, this build = Stage A through P1):** additive + INERT against fixtures.
``FakeRouter`` is the DEFAULT (no keys / no network / no live-corpus fetch in tests). The package
reuses the council router + ``FakeRouter`` + the quote-authenticity pattern; no migration.

**Write isolation (§6.4):** the generator writes ONLY under :data:`GENERATOR_RECORDS_DIR` —
``records/`` co-houses BLIND artifacts the 7/10 review consumes (``gate_baserate_surfaced.csv``,
the dated ``*_closeout_*`` / window-screen reads), so a write outside this dir would corrupt the
blind. A merge-blocker test (``tests/test_generator_isolation.py``) asserts that invariant, and a
generator-specific CI import-graph test asserts the live loop never imports this package.

**NOT built here (held for the operator red-team, §6/§11):** P2 (the §3 citation VERIFIER — the
DROP gate + the split ``dropped_entity_unresolved`` / ``dropped_fact_untraced`` counters) and P3
(the ``--generate`` entry + kill/cost gates). P0 builds only the entity-RESOLUTION mechanism.
"""

from __future__ import annotations

# §6.4: the SINGLE write root for every generator artifact. All generator writes route through
# this constant so the merge-blocker test has one thing to assert against; nothing in this package
# may write a blind `records/*` artifact (the 7/10 close-out's substrate) or config/register.
GENERATOR_RECORDS_DIR = "records/generator/"

__all__ = ["GENERATOR_RECORDS_DIR"]
