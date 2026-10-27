import { useState } from "react";

import type { OutsideFrameVM, TailFigure } from "../data/types";
import { signal } from "../theme/tokens";
import { Chip } from "./primitives";

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
              <span>{o.symbol} · {o.kind} · {o.book}</span>
              <span style={{ color: signal.mute.text }}>{o.moneyness != null ? `${(o.moneyness * 100).toFixed(1)}%` : "—"} · {o.status}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
