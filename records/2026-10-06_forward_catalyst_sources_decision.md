# 2026-10-06 — Forward-catalyst sources: FDA deferred, DoD declined, Federal Register pin suggestions adopted

**Operator's word (2026-10-06):** *"Sure, merge it and let's follow your recommendations"*, on CC's
recommendation for the charter §3b source proposals carried since the 2026-09-24 catalyst shortlist.

## Decision
| Proposal | Decision | Why |
|---|---|---|
| **FDA calendar** (advisory-committee meetings / PDUFA) | **DEFERRED** | Forward-dated and citable, but the universe holds one pharma name (MRK, `mrna_oncology`). Revisit when ≥ 2 biotech/pharma names are admitted. |
| **DoD contract announcements** | **DECLINED** | They announce awards already made, not future dates, so they don't fit the forward-dated class (a)/(c) shape. The names they would touch (LMT/NOC/LHX/RTX/KTOS) are among the most heavily covered in the universe. |
| **Federal Register effective-date pin SUGGESTIONS** | **ADOPTED** | `scripts/catalyst_pin_suggestions.py` (details below). |

How the Federal Register suggestions work:
- **Sources:** the digest's existing agency list (NRC, DOE, FERC, EPA, FCC, NTIA, FAA, USDA, IRS). No new channel.
- **What is listed:** final rules published in the last 14 days whose effective date is still ahead, and whose
  title or abstract literally names a basket keyword.
- **Noise control:** routine rule classes (airworthiness directives, state implementation plans, airspace,
  marketing orders) are dropped by title and counted.
- **Origin:** this formalizes the hand read that produced the first class-(a) pin (EPA FR 2026-19071).

## Discipline
- **Suggestions only.** Nothing is pinned, scored or ranked; rows sort by effective date. The operator reads each
  rule and pins in `forward_catalysts.json`, with the FR document as the citable source, or skips. The pin
  remains the operator's act (channel §3).
- **The basket tag is the literal keyword hit:** a routing hint, never a relevance claim.
- **Not a list that needs ranking.** The first unfiltered dry run listed every rule from every agency (36
  routine + 13 off-topic in 30 days). That is the "requires ranking to be useful" failure the reach charter
  forbids, so the keyword + routine-class rules are part of the design, and both skips are printed.
- **Read-only:** the keyless public Federal Register API; no DB, no keys. It writes only an optional records .md.

## First run (dry, 2026-10-06, 30-day lookback)
Three suggestions survived the filters:
- **NRC 2026-19963**, "NRC Modernization", effective 2026-10-26: procedural.
- **EPA 2026-19071**, effective 2026-11-16: **already pinned**, correctly marked.
- **NRC 2026-20336**, "Exemptions From Materials Licensing", effective 2026-12-21.

The first finding is that the existing pin is reproduced. Neither NRC rule is proposed for pinning: both are
procedural or licensing housekeeping with no inflection claim.

## Cadence
Run in the Sunday review beside the L0/digest reads. The table goes into the week's records PR.
