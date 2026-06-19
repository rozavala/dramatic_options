import type { ViewModel } from "../data/types";
import { signal, type Level } from "../theme/tokens";

const INTRO =
  "The point of the calibration period is to prove the apparatus earns its keep. Each shadow book switches one " +
  "piece off, so any edge can be isolated. These tails are forward calibration substrate — never a pass/fail gate " +
  "by themselves.";

export function Edge({ vm }: { vm: ViewModel }) {
  const books: { name: string; tag: string; n: number; p95: number | null; level: Level }[] = [
    { name: "Real (live paper)", tag: "the actual book — gate on, council on", ...vm.perf.real, level: "acc" },
    { name: "Shadow", tag: "gate on, council off — isolates the council", ...vm.perf.shadow, level: "mute" },
    { name: "3A · no-gate", tag: "gate off, same names — isolates the gate", ...vm.perf.a3, level: "mute" },
    { name: "3B · whole basket", tag: "gate off, everything — beat-the-basket", ...vm.perf.basket, level: "mute" },
  ];
  const maxP95 = Math.max(1, ...books.map((b) => b.p95 ?? 0));
  const anyResolved = books.some((b) => b.p95 != null);
  const caveat = anyResolved
    ? "Early and not yet significant, but the real book should out-tail shadow and no-gate as bets resolve."
    : "All books are accruing — no bets have resolved yet (~6 months from the first entry). This is expected, not a failure.";

  const outcomes: { label: string; sub: string; value: string; color: string }[] = [
    { label: "Premium paid", sub: "the most that can be lost", value: vm.perf.paid, color: "#141b28" },
    { label: "Premium bled", sub: "decayed so far", value: vm.perf.bledPct != null ? `${vm.perf.bledPct}%` : "—", color: vm.perf.bledPct != null ? signal.warn.text : signal.mute.text },
    { label: "Hit rate", sub: vm.perf.closed ? `${vm.perf.hits}/${vm.perf.closed} closed positive` : "no closed bets yet", value: vm.perf.hitRate != null ? `${vm.perf.hitRate}%` : "accruing", color: vm.perf.hitRate != null ? "#2c3645" : signal.mute.text },
  ];
  const brierRows = (vm.brier.roles.length ? vm.brier.roles : [{ label: "strategist (final)", value: vm.brier.strategist }]);

  return (
    <>
      <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px", marginBottom: 16 }}>
        <div style={{ fontSize: 13, color: "#2c3645", lineHeight: 1.6 }}>{INTRO}</div>
      </div>

      {/* beat brain-off */}
      <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "20px 22px", marginBottom: 16 }}>
        <div className="flex items-baseline justify-between">
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Does the machine beat "brain-off"?</div>
          <div style={{ fontSize: 11.5, color: "#6a7280" }}>tail multiple (p95) per book · higher = fatter winners</div>
        </div>
        <div style={{ fontSize: 12, color: "#414956", marginTop: 4, marginBottom: 16, lineHeight: 1.5 }}>
          We run shadow copies of the book with pieces switched off, so any edge can be isolated. The real book should out-tail them.
        </div>
        {books.map((b) => {
          const has = b.p95 != null;
          const w = has ? Math.max(4, ((b.p95 as number) / maxP95) * 100) : 0;
          const lv = signal[b.level];
          return (
            <div key={b.name} className="flex items-center gap-3.5" style={{ padding: "12px 0", borderTop: "1px solid #edf0f4" }}>
              <div style={{ width: 150, flex: "none" }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: "#141b28" }}>{b.name}</div>
                <div style={{ fontSize: 11, color: "#6a7280" }}>{b.tag}</div>
              </div>
              <div style={{ flex: 1, height: 26, background: "#edf0f4", borderRadius: 6, position: "relative", overflow: "hidden" }}>
                {has ? (
                  <div style={{ position: "absolute", left: 0, top: 0, height: "100%", width: `${w}%`, background: lv.bg, borderRight: `2px solid ${lv.text}`, borderRadius: 6 }} />
                ) : (
                  <div style={{ position: "absolute", inset: 0, background: "repeating-linear-gradient(135deg,#edf0f4,#edf0f4 7px,#e7eaef 7px,#e7eaef 14px)", borderRadius: 6, animation: "accruePulse 2.6s ease-in-out infinite" }} />
                )}
              </div>
              <div className="text-right font-mono" style={{ width: 118, flex: "none" }}>
                <span style={{ fontSize: 15, fontWeight: 500, color: has ? lv.text : signal.mute.text }}>{has ? `${(b.p95 as number).toFixed(2)}×` : "accruing"}</span>
                <span style={{ fontSize: 11, color: "#6a7280" }}> · n={b.n}</span>
              </div>
            </div>
          );
        })}
        <div style={{ fontSize: 11.5, color: "#6a7280", marginTop: 14, lineHeight: 1.5, fontStyle: "italic" }}>{caveat}</div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* premium & outcomes */}
        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 14, color: "#141b28" }}>Premium &amp; outcomes so far</div>
          {outcomes.map((o) => (
            <div key={o.label} className="flex justify-between items-center" style={{ padding: "10px 0", borderTop: "1px solid #edf0f4" }}>
              <div>
                <div style={{ fontSize: 12.5, color: "#2c3645" }}>{o.label}</div>
                <div style={{ fontSize: 11, color: "#6a7280" }}>{o.sub}</div>
              </div>
              <span className="font-mono" style={{ fontSize: 16, fontWeight: 500, color: o.color }}>{o.value}</span>
            </div>
          ))}
        </div>
        {/* brier */}
        <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Is the council's conviction calibrated?</div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 14 }}>
            Brier score grades how well the AI's confidence matched reality. Lower is better; 0 is perfect.
          </div>
          {brierRows.map((r) => (
            <div key={r.label} className="flex justify-between items-center" style={{ padding: "9px 0", borderTop: "1px solid #edf0f4" }}>
              <span style={{ fontSize: 12.5, color: "#2c3645" }}>{r.label}</span>
              <span className="font-mono" style={{ fontSize: 14, fontWeight: 500, color: r.value != null ? signal.ok.text : signal.mute.text }}>
                {r.value != null ? r.value.toFixed(3) : "accruing"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
