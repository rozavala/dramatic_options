"""The Council (T2) — the LLM theme-judgment layer (SPEC §5, PREREG §2).

The council only **proposes** themes (which is at inflection, structural-vs-fad, the cleanest
single-name expression, the bull/bear case). The deterministic Layer-1 gates in the paper loop
still **dispose** and can never be overridden by council conviction (the hard seam). Conviction
is recorded and forward-scored ONLY — it never sizes a position and never defeats a veto.

Guardrail §6: the council is **never** backtested historically (training-data lookahead) — it is
validated forward (Brier + contribution scoring). There is intentionally no replay-on-history
entry point anywhere in this package.
"""
