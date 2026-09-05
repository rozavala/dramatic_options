import { clusterLevel } from "../data/status";
import type { ViewModel } from "../data/types";
import { color, signal, type Level } from "../theme/tokens";
import { Sparkline } from "./Sparkline";
import { Card, Chip } from "./primitives";

function Tile({ label, value, valColor, sub, series, bar }: { label: string; value: React.ReactNode; valColor?: string; sub: string; series?: { equity: number }[]; bar?: { frac: number; level: Level } }) {
  return (
    <Card style={{ padding: "16px 17px" }}>
      <div style={{ fontSize: 12, color: "#414956" }}>{label}</div>
      <div className="font-mono" style={{ fontSize: 25, fontWeight: 700, marginTop: 9, color: valColor ?? "#141b28", letterSpacing: "-.5px" }}>{value}</div>
      <div style={{ fontSize: 11.5, color: "#6a7280", marginTop: 3 }}>{sub}</div>
      {series && <Sparkline series={series} height={30} />}
      {bar && (
        <div style={{ height: 6, background: "#edf0f4", borderRadius: 3, marginTop: 14, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${Math.max(1, Math.min(100, bar.frac * 100))}%`, background: signal[bar.level].text, borderRadius: 3 }} />
        </div>
      )}
    </Card>
  );
}
const Row = ({ label, value }: { label: React.ReactNode; value: React.ReactNode }) => (
  <div className="flex justify-between items-center" style={{ gap: 14, padding: "8px 0", borderTop: "1px solid #edf0f4" }}>
    <span style={{ fontSize: 12.5, color: "#2c3645" }}>{label}</span>
    <span className="font-mono text-right" style={{ fontSize: 12.5, fontWeight: 500, color: "#2c3645" }}>{value}</span>
  </div>
);
const Muted = ({ children }: { children: React.ReactNode }) => <span style={{ color: "#6a7280", fontWeight: 400 }}>{children}</span>;

/** Risk & Feeds: the frame tiles · cluster exposure (non-zero only) · council health · the five feed wires
 *  (ONE card — the old soak + runtime cards drew the same wires twice) · month-to-date spend vs tripwire. */
export function Safety({ vm }: { vm: ViewModel }) {
  const c = vm.council;
  const sig = signal[c.vlevel];
  const councilOk = c.vlevel === "ok";
  const held = vm.clusters.filter((cl) => cl.premium > 0);
  const empty = vm.clusters.filter((cl) => cl.premium <= 0);
  const dr = vm.dualread;
  const rt = vm.dualreadRuntime;
  const ddFrac = (parseFloat(vm.bookDD) || 0) / 20;
  return (
    <div className="flex flex-col" style={{ gap: 16 }}>
      <div className="grid grid-cols-2 lg:grid-cols-4" style={{ gap: 14 }}>
        <Tile label="Paper equity" value={vm.equity} sub={`${vm.deltaFrame} · informational`} series={vm.equitySeries} />
        <Tile label="Book drawdown" value={vm.bookDD} valColor={signal[vm.bookDDlevel].text} sub="the kill rule halts new entries at 20%" bar={{ frac: ddFrac, level: vm.bookDDlevel }} />
        <Tile label="Open positions" value={<>{vm.openN} <span style={{ fontSize: 15, color: "#6a7280", fontWeight: 500 }}>/ {vm.maxN}</span></>} sub={`${vm.openPrem} premium at risk · ${vm.openN} slot${vm.openN === 1 ? "" : "s"} used`} bar={{ frac: vm.maxN ? vm.openN / vm.maxN : 0, level: "acc" }} />
        <Tile label="Headroom" value={vm.headroom} valColor={signal.ok.text} sub={`of the ${vm.bookBudget} book budget · per name ≤ $1,000`} bar={{ frac: 1 - Math.min(1, vm.openN / Math.max(1, vm.maxN)), level: "ok" }} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr]" style={{ gap: 16 }}>
        <Card style={{ padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Cluster exposure <Muted>· each correlated theme capped at $2,000 (~2%)</Muted></div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5 }}>Only clusters holding premium are drawn; the rest are listed, not charted.</div>
          <div style={{ marginTop: 16 }}>
            {held.length === 0 && <div style={{ fontSize: 12.5, color: "#5f6675" }}>No cluster holds premium.</div>}
            {held.map((cl) => {
              const frac = cl.cap ? cl.premium / cl.cap : 0;
              const lv = signal[clusterLevel(frac)];
              return (
                <div key={cl.name} style={{ marginBottom: 13 }}>
                  <div className="flex justify-between items-baseline" style={{ marginBottom: 5 }}>
                    <span className="font-mono" style={{ fontSize: 12.5, fontWeight: 500, color: "#2c3645" }}>{cl.name}</span>
                    <span className="font-mono" style={{ fontSize: 11.5, color: "#414956" }}>
                      ${cl.premium.toLocaleString()} / ${cl.cap.toLocaleString()} · <span style={{ color: lv.text, fontWeight: 500 }}>{Math.round(frac * 100)}%</span>{cl.dirs !== "—" ? ` · ${cl.dirs}` : ""}
                    </span>
                  </div>
                  <div style={{ height: 8, background: "#edf0f4", borderRadius: 4, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${Math.max(2, frac * 100)}%`, background: lv.text, borderRadius: 4 }} />
                  </div>
                </div>
              );
            })}
          </div>
          {empty.length > 0 && (
            <div className="font-mono" style={{ fontSize: 11.5, color: "#6a7280", marginTop: 12, lineHeight: 1.7, paddingTop: 12, borderTop: "1px solid #edf0f4" }}>
              {empty.length} cluster{empty.length === 1 ? "" : "s"} at $0 — {empty.map((cl) => cl.name).join(" · ")}
            </div>
          )}
          <div style={{ fontSize: 11, color: "#6a7280", marginTop: 10, lineHeight: 1.5 }}>The book fills at most 5 clusters × $2,000. Cluster-cap rejections of otherwise-passing candidates: {vm.capFlow.rejected}.</div>
        </Card>

        <Card style={{ padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>AI council — deliberation health</div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5 }}>Three models debate each idea (proposer → adversary → strategist). They only suggest; the gate decides.</div>
          <div className="flex items-center" style={{ gap: 11, margin: "14px 0 10px", padding: "12px 13px", borderRadius: 10, background: sig.bg, border: `1px solid ${sig.border}` }}>
            <span style={{ fontSize: 18, color: sig.text }}>{councilOk ? "✓" : "⚠"}</span>
            <div>
              <div style={{ fontSize: 14, fontWeight: 500, color: sig.text }}>{c.verdict}</div>
              <div style={{ fontSize: 11.5, color: "#414956" }}>session #{c.runId ?? "—"} · {vm.session.cleanLine}</div>
            </div>
          </div>
          <Row label="Full round-trips" value={`${c.roundtrips} of ${c.parseCalled}`} />
          <Row label="Parse-fails · provider drops" value={<span style={{ color: c.parseFail || vm.session.providerDrops ? signal.warn.text : signal.ok.text }}>{c.parseFail} · {vm.session.providerDrops}</span>} />
          <Row label={<>Per-provider parse-fails <Muted>latest session</Muted></>} value={c.byProvider.length ? c.byProvider.map((p) => `${p.provider} ${p.parseError}/${p.calls}`).join(" · ") : "—"} />
          <Row label="Session cost" value={c.cost} />
          <Row label="Roles" value={<span style={{ fontSize: 11.5 }}>{c.models}</span>} />
          {vm.session.understudy.configured && (
            <Row label={<>Understudy <Muted>strategist fallback</Muted></>} value={<span style={{ fontSize: 11.5 }}>{vm.session.understudy.configured.split(":").pop()?.split("/").pop()} · <span style={{ color: vm.session.understudy.fired ? signal.warn.text : signal.ok.text }}>{vm.session.understudy.fired ? `fired ×${vm.session.understudy.fired}` : "dormant"}</span></span>} />
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr]" style={{ gap: 16 }}>
        <Card style={{ padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Data-feed tripwires <Muted>· OPRA gate vs INDICATIVE shadow · rolling {rt.window || dr.window}</Muted></div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5 }}>
            The entry gate reads the real OPRA chain; the indicative feed shadows it and can only veto. A tripped wire fires the fail-closed response (investigate, or revert + page).
          </div>
          <div style={{ marginTop: 10 }}>
            {rt.classes.map((w) => (
              <div key={w.key} className="flex justify-between items-center" style={{ gap: 14, padding: "8px 0", borderTop: "1px solid #edf0f4" }}>
                <span style={{ fontSize: 12.5, color: "#2c3645" }}>
                  {w.label}{w.reverts && <span style={{ color: "#6a7280", fontSize: 11 }}> · the only wire that can revert the gate</span>}
                </span>
                <span className="flex items-center" style={{ gap: 9 }}>
                  {w.key === "delta" && dr.medianD != null && <span className="font-mono" style={{ fontSize: 12, color: "#414956" }}>med {dr.medianD} · max {dr.maxD}</span>}
                  {w.key !== "delta" && w.sessions != null && <span className="font-mono" style={{ fontSize: 12, color: "#414956" }}>{w.sessions} / {rt.window}</span>}
                  {w.pages.length > 0 && <span className="font-mono" style={{ fontSize: 11.5, color: signal.warn.text }}>pages: {w.pages.join(", ")}</span>}
                  <Chip level={w.tripped ? "bad" : "ok"}>{w.tripped ? "TRIPPED" : "clear"}</Chip>
                </span>
              </div>
            ))}
            {rt.classes.length === 0 && <div style={{ fontSize: 12.5, color: "#5f6675", paddingTop: 8 }}>no dual-read sessions yet (accruing from the first post-flip L1)</div>}
          </div>
          <div className="font-mono" style={{ fontSize: 11, color: "#6a7280", marginTop: 12, lineHeight: 1.6 }}>
            {dr.lastRun != null ? `latest #${dr.lastRun}` : "no sessions"} · {dr.sessions} sessions · coverage {dr.opraCov != null ? `${Math.round(dr.opraCov * 100)}%` : "—"} both arms
            · revert latch: Phase 3 {rt.phase3 ? "ON" : "OFF"} · {rt.latched ? "LATCHED" : "not latched"} · {rt.authorized ? "REVERT AUTHORIZED" : "not authorized"}
            {vm.wingMismatch.length > 0 && <> · wing mismatch {vm.wingMismatch.join(", ")}</>}
            {dr.vetoUntil && <> · disagree-veto {dr.vetoActive ? `until ${dr.vetoUntil}` : `lapsed ${dr.vetoUntil}`}</>}
          </div>
        </Card>

        <Card style={{ padding: "18px 20px" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>LLM spend <Muted>· {vm.spend.month} · tripwire per provider</Muted></div>
          <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5 }}>
            The page fires at 80% of a provider’s monthly cap. Council-scope only — a shared key’s external usage is invisible here, so console-side alerts stay the operator’s lever.
          </div>
          <div className="flex flex-col" style={{ gap: 9, marginTop: 14 }}>
            {vm.spend.rows.map((r) => (
              <div key={r.provider}>
                <div className="flex justify-between" style={{ marginBottom: 4 }}>
                  <span className="font-mono" style={{ fontSize: 12, color: "#2c3645" }}>{r.provider}{!r.cap && <Muted> no cap</Muted>}</span>
                  <span className="font-mono" style={{ fontSize: 12, color: r.page ? signal.warn.text : "#414956" }}>{r.mtd}{r.cap ? ` / ${r.cap}` : ""}</span>
                </div>
                <div style={{ height: 6, background: "#edf0f4", borderRadius: 3, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${Math.min(100, (r.frac ?? 0) * 100)}%`, background: r.page ? signal.warn.text : color.accent, borderRadius: 3 }} />
                </div>
              </div>
            ))}
            {vm.spend.rows.length === 0 && <div style={{ fontSize: 12.5, color: "#5f6675" }}>no providers configured</div>}
          </div>
          <div style={{ marginTop: 12 }}>
            <Row label={<>Cumulative <Muted>all-time</Muted></>} value={<>{vm.spend.cumulative} <Muted>· L0 framer {vm.spend.framer}</Muted></>} />
            {vm.spend.perCycleCap && <Row label="Per-cycle cap" value={vm.spend.perCycleCap} />}
          </div>
        </Card>
      </div>
    </div>
  );
}
