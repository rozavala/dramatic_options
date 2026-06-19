import { STATE_PRESENT } from "../data/status";
import type { ViewModel } from "../data/types";
import { color, signal } from "../theme/tokens";
import { Chip } from "./primitives";

/** The road to go-live: a readiness ring + the five T4 conditions as status rows (accruing rows pulse). */
export function T4Road({ vm }: { vm: ViewModel }) {
  const r = vm.readiness;
  const allPass = r.checkable > 0 && r.pass === r.checkable;
  const ringColor = allPass ? signal.ok.text : color.accent;
  return (
    <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "22px 24px", marginTop: 18 }}>
      <div className="flex items-center" style={{ gap: 18, paddingBottom: 16, borderBottom: "1px solid #edf0f4" }}>
        <div className="flex flex-col items-center justify-center" style={{ width: 80, height: 80, borderRadius: "50%", border: `3px solid ${ringColor}`, flex: "none" }}>
          <span className="font-mono" style={{ fontSize: 24, fontWeight: 700, color: ringColor, lineHeight: 1 }}>{r.pass}/{r.checkable}</span>
          <span style={{ fontSize: 9, color: "#6a7280", textTransform: "uppercase", letterSpacing: ".6px", marginTop: 2 }}>gates</span>
        </div>
        <div className="flex-1">
          <div style={{ fontSize: 16, fontWeight: 500, letterSpacing: "-.2px", color: "#141b28" }}>
            The road to go-live <span style={{ color: "#6a7280", fontWeight: 400 }}>· T4 readiness</span>
          </div>
          <div style={{ fontSize: 12.5, color: "#414956", marginTop: 3, lineHeight: 1.5, maxWidth: 560 }}>
            The pre-committed conditions for the operator to consider switching from paper to real money — {r.accruing} more
            accruing. Not a go signal; a checklist.
          </div>
        </div>
      </div>
      <div className="flex flex-col" style={{ gap: 2, marginTop: 8 }}>
        {vm.t4.map((cond) => {
          const [lvl, icon, tag] = STATE_PRESENT[cond.state];
          const s = signal[lvl];
          const accru = cond.state === "accruing";
          return (
            <div key={cond.id} className="flex items-center" style={{ gap: 14, padding: "12px 4px", borderBottom: "1px solid #f6f8fa" }}>
              <span
                className="flex items-center justify-center"
                style={{ width: 27, height: 27, borderRadius: 8, flex: "none", fontSize: 13, fontWeight: 700, color: s.text, background: s.bg, border: `1px solid ${s.border}`, animation: accru ? "accruePulse 2.4s ease-in-out infinite" : undefined }}
              >
                {icon}
              </span>
              <span className="font-mono" style={{ fontSize: 11, color: "#6a7280", width: 18, flex: "none" }}>0{cond.id}</span>
              <div className="flex-1 min-w-0">
                <div style={{ fontSize: 13.5, fontWeight: 500, color: "#141b28" }}>{cond.name}</div>
                <div style={{ fontSize: 11.5, color: "#414956", marginTop: 1, lineHeight: 1.45 }}>{cond.detail}</div>
              </div>
              <Chip level={lvl}>{tag}</Chip>
            </div>
          );
        })}
      </div>
    </div>
  );
}
