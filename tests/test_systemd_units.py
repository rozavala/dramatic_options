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

import pytest

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
DASHBOARD_SERVICE = "dramatic-options-dashboard.service"
WRAPPER = REPO / "scripts" / "dashboard_run.sh"


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
        assert "__REPO_ROOT__/venv/bin/python -u -m orchestrator" in es, name
        text = (SYSTEMD / name).read_text()
        assert "__USER__" in text and "__GROUP__" in text, f"{name} not a render template"


def test_l0_service_runs_discovery_with_the_measured_timeout():
    cp = _parse(SYSTEMD / "dramatic-options-l0.service")
    assert cp["Service"]["ExecStart"].endswith("-m orchestrator --discover")
    # Hang ceiling DERIVED from the §C cold-cache measurement (see the unit comment): clears the
    # realistic-healthy ~540s ceiling, SIGTERMs a broadly-degraded-provider scan (~1460s).
    assert cp["Service"]["TimeoutStartSec"] == "900"


def test_l1_and_l2_execstart_flags_unchanged():
    assert _parse(SYSTEMD / "dramatic-options-l1.service")["Service"]["ExecStart"].endswith(
        "-m orchestrator"
    )
    assert _parse(SYSTEMD / "dramatic-options-l2.service")["Service"]["ExecStart"].endswith(
        "-m orchestrator --monitor"
    )


def test_no_unit_cmdline_matches_a_neighbours_pkill_pattern():
    """2026-10-15: Real Options' deploy.sh runs `pkill -9 -f orchestrator.py` on the shared host, which
    SIGKILLed our L2 mid-run. No unit of ours may carry a command line that pattern (a regex: '.' is any
    character) can match, so a neighbour's cleanup can never kill a council session or an order submit."""
    pattern = re.compile(r"orchestrator.py")
    for unit in sorted(SYSTEMD.glob("*.service")):
        for line in unit.read_text().splitlines():
            if line.startswith("ExecStart="):
                cmd = line.replace("__REPO_ROOT__", "/home/u/dramatic_options")
                assert not pattern.search(cmd), f"{unit.name}: {cmd}"


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


# ── the Streamlit dashboard service is RETIRED (2026-10-06): the web dashboard replaces it ─────────────
def test_streamlit_dashboard_service_is_retired():
    assert not (REPO / "scripts" / "systemd" / DASHBOARD_SERVICE).exists(), "the retired unit must not be installed"
    assert not WRAPPER.exists(), "the retired wrapper must be gone"
    deploy = DEPLOY.read_text()
    body = deploy[deploy.index("apply_dashboard() {"):]
    body = body[:body.index("\n}\n")]
    assert 'disable --now "$DASHBOARD_SERVICE"' in body and "enable --now" not in body
    assert (REPO / "dashboard.py").exists()   # kept: the web API's panel-parity reference


def test_dashboard_is_handled_outside_the_trading_arrays_and_gate():
    deploy = DEPLOY.read_text()
    # long-running → NOT in the oneshot TIMERS/SERVICES arrays; apply_dashboard handles it separately.
    assert "dashboard" not in re.search(r"^TIMERS=\((.*?)\)", deploy, re.M).group(1)
    assert "dashboard" not in re.search(r"^SERVICES=\((.*?)\)", deploy, re.M).group(1)
    assert "apply_dashboard" in deploy and "DASHBOARD_SERVICE=" in deploy
    # a dashboard failure must NEVER roll back trading → it is not among the verify gate's critical files.
    verify = (REPO / "scripts" / "verify_deploy.sh").read_text()
    crit = re.search(r"CRITICAL_FILES=\((.*?)\)", verify, re.S).group(1)
    assert "dashboard" not in crit


def _deploy_function(name: str) -> str:
    """The text of one shell function from deploy.sh (``name() {`` … the closing ``}`` at column 0)."""
    m = re.search(rf"^{name}\(\) {{\n.*?^}}\n", DEPLOY.read_text(), re.S | re.M)
    assert m, name
    return m.group(0)


def _run_install_units(tmp_path, *, sudo_ok: bool, allow: str = "cp") -> tuple[str, str]:
    import subprocess

    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir(), dst.mkdir()
    (src / "dramatic-options-l1.service").write_text("ExecStart=__REPO_ROOT__/venv/bin/python -u -m orchestrator\n")
    # A fake sudo that permits only the ``allow`` command (cp = classic sudo's wildcard rule; tee = sudo-rs's
    # exact per-unit rules) and refuses everything else, the way a missing NOPASSWD rule does.
    ok_cp = 'command cp "$2" "$3"' if sudo_ok and allow == "cp" else "return 1"
    ok_tee = 'command tee "$2"' if sudo_ok and allow == "tee" else "return 1"
    fake_sudo = ('sudo() { [ "$1" = "-n" ] && shift; case "$1" in cp) ' + ok_cp + ";; tee) " + ok_tee +
                 ";; *) return 0;; esac; }\n")
    script = (f'set -e\nSYSTEMD_SRC="{src}"\nSYSTEMD_DST="{dst}"\nREPO_ROOT=/r\nENV_NAME=DEV\n' + fake_sudo +
              _deploy_function("render_unit") + _deploy_function("install_units") +
              'install_units\necho "FAILED=[$UNITS_FAILED] CHANGED=$UNITS_CHANGED"\n')
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout, (dst / "dramatic-options-l1.service").read_text() if sudo_ok else ""


def test_install_units_records_a_unit_it_could_not_install(tmp_path):
    """2026-10-15: DEV's sudo allowed systemctl but not cp, so every unit install failed with a WARNING and
    the deploy reported success while systemd ran stale units. A failed install is now recorded."""
    stdout, _ = _run_install_units(tmp_path, sudo_ok=False)
    assert "FAILED=[ dramatic-options-l1.service] CHANGED=0" in stdout
    assert "ERROR: could not install dramatic-options-l1.service" in stdout


@pytest.mark.parametrize("allow", ["cp", "tee"])   # PROD's classic-sudo wildcard rule · DEV's sudo-rs exact rules
def test_install_units_installs_the_rendered_unit(tmp_path, allow):
    stdout, installed = _run_install_units(tmp_path, sudo_ok=True, allow=allow)
    assert "FAILED=[] CHANGED=1" in stdout
    assert installed == "ExecStart=/r/venv/bin/python -u -m orchestrator\n"


def test_deploy_fails_at_the_end_when_a_unit_is_stale():
    text = DEPLOY.read_text()
    tail = text[text.index("# STEP 9"):]
    assert 'if [ -n "$UNITS_FAILED" ]' in tail and "exit 1" in tail.split("Deployment finished successfully")[0]
