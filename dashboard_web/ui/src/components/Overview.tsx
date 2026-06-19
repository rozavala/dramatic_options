import type { ViewModel } from "../data/types";
import type { SectionId } from "../nav";
import { KpiRow } from "./KpiRow";
import { MissionStrip } from "./MissionStrip";
import { SectionCards } from "./SectionCards";
import { StatusBanner } from "./StatusBanner";
import { T4Road } from "./T4Road";
import { TwoQuestions } from "./TwoQuestions";

/** The command-center Overview: status banner → mission → KPIs → two questions → T4 road → section cards. */
export function Overview({ vm, onNavigate }: { vm: ViewModel; onNavigate: (id: SectionId) => void }) {
  return (
    <>
      <StatusBanner vm={vm} />
      <MissionStrip vm={vm} />
      <div style={{ marginTop: 14 }}>
        <KpiRow vm={vm} />
      </div>
      <TwoQuestions vm={vm} />
      <T4Road vm={vm} />
      <SectionCards vm={vm} onNavigate={onNavigate} />
    </>
  );
}
