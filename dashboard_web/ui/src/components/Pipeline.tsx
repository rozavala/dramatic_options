import { useState } from "react";

import type { ViewModel } from "../data/types";
import { signal, type Level } from "../theme/tokens";
import { CheapnessWatch } from "./CheapnessWatch";
import { Card } from "./primitives";
import { CriteriaLegs, SessionTable } from "./SessionTable";

const Muted = ({ children }: { children: React.ReactNode }) => <span style={{ color: "#6a7280", fontWeight: 400 }}>{children}</span>;
const Row = ({ label, value }: { label: React.ReactNode; value: React.ReactNode }) => (
  <div className="flex justify-between items-center" style={{ gap: 14, padding: "8px 0", borderTop: "1px solid #edf0f4" }}>
    <span style={{ fontSize: 12.5, color: "#2c3645" }}>{label}</span>
    <span className="font-mono text-right" style={{ fontSize: 12.5, fontWeight: 500, color: "#2c3645" }}>{value}</span>
  </div>
);

function Stage({ label, n, sub, level, max }: { label: string; n: number; sub: string; level: Level; max: number }) {
  const lv = signal[level];
  const h = Math.max(34, (n / max) * 120);
  return (
    <div className="flex-1" style={{ textAlign: "center" }}>
      <div className="flex items-center justify-center" style={{ height: h, borderRadius: 9, background: lv.bg, border: `1px solid ${lv.border}` }}>
        <span className="font-mono" style={{ fontSize: 24, fontWeight: 500, color: lv.text }}>{n}</span>
      </div>
      <div style={{ fontSize: 12, fontWeight: 500, color: "#2c3645", marginTop: 9 }}>{label}</div>
      <div style={{ fontSize: 11, color: "#6a7280", marginTop: 1 }}>{sub}</div>
    </div>
  );
}

/** A collapsed research instrument: title + one-line record; opens in place. Records, not decisions. */
function Instrument({ title, meta, children }: { title: string; meta: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ borderTop: "1px solid #edf0f4" }}>
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="w-full flex items-center text-left" style={{ gap: 12, padding: "11px 4px", background: "none", border: "none", cursor: "pointer" }}>
        <span aria-hidden="true" style={{ color: "#6a7280", fontSize: 11, width: 10 }}>{open ? "▾" : "▸"}</span>
        <span style={{ flex: 1, fontSize: 13, color: "#141b28", fontWeight: 500 }}>{title}</span>
        <span className="font-mono" style={{ fontSize: 11.5, color: "#6a7280" }}>{meta}</span>
      </button>
      {open && <div style={{ padding: "0 4px 14px 26px" }}>{children}</div>}
    </div>
  );
}

// PREREG_DIRECTION_COHERENCE (#264): what the union filter held back before the council, with the filed
// revenue it decided on, and the one-number wiring check (F2) — withheld names that still reached the council.
function DirCoherenceCard({ dc }: { dc: NonNullable<ViewModel["dircoherence"]> }) {
  const clean = dc.reachedDespite.length === 0;
  const list = (items: { symbol: string; facts: string | null }[]) => items.length
    ? items.map((i) => <div key={i.symbol} className="flex justify-between" style={{ gap: 12, padding: "3px 0", fontSize: 12.5 }}>
        <span className="font-mono" style={{ color: "#2c3645", fontWeight: 500 }}>{i.symbol}</span>
        <span className="font-mono" style={{ color: "#6a7280" }}>{i.facts ?? "values not on this record"}</span>
      </div>)
    : <div style={{ fontSize: 12, color: "#6a7280", padding: "3px 0" }}>none</div>;
  return (
    <Card style={{ padding: "18px 20px", borderColor: clean ? "#cbd0da" : signal.warn.border }}>
      <div className="flex justify-between items-center" style={{ gap: 12 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>
          Direction coherence <Muted>· {dc.day}{dc.runId != null ? ` · run #${dc.runId}` : ""}</Muted>
        </div>
        <span className="font-mono" style={{ fontSize: 12, fontWeight: 500, color: clean ? signal.ok.text : signal.warn.text }}>
          {clean ? "0 reached the council" : `${dc.reachedDespite.join(", ")} reached the council`}
        </span>
      </div>
      <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 10 }}>
        {dc.unavailable
          ? "No fundamentals provider this run, so nothing was withheld."
          : "A discovery candidate framed bearish is held back when its latest filed quarter shows revenue growing and accelerating. Hand-seeds and bullish framings are never touched, and missing data never withholds."}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 18 }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 500, color: "#2c3645", marginBottom: 2 }}>Withheld <Muted>· {dc.withheld.length}</Muted></div>
          {list(dc.withheld)}
        </div>
        <div>
          <div style={{ fontSize: 12, fontWeight: 500, color: "#2c3645", marginBottom: 2 }}>Examined, let through <Muted>· {dc.kept.length}</Muted></div>
          {list(dc.kept)}
          <div style={{ fontSize: 12, color: "#6a7280", marginTop: 8 }}>
            No filed acceleration, kept: {dc.noAccel.length ? dc.noAccel.join(", ") : "none"}
            {dc.errors ? <span style={{ color: signal.warn.text }}> · {dc.errors} read error{dc.errors === 1 ? "" : "s"} (kept)</span> : null}
          </div>
        </div>
      </div>
      {dc.history.length > 1 ? (
        <div style={{ fontSize: 11, color: "#6a7280", marginTop: 10 }}>
          Withheld by night: {dc.history.map((h) => `${h.day.slice(5)} ${h.withheld}`).join(" · ")}
        </div>
      ) : null}
    </Card>
  );
}

// #269 — names the council or the direction rule read on an older quarter than their latest filed report.
function StalenessCard({ st }: { st: NonNullable<ViewModel["staleness"]> }) {
  const clean = st.lagging.length === 0;
  return (
    <Card style={{ padding: "16px 20px", borderColor: clean ? "#cbd0da" : signal.warn.border }}>
      <div className="flex justify-between items-center" style={{ gap: 12 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>
          Stale fundamentals <Muted>· {st.day}{st.runId != null ? ` · run #${st.runId}` : ""}</Muted>
        </div>
        <span className="font-mono" style={{ fontSize: 12, fontWeight: 500, color: clean ? signal.ok.text : signal.warn.text }}>
          {st.unavailable ? "not checked" : clean ? `0 of ${st.checked} read stale` : `${st.lagging.length} of ${st.checked} read stale`}
        </span>
      </div>
      <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5 }}>
        {st.unavailable
          ? `Not checked this run: ${st.unavailable}.`
          : "A name is flagged when the council or the direction rule read an older quarter than the company's latest filed report — usually an SEC data gap, not a refresh problem. Telemetry only: nothing here changes a decision."}
      </div>
      {st.lagging.map((l) => (
        <div key={l.symbol} className="flex justify-between" style={{ gap: 12, padding: "6px 0 0", fontSize: 12.5 }}>
          <span className="font-mono" style={{ color: "#2c3645", fontWeight: 500 }}>{l.symbol}</span>
          <span className="font-mono" style={{ color: signal.warn.text }}>{l.line}</span>
        </div>
      ))}
      {st.errors ? <div style={{ fontSize: 11, color: signal.warn.text, marginTop: 6 }}>{st.errors} check error{st.errors === 1 ? "" : "s"} (skipped)</div> : null}
    </Card>
  );
}

export function Pipeline({ vm }: { vm: ViewModel }) {
  const f = vm.funnel;
  const se = vm.session;
  const judged = se.rows.length || f.proposed;
  const deliberated = f.council.asserted;
  const aboveFloor = f.council.aboveFloor;
  const stMax = Math.max(judged, 1);
  const abstainedStrategist = vm.council.strategistAbstained;
  const provenance = { reserve: se.rows.filter((r) => r.via === "reserve").length, fairness: se.rows.filter((r) => r.via === "fairness").length, rank: se.rows.filter((r) => r.via === "rank").length };
  const attempts = vm.attempts;
  const cat = vm.catalysts;
  const ch = vm.cheapness;
  return (
    <div className="flex flex-col" style={{ gap: 16 }}>
      <Card style={{ padding: "20px 22px" }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>
          Session {se.runId != null ? `#${se.runId}` : "—"} — where the {judged} candidates stopped
          {se.startedAt && <Muted> · {se.startedAt.slice(0, 16)} UTC</Muted>}
        </div>
        <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5 }}>Left to right; each step can drop a name. Zero opened is healthy when nothing was both grounded and genuinely cheap.</div>
        <div className="flex" style={{ alignItems: "flex-end", gap: 8, marginTop: 18 }}>
          <Stage label="Judged" n={judged} sub="the slate the council saw" level="acc" max={stMax} />
          <Stage label="Deliberated" n={deliberated} sub="proposer asserted a direction" level="acc" max={stMax} />
          <Stage label="Above floor" n={aboveFloor} sub={`strategist ≥ ${f.council.floor}`} level={aboveFloor ? "acc" : "mute"} max={stMax} />
          <Stage label="Reached the gate" n={f.council.toGate} sub="cheapness + caps" level={f.council.toGate ? "acc" : "mute"} max={stMax} />
          <Stage label="Opened" n={f.opened} sub="cleared everything" level={f.opened ? "ok" : "mute"} max={stMax} />
        </div>
        <div className="flex flex-wrap" style={{ gap: 20, marginTop: 16, paddingTop: 13, borderTop: "1px solid #edf0f4", fontSize: 11.5, color: "#414956" }}>
          <span>Proposer abstained · <span className="font-mono" style={{ fontWeight: 500 }}>{f.council.abstained}</span></span>
          <span>Strategist abstained · <span className="font-mono" style={{ fontWeight: 500 }}>{abstainedStrategist}</span></span>
          <span>Criteria-vetoed · <span className="font-mono" style={{ fontWeight: 500 }}>{f.council.criteriaVetoed}</span></span>
          <span>Ungrounded · <span className="font-mono" style={{ fontWeight: 500 }}>{f.council.ungrounded}</span></span>
          <span>Wasted LLM calls <Muted>(deliberated, then gate-vetoed)</Muted> · <span className="font-mono" style={{ fontWeight: 500 }}>{f.wasted}</span></span>
          {(provenance.reserve || provenance.fairness || provenance.rank) > 0 && (
            <span>Slate: {provenance.rank} by motion rank · {provenance.reserve} cheap reserve · {provenance.fairness} fairness</span>
          )}
        </div>
      </Card>

      {vm.dircoherence ? <DirCoherenceCard dc={vm.dircoherence} /> : null}
      {vm.staleness ? <StalenessCard st={vm.staleness} /> : null}

      <div className="grid grid-cols-1 lg:grid-cols-[1.6fr_1fr] items-start" style={{ gap: 16 }}>
        <Card style={{ padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>The decisions, and why <Muted>· proposer → adversary → strategist</Muted></div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 12 }}>
            The strategist’s weakest-point line is the “why”. <b>Via</b> is the slate provenance — reserve and fairness change <em>who</em> is judged, never <em>how</em>.
          </div>
          <SessionTable session={se} lastCol="weakest" />
        </Card>

        <div className="flex flex-col" style={{ gap: 16 }}>
          <Card style={{ padding: "18px 20px" }}>
            <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Why nothing passes</div>
            <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 8 }}>The mandate needs all three criteria on an include. Of {f.legs?.n ?? 0} deliberated:</div>
            <CriteriaLegs legs={f.legs} />
            <div style={{ fontSize: 11, color: "#6a7280", marginTop: 10, lineHeight: 1.5 }}>
              When inflection is the binding leg the universe is grounded and quiet but the council does not see the turn yet — the expected shape of a copper-not-rockets book.
            </div>
          </Card>
          <Card style={{ padding: "18px 20px" }}>
            <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>The cheapness gate <Muted>· {f.council.toGate ? `${f.council.toGate} reached it` : "nothing reached it"}</Muted></div>
            <div style={{ marginTop: 8 }}>
              <Row label={<>IV-gate vetoes <Muted>too rich</Muted></>} value={f.gate.ivReal} />
              <Row label={<>Fail-closed <Muted>missing data</Muted></>} value={<span style={{ color: f.gate.ivFail ? signal.warn.text : signal.ok.text }}>{f.gate.ivFail}</span>} />
              <Row label="Eligibility vetoes" value={f.gate.elig} />
              <Row label={<>Cluster-cap rejections <Muted>all-time</Muted></>} value={vm.capFlow.rejected} />
            </div>
          </Card>
        </div>
      </div>

      <Card style={{ padding: "18px 20px" }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Research instruments <Muted>· collapsed by default — records, not decisions</Muted></div>
        <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 8 }}>The pre-registered reads’ substrate. They matter for the frozen records, not for a daily glance.</div>
        <Instrument title="Null-book entry walk" meta={attempts.books.length ? `${attempts.books.map((b) => `${b.book} ${b.rows.length} rows`).join(" · ")} · session #${attempts.runId ?? "—"}` : "no rows yet"}>
          <div style={{ fontSize: 12, color: "#414956", marginBottom: 8 }}>Every candidate each capped null book touched last cycle, in walk order — why a name is (or isn’t) in a control book.</div>
          <div className="grid grid-cols-1 lg:grid-cols-2" style={{ gap: 16 }}>
            {attempts.books.map((b) => (
              <div key={b.book}>
                <div style={{ fontSize: 11, color: "#6a7280", textTransform: "uppercase", letterSpacing: ".6px", fontWeight: 500, marginBottom: 4 }}>book {b.book}</div>
                <div style={{ maxHeight: 240, overflowY: "auto" }}>
                  {b.rows.map((r, i) => (
                    <div key={i} className="flex items-center font-mono" style={{ gap: 10, padding: "5px 2px", borderTop: "1px solid #f6f8fa", fontSize: 12 }}>
                      <span style={{ color: "#6a7280", width: 22, textAlign: "right" }}>{r.idx}</span>
                      <span style={{ fontWeight: 500, color: "#141b28", width: 52 }}>{r.symbol}</span>
                      <span style={{ color: "#6a7280", width: 76 }}>{r.origin}</span>
                      <span style={{ color: r.outcome === "booked" ? signal.ok.text : "#414956", flex: 1 }}>{r.outcome}</span>
                      <span style={{ color: "#414956" }}>{r.premium == null ? "—" : `$${Math.round(r.premium).toLocaleString("en-US")}`}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Instrument>
        <Instrument title="Forward-catalyst channel" meta={`${cat.pins.length} pin${cat.pins.length === 1 ? "" : "s"}${cat.pins[0] ? ` · ${cat.pins[0].symbol} class ${cat.pins[0].cls} · expires ${cat.pins[0].expires}` : ""}${cat.ledgerLine ? ` · ${cat.ledgerLine.split(" · ")[0]}` : ""}`}>
          <div style={{ fontSize: 12, color: "#414956", marginBottom: 8 }}>Dated public forward evidence in the council pack — grounding, never permission. The M={cat.mTarget} disposition read stays the operator’s.</div>
          <div className="font-mono" style={{ fontSize: 12, color: "#414956" }}>{cat.stamp ?? "no stamp"}{cat.countersRunId != null ? ` · run #${cat.countersRunId}` : ""} · {cat.countersLine ?? "no cycle counters yet"}</div>
          {cat.pins.length > 0 && (
            <div className="flex flex-wrap" style={{ gap: 8, margin: "10px 0" }}>
              {cat.pins.map((p, i) => (
                <span key={i} className="font-mono" style={{ fontSize: 12, padding: "4px 9px", borderRadius: 7, background: signal.acc.bg, border: `1px solid ${signal.acc.border}`, color: signal.acc.text }}>
                  <span style={{ fontWeight: 500 }}>{p.symbol}</span><span style={{ opacity: 0.75 }}> · class {p.cls}{p.eventDate ? ` · event ${p.eventDate}` : ""} · pinned {p.asOf} · expires {p.expires}</span>
                </span>
              ))}
            </div>
          )}
          <div className="font-mono" style={{ fontSize: 12, color: "#141b28", marginTop: 6 }}>{cat.ledgerLine ?? "no pairs ledger yet"}{cat.bySymbol ? <span style={{ color: "#6a7280" }}> ({cat.bySymbol})</span> : null}</div>
        </Instrument>
        <Instrument title="Cheapness-watch (finding #1)" meta={ch ? `verdict ${ch.verdict} · ${ch.n_breaks} breaks · ${ch.n_qualifying} qualifying` : "accruing"}>
          <CheapnessWatch data={ch} />
        </Instrument>
      </Card>
    </div>
  );
}
