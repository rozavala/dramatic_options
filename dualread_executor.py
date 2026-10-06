"""The §5 dual-read tripwire RUNTIME executor (#72 / the 2026-07-10 close-out amendment).

The rolling wires were computed only at dashboard-read time; nothing executed the §5 response on
the live loop (issue #72). This module is the post-cycle hook that DOES — but it is built strictly
against the CONVERGED, split-by-breach-mechanism response table
(``records/2026-07-10_closeout_s5_amendment_DRAFT.md`` → ``PREREG_DATA_FEED_OPRA_SEQUENCING §5``):

  • **Single source of truth.** The Δ / material-flip / coverage-gap-partition math lives ONLY in
    ``dashboard_data.gate_dualread_report``. This module CONSUMES that report; it never re-derives a
    tripwire. (A test patches the report and asserts the executor's branch follows it.)

  • **Per-class response, never the old one-response-for-three.** Each wire routes to its own action:

      | wire / class           | response (this module)                                     |
      |------------------------|------------------------------------------------------------|
      | ``|Δ iv/rv|``          | the SOLE revert trigger → page (+ revert iff the flag is on)|
      | material cheap-flip    | investigate + page (debounced); **no revert**              |
      | gap · structural       | coverage-feasibility page (debounced); **no revert**       |
      | gap · entitlement      | feed-wide hold + ONE page/session; **no revert** (§7 holds) |
      | gap · transient        | log; per-name page only once it recurs to ≥2/5             |

  • **Phases.** Phase 1 (observe) computes the per-class verdict and LOGS it — no response. Phase 2
    (paging) executes the page paths with the ≥4-consecutive debounce. Phase 3 (the revert latch) is
    CODE-PRESENT but **gated behind ``config.data_feed.dualread_revert_enabled`` (DEFAULT false)** —
    inert on the live loop until an operator flips it. Only the Δ wire can ever write the override
    sentinel, and only with the flag true.

  • **Fail-soft + fail-loud.** The orchestrator wraps the whole call in try/except (a crash here must
    NOT halt a cycle whose entries already ran). Inside, a degraded read fails LOUD (a page), never
    silently — the #37 / build_event_provider discipline.

The override mechanism is a runtime SENTINEL FILE (``OPRA_REVERTED`` at repo root, the KILL-file
precedent): ``config_loader.load_config`` consults it AFTER reading ``config.json`` and forces
``option_gate='indicative'`` until an operator removes it (one-directional toward safety, idempotent,
record-segmenting — the next run's ``data_feed_stamp`` changes). See :data:`REVERT_SENTINEL`.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("dualread_executor")

# The runtime override sentinel (KILL-file precedent). Its PRESENCE forces option_gate→indicative on
# the next cycle (config_loader consults it). One-directional toward safety; the operator removes it
# to un-latch. Kept here as the single definition; config_loader imports this constant.
REVERT_SENTINEL = Path(__file__).resolve().parent / "OPRA_REVERTED"

DEBOUNCE_REARM = 4  # §5: ≥4 CONSECUTIVE clear sessions re-arm a look-once signal (derived from the
#                     rolling-5 — 4-in-a-row ⇒ ≤1 trip in the window, so a lift can't immediately
#                     re-trip; the implementation target is the consecutive count, NOT "rolling-5
#                     would no longer trip", which diverges on flickering names like UROY).
TRANSIENT_ESCALATE_MIN = 2  # a "transient" that recurs to ≥2/5 has falsified transient → per-name page


# ── the debounce (stateless, row-derived — NO table, NO migration) ───────────────────────────────

def rising_edge_page(tripped_seq: list[bool], *, rearm: int = DEBOUNCE_REARM) -> bool:
    """Should the LAST session in ``tripped_seq`` PAGE, under the §5 ≥``rearm``-consecutive debounce?

    ``tripped_seq`` is the per-session boolean history for ONE signal (oldest→newest), restricted to
    the sessions where the name was observable. Rising-edge: page when the signal newly trips; stay
    latched (suppressed) through trips AND through clear-runs shorter than ``rearm``; re-arm only after
    ``rearm`` consecutive clear sessions. This is the UROY pin: ``[absent,wing,wing,wing,absent]`` →
    page on the first absence, then the 3-wing run (<4) does NOT re-arm, so the second absence is
    suppressed (one continuous episode), never a nightly re-page."""
    alerted = False
    consec_clear = 0
    page_here = False
    for t in tripped_seq:
        if t:
            page_here = not alerted  # rising edge: page only on the transition into the tripped state
            alerted = True
            consec_clear = 0
        else:
            page_here = False
            consec_clear += 1
            if consec_clear >= rearm:
                alerted = False
    return page_here


def _rolling_escalated_seq(occ_seq: list[bool], min_count: int, *, window: int = 5) -> list[bool]:
    """Map a per-name OCCURRENCE history to a per-session ESCALATED-state history: position ``t`` is
    True iff the trailing-``window`` occurrence count through ``t`` is ≥ ``min_count``. Debouncing on
    THIS (not the raw occurrence) makes the per-name transient page fire on the rising edge of
    escalation (when ≥2/5 is first reached), not on the first blip."""
    return [sum(occ_seq[max(0, t - window + 1):t + 1]) >= min_count for t in range(len(occ_seq))]


def _name_in(sessions: list[dict], key: str) -> dict[str, list[bool]]:
    """Per-name tripped-history for a per-session list-of-names field (e.g. ``gap_structural``).
    A name's history covers only the sessions it APPEARS in that field's universe — but for a
    list-membership signal, absence-from-the-list IS the clear state, so we build the boolean over
    every session and let :func:`rising_edge_page` collapse it."""
    names: set[str] = set()
    for s in sessions:
        names.update(s.get(key, []) or [])
    return {name: [name in (s.get(key, []) or []) for s in sessions] for name in sorted(names)}


def _structural_history(sessions: list[dict]) -> dict[str, list[bool]]:
    """Per-name structural-absence history for the debounce. ``tripped`` = the name is structurally
    absent that session; ``clear`` = it has a durable OPRA wing (``opra_wing``) that session. Sessions
    where the name is NEITHER absent NOR winged (it wasn't in the universe / OPRA errored transiently)
    are SKIPPED — they neither page nor re-arm, so a flicker name's wing-run is counted faithfully."""
    names: set[str] = set()
    for s in sessions:
        names.update(s.get("gap_structural", []) or [])
    hist: dict[str, list[bool]] = {}
    for name in sorted(names):
        seq: list[bool] = []
        for s in sessions:
            absent = name in (s.get("gap_structural", []) or [])
            winged = name in (s.get("opra_wing", []) or [])
            if absent:
                seq.append(True)
            elif winged:
                seq.append(False)
            # else: not observable this session → contributes neither a trip nor a re-arm step
        hist[name] = seq
    return hist


# ── the verdict (pure — consumes the canonical report, derives the per-class actions) ────────────

def evaluate(report: dict, config: dict | None = None) -> dict:
    """Derive the §5 per-class verdict from the canonical ``gate_dualread_report`` output.

    Returns a structured verdict: the trip booleans (straight from the report — NOT re-derived), the
    debounced page sets per class, the entitlement feed-wide state, and whether a revert is AUTHORIZED
    (Δ-wire tripped AND ``dualread_revert_enabled`` true). Pure: no I/O, no paging, no sentinel write —
    the caller disposes. ``config`` supplies only the revert flag."""
    tw = report.get("tripwires", {}) or {}
    gp = report.get("gap_partition", {}) or {}
    sessions = report.get("sessions", []) or []
    revert_enabled = bool(((config or {}).get("data_feed", {}) or {}).get("dualread_revert_enabled", False))

    # The Δ wire — the SOLE revert trigger (the report owns the threshold math).
    delta_tripped = bool(tw.get("delta_tripped"))

    # Material cheap-flip — investigate + page, debounced, NEVER revert.
    flip_hist = _name_in(sessions, "material_flips")
    flip_pages = sorted(name for name, seq in flip_hist.items() if seq and rising_edge_page(seq))
    flip_tripped = bool(tw.get("flip_tripped"))

    # Coverage-gap · structural absence — feasibility page, debounced, NEVER revert.
    struct_hist = _structural_history(sessions)
    structural_pages = sorted(name for name, seq in struct_hist.items() if seq and rising_edge_page(seq))
    structural_tripped = bool(gp.get("structural_tripped"))

    # Coverage-gap · transient — per-name page only once a name's own transient sessions reach ≥2/5
    # (a transient that recurs has falsified "transient"). The DEBOUNCE is on the ESCALATED STATE (the
    # rolling-5 ≥ min), not the raw occurrence: page on the rising edge of escalation, suppress while
    # it stays escalated, so a parked flaky name doesn't re-page nightly.
    trans_hist = _name_in(sessions, "gap_transient")
    transient_pages = sorted(
        name for name, seq in trans_hist.items()
        if rising_edge_page(_rolling_escalated_seq(seq, TRANSIENT_ESCALATE_MIN))
    )

    # Coverage-gap · entitlement — feed-wide, per-session, NEVER debounced, NEVER revert (§7 holds).
    entitlement_active = bool(gp.get("entitlement_active"))

    return {
        "delta": {"tripped": delta_tripped, "revert_authorized": delta_tripped and revert_enabled,
                  "revert_enabled": revert_enabled},
        "material_flip": {"tripped": flip_tripped, "pages": flip_pages},
        "gap_structural": {"tripped": structural_tripped, "pages": structural_pages},
        "gap_transient": {"pages": transient_pages},
        "entitlement": {"active": entitlement_active},
        "tripwires": tw, "gap_partition": gp,
    }


# ── disposition (the side-effecting layer — paging + the gated revert) ───────────────────────────

def _page(notify, title: str, message: str, *, priority: int = 0) -> None:
    """Page via the injected notifier; ``notify.send`` already never raises, but belt-and-braces."""
    try:
        notify.send(title, message, priority=priority)
    except Exception:  # noqa: BLE001 — paging is best-effort; never break the hook
        log.warning("dual-read page failed to send: %s", title)


def run_executor(report: dict, config: dict, *, notify, write_sentinel=None) -> dict:
    """Phases 1–3 over the canonical report. Returns the verdict (also logged). PURE of cycle state —
    the orchestrator passes the report + config + the notifier; ``write_sentinel`` (Phase 3) defaults
    to the real sentinel writer but is injectable for tests.

    Phase 1 (observe): always — compute + LOG the per-class verdict.
    Phase 2 (page): always — the debounced page paths.
    Phase 3 (revert): only when ``dualread_revert_enabled`` is true AND the Δ wire tripped → write the
    override sentinel (next cycle's gate feed → indicative). Default-false ⇒ inert on the live loop."""
    verdict = evaluate(report, config)

    # ── Phase 1: observe (LOG the verdict, every run) ──
    log.info(
        "dual-read §5 verdict: delta_tripped=%s flip_tripped=%s structural_tripped=%s "
        "entitlement_active=%s revert_enabled=%s",
        verdict["delta"]["tripped"], verdict["material_flip"]["tripped"],
        verdict["gap_structural"]["tripped"], verdict["entitlement"]["active"],
        verdict["delta"]["revert_enabled"],
    )

    # ── Phase 2: paging (debounced; the entitlement state is NEVER debounced) ──
    if verdict["entitlement"]["active"]:
        # Feed-wide OPRA-trust failure → one page/session while down; §7's inline per-name entry-veto
        # is the entry backstop. HOLD-visibility, never a silent downgrade (and never a revert).
        _page(notify, "OPRA dual-read: entitlement lapse (feed-wide)",
              "An OPRA fetch was refused for subscription/permission reasons during the §5 sweep. "
              "The gate fails closed per name (§7 veto); holding option_gate=opra — no silent "
              "downgrade. Investigate the OPRA entitlement.", priority=1)

    if verdict["delta"]["tripped"]:
        action = "reverting option_gate→indicative" if verdict["delta"]["revert_authorized"] \
            else "investigate (revert latch OFF — no auto-revert)"
        _page(notify, "OPRA dual-read: |Δ iv/rv| wire TRIPPED",
              f"The OPRA/INDICATIVE iv_rv disagreement breached the rolling-5 wire "
              f"(the sole revert trigger). {action}.", priority=1)

    for name in verdict["material_flip"]["pages"]:
        _page(notify, "OPRA dual-read: material cheap-flip — investigate",
              f"{name}: OPRA and INDICATIVE disagree on `cheap` on an existing wing "
              f"(|Δ iv/rv| ≥ floor), recurring on the rolling-5. Investigate; no revert.")

    for name in verdict["gap_structural"]["pages"]:
        _page(notify, "OPRA dual-read: coverage-feasibility",
              f"{name}: OPRA has no tradeable wing in the tenor window across the rolling-5 "
              f"(structural absence — OPRA-correct). The gate fail-closes it; the name stays in the "
              f"basket (PREREG_UNIVERSE_CURATION §3). No revert. Review feasibility.")

    for name in verdict["gap_transient"]["pages"]:
        _page(notify, "OPRA dual-read: transient gap escalation",
              f"{name}: a 'transient' OPRA fetch gap recurred to ≥{TRANSIENT_ESCALATE_MIN}/5 — it has "
              f"falsified 'transient'. Per-name page (no feed-wide hold, no revert). Check this chain.")

    # ── Phase 3: the revert latch (CODE-PRESENT, DEFAULT-OFF) ──
    # SAFETY INVARIANT: only the Δ wire writes the sentinel, and only with the flag true. A structural
    # or entitlement trip NEVER writes it (reverting would restore phantom coverage the gate correctly
    # refuses / silently downgrade a held feed). evaluate() encodes this in revert_authorized.
    if verdict["delta"]["revert_authorized"]:
        writer = write_sentinel if write_sentinel is not None else write_revert_sentinel
        try:
            writer("|Δ iv/rv| wire tripped — §5 revert (operator-enabled)")
            verdict["revert_written"] = True
            _page(notify, "OPRA dual-read: REVERTED to indicative",
                  "The override sentinel OPRA_REVERTED was written — the next cycle's option_gate is "
                  "forced indicative. Remove the sentinel to un-latch (operator action).", priority=1)
        except Exception as e:  # noqa: BLE001 — a failed sentinel write must fail LOUD, not halt
            verdict["revert_written"] = False
            log.error("dual-read REVERT sentinel write FAILED (gate NOT reverted): %s", e)
            _page(notify, "OPRA dual-read: revert FAILED to latch",
                  f"The Δ wire tripped with the latch ON but writing OPRA_REVERTED failed: {e}. "
                  f"option_gate is UNCHANGED — investigate immediately.", priority=1)
    else:
        verdict["revert_written"] = False

    return verdict


def write_revert_sentinel(reason: str) -> None:
    """Write the ``OPRA_REVERTED`` override sentinel (Phase 3). Idempotent — overwrites with the
    latest reason/timestamp. Its presence forces option_gate→indicative on the next cycle."""
    from datetime import datetime

    REVERT_SENTINEL.write_text(
        f"{datetime.now().astimezone().isoformat()}\n{reason}\n"
        "Remove this file to restore option_gate=opra (operator un-latch).\n"
    )


def revert_latched() -> bool:
    """True iff the ``OPRA_REVERTED`` override sentinel is present (config_loader consults this)."""
    return REVERT_SENTINEL.exists()
