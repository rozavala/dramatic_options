"""Basket-quality report — close the survivorship → basket-curation loop (report-not-gate).

`config.universe.themes` is the operator-curated set of thematic **scan baskets** the weekly L0
discovery scan reads. This report ties what each basket *produces* (surfaced sentinels, framer
verdicts, traded outcomes, forward returns) back to the curated roster, so the operator can see
**curation drift** and curate `universe.themes` by hand (the hard seam — it NEVER edits config,
NEVER gates a trade, writes NO DB row, needs NO migration). It is the sibling
``PREREG_FIXED_BASKET_NULL.md`` (lines 74-79) names: the thing that makes `3B-absolute`'s curation
contamination auditable (heavy drift here → discount `3B-absolute`; `real − 3B` stays the clean read).

Three **cache-only / DB-read-only** sources (the ``cluster_diagnostic`` NO-FETCH discipline), all
keyed name → basket via ``fixed_basket.basket_symbols``:

1. **Discovery survivorship** (``sentinel_candidates``) as a STAGE FUNNEL — framer-passed → traded
   (``proposal_id``) → resolved — which localizes where a basket's names drop. Numerator is
   ``kind='sentinel'`` only; ``kind='control'`` is the separate pooled null baseline (random by
   construction — hand-seeds land here as controls). ``never_surfaced`` subtracts the discovery-barred
   set (hand-seeds ∪ open ∪ active sentinels) — those can't surface, so they are ``barred`` not
   deadweight. The ``prescreen → framer-pass`` stage is NOT persisted per basket (the framer DROPS
   artifacts/NEUTRALs — ``council/sentinel.py``), so the verdict mix is **survivor-biased** (can't
   show "basket is mostly artifacts") and a broken framer silently under-counts (no censor exists yet).
2. **Real-loop gate profile** (``convexity_eval`` — the REAL book's gate decisions only): per basket
   eligible% / gate_cheap% / median iv_rv / median otm_skew. Never-evaluated ≠ rich.
3. **Current snapshot** (report-time, NO-FETCH): the motion/structural **prescreen** (``would_surface_now``
   — NOT the IV/cheap-convexity gate, which needs a live chain) + the evidence-independent **data-dead**
   flag (a curated name with no cached bars can never be scanned).

**Forward read — two metrics, split by horizon semantics:** a stock **reference return** is
horizon-indexable; an option **realized multiple** resolves once at the ~250d exit. So
``reference_forward`` is horizon-indexed {180,270,365} (surfaced-never-traded sentinels + controls,
recomputed at report time with the §6 terminal guard) and ``traded_outcomes`` is pooled,
non-horizon-indexed. The decisive surfaced-vs-control null belongs to the sentinel-scoring layer; this
report *surfaces* it (pooled, p95 + bootstrap CI, **computed-when-mature**).

**Maturity gate (load-bearing for the null hierarchy):** the forward record is young (references resolve
~180d after surfacing; the traded clock ~never ticks on an empty book). Outcome/prune flags are gated
behind maturity; default KEEP. Only data-dead + degenerate-basket flags are evidence-independent. This is
not just honesty — 3B runs over the live basket, so outcome-conditioned pruning on a thin record would make
the contamination adaptive/outcome-correlated.

**basket ≠ cluster:** this curates the SCAN BASKETS (``universe.themes``) via survivorship; the correlation
diagnostic curates the RISK-CLUSTER map (``convexity_book.clusters``) via return-correlation. Different
object — no duplication.

**NO-FETCH:** read **cache-only** — pass a ``MarketData`` built with ``client=None`` so a cache-miss
surfaces as insufficient data, never a network call.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

import numpy as np

from dramatic_options import state
from dramatic_options.discovery import MarkerParams, clears_gate, compute_markers
from dramatic_options.fixed_basket import basket_symbols
from dramatic_options.sentinel_scoring import reference_return_from_bars
from dramatic_options.themes import active_themes, load_themes

log = logging.getLogger("basket_quality")

DEFAULT_HORIZONS = (180, 270, 365)
BOOTSTRAP_ITERS = 2000

CAVEATS = (
    "REPORT-NOT-GATE: informs the operator-curated universe.themes (hard seam); it never edits the basket "
    "or gates a trade, and writes no DB row.",
    "3B loop-close (PREREG_FIXED_BASKET_NULL 74-79): heavy curation drift here → discount 3B-absolute; "
    "real − 3B stays the clean read (both books see the same evolving basket each period).",
    "YOUNG RECORD: forward cells are unresolved for ~6 months (references resolve ~180d after surfacing; the "
    "traded clock ~never ticks on an empty book). Read as accruing substrate, not a verdict. Outcome/prune "
    "flags are maturity-gated; default is KEEP. Only data-dead + degenerate-basket flags are evidence-independent.",
    "FRAMER SURVIVOR BIAS: the framer DROPS artifacts/NEUTRALs/parse-fails (no row), so the confound_label / "
    "conviction mix is 'of the survivors' — it can NOT show 'basket is mostly artifacts', and a broken framer "
    "silently under-counts productivity (no framer-health censor exists yet — the proper fix is deferred).",
    "would_surface_now is the motion/structural PRESCREEN, not the IV/cheap-convexity gate (NO-FETCH can't see "
    "a live chain); cheapness lives only in the real_gate_profile (convexity_eval).",
    "SNAPSHOT IS CACHE-RELATIVE: data_dead / would_surface_now / eligible_now reflect the cache AS-OF this run. In "
    "the L0 scan the cache is freshly fetched (data-dead = genuinely dataless); a STANDALONE run over a stale cache "
    "(NO-FETCH) over-reports data-dead — read the snapshot from the L0 run, not a much-later standalone one.",
    "barred is as-of-now: a name barred most of the window then un-barred (dropped from themes.json) would "
    "misclassify — immaterial on a young record, a point-in-time exclude-history is disproportionate here.",
    "first-basket-wins: an overlap name is single-attributed to one basket; its quality contribution is "
    "invisible to a non-owning basket — don't read a sharing basket's productivity as complete.",
    "basket != cluster: this curates the scan baskets (universe.themes); the correlation diagnostic curates "
    "the risk-cluster map (convexity_book.clusters). Different curated object.",
)


# ── cache-only forward read (mirrors shares_basket.shares_return_report) ───────────────────────


def _bar_after(bar, anchor: datetime) -> bool:
    try:
        return datetime.fromisoformat(bar["ts"]) > anchor
    except (ValueError, TypeError, KeyError):
        return False


def _signed_ref_returns(market, symbol, direction, anchor: datetime, now: datetime,
                        horizons) -> dict[int, float | None]:
    """Per-horizon SIGNED reference return for one name from ``anchor`` (the §6 terminal guard reused per
    horizon; bullish = raw underlying return, bearish = negated). Cache-only: a missing entry/forward
    series → all None (unresolved, never fabricated)."""
    entry = market.latest_price(symbol, anchor)
    out: dict[int, float | None] = {h: None for h in horizons}
    if entry is None or entry <= 0:
        return out
    try:
        fwd = [b["close"] for b in market.cache.read_between("bars", symbol, anchor, now)
               if _bar_after(b, anchor)]
    except Exception:  # noqa: BLE001 — CacheMiss / missing name → unresolved, never a fetch
        return out
    is_bull = (direction or "bullish") == "bullish"
    for h in horizons:
        terminated = now >= anchor + timedelta(days=int(h * 1.6) + 4) and 0 < len(fwd) < h
        r, _tag = reference_return_from_bars(entry, fwd, h, terminated=terminated)
        out[h] = (r if is_bull else -r) if r is not None else None
    return out


def _pctl(xs: list[float], p: float) -> float | None:
    return round(float(np.percentile(xs, p)), 4) if xs else None


def _tail(returns_by_h: dict[int, list[float]], horizons) -> dict:
    """Per-horizon descriptive tail of a pool of signed returns (resolved counts + p50/p95)."""
    return {f"h{h}": {"resolved": len(returns_by_h[h]), "p50": _pctl(returns_by_h[h], 50),
                      "p95": _pctl(returns_by_h[h], 95)} for h in horizons}


def _bootstrap_p95_gap(surfaced: list[float], control: list[float], *, iters=BOOTSTRAP_ITERS,
                       seed=0) -> dict:
    """Pooled surfaced-vs-control p95 gap with a bootstrap CI (the pre-registered contrast, computed only
    when mature). Returns the point gap + 90% CI."""
    rng = np.random.default_rng(seed)
    s, c = np.asarray(surfaced, float), np.asarray(control, float)
    point = float(np.percentile(s, 95) - np.percentile(c, 95))
    gaps = [float(np.percentile(rng.choice(s, len(s)), 95) - np.percentile(rng.choice(c, len(c)), 95))
            for _ in range(iters)]
    lo, hi = np.percentile(gaps, [5, 95])
    return {"p95_gap": round(point, 4), "ci90": [round(float(lo), 4), round(float(hi), 4)],
            "n_surfaced": len(surfaced), "n_control": len(control)}


# ── basket / barred helpers ───────────────────────────────────────────────────────────────────


def _baskets(config: dict) -> dict[str, list[str]]:
    """``{basket: [SYMBOL,...]}`` from config.universe.themes (skip ``_``-comment keys)."""
    return {str(k): [str(s).upper() for s in v]
            for k, v in (config.get("universe", {}).get("themes", {}) or {}).items()
            if not str(k).startswith("_")}


def _barred_set(conn, config: dict) -> set[str]:
    """Names the discovery scan bars from surfacing (so 'never surfaced' is structural, not deadweight):
    hand-seeds ∪ open positions ∪ active sentinels — the same exclude orchestrator.run_discover builds."""
    barred = set(state.open_position_symbols(conn)) | state.active_sentinel_symbols(conn)
    try:
        barred |= {t.symbol.upper() for t in active_themes(load_themes(config.get("themes_path", "themes.json")))}
    except Exception as e:  # noqa: BLE001 — a missing themes.json must not break the report
        log.debug("themes.json load failed (%s) — barred set omits hand-seeds.", e)
    return {s.upper() for s in barred}


# ── the report ────────────────────────────────────────────────────────────────────────────────


def basket_quality_report(conn, config, as_of: datetime, market, *, horizons=None) -> dict:
    """Per-basket curation health over the curated scan baskets. Cache-only, read-only, no DB write."""
    bq = config.get("basket_quality", {})
    horizons = list(horizons or bq.get("horizons", DEFAULT_HORIZONS))
    min_refs = int(bq.get("min_resolved_references_for_flag", 20))
    min_traded = int(bq.get("min_traded_outcomes_for_flag", 10))
    min_live = int(bq.get("min_live_names_per_basket", 2))
    top_n = int(bq.get("top_n_per_name", 40))

    baskets = _baskets(config)
    barred = _barred_set(conn, config)
    sym2basket = basket_symbols(config)
    benchmark = str(config.get("universe", {}).get("benchmarks", {}).get("broad", "SPY")).upper()
    params = MarkerParams(**dict(config.get("discovery", {}).get("markers", {})))

    sents = [dict(r) for r in conn.execute(
        "SELECT kind, symbol, basket, direction, framer_conviction, confound_label, structural_vs_fad, "
        "status, surface_count, discovered_at, proposal_id, outcome, brier, realized_multiple "
        "FROM sentinel_candidates").fetchall()]
    evals = [dict(r) for r in conn.execute(
        "SELECT symbol, eligible, gate_cheap, iv_rv, otm_skew FROM convexity_eval").fetchall()]

    # report window age (the maturity proxy) = oldest discovered_at → now
    anchors = [_dt(s["discovered_at"]) for s in sents if _dt(s["discovered_at"])]
    window_age_days = (as_of - min(anchors)).days if anchors else 0
    mature = window_age_days >= max(horizons)   # references could have resolved across the whole window

    # control pool (global null baseline), recomputed multi-horizon at report time
    control_pool: dict[int, list[float]] = {h: [] for h in horizons}
    for c in (s for s in sents if s["kind"] == "control"):
        for h, r in _signed_ref_returns(market, c["symbol"].upper(), c["direction"],
                                        _dt(c["discovered_at"]) or as_of, as_of, horizons).items():
            if r is not None:
                control_pool[h].append(r)

    surfaced_pool: dict[int, list[float]] = {h: [] for h in horizons}   # for the pooled contrast
    baskets_out: dict[str, dict] = {}
    per_name: list[dict] = []
    drift: list[dict] = []

    for basket, members in baskets.items():
        members_up = [m.upper() for m in members]
        b_sents = [s for s in sents if s["kind"] == "sentinel" and (s["basket"] or "").upper() == basket.upper()]
        b_ctrl = [s for s in sents if s["kind"] == "control" and (s["basket"] or "").upper() == basket.upper()]
        surfaced_syms = {s["symbol"].upper() for s in b_sents}

        # ── current snapshot (report-time prescreen, NO-FETCH) ──
        has_bars = data_dead = surf_now = elig_now = 0
        bar_present: dict[str, bool] = {}
        for sym in members_up:
            m = compute_markers(sym, as_of, market=market, benchmark=benchmark, params=params, basket=basket)
            present = m.price is not None
            bar_present[sym] = present
            if present:
                has_bars += 1
                if m.eligible:
                    elig_now += 1
                if clears_gate(m, params)[0]:
                    surf_now += 1
            else:
                data_dead += 1

        # ── funnel (framer-passed → traded → resolved) ──
        traded = sum(1 for s in b_sents if s["proposal_id"] is not None)
        resolved = sum(1 for s in b_sents if s["realized_multiple"] is not None or s["outcome"] is not None)
        never_surfaced = [s for s in members_up if s not in surfaced_syms and s not in barred]
        barred_members = [s for s in members_up if s in barred]

        # ── verdict mix (survivor-biased — see caveat) ──
        verdict_mix = {
            "framer_conviction": _counts(s["framer_conviction"] for s in b_sents),
            "confound_label": _counts(s["confound_label"] for s in b_sents),
            "structural_vs_fad": _counts(s["structural_vs_fad"] for s in b_sents),
        }

        # ── real-loop gate profile (convexity_eval, real book only; never-evaluated ≠ rich) ──
        b_evals = [e for e in evals if (sym2basket.get(e["symbol"].upper()) or "").upper() == basket.upper()]
        gate_profile = _gate_profile(b_evals)

        # ── forward read: reference (surfaced-never-traded, horizon-indexed) + traded (pooled) ──
        ref_by_h: dict[int, list[float]] = {h: [] for h in horizons}
        n_never_traded = 0
        for s in b_sents:
            if s["proposal_id"] is not None:
                continue
            n_never_traded += 1
            for h, r in _signed_ref_returns(market, s["symbol"].upper(), s["direction"],
                                            _dt(s["discovered_at"]) or as_of, as_of, horizons).items():
                if r is not None:
                    ref_by_h[h].append(r)
                    surfaced_pool[h].append(r)
        traded_mults = [s["realized_multiple"] for s in b_sents if s["realized_multiple"] is not None]
        n_ref_resolved = sum(len(v) for v in ref_by_h.values())

        # ── maturity + flags ──
        flags: list[str] = []
        for sym in members_up:
            if not bar_present[sym]:
                flags.append(f"data-dead: {sym} (no cached bars as-of this run)")
        if (has_bars < min_live) or (data_dead == len(members_up)):
            flags.append(f"degenerate basket: {has_bars}/{len(members_up)} names with usable bars (< {min_live})")
        if mature:   # never-productive is only meaningful once the window is old enough
            for sym in never_surfaced:
                if bar_present.get(sym):
                    flags.append(f"never-productive: {sym} (eligible, never surfaced over {window_age_days}d)")

        baskets_out[basket] = {
            "n_curated": len(members_up),
            "current_snapshot": {"with_bars": has_bars, "data_dead": data_dead,
                                 "would_surface_now": surf_now, "eligible_now": elig_now},
            "funnel": {"framer_passed_lineages": len(b_sents), "traded": traded, "resolved": resolved,
                       "never_surfaced_curated": never_surfaced, "barred": barred_members},
            "verdict_mix": verdict_mix,
            "controls": {"n": len(b_ctrl)},
            "real_gate_profile": gate_profile,
            "reference_forward": _tail(ref_by_h, horizons),
            "traded_outcomes": {"n_traded": len(traded_mults),
                                "realized_multiple_p95": _pctl(traded_mults, 95)},
            "evidence_maturity": {
                "window_age_days": window_age_days, "mature": mature,
                "reference_clock": f"{n_ref_resolved} resolved / {n_never_traded} surfaced-never-traded",
                "traded_clock": f"{len(traded_mults)} resolved / {traded} traded",
            },
            "flags": flags,
        }

        for sym in members_up:
            lin = [s for s in b_sents if s["symbol"].upper() == sym]
            per_name.append({
                "symbol": sym, "basket": basket, "has_bars": bar_present[sym],
                "is_barred": sym in barred, "ever_surfaced_as_sentinel": bool(lin),
                "lineages": [{"direction": s["direction"], "status": s["status"]} for s in lin],
                "surface_count": sum(int(s["surface_count"] or 0) for s in lin),
                "funnel_stage": _stage(lin),
                "n_evaluated_real": sum(1 for e in b_evals if e["symbol"].upper() == sym),
            })
        drift.extend({"basket": basket, "indicator": f} for f in flags)

    # ── the pre-registered pooled surfaced-vs-control contrast (computed-when-mature) ──
    contrast = {}
    for h in horizons:
        s_h, c_h = surfaced_pool[h], control_pool[h]
        if len(s_h) >= min_refs and len(c_h) >= min_refs:
            contrast[f"h{h}"] = _bootstrap_p95_gap(s_h, c_h)
        else:
            contrast[f"h{h}"] = {"status": "insufficient_evidence",
                                 "n_surfaced": len(s_h), "n_control": len(c_h), "min_required": min_refs}

    return {
        "as_of": as_of.isoformat(), "horizons": horizons, "window_age_days": window_age_days,
        "mature": mature, "min_resolved_references_for_flag": min_refs,
        "min_traded_outcomes_for_flag": min_traded, "schema_note": "report-not-gate; no DB write; no migration",
        "baskets": baskets_out,
        "control_baseline": _tail(control_pool, horizons),
        "surfaced_vs_control_contrast": contrast,   # belongs to the sentinel-scoring null; surfaced here
        "per_name": sorted(per_name, key=lambda r: (r["basket"], r["symbol"]))[:top_n],
        "curation_drift_indicators": drift,
        "caveats": list(CAVEATS),
    }


# ── small helpers ───────────────────────────────────────────────────────────────────────────────


def _dt(s) -> datetime | None:
    try:
        return datetime.fromisoformat(s) if s else None
    except (ValueError, TypeError):
        return None


def _counts(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        k = str(v) if v is not None else "null"
        out[k] = out.get(k, 0) + 1
    return out


def _stage(lineages: list[dict]) -> str:
    if not lineages:
        return "never_surfaced"
    if any(s["realized_multiple"] is not None or s["outcome"] is not None for s in lineages):
        return "resolved"
    if any(s["proposal_id"] is not None for s in lineages):
        return "traded"
    return "framer_passed"


def _gate_profile(b_evals: list[dict]) -> dict | str:
    if not b_evals:
        return "no gate data (never evaluated)"
    n = len(b_evals)
    ivs = [float(e["iv_rv"]) for e in b_evals if e["iv_rv"] is not None]
    sks = [float(e["otm_skew"]) for e in b_evals if e["otm_skew"] is not None]
    return {
        "n_evaluated": n,
        "eligible_pct": round(sum(1 for e in b_evals if e["eligible"]) / n, 3),
        "gate_cheap_pct": round(sum(1 for e in b_evals if e["gate_cheap"]) / n, 3),
        "median_iv_rv": round(float(np.median(ivs)), 3) if ivs else None,
        "median_otm_skew": round(float(np.median(sks)), 3) if sks else None,
    }


def main() -> int:
    from datetime import UTC

    from dramatic_options.config_loader import load_config
    from dramatic_options.data.cache import PointInTimeCache
    from dramatic_options.data.market import MarketData, default_fetch_window

    config = load_config()
    conn = state.get_db(config)
    as_of = datetime.now(UTC)
    cache = PointInTimeCache(config.get("cache", {}).get("dir", "data/cache"))
    fetch_start, _ = default_fetch_window(as_of)
    # client=None → the NO-FETCH invariant (read-only over the warm cache).
    market = MarketData(cache, client=None, fetch_start=fetch_start, fetch_end=as_of)
    print(json.dumps(basket_quality_report(conn, config, as_of, market), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
