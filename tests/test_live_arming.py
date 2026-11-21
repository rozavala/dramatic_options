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
