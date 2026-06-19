import { describe, expect, it } from "vitest";

import { fromBackend } from "./adapter";
import type { Snapshot } from "./types";

// A SYNTHETIC snapshot (fake symbols/numbers — never live data) exercising every mapping the adapter does,
// especially the four reconciliations vs the prototype adapter and the readiness/wasted-count semantics.
function synthetic(): Snapshot {
  const beat = (age: number, status: "ONLINE" | "STALE" | "OFFLINE") => ({ at: "2026-10-14T16:00:00+00:00", age_hours: age, status, stale: status !== "ONLINE" });
  const ci = (n: number, p95: number | null) => ({ n, p95, ci90: null, flag: null });
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
      by_provider: {},
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

  it("computes readiness: VACUOUS excluded, accruing counted separately", () => {
    // conditions: MET(pass) · null(accruing) · VACUOUS(excluded) · BREACH(blocked) · IN_PROGRESS(inprogress)
    expect(vm.readiness).toEqual({ pass: 1, checkable: 3, accruing: 1 });
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
