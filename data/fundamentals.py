"""Fundamentals adapter (Phase 1 iteration k=4 — substance INFORMATIVENESS).

The deterministic substance proxy through k=3 measured tangible-event *presence* (8-K item
codes, 13D/G, insider flows) — activity, not whether delivery actually backs the story. This
adapter measures **reported delivery** itself: year-over-year growth of revenue from SEC
**XBRL companyfacts** (`data.sec.gov/api/xbrl/companyfacts`).

Point-in-time by construction: every XBRL datapoint carries a ``filed`` date, so an as-of
read uses only facts filed ≤ as_of (amendments superseding by latest filed). Quarterly
datapoints (duration ≈ 90d) are summed into a trailing-twelve-month (TTM) figure; YoY growth
compares the latest TTM available as-of to the TTM one year earlier. Names whose year-ago
TTM revenue is below a materiality floor return None (excluded from that date's cross-section
— consistent with the N_min discipline): for pre-revenue names YoY growth on a ~0 base is
noise, not delivery.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REV_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SOURCE = "fundamentals"
_EARLY = datetime(2003, 1, 1, tzinfo=UTC)


def _d(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC) if len(s) == 10 else \
        datetime.fromisoformat(s)


def extract_quarterly_revenue(facts_json: dict) -> list[dict[str, Any]]:
    """Quarterly (≈90-day) revenue datapoints from a companyfacts payload.

    Returns records {"start","end","val","filed"} (ISO strings), one per (start,end) period
    keeping the LATEST-filed value (amendments win). Annual/YTD durations are dropped so the
    TTM sum doesn't double-count.
    """
    usg = facts_json.get("facts", {}).get("us-gaap", {})
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for concept in REV_CONCEPTS:
        for u in usg.get(concept, {}).get("units", {}).get("USD", []):
            start, end, filed = u.get("start"), u.get("end"), u.get("filed")
            if not (start and end and filed and u.get("val") is not None):
                continue
            dur = (_d(end) - _d(start)).days
            if not (80 <= dur <= 100):  # quarterly only
                continue
            key = (start, end)
            prev = best.get(key)
            if prev is None or filed > prev["filed"]:
                best[key] = {"start": start, "end": end, "val": float(u["val"]), "filed": filed}
    return sorted(best.values(), key=lambda r: r["end"])


def _ttm_at(points: list[dict[str, Any]], anchor_end: str) -> float | None:
    """Sum of the 4 quarterly values ending at or before ``anchor_end`` (need exactly 4,
    CONSECUTIVE). The consecutiveness guard (§9 corpus build): without it a systematically
    missing quarter (e.g. Q4 filed only inside the FY duration) makes the "last 4 available"
    span 5+ calendar quarters — a silently wrong TTM. Adjacent ends must be ~one quarter apart."""
    elig = [p for p in points if p["end"] <= anchor_end]
    if len(elig) < 4:
        return None
    last4 = elig[-4:]
    for a, b in zip(last4, last4[1:], strict=False):
        gap = (_d(b["end"]) - _d(a["end"])).days
        if not (70 <= gap <= 115):  # ~one quarter; else the window is non-consecutive → refuse
            return None
    return sum(p["val"] for p in last4)


def revenue_yoy(points: list[dict[str, Any]], as_of: datetime, *, min_base: float) -> float | None:
    """YoY growth of TTM revenue using only points filed ≤ as_of.

    None if: <8 quarters available, no period ~1y before the latest, or year-ago TTM below
    ``min_base`` (immaterial → growth is noise).
    """
    iso = as_of.isoformat()
    visible = sorted((p for p in points if p["filed"] <= iso), key=lambda r: r["end"])
    if len(visible) < 8:
        return None
    latest_end = visible[-1]["end"]
    ttm_now = _ttm_at(visible, latest_end)
    if ttm_now is None:
        return None
    # find a period ~1 year before latest_end (within ±45 days)
    target = (_d(latest_end).replace(year=_d(latest_end).year - 1)).date().isoformat()
    prior = [p for p in visible if abs((_d(p["end"]) - _d(target)).days) <= 45]
    if not prior:
        return None
    ttm_prior = _ttm_at(visible, prior[-1]["end"])
    if ttm_prior is None or ttm_prior < min_base:
        return None
    return ttm_now / ttm_prior - 1.0


class FundamentalsData:
    """As-of revenue-growth (delivery) per name, backed by the point-in-time cache.

    Raw companyfacts JSON is cached on disk (keyed by CIK); the parsed quarterly series is
    cached in the point-in-time cache. ``edgar`` resolves ticker→CIK; ``None`` ⇒ offline.
    """

    def __init__(
        self,
        cache: Any,
        *,
        edgar: Any | None,
        fetch_end: datetime,
        ua: str = "",
        cache_dir: str | Path = "data/cache",
        min_base_revenue: float = 10_000_000.0,
        session: Any | None = None,
        cik_overrides: dict[str, str] | None = None,
        max_raw_age_days: int | None = None,
    ) -> None:
        self.cache = cache
        self.edgar = edgar
        self.fetch_end = fetch_end
        self.ua = ua
        self.raw_dir = Path(cache_dir) / "xbrl_raw"
        self.min_base = min_base_revenue
        self.session = session
        self.cik_overrides = cik_overrides or {}
        # §9 corpus freshness policy: None = the historical never-refetch behavior (shelved
        # callers byte-compatible); the council path passes a small number (e.g. 7).
        self.max_raw_age_days = max_raw_age_days

    def _cik(self, symbol: str) -> str | None:
        if self.edgar is not None:
            return self.edgar.ticker_to_cik(symbol, overrides=self.cik_overrides)
        ov = self.cik_overrides.get(symbol.upper())
        return str(ov).zfill(10) if ov else None

    def _points(self, symbol: str) -> list[dict[str, Any]]:
        cik = self._cik(symbol)
        if cik is None:
            return []
        if self.cache.covers(SOURCE, cik, _EARLY, self.fetch_end):
            return self.cache.read_between(SOURCE, cik, None, self.fetch_end)
        if self.edgar is None or self.cache.offline:
            return []
        raw = self._download(cik)
        points = extract_quarterly_revenue(raw) if raw else []
        # store with ts = filed date so as-of reads filter correctly via read_between
        recs = [{"ts": p["filed"] if len(p["filed"]) > 10 else p["filed"] + "T20:00:00+00:00",
                 "start": p["start"], "end": p["end"], "val": p["val"], "filed": p["filed"]}
                for p in points]
        self.cache.write(SOURCE, cik, recs, coverage_from=_EARLY, coverage_through=self.fetch_end)
        return recs

    def _download(self, cik: str) -> dict | None:
        path = self.raw_dir / f"CIK{cik}.json"
        if path.exists():
            return json.loads(path.read_text())
        if not self.ua or self.session is None:
            import requests
            self.session = self.session or requests.Session()
        resp = self.session.get(FACTS_URL.format(cik=cik), headers={"User-Agent": self.ua},
                                timeout=60)
        if resp.status_code != 200:
            return None
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(resp.text)
        return resp.json()

    def revenue_growth_asof(self, symbol: str, as_of: datetime) -> float | None:
        pts = self._points(symbol)
        if not pts:
            return None
        return revenue_yoy(pts, as_of, min_base=self.min_base)

    # ── §9 evidence-grounding corpus (PREREG_EVIDENCE_GROUNDING) ─────────────────────────────

    def _raw_fresh(self, cik: str, *, force_refresh: bool = False) -> dict | None:
        """Freshness-aware companyfacts loader (§4 of the grounding pre-reg).

        ``max_raw_age_days=None`` (default) = the historical never-refetch behavior (shelved
        callers byte-compatible). With a policy set: a disk raw older than the policy — or
        ``force_refresh`` (a fresh filing event: the moment evidence matters most) — refetches
        when online. The refetch VALIDATES before committing (parse + a 'facts' key; a 200-OK
        SEC error page must not pass) and writes temp-then-rename (a partial response never
        clobbers a good raw). Online-but-SEC-errors falls back to the stale disk raw — a stale
        line with its dates visible beats an empty section."""
        path = self.raw_dir / f"CIK{cik}.json"
        stale = None
        if path.exists():
            try:
                stale = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                stale = None
            age_days = (datetime.now(UTC) - datetime.fromtimestamp(path.stat().st_mtime, UTC)).days
            fresh_enough = (self.max_raw_age_days is None or age_days <= self.max_raw_age_days)
            if stale is not None and fresh_enough and not force_refresh:
                return stale
        if not self.ua:
            return stale
        try:
            if self.session is None:
                import requests
                self.session = requests.Session()
            resp = self.session.get(FACTS_URL.format(cik=cik),
                                    headers={"User-Agent": self.ua}, timeout=60)
            if resp.status_code != 200:
                return stale
            fresh = resp.json()
            if not isinstance(fresh, dict) or "facts" not in fresh:
                return stale
            self.raw_dir.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(resp.text)
            tmp.replace(path)
            return fresh
        except Exception:  # noqa: BLE001 — fail-soft: grounding must never break a cycle
            return stale

    def corpus_asof(self, symbol: str, as_of: datetime, *, force_refresh: bool = False) -> dict:
        """The pinned evidence lines for one name (fail-soft; see CONCEPTS for the registry).

        Returns ``{"lines": [...], "status": "ok"|"partial"|"empty", "n_lines": int}``.
        Never raises into a cycle."""
        try:
            cik = self._cik(symbol)
            raw = self._raw_fresh(cik, force_refresh=force_refresh) if cik else None
            usg = (raw or {}).get("facts", {}).get("us-gaap", {})
            lines = corpus_lines(usg, as_of) if usg else []
        except Exception:  # noqa: BLE001
            lines = []
        n_concepts = len({ln["concept"] for ln in lines})
        status = "empty" if not lines else ("ok" if n_concepts >= 3 else "partial")
        return {"lines": lines, "status": status, "n_lines": len(lines)}


# ── §9 corpus: concept registry + the three extraction shapes ─────────────────────────────────
#
# Shapes (XBRL mechanics — each fixture-tested):
#   quarterly_income — quarterly durations (80–100d) + Q4 DERIVATION (Q4 = FY − Q1..Q3 inside
#                      the same fiscal window) where standalone Q4 isn't filed; never a
#                      non-consecutive sum.
#   ytd_cashflow     — 10-Q cash-flow facts are fiscal-YTD: quarterly values = differences of
#                      consecutive same-fiscal-window YTD facts (Q1 = the ~90d fact itself).
#   instant          — point-in-time balances (RPO): end-only; YoY = two instants 350–380d apart.
# PIT pick rule: ALL (period, filed) variants are kept; the read picks max-filed ≤ as_of per
# period (an amendment filed after as_of never erases the original from an earlier read).
# Same-day boundary: a filed DATE compares at T20:00:00Z (a same-day filing is NOT visible to
# the 19:45 UTC L1 — deterministic, identical in backtest and live).
# Year-ago matching: period-end proximity ±45 days around one year back — the operative rule
# (the fy/fp fields on companyfacts units describe the FILING, not the fact's period — the
# known XBRL gotcha — so fiscal-label matching is not reliably implementable from this payload).
# Tag selection is stable PER NAME (most deduped visible periods wins), never per-period;
# gross margin uses the consistent (revenue, cost) winner pair.

CONCEPT_TAGS: dict[str, list[str]] = {
    "revenue": REV_CONCEPTS,
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "rpo": ["RevenueRemainingPerformanceObligation"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
}
# Denominator floors (omit a YoY whose base is below floor or flips sign — no "+4,300%" lines).
MIN_BASE = {"revenue_ttm": 10e6, "revenue_qtr": 2.5e6, "capex_qtr": 1e6, "rpo": 10e6}
_Q = (80, 100)     # quarterly duration days
_FY = (330, 380)   # full-year duration days


def _filed_visible(filed: str, as_of: datetime) -> bool:
    """The pinned same-day boundary: filed date @ T20:00Z ≤ as_of."""
    ts = filed if len(filed) > 10 else filed + "T20:00:00+00:00"
    return _d(ts) <= as_of


def _collect(usg: dict, tag: str, *, instant: bool) -> list[dict[str, Any]]:
    """ALL (period, filed) variants for one tag — no dedup here (the PIT pick is read-time)."""
    out = []
    for u in usg.get(tag, {}).get("units", {}).get("USD", []):
        end, filed, val = u.get("end"), u.get("filed"), u.get("val")
        if not (end and filed and val is not None):
            continue
        start = u.get("start")
        if instant:
            if start and start != end:
                continue
            out.append({"start": None, "end": end, "val": float(val), "filed": filed})
        else:
            if not start:
                continue
            out.append({"start": start, "end": end, "val": float(val), "filed": filed})
    return out


def _pit_dedup(facts: list[dict], as_of: datetime) -> list[dict]:
    """Visible-at-as_of facts, max-filed-≤-as_of winning per (start, end). Sorted by end."""
    best: dict[tuple, dict] = {}
    for f in facts:
        if not _filed_visible(f["filed"], as_of):
            continue
        key = (f["start"], f["end"])
        prev = best.get(key)
        if prev is None or f["filed"] > prev["filed"]:
            best[key] = f
    return sorted(best.values(), key=lambda r: r["end"])


def _pick_tag(usg: dict, tags: list[str], as_of: datetime, *, instant: bool = False) -> tuple[str | None, list[dict]]:
    """Stable per-name tag: the tag with the MOST deduped visible periods wins (ties → list
    order). Never first-with-data per period — a mid-history tag migration must not splice."""
    best_tag, best_series = None, []
    for tag in tags:
        series = _pit_dedup(_collect(usg, tag, instant=instant), as_of)
        if len(series) > len(best_series):
            best_tag, best_series = tag, series
    return best_tag, best_series


def _dur_days(f: dict) -> int:
    return (_d(f["end"]) - _d(f["start"])).days


def quarterly_income_series(series: list[dict]) -> list[dict]:
    """Shape (i): quarterly facts + Q4 derivation from the FY duration where standalone Q4 is
    absent. Derived Q4 carries filed = max(filed of inputs) — PIT-correct by construction."""
    quarters = [f for f in series if _Q[0] <= _dur_days(f) <= _Q[1]]
    fys = [f for f in series if _FY[0] <= _dur_days(f) <= _FY[1]]
    by_end = {q["end"] for q in quarters}
    derived = []
    for fy in fys:
        inside = [q for q in quarters if fy["start"] <= q["start"] and q["end"] <= fy["end"]]
        if len(inside) != 3:
            continue
        last_q_end = max(q["end"] for q in inside)
        gap = (_d(fy["end"]) - _d(last_q_end)).days
        if not (_Q[0] <= gap <= _Q[1]) or fy["end"] in by_end:
            continue
        derived.append({"start": last_q_end, "end": fy["end"],
                        "val": fy["val"] - sum(q["val"] for q in inside),
                        "filed": max([fy["filed"], *[q["filed"] for q in inside]])})
    return sorted(quarters + derived, key=lambda r: r["end"])


def ytd_cashflow_series(series: list[dict]) -> list[dict]:
    """Shape (ii): same-fiscal-window YTD chains differenced into quarters (Q1 = the ~90d fact)."""
    chains: dict[str, list[dict]] = {}
    for f in series:
        chains.setdefault(f["start"], []).append(f)
    out = []
    for chain in chains.values():
        chain = sorted(chain, key=lambda r: r["end"])
        prev = None
        for f in chain:
            dur = _dur_days(f)
            if prev is None:
                if _Q[0] <= dur <= _Q[1]:
                    out.append(dict(f))
                prev = f
                continue
            gap = (_d(f["end"]) - _d(prev["end"])).days
            if _Q[0] <= gap <= _Q[1]:
                out.append({"start": prev["end"], "end": f["end"], "val": f["val"] - prev["val"],
                            "filed": max(f["filed"], prev["filed"])})
            prev = f
    return sorted(out, key=lambda r: r["end"])


def _year_ago(series: list[dict], end: str, *, lo: int = 320, hi: int = 410) -> dict | None:
    """Period-end proximity match ~one year back (±45d around 365)."""
    target = _d(end)
    cands = [f for f in series if lo <= (target - _d(f["end"])).days <= hi]
    return cands[-1] if cands else None


def _yoy(latest: dict, base: dict, *, min_base: float) -> float | None:
    if base["val"] < min_base or base["val"] <= 0:
        return None
    return latest["val"] / base["val"] - 1.0


def _line(concept: str, metric: str, value: float, latest: dict, base: dict | None) -> dict:
    return {"concept": concept, "metric": metric, "value": round(value, 4),
            "latest_musd": round(latest["val"] / 1e6, 1),
            "base_musd": round(base["val"] / 1e6, 1) if base else None,
            "period_end": latest["end"], "filed": latest["filed"]}


def corpus_lines(usg: dict, as_of: datetime) -> list[dict]:
    """The pinned §2 evidence lines from one companyfacts us-gaap dict, as-of-correct."""
    lines: list[dict] = []

    _rtag, rev_raw = _pick_tag(usg, CONCEPT_TAGS["revenue"], as_of)
    rev_q = quarterly_income_series(rev_raw)
    if rev_q:
        latest = rev_q[-1]
        # revenue level: TTM YoY (consecutive both legs)
        pts = [{"start": q["start"], "end": q["end"], "val": q["val"], "filed": q["filed"]} for q in rev_q]
        ttm_now = _ttm_at(pts, latest["end"])
        prior_anchor = _year_ago(rev_q, latest["end"])
        if ttm_now is not None and prior_anchor is not None:
            ttm_prior = _ttm_at(pts, prior_anchor["end"])
            if ttm_prior is not None and ttm_prior >= MIN_BASE["revenue_ttm"]:
                lines.append(_line("revenue", "ttm_yoy", ttm_now / ttm_prior - 1.0,
                                   {"val": ttm_now, "end": latest["end"], "filed": latest["filed"]},
                                   {"val": ttm_prior, "end": prior_anchor["end"], "filed": prior_anchor["filed"]}))
        # quarterly accel: qtr YoY now minus qtr YoY two quarters back (earlier than TTM-on-TTM)
        def _qtr_yoy(anchor: dict) -> float | None:
            base = _year_ago(rev_q, anchor["end"])
            return _yoy(anchor, base, min_base=MIN_BASE["revenue_qtr"]) if base else None
        yoy_now = _qtr_yoy(latest)
        yoy_prev = _qtr_yoy(rev_q[-3]) if len(rev_q) >= 3 else None
        if yoy_now is not None:
            lines.append(_line("revenue", "qtr_yoy", yoy_now, latest, _year_ago(rev_q, latest["end"])))
            if yoy_prev is not None:
                lines.append({"concept": "revenue", "metric": "qtr_yoy_accel",
                              "value": round(yoy_now - yoy_prev, 4), "latest_musd": None,
                              "base_musd": None, "period_end": latest["end"], "filed": latest["filed"]})

        # gross margin Δ — the CONSISTENT (revenue, cost) pair
        _ctag, cost_raw = _pick_tag(usg, CONCEPT_TAGS["cost_of_revenue"], as_of)
        cost_q = {c["end"]: c for c in quarterly_income_series(cost_raw)}
        common = [q for q in rev_q if q["end"] in cost_q and q["val"] > 0]
        if common:
            cur = common[-1]
            ago = _year_ago(common, cur["end"])
            if ago is not None:
                gm_now = (cur["val"] - cost_q[cur["end"]]["val"]) / cur["val"]
                gm_ago = (ago["val"] - cost_q[ago["end"]]["val"]) / ago["val"]
                lines.append({"concept": "gross_margin", "metric": "delta_pts",
                              "value": round((gm_now - gm_ago) * 100, 2),
                              "latest_musd": round(gm_now * 100, 1), "base_musd": round(gm_ago * 100, 1),
                              "period_end": cur["end"],
                              "filed": max(cur["filed"], cost_q[cur["end"]]["filed"])})

    _ktag, capex_raw = _pick_tag(usg, CONCEPT_TAGS["capex"], as_of)
    capex_q = ytd_cashflow_series(capex_raw)
    if capex_q:
        latest = capex_q[-1]
        base = _year_ago(capex_q, latest["end"])
        if base is not None:
            v = _yoy(latest, base, min_base=MIN_BASE["capex_qtr"])
            if v is not None:
                lines.append(_line("capex", "qtr_yoy", v, latest, base))

    _ptag, rpo = _pick_tag(usg, CONCEPT_TAGS["rpo"], as_of, instant=True)
    if rpo:
        latest = rpo[-1]
        base = _year_ago(rpo, latest["end"], lo=350, hi=380)
        if base is not None:
            v = _yoy(latest, base, min_base=MIN_BASE["rpo"])
            if v is not None:
                lines.append(_line("rpo", "yoy", v, latest, base))

    return lines
