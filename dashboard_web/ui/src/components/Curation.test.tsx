// @vitest-environment jsdom
// The interactive curation tools: renders both forms, and POSTs to the pure /api/curation/draft endpoint
// (mocked) → renders the drafted command. Sanitization itself is covered by the API + dashboard_data tests.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Curation } from "./Curation";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Curation", () => {
  it("renders both tools without crashing", () => {
    render(<Curation />);
    expect(screen.getByText("Feasibility screen")).toBeTruthy();
    expect(screen.getByText("New theme")).toBeTruthy();
  });

  it("drafts the screen command via the POST endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        kind: "screen",
        tickers: ["AMBA", "MBLY"],
        dropped: 1,
        command:
          "cd ~/dramatic_options && PYTHONPATH=. venv/bin/python scripts/probe_basket_feasibility.py AMBA MBLY",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Curation />);
    fireEvent.change(screen.getByPlaceholderText("AMBA MBLY CF MOS IPI"), {
      target: { value: "amba mbly $(x)" },
    });
    fireEvent.click(screen.getByText("Build command"));

    await waitFor(() => expect(screen.getByText(/probe_basket_feasibility\.py AMBA MBLY/)).toBeTruthy());
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/curation/draft"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});
