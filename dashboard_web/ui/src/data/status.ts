// Status maps — verdict/level → display vocabulary. Ported verbatim from the prototype's P()/col()/VL/ST
// so colors and labels match the hi-fi reference exactly. Pure (no React); the single place these rules live.

import type { Level } from "../theme/tokens";

export type CouncilVerdict =
  | "ROUNDTRIP_CONFIRMED" | "PROPOSER_CLEAN_NO_ROUNDTRIP" | "ROUNDTRIP_DEGRADED" | "PARSE_FAIL" | "NO_COUNCIL";
export type T4Verdict = "MET" | "PASS" | "NOT_OK" | "BREACH" | "VACUOUS" | "IN_PROGRESS" | null;
export type DisplayState = "pass" | "blocked" | "vacuous" | "inprogress" | "accruing";

// system_status.level → palette Level (the Overview banner color).
export const levelFromSystem = (l?: string): Level => (l === "success" ? "ok" : l === "error" ? "bad" : "warn");

// council round-trip verdict → [plain-English label, Level].
const VERDICT: Record<string, [string, Level]> = {
  ROUNDTRIP_CONFIRMED: ["Round-trip confirmed", "ok"],
  PROPOSER_CLEAN_NO_ROUNDTRIP: ["Proposer clean, no round-trip", "warn"],
  ROUNDTRIP_DEGRADED: ["Round-trip degraded", "warn"],
  PARSE_FAIL: ["Parse failure", "bad"],
  NO_COUNCIL: ["No council yet", "mute"],
};
export const verdictDisplay = (v?: string | null): [string, Level] => VERDICT[v ?? ""] ?? ["—", "mute"];

// T4 condition verdict → display state (README map: MET|PASS→pass, BREACH|NOT_OK→blocked, VACUOUS→vacuous,
// IN_PROGRESS→inprogress, null/unknown→accruing).
const T4_STATE: Record<string, DisplayState> = {
  MET: "pass", PASS: "pass", BREACH: "blocked", NOT_OK: "blocked", VACUOUS: "vacuous", IN_PROGRESS: "inprogress",
};
export const t4State = (v: T4Verdict): DisplayState => (v && T4_STATE[v]) || "accruing";

// display state → [Level, icon glyph, tag label] for the T4 checklist rows / ring.
export const STATE_PRESENT: Record<DisplayState, [Level, string, string]> = {
  pass:       ["ok", "✓", "PASS"],          // ✓
  blocked:    ["warn", "✕", "BLOCKED"],      // ✕
  vacuous:    ["mute", "◯", "VACUOUS"],      // ◯
  inprogress: ["acc", "◐", "IN PROGRESS"],   // ◐
  accruing:   ["mute", "◷", "ACCRUING"],     // ◷ (pulses)
};

// cluster fill fraction → Level (<70% green, 70–90% amber, ≥90% red, 0 mute).
export const clusterLevel = (frac: number): Level => (frac >= 0.9 ? "bad" : frac >= 0.7 ? "warn" : frac > 0 ? "ok" : "mute");

// open-position mark÷entry multiple → Level (≥1.5 green, ≥1.0 accent, else mute).
export const markLevel = (m: number): Level => (m >= 1.5 ? "ok" : m >= 1.0 ? "acc" : "mute");
