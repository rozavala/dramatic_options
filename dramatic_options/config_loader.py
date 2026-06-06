"""Configuration loading for dramatic_options.

Loads ``config.json`` then applies ``.env`` overrides (secrets + per-host gates).
Centralizes the paper-first safety gates and the single ``live_allowed`` invariant
that every order path must consult. Pattern mirrors real_options' config_loader,
re-implemented for this system.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# This module lives in the dramatic_options/ package; config.json and .env sit at the
# repo root (one level up) — see SPEC §10.
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.json"
ENV_PATH = REPO_ROOT / ".env"


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

    # FORWARD_ENABLED (T2.5): gates whether THIS env actively trades on the scheduled loop.
    # Kept TOP-LEVEL and deliberately distinct from the live triple-gate above (PAPER /
    # live_trading_enabled / --live): DEV (paper) runs the loop with forward_enabled=true; PROD
    # (real-money) stays installed-but-inert with forward_enabled=false until T4. Default false
    # (fail-safe: an env trades only when it opts in explicitly via .env).
    config["forward_enabled"] = _as_bool(os.getenv("FORWARD_ENABLED"), default=False)

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


def _drop_comments(obj: Any) -> Any:
    """Strip ``_``-prefixed keys (e.g. ``_comment``) recursively, so a docs-only config edit doesn't
    churn the frame version."""
    if isinstance(obj, dict):
        return {k: _drop_comments(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [_drop_comments(v) for v in obj]
    return obj


def frame_version(config: dict[str, Any]) -> str:
    """A short deterministic stamp of the live FROZEN risk frame (PREREG §5) — the convexity book +
    cluster taxonomy/cap, the IV gate, the exits, and the kill rule. Recorded per run (migration 0009)
    so positions segment by risk regime at T4 and the breach audit can ask "was this entry admitted
    under the THEN-LIVE frame." Changes whenever any frozen parameter changes; comment-only edits don't."""
    frame = _drop_comments({
        "convexity_book": config.get("convexity_book", {}),
        "convexity_gate": config.get("convexity_gate", {}),
        "convexity_exits": config.get("convexity_exits", {}),
        "kill_rule": config.get("kill_rule", {}),
    })
    blob = json.dumps(frame, sort_keys=True, default=str)
    return "frame-" + hashlib.sha1(blob.encode()).hexdigest()[:12]
