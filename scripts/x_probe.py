#!/usr/bin/env python3
"""X API tier/pricing probe — the RETAINED charter §2(b) precondition (run BEFORE enabling).

Reach-channels charter (records/2026-07-14_reach_channels_charter_RATIFIED.md) §2 + the
2026-07-16 amendment: the manual-v0 yield precondition is WAIVED (dated operator word);
THIS check is retained — the x_lists channel ships CONFIG-DISABLED in ``x_accounts.json``
and is enabled by the operator flipping ``"enabled": true`` ONLY after this probe passes
on-box. Standalone and manual (never systemd, never imported by the digest runner).

What it does (2 or 3 billable requests, ~$0.05 at current pricing):
  1. Verifies the bearer token resolves via the ``config_loader`` seam
     (``X_BEARER_TOKEN`` in .env → ``config["x_api"]["bearer_token"]``).
  2. Probes ``GET /2/users/by`` (handle→id lookup) on a small sample of the configured
     handles and prints the resolved display names (the eyeball surface).
  3. Probes ``GET /2/users/:id/tweets`` with the leg's EXACT no-engagement field set
     (``tweet.fields=created_at,text``, ``exclude=retweets,replies`` — public_metrics is
     never requested, charter §2).
  4. Reports the rate-limit headers observed on each endpoint, the estimated weekly
     request/read volume for the configured accounts, and a PASS/FAIL verdict.

X developer pricing as checked 2026-07-16 (docs.x.com/x-api/getting-started/pricing via
web fetch, plus third-party pricing trackers postproxy.dev / blotato.com / api.sorsa.io /
twitterapi.io, all July 2026):

  - X replaced its tiered plans with PAY-PER-USE as the default for NEW developers
    (effective ~2026-02-06): credits are purchased upfront in the Developer Console and
    deducted per request. There is NO free tier. Legacy Basic ($200/mo) and Pro
    ($5,000/mo) remain only for existing subscribers (closed to new signups); Enterprise
    starts ~$42,000/mo.
  - Post reads: $0.005 per post — billed per RESOURCE RETURNED, not per request (a quiet
    since_id week bills ~nothing).
  - User reads (e.g. ``/2/users/by``): $0.010 per user.
  - "Owned reads" (your OWN posts/lists/followers): $0.001 per resource — does NOT apply
    to reading other accounts' timelines, which is what this leg does.
  - Post creation: $0.015 ($0.200 with a link) — irrelevant; this leg is read-only.
  - An operator-set spend cap per billing cycle is available in the Developer Console.

  CONTRADICTION FLAG vs the prior "pay-per-use $0.005/post, 2M/month cap": the
  $0.005/post-read rate is CONFIRMED by the official pricing page. The "2M post
  reads/month cap" is reported by the third-party trackers as the pay-per-use ceiling
  (Enterprise above it), but the official pricing page as fetched 2026-07-16 shows NO
  hard monthly cap — it offers the operator-set spend cap instead. Also note the prior
  statement omits that USER lookups bill separately at $0.010/read (one-time ~$0.48 for
  48 handles, then cached). Verify the Developer Console's own numbers when running this
  probe — pricing metadata is NOT exposed via API response headers.

  This leg's steady-state volume at the shipped config (48 accounts,
  per_account_per_week=10): ~49 requests/week (1 amortized users/by batch + 48 timeline
  pulls), ≤480 post reads/week → ≈2,088 posts/month ≈ $10.44/month UPPER BOUND at
  $0.005/post (real weeks bill less: max_results is capped at the per-account cap and
  billing is per post returned). One-time handle resolution: 48 × $0.010 = $0.48.

Run (from the repo root, on the box with .env):
    venv/bin/python scripts/x_probe.py [--accounts x_accounts.json] [--sample 2]

Exit 0 = PASS (safe to flip ``"enabled": true`` — that flip is the channel's activation
date, charter §1). Exit 1 = FAIL (leave disabled; the reason is printed). The token is
never printed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:  # `python scripts/x_probe.py` puts scripts/ first
    sys.path.insert(0, str(_ROOT))

POST_READ_USD = 0.005  # per post returned (docs.x.com, checked 2026-07-16)
USER_READ_USD = 0.010  # per user resource (docs.x.com, checked 2026-07-16)
WEEKS_PER_MONTH = 52 / 12


def _print_rate_headers(label: str, headers: dict[str, str]) -> dict[str, str]:
    """Print every rate/limit header observed (x-rate-limit-*, x-app-limit-*,
    x-user-limit-*); returns just the x-rate-limit-* trio for the verdict."""
    picked = {
        k: v
        for k, v in sorted(headers.items())
        if k.startswith(("x-rate-limit", "x-app-limit", "x-user-limit"))
    }
    if picked:
        for k, v in picked.items():
            print(f"[x-probe]   {label} {k}: {v}")
    else:
        print(f"[x-probe]   {label} (no rate-limit headers observed)")
    return picked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--accounts", default="x_accounts.json", help="accounts config path")
    parser.add_argument(
        "--sample", type=int, default=2, help="handles to probe via users/by (default 2)"
    )
    args = parser.parse_args(argv)

    from config_loader import load_config
    from data.x_feed import TWEET_FIELDS, _bearer_get_json, timeline_url, users_by_url

    failures: list[str] = []

    # ── token via the config seam (never os.environ here, never printed) ──────
    token = (load_config().get("x_api") or {}).get("bearer_token")
    if not token:
        print("[x-probe] FAIL — no bearer token: set X_BEARER_TOKEN in .env "
              "(config_loader maps it to config['x_api']['bearer_token'])")
        print("[x-probe] VERDICT: FAIL")
        return 1
    print("[x-probe] token resolved via config_loader (X_BEARER_TOKEN) — not printed")

    # ── the configured pond + volume estimate ─────────────────────────────────
    cfg = json.loads(Path(args.accounts).read_text())
    accounts = [
        (vertical, str(acct["handle"]))
        for vertical, accts in (cfg.get("verticals") or {}).items()
        for acct in accts
    ]
    n = len(accounts)
    per_account = int((cfg.get("caps") or {}).get("per_account_per_week", 10))
    weekly_requests = math.ceil(n / 100) + n  # users/by batches (amortize→0 once cached) + pulls
    weekly_posts_max = n * per_account
    monthly_posts_max = weekly_posts_max * WEEKS_PER_MONTH
    print(f"[x-probe] configured: {n} account(s), per_account_per_week={per_account}, "
          f"enabled={bool(cfg.get('enabled'))}")
    print(f"[x-probe] estimated volume: ≤{weekly_requests} requests/week; "
          f"≤{weekly_posts_max} post reads/week ≈ {monthly_posts_max:.0f}/month")
    print(f"[x-probe] estimated cost basis (docs.x.com 2026-07-16, per-resource billing): "
          f"≤${monthly_posts_max * POST_READ_USD:.2f}/month post reads "
          f"+ one-time ${n * USER_READ_USD:.2f} handle resolution "
          f"(quiet since_id weeks bill ~nothing; see module docstring for the dated "
          f"pricing summary + the 2M/month-cap contradiction flag)")

    # ── probe 1: users/by (handle→id; the eyeball surface) ────────────────────
    sample = [h for _, h in accounts[: max(1, args.sample)]]
    resolved: list[dict[str, str]] = []
    try:
        payload, headers = _bearer_get_json(users_by_url(sample), token)
        _print_rate_headers("users/by", headers)
        resolved = list(payload.get("data") or [])
        for row in resolved:
            print(f"[x-probe]   users/by OK: @{row.get('username')} → {row.get('name')!r} "
                  f"(id {row.get('id')})")
        if not resolved:
            failures.append(f"users/by returned no users for sample {sample}")
    except urllib.error.HTTPError as e:
        _print_rate_headers("users/by", {k.lower(): v for k, v in (e.headers or {}).items()})
        reason = {401: "token rejected (401)", 403: "tier does not allow user lookup (403)",
                  429: "rate-limited at first request (429)"}.get(e.code, f"HTTP {e.code}")
        failures.append(f"users/by: {reason}")
    except Exception as e:  # noqa: BLE001 — a probe reports, never crashes
        failures.append(f"users/by: {type(e).__name__}: {e}")

    # ── probe 2: users/:id/tweets (the leg's exact no-engagement request) ─────
    tweets_headers: dict[str, str] = {}
    if resolved:
        uid, uname = str(resolved[0]["id"]), str(resolved[0].get("username"))
        url = timeline_url(uid, since_id=None, max_results=5)
        assert "public_metrics" not in url  # charter §2 — the probe uses the leg's own literals
        try:
            payload, headers = _bearer_get_json(url, token)
            tweets_headers = _print_rate_headers("users/:id/tweets", headers)
            got = len(payload.get("data") or [])
            print(f"[x-probe]   users/:id/tweets OK: @{uname} → {got} post(s) "
                  f"(fields: {TWEET_FIELDS}; ~${got * POST_READ_USD:.3f} billed)")
        except urllib.error.HTTPError as e:
            _print_rate_headers(
                "users/:id/tweets", {k.lower(): v for k, v in (e.headers or {}).items()}
            )
            reason = {401: "token rejected (401)",
                      403: "tier does not allow timeline reads (403)",
                      429: "rate-limited (429)"}.get(e.code, f"HTTP {e.code}")
            failures.append(f"users/:id/tweets: {reason}")
        except Exception as e:  # noqa: BLE001
            failures.append(f"users/:id/tweets: {type(e).__name__}: {e}")
    else:
        failures.append("users/:id/tweets: not probed (no resolved user id)")

    # ── verdict: both endpoints usable AND the window limit covers one run ────
    limit = (tweets_headers or {}).get("x-rate-limit-limit")
    if limit is not None and limit.isdigit() and int(limit) < n:
        failures.append(
            f"tweets endpoint window limit {limit} < {n} accounts — one weekly run "
            f"cannot complete in a single rate window (the fetcher would defer "
            f"{n - int(limit)} account(s) to the NEXT week)"
        )
    if failures:
        for f in failures:
            print(f"[x-probe] FAIL — {f}")
        print("[x-probe] VERDICT: FAIL — leave x_accounts.json disabled")
        return 1
    print("[x-probe] VERDICT: PASS — both endpoints usable at this tier; volume estimate "
          "above. Enabling is the operator's flip of x_accounts.json \"enabled\": true "
          "(that flip = the channel's activation date, charter §1).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
