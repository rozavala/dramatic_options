import type { RegimeVM, TelemetryVM } from "../data/types";
import { Card, Chip } from "./primitives";

// 2026-11-03 profit-program telemetry (records/2026-11-03_profit_program_DRAFTS.md): D0 execution ledger,
// D4 IV history, D3b falsifier ledger, D5 capex cycle, D6 coverage trend. Display only — nothing here gates an entry or reaches a council prompt.

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

// #467 step 3: every paper result's "net of slippage" twin. An estimate; display only, nothing is re-booked.
export function SlippageCard({ t }: { t: TelemetryVM }) {
  const s = t.slip;
  return (
    <Card style={{ padding: "18px 20px" }}>
      <div data-testid="tel-slip">
        <Head title="Net of slippage (estimate, #467)" sub={s ? s.note : "panel unavailable"}
          chip={<Chip level="mute">estimate</Chip>} />
        {s && s.entries > 0 && (
          <div style={{ fontSize: 12, color: "#2c3645", marginBottom: 8 }}>
            {s.known} of {s.entries} entries priced ({s.unknown} unknown) · haircut {s.haircut} ({s.haircutPct} of premium) ·
            P&L over {s.pnlN} priced and marked or closed: as filled {s.pnlFilled}, net of slippage {s.pnlCons}
          </div>
        )}
        {s && s.rows.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th style={th}>#</th><th style={th}>Name</th><th style={th}>Contract</th><th style={th}>Status</th>
                <th style={{ ...th, textAlign: "right" }}>Fill</th><th style={{ ...th, textAlign: "right" }}>Conservative</th>
                <th style={th}>Basis</th><th style={{ ...th, textAlign: "right" }}>Premium filled</th>
                <th style={{ ...th, textAlign: "right" }}>Premium conservative</th><th style={th}>P&L</th>
                <th style={{ ...th, textAlign: "right" }}>As filled</th><th style={{ ...th, textAlign: "right" }}>Net of slippage</th></tr></thead>
              <tbody>
                {s.rows.map((r) => (
                  <tr key={r.key} data-testid={`slip-row-${r.key}`}><td style={num}>{r.key}</td><td style={td}>{r.symbol}</td>
                    <td style={td}>{r.contract}</td><td style={td}>{r.status}{r.partial && <> · {r.partial}</>}</td><td style={num}>{r.fill}</td>
                    <td style={num}>{r.cons}</td><td style={td}>{r.basis}</td><td style={num}>{r.premium}</td>
                    <td style={num}>{r.premiumCons}</td><td style={td}>{r.pnlKind}</td><td style={num}>{r.pnl}</td>
                    <td style={num}>{r.pnlCons}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : s && <Empty>No real-book entry has filled yet.</Empty>}
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

// #462 §8: one card, measurement only. Neutral greys only (no colour scale, no level keyed to any action); S5 and the
// live companion are greyed and labelled display-only. The server's own status text is never shown as a verdict.
const GREY = "#8a93a1";

function Spark({ pts }: { pts: RegimeVM["spark"] }) {
  const W = 240, H = 36, pad = 3;
  if (pts.length === 0) return null;
  const vs = pts.map((p) => p.v);
  const lo = Math.min(...vs), hi = Math.max(...vs), span = hi - lo || 1;
  const x = (i: number) => (pts.length === 1 ? W / 2 : pad + (i * (W - 2 * pad)) / (pts.length - 1));
  const y = (v: number) => H - pad - ((v - lo) * (H - 2 * pad)) / span;
  const kept = pts.map((p, i) => ({ ...p, i })).filter((p) => !p.low);
  return (
    <svg width={W} height={H} role="img" aria-label="S1 median by night" data-testid="regime-spark" style={{ display: "block" }}>
      {kept.length > 1 && <polyline fill="none" stroke="#2c3645" strokeWidth={1.25} points={kept.map((p) => `${x(p.i)},${y(p.v)}`).join(" ")} />}
      {kept.length === 1 && <circle cx={x(kept[0].i)} cy={y(kept[0].v)} r={2} fill="#2c3645" />}
      {pts.filter((p) => p.low).map((p) => <circle key={p.d} data-testid="regime-spark-low" cx={x(pts.indexOf(p))} cy={y(p.v)} r={2.5} fill="none" stroke={GREY} />)}
    </svg>
  );
}

export function RegimeSeriesCard({ t }: { t: TelemetryVM }) {
  const g = t.regime;
  const body: React.CSSProperties = { fontSize: 12, color: g?.coverageLow ? GREY : "#2c3645", marginBottom: 6 };
  return (
    <Card style={{ padding: "18px 20px" }}>
      <div data-testid="tel-regime">
        <Head title="Convexity regime series (#462)"
          sub={g ? "A 270-day read of option implied vol against realized vol across the frozen universe, kept nightly. Measurement only: it changes no entry, size, exit or quota."
            : "panel unavailable"}
          chip={<Chip level="mute">telemetry</Chip>} />
        {g && !g.ok && <Empty>No term record yet ({g.status}).</Empty>}
        {g && g.ok && (
          <>
            {g.coverageLow && <div style={{ fontSize: 12, color: "#2c3645", marginBottom: 6 }} data-testid="regime-low">{g.coverageNote}</div>}
            <div style={body}>
              Night of {g.date}: implied ÷ realized vol (S1), p25 / p50 / p75 {g.s1.p25} / {g.s1.p50} / {g.s1.p75} over {g.s1.n} names · coverage {g.coverage}
            </div>
            <div style={body} data-testid="regime-pctile">Percentile in its own history: {g.percentile}</div>
            <div style={{ margin: "4px 0 8px" }}><Spark pts={g.spark} /></div>
            <div style={body}>
              S2 term slope median {g.s2} vp · S3 25%-OTM skew median, calls {g.s3.calls} / puts {g.s3.puts} vp (put side {g.s3.putShare}) ·
              S4 270-day IV median {g.s4.iv}, ÷ RV63 {g.s4.ivRv63}
            </div>
            <div style={{ fontSize: 11.5, color: GREY, marginTop: 8 }} data-testid="regime-display-only">
              <div>Display only. S5, the gate&apos;s own cheapness test (IV/RV and wing skew) over the same names: pass share {g.s5.passShare}, median IV/RV {g.s5.medianIvRv}, n {g.s5.n}, frame {g.s5.frame}.</div>
              {g.live && (
                <div>Display only. Live companion, the same S1 over today&apos;s {g.live.names} universe names: p25 / p50 / p75 {g.live.s1.p25} / {g.live.s1.p50} / {g.live.s1.p75}, n {g.live.s1.n}, coverage {g.live.coverage}.</div>
              )}
            </div>
          </>
        )}
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

export function CapexCycleCard({ t }: { t: TelemetryVM }) {
  const x = t.capex;
  return (
    <Card style={{ padding: "18px 20px" }}>
      <div data-testid="tel-capex">
        <Head title="Capex cycle by cluster" sub={x ? `${x.note} Latest record ${x.asOf}.` : "panel unavailable"}
          chip={<Chip level="mute">telemetry</Chip>} />
        {x && x.rows.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th style={th}>Cluster</th><th style={{ ...th, textAlign: "right" }}>names</th>
                <th style={{ ...th, textAlign: "right" }}>TTM capex</th><th style={{ ...th, textAlign: "right" }}>YoY</th>
                <th style={{ ...th, textAlign: "right" }}>accel</th><th style={th}>Phase</th></tr></thead>
              <tbody>
                {x.rows.map((r) => (
                  <tr key={r.cluster}><td style={td}>{r.cluster}</td><td style={num}>{r.n}</td><td style={num}>{r.ttm}</td>
                    <td style={num}>{r.yoy}</td><td style={num}>{r.accel}</td><td style={td}>{r.phase}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : x && <Empty>No capex-cycle record yet (written at the next L1).</Empty>}
      </div>
    </Card>
  );
}

export function AttentionCard({ t }: { t: TelemetryVM }) {
  const x = t.attention;
  return (
    <Card style={{ padding: "18px 20px" }}>
      <div data-testid="tel-attention">
        <Head title="Analyst coverage trend" sub={x ? `${x.status}. ${x.note}` : "panel unavailable"}
          chip={<Chip level="mute">telemetry</Chip>} />
        {x && x.rows.length > 0 ? (
          <div style={{ overflowX: "auto", maxHeight: 360 }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th style={th}>Name</th><th style={{ ...th, textAlign: "right" }}>analysts</th>
                <th style={th}>~90-day change</th><th style={th}>Label</th><th style={th}>As of</th></tr></thead>
              <tbody>
                {x.rows.map((r) => (
                  <tr key={r.symbol}><td style={td}>{r.symbol}</td><td style={num}>{r.count}</td><td style={td}>{r.change}</td>
                    <td style={td}>{r.label}</td><td style={td}>{r.asOf}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : x && <Empty>No coverage history yet (recorded at each L1 for the names the council judges).</Empty>}
      </div>
    </Card>
  );
}

export function Telemetry({ t }: { t: TelemetryVM }) {
  return (
    <div className="flex flex-col" style={{ gap: 16 }}>
      <ExecutionCard t={t} />
      <SlippageCard t={t} />
      <IvHistoryCard t={t} />
      <RegimeSeriesCard t={t} />
      <FalsifierCard t={t} />
      <CapexCycleCard t={t} />
      <AttentionCard t={t} />
    </div>
  );
}
