"""Issue #279 item 6 (rozavala/finance#947 §5) — venue-named Alpaca keys, STRICT step.

The venue (the PAPER gate) picks the pair: ``ALPACA_PAPER_KEY_ID`` / ``ALPACA_PAPER_SECRET_KEY`` or
``ALPACA_LIVE_KEY_ID`` / ``ALPACA_LIVE_SECRET_KEY``. The legacy ``ALPACA_API_KEY`` / ``ALPACA_SECRET_KEY`` /
``ALPACA_PAPER`` are refused: the loop will not start while any is set (the DEV .env was renamed 2026-10-05).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from config_loader import (
    LEGACY_KEY_VARS,
    LIVE_KEY_VARS,
    PAPER_KEY_VARS,
    ConfigError,
    alpaca_credentials,
    require_alpaca_credentials,
)

ALL = PAPER_KEY_VARS + LIVE_KEY_VARS + LEGACY_KEY_VARS
REPO = Path(__file__).resolve().parents[1]


def _set(mp, **kv):
    for k, v in kv.items():
        mp.setenv(k, v)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for v in ALL:
        monkeypatch.delenv(v, raising=False)


def test_paper_venue_reads_the_paper_pair(monkeypatch):
    _set(monkeypatch, ALPACA_PAPER_KEY_ID="pk", ALPACA_PAPER_SECRET_KEY="ps")
    _set(monkeypatch, ALPACA_LIVE_KEY_ID="lk", ALPACA_LIVE_SECRET_KEY="ls")
    c = alpaca_credentials({"paper": True})
    assert (c["api_key"], c["secret_key"], c["paper"], c["key_source"]) == ("pk", "ps", True, "venue")


def test_live_venue_reads_the_live_pair_never_the_paper_pair(monkeypatch):
    _set(monkeypatch, ALPACA_PAPER_KEY_ID="pk", ALPACA_PAPER_SECRET_KEY="ps")
    _set(monkeypatch, ALPACA_LIVE_KEY_ID="lk", ALPACA_LIVE_SECRET_KEY="ls")
    c = alpaca_credentials({"paper": False})
    assert (c["api_key"], c["secret_key"], c["paper"]) == ("lk", "ls", False)


def test_live_venue_without_a_live_pair_never_borrows_the_paper_pair(monkeypatch):
    _set(monkeypatch, ALPACA_PAPER_KEY_ID="pk", ALPACA_PAPER_SECRET_KEY="ps")
    c = alpaca_credentials({"paper": False})
    assert c["api_key"] is None and c["key_source"] == "missing"
    with pytest.raises(ConfigError):
        require_alpaca_credentials({"alpaca": c})


@pytest.mark.parametrize("legacy", ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_PAPER"])
def test_any_legacy_name_refuses_to_start(monkeypatch, legacy):
    _set(monkeypatch, ALPACA_PAPER_KEY_ID="pk", ALPACA_PAPER_SECRET_KEY="ps")
    monkeypatch.setenv(legacy, "x")
    with pytest.raises(ConfigError, match="legacy Alpaca env name"):
        alpaca_credentials({"paper": True})


def test_a_half_set_pair_is_missing_never_completed_from_elsewhere(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_KEY_ID", "pk")          # secret missing; no fallback exists
    c = alpaca_credentials({"paper": True})
    assert c["key_source"] == "missing"
    with pytest.raises(ConfigError):
        require_alpaca_credentials({"alpaca": c})


def test_keyless_paths_still_load(monkeypatch):
    c = alpaca_credentials({"paper": True})                  # nothing set: --demo / the keyless dashboard
    assert c["api_key"] is None and c["key_source"] == "missing"


def test_no_module_reads_the_alpaca_env_directly():
    # one seam: every caller goes through config_loader (require_alpaca_credentials)
    for p in REPO.rglob("*.py"):
        rel = p.relative_to(REPO).as_posix()
        if rel.startswith(("tests/", "shelf/", "venv/", ".venv/")) or rel == "config_loader.py":
            continue
        src = p.read_text()
        for v in ALL:
            assert f'getenv("{v}")' not in src and f"environ['{v}']" not in src, f"{rel} reads {v}"


@pytest.mark.parametrize("env,ok,msg", [
    ("ALPACA_PAPER_KEY_ID=a\nALPACA_PAPER_SECRET_KEY=b\n", True, "venue-named paper pair"),
    ("ALPACA_API_KEY=a\nALPACA_SECRET_KEY=b\n", False, "legacy Alpaca name"),
    ("ALPACA_PAPER_KEY_ID=a\nALPACA_PAPER_SECRET_KEY=b\nALPACA_PAPER=true\n", False, "legacy Alpaca name"),
    ("ALPACA_PAPER_KEY_ID=a\n", False, "no Alpaca paper key pair"),
    ("ALPACA_PAPER_KEY_ID=your_key\nALPACA_PAPER_SECRET_KEY=your_secret\n", False, "no Alpaca paper key pair"),
])
def test_verify_deploy_requires_the_paper_pair_and_no_legacy_name(tmp_path, env, ok, msg):
    # Run only the Alpaca block of scripts/verify_deploy.sh against a temp .env.
    src = (REPO / "scripts/verify_deploy.sh").read_text()
    start = src.index("        _pk=$(_env_val ALPACA_PAPER_KEY_ID)")
    end = src.index("        fi", start) + len("        fi")
    envf = tmp_path / ".env"
    envf.write_text(env)
    script = (f'ENV_FILE="{envf}"; HEALTH_LOG="{tmp_path}/h.log"; FAILED=0; MISSING=0\n'
              '_env_val() { grep -E "^[[:space:]]*$1[[:space:]]*=" "$ENV_FILE" 2>/dev/null | tail -1 | '
              "cut -d= -f2- | tr -d \"\\\"' \\t\\r\"; }\n" + src[start:end] + '\necho "FAILED=$FAILED"\n')
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout
    assert msg in out
    assert ("FAILED=0" in out) is ok
