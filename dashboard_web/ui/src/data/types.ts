// Data-layer types. TWO shapes:
//   1. Snapshot   — the JSON the API returns = dashboard.load_all()'s panels + the injected system_status.
//                   Shapes are GROUNDED in dashboard_data.py (the live, tested data layer). Only the panels
//                   the UI consumes are typed in full; the rest are available on the wire but left untyped.
//   2. ViewModel  — the FLAT shape the components render (the prototype's td/mt). `fromBackend` maps 1 → 2.

import type { Level } from "../theme/tokens";
import type { CouncilVerdict, DisplayState, T4Verdict } from "./status";

/* ────────────────────────── 1 · Snapshot (panel shapes) ────────────────────────── */
export interface Heartbeat {
  at: string | null; age_hours: number | null; status: "ONLINE" | "STALE" | "OFFLINE"; stale: boolean;
}
export interface CI { n: number; p95: number | null; ci90: [number, number] | null; flag: string | null }

export interface CouncilHealth {
  run_id: number | null; council_health: string | null; verdict: CouncilVerdict;
  proposer: { called: number; parse_failed: number; parse_fail_rate: number; page_would_fire: boolean; above_floor_proposals: number };
  roundtrip: {
    n: number; adversary_direction_relative: number; strategist_valid_conviction: number;
    strategist_abstained: number; strategist_criteria_vetoed: number; any_role_parse_error: boolean;
  };
  cost_usd: number; cost_by_role: Record<string, number>; notes: string[];
}

export interface PositionRow {
  id: number; symbol: string; direction: string; contract_symbol: string; status: string;
  dte: number | null; contracts: number; total_premium: number; mark: number | null;
  origin_conviction: string | null;
  theme?: string; // ⚠ NOT yet emitted by positions_panel — pending a 1-line SELECT add (see adapter, fix #3).
}

// Active sentinel rows are state.active_sentinel_rows() (wide); only the fields the UI reads are named.
export interface SentinelRow {
  symbol: string; basket?: string; theme?: string; direction?: string;
  structural_vs_fad?: string; framer_conviction?: string; markers?: unknown;
  discovered_at?: string; last_seen_at?: string; note?: string;
  [k: string]: unknown;
}

export interface Snapshot {
  system_status: { level: "success" | "warn" | "error"; headline: string; issues: string[] };
  header: {
    now: string; schema_version: number; schema_expected: number; schema_ok: boolean; schema_warning: string | null;
    kill_switch_engaged: boolean; cycle: Heartbeat; council: Heartbeat; discovery: Heartbeat;
  };
  account: {
    broker_equity: number | null; delta_vs_frame: number | null; headroom: number;
    equity_series: { day: string; equity: number }[];
    frame: { frame_equity: number; book_budget: number; per_name_cap: number; cluster_cap: number; max_open: number };
  };
  risk: {
    kill_rule: { tripped: boolean; reasons: string[]; book_drawdown: number; drawdown_halt: number; have_marks: boolean };
    book: { open: number; max: number; open_premium: number; budget: number };
    clusters: { cluster: string; premium: number; cap: number; frac: number | null; directions: string[] }[];
  };
  council: {
    health: CouncilHealth; model_mix: string | null;
    cost: { l0_framer_usd: number; l1_council_usd: number; cumulative_usd: number };
    by_provider: Record<string, { calls: number; parse_error: number; parse_error_rate: number | null }>;
  };
  performance: {
    p95_ci: { real: CI; shadow_all: CI; nogate_union_nogate: CI; nogate_basket_nogate: CI };
    premium_bled: { paid: number; running_fraction: number | null; realized_fraction: number | null };
    hit_rate: { closed: number; hits: number; hit_rate: number | null };
    caveat: string;
  };
  attribution: {
    proposal_brier: { n: number; mean: number | null };
    role_contribution_brier: Record<string, { n: number; mean: number }>;
  };
  funnel: { l1_decision: { run_id: number | null; proposed: number; evaluated: number; opened: number; wasted_llm_spend: number } };
  council_stage: { // ⚠ TOP-LEVEL panel (the prototype adapter wrongly nested it under funnel — fix #2).
    run_id: number | null; empty: boolean; floor?: string;
    stages?: {
      proposed: number; asserted: number; ungrounded: number; proposer_abstained: number; other: number;
      strategist_include_raw: number; criteria_vetoed: number; post_veto_include: number; below_floor: number; to_gate: number;
    };
    legs?: { n_deliberated: number; structural: number; under_narrated: number; at_inflection: number };
  };
  gate_reasons: { iv_gate: { total: number; fail_closed_missing_data: number; real_veto: number }; eligibility_vetoes: number };
  positions: { real_open: PositionRow[]; counts: { real: number; shadow: number } };
  sentinels: { active: SentinelRow[]; active_n: number; dormant: number };
  market_ctx: {
    open_positions: { symbol: string; contract: string; dte: number | null; moneyness: number | null; mark_over_entry: number | null; marked_at: string | null }[];
    universe_iv_rv: { n: number; p50?: number }; universe_otm_skew: { n: number; p50?: number };
  };
  data_gathered: { chain_snapshots: { symbols: number; latest: string | null }; bar_coverage_symbols: number };
  t4: { conditions: { id: number; name: string; checkable: boolean; verdict: T4Verdict; detail: string }[]; note: string };
  // available on the wire, not yet rendered: regime · deliberation · nulls · cap_flow · cost · dualread · curation
  _fatal?: string;
}

/* ────────────────────────── 2 · ViewModel (flat render shape) ────────────────────────── */
export type BeatKey = "kill" | "cycle" | "council" | "discovery" | "schema";
export interface BookCI { n: number; p95: number | null }
export interface ClusterVM { name: string; premium: number; cap: number; dirs: string }
export interface PositionVM { symbol: string; theme?: string; dir: string; conviction: string | null; dte: number | null; premium: string; mark: number | null }
export interface SentinelVM { symbol: string; basket?: string; note: string }
export interface T4ItemVM { id: number; name: string; detail: string; verdict: T4Verdict; state: DisplayState }

export interface ViewModel {
  asOf: string; level: Level; headline: string; sub: string;
  issues: { sev: "warn"; text: string }[];
  beats: Record<BeatKey, string>;
  beatLevels: Record<BeatKey, Level>;
  equity: string; deltaFrame: string; bookBudget: string; headroom: string;
  equitySeries: { day: string; equity: number }[];
  bookDD: string; bookDDlevel: Level; openN: number; maxN: number; openPrem: string;
  council: {
    verdict: string; vlevel: Level; runId: number | null; roundtrips: number;
    parseFail: number; parseCalled: number; cost: string; streak: string; models: string;
  };
  clusters: ClusterVM[];
  perf: {
    real: BookCI; shadow: BookCI; a3: BookCI; basket: BookCI;
    paid: string; bledPct: number | null; hits: number; closed: number; hitRate: number | null;
  };
  brier: { strategist: number | null; n: number; roles: { label: string; value: number | null }[] };
  funnel: {
    runId: number | null; proposed: number; evaluated: number; opened: number; wasted: string;
    council: { asserted: number; ungrounded: number; abstained: number; toGate: number; floor: string };
    gate: { ivTotal: number; ivReal: number; ivFail: number; elig: number };
  };
  universe: { ivrv: string; skew: string; n: number };
  positions: PositionVM[]; openCount: number; openPrem2: string;
  sentinels: SentinelVM[]; sentinelSub: string;
  data: { label: string; value: string }[];
  t4: T4ItemVM[]; readiness: { pass: number; checkable: number; accruing: number };
  edgeAccrual: { n: number; target: number }; phasePct: string; phaseSub: string;
}

/** Props the desktop console + mobile app both receive from <App> (one fetch, two layouts). */
export interface ConsoleProps {
  vm: ViewModel | null;
  loading: boolean;
  error: string | null;
  fatal: string | null;
  refresh: () => void;
}
