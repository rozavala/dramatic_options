"""READ-ONLY report for the #456 council repeat-read probe (PREREG_COUNCIL_GATE_SEPARATION §10.12;
records/2026-11-14_council_repeat_probe_armA_PREREG.md §6). The thin CLI is ``scripts/probe_repeat_report.py``.

On final (post-filter) convictions, per session and pooled over the segment, for each binary item —
``structural`` (structural_vs_fad == "structural"), ``under_narrated`` (is True), ``at_inflection`` (is True),
``include`` and ``floor`` (conviction ≥ MODERATE):
- agreement: the share of a name's counted repeats equal to the verdict of record, averaged over names;
- majority match: whether the verdict of record equals the strict majority of the counted repeats;
- Fleiss' kappa among the repeats (raters = a name's counted repeats, subjects = name-sessions).

Then the two pre-stated reads (PINNED in the prereg):
- **Read 1 (entry):** floor-contact names (record ≥ floor, or ≥ 1 counted repeat ≥ floor). Evaluable with ≥ 5;
  if fewer than 70% have the record's ≥floor equal to the repeat majority ⇒ "look owed"; else "no trigger".
- **Read 2 (include):** pooled over all probed name-sessions. Evaluable with ≥ 30; majority match < 80% ⇒ a lone
  include=false read is not treated as reversing an entry.

Definitions this module had to fix (the prereg is silent; stated in the output):
- **Counted repeats** are those with ``excluded_reason IS NULL`` (understudy / parse_error / provider_error left out,
  reported by reason). A name-session with zero counted repeats is not "probed" and enters no statistic.
- **Majority** is strict (> half of the counted repeats). A tie (possible only when an exclusion leaves an even count)
  has NO majority, so the record cannot equal it: it counts as a non-match, and ties are reported.
- **Fleiss' kappa** uses the variable-rater form (each subject's own n_i ≥ 2; subjects with n_i < 2 are left out), so
  exclusions do not drop a whole name. It is None when undefined (no subjects, or every rating the same: P_e = 1).
  The record is NOT a rater: kappa measures the repeats' agreement among themselves.

Measurement only (prereg §8): never selects, sizes, holds or exits; never compared with prices or outcomes.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from council.proposal import passes_floor

FLOOR = "MODERATE"
ITEMS = ("structural", "under_narrated", "at_inflection", "include", "floor")
READ1_MIN_NAMES = 5
READ1_TRIGGER = 0.70
READ2_MIN_NAMES = 30
READ2_TRIGGER = 0.80
PREVALENCE_CAVEAT = ("'floor' (conviction >= MODERATE) is rare (3 of 240 proposals 10-19 → 11-13), so its kappa is "
                     "unstable: with prevalence near 0, P_e is near 1 and a single disagreement swings kappa widely.")


@dataclass(frozen=True)
class Verdict:
    """One verdict's five binary items."""

    structural: bool
    under_narrated: bool
    at_inflection: bool
    include: bool
    floor: bool

    def get(self, item: str) -> bool:
        return bool(getattr(self, item))


@dataclass
class NameSession:
    run_id: int
    proposal_id: int
    symbol: str
    session_date_et: str
    record: Verdict
    repeats: list[Verdict]           # the counted repeats only


def verdict(*, structural_vs_fad, under_narrated, at_inflection, include, conviction) -> Verdict:
    """The binary items with the record's comparison semantics (exact string equality, ``is True`` identity)."""
    return Verdict(structural=str(structural_vs_fad) == "structural", under_narrated=under_narrated is True,
                   at_inflection=at_inflection is True, include=bool(include),
                   floor=passes_floor(conviction, FLOOR))


def majority(values: list[bool]) -> bool | None:
    """Strict majority of ``values``; None on a tie or no values."""
    t = sum(1 for v in values if v)
    f = len(values) - t
    return True if t > f else False if f > t else None


def fleiss_kappa(subjects: list[list[bool]]) -> float | None:
    """Fleiss' kappa for binary ratings with a variable number of raters per subject (n_i ≥ 2 kept).

    P_i = (Σ_j n_ij² − n_i) / (n_i (n_i − 1)); P̄ = mean P_i; p_j = Σ_i n_ij / Σ_i n_i; P_e = Σ_j p_j²;
    κ = (P̄ − P_e) / (1 − P_e). None when there are no usable subjects or P_e == 1."""
    subs = [s for s in subjects if len(s) >= 2]
    if not subs:
        return None
    p_i, tot_true, tot = [], 0, 0
    for s in subs:
        n = len(s)
        t = sum(1 for v in s if v)
        f = n - t
        p_i.append((t * t + f * f - n) / (n * (n - 1)))
        tot_true += t
        tot += n
    p_bar = sum(p_i) / len(p_i)
    pt = tot_true / tot
    p_e = pt * pt + (1 - pt) * (1 - pt)
    if p_e >= 1.0:
        return None
    return (p_bar - p_e) / (1 - p_e)


def item_stats(names: list[NameSession], item: str) -> dict:
    """Agreement, majority match (ties counted as non-matches) and kappa for one item over ``names``."""
    usable = [n for n in names if n.repeats]
    if not usable:
        return {"n_names": 0, "agreement": None, "majority_match": None, "ties": 0, "kappa": None}
    agree = [sum(1 for r in n.repeats if r.get(item) == n.record.get(item)) / len(n.repeats) for n in usable]
    maj = [majority([r.get(item) for r in n.repeats]) for n in usable]
    match = [m is not None and m == n.record.get(item) for m, n in zip(maj, usable, strict=True)]
    return {"n_names": len(usable), "agreement": sum(agree) / len(agree),
            "majority_match": sum(match) / len(match), "ties": sum(1 for m in maj if m is None),
            "kappa": fleiss_kappa([[r.get(item) for r in n.repeats] for n in usable])}


def read1(names: list[NameSession]) -> dict:
    """Read 1 (entry), the 11-10 trigger kept: floor-contact names, record-vs-majority on ≥ floor."""
    contact = [n for n in names if n.repeats and (n.record.floor or any(r.floor for r in n.repeats))]
    if len(contact) < READ1_MIN_NAMES:
        return {"floor_contact_names": len(contact), "majority_match": None, "verdict": "not evaluable"}
    hits = sum(1 for n in contact if majority([r.floor for r in n.repeats]) == n.record.floor)
    share = hits / len(contact)
    return {"floor_contact_names": len(contact), "majority_match": share,
            "verdict": "look owed (k-read entry rule)" if share < READ1_TRIGGER else "no trigger"}


def read2(names: list[NameSession]) -> dict:
    """Read 2 (include): pooled include majority match + the share of names with any include disagreement."""
    usable = [n for n in names if n.repeats]
    if not usable:
        return {"name_sessions": 0, "majority_match": None, "any_disagreement": None, "verdict": "not evaluable"}
    match = sum(1 for n in usable if majority([r.include for r in n.repeats]) == n.record.include) / len(usable)
    split = sum(1 for n in usable if len({r.include for r in n.repeats}) > 1) / len(usable)
    if len(usable) < READ2_MIN_NAMES:
        verdict_ = "not evaluable"
    elif match < READ2_TRIGGER:
        verdict_ = "below 80%: a lone include=false read is not treated as reversing an entry"
    else:
        verdict_ = "at or above 80%"
    return {"name_sessions": len(usable), "majority_match": match, "any_disagreement": split, "verdict": verdict_}


# ── DB load (read-only) ──────────────────────────────────────────────────────────────────────────────────────────
def load(conn: sqlite3.Connection) -> tuple[list[NameSession], dict, list[dict]]:
    """(name-sessions, excluded-by-reason, sessions) from the probe tables + the record rows they point at."""
    sessions = [dict(r) for r in conn.execute("SELECT * FROM council_repeat_sessions ORDER BY id")]
    sdate = {s["run_id"]: s["session_date_et"] for s in sessions}
    excluded = {r[0]: int(r[1]) for r in conn.execute(
        "SELECT excluded_reason, COUNT(*) FROM council_repeat_reads WHERE excluded_reason IS NOT NULL "
        "GROUP BY excluded_reason ORDER BY excluded_reason")}
    out: list[NameSession] = []
    for p in conn.execute(
            "SELECT DISTINCT r.run_id, r.proposal_id, r.symbol, cp.conviction, cp.structural_vs_fad, cp.rationale "
            "FROM council_repeat_reads r JOIN council_proposals cp ON cp.id = r.proposal_id "
            "ORDER BY r.run_id, r.proposal_id").fetchall():
        try:
            strat = (json.loads(p["rationale"] or "{}") or {}).get("strategist") or {}
        except (TypeError, ValueError):
            strat = {}
        record = verdict(structural_vs_fad=p["structural_vs_fad"], under_narrated=strat.get("under_narrated"),
                         at_inflection=strat.get("at_inflection"), include=strat.get("include"),
                         conviction=p["conviction"])
        reps = [verdict(structural_vs_fad=r["structural_vs_fad"],
                        under_narrated=(None if r["under_narrated"] is None else bool(r["under_narrated"])),
                        at_inflection=(None if r["at_inflection"] is None else bool(r["at_inflection"])),
                        include=bool(r["include"]), conviction=r["conviction"])
                for r in conn.execute(
                    "SELECT * FROM council_repeat_reads WHERE run_id = ? AND proposal_id = ? "
                    "AND excluded_reason IS NULL ORDER BY repeat_idx", (p["run_id"], p["proposal_id"]))]
        out.append(NameSession(int(p["run_id"]), int(p["proposal_id"]), str(p["symbol"]),
                               str(sdate.get(p["run_id"], "?")), record, reps))
    return out, excluded, sessions


def report(conn: sqlite3.Connection) -> dict:
    names, excluded, sessions = load(conn)
    per_session = []
    for run_id in sorted({n.run_id for n in names}):
        group = [n for n in names if n.run_id == run_id]
        per_session.append({"run_id": run_id, "session_date_et": group[0].session_date_et,
                            "name_sessions": sum(1 for n in group if n.repeats),
                            "items": {it: item_stats(group, it) for it in ITEMS}})
    return {
        "sessions": [{k: s[k] for k in ("run_id", "session_date_et", "status", "k", "names_captured",
                                         "names_probed", "repeats", "cost_usd", "summary")} for s in sessions],
        "per_session": per_session,
        "pooled": {it: item_stats(names, it) for it in ITEMS},
        "read1": read1(names),
        "read2": read2(names),
        "excluded_by_reason": excluded,
        "unprobed_name_sessions": sum(1 for n in names if not n.repeats),
        "prevalence_caveat": PREVALENCE_CAVEAT,
        "definitions": ("counted repeats exclude understudy/parse_error/provider_error; majority is strict (a tie "
                        "is a non-match); kappa is variable-rater Fleiss among the repeats (record not a rater)"),
    }


def _f(x) -> str:
    return "  -  " if x is None else f"{x:5.2f}"


def render(rep: dict) -> str:
    lines = ["#456 council repeat-read probe — Arm A (measurement only; prereg §6)", ""]
    for s in rep["sessions"]:
        lines.append(f"session run #{s['run_id']} {s['session_date_et']}: {s['status']}, k={s['k']}, "
                     f"probed {s['names_probed']}/{s['names_captured']} captured, {s['repeats']} repeats, "
                     f"${float(s['cost_usd'] or 0):.4f} {s['summary']}")
    blocks = [(f"run #{p['run_id']} {p['session_date_et']} ({p['name_sessions']} names)", p["items"])
              for p in rep["per_session"]]
    blocks.append(("POOLED", rep["pooled"]))
    for title, items in blocks:
        lines += ["", title, f"  {'item':<15} {'n':>4} {'agree':>6} {'major':>6} {'ties':>5} {'kappa':>6}"]
        for it in ITEMS:
            st = items[it]
            lines.append(f"  {it:<15} {st['n_names']:>4} {_f(st['agreement']):>6} {_f(st['majority_match']):>6} "
                         f"{st['ties']:>5} {_f(st['kappa']):>6}")
    r1, r2 = rep["read1"], rep["read2"]
    lines += ["", f"Read 1 (entry): floor-contact names={r1['floor_contact_names']} "
                  f"majority match={_f(r1['majority_match']).strip()} → {r1['verdict']}",
              f"Read 2 (include): name-sessions={r2['name_sessions']} majority match="
              f"{_f(r2['majority_match']).strip()} any-disagreement={_f(r2['any_disagreement']).strip()} "
              f"→ {r2['verdict']}",
              f"Excluded repeats by reason: {rep['excluded_by_reason'] or 'none'}; "
              f"name-sessions with no counted repeat: {rep['unprobed_name_sessions']}",
              f"Caveat: {rep['prevalence_caveat']}",
              f"Definitions: {rep['definitions']}"]
    return "\n".join(lines)
