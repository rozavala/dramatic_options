"""Dramatic Options — thesis-first thematic equity-options trading system (Alpaca, paper-first).

Core package: orchestrator, config, signal/gate modules, council, data adapters, and the
calibration engine. Runnable entrypoints (per SPEC §10):
    python -m dramatic_options.orchestrator        # one cycle on themes.json
    python -m dramatic_options.orchestrator --demo # offline deterministic cycle
The Streamlit dashboard (dashboard.py), scripts/, and tests/ live at the repo root.
"""
