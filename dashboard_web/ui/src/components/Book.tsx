import { directionLabel, markLevel } from "../data/status";
import type { ViewModel } from "../data/types";
import { signal } from "../theme/tokens";

const INTRO =
  "The real book is the only one sent to the (paper) broker. Four shadow books run alongside it in simulation only. " +
  "Below: what's open, what the scanner is watching, and the data accruing.";

const GRID = "0.8fr 0.9fr 0.7fr 0.7fr 0.9fr 1fr";
const dirLabel = directionLabel; // A6 — single source in status.ts

export function Book({ vm }: { vm: ViewModel }) {
  const has = vm.positions.length > 0;
  const posMaxMark = Math.max(1.2, ...vm.positions.map((p) => p.mark ?? 0));

  return (
    <>
      <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px", marginBottom: 16 }}>
        <div style={{ fontSize: 13, color: "#2c3645", lineHeight: 1.6 }}>{INTRO}</div>
      </div>

      {/* open positions */}
      <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "20px 22px", marginBottom: 16 }}>
        <div className="flex items-baseline justify-between" style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Open positions <span style={{ color: "#6a7280", fontWeight: 400 }}>· the real (live paper) book</span></div>
          <span className="font-mono" style={{ fontSize: 12, color: "#414956" }}>{vm.openCount} open · {vm.openPrem2} at risk</span>
        </div>
        {has ? (
          <>
            <div className="grid" style={{ gridTemplateColumns: GRID, gap: 10, padding: "0 4px 9px", borderBottom: "1px solid #cbd0da", fontSize: 10.5, color: "#6a7280", textTransform: "uppercase", letterSpacing: ".6px", fontWeight: 500 }}>
              <span>Ticker</span><span>Theme</span><span>Conviction</span><span>Days left</span><span>Premium</span><span>Mark ÷ entry</span>
            </div>
            {vm.positions.map((p, i) => {
              const lv = p.mark != null ? signal[markLevel(p.mark)] : signal.mute;
              return (
                <div key={i} className="grid items-center font-mono" style={{ gridTemplateColumns: GRID, gap: 10, padding: "11px 4px", borderBottom: "1px solid #f6f8fa", fontSize: 12.5 }}>
                  <span style={{ fontWeight: 500, color: "#141b28" }}>{p.symbol} <span style={{ fontSize: 10, fontFamily: "Roboto", color: p.dir === "bearish" ? signal.bad.text : signal.ok.text }}>{dirLabel(p.dir)}</span></span>
                  <span style={{ fontFamily: "Roboto", fontSize: 12, color: "#414956" }}>{p.theme ?? "—"}</span>
                  <span style={{ color: "#2c3645" }}>{p.conviction ?? "—"}</span>
                  <span style={{ color: "#414956" }}>{p.dte != null ? `${p.dte}d` : "—"}</span>
                  <span style={{ color: "#2c3645" }}>{p.premium}</span>
                  <span className="flex items-center" style={{ gap: 8 }}>
                    <span style={{ fontWeight: 500, color: lv.text }}>{p.mark != null ? `${p.mark.toFixed(1)}×` : "—"}</span>
                    <span style={{ flex: 1, height: 5, background: "#edf0f4", borderRadius: 3, overflow: "hidden", maxWidth: 80 }}>
                      <span style={{ display: "block", height: "100%", width: `${p.mark != null ? Math.min(100, (p.mark / posMaxMark) * 100) : 0}%`, background: lv.text }} />
                    </span>
                  </span>
                </div>
              );
            })}
          </>
        ) : (
          <div className="flex items-center" style={{ gap: 14, padding: 22, border: "1px dashed #b3bfd4", borderRadius: 10, background: "#f6f8fa" }}>
            <span style={{ fontSize: 22, animation: "accruePulse 2.4s ease-in-out infinite" }}>◷</span>
            <div>
              <div style={{ fontSize: 13.5, fontWeight: 500, color: "#2c3645" }}>No open positions yet — by design</div>
              <div style={{ fontSize: 12, color: "#414956", marginTop: 2 }}>The book stays empty until a genuinely cheap idea clears the gate. Nothing has, which is a clean state, not a problem.</div>
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* sentinels */}
        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4, color: "#141b28" }}>Active sentinels</div>
          <div style={{ fontSize: 12, color: "#414956", lineHeight: 1.5, marginBottom: 14 }}>Names the weekly scanner is watching for an inflection. {vm.sentinelSub}</div>
          {vm.sentinels.length === 0 && <div style={{ fontSize: 12, color: "#5f6675" }}>None active.</div>}
          {vm.sentinels.map((s, i) => (
            <div key={i} className="flex justify-between items-center" style={{ padding: "8px 0", borderTop: "1px solid #edf0f4" }}>
              <span className="font-mono" style={{ fontSize: 12.5, fontWeight: 500, color: "#2c3645" }}>
                {s.symbol} <span style={{ color: "#6a7280", fontSize: 11 }}>{s.basket ?? ""}</span>
              </span>
              <span style={{ fontSize: 11.5, color: "#414956" }}>{s.note}</span>
            </div>
          ))}
        </div>
        {/* data accruing */}
        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4, color: "#141b28" }}>Data accruing</div>
          <div style={{ fontSize: 12, color: "#414956", lineHeight: 1.5, marginBottom: 14 }}>The forward IV baseline the gate will read against, building up over time.</div>
          {vm.data.map((d) => (
            <div key={d.label} className="flex justify-between items-center" style={{ padding: "10px 0", borderTop: "1px solid #edf0f4" }}>
              <span style={{ fontSize: 12.5, color: "#2c3645" }}>{d.label}</span>
              <span className="font-mono" style={{ fontSize: 15, fontWeight: 500, color: "#141b28" }}>{d.value}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
