import type { ViewModel, WhyNoEntryRowVM, WhyNoEntryVM } from "../data/types";
import { runLabel } from "../data/runLabel";
import { signal } from "../theme/tokens";
import { Banner, Card, Chip } from "./primitives";

// #351 — "why no entry": one row per judged name of the latest council session, plus three tiles
// (expressible n/N · last above-floor conviction · last order attempt). Display only.

const MONO = "'Roboto Mono', ui-monospace, monospace";

function convLevel(r: WhyNoEntryRowVM): "acc" | "mute" { return r.aboveFloor ? "acc" : "mute"; }

/** Where the name stopped. An order outcome is shown with the contract detail beneath it; a gate stamp or a
 *  council stage stays muted. */
function Stopped({ r, compact }: { r: WhyNoEntryRowVM; compact?: boolean }) {
  const col = r.stoppedLevel === "mute" ? "#414956" : signal[r.stoppedLevel].text;
  return (
    <div data-testid="why-stopped" data-order={r.isOrder ? "1" : "0"}>
      <span style={{ color: col, fontWeight: r.isOrder ? 600 : 400, fontFamily: r.isOrder ? undefined : MONO, fontSize: compact ? 11 : 11.5 }}>{r.stoppedAt}</span>
      {r.orderDetail && <div className="font-mono" style={{ fontSize: compact ? 10 : 10.5, color: "#6a7280", marginTop: 2 }}>{r.orderDetail}</div>}
    </div>
  );
}

function Express({ r }: { r: WhyNoEntryRowVM }) {
  if (r.express === "yes") return <Chip level="ok" style={{ fontSize: 9.5, padding: "2px 7px" }}>expressible</Chip>;
  if (r.express === "no") return <Chip level="warn" style={{ fontSize: 9.5, padding: "2px 7px" }} >no structure</Chip>;
  return <Chip level="mute" style={{ fontSize: 9.5, padding: "2px 7px" }}>unread</Chip>;
}

function MiniTile({ label, chip, chipLevel, line, sub, testid }: {
  label: string; chip: string; chipLevel: "ok" | "warn" | "bad" | "acc" | "mute"; line: string; sub: string; testid: string;
}) {
  return (
    <div data-testid={testid} style={{ border: "1px solid #e3e6ec", borderRadius: 12, padding: "11px 13px", background: "#fafbfc", minWidth: 0 }}>
      <div className="flex justify-between items-center" style={{ gap: 6 }}>
        <span style={{ fontSize: 11.5, color: "#414956", fontWeight: 500 }}>{label}</span>
        <Chip level={chipLevel} style={{ fontSize: 9.5, padding: "2px 7px" }}>{chip}</Chip>
      </div>
      <div className="font-mono" style={{ fontSize: 14, fontWeight: 700, color: "#141b28", marginTop: 7, lineHeight: 1.3, overflowWrap: "anywhere" }}>{line}</div>
      <div style={{ fontSize: 11, color: "#6a7280", marginTop: 3, lineHeight: 1.45, overflowWrap: "anywhere" }}>{sub}</div>
    </div>
  );
}

export function WhyNoEntryTiles({ w }: { w: WhyNoEntryVM }) {
  const ex = w.expressible, af = w.lastAboveFloor, lo = w.lastOrder;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3" style={{ gap: 10 }}>
      <MiniTile
        testid="why-tile-expressible" label="Expressible" chip={ex.of ? "gate-of-record read" : "no reads"} chipLevel="mute"
        line={ex.of ? `${ex.n} / ${ex.of} names` : "—"}
        sub={ex.noStructure.length ? `no eligible structure: ${ex.noStructure.join(", ")}` : ex.of ? "every read name has a structure" : "no fresh read yet"}
      />
      <MiniTile
        testid="why-tile-above-floor" label={`Last conviction ≥ ${w.floor}`} chip={af ? "found" : "none yet"} chipLevel={af ? "acc" : "mute"}
        line={af ? af.line : "—"} sub={af ? af.sub : "no proposal has cleared the floor"}
      />
      <MiniTile
        testid="why-tile-last-order" label="Last order attempt" chip={lo ? (lo.level === "warn" ? "not filled" : lo.level === "ok" ? "filled" : "resting") : "none"}
        chipLevel={lo ? (lo.level === "mute" ? "acc" : lo.level) : "mute"}
        line={lo ? lo.line : "—"} sub={lo ? lo.sub : "no order has been attempted"}
      />
    </div>
  );
}

/** Desktop table. */
export function WhyNoEntryTable({ w }: { w: WhyNoEntryVM }) {
  const th: React.CSSProperties = { textAlign: "left", fontSize: 11, color: "#6a7280", fontWeight: 500, padding: "6px 8px", borderBottom: "1px solid #edf0f4", whiteSpace: "nowrap" };
  const td: React.CSSProperties = { padding: "8px 8px", borderBottom: "1px solid #f3f5f8", verticalAlign: "top", fontSize: 12, color: "#141b28" };
  return (
    <div style={{ overflowX: "auto" }}>
      <table data-testid="why-table" style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={th}>Name</th><th style={th}>Conviction</th><th style={th}>Stopped at</th>
            <th style={{ ...th, textAlign: "right" }}>iv/rv</th><th style={{ ...th, textAlign: "right" }}>skew</th><th style={th}>Structure</th>
          </tr>
        </thead>
        <tbody>
          {w.rows.map((r) => (
            <tr key={r.symbol} data-testid={`why-row-${r.symbol}`}>
              <td style={td}><span className="font-mono" style={{ fontWeight: 700 }}>{r.symbol}</span> <span style={{ fontSize: 10.5, color: "#6a7280" }}>{r.dir}</span></td>
              <td style={td}><Chip level={convLevel(r)} style={{ fontSize: 9.5, padding: "2px 7px" }}>{r.conviction}</Chip></td>
              <td style={td}><Stopped r={r} /></td>
              <td className="font-mono" style={{ ...td, textAlign: "right" }}>{r.ivrv}</td>
              <td className="font-mono" style={{ ...td, textAlign: "right" }}>{r.skew}</td>
              <td style={td}><Express r={r} />{r.expressNote && <div className="font-mono" style={{ fontSize: 10, color: "#6a7280", marginTop: 3 }}>{r.expressNote}</div>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Mobile list — one stacked card per name (a 6-column table does not fit 390px). */
export function WhyNoEntryList({ w }: { w: WhyNoEntryVM }) {
  return (
    <div data-testid="why-list">
      {w.rows.map((r) => (
        <div key={r.symbol} data-testid={`why-row-${r.symbol}`} style={{ padding: "9px 0", borderBottom: "1px solid #f3f5f8" }}>
          <div className="flex items-center justify-between" style={{ gap: 8 }}>
            <span><span className="font-mono" style={{ fontSize: 13, fontWeight: 700, color: "#141b28" }}>{r.symbol}</span> <span style={{ fontSize: 10, color: "#6a7280" }}>{r.dir}</span></span>
            <span className="flex items-center" style={{ gap: 5 }}>
              <Chip level={convLevel(r)} style={{ fontSize: 9, padding: "2px 7px" }}>{r.conviction}</Chip>
              <Express r={r} />
            </span>
          </div>
          <div style={{ marginTop: 5 }}><Stopped r={r} compact /></div>
          <div className="font-mono" style={{ fontSize: 10, color: "#6a7280", marginTop: 3 }}>
            iv/rv {r.ivrv} · skew {r.skew}{r.expressNote ? ` · ${r.expressNote}` : ""}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Shared blurb above the rows: unavailable / empty / drift warnings. Returns null when the table should render. */
function Notice({ w }: { w: WhyNoEntryVM }) {
  if (w.unavailable) return <div data-testid="why-unavailable" style={{ fontSize: 12, color: signal.warn.text, marginTop: 10 }}>unavailable — the why-no-entry panel did not load</div>;
  if (w.empty || w.rows.length === 0) return <div data-testid="why-empty" style={{ fontSize: 12, color: "#6a7280", marginTop: 10 }}>no council session recorded yet</div>;
  return null;
}

/** Desktop Overview card. */
export function WhyNoEntryCard({ vm }: { vm: ViewModel }) {
  const w = vm.whyNoEntry;
  const notice = Notice({ w });
  return (
    <Card style={{ padding: "20px 22px" }}>
      <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>
        Why no entry
        <span style={{ color: "#6a7280", fontWeight: 400 }}>
          {w.runId != null ? ` · ${runLabel(vm.runDates, w.runId)} · conviction floor ${w.floor}` : ""}
        </span>
      </div>
      <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5, marginBottom: 12 }}>
        One row per judged name, where it stopped and whether the gate could even build a structure for it.
      </div>
      {w.warning && <Banner level="warn" style={{ marginBottom: 10 }}>{w.warning}</Banner>}
      <WhyNoEntryTiles w={w} />
      {notice ?? <div style={{ marginTop: 12 }}><WhyNoEntryTable w={w} /></div>}
    </Card>
  );
}
