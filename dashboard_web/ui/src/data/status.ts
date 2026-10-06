// Status maps — verdict/level → display vocabulary. Ported verbatim from the prototype's P()/col()/VL/ST
// so colors and labels match the hi-fi reference exactly. Pure (no React); the single place these rules live.

import type { Level } from "../theme/tokens";

export type CouncilVerdict =
  | "ROUNDTRIP_CONFIRMED" | "PROPOSER_CLEAN_NO_ROUNDTRIP" | "ROUNDTRIP_DEGRADED" | "PARSE_FAIL" | "NO_COUNCIL";
export type T4Verdict = "MET" | "PASS" | "NOT_OK" | "BREACH" | "VACUOUS" | "IN_PROGRESS" | null;
export type DisplayState = "pass" | "blocked" | "vacuous" | "inprogress" | "accruing" | "deferred";

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
// IN_PROGRESS→inprogress, null/unknown→accruing). Only applied to CHECKABLE conditions — a non-checkable row
// is "deferred" regardless of any verdict it carries (A1: the backend never counts it as a gate).
const T4_STATE: Record<string, DisplayState> = {
  MET: "pass", PASS: "pass", BREACH: "blocked", NOT_OK: "blocked", VACUOUS: "vacuous", IN_PROGRESS: "inprogress",
};
export const t4State = (v: T4Verdict): DisplayState => (v && T4_STATE[v]) || "accruing";

// A1: the row state honoring `checkable`. !checkable → "deferred" (verdict deferred to the null layer / human),
// matching the Streamlit tag "(accruing — verdict deferred)"; checkable → the verdict→state map above.
export const t4RowState = (checkable: boolean, v: T4Verdict): DisplayState => (checkable ? t4State(v) : "deferred");

// states that render as "accruing-like" (muted ◷, pulse).
export const isAccruingState = (s: DisplayState): boolean => s === "accruing" || s === "deferred";

// display state → [Level, icon glyph, tag label] for the T4 checklist rows / ring.
export const STATE_PRESENT: Record<DisplayState, [Level, string, string]> = {
  pass:       ["ok", "✓", "PASS"],          // ✓
  blocked:    ["warn", "✕", "BLOCKED"],      // ✕
  vacuous:    ["mute", "◯", "VACUOUS"],      // ◯
  inprogress: ["acc", "◐", "IN PROGRESS"],   // ◐
  accruing:   ["mute", "◷", "ACCRUING"],     // ◷ (pulses)
  deferred:   ["mute", "◷", "DEFERRED"],     // ◷ (pulses) — non-checkable, verdict deferred
};

// CALL/PUT label from the direction vocabulary (A6 — one place; the components used to each re-map this).
export const directionLabel = (d: string): string => (d === "bullish" ? "CALL" : d === "bearish" ? "PUT" : d.toUpperCase());

// E2: a "Nh ago" / "Nd ago" label + a staleness Level from an ISO timestamp, relative to now.
export function relativeAge(iso?: string | null): { label: string; level: Level } {
  if (!iso) return { label: "", level: "mute" };
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return { label: "", level: "mute" };
  const mins = Math.max(0, Math.round((Date.now() - t) / 60_000));
  const label = mins < 1 ? "just now" : mins < 60 ? `${mins}m ago` : mins < 1440 ? `${Math.round(mins / 60)}h ago` : `${Math.round(mins / 1440)}d ago`;
  const level: Level = mins > 1440 ? "bad" : mins > 240 ? "warn" : "ok"; // >24h bad, >4h warn
  return { label, level };
}

// cluster fill fraction → Level (<70% green, 70–90% amber, ≥90% red, 0 mute).
export const clusterLevel = (frac: number): Level => (frac >= 0.9 ? "bad" : frac >= 0.7 ? "warn" : frac > 0 ? "ok" : "mute");

// open-position mark÷entry multiple → Level (≥1.5 green, ≥1.0 accent, else mute).
export const markLevel = (m: number): Level => (m >= 1.5 ? "ok" : m >= 1.0 ? "acc" : "mute");
