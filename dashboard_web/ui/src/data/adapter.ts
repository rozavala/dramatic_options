// fromBackend(panels) → ViewModel — ported from the prototype's static adapter (Dramatic Options
// Dashboard.dc.html), the field-by-field spec. FOUR reconciliations vs the prototype, each marked:
//   #1 system_status — the API injects it (dd.system_status runs over the assembled snapshot; it is NOT a
//      load_all panel). The prototype read panels.system_status, which is correct once injected. ✓
//   #2 council_stage is a TOP-LEVEL panel (the prototype read panels.funnel.council_stage). Read it directly.
//   #3 positions: mark÷entry is NOT on the position row — it is market_ctx.open_positions[].mark_over_entry,
//      joined here by contract_symbol. `theme` is not yet emitted by positions_panel (pending a 1-line SELECT
//      add); until then it is undefined and the Book "Theme" column falls back. The book is empty today.
//   #4 sentinel `note` ("rv-slope · 4d") is composed (trigger + age) — not a raw column; best-effort here.

import type { PositionVM, SentinelVM, Snapshot, ViewModel } from "./types";
import { levelFromSystem, t4State, verdictDisplay, type DisplayState } from "./status";

const DASH = "—";
const fmt = (v: number | null | undefined): string =>
  v == null ? DASH : "$" + Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
const pct = (v: number | null | undefined): string => (v == null ? DASH : (v * 100).toFixed(1) + "%");
const ageH = (b?: { age_hours: number | null } | null): string =>
  b && b.age_hours != null ? Math.round(b.age_hours) + "h" : DASH;
const beatLevel = (b?: { status?: string } | null) => (b && b.status && b.status !== "ONLINE" ? "warn" : "ok");
const ci = (c?: { n?: number; p95?: number | null } | null) => ({ n: c?.n ?? 0, p95: c?.p95 ?? null });

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

  // #3 join mark÷entry from market_ctx by contract_symbol (it is not on the position row).
  const markByContract = new Map((mc.open_positions ?? []).map((o) => [o.contract, o.mark_over_entry] as const));
  const positions: PositionVM[] = (ps.real_open ?? []).map((p) => ({
    symbol: p.symbol, theme: p.theme, dir: p.direction, conviction: p.origin_conviction, dte: p.dte,
    premium: fmt(p.total_premium), mark: markByContract.get(p.contract_symbol) ?? p.mark ?? null,
  }));
  const sentinels: SentinelVM[] = (se.active ?? []).map((x) => ({ symbol: x.symbol, basket: x.basket, note: sentinelNote(x) })); // #4

  const cond = (P.t4?.conditions ?? []).map((c) => ({ id: c.id, name: c.name, detail: c.detail, verdict: c.verdict, state: t4State(c.verdict) }));
  // readiness = pass / checkable, where "checkable" = conditions with a definite or active state
  // (pass/blocked/inprogress). VACUOUS is EXCLUDED (0/0 admissions is not a pass — the anti-vacuous-pass
  // discipline); accruing (null verdict) is counted separately. The full per-condition breakdown is the T4 list.
  const able = cond.filter((c) => (["pass", "blocked", "inprogress"] as DisplayState[]).includes(c.state));
  const delta = acc.delta_vs_frame ?? 0;

  return {
    asOf: h.now ?? "",
    level: levelFromSystem(ss.level),
    headline: ss.headline ?? "",
    sub: (ss.issues && ss.issues.join(" · ")) || "Nothing needs your attention.",
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
      parseFail: ch.proposer?.parse_failed ?? 0, parseCalled: ch.proposer?.called ?? 0,
      cost: "$" + Number(ch.cost_usd ?? 0).toFixed(3), streak: "—", models: modelMixSummary(P.council?.model_mix ?? null),
    },
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
      council: { asserted: cs.asserted ?? 0, ungrounded: cs.ungrounded ?? 0, abstained: cs.proposer_abstained ?? 0, toGate: cs.to_gate ?? 0, floor: P.council_stage?.floor ?? "MODERATE" },
      gate: { ivTotal: ivg.total ?? 0, ivReal: ivg.real_veto ?? 0, ivFail: ivg.fail_closed_missing_data ?? 0, elig: gr.eligibility_vetoes ?? 0 },
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
    readiness: {
      pass: able.filter((c) => c.state === "pass").length,
      checkable: able.length,
      accruing: cond.filter((c) => c.state === "accruing").length,
    },
    edgeAccrual: { n: ci(ciP.real).n, target: 30 }, phasePct: "50%", phaseSub: "first null reads ~Mo 6",
  };
}
