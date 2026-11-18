// §10.13 §3 (#508): the held-read timeline view model. Measurement only — never acted on.
// Pinned by the prereg: no trend, no "thesis broken" badge, no colour keyed to exit. Everything here is neutral text.
import type { HeldEntry, HeldLineVM, HeldReadsVM, HeldVerdict, Snapshot } from "./types";

const DASH = "—";
const tf = (v: boolean | null | undefined) => (v == null ? DASH : v ? "T" : "F");

export function criteriaText(v: HeldVerdict): string {
  return `structural ${tf(v.structural)} · under-narrated ${tf(v.under_narrated)} · at inflection ${tf(v.at_inflection)}`;
}

const mult = (m: number | null | undefined) => (m == null ? DASH : `${m.toFixed(2)}×`);

function verdictLine(kind: HeldLineVM["kind"], e: HeldEntry): HeldLineVM {
  return {
    kind, day: e.day ?? DASH, runId: e.run_id, label: e.source + (e.status ? ` · ${e.status}` : ""),
    conviction: e.conviction ?? DASH, include: tf(e.include), criteria: criteriaText(e), note: "",
  };
}

export function buildHeldReads(P: Snapshot): HeldReadsVM {
  const h = P.held_reads;
  const blank: HeldReadsVM = { unavailable: true, note: "measurement only — never acted on (§10.13)", noTable: false,
    falsifierStatus: DASH, markFixNote: "", positions: [] };
  if (!h || (typeof h === "object" && "error" in h)) return blank;
  return {
    unavailable: false, note: h.note, noTable: !h.held_reads_table, falsifierStatus: h.falsifier_status,
    markFixNote: h.mark_fix_note,
    positions: (h.positions ?? []).map((p) => {
      const lines: HeldLineVM[] = [];
      if (p.entry) lines.push(verdictLine("entry", p.entry));
      for (const r of p.reads ?? []) {
        lines.push({
          kind: "held read", day: r.day ?? DASH, runId: r.run_id, label: r.lineage_status ? `lineage ${r.lineage_status}` : DASH,
          conviction: r.conviction ?? DASH, include: tf(r.include), criteria: criteriaText(r),
          note: [r.dropped ? `dropped: ${r.dropped}` : "", r.mark_multiple != null
            ? `mark ${mult(r.mark_multiple)}${r.mark_corrected ? " (corrected ×100, #511)" : ""}` : ""].filter(Boolean).join(" · "),
        });
      }
      for (const s of p.seatings ?? []) lines.push(verdictLine("seating", s));
      for (const f of p.falsifiers ?? []) {
        lines.push({
          kind: "falsifier", day: f.read_at ?? DASH, runId: null, label: f.spec_id ?? DASH, conviction: DASH, include: DASH,
          criteria: DASH,
          note: `${f.metric ?? "?"} ${f.value ?? "?"} vs ${f.threshold ?? "?"}${f.period_end ? ` (Q ${f.period_end})` : ""} · fired ${tf(f.fired)}`,
        });
      }
      const order = { entry: 0, "held read": 1, seating: 1, falsifier: 1 } as const;
      lines.sort((a, b) => order[a.kind] - order[b.kind] || a.day.localeCompare(b.day) || (a.runId ?? 0) - (b.runId ?? 0));
      return {
        id: p.position_id, symbol: p.symbol, dir: p.direction, status: p.status, origin: p.origin,
        opened: p.opened_day ?? DASH, mark: mult(p.mark_multiple), lines,
      };
    }),
  };
}
