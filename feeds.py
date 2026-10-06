"""Data-feed resolution + classification (the data-feed upgrade, PR1).

``config.data_feed`` is a structured block with three roles, each a string:
  - ``equity_bars``    : ``"iex" | "sip"``         — RV closes + underlying + discovery markers
  - ``option_gate``    : ``"indicative" | "opra"`` — the L1 entry-authorization IV/skew (the gate)
  - ``option_monitor`` : ``"indicative" | "opra"`` — the L2 mark path (pinned free in practice)

Two layers, deliberately split so ``config_loader`` stays alpaca-free (the keyless dashboard
imports it):
  - **Validation** (plain, no alpaca): :func:`validate` raises on an unknown string so a config
    typo fails CLOSED at load — never a silent fallback to a default feed.
  - **Resolution** (lazy alpaca import): :func:`to_equity_feed` / :func:`to_option_feed` map a
    validated string to the alpaca enum, used by the providers (which already depend on alpaca).

:func:`classify_feed_error` distinguishes an ENTITLEMENT lapse (subscription/permission — the
premium feed isn't authorized) from a TRANSIENT blip, so the OPRA-gate path (PR3) can VETO + page
on a lapse but merely log a transient. In PR1 ``option_gate`` stays ``"indicative"`` (free), so the
entitlement path isn't exercised yet — the classifier ships now for PR3.
"""

from __future__ import annotations

VALID_EQUITY = ("iex", "sip")
VALID_OPTION = ("indicative", "opra")
_ROLES: dict[str, tuple[str, ...]] = {
    "equity_bars": VALID_EQUITY,
    "option_gate": VALID_OPTION,
    "option_monitor": VALID_OPTION,
}


class FeedConfigError(ValueError):
    """An unknown/missing feed string in ``config.data_feed`` (fail-closed config typo)."""


def validate(block: dict) -> None:
    """Raise :class:`FeedConfigError` if ``config.data_feed`` has a missing/unknown role value.

    Plain — no alpaca import — so ``config_loader`` can fail closed at load time.
    """
    if not isinstance(block, dict):
        raise FeedConfigError(f"config.data_feed must be an object, got {type(block).__name__}")
    for role, allowed in _ROLES.items():
        val = block.get(role)
        if val not in allowed:
            raise FeedConfigError(
                f"config.data_feed.{role}={val!r} is invalid; expected one of {allowed}"
            )


def to_equity_feed(name: str):
    """``'iex'|'sip'`` → alpaca ``DataFeed`` (lazy import). Unknown → :class:`FeedConfigError`."""
    from alpaca.data.enums import DataFeed

    mapping = {"iex": DataFeed.IEX, "sip": DataFeed.SIP}
    try:
        return mapping[name]
    except KeyError as e:
        raise FeedConfigError(f"unknown equity feed {name!r}; expected {VALID_EQUITY}") from e


def to_option_feed(name: str):
    """``'indicative'|'opra'`` → alpaca ``OptionsFeed`` (lazy import). Unknown → :class:`FeedConfigError`."""
    from alpaca.data.enums import OptionsFeed

    mapping = {"indicative": OptionsFeed.INDICATIVE, "opra": OptionsFeed.OPRA}
    try:
        return mapping[name]
    except KeyError as e:
        raise FeedConfigError(f"unknown option feed {name!r}; expected {VALID_OPTION}") from e


def classify_feed_error(exc: BaseException) -> str:
    """Classify a market-data fetch error: ``'entitlement'`` (subscription/permission lapse) vs
    ``'transient'`` (network/timeout/rate).

    Used by the OPRA-gate path (PR3) to VETO + page on an entitlement lapse but only log a
    transient. Conservative: matches known Alpaca subscription-error phrasing; everything else
    → ``'transient'`` (so a novel error never masquerades as a deliberate veto).
    """
    msg = str(exc).lower()
    markers = (
        "subscription does not permit",
        "not permitted",
        "not authorized",
        "unauthorized",
        "forbidden",
        "no subscription",
        "upgrade your plan",
    )
    return "entitlement" if any(m in msg for m in markers) else "transient"
