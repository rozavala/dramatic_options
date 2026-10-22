SUNDAY REVIEW — Dramatic Options, DEV box `all-options-dev`. SCHEDULED UNATTENDED RUN: the operator is not present.
Template: the newest `records/*_sunday_w*.md` on origin/main (same sections, same tone). RULES: never write the live
DB, never trigger a run, never auto-admit, never print key values; records are `.md`. You MAY create a branch from
origin/main, commit the records named below, push it and open ONE records PR. You may NOT merge it, and may not
touch any other PR or issue: merging is the operator's, on resume.

PATHS: this runner checkout (run Python as `PYTHONPATH=. venv/bin/python`), live checkout
/home/rozavala/dramatic_options (read-only: copy the week's digest and cards from its `records/` into the PR), live DB
/home/rozavala/dramatic_options/data/dramatic_options.db (`?mode=ro`), memory
/home/rozavala/.claude/projects/-home-rozavala-dramatic-options-claude/memory/dramatic-options-thematic-convexity.md.
Expectations and the docket come from `records/STANDING_STATE.md` and the newest memory banners, not this prompt.

1. Weekly L0 (12:00 UTC): exit code; scanned/cleared/surfaced/controls/dormant; framer cost; new and re-surfaced
   lineages; the event leg's fresh count; recent admissions — covered, surfaced, as what.
2. The week's digest + survivor cards (13:40 UTC reach run): items, errors, orphan_watch, survivors, homonym checks.
   Copy `records/digests/<week>.md` and `records/cards/<week>.md` from the live checkout into the PR.
3. `PYTHONPATH=. venv/bin/python scripts/catalyst_pin_suggestions.py --out records/<date>_catalyst_pin_suggestions.md`
   — suggestions only.
4. Every pin in `forward_catalysts.json` expiring today: re-verify its source; a dates-only re-pin (as_of today,
   expires +7d) ONLY if its fact is unchanged — else report and leave it to expire.
5. The class-(a) pins (effective dates, litigation, later documents) and the week's council verdicts on them.
6. `PYTHONPATH=. venv/bin/python scripts/probe_miss_baserate.py sweep`.
7. Tenor: which universe names have no eligible contract on live OPRA; any new expiry listed; the expressible count.
   `scripts/probe_basket_feasibility.py` over the near-miss bench — report only (admissions need the operator's word).
8. The week's reads from the nightly banners: slate composition, marker refresh, register-thesis tally by role,
   `at_inflection=false` share, watched names.
9. Hosts: DEV + PROD uptime, reboot-required, failed units, ExecStart `-m orchestrator`, any `status=9/KILL` this
   week, PROD's lag behind main.
10. Write `records/<date>_sunday_w<NN>.md`; refresh `records/STANDING_STATE.md` (as_of, docket, board) if anything
    changed; commit, push, open ONE records PR (do not merge). Prepend one dated memory banner.
11. Final message: plain prose for the operator — what changed, decisions needed, the countdown to the next dated
    review in STANDING_STATE, and the PR link. End with exactly one line:
    HEADLINE: <week>; <the one thing that matters most>; PR <url or "none">
