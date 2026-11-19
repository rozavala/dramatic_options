import type { HeldReadsVM, ViewModel } from "../data/types";
import { runLabel } from "../data/runLabel";
import { Card } from "./primitives";

// §10.13 §3 (#508): the per-position held-read timeline. MEASUREMENT ONLY — never acted on (§5).
// Pinned by the prereg: no trend line, no "thesis broken" badge, no colour keyed to exit. Every cell is the same
// neutral ink; the only distinction is the line's kind, written as text.

const INK = "#2c3645";
const MUTED = "#6a7280";

export function HeldReadsTimeline({ h, runDates, compact }: { h: HeldReadsVM; runDates: ViewModel["runDates"]; compact?: boolean }) {
  if (h.unavailable) return <div data-testid="held-unavailable" style={{ fontSize: 12, color: MUTED }}>unavailable — the held-reads panel did not load</div>;
  if (h.positions.length === 0) return <div data-testid="held-empty" style={{ fontSize: 12, color: MUTED }}>no open or closing real position</div>;
  const th: React.CSSProperties = { textAlign: "left", fontSize: 10.5, color: MUTED, fontWeight: 500, padding: "5px 6px", borderBottom: "1px solid #edf0f4", whiteSpace: "nowrap" };
  const td: React.CSSProperties = { padding: "6px 6px", borderBottom: "1px solid #f3f5f8", verticalAlign: "top", fontSize: 11.5, color: INK };
  return (
    <div data-testid="held-timeline" className="flex flex-col" style={{ gap: 14 }}>
      {h.noTable && <div style={{ fontSize: 11.5, color: MUTED }}>no held_reads table on this database yet — entry verdicts and seatings only</div>}
      {h.positions.map((p) => (
        <div key={p.id} data-testid={`held-pos-${p.symbol}`}>
          <div className="font-mono" style={{ fontSize: 12.5, color: INK }}>
            <b style={{ fontWeight: 600 }}>{p.symbol}</b> <span style={{ color: MUTED }}>{p.dir} · #{p.id} · {p.status} · opened {p.opened}{p.origin ? ` · origin ${p.origin}` : ""} · mark ÷ entry now {p.mark}</span>
          </div>
          {p.earlier.map((e) => <div key={e} data-testid="held-earlier" style={{ fontSize: 11, color: MUTED, marginTop: 3 }}>{e}</div>)}
          {compact ? (
            <div style={{ marginTop: 4 }}>
              {p.lines.map((l, i) => (
                <div key={i} data-testid="held-line" style={{ padding: "5px 0", borderBottom: "1px solid #f3f5f8", fontSize: 11, color: INK }}>
                  <span style={{ color: MUTED }}>{l.kind} · {l.day}{l.runId != null ? ` · ${runLabel(runDates, l.runId)}` : ""} · {l.label}</span>
                  <div className="font-mono">{l.conviction} · include {l.include} · {l.criteria}</div>
                  {l.note && <div className="font-mono" style={{ color: MUTED }}>{l.note}</div>}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ overflowX: "auto", marginTop: 4 }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead><tr>
                  <th style={th}>Line</th><th style={th}>Day</th><th style={th}>Run</th><th style={th}>Source / lineage</th>
                  <th style={th}>Conviction</th><th style={th}>Include</th><th style={th}>Criteria</th><th style={th}>Note</th>
                </tr></thead>
                <tbody>
                  {p.lines.map((l, i) => (
                    <tr key={i} data-testid="held-line">
                      <td style={td}>{l.kind}</td>
                      <td className="font-mono" style={td}>{l.day}</td>
                      <td className="font-mono" style={td}>{l.runId != null ? `#${l.runId}` : "—"}</td>
                      <td style={td}>{l.label}</td>
                      <td className="font-mono" style={td}>{l.conviction}</td>
                      <td className="font-mono" style={td}>{l.include}</td>
                      <td className="font-mono" style={td}>{l.criteria}</td>
                      <td className="font-mono" style={{ ...td, color: MUTED }}>{l.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
      {h.markFixNote && <div style={{ fontSize: 10.5, color: MUTED }}>{h.markFixNote}. Falsifier ledger: {h.falsifierStatus}.</div>}
    </div>
  );
}

/** Book section card. */
export function HeldReadsCard({ vm, compact }: { vm: ViewModel; compact?: boolean }) {
  const h = vm.heldReads;
  return (
    <Card style={{ padding: compact ? "14px 14px" : "20px 22px" }}>
      <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Held reads <span style={{ color: MUTED, fontWeight: 400 }}>· per position, {h.note}</span></div>
      <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 10 }}>
        The entry verdict, each nightly held read, later of-record seatings of the same name and direction, and the
        falsifier-ledger reads. A record to look at, not a signal: no read here changes an exit, an add or a size.
      </div>
      <HeldReadsTimeline h={h} runDates={vm.runDates} compact={compact} />
    </Card>
  );
}
