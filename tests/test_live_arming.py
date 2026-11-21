"""#468 T4 arming (inert): the operator's marker renders ``--live`` into the trading units; the deploy gate accepts
the live pair only when armed.

The third live key (``--live``, CLAUDE.md guardrail 1) comes from a root-owned marker the operator creates by hand
(``/etc/dramatic-options/live-armed``, content = the env name), never from the ``.env``. ``deploy.sh`` renders it into
L1 and L2 only when the marker is valid AND the ``.env`` already says armed (PAPER=false, LIVE_TRADING_ENABLED=true,
FORWARD_ENABLED=true); ``verify_deploy.sh`` CHECK 5 then requires the LIVE pair. Everything else renders exactly what
main rendered before this change.

Shell-level tests (no systemd, no sudo): the real ``scripts/live_arming.sh`` with its two constants (the marker path
and the owner uid) pointed at a temp file and this test user, the real ``deploy.sh`` functions, the real
``verify_deploy.sh`` run whole in a temp repo.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SYSTEMD = REPO / "scripts" / "systemd"
DEPLOY = REPO / "deploy.sh"
LIB = REPO / "scripts" / "live_arming.sh"
VERIFY = REPO / "scripts" / "verify_deploy.sh"
L1, L2 = "dramatic-options-l1.service", "dramatic-options-l2.service"
SECRET = "SEKRETVALUE123"   # a key value that must never reach the log

# The render_unit of main before #468, verbatim: the byte-identity reference.
LEGACY_RENDER_UNIT = '''render_unit() {
    sed -e "s|__REPO_ROOT__|${REPO_ROOT}|g" \\
        -e "s|__USER__|$(id -un)|g" \\
        -e "s|__GROUP__|$(id -gn)|g" \\
        -e "s|__ENV_NAME__|${ENV_NAME}|g" \\
        "$1"
}
'''

_KEYS = (f"GEMINI_API_KEY={SECRET}\nXAI_API_KEY={SECRET}\nANTHROPIC_API_KEY={SECRET}\n"
         f"PUSHOVER_API_TOKEN={SECRET}\nPUSHOVER_USER_KEY={SECRET}\n")
_PAPER_PAIR = f"ALPACA_PAPER_KEY_ID={SECRET}\nALPACA_PAPER_SECRET_KEY={SECRET}\n"
_LIVE_PAIR = f"ALPACA_LIVE_KEY_ID={SECRET}\nALPACA_LIVE_SECRET_KEY={SECRET}\n"
# DEV as it runs: paper, trading on the loop.
DEV_ENV = "PAPER=true\nLIVE_TRADING_ENABLED=false\nDRY_RUN=false\nFORWARD_ENABLED=true\n" + _PAPER_PAIR + _KEYS
# PROD as verified read-only on 2026-11-12: the live pair only, every gate shut.
PROD_ENV = "PAPER=false\nLIVE_TRADING_ENABLED=false\nDRY_RUN=true\nFORWARD_ENABLED=false\n" + _LIVE_PAIR + _KEYS
# PROD after the operator's .env act (§4 step 4): the first armed L1 keeps DRY_RUN=true.
ARMED_ENV = "PAPER=false\nLIVE_TRADING_ENABLED=true\nDRY_RUN=true\nFORWARD_ENABLED=true\n" + _LIVE_PAIR + _KEYS


def _lib(marker: Path, owner_uid: int | None = None) -> str:
    """live_arming.sh with the marker path (and the owner uid, unless None) pointed at the test's."""
    src = LIB.read_text()
    out, n = re.subn(r'^LIVE_MARKER="/etc/dramatic-options/live-armed"$', f'LIVE_MARKER="{marker}"', src, flags=re.M)
    assert n == 1, "the marker constant moved — update the harness"
    if owner_uid is not None:
        out, n = re.subn(r"^LIVE_MARKER_OWNER_UID=0$", f"LIVE_MARKER_OWNER_UID={owner_uid}", out, flags=re.M)
        assert n == 1, "the owner constant moved — update the harness"
    return out


def _deploy_function(name: str) -> str:
    m = re.search(rf"^{name}\(\) {{\n.*?^}}\n", DEPLOY.read_text(), re.S | re.M)
    assert m, name
    return m.group(0)


def _deploy_line(prefix: str) -> str:
    m = re.search(rf"^{re.escape(prefix)}.*$", DEPLOY.read_text(), re.M)
    assert m, prefix
    return m.group(0) + "\n"


def _write_marker(path: Path, content: str = "PROD\n", mode: int = 0o644) -> Path:
    path.write_text(content)
    path.chmod(mode)
    return path


def render_all(tmp_path: Path, env: str, *, env_name: str = "PROD", marker: Path | None = None,
               owner_uid: int | None = -1, legacy: bool = False) -> tuple[dict[str, str], str]:
    """Render every template in scripts/systemd the way deploy.sh does. ``legacy`` uses main's pre-#468 render_unit.
    ``owner_uid=-1`` (default) means this test user owns a valid marker; None keeps the real root (0) constant."""
    out = tmp_path / ("legacy" if legacy else "new")
    out.mkdir(exist_ok=True)
    envf = tmp_path / ".env"
    envf.write_text(env)
    marker = marker if marker is not None else tmp_path / "no-such-marker"
    uid = os.getuid() if owner_uid == -1 else owner_uid
    if legacy:
        funcs = LEGACY_RENDER_UNIT
    else:
        funcs = (_lib(marker, uid) + _deploy_line("LIVE_UNITS=(") + _deploy_line("LIVE_FLAG=") +
                 _deploy_function("resolve_live_flag") + _deploy_function("render_unit") + "resolve_live_flag\n")
    script = (f'set -e\nREPO_ROOT=/home/u/dramatic_options\nENV_NAME="{env_name}"\nENV_FILE="{envf}"\n'
              'SERVICE_PREFIX="dramatic-options"\n' + funcs +
              f'for f in "{SYSTEMD}"/*.service "{SYSTEMD}"/*.timer; do render_unit "$f" > "{out}/$(basename "$f")"; done\n')
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return {p.name: p.read_text() for p in sorted(out.iterdir())}, r.stdout


def _execstart(unit_text: str) -> list[str]:
    return [ln for ln in unit_text.splitlines() if ln.startswith("ExecStart=")]


# ── inert today: byte-identical renders ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("env", [DEV_ENV, PROD_ENV, ARMED_ENV], ids=["dev", "prod-as-is", "flags-armed-no-marker"])
def test_no_marker_renders_byte_identical_to_main(tmp_path, env):
    new, log = render_all(tmp_path, env)
    legacy, _ = render_all(tmp_path, env, legacy=True)
    assert set(new) == set(legacy) and len(new) >= 12
    for name in legacy:
        assert new[name] == legacy[name], name
    assert "--live" not in "".join(new.values())
    assert "ARMED on" not in log


def test_no_marker_pins_the_trading_execstarts(tmp_path):
    new, _ = render_all(tmp_path, PROD_ENV)
    assert _execstart(new[L1]) == ["ExecStart=/home/u/dramatic_options/venv/bin/python -u -m orchestrator"]
    assert _execstart(new[L2]) == ["ExecStart=/home/u/dramatic_options/venv/bin/python -u -m orchestrator --monitor"]


def test_flags_armed_without_a_marker_say_so_loudly(tmp_path):
    _, log = render_all(tmp_path, ARMED_ENV)
    assert "REFUSED" in log and "no marker" in log and "rendering NO --live" in log


def test_the_quiet_state_is_one_plain_line(tmp_path):
    _, log = render_all(tmp_path, PROD_ENV)
    assert "live arming: not armed (no marker at" in log and "!!!" not in log


# ── armed: marker + all three flags ──────────────────────────────────────────────────────────────────────────────
def test_marker_and_armed_env_render_live_into_l1_and_l2_only(tmp_path):
    marker = _write_marker(tmp_path / "live-armed")
    new, log = render_all(tmp_path, ARMED_ENV, marker=marker)
    legacy, _ = render_all(tmp_path, ARMED_ENV, legacy=True)
    assert _execstart(new[L1]) == ["ExecStart=/home/u/dramatic_options/venv/bin/python -u -m orchestrator --live"]
    assert _execstart(new[L2]) == [
        "ExecStart=/home/u/dramatic_options/venv/bin/python -u -m orchestrator --monitor --live"]
    for name in legacy:
        if name in (L1, L2):
            # only the ExecStart line differs
            diff = [(a, b) for a, b in zip(legacy[name].splitlines(), new[name].splitlines(), strict=True) if a != b]
            assert len(diff) == 1 and diff[0][1] == diff[0][0] + " --live", name
        else:
            assert new[name] == legacy[name], f"{name} must never get --live"   # L0, post-l1, reach, notify@, web
    assert "LIVE ARMED on PROD" in log and "DRY_RUN=true" in log
    assert SECRET not in log


def test_each_live_unit_has_exactly_one_execstart():
    for name in (L1, L2):
        assert len(_execstart((SYSTEMD / name).read_text())) == 1, name


def test_live_units_are_exactly_l1_and_l2():
    assert _deploy_line("LIVE_UNITS=(").strip() == (
        'LIVE_UNITS=("${SERVICE_PREFIX}-l1.service" "${SERVICE_PREFIX}-l2.service")')


# ── a stray marker, or a partly armed env, renders nothing ───────────────────────────────────────────────────────
_PARTIAL = {
    "paper-true": ARMED_ENV.replace("PAPER=false", "PAPER=true"),
    "paper-unset": ARMED_ENV.replace("PAPER=false\n", ""),
    "paper-garbage": ARMED_ENV.replace("PAPER=false", "PAPER=nope"),
    "live-false": ARMED_ENV.replace("LIVE_TRADING_ENABLED=true", "LIVE_TRADING_ENABLED=false"),
    "live-unset": ARMED_ENV.replace("LIVE_TRADING_ENABLED=true\n", ""),
    "forward-false": ARMED_ENV.replace("FORWARD_ENABLED=true", "FORWARD_ENABLED=false"),
    "live-conflict": ARMED_ENV + "LIVE_TRADING_ENABLED=false\n",
    "paper-conflict": ARMED_ENV + "PAPER=true\n",
    # the armed value LAST (what dotenv/systemd would use): still refused, arming never guesses between two values
    "live-conflict-armed-last": "LIVE_TRADING_ENABLED=false\n" + ARMED_ENV,
    "paper-conflict-armed-last": "PAPER=true\n" + ARMED_ENV,
    "forward-conflict-armed-last": "FORWARD_ENABLED=false\n" + ARMED_ENV,
    "dev": DEV_ENV,
    "prod-as-is": PROD_ENV,
}


@pytest.mark.parametrize("case", sorted(_PARTIAL))
def test_a_valid_marker_on_a_not_armed_env_renders_nothing(tmp_path, case):
    marker = _write_marker(tmp_path / "live-armed")
    new, log = render_all(tmp_path, _PARTIAL[case], marker=marker)
    legacy, _ = render_all(tmp_path, _PARTIAL[case], legacy=True)
    assert new == legacy
    assert "REFUSED" in log and "the .env is not armed" in log and "rendering NO --live" in log


def test_no_env_file_is_not_armed(tmp_path):
    marker = _write_marker(tmp_path / "live-armed")
    envf = tmp_path / "a.env"
    envf.write_text(ARMED_ENV)
    assert _check(tmp_path, marker, env_file=envf) == ("1", "1")                      # armed with it
    assert _check(tmp_path, marker, env_file=tmp_path / "missing.env") == ("0", "1")   # refused, loudly, without


def _check(tmp_path: Path, marker: Path, *, env_file: Path, env_name: str = "PROD",
           owner_uid: int | None = -1, extra_env: dict | None = None) -> tuple[str, str]:
    """live_arming_check alone → (LIVE_ARMED, LIVE_ARMING_LOUD)."""
    uid = os.getuid() if owner_uid == -1 else owner_uid
    script = (_lib(marker, uid) + f'live_arming_check "{env_file}" "{env_name}"\n'
              'echo "ARMED=$LIVE_ARMED LOUD=$LIVE_ARMING_LOUD REASON=$LIVE_ARMING_REASON"\n')
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30,
                       env={**os.environ, **(extra_env or {})})
    assert r.returncode == 0, r.stderr
    m = re.search(r"ARMED=(\d) LOUD=(\d)", r.stdout)
    assert m, r.stdout
    return m.group(1), m.group(2)


# ── the marker must be the operator's act: every malformed marker renders nothing ───────────────────────────────
def _bad_marker(tmp_path: Path, kind: str) -> Path:
    good = _write_marker(tmp_path / "real-marker")
    p = tmp_path / "live-armed"
    if kind == "wrong-env":
        _write_marker(p, "DEV\n")
    elif kind == "empty":
        _write_marker(p, "")
    elif kind == "two-lines":
        _write_marker(p, "PROD\nPROD\n")
    elif kind == "symlink":
        p.symlink_to(good)
    elif kind == "directory":
        p.mkdir()
    elif kind == "group-writable":
        _write_marker(p, mode=0o664)
    elif kind == "world-writable":
        _write_marker(p, mode=0o646)
    elif kind == "unreadable":
        _write_marker(p, mode=0o000)
    else:
        raise AssertionError(kind)
    return p


_BAD_REASON = {   # each check is pinned by its own reason, so no check passes on another's back
    "wrong-env": "names 'DEV', not this env 'PROD'",
    "empty": "is not exactly one line naming an env",
    "two-lines": "is not exactly one line naming an env",
    "symlink": "is a symlink",
    "directory": "is not a regular file",
    "group-writable": "live-armed is group- or other-writable (mode 664)",
    "world-writable": "live-armed is group- or other-writable (mode 646)",
    "unreadable": "is unreadable",
}


@pytest.mark.parametrize("kind", sorted(_BAD_REASON))
def test_a_malformed_marker_renders_nothing_and_says_so(tmp_path, kind):
    if kind == "unreadable" and os.getuid() == 0:
        pytest.skip("root reads a mode-000 file")
    marker = _bad_marker(tmp_path, kind)
    new, log = render_all(tmp_path, ARMED_ENV, marker=marker)
    legacy, _ = render_all(tmp_path, ARMED_ENV, legacy=True)
    assert new == legacy
    assert "REFUSED" in log and "rendering NO --live" in log
    assert _BAD_REASON[kind] in log, log
    assert SECRET not in log


@pytest.mark.skipif(os.getuid() == 0, reason="the marker must be root-owned; a root test user owns it")
def test_a_marker_not_owned_by_root_renders_nothing(tmp_path):
    marker = _write_marker(tmp_path / "live-armed")
    new, log = render_all(tmp_path, ARMED_ENV, marker=marker, owner_uid=None)   # the real uid-0 rule
    legacy, _ = render_all(tmp_path, ARMED_ENV, legacy=True)
    assert new == legacy
    # the directory is checked first, so the refusal names it (the file's own owner check is the same loop)
    assert f"{tmp_path} is owned by uid {os.getuid()}, not uid 0" in log


def test_the_marker_names_the_env_it_arms(tmp_path):
    marker = _write_marker(tmp_path / "live-armed", "PROD\n")
    envf = tmp_path / "a.env"
    envf.write_text(ARMED_ENV)
    assert _check(tmp_path, marker, env_file=envf, env_name="PROD") == ("1", "1")
    assert _check(tmp_path, marker, env_file=envf, env_name="DEV") == ("0", "1")
    assert _check(tmp_path, marker, env_file=envf, env_name="") == ("0", "1")


def test_the_marker_path_cannot_be_moved_by_the_environment(tmp_path):
    # the real constants: an env var LIVE_MARKER pointing at a valid marker is ignored (sourcing resets it)
    marker = _write_marker(tmp_path / "live-armed")
    envf = tmp_path / "a.env"
    envf.write_text(ARMED_ENV)
    script = (LIB.read_text() + f'live_arming_check "{envf}" PROD\necho "ARMED=$LIVE_ARMED M=$LIVE_MARKER"\n')
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30,
                       env={**os.environ, "LIVE_MARKER": str(marker), "LIVE_MARKER_OWNER_UID": str(os.getuid())})
    assert "M=/etc/dramatic-options/live-armed" in r.stdout
    if not Path("/etc/dramatic-options/live-armed").exists():
        assert "ARMED=0" in r.stdout


def test_nothing_in_the_repo_writes_the_marker():
    lib = LIB.read_text()
    assert lib.count("/etc/dramatic-options/live-armed") == 2   # the header comment and the constant
    for f in [DEPLOY, VERIFY, LIB, *sorted((REPO / "scripts").glob("*.sh"))]:
        text = f.read_text()
        assert not re.search(r"(touch|tee|>)\s*\"?\$LIVE_MARKER", text), f
        assert not re.search(r"(touch|tee|>)\s*\"?/etc/dramatic-options", text), f
    for f in [DEPLOY, *sorted((REPO / "scripts").glob("*.sh"))]:
        if f != LIB:
            assert "/etc/dramatic-options" not in f.read_text(), f"{f.name} must read the marker only through the lib"


# ── wiring: deploy.sh decides before every render, and loads the lib before touching anything ────────────────────
def test_deploy_sources_the_lib_before_it_stops_anything():
    text = DEPLOY.read_text()
    src = text.index('\n. "$REPO_ROOT/scripts/live_arming.sh"\n')
    assert src < text.index("\nwait_clear_of_ticks\n")          # the first command that waits on / touches systemd
    assert src < text.index('echo "--- 1. Stopping timers')


def test_install_units_decides_before_rendering():
    body = _deploy_function("install_units")
    assert body.index("resolve_live_flag") < body.index("render_unit")


def test_rollback_renders_through_install_units():
    # the rollback re-renders with the same decision (marker + .env), so an armed box stays armed after a rollback
    body = _deploy_function("rollback_and_restart")
    assert "install_units" in body and "render_unit" not in body


# ── verify_deploy.sh CHECK 5: the live pair only when armed; today's paper rule everywhere else ─────────────────
def run_verify(tmp_path: Path, env: str | None, *, marker_content: str | None = None, marker_mode: int = 0o644,
               env_name: str = "PROD") -> tuple[int, str, str]:
    """Run the whole scripts/verify_deploy.sh in a temp repo → (exit code, stdout, health log)."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(VERIFY, repo / "scripts" / "verify_deploy.sh")
    marker = tmp_path / "live-armed"
    if marker_content is not None:
        _write_marker(marker, marker_content, marker_mode)
    (repo / "scripts" / "live_arming.sh").write_text(_lib(marker, os.getuid()))
    for f in ("deploy.sh", "orchestrator.py"):      # CHECK 4's critical files (no config_loader → CHECK 2 skips)
        (repo / f).write_text("")
    if env is not None:
        (repo / ".env").write_text(env)
    r = subprocess.run(["bash", "scripts/verify_deploy.sh"], cwd=repo, capture_output=True, text=True, timeout=60,
                       env={**os.environ, "ENV_NAME": env_name, "HEALTH_URL": ""})
    hl = repo / "logs" / "deploy_health.log"
    return r.returncode, r.stdout, hl.read_text() if hl.exists() else ""


@pytest.mark.parametrize("name,env,marker,ok,msg", [
    # every not-armed trading env: today's paper rule, word for word
    ("dev", DEV_ENV, None, True, "venue-named paper pair present"),
    ("dev-stray-marker", DEV_ENV, "PROD\n", True, "venue-named paper pair present"),
    ("flags-armed-no-marker", ARMED_ENV, None, False,
     "no Alpaca paper key pair (ALPACA_PAPER_KEY_ID/ALPACA_PAPER_SECRET_KEY)"),
    ("wrong-env-marker", ARMED_ENV, "DEV\n", False, "no Alpaca paper key pair"),
    # armed: the live pair
    ("armed-live-pair", ARMED_ENV, "PROD\n", True, "venue-named live pair present"),
    ("armed-paper-pair-only", ARMED_ENV.replace(_LIVE_PAIR, _PAPER_PAIR), "PROD\n", False,
     "no Alpaca live key pair (ALPACA_LIVE_KEY_ID/ALPACA_LIVE_SECRET_KEY)"),
    ("armed-half-live-pair", ARMED_ENV.replace(f"ALPACA_LIVE_SECRET_KEY={SECRET}\n", ""), "PROD\n", False,
     "no Alpaca live key pair"),
    ("armed-placeholder", ARMED_ENV.replace(f"ALPACA_LIVE_KEY_ID={SECRET}", "ALPACA_LIVE_KEY_ID=your_key"),
     "PROD\n", False, "no Alpaca live key pair"),
    # legacy names stay refused, armed or not
    ("armed-legacy", ARMED_ENV + "ALPACA_API_KEY=x\n", "PROD\n", False, "legacy Alpaca name(s) in .env: ALPACA_API_KEY"),
    ("armed-legacy-paper", ARMED_ENV + "ALPACA_PAPER=false\n", "PROD\n", False, "legacy Alpaca name"),
    ("dev-legacy", DEV_ENV + "ALPACA_SECRET_KEY=x\n", None, False, "legacy Alpaca name"),
    # inert PROD as it stands: the key assertion is skipped
    ("prod-as-is", PROD_ENV, None, True, "inert env; .env key assertion skipped"),
    ("prod-as-is-stray-marker", PROD_ENV, "PROD\n", True, "inert env; .env key assertion skipped"),
])
def test_verify_check5(tmp_path, name, env, marker, ok, msg):
    code, out, health = run_verify(tmp_path, env, marker_content=marker)
    assert msg in out, out
    assert (code == 0) is ok, out
    assert SECRET not in out and SECRET not in health
    if name == "armed-live-pair":
        assert "requiring the LIVE key pair" in out
    if name in ("dev-stray-marker", "flags-armed-no-marker", "wrong-env-marker"):
        assert "not armed, so the paper pair is required" in out


def test_verify_without_the_helper_keeps_the_paper_rule(tmp_path):
    code, out, _ = run_verify(tmp_path, ARMED_ENV, marker_content="PROD\n")
    assert code == 0
    (tmp_path / "repo" / "scripts" / "live_arming.sh").unlink()
    r = subprocess.run(["bash", "scripts/verify_deploy.sh"], cwd=tmp_path / "repo", capture_output=True, text=True,
                       timeout=60, env={**os.environ, "ENV_NAME": "PROD", "HEALTH_URL": ""})
    assert r.returncode != 0 and "no Alpaca paper key pair" in r.stdout


# ── review fixes (#541): one-line marker, its directory, PROD only, dotenv-subset flag reading, the deploy guard ──
@pytest.mark.parametrize("content,armed", [
    ("PROD", True), ("PROD\n", True), ("PROD\r\n", True), ("PROD  \t\n\n\n", True),
    ("P\nR\nO\nD\n", False), ("PR OD\n", False), (" PROD\n", False), ("PROD\nx\n", False),
    ("PROD\nPROD\n", False), ("\nPROD\n", False),
])
def test_the_marker_is_exactly_one_line(tmp_path, content, armed):
    marker = _write_marker(tmp_path / "live-armed", content)
    envf = tmp_path / "a.env"
    envf.write_text(ARMED_ENV)
    assert _check(tmp_path, marker, env_file=envf) == (("1" if armed else "0"), "1")


@pytest.mark.parametrize("mode", [0o775, 0o757, 0o777])
def test_a_writable_marker_directory_renders_nothing(tmp_path, mode):
    d = tmp_path / "etc-dir"
    d.mkdir()
    marker = _write_marker(d / "live-armed")
    d.chmod(mode)
    new, log = render_all(tmp_path, ARMED_ENV, marker=marker)
    legacy, _ = render_all(tmp_path, ARMED_ENV, legacy=True)
    assert new == legacy
    assert f"{d} is group- or other-writable (mode {mode:o})" in log


def test_a_symlinked_marker_directory_renders_nothing(tmp_path):
    real = tmp_path / "real-dir"
    real.mkdir(mode=0o755)
    _write_marker(real / "live-armed")
    (tmp_path / "link-dir").symlink_to(real)
    new, log = render_all(tmp_path, ARMED_ENV, marker=tmp_path / "link-dir" / "live-armed")
    assert "--live" not in "".join(new.values()) and "directory" in log and "is a symlink" in log


def test_a_valid_marker_in_a_safe_directory_arms(tmp_path):
    d = tmp_path / "etc-dir"
    d.mkdir(mode=0o755)
    new, _ = render_all(tmp_path, ARMED_ENV, marker=_write_marker(d / "live-armed"))
    assert _execstart(new[L1])[0].endswith(" --live")


def test_only_prod_can_be_armed(tmp_path):
    marker = _write_marker(tmp_path / "live-armed", "DEV\n")
    new, log = render_all(tmp_path, ARMED_ENV, marker=marker, env_name="DEV")
    legacy, _ = render_all(tmp_path, ARMED_ENV, env_name="DEV", legacy=True)
    assert new == legacy
    assert "only PROD can be armed" in log and "rendering NO --live" in log


@pytest.mark.parametrize("line,armed", [
    ("LIVE_TRADING_ENABLED=true", True),
    ('LIVE_TRADING_ENABLED="true"', True),
    ("LIVE_TRADING_ENABLED='true'", True),
    ("LIVE_TRADING_ENABLED=  TRUE  ", True),
    ("export LIVE_TRADING_ENABLED=true", True),
    ("LIVE_TRADING_ENABLED=tr ue", False),
    ('LIVE_TRADING_ENABLED=t"r"ue', False),
    ("LIVE_TRADING_ENABLED=\"true'", False),
    ('LIVE_TRADING_ENABLED=""true""', False),
    ("LIVE_TRADING_ENABLED=true # armed", False),
])
def test_flag_values_are_read_as_a_subset_of_dotenv(tmp_path, line, armed):
    marker = _write_marker(tmp_path / "live-armed")
    envf = tmp_path / "a.env"
    envf.write_text(ARMED_ENV.replace("LIVE_TRADING_ENABLED=true", line))
    assert _check(tmp_path, marker, env_file=envf)[0] == ("1" if armed else "0")


@pytest.mark.parametrize("line", ["PAPER=fal se", "PAPER='false\"", 'PAPER=f"alse'])
def test_paper_values_are_read_as_a_subset_of_dotenv(tmp_path, line):
    marker = _write_marker(tmp_path / "live-armed")
    envf = tmp_path / "a.env"
    envf.write_text(ARMED_ENV.replace("PAPER=false", line))
    assert _check(tmp_path, marker, env_file=envf)[0] == "0"


def test_an_export_line_with_another_value_is_a_conflict(tmp_path):
    marker = _write_marker(tmp_path / "live-armed")
    envf = tmp_path / "a.env"
    envf.write_text(ARMED_ENV + "export LIVE_TRADING_ENABLED=false\n")
    assert _check(tmp_path, marker, env_file=envf)[0] == "0"


def _guard(tmp_path: Path, marker: Path, given: str) -> tuple[int, str]:
    script = (_lib(marker, os.getuid()) + f'live_deploy_guard "{given}"; rc=$?\n'
              'echo "RC=$rc REASON=$LIVE_GUARD_REASON"\n')
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    m = re.search(r"RC=(\d+) REASON=(.*)", r.stdout)
    assert m, r.stdout + r.stderr
    return int(m.group(1)), m.group(2)


@pytest.mark.parametrize("given", ["", "DEV", "PROD"])
def test_the_guard_passes_every_deploy_when_there_is_no_marker(tmp_path, given):
    assert _guard(tmp_path, tmp_path / "no-marker", given) == (0, "")


@pytest.mark.parametrize("content,given,ok,why", [
    ("PROD\n", "PROD", True, ""),
    ("PROD\n", "", False, "ENV_NAME was not given"),
    ("PROD\n", "DEV", False, "names 'PROD' but this deploy is ENV_NAME='DEV'"),
    ("P\nROD\n", "PROD", False, "cannot be read as one line"),
    ("DEV\n", "PROD", False, "names 'DEV' but this deploy is ENV_NAME='PROD'"),
])
def test_the_guard_refuses_a_deploy_that_does_not_name_the_marker_env(tmp_path, content, given, ok, why):
    rc, reason = _guard(tmp_path, _write_marker(tmp_path / "live-armed", content), given)
    assert (rc == 0) is ok and why in reason


@pytest.mark.skipif(os.getuid() == 0, reason="root reads a mode-000 file")
def test_the_guard_refuses_an_unreadable_marker(tmp_path):
    rc, reason = _guard(tmp_path, _write_marker(tmp_path / "live-armed", mode=0o000), "PROD")
    assert rc == 1 and "cannot be read" in reason


# ── the whole deploy.sh in a sandbox (#541 review M2/M3/L4): stubbed sudo/systemctl/pkill/pip/git, a temp
# SYSTEMD_DST, lock and marker. Nothing here reaches systemd, /etc or another process. ─────────────────────────────
_STUBS = {
    # sudo: drop -n, refuse the install of $FAIL_INSTALL (cp's / tee's last argument), run everything else
    "sudo": '[ "$1" = -n ] && shift\ncase "$1" in cp|tee) t="${*: -1}"\n'
            '  if [ -n "$FAIL_INSTALL" ] && [ "$(basename "$t")" = "$FAIL_INSTALL" ]; then exit 1; fi ;; esac\nexec "$@"\n',
    # systemctl: log every call; keep the enabled set in $SANDBOX/enabled so STEP 8's is-active sees it
    "systemctl": 'echo "$*" >> "$SANDBOX/calls"\nE="$SANDBOX/enabled"; touch "$E"\ncase "$1" in\n'
                 '  is-active) u="${*: -1}"; grep -qxF "$u" "$E" && { echo active; exit 0; }; echo inactive; exit 3 ;;\n'
                 '  show) echo ""; exit 0 ;;\n'
                 '  enable) for a in "$@"; do case "$a" in enable|--now) ;; *) echo "$a" >> "$E" ;; esac; done ;;\n'
                 '  disable) for a in "$@"; do case "$a" in disable|--now) ;; *) grep -vxF "$a" "$E" > "$E.t"; '
                 'mv "$E.t" "$E" ;; esac; done ;;\nesac\nexit 0\n',
    "pkill": 'echo "pkill $*" >> "$SANDBOX/calls"\nexit 0\n',
    "pip": "exit 0\n",
    "npm": "exit 0\n",
    "git": 'case "$1" in rev-parse) echo 0123456789abcdef ;; esac\nexit 0\n',
}
_TIMERS = [f"dramatic-options-{t}.timer" for t in ("l0", "l1", "l2", "reach", "post-l1")]
REHEARSAL_ENV = "PAPER=true\nLIVE_TRADING_ENABLED=false\nDRY_RUN=true\nFORWARD_ENABLED=true\n" + _PAPER_PAIR + _KEYS


def run_deploy(tmp_path: Path, env: str, *, env_name: str | None, marker_content: str | None = None,
               installed: dict[str, str] | None = None, fail_install: str | None = None, marker_mode: int = 0o644):
    """Run the real deploy.sh in a temp repo → (exit code, output, systemctl/pkill calls, enabled timers, installed)."""
    sandbox = tmp_path / "sandbox"
    repo, dst, bindir, etc = sandbox / "repo", sandbox / "dst", sandbox / "bin", sandbox / "etc-dir"
    for d in (repo / "scripts", dst, bindir, repo / "venv" / "bin"):
        d.mkdir(parents=True)
    etc.mkdir(mode=0o755)
    text = DEPLOY.read_text()
    for old, new in (('SYSTEMD_DST="/etc/systemd/system"', f'SYSTEMD_DST="{dst}"'),
                     ('DEPLOY_LOCK="/tmp/${SERVICE_PREFIX}-deploy.lock"', f'DEPLOY_LOCK="{sandbox}/deploy.lock"')):
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    (repo / "deploy.sh").write_text(text)
    shutil.copytree(SYSTEMD, repo / "scripts" / "systemd")
    shutil.copy(VERIFY, repo / "scripts" / "verify_deploy.sh")
    shutil.copy(REPO / "scripts" / "predeploy_guard.sh", repo / "scripts" / "predeploy_guard.sh")
    marker = etc / "live-armed"
    (repo / "scripts" / "live_arming.sh").write_text(_lib(marker, os.getuid()))
    if marker_content is not None:
        _write_marker(marker, marker_content, marker_mode)
    (repo / "orchestrator.py").write_text("")
    (repo / "venv" / "bin" / "activate").write_text("")
    (repo / ".env").write_text(env)
    for name, content in (installed or {}).items():
        (dst / name).write_text(content)
    for name, body in _STUBS.items():
        (bindir / name).write_text("#!/bin/bash\n" + body)
        (bindir / name).chmod(0o755)
    run_env = {k: v for k, v in os.environ.items() if k not in ("ENV_NAME", "FAIL_INSTALL", "HEALTH_URL")}
    run_env.update(PATH=f"{bindir}:{os.environ['PATH']}", SANDBOX=str(sandbox))
    if env_name is not None:
        run_env["ENV_NAME"] = env_name
    if fail_install:
        run_env["FAIL_INSTALL"] = fail_install
    r = subprocess.run(["bash", "deploy.sh"], cwd=repo, capture_output=True, text=True, timeout=120, env=run_env)
    calls = (sandbox / "calls").read_text().splitlines() if (sandbox / "calls").exists() else []
    enabled = (sandbox / "enabled").read_text().split() if (sandbox / "enabled").exists() else []
    inst = {p.name: p.read_text() for p in dst.iterdir()}
    return r.returncode, r.stdout + r.stderr, calls, enabled, inst


def _enabled_timers(enabled: list[str]) -> list[str]:
    return sorted(t for t in enabled if t.endswith(".timer"))


def test_sandbox_unarmed_dev_deploys_as_before(tmp_path):
    code, out, calls, enabled, inst = run_deploy(tmp_path, DEV_ENV, env_name="DEV")
    assert code == 0, out
    assert _enabled_timers(enabled) == sorted(_TIMERS)
    assert not any(" --live" in ln for ln in _execstart(inst[L1]) + _execstart(inst[L2]))
    assert "live arming: not armed (no marker" in out and "--live not rendered" in out


def test_sandbox_armed_prod_installs_live_l1_l2_and_enables_timers(tmp_path):
    code, out, calls, enabled, inst = run_deploy(tmp_path, ARMED_ENV, env_name="PROD", marker_content="PROD\n")
    assert code == 0, out
    assert _execstart(inst[L1])[0].endswith("-m orchestrator --live")
    assert _execstart(inst[L2])[0].endswith("-m orchestrator --monitor --live")
    assert _enabled_timers(enabled) == sorted(_TIMERS)
    assert "LIVE ARMED on PROD" in out and "venue-named live pair present" in out and "--live RENDERED (ARMED)" in out
    assert SECRET not in out


@pytest.mark.parametrize("env_name,why", [
    (None, "ENV_NAME was not given (this deploy would default to DEV)"),
    ("", "ENV_NAME was not given"),
    ("DEV", "names 'PROD' but this deploy is ENV_NAME='DEV'"),
])
def test_sandbox_a_deploy_not_naming_the_marker_env_aborts_before_any_change(tmp_path, env_name, why):
    before = {L1: "SENTINEL-L1\n", L2: "SENTINEL-L2\n"}
    code, out, calls, enabled, inst = run_deploy(tmp_path, ARMED_ENV, env_name=env_name, marker_content="PROD\n",
                                                 installed=before)
    assert code != 0
    assert "DEPLOY ABORTED BEFORE ANY CHANGE" in out and why in out
    assert calls == [] and enabled == []           # no stop, no pkill, no enable/disable: systemd untouched
    assert inst == before                           # no unit re-rendered
    assert "--- 1. Stopping" not in out


@pytest.mark.parametrize("failing", [L1, L2])
def test_sandbox_an_armed_deploy_with_a_failed_live_unit_install_enables_no_timer(tmp_path, failing):
    # the box before its arming deploy: unarmed units installed (no --live)
    unarmed, _ = render_all(tmp_path, ARMED_ENV)
    code, out, calls, enabled, inst = run_deploy(tmp_path, ARMED_ENV, env_name="PROD", marker_content="PROD\n",
                                                 installed={L1: unarmed[L1], L2: unarmed[L2]}, fail_install=failing)
    assert code != 0
    assert _enabled_timers(enabled) == []
    assert not any(c.startswith("enable") and ".timer" in c for c in calls), calls
    assert any(c.startswith("disable --now") and "dramatic-options-l1.timer" in c for c in calls)
    assert "DISAGREE WITH THE ARMING DECISION" in out and f"{failing}(installed: none, decided: live)" in out


def test_sandbox_a_disarming_deploy_that_keeps_the_timers_on_aborts_before_any_change(tmp_path):
    # armed units installed; the operator removed the marker and flipped the .env to the paper rehearsal while
    # FORWARD_ENABLED stays true. Re-rendering without --live under running timers would strip a live book's L2, so
    # the deploy now refuses before any change (N3), well before the timer gate could be reached.
    marker = _write_marker(tmp_path / "m", "PROD\n")
    armed, _ = render_all(tmp_path, ARMED_ENV, marker=marker)
    before = {L1: armed[L1], L2: armed[L2]}
    code, out, calls, enabled, inst = run_deploy(tmp_path, REHEARSAL_ENV, env_name="PROD", installed=before,
                                                 fail_install=L2)
    assert code != 0 and calls == [] and inst == before
    assert "DEPLOY ABORTED BEFORE ANY CHANGE" in out and "carry --live" in out


@pytest.mark.parametrize("dry,expect", [
    ("true", "DRY_RUN=true: the live path logs every order and transmits nothing"),
    ("false", "DRY_RUN=false: the live path is TRANSMITTING REAL-MONEY ORDERS"),
    ("", "DRY_RUN is unset in .env"),
])
def test_the_armed_banner_states_the_real_dry_run(tmp_path, dry, expect):
    env = ARMED_ENV.replace("DRY_RUN=true", f"DRY_RUN={dry}")
    _, log = render_all(tmp_path, env, marker=_write_marker(tmp_path / "live-armed"))
    assert expect in log
    if dry != "true":
        assert "transmits nothing" not in log


# ── DEPLOYMENT.md step 8 (#541 review M1): the DRY_RUN cycle's rows are archived before the flip, and the operator's
# precheck refuses any row left in the real book. The snippets are run exactly as the doc prints them. ─────────────
def _doc_block(opening: str, closing: str) -> str:
    doc = (REPO / "DEPLOYMENT.md").read_text()
    start = doc.index(opening) + len(opening)
    body = doc[start:doc.index(closing, start)]
    return "\n".join(ln[6:] if ln.startswith("      ") else ln for ln in body.splitlines()) + "\n"


def _precheck(cwd: Path) -> subprocess.CompletedProcess:
    import sys

    script = _doc_block("venv/bin/python - <<'EOF'\n", "      EOF\n")
    return subprocess.run([sys.executable, "-c", script], cwd=cwd, capture_output=True, text=True, timeout=30)


def _real_book(tmp_path: Path, statuses: list[str]) -> Path:
    import orchestrator
    import state

    (tmp_path / "data").mkdir(exist_ok=True)
    conn = state.connect(tmp_path / "data" / "dramatic_options.db")
    orchestrator._ensure_schema(conn)
    for st in statuses:
        conn.execute("INSERT INTO convexity_positions (opened_at, theme, symbol, direction, structure_kind, "
                     "contract_symbol, contracts, entry_premium_per_contract, total_premium, status) "
                     "VALUES ('2027-01-04', 't', 'X', 'long', 'single', 'X270115C00010000', 1, 10.0, 10.0, ?)", (st,))
    conn.commit()
    conn.close()
    return tmp_path


def test_the_precheck_passes_with_no_db(tmp_path):
    r = _precheck(tmp_path)
    assert r.returncode == 0 and r.stdout.startswith("PASS"), r.stdout + r.stderr


def test_the_precheck_passes_on_an_empty_book(tmp_path):
    r = _precheck(_real_book(tmp_path, []))
    assert r.returncode == 0 and "PASS: convexity_positions is empty" in r.stdout, r.stdout + r.stderr


@pytest.mark.parametrize("statuses", [["open"], ["pending"], ["carried"], ["closing"], ["closed"], ["open", "closed"]])
def test_the_precheck_refuses_any_row_the_dry_run_cycle_left(tmp_path, statuses):
    r = _precheck(_real_book(tmp_path, statuses))
    assert r.returncode == 1 and r.stdout.startswith("FAIL"), r.stdout + r.stderr


def test_the_archive_step_moves_the_db_aside_and_the_precheck_then_passes(tmp_path):
    from datetime import date

    _real_book(tmp_path, ["open"])
    assert _precheck(tmp_path).returncode == 1
    r = _archive(tmp_path)
    assert r.returncode == 0 and "ARCHIVED to" in r.stdout, r.stdout + r.stderr
    assert not (tmp_path / "data" / "dramatic_options.db").exists()
    assert (tmp_path / "data" / "archive" / f"{date.today():%Y-%m-%d}-dryrun" / "dramatic_options.db").exists()
    assert _precheck(tmp_path).returncode == 0


def test_the_doc_says_the_rollback_keeps_an_armed_box_armed():
    doc = (REPO / "DEPLOYMENT.md").read_text()
    assert "an armed box that fails its verify gate stays armed after the rollback" in doc


# ── re-review follow-ups (#541): disarm to the inert state (N1), a WAL-safe archive (N2), no --live stripped under
# running timers (N3), the step 8 order and the production-merge hold (N4) ──────────────────────────────────────
def _armed_installed(tmp_path: Path) -> dict[str, str]:
    armed, _ = render_all(tmp_path, ARMED_ENV, marker=_write_marker(tmp_path / "armed-marker", "PROD\n"))
    assert _execstart(armed[L1])[0].endswith(" --live") and _execstart(armed[L2])[0].endswith(" --live")
    return {L1: armed[L1], L2: armed[L2]}


def _disarmed_env_from_doc() -> str:
    block = _doc_block("2. The disarmed `.env`, exactly today's inert PROD (the live pair stays; no paper pair):\n"
                       "   ```\n", "   ```\n")
    flags = [ln.strip() for ln in block.splitlines() if ln.strip()]
    assert flags == ["PAPER=false", "LIVE_TRADING_ENABLED=false", "DRY_RUN=true", "FORWARD_ENABLED=false"], flags
    return "\n".join(flags) + "\n"


def test_the_documented_disarm_env_passes_verify(tmp_path):
    code, out, _ = run_verify(tmp_path, _disarmed_env_from_doc() + _LIVE_PAIR + _KEYS)
    assert code == 0 and "inert env; .env key assertion skipped" in out


def test_the_documented_disarm_deploys_with_no_timer_and_no_live(tmp_path):
    # the doc's order: KILL, the disarmed .env, the marker removed, then a deploy naming PROD
    code, out, calls, enabled, inst = run_deploy(tmp_path, _disarmed_env_from_doc() + _LIVE_PAIR + _KEYS,
                                                 env_name="PROD", installed=_armed_installed(tmp_path))
    assert code == 0, out
    assert _enabled_timers(enabled) == []
    assert any(c.startswith("disable --now") and "dramatic-options-l2.timer" in c for c in calls)
    assert not any(c.startswith("enable") and ".timer" in c for c in calls)
    assert not _execstart(inst[L1])[0].endswith("--live") and not _execstart(inst[L2])[0].endswith("--live")


def test_the_disarm_order_and_what_kill_does_are_stated():
    doc = (REPO / "DEPLOYMENT.md").read_text()
    sec = doc[doc.index("**Disarm**"):doc.index("**What the marker is, and is not.**")]
    order = [sec.index(k) for k in ("1. `touch KILL`", "2. The disarmed `.env`", "3. Remove the marker",
                                    "4. Deploy with `ENV_NAME=PROD`")]
    assert order == sorted(order)
    assert "`touch KILL` halts the L1 **and the L2**" in sec and "not managed" in sec
    assert "wind down under the armed L2" in sec


@pytest.mark.parametrize("why,setup", [
    ("is group- or other-writable (mode 664)", "bad-mode"),
    ("no marker", "removed"),
    ("names 'PROD'", "flags-off"),
])
def test_sandbox_stripping_live_under_running_timers_aborts_before_any_change(tmp_path, why, setup):
    before = _armed_installed(tmp_path)
    env = ARMED_ENV
    marker = None if setup == "removed" else "PROD\n"
    if setup == "flags-off":   # the marker stays, the .env says paper rehearsal, FORWARD stays on
        env = REHEARSAL_ENV
        why = "carry --live"
    code, out, calls, enabled, inst = run_deploy(tmp_path, env, env_name="PROD", marker_content=marker,
                                                 installed=before, marker_mode=0o664 if setup == "bad-mode" else 0o644)
    assert code != 0 and calls == [] and enabled == [] and inst == before
    assert "DEPLOY ABORTED BEFORE ANY CHANGE" in out and why in out


def test_sandbox_an_armed_box_redeploys_armed(tmp_path):
    code, out, calls, enabled, inst = run_deploy(tmp_path, ARMED_ENV, env_name="PROD", marker_content="PROD\n",
                                                 installed=_armed_installed(tmp_path))
    assert code == 0, out
    assert _enabled_timers(enabled) == sorted(_TIMERS) and _execstart(inst[L2])[0].endswith("--live")


def _archive(cwd: Path, label: str = "dryrun") -> subprocess.CompletedProcess:
    bindir = cwd / "stub-bin"
    bindir.mkdir(exist_ok=True)
    for name in ("sudo", "systemctl"):
        (bindir / name).write_text("#!/bin/bash\n" + _STUBS[name])
        (bindir / name).chmod(0o755)
    snippet = _doc_block("   2. Archive the DB (keep the three files together, under their own names):\n"
                         "      ```\n", "      ```\n")
    assert snippet.startswith("label=dryrun")
    snippet = snippet.replace("label=dryrun", f"label={label}", 1)
    return subprocess.run(["bash", "-c", snippet], cwd=cwd, capture_output=True, text=True, timeout=30,
                          env={**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "SANDBOX": str(cwd)})


def test_the_archive_keeps_an_uncheckpointed_wal_readable(tmp_path):
    import sqlite3
    from datetime import date

    (tmp_path / "data").mkdir()
    live = sqlite3.connect(tmp_path / "data" / "dramatic_options.db")
    live.execute("PRAGMA journal_mode=WAL")
    live.execute("PRAGMA wal_autocheckpoint=0")
    live.execute("CREATE TABLE t (x)")
    live.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(7)])
    live.commit()                                  # committed to the -wal, never checkpointed into the main file
    assert (tmp_path / "data" / "dramatic_options.db-wal").stat().st_size > 0
    r = _archive(tmp_path)
    assert r.returncode == 0 and "ARCHIVED to" in r.stdout, r.stdout + r.stderr
    d = tmp_path / "data" / "archive" / f"{date.today():%Y-%m-%d}-dryrun"
    assert sorted(p.name for p in d.iterdir()) == ["dramatic_options.db", "dramatic_options.db-shm",
                                                   "dramatic_options.db-wal"]
    assert not (tmp_path / "data" / "dramatic_options.db").exists()
    assert sqlite3.connect(d / "dramatic_options.db").execute("SELECT COUNT(*) FROM t").fetchone()[0] == 7
    calls = (tmp_path / "calls").read_text().splitlines()
    assert calls == ["stop dramatic-options-web.service", "start dramatic-options-web.service"]
    live.close()


def test_the_archive_refuses_an_existing_directory_and_moves_nothing(tmp_path):
    _real_book(tmp_path, ["open"])
    assert _archive(tmp_path).returncode == 0
    _real_book(tmp_path, ["open"])                 # a second DB the same day
    r = _archive(tmp_path)
    assert "REFUSED" in r.stdout and "nothing moved" in r.stdout
    assert (tmp_path / "data" / "dramatic_options.db").exists()


def test_the_archive_label_serves_the_rehearsal_db_too(tmp_path):
    from datetime import date

    _real_book(tmp_path, [])
    assert _archive(tmp_path, label="rehearsal").returncode == 0
    assert (tmp_path / "data" / "archive" / f"{date.today():%Y-%m-%d}-rehearsal" / "dramatic_options.db").exists()
    doc = (REPO / "DEPLOYMENT.md").read_text()
    assert "with `label=rehearsal`" in doc[doc.index("3. PROD's DB"):doc.index("4. PROD `.env`")]


def test_the_precheck_fails_cleanly_when_the_table_is_missing(tmp_path):
    import sqlite3

    (tmp_path / "data").mkdir()
    sqlite3.connect(tmp_path / "data" / "dramatic_options.db").execute("CREATE TABLE other (x)").connection.commit()
    r = _precheck(tmp_path)
    assert r.returncode == 1 and r.stdout.startswith("FAIL") and "Traceback" not in r.stderr, r.stdout + r.stderr


def test_step_8_prechecks_before_the_flip_inside_a_merge_hold():
    doc = (REPO / "DEPLOYMENT.md").read_text()
    step = doc[doc.index("8. **Before the flip"):doc.index("**First-week watch**")]
    assert step.index("The precheck") < step.index("edit `.env` to `DRY_RUN=false`")
    assert "Hold `production` merges for the whole of step 8" in step and "re-enables every timer" in step


def test_sandbox_a_live_l2_alone_also_blocks_stripping(tmp_path):
    # the half state an interrupted install can leave: L1 without --live, L2 with it. The L2 is the unit that closes
    # and reconciles a live book, so it alone is enough to refuse.
    armed = _armed_installed(tmp_path)
    unarmed, _ = render_all(tmp_path, ARMED_ENV)
    before = {L1: unarmed[L1], L2: armed[L2]}
    code, out, calls, enabled, inst = run_deploy(tmp_path, ARMED_ENV, env_name="PROD", marker_content="PROD\n",
                                                 installed=before, marker_mode=0o664)
    assert code != 0 and calls == [] and inst == before
    assert f"the installed {L2} carry --live" in out


# ── the predeploy guard in the deploy WORKFLOW (#541 final review): both guards run against the current checkout
# BEFORE the workflow moves it. The workflow's real `run:` block is executed with stub ssh (runs the remote command
# here) and stub git (logs), so the test exercises its actual quoting. ───────────────────────────────────────────
WORKFLOW = REPO / ".github" / "workflows" / "deploy.yml"
GUARD = REPO / "scripts" / "predeploy_guard.sh"


def _workflow_run_block() -> str:
    import yaml

    wf = yaml.safe_load(WORKFLOW.read_text())
    steps = [st for job in wf["jobs"].values() for st in job["steps"] if st.get("name") == "Deploy and Restart App"]
    assert len(steps) == 1
    return steps[0]["run"]


def run_workflow_deploy(tmp_path: Path, *, env_name: str, with_guard: bool, marker_content: str | None = None,
                        marker_mode: int = 0o644, installed: dict[str, str] | None = None, env: str = PROD_ENV):
    """The workflow's deploy step against a fake live checkout → (exit code, output, git calls, deploy ran)."""
    home, bindir, dst, etc = tmp_path / "home", tmp_path / "wfbin", tmp_path / "wfdst", tmp_path / "wfetc"
    live = home / "dramatic_options"
    for d in (live / "scripts", bindir, dst):
        d.mkdir(parents=True)
    etc.mkdir(mode=0o755)
    (live / ".env").write_text(env)
    (live / "deploy.sh").write_text('#!/bin/bash\necho "DEPLOY.SH RAN ENV_NAME=$ENV_NAME"\n')
    (live / "deploy.sh").chmod(0o755)
    marker = etc / "live-armed"
    if marker_content is not None:
        _write_marker(marker, marker_content, marker_mode)
    if with_guard:
        (live / "scripts" / "live_arming.sh").write_text(_lib(marker, os.getuid()))
        g = GUARD.read_text()
        assert g.count('PREDEPLOY_SYSTEMD_DST="/etc/systemd/system"') == 1
        (live / "scripts" / "predeploy_guard.sh").write_text(
            g.replace('PREDEPLOY_SYSTEMD_DST="/etc/systemd/system"', f'PREDEPLOY_SYSTEMD_DST="{dst}"'))
    for name, content in (installed or {}).items():
        (dst / name).write_text(content)
    ref = "production" if env_name == "PROD" else "main"
    stubs = {
        "ssh": 'exec bash -c "${@: -1}"\n',
        "git": f'echo "git $*" >> "{tmp_path}/git-calls"\ncase "$1" in branch) echo {ref} ;; esac\nexit 0\n',
    }
    for name, body in stubs.items():
        (bindir / name).write_text("#!/bin/bash\n" + body)
        (bindir / name).chmod(0o755)
    block = _workflow_run_block()
    for k, v in {"env.USER": "u", "env.HOST": "h", "github.ref_name": ref, "env.ENV_NAME": env_name}.items():
        block = block.replace("${{ " + k + " }}", v)
    assert "${{" not in block
    r = subprocess.run(["bash", "-c", block], capture_output=True, text=True, timeout=60,
                       env={**os.environ, "HOME": str(home), "PATH": f"{bindir}:{os.environ['PATH']}"})
    gc = tmp_path / "git-calls"
    return r.returncode, r.stdout + r.stderr, gc.read_text().splitlines() if gc.exists() else [], \
        "DEPLOY.SH RAN" in r.stdout


def test_workflow_skips_the_guard_on_a_pre_468_checkout(tmp_path):
    # every box today: the deployed checkout has no guard → skipped, then the usual fetch/checkout/reset/deploy
    code, out, git, ran = run_workflow_deploy(tmp_path, env_name="PROD", with_guard=False)
    assert code == 0 and ran, out
    assert "predeploy guard: none in this checkout (pre-#468); skipped" in out
    assert "git fetch --prune" in git and "git reset --hard origin/production" in git


def test_workflow_guard_passes_on_an_unarmed_box_and_the_deploy_proceeds(tmp_path):
    code, out, git, ran = run_workflow_deploy(tmp_path, env_name="DEV", with_guard=True, env=DEV_ENV)
    assert code == 0 and ran, out
    assert "predeploy guard: passed" in out and "git reset --hard origin/main" in git


@pytest.mark.parametrize("case", ["wrong-env", "bad-marker-on-live-units", "removed-marker-on-live-units"])
def test_workflow_guard_refusal_fails_the_job_with_the_checkout_untouched(tmp_path, case):
    kw: dict = {"env": ARMED_ENV}
    if case == "wrong-env":
        kw.update(env_name="DEV", marker_content="PROD\n")
        why = "names 'PROD' but this deploy is ENV_NAME='DEV'"
    else:
        kw.update(env_name="PROD", installed=_armed_installed(tmp_path))
        if case == "bad-marker-on-live-units":
            kw.update(marker_content="PROD\n", marker_mode=0o664)
            why = "group- or other-writable"
        else:
            why = "no marker"
    code, out, git, ran = run_workflow_deploy(tmp_path, with_guard=True, **kw)
    assert code != 0 and not ran
    assert git == []                     # no self-heal, fetch, checkout or reset: the checkout never moved
    assert "DEPLOY ABORTED BEFORE ANY CHANGE" in out and why in out
    assert "Manual deploy: if you already moved this checkout" in out


def test_workflow_runs_the_guard_before_anything_moves_the_checkout():
    block = _workflow_run_block()
    g = block.index("bash scripts/predeploy_guard.sh || exit 1")
    for later in ("git checkout -- .", "git clean -fd", "git fetch --prune", "git checkout ${{ github.ref_name }}",
                  "git reset --hard origin/", "./deploy.sh"):
        assert g < block.index(later), later
    assert block.index("cd ~/dramatic_options") < g
    assert "'" not in block[block.index("predeploy guard: BEGIN"):block.index("predeploy guard: END")]


def test_the_guard_defaults_match_deploy_sh():
    g = GUARD.read_text()
    assert 'PREDEPLOY_LIVE_UNITS=("dramatic-options-l1.service" "dramatic-options-l2.service")' in g
    assert _deploy_line("LIVE_UNITS=(").strip() == (
        'LIVE_UNITS=("${SERVICE_PREFIX}-l1.service" "${SERVICE_PREFIX}-l2.service")')
    assert 'SERVICE_PREFIX="dramatic-options"' in DEPLOY.read_text()
    assert 'SYSTEMD_DST="/etc/systemd/system"' in DEPLOY.read_text()


def test_deploy_sh_runs_the_same_guard_with_the_env_name_it_was_given():
    text = DEPLOY.read_text()
    call = 'ENV_NAME="$ENV_NAME_GIVEN" bash "$REPO_ROOT/scripts/predeploy_guard.sh" "$SYSTEMD_DST" "${LIVE_UNITS[@]}"'
    assert call in text and text.index(call) < text.index('DEPLOY_LOCK="')


def test_a_guard_without_its_helper_refuses(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copy(GUARD, tmp_path / "scripts" / "predeploy_guard.sh")
    r = subprocess.run(["bash", str(tmp_path / "scripts" / "predeploy_guard.sh")], capture_output=True, text=True,
                       timeout=30, env={**os.environ, "ENV_NAME": "PROD"})
    assert r.returncode == 1 and "live_arming.sh is missing" in r.stdout


def test_the_doc_tells_a_manual_deploy_to_guard_before_moving_the_checkout():
    doc = (REPO / "DEPLOYMENT.md").read_text()
    assert "ENV_NAME=PROD bash scripts/predeploy_guard.sh" in doc
    assert "before the workflow moves the checkout" in doc
