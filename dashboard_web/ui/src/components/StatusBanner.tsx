import type { ViewModel } from "../data/types";
import { signal } from "../theme/tokens";
import { StatusDot } from "./primitives";

const BEATS: [keyof ViewModel["beats"], string][] = [
  ["kill", "KILL"],
  ["cycle", "L2 monitor"],
  ["council", "L1 council"],
  ["discovery", "L0 discovery"],
];

/** The one-glance status line: tonal container, headline + issues, heartbeat pills inline. The schema pill
 *  only appears when the schema is behind (a warning is worth a pill; "19/18 fine" is not). */
export function StatusBanner({ vm }: { vm: ViewModel }) {
  const s = signal[vm.level];
  const head = vm.headline.replace(/^[^\p{L}\p{N}]+/u, "").split(" — ")[0];
  const beats: [keyof ViewModel["beats"], string][] = vm.beatLevels.schema === "ok" ? BEATS : [...BEATS, ["schema", "Schema"]];
  return (
    <div style={{ background: s.bg, border: `1px solid ${s.border}`, borderLeft: `5px solid ${s.text}`, borderRadius: 16, padding: "14px 20px" }}>
      <div className="flex items-center flex-wrap" style={{ gap: 16 }}>
        <StatusDot level={vm.level} size={12} />
        <div className="flex-1 min-w-0 flex items-baseline flex-wrap" style={{ gap: 10 }}>
          <span style={{ fontSize: 17, fontWeight: 500, letterSpacing: "-.3px", color: s.text }}>{head}</span>
          <span style={{ fontSize: 13, color: "#2c3645" }}>{vm.sub}</span>
        </div>
        <div className="flex flex-wrap" style={{ gap: 8 }}>
          {beats.map(([key, label]) => {
            const lvl = vm.beatLevels[key];
            return (
              <div key={key} className="flex items-center" style={{ gap: 7, padding: "5px 10px", borderRadius: 8, background: "#fff", border: "1px solid #cbd0da" }}>
                <StatusDot level={lvl} size={6} />
                <span style={{ fontSize: 11, color: "#414956" }}>{label}</span>
                <span className="font-mono" style={{ fontSize: 11.5, fontWeight: 500, color: signal[lvl].text }}>{vm.beats[key]}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
