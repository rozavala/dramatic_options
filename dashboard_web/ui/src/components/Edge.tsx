import type { ViewModel } from "../data/types";
import { color, signal } from "../theme/tokens";
import { Card, Chip } from "./primitives";

const LIFECYCLE_DAYS = 250; // the option lifecycle (~250d) — the first resolutions land this long after the first entry
const Muted = ({ children }: { children: React.ReactNode }) => <span style={{ color: "#6a7280", fontWeight: 400 }}>{children}</span>;
const Row = ({ label, value }: { label: React.ReactNode; value: React.ReactNode }) => (
  <div className="flex justify-between items-center" style={{ gap: 14, padding: "9px 0", borderTop: "1px solid #edf0f4" }}>
    <span style={{ fontSize: 12.5, color: "#2c3645" }}>{label}</span>
    <span className="font-mono text-right" style={{ fontSize: 13, fontWeight: 500, color: "#2c3645" }}>{value}</span>
  </div>
);

function addDays(iso: string, d: number): string {
  const t = new Date(iso + "T00:00:00Z");
  t.setUTCDate(t.getUTCDate() + d);
  return t.toISOString().slice(0, 7);
}

export function Edge({ vm }: { vm: ViewModel }) {
  const books = [
    { name: "Real", tag: "gate on · council on — the actual book", ...vm.perf.real, open: vm.booksOpen.real, level: "acc" as const },
    { name: "Shadow", tag: "gate on · council off — isolates the council", ...vm.perf.shadow, open: vm.booksOpen.shadow, level: "mute" as const },
    { name: "3A · no-gate", tag: "gate off · same names — isolates the gate", ...vm.perf.a3, open: vm.booksOpen.a3, level: "mute" as const },
    { name: "3B · whole basket", tag: "gate off · everything — beat-the-basket", ...vm.perf.basket, open: vm.booksOpen.basket, level: "mute" as const },
  ];
  const maxP95 = Math.max(1, ...books.map((b) => b.p95 ?? 0));
  const anyResolved = books.some((b) => b.p95 != null);
  const first = vm.firstEntry;
  const dayN = first ? Math.max(0, Math.round((Date.now() - Date.parse(first + "T00:00:00Z")) / 86_400_000)) : null;
  const progress = dayN != null ? Math.min(1, dayN / LIFECYCLE_DAYS) : 0;
  const firstRes = first ? addDays(first, LIFECYCLE_DAYS) : null;
  const n = vm.edgeAccrual.n;
  return (
    <div className="flex flex-col" style={{ gap: 16 }}>
      <Card style={{ padding: "22px 24px" }}>
        <div className="flex items-baseline justify-between" style={{ gap: 12 }}>
          <div style={{ fontSize: 16, fontWeight: 500, color: "#141b28" }}>
            {anyResolved ? "Early reads — not yet significant" : "Nothing has resolved yet — and that is on schedule"}
          </div>
          <Chip level={anyResolved ? "acc" : "mute"}>{anyResolved ? `${n} of ~${vm.edgeAccrual.target} resolved` : `accruing · ${n} of ~${vm.edgeAccrual.target} resolved`}</Chip>
        </div>
        <div style={{ fontSize: 12, color: "#414956", marginTop: 4, lineHeight: 1.5, maxWidth: 760 }}>
          Each bet runs ~{LIFECYCLE_DAYS} days.{first ? <> The first real entry was <b>{first}</b>, so the first resolved outcomes land around <b>{firstRes}</b>;</> : " No real entry yet, so the clock has not started;"} the first null read needs ~{vm.edgeAccrual.target} of them.
          Until then every tail, CI and Brier score on this page is genuinely empty — never a zero.
        </div>
        {first && (
          <div style={{ marginTop: 20, position: "relative", height: 54 }}>
            <div style={{ position: "absolute", left: 0, right: 0, top: 22, height: 6, background: "#edf0f4", borderRadius: 3 }} />
            <div style={{ position: "absolute", left: 0, width: `${progress * 100}%`, top: 22, height: 6, background: color.accent, borderRadius: 3 }} />
            <div style={{ position: "absolute", left: 0, top: 16, width: 2, height: 18, background: color.accent }} />
            <div style={{ position: "absolute", left: `${progress * 100}%`, top: 14, width: 12, height: 12, marginLeft: -6, borderRadius: "50%", background: color.accent, border: "2px solid #ffffff", boxShadow: `0 0 0 1px ${color.accent}` }} />
            <div style={{ position: "absolute", right: 0, top: 16, width: 2, height: 18, background: "#6a7280" }} />
            <div className="font-mono" style={{ position: "absolute", left: 0, top: 38, fontSize: 10.5, color: "#414956" }}>{first} · first entry</div>
            <div className="font-mono" style={{ position: "absolute", left: `${Math.min(88, progress * 100)}%`, top: 0, marginLeft: -6, fontSize: 10.5, color: color.accent, fontWeight: 500 }}>today · day {dayN}</div>
            <div className="font-mono" style={{ position: "absolute", right: 0, top: 38, fontSize: 10.5, color: "#414956", textAlign: "right" }}>~{firstRes} · first resolutions</div>
          </div>
        )}
      </Card>

      <Card style={{ padding: "20px 22px" }}>
        <div className="flex items-baseline justify-between" style={{ gap: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Does the machine beat brain-off? <Muted>· p95 tail multiple per book</Muted></div>
          <span style={{ fontSize: 11.5, color: "#6a7280" }}>higher = fatter winners · the real book should out-tail the controls</span>
        </div>
        <div style={{ marginTop: 12 }}>
          {books.map((b) => {
            const has = b.p95 != null;
            const w = has ? Math.max(4, ((b.p95 as number) / maxP95) * 100) : 0;
            const lv = signal[b.level];
            return (
              <div key={b.name} className="flex items-center" style={{ gap: 14, padding: "11px 0", borderTop: "1px solid #edf0f4" }}>
                <div style={{ width: 170, flex: "none" }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "#141b28" }}>{b.name}</div>
                  <div style={{ fontSize: 11, color: "#6a7280" }}>{b.tag}</div>
                </div>
                <div style={{ flex: 1, height: 22, background: "#edf0f4", borderRadius: 6, position: "relative", overflow: "hidden" }}>
                  {has ? (
                    <div style={{ position: "absolute", left: 0, top: 0, height: "100%", width: `${w}%`, background: lv.bg, borderRight: `2px solid ${lv.text}`, borderRadius: 6 }} />
                  ) : (
                    <div style={{ position: "absolute", inset: 0, background: "repeating-linear-gradient(135deg,#edf0f4,#edf0f4 7px,#e7eaef 7px,#e7eaef 14px)", borderRadius: 6 }} />
                  )}
                </div>
                <div className="font-mono text-right" style={{ width: 190, flex: "none", fontSize: 12.5, color: "#4b5667" }}>
                  {has ? <span style={{ color: lv.text, fontWeight: 500, fontSize: 15 }}>{(b.p95 as number).toFixed(2)}×</span> : "accruing"} · <span style={{ color: "#141b28" }}>{b.open} open</span> · {b.n} resolved
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 items-start" style={{ gap: 16 }}>
        <Card style={{ padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28", marginBottom: 8 }}>Premium and outcomes so far</div>
          <Row label={<>Premium paid <Muted>the most that can be lost</Muted></>} value={<span style={{ fontSize: 15 }}>{vm.perf.paid}</span>} />
          <Row label={<>Bled so far <Muted>running, unrealized</Muted></>} value={<span style={{ fontSize: 15, color: vm.perf.bledPct != null && vm.perf.bledPct > 0 ? signal.warn.text : "#2c3645" }}>{vm.perf.bledPct != null ? `${vm.perf.bledPct}%` : "—"}</span>} />
          <Row label="Closed bets · hit rate" value={<span style={{ color: vm.perf.hitRate != null ? "#2c3645" : "#4b5667" }}>{vm.perf.closed} · {vm.perf.hitRate != null ? `${vm.perf.hitRate}%` : "accruing"}</span>} />
          <Row label={<>Council calibration <Muted>Brier, lower is better</Muted></>} value={<span style={{ color: vm.brier.strategist != null ? signal.ok.text : "#4b5667" }}>{vm.brier.strategist != null ? vm.brier.strategist.toFixed(3) : `accruing · ${vm.brier.n} resolved proposals`}</span>} />
        </Card>
        <Card style={{ padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>The null hierarchy <Muted>· which contrast is clean</Muted></div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 8 }}>Each step isolates one variable. Plumbing only — the significance verdict belongs to the blind null layer (T4 #2).</div>
          {vm.nulls.length === 0 && <div style={{ fontSize: 12.5, color: "#5f6675" }}>no contrasts plumbed yet</div>}
          {vm.nulls.map((s) => (
            <div key={s.name} className="flex justify-between items-center" style={{ gap: 12, padding: "9px 0", borderTop: "1px solid #edf0f4" }}>
              <span style={{ fontSize: 12.5, color: "#2c3645" }}>
                {s.name}
                {s.bundled && <Muted> · {s.bundled}</Muted>}
                {s.censored != null && s.censored > 0 && <Muted> · {s.censored} parse-fail run{s.censored === 1 ? "" : "s"} censored</Muted>}
              </span>
              <Chip level={s.clean ? "acc" : "mute"}>{s.clean ? "clean · 1 variable" : "bundled"}</Chip>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
