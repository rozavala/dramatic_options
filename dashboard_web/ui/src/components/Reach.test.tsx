// @vitest-environment jsdom
// Reach panel tests: renders a fixture cards document (document order, no reordering), the digest
// stays behind the collapsible "audit trail" toggle, staleness pill >8d, the explicit absent-state,
// and the safety property — markdown renders through React text nodes (a <script> in a machine-
// generated doc stays inert text; no dangerouslySetInnerHTML anywhere).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Reach, isStale, renderMarkdown, type ReachDoc, type ReachPayload } from "./Reach";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// Fixture mirroring survivor_cards.assemble_cards (charter §3b): NIC before AAA on purpose —
// the panel must render DOCUMENT order, never re-sort.
const CARDS_DOC = `# Survivor cards — 2026-W29

- generated: 2026-07-15T18:00:00+00:00
- digest: records/digests/2026-W29.md
- funnel: 12 extracted -> 9 screened -> 2 survivor(s)
- ordering: alphabetical (no ranking anywhere — charter §3b)

## NIC

- provenance: machine_surfaced
- surfaced via:
  - trade_press/Utility Dive [exact] — Grid orders surge — https://example.com/grid
- screen:
  - price: PASS — $41.20 within band
- premise currency:
  - trailing return 1m / 12m: +2.0% / +31.4%

### Draft thesis (Stage B seam)

_(empty — Stage B, the thesis-drafting layer, is not built; everything above this line is mechanical.)_

## AAA

- provenance: machine_surfaced

## Screened out

- QWTR — failed price [price FAIL · adv PASS]
`;

const DIGEST_DOC = `# Reach digest — 2026-W29

- generated: 2026-07-15T01:04:39+00:00
- provenance: trade_press/agency/orphan_watch

## trade_press

- 2026-07-13 07:02Z — Watch out for <script>alert(1)</script> injection — https://example.com/x
`;

const doc = (over: Partial<ReachDoc> = {}): ReachDoc => ({
  available: true,
  filename: "2026-W29.md",
  week: "2026-W29",
  content: CARDS_DOC,
  mtime: new Date().toISOString(),
  generated: new Date().toISOString(),
  ...over,
});

function stubReach(payload: ReachPayload) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => payload })),
  );
}

describe("Reach", () => {
  it("renders the cards document as the primary view, in document order", async () => {
    stubReach({ cards: doc(), digest: doc({ content: DIGEST_DOC }) });
    render(<Reach />);
    expect(await screen.findByText("NIC")).toBeTruthy();
    expect(screen.getByText("AAA")).toBeTruthy();
    // document order preserved (NIC is written before AAA in the fixture)
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings.indexOf("NIC")).toBeLessThan(headings.indexOf("AAA"));
    // header: week stamp + file name
    expect(screen.getAllByText("2026-W29").length).toBeGreaterThan(0);
    expect(screen.getByText("records/cards/2026-W29.md")).toBeTruthy();
  });

  it("keeps the digest behind the collapsible audit-trail toggle", async () => {
    stubReach({ cards: doc(), digest: doc({ content: DIGEST_DOC }) });
    render(<Reach />);
    await screen.findByText("NIC");
    expect(screen.queryByText(/Reach digest — 2026-W29/)).toBeNull(); // collapsed by default
    const toggle = screen.getByRole("button", { name: /raw digest/i });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText(/Reach digest — 2026-W29/)).toBeTruthy();
  });

  it("shows the stale pill when the digest is older than 8 days", async () => {
    const old = new Date(Date.now() - 9 * 24 * 3600 * 1000).toISOString();
    stubReach({ cards: doc(), digest: doc({ content: DIGEST_DOC, generated: old, mtime: old }) });
    render(<Reach />);
    await screen.findByText("NIC");
    expect(screen.getByText(/stale — digest older than 8 days/)).toBeTruthy();
  });

  it("renders the explicit absent-state (never an error) when documents are missing", async () => {
    stubReach({
      cards: { available: false, reason: "cards/ not found — no weekly documents yet" },
      digest: { available: false, reason: "digests/ not found — no weekly documents yet" },
    });
    render(<Reach />);
    expect(await screen.findByText("No survivor-cards document yet")).toBeTruthy();
    expect(screen.getByText(/cards\/ not found/)).toBeTruthy();
    expect(screen.getByText("no week yet")).toBeTruthy();
  });

  it("renders embedded markup as inert text (sanitized — no HTML injection)", async () => {
    stubReach({ cards: doc(), digest: doc({ content: DIGEST_DOC }) });
    const { container } = render(<Reach />);
    await screen.findByText("NIC");
    fireEvent.click(screen.getByRole("button", { name: /raw digest/i }));
    // the literal "<script>" from the digest is visible TEXT, and no script element exists
    expect(screen.getByText(/<script>alert\(1\)<\/script>/)).toBeTruthy();
    expect(container.querySelector("script")).toBeNull();
  });

  it("has no action affordances — the only button is the digest view toggle", async () => {
    stubReach({ cards: doc(), digest: doc({ content: DIGEST_DOC }) });
    render(<Reach />);
    await screen.findByText("NIC");
    expect(screen.getAllByRole("button").length).toBe(1); // the collapsible toggle only
    expect(screen.queryByRole("textbox")).toBeNull();     // no forms, no inputs, no pick paths
  });

  it("surfaces a fetch failure as an explicit error card", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })));
    render(<Reach />);
    expect(await screen.findByText(/Couldn’t load \/api\/reach: HTTP 503/)).toBeTruthy();
  });
});

describe("renderMarkdown / isStale helpers", () => {
  it("linkifies only verbatim http(s) URLs, with rel=noopener", () => {
    const { container } = render(<div>{renderMarkdown("- see https://example.com/a and javascript:alert(1)")}</div>);
    const links = container.querySelectorAll("a");
    expect(links.length).toBe(1);
    expect(links[0].getAttribute("href")).toBe("https://example.com/a");
    expect(links[0].getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("isStale: fresh → false, >8 days → true, unknown age → false (no false alarm)", () => {
    const now = new Date("2026-07-16T00:00:00Z");
    const iso = (d: number) => new Date(now.getTime() - d * 24 * 3600 * 1000).toISOString();
    expect(isStale({ available: true, generated: iso(2) }, now)).toBe(false);
    expect(isStale({ available: true, generated: iso(9) }, now)).toBe(true);
    expect(isStale({ available: true, generated: null, mtime: iso(9) }, now)).toBe(true); // mtime fallback
    expect(isStale({ available: false }, now)).toBe(false);
  });
});
