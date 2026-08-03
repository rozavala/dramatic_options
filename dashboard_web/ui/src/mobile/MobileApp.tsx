import { useState } from "react";

import { Curation } from "../components/Curation";
import { Reach } from "../components/Reach";
import { Sparkline } from "../components/Sparkline";
import { Banner, Chip, Skeleton } from "../components/primitives";
import { STATE_PRESENT, clusterLevel, directionLabel, isAccruingState, markLevel, relativeAge } from "../data/status";
import type { ConsoleProps, ViewModel } from "../data/types";
import { useCountUp } from "../data/useCountUp";
import { TITLES, type SectionId } from "../nav";
import { color, signal, type Level } from "../theme/tokens";

const CARD = "bg-white rounded-2xl";
const cardStyle = { border: "1px solid #e3e6ec", boxShadow: "0 1px 2px rgba(20,27,40,.05)" } as const;
const TAB_ICON: Record<SectionId, string> = {
  overview: "M4 5h6v6H4zM14 5h6v6h-6zM4 15h6v6H4zM14 15h6v6h-6z",
  safety: "M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z",
  edge: "M4 19V11M9 19V5M14 19v-6M19 19V8",
  pipeline: "M4 5h16l-6 8v5l-4 2v-7z",
  book: "M5 6h14M5 12h14M5 18h9",
  reach: "M6 4h9l3 3v13H6zM9 10h6M9 14h6",
  curation: "M5 5h14v14H5zM12 9v6M9 12h6",
};
const dirLabel = directionLabel; // A6 — single source in status.ts

// ── Overview ──────────────────────────────────────────────────────────────────────────────────
function MOverview({ vm }: { vm: ViewModel }) {
  const sig = signal[vm.level];
  const r = vm.readiness;
  const allPass = r.checkable > 0 && r.pass === r.checkable; // guard vacuous 0/0 (parity with KpiRow)
  const passN = useCountUp(r.pass); // F2 parity — count up the ring number
  const ringColor = allPass ? signal.ok.text : color.accent;
  const kpis: { label: string; value: string; color: string; sub: string; chip: string; level: Level }[] = [
    { label: "Go-live", value: `${r.pass}/${r.checkable}`, color: color.ink, sub: `${r.accruing} accruing`, chip: allPass ? "on track" : "in progress", level: allPass ? "ok" : "acc" },
    { label: "Safety", value: vm.bookDD, color: signal.ok.text, sub: `${vm.openN}/${vm.maxN} open`, chip: "safe", level: "ok" },
    { label: "Council", value: vm.council.vlevel === "ok" ? "Healthy" : "Degraded", color: signal[vm.council.vlevel].text, sub: `#${vm.council.runId ?? "—"}`, chip: vm.council.vlevel === "ok" ? "clean" : "check", level: vm.council.vlevel },
    { label: "Edge", value: `${vm.edgeAccrual.n}/~${vm.edgeAccrual.target}`, color: color.ink, sub: "resolved bets", chip: "accruing", level: "mute" },
  ];
  return (
    <>
      <div style={{ background: sig.bg, border: `1px solid ${sig.border}`, borderLeft: `5px solid ${sig.text}`, borderRadius: 14, padding: 14 }}>
        <div className="flex items-center" style={{ gap: 10 }}>
          <span style={{ width: 11, height: 11, borderRadius: "50%", flex: "none", background: sig.text, boxShadow: `0 0 0 3px ${sig.bg}` }} />
          <div style={{ fontSize: 15, fontWeight: 600, color: sig.text }}>{vm.headline}</div>
        </div>
        <div style={{ fontSize: 12, color: "#33373f", marginTop: 6, lineHeight: 1.5 }}>{vm.sub}</div>
      </div>
      <div className="grid grid-cols-2" style={{ gap: 10 }}>
        {kpis.map((k) => (
          <div key={k.label} className={CARD} style={{ ...cardStyle, padding: "12px 13px" }}>
            <div className="flex items-center justify-between" style={{ gap: 6 }}>
              <span style={{ fontSize: 10.5, color: "#5f6675" }}>{k.label}</span>
              <Chip level={k.level} style={{ fontSize: 9, padding: "2px 7px" }}>{k.chip}</Chip>
            </div>
            <div className="font-mono" style={{ fontSize: 20, fontWeight: 700, color: k.color, marginTop: 8, letterSpacing: "-.3px" }}>{k.value}</div>
            <div style={{ fontSize: 10, color: "#5f6675", marginTop: 2, lineHeight: 1.35 }}>{k.sub}</div>
          </div>
        ))}
      </div>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div className="flex items-center" style={{ gap: 13, paddingBottom: 12, borderBottom: "1px solid #edf0f4" }}>
          <div className="flex flex-col items-center justify-center" style={{ width: 56, height: 56, borderRadius: "50%", border: `3px solid ${ringColor}`, flex: "none" }}>
            <span className="font-mono" style={{ fontSize: 18, fontWeight: 700, color: ringColor, lineHeight: 1 }}>{passN}/{r.checkable}</span>
            <span style={{ fontSize: 7.5, color: "#5f6675", textTransform: "uppercase", letterSpacing: ".4px", marginTop: 1 }}>gates</span>
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#141b28" }}>Road to go-live</div>
            <div style={{ fontSize: 11, color: "#5f6675", marginTop: 2, lineHeight: 1.4 }}>{r.accruing} more accruing · the operator’s real-money checklist</div>
          </div>
        </div>
        {vm.t4.map((c) => {
          const [lvl, icon, tag] = STATE_PRESENT[c.state];
          const s = signal[lvl];
          return (
            <div key={c.id} className="flex items-center" style={{ gap: 10, padding: "9px 0", borderBottom: "1px solid #f3f5f8" }}>
              <span className="flex items-center justify-center" style={{ width: 23, height: 23, borderRadius: 7, flex: "none", fontSize: 11, fontWeight: 700, color: s.text, background: s.bg, border: `1px solid ${s.border}`, animation: isAccruingState(c.state) ? "accruePulse 2.4s ease-in-out infinite" : undefined }}>{icon}</span>
              <span style={{ flex: 1, fontSize: 11.5, fontWeight: 500, color: "#2c3645", lineHeight: 1.3 }}>{c.name}</span>
              <Chip level={lvl} style={{ fontSize: 9, padding: "2px 7px" }}>{tag}</Chip>
            </div>
          );
        })}
      </div>
    </>
  );
}

// ── Safety ────────────────────────────────────────────────────────────────────────────────────
function MSafety({ vm }: { vm: ViewModel }) {
  const c = vm.council;
  const sig = signal[c.vlevel];
  const tiles: { label: string; value: string; color: string; sub: string; series?: { equity: number }[] }[] = [
    { label: "Paper equity", value: vm.equity, color: color.ink, sub: vm.deltaFrame, series: vm.equitySeries },
    { label: "Drawdown", value: vm.bookDD, color: signal[vm.bookDDlevel].text, sub: "halt at 20%" },
    { label: "Positions", value: `${vm.openN}/${vm.maxN}`, color: color.ink, sub: `${vm.openPrem} at risk` },
    { label: "Headroom", value: vm.headroom, color: signal.ok.text, sub: `of ${vm.bookBudget}` },
  ];
  const rows = [
    { label: "Full round-trips", value: `${c.roundtrips}` },
    { label: "Parse-fails", value: `${c.parseFail}/${c.parseCalled}` },
    { label: "Run streak", value: c.streak },
    { label: "Cost", value: c.cost },
  ];
  const dr = vm.dualread;
  const rt = vm.dualreadRuntime;
  const dualTw = [
    { label: "Δ iv/rv wire", tripped: dr.deltaTripped },
    { label: "material flips", tripped: dr.flipTripped },
    { label: "coverage gaps", tripped: dr.gapTripped },
  ];
  return (
    <>
      <div className="grid grid-cols-2" style={{ gap: 10 }}>
        {tiles.map((t) => (
          <div key={t.label} className={CARD} style={{ ...cardStyle, padding: "12px 13px" }}>
            <div style={{ fontSize: 10.5, color: "#5f6675" }}>{t.label}</div>
            <div className="font-mono" style={{ fontSize: 19, fontWeight: 700, color: t.color, marginTop: 6, letterSpacing: "-.3px" }}>{t.value}</div>
            <div style={{ fontSize: 9.5, color: "#5f6675", marginTop: 2, lineHeight: 1.3 }}>{t.sub}</div>
            {t.series && <Sparkline series={t.series} height={24} />}
          </div>
        ))}
      </div>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28" }}>Cluster exposure</div>
        <div style={{ fontSize: 11, color: "#5f6675", margin: "3px 0 13px", lineHeight: 1.4 }}>Each correlated theme capped at ~2% of the account.</div>
        {vm.clusters.map((cl) => {
          const frac = cl.cap ? cl.premium / cl.cap : 0;
          const lv = signal[clusterLevel(frac)];
          return (
            <div key={cl.name} style={{ marginBottom: 11 }}>
              <div className="flex justify-between items-baseline" style={{ marginBottom: 4 }}>
                <span className="font-mono" style={{ fontSize: 11, color: "#33373f" }}>{cl.name}</span>
                <span className="font-mono" style={{ fontSize: 10.5, color: lv.text, fontWeight: 600 }}>{Math.round(frac * 100)}%</span>
              </div>
              <div style={{ height: 7, background: "#edf0f4", borderRadius: 4, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${Math.max(2, frac * 100)}%`, background: lv.text, borderRadius: 4 }} />
              </div>
            </div>
          );
        })}
      </div>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28" }}>AI council health</div>
        <div className="flex items-center" style={{ gap: 10, margin: "11px 0", padding: 11, borderRadius: 11, background: sig.bg, border: `1px solid ${sig.border}` }}>
          <span style={{ fontSize: 17 }}>{c.vlevel === "ok" ? "✓" : "⚠"}</span>
          <div>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: sig.text }}>{c.verdict}</div>
            <div style={{ fontSize: 10.5, color: "#5f6675" }}>run #{c.runId ?? "—"} · {c.models}</div>
          </div>
        </div>
        {rows.map((r) => (
          <div key={r.label} className="flex justify-between items-baseline" style={{ gap: 12, padding: "6px 0", borderTop: "1px solid #edf0f4" }}>
            <span style={{ fontSize: 11.5, color: "#5f6675" }}>{r.label}</span>
            <span className="font-mono" style={{ fontSize: 11.5, fontWeight: 500, color: "#2c3645" }}>{r.value}</span>
          </div>
        ))}
      </div>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28" }}>OPRA dual-read <span style={{ fontWeight: 400, color: "#5f6675" }}>· §5 soak</span></div>
        {dualTw.map((t) => (
          <div key={t.label} className="flex justify-between items-center" style={{ gap: 10, padding: "7px 0", borderTop: "1px solid #edf0f4", marginTop: 2 }}>
            <span style={{ fontSize: 11.5, color: "#33373f" }}>{t.label}</span>
            <Chip level={t.tripped ? "bad" : "ok"} style={{ fontSize: 9, padding: "2px 7px" }}>{t.tripped ? "⚠ TRIPPED" : "clear"}</Chip>
          </div>
        ))}
        <div className="flex justify-between items-center" style={{ gap: 10, padding: "7px 0", borderTop: "1px solid #edf0f4", marginTop: 2 }}>
          <span style={{ fontSize: 11.5, color: "#33373f" }}>revert latch (#72)</span>
          <Chip level={rt.latched ? "bad" : "ok"} style={{ fontSize: 9, padding: "2px 7px" }}>
            {rt.latched ? "LATCHED" : `Phase 3 ${rt.phase3 ? "ON" : "OFF"}`}
          </Chip>
        </div>
        <div style={{ fontSize: 10, color: "#5f6675", marginTop: 9 }}>cumulative LLM cost {vm.cost.cumulative}</div>
      </div>
    </>
  );
}

// ── Edge ──────────────────────────────────────────────────────────────────────────────────────
function MEdge({ vm }: { vm: ViewModel }) {
  const books: { name: string; tag: string; n: number; p95: number | null; level: Level }[] = [
    { name: "Real", tag: "gate + council on", ...vm.perf.real, level: "acc" },
    { name: "Shadow", tag: "no council", ...vm.perf.shadow, level: "mute" },
    { name: "3A", tag: "no gate", ...vm.perf.a3, level: "mute" },
    { name: "3B", tag: "whole basket", ...vm.perf.basket, level: "mute" },
  ];
  const maxP95 = Math.max(1, ...books.map((b) => b.p95 ?? 0));
  const anyResolved = books.some((b) => b.p95 != null);
  const outcomes = [
    { label: "Premium paid", sub: "max at risk", value: vm.perf.paid, color: color.ink },
    { label: "Premium bled", sub: "decayed so far", value: vm.perf.bledPct != null ? `${vm.perf.bledPct}%` : "—", color: vm.perf.bledPct != null ? signal.warn.text : signal.mute.text },
    { label: "Hit rate", sub: vm.perf.closed ? `${vm.perf.hits}/${vm.perf.closed} closed` : "no closed bets", value: vm.perf.hitRate != null ? `${vm.perf.hitRate}%` : "—", color: vm.perf.hitRate != null ? "#2c3645" : signal.mute.text },
  ];
  const brierRows = vm.brier.roles.length ? vm.brier.roles : [{ label: "strategist", value: vm.brier.strategist }];
  return (
    <>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28" }}>Does the machine beat "brain-off"?</div>
        <div style={{ fontSize: 11, color: "#5f6675", margin: "3px 0 12px", lineHeight: 1.4 }}>Tail multiple (p95) per book — the real book should out-tail the rest.</div>
        {books.map((b) => {
          const has = b.p95 != null;
          const w = has ? Math.max(5, ((b.p95 as number) / maxP95) * 100) : 0;
          const lv = signal[b.level];
          return (
            <div key={b.name} className="flex items-center" style={{ gap: 10, padding: "8px 0", borderTop: "1px solid #edf0f4" }}>
              <div style={{ width: 96, flex: "none" }}>
                <div style={{ fontSize: 11.5, fontWeight: 600, color: "#26292f" }}>{b.name}</div>
                <div style={{ fontSize: 9, color: "#5f6675" }}>{b.tag}</div>
              </div>
              <div style={{ flex: 1, height: 20, background: "#edf0f4", borderRadius: 6, position: "relative", overflow: "hidden" }}>
                {has ? (
                  <div style={{ position: "absolute", left: 0, top: 0, height: "100%", width: `${w}%`, background: lv.bg, borderRight: `2px solid ${lv.text}`, borderRadius: 6 }} />
                ) : (
                  <div style={{ position: "absolute", inset: 0, background: "repeating-linear-gradient(135deg,#edf0f4,#edf0f4 7px,#e7eaef 7px,#e7eaef 14px)", borderRadius: 6, animation: "accruePulse 2.6s ease-in-out infinite" }} />
                )}
              </div>
              <div className="font-mono text-right" style={{ width: 48, flex: "none", fontSize: 12, fontWeight: 700, color: has ? lv.text : signal.mute.text }}>{has ? `${(b.p95 as number).toFixed(2)}×` : "—"}</div>
            </div>
          );
        })}
        <div style={{ fontSize: 10, color: "#5f6675", marginTop: 11, lineHeight: 1.4, fontStyle: "italic" }}>
          {anyResolved ? "Early — pointing the right way as bets resolve." : "All accruing — no bets resolved yet (~6mo). Expected, not a failure."}
        </div>
      </div>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28", marginBottom: 10 }}>Premium &amp; outcomes</div>
        {outcomes.map((o) => (
          <div key={o.label} className="flex justify-between items-center" style={{ padding: "8px 0", borderTop: "1px solid #edf0f4" }}>
            <div>
              <div style={{ fontSize: 12, color: "#33373f" }}>{o.label}</div>
              <div style={{ fontSize: 10, color: "#5f6675" }}>{o.sub}</div>
            </div>
            <span className="font-mono" style={{ fontSize: 15, fontWeight: 700, color: o.color }}>{o.value}</span>
          </div>
        ))}
      </div>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28" }}>Conviction calibration <span style={{ fontWeight: 400, color: "#5f6675" }}>· Brier, lower is better</span></div>
        {brierRows.map((r) => (
          <div key={r.label} className="flex justify-between items-center" style={{ padding: "8px 0", borderTop: "1px solid #edf0f4", marginTop: 2 }}>
            <span style={{ fontSize: 12, color: "#33373f" }}>{r.label}</span>
            <span className="font-mono" style={{ fontSize: 13, fontWeight: 700, color: r.value != null ? signal.ok.text : signal.mute.text }}>{r.value != null ? r.value.toFixed(3) : "accruing"}</span>
          </div>
        ))}
      </div>
      {vm.nulls.length > 0 && (
        <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28" }}>Null hierarchy <span style={{ fontWeight: 400, color: "#5f6675" }}>· clean vs bundled</span></div>
          {vm.nulls.map((step) => (
            <div key={step.name} style={{ padding: "8px 0", borderTop: "1px solid #edf0f4", marginTop: 2 }}>
              <div className="flex items-center justify-between" style={{ gap: 8 }}>
                <span style={{ fontSize: 11.5, fontWeight: 600, color: "#33373f" }}>{step.name}</span>
                <Chip level={step.clean ? "acc" : "mute"} style={{ fontSize: 9, padding: "2px 7px" }}>{step.clean ? "clean" : "bundled"}</Chip>
              </div>
              <div className="font-mono" style={{ fontSize: 10.5, color: "#5f6675", marginTop: 3 }}>
                {step.arms.map((a) => `${a.label} ${a.ci.p95 != null ? `${a.ci.p95.toFixed(2)}×` : "—"}`).join("  ·  ")}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

// ── Pipeline ──────────────────────────────────────────────────────────────────────────────────
function MPipeline({ vm }: { vm: ViewModel }) {
  const f = vm.funnel;
  const steps: { label: string; value: string | number; sub: string; level: Level }[] = [
    { label: "Proposed", value: f.proposed, sub: "by the AI council", level: "acc" },
    { label: "Evaluated", value: f.evaluated, sub: "reached the gate", level: "acc" },
    { label: "Opened", value: f.opened, sub: "cleared everything", level: f.opened > 0 ? "ok" : "mute" },
  ];
  const cmax = f.council.asserted + f.council.ungrounded + f.council.abstained || 1;
  const debate: { label: string; value: number; level: Level }[] = [
    { label: "Asserted (full debate)", value: f.council.asserted, level: "ok" },
    { label: "Reached the gate", value: f.council.toGate, level: "acc" },
    { label: "Dropped — ungrounded", value: f.council.ungrounded, level: "mute" },
    { label: "Dropped — abstained", value: f.council.abstained, level: "mute" },
  ];
  const gate = [
    { label: "IV-gate vetoes", sub: "too rich or missing", value: f.gate.ivTotal, color: color.ink2 },
    { label: "Real veto", sub: "genuinely rich", value: f.gate.ivReal, color: color.accent },
    { label: "Fail-closed", sub: "missing input", value: f.gate.ivFail, color: f.gate.ivFail ? signal.warn.text : signal.ok.text },
    { label: "Eligibility", sub: "liquidity floor", value: f.gate.elig, color: color.ink2 },
  ];
  return (
    <>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28" }}>Latest cycle <span style={{ fontWeight: 400, color: "#5f6675" }}>· run #{f.runId ?? "—"}</span></div>
        <div style={{ fontSize: 11, color: "#5f6675", margin: "3px 0 13px", lineHeight: 1.4 }}>Where candidate ideas stop. Zero opened is healthy if nothing was cheap.</div>
        {steps.map((s) => (
          <div key={s.label} className="flex items-center" style={{ gap: 12, padding: "8px 0", borderTop: "1px solid #edf0f4" }}>
            <span className="font-mono" style={{ fontSize: 18, fontWeight: 700, color: signal[s.level].text, width: 34, flex: "none" }}>{s.value}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: "#33373f" }}>{s.label}</div>
              <div style={{ fontSize: 10, color: "#5f6675" }}>{s.sub}</div>
            </div>
          </div>
        ))}
        <div style={{ marginTop: 9, paddingTop: 9, borderTop: "1px solid #edf0f4", fontSize: 10.5, color: "#5f6675", lineHeight: 1.6 }}>
          Wasted LLM calls <span className="font-mono" style={{ fontWeight: 600 }}>{f.wasted}</span> · cluster-cap rejected <span className="font-mono" style={{ fontWeight: 600 }}>{vm.capFlow.rejected}</span>
        </div>
      </div>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28", marginBottom: 9 }}>Inside the AI debate</div>
        {debate.map((r) => (
          <div key={r.label} className="flex items-center" style={{ gap: 10, padding: "7px 0", borderTop: "1px solid #edf0f4" }}>
            <span style={{ flex: 1, fontSize: 11.5, color: "#33373f" }}>{r.label}</span>
            <div style={{ width: 60, height: 6, background: "#edf0f4", borderRadius: 3, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${Math.max(3, (r.value / cmax) * 100)}%`, background: signal[r.level].text, borderRadius: 3 }} />
            </div>
            <span className="font-mono text-right" style={{ fontSize: 12, fontWeight: 700, color: signal[r.level].text, width: 20 }}>{r.value}</span>
          </div>
        ))}
      </div>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28", marginBottom: 9 }}>The cheapness gate</div>
        {gate.map((r) => (
          <div key={r.label} className="flex justify-between items-center" style={{ padding: "8px 0", borderTop: "1px solid #edf0f4" }}>
            <div>
              <div style={{ fontSize: 12, color: "#33373f" }}>{r.label}</div>
              <div style={{ fontSize: 10, color: "#5f6675" }}>{r.sub}</div>
            </div>
            <span className="font-mono" style={{ fontSize: 14, fontWeight: 700, color: r.color }}>{r.value}</span>
          </div>
        ))}
      </div>
      {vm.deliberation.rows.length > 0 && (
        <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28" }}>Latest decisions <span style={{ fontWeight: 400, color: "#5f6675" }}>· #{vm.deliberation.runId}</span></div>
          {vm.deliberation.rows.map((d, i) => (
            <div key={i} className="flex justify-between items-center" style={{ gap: 10, padding: "7px 0", borderTop: "1px solid #edf0f4", marginTop: 2 }}>
              <span className="font-mono" style={{ fontSize: 12, fontWeight: 600, color: "#141b28" }}>{d.symbol} <span style={{ fontWeight: 400, color: "#5f6675" }}>{d.dir ?? ""}</span></span>
              <span style={{ fontSize: 11, color: "#5f6675" }}>{d.adversary ?? "—"} → <span style={{ fontWeight: 600, color: "#33373f" }}>{d.conviction ?? "—"}</span></span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

// ── Book ──────────────────────────────────────────────────────────────────────────────────────
function MBook({ vm }: { vm: ViewModel }) {
  const has = vm.positions.length > 0;
  return (
    <>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div className="flex justify-between items-baseline" style={{ marginBottom: 4 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28" }}>Open positions</div>
          <span className="font-mono" style={{ fontSize: 10.5, color: "#5f6675" }}>{vm.openCount} · {vm.openPrem2}</span>
        </div>
        {has ? (
          vm.positions.map((p, i) => {
            const lv = p.mark != null ? signal[markLevel(p.mark)] : signal.mute;
            return (
              <div key={i} className="flex items-center" style={{ gap: 10, padding: "10px 0", borderTop: "1px solid #edf0f4" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="font-mono" style={{ fontSize: 13, fontWeight: 700, color: "#141b28" }}>{p.symbol} <span style={{ fontSize: 9, fontFamily: "Roboto", color: p.dir === "bearish" ? signal.bad.text : signal.ok.text }}>{dirLabel(p.dir)}</span></div>
                  <div style={{ fontSize: 10, color: "#5f6675" }}>{[p.theme, p.conviction, p.dte != null ? `${p.dte}d` : null].filter(Boolean).join(" · ")}</div>
                </div>
                <div className="text-right font-mono">
                  <div style={{ fontSize: 13, fontWeight: 700, color: lv.text }}>{p.mark != null ? `${p.mark.toFixed(1)}×` : "—"}</div>
                  <div style={{ fontSize: 10, color: "#5f6675" }}>{p.premium}</div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="flex items-center" style={{ gap: 11, padding: 16, marginTop: 8, border: "1px dashed #c4c7c5", borderRadius: 12, background: "#f6f8fa" }}>
            <span style={{ fontSize: 19, animation: "accruePulse 2.4s ease-in-out infinite" }}>◷</span>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#33373f" }}>No open positions — by design</div>
              <div style={{ fontSize: 10.5, color: "#5f6675", marginTop: 2, lineHeight: 1.35 }}>The book stays empty until a genuinely cheap idea clears the gate.</div>
            </div>
          </div>
        )}
      </div>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28" }}>Active sentinels <span style={{ fontWeight: 400, color: "#5f6675" }}>· {vm.sentinelSub}</span></div>
        {vm.sentinels.map((s, i) => (
          <div key={i} className="flex justify-between items-center" style={{ padding: "8px 0", borderTop: "1px solid #edf0f4", marginTop: 2 }}>
            <span className="font-mono" style={{ fontSize: 12, color: "#33373f" }}>{s.symbol} <span style={{ fontSize: 10, color: "#5f6675" }}>{s.basket ?? ""}</span></span>
            <span style={{ fontSize: 10.5, color: "#5f6675" }}>{s.note}</span>
          </div>
        ))}
      </div>
      <div className={CARD} style={{ ...cardStyle, padding: 15 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#141b28", marginBottom: 6 }}>Data accruing</div>
        {vm.data.map((d) => (
          <div key={d.label} className="flex justify-between items-center" style={{ padding: "8px 0", borderTop: "1px solid #edf0f4" }}>
            <span style={{ fontSize: 12, color: "#33373f" }}>{d.label}</span>
            <span className="font-mono" style={{ fontSize: 14, fontWeight: 700, color: "#141b28" }}>{d.value}</span>
          </div>
        ))}
      </div>
    </>
  );
}

const NAV_IDS: SectionId[] = ["overview", "safety", "edge", "pipeline", "book", "reach", "curation"];
const TAB_LABEL: Record<SectionId, string> = { overview: "Overview", safety: "Safety", edge: "Edge", pipeline: "Pipeline", book: "Book", reach: "Reach", curation: "Curate" };

export function MobileApp({ vm, loading, error, fatal, refresh }: ConsoleProps) {
  const [tab, setTab] = useState<SectionId>("overview");
  const [title, subtitle] = TITLES[tab];
  const age = relativeAge(vm?.asOf); // E2

  return (
    <div className="flex flex-col" style={{ height: "100dvh", background: "#f4f6f8", overflow: "hidden" }}>
      {/* header */}
      <div style={{ flex: "none", background: color.navy900, padding: "calc(env(safe-area-inset-top, 0px) + 14px) 18px 13px" }}>
        <div className="flex items-center justify-between" style={{ gap: 10 }}>
          <div className="flex items-center" style={{ gap: 9, minWidth: 0 }}>
            <div className="flex items-center justify-center font-mono" style={{ width: 26, height: 26, borderRadius: 7, flex: "none", background: color.accent, fontWeight: 700, fontSize: 14, color: "#fff" }}>◭</div>
            <div style={{ minWidth: 0 }}>
              <div style={{ color: "#fff", fontSize: 15, fontWeight: 600, letterSpacing: "-.2px" }}>{title}</div>
              <div className="font-mono" style={{ color: "#8a98b0", fontSize: 10 }}>{subtitle}</div>
            </div>
          </div>
          <div className="flex items-center" style={{ gap: 9, flex: "none" }}>
            {age.label && (
              <span className="font-mono" style={{ fontSize: 9.5, color: signal[age.level].text === "#0b8a3e" ? "#8a98b0" : signal[age.level].text }}>{age.label}</span>
            )}
            <button onClick={() => refresh()} disabled={loading} aria-label="Refresh snapshot" className="flex items-center justify-center" style={{ flex: "none", width: 32, height: 32, borderRadius: 8, background: "rgba(255,255,255,.08)", border: "1px solid #2a3c5e", color: "#aeb8cc", fontSize: 14, cursor: loading ? "default" : "pointer", opacity: loading ? 0.55 : 1, animation: loading ? "spin .7s linear infinite" : undefined }}>↻</button>
          </div>
        </div>
      </div>
      {loading && <div style={{ height: 3, flex: "none", background: "#dbe7ff", overflow: "hidden" }}><div style={{ height: "100%", width: "35%", background: color.accent, animation: "indet 1.1s ease-in-out infinite" }} /></div>}

      {/* content */}
      <div className="flex-1 overflow-y-auto" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 11 }}>
        {fatal && (
          <div className={CARD} style={{ ...cardStyle, padding: 22, textAlign: "center" }}>
            <div style={{ fontSize: 26, marginBottom: 6 }}>⚠</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#d12d1c", marginBottom: 6 }}>Snapshot unavailable</div>
            <div className="font-mono" style={{ fontSize: 11, color: "#5f6675", lineHeight: 1.6, wordBreak: "break-word" }}>{fatal}</div>
          </div>
        )}
        {error && !fatal && <div className={CARD} style={{ ...cardStyle, padding: 16, color: "#d12d1c" }}>Couldn’t load the snapshot: {error}.</div>}
        {vm?.schemaWarning && <Banner level="warn">⚠ {vm.schemaWarning}</Banner>}
        {vm && vm.degraded.length > 0 && (
          <Banner level="bad">{vm.degraded.length} panel{vm.degraded.length > 1 ? "s" : ""} unavailable (fail-soft): {vm.degraded.join(", ")}. Blank/zero here = a crash, not “accruing”.</Banner>
        )}
        {vm && tab === "overview" && <MOverview vm={vm} />}
        {vm && tab === "safety" && <MSafety vm={vm} />}
        {vm && tab === "edge" && <MEdge vm={vm} />}
        {vm && tab === "pipeline" && <MPipeline vm={vm} />}
        {vm && tab === "book" && <MBook vm={vm} />}
        {tab === "reach" && <Reach />}
        {tab === "curation" && <Curation />}
        {!vm && !error && !fatal && loading && tab !== "curation" && tab !== "reach" && (
          <>
            <Skeleton height={84} /><Skeleton height={150} /><Skeleton height={150} />
          </>
        )}
        <div style={{ height: 6, flex: "none" }} />
      </div>

      {/* bottom tab bar */}
      <div role="tablist" aria-label="Sections" className="flex" style={{ flex: "none", background: color.navy900, borderTop: `1px solid ${color.navy700}`, padding: "9px 6px calc(env(safe-area-inset-bottom, 0px) + 14px)" }}>
        {NAV_IDS.map((id) => {
          const active = id === tab;
          const c = active ? color.accent : "#7d8aa3";
          return (
            <button key={id} role="tab" aria-selected={active} aria-label={TAB_LABEL[id]} onClick={() => setTab(id)} className="flex flex-col items-center" style={{ flex: 1, background: "none", border: "none", cursor: "pointer", gap: 4, padding: "3px 0" }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={TAB_ICON[id]} /></svg>
              <span style={{ fontSize: 9, fontWeight: 500, color: c, letterSpacing: ".1px" }}>{TAB_LABEL[id]}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
