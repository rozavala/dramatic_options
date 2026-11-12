"""#427 — the two weekly sweeps select as the gate of record does, including #425's 15% floor (dated notes 2026-11-05:
PREREG_MISS_BASERATE §8, PREREG_UNIVERSE_CURATION §6; boundary = the 2026-11-08 sweep)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script", ["scripts/probe_miss_baserate.py", "scripts/probe_basket_gate_baserate.py"])
def test_each_sweep_passes_the_side_guard_and_the_floor(script):
    src = (ROOT / script).read_text()
    calls = len(re.findall(r"select_structure\(", src))
    assert calls >= 1
    assert src.count('require_otm_side=bool(gate.get("otm_side_guard", False))') == calls
    assert src.count('min_otm_moneyness=float(gate.get("min_otm_moneyness", 0.0) or 0.0)') == calls


def test_both_prereg_notes_name_the_boundary():
    assert "2026-11-08 sweep" in (ROOT / "PREREG_MISS_BASERATE.md").read_text()
    assert "2026-11-08 sweep" in (ROOT / "PREREG_UNIVERSE_CURATION.md").read_text()
