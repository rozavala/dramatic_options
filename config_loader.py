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

from feeds import FeedConfigError
from feeds import validate as validate_data_feed

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

    # .env holds secrets + per-host overrides. Absent is fine (e.g. CI). The read-only observability
    # dashboard sets DRAMATIC_SKIP_DOTENV=1 so it loads config.json tunables but NEVER reads .env — the
    # process stays keyless (nothing for a long-running HTTP server to leak). The trading loop leaves the
    # flag unset (default path); the L1/L2 systemd units inject their keys via EnvironmentFile regardless.
    if not os.getenv("DRAMATIC_SKIP_DOTENV"):
        load_dotenv(ENV_PATH)

    safety = config.setdefault("safety", {})
    # Env wins over file for the gates; default to the safe (paper) values.
    safety["paper"] = _as_bool(os.getenv("PAPER"), default=bool(safety.get("paper", True)))
    safety["live_trading_enabled"] = _as_bool(
        os.getenv("LIVE_TRADING_ENABLED"),
        default=bool(safety.get("live_trading_enabled", False)),
    )
    safety["dry_run"] = _as_bool(os.getenv("DRY_RUN"), default=bool(safety.get("dry_run", True)))
    # The live broker's hard per-order notional ceiling (PREREG_REAL_MONEY_BROKER §3 — absent ⇒
    # the live class rejects ALL orders, fail-closed). Env path exists so the §5 smoke can arm the
    # ceiling AT SESSION TIME and unset it after: config.json is git-tracked and a box-local edit
    # is clobbered by the next deploy's reset (the 2026-07-02 lesson) — a live-money knob should
    # not have to live in git to be usable. An unparseable value is ignored (stays fail-closed).
    if os.getenv("LIVE_MAX_ORDER_NOTIONAL"):
        try:
            safety["live_max_order_notional"] = float(os.getenv("LIVE_MAX_ORDER_NOTIONAL"))
        except ValueError:
            pass

    # Data-feed roles (the data-feed upgrade). config.json is the source of truth — there is NO env
    # override (the old flat DATA_FEED knob was dead: read into safety.data_feed but never wired to a
    # fetch). Default to the SAFE/current feeds if a (minimal) config omits the block, then validate so
    # an unknown value fails CLOSED at load — never a silent fallback to a default feed.
    df = config.setdefault("data_feed", {})
    df.setdefault("equity_bars", "iex")
    df.setdefault("option_gate", "indicative")
    df.setdefault("option_monitor", "indicative")
    df.setdefault("dualread_revert_enabled", False)
    # The §5 dual-read REVERT override (#72, Phase 3): a runtime sentinel file ``OPRA_REVERTED`` at
    # repo root (the KILL-file precedent) FORCES option_gate→indicative until an operator removes it.
    # One-directional toward safety, idempotent, record-segmenting (the next run's data_feed_stamp
    # changes). Consulted AFTER config.json so an operator (or the gated Phase-3 latch) can fall the
    # gate back to the validated prior feed without a code/config deploy. Default config never trips
    # this (the sentinel is absent); the executor only writes it when dualread_revert_enabled is true.
    from dualread_executor import revert_latched

    if revert_latched() and df.get("option_gate") == "opra":
        df["option_gate"] = "indicative"
        df["_dualread_reverted"] = True  # provenance for the stamp/log (a comment key, dropped from frame)
    try:
        validate_data_feed(df)
    except FeedConfigError as e:
        raise ConfigError(str(e)) from e

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


def data_feed_stamp(config: dict[str, Any]) -> str:
    """A compact JSON stamp of the resolved data-feed roles, recorded per run (migration 0013).

    Lets the forward record segment by data regime — the gate's RV/option inputs and the discovery
    funnel all hang off these (companion to ``frame_version`` / ``model_mix``). Comment keys dropped so
    a docs-only edit doesn't churn the stamp."""
    return json.dumps(_drop_comments(config.get("data_feed", {})), sort_keys=True, default=str)
