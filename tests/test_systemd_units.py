"""Systemd unit + deploy.sh wiring checks (T2.5 PR2 units; T3 PR3 adds the weekly L0 scan).

Static, file-shape validation (no systemd, no network): the rendered-at-install templates must
carry the directives the run model depends on, and deploy.sh must arm / stop / verify EXACTLY the
units that exist. These guard against a unit drifting out of the deploy arrays or losing a
load-bearing directive (the OnFailure pager, Type=oneshot, the §C-derived L0 hang ceiling).
"""

from __future__ import annotations

import configparser
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SYSTEMD = REPO / "scripts" / "systemd"
DEPLOY = REPO / "deploy.sh"

ONESHOT_SERVICES = [
    "dramatic-options-l0.service",
    "dramatic-options-l1.service",
    "dramatic-options-l2.service",
]
TIMERS = [
    "dramatic-options-l0.timer",
    "dramatic-options-l1.timer",
    "dramatic-options-l2.timer",
]


def _parse(path: Path) -> configparser.ConfigParser:
    # interpolation=None: unit values contain %n / %i (OnFailure, instance) — never interpolate.
    # optionxform=str: preserve directive case (TimeoutStartSec, not timeoutstartsec).
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read_string(path.read_text())
    return cp


def test_all_referenced_units_exist():
    for name in [*ONESHOT_SERVICES, *TIMERS, "dramatic-options-notify@.service"]:
        assert (SYSTEMD / name).is_file(), f"missing unit template {name}"


def test_oneshot_services_share_the_safe_shape():
    """Every L-tier oneshot pages on hard failure, reads the live-checkout .env, and renders."""
    for name in ONESHOT_SERVICES:
        cp = _parse(SYSTEMD / name)
        assert cp["Service"]["Type"] == "oneshot", name
        assert cp["Unit"]["OnFailure"] == "dramatic-options-notify@%n.service", name
        assert cp["Service"]["EnvironmentFile"] == "__REPO_ROOT__/.env", name
        es = cp["Service"]["ExecStart"]
        assert "__REPO_ROOT__/venv/bin/python -u -m dramatic_options.orchestrator" in es, name
        text = (SYSTEMD / name).read_text()
        assert "__USER__" in text and "__GROUP__" in text, f"{name} not a render template"


def test_l0_service_runs_discovery_with_the_measured_timeout():
    cp = _parse(SYSTEMD / "dramatic-options-l0.service")
    assert cp["Service"]["ExecStart"].endswith("dramatic_options.orchestrator --discover")
    # Hang ceiling DERIVED from the §C cold-cache measurement (see the unit comment): clears the
    # realistic-healthy ~540s ceiling, SIGTERMs a broadly-degraded-provider scan (~1460s).
    assert cp["Service"]["TimeoutStartSec"] == "900"


def test_l1_and_l2_execstart_flags_unchanged():
    assert _parse(SYSTEMD / "dramatic-options-l1.service")["Service"]["ExecStart"].endswith(
        "dramatic_options.orchestrator"
    )
    assert _parse(SYSTEMD / "dramatic-options-l2.service")["Service"]["ExecStart"].endswith(
        "dramatic_options.orchestrator --monitor"
    )


def test_l0_timer_is_weekly_offmarket_and_persistent():
    cp = _parse(SYSTEMD / "dramatic-options-l0.timer")
    oncal = cp["Timer"]["OnCalendar"]
    assert "Sun" in oncal and "America/New_York" in oncal, oncal
    assert cp["Timer"]["Persistent"] == "true"
    assert cp["Timer"]["Unit"] == "dramatic-options-l0.service"
    assert cp["Install"]["WantedBy"] == "timers.target"


def test_every_timer_points_at_an_existing_service():
    for tname in TIMERS:
        unit = _parse(SYSTEMD / tname)["Timer"]["Unit"]
        assert (SYSTEMD / unit).is_file(), f"{tname} -> missing {unit}"


def _deploy_array(name: str) -> set[str]:
    """The l<n>.{timer,service} tokens listed in a deploy.sh bash array (NAME=(...))."""
    m = re.search(rf"^{name}=\((.*?)\)", DEPLOY.read_text(), re.M)
    assert m, f"{name}=(...) not found in deploy.sh"
    return set(re.findall(r"-(l\d\.(?:timer|service))", m.group(1)))


def test_deploy_arrays_cover_exactly_the_unit_set():
    """deploy.sh arms/stops the SAME L-tier units that exist as templates (no drift either way)."""
    assert _deploy_array("TIMERS") == {"l0.timer", "l1.timer", "l2.timer"}
    assert _deploy_array("SERVICES") == {"l0.service", "l1.service", "l2.service"}
