"""Config gates: the live-trading invariant truth table + coercion + defaults."""

import itertools
import json

import pytest

import config_loader
from config_loader import _as_bool, live_allowed


def test_frozen_exit_rules_match_prereg():
    """Guard the frozen §6a exit thresholds in the shipped config against silent drift.

    profit_take_multiple was operator-raised 4.0→10.0 on 2026-06-01 (calibration-cited,
    PREREG_THEMATIC_CONVEXITY §6a amendment). A change here must be a documented PREREG edit,
    so this test pins the shipped value.
    """
    config_loader.load_config.cache_clear()
    exits = config_loader.load_config()["convexity_exits"]
    assert exits["profit_take_multiple"] == 10.0
    assert exits["time_stop_dte"] == 21
    config_loader.load_config.cache_clear()


def test_frozen_cluster_cap_matches_prereg():
    """Pin the shipped cluster cap + taxonomy (PREREG §5 amendment 2026-06-03; curated 2026-06-04)
    against silent drift.

    cluster_fraction = 0.02 (2 full names; graduate to 0.03 only at >=4 curated clusters) and the
    driver-documented clusters. A change must be a dated PREREG edit — mirrors the §6a exit pin above.
    2026-06-04: space_defense EXTENDED with the defense primes LMT/NOC/LHX/RTX, surfaced by the
    trailing-return correlation diagnostic as a 0.50-0.68 shared-driver cluster (operator-curated, hard seam).
    2026-06-10: RE-PARTITIONED to five clusters at window #1 (PREREG_UNIVERSE_CURATION §11 Rule 4,
    operator-authorized): nuclear_fuel NEW (CCJ migrated — uranium shares one budget); ai_capex_power
    += the grid names ATKR/AMSC/FLNC; copper_supply NEW (FCX re-clustered + HBM/ERO/TGB); the RKLB
    split-on-evidence fired → space_smallcap NEW (RKLB migrated + PL/LUNR/RDW/FLY/IRDM); space_defense
    keeps the budget-driver primes + KTOS. cluster_fraction unchanged.
    """
    config_loader.load_config.cache_clear()
    book = config_loader.load_config()["convexity_book"]
    assert book["cluster_fraction"] == 0.02
    assert set(book["clusters"]["ai_capex_power"]) == {"VRT", "PWR", "GEV", "ETN", "CEG", "NEE", "ATKR", "AMSC", "FLNC"}
    assert set(book["clusters"]["space_defense"]) == {"KTOS", "LMT", "NOC", "LHX", "RTX"}
    assert set(book["clusters"]["nuclear_fuel"]) == {"CCJ", "UEC", "UUUU", "NXE", "UROY", "SMR", "NNE"}
    assert set(book["clusters"]["copper_supply"]) == {"FCX", "HBM", "ERO", "TGB"}
    assert set(book["clusters"]["space_smallcap"]) == {"RKLB", "PL", "LUNR", "RDW", "FLY", "IRDM"}
    config_loader.load_config.cache_clear()


def test_frame_version_changes_with_frozen_params_not_comments():
    from config_loader import frame_version
    base = {"convexity_book": {"cluster_fraction": 0.02}, "convexity_gate": {"iv_rv_max": 1.2}}
    v0 = frame_version(base)
    # a comment-only edit does NOT churn the version
    assert frame_version({**base, "convexity_book": {"_comment": "x", "cluster_fraction": 0.02},
                          "convexity_gate": {"iv_rv_max": 1.2}}) == v0
    # a real frozen-param change DOES
    assert frame_version({**base, "convexity_book": {"cluster_fraction": 0.03}}) != v0


def test_council_block_and_llm_keys_surfaced(monkeypatch, tmp_path):
    """The shipped council config + .env-sourced provider keys load as expected (T2).

    Hermetic: point ENV_PATH at a nonexistent file so the developer's real ``.env`` (which may
    now hold real provider keys) can't sway the assertions — ``load_dotenv`` would otherwise
    re-set a ``delenv``'d key from ``.env`` and break the ``is None`` check locally.
    """
    monkeypatch.setattr(config_loader, "ENV_PATH", tmp_path / "absent.env")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    config_loader.load_config.cache_clear()
    cfg = config_loader.load_config()
    council = cfg["council"]
    # The hard seam depends on these roles being mapped to DISTINCT providers.
    providers = {council["roles"][r]["provider"] for r in ("proposer", "adversary", "strategist")}
    assert len(providers) == 3
    assert council["conviction_floor"] in ("LOW", "MODERATE", "HIGH", "EXTREME")
    assert cfg["llm_keys"]["anthropic"] == "a-key"
    assert cfg["llm_keys"]["xai"] is None  # unset → None (enabled council fails closed on it)
    config_loader.load_config.cache_clear()


def test_as_bool_coercion():
    for truthy in ("1", "true", "TRUE", "Yes", "on", True):
        assert _as_bool(truthy) is True
    for falsy in ("0", "false", "no", "off", "", None, False):
        assert _as_bool(falsy) is False
    assert _as_bool(None, default=True) is True
    assert _as_bool("", default=True) is True


def test_live_allowed_full_truth_table():
    """live is True ONLY when paper=False AND live_enabled=True AND cli_live=True."""
    for paper, live_enabled, cli_live in itertools.product([True, False], repeat=3):
        config = {"safety": {"paper": paper, "live_trading_enabled": live_enabled}}
        expected = (paper is False) and (live_enabled is True) and (cli_live is True)
        assert live_allowed(config, cli_live) is expected, (paper, live_enabled, cli_live)


def test_live_allowed_only_one_true_combo():
    combos = [
        (p, le, cl)
        for p, le, cl in itertools.product([True, False], repeat=3)
        if live_allowed({"safety": {"paper": p, "live_trading_enabled": le}}, cl)
    ]
    assert combos == [(False, True, True)]


def test_load_config_defaults_to_paper(monkeypatch):
    """With no gate env vars set, defaults are the safe paper values."""
    for var in ("PAPER", "LIVE_TRADING_ENABLED", "DRY_RUN"):
        monkeypatch.delenv(var, raising=False)
    config_loader.load_config.cache_clear()
    cfg = config_loader.load_config()
    safety = cfg["safety"]
    assert safety["paper"] is True
    assert safety["live_trading_enabled"] is False
    assert safety["dry_run"] is True
    config_loader.load_config.cache_clear()


def test_data_feed_block_structured_and_valid():
    """The shipped config exposes data_feed as a top-level structured block (the dead-knob fix),
    no longer a string under safety."""
    config_loader.load_config.cache_clear()
    cfg = config_loader.load_config()
    df = cfg["data_feed"]
    assert df["equity_bars"] in ("iex", "sip")
    assert df["option_gate"] in ("indicative", "opra")
    assert df["option_monitor"] in ("indicative", "opra")
    assert "data_feed" not in cfg["safety"]  # relocated top-level; the old dead safety knob is gone
    config_loader.load_config.cache_clear()


def test_data_feed_typo_fails_closed(tmp_path, monkeypatch):
    """An unknown feed value fails CLOSED at config load (never a silent fallback)."""
    bad = tmp_path / "config.json"
    bad.write_text(json.dumps({"safety": {}, "data_feed": {
        "equity_bars": "sipp", "option_gate": "indicative", "option_monitor": "indicative"}}))
    monkeypatch.setattr(config_loader, "CONFIG_PATH", bad)
    monkeypatch.setenv("DRAMATIC_SKIP_DOTENV", "1")  # don't read the real .env
    config_loader.load_config.cache_clear()
    with pytest.raises(config_loader.ConfigError):
        config_loader.load_config()
    config_loader.load_config.cache_clear()


def test_env_overrides_gates(monkeypatch):
    monkeypatch.setenv("PAPER", "false")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    config_loader.load_config.cache_clear()
    cfg = config_loader.load_config()
    assert cfg["safety"]["paper"] is False
    assert cfg["safety"]["live_trading_enabled"] is True
    config_loader.load_config.cache_clear()


def test_forward_enabled_defaults_false(monkeypatch, tmp_path):
    """FORWARD_ENABLED is top-level and defaults False — an env trades only when it opts in."""
    monkeypatch.setattr(config_loader, "ENV_PATH", tmp_path / "absent.env")
    monkeypatch.delenv("FORWARD_ENABLED", raising=False)
    config_loader.load_config.cache_clear()
    assert config_loader.load_config()["forward_enabled"] is False
    config_loader.load_config.cache_clear()


def test_forward_enabled_env_override_is_distinct_from_live(monkeypatch, tmp_path):
    """FORWARD_ENABLED=true arms the loop but is NOT the live triple-gate (stays paper)."""
    monkeypatch.setattr(config_loader, "ENV_PATH", tmp_path / "absent.env")
    monkeypatch.setenv("FORWARD_ENABLED", "true")
    monkeypatch.delenv("PAPER", raising=False)
    monkeypatch.delenv("LIVE_TRADING_ENABLED", raising=False)
    config_loader.load_config.cache_clear()
    cfg = config_loader.load_config()
    assert cfg["forward_enabled"] is True
    assert cfg["safety"]["paper"] is True              # forward_enabled does not touch the gates
    assert cfg["safety"]["live_trading_enabled"] is False
    assert live_allowed(cfg, cli_live=True) is False   # still no live path
    config_loader.load_config.cache_clear()


def test_require_alpaca_credentials_friendly_error():
    import pytest

    from config_loader import ConfigError, require_alpaca_credentials

    with pytest.raises(ConfigError, match="Alpaca credentials missing"):
        require_alpaca_credentials({"alpaca": {"api_key": None, "secret_key": None}})
    key, secret = require_alpaca_credentials({"alpaca": {"api_key": "k", "secret_key": "s"}})
    assert (key, secret) == ("k", "s")
