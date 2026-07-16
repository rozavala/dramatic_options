"""X practitioner-lists ingestion — the ``x_lists`` reach channel (X API v2, bearer token).

Governing spec: ``records/2026-07-14_reach_channels_charter_RATIFIED.md`` §2 plus the
2026-07-16 amendment (operator word: the manual-v0 yield precondition WAIVED; the
tier/pricing check RETAINED as ``scripts/x_probe.py``). The leg ships CONFIG-DISABLED
(``x_accounts.json`` ``enabled: false``) and is enabled by a one-line config flip after
the probe passes — that flip is the channel's activation date (charter §1).

Charter law enforced here by construction:

- **X is a pointer, never evidence** — an item carries title/link/date only; a thesis
  traces to verifiable prints (filings, agency data, tape), never to a post.
- **No engagement math anywhere**: engagement data (``public_metrics``) is NEVER
  requested, stored, or logged. :data:`TWEET_FIELDS` is the ENTIRE per-tweet field set
  sent to the API; a schema-guard test pins the request literals so an engagement field
  fails CI before it can fail the charter.
- **Chronological only** — the API's newest-first pages are re-ordered chronologically by
  ``digest.assemble``; overflow is truncation (oldest dropped, counted), never selection.
- **No LLM synthesis from the stream** — this module fetches and maps; nothing here calls
  a model.

WHO is in the pond is the operator's curation act: ``x_accounts.json`` at repo root,
edits by PR. The bearer token arrives via the ``config_loader`` seam
(``X_BEARER_TOKEN`` → ``config["x_api"]["bearer_token"]``) — this module never reads
``os.environ`` and never logs the token.

Failure semantics: fail-SOFT per account (a dead account is counted into ``errors`` and
skipped — dead-arm ≠ quiet-arm — and its ``since_id`` is NOT advanced, so nothing is
lost); fail-CLOSED for the channel as a whole (token absent / 401 / tier-insufficient →
:class:`XChannelOff`, which the runner renders as ONE loud counted ``x_lists: OFF (…)``
note — never a silent dead arm). Politeness: an inter-request throttle, a per-run request
budget, and rate-limit headers respected (remaining=0 or HTTP 429 stops the run early
with a counted deferral note). Stdlib-only (urllib/json), same as ``digest``.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from digest import DEFAULT_USER_AGENT, DIGEST_CACHE_DIR, Item, parse_date

X_API_BASE = "https://api.x.com/2"

# Charter §2 — the ENTIRE per-tweet field set and timeline knobs. No public_metrics, no
# engagement field of any kind, ever; retweets/replies excluded so the stream is the
# practitioner's own words. A schema-guard test pins these literals.
TWEET_FIELDS = "created_at,text"
TIMELINE_EXCLUDE = "retweets,replies"

TITLE_LIMIT = 140  # title = first ~140 chars of the post text
X_USER_ID_CACHE = "x_user_ids.json"
X_SINCE_ID_CACHE = "x_since_ids.json"
X_SINCE_ID_PATH = DIGEST_CACHE_DIR / X_SINCE_ID_CACHE


class XChannelOff(RuntimeError):
    """The whole channel must fail CLOSED (token absent/rejected or tier-insufficient).

    The runner converts this into one loud counted ``x_lists: OFF (…)`` note in the
    digest — never a silent dead arm."""


# ── HTTP (the only network seam; tests monkeypatch this) ──────────────────────
def _bearer_get_json(url: str, token: str, *, timeout: float = 20) -> tuple[Any, dict[str, str]]:
    """One authenticated GET → (parsed JSON, lower-cased response headers). Raises
    ``urllib.error.HTTPError``/``OSError`` on failure — callers decide fail-soft vs
    fail-closed. The token rides ONLY the Authorization header; never logged/echoed."""
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "User-Agent": DEFAULT_USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https URLs only)
        headers = {str(k).lower(): str(v) for k, v in resp.headers.items()}
        return json.loads(resp.read()), headers


# ── request URLs (pure; the no-engagement guard test pins these) ──────────────
def users_by_url(handles: list[str]) -> str:
    """``GET /2/users/by`` batch handle→id lookup (≤100 usernames per request).
    Deliberately NO ``user.fields`` — the default payload (id/name/username) is all the
    eyeball surface needs; no follower counts, no metrics."""
    return f"{X_API_BASE}/users/by?{urllib.parse.urlencode([('usernames', ','.join(handles))])}"


def timeline_url(user_id: str, *, since_id: str | None, max_results: int) -> str:
    """``GET /2/users/:id/tweets`` — chronological pull, no retweets/replies, and the
    pinned no-engagement field set (:data:`TWEET_FIELDS`)."""
    params = [
        ("tweet.fields", TWEET_FIELDS),
        ("exclude", TIMELINE_EXCLUDE),
        ("max_results", str(max_results)),
    ]
    if since_id:
        params.append(("since_id", since_id))
    return f"{X_API_BASE}/users/{user_id}/tweets?{urllib.parse.urlencode(params)}"


# ── item mapping (pure) ───────────────────────────────────────────────────────
def tweet_title(text: str, limit: int = TITLE_LIMIT) -> str:
    """First ~``limit`` chars of the post text, whitespace-collapsed (an over-long post
    is truncated with an ellipsis — the LINK is the pointer; the title is just a label)."""
    collapsed = " ".join(str(text).split())
    if len(collapsed) <= limit:
        return collapsed or "(empty post)"
    return collapsed[: limit - 1].rstrip() + "…"


def timeline_items(payload: Mapping[str, Any], *, handle: str, vertical: str) -> list[Item]:
    """Map one timeline response to digest Items: channel ``x_lists``, source
    ``x/<vertical>/<handle>``, link = the canonical post URL, published = created_at.
    No other tweet field is read — there is nothing else in the response by construction
    (:func:`timeline_url` requests only :data:`TWEET_FIELDS`)."""
    items: list[Item] = []
    for tweet in payload.get("data") or []:
        tweet_id = str(tweet.get("id") or "")
        items.append(
            Item(
                channel="x_lists",
                source=f"x/{vertical}/{handle}",
                title=tweet_title(tweet.get("text") or ""),
                link=f"https://x.com/{handle}/status/{tweet_id}" if tweet_id else "",
                published=parse_date(tweet.get("created_at")),
            )
        )
    return items


# ── per-user since_id state (persisted in the digest cache dir) ───────────────
def load_since_ids(path: str | Path = X_SINCE_ID_PATH) -> dict[str, str]:
    """handle → newest-seen tweet id; absent file → {} (first run pulls fresh)."""
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


def save_since_ids(state: dict[str, str], path: str | Path = X_SINCE_ID_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(sorted(state.items())), indent=1) + "\n")


# ── handle → user-id resolution (cached WITH display names) ───────────────────
def resolve_user_ids(
    handles: list[str],
    token: str,
    *,
    cache_dir: str | Path | None = None,
    timeout: float = 20,
    errors: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, dict[str, str]]:
    """handle → ``{"id", "name"}`` via batched ``GET /2/users/by``, cached to
    ``<cache_dir>/x_user_ids.json`` WITH the resolved display name.

    The [likely]-confidence handles need an eyeball surface: every FIRST resolution emits
    a one-time ``handle → display name`` verification table into the digest notes, so a
    wrong-person match is visible and fixable as an ``x_accounts.json`` edit. Cached
    handles are network-free on reruns; an unresolvable handle is counted into ``errors``
    and NOT cached (retried next run). 401/403 on the lookup is the channel-off signal →
    :class:`XChannelOff` (fail-closed, never a silent dead arm)."""
    path = Path(cache_dir if cache_dir is not None else DIGEST_CACHE_DIR) / X_USER_ID_CACHE
    cache: dict[str, dict[str, str]] = json.loads(path.read_text()) if path.exists() else {}
    missing = [h for h in handles if h not in cache]
    newly: list[str] = []
    for start in range(0, len(missing), 100):
        batch = missing[start : start + 100]
        try:
            payload, _headers = _bearer_get_json(users_by_url(batch), token, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise XChannelOff(
                    f"users/by HTTP {e.code} — token rejected or tier lacks user lookup "
                    "(run scripts/x_probe.py)"
                ) from e
            if errors is not None:
                errors.append(f"x_lists/users-by: HTTPError {e.code}")
            continue
        except Exception as e:  # noqa: BLE001 — the fail-soft boundary is the point
            if errors is not None:
                errors.append(f"x_lists/users-by: {type(e).__name__}: {e}")
            continue
        by_username = {
            str(row.get("username") or "").lower(): row for row in payload.get("data") or []
        }
        for handle in batch:
            row = by_username.get(handle.lower())
            if not row or not row.get("id"):
                if errors is not None:
                    errors.append(f"x_lists/@{handle}: handle did not resolve (users/by)")
                continue
            cache[handle] = {"id": str(row["id"]), "name": str(row.get("name") or "")}
            newly.append(handle)
    if newly:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(sorted(cache.items())), indent=1) + "\n")
        if notes is not None:
            notes.append(
                "x_lists: first-time handle resolution — VERIFY each display name is the "
                "intended person (a wrong match is an x_accounts.json edit):"
            )
            notes.extend(f"x_lists:   @{h} → {cache[h]['name']}" for h in newly)
    return {h: cache[h] for h in handles if h in cache}


# ── politeness: throttle + per-run budget + rate-limit-header respect ─────────
class _Budget:
    """Per-run request cap, inter-request throttle, and rate-limit respect for the
    timeline endpoint. remaining=0 (header) or HTTP 429 latches ``limited_reset`` and
    stops further requests this run — deferred accounts keep their since_id, so nothing
    is lost, and the deferral is a counted note."""

    def __init__(self, max_requests: int, rate_limit_per_sec: float) -> None:
        self.left = max_requests
        self.min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self.limited_reset: str | None = None
        self._last = 0.0

    def take(self) -> bool:
        """Reserve one request (throttled). False → stop (budget/rate-limit)."""
        if self.left <= 0 or self.limited_reset is not None:
            return False
        self.left -= 1
        if self.min_interval:
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
        self._last = time.monotonic()
        return True

    def observe(self, headers: Mapping[str, str]) -> None:
        if str(headers.get("x-rate-limit-remaining", "")).strip() == "0":
            self.limited_reset = str(headers.get("x-rate-limit-reset", "?"))


def _chrono_key(pair: tuple[int, Item]) -> tuple[int, float, int]:
    idx, item = pair
    if item.published is None:
        return (1, 0.0, idx)  # undated sorts as newest (never truncation-preferred)
    return (0, item.published.timestamp(), idx)


def _cap_verticals(items: list[Item], cap: int | None, notes: list[str] | None) -> list[Item]:
    """Per-vertical weekly cap — chronological truncation (OLDEST dropped, counted),
    never selection (charter §3). The per-ACCOUNT cap rides ``digest.assemble``'s
    per-source truncation instead (source = one account)."""
    if not cap:
        return items
    by_vertical: dict[str, list[tuple[int, Item]]] = {}
    for idx, item in enumerate(items):
        vertical = item.source.split("/", 2)[1] if item.source.count("/") >= 2 else ""
        by_vertical.setdefault(vertical, []).append((idx, item))
    out: list[Item] = []
    for vertical, group in by_vertical.items():
        ordered = [item for _, item in sorted(group, key=_chrono_key)]
        dropped = len(ordered) - cap
        if dropped > 0:
            if notes is not None:
                notes.append(
                    f"x_lists: {vertical} capped at {cap}/week; "
                    f"{dropped} older item(s) dropped"
                )
            ordered = ordered[dropped:]
        out += ordered
    return out


# ── the channel ───────────────────────────────────────────────────────────────
def fetch_x_channel(
    accounts_cfg: Mapping[str, Any],
    token: str,
    *,
    cache_dir: str | Path | None = None,
    timeout: float = 20,
    max_requests: int = 80,
    rate_limit_per_sec: float = 1.0,
    errors: list[str] | None = None,
    notes: list[str] | None = None,
) -> tuple[list[Item], dict[str, str]]:
    """Pull every configured account's timeline since its last-seen post.

    Returns ``(items, updated since_id state)`` — the caller persists the state only on
    a real (non-dry-run) digest write, so a dry run never consumes timeline progress.
    Fail-soft per account (counted, since_id not advanced); fail-closed for the channel
    (:class:`XChannelOff` on no-token/401/tier). ``max_requests`` caps the run's total
    timeline requests; rate-limit headers/429 stop the run early with a counted deferral
    note (never a silent dead arm)."""
    if not token:
        raise XChannelOff("no bearer token")
    accounts = [
        (vertical, str(acct["handle"]))
        for vertical, accts in (accounts_cfg.get("verticals") or {}).items()
        for acct in accts
    ]
    caps = accounts_cfg.get("caps") or {}
    per_account = int(caps["per_account_per_week"]) if caps.get("per_account_per_week") else None
    per_vertical = int(caps["per_vertical_per_week"]) if caps.get("per_vertical_per_week") else None
    # Billing is per post RETURNED — never request more than the per-account cap keeps
    # (API bounds: 5 ≤ max_results ≤ 100). Newest-first at the API = keep-newest, which
    # is exactly the chronological-truncation overflow policy.
    max_results = min(100, max(5, per_account)) if per_account else 100

    base = Path(cache_dir if cache_dir is not None else DIGEST_CACHE_DIR)
    resolved = resolve_user_ids(
        [h for _, h in accounts], token,
        cache_dir=base, timeout=timeout, errors=errors, notes=notes,
    )
    since = load_since_ids(base / X_SINCE_ID_CACHE)
    updated = dict(since)
    budget = _Budget(max_requests, rate_limit_per_sec)
    items: list[Item] = []
    deferred = 0
    for vertical, handle in accounts:
        info = resolved.get(handle)
        if not info:
            continue  # unresolved — already counted by resolve_user_ids
        if not budget.take():
            deferred += 1
            continue
        url = timeline_url(info["id"], since_id=since.get(handle), max_results=max_results)
        try:
            payload, headers = _bearer_get_json(url, token, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise XChannelOff("HTTP 401 — bearer token rejected") from e
            if e.code == 429:  # rate-capped mid-run: stop, defer the rest, keep since_ids
                budget.limited_reset = str(
                    (e.headers or {}).get("x-rate-limit-reset", "?")
                )
                deferred += 1
                continue
            if errors is not None:  # 403/404/…: protected/suspended/gone — one dead arm
                errors.append(f"x_lists/@{handle}: HTTPError {e.code}")
            continue
        except Exception as e:  # noqa: BLE001 — the fail-soft boundary is the point
            if errors is not None:
                errors.append(f"x_lists/@{handle}: {type(e).__name__}: {e}")
            continue
        budget.observe(headers)
        items += timeline_items(payload, handle=handle, vertical=vertical)
        meta = payload.get("meta") or {}
        if meta.get("newest_id"):
            updated[handle] = str(meta["newest_id"])
        if meta.get("next_token") and notes is not None:
            notes.append(
                f"x_lists: @{handle} posted more than {max_results} since last pull; "
                "older dropped (per-account cap)"
            )
    if deferred and notes is not None:
        reason = (
            f"rate-limited (reset {budget.limited_reset})"
            if budget.limited_reset
            else f"request budget ({max_requests}) exhausted"
        )
        notes.append(f"x_lists: {reason}; {deferred} account(s) deferred to next run")
    return _cap_verticals(items, per_vertical, notes), updated
