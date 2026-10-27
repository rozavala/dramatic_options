// @vitest-environment jsdom
// #354 acceptance: no run id appears on any screen without an ET date, and a STALE council shows a STALE chip.
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fromBackend } from "../data/adapter";
import type { Snapshot } from "../data/types";
import { MobileApp } from "../mobile/MobileApp";
import { Overview } from "./Overview";
import { Pipeline } from "./Pipeline";
import { Safety } from "./Safety";

beforeEach(() => {
  // Reach/Curation fetch on mount; the test only cares what the tab renders, so the request just never lands.
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const RUN = 1816;
const STARTED = "2026-10-27 02:30:04"; // naive UTC, near midnight → Mon 2026-10-26 22:30 ET
const beat = (status: "ONLINE" | "STALE") => ({ at: STARTED, age_hours: 3, status, stale: status !== "ONLINE" });

function snap(councilStatus: "ONLINE" | "STALE"): Snapshot {
  return {
    header: { now: STARTED, schema_version: 14, schema_expected: 14, schema_ok: true, kill_switch_engaged: false,
      cycle: beat("ONLINE"), council: beat(councilStatus), discovery: beat("ONLINE") },
    council: {
      health: { run_id: RUN, council_health: "ok", verdict: "ROUNDTRIP_CONFIRMED", proposer: { called: 5, parse_failed: 0 }, roundtrip: { n: 3 }, cost_usd: 0.1 },
      recent: [{ run_id: RUN - 1, started_at: "2026-10-26 19:45:00", kind: "L1", verdict: "ROUNDTRIP_DEGRADED" }, { run_id: RUN, started_at: STARTED, kind: "L1", verdict: "ROUNDTRIP_CONFIRMED" }],
    },
    funnel: { l1_decision: { run_id: RUN } },
    deliberation: [{ run_id: RUN, symbol: "ACME", proposer_direction: "bullish", adversary_stance: "agree", strategist_conviction: "MODERATE" }],
    session: { run_id: RUN, started_at: STARTED, rows: [], profile: {}, low_history: [{ run_id: RUN, started_at: STARTED, low: 2, judged: 5 }] },
    reserve: { run_id: RUN, stamp: null, reserve: [], rank: [], unlabeled: [] },
    null_attempts: { run_id: RUN, books: { null_a: { rows: [] } } },
    forward_catalysts: { stamp: "s", counters_run_id: RUN, counters: { rendered: 1, expired: 0, malformed: 0, stale_flagged: 0 }, pins: [], ledger: null },
    dualread: { n_sessions_total: 1, sessions: [{ run_id: RUN }], tripwires: {} },
    dualread_runtime: { classes: {}, window: 5, last_run: RUN },
    dircoherence: { active: true, stamp: "s", f2_clean: true, runs: [{ run_id: RUN, started_at: STARTED, status: "ok", errors: 0, withheld: [], kept: [], kept_no_accel: [], reached_despite_withheld: [] }] },
    staleness: { latest_lagging: [], runs: [{ run_id: RUN, started_at: STARTED, status: "ok", lagging: [], checked: 4, no_corpus: 0, errors: 0 }] },
    // t4 details are baked server-side (dashboard_data.run_label) — same string runLabel.ts prints
    t4: { conditions: [
      { id: 1, name: "council healthy", checkable: true, verdict: "NOT_OK",
        detail: `need the last 4 council runs ALL ROUNDTRIP_CONFIRMED (≥2, parse_fail censored); blocked by L1 #${RUN - 1} · Mon 2026-10-26 15:45 ET ROUNDTRIP_DEGRADED — L1 #${RUN - 1} · Mon 2026-10-26 15:45 ET ROUNDTRIP_DEGRADED · L1 #${RUN} · Mon 2026-10-26 22:30 ET ROUNDTRIP_CONFIRMED` },
      { id: 2, name: "null reads", checkable: false, verdict: null, detail: "accruing" },
    ], note: "" },
    run_dates: { [String(RUN)]: STARTED, [String(RUN - 1)]: "2026-10-26 19:45:00" },
    run_kinds: { [String(RUN)]: "L1", [String(RUN - 1)]: "L1" },
  } as unknown as Snapshot;
}

const RUN_ID = /#\d+/g;
const DATED = /L[01] #\d+ · (?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{4}-\d{2}-\d{2} \d{2}:\d{2} ET|date unavailable)/g;

// every "#<digits>" in the rendered text must be the head of a full "L1 #id · <ET stamp>" label
function expectNoBareRunIds(text: string) {
  const ids = text.replace(/finding #\d+|\(#\d+\)/g, "").match(RUN_ID) ?? []; // "finding #1" / "(#72)" are record / issue refs, not runs
  const labelled = text.match(DATED) ?? [];
  expect(labelled.length).toBe(ids.length);
}

describe("every run id carries an ET date (#354)", () => {
  const vm = fromBackend(snap("ONLINE"));
  const ui = { Overview, Pipeline, Safety };

  for (const [name, C] of Object.entries(ui)) {
    it(`${name}: no bare run ids`, () => {
      const { container } = render(<C vm={vm} />);
      const text = container.textContent ?? "";
      expect(text).toContain(`L1 #${RUN} · Mon 2026-10-26 22:30 ET`); // ET date, not the UTC 10-27
      expectNoBareRunIds(text);
    });
  }

  it("Overview: the T4 council detail names each run with its ET date", () => {
    const { container } = render(<Overview vm={vm} />);
    expect(container.textContent).toContain(`blocked by L1 #${RUN - 1} · Mon 2026-10-26 15:45 ET`);
  });

  it("the LOW-history tooltip carries the ET date, not a bare run id", () => {
    const { container } = render(<Overview vm={vm} />);
    const tips = [...container.querySelectorAll("[title]")].map((e) => e.getAttribute("title") ?? "").filter((t) => t.includes("#"));
    expect(tips.length).toBeGreaterThan(0);
    for (const t of tips) expect(t).toMatch(/^L1 #\d+ · \w{3} \d{4}-\d{2}-\d{2} \d{2}:\d{2} ET$/);
  });

  // every tab the bottom bar exposes, not just the landing one — a bare id on any of them fails here
  it("Mobile: no bare run ids on any tab", () => {
    const { container, getByRole } = render(<MobileApp vm={vm} loading={false} error={null} fatal={null} refresh={() => {}} />);
    const tabs = ["Overview", "Safety", "Edge", "Pipeline", "Book", "Reach", "Curate"];
    expect(container.querySelectorAll('[role="tab"]')).toHaveLength(tabs.length);
    for (const name of tabs) {
      fireEvent.click(getByRole("tab", { name }));
      expect(getByRole("tab", { name }).getAttribute("aria-selected")).toBe("true");
      expectNoBareRunIds(container.textContent ?? "");
    }
  });

  it("the LOW-history axis shows the full ET date with its year", () => {
    const { container } = render(<Overview vm={vm} />);
    expect(container.textContent).toContain("2026-10-26");
  });
});

describe("STALE chip (#354)", () => {
  it("shows STALE when header.council.status (council_session_stale) is STALE", () => {
    const { container } = render(<Overview vm={fromBackend(snap("STALE"))} />);
    expect(container.textContent).toContain("STALE");
  });

  it("is absent when the council beat is ONLINE", () => {
    const { container } = render(<Overview vm={fromBackend(snap("ONLINE"))} />);
    expect(container.textContent).not.toContain("STALE");
  });
});
