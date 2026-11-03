// @vitest-environment jsdom
// 2026-11-03 profit telemetry cards (D0 / D4 / D3b). Synthetic data only.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildTelemetry } from "../data/adapter";
import type { Snapshot } from "../data/types";
import { Telemetry } from "./Telemetry";

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
} as unknown as Snapshot;

describe("profit telemetry", () => {
  it("builds the VM and degrades an errored panel to null", () => {
    const t = buildTelemetry(P);
    expect(t.exec?.fillRate).toBe("50%");
    expect(t.exec?.rows[0].attempts).toBe(1);
    expect(t.iv?.rows[0].ivrvPct).toBe("—");
    expect(t.fals).toBeNull();
    expect(t.capex?.rows[0]).toMatchObject({ n: "6/7", yoy: "31%", accel: "+9 pp", phase: "capex boom, accelerating" });
  });

  it("renders all three cards", () => {
    render(<Telemetry t={buildTelemetry(P)} />);
    expect(screen.getByTestId("tel-exec").textContent).toContain("filled_carry");
    expect(screen.getByTestId("tel-iv").textContent).toContain("101 of 120");
    expect(screen.getByTestId("tel-fals").textContent).toContain("panel unavailable");
    expect(screen.getByTestId("tel-capex").textContent).toContain("ai_capex_power");
  });
});
