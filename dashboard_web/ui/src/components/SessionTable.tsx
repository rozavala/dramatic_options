import type { SessionVM } from "../data/types";
import { signal } from "../theme/tokens";
import { Chip } from "./primitives";

const GRID = "70px 60px 90px 90px 84px 1fr";
const viaLevel = (via: string) => (via === "reserve" || via === "fairness" ? "acc" : "mute");

/** The latest council session, per name: proposer → adversary → strategist · via (slate provenance) · the
 *  streak/note (Overview) or the strategist's weakest point (Council & Pipeline). Shared by both sections. */
export function SessionTable({ session, lastCol }: { session: SessionVM; lastCol: "streak" | "weakest" }) {
  if (!session.rows.length) {
    return <div style={{ fontSize: 12.5, color: "#5f6675", padding: "12px 0" }}>No council session recorded yet.</div>;
  }
  return (
    <div>
      <div className="grid" style={{ gridTemplateColumns: GRID, gap: 10, padding: "0 4px 8px", borderBottom: "1px solid #cbd0da", fontSize: 10.5, color: "#6a7280", textTransform: "uppercase", letterSpacing: ".6px", fontWeight: 500 }}>
        <span>Name</span><span>Proposer</span><span>Adversary</span><span>Strategist</span><span>Via</span>
        <span>{lastCol === "streak" ? "Streak / note" : "Weakest point"}</span>
      </div>
      {session.rows.map((r) => (
        <div key={r.symbol} className="grid items-center font-mono" style={{ gridTemplateColumns: GRID, gap: 10, padding: "8px 4px", borderBottom: "1px solid #f6f8fa", fontSize: 12.5 }}>
          <span style={{ fontWeight: 500, color: "#141b28" }}>{r.symbol}</span>
          <span style={{ fontSize: 11, color: r.dir === "PUT" ? signal.bad.text : r.dir === "CALL" ? signal.ok.text : "#6a7280" }}>{r.dir}</span>
          <span style={{ color: "#414956" }}>{r.adversary}</span>
          <span style={{ fontWeight: 500, color: r.conviction === "NEUTRAL" ? "#6a7280" : "#141b28" }}>{r.conviction}</span>
          <span>{r.via === "—" ? <span style={{ color: "#8b919b" }}>—</span> : <Chip level={viaLevel(r.via)}>{r.via}</Chip>}</span>
          <span
            title={lastCol === "weakest" ? r.weakest : undefined}
            style={{ fontFamily: "Roboto, system-ui, sans-serif", fontSize: 12, color: "#414956", lineHeight: 1.35, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}
          >
            {lastCol === "streak" ? r.streak : r.weakest || r.streak}
          </span>
        </div>
      ))}
    </div>
  );
}

/** The LOW-count history over the trailing sessions: how much of the slate was grounded-but-not-inflecting. */
export function LowHistory({ session }: { session: SessionVM }) {
  const hist = session.lowHistory;
  if (!hist.length) return null;
  const max = Math.max(1, ...hist.map((h) => h.low));
  return (
    <div>
      <div style={{ fontSize: 12, color: "#414956", fontWeight: 500 }}>LOW count, last {hist.length} sessions</div>
      <div style={{ fontSize: 11, color: "#6a7280", marginTop: 2, lineHeight: 1.5 }}>how much of the slate the strategist found grounded but not yet inflecting</div>
      <div className="flex items-end" style={{ gap: 10, height: 96, marginTop: 14, borderBottom: "1px solid #edf0f4" }}>
        {hist.map((h, i) => {
          const last = i === hist.length - 1;
          return (
            <div key={h.runId} className="flex-1 flex flex-col items-center" style={{ gap: 4 }}>
              <span className="font-mono" style={{ fontSize: 11, color: last ? "#141b28" : "#414956", fontWeight: last ? 500 : 400 }}>{h.low}</span>
              <div style={{ width: 24, height: Math.max(3, (h.low / max) * 72), background: last ? "#1558d6" : "#a7c4fb", borderRadius: "4px 4px 0 0" }} />
            </div>
          );
        })}
      </div>
      <div className="flex justify-between font-mono" style={{ fontSize: 10.5, color: "#6a7280", marginTop: 5 }}>
        {hist.map((h) => <span key={h.runId}>{h.day || `#${h.runId}`}</span>)}
      </div>
    </div>
  );
}

/** The three §10.7 criteria the strategist must all confirm — the "why nothing passes" read. */
export function CriteriaLegs({ legs, compact = false }: { legs: { n: number; structural: number; underNarrated: number; atInflection: number } | null; compact?: boolean }) {
  if (!legs || !legs.n) return <div style={{ fontSize: 12, color: "#6a7280" }}>no deliberations yet</div>;
  const rows = [
    { label: "structural", v: legs.structural, warn: false },
    { label: "under-narrated", v: legs.underNarrated, warn: false },
    { label: "at inflection", v: legs.atInflection, warn: legs.atInflection <= Math.min(legs.structural, legs.underNarrated) / 2 },
  ];
  return (
    <div>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center" style={{ gap: 10, padding: compact ? "7px 0" : "8px 0", borderTop: "1px solid #edf0f4" }}>
          <span style={{ flex: 1, fontSize: 12.5, color: "#2c3645" }}>
            {r.label}{r.warn && <span style={{ color: "#6a7280", fontSize: 11 }}> · the binding leg</span>}
          </span>
          <div style={{ width: 90, height: 6, background: "#edf0f4", borderRadius: 3, overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${Math.max(2, (r.v / legs.n) * 100)}%`, background: r.warn ? signal.warn.text : "#1558d6", borderRadius: 3 }} />
          </div>
          <span className="font-mono" style={{ width: 38, textAlign: "right", fontSize: 12.5, fontWeight: 500, color: r.warn ? signal.warn.text : "#2c3645" }}>{r.v}/{legs.n}</span>
        </div>
      ))}
    </div>
  );
}
