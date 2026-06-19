// Design tokens — the navy/signal system from the redesign handoff. Single source of truth for color,
// type, radius and elevation; mirrored into tailwind.config for className use. All values are exact.

export const color = {
  // chrome (navy frame)
  navy900: "#0f1b32", navy700: "#1d2c46", navy600: "#2a3c5e",
  navActiveBg: "rgba(120,162,255,0.18)", navActiveText: "#eaf1ff", navIdleText: "#aeb8cc",
  navSub: "#8a98b0", tabIdleMobile: "#7d8aa3",
  // content surfaces
  canvas: "#fafbfc", canvasMobile: "#f4f6f8", card: "#ffffff",
  cardBorder: "#cbd0da", cardBorderMobile: "#e3e6ec",
  innerTile: "#f6f8fa", innerBorder: "#edf0f4", track: "#edf0f4",
  // text
  ink: "#141b28", ink2: "#2c3645", ink3: "#414956", ink4: "#5f6675", inkFaint: "#8b919b",
  accent: "#1558d6",
  // four-color section-card dots (decorative, in order)
  dotBlue: "#1558d6", dotRed: "#ea4335", dotAmber: "#f9ab00", dotGreen: "#0b8a3e",
} as const;

// Signal palette — used as TONAL CONTAINERS {text/icon, bg, border}. `acc` is the blue primary.
export type Level = "ok" | "warn" | "bad" | "acc" | "mute";
export const signal: Record<Level, { text: string; bg: string; border: string }> = {
  acc:  { text: "#1558d6", bg: "#dbe7ff", border: "#a7c4fb" },
  ok:   { text: "#0b8a3e", bg: "#d2efda", border: "#86ce9b" },
  warn: { text: "#9a5b04", bg: "#fce6a6", border: "#f4cb66" },
  bad:  { text: "#d12d1c", bg: "#fbd8d2", border: "#f2a99e" },
  mute: { text: "#4b5667", bg: "#eef2f8", border: "#d2dae8" },
};

export const font = {
  sans: "'Roboto', system-ui, sans-serif",
  mono: "'Roboto Mono', ui-monospace, monospace",
} as const;

export const radius = { card: 16, tile: 12, pill: 20, navItem: 24 } as const;
export const shadow = {
  card: "0 1px 2px 0 rgba(60,64,67,0.10), 0 1px 3px 1px rgba(60,64,67,0.05)",
  cardHover: "0 1px 3px 0 rgba(60,64,67,0.16), 0 4px 8px 3px rgba(60,64,67,0.10)",
} as const;

export const accruePulse = "accruePulse 2.4s ease-in-out infinite"; // T4 accruing rows + striped tail bars
