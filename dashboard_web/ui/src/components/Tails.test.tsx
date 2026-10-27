// @vitest-environment jsdom
// #352 render checks: the Edge tails show the in-frame figure with the with-legacy one beside it, and the
// "N outside-frame" chip expands to exactly the tagged positions. Synthetic data only.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { fromBackend } from "../data/adapter";
import type { Snapshot } from "../data/types";
import { MobileApp } from "../mobile/MobileApp";
import { Edge } from "./Edge";

afterEach(cleanup);

const ci = (n: number, p95: number | null) => ({ n, p95, ci90: null, flag: null });
const pos = (id: number, symbol: string) => ({
  book: "shadow", id, symbol, direction: "bearish", structure_kind: "P", contract_symbol: `${symbol}P`, moneyness: 0.425, status: "closed",
});
const vmWith = (performance: Record<string, unknown>) => fromBackend({ performance } as unknown as Snapshot);
const base = { real: ci(11, 3.1), shadow_all: ci(18, 2.35), nogate_union_nogate: ci(22, 1.9), nogate_basket_nogate: ci(14, 1.55) };
const taggedVm = () => vmWith({
  p95_ci: { ...base, shadow_all_in_frame: ci(15, 4.2), real_in_frame: ci(11, 3.1), nogate_union_nogate_in_frame: ci(22, 1.9), nogate_basket_nogate_in_frame: ci(14, 1.55) },
  outside_frame: [pos(7, "STUB"), pos(9, "KLAR"), pos(11, "UROY")],
});
const untaggedVm = () => vmWith({ p95_ci: base, outside_frame: [] });

describe("Edge tails (#352)", () => {
  it("tagged: both numbers shown, a chip with the count, list hidden until expanded", () => {
    render(<Edge vm={taggedVm()} />);
    expect(screen.getByText("4.20×")).toBeTruthy();                        // in-frame first
    expect(screen.getByText(/with legacy 2\.35× \(18\)/)).toBeTruthy();    // with-legacy beside it
    expect(screen.getAllByTestId("with-legacy")).toHaveLength(1);          // only the book the tags changed
    const chip = screen.getByRole("button", { name: /3 outside-frame/ });
    expect(chip.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByTestId("outside-frame-list")).toBeNull();
  });

  it("the chip's expanded list matches state.outside_frame_positions", () => {
    render(<Edge vm={taggedVm()} />);
    fireEvent.click(screen.getByRole("button", { name: /3 outside-frame/ }));
    const items = within(screen.getByTestId("outside-frame-list")).getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual([
      expect.stringContaining("STUB"), expect.stringContaining("KLAR"), expect.stringContaining("UROY"),
    ]);
  });

  it("untagged: one number per book and no chip", () => {
    render(<Edge vm={untaggedVm()} />);
    expect(screen.getByText("3.10×")).toBeTruthy();
    expect(screen.queryByTestId("with-legacy")).toBeNull();
    expect(screen.queryByTestId("outside-frame")).toBeNull();
    expect(screen.queryByText(/outside-frame/)).toBeNull();
  });
});

describe("mobile Edge tails (#352)", () => {
  const props = (vm: ReturnType<typeof taggedVm>) => ({ vm, loading: false, error: null, fatal: null, refresh: () => {} });
  const openEdge = (vm: ReturnType<typeof taggedVm>) => {
    render(<MobileApp {...props(vm)} />);
    fireEvent.click(screen.getByRole("tab", { name: "Edge" }));
  };

  it("tagged: shows both numbers and the chip", () => {
    openEdge(taggedVm());
    expect(screen.getByText(/with legacy 2\.35× \(18\)/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /3 outside-frame/ })).toBeTruthy();
  });

  it("untagged: no chip, no with-legacy figure", () => {
    openEdge(untaggedVm());
    expect(screen.queryByTestId("with-legacy")).toBeNull();
    expect(screen.queryByTestId("outside-frame")).toBeNull();
  });
});
