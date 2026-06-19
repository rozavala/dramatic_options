import type { ViewModel } from "../data/types";
import { signal } from "../theme/tokens";
import { Chip, StatusDot } from "./primitives";

const BEATS: [keyof ViewModel["beats"], string][] = [
  ["kill", "KILL"],
  ["cycle", "Cycle"],
  ["council", "Council"],
  ["discovery", "Discovery"],
  ["schema", "Schema"],
];

/** The one-glance status banner: tonal container + 5px left edge, headline + sub, issue chips, heartbeat pills. */
export function StatusBanner({ vm }: { vm: ViewModel }) {
  const s = signal[vm.level];
  return (
    <div style={{ background: s.bg, border: `1px solid ${s.border}`, borderLeft: `5px solid ${s.text}`, borderRadius: 16, padding: "20px 22px" }}>
      <div className="flex items-start gap-3.5">
        <span style={{ marginTop: 5 }}>
          <StatusDot level={vm.level} size={14} />
        </span>
        <div className="min-w-0 flex-1">
          <div style={{ fontSize: 20, fontWeight: 500, letterSpacing: "-.3px", color: s.text }}>{vm.headline}</div>
          <div style={{ fontSize: 13.5, color: "#2c3645", marginTop: 4, lineHeight: 1.5, maxWidth: 640 }}>{vm.sub}</div>
          {vm.issues.length > 0 && (
            <div className="flex flex-wrap gap-2" style={{ marginTop: 13 }}>
              {vm.issues.map((iss, i) => (
                <Chip key={i} level="warn" style={{ fontSize: 11.5, padding: "5px 11px" }}>
                  {iss.text}
                </Chip>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-2" style={{ marginTop: 15, paddingLeft: 28 }}>
        {BEATS.map(([key, label]) => {
          const lvl = vm.beatLevels[key];
          return (
            <div key={key} className="flex items-center" style={{ gap: 7, padding: "6px 11px", borderRadius: 8, background: "#fff", border: "1px solid #cbd0da" }}>
              <StatusDot level={lvl} size={6} />
              <span style={{ fontSize: 11, color: "#414956" }}>{label}</span>
              <span className="font-mono" style={{ fontSize: 11.5, fontWeight: 500, color: signal[lvl].text }}>
                {vm.beats[key]}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
