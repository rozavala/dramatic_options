// @vitest-environment jsdom
// §10.13 §3 (#508): the held-read timeline. Synthetic data only. Pinned: no trend, no "thesis broken" badge,
// no colour keyed to exit — every line is the same neutral ink.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { fromBackend } from "../data/adapter";
import type { HeldReadsPanel, Snapshot } from "../data/types";
import { MobileApp } from "../mobile/MobileApp";
import { Book } from "./Book";

afterEach(cleanup);

const v = { structural: true, under_narrated: true, at_inflection: false };
const panel = (over: Partial<HeldReadsPanel> = {}): HeldReadsPanel => ({
  note: "measurement only — never acted on (§10.13)", held_reads_table: true, falsifier_status: "ok",
  mark_fix_note: "held reads written before 2026-11-17 stored the mark multiple 100x too small (#511); shown corrected (x100) and flagged",
  positions: [{
    position_id: 6, symbol: "FLNC", direction: "bearish", status: "open", opened_day: "2026-11-04", origin: null,
    mark_multiple: 1.776,
    entry: { proposal_id: 1258, run_id: 1918, day: "2026-11-03", conviction: "MODERATE", include: true, ...v, status: "traded", source: "sentinel · rank" },
    reads: [
      { run_id: 2073, day: "2026-11-16", conviction: "LOW", include: false, ...v, dropped: null, lineage_status: "candidate", mark_multiple: 1.68, mark_corrected: true },
      { run_id: 2090, day: "2026-11-17", conviction: "NEUTRAL", include: false, structural: null, under_narrated: null, at_inflection: null,
        dropped: "proposer abstained (NEUTRAL)", lineage_status: "dormant", mark_multiple: 1.776, mark_corrected: false },
    ],
    seatings: [{ proposal_id: 1400, run_id: 2055, day: "2026-11-13", conviction: "LOW", include: false, ...v, status: "dropped", source: "sentinel · fairness" }],
    falsifiers: [{ read_at: "2026-11-10", spec_id: "f-grid", metric: "qtr_yoy", value: "0.12", threshold: "0.0", period_end: "2026-09-30", fired: false }],
  }],
  ...over,
});
const vmWith = (h: unknown) => fromBackend({ held_reads: h, run_dates: {}, run_kinds: {} } as unknown as Snapshot);

describe("adapter · heldReads", () => {
  it("orders the entry first, then every read, seating and falsifier by day, criteria as T/F", () => {
    const h = vmWith(panel()).heldReads;
    const p = h.positions[0];
    expect(p.lines.map((l) => [l.kind, l.day])).toEqual([
      ["entry", "2026-11-03"], ["falsifier", "2026-11-10"], ["seating", "2026-11-13"],
      ["held read", "2026-11-16"], ["held read", "2026-11-17"],
    ]);
    expect(p.lines[0].criteria).toBe("structural T · under-narrated T · at inflection F");
    expect(p.lines[4].criteria).toBe("structural — · under-narrated — · at inflection —");
    expect(p.lines[3].note).toBe("mark 1.68× (corrected ×100, #511)");
    expect(p.lines[4].note).toBe("dropped: proposer abstained (NEUTRAL) · mark 1.78×");
    expect(p.lines[2].label).toBe("sentinel · fairness · dropped");
    expect(p.mark).toBe("1.78×");
  });

  it("degrades without throwing", () => {
    expect(fromBackend({} as unknown as Snapshot).heldReads.unavailable).toBe(true);
    const err = fromBackend({ held_reads: { error: "boom" } } as unknown as Snapshot);
    expect(err.heldReads.unavailable).toBe(true);
    expect(err.degraded).toContain("held_reads");
  });
});

const FORBIDDEN = /broken|intact|trend|thesis (is )?(broken|failing|weakening)|exit now|sell|warning/i;

describe("Book · held reads (desktop)", () => {
  it("shows every line, the measurement-only label, and no badge / trend / exit colour", () => {
    render(<Book vm={vmWith(panel())} />);
    const pos = screen.getByTestId("held-pos-FLNC");
    expect(within(pos).getAllByTestId("held-line")).toHaveLength(5);
    expect(screen.getByText(/measurement only — never acted on \(§10\.13\)/)).toBeTruthy();
    const timeline = screen.getByTestId("held-timeline");
    expect(timeline.textContent).not.toMatch(FORBIDDEN);
    // no colour keyed to anything: every cell in the timeline uses the two neutral inks only
    const colours = new Set([...timeline.querySelectorAll<HTMLElement>("*")].map((e) => e.style.color).filter(Boolean));
    for (const c of colours) expect(["rgb(44, 54, 69)", "rgb(106, 114, 128)"]).toContain(c);
    // no chip / badge / sparkline / svg inside the timeline
    expect(timeline.querySelector("svg, [class*=chip], [class*=badge], [data-level]")).toBeNull();
  });

  it("explains an unavailable or empty panel", () => {
    render(<Book vm={fromBackend({} as unknown as Snapshot)} />);
    expect(screen.getByTestId("held-unavailable")).toBeTruthy();
    cleanup();
    render(<Book vm={vmWith(panel({ positions: [] }))} />);
    expect(screen.getByTestId("held-empty")).toBeTruthy();
  });
});

describe("MobileApp · held reads", () => {
  it("renders the stacked timeline on the Book tab", () => {
    const vm = vmWith(panel());
    render(<MobileApp vm={vm} loading={false} error={null} fatal={null} refresh={() => {}} />);
    fireEvent.click(screen.getByRole("tab", { name: "Book" }));
    const pos = screen.getByTestId("held-pos-FLNC");
    expect(within(pos).getAllByTestId("held-line")).toHaveLength(5);
    expect(screen.getByTestId("held-timeline").textContent).not.toMatch(FORBIDDEN);
  });
});
