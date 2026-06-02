"""Config gates: the live-trading invariant truth table + coercion + defaults."""

import itertools

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
    for var in ("PAPER", "LIVE_TRADING_ENABLED", "DRY_RUN", "DATA_FEED"):
        monkeypatch.delenv(var, raising=False)
    config_loader.load_config.cache_clear()
    cfg = config_loader.load_config()
    safety = cfg["safety"]
    assert safety["paper"] is True
    assert safety["live_trading_enabled"] is False
    assert safety["dry_run"] is True
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
