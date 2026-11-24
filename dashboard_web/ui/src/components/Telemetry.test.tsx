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
    note: "Estimate (#467): each entry re-priced at a conservative fill, the ask quoted at decision time (the order may have filled after it moved), else the carry walk's worst rung, else unknown. Entry side only. Display only: nothing is re-booked.",
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
    expect(flnc).toContain("ask at decision");
    expect(card).toContain("the ask quoted at decision time (the order may have filled after it moved)");
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

  it("flags a partially closed entry and an ask that moved below the fill (#467 review)", () => {
    const snap = { slippage: { ...SLIP.slippage, rows: [
      { position_id: 21, symbol: "PL", contract: "PL270115C00020000", short_contract: null, status: "open", opened_at: "2026-11-04",
        contracts: 10, partial: true, sold_qty: 6, contracts_remaining: 4, fill_px: 1.5, conservative_px: 1.6, basis: "ask_at_entry",
        premium_filled_usd: 1500, premium_conservative_usd: 1600, haircut_usd: 100, haircut_pct: 0.0667,
        pnl_kind: "realized+marked", pnl_filled_usd: 420, pnl_conservative_usd: 320 },
      { position_id: 22, symbol: "CCJ", contract: "CCJ270115C00090000", short_contract: null, status: "open", opened_at: "2026-11-04",
        contracts: 5, partial: false, sold_qty: 0, contracts_remaining: 5, fill_px: 1.7, conservative_px: null, basis: "ask_below_fill",
        premium_filled_usd: 850, premium_conservative_usd: null, haircut_usd: null, haircut_pct: null,
        pnl_kind: "marked", pnl_filled_usd: 50, pnl_conservative_usd: null },
    ] } } as unknown as Snapshot;
    render(<Telemetry t={buildTelemetry(snap)} />);
    const pl = screen.getByTestId("slip-row-21").textContent ?? "";
    expect(pl).toContain("partial: 6 of 10 sold");
    expect(pl).toContain("$1,600.00");
    expect(pl).toContain("realized+marked");
    const ccj = screen.getByTestId("slip-row-22").textContent ?? "";
    expect(ccj).toContain("ask at decision below the fill");
    expect(ccj).toContain("unknown");
    expect(ccj).not.toContain("partial");
  });

  it("degrades an errored panel to unavailable", () => {
    render(<Telemetry t={buildTelemetry({ slippage: { error: "boom" } } as unknown as Snapshot)} />);
    expect(screen.getByTestId("tel-slip").textContent).toContain("panel unavailable");
  });
});

// #462 §8: the regime series card. Synthetic values only; none is a live reading.
const Q = (p25: number, p50: number, p75: number, n = 48) => ({ p25, p50, p75, n });
const REGIME = {
  status: "ok", as_of: "2026-11-20", R: 49, R_adopted: "2026-11-18", nights: 3, min_sessions: 120, coverage_min: 0.7, note: "internal",
  date: "2026-11-05", segment: "R 2026-11-18 · rv252 · term v1", coverage: 0.9796, coverage_low: false,
  S1: Q(0.71, 0.82, 0.93), S1_percentile: null, S1_accruing: { k: 3, of: 120 },
  spark: [{ d: "2026-11-03", v: 0.8, low: false }, { d: "2026-11-04", v: 0.81, low: true }, { d: "2026-11-05", v: 0.82, low: false }],
  S2_term_slope_vp_p50: 4.5, S3_skew_calls_vp_p50: 3.1, S3_skew_puts_vp_p50: 7.4, S3_put_side_share: 0.25,
  S4_cm270_iv_p50: 0.512, S4_cm270_iv_over_rv63_p50: 0.97,
  S5_display_only: { share_cheap: 0.4, median_iv_rv: 1.05, n: 30, frame_version: ["f1"] },
  live_companion_display_only: { names: 47, coverage: 0.9574, coverage_low: false, S1: Q(0.7, 0.8, 0.9, 45) },
};
const REGIME_BANNED = /cheap|expensive|deploy|buy|sell|pac(e|ing)|signal/i;

describe("regime series card (#462 §8)", () => {
  it("accruing: shows S1 p25/p50/p75 with n, 'accruing k of 120', S2-S4 medians, S5 and the live companion labelled display-only", () => {
    render(<Telemetry t={buildTelemetry({ regime_series: REGIME } as unknown as Snapshot)} />);
    const card = screen.getByTestId("tel-regime").textContent ?? "";
    expect(card).toContain("0.71 / 0.82 / 0.93 over 48 names");
    expect(screen.getByTestId("regime-pctile").textContent).toContain("accruing 3 of 120");
    expect(card).toContain("S2 term slope median 4.5 vp");
    expect(card).toContain("calls 3.1 / puts 7.4 vp (put side 25%)");
    expect(card).toContain("S4 270-day IV median 0.512, ÷ RV63 0.97");
    const disp = screen.getByTestId("regime-display-only").textContent ?? "";
    expect(disp).toContain("Display only. S5");
    expect(disp).toContain("pass share 40%");
    expect(disp).toContain("Display only. Live companion");
    expect(disp).toContain("47 universe names");
    expect(screen.getByTestId("regime-spark")).toBeTruthy();
    expect(screen.getAllByTestId("regime-spark-low")).toHaveLength(1);          // the coverage-low night is a hollow grey mark
    expect(screen.queryByTestId("regime-low")).toBeNull();
  });

  it("percentile live: prints the percentile once the history is long enough", () => {
    const t = buildTelemetry({ regime_series: { ...REGIME, S1_percentile: 0.7312, S1_accruing: null } } as unknown as Snapshot);
    expect(t.regime?.percentile).toBe("73% of its own history at or below");
  });

  it("coverage low: says so, prints no percentile, and greys the numbers", () => {
    const t = buildTelemetry({ regime_series: { ...REGIME, coverage: 0.4082, coverage_low: true, S1_accruing: null } } as unknown as Snapshot);
    expect(t.regime?.percentile).toBe("none (coverage low)");
    render(<Telemetry t={t} />);
    expect(screen.getByTestId("regime-low").textContent).toContain("coverage low: under 70% of the 49 names");
    expect(screen.getByTestId("regime-pctile").textContent).toContain("none (coverage low)");
  });

  it("no term record yet: honest unknown, no numbers; an errored panel reads unavailable", () => {
    const none = { status: "no term records yet", as_of: "2026-11-20", R: 49, R_adopted: "2026-11-18", nights: 0, min_sessions: 120, coverage_min: 0.7, note: "" };
    const { unmount } = render(<Telemetry t={buildTelemetry({ regime_series: none } as unknown as Snapshot)} />);
    expect(screen.getByTestId("tel-regime").textContent).toContain("No term record yet");
    expect(screen.queryByTestId("regime-pctile")).toBeNull();
    unmount();
    render(<Telemetry t={buildTelemetry({ regime_series: { error: "boom" } } as unknown as Snapshot)} />);
    expect(screen.getByTestId("tel-regime").textContent).toContain("panel unavailable");
  });

  it("uses no verdict wording and no colour (neutral greys only) in any state", () => {
    for (const rs of [REGIME, { ...REGIME, coverage_low: true }, { ...REGIME, S1_percentile: 0.05, S1_accruing: null }]) {
      const { unmount, container } = render(<Telemetry t={buildTelemetry({ regime_series: rs } as unknown as Snapshot)} />);
      const card = screen.getByTestId("tel-regime");
      expect(card.textContent ?? "").not.toMatch(REGIME_BANNED);
      // every colour on the card (inline style colours jsdom normalises to rgb(), plus svg stroke / fill) is a neutral
      // slate grey: its channels sit within 30 of each other. A red, green or amber would not.
      const seen: number[][] = [];
      const take = (v: string | null) => {
        const m = v?.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
        const rgb = v?.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        if (rgb) seen.push([+rgb[1], +rgb[2], +rgb[3]]);
        else if (m) { const h = m[1].length === 3 ? m[1].replace(/./g, "$&$&") : m[1]; seen.push([0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16))); }
      };
      for (const el of [card, ...Array.from(card.querySelectorAll<HTMLElement>("*"))]) {
        const st = getComputedStyle(el);
        take(st.color); take(st.backgroundColor); take(el.getAttribute("stroke")); take(el.getAttribute("fill"));
      }
      expect(seen.length).toBeGreaterThan(3);
      expect(seen.every((c) => Math.max(...c) - Math.min(...c) <= 30)).toBe(true);
      expect(container.querySelector("[class*=green],[class*=red],[class*=amber]")).toBeNull();
      unmount();
    }
  });
});
