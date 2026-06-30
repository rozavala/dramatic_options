"""§5b observability dashboard — the thin Streamlit shell.

ALL data/compute lives in `dashboard_data` (pure, streamlit-free, tested); this file only renders. It is
**read-only** (`?mode=ro`), **NO-FETCH** (`MarketData(client=None)`), **fail-soft** (every panel via
`dd.safe`), and observation-only (never edits clusters/themes/config, never a trade/auth path). The render
favours labelled metrics/tables + hover-help over raw JSON; the raw dict stays behind an expander per panel.

Run it where the live state lives, and bind to localhost only — it renders the whole book + the cluster map
(operator-confidential), so never expose it on a public port:

    pip install -r requirements-dashboard.txt
    # Run from the live checkout so the relative DB path resolves to the live DB (or set DRAMATIC_DB /
    # DRAMATIC_CACHE_DIR explicitly). `.streamlit/config.toml` pins PORT 8601 + localhost so it NEVER
    # collides with the real_options dashboards on 8501/8502; pass --server.port / --server.address to override
    # (e.g. the tailnet IP for remote access — but it renders the whole book + cluster map, so prefer a tunnel).
    DRAMATIC_DB=~/dramatic_options/data/dramatic_options.db \
    DRAMATIC_CACHE_DIR=~/dramatic_options/data/cache \
    streamlit run dashboard.py --server.port 8601

The performance/null panels are EMPTY (accruing) for ~6mo until positions resolve — they render a friendly
"accruing" empty-state by design, never a misleading "0.0×".
"""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

import dashboard_data as dd
from config_loader import load_config


def _market(cache_dir: str):
    """A NO-FETCH MarketData over the cache (client=None ⇒ never fetches; a cache miss raises CacheMiss,
    surfaced as 'accruing' by dd.safe). Returns None on any setup error (curation then shows 'accruing')."""
    try:
        from data.cache import PointInTimeCache
        from data.market import MarketData, default_fetch_window

        now = datetime.now(UTC)
        start, _ = default_fetch_window(now)
        return MarketData(PointInTimeCache(cache_dir), client=None, fetch_start=start, fetch_end=now)
    except Exception:  # noqa: BLE001 — curation degrades to "accruing"
        return None


@st.cache_data(ttl=60, show_spinner=False)
def load_all(db_path: str, cache_dir: str, db_exists: bool, _nonce: int) -> dict:
    """One short-lived read-only snapshot of every panel (so the WAL reader can't linger and block a deploy
    migration). Cached 60s; the Refresh button busts it via ``_nonce``. Every panel is fail-soft."""
    if not db_exists:
        return {"_fatal": f"no database at {db_path} — set DRAMATIC_DB to the live checkout's DB"}
    config = load_config()
    conn = dd.connect_ro(db_path)
    market = _market(cache_dir)
    try:
        return {
            "header": dd.safe(dd.header_status, conn),
            "t4": dd.safe(dd.t4_scoreboard, conn, config),
            "risk": dd.safe(dd.risk_panel, conn, config),
            "account": dd.safe(dd.account_panel, conn, config),
            "regime": dd.safe(dd.regime_panel, conn, config),
            "sentinels": dd.safe(dd.sentinels_panel, conn),
            "positions": dd.safe(dd.positions_panel, conn),
            "council": dd.safe(dd.council_panel, conn, config),
            "deliberation": dd.safe(dd.latest_run_deliberation, conn),
            "performance": dd.safe(dd.performance_panel, conn),
            "nulls": dd.safe(dd.null_hierarchy, conn),
            "attribution": dd.safe(dd.attribution_panel, conn, config),
            "funnel": dd.safe(dd.funnel_panel, conn),
            "council_stage": dd.safe(dd.council_stage_funnel, conn, config),
            "gate_reasons": dd.safe(dd.gate_reasons, conn),
            "cap_flow": dd.safe(dd.cap_binding_flow, conn),
            "cost": dd.safe(dd.cost_ledger, conn),
            "market_ctx": dd.safe(dd.market_context, conn),
            "dualread": dd.safe(dd.gate_dualread_report, conn, config),
            "dualread_runtime": dd.safe(dd.dualread_runtime_panel, conn, config),
            "cheapness": dd.safe(dd.cheapness_watch_panel, conn, config),
            "curation": dd.safe(dd.curation_panel, conn, config, market),
            "data_gathered": dd.safe(dd.data_gathered_panel, cache_dir),
        }
    finally:
        conn.close()


def _err(panel) -> str | None:
    return panel.get("error") if isinstance(panel, dict) else None


def _show(panel, label: str = "") -> bool:
    """Render a panel's error box if it failed; return True if OK to render the body."""
    e = _err(panel)
    if e:
        st.warning(f"{label or 'panel'} unavailable (fail-soft): {e}")
        return False
    return True


def _accruing(what: str) -> None:
    st.info(f"⏳ Accruing — nothing has resolved yet. First read once positions open and resolve (~6–12mo "
            f"after the first entry; the book is empty today). This will then show {what}.")


def _is_accruing(d) -> bool:
    """A per-book CI/tail cell is accruing when n==0 (or its flag says so)."""
    return isinstance(d, dict) and (d.get("n") == 0 or str(d.get("flag") or "").startswith("accruing"))


def _ci_rows(arms: dict) -> list[dict]:
    """{name: {n,p95,ci90,flag}} → table rows (shared by Performance + Null books)."""
    rows = []
    for name, a in arms.items():
        lo, hi = (a.get("ci90") or [None, None])
        rows.append({"book": name, "n": a.get("n"), "p95": a.get("p95"),
                     "CI90 low": lo, "CI90 high": hi, "note": a.get("flag")})
    return rows


# Plain-English meaning for each council round-trip verdict (display copy; the logic lives in dashboard_data).
_VERDICT_ICON = {
    "ROUNDTRIP_CONFIRMED": "✅", "PROPOSER_CLEAN_NO_ROUNDTRIP": "🟡",
    "ROUNDTRIP_DEGRADED": "⚠️", "PARSE_FAIL": "🚨", "NO_COUNCIL": "⏳",
}
_VERDICT_HELP = {
    "ROUNDTRIP_CONFIRMED": "Full 3-role debate fired and parsed cleanly (direction-relative adversary, "
                           "deliberated strategist). A no-entry result is still healthy — the gate may veto rich convexity.",
    "PROPOSER_CLEAN_NO_ROUNDTRIP": "Proposer parsed but judged everything NEUTRAL, so the adversary + strategist "
                                   "didn't fire. Benign, but they stay live-unconfirmed until an above-floor proposal exercises them.",
    "ROUNDTRIP_DEGRADED": "The debate fired but something's off — a degenerate row, a non-direction-relative "
                          "adversary, or $0 cost. Worth a look.",
    "PARSE_FAIL": "The council couldn't deliberate — a JSON parse failure (the #37 thinking-starvation class). This pages the operator.",
    "NO_COUNCIL": "No council has run on this DB yet.",
}

_T4_MARK = {"MET": "✅", "PASS": "✅", "NOT_OK": "❌", "BREACH": "🚨", "VACUOUS": "◻️", "IN_PROGRESS": "🔧", None: "⏳"}

_LEGEND = (
    "- **The five books** — **real** (the live paper book) · **shadow** (gate-on, no council → isolates the "
    "council's value) · **3A** (gate-off, same names → isolates the IV gate) · **3B** (gate-off, whole basket, "
    "equal-weight → beat-the-basket) · **shares** (linear stock, descriptive). All but *real* are "
    "simulated-only, **never** sent to the broker.\n"
    "- **Realized multiple (×)** — exit value ÷ entry premium of a closed bet. A few big winners carry a convex "
    "book, so the **p95 tail** is the read, not the mean.\n"
    "- **Brier** — forward calibration score for the council's conviction (lower = better; 0 = perfect).\n"
    "- **Accruing** — no positions have resolved yet (~6–12mo), so a metric is genuinely empty, not zero.\n"
    "- **The hard seam** — deterministic gates DISPOSE; the LLM council only PROPOSES. This surface is "
    "read-only and never trades."
)


def _render_health_risk(snap) -> None:
    st.caption("Is the book within its risk limits, and is the LLM council deliberating cleanly?")
    acct = snap.get("account")
    if _show(acct, "account"):
        be, dv = acct["broker_equity"], acct["delta_vs_frame"]
        a = st.columns(3)
        a[0].metric("Paper account equity", "—" if be is None else f"${be:,.2f}",
                    delta=None if dv is None else f"{dv:+,.2f} vs frame", delta_color="off",
                    help="Journal-sourced (runs.equity — the live loop records client.get_equity() "
                         "every cycle). The dashboard is keyless and never calls the broker.")
        a[1].metric("Headroom", f"${acct['headroom']:,.0f}",
                    delta=f"of ${acct['frame']['book_budget']:,.0f} budget", delta_color="off",
                    help="Book budget minus premium-at-risk currently deployed.")
        a[2].metric("Frame equity", f"${acct['frame']['frame_equity']:,.0f}",
                    help="The OPERATOR-FROZEN risk frame (PREREG §5) that sizes every cap. "
                         "It never floats with the broker number.")
        st.caption(f"as of {acct['as_of'] or '—'} (run #{acct['run_id'] or '—'}"
                   + (f", {acct['age_hours']}h ago" if acct["age_hours"] is not None else "")
                   + ") · journal-sourced, keyless · the risk frame is operator-FROZEN (PREREG §5) — "
                     "the broker number is informational and never resizes the frame.")
        if acct["equity_series"]:
            with st.expander("equity history (UTC days)"):
                import pandas as pd
                st.line_chart(pd.DataFrame({"equity": [r["equity"] for r in acct["equity_series"]]},
                                           index=[r["day"] for r in acct["equity_series"]]))
    risk = snap["risk"]
    if _show(risk, "risk"):
        kr, bk, cc = risk["kill_rule"], risk["book"], risk["cost_cap"]
        c = st.columns(4)
        c[0].metric("Book drawdown", f"{kr['book_drawdown']:.1%}",
                    delta="TRIPPED" if kr["tripped"] else f"halt @ {kr['drawdown_halt']:.0%}",
                    delta_color="inverse" if kr["tripped"] else "off",
                    help="Marked-down loss vs the book's premium budget. The kill rule halts all NEW entries at the halt threshold.")
        c[1].metric("Open positions", f"{bk['open']}/{bk['max']}",
                    help="Open option positions vs the concurrent cap (the frozen PREREG risk frame).")
        c[2].metric("Open premium", f"${bk['open_premium']:,.0f}", delta=f"of ${bk['budget']:,.0f} budget",
                    delta_color="off",
                    help="Premium-at-risk deployed vs the total book budget (~10% of account). Defined-risk, so this is the max loss.")
        c[3].metric("KILL switch", "ENGAGED" if risk["kill_switch_engaged"] else "off", delta_color="inverse",
                    help="The always-on manual halt (KILL file/env), checked every cycle.")
        st.caption(f"Cost-cap — last council health `{cc['last_council_health']}` · cap ${cc['cap_usd']:,.2f}"
                   + (" · ⚠ TRIPPED" if cc["tripped"] else ""))
        st.markdown("**Per-cluster exposure vs the correlation cap**")
        st.caption("Each correlated cluster is capped at ~2% of account (premium-at-risk) so a crowded theme "
                   "can't pass as diversification. The bar is the fraction of that cluster's cap in use.")
        crows = [{"cluster": r["cluster"], "premium": r["premium"], "cap": r["cap"],
                  "% of cap": round((r["frac"] or 0) * 100, 1), "directions": ", ".join(r["directions"])}
                 for r in risk["clusters"]]
        st.dataframe(crows, width="stretch", column_config={
            "premium": st.column_config.NumberColumn("premium", format="$%.0f"),
            "cap": st.column_config.NumberColumn("cap", format="$%.0f"),
            "% of cap": st.column_config.ProgressColumn("% of cap", min_value=0, max_value=100, format="%.0f%%")})

    if _show(snap["council"], "council"):
        cp = snap["council"]
        h = cp["health"]
        verdict = h.get("verdict", "—")
        st.markdown("**LLM council — latest L1 round-trip**")
        st.markdown(f"### {_VERDICT_ICON.get(verdict, '•')} {verdict.replace('_', ' ').title()}")
        st.caption(_VERDICT_HELP.get(verdict, ""))
        if verdict == "NO_COUNCIL":
            st.info("No council has run on this DB yet.")
        else:
            rt, pr = h.get("roundtrip", {}), h.get("proposer", {})
            c = st.columns(4)
            c[0].metric("Run", h.get("run_id", "—"), help="The L1 cycle id behind this verdict.")
            c[1].metric("Full round-trips", rt.get("n", "—"),
                        help="Names that got all 3 roles (proposer → adversary → strategist). The last two only fire on an above-floor proposal.")
            c[2].metric("Proposer parse-fails", f"{pr.get('parse_failed', '—')}/{pr.get('called', '—')}",
                        help="0 is healthy. The #37 bug was 100% parse-fail — a silent fail-closed to NEUTRAL.")
            c[3].metric("Council cost", f"${h.get('cost_usd', 0):.4f}",
                        help="LLM spend for this council run across all 3 providers.")
            if rt.get("strategist_abstained"):
                st.caption(f"🧠 strategist reasoned-abstained on {rt['strategist_abstained']} name(s) — a healthy exclude, not a failure.")
            ms = h.get("marker_staleness") or {}
            if ms.get("n_with_markers"):
                st.caption(
                    f"🕐 markers as-of: median {ms.get('median_age_days')}d · max {ms.get('max_age_days')}d "
                    f"({ms.get('max_age_symbol')}) over {ms['n_with_markers']} sentinel(s) — DIAGNOSTIC magnitude, "
                    "not an alarm (a large age on a quiet name is benign; catch-relevant 'stale ∧ moved' needs "
                    "the marker-refresh to detect). §7.1.")
        st.caption(f"models: {cp.get('model_mix') or '—'}")

        bp = cp.get("by_provider") or {}
        if bp:
            st.markdown("**Per-provider parse health** (latest run)")
            prov = [{"provider": k, "calls": v.get("calls"), "parse errors": v.get("parse_error"),
                     "error rate": round((v.get("parse_error_rate") or 0) * 100, 1)} for k, v in bp.items()]
            st.dataframe(prov, width="stretch", column_config={
                "error rate": st.column_config.ProgressColumn("error rate", min_value=0, max_value=100, format="%.0f%%")})

        recent = cp.get("recent") or []
        if recent:
            st.markdown("**Recent council runs** (oldest → newest — a regression shows here before it flips a checkmark)")
            provs = sorted({p for w in recent for p in (w.get("by_provider") or {})})
            strip = []
            for w in recent:
                row = {"run": f"#{w['run_id']}", "health": w["council_health"], "verdict": w["verdict"],
                       "proposer parse%": round((w.get("proposer_parse_rate") or 0) * 100, 1)}
                for p in provs:
                    row[f"{p} err%"] = round(((w.get("by_provider") or {}).get(p, {}).get("parse_error_rate") or 0) * 100, 1)
                strip.append(row)
            st.dataframe(strip, width="stretch")

        with st.expander("raw council-health JSON (for the curious)"):
            st.json(h)


def _render_performance(snap) -> None:
    st.caption("Does the convex book pay off in the tail? (accruing for ~6mo until positions resolve)")
    perf = snap["performance"]
    if not _show(perf, "performance"):
        return
    st.caption(perf["caveat"])
    ci = perf["p95_ci"]
    st.markdown("**Per-book realized-multiple tail** (p95 + bootstrap CI — substrate, no gap verdict)")
    if all(_is_accruing(v) for v in ci.values()):
        _accruing("each book's p95 realized-multiple with a bootstrap CI, side by side")
    else:
        st.dataframe(_ci_rows(ci), width="stretch",
                     column_config={"p95": st.column_config.NumberColumn("p95", format="%.2f×")})
    pb, hr = perf["premium_bled"], perf["hit_rate"]
    c = st.columns(3)
    c[0].metric("Premium paid", f"${pb['paid']:,.0f}", help="Σ premium over all booked bets (the max at risk).")
    c[1].metric("Bled (running)", f"{(pb['running_fraction'] or 0) * 100:.0f}%" if pb["running_fraction"] is not None else "—",
                delta=f"${pb['running_bled']:,.0f}", delta_color="off",
                help="Premium decayed so far = realized losses + mark-decay on open positions, ÷ paid.")
    c[2].metric("Hit rate", f"{hr['hit_rate'] * 100:.0f}%" if hr["hit_rate"] is not None else "accruing",
                delta=f"{hr['hits']}/{hr['closed']} closed", delta_color="off",
                help="Fraction of closed bets with positive P&L. Pairs with the calibration break-even hit-rate.")
    with st.expander("per-origin tails + raw"):
        st.json({"tails": perf["tails"], "real_by_origin": perf["real_by_origin"]})


def _render_nulls(snap) -> None:
    st.caption("Does the apparatus beat brain-off? Each step is one contrast; the VERDICT (significance) "
               "belongs to the blind/mature null layer — this is the plumbing, shown side by side.")
    nulls = snap["nulls"]
    if not _show(nulls, "nulls"):
        return
    for step in nulls["steps"]:
        badge = "🟦 clean (1 variable)" if step["clean"] else f"🟨 bundled — {step.get('bundled', '')}"
        extra = (f" · {step['censored_parse_fail_runs']} parse_fail run(s) censored"
                 if "censored_parse_fail_runs" in step else "")
        st.markdown(f"**{step['name']}** — {badge}{extra}")
        st.dataframe(_ci_rows(step["arms"]), width="stretch",
                     column_config={"p95": st.column_config.NumberColumn("p95", format="%.2f×")})
    st.caption(nulls["note"])


def _render_cheapness(snap) -> None:
    st.subheader("Cheapness-watch (finding #1)")
    st.caption("When a staged name BREAKS, is there a cheap-entry window, and does it co-occur with stale "
               "markers (the §7.1 harm)? `insufficient_N` is the EXPECTED reading — the harm is conjunctively "
               "rare; interpretable only once curation gives the cohort break-capable names (§2.1.7).")
    cw = snap["cheapness"]
    if not _show(cw, "cheapness"):
        return
    rate = cw.get("qualifying_per_quarter")
    rate_str = f" · {rate:.2f}/qtr" if rate is not None else ""
    st.markdown(f"**verdict: `{cw['verdict']}`** · breaks {cw['n_breaks']} "
                f"(qualifying {cw['n_qualifying']} · never-cheap {cw['n_never_cheap']} · "
                f"fresh-marker {cw['n_fresh_marker']}){rate_str}")
    # §2.1.7 fail-closed clock-start — why the RATE reads (or is None): the clock starts only once the
    # cohort holds a council-confirmed-quiet (under_narrated=True at first judgment) name.
    clk = cw.get("clock") or {}
    if clk.get("clock_started"):
        st.caption(f"§2.1.7 clock STARTED {clk.get('clock_start')} on `{clk.get('clock_start_symbol')}` "
                   f"(council-confirmed-quiet: {clk.get('n_confirmed_quiet_watched', 0)} watched)")
    else:
        st.caption("§2.1.7 clock NOT STARTED — no council-confirmed-quiet (under_narrated=True at first "
                   "judgment) name in the cohort yet → rate uninterpretable (fail-closed), not a clean negative.")
    # §2.1.8 — make the blindness visible: the reclassified/censored counts (0/0/0 is the healthy reading)
    st.caption(f"§2.1.8 reclassified out — degenerate_iv {cw.get('n_degenerate_iv', 0)} · "
               f"unmeasurable {cw.get('n_unmeasurable', 0)} · censored-short {cw.get('n_censored_short', 0)}")
    if cw.get("latest_by_name"):
        st.dataframe(cw["latest_by_name"], width="stretch")
    if cw.get("reclassified_rows"):   # the audit list — which bound tripped + the offending value
        st.caption("Reclassified rows (§2.1.8 audit — which bound + offending value):")
        st.dataframe(cw["reclassified_rows"], width="stretch")
    st.caption(cw["note"])


def _render_market(snap) -> None:
    st.caption("Is the thesis playing out on open positions, and what regime is convexity priced in?")
    mc = snap["market_ctx"]
    if not _show(mc, "market context"):
        return
    st.markdown("**Open positions — mark ÷ entry** (the robust 'is the thesis playing out' read)")
    if mc["open_positions"]:
        st.dataframe(mc["open_positions"], width="stretch", column_config={
            "mark_over_entry": st.column_config.NumberColumn("mark÷entry", format="%.2f×")})
    else:
        st.caption("No open positions.")
    c = st.columns(2)
    for col, key, label, helptext in (
        (c[0], "universe_iv_rv", "IV / RV regime",
         "ATM IV ÷ trailing realized vol across evaluated names. ≤1.2 is the gate's 'cheap'."),
        (c[1], "universe_otm_skew", "OTM skew regime",
         "OTM-wing minus ATM, in vol points, across evaluated names. ≤10 is the gate's 'cheap wing'."),
    ):
        d = mc[key]
        col.markdown(f"**{label}**")
        if d.get("n"):
            col.metric("median", f"{d['p50']}", help=helptext)
            col.caption(f"p90 {d['p90']} · max {d['max']} · n={d['n']}")
        else:
            col.caption("accruing — no evaluated names yet")
    st.caption("Current regime across the universe (a snapshot, not a 'cheap vs its own history' verdict). "
               "Distance-to-strike is deferred (a dormant name's cached spot lags).")


def _render_attribution(snap) -> None:
    st.caption("Where is P&L coming from, and is the council's conviction calibrated?")
    attr = snap["attribution"]
    if not _show(attr, "attribution"):
        return
    c = st.columns(2)
    for col, key, label in ((c[0], "pnl_by_theme", "P&L by theme"), (c[1], "pnl_by_cluster", "P&L by cluster")):
        col.markdown(f"**{label}** (realized + running)")
        d = attr[key]
        if d:
            rows = [{"group": g, "realized": v["realized"], "running": v["running"], "n": v["n"]}
                    for g, v in d.items()]
            col.dataframe(rows, width="stretch", column_config={
                "realized": st.column_config.NumberColumn("realized", format="$%.0f"),
                "running": st.column_config.NumberColumn("running", format="$%.0f")})
        else:
            col.caption("no booked positions yet")
    st.markdown("**Brier** (lower = better; forward calibration)")
    pbri, rc = attr["proposal_brier"], attr["role_contribution_brier"]
    cc = st.columns(1 + len(rc))
    cc[0].metric("strategist final", pbri["mean"] if pbri["mean"] is not None else "—",
                 help=f"Persisted strategist conviction Brier (n={pbri['n']}).")
    for col, (role, v) in zip(cc[1:], sorted(rc.items()), strict=False):
        col.metric(role, v["mean"], help=f"Per-role contribution Brier, recomputed (n={v['n']}).")
    if pbri["mean"] is None:
        st.caption("accruing — no resolved proposals yet")


def _render_funnel(snap) -> None:
    st.caption("Where do candidates stop — and why was each one judged the way it was?")
    fn = snap["funnel"]
    if _show(fn, "funnel"):
        d = fn["l1_decision"]
        st.markdown(f"**L1 decision funnel** (run #{d.get('run_id')})")
        cc = st.columns(4)
        cc[0].metric("proposed", d["proposed"], help="Candidates the council proposed this cycle.")
        cc[1].metric("evaluated", d["evaluated"], help="Candidates the deterministic gate evaluated.")
        cc[2].metric("opened", d["opened"], help="Positions actually opened (0 is healthy if nothing was cheap).")
        cc[3].metric("wasted LLM $", d["wasted_llm_spend"],
                     help="Proposals the council paid to judge that the gate then vetoed at eligibility/IV (the council runs before the gate).")
        if d.get("by_decision"):
            st.caption("by veto stage: " + " · ".join(f"{k}={v}" for k, v in d["by_decision"].items()))
        st.caption(f"L0 discovery (run #{fn['l0_discovery'].get('run_id')}): "
                   f"surfaced {fn['l0_discovery'].get('surfaced')} · controls {fn['l0_discovery'].get('controls')}")

    cs = snap.get("council_stage")
    if _show(cs, "council stage") and not cs.get("empty"):
        s, legs, br = cs["stages"], cs["legs"], cs["bridge"]
        st.markdown(f"**Council stage — where the debate stops** (run #{cs.get('run_id')}, floor {cs.get('floor')})")
        st.caption(
            f"proposed {s['proposed']} → asserted {s['asserted']} "
            f"(ungrounded {s['ungrounded']} · abstained {s['proposer_abstained']} · other {s['other']}) → "
            f"include-raw {s['strategist_include_raw']} → (criteria-veto {s['criteria_vetoed']}) → "
            f"(below-floor {s['below_floor']}) → **to-gate {s['to_gate']}**  ·  evaluated ≤ to-gate "
            f"(the gap = survivors a post-council close / kill-halt didn't reach)")
        n = legs["n_deliberated"]
        if n:
            cc = st.columns(3)
            cc[0].metric("structural", f"{legs['structural']}/{n}")
            cc[1].metric("under-narrated", f"{legs['under_narrated']}/{n}")
            cc[2].metric("at-inflection", f"{legs['at_inflection']}/{n}",
                         help="The tri-criteria each name must assert to be included. The lowest pass-rate is "
                              "the binding leg — but legs are independent, so it's an upper bound on the joint "
                              "pass-rate, not 'fix this one and trades unlock'.")
        st.caption("`abstained` includes proposer parse-failures — see the council-health panel.")
        if not br["ok"]:
            st.warning(f"reconstruction self-check FAILED: to_gate {br['to_gate']} ≠ survivors-by-status "
                       f"{br['survivors_by_status']} (a council_stage_funnel bug — inspect the rationale shape)")
    elif isinstance(cs, dict) and cs.get("empty"):
        st.caption("Council-stage breakout: no council run yet.")

    delib = snap["deliberation"]
    if isinstance(delib, dict) and delib.get("error"):
        st.warning(f"deliberation unavailable (fail-soft): {delib['error']}")
    elif delib:
        st.markdown("**Latest run — per-name deliberation** (the 'why': proposer → adversary → strategist)")
        st.dataframe(delib, width="stretch")
    else:
        st.caption("No council deliberation recorded yet.")

    if _show(snap["gate_reasons"], "gate reasons"):
        ivg = snap["gate_reasons"]["iv_gate"]
        st.markdown("**IV-gate vetoes**")
        cc = st.columns(3)
        cc[0].metric("total", ivg["total"])
        cc[1].metric("real (too rich)", ivg["real_veto"],
                     help="Vetoed because IV/RV or skew exceeded the cheap threshold — a real read.")
        cc[2].metric("fail-closed (missing data)", ivg["fail_closed_missing_data"],
                     help="Vetoed because an input was missing — fail-closed, NOT a richness read.")
        st.caption(f"eligibility vetoes: {snap['gate_reasons']['eligibility_vetoes']}")
    if _show(snap["cap_flow"], "cap flow"):
        cf = snap["cap_flow"]
        st.caption(f"cluster-cap rejections of otherwise-passing candidates: "
                   f"**{cf['cluster_cap_rejections_of_passing']}** ({cf['tightening_note']})")
    if _show(snap["cost"], "cost"):
        co = snap["cost"]
        st.markdown("**LLM cost ledger**")
        cc = st.columns(3)
        cc[0].metric("L0 framer", f"${co['l0_framer_usd']:.4f}", help="Weekly discovery framer spend.")
        cc[1].metric("L1 council", f"${co['l1_council_usd']:.4f}", help="Daily 3-role council spend.")
        cc[2].metric("cumulative", f"${co['cumulative_usd']:.4f}")


_DUALREAD_CLASS_LABELS = {
    "delta": "|Δ iv/rv| wire — the SOLE revert trigger",
    "material_flip": "material cheap-flip — investigate (no revert)",
    "gap_structural": "coverage gap · structural absence — feasibility (no revert)",
    "gap_transient": "coverage gap · transient — escalate ≥2/5 (no revert)",
    "entitlement": "entitlement lapse — feed-wide hold (no revert)",
}


def _render_dualread_runtime(rt) -> None:
    """The #72 §5 dual-read RUNTIME view: the per-class verdict, the Phase-3 revert latch, and the
    debounce/page summary — what the live ``dualread_executor`` would do (read-only)."""
    st.markdown("**§5 dual-read — runtime (#72)** "
                f"(rolling-{rt.get('window', 0)}; latest #{rt.get('last_run') if rt.get('last_run') is not None else '—'})")
    st.caption("The per-class response the live post-cycle executor would take. Each class routes to its own "
               "action; only the Δ wire can ever revert option_gate→indicative (and only with Phase 3 ON).")

    latch = rt.get("revert_latch", {})
    lc = st.columns(3)
    lc[0].metric("Phase 3 (revert latch)", "ON" if latch.get("enabled") else "OFF",
                 help="config.data_feed.dualread_revert_enabled — default OFF (the latch is inert on the live loop).")
    lc[1].metric("latched", "yes" if latch.get("latched") else "no",
                 help="The OPRA_REVERTED sentinel is present ⇒ the next cycle forces option_gate=indicative.")
    lc[2].metric("revert authorized", "yes" if latch.get("authorized") else "no",
                 help="Δ wire tripped AND Phase 3 ON — what the executor would write this cycle.")

    classes = rt.get("classes", {})
    table = [
        {"class": _DUALREAD_CLASS_LABELS.get(k, k),
         "tripped": "⚠ TRIPPED" if c.get("tripped") else "clear",
         "rolling-5": c.get("sessions"),
         "reverts?": "Δ (yes)" if c.get("revert") else "no",
         "paging now": ", ".join(c.get("pages") or []) or "—"}
        for k, c in classes.items()
    ]
    if table:
        st.dataframe(table, width="stretch", hide_index=True)

    # Debounce: which tripped names page now (rising edge) vs are suppressed (already alerted) under the
    # ≥N-consecutive re-arm — the UROY-pin made legible.
    deb = rt.get("debounce", {})
    rearm = deb.get("rearm_consecutive")
    paging, suppressed = [], []
    for cls in ("material_flip", "gap_structural", "gap_transient"):
        split = deb.get(cls, {})
        paging += [f"{n} ({cls})" for n in split.get("paging", [])]
        suppressed += [f"{n} ({cls})" for n in split.get("suppressed", [])]
    if paging or suppressed:
        st.caption(f"debounce (≥{rearm} consecutive clear sessions re-arm): "
                   f"paging now → {', '.join(paging) or '—'} · "
                   f"suppressed (already alerted) → {', '.join(suppressed) or '—'}")


def _render_scanning(snap) -> None:
    st.caption("What the scanner surfaced, what's in each book (with provenance), and what data has accrued.")
    if _show(snap.get("dualread"), "gate dual-read"):
        dr = snap["dualread"]
        tw = dr["tripwires"]
        tripped = tw["delta_tripped"] or tw["flip_tripped"] or tw["gap_tripped"]
        st.markdown("**OPRA gate dual-read** (gate-of-record = OPRA; INDICATIVE = the shadow arm — "
                    "veto-only, never authorizes)")
        st.caption(f"tripwires (rolling {tw['window']}): "
                   f"Δiv/rv breaches={tw['delta_breach_sessions']} · "
                   f"material-flip sessions={tw['flip_sessions']} (Δ≥{tw.get('flip_floor')}) · "
                   f"gap sessions={tw['gap_sessions']} → "
                   f"{'⚠ TRIPPED — §5 fail-closed response' if tripped else 'clear'} · "
                   f"disagree-veto until {dr['disagree_veto']['until']} "
                   f"({'active' if dr['disagree_veto']['active'] else 'lapsed/unset'})")
        if dr["sessions"]:
            st.dataframe(dr["sessions"], width="stretch")
        else:
            st.caption("no dual-read sessions yet (accruing from the first post-flip L1)")
    if _show(snap.get("dualread_runtime"), "dual-read runtime"):
        _render_dualread_runtime(snap["dualread_runtime"])
    if _show(snap["sentinels"], "sentinels"):
        se = snap["sentinels"]
        st.markdown(f"**Active sentinels** — {se['active_n']} active · {se['dormant']} dormant")
        if se["active"]:
            st.dataframe(se["active"], width="stretch")
        else:
            st.caption("no active sentinels")
        with st.expander("recent discovery runs"):
            st.dataframe(se["discovery_runs"], width="stretch")
    if _show(snap["positions"], "positions"):
        ps = snap["positions"]
        st.markdown("**Real book — open / pending** (with originating run + conviction)")
        if ps["real_open"]:
            st.dataframe(ps["real_open"], width="stretch")
        else:
            st.caption("real book is empty")
        if ps["pending"]:
            st.caption(f"⚠ {len(ps['pending'])} pending (watch for stale-pending)")
        st.markdown("**Null books** — simulated-only, never broker")
        for k, label in (("shadow_open", "shadow (gate-on, no council)"),
                         ("nogate_3A_open", "3A (gate-off, same names)"),
                         ("nogate_3B_open", "3B (gate-off, whole basket)"),
                         ("shares", "shares (linear)")):
            rows = ps[k]
            with st.expander(f"{label} — {len(rows)} rows"):
                st.dataframe(rows, width="stretch") if rows else st.caption("empty")
    if _show(snap["curation"], "curation"):
        cu = snap["curation"]
        with st.expander("cluster diagnostic (the correlation backstop for the cluster map)"):
            st.json(cu["cluster"])
        with st.expander("basket quality (the survivorship → curation loop)"):
            st.json(cu["basket"])
    if _show(snap["data_gathered"], "data gathered"):
        dg = snap["data_gathered"]
        cg = dg.get("chain_snapshots", {})
        st.markdown("**Data gathered** — the forward IV baseline accruing")
        cc = st.columns(3)
        cc[0].metric("chain-snapshot symbols", cg.get("symbols", 0))
        cc[1].metric("bar-coverage symbols", dg.get("bar_coverage_symbols", 0))
        cc[2].metric("latest snapshot", (cg.get("latest") or "—")[:10] if cg.get("latest") else "—")


def main() -> None:
    st.set_page_config(page_title="Dramatic Options — observability", layout="wide")
    config = load_config()
    paths = dd.resolve_paths(config)

    with st.sidebar:
        st.header("Dramatic Options")
        st.caption("read-only · NO-FETCH · fail-soft · observation-only")
        st.code(paths["db_path"], language=None)
        if paths.get("from_env"):
            st.caption("DB from $DRAMATIC_DB")
        if st.button("↻ Refresh", width="stretch"):
            st.session_state["_nonce"] = st.session_state.get("_nonce", 0) + 1
            st.cache_data.clear()

    snap = load_all(paths["db_path"], paths["cache_dir"], paths["db_exists"], st.session_state.get("_nonce", 0))
    if snap.get("_fatal"):
        st.error(snap["_fatal"])
        return

    # ── one-glance system status (the headline) ──
    status = dd.system_status(snap)
    {"error": st.error, "warn": st.warning, "success": st.success}[status["level"]](status["headline"])
    if status["issues"]:
        st.caption("wants a look: " + " · ".join(status["issues"]))
    with st.expander("ℹ️ How to read this"):
        st.markdown(_LEGEND)

    header = snap["header"]
    if _show(header, "header"):
        if header.get("schema_warning"):
            st.warning(f"⚠ {header['schema_warning']}")
        cols = st.columns(5)
        cols[0].metric("schema", header["schema_version"], help="DB migration version vs what the dashboard expects.")
        cols[1].metric("KILL", "ENGAGED" if header["kill_switch_engaged"] else "off",
                       help="The always-on manual halt, checked every cycle.")
        for col, key, helptext in (
            (cols[2], "cycle", "L1∪L2 loop liveness (market-aware: weekends don't false-alarm)."),
            (cols[3], "council", "Last L1 that deliberated (market-aware daily cadence)."),
            (cols[4], "discovery", "Weekly L0 discovery scan."),
        ):
            beat = header[key]
            age = beat["age_hours"]
            col.metric(f"last {key}", "—" if age is None else f"{age:.0f}h ago",
                       delta=(beat["status"] if beat["status"] != "ONLINE" else None), delta_color="inverse",
                       help=helptext)

    # ── the regime strip (configuration of record — the record-segmentation keys; a readout, no verdicts)
    regime = snap.get("regime")
    if _show(regime, "regime"):
        f, c, v = regime["feeds"], regime["council"], regime["dualread_veto"]
        veto_txt = ""
        if v["until"]:
            veto_txt = (f" · disagree-veto lapses {v['until']} ({v['days_remaining']}d)" if v["active"]
                        else f" · disagree-veto lapsed {v['until']}")
        st.caption(f"regime — feeds (run #{f['run_id'] or '—'}, {f['as_of'] or '—'}): "
                   f"gate {f['option_gate'] or '—'} · bars {f['equity_bars'] or '—'} · "
                   f"monitor {f['option_monitor'] or '—'}{veto_txt} · frame {f['frame_version'] or '—'}")
        models = " · ".join(f"{r} {m}" for r, m in c["models"].items()) or "—"
        extras = " · ".join(f"{k} {val}" for k, val in c["extras"].items())
        st.caption(f"council (run #{c['run_id'] or '—'}, {c['as_of'] or '—'}): "
                   f"health {c['council_health'] or '—'} · {models}"
                   + (f" · {extras}" if extras else ""))

    st.subheader("T4-readiness scoreboard")
    st.caption("**Automatable checks only — NOT a go signal.** Conditions 2 & 4 need ~6 months of resolved "
               "positions and stay verdict-less; T4 (real-money go-live) is the operator's decision.")
    t4 = snap["t4"]
    if _show(t4, "T4 scoreboard"):
        checkable = [c for c in t4["conditions"] if c["checkable"]]
        met = [c for c in checkable if c["verdict"] in ("MET", "PASS")]
        accruing = [c for c in t4["conditions"] if not c["checkable"]]
        st.caption(f"{len(met)}/{len(checkable)} automatable checks pass · {len(accruing)} conditions accruing (no verdict)")
        for c in t4["conditions"]:
            mark = _T4_MARK.get(c["verdict"], "⏳")
            tag = "" if c["checkable"] else " · (accruing — verdict deferred)"
            st.markdown(f"{mark} **({c['id']}) {c['name']}** — {c['verdict'] or 'accruing'}{tag}  \n"
                        f"&nbsp;&nbsp;&nbsp;{c['detail']}")

    tabs = st.tabs(["🩺 Health & Risk", "📈 Performance", "🧪 Null books — does the brain help?",
                    "🌡️ Market context", "🧭 Attribution", "🚦 Funnel — where trades stop",
                    "🔍 Scanning · positions · data"])
    with tabs[0]:
        _render_health_risk(snap)
    with tabs[1]:
        _render_performance(snap)
    with tabs[2]:
        _render_nulls(snap)
    with tabs[3]:
        _render_market(snap)
    with tabs[4]:
        _render_attribution(snap)
    with tabs[5]:
        _render_funnel(snap)
    with tabs[6]:
        _render_scanning(snap)
        _render_cheapness(snap)


if __name__ == "__main__":
    main()
