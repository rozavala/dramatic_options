"""§5b observability dashboard — the thin Streamlit shell.

ALL data/compute lives in `dashboard_data` (pure, streamlit-free, tested); this file only renders. It is
**read-only** (`?mode=ro`), **NO-FETCH** (`MarketData(client=None)`), **fail-soft** (every panel via
`dd.safe`), and observation-only (never edits clusters/themes/config, never a trade/auth path).

Run it where the live state lives, and bind to localhost only — it renders the whole book + the cluster map
(operator-confidential), so never expose it on a public port:

    pip install -r requirements-dashboard.txt
    # Run from the live checkout so the relative DB path resolves to the live DB (or set DRAMATIC_DB /
    # DRAMATIC_CACHE_DIR explicitly). `.streamlit/config.toml` pins PORT 8502 + localhost so it NEVER
    # collides with the real_options dashboard on 8501; pass --server.port / --server.address to override
    # (e.g. the tailnet IP for remote access — but it renders the whole book + cluster map, so prefer a tunnel).
    DRAMATIC_DB=~/dramatic_options/data/dramatic_options.db \
    DRAMATIC_CACHE_DIR=~/dramatic_options/data/cache \
    streamlit run dashboard.py --server.port 8502

The performance/null panels are EMPTY (accruing) for ~6mo until positions resolve — they render "n=0 /
accruing" by design, never a misleading "0.0×".
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
            "sentinels": dd.safe(dd.sentinels_panel, conn),
            "positions": dd.safe(dd.positions_panel, conn),
            "council": dd.safe(dd.council_panel, conn, config),
            "performance": dd.safe(dd.performance_panel, conn),
            "nulls": dd.safe(dd.null_hierarchy, conn),
            "attribution": dd.safe(dd.attribution_panel, conn, config),
            "funnel": dd.safe(dd.funnel_panel, conn),
            "gate_reasons": dd.safe(dd.gate_reasons, conn),
            "cap_flow": dd.safe(dd.cap_binding_flow, conn),
            "cost": dd.safe(dd.cost_ledger, conn),
            "market_ctx": dd.safe(dd.market_context, conn),
            "curation": dd.safe(dd.curation_panel, conn, config, market),
            "data_gathered": dd.safe(dd.data_gathered_panel, cache_dir),
        }
    finally:
        conn.close()


def _err(panel: dict) -> str | None:
    return panel.get("error") if isinstance(panel, dict) else None


def _show(panel: dict, label: str = "") -> bool:
    """Render a panel's error box if it failed; return True if OK to render the body."""
    e = _err(panel)
    if e:
        st.warning(f"{label or 'panel'} unavailable (fail-soft): {e}")
        return False
    return True


def main() -> None:
    st.set_page_config(page_title="Dramatic Options — observability", layout="wide")
    config = load_config()
    paths = dd.resolve_paths(config)

    # ── sidebar: which DB, schema, heartbeat, KILL, refresh ──
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

    header = snap["header"]
    if _show(header, "header"):
        if header.get("schema_warning"):
            st.warning(f"⚠ {header['schema_warning']}")
        cols = st.columns(5)
        cols[0].metric("schema", header["schema_version"])
        cols[1].metric("KILL", "ENGAGED" if header["kill_switch_engaged"] else "off")
        for col, key in ((cols[2], "cycle"), (cols[3], "council"), (cols[4], "discovery")):
            beat = header[key]
            age = beat["age_hours"]
            col.metric(f"last {key}", "—" if age is None else f"{age:.0f}h ago",
                       delta=(beat["status"] if beat["status"] != "ONLINE" else None), delta_color="inverse")

    st.subheader("T4-readiness scoreboard")
    st.caption("A scoreboard, not a graduation verdict — conditions 2 & 4 are plumbing/accruing (no checkmark).")
    t4 = snap["t4"]
    if _show(t4, "T4 scoreboard"):
        for c in t4["conditions"]:
            mark = {"MET": "✅", "PASS": "✅", "NOT_OK": "❌", "BREACH": "🚨",
                    "VACUOUS": "◻️", "IN_PROGRESS": "🔧", None: "⏳"}.get(c["verdict"], "⏳")
            tag = "" if c["checkable"] else " · (accruing — verdict deferred)"
            st.markdown(f"{mark} **({c['id']}) {c['name']}** — {c['verdict'] or 'accruing'}{tag}  \n"
                        f"&nbsp;&nbsp;&nbsp;{c['detail']}")

    tabs = st.tabs(["A · health/risk", "B · performance", "C · nulls", "D · market",
                    "E · drivers", "F · bottleneck", "G · scanning/positions/data"])

    with tabs[0]:
        risk = snap["risk"]
        if _show(risk, "risk"):
            kr = risk["kill_rule"]
            st.metric("book drawdown", f"{kr['book_drawdown']:.1%}",
                      delta="TRIPPED" if kr["tripped"] else f"halt @ {kr['drawdown_halt']:.0%}",
                      delta_color="inverse" if kr["tripped"] else "off")
            st.write(f"open positions: **{risk['book']['open']}/{risk['book']['max']}** · "
                     f"open premium ${risk['book']['open_premium']:,.0f} / ${risk['book']['budget']:,.0f}")
            st.write(f"cost-cap: last council health = `{risk['cost_cap']['last_council_health']}`"
                     f"{' · TRIPPED' if risk['cost_cap']['tripped'] else ''}")
            st.markdown("**Per-cluster exposure vs cap**")
            st.dataframe(risk["clusters"], width="stretch")
        if _show(snap["council"], "council"):
            st.markdown("**Council health (latest L1)**")
            st.json(snap["council"]["health"], expanded=False)
            st.markdown("**Per-provider parse/error rate**")
            st.json(snap["council"]["by_provider"], expanded=False)
            st.caption(f"model_mix: {snap['council']['model_mix']}")

    with tabs[1]:
        perf = snap["performance"]
        if _show(perf, "performance"):
            st.caption(perf["caveat"])
            st.markdown("**Per-book realized-multiple tails**")
            st.json(perf["tails"], expanded=False)
            st.markdown("**Per-book p95 + bootstrap CI** (substrate — small-n suppressed; no gap verdict)")
            st.json(perf["p95_ci"], expanded=True)
            st.markdown("**Real book by origin (hand_seed vs sentinel)**")
            st.json(perf["real_by_origin"], expanded=False)
            c = st.columns(2)
            c[0].markdown("**Premium bled vs paid**")
            c[0].json(perf["premium_bled"])
            c[1].markdown("**Hit rate**")
            c[1].json(perf["hit_rate"])

    with tabs[2]:
        nulls = snap["nulls"]
        if _show(nulls, "nulls"):
            st.caption(nulls["note"])
            for step in nulls["steps"]:
                tag = "clean (1 variable)" if step["clean"] else f"BUNDLED — {step.get('bundled', '')}"
                st.markdown(f"**{step['name']}** — _{tag}_"
                            + (f" · {step['censored_parse_fail_runs']} parse_fail runs censored"
                               if "censored_parse_fail_runs" in step else ""))
                st.json(step["arms"], expanded=False)

    with tabs[3]:
        mc = snap["market_ctx"]
        if _show(mc, "market context"):
            st.markdown("**Open positions — mark ÷ entry** (the robust 'is the thesis playing out' signal)")
            st.dataframe(mc["open_positions"], width="stretch")
            c = st.columns(2)
            c[0].markdown("**Universe IV/RV regime**")
            c[0].json(mc["universe_iv_rv"])
            c[1].markdown("**Universe OTM skew regime**")
            c[1].json(mc["universe_otm_skew"])
            st.caption("distance-to-strike deferred (cached-snapshot as-of; a dormant name's spot lags).")

    with tabs[4]:
        attr = snap["attribution"]
        if _show(attr, "attribution"):
            c = st.columns(2)
            c[0].markdown("**P&L by theme** (realized + running)")
            c[0].json(attr["pnl_by_theme"], expanded=False)
            c[1].markdown("**P&L by cluster**")
            c[1].json(attr["pnl_by_cluster"], expanded=False)
            st.markdown("**Brier** — strategist final (persisted) + per-role contribution (recomputed)")
            st.json({"proposal_brier": attr["proposal_brier"],
                     "role_contribution_brier": attr["role_contribution_brier"]}, expanded=False)

    with tabs[5]:
        fn = snap["funnel"]
        if _show(fn, "funnel"):
            st.markdown("**L1 decision funnel** (the bottleneck view)")
            st.json(fn["l1_decision"], expanded=True)
            st.markdown("**L0 discovery funnel**")
            st.json(fn["l0_discovery"], expanded=False)
        if _show(snap["gate_reasons"], "gate reasons"):
            st.markdown("**Veto reasons + fail-closed-on-missing-data**")
            st.json(snap["gate_reasons"], expanded=False)
        if _show(snap["cap_flow"], "cap flow"):
            st.json(snap["cap_flow"])
        if _show(snap["cost"], "cost"):
            st.markdown("**Cost ledger (per stage + cumulative)**")
            st.json(snap["cost"])

    with tabs[6]:
        if _show(snap["sentinels"], "sentinels"):
            st.markdown(f"**Active sentinels** ({snap['sentinels']['active_n']}) · "
                        f"dormant {snap['sentinels']['dormant']}")
            st.dataframe(snap["sentinels"]["active"], width="stretch")
            st.caption("recent discovery runs")
            st.json(snap["sentinels"]["discovery_runs"], expanded=False)
        if _show(snap["positions"], "positions"):
            st.markdown("**Real book — open/pending**")
            st.dataframe(snap["positions"]["real_open"], width="stretch")
            if snap["positions"]["pending"]:
                st.caption(f"{len(snap['positions']['pending'])} pending (watch stale-pending)")
            st.markdown("**Null books (shadow / 3A / 3B / shares)**")
            for k in ("shadow_open", "nogate_3A_open", "nogate_3B_open", "shares"):
                st.caption(k)
                st.dataframe(snap["positions"][k], width="stretch")
        if _show(snap["curation"], "curation"):
            st.markdown("**Cluster diagnostic**")
            st.json(snap["curation"]["cluster"], expanded=False)
            st.markdown("**Basket quality**")
            st.json(snap["curation"]["basket"], expanded=False)
        if _show(snap["data_gathered"], "data gathered"):
            st.markdown("**Data gathered (chain snapshots = the forward IV baseline)**")
            st.json(snap["data_gathered"], expanded=False)


if __name__ == "__main__":
    main()
