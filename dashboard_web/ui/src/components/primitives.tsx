import type { CSSProperties, ReactNode } from "react";

import { signal, type Level } from "../theme/tokens";

/** Signal dot with the tonal halo (box-shadow ring) from the hi-fi reference. */
export function StatusDot({ level, size = 9 }: { level: Level; size?: number }) {
  const s = signal[level];
  return (
    <span
      style={{ width: size, height: size, borderRadius: "50%", flex: "none", background: s.text, boxShadow: `0 0 0 3px ${s.bg}` }}
    />
  );
}

/** Pill chip: status `text` on status `bg` with status `border`. */
export function Chip({ level, children, style }: { level: Level; children: ReactNode; style?: CSSProperties }) {
  const s = signal[level];
  return (
    <span
      className="inline-flex items-center whitespace-nowrap font-medium"
      style={{ fontSize: 10.5, letterSpacing: ".3px", padding: "3px 9px", borderRadius: 20, color: s.text, background: s.bg, border: `1px solid ${s.border}`, ...style }}
    >
      {children}
    </span>
  );
}

/** White 16px card with the standard elevation; border overridable. */
export function Card({ children, className = "", style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <div className={`bg-white border rounded-card shadow-card ${className}`} style={{ borderColor: "#cbd0da", ...style }}>
      {children}
    </div>
  );
}
