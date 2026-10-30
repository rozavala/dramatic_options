// @vitest-environment jsdom
// Risk & Feeds kill tile: dollar distance to the halt, halt fraction from the snapshot (config), dry-months note.
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fromBackend } from "../data/adapter";
import type { Snapshot } from "../data/types";
import { MobileApp } from "../mobile/MobileApp";
import { Safety } from "./Safety";

beforeEach(() => { vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {}))); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const DRY = "Dry-months leg: not computed (pending Rodrigo)";
// $10,000 book frame; 6.83% drawdown = $683 lost; the halt fraction is the variable under test
const snap = (halt: number | undefined): Snapshot => ({
  account: { broker_equity: 100000, delta_vs_frame: 0, headroom: 5000, equity_series: [], frame: { frame_equity: 100000, book_budget: 10000, per_name_cap: 1000, cluster_cap: 2000, max_open: 15 } },
  risk: { kill_rule: { tripped: false, reasons: [], book_drawdown: 0.0683, have_marks: true, ...(halt === undefined ? {} : { drawdown_halt: halt }) },
    book: { open: 3, max: 15, open_premium: 1500, budget: 10000 }, clusters: [] },
}) as unknown as Snapshot;

describe("kill tile — dollar distance to the halt", () => {
  it("desktop: shows $1,317 of open-book mark loss to the halt, the config halt %, and the dry-months line", () => {
    const { container, getByTestId } = render(<Safety vm={fromBackend(snap(0.2))} />);
    expect(getByTestId("kill-distance").textContent).toBe("$1,317 of open-book mark loss to the halt");
    expect(container.textContent).toContain("halts new entries at 20%");
    expect(container.textContent).toContain(DRY);
  });

  it("desktop: the halt % and the dollar figure follow the snapshot's drawdown_halt", () => {
    const { container, getByTestId } = render(<Safety vm={fromBackend(snap(0.25))} />);
    expect(getByTestId("kill-distance").textContent).toBe("$1,817 of open-book mark loss to the halt");
    expect(container.textContent).toContain("halts new entries at 25%");
    expect(container.textContent).not.toContain("halts new entries at 20%");
  });

  it("desktop: no halt in the snapshot ⇒ dashes, not a hard-coded 20%", () => {
    const { container, getByTestId } = render(<Safety vm={fromBackend(snap(undefined))} />);
    expect(getByTestId("kill-distance").textContent).toBe("— of open-book mark loss to the halt");
    expect(container.textContent).toContain("halts new entries at —");
    expect(container.textContent).not.toContain("—%");
  });

  it("mobile: the Safety tab shows the same dollar figure, halt % and dry-months line", () => {
    const { container, getByRole } = render(<MobileApp vm={fromBackend(snap(0.2))} loading={false} error={null} fatal={null} refresh={() => {}} />);
    fireEvent.click(getByRole("tab", { name: "Safety" }));
    expect(container.textContent).toContain("halt 20%");
    expect(container.textContent).toContain("$1,317 of open-book mark loss to the halt");
    expect(container.textContent).toContain(DRY);
  });

  it("desktop: with nothing marked yet the full distance is flagged as unmeasured", () => {
    const s = snap(0.2);
    const vm = fromBackend({ ...s, risk: { ...s.risk, kill_rule: { ...s.risk.kill_rule, book_drawdown: 0, have_marks: false } } } as Snapshot);
    const { getByTestId } = render(<Safety vm={vm} />);
    expect(getByTestId("kill-distance").textContent).toBe("$2,000 of open-book mark loss to the halt (no marks yet)");
  });

  it("mobile: halt % follows the snapshot", () => {
    const { container, getByRole } = render(<MobileApp vm={fromBackend(snap(0.25))} loading={false} error={null} fatal={null} refresh={() => {}} />);
    fireEvent.click(getByRole("tab", { name: "Safety" }));
    expect(container.textContent).toContain("halt 25%");
    expect(container.textContent).toContain("$1,817 of open-book mark loss to the halt");
  });
});
