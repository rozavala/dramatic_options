// @vitest-environment jsdom
// #351: the Overview "why no entry" table + tiles (desktop) and the stacked list (mobile). Synthetic data only.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { fromBackend } from "../data/adapter";
import type { Snapshot, WhyNoEntryPanel, WhyNoEntryRow } from "../data/types";
import { MobileApp } from "../mobile/MobileApp";
import { Overview } from "./Overview";

afterEach(cleanup);

const row = (symbol: string, over: Partial<WhyNoEntryRow> = {}): WhyNoEntryRow => ({
  proposal_id: 1, symbol, direction: "bullish", conviction: "LOW", above_floor: false, stage: "below_floor",
  gate_decision: null, veto_stage: "council: below the conviction floor", order: null,
  iv_rv: null, otm_skew: null, expressible: true, structure_note: null, iv_rv_source: null, ...over,
});
const panel = (over: Partial<WhyNoEntryPanel> = {}): WhyNoEntryPanel => ({
  run_id: 1816, empty: false, floor: "MODERATE",
  rows: [
    // reached the gate; the gate stamp says submit-pending but the order was cancelled unfilled
    row("ACME", {
      proposal_id: 2, conviction: "MODERATE", above_floor: true, stage: "to_gate", gate_decision: "submit-pending",
      veto_stage: "submit-pending", iv_rv: 0.934, otm_skew: 3.2, expressible: true,
      order: { kind: "not_filled", result: "not filled — cancelled unfilled", position_id: 2, status: "cancelled",
        contract: "ACME270617C00017000", contracts: 5, premium: 880 },
    }),
    row("RESTO", {
      proposal_id: 3, conviction: "HIGH", above_floor: true, stage: "to_gate", gate_decision: "submit-pending",
      veto_stage: "submit-pending", order: { kind: "resting", result: "resting at the broker (awaiting fill)", position_id: 3,
        status: "pending", contract: "RESTO270115C00012000", contracts: 2, premium: 690 },
    }),
    row("NOSTR", { proposal_id: 4, expressible: false, structure_note: "no_eligible_contract_in_tenor_window", iv_rv: null }),
    row("DARK", { proposal_id: 5, expressible: null, veto_stage: "council: ungrounded (no numeric evidence)", stage: "ungrounded" }),
    row("RICH", { proposal_id: 6, conviction: "HIGH", above_floor: true, stage: "to_gate", gate_decision: "veto-iv-gate",
      veto_stage: "veto-iv-gate", iv_rv: 1.71, otm_skew: 6.0 }),
  ],
  tiles: {
    expressible: { n: 38, of: 50, no_structure: ["NOSTR"], basis: "gate-of-record (opra) read, <=5 weekdays old" },
    last_above_floor: { run_id: 1816, symbol: "ACME", direction: "bullish", conviction: "MODERATE", day: "2026-10-26", days_ago: 1 },
    last_order: { symbol: "ACME", at: "2026-10-26T19:50:00+00:00", run_id: 1816, day: "2026-10-26", days_ago: 1, kind: "not_filled",
      result: "not filled — cancelled unfilled", contract: "ACME270617C00017000", contracts: 5, premium: 880, position_id: 2 },
  },
  totals: { judged: 5, reached_gate: 3, by_stage: {}, by_decision: {}, unattributed_gate_rows: 0 },
  reconciliation: { by_decision_ok: true, stages_ok: true },
  ...over,
});
const vmWith = (w: unknown) => fromBackend({
  why_no_entry: w, run_dates: { "1816": "2026-10-26T19:45:00+00:00" }, run_kinds: { "1816": "L1" },
} as unknown as Snapshot);

describe("adapter · whyNoEntry", () => {
  it("shows the order's real outcome, not the stale gate stamp", () => {
    const vm = vmWith(panel());
    const by = Object.fromEntries(vm.whyNoEntry.rows.map((r) => [r.symbol, r]));
    expect(by.ACME.stoppedAt).toBe("not filled — cancelled unfilled");
    expect(by.ACME.stoppedAt).not.toContain("submit-pending");
    expect(by.ACME.isOrder).toBe(true);
    expect(by.ACME.stoppedLevel).toBe("warn");
    expect(by.ACME.orderDetail).toBe("5× ACME270617C00017000 · $880");
    expect(by.RESTO.stoppedAt).toMatch(/resting at the broker/);
    expect(by.RESTO.stoppedLevel).toBe("ok");
    expect(by.RICH.stoppedAt).toBe("veto-iv-gate");      // no order → the gate's own code
    expect(by.RICH.isOrder).toBe(false);
    expect(by.ACME.ivrv).toBe("0.93");
  });

  it("expressible tri-state and tiles", () => {
    const w = vmWith(panel()).whyNoEntry;
    expect(w.rows.map((r) => r.express)).toEqual(["yes", "yes", "no", "unread", "yes"]);
    expect(w.rows.find((r) => r.symbol === "NOSTR")?.expressNote).toBe("no_eligible_contract_in_tenor_window");
    expect(w.expressible).toEqual({ n: 38, of: 50, noStructure: ["NOSTR"] });
    expect(w.lastAboveFloor).toEqual({ line: "ACME · MODERATE", sub: "1 day ago · Mon 2026-10-26" });
    expect(w.lastOrder?.line).toBe("ACME · not filled — cancelled unfilled");
    expect(w.lastOrder?.sub).toBe("5× ACME270617C00017000 · $880 · 1 day ago · Mon 2026-10-26");
    expect(w.lastOrder?.level).toBe("warn");
  });

  it("missing / errored / empty panels degrade without throwing", () => {
    expect(fromBackend({} as unknown as Snapshot).whyNoEntry.unavailable).toBe(true);
    const err = fromBackend({ why_no_entry: { error: "boom" } } as unknown as Snapshot);
    expect(err.whyNoEntry.unavailable).toBe(true);
    expect(err.degraded).toContain("why_no_entry");
    const e = vmWith(panel({ run_id: null, empty: true, rows: [], tiles: { expressible: { n: 0, of: 0, no_structure: [], basis: "" }, last_above_floor: null, last_order: null } }));
    expect(e.whyNoEntry.unavailable).toBe(false);
    expect(e.whyNoEntry.empty).toBe(true);
    expect(e.whyNoEntry.lastOrder).toBeNull();
  });

  it("flags a reconciliation drift", () => {
    expect(vmWith(panel()).whyNoEntry.warning).toBeNull();
    const w = vmWith(panel({ reconciliation: { by_decision_ok: false, stages_ok: true } })).whyNoEntry;
    expect(w.warning).toMatch(/gate-decision/);
  });
});

describe("Overview · Why no entry (desktop)", () => {
  it("renders a row per name with the real order outcome, n/N, last above-floor and last order", () => {
    render(<Overview vm={vmWith(panel())} />);
    const table = screen.getByTestId("why-table");
    expect(within(table).getAllByRole("row")).toHaveLength(1 + 5);
    const acme = screen.getByTestId("why-row-ACME");
    expect(within(acme).getByTestId("why-stopped").textContent).toContain("not filled — cancelled unfilled");
    expect(within(acme).getByTestId("why-stopped").textContent).not.toContain("submit-pending");
    expect(within(acme).getByTestId("why-stopped").textContent).toContain("5× ACME270617C00017000");
    expect(within(screen.getByTestId("why-row-NOSTR")).getByText("no structure")).toBeTruthy();
    expect(within(screen.getByTestId("why-row-DARK")).getByText("unread")).toBeTruthy();
    expect(screen.getByTestId("why-tile-expressible").textContent).toContain("38 / 50 names");
    expect(screen.getByTestId("why-tile-expressible").textContent).toContain("NOSTR");
    expect(screen.getByTestId("why-tile-above-floor").textContent).toContain("ACME · MODERATE");
    expect(screen.getByTestId("why-tile-above-floor").textContent).toContain("1 day ago");
    expect(screen.getByTestId("why-tile-last-order").textContent).toContain("cancelled unfilled");
  });

  it("explains an unavailable panel and an empty session instead of an empty table", () => {
    render(<Overview vm={fromBackend({} as unknown as Snapshot)} />);
    expect(screen.getByTestId("why-unavailable")).toBeTruthy();
    expect(screen.queryByTestId("why-table")).toBeNull();
    cleanup();
    render(<Overview vm={vmWith(panel({ run_id: null, empty: true, rows: [] }))} />);
    expect(screen.getByTestId("why-empty")).toBeTruthy();
  });

  it("shows the drift warning", () => {
    render(<Overview vm={vmWith(panel({ reconciliation: { by_decision_ok: true, stages_ok: false } }))} />);
    expect(screen.getByText(/no longer total back to the council-stage funnel/)).toBeTruthy();
  });
});

describe("MobileApp · Why no entry", () => {
  it("renders the stacked list and the same tiles on the Overview tab", () => {
    const vm = vmWith(panel());
    render(<MobileApp vm={vm} loading={false} error={null} fatal={null} refresh={() => {}} />);
    const list = screen.getByTestId("why-list");
    expect(within(list).getAllByTestId(/^why-row-/)).toHaveLength(5);
    expect(within(screen.getByTestId("why-row-ACME")).getByTestId("why-stopped").textContent).toContain("cancelled unfilled");
    expect(screen.getByTestId("why-tile-expressible").textContent).toContain("38 / 50");
    expect(screen.getByTestId("why-tile-last-order").textContent).toContain("ACME");
  });
});
