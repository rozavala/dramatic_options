# PREREG — Forward-Catalyst Grounding Channel

**STATUS: FROZEN v3.1 (2026-07-09, PR #167 merge = the freeze act).** Ratification (informed
delegation, TRUE form) + the §9.5 verification (outcome: NO qualifying public APT series — the
KMT filed-print pin stands) are recorded in `records/2026-07-09_channel_prereg_freeze.md`.
Changes from here are dated §-amendments only. The build was separately authorized by the
operator's fresh go 2026-07-09 (this correction rides the first build PR — administrative
status-line fix only; no §-content change).

## §0.5 Revision log

- **v3.1 (2026-07-09):** advisor round 4 closed with **zero P1s and zero P2s** ("ratification-
  ready"); the three optional P3s folded in pre-freeze since one touches the pinned rule:
  (iii)-pins-the-floor clause (a lone flip never vetoes a strong cited-not-now signal — the
  operator may open the (ii) pre-registration discretionarily, dated, even under (iii));
  `reverse_conversion_n` counter (the one channel-HARM signature — deliberation→abstention —
  now visible in telemetry, no rule effect); cite-token distinctiveness pinned as a build
  requirement (full ISO dates / multi-digit figures, bare years excluded — a false-positive
  cite misroute is bounded by (ii) being operator-gated, but the build must not invite it).
- **v3 (2026-07-09):** advisor red-team round 3 — a surgical §8 pass (the advisor ratified
  §0–§7 and §9–§10 as stable across two rounds; only §8 + one §9.5 clause changed). The blocker:
  v2's flip definition (at_inflection value change only) and disposition semantics collided with
  the round-2 eligibility split — the KMT-class pair (abstention → deliberation) could never
  register as a flip, and a class-(d) cites-but-False pair misrouted to the mandate escalation
  (a cost shock IS "now"; a False read on it is the council answering, not a mandate wall).
  Fixed: flip := at_inflection value change ∨ abstention→deliberation conversion; disposition
  (ii) restricted to (a)/(c) pairs. Also: "cites" OPERATIONALIZED (block-derived token present
  in rationale, the §3 tokenizer — ONE detector shared by F-a and F-c, closing the drift);
  class-(d) eligibility restated as "rendered" (freshness is enforced upstream by §3 expiry —
  the v2 wording was a tautology); the single-sample-noise honesty line added (flips≥1 is a
  survival read, value is proven downstream); §9.5 given an owner and a date (the operator
  verifies the public-source iff as part of the freeze act).
- **v2 (2026-07-09):** advisor red-team round 2. The one blocker was a **v1-introduced
  regression**: v1's horizon-eligibility rule (event_date inside the forward tenor) structurally
  blinded F-a to class (d) — the KMT case §0 leads with has no forward event date (the shock
  already printed; the forward content is the undated flow-through). Fixed by per-class
  eligibility (§8) + a nullable `event_date` for class (d) (§2). Also: eligibility lower bound
  corrected to 0 (v1's "inside 180–365d" excluded near-dated catalysts — the most
  at-inflection-now case); the F-a decision rule at M pinned MECHANICAL (precedence, no
  texture-reading); §7 split into two bounds (tokens vs dollars — v1 carried a category error);
  F-c's v0 dormancy stated; the F-a(iii)→profitability handoff added (segmented by the corpus
  stamp, never pooled); §5 symbols re-verified against the live tree with line numbers; the
  §0/§0.5 citation mismatch aligned; the class-(d)-proxy vs class-(b)-exclusion distinguishing
  clause added; item re-verification cadence pinned.
- **v1 (2026-07-09):** advisor round 1 — all four P1s + P2 pins + P3 hygiene (§5 honest
  pack-wide visibility; §9.5 KMT supersession; F-a horizon-eligible paired-contrast flip-rate;
  F-a tri-disposition incl. the pre-registered mandate-amendment escalation; class (b) excluded;
  class (d) public-source fail-closed; counters; date-token deviation; §5-read-safety;
  catalyst-claim accuracy split; solar citation repaired to a committed record).
- v0 (2026-07-08): initial skeleton.

## §0 Why — the located wall this addresses (and what it cannot buy)

The council's grounding corpus is markers + filed XBRL + analyst-coverage/news counts. Three
faces of the resulting wall are on the record:

1. **Trailing-evidence at_inflection** — inflection is graded on what has already printed. RUN
   was rejected at_inflection=False on +0.65 12m momentum while the rationale itself cited
   ~+52% TTM revenue acceleration; CC (under_narrated=True) died the same way
   (`records/2026-07-07_preL1_two_slates_triage_fifth_bias_and_wall.md`, committed via PR #168 —
   session-record provenance, stated in its header).
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
(when pinned), expires, provenance}`. **`event_date` is REQUIRED for classes (a)/(c) and NULL
for class (d)** — a published cost shock is current-state evidence with no forward date; forcing
a fictitious one (the print date, the next earnings date) would be instrument-shaped data entry,
exactly what F-b exists to catch. For class (d), `as_of`/`expires` carry the temporal discipline.

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
  trigger (§9.5). **Proxy clause (keeps the (b) exclusion clean):** a filed print qualifies as a
  class-(d) proxy only as evidence about the INPUT (the commodity's realized price/cost), never
  as the candidate's own forward-commitment line — (b) excludes the candidate's filed forward
  book; (d) admits third-party prints about the input's price. A future reader must not see (b)
  re-entering through (d).

## §3 Source discipline

Point-in-time stamped; citation-checkable against the named public source; **no LLM-authored
facts** — items are operator-pinned or mechanically pulled, never model-generated (`generated`
provenance reserved, as in the §11 register). An item past `expires` drops from the pack —
stale forward claims are worse than none (never silently: §4 counters).

**Re-verification cadence (pinned — silence is not an option between pin and expiry):** an item
whose `as_of` is older than **N=30 days** at render is flagged for operator re-verification
(counter + `runs.note`, §4) — it still renders (fail-soft) but the flag is the standing check
that a statute wasn't repealed or a milestone re-dated between pin time and `event_date`. F-b
remains the backstop for anything the flag misses.

**Named deviation — dates are evidence tokens for this block.** The fundamentals authenticity
precedent (`fundamental_evidence_tokens`) deliberately excludes dates; here the date IS the
load-bearing figure. The filter extension must support date citations from the block (a
strategist citing "2027-01-01" must not flag as unsupported — the PR #55 lesson, recursively).
This asymmetry is intentional; a future symmetry-minded cleanup must not "fix" it back.

## §4 Council integration & telemetry

A bounded `forward_catalysts` block in `ContextPack` (the fundamentals_v1 shape): ≤K items per
candidate, each dated per the §2 schema. Stamp `corpus:forward_catalyst_v1` into
`runs.model_mix` — record-segmenting, zero migration. Origin scope v0: **hand-seed + staged
register candidates only**; sentinel grounding stays byte-unchanged (the §6 framer leash holds).

**Anti-silent-dormancy counters (the event-leg precedent):** per cycle, `rendered_n / expired_n
/ malformed_n / stale_flagged_n / reverse_conversion_n` for the block, stamped into `runs.note`
telemetry (`reverse_conversion_n` — §8's flip detector, reverse direction — is telemetry only,
never a rule input). A
"channel-grounded judgment" for any denominator in this document means **the block actually
rendered** — configured-but-withheld never counts.

## §5 The behavior change — stated honestly

The block is **visible to all three roles**. Mechanism verified against the live tree
2026-07-09: the live path is `council.wiring.council_to_themes` → `council.council.propose`
(council.py:93) → `council.debate.run_candidate` (council.py:129 → debate.py:67), which passes
the pack to `agents.proposer_prompt(pack)` (agents.py:107), `agents.adversary_prompt(pack, …)`
(agents.py:111), and `agents.strategist_prompt(pack, …)` (agents.py:123). There is no
per-criterion visibility mechanism, and this document does not pretend one. The **design
intent** is timing evidence — informing `at_inflection` with dated forward facts — and F-c is
the monitor for leakage into `under_narrated`/`structural` adjudication. Because the proposer
sees the pack first, the channel also reaches the KMT face: a proposer that abstained for
channel-blindness (couldn't see the thesis driver) now deliberates with the driver in view. If
the council reads at_inflection=False *with the dated catalyst in view*, that is a judgment,
not a wall — and it stands.

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
pinned (deterministic, graded at `event_date` for (a)/(c); for (d), was the print authentic and
in-force at render) vs did the *trade* pay (the existing Brier). The first is nearly free and
feeds F-b integrity directly.

**Dated backstop:** if M eligible paired contrasts have not accrued by the ~Sept §11 window,
the scope is REVIEWED then (dated, on the record) — F-a is not left unfireable by starvation.

## §7 Cost & kill — two bounds, two ledger lines

1. **Pack token bound:** the `forward_catalysts` block adds ≤ **400 tokens** per pack (pinned at
   freeze).
2. **Sample dollar bound:** during the M-sample, per-name deliberation spend on channel-grounded
   candidates ≤ **2× baseline** (the §6 paired contrast is the 2nd deliberation) — a ledger
   line, not a token property. Trivial in dollars at current rates, but the cost ledger is
   first-class, so it is pinned as its own line.

Fail-soft: a missing/expired/malformed item never blocks a cycle — the block degrades to absent
(counted, §4). Kill-before-spend unchanged.

## §8 Falsifiers for the channel (it dies — or escalates — by its own rules)

**Eligibility (the F-a denominator), PER CLASS — a judgment counts iff the block rendered (§4)
and:**

- **Classes (a)/(c) (forward-dated):** `0 < event_date − as_of ≤ 365d` — or ≤ the selected
  structure's expiry when a structure exists at judgment time. The lower bound is ZERO: a
  near-dated catalyst is the most at-inflection-now case the channel can carry (v1's "inside
  180–365d" wrongly excluded it). A catalyst beyond the horizon correctly read as not-now is
  out-of-sample — the council working is not channel failure.
- **Class (d) (current-state):** eligible iff **rendered** — freshness is enforced upstream by
  §3 expiry (an expired item never renders), so a rendered class-(d) item is fresh by
  construction; there is no separate eligibility filter to hunt for. A published cost shock is
  by definition "now"; class (d) carries no forward date (§2 schema). (Without this split, F-a
  would be structurally blind to the KMT case — face #3, the one §0 leads with.)

**The two pinned detectors (both mechanical — no textual judgment at resolution):**

- **flip** := (`at_inflection` changes value between the arms) **∨** (**proposer abstention in
  the no-channel arm ∧ a deliberated tri-criteria judgment in the channel arm**). The second
  disjunct is F-a's own name: converting an unadjudicable name into an adjudicated one IS
  adjudicability, regardless of the verdict's sign — the KMT-class contrast (abstention →
  deliberation) registers here, not as a boolean change.
- **cite** := ≥1 **block-derived token** present in the rationale text — the item's dates and
  figures, detected by the same tokenizer the §3 authenticity-filter extension carries. This ONE
  detector serves both F-a's cite-count and F-c's "includes citing the dated catalysts" — two
  informal rationale-checks would drift apart; one definition cannot. **Build requirement
  (token distinctiveness):** the cite set uses distinctive tokens only — full ISO dates and
  multi-digit figures; bare years ("2026") and small integers are EXCLUDED (a false-positive
  cite on an (a)/(c) pair would misroute (i)→(ii); the consequence is bounded — (ii) is
  operator-gated with its own red-team — but the build must not invite it).

**Completeness note (telemetry only):** the flip detector is one-directional by design; the
reverse conversion — deliberation in the no-channel arm ∧ abstention in the CHANNEL arm (the
block confusing rather than grounding a proposer) — is the one channel-HARM signature a flip
count can't see. It is counted (`reverse_conversion_n`, §4) so the F-a record is complete in
both directions; it changes no rule.

**F-a (adjudicability), instrument = §6 paired-contrast flip-rate over the first M=8 eligible
pairs. The decision rule at M is MECHANICAL (pinned now, no texture-reading after the data):**

- **flips ≥ 1 → (iii) continue** — the channel is earning its keep (adjudicability). Stated
  honestly: each arm is one LLM sample, so a lone flip in 8 pairs can be sampling noise —
  flips ≥ 1 is a **survival** read (F-a screens for inertness), corrected downstream by the
  segmented Brier/outcome record; it is not evidence of value. **(iii) pins the FLOOR, not a
  ceiling:** the dispositions are mutually exclusive by precedence but the underlying states
  are not — the channel can be earning its keep while the mandate is a wall for the
  forward-dated subset (e.g. 1 flip + 6 cited-not-now (a)/(c) pairs). On a high cited-not-now
  (a)/(c) count under (iii), the operator MAY open the (ii) pre-registration as a
  discretionary, dated act; the mechanical rule never blocks that door — it only guarantees
  the floor disposition fires without interpretation;
- **flips = 0 ∧ cites ≥ 1 on (a)/(c) pairs → (ii) mandate escalation** — rationales cite a
  forward-dated catalyst yet read not-now under the sha-pinned wording ("the change is
  happening NOW"): the wall is the **mandate** and the channel *worked* as evidence delivery.
  **Disposition (ii) is restricted to classes (a)/(c)** — the cites-but-not-now diagnosis
  requires a forward `event_date` for the wording to conflict with; a class-(d) cost shock IS
  happening now, so a cited-but-False class-(d) pair is the council answering the question, not
  a mandate wall (those pairs accrue to the denominator as judgments; abstention-conversions
  among them already count as flips under the first detector). Pre-registered escalation (so
  this result is never misread as "forward catalysts are worthless" and buried): a
  **mandate-amendment pre-registration** — its own document, its own red-team, operator-gated,
  with the CGS §10.7 at_inflection wording as the object. Not retirement, and not a quiet
  prompt edit;
- **flips = 0 ∧ no (a)/(c) pair with cites ≥ 1 → (i) retire** — the channel failed as evidence
  delivery (dated record). This is also the honest read when the sample is all class-(d)
  judgments with zero flips of either kind.

**F-a(iii) proves causation, not value — the profitability handoff:** channel-flipped judgments
are graded on the segmented forward record (Brier + realized outcome), segmented by the
`corpus:forward_catalyst_v1` stamp and **never pooled with unflipped judgments**. Adjudicability
earned ≠ P&L earned; the stamp makes the second read free, and it is the read that matters.

**F-b (integrity):** any item found non-re-derivable (per its class's §2 instrument), undated
where its class requires a date, or LLM-authored → halt the channel same-day, audit all items,
record before re-arm. The §6 catalyst-claim accuracy feed + the §3 staleness flag are the
standing monitors.

**F-c (leniency leak):** include-rate rises without the includes citing the dated catalysts
(the pinned **cite** detector above — the same tokenizer, never a second informal check) →
halt. The channel is grounding, not permission; a diffuse leniency shift is
the §5 failure mode — and the monitor for §5's visibility honesty (leakage into
under_narrated/structural adjudication). **Stated plainly: F-c is near-dormant under the v0
scope** — ephemeral probes (which dominate the M sample) cannot produce includes, and active
hand-seeds are ~1, so F-c reads live channel-grounded judgments only. It becomes a live guard
at sentinel expansion (post-§5-read); until then it is a standing rule with a small population,
not an active tripwire.

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
fail-closed rule). **The iff has an owner and a date: the OPERATOR performs that verification
as part of the freeze act** (does a genuinely public APT proxy series exist — e.g.
customs/export statistics — yes or no, recorded with the freeze), so it resolves at freeze,
never lazily later. Absent that source, the original filed-print trigger stands unamended. No
other standing pin is touched.

## §10 Freeze & build process, and the open numbers

Operator red-team (per-section word, TRUE-form ratification — merge-inherits-nothing). Freeze =
merge of this document after that word. Build PRs only after freeze, each green before the next.

**Proposed defaults (anchors for ratification, not pins):** K=3 items/pack (fundamentals-block
scale) · M=8 eligible paired contrasts · pack token bound +400 · sample dollar bound 2×
baseline · staleness flag N=30d · expiries — class (a): `event_date` + 5 trading days; class
(c): `event_date` + 5 trading days or superseded by a later announcement; class (d): `as_of` +
7 days (mirroring `max_raw_age_days`).
