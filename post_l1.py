"""The post-L1 measurement unit (``python -m orchestrator --post-l1``; ``dramatic-options-post-l1``): every
measurement pass that runs after the L1 has finished, in one process (PREREG_COUNCIL_GATE_SEPARATION §10.12 and
§10.13 share one unit, so the operator adds the sudoers lines once).

Passes are INDEPENDENT: each runs in its own try/except, so one raising never prevents the next. Exit 1 if any pass
raised (the unit's OnFailure then pages), else 0. A pass's refusals (disabled, L1 not finished, caps, ...) are log
lines inside the pass and return normally, so they exit 0.

A pass is ``(name, fn)`` with ``fn(config) -> object``; it opens its own DB connection, builds its own router and
ledger, and never writes the council of record. Measurement only: none of them trades.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

log = logging.getLogger("post_l1")

Pass = tuple[str, Callable[[dict], object]]


def _repeat_probe(config: dict) -> object:
    from council.repeat_probe import run_live

    return run_live(config)


def _held_reads(config: dict) -> object:
    from council.held_reads import run_live

    return run_live(config)


# Order matters only for the log: the §10.12 probe first, then the §10.13 held pass.
PASSES: list[Pass] = [("repeat_probe", _repeat_probe), ("held_reads", _held_reads)]


def run(config: dict, passes: list[Pass] | None = None) -> int:
    """Run every pass; 1 if any raised, else 0."""
    failed: list[str] = []
    for name, fn in (PASSES if passes is None else passes):
        try:
            fn(config)
        except Exception:  # noqa: BLE001 — one pass failing must never stop the next
            log.exception("post-L1 pass %s failed (the other passes still run)", name)
            failed.append(name)
    if failed:
        log.error("post-L1: %d pass(es) failed: %s", len(failed), ", ".join(failed))
        return 1
    return 0


def main() -> int:
    from config_loader import load_config

    try:
        config = load_config()
    except Exception:  # noqa: BLE001 — no config, no pass can run: fail loudly
        log.exception("post-L1: config failed to load")
        return 1
    return run(config)
