import { clusterLevel } from "../data/status";
import type { ViewModel } from "../data/types";
import { color, signal } from "../theme/tokens";
import { Sparkline } from "./Sparkline";
import { Chip } from "./primitives";

const INTRO =
  "The frozen risk frame caps the whole book at 10% of a $100k paper account, any one name at 1%, and any " +
  "correlated cluster at ~2%. The kill rule halts new entries at 20% book drawdown. Everything here is " +
  "read-only — the dashboard never trades.";

function Tile({ label, value, valColor, sub, series }: { label: string; value: string; valColor: string; sub: string; series?: { equity: number }[] }) {
  return (
    <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "16px 17px" }}>
      <div style={{ fontSize: 12, color: "#414956" }}>{label}</div>
      <div className="font-mono" style={{ fontSize: 25, fontWeight: 700, marginTop: 9, color: valColor, letterSpacing: "-.5px" }}>{value}</div>
      <div style={{ fontSize: 11.5, color: "#6a7280", marginTop: 3 }}>{sub}</div>
      {series && <Sparkline series={series} height={30} />}
    </div>
  );
}

export function Safety({ vm }: { vm: ViewModel }) {
  const c = vm.council;
  const sig = signal[c.vlevel];
  const councilOk = c.vlevel === "ok";
  const rows: { label: string; value: string; color: string }[] = [
    { label: "Full round-trips", value: `${c.roundtrips}`, color: color.ink2 },
    { label: "Proposer parse-fails", value: `${c.parseFail}/${c.parseCalled}`, color: c.parseFail ? signal.warn.text : signal.ok.text },
    { label: "Recent run streak", value: c.streak, color: color.ink2 },
    { label: "Council cost", value: c.cost, color: color.ink2 },
    { label: "Models", value: c.models, color: color.ink3 },
  ];
  const dr = vm.dualread;
  const tripwires = [
    { label: "Δ iv/rv (median / max)", val: dr.medianD != null ? `${dr.medianD} / ${dr.maxD}` : "—", tripped: dr.deltaTripped },
    { label: `material flips (≥${dr.flipFloor}, rolling-5)`, val: `${dr.flipSessions}/${dr.window}`, tripped: dr.flipTripped },
    { label: "coverage gaps (rolling-5)", val: `${dr.gapSessions}/${dr.window}`, tripped: dr.gapTripped },
  ];

  return (
    <>
      <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px", marginBottom: 16 }}>
        <div style={{ fontSize: 13, color: "#2c3645", lineHeight: 1.6 }}>{INTRO}</div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5" style={{ marginBottom: 16 }}>
        <Tile label="Paper equity" value={vm.equity} valColor={color.ink} sub={`${vm.deltaFrame} (informational)`} series={vm.equitySeries} />
        <Tile label="Book drawdown" value={vm.bookDD} valColor={signal[vm.bookDDlevel].text} sub="halts new entries at 20%" />
        <Tile label="Open positions" value={`${vm.openN}/${vm.maxN}`} valColor={color.ink} sub={`${vm.openPrem} premium at risk`} />
        <Tile label="Headroom" value={vm.headroom} valColor={signal.ok.text} sub={`of ${vm.bookBudget} book budget`} />
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: "1.3fr 1fr" }}>
        {/* cluster exposure */}
        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Correlation-cluster exposure</div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, marginBottom: 15, lineHeight: 1.5 }}>
            Each correlated theme is capped at ~2% of the account so a crowded bet can't masquerade as diversification.
          </div>
          {vm.clusters.map((cl) => {
            const frac = cl.cap ? cl.premium / cl.cap : 0;
            const lv = signal[clusterLevel(frac)];
            return (
              <div key={cl.name} style={{ marginBottom: 13 }}>
                <div className="flex justify-between items-baseline" style={{ marginBottom: 5 }}>
                  <span className="font-mono" style={{ fontSize: 12.5, fontWeight: 500, color: "#2c3645" }}>{cl.name}</span>
                  <span className="font-mono" style={{ fontSize: 11.5, color: "#414956" }}>
                    ${cl.premium.toLocaleString()} / ${cl.cap.toLocaleString()} · <span style={{ color: lv.text, fontWeight: 500 }}>{Math.round(frac * 100)}%</span>
                  </span>
                </div>
                <div style={{ height: 8, background: "#edf0f4", borderRadius: 4, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${Math.max(2, frac * 100)}%`, background: lv.text, borderRadius: 4 }} />
                </div>
              </div>
            );
          })}
        </div>

        {/* council health */}
        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>AI council — deliberation health</div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5 }}>
            Three different AI models debate each idea (proposer → adversary → strategist). They only <em>suggest</em> — the gate still decides.
          </div>
          <div className="flex items-center" style={{ gap: 11, margin: "16px 0 14px", padding: 13, borderRadius: 10, background: sig.bg, border: `1px solid ${sig.border}` }}>
            <span style={{ fontSize: 20 }}>{councilOk ? "✓" : "⚠"}</span>
            <div>
              <div style={{ fontSize: 14.5, fontWeight: 500, color: sig.text }}>{c.verdict}</div>
              <div style={{ fontSize: 11.5, color: "#414956" }}>run #{c.runId ?? "—"} · {councilOk ? "a no-entry result is still healthy" : "worth a look — a degenerate row fired"}</div>
            </div>
          </div>
          {rows.map((r) => (
            <div key={r.label} className="flex justify-between items-baseline" style={{ gap: 14, padding: "7px 0", borderTop: "1px solid #edf0f4" }}>
              <span style={{ fontSize: 12, color: "#414956", flex: "none" }}>{r.label}</span>
              <span className="font-mono text-right" style={{ fontSize: 12, fontWeight: 500, color: r.color }}>{r.value}</span>
            </div>
          ))}
          {c.byProvider.length > 0 && (
            <div style={{ marginTop: 9, paddingTop: 9, borderTop: "1px solid #edf0f4" }}>
              <div style={{ fontSize: 11, color: "#6a7280", marginBottom: 5 }}>Per-provider parse health · latest run</div>
              {c.byProvider.map((p) => (
                <div key={p.provider} className="flex justify-between items-baseline" style={{ gap: 14, padding: "3px 0" }}>
                  <span className="font-mono" style={{ fontSize: 11.5, color: "#414956" }}>{p.provider}</span>
                  <span className="font-mono" style={{ fontSize: 11.5, fontWeight: 500, color: p.parseError ? signal.warn.text : signal.ok.text }}>{p.parseError}/{p.calls} fail</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* OPRA dual-read soak (§5 safety) + LLM cost ledger */}
      <div className="grid gap-4" style={{ gridTemplateColumns: "1.3fr 1fr", marginTop: 16 }}>
        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>OPRA gate dual-read <span style={{ color: "#6a7280", fontWeight: 400 }}>· §5 soak</span></div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, marginBottom: 14, lineHeight: 1.5 }}>
            The entry gate reads the real OPRA chain; INDICATIVE shadows it (veto-only). A tripped wire fires the §5 fail-closed response (investigate / revert + page).
          </div>
          {tripwires.map((t) => (
            <div key={t.label} className="flex justify-between items-center" style={{ gap: 14, padding: "8px 0", borderTop: "1px solid #edf0f4" }}>
              <span style={{ fontSize: 12.5, color: "#2c3645" }}>{t.label}</span>
              <span className="flex items-center" style={{ gap: 9 }}>
                <span className="font-mono" style={{ fontSize: 12, color: "#414956" }}>{t.val}</span>
                <Chip level={t.tripped ? "bad" : "ok"}>{t.tripped ? "⚠ TRIPPED" : "clear"}</Chip>
              </span>
            </div>
          ))}
          <div style={{ fontSize: 11, color: "#6a7280", marginTop: 12, lineHeight: 1.5 }}>
            {dr.lastRun != null ? `latest #${dr.lastRun}` : "no sessions yet"} · {dr.sessions} sessions · OPRA coverage {dr.opraCov != null ? `${Math.round(dr.opraCov * 100)}%` : "—"}
            {dr.vetoUntil && <> · disagree-veto until {dr.vetoUntil} ({dr.vetoActive ? "active" : "lapsed"})</>}
          </div>
        </div>

        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>LLM cost ledger</div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, marginBottom: 12, lineHeight: 1.5 }}>Cumulative spend — cost-as-argument (SPEC §4).</div>
          {[
            { label: "L0 framer (discovery)", value: vm.cost.framer },
            { label: "L1 council", value: vm.cost.council },
            { label: "Cumulative", value: vm.cost.cumulative },
          ].map((r, i) => (
            <div key={r.label} className="flex justify-between items-baseline" style={{ gap: 14, padding: "9px 0", borderTop: i ? "1px solid #edf0f4" : "none" }}>
              <span style={{ fontSize: 12.5, color: "#2c3645" }}>{r.label}</span>
              <span className="font-mono" style={{ fontSize: 14, fontWeight: 500, color: i === 2 ? "#141b28" : "#414956" }}>{r.value}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
