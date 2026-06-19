import type { ViewModel } from "../data/types";
import { color } from "../theme/tokens";

const MISSION =
  "This is a paper-trading harness, not a live fund. Right now success means three things: run safely inside " +
  "the frozen risk frame, keep the three-model AI council deliberating cleanly, and accrue enough resolved bets " +
  "to prove the machine beats “brain-off.” We are deliberately not optimizing for P&L yet — the book is tiny on " +
  "purpose. The finish line is T4: the operator’s decision to consider real money.";

/** "What we're optimizing for right now" — mission copy + the Calibration phase mini-panel. */
export function MissionStrip({ vm }: { vm: ViewModel }) {
  return (
    <div className="flex gap-3.5 bg-white border rounded-card shadow-card" style={{ marginTop: 16, borderColor: "#cbd0da", borderLeft: `3px solid ${color.accent}`, padding: "18px 20px" }}>
      <div className="flex-1">
        <div style={{ fontSize: 11, color: color.accent, textTransform: "uppercase", letterSpacing: "1.1px", fontWeight: 700, marginBottom: 6 }}>
          What we're optimizing for right now
        </div>
        <div style={{ fontSize: 14.5, lineHeight: 1.6, color: "#2c3645", maxWidth: 790 }}>{MISSION}</div>
      </div>
      <div style={{ flex: "none", width: 190, borderLeft: "1px solid #edf0f4", paddingLeft: 18 }}>
        <div style={{ fontSize: 11, color: "#414956", marginBottom: 4 }}>Phase</div>
        <div style={{ fontSize: 15, fontWeight: 500, color: "#141b28" }}>Calibration</div>
        <div style={{ fontSize: 11.5, color: "#414956", marginTop: 2 }}>{vm.phaseSub}</div>
        <div style={{ height: 7, background: "#edf0f4", borderRadius: 4, marginTop: 11, overflow: "hidden" }}>
          <div style={{ height: "100%", width: vm.phasePct, background: color.accent, borderRadius: 4 }} />
        </div>
      </div>
    </div>
  );
}
