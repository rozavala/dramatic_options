import { STATE_PRESENT, isAccruingState } from "../data/status";
import type { ViewModel } from "../data/types";
import { signal } from "../theme/tokens";
import { Card, Chip } from "./primitives";

/** The road to go-live, compact: one row per condition (icon · number · name — detail · tag). Not a go signal. */
export function T4Road({ vm }: { vm: ViewModel }) {
  const r = vm.readiness;
  return (
    <Card style={{ padding: "18px 22px" }}>
      <div className="flex items-baseline justify-between" style={{ gap: 12 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>
          The road to go-live
          <span style={{ color: "#6a7280", fontWeight: 400 }}> · T4 readiness · {r.pass} of {r.checkable} checkable met · {r.accruing} accruing · not a go signal</span>
        </div>
      </div>
      <div style={{ marginTop: 10 }}>
        {vm.t4.map((cond) => {
          const [lvl, icon, tag] = STATE_PRESENT[cond.state];
          const s = signal[lvl];
          return (
            <div key={cond.id} className="flex items-center" style={{ gap: 12, padding: "9px 4px", borderTop: "1px solid #f6f8fa" }}>
              <span className="flex items-center justify-center" style={{ width: 24, height: 24, borderRadius: 7, flex: "none", fontSize: 12, fontWeight: 700, color: s.text, background: s.bg, border: `1px solid ${s.border}`, animation: isAccruingState(cond.state) ? "accruePulse 2.4s ease-in-out infinite" : undefined }}>
                {icon}
              </span>
              <span className="font-mono" style={{ fontSize: 11, color: "#6a7280", width: 18, flex: "none" }}>0{cond.id}</span>
              <span className="flex-1 min-w-0" style={{ fontSize: 13, color: "#141b28", fontWeight: 500 }}>
                {cond.name} <span style={{ color: "#6a7280", fontWeight: 400, fontSize: 12 }}>— {cond.detail}</span>
              </span>
              <Chip level={lvl}>{tag}</Chip>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
