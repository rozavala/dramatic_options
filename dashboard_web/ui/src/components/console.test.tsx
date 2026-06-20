// @vitest-environment jsdom
// Section render smoke tests (H3): the consoles render on a near-empty (accruing) VM without crashing, the
// fail-soft degraded banner (B1) and schema-warning strip (B2) appear, and the fatal state renders full-panel.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { fromBackend } from "../data/adapter";
import type { ConsoleProps, Snapshot } from "../data/types";
import { MobileApp } from "../mobile/MobileApp";
import { DesktopConsole } from "./DesktopConsole";

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
    expect(screen.getAllByRole("tab").length).toBe(5);
  });

  it("surfaces a degraded banner on mobile too (B1)", () => {
    render(<MobileApp {...props({ vm: vmFrom({ council: { error: "boom" } }) })} />);
    expect(screen.getByText(/unavailable \(fail-soft\)/i)).toBeTruthy();
  });
});
