import type { ViewModel } from "../data/types";
import { color, signal, type Level } from "../theme/tokens";
import { CheapnessWatch } from "./CheapnessWatch";

const INTRO =
  "Ideas pass through the AI debate first, then a deterministic cheapness gate, then the risk caps. The council can " +
  "only propose — it can never overrule a veto. This is “the hard seam.”";

export function Pipeline({ vm }: { vm: ViewModel }) {
  const f = vm.funnel;
  const fmax = Math.max(f.proposed, f.evaluated, f.opened, 1);
  // F3: proposed→evaluated→opened is a FLOW; "wasted calls" is a side-metric shown below, not a 4th stage.
  const steps: { label: string; value: number; sub: string; level: Level }[] = [
    { label: "Proposed", value: f.proposed, sub: "by the AI council", level: "acc" },
    { label: "Evaluated", value: f.evaluated, sub: "reached the gate", level: "acc" },
    { label: "Opened", value: f.opened, sub: "cleared everything", level: f.opened > 0 ? "ok" : "mute" },
  ];

  const cmax = f.council.asserted + f.council.ungrounded + f.council.abstained || 1;
  const debate: { label: string; value: number; level: Level }[] = [
    { label: "Asserted (full debate)", value: f.council.asserted, level: "ok" },
    { label: "Reached the gate", value: f.council.toGate, level: "acc" },
    { label: "Dropped — ungrounded", value: f.council.ungrounded, level: "mute" },
    { label: "Dropped — proposer abstained", value: f.council.abstained, level: "mute" },
  ];

  const gate: { label: string; sub: string; value: number; color: string }[] = [
    { label: "IV-gate vetoes (total)", sub: "too rich or missing data", value: f.gate.ivTotal, color: color.ink2 },
    { label: "Real veto", sub: "genuinely too richly priced", value: f.gate.ivReal, color: color.accent },
    { label: "Fail-closed", sub: "missing input — safe default", value: f.gate.ivFail, color: f.gate.ivFail ? signal.warn.text : signal.ok.text },
    { label: "Eligibility vetoes", sub: "liquidity / tradability floor", value: f.gate.elig, color: color.ink2 },
  ];

  return (
    <>
      <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px", marginBottom: 16 }}>
        <div style={{ fontSize: 13, color: "#2c3645", lineHeight: 1.6 }}>{INTRO}</div>
      </div>

      {/* funnel */}
      <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "20px 22px", marginBottom: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 3, color: "#141b28" }}>
          Latest cycle — where candidates stop <span style={{ color: "#6a7280", fontWeight: 400 }}>· run #{f.runId ?? "—"}</span>
        </div>
        <div style={{ fontSize: 12, color: "#414956", marginBottom: 18 }}>Ideas flow left to right; each step can veto. Zero opened is healthy if nothing was genuinely cheap.</div>
        <div className="flex" style={{ alignItems: "stretch", gap: 8 }}>
          {steps.map((s) => {
            const lv = signal[s.level];
            const h = Math.max(34, (s.value / fmax) * 120);
            return (
              <div key={s.label} className="flex-1" style={{ textAlign: "center" }}>
                <div className="flex items-center justify-center" style={{ height: h, borderRadius: 9, background: lv.bg, border: `1px solid ${lv.border}` }}>
                  <span className="font-mono" style={{ fontSize: 24, fontWeight: 500, color: lv.text }}>{s.value}</span>
                </div>
                <div style={{ fontSize: 12, fontWeight: 500, color: "#2c3645", marginTop: 9 }}>{s.label}</div>
                <div style={{ fontSize: 11, color: "#6a7280", marginTop: 1 }}>{s.sub}</div>
              </div>
            );
          })}
        </div>
        {/* F3: side-metrics, visually separated from the flow above */}
        <div className="flex flex-wrap" style={{ gap: 20, marginTop: 16, paddingTop: 13, borderTop: "1px solid #edf0f4", fontSize: 11.5, color: "#414956" }}>
          <span>Wasted LLM calls <span style={{ color: "#6a7280" }}>(deliberated, then gate-vetoed)</span> · <span className="font-mono" style={{ fontWeight: 500 }}>{f.wasted}</span></span>
          <span>Cluster-cap rejected otherwise-passing · <span className="font-mono" style={{ fontWeight: 500, color: vm.capFlow.rejected ? signal.warn.text : color.ink2 }}>{vm.capFlow.rejected}</span></span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* inside the debate */}
        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Inside the AI debate</div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 14 }}>Where ideas drop out before they ever reach the gate.</div>
          {debate.map((r) => {
            const lv = signal[r.level];
            return (
              <div key={r.label} className="flex items-center gap-3" style={{ padding: "8px 0", borderTop: "1px solid #edf0f4" }}>
                <span style={{ fontSize: 12.5, color: "#2c3645", flex: 1 }}>{r.label}</span>
                <div style={{ width: 90, height: 6, background: "#edf0f4", borderRadius: 3, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${Math.max(3, (r.value / cmax) * 100)}%`, background: lv.text, borderRadius: 3 }} />
                </div>
                <span className="font-mono text-right" style={{ fontSize: 13, fontWeight: 500, color: lv.text, width: 26 }}>{r.value}</span>
              </div>
            );
          })}
        </div>
        {/* cheapness gate */}
        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>The cheapness gate</div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 14 }}>
            Only buys convexity that's genuinely cheap. A real veto (too rich) differs from a fail-closed veto (missing data).
          </div>
          {gate.map((r) => (
            <div key={r.label} className="flex justify-between items-center" style={{ padding: "9px 0", borderTop: "1px solid #edf0f4" }}>
              <div>
                <div style={{ fontSize: 12.5, color: "#2c3645" }}>{r.label}</div>
                <div style={{ fontSize: 11, color: "#6a7280" }}>{r.sub}</div>
              </div>
              <span className="font-mono" style={{ fontSize: 15, fontWeight: 500, color: r.color }}>{r.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* latest run's per-name deliberation — the "why" */}
      {vm.deliberation.rows.length > 0 && (
        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px", marginTop: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Latest decisions <span style={{ color: "#6a7280", fontWeight: 400 }}>· run #{vm.deliberation.runId} · proposer → adversary → strategist</span></div>
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 10, padding: "12px 4px 8px", borderBottom: "1px solid #cbd0da", fontSize: 10.5, color: "#6a7280", textTransform: "uppercase", letterSpacing: ".6px", fontWeight: 500, marginTop: 6 }}>
            <span>Name</span><span>Proposer</span><span>Adversary</span><span>Strategist</span>
          </div>
          {vm.deliberation.rows.map((d, i) => (
            <div key={i} className="grid items-center font-mono" style={{ gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 10, padding: "9px 4px", borderBottom: "1px solid #f6f8fa", fontSize: 12.5 }}>
              <span style={{ fontWeight: 500, color: "#141b28" }}>{d.symbol}</span>
              <span style={{ color: "#414956" }}>{d.dir ?? "—"}</span>
              <span style={{ color: "#414956" }}>{d.adversary ?? "—"}</span>
              <span style={{ color: "#2c3645", fontWeight: 500 }}>{d.conviction ?? "—"}</span>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 16 }}><CheapnessWatch data={vm.cheapness} /></div>
    </>
  );
}
