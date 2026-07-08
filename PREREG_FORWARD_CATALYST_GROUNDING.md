# PREREG — Forward-Catalyst Grounding Channel

**STATUS: DRAFT v0 (2026-07-08) — NOT FROZEN. This document binds nothing.** It exists for the
operator's red-team. House convention: merge = freeze; this PR is to be held OPEN until the
operator's explicit per-section word. The build is separately gated on a fresh go after freeze.

## §0 Why — the located wall this addresses (and what it cannot buy)

The council's grounding corpus is markers + filed XBRL + analyst-coverage/news counts. Three
faces of the resulting wall are demonstrated on the record (2026-07-07/08 records):

1. **Trailing-evidence at_inflection** — the strategist grades inflection on what has already
   printed; RUN was rejected at +52% TTM revenue acceleration *cited in the rationale* because
   the tape/trailing evidence had "already moved" (solar, CC).
2. **Coverage-count under_narrated** — the count can't see qualitative under-narration (solar
   at 22–31 analysts; TROX judged False at 8).
3. **Evidence-channel** (KMT) — load-bearing evidence (input-commodity price, APT ~9×) sits
   outside the corpus entirely → a deliberated proposer abstention: the council *cannot* see
   the thesis's driver, however real.

The class that dies BY CONSTRUCTION: theses whose inflection is a **dated, public, forward
fact** — statutory step-downs/sunsets, dated program milestones, contracted ramps, published
input-cost shocks — rather than a trailing print. Evidence file: TROX, CLFD, KMT, solar
(retrospective), plus nine documented consumption cases bounding the alternative.

**The floors-first bound (batch-3 correction, pinned here):** the channel buys ADJUDICABILITY
for names that already pass the frozen floors/feasibility screen. It cannot buy expression for
sub-floor names (OPAL/MNTK died at floors — channel-irrelevant) or immunity from the tape.

## §1 The principle — GROUND, NEVER PERMISSION

The §9 idiom, unchanged from `PREREG_EVIDENCE_GROUNDING` / `corpus:fundamentals_v1`: the
channel ADDS evidence to the council's `ContextPack`. It never scores, never gates, never
admits, never sizes. A channel-grounded candidate still needs the same §10.7 tri-criteria
judgment, the same IV gate, the same caps. Prompts stay sha-pinned and byte-identical — the
channel rides the pack, not the prompt (`tests/test_council_prompts.py` must hold unmodified).

## §2 Evidence classes (exhaustive; anything not listed is out)

Each item is a dated claim: `{claim, event_date, source (public doc/register/print), as_of
(when pinned), expires (when stale), provenance}`.

- **(a) Statutory/regulatory dated events** — e.g. a credit's first-print date, a sunset/step-
  down, a dated review. Instrument: the public legal text or register entry itself.
- **(b) Filed forward commitments** — backlog/RPO/take-or-pay/contracted-capacity lines from
  filings (extends the existing XBRL corpus to FORWARD-dated lines, same PIT discipline).
- **(c) Dated program/procurement milestones** — e.g. state-level program construction starts
  with public announcements (the CLFD/BEAD class).
- **(d) Published input-commodity prices** — exchange/assessment prints for a named input (the
  KMT/APT class). Public, dated, re-derivable prints only.

## §3 Source discipline

Point-in-time stamped; independently re-derivable from the named public source; **no
LLM-generated facts** — items are operator-pinned or mechanically pulled, never model-authored
(`generated` provenance reserved, as in the §11 register). The quote-authenticity filter
extends to channel text (`filters.evidence_text` supports the citations, the PR #55 lesson).
An item past `expires` drops silently from the pack — stale forward claims are worse than none.

## §4 Council integration

A bounded `forward_catalysts` block in `ContextPack` (the fundamentals_v1 shape): ≤K items per
candidate, each dated. Stamp `corpus:forward_catalyst_v1` into `runs.model_mix` — a
record-segmenting event, zero migration. Origin scope v0: **hand-seed + staged register
candidates only**; sentinel grounding stays byte-unchanged (the §6 framer leash holds).

## §5 The one behavior change

`at_inflection` adjudication gains access to dated forward evidence. `structural` and
`under_narrated` adjudication are untouched — the channel does not argue narration, only
timing. If the council still reads at_inflection=False *with the dated catalyst in view*, that
is a judgment, not a wall — and it stands.

## §6 Forward-scoring the channel itself (never backtested — guardrail §6)

Every channel-grounded deliberation records the block's presence in `rationale` telemetry.
The channel's read is the PAIRED contrast: for the first M channel-grounded candidates, an
ephemeral no-channel re-score (same candidate, block withheld) gives the counterfactual —
surfaced to the operator, never auto-acted. Catalyst-dated outcomes feed Brier as usual.

## §7 Cost & kill

Bounded token add per pack (pinned at freeze). Fail-soft: a missing/expired/malformed item
never blocks a cycle — the block degrades to absent, exactly like fundamentals `status:
"none"`. Kill-before-spend unchanged.

## §8 Falsifiers for the channel (the channel dies by its own rules)

- **F-a (didn't buy adjudicability):** after the first **M=8** channel-grounded judgments,
  at_inflection=True on **0** of them → the wall was mandate-level, not evidential; retire the
  channel (dated record).
- **F-b (integrity):** any item found non-re-derivable, undated, or LLM-authored → halt the
  channel same-day, audit all items, record before re-arm.
- **F-c (leniency leak):** include-rate rises without the includes citing the dated catalysts
  (rationale check) → halt; the channel is grounding, not permission, and a diffuse leniency
  shift is the §5 failure mode.

## §9 Explicitly out of scope

Idea supply / thesis generation (the closed fork stays closed); any floor/gate/cap/mandate
edit; any prompt edit; sentinel grounding changes; admission mechanics; sizing. The register's
§11 admission rule is untouched — a channel-grounded name still enters only via a window or a
§3 exception with the operator's word.

## §10 Freeze & build process

Operator red-team (per-section word, TRUE-form ratification — merge-inherits-nothing). Freeze
= merge of this document after that word. Build PRs only after freeze, each green before the
next. Numbers left open for the red-team: K (items per pack), M (F-a sample), the token bound.
