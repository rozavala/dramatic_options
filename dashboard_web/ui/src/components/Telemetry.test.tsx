// @vitest-environment jsdom
// 2026-11-03 profit telemetry cards (D0 / D4 / D3b). Synthetic data only.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { buildTelemetry } from "../data/adapter";
import type { Snapshot } from "../data/types";
import { Telemetry } from "./Telemetry";

afterEach(cleanup);

const P = {
  execution: {
    summary: { read: "accruing: 1 of 5 decided orders under carry-over",
      all: { approvals: 3, reached_order: 2, decided: 2, filled: 1, fill_rate: 0.5 },
      under_carry: { approvals: 1, reached_order: 1, decided: 1, filled: 1, fill_rate: 1 } },
    rows: [{ proposal_id: 9, date: "2026-11-04", symbol: "NTSK", conviction: "MODERATE", outcome: "filled_carry",
      limit: 1.5, mid: 1.5, ask: 1.6, fill_px: 1.58, under_carry: true, attempts: [{ step: 0, limit: 1.5, status: "cancelled" }] }],
  },
  iv_history: { rows: [{ symbol: "FCX", sessions: 101, iv_rv: 0.98, iv_rv_pct: null, skew: 3.2, skew_pct: null,
    term_sessions: 0, term_slope: null, d_iv_call: null, d_iv_put: null }],
    status: "percentiles accruing: 101 of 120 sessions", note: "", max_term_sessions: 0 },
  falsifiers: { error: "boom" },
  capex_cycle: { as_of: "2026-11-03T21:00:00+00:00", note: "Telemetry only.", rows: [{ cluster: "ai_capex_power",
    n_with_data: 6, members: ["VRT", "PWR", "GEV", "ETN", "CCJ", "CEG", "NEE"], missing: ["NEE"], ttm_now_musd: 41234.5,
    yoy: 0.31, yoy_prev: 0.22, accel: 0.09, phase: "capex boom, accelerating", latest_period: "2026-09-30" }] },
  attention: { records: 90, since: "2026-08-01", status: "trend live (90 days of history)", note: "Telemetry only.",
    rows: [{ symbol: "NTSK", count: 9, as_of: "2026-11-03", count_then: 5, then: "2026-08-05", change: 4,
      label: "covered, coverage rising", stale_days: 0 }] },
} as unknown as Snapshot;

describe("profit telemetry", () => {
  it("builds the VM and degrades an errored panel to null", () => {
    const t = buildTelemetry(P);
    expect(t.exec?.fillRate).toBe("50%");
    expect(t.exec?.rows[0].attempts).toBe(1);
    expect(t.iv?.rows[0].ivrvPct).toBe("—");
    expect(t.fals).toBeNull();
    expect(t.attention?.rows[0]).toMatchObject({ count: "9", change: "+4 since 2026-08-05", label: "covered, coverage rising" });
    expect(t.capex?.rows[0]).toMatchObject({ n: "6/7", yoy: "31%", accel: "+9 pp", phase: "capex boom, accelerating" });
  });

  it("renders all three cards", () => {
    render(<Telemetry t={buildTelemetry(P)} />);
    expect(screen.getByTestId("tel-exec").textContent).toContain("filled_carry");
    expect(screen.getByTestId("tel-iv").textContent).toContain("101 of 120");
    expect(screen.getByTestId("tel-fals").textContent).toContain("panel unavailable");
    expect(screen.getByTestId("tel-capex").textContent).toContain("ai_capex_power");
    expect(screen.getByTestId("tel-attention").textContent).toContain("coverage rising");
  });
});

// #467 step 3: the net-of-slippage twin. One priced entry, one with no quote at entry (must read "unknown").
const SLIP = {
  slippage: {
    note: "Estimate (#467): each entry re-priced at a conservative fill, the ask recorded at entry, else the carry walk's worst rung, else unknown. Entry side only. Display only: nothing is re-booked.",
    totals: { entries: 2, known: 1, unknown: 1, premium_filled_usd: 1780, premium_filled_known_usd: 1000,
      premium_conservative_usd: 1100, haircut_usd: 100, haircut_pct: 0.1, pnl_n: 1, pnl_filled_usd: 200, pnl_conservative_usd: 100 },
    rows: [
      { position_id: 12, symbol: "TITN", contract: "TITN270115C00030000", short_contract: null, status: "open",
        opened_at: "2026-10-01", contracts: 3, fill_px: 2.6, conservative_px: null, basis: null,
        premium_filled_usd: 780, premium_conservative_usd: null, haircut_usd: null, haircut_pct: null,
        pnl_kind: "marked", pnl_filled_usd: 60, pnl_conservative_usd: null },
      { position_id: 11, symbol: "FLNC", contract: "FLNC270521C00005000", short_contract: null, status: "open",
        opened_at: "2026-11-04", contracts: 10, fill_px: 1.0, conservative_px: 1.1, basis: "ask_at_entry",
        premium_filled_usd: 1000, premium_conservative_usd: 1100, haircut_usd: 100, haircut_pct: 0.1,
        pnl_kind: "marked", pnl_filled_usd: 200, pnl_conservative_usd: 100 },
    ],
  },
} as unknown as Snapshot;

describe("net-of-slippage twin (#467)", () => {
  it("renders each entry as filled and at the conservative fill, labelled an estimate", () => {
    render(<Telemetry t={buildTelemetry(SLIP)} />);
    const card = screen.getByTestId("tel-slip").textContent ?? "";
    expect(card).toContain("Net of slippage (estimate, #467)");
    expect(card).toContain("nothing is re-booked");
    expect(card).toContain("1 of 2 entries priced (1 unknown)");
    const flnc = screen.getByTestId("slip-row-11").textContent ?? "";
    expect(flnc).toContain("1.00");
    expect(flnc).toContain("1.10");
    expect(flnc).toContain("ask at entry");
    expect(flnc).toContain("$1,100.00");
    expect(flnc).toContain("+$200.00");
    expect(flnc).toContain("+$100.00");
  });

  it("shows unknown, never the fill, when the conservative price can't be derived", () => {
    const t = buildTelemetry(SLIP);
    expect(t.slip?.rows[0]).toMatchObject({ fill: "2.60", cons: "unknown", premiumCons: "unknown", pnl: "+$60.00", pnlCons: "unknown",
      basis: "no quote at entry" });
    render(<Telemetry t={t} />);
    const titn = screen.getByTestId("slip-row-12").textContent ?? "";
    expect(titn).toContain("unknown");
    expect(titn.match(/2\.60/g)?.length).toBe(1);   // the fill appears once: no stand-in equal to it
  });

  it("degrades an errored panel to unavailable", () => {
    render(<Telemetry t={buildTelemetry({ slippage: { error: "boom" } } as unknown as Snapshot)} />);
    expect(screen.getByTestId("tel-slip").textContent).toContain("panel unavailable");
  });
});
