import type { ViewModel } from "../data/types";
import { color, signal, type Level } from "../theme/tokens";
import { Chip } from "./primitives";

interface Kpi {
  label: string;
  value: string;
  valColor: string;
  sub: string;
  chip: string;
  chipLevel: Level;
  barPct: number;
  barLevel: Level;
}

function buildKpis(vm: ViewModel): Kpi[] {
  const r = vm.readiness;
  const allPass = r.checkable > 0 && r.pass === r.checkable;
  const councilHealthy = vm.council.vlevel === "ok";
  return [
    {
      label: "Go-live readiness",
      value: `${r.pass} / ${r.checkable}`,
      valColor: color.ink,
      sub: `checkable gates pass · ${r.accruing} accruing`,
      chip: allPass ? "on track" : "in progress",
      chipLevel: allPass ? "ok" : "acc",
      barPct: r.checkable ? (r.pass / r.checkable) * 100 : 0,
      barLevel: "acc",
    },
    {
      label: "Safety",
      value: "Within frame",
      valColor: signal.ok.text,
      sub: `${vm.bookDD} book drawdown · ${vm.openN}/${vm.maxN} open`,
      chip: "safe",
      chipLevel: "ok",
      barPct: vm.maxN ? (vm.openN / vm.maxN) * 100 || 3 : 3,
      barLevel: "ok",
    },
    {
      label: "AI council health",
      value: councilHealthy ? "Healthy" : "Degraded",
      valColor: signal[vm.council.vlevel].text,
      sub: `${vm.council.verdict.toLowerCase()} · #${vm.council.runId ?? "—"}`,
      chip: councilHealthy ? "clean" : "needs a look",
      chipLevel: vm.council.vlevel,
      barPct: 100,
      barLevel: vm.council.vlevel,
    },
    {
      label: "Edge accrual",
      value: `${vm.edgeAccrual.n} / ~${vm.edgeAccrual.target}`,
      valColor: color.ink,
      sub: "resolved bets toward the first null read",
      chip: "accruing",
      chipLevel: "mute",
      barPct: Math.min(100, (vm.edgeAccrual.n / vm.edgeAccrual.target) * 100),
      barLevel: "acc",
    },
  ];
}

/** The four north-star KPI cards (desktop 4-col). */
export function KpiRow({ vm }: { vm: ViewModel }) {
  return (
    <div className="grid grid-cols-4 gap-3.5">
      {buildKpis(vm).map((k) => (
        <div key={k.label} className="bg-white border rounded-card shadow-card" style={{ borderColor: "#cbd0da", padding: "16px 17px" }}>
          <div className="flex items-center justify-between gap-2">
            <span style={{ fontSize: 12, color: "#414956", fontWeight: 500 }}>{k.label}</span>
            <Chip level={k.chipLevel}>{k.chip}</Chip>
          </div>
          <div className="font-mono" style={{ fontSize: 27, fontWeight: 700, marginTop: 11, letterSpacing: "-.5px", color: k.valColor }}>
            {k.value}
          </div>
          <div style={{ fontSize: 11.5, color: "#414956", marginTop: 3, lineHeight: 1.45 }}>{k.sub}</div>
          <div style={{ height: 5, background: "#edf0f4", borderRadius: 3, marginTop: 13, overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${k.barPct}%`, background: signal[k.barLevel].text, borderRadius: 3 }} />
          </div>
        </div>
      ))}
    </div>
  );
}
