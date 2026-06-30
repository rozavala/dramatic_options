"""One-command curation executor — draft a §11 theme entry and OPEN A PR (PREREG_UNIVERSE_CURATION §11).

Collapses the manual curation hop (fill form → copy JSON → edit file → branch → commit → push → open PR)
into a single command. It reuses the SAME tested drafter the dashboard uses (``dashboard_data.build_theme_entry``,
cluster-cap guard included), then writes the additive entry, branches, commits, pushes, and opens the PR.

**The seam (why this is the safe self-executable piece):**
- It edits ONLY ``universe_register.json`` — the §11 *rule artifact*, which the trading loop NEVER loads
  (``config.universe.themes`` is the loop-facing basket). So this is **inert to trading**: it records a
  falsifiable thesis, it does not admit a single name to the scan. Constituent NAMES enter later via the
  feasibility screen (the separate, gated step).
- **Additive-only:** it refuses to overwrite an existing theme key (the §11 additive rule).
- **Merge stays the operator's** — it OPENS a PR, never merges. The merge is the §11 operator veto +
  frozen-frame discipline; branch protection requires CI green first.
- No market/trading keys — only ``git``/``gh`` (the dashboard stays the keyless read-only previewer; this
  executor is run intentionally by the operator).
- ``--source`` is NOT fetch-validated here (keyless) — it is exercised at the KEYED screen step; a merged
  register PR records the thesis, it does NOT confirm the source actually fetches.

Usage (repo root):
    python scripts/curation_open_pr.py --name "silver deficit" --cluster silver_deficit \\
        --thesis "..." --falsifier "..." --source "SIL constituent file (stockanalysis.com/etf/sil/holdings)"
    python scripts/curation_open_pr.py ... --dry-run    # validate + preview the entry/diff/PR body, no writes
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REGISTER = REPO / "universe_register.json"

sys.path.insert(0, str(REPO))

from config_loader import load_config  # noqa: E402
from dashboard_data import build_theme_entry, cluster_names  # noqa: E402


def merge_theme(register: dict, key: str, entry: dict) -> dict:
    """Additive insert of ``{key: entry}`` into the register's ``themes``. Raises on an existing key
    (the §11 additive-only rule — never clobber a recorded thesis). Returns the new register dict."""
    themes = register.get("themes")
    if not isinstance(themes, dict):
        raise ValueError("universe_register.json has no 'themes' object")
    if key in themes:
        raise ValueError(f"theme '{key}' already exists (additive-only; edit via a dated amendment, not this tool)")
    out = dict(register)
    out["themes"] = {**themes, key: entry}
    return out


def insert_theme_text(base_text: str, key: str, entry: dict) -> str:
    """Append ``{key: entry}`` as the LAST theme via a minimal TEXT splice — the rest of the file
    (notably the hand-aligned ``windows.admitted`` one-liners) is preserved **byte-for-byte**, so the
    diff shows ONLY the inserted theme. This is the executor's *auditability invariant*: a full
    ``json.dumps`` re-serialize reformats the whole file (compact one-liners → multi-line), burying the
    real change in reformat noise — which defeats the keyless/inert/eyeball-the-diff safety case for
    automating this hop at all. The caller MUST validate the result deep-equals the intended dict.

    Inserts at the themes-dict close (the ``},`` immediately before the top-level ``"windows"`` key),
    indenting the new entry to the themes level (key at 4 spaces). Raises if that anchor is absent."""
    block = json.dumps({key: entry}, indent=2, ensure_ascii=False)
    inner = "\n".join("  " + ln for ln in block.split("\n")[1:-1])  # drop outer braces; re-indent to themes level
    anchor = '\n  },\n  "windows"'  # themes-dict close immediately followed by the top-level windows key
    if anchor not in base_text:
        raise ValueError("register format unexpected: themes-close/windows anchor not found")
    i = base_text.index(anchor)
    return base_text[:i] + ",\n" + inner + base_text[i:]


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], check=True, capture_output=True, text=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser(description="Open a §11 theme-register PR (curation executor)")
    ap.add_argument("--name", required=True, help="theme name (→ snake_case key)")
    ap.add_argument("--cluster", default="", help="cluster_default (enforcement-map key; new is allowed w/ a warning)")
    ap.add_argument("--thesis", required=True)
    ap.add_argument("--falsifier", required=True, help="what would kill the thesis")
    ap.add_argument("--source", required=True, nargs="+",
                    help="mechanical constituent source(s) — ETF holdings file(s); repeatable for multi-ETF themes")
    ap.add_argument("--added-label", default="off-cycle",
                    help="the register 'added' note (audit convention), e.g. 'window #3'; default 'off-cycle'")
    ap.add_argument("--dry-run", action="store_true", help="validate + preview only; no branch/commit/push/PR")
    args = ap.parse_args()

    config = load_config()
    draft = build_theme_entry(name=args.name, cluster=args.cluster, thesis=args.thesis,
                              falsifier=args.falsifier, source=args.source,
                              added_label=args.added_label, known_clusters=cluster_names(config))
    key, entry = draft["key"], draft["entry"]
    for w in draft["warnings"]:
        print(f"  ⚠ WARNING: {w}")
    if not draft["valid"]:
        for p in draft["problems"]:
            print(f"  ✗ {p}")
        print("\nrefused — fix the problems above (no PR opened).")
        return 1

    print(f"\n=== §11 theme entry: {key} ===")
    print(json.dumps({key: entry}, indent=2, ensure_ascii=False))
    print("\n(writes ONLY universe_register.json — the §11 rule artifact the loop never loads; names enter "
          "later via the KEYED screen, NOT here. Additive; merge stays yours.)")

    if args.dry_run:
        local = json.loads(REGISTER.read_text())
        if key in (local.get("themes") or {}):
            print(f"  ⚠ note: '{key}' already in the LOCAL register (the real run checks a fresh origin/main).")
        print("\n--dry-run: preview only; the real run merges onto a FRESH origin/main base. No writes/PR.")
        return 0

    # P2 — build the merge on a FRESH origin/main base, NEVER the worktree: the worktree register may LAG
    # origin/main (the linked-worktree race) and writing a worktree-based merge over an origin/main checkout
    # would silently DROP any theme merged since the last sync. Fetch → read the base from origin/main →
    # merge (+ dup-check) → only THEN branch + write, so new_text and the checked-out tree share one base.
    branch = f"curate-theme-{key}"
    _git("fetch", "origin", "main")
    base_text = _git("show", "origin/main:universe_register.json")
    register = json.loads(base_text)
    try:
        new_register = merge_theme(register, key, entry)   # additive-check + the intended dict
    except ValueError as e:
        print(f"  ✗ {e}")
        return 1
    # Minimal TEXT splice (NOT a full json.dumps re-serialize) so the diff shows ONLY the new theme —
    # the auditability invariant (a re-serialize reformats the whole file). Validate the splice
    # deep-equals the intended dict before writing: a mis-splice ABORTS, it can never corrupt the register.
    new_text = insert_theme_text(base_text, key, entry)
    if json.loads(new_text) != new_register:
        print("  ✗ splice validation failed (result would not match the intended register) — aborting")
        return 1
    _git("checkout", "-B", branch, "origin/main")
    REGISTER.write_text(new_text)
    _git("add", "universe_register.json")
    msg = (f"curation: register theme '{key}' (§11, operator) — inert to the loop\n\n"
           f"Additive universe_register.json entry (the §11 rule artifact; config.universe.themes — the "
           f"loop-facing basket — is unchanged, so this admits no name and is inert to trading). Names enter "
           f"via the feasibility screen. Merge = the §11 operator veto.\n\n"
           f"Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>\n"
           f"Claude-Session: https://claude.ai/code/session_011weNZd94AxRAcS1Tfjzex2")
    subprocess.run(["git", "-C", str(REPO), "commit", "-F", "-"], input=msg, text=True, check=True)
    _git("push", "-u", "origin", branch)
    warn_block = ("\n".join(f"- ⚠ {w}" for w in draft["warnings"]) + "\n\n") if draft["warnings"] else ""
    body = (f"Adds the §11 theme **`{key}`** to `universe_register.json` (provenance: operator).\n\n"
            f"{warn_block}"
            f"**Inert to trading:** `universe_register.json` is the §11 rule artifact — the loop never loads it "
            f"(`config.universe.themes` is the scan basket, unchanged here). This records a falsifiable thesis; "
            f"constituent names enter later via the feasibility screen (the gated step). Additive-only; "
            f"**merge = the §11 operator veto** (frozen-frame discipline; CI must pass).\n\n"
            f"🤖 Generated with [Claude Code](https://claude.com/claude-code)")
    pr_url = subprocess.run(["gh", "pr", "create", "--repo", "rozavala/dramatic_options", "--base", "main",
                             "--head", branch, "--title", f"curation: register theme '{key}' (§11)",
                             "--body", body], cwd=str(REPO), check=True, capture_output=True, text=True).stdout.strip()
    print(f"\n✓ PR opened: {pr_url}\n  review + merge (the veto) when ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
