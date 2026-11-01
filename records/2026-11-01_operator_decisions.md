# 2026-11-01 — Operator decisions on the W44 pending items

## Provenance

**Operator word (2026-11-01):** "Ok, let's follow your seuggestions. Can you help me implement?" It was given on
the recommendations CC presented the same day, in answer to "What would you suggest to do on the pending items?",
after the W44 Sunday review (`records/2026-11-01_sunday_w44.md`, PR #406). The table quotes each recommendation.

| # | recommendation (as presented) | decision | where it lives |
|---|---|---|---|
| 1 | "Merge PR #406 when you're back." | **The operator's merge**, unchanged. This record and the STANDING_STATE edits below ride on the same PR. | PR #406 |
| 2 | "Move the 11-05 model refresh back about a week, to around 11-12." | **MOVED to ~2026-11-12.** §10.11 began 10-30 and the ISO-date filter (#403) begins 11-02. A 11-05 swap would land at about session 5 of §10.11's 10-session floor-drought clock and confound it. The ~11-03 shadow check (parse rate, cost, latency; no outcome scoring) is unchanged. | STANDING_STATE docket |
| 3 | "Let the KMT pin expire on 11-08 instead of renewing it every week." | **RETIRED at expiry.** KMT pin #19 (`as_of` 2026-11-01) runs to 2026-11-08 and is **not re-pinned**. The 11-08 Sunday run reports the expiry and leaves the item to lapse. | STANDING_STATE rulings; `scripts/ops/prompts/sunday_review.md` §4 |
| 4 | "Don't pin the NRC reactor-design rule (2026-21801)." | **REVIEWED, NOT PINNED.** It drops off the staged list. | STANDING_STATE |
| 5 | "Fix the PROD journal access (small, your step)." | **PENDING the operator's step on PROD** (sudo). Until the step is done, the Sunday review reports PROD's `status=9` check as *unreadable*, never as 0. | STANDING_STATE staged; `scripts/ops/prompts/sunday_review.md` §9 |
| 6 | "BNTX: no action." | **No action.** | — |
| 7 | "The May-2027 cutoff (~11-23): check it next Sunday." | **Checked today instead** (see below). It stays on the docket with the 11-23 listing check named. | STANDING_STATE docket |
| 8 | "The BWXT headline the homonym guard dropped: no issue yet." | **No issue.** File one only if a universe name loses a real headline to the guard again. | — |

## Why #3: the pin never reached a council

Every nightly grade from 10-26 to 10-30 logged `Fwd catalysts rendered=1 (CEG/EPA)`. KMT is neither a universe name
nor a sentinel, so pin #19 rendered into no prompt. The pin itself records that the July print contradicts its cost
thesis. KMT is also expression-dead (bench Tier B: −27.5% ITM at tenor). The weekly Comtrade check and re-pin produced
no input to any decision. If tungsten is worth watching, record it in a dated record, not as a live pin.

## Why #4: a weak catalyst on no expressible name

- **Procedural.** 2026-21801 lets applicants use a prior DOE/DoW demonstration-reactor authorization in NRC
  licensing. It does not move a name's demand or filed figures inside a 6–12-month horizon.
- **No name to carry it.** Its plausible names are NNE (no structure) and BWXT. BWXT's live lineage is bearish, so a
  tailwind pinned to it would more likely confuse the council than inform it.
- **Short life.** Effective 2026-11-25; the pin would expire about a week later.
- **The precedent shows nothing new to learn.** The EPA pin has been read as irrelevant 17 times running. That shows
  the F-c guard holds, not that more pins of this kind add information.

## #5: the step (operator, on PROD)

The review user on PROD (`console`) is not in a journal-reading group. `journalctl -u 'dramatic-options-*'` returns
"Failed to add filter for units: No data available", so this week's PROD `status=9` count was never actually read.

```bash
# on all-options-prod, as the operator
sudo usermod -aG systemd-journal console
# takes effect on the next login; verify from DEV:
ssh all-options-prod 'id -nG; journalctl -u dramatic-options-l2 -n 1 --no-pager -q'
```

The group grants read-only journal access. Once it is in place, change the STANDING_STATE staged item to done.

## #7: the May-2027 check (live OPRA, read 2026-11-01)

May-2027 (201 d today) falls under the gate's 180-day floor on **Mon 2026-11-23**. That is also the first session
after the November monthly expires (Fri 11-20), when a new quarterly would normally list. Expiries in or near the
window for the twelve names that select a May-2027 wing:

| name | after May-2027 | gap if no new listing |
|---|---|---|
| SMCI | Jun-2027 (228 d), Sep-2027, Dec-2027 | none |
| KLAR | Jun-2027, Aug-2027, Nov-2027 | none |
| NXE | Aug-2027 (292 d), Nov-2027 | none |
| FRO | Jul-2027 (257 d) | none (the July chain failed the spread cap on 10-28) |
| KTOS | Dec-2027 (411 d) | 11-23 → **~12-17**, when Dec-2027 enters 365 d |
| LHX · UEC · SMR · BWXT · FLNC · RDW · FLY | Jan-2028 (446 d) only | 11-23 → **~2027-01-21**, when Jan-2028 enters 365 d |

- **If no August-2027 quarterly lists on 11-23, eight names lose structure that day.** Expressible would fall from
  39 to about 31 (before any spread-cap flicker).
- That is plausible. The January-cycle names got no July-2027 listing after the October monthly expired (W43–W44),
  so the same could happen to the February-cycle names.
- Only the slate and the expressible count are affected. The gate fails closed on a name without structure, and
  Expressible-first holds those names off the council.
- **Read on Mon 11-23:** which of the eight list Aug-2027, and the nightly `record_ok`.
