import type { ViewModel } from "../data/types";
import type { SectionId } from "../nav";
import { color, signal } from "../theme/tokens";

interface Stat { value: string; color: string; label: string }
interface CardDef { id: SectionId; title: string; dot: string; desc: string; stats: Stat[] }

function buildCards(vm: ViewModel): CardDef[] {
  return [
    {
      id: "safety", title: "Safety & Risk", dot: color.dotBlue,
      desc: "Book drawdown, slot usage, cluster caps and the AI council’s deliberation health.",
      stats: [
        { value: vm.bookDD, color: signal.ok.text, label: "book drawdown" },
        { value: `${vm.openN}/${vm.maxN}`, color: color.ink, label: "positions open" },
      ],
    },
    {
      id: "edge", title: "The Edge", dot: color.dotRed,
      desc: "Whether the real book out-tails the brain-off shadow books, and if conviction is calibrated.",
      stats: [
        { value: vm.perf.real.p95 != null ? `${vm.perf.real.p95.toFixed(1)}×` : "—", color: vm.perf.real.p95 != null ? signal.ok.text : signal.mute.text, label: "real p95 tail" },
        { value: `${vm.perf.real.n}`, color: color.ink, label: "resolved bets" },
      ],
    },
    {
      id: "pipeline", title: "Pipeline", dot: color.dotAmber,
      desc: "How many ideas the council proposed, where they were vetoed, and what reached the gate.",
      stats: [
        { value: `${vm.funnel.proposed}`, color: color.ink, label: "proposed" },
        { value: `${vm.funnel.opened}`, color: signal.ok.text, label: "opened" },
      ],
    },
    {
      id: "book", title: "Book & Data", dot: color.dotGreen,
      desc: "Open positions, the names the scanner is watching, and the IV baseline accruing.",
      stats: [
        { value: `${vm.openCount}`, color: color.ink, label: "open positions" },
        { value: vm.data[0]?.value ?? "—", color: color.ink, label: "chain symbols" },
      ],
    },
  ];
}

/** The four "jump into the detail" cards (four-color dots), each navigates to its section. */
export function SectionCards({ vm, onNavigate }: { vm: ViewModel; onNavigate: (id: SectionId) => void }) {
  return (
    <>
      <div style={{ fontSize: 11, color: "#414956", textTransform: "uppercase", letterSpacing: "1.2px", fontWeight: 700, margin: "26px 0 12px" }}>
        Jump into the detail
      </div>
      <div className="grid grid-cols-2 gap-3.5">
        {buildCards(vm).map((c) => (
          <button
            key={c.id}
            onClick={() => onNavigate(c.id)}
            className="text-left bg-white border border-cardborder hover:border-accent rounded-card shadow-card hover:shadow-cardhover flex flex-col transition-[border-color,box-shadow] duration-150"
            style={{ padding: "17px 19px", cursor: "pointer", gap: 13 }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center" style={{ gap: 9 }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", flex: "none", background: c.dot, boxShadow: `0 0 0 3px ${c.dot}22` }} />
                <span style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>{c.title}</span>
              </div>
              <span style={{ fontSize: 12, color: color.accent, fontWeight: 500 }}>View →</span>
            </div>
            <div style={{ fontSize: 12, color: "#414956", lineHeight: 1.5 }}>{c.desc}</div>
            <div className="flex" style={{ gap: 22 }}>
              {c.stats.map((s, i) => (
                <div key={i}>
                  <div className="font-mono" style={{ fontSize: 18, fontWeight: 500, color: s.color }}>{s.value}</div>
                  <div style={{ fontSize: 10.5, color: "#6a7280", marginTop: 1 }}>{s.label}</div>
                </div>
              ))}
            </div>
          </button>
        ))}
      </div>
    </>
  );
}
