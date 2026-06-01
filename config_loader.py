"""Configuration loading for dramatic_options.

Loads ``config.json`` then applies ``.env`` overrides (secrets + per-host gates).
Centralizes the paper-first safety gates and the single ``live_allowed`` invariant
that every order path must consult. Pattern mirrors real_options' config_loader,
re-implemented for this system.
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
ENV_PATH = BASE_DIR / ".env"


def _as_bool(value: str | bool | None, default: bool = False) -> bool:
    """Coerce an env string to bool. Unset/empty → default."""
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class ConfigError(RuntimeError):
    """Raised with a friendly message when configuration is invalid/missing."""


@functools.lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    """Load config.json, apply .env overrides, validate. Cached per process."""
    try:
        config = json.loads(CONFIG_PATH.read_text())
    except FileNotFoundError as e:
        raise ConfigError(f"config.json not found at {CONFIG_PATH}") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"config.json is not valid JSON: {e}") from e

    # .env holds secrets + per-host overrides. Absent is fine (e.g. CI).
    load_dotenv(ENV_PATH)

    safety = config.setdefault("safety", {})
    # Env wins over file for the gates; default to the safe (paper) values.
    safety["paper"] = _as_bool(os.getenv("PAPER"), default=bool(safety.get("paper", True)))
    safety["live_trading_enabled"] = _as_bool(
        os.getenv("LIVE_TRADING_ENABLED"),
        default=bool(safety.get("live_trading_enabled", False)),
    )
    safety["dry_run"] = _as_bool(os.getenv("DRY_RUN"), default=bool(safety.get("dry_run", True)))
    if os.getenv("DATA_FEED"):
        safety["data_feed"] = os.getenv("DATA_FEED").strip()

    # Alpaca credentials (never stored in config.json).
    config["alpaca"] = {
        "api_key": os.getenv("ALPACA_API_KEY"),
        "secret_key": os.getenv("ALPACA_SECRET_KEY"),
        # ALPACA_PAPER controls the endpoint; defaults to the PAPER gate.
        "paper": _as_bool(os.getenv("ALPACA_PAPER"), default=safety["paper"]),
    }

    # EDGAR User-Agent (Phase 1). SEC requires a contact UA on every request.
    edgar = config.setdefault("edgar", {})
    if os.getenv("EDGAR_USER_AGENT"):
        edgar["user_agent"] = os.getenv("EDGAR_USER_AGENT").strip()

    # Council LLM provider keys (T2; never stored in config.json). Absent is fine — an
    # enabled council with a missing key for a mapped provider fails closed at run time.
    config["llm_keys"] = {
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "openai": os.getenv("OPENAI_API_KEY"),
        "gemini": os.getenv("GEMINI_API_KEY"),
        "xai": os.getenv("XAI_API_KEY"),
        "perplexity": os.getenv("PERPLEXITY_API_KEY"),
    }
    return config


def require_alpaca_credentials(config: dict[str, Any]) -> tuple[str, str]:
    """Return (api_key, secret_key) or raise a friendly ConfigError."""
    creds = config.get("alpaca", {})
    key, secret = creds.get("api_key"), creds.get("secret_key")
    if not key or not secret:
        raise ConfigError(
            "Alpaca credentials missing. Copy .env.example to .env and set "
            "ALPACA_API_KEY and ALPACA_SECRET_KEY (paper keys for now)."
        )
    return key, secret


def live_allowed(config: dict[str, Any], cli_live: bool) -> bool:
    """The single live-trading invariant.

    Live is permitted ONLY when ALL THREE hold:
      - PAPER is false, AND
      - LIVE_TRADING_ENABLED is true, AND
      - the caller passed --live (cli_live=True).
    Any other combination → paper. There is intentionally no other path to live.
    """
    safety = config.get("safety", {})
    return (
        safety.get("paper") is False
        and safety.get("live_trading_enabled") is True
        and cli_live is True
    )
