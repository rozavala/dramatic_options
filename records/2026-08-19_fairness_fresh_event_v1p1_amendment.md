# 2026-08-19 — Fairness reserve fresh-event leg v1.1 (the leg-1 no-op fix)

**Status: STAGED — in force only from the operator's explicit merge of the build PR (the
activation act). Amends the 2026-08-11 fairness-reserve amendment
(`records/2026-08-11_fairness_reserve_amendment.md`); rank structure unchanged, leg-1's
SOURCE and lifetime fixed.**

## The finding (2026-08-17, L1 #956 grade; reproduced #973)

`fresh_event=[]` on 08-14, 08-17 and 08-18 despite the 08-16 L0 detecting four fresh
structural filings (IRDM/PWR/RKLB/SMR, stamped `fresh_on_active_lineage=` in `runs.note`).
Root cause, DB-confirmed: `state.fresh_event_symbols` read the sentinel ROW
(`last_seen_at ≥ now−7d` AND `markers.has_event`) — but an ACTIVE lineage is
novelty-excluded from re-surfacing, so both fields freeze at original surface time
(IRDM 07-26, PWR/RKLB 07-19, all `has_event=False`). The L0's event detection goes to
`runs.note` only (the 2026-07-13 LUNR amendment's deliberate "detection-layer visibility
ONLY" scope). Net: **leg 1 could never fire for its motivating case** — a fresh filing on
an old active lineage, the exact LUNR/IRDM gap the fairness reserve was built to close. It
could only fire for a name surfaced ≤7d ago already carrying an event at surface time.
Leg 2 (least-recently-judged) meanwhile carried the rotation correctly (8 distinct rescues
in 4 nights).

## The fix (fork (a) of the three presented 08-17; operator said "Go" 08-19)

`state.fresh_event_symbols` v1.1 — two visibility sources, unioned, then a demotion rule:

1. **Row leg (unchanged):** active sentinel re-surfaced within `window_days=7` with
   `markers.has_event` — visibility timestamp = `last_seen_at`.
2. **Note leg (new):** the latest `mode='DISCOVERY'` run within `window_days` whose note
   carries `events:ON`; parse the `fresh_names=` token (the PREREG_EVENT_LEG §4 stamp the
   detection layer already persists), intersect with the ACTIVE sentinel set — visibility
   timestamp = that run's `started_at`. Single-sources from the existing detection stamp;
   no new fetch, no schema change, surfacing/judgment mechanics untouched (the 07-13 pin
   holds — this is a read of the visibility stamp, not a mechanics change).
3. **Judged-since-visibility demotion (new, uniform over both legs):** a symbol
   council-judged at-or-after its visibility timestamp drops out of leg 1. The amendment's
   intent is judged-the-NEXT-L1 **once**; without this, the 14d detection lookback (≈2
   scans) would pin a fairness slot to the same name nightly for up to two weeks,
   starving the rotation the reserve exists to serve.

Fail-soft throughout: `events:OFF`, a missing `fresh_names` token, a malformed note, or a
stale (>7d) L0 each contribute nothing — the leg degrades to the pre-fix behavior, never
raises. A deliberate operator `events:OFF` can linger in this leg at most 7 days (the
window guard bounds note staleness).

## Named limitation (the semantics loosening, stated not silent)

The note carries names, not filing timestamps. A note-sourced name's filing may be up to
14 days old at detection (the closed L0 lookback) — the original 08-11 wording's "≤7d"
freshness cannot be enforced against the filing date from this source. The honest v1.1
semantics: **leg-1 priority applies for the week following detection, until first
judgment.** The detection window itself is unchanged (funnel knobs, dated-edit-only).

## Record segmentation

`runs.model_mix.union_rank` → `cheap_reserve_v1+fairness_v1.1` from the deploy (zero
migration, self-describing). Never pool fairness-slot selection reads across the boundary;
council-marginal/Brier pooling rules unchanged (the composition still only changes WHO is
judged, never HOW — the §10 seam guard; `compose_judged_set` byte-untouched).

## Provenance (TRUE form)

The no-op finding and three design forks were reported to the operator in the 2026-08-17
nightly grade; the operator asked "Anything we need to work on?" 2026-08-19, was given the
board with fork (a) recommended, and answered **"Go"** — informed delegation on the
recommended fork (red-team + staged build). The demotion rule and the named limitation
were added by the build's own red-team and are presented for review IN this record; the
operator's merge of the build PR ratifies both and is the activation act.
