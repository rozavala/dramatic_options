// fromBackend(panels) → ViewModel — ported from the prototype's static adapter (Dramatic Options
// Dashboard.dc.html), the field-by-field spec. FOUR reconciliations vs the prototype, each marked:
//   #1 system_status — the API injects it (dd.system_status runs over the assembled snapshot; it is NOT a
//      load_all panel). The prototype read panels.system_status, which is correct once injected. ✓
//   #2 council_stage is a TOP-LEVEL panel (the prototype read panels.funnel.council_stage). Read it directly.
//   #3 positions: mark÷entry is NOT on the position row — it is market_ctx.open_positions[].mark_over_entry,
//      joined here by contract_symbol. `theme` IS emitted by positions_panel (dashboard_data.py SELECT p.theme).
//   #4 sentinel `note` ("rv-slope · 4d") is composed (trigger + age) — not a raw column; best-effort here.

import type {
  AttemptsVM, BooksOpenVM, CanaryVM, DataAccrualVM, DeliberationVM, DualReadRuntimeClassVM, DualReadRuntimeVM,
  NullStepVM, PositionVM, CatalystVM, ProviderVM, ReserveSlotVM, ReserveVM, SentinelVM, SessionRowVM, SessionVM,
  Snapshot, SpendVM, ViewModel,
} from "./types";
import { directionLabel, levelFromSystem, t4RowState, verdictDisplay } from "./status";

const DASH = "—";
// The "first null read" sample target (PREREG_FIXED_BASKET_NULL — the calibration cohort size). No config
// field carries it on the wire, so it lives here as ONE named constant rather than a buried literal (A4).
const EDGE_TARGET = 30;

const fmt = (v: number | null | undefined): string =>
  v == null ? DASH : "$" + Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
const pct = (v: number | null | undefined): string => (v == null ? DASH : (v * 100).toFixed(1) + "%");
const ageH = (b?: { age_hours: number | null } | null): string =>
  b && b.age_hours != null ? Math.round(b.age_hours) + "h" : DASH;
const beatLevel = (b?: { status?: string } | null) => (b && b.status && b.status !== "ONLINE" ? "warn" : "ok");
const ci = (c?: { n?: number; p95?: number | null } | null) => ({ n: c?.n ?? 0, p95: c?.p95 ?? null });
const usd = (v: number | null | undefined, dp = 3): string => "$" + Number(v ?? 0).toFixed(dp);

// A fail-soft panel (dd.safe) comes back as {"error": "..."}. Detect it so a crashed panel reads as
// "unavailable", not as a present-but-empty 0/— (B1). Returns the error string, or null if the panel is fine.
function panelError(p: unknown): string | null {
  if (p && typeof p === "object" && "error" in p) {
    const e = (p as { error?: unknown }).error;
    if (typeof e === "string") return e;
  }
  return null;
}

function ageDays(iso?: string): number | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  return Math.max(0, Math.round((Date.now() - t) / 86_400_000));
}

// Compose the sentinel trigger note from the active row (refine once the markers shape is pinned).
function sentinelNote(s: Snapshot["sentinels"]["active"][number]): string {
  if (typeof s.note === "string" && s.note) return s.note;
  const trig = s.structural_vs_fad === "structural" ? "structural" : "motion";
  const d = ageDays(s.last_seen_at ?? s.discovered_at);
  return d == null ? trig : `${trig} · ${d}d`;
}

// model_mix is a JSON blob {proposer, adversary, strategist, …}; show the three role models (sans provider).
function modelMixSummary(raw: string | null): string {
  if (!raw) return "—";
  try {
    const m = JSON.parse(raw) as Record<string, unknown>;
    const names = ["proposer", "adversary", "strategist"]
      .map((r) => m[r])
      .filter(Boolean)
      .map((v) => String(v).split("/").pop());
    return names.length ? names.join(" · ") : "—";
  } catch {
    return "—";
  }
}

// A3: trailing ROUNDTRIP_CONFIRMED runs from the recent_council_health window (oldest→newest). Saturates at
// the window length (the backend caps it at RECENT_COUNCIL_N), so phrase "N clean" / "N clean, then #id".
function councilStreak(recent: Snapshot["council"]["recent"] | undefined): string {
  const r = recent ?? [];
  if (!r.length) return "—";
  let s = 0;
  for (let i = r.length - 1; i >= 0 && r[i].verdict === "ROUNDTRIP_CONFIRMED"; i--) s++;
  if (s === r.length) return `${s} clean`;
  const broke = r[r.length - 1 - s];
  return s === 0 ? `0 · #${broke.run_id} not clean` : `${s} clean, then #${broke.run_id}`;
}

export function fromBackend(P: Snapshot): ViewModel {
  const ss = P.system_status ?? ({} as Snapshot["system_status"]);          // #1 (API-injected)
  const h = P.header ?? ({} as Snapshot["header"]);
  const acc = P.account ?? ({} as Snapshot["account"]);
  const rk = P.risk ?? ({} as Snapshot["risk"]);
  const ch = P.council?.health ?? ({} as Snapshot["council"]["health"]);
  const pf = P.performance ?? ({} as Snapshot["performance"]);
  const ciP = pf.p95_ci ?? ({} as Snapshot["performance"]["p95_ci"]);
  const pbd = pf.premium_bled ?? ({} as Snapshot["performance"]["premium_bled"]);
  const hr = pf.hit_rate ?? ({} as Snapshot["performance"]["hit_rate"]);
  const at = P.attribution ?? ({} as Snapshot["attribution"]);
  const l1 = P.funnel?.l1_decision ?? ({} as Snapshot["funnel"]["l1_decision"]);
  const cs = P.council_stage?.stages ?? ({} as NonNullable<Snapshot["council_stage"]["stages"]>); // #2 top-level
  const gr = P.gate_reasons ?? ({} as Snapshot["gate_reasons"]);
  const ivg = gr.iv_gate ?? ({} as Snapshot["gate_reasons"]["iv_gate"]);
  const ps = P.positions ?? ({} as Snapshot["positions"]);
  const se = P.sentinels ?? ({} as Snapshot["sentinels"]);
  const mc = P.market_ctx ?? ({} as Snapshot["market_ctx"]);
  const dg = P.data_gathered ?? ({} as Snapshot["data_gathered"]);
  const cgs = dg.chain_snapshots ?? { symbols: 0, latest: null };

  const [verdictLabel, vlevel] = verdictDisplay(ch.verdict);

  // B1: which panels came back {error} (fail-soft) — surfaced as inline banners so a crashed panel can't pass
  // for "genuinely accruing". (Panels not in this list either can't error or aren't rendered.)
  const degraded = (
    [
      ["header", P.header], ["account", P.account], ["risk", P.risk], ["council", P.council],
      ["performance", P.performance], ["attribution", P.attribution], ["funnel", P.funnel],
      ["council_stage", P.council_stage], ["gate_reasons", P.gate_reasons], ["positions", P.positions],
      ["sentinels", P.sentinels], ["market_ctx", P.market_ctx], ["t4", P.t4], ["nulls", P.nulls],
      ["dualread", P.dualread], ["dualread_runtime", P.dualread_runtime], ["cost", P.cost],
      ["deliberation", P.deliberation], ["cap_flow", P.cap_flow], ["reserve", P.reserve],
      ["forward_catalysts", P.forward_catalysts],
      ["null_attempts", P.null_attempts],
      ["data_gathered", P.data_gathered], ["cheapness", P.cheapness],
      ["session", P.session], ["spend", P.spend], ["canary", P.canary],
    ] as [string, unknown][]
  )
    .filter(([, p]) => panelError(p))
    .map(([k]) => k);

  // #3 join mark÷entry from market_ctx by contract_symbol (it is not on the position row).
  const markByContract = new Map((mc.open_positions ?? []).map((o) => [o.contract, o.mark_over_entry] as const));
  const positions: PositionVM[] = (ps.real_open ?? []).map((p) => ({
    symbol: p.symbol, theme: p.theme ?? null, dir: p.direction, conviction: p.origin_conviction, dte: p.dte,
    premium: fmt(p.total_premium), premiumUsd: Number(p.total_premium ?? 0),
    mark: markByContract.get(p.contract_symbol) ?? p.mark ?? null, opened: p.opened_at ? String(p.opened_at).slice(0, 10) : null,
  }));
  const sentinels: SentinelVM[] = (se.active ?? []).map((x) => ({ symbol: x.symbol, basket: x.basket, dir: x.direction, note: sentinelNote(x) })); // #4

  // A1: readiness is driven off the backend `checkable` flag (NOT the verdict→state map) so the headline
  // matches dashboard.py: pass/checkable over checkable conditions, accruing = the non-checkable ones.
  const condsRaw = P.t4?.conditions ?? [];
  const cond = condsRaw.map((c) => ({ id: c.id, name: c.name, detail: c.detail, verdict: c.verdict, state: t4RowState(c.checkable, c.verdict) }));
  const checkable = condsRaw.filter((c) => c.checkable);
  const readiness = {
    pass: checkable.filter((c) => c.verdict === "MET" || c.verdict === "PASS").length,
    checkable: checkable.length,
    accruing: condsRaw.filter((c) => !c.checkable).length,
  };

  // C: the null hierarchy — flatten each step's arms dict → an ordered [{label, ci}] list for rendering.
  const nulls: NullStepVM[] = (P.nulls?.steps ?? []).map((s) => ({
    name: s.name, clean: s.clean, bundled: s.bundled ?? null, censored: s.censored_parse_fail_runs ?? null,
    arms: Object.entries(s.arms ?? {}).map(([label, c]) => ({ label, ci: ci(c) })),
  }));

  // C: the OPRA dual-read soak — latest session stats + the rolling-5 tripwire status + the veto window.
  const dr = P.dualread;
  const tw = dr?.tripwires;
  const drLast = dr?.sessions?.[dr.sessions.length - 1];
  const dualread = {
    sessions: dr?.n_sessions_total ?? 0, lastRun: drLast?.run_id ?? null,
    medianD: drLast?.median_d_ivrv ?? null, maxD: drLast?.max_d_ivrv ?? null,
    opraCov: drLast?.opra_coverage ?? null, indCov: drLast?.indicative_coverage ?? null,
    window: tw?.window ?? 0,
    deltaTripped: tw?.delta_tripped ?? false, flipTripped: tw?.flip_tripped ?? false, gapTripped: tw?.gap_tripped ?? false,
    flipFloor: tw?.flip_floor ?? 0.02,
    deltaSessions: tw?.delta_breach_sessions ?? 0, flipSessions: tw?.flip_sessions ?? 0, gapSessions: tw?.gap_sessions ?? 0,
    vetoUntil: dr?.disagree_veto?.until ?? null, vetoActive: dr?.disagree_veto?.active ?? null,
  };

  // #72: the §5 dual-read RUNTIME view — per-class verdict + the Phase-3 revert latch + the debounce split.
  // Maps the dualread_runtime panel 1:1 (the per-class math is single-sourced server-side; we only label/flatten).
  const RT_LABELS: Record<string, string> = {
    delta: "Δ iv/rv wire (sole revert)", material_flip: "material cheap-flip",
    gap_structural: "coverage gap · structural", gap_transient: "coverage gap · transient",
    entitlement: "entitlement (feed-wide)",
  };
  const rt = P.dualread_runtime;
  const rtClasses: DualReadRuntimeClassVM[] = Object.entries(rt?.classes ?? {}).map(([key, c]) => ({
    key, label: RT_LABELS[key] ?? key, tripped: c.tripped, sessions: c.sessions ?? null,
    pages: c.pages ?? [], reverts: c.revert,
  }));
  const rtSplit = (which: "material_flip" | "gap_structural" | "gap_transient", kind: "paging" | "suppressed") =>
    (rt?.debounce?.[which]?.[kind] ?? []).map((n) => `${n} (${which})`);
  const dualreadRuntime: DualReadRuntimeVM = {
    window: rt?.window ?? 0, lastRun: rt?.last_run ?? null,
    phase3: rt?.revert_latch?.enabled ?? false, latched: rt?.revert_latch?.latched ?? false,
    authorized: rt?.revert_latch?.authorized ?? false, rearm: rt?.debounce?.rearm_consecutive ?? 4,
    classes: rtClasses,
    paging: [...rtSplit("material_flip", "paging"), ...rtSplit("gap_structural", "paging"), ...rtSplit("gap_transient", "paging")],
    suppressed: [...rtSplit("material_flip", "suppressed"), ...rtSplit("gap_structural", "suppressed"), ...rtSplit("gap_transient", "suppressed")],
  };

  // C: LLM cost ledger — prefer council.cost (the same ledger, always alongside health), else the top-level panel.
  const costSrc = (P.council?.cost ?? P.cost ?? {}) as { l0_framer_usd?: number; l1_council_usd?: number; cumulative_usd?: number };
  const cost = { framer: usd(costSrc.l0_framer_usd, 4), council: usd(costSrc.l1_council_usd), cumulative: usd(costSrc.cumulative_usd) };

  // C: latest run's per-name deliberation (the "why").
  const delibRows = Array.isArray(P.deliberation) ? P.deliberation : [];
  const deliberation: DeliberationVM = {
    runId: delibRows[0]?.run_id ?? null,
    rows: delibRows.map((d) => ({ symbol: d.symbol, dir: d.proposer_direction, adversary: d.adversary_stance, conviction: d.strategist_conviction })),
  };

  // C: per-provider parse health (scoped to the latest run by council_panel).
  const byProvider: ProviderVM[] = Object.entries(P.council?.by_provider ?? {}).map(([provider, v]) => ({
    provider, calls: v.calls ?? 0, parseError: v.parse_error ?? 0, rate: v.parse_error_rate ?? null,
  }));

  // C: judged-set provenance — the gate-cheap reserve vs the motion rank. Stamp absent = reserve OFF or a
  // pre-deploy run; the panel then emits `unlabeled` rows and we render OFF — never invent provenance.
  const rvP = panelError(P.reserve) ? null : P.reserve;
  const slotVM = (via: ReserveSlotVM["via"]) => (s: { symbol: string; conviction: string | null; status: string | null }): ReserveSlotVM =>
    ({ symbol: s.symbol, conviction: s.conviction ?? DASH, status: s.status ?? DASH, via });
  const reserve: ReserveVM = {
    runId: rvP?.run_id ?? null, stamp: rvP?.stamp ?? null,
    slots: [
      ...(rvP?.reserve ?? []).map(slotVM("reserve")),
      ...(rvP?.rank ?? []).map(slotVM("rank")),
      ...(rvP?.fairness ?? []).map(slotVM("fairness")),
      ...(rvP?.unlabeled ?? []).map(slotVM("unlabeled")),
    ],
  };

  // C: the null-book entry walk (migration 0018) — per capped book, walk order, terminal outcome + premium.
  const naP = panelError(P.null_attempts) ? null : P.null_attempts;
  const attempts: AttemptsVM = {
    runId: naP?.run_id ?? null,
    books: Object.entries(naP?.books ?? {}).map(([book, b]) => ({
      book,
      rows: (b?.rows ?? []).map((r) => ({
        idx: r.attempt_idx, symbol: r.symbol, origin: r.origin ?? DASH, outcome: r.outcome ?? DASH,
        premium: r.entry_premium_per_contract ?? null,
      })),
    })),
  };

  // The forward-catalyst channel — render the record, never a verdict (the M=8 read is the operator's).
  const fcP = panelError(P.forward_catalysts) ? null : P.forward_catalysts;
  const fcC = fcP?.counters ?? null;
  const fcL = fcP?.ledger ?? null;
  const catalysts: CatalystVM = {
    stamp: fcP?.stamp ?? null,
    countersLine: fcC
      ? `rendered ${fcC.rendered} · expired ${fcC.expired} · malformed ${fcC.malformed} · stale ${fcC.stale_flagged}`
      : null,
    countersRunId: fcP?.counters_run_id ?? null,
    pins: (fcP?.pins ?? []).map((p) => ({
      symbol: p.symbol ?? DASH, cls: p.class ?? DASH, eventDate: p.event_date ?? null,
      asOf: p.as_of ?? DASH, expires: p.expires ?? DASH,
    })),
    pinsFileMissing: fcP?.pins_file_missing ?? false,
    ledgerLine: fcL
      ? `${fcL.eligible}/${fcP?.m_target ?? 8} eligible pairs · flips ${fcL.flips} · cites ${fcL.cites} · voids ${fcL.void} · reverse ${fcL.reverse_conversions}`
      : null,
    bySymbol: fcL ? Object.entries(fcL.by_symbol).map(([k, v]) => `${k} ${v}`).join(" · ") : null,
    mTarget: fcP?.m_target ?? 8,
  };

  // The nightly-grade read — the latest council SESSION per name (council_session_panel).
  const seP = panelError(P.session) ? null : P.session;
  const streakText = (r: NonNullable<typeof seP>["rows"][number]): string => {
    if (r.proposer_abstained) return "proposer abstained";
    const { reads, low, prev } = r.streak;
    if (reads <= 1) return "1 read";
    if (r.conviction === "LOW" && low >= 2) return `LOW ×${low} of ${reads}`;
    if (prev && prev !== r.conviction) return `${prev} → ${r.conviction}`;
    return `${reads} reads`;
  };
  const sessionRows: SessionRowVM[] = (seP?.rows ?? []).map((r) => ({
    symbol: r.symbol, dir: r.direction ? directionLabel(r.direction) : DASH, adversary: r.adversary_stance ?? DASH,
    conviction: r.conviction, via: r.selection ?? "—", weakest: r.weakest_point ?? "", streak: streakText(r),
  }));
  const prof = seP?.profile ?? {};
  const recentW = P.council?.recent ?? [];
  const cleanN = recentW.filter((r) => r.verdict === "ROUNDTRIP_CONFIRMED").length;
  const session: SessionVM = {
    runId: seP?.run_id ?? null, startedAt: seP?.started_at ?? null, rows: sessionRows,
    profile: [
      { level: "LOW", n: prof.LOW ?? 0 }, { level: "NEUTRAL", n: prof.NEUTRAL ?? 0 },
      { level: "MODERATE+", n: (prof.MODERATE ?? 0) + (prof.HIGH ?? 0) + (prof.EXTREME ?? 0) },
    ],
    lowHistory: (seP?.low_history ?? []).map((h) => ({
      runId: h.run_id, day: (h.started_at ?? "").slice(5, 10), low: h.low, judged: h.judged,
    })),
    providerDrops: seP?.provider_drops ?? 0,
    understudy: { configured: seP?.understudy?.configured ?? null, fired: seP?.understudy?.fired ?? 0 },
    cleanLine: recentW.length ? `${cleanN} of the last ${recentW.length} sessions clean` : "no sessions yet",
  };

  // Month-to-date spend vs the per-provider tripwire (spend_panel).
  const spP = panelError(P.spend) ? null : P.spend;
  const spend: SpendVM = {
    month: spP?.month ?? DASH,
    rows: (spP?.providers ?? []).map((r) => ({
      provider: r.provider, mtd: usd(r.mtd_usd, 2), cap: r.cap_usd != null ? usd(r.cap_usd, 0) : null,
      frac: r.frac, page: r.page_would_fire,
    })),
    totalMtd: usd(spP?.total_mtd_usd, 2), totalCap: spP?.total_cap_usd != null ? usd(spP.total_cap_usd, 0) : null,
    cumulative: usd(spP?.cumulative?.cumulative_usd, 2), framer: usd(spP?.cumulative?.l0_framer_usd, 2),
    perCycleCap: spP?.per_cycle_cap_usd != null ? usd(spP.per_cycle_cap_usd, 2) : null,
    anyPage: (spP?.providers ?? []).some((r) => r.page_would_fire),
  };

  // The gate-rich canary (canary_panel) — first canary only (NVDA today); trend from the last two reads.
  const caP = panelError(P.canary) ? null : P.canary;
  const c0 = caP?.canaries?.[0];
  const cSeries = (c0?.series ?? []).map((pt) => pt.iv_rv);
  const cLast = cSeries.length ? cSeries[cSeries.length - 1] : null;
  const cPrev = cSeries.length > 1 ? cSeries[cSeries.length - 2] : null;
  const canary: CanaryVM | null = c0
    ? {
        symbol: c0.symbol, latest: cLast, skew: c0.latest?.otm_skew ?? null,
        cheap: c0.latest?.cheap == null ? null : c0.latest.cheap === 1, series: cSeries, gateLine: caP?.gate_line ?? 1.2,
        trend: cLast == null || cPrev == null ? "—" : cLast > cPrev + 0.002 ? "up" : cLast < cPrev - 0.002 ? "down" : "flat",
      }
    : null;

  const dualreadLast = P.dualread?.sessions?.[(P.dualread?.sessions?.length ?? 0) - 1];
  const wingMismatch = dualreadLast?.wing_mismatch ?? [];

  const dataAccrual: DataAccrualVM = {
    symbols: cgs.symbols ?? 0, latest: String(cgs.latest ?? DASH).slice(0, 10), ageDays: dg.latest_age_days ?? null,
    accruing: dg.accruing ?? false, barSymbols: dg.bar_coverage_symbols ?? 0, names: cgs.names ?? [],
  };
  const booksOpen: BooksOpenVM = {
    real: (ps.real_open ?? []).length, shadow: (ps.shadow_open ?? []).length, a3: (ps.nogate_3A_open ?? []).length,
    basket: (ps.nogate_3B_open ?? []).length, shares: (ps.shares ?? []).length,
  };
  const openedAts = [...(ps.real_open ?? []), ...(ps.real_closed ?? [])]
    .map((p) => (p as { opened_at?: string | null }).opened_at)
    .filter((x): x is string => typeof x === "string" && x.length > 0)
    .sort();
  const firstEntry = openedAts.length ? openedAts[0].slice(0, 10) : null;

  const cf = P.cap_flow;
  const delta = acc.delta_vs_frame ?? 0;
  const edgeN = ci(ciP.real).n;
  // A2: honest calibration progress — resolved bets toward the first null read (NOT a hardcoded 50%).
  const phasePct = `${Math.min(100, Math.round((edgeN / EDGE_TARGET) * 100))}%`;
  const phaseSub = edgeN > 0 ? `${edgeN}/${EDGE_TARGET} resolved bets` : "accruing — first reads after entries resolve";

  return {
    asOf: h.now ?? "",
    level: levelFromSystem(ss.level),
    headline: ss.headline ?? "",
    sub: (ss.issues && ss.issues.join(" · ")) || "Nothing needs your attention.",
    schemaWarning: h.schema_warning ?? null,
    degraded,
    cheapness: panelError(P.cheapness) ? null : (P.cheapness ?? null),
    issues: (ss.issues ?? []).map((t) => ({ sev: "warn" as const, text: t })),
    beats: {
      kill: h.kill_switch_engaged ? "ENGAGED" : "off",
      cycle: ageH(h.cycle), council: ageH(h.council), discovery: ageH(h.discovery),
      schema: `${h.schema_version}/${h.schema_expected}`,
    },
    beatLevels: {
      kill: h.kill_switch_engaged ? "bad" : "ok",
      cycle: beatLevel(h.cycle), council: beatLevel(h.council), discovery: beatLevel(h.discovery),
      schema: h.schema_ok ? "ok" : "warn",
    },
    equity: fmt(acc.broker_equity),
    deltaFrame: `${delta >= 0 ? "+" : "−"}$${Math.abs(delta).toLocaleString("en-US")} vs frame`,
    bookBudget: fmt(acc.frame?.book_budget), headroom: fmt(acc.headroom), equitySeries: acc.equity_series ?? [],
    bookDD: pct(rk.kill_rule?.book_drawdown), bookDDlevel: rk.kill_rule?.tripped ? "bad" : "ok",
    openN: rk.book?.open ?? 0, maxN: rk.book?.max ?? 0, openPrem: fmt(rk.book?.open_premium),
    council: {
      verdict: verdictLabel, vlevel, runId: ch.run_id ?? null, roundtrips: ch.roundtrip?.n ?? 0,
      strategistAbstained: ch.roundtrip?.strategist_abstained ?? 0,
      parseFail: ch.proposer?.parse_failed ?? 0, parseCalled: ch.proposer?.called ?? 0,
      cost: usd(ch.cost_usd), streak: councilStreak(P.council?.recent), models: modelMixSummary(P.council?.model_mix ?? null),
      byProvider,
    },
    cost, dualread, dualreadRuntime, nulls, deliberation, reserve, attempts, catalysts,
    capFlow: { rejected: cf?.cluster_cap_rejections_of_passing ?? 0, note: cf?.tightening_note ?? "" },
    clusters: (rk.clusters ?? []).map((c) => ({ name: c.cluster, premium: c.premium, cap: c.cap, dirs: (c.directions ?? []).join(", ") || "—" })),
    perf: {
      real: ci(ciP.real), shadow: ci(ciP.shadow_all), a3: ci(ciP.nogate_union_nogate), basket: ci(ciP.nogate_basket_nogate),
      paid: fmt(pbd.paid), bledPct: pbd.running_fraction != null ? Math.round(pbd.running_fraction * 100) : null,
      hits: hr.hits ?? 0, closed: hr.closed ?? 0, hitRate: hr.hit_rate != null ? Math.round(hr.hit_rate * 100) : null,
    },
    brier: {
      strategist: at.proposal_brier?.mean ?? null, n: at.proposal_brier?.n ?? 0,
      roles: Object.entries(at.role_contribution_brier ?? {}).map(([label, v]) => ({ label, value: v?.mean ?? null })),
    },
    funnel: {
      runId: l1.run_id ?? null, proposed: l1.proposed ?? 0, evaluated: l1.evaluated ?? 0, opened: l1.opened ?? 0,
      wasted: String(l1.wasted_llm_spend ?? 0), // a COUNT of paid-then-gate-vetoed proposals, not dollars
      council: {
        asserted: cs.asserted ?? 0, ungrounded: cs.ungrounded ?? 0, abstained: cs.proposer_abstained ?? 0, toGate: cs.to_gate ?? 0,
        floor: P.council_stage?.floor ?? "MODERATE", aboveFloor: cs.post_veto_include ?? 0, criteriaVetoed: cs.criteria_vetoed ?? 0,
      },
      gate: { ivTotal: ivg.total ?? 0, ivReal: ivg.real_veto ?? 0, ivFail: ivg.fail_closed_missing_data ?? 0, elig: gr.eligibility_vetoes ?? 0 },
      legs: P.council_stage?.legs
        ? { n: P.council_stage.legs.n_deliberated ?? 0, structural: P.council_stage.legs.structural ?? 0, underNarrated: P.council_stage.legs.under_narrated ?? 0, atInflection: P.council_stage.legs.at_inflection ?? 0 }
        : null,
    },
    universe: { ivrv: String(mc.universe_iv_rv?.p50 ?? "—"), skew: String(mc.universe_otm_skew?.p50 ?? "—"), n: mc.universe_iv_rv?.n ?? 0 },
    positions, openCount: (ps.real_open ?? []).length, openPrem2: fmt(rk.book?.open_premium),
    sentinels, sentinelSub: `${se.active_n ?? 0} active · ${se.dormant ?? 0} dormant.`,
    data: [
      { label: "Chain-snapshot symbols", value: String(cgs.symbols ?? 0) },
      { label: "Bar-coverage symbols", value: String(dg.bar_coverage_symbols ?? 0) },
      { label: "Latest snapshot", value: String(cgs.latest ?? "—").slice(0, 10) },
    ],
    t4: cond,
    readiness,
    edgeAccrual: { n: edgeN, target: EDGE_TARGET }, phasePct, phaseSub,
    session, spend, canary, wingMismatch, dataAccrual, booksOpen, firstEntry,
  };
}
