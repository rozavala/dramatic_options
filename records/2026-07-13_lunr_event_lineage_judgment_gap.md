# 2026-07-13 — The event-leg/lineage judgment gap: a fresh structural filing on a rank-buried active lineage has no path to a council judgment (LUNR)

**Status: OBSERVATION, report-only.** No gate, floor, prereg, or config is moved by this record.
Disposition options are enumerated at the end; the call is the operator's. Found while grading
L1 #526 (Mon 2026-07-13 19:45 UTC — CC-bearish's first council judgment; the L1 itself graded
`ROUNDTRIP_CONFIRMED`, 12 judged, 0 parse errors, 0 entries, $0.186).

## The finding

LUNR filed **SCHEDULE 13D/A twice in one week** — 2026-07-02T01:15:59Z and 2026-07-08T00:00:01Z
(PIT cache `data/cache/filings/LUNR.json`, coverage through 2026-07-12; an active accumulator
amending a 13D is exactly the event class `PREREG_EVENT_LEG` pinned as structural). The L0 #511
event leg **detected it honestly**: run 511's note reads
`events:ON ev=607142 checked=39 cik=39 no_cik=0 fresh=1 err=0 fresh_names=LUNR`.

**No council judgment of that evidence will ever happen under current mechanics.** The chain,
each link verified against the live DB and the code:

1. **07-12 L0 (#511): novelty-excluded.** LUNR already holds a live sentinel lineage — id 28,
   surfaced run #114 (2026-06-10), `inflection_score=-0.44`, `status='candidate'`. The scan's
   novelty exclusion (`orchestrator.py:412` — open positions ∪ active sentinels ∪ themes.json;
   applied at `discovery.py` `passed and sym not in exclude`) skips any name with an active
   lineage. The fresh filing can neither re-surface LUNR nor refresh its score/markers: the
   lineage's markers still read `has_event: false`, `last_seen_at` stays 2026-06-10,
   `surface_count` stays 1. Only CC and CEG surfaced from #511.
2. **07-13 L1 (#526): rank-buried.** The union takes hand-seeds + live sentinels ranked by
   `inflection_score` desc, truncated at `council.max_candidates=12`
   (`sentinels.union_candidates` → `council.propose [:max_candidates]`). LUNR's frozen −0.44
   ranks 22nd of 27 live candidates — it does not ride, and cannot climb because its score can
   only be refreshed by re-surfacing (blocked at step 1).
3. **07-19 L0: still excluded, then dormant.** The exclude set is built BEFORE the scan
   (`orchestrator.py:412`), TTL expiry runs AFTER persist (`orchestrator.py` →
   `state.expire_stale_sentinels`, ttl=35d). At 07-19 the cutoff is 06-14 > LUNR's 06-10
   `last_seen` — so LUNR is *still active during the scan* (excluded again), and flips
   `dormant` only post-scan.
4. **07-26 L0: the door is closed.** First scan where LUNR is novelty-eligible (dormant). But
   the 07-08 filing is now 18 days old — outside the event door's `lookback_days=14`
   (`data/structural_events.py:91`). LUNR can then re-surface only via the motion legs.
5. **The reserve can't carry it either.** Even if a rotation slot judges LUNR later, a
   sentinel pack grounds on its lineage MARKERS (origin-aware grounding, PR2 discipline) — and
   this lineage's markers carry `has_event: false`. The filing never enters any pack.

Net: **the filing was counted but is structurally unjudgeable.** The anti-silent-dormancy
counters did their job at the detection layer (`fresh=1` is on the record); the gap is between
detection and judgment, and it is invisible unless someone walks the chain by hand — which is
what tonight's grade did, because the 07-12 grade had flagged "LUNR fresh structural filing"
as something Monday's council would see. It did not see it.

## The general class

Any name with a **live-but-rank-buried sentinel lineage** that receives **new structural
evidence** is in this state: the active lineage blocks re-surfacing (so the new evidence can't
refresh score or markers), the buried rank blocks the union, and by the time TTL dormancy
restores novelty eligibility the event window (14d) has usually lapsed. The window for the gap
is roughly TTL − lookback ≈ 3 weeks of lineage age: a filing landing in weeks ~2–5 of a
buried lineage's life is silently unjudgeable. Motion-strong lineages are fine (they ride the
union on rank); it is precisely the *faded-motion + fresh-structural-event* combination — a
plausible pre-inflection shape — that falls through.

## Rhythm notes attached to the same grade (context, not defects)

- The whole 2026-06-10 sentinel cohort (PL, FLNC, UUUU, NXE, HBM, UEC, + the buried tail
  incl. LUNR) crosses the 35d TTL at the **07-19 L0**: excluded-then-dormant that run,
  re-surface-eligible **07-26** with fresh markers wherever motion still clears the floors.
  This is the designed recycle (it also self-heals the 33.6d median marker staleness the L1
  health report shows tonight).
- **PL cannot re-surface while the real position is open** (open positions are in the same
  exclude set) — L1 #526 was likely PL's last nightly council read for the duration of the
  hold. By design: exits are the deterministic monitor's job, not the council's.

## Disposition options (the operator's call — none exercised here)

a. **Accept as designed.** The event door exists to admit NEW names; tracked names ride their
   lineage. The cost is the class above, now documented with dates.
b. **Probe-only judgment** (zero-touch): author a LUNR thesis line in `probe_themes.json` and
   run the paired-contrast probe vehicle (~$0.04, ephemeral, hand-seed origin, never touches
   the live path). Answers "what would the council say" without moving anything.
c. **A dated funnel/event-leg amendment** — e.g. "a fresh structural filing on an ACTIVE
   lineage refreshes that lineage's markers/score in place (re-surface semantics, no new
   row)". Touches TWO frozen preregs (`PREREG_FRESH_INFLECTION_FUNNEL`,
   `PREREG_EVENT_LEG`), record-segmenting (`DISCOVERY_FUNNEL_VERSION` bump) — a
   post-§5-read question (after the 2026-08-02 close), not a now question.

A companion **observability** patch (additive: stamp `fresh_on_active_lineage=<names>` into
the L0 status/note so this class is loud at detection time) is staged as its own PR for
explicit operator merge — it extends the frozen event-leg note stamp, so it does not ride the
records pre-authorization.
