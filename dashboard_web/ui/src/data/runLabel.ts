// ONE shared formatter for "which run is this" (issue #354). A bare `#1816` says nothing about WHEN — a
// stale council session and a fresh one look identical — so every run id the UI prints goes through here:
//   L1 #1816 · Mon 2026-10-26 15:45 ET
// Dates are always America/New_York (the market's clock; the L1 slot is 15:45 ET), never the browser's zone
// and never the UTC the DB stores. `started_at` arrives either tz-aware ISO ("…T19:45:00+00:00") or SQLite's
// naive `datetime('now')` ("2026-09-04 19:45:04"), which is UTC — mirrors dashboard_data._parse_dt.

// run_id → started_at / run_id → kind ("L1", "L0", …; derived from runs.mode server-side), each fail-soft.
type Wire = Record<string, string> | { error: string } | null | undefined;
export type RunDates = { at: Wire; kind: Wire } | null | undefined;

const ET = "America/New_York";
const fmt = new Intl.DateTimeFormat("en-US", {
  timeZone: ET, weekday: "short", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});

/** Parse a backend timestamp (naive ⇒ UTC) → epoch ms, or null. */
export function parseBackendTs(ts?: string | null): number | null {
  if (!ts) return null;
  const s = String(ts).trim();
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(s);
  const t = Date.parse(hasZone ? s : `${s.replace(" ", "T")}Z`);
  return Number.isNaN(t) ? null : t;
}

function etParts(ts?: string | null): { wd: string; date: string; hm: string } | null {
  const t = parseBackendTs(ts);
  if (t == null) return null;
  const p: Record<string, string> = {};
  for (const part of fmt.formatToParts(new Date(t))) p[part.type] = part.value;
  return { wd: p.weekday, date: `${p.year}-${p.month}-${p.day}`, hm: `${p.hour}:${p.minute}` };
}

/** ET calendar date "YYYY-MM-DD" of a backend timestamp, or null. */
export function etDate(ts?: string | null): string | null {
  return etParts(ts)?.date ?? null;
}

/** "Mon 2026-10-26 15:45 ET", or null when the timestamp is missing/unparseable. */
export function formatEtStamp(ts?: string | null): string | null {
  const p = etParts(ts);
  return p ? `${p.wd} ${p.date} ${p.hm} ET` : null;
}

/** "L1 #1816 · Mon 2026-10-26 15:45 ET". An undated run says so rather than printing a bare id. */
export function formatRunLabel(runId: number | null | undefined, startedAt?: string | null, kind = "run"): string {
  if (runId == null) return "—";
  const stamp = formatEtStamp(startedAt);
  return `${kind} #${runId} · ${stamp ?? "date unavailable"}`;
}

const pick = (w: Wire, id: number): string | undefined => (w && !("error" in w) ? w[String(id)] : undefined);

/** Label a run id from the snapshot's `run_dates` (started_at) + `run_kinds` (layer, from runs.mode) maps. An
 *  unknown kind prints as the neutral "run", never a guessed "L1". */
export function runLabel(dates: RunDates, runId: number | null | undefined): string {
  if (runId == null) return "—";
  return formatRunLabel(runId, pick(dates?.at, runId), pick(dates?.kind, runId));
}
