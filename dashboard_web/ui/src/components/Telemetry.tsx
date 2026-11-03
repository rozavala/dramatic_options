import type { TelemetryVM } from "../data/types";
import { Card, Chip } from "./primitives";

// 2026-11-03 profit-program telemetry (records/2026-11-03_profit_program_DRAFTS.md): D0 execution ledger,
// D4 IV history, D3b falsifier ledger. Display only — nothing here gates an entry or reaches a council prompt.

const th: React.CSSProperties = { textAlign: "left", fontSize: 11, color: "#6a7280", fontWeight: 500, padding: "5px 8px", borderBottom: "1px solid #edf0f4", whiteSpace: "nowrap" };
const td: React.CSSProperties = { padding: "6px 8px", borderBottom: "1px solid #f3f5f8", fontSize: 12, color: "#141b28", whiteSpace: "nowrap" };
const num: React.CSSProperties = { ...td, textAlign: "right", fontFamily: "'Roboto Mono', ui-monospace, monospace" };

function Head({ title, sub, chip }: { title: string; sub: string; chip?: React.ReactNode }) {
  return (
    <div className="flex justify-between items-start" style={{ gap: 10, marginBottom: 10 }}>
      <div>
        <div style={{ fontSize: 14.5, fontWeight: 500, color: "#141b28" }}>{title}</div>
        <div style={{ fontSize: 12, color: "#6a7280", marginTop: 3, lineHeight: 1.45 }}>{sub}</div>
      </div>
      {chip}
    </div>
  );
}

const Empty = ({ children }: { children: React.ReactNode }) => (
  <div style={{ fontSize: 12, color: "#6a7280", padding: "6px 0" }}>{children}</div>
);

export function ExecutionCard({ t }: { t: TelemetryVM }) {
  const e = t.exec;
  return (
    <Card style={{ padding: "18px 20px" }}>
      <div data-testid="tel-exec">
        <Head title="Execution ledger" sub={e ? e.read : "panel unavailable"}
          chip={e && <Chip level={e.decided ? "acc" : "mute"}>fill rate {e.fillRate}</Chip>} />
        {e && (
          <div style={{ fontSize: 12, color: "#2c3645", marginBottom: 8 }}>
            {e.approvals} approvals · {e.reached} reached an order · {e.filled} of {e.decided} decided filled · under carry-over {e.carryFilled} of {e.carryDecided}
          </div>
        )}
        {e && e.rows.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th style={th}>Date</th><th style={th}>Name</th><th style={th}>Outcome</th>
                <th style={{ ...th, textAlign: "right" }}>Limit</th><th style={{ ...th, textAlign: "right" }}>Ask</th>
                <th style={{ ...th, textAlign: "right" }}>Fill</th><th style={{ ...th, textAlign: "right" }}>Carry steps</th></tr></thead>
              <tbody>
                {e.rows.map((r) => (
                  <tr key={r.key}><td style={td}>{r.date}</td><td style={td}>{r.symbol}</td><td style={td}>{r.outcome}</td>
                    <td style={num}>{r.limit}</td><td style={num}>{r.ask}</td><td style={num}>{r.fill}</td><td style={num}>{r.attempts}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : e && <Empty>No approval has reached the broker yet.</Empty>}
      </div>
    </Card>
  );
}

export function IvHistoryCard({ t }: { t: TelemetryVM }) {
  const v = t.iv;
  return (
    <Card style={{ padding: "18px 20px" }}>
      <div data-testid="tel-iv">
        <Head title="IV history (own-name)" sub={v ? `${v.status} · term records: ${v.termSessions} session(s)` : "panel unavailable"}
          chip={<Chip level="mute">telemetry</Chip>} />
        {v && v.rows.length > 0 ? (
          <div style={{ overflowX: "auto", maxHeight: 360 }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th style={th}>Name</th><th style={{ ...th, textAlign: "right" }}>n</th>
                <th style={{ ...th, textAlign: "right" }}>IV/RV</th><th style={{ ...th, textAlign: "right" }}>pctile</th>
                <th style={{ ...th, textAlign: "right" }}>skew vp</th><th style={{ ...th, textAlign: "right" }}>term slope</th>
                <th style={{ ...th, textAlign: "right" }}>ΔIV call</th><th style={{ ...th, textAlign: "right" }}>ΔIV put</th></tr></thead>
              <tbody>
                {v.rows.map((r) => (
                  <tr key={r.symbol}><td style={td}>{r.symbol}</td><td style={num}>{r.n}</td><td style={num}>{r.ivrv}</td>
                    <td style={num}>{r.ivrvPct}</td><td style={num}>{r.skew}</td><td style={num}>{r.slope}</td>
                    <td style={num}>{r.dIvC}</td><td style={num}>{r.dIvP}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : v && <Empty>No sweep reads yet.</Empty>}
      </div>
    </Card>
  );
}

export function FalsifierCard({ t }: { t: TelemetryVM }) {
  const f = t.fals;
  return (
    <Card style={{ padding: "18px 20px" }}>
      <div data-testid="tel-fals">
        <Head title="Falsifier ledger" sub={f ? f.note : "panel unavailable"}
          chip={f && <Chip level={f.fired ? "warn" : "mute"}>{f.fired} of {f.reads} fired</Chip>} />
        {f && f.rows.map((r) => (
          <div key={r.key} className="flex justify-between" style={{ fontSize: 12, padding: "5px 0", borderTop: "1px solid #f3f5f8" }}>
            <span>{r.readAt} · {r.symbol}</span>
            <span className="font-mono">{r.value} vs {r.threshold} {r.fired ? <Chip level="warn">fired</Chip> : <Chip level="ok">held</Chip>}</span>
          </div>
        ))}
        {f && f.waiting.length > 0 && (
          <div style={{ fontSize: 11.5, color: "#6a7280", marginTop: 8 }}>
            Waiting for the quarter: {f.waiting.map((w) => `${w.symbol} (< ${w.threshold}, filed after ${w.after})`).join(" · ")}
          </div>
        )}
      </div>
    </Card>
  );
}

export function Telemetry({ t }: { t: TelemetryVM }) {
  return (
    <div className="flex flex-col" style={{ gap: 16 }}>
      <ExecutionCard t={t} />
      <IvHistoryCard t={t} />
      <FalsifierCard t={t} />
    </div>
  );
}
