import { describe, expect, it } from "vitest";

import { fromBackend } from "./adapter";
import type { Snapshot } from "./types";

// A SYNTHETIC snapshot (fake symbols/numbers — never live data) exercising every mapping the adapter does,
// especially the four reconciliations vs the prototype adapter and the readiness/wasted-count semantics.
function synthetic(): Snapshot {
  const beat = (age: number, status: "ONLINE" | "STALE" | "OFFLINE") => ({ at: "2026-10-14T16:00:00+00:00", age_hours: age, status, stale: status !== "ONLINE" });
  const ci = (n: number, p95: number | null) => ({ n, p95, ci90: null, flag: null });
  const rrun = (run_id: number, verdict: "ROUNDTRIP_CONFIRMED" | "ROUNDTRIP_DEGRADED") => ({
    run_id, started_at: "2026-10-14T15:45:00+00:00", council_health: "ok" as const, verdict,
    proposer_parse_rate: 0, proposer_called: 12, proposer_parse_failed: 0, by_provider: {},
  });
  return {
    system_status: { level: "warn", headline: "🟡 A few things to check", issues: ["council ROUNDTRIP_DEGRADED", "ai_capex_power cluster at 78% of cap"] },
    header: {
      now: "2026-10-14T16:02:00+00:00", schema_version: 14, schema_expected: 14, schema_ok: true, schema_warning: null,
      kill_switch_engaged: false, cycle: beat(1, "ONLINE"), council: beat(20, "STALE"), discovery: beat(50, "ONLINE"),
    },
    account: {
      broker_equity: 99120, delta_vs_frame: -880, headroom: 5740,
      equity_series: [{ day: "10-01", equity: 100000 }, { day: "10-14", equity: 99120 }],
      frame: { frame_equity: 100000, book_budget: 10000, per_name_cap: 1000, cluster_cap: 2000, max_open: 15 },
    },
    risk: {
      kill_rule: { tripped: false, reasons: [], book_drawdown: 0.062, drawdown_halt: 0.2, have_marks: true },
      book: { open: 9, max: 15, open_premium: 4260, budget: 10000 },
      clusters: [{ cluster: "ai_capex_power", premium: 1560, cap: 2000, frac: 0.78, directions: ["bullish"] }],
    },
    council: {
      health: {
        run_id: 287, council_health: "ok", verdict: "ROUNDTRIP_DEGRADED",
        proposer: { called: 12, parse_failed: 0, parse_fail_rate: 0, page_would_fire: false, above_floor_proposals: 4 },
        roundtrip: { n: 4, adversary_direction_relative: 4, strategist_valid_conviction: 4, strategist_abstained: 1, strategist_criteria_vetoed: 0, any_role_parse_error: false },
        cost_usd: 0.114, cost_by_role: {}, notes: [],
      },
      model_mix: '{"proposer":"gemini/gemini-3.5-flash","adversary":"xai/grok-4","strategist":"anthropic/claude-opus-4-8","corpus":"fundamentals_v1"}',
      cost: { l0_framer_usd: 0.001, l1_council_usd: 0.114, cumulative_usd: 0.115 },
      by_provider: { gemini: { calls: 12, parse_error: 0, parse_error_rate: 0 }, xai: { calls: 4, parse_error: 1, parse_error_rate: 0.25 } },
      recent: [
        rrun(284, "ROUNDTRIP_CONFIRMED"), rrun(285, "ROUNDTRIP_DEGRADED"),
        rrun(286, "ROUNDTRIP_CONFIRMED"), rrun(287, "ROUNDTRIP_CONFIRMED"),
      ], // oldest→newest ⇒ trailing streak = 2 (286, 287), broken at #285
    },
    performance: {
      p95_ci: { real: ci(11, 3.1), shadow_all: ci(18, 2.35), nogate_union_nogate: ci(22, 1.9), nogate_basket_nogate: ci(14, 1.55) },
      premium_bled: { paid: 14200, running_fraction: 0.41, realized_fraction: 0.2 },
      hit_rate: { closed: 11, hits: 3, hit_rate: 0.2727 },
      caveat: "x",
    },
    attribution: {
      proposal_brier: { n: 11, mean: 0.214 },
      role_contribution_brier: { proposer: { n: 11, mean: 0.243 }, adversary: { n: 11, mean: 0.228 }, strategist: { n: 11, mean: 0.214 } },
    },
    funnel: { l1_decision: { run_id: 287, proposed: 11, evaluated: 9, opened: 2, wasted_llm_spend: 2 } },
    council_stage: {
      run_id: 287, empty: false, floor: "MODERATE",
      stages: { proposed: 11, asserted: 7, ungrounded: 1, proposer_abstained: 2, other: 1, strategist_include_raw: 4, criteria_vetoed: 0, post_veto_include: 4, below_floor: 0, to_gate: 4 },
      legs: { n_deliberated: 7, structural: 7, under_narrated: 2, at_inflection: 1 },
    },
    gate_reasons: { iv_gate: { total: 5, fail_closed_missing_data: 1, real_veto: 4 }, eligibility_vetoes: 2 },
    positions: {
      real_open: [{ id: 1, symbol: "ACME", direction: "bullish", contract_symbol: "ACME260116C00050000", status: "open", dte: 248, contracts: 1, total_premium: 620, mark: 0.3, origin_conviction: "HIGH", theme: "ai_capex_power" }],
      counts: { real: 1, shadow: 0 },
    },
    sentinels: { active: [{ symbol: "ACME", basket: "ai_capex_power", structural_vs_fad: "structural", discovered_at: "2026-10-10T00:00:00+00:00" }], active_n: 1, dormant: 3 },
    market_ctx: {
      open_positions: [{ symbol: "ACME", contract: "ACME260116C00050000", dte: 248, moneyness: 0.25, mark_over_entry: 1.8, marked_at: "2026-10-14T16:00:00+00:00" }],
      universe_iv_rv: { n: 54, p50: 1.11 }, universe_otm_skew: { n: 54, p50: 7.2 },
    },
    data_gathered: { chain_snapshots: { symbols: 58, latest: "2026-10-14T12:00:00+00:00" }, bar_coverage_symbols: 231 },
    t4: {
      conditions: [
        { id: 1, name: "council healthy", checkable: true, verdict: "MET", detail: "" },
        { id: 2, name: "null reads", checkable: false, verdict: null, detail: "" },
        { id: 3, name: "cluster-cap", checkable: true, verdict: "VACUOUS", detail: "" },
        { id: 4, name: "payoff shape", checkable: false, verdict: "BREACH", detail: "" },
        { id: 5, name: "pre-T4 items", checkable: true, verdict: "IN_PROGRESS", detail: "" },
      ],
      note: "",
    },
    nulls: {
      steps: [
        { name: "gate (shadow − 3A)", clean: true, arms: { shadow: ci(18, 2.35), "3A": ci(22, 1.9) } },
        { name: "council (real − shadow)", clean: true, censored_parse_fail_runs: 1, arms: { real: ci(11, 3.1), shadow: ci(18, 2.35) } },
        { name: "apparatus (real − 3B)", clean: false, bundled: "universe AND caps differ", arms: { real: ci(11, 3.1), "3B": ci(14, 1.55) } },
      ],
      note: "x",
    },
    dualread: {
      sessions: [
        { run_id: 129, names: 33, median_d_ivrv: 0.004, max_d_ivrv: 0.02, flips: [], material_flips: [], coverage_gaps: [], opra_coverage: 1, indicative_coverage: 1 },
        { run_id: 130, names: 33, median_d_ivrv: 0.0075, max_d_ivrv: 0.031, flips: ["NOC"], material_flips: [], coverage_gaps: [], opra_coverage: 0.97, indicative_coverage: 1 },
      ],
      n_sessions_total: 5,
      tripwires: { window: 5, delta_breach_sessions: 0, delta_tripped: false, flip_sessions: 0, flip_tripped: false, flip_floor: 0.02, gap_sessions: 1, gap_tripped: false },
      disagree_veto: { until: "2026-07-10", active: true },
      note: "x",
    },
    dualread_runtime: {
      window: 5, last_run: 130,
      classes: {
        delta: { tripped: false, sessions: 0, pages: [], revert: true },
        material_flip: { tripped: false, sessions: 0, pages: [], revert: false },
        gap_structural: { tripped: true, sessions: 2, pages: [], revert: false },
        gap_transient: { tripped: false, sessions: 0, pages: [], revert: false },
        entitlement: { tripped: false, sessions: 0, pages: [], revert: false },
      },
      revert_latch: { enabled: false, latched: false, authorized: false, sentinel_path: "/x/OPRA_REVERTED" },
      debounce: {
        rearm_consecutive: 4,
        material_flip: { active: [], paging: [], suppressed: [] },
        gap_structural: { active: ["UROY"], paging: [], suppressed: ["UROY"] },
        gap_transient: { active: [], paging: [], suppressed: [] },
      },
      note: "x",
    },
    cost: { l0_framer_usd: 0.001, l1_council_usd: 0.114, cumulative_usd: 0.115 },
    deliberation: [
      { run_id: 287, symbol: "ACME", proposer_direction: "bullish", adversary_stance: "agree", strategist_conviction: "MODERATE" },
    ],
    cap_flow: { cluster_cap_rejections_of_passing: 3, tightening_note: "x" },
  };
}

describe("fromBackend", () => {
  const vm = fromBackend(synthetic());

  it("maps the status banner from system_status (API-injected, reconciliation #1)", () => {
    expect(vm.level).toBe("warn");
    expect(vm.headline).toBe("🟡 A few things to check");
    expect(vm.issues).toHaveLength(2);
  });

  it("maps heartbeats with per-beat levels", () => {
    expect(vm.beats.schema).toBe("14/14");
    expect(vm.beatLevels.schema).toBe("ok");
    expect(vm.beatLevels.council).toBe("warn"); // STALE beat → warn
    expect(vm.beatLevels.cycle).toBe("ok");
    expect(vm.beats.kill).toBe("off");
  });

  it("formats account + delta sign", () => {
    expect(vm.equity).toBe("$99,120");
    expect(vm.deltaFrame.startsWith("−$880")).toBe(true); // negative → minus glyph
    expect(vm.headroom).toBe("$5,740");
  });

  it("maps the council health + summarises model_mix to the three role models", () => {
    expect(vm.council.verdict).toBe("Round-trip degraded");
    expect(vm.council.vlevel).toBe("warn");
    expect(vm.council.runId).toBe(287);
    expect(vm.council.roundtrips).toBe(4);
    expect(vm.council.cost).toBe("$0.114");
    expect(vm.council.models).toBe("gemini-3.5-flash · grok-4 · claude-opus-4-8");
  });

  it("reads council_stage TOP-LEVEL, not funnel.council_stage (reconciliation #2)", () => {
    expect(vm.funnel.council.asserted).toBe(7);
    expect(vm.funnel.council.toGate).toBe(4);
    expect(vm.funnel.council.floor).toBe("MODERATE");
  });

  it("joins mark÷entry from market_ctx by contract_symbol (reconciliation #3)", () => {
    expect(vm.positions).toHaveLength(1);
    expect(vm.positions[0].mark).toBe(1.8);
    expect(vm.positions[0].theme).toBe("ai_capex_power");
    expect(vm.positions[0].premium).toBe("$620");
  });

  it("composes the sentinel trigger note (reconciliation #4)", () => {
    expect(vm.sentinels[0].note.startsWith("structural")).toBe(true);
    expect(vm.sentinelSub).toBe("1 active · 3 dormant.");
  });

  it("renders Wasted as a COUNT, not dollars", () => {
    expect(vm.funnel.wasted).toBe("2"); // not "$2"
    expect(vm.funnel.opened).toBe(2);
  });

  it("computes readiness off the backend `checkable` flag (A1)", () => {
    // checkable conditions: #1 MET, #3 VACUOUS, #5 IN_PROGRESS ⇒ checkable=3, pass=1 (only MET).
    // accruing = the NON-checkable conditions (#2, #4) ⇒ 2 — even though #4 carries a BREACH verdict, it is
    // !checkable so it is deferred, not a blocked gate. Matches dashboard.py's composition.
    expect(vm.readiness).toEqual({ pass: 1, checkable: 3, accruing: 2 });
  });

  it("renders a non-checkable verdict-bearing row as deferred, not blocked (A1)", () => {
    const c4 = vm.t4.find((c) => c.id === 4);
    expect(c4?.verdict).toBe("BREACH"); // verdict preserved for display…
    expect(c4?.state).toBe("deferred"); // …but state is deferred (it's !checkable)
    expect(vm.t4.find((c) => c.id === 3)?.state).toBe("vacuous"); // checkable VACUOUS still shows vacuous
  });

  it("computes the council run streak from council.recent (A3)", () => {
    expect(vm.council.streak).toBe("2 clean, then #285");
    expect(vm.council.byProvider).toHaveLength(2);
    expect(vm.council.byProvider.find((p) => p.provider === "xai")?.rate).toBe(0.25);
  });

  it("maps the cost ledger, dual-read soak, null hierarchy, deliberation, cap-flow (C)", () => {
    expect(vm.cost.cumulative).toBe("$0.115");
    expect(vm.dualread.lastRun).toBe(130); // latest session
    expect(vm.dualread.flipTripped).toBe(false);
    expect(vm.dualread.vetoUntil).toBe("2026-07-10");
    expect(vm.nulls).toHaveLength(3);
    expect(vm.nulls[0].arms.map((a) => a.label)).toEqual(["shadow", "3A"]);
    expect(vm.deliberation.runId).toBe(287);
    expect(vm.deliberation.rows).toHaveLength(1);
    expect(vm.capFlow.rejected).toBe(3);
  });

  it("maps the §5 dual-read runtime view (#72) — per-class verdict + revert latch + debounce split", () => {
    const rt = vm.dualreadRuntime;
    expect(rt.window).toBe(5);
    expect(rt.lastRun).toBe(130);
    // Phase 3 OFF, not latched, not authorized (the live UROY-structural state)
    expect(rt.phase3).toBe(false);
    expect(rt.latched).toBe(false);
    expect(rt.authorized).toBe(false);
    expect(rt.rearm).toBe(4);
    // five classes; only Δ can revert
    expect(rt.classes.map((c) => c.key)).toEqual(["delta", "material_flip", "gap_structural", "gap_transient", "entitlement"]);
    expect(rt.classes.find((c) => c.key === "delta")?.reverts).toBe(true);
    expect(rt.classes.find((c) => c.key === "gap_structural")?.reverts).toBe(false);
    // structural tripped (2/5); the debounce split shows UROY suppressed (already alerted), labelled by class
    const struct = rt.classes.find((c) => c.key === "gap_structural")!;
    expect(struct.tripped).toBe(true);
    expect(struct.sessions).toBe(2);
    expect(rt.paging).toEqual([]);
    expect(rt.suppressed).toEqual(["UROY (gap_structural)"]);
  });

  it("flags a fail-soft {error} panel as degraded, not silently empty (B1)", () => {
    const clean = fromBackend(synthetic());
    expect(clean.degraded).toEqual([]);
    const broken = fromBackend({ ...synthetic(), risk: { error: "OperationalError: boom" } } as never);
    expect(broken.degraded).toContain("risk");
  });

  it("surfaces a non-null schema_warning (B2)", () => {
    expect(vm.schemaWarning).toBeNull();
    const warned = fromBackend({ ...synthetic(), header: { ...synthetic().header, schema_warning: "schema 13 < expected 14" } } as never);
    expect(warned.schemaWarning).toBe("schema 13 < expected 14");
  });

  it("computes honest calibration phase progress (A2)", () => {
    // edgeAccrual.n = real CI n = 11; target 30 ⇒ 37%.
    expect(vm.phasePct).toBe("37%");
    expect(vm.phaseSub).toBe("11/30 resolved bets");
  });

  it("maps performance tails + rounds bled/hit-rate to whole percents", () => {
    expect(vm.perf.real).toEqual({ n: 11, p95: 3.1 });
    expect(vm.perf.bledPct).toBe(41);
    expect(vm.perf.hitRate).toBe(27); // round(0.2727 * 100)
    expect(vm.brier.roles).toHaveLength(3);
  });

  it("maps the cheapness-gate split", () => {
    expect(vm.funnel.gate).toEqual({ ivTotal: 5, ivReal: 4, ivFail: 1, elig: 2 });
  });

  it("returns no view-model fields as undefined for the rendered surface", () => {
    expect(vm.data).toHaveLength(3);
    expect(vm.universe.n).toBe(54);
  });
});
