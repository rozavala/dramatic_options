# RATIFIED — The restricted list (insider-relationship exclusion) + the network-channel line

**Status: RATIFIED 2026-07-15.** Operator's word verbatim: *"This is some feedback I got.
Let's go with this if you agree with it."* (2026-07-15) — informed delegation adopting the
advisor's plan, whose item 1 was "give the ratifications"; the rule and entry R-001 as
drafted below. CC's agreement recorded.

## The rule (person-anchored, not ticker-anchored)

Any name where the operator has a personal relationship with an insider is **permanently
excluded from every path** — register admission, `universe.themes` scan baskets, `themes.json`,
probe files, forward-catalyst pins, and **all books including the null books**
(shadow / 3A / 3B / shares) — regardless of thesis quality or public-record grounding.

Rationale (advisor round 2026-07-13, endorsed): the exposure is not only MNPI leakage into a
thesis — it is that a large asymmetric payoff on an insider-friend's name is indefensible
optics *even when perfectly public-record grounded*, and a large asymmetric payoff is exactly
what this strategy produces when it works. The null-book clause is deliberate: a restricted
name printing a 10× in a shadow book is a temptation generator with no offsetting
informational value.

**Entries name the RELATIONSHIP; tickers are derived.** If the person changes companies or
roles, the derived ticker set changes with them. The list is reviewed whenever a listed
relationship or role changes; review is the operator's act.

## Entry #1 (ID: R-001)

- **Relationship:** personal friend of the operator; CEO of Ethos Technologies Inc.
- **Derived tickers (current):** LIFE (Nasdaq) — and any future issuer where this person is an
  insider. **The mechanism for the future-issuer clause is the periodic re-confirmation tick
  below** (the clause is not self-executing; the tick is what notices the change).
- **Added:** 2026-07-14. The LIFE staging option (2026-07-13 triage, option (b)) is DEAD; the
  options-class-listing watch is retired. The kill scope stands as recorded: chain-absence +
  consumption pattern on that day's record — not "bad company."

## Review cadence

Event-driven (a listed relationship or role changes) AND periodic: **the list is re-confirmed
at the 2026-09-30 reach-channels checkpoint and at each subsequent one** — the tick that
closes the unnoticed-role-change gap and executes each entry's derived-ticker refresh.

## Enforcement plan (follow-up PR, fail-closed, defense in depth)

**The repo file carries no relationship data.** `restricted.json` holds opaque entry IDs +
derived ticker arrays ONLY — e.g. `{"id": "R-001", "tickers": ["LIFE"]}` — because a
person-keyed repo file exercised by CI would write the relationship into infrastructure
(repo history, CI logs, collaborator surfaces, the tailnet dashboards). The ID → person
mapping, relationship prose, and review triggers live HERE, at the governance layer.
Enforcement needs only tickers to fail closed.

Checks at: (a) the curation PR gate (a restricted symbol anywhere in the
register/`universe.themes` fails CI — merge-blocker test), (b) union construction (a
restricted symbol never enters the candidate union, any origin), (c) each book cycle
including ALL null books (belt-and-suspenders), (d) probe drivers and the forward-catalyst
pin loader. Absent/malformed `restricted.json` → fail-closed (a missing list blocks admission
acts, never silently passes).

**Sequencing under the #185 ruling:** the RULE binds at ratification — the operator's word
makes the list effective immediately, code or no code. The enforcement PR is built promptly
but **STAGED, merging after the §5 read closes (post-2026-08-02) by default**: on the current
universe the checks are provably a no-op (no restricted name sits in any path), so the scans
would be byte-identical either way — but staging costs nothing and leaves no argument. An
earlier merge requires an explicit dated operator line.

## The network-channel line (same governance act, second half)

Personal-network sourcing is a **legitimate curation input** — structurally decorrelated from
media salience (the property every automated source lacked; the LIFE episode is the live
demonstration). Network-sourced candidates are provenance-tagged (`network`) per the reach-
channels charter, are subject to the same public-record grounding discipline as every thesis,
and are **excluded when the source relationship is an insider one** (this list).

## Ratification

See the status line — ratified 2026-07-15 under informed delegation. The rule is EFFECTIVE
NOW; the enforcement PR (fail-closed code) follows, staged, merging post-2026-08-02 by
default per the sequencing clause above.
