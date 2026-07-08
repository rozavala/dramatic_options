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

// One trailing council-deliberated run (recent_council_health, oldest→newest); feeds the streak (A3).
export interface CouncilRecentRun {
  run_id: number; started_at: string | null; council_health: string | null; verdict: CouncilVerdict;
  proposer_parse_rate: number; proposer_called: number; proposer_parse_failed: number;
  by_provider: Record<string, { calls: number; parse_error: number; parse_error_rate?: number | null }>;
}

export interface PositionRow {
  id: number; symbol: string; direction: string; contract_symbol: string; status: string;
  dte: number | null; contracts: number; total_premium: number; mark: number | null;
  origin_conviction: string | null;
  theme: string | null; // emitted by positions_panel (dashboard_data.py SELECT p.theme)
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
    recent: CouncilRecentRun[]; // recent_council_health window (oldest→newest); the run streak (A3)
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
  // Panels below are always emitted by load_all but may be replaced by {error} (dd.safe), so they are typed
  // optional — the adapter must guard. (C: now rendered. regime/curation remain on the wire, not rendered.)
  nulls?: NullHierarchy;
  dualread?: DualRead;
  dualread_runtime?: DualReadRuntime;
  cost?: { l0_framer_usd: number; l1_council_usd: number; cumulative_usd: number };
  deliberation?: DeliberationRow[];
  cap_flow?: { cluster_cap_rejections_of_passing: number; tightening_note: string };
  reserve?: ReservePanel;
  null_attempts?: NullAttempts;
  regime?: unknown;
  curation?: unknown;
  cheapness?: CheapnessPanel;
  _fatal?: string;
}

// reserve_panel: judged-set provenance (PREREG gate_cheap_reserve §6) — which judged names came via the
// RESERVE (gate-cheap, salience-truncated) vs the motion RANK. Stamp absent + all-unlabeled = reserve OFF
// or a pre-deploy run: the UI renders "off", it never invents provenance.
export interface ReserveSlot { symbol: string; conviction: string | null; status: string | null }
export interface ReservePanel {
  run_id: number | null; stamp: string | null;
  reserve: ReserveSlot[]; rank: ReserveSlot[]; unlabeled: ReserveSlot[];
}
// null_attempts_panel (migration 0018): every candidate each capped null book touched last cycle, in walk
// order, with the terminal outcome + premium-at-attempt — the per-name attribution surface.
export interface NullAttemptRow {
  book: string; attempt_idx: number; symbol: string; direction: string | null;
  origin: string | null; outcome: string | null; entry_premium_per_contract: number | null;
}
export interface NullAttempts { run_id: number | null; books: Record<string, { rows: NullAttemptRow[] }> }

// cheapness-watch (finding #1): the §7.1 verdict + counts + per-name latest cheap state (PREREG_CHEAPNESS_WATCH).
export interface CheapnessPanel {
  verdict: string;
  n_breaks: number; n_qualifying: number; n_never_cheap: number; n_fresh_marker: number;
  qualifying_per_quarter: number | null; observed_days: number | null;
  staleness_lag_days?: number; n_qualify_floor?: number;
  latest_by_name: { symbol: string; as_of: string; cheap: number | null; iv_rv: number | null; marker_age_days: number | null }[];
  note: string;
  error?: string;
}

// null_hierarchy: per-step clean/bundled contrasts, arms keyed by book label → CI (PREREG_FIXED_BASKET_NULL §2).
export interface NullHierarchy {
  steps: { name: string; clean: boolean; bundled?: string; censored_parse_fail_runs?: number; arms: Record<string, CI> }[];
  note: string;
}
// gate_dualread_report: the §5 OPRA dual-read soak surface.
export interface DualRead {
  sessions: { run_id: number; names: number; median_d_ivrv: number | null; max_d_ivrv: number | null;
    flips: string[]; material_flips: string[]; coverage_gaps: string[];
    opra_coverage: number | null; indicative_coverage: number | null }[];
  n_sessions_total: number;
  tripwires: { window: number; delta_breach_sessions: number; delta_tripped: boolean;
    flip_sessions: number; flip_tripped: boolean; flip_floor: number;
    gap_sessions: number; gap_tripped: boolean };
  disagree_veto: { until: string | null; active: boolean | null };
  note: string;
}
// dualread_runtime_panel: the #72 RUNTIME view — the per-class §5 verdict, the Phase-3 revert latch,
// and the debounce/page summary (what the live dualread_executor would do; read-only).
export interface DualReadRuntime {
  window: number;
  last_run: number | null;
  classes: Record<string, { tripped: boolean; sessions: number | null; pages: string[]; revert: boolean }>;
  revert_latch: { enabled: boolean; latched: boolean; authorized: boolean; sentinel_path: string };
  debounce: {
    rearm_consecutive: number;
    material_flip: { active: string[]; paging: string[]; suppressed: string[] };
    gap_structural: { active: string[]; paging: string[]; suppressed: string[] };
    gap_transient: { active: string[]; paging: string[]; suppressed: string[] };
  };
  note: string;
}
// latest_run_deliberation: per-name proposer→adversary→strategist (the "why").
export interface DeliberationRow {
  run_id: number; symbol: string; proposer_direction: string | null;
  adversary_stance: string | null; strategist_conviction: string | null;
}

/* ────────────────────────── 2 · ViewModel (flat render shape) ────────────────────────── */
export type BeatKey = "kill" | "cycle" | "council" | "discovery" | "schema";
export interface BookCI { n: number; p95: number | null }
export interface ClusterVM { name: string; premium: number; cap: number; dirs: string }
export interface PositionVM { symbol: string; theme: string | null; dir: string; conviction: string | null; dte: number | null; premium: string; mark: number | null }
export interface SentinelVM { symbol: string; basket?: string; note: string }
export interface T4ItemVM { id: number; name: string; detail: string; verdict: T4Verdict; state: DisplayState }
export interface ProviderVM { provider: string; calls: number; parseError: number; rate: number | null }
export interface NullStepVM { name: string; clean: boolean; bundled: string | null; censored: number | null; arms: { label: string; ci: BookCI }[] }
export interface DualReadVM {
  sessions: number; lastRun: number | null; medianD: number | null; maxD: number | null;
  opraCov: number | null; indCov: number | null; window: number;
  deltaTripped: boolean; flipTripped: boolean; gapTripped: boolean; flipFloor: number;
  deltaSessions: number; flipSessions: number; gapSessions: number;
  vetoUntil: string | null; vetoActive: boolean | null;
}
export interface DualReadRuntimeClassVM { key: string; label: string; tripped: boolean; sessions: number | null; pages: string[]; reverts: boolean }
export interface DualReadRuntimeVM {
  window: number; lastRun: number | null;
  phase3: boolean; latched: boolean; authorized: boolean;
  rearm: number; classes: DualReadRuntimeClassVM[];
  paging: string[]; suppressed: string[];   // debounce split across the debounced classes (name (class))
}
export interface DeliberationVM { runId: number | null; rows: { symbol: string; dir: string | null; adversary: string | null; conviction: string | null }[] }
export interface ReserveSlotVM { symbol: string; conviction: string; status: string; via: "reserve" | "rank" | "unlabeled" }
export interface ReserveVM { runId: number | null; stamp: string | null; slots: ReserveSlotVM[] }
export interface AttemptRowVM { idx: number; symbol: string; origin: string; outcome: string; premium: number | null }
export interface AttemptsVM { runId: number | null; books: { book: string; rows: AttemptRowVM[] }[] }

export interface ViewModel {
  asOf: string; level: Level; headline: string; sub: string;
  schemaWarning: string | null;        // B2 — header.schema_warning, rendered as a top strip
  degraded: string[];                  // B1 — panel keys that came back {error} (fail-soft), shown inline
  issues: { sev: "warn"; text: string }[];
  beats: Record<BeatKey, string>;
  beatLevels: Record<BeatKey, Level>;
  equity: string; deltaFrame: string; bookBudget: string; headroom: string;
  equitySeries: { day: string; equity: number }[];
  bookDD: string; bookDDlevel: Level; openN: number; maxN: number; openPrem: string;
  council: {
    verdict: string; vlevel: Level; runId: number | null; roundtrips: number;
    parseFail: number; parseCalled: number; cost: string; streak: string; models: string;
    byProvider: ProviderVM[];          // C — per-provider parse health (scoped to the latest run)
  };
  cost: { framer: string; council: string; cumulative: string };  // C — LLM cost ledger
  dualread: DualReadVM;                // C — OPRA gate dual-read soak (§5 safety)
  dualreadRuntime: DualReadRuntimeVM;  // #72 — the §5 dual-read runtime view (per-class verdict + revert latch)
  nulls: NullStepVM[];                 // C — the null hierarchy contrasts
  deliberation: DeliberationVM;        // C — latest run's per-name reasoning
  reserve: ReserveVM;                  // C — judged-set provenance (the gate-cheap reserve)
  attempts: AttemptsVM;                // C — the null-book entry walk (migration 0018)
  capFlow: { rejected: number; note: string };  // C — cluster-cap rejections of otherwise-passing
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
  cheapness: CheapnessPanel | null;   // finding #1's instrument (PREREG_CHEAPNESS_WATCH)
}

/** Props the desktop console + mobile app both receive from <App> (one fetch, two layouts). */
export interface ConsoleProps {
  vm: ViewModel | null;
  loading: boolean;
  error: string | null;
  fatal: string | null;
  refresh: () => void;
}
