// @vitest-environment jsdom
// Section render smoke tests (H3): the consoles render on a near-empty (accruing) VM without crashing, the
// fail-soft degraded banner (B1) and schema-warning strip (B2) appear, and the fatal state renders full-panel.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { fromBackend } from "../data/adapter";
import type { ConsoleProps, Snapshot } from "../data/types";
import { MobileApp } from "../mobile/MobileApp";
import { Book } from "./Book";
import { DesktopConsole } from "./DesktopConsole";
import { Safety } from "./Safety";
import { StatusBanner } from "./StatusBanner";

afterEach(cleanup);

// fromBackend tolerates a near-empty snapshot (every read is guarded) → a fully-defaulted "accruing" VM.
const vmFrom = (over: Record<string, unknown> = {}) => fromBackend(over as unknown as Snapshot);
const props = (over: Partial<ConsoleProps> = {}): ConsoleProps => ({
  vm: vmFrom(), loading: false, error: null, fatal: null, refresh: () => {}, ...over,
});

describe("DesktopConsole", () => {
  it("renders the overview on an empty (accruing) VM without crashing", () => {
    render(<DesktopConsole {...props()} />);
    expect(screen.getAllByText("Overview").length).toBeGreaterThan(0); // rail label + topbar title
    expect(screen.getByText("The road to go-live")).toBeTruthy();
  });

  it("surfaces a fail-soft {error} panel as a degraded banner, not a silent zero (B1)", () => {
    render(<DesktopConsole {...props({ vm: vmFrom({ risk: { error: "OperationalError: boom" } }) })} />);
    const banner = screen.getByText(/unavailable \(fail-soft\)/i);
    expect(banner.textContent).toContain("risk"); // names the crashed panel
  });

  it("renders the schema-warning strip when present (B2)", () => {
    render(<DesktopConsole {...props({ vm: vmFrom({ header: { schema_warning: "schema 13 < expected 14" } }) })} />);
    expect(screen.getByText(/schema 13 < expected 14/)).toBeTruthy();
  });

  it("renders the fatal state full-panel with the resolution hint (B3)", () => {
    render(<DesktopConsole {...props({ vm: null, fatal: "no database at /x — set DRAMATIC_DB" })} />);
    expect(screen.getByText("Snapshot unavailable")).toBeTruthy();
    expect(screen.getByText(/no database at \/x/)).toBeTruthy();
  });

  it("shows skeletons (not 'No snapshot.') while the first fetch is loading (F1)", () => {
    render(<DesktopConsole {...props({ vm: null, loading: true })} />);
    expect(screen.queryByText("No snapshot.")).toBeNull();
  });
});

describe("MobileApp", () => {
  it("renders on an empty VM and exposes the tab bar as a tablist (G1)", () => {
    render(<MobileApp {...props()} />);
    expect(screen.getByRole("tablist")).toBeTruthy();
    expect(screen.getAllByRole("tab").length).toBe(7); // overview/safety/edge/pipeline/book/reach/curation
  });

  it("surfaces a degraded banner on mobile too (B1)", () => {
    render(<MobileApp {...props({ vm: vmFrom({ council: { error: "boom" } }) })} />);
    expect(screen.getByText(/unavailable \(fail-soft\)/i)).toBeTruthy();
  });
});

// Diana item 3: the console leads with the Dramatic book value; the broker number is relabelled + secondary.
describe("book value leads, broker equity is secondary", () => {
  const bookVm = () => vmFrom({ account: { broker_equity: 99120, delta_vs_frame: -880, book_value: { value: 100200, as_of: null, note: null } } });

  it("desktop Safety shows the book value and the 'Broker equity (shared account)' label", () => {
    render(<Safety vm={bookVm()!} />);
    expect(screen.getByText("Dramatic book value")).toBeTruthy();
    expect(screen.getByText("$100,200")).toBeTruthy();
    expect(screen.getByText(/Broker equity \(shared account\)/)).toBeTruthy();
    expect(screen.getByText("$99,120")).toBeTruthy();
    expect(screen.queryByText("Paper equity")).toBeNull();
  });

  it("mobile Safety shows the same label", () => {
    render(<MobileApp {...props({ vm: bookVm() })} />);
    fireEvent.click(screen.getByRole("tab", { name: "Safety" }));
    expect(screen.getByText("Dramatic book value")).toBeTruthy();
    expect(screen.getByText("$100,200")).toBeTruthy();
    expect(screen.getByText(/Broker equity \(shared account\)/)).toBeTruthy();
  });
});

// #306: the upcoming-actions read — the timers' next fire on the heartbeat pills, the known exit dates on the book.
describe("upcoming actions (#306)", () => {
  const beat = (next_at: string | null) => ({ at: "2026-10-14T16:00:00+00:00", age_hours: 0, status: "ONLINE", stale: false, next_at });

  it("shows the next fire on each timer pill when scheduled", () => {
    const vm = vmFrom({ header: { now: "2026-10-14T16:02:00+00:00", cycle: beat("2026-10-14 16:32:00"), council: beat("2026-10-14 19:45:00"), discovery: beat("2026-10-18 12:00:00") } });
    render(<StatusBanner vm={vm} />);
    expect(screen.getByText("· next in 30m")).toBeTruthy();
    expect(screen.getByText("· next in 4h")).toBeTruthy();
    expect(screen.getByText("· next in 92h")).toBeTruthy();
    expect(screen.queryByText("· not scheduled")).toBeNull();
  });

  it("reads a null next_at (PROD's disabled timers) as not scheduled, never an error", () => {
    const vm = vmFrom({ header: { now: "2026-10-14T16:02:00+00:00", cycle: beat(null), council: beat(null), discovery: beat(null) } });
    render(<StatusBanner vm={vm} />);
    expect(screen.getAllByText("· not scheduled")).toHaveLength(3); // cycle · council · discovery — not KILL
  });

  it("renders the Expiry + Time-stop columns on the real book", () => {
    const vm = vmFrom({ positions: { real_open: [{ id: 1, symbol: "ACME", direction: "bullish", contract_symbol: "ACME260116C00050000", status: "open", dte: 248, contracts: 1, total_premium: 620, mark: null, origin_conviction: "HIGH", theme: null, expiry: "2026-01-16", time_stop_on: "2025-12-26" }] } });
    render(<Book vm={vm} />);
    expect(screen.getByText("Expiry")).toBeTruthy();
    expect(screen.getByText("Time-stop")).toBeTruthy();
    expect(screen.getByText("2026-01-16")).toBeTruthy();
    expect(screen.getByText("2025-12-26")).toBeTruthy();
  });
});
