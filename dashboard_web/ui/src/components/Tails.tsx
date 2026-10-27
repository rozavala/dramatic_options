import { useState } from "react";

import type { OutsideFrameVM, TailFigure } from "../data/types";
import { signal } from "../theme/tokens";
import { Chip } from "./primitives";

// The book names the Edge bars use, keyed by the raw book value on state.outside_frame_positions.
const BOOK_LABEL: Record<string, string> = {
  real: "Real", shadow: "Shadow", union_nogate: "3A · no-gate", basket_nogate: "3B · whole basket",
};
export const bookLabel = (book: string): string => BOOK_LABEL[book] ?? book;

/** moneyness = (strike − spot) / spot, so a put is OTM below spot and a call above it. Says which side of the money. */
export function moneynessLabel(o: Pick<OutsideFrameVM, "kind" | "dir" | "moneyness">): string {
  if (o.moneyness == null) return "—";
  const put = o.kind === "P" || (o.kind !== "C" && o.dir === "bearish");
  const call = o.kind === "C" || (o.kind !== "P" && o.dir === "bullish");
  if (!put && !call) return "—";
  const otm = put ? -o.moneyness : o.moneyness;
  return otm >= 0 ? `${(otm * 100).toFixed(1)}% OTM` : `${(-otm * 100).toFixed(1)}% ITM (wrong side)`;
}

/** "with legacy 2.35× · n 18" — the figure including the tagged outside-frame positions, shown beside the in-frame one. */
export function WithLegacy({ t, style }: { t: TailFigure; style?: React.CSSProperties }) {
  if (!t.withLegacy) return null;
  const w = t.withLegacy;
  return (
    <span data-testid="with-legacy" className="font-mono" style={{ color: "#6a7280", fontWeight: 400, whiteSpace: "nowrap", ...style }}>
      with legacy {w.p95 != null ? `${w.p95.toFixed(2)}×` : "accruing"} ({w.n})
    </span>
  );
}

/** The "N outside-frame" chip; tap/click expands the tagged positions (state.outside_frame_positions). Renders nothing with no tags. */
export function OutsideFrameChip({ items, compact = false }: { items: OutsideFrameVM[]; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;
  return (
    <div data-testid="outside-frame">
      <button
        type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)}
        style={{ background: "none", border: 0, padding: 0, cursor: "pointer", font: "inherit" }}
      >
        <Chip level="mute" style={compact ? { fontSize: 9, padding: "2px 7px" } : undefined}>
          {items.length} outside-frame {open ? "▴" : "▾"}
        </Chip>
      </button>
      {open && (
        <ul data-testid="outside-frame-list" style={{ listStyle: "none", margin: "8px 0 0", padding: 0, textAlign: "left" }}>
          {items.map((o, i) => (
            <li key={`${o.book}-${o.symbol}-${i}`} className="flex justify-between font-mono" style={{ gap: 10, fontSize: compact ? 10.5 : 11.5, color: "#414956", padding: "3px 0", borderTop: "1px solid #edf0f4" }}>
              <span>{o.symbol} · {o.kind} · {bookLabel(o.book)}</span>
              <span style={{ color: signal.mute.text }}>{moneynessLabel(o)} · {o.status}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
