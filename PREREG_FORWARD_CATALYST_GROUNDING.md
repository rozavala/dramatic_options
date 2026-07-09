# PREREG — Forward-Catalyst Grounding Channel

**STATUS: DRAFT v1 (2026-07-09) — NOT FROZEN. This document binds nothing.** Held open for the
operator's per-section word (TRUE-form ratification; merge = freeze; build separately gated on a
fresh go after freeze).

## §0.5 Revision log

- **v1 (2026-07-09):** advisor red-team round 1 (relayed by the operator), all four P1 fixes +
  the P2 pins + P3 hygiene applied. Load-bearing changes: §5 rewritten to the honest pack-wide
  visibility claim (mechanism verified in `council/debate.py` — the pack goes to all three
  roles; there is no per-criterion visibility control) and now covers the KMT proposer-abstention
  face; §9.5 added (explicit supersession of the 2026-07-07 KMT re-entry pin); F-a re-instrumented
  as horizon-eligible paired-contrast flip-rate with THREE dispositions incl. a pre-registered
  mandate-amendment escalation; class (b) EXCLUDED (one home for filed lines — the fundamentals
  corpus); per-class source instruments pinned incl. the class-(d) public-source fail-closed
  rule; telemetry counters; the date-token filter deviation named; §5-read-safety asserted;
  catalyst-claim accuracy split from trade Brier; paired-contrast spend pinned into §7; the two
  §0 honesty lines added; the solar citation repaired to a committed record (PR #168).
- v0 (2026-07-08): initial skeleton.

## §0 Why — the located wall this addresses (and what it cannot buy)

The council's grounding corpus is markers + filed XBRL + analyst-coverage/news counts. Three
faces of the resulting wall are on the record:

1. **Trailing-evidence at_inflection** — inflection is graded on what has already printed. RUN
   was rejected at_inflection=False on +0.65 12m momentum while the rationale itself cited
   ~+52% TTM revenue acceleration; CC (under_narrated=True) died the same way
   (`records/2026-07-07_preL1_two_slates_triage_fifth_bias_and_wall.md` — session-record
   provenance, stated in its header).
2. **Coverage-count under_narrated** — the count can't see qualitative under-narration (solar at
   22–31 analysts; TROX judged False at 8 — record #162).
3. **Evidence-channel** (KMT, record #162) — load-bearing evidence (input-commodity price, APT
   ~9×) sits outside the corpus entirely → a deliberated **proposer abstention**: the council
   cannot see the thesis driver at all.

The class that dies BY CONSTRUCTION: theses whose inflection is a **dated, public, forward
fact** — statutory step-downs/sunsets, dated program milestones, published input-cost shocks —
rather than a trailing print.

**The EV frame:** time arbitrage on council visibility. The nine-case consumption finding says
quiet names with print-legible drivers reprice within ~1–2 quarters; the current corpus lets the
council see drivers only *after* they are print-legible — structurally inside the consumption
window. The channel moves adjudicability pre-print, the only place this strategy's edge can live.

**Bounds, stated honestly (three, the first from batch-3):**

- **Floors-first:** the channel buys ADJUDICABILITY only for names already past the frozen
  floors/feasibility screen (OPAL/MNTK died at floors — channel-irrelevant). It cannot buy
  expression or immunity from the tape.
- **It does nothing about the largest killer on the record** — currency/tape consumption
  upstream of the council. The yield bottleneck may simply relocate upstream; if it does, that
  relocation IS the diagnostic (not a channel failure — measure it, don't bury it).
- **Realistic throughput is small:** converting perhaps 2–4 parked/staged names per quarter from
  unadjudicable to adjudicable. The channel feeds the include-criteria; it does not manufacture
  includes.

## §1 The principle — GROUND, NEVER PERMISSION

The §9 idiom, unchanged from `PREREG_EVIDENCE_GROUNDING` / `corpus:fundamentals_v1`: the channel
ADDS evidence to the council's `ContextPack`. It never scores, never gates, never admits, never
sizes. A channel-grounded candidate still needs the same §10.7 tri-criteria judgment, the same
IV gate, the same caps. Prompts stay sha-pinned and byte-identical — the channel rides the pack,
not the prompt (`tests/test_council_prompts.py` must hold unmodified).

## §2 Evidence classes (exhaustive; anything not listed is out)

Each item is a dated claim: `{claim, event_date, source (named public document/series), as_of
(when pinned), expires, provenance}`.

- **(a) Statutory/regulatory dated events** — a credit's first-print date, a sunset/step-down, a
  dated review. Instrument: the public legal text or register entry itself.
- **(b) Filed forward commitments — EXCLUDED from this channel (deliberate).** Backlog/RPO/
  take-or-pay lines are filed data: they have ONE home, the fundamentals corpus; extending that
  corpus to forward-dated XBRL tags is a future `fundamentals_v2` amendment, not this channel.
  (Two homes for filed lines invites drift; and print-legible filed lines sit in the nine-case
  consumption kill zone — the three-shapes doctrine and this channel stay consistent by keeping
  them out. The TROX realized-price triggers already work through the existing corpus when the
  prints land.)
- **(c) Dated program/procurement milestones** — e.g. state-level program construction starts
  (the CLFD/BEAD class). No mechanical source exists: items are operator-pinned with a named
  public announcement; the re-derivability bar is **citation-checkable**, not mechanically
  re-pullable.
- **(d) Published input-commodity prices** (the KMT/APT class) — **public-source fail-closed,
  per input:** an item may be pinned ONLY if a named, genuinely public, freely accessible series
  exists for that input, verified at pin time. Subscription assessments (e.g. Argus/Fastmarkets
  Rotterdam APT) do NOT qualify as the item's source. Stated plainly: for APT specifically a
  clean public series may not exist — in that case class (d) is simply unavailable for that
  input until the operator pins a public-print proxy (e.g. customs/export statistics or a
  competitor's filed print), and the KMT case waits on that or on its existing filed-print
  trigger (§9.5).

## §3 Source discipline

Point-in-time stamped; citation-checkable against the named public source; **no LLM-authored
facts** — items are operator-pinned or mechanically pulled, never model-generated (`generated`
provenance reserved, as in the §11 register). An item past `expires` drops from the pack —
stale forward claims are worse than none (never silently: §4 counters).

**Named deviation — dates are evidence tokens for this block.** The fundamentals authenticity
precedent (`fundamental_evidence_tokens`) deliberately excludes dates; here the date IS the
load-bearing figure. The filter extension must support date citations from the block (a
strategist citing "2027-01-01" must not flag as unsupported — the PR #55 lesson, recursively).
This asymmetry is intentional; a future symmetry-minded cleanup must not "fix" it back.

## §4 Council integration & telemetry

A bounded `forward_catalysts` block in `ContextPack` (the fundamentals_v1 shape): ≤K items per
candidate, each dated. Stamp `corpus:forward_catalyst_v1` into `runs.model_mix` — record-
segmenting, zero migration. Origin scope v0: **hand-seed + staged register candidates only**;
sentinel grounding stays byte-unchanged (the §6 framer leash holds).

**Anti-silent-dormancy counters (the event-leg precedent):** per cycle, `rendered_n / expired_n
/ malformed_n` for the block, stamped into `runs.note` telemetry. A "channel-grounded judgment"
for any denominator in this document means **the block actually rendered** — configured-but-
withheld never counts.

## §5 The behavior change — stated honestly

The block is **visible to all three roles** (verified: `debate.run_candidate` passes the pack to
`proposer_prompt`, `adversary_prompt`, and `strategist_prompt`; there is no per-criterion
visibility mechanism, and this document does not pretend one). The **design intent** is timing
evidence — informing `at_inflection` with dated forward facts — and F-c is the monitor for
leakage into `under_narrated`/`structural` adjudication. Because the proposer sees the pack
first, the channel also reaches the KMT face: a proposer that abstained for channel-blindness
(couldn't see the thesis driver) now deliberates with the driver in view. If the council reads
at_inflection=False *with the dated catalyst in view*, that is a judgment, not a wall — and it
stands.

**§5-read safety (asserted, not implied):** sentinel grounding is byte-unchanged in v0, so the
live sentinel council layer — the thing the §5 four-scan read measures — is untouched; this
document does not stale that read. Sentinel expansion of the channel is held until after the §5
read closes, for exactly this reason.

## §6 Forward-scoring the channel itself (never backtested — guardrail §6)

**The instrument is the paired contrast:** for each channel-grounded judgment among the first M,
an ephemeral no-channel re-score of the same candidate (block withheld, all else identical)
gives the counterfactual — surfaced to the operator, never auto-acted. **Ephemeral channel-
grounded re-scores count toward M** (the ~$0.09 probe pattern is the fastest path to the read;
the live L1 alone would starve the sample under the v0 origin scope). Rationale telemetry
records block presence + whether the rationale cites it.

**Catalyst-claim accuracy is tracked separately from trade Brier:** did the *event* occur as
pinned (deterministic, graded at `event_date`) vs did the *trade* pay (the existing Brier).
The first is nearly free and feeds F-b integrity directly.

**Dated backstop:** if M horizon-eligible paired contrasts have not accrued by the ~Sept §11
window, the scope is REVIEWED then (dated, on the record) — F-a is not left unfireable by
starvation.

## §7 Cost & kill

Bounded token add per pack (default +400 tokens/pack, pinned at freeze) **including the §6
paired-contrast spend for the first M** (≈2× council cost on channel names during the sample —
trivial in dollars at current rates, but the ledger is first-class, so it is in the bound
explicitly). Fail-soft: a missing/expired/malformed item never blocks a cycle — the block
degrades to absent (counted, §4). Kill-before-spend unchanged.

## §8 Falsifiers for the channel (it dies — or escalates — by its own rules)

**Horizon eligibility (the denominator for F-a):** a judgment counts only if the item's
`event_date` falls inside the trade-relevant horizon (within the 180–365d structure tenor of an
entry dated `as_of`). A distant-dated catalyst correctly read as not-now is out-of-sample — the
council working is not channel failure.

**F-a (adjudicability), instrument = §6 paired-contrast flip-rate over the first M=8
horizon-eligible pairs, THREE dispositions read from rationale text:**

- **(i) Inert:** rationales never cite the block → the channel failed as evidence delivery →
  **retire** (dated record).
- **(ii) Cited-but-not-now:** rationales cite the catalyst yet read not-now under the sha-pinned
  mandate wording ("the change is happening NOW") → the wall is the **mandate**, and the channel
  *worked* as evidence delivery. Pre-registered escalation (so this result is never misread as
  "forward catalysts are worthless" and buried): a **mandate-amendment pre-registration** — its
  own document, its own red-team, operator-gated, with the CGS §10.7 at_inflection wording as
  the object. Not retirement, and not a quiet prompt edit.
- **(iii) Flips:** the block flips `at_inflection` on ≥1 pair → the channel is earning its keep;
  continue accruing.

**F-b (integrity):** any item found non-re-derivable (per its class's §2 instrument), undated,
or LLM-authored → halt the channel same-day, audit all items, record before re-arm. The §6
catalyst-claim accuracy feed is the standing monitor.

**F-c (leniency leak):** include-rate rises without the includes citing the dated catalysts
(rationale check) → halt. The channel is grounding, not permission; a diffuse leniency shift is
the §5 failure mode — and the monitor for §5's visibility honesty (leakage into
under_narrated/structural adjudication).

## §9 Explicitly out of scope

Idea supply / thesis generation (the closed fork stays closed); any floor/gate/cap/mandate edit
(a mandate amendment can only arrive via F-a(ii)'s own pre-registration); any prompt edit;
sentinel grounding changes; admission mechanics; sizing. The register's §11 admission rule is
untouched — a channel-grounded name still enters only via a window or a §3 exception with the
operator's word.

## §9.5 Supersession on freeze (merge-inherits-nothing cuts both ways)

On freeze, §2(d) **amends the 2026-07-07 KMT re-entry pin** (record #162: "margin compression
appears in a filed print"): the park converts to a channel-grounded re-score candidate, dated —
**iff** a class-(d)-qualifying public source for the input exists at pin time (§2(d)'s
fail-closed rule). Absent that source, the original filed-print trigger stands unamended. No
other standing pin is touched.

## §10 Freeze & build process, and the open numbers

Operator red-team (per-section word, TRUE-form ratification — merge-inherits-nothing). Freeze =
merge of this document after that word. Build PRs only after freeze, each green before the next.

**Proposed defaults (anchors for ratification, not pins):** K=3 items/pack (fundamentals-block
scale) · M=8 horizon-eligible paired contrasts · token bound +400/pack · expiries — class (a):
`event_date` + 5 trading days; class (c): `event_date` + 5 trading days or superseded by a later
announcement; class (d): `as_of` + 7 days (mirroring `max_raw_age_days`).
