import { directionLabel, markLevel } from "../data/status";
import type { ViewModel } from "../data/types";
import { signal } from "../theme/tokens";
import { Card, Chip } from "./primitives";

const GRID = ".9fr 1.4fr .8fr .7fr .8fr .9fr 1fr";
const Muted = ({ children }: { children: React.ReactNode }) => <span style={{ color: "#6a7280", fontWeight: 400 }}>{children}</span>;
const Row = ({ label, value }: { label: React.ReactNode; value: React.ReactNode }) => (
  <div className="flex justify-between items-center" style={{ gap: 14, padding: "8px 0", borderTop: "1px solid #edf0f4" }}>
    <span style={{ fontSize: 12.5, color: "#2c3645" }}>{label}</span>
    <span className="font-mono text-right" style={{ fontSize: 12.5, fontWeight: 500, color: "#2c3645" }}>{value}</span>
  </div>
);
const money = (v: number) => `${v < 0 ? "−" : "+"}$${Math.abs(Math.round(v)).toLocaleString("en-US")}`;

/** Book & Watchlist: the real book with running P&L · sentinels grouped by basket · the five books' open
 *  counts · the data-accrual card with its honesty flag. */
export function Book({ vm }: { vm: ViewModel }) {
  const has = vm.positions.length > 0;
  const byBasket = new Map<string, { symbol: string; dir: string }[]>();
  for (const s of vm.sentinels) {
    const k = s.basket ?? "—";
    if (!byBasket.has(k)) byBasket.set(k, []);
    byBasket.get(k)!.push({ symbol: s.symbol, dir: s.dir ?? "" });
  }
  const baskets = [...byBasket.entries()].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]));
  const da = vm.dataAccrual;
  const bo = vm.booksOpen;
  return (
    <div className="flex flex-col" style={{ gap: 16 }}>
      <Card style={{ padding: "20px 22px" }}>
        <div className="flex items-baseline justify-between" style={{ gap: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Open positions <Muted>· the real (paper) book — the only one sent to the broker</Muted></div>
          <span className="font-mono" style={{ fontSize: 12, color: "#414956" }}>{vm.openCount} open · {vm.openPrem2} at risk</span>
        </div>
        {has ? (
          <>
            <div className="grid" style={{ gridTemplateColumns: GRID, gap: 10, padding: "14px 4px 9px", borderBottom: "1px solid #cbd0da", fontSize: 10.5, color: "#6a7280", textTransform: "uppercase", letterSpacing: ".6px", fontWeight: 500 }}>
              <span>Ticker</span><span>Theme</span><span>Conviction at entry</span><span>Days left</span><span>Premium</span><span>Mark ÷ entry</span><span>Running</span>
            </div>
            {vm.positions.map((p, i) => {
              const lv = p.mark != null ? signal[markLevel(p.mark)] : signal.mute;
              const running = p.mark != null ? p.premiumUsd * (p.mark - 1) : null;
              const bled = p.mark != null && p.mark < 1 ? Math.round((1 - p.mark) * 100) : null;
              return (
                <div key={i} className="grid items-center font-mono" style={{ gridTemplateColumns: GRID, gap: 10, padding: "11px 4px", borderBottom: "1px solid #f6f8fa", fontSize: 12.5 }}>
                  <span style={{ fontWeight: 500, color: "#141b28" }}>{p.symbol} <span style={{ fontSize: 10, fontFamily: "Roboto", color: p.dir === "bearish" ? signal.bad.text : signal.ok.text }}>{directionLabel(p.dir)}</span></span>
                  <span style={{ fontFamily: "Roboto", fontSize: 12, color: "#414956" }}>{p.theme ?? "—"}</span>
                  <span style={{ color: "#2c3645" }}>{p.conviction ?? "—"}</span>
                  <span style={{ color: "#414956" }}>{p.dte != null ? `${p.dte}d` : "—"}</span>
                  <span style={{ color: "#2c3645" }}>{p.premium}</span>
                  <span className="flex items-center" style={{ gap: 8 }}>
                    <span style={{ fontWeight: 500, color: p.mark != null && p.mark < 1 ? signal.warn.text : lv.text }}>{p.mark != null ? `${p.mark.toFixed(2)}×` : "—"}</span>
                    <span style={{ flex: 1, height: 5, background: "#edf0f4", borderRadius: 3, overflow: "hidden", maxWidth: 80 }}>
                      <span style={{ display: "block", height: "100%", width: `${p.mark != null ? Math.min(100, (p.mark / Math.max(1.2, p.mark)) * 100) : 0}%`, background: p.mark != null && p.mark < 1 ? signal.warn.text : lv.text }} />
                    </span>
                  </span>
                  <span style={{ color: running != null && running < 0 ? signal.warn.text : signal.ok.text }}>
                    {running == null ? "—" : money(running)}{bled != null && <span style={{ color: "#6a7280" }}> · {bled}% bled</span>}
                  </span>
                </div>
              );
            })}
            <div style={{ fontSize: 11, color: "#6a7280", marginTop: 10, lineHeight: 1.5 }}>Running is mark-to-market, unrealized. A far-OTM option sitting near zero mid-life is the design, not a fault — the read is the tail at expiry.</div>
          </>
        ) : (
          <div className="flex items-center" style={{ gap: 14, padding: 22, marginTop: 12, border: "1px dashed #b3bfd4", borderRadius: 10, background: "#f6f8fa" }}>
            <span style={{ fontSize: 22, animation: "accruePulse 2.4s ease-in-out infinite" }}>◷</span>
            <div>
              <div style={{ fontSize: 13.5, fontWeight: 500, color: "#2c3645" }}>No open positions — by design</div>
              <div style={{ fontSize: 12, color: "#414956", marginTop: 2 }}>The book stays empty until a genuinely cheap, grounded idea clears the gate. A clean state, not a problem.</div>
            </div>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] items-start" style={{ gap: 16 }}>
        <Card style={{ padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Sentinel watchlist <Muted>· {vm.sentinels.length} active lineages, grouped by basket</Muted></div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 12 }}>
            The names the weekly scan is carrying for an inflection. Arrow = the direction the funnel framed; the council judges ~12 of these each session. {vm.sentinelSub}
          </div>
          {baskets.length === 0 && <div style={{ fontSize: 12.5, color: "#5f6675" }}>None active.</div>}
          {baskets.map(([name, syms]) => (
            <div key={name} className="flex items-center" style={{ gap: 12, padding: "7px 0", borderTop: "1px solid #edf0f4" }}>
              <span className="font-mono" style={{ width: 150, flex: "none", fontSize: 12, color: "#414956" }}>{name}</span>
              <div className="flex flex-wrap" style={{ gap: 6 }}>
                {syms.map((s) => (
                  <span key={s.symbol} className="font-mono" style={{ fontSize: 11.5, padding: "3px 8px", borderRadius: 7, background: "#f6f8fa", border: "1px solid #edf0f4", color: s.dir === "bearish" ? signal.bad.text : s.dir === "bullish" ? signal.ok.text : "#6a7280" }}>
                    <b style={{ color: "#141b28", fontWeight: 500 }}>{s.symbol}</b> {s.dir === "bearish" ? "↓" : s.dir === "bullish" ? "↑" : ""}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </Card>

        <div className="flex flex-col" style={{ gap: 16 }}>
          <Card style={{ padding: "18px 20px" }}>
            <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>The five books <Muted>· open counts</Muted></div>
            <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 8 }}>Real trades the paper broker; the other four are simulated controls with one piece switched off each.</div>
            <Row label={<>Real <Muted>gate + council</Muted></>} value={bo.real} />
            <Row label={<>Shadow <Muted>gate on, council off</Muted></>} value={bo.shadow} />
            <Row label={<>3A <Muted>gate off, same names</Muted></>} value={bo.a3} />
            <Row label={<>3B <Muted>gate off, whole basket</Muted></>} value={bo.basket} />
            <Row label={<>Shares <Muted>linear, descriptive</Muted></>} value={bo.shares} />
          </Card>

          <Card style={{ padding: "18px 20px", borderColor: da.accruing ? "#cbd0da" : signal.warn.border }}>
            <div className="flex justify-between items-center">
              <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Data accrual <Muted>· chain-snapshot store</Muted></div>
              <Chip level={da.accruing ? "ok" : da.symbols ? "warn" : "mute"}>{da.accruing ? "accruing" : da.symbols ? "not accruing" : "empty"}</Chip>
            </div>
            <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 8 }}>
              {da.accruing ? "The forward IV baseline the gate will read against." : "The snapshot store has not written in over a week — it is not building an IV baseline."}
            </div>
            <Row label="Chain snapshots" value={<>{da.symbols} name{da.symbols === 1 ? "" : "s"}{da.names.length ? <Muted> · {da.names.slice(0, 4).join(", ")}</Muted> : null}</>} />
            <Row label="Latest snapshot" value={<span style={{ color: da.accruing || da.ageDays == null ? "#2c3645" : signal.warn.text }}>{da.latest}{da.ageDays != null ? ` · ${Math.round(da.ageDays)}d ago` : ""}</span>} />
            <Row label="Bar coverage" value={`${da.barSymbols} symbols`} />
            <Row label={<>Dual-read sessions <Muted>the live IV record</Muted></>} value={<span style={{ color: signal.ok.text }}>{vm.dualread.sessions}</span>} />
          </Card>
        </div>
      </div>
    </div>
  );
}
