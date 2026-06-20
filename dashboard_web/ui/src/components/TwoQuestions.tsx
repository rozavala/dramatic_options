import type { ViewModel } from "../data/types";
import { color, signal, type Level } from "../theme/tokens";
import { Sparkline } from "./Sparkline";

function MetricTile({ label, value, valColor, sub, series }: { label: string; value: string; valColor: string; sub: string; series?: { equity: number }[] }) {
  return (
    <div style={{ background: "#f6f8fa", border: "1px solid #edf0f4", borderRadius: 10, padding: "12px 13px" }}>
      <div style={{ fontSize: 11, color: "#414956" }}>{label}</div>
      <div className="font-mono" style={{ fontSize: 19, fontWeight: 700, marginTop: 5, color: valColor }}>{value}</div>
      <div style={{ fontSize: 10.5, color: "#6a7280", marginTop: 2, lineHeight: 1.4 }}>{sub}</div>
      {series && <Sparkline series={series} />}
    </div>
  );
}

/** Q1 "Is it safe to run?" (4 tiles + council verdict box) and Q2 "Is the brain earning its keep?" (p95 tail bars). */
export function TwoQuestions({ vm }: { vm: ViewModel }) {
  const c = vm.council;
  const councilOk = c.vlevel === "ok";
  const sig = signal[c.vlevel];

  const books: { name: string; tag: string; n: number; p95: number | null; level: Level }[] = [
    { name: "Real (live paper)", tag: "gate + council on", ...vm.perf.real, level: "acc" },
    { name: "Shadow", tag: "gate on, council off", ...vm.perf.shadow, level: "mute" },
    { name: "3A · no-gate", tag: "gate off, same names", ...vm.perf.a3, level: "mute" },
    { name: "3B · whole basket", tag: "gate off, everything", ...vm.perf.basket, level: "mute" },
  ];
  const maxP95 = Math.max(1, ...books.map((b) => b.p95 ?? 0));
  const anyResolved = books.some((b) => b.p95 != null);
  const caveat = anyResolved
    ? "Early and not yet significant — the real book should out-tail the rest as bets resolve."
    : "All books are accruing — no bets have resolved yet (~6 months from the first entry). Expected, not a failure.";

  return (
    <>
      <div style={{ fontSize: 11, color: "#414956", textTransform: "uppercase", letterSpacing: "1.2px", fontWeight: 700, margin: "26px 0 12px" }}>
        The two questions that matter today
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3.5 items-start">
        {/* Q1 — safe to run? */}
        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "20px 22px" }}>
          <div className="flex items-baseline gap-2.5">
            <span className="font-mono" style={{ fontSize: 11, color: color.accent, fontWeight: 700 }}>Q1</span>
            <span style={{ fontSize: 17, fontWeight: 500, letterSpacing: "-.3px", color: "#141b28" }}>Is it safe to run?</span>
          </div>
          <div className="grid grid-cols-2 gap-2.5" style={{ marginTop: 15 }}>
            <MetricTile label="Paper equity" value={vm.equity} valColor={color.ink} sub={`${vm.deltaFrame} (informational)`} series={vm.equitySeries} />
            <MetricTile label="Book drawdown" value={vm.bookDD} valColor={signal[vm.bookDDlevel].text} sub="halts new entries at 20%" />
            <MetricTile label="Open positions" value={`${vm.openN}/${vm.maxN}`} valColor={color.ink} sub={`${vm.openPrem} premium at risk`} />
            <MetricTile label="Headroom" value={vm.headroom} valColor={signal.ok.text} sub={`of ${vm.bookBudget} book budget`} />
          </div>
          <div className="flex items-center" style={{ gap: 11, marginTop: 13, padding: 13, borderRadius: 10, background: sig.bg, border: `1px solid ${sig.border}` }}>
            <span style={{ fontSize: 18 }}>{councilOk ? "✓" : "⚠"}</span>
            <div>
              <div style={{ fontSize: 13.5, fontWeight: 500, color: sig.text }}>AI council — {c.verdict}</div>
              <div style={{ fontSize: 11.5, color: "#414956" }}>run #{c.runId ?? "—"} · {councilOk ? "a no-entry result is still healthy" : "worth a look"}</div>
            </div>
          </div>
        </div>

        {/* Q2 — brain earning its keep? */}
        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "20px 22px" }}>
          <div className="flex items-baseline gap-2.5">
            <span className="font-mono" style={{ fontSize: 11, color: color.accent, fontWeight: 700 }}>Q2</span>
            <span style={{ fontSize: 17, fontWeight: 500, letterSpacing: "-.3px", color: "#141b28" }}>Is the brain earning its keep?</span>
          </div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 7, marginBottom: 4, lineHeight: 1.5 }}>
            Tail multiple (p95) per book — the real book should out-tail “brain-off.”
          </div>
          {books.map((b) => {
            const has = b.p95 != null;
            const w = has ? Math.max(4, ((b.p95 as number) / maxP95) * 100) : 0;
            const lv = signal[b.level];
            return (
              <div key={b.name} className="flex items-center gap-3" style={{ padding: "9px 0", borderTop: "1px solid #edf0f4" }}>
                <div style={{ width: 118, flex: "none" }}>
                  <div style={{ fontSize: 12, fontWeight: 500, color: "#141b28" }}>{b.name}</div>
                  <div style={{ fontSize: 10, color: "#6a7280" }}>{b.tag}</div>
                </div>
                <div style={{ flex: 1, height: 22, background: "#edf0f4", borderRadius: 6, position: "relative", overflow: "hidden" }}>
                  {has ? (
                    <div style={{ position: "absolute", left: 0, top: 0, height: "100%", width: `${w}%`, background: lv.bg, borderRight: `2px solid ${lv.text}`, borderRadius: 6 }} />
                  ) : (
                    <div style={{ position: "absolute", inset: 0, background: "repeating-linear-gradient(135deg,#edf0f4,#edf0f4 7px,#e7eaef 7px,#e7eaef 14px)", borderRadius: 6, animation: "accruePulse 2.6s ease-in-out infinite" }} />
                  )}
                </div>
                <div className="font-mono text-right" style={{ width: 64, flex: "none", fontSize: 13, fontWeight: 500, color: has ? lv.text : signal.mute.text }}>
                  {has ? `${(b.p95 as number).toFixed(2)}×` : "accruing"}
                </div>
              </div>
            );
          })}
          <div style={{ fontSize: 11.5, color: "#6a7280", marginTop: 11, lineHeight: 1.5, fontStyle: "italic" }}>{caveat}</div>
        </div>
      </div>
    </>
  );
}
