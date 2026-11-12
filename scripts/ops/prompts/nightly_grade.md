GRADE TONIGHT'S 19:45 UTC L1 — Dramatic Options, DEV box `all-options-dev`. SCHEDULED UNATTENDED RUN: the operator is
not present. READ-ONLY: never write the live DB, never trigger a run, never commit, push, merge, or touch issues/PRs,
never print key values. The ONLY write is the memory banner in step 4.

PATHS: this runner checkout (`scripts/`, `dashboard_data.py`, … — run Python as `DRAMATIC_SKIP_DOTENV=1 PYTHONPATH=.
venv/bin/python`), live checkout /home/rozavala/dramatic_options, live DB
/home/rozavala/dramatic_options/data/dramatic_options.db (open it `file:…?mode=ro`, uri=True; set
`conn.row_factory = sqlite3.Row` before calling `dashboard_data` helpers), memory
/home/rozavala/.claude/projects/-home-rozavala-dramatic-options-claude/memory/dramatic-options-thematic-convexity.md
(the newest banner is at the top, after the front matter).

**EXPECTATIONS come from the record, not from this prompt.** The expected stamps (every `runs.model_mix` key, the
`frame_version`), the running tallies and the watch-list (named names, the tenor-cliff set, the NVDA canary prints,
the shadow marks) are whatever the NEWEST memory banner and `records/STANDING_STATE.md` (on origin/main) say. A stamp
that differs from the newest banner is a FINDING unless STANDING_STATE records a dated change that explains it.

0. If today is not a US market day, report that and stop. If `MAX(run_id) FROM council_proposals` is the run the newest
   banner already graded, report "already graded" and stop.
1. `journalctl -u dramatic-options-l1 --since "$(date -u +%F) 19:40" --no-pager -q` (explicit date): count
   "call failed (attempt" lines; read the Marker refresh, Expressible-first, Cheap-reserve, Coverage meter, Council,
   cost-ledger, parse-health, Corpus refetch, fundamentals-staleness, Quote (spreads), Cycle, dual-read, null-book
   and Book lines and the direction-coherence note.
   `systemctl --failed`; `journalctl -u dramatic-options-l2 --since "$(date -u +%F) 13:00" --no-pager -q | grep -c
   'mark budget exhausted'`; any `status=9/KILL` on dramatic-options-* units today is a finding.
2. Read-only SQLite: `runs.council_health` MUST be 'ok' (provider_fail → censor; name provider + error); every
   `model_mix` key and `frame_version` vs the newest banner; roles_fallback present;
   `council_health_report.council_l1_health(conn)` (ROUNDTRIP_CONFIRMED; parse fails; drops; marker_staleness);
   per-provider cost — the strategist understudy firing is LOUD.
   Council read: per name, proposer/adversary/strategist confidence, the strategist's reason and its
   `under_narrated` / `at_inflection` flags; classify rejections (timing / narration / contradicting fundamentals);
   count `at_inflection=false` of deliberated. Report any name the newest banner or STANDING_STATE asks to watch
   (new admissions' first council reads, repeated reads).
   Persistence (STANDING_STATE watch, 2026-11-04, amended 2026-11-09 to the next 3 reads): for every real-book entry
   whose name was read tonight within its first 3 reads since entry, report that read (at/above the floor, or for a
   backfill entry `include = true` at ≥ LOW) and the entry's tally so far. Reads start strictly after the entry's own
   run; an abstained or NEUTRAL read counts as below. Decided at 2 agreeing reads: 2 at/above ⇒ persisted, 2 below ⇒
   reversed (a 3rd read after a decision is reported but never changes it). A name that goes dormant before a
   decision is "not measurable" and stays out of the count unless it is read again. Continue the running count from
   STANDING_STATE's watch line: decided real entries (the first 5 are the trigger's denominator) against the pinned
   trigger, with backfill entries reported beside it, not in it.
   Running tallies (continue the newest banner's counts, by ROLE): register-thesis consensus-leak, falsifier misuse,
   misattributed claims (check `flagged_unsupported`), productive uses; marker-refresh reads (fresh-as-current /
   at_surfacing misread / since-surfacing contrast; quote any verdict flip). Driver scope (criterion 3, STANDING_STATE):
   for every strategist `at_inflection = true`, is the driver it cites visibly still changing in THIS name's own
   figures/markers (name-level), or is it the basket thesis's driver while the name's own figures decelerate
   (basket-level)? Count basket-level, quote the line, mark above-floor ones. Forward catalysts: the run-note counters;
   if a pinned item reached the strategist, how it was cited (flag any leak into under_narrated/structural).
   Direction coherence: `direction_coherence.parse_summary`; `dashboard_data.direction_coherence_panel(conn)`
   reached_despite_withheld must be empty. Stale fundamentals: only names already known in the banner are expected.
   Foreign-quantity vetoes: any is a finding. Null books: any booking. Dual-read: record_ok, wing_mismatch, flips,
   pages; names that gain or lose structure vs the previous run. NVDA opra canary vs 1.0; the watched shadow marks;
   `dashboard_data.book_pnl(conn)`; `dashboard_data.spend_panel(conn, config)`.
3. Box: live checkout HEAD = origin/main; no failed units; the app answers 200 at
   https://all-options-dev.tail57521e.ts.net:8602/; installed `/etc/systemd/system/dramatic-options-l{0,1,2}.service`
   ExecStart is `-m orchestrator`; `PYTHONPATH=. venv/bin/python scripts/ops/standing_state_issues.py` (read-only,
   #371): a DRIFT line (an open issue STANDING_STATE doesn't list) is a finding only for an issue filed before the
   `as_of` in STANDING_STATE's header (compare `gh issue view N --json createdAt`); one filed since is information
   (the Sunday review lists it). Quote the line.
4. Prepend ONE dated banner to the memory file (same format and density as the newest one; insert it directly above
   the newest banner, never edit older ones).
5. Final message: a concise plain-prose report for the operator. End with exactly one line:
   HEADLINE: <run #, clean or not>; <the one thing that changed or needs attention, or "nothing new">; FINDINGS: <n>
