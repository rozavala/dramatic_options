import type { ViewModel } from "../data/types";
import { color, signal } from "../theme/tokens";
import { Card, Chip } from "./primitives";
import { CriteriaLegs, LowHistory, SessionTable } from "./SessionTable";
import { StatusBanner } from "./StatusBanner";
import { T4Road } from "./T4Road";

function Tile({ label, chip, chipLevel, children }: { label: React.ReactNode; chip: string; chipLevel: "ok" | "warn" | "bad" | "acc" | "mute"; children: React.ReactNode }) {
  return (
    <Card style={{ padding: "16px 18px" }}>
      <div className="flex justify-between items-center" style={{ gap: 8 }}>
        <span style={{ fontSize: 12, color: "#414956", fontWeight: 500 }}>{label}</span>
        <Chip level={chipLevel}>{chip}</Chip>
      </div>
      {children}
    </Card>
  );
}
const big: React.CSSProperties = { fontFamily: "'Roboto Mono', ui-monospace, monospace", fontSize: 25, fontWeight: 700, letterSpacing: "-.5px", marginTop: 9, color: "#141b28" };
const small: React.CSSProperties = { fontSize: 15, color: "#6a7280", fontWeight: 500 };
const sub: React.CSSProperties = { fontSize: 11.5, color: "#6a7280", marginTop: 3, lineHeight: 1.45 };

/** Overview = what changed since yesterday + is it safe: status line → three tiles (book · last session ·
 *  spend) → the session's decisions → the position / canary / feed wires → the compact T4 road. */
export function Overview({ vm }: { vm: ViewModel }) {
  const se = vm.session;
  const dd = vm.bookDD;
  const ddFrac = parseFloat(dd) / 20 || 0;
  const councilOk = vm.council.vlevel === "ok";
  const pos = vm.positions[0];
  const running = pos && pos.mark != null ? pos.premiumUsd * (pos.mark - 1) : null;
  const bled = pos && pos.mark != null ? Math.round((1 - pos.mark) * 100) : null;
  const legs = vm.funnel.legs;
  const wires = vm.dualreadRuntime.classes;
  const wiresClear = wires.filter((c) => !c.tripped).length;
  const c = vm.canary;
  return (
    <div className="flex flex-col" style={{ gap: 16 }}>
      <StatusBanner vm={vm} />

      <div className="grid grid-cols-1 lg:grid-cols-3" style={{ gap: 14 }}>
        <Tile label="Book" chip={vm.bookDDlevel === "ok" ? "inside frame" : "kill rule tripped"} chipLevel={vm.bookDDlevel}>
          <div style={big}>{vm.openN} <span style={small}>/ {vm.maxN} open</span></div>
          <div style={sub}>{vm.openPrem} premium at risk of {vm.bookBudget} · drawdown <b style={{ color: signal[vm.bookDDlevel].text }}>{dd}</b> of the 20% halt</div>
          <div style={{ height: 6, background: "#edf0f4", borderRadius: 3, marginTop: 12, overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${Math.min(100, ddFrac * 100)}%`, background: signal[vm.bookDDlevel].text, borderRadius: 3 }} />
          </div>
          <div style={{ fontSize: 11, color: "#6a7280", marginTop: 5 }}>drawdown vs halt</div>
        </Tile>

        <Tile
          label={<>Last council session <span className="font-mono" style={{ color: "#6a7280", fontWeight: 400 }}>{se.runId != null ? `#${se.runId}` : ""}</span></>}
          chip={vm.council.verdict.toLowerCase()} chipLevel={vm.council.vlevel}
        >
          <div style={big}>{vm.council.parseFail}<span style={small}>/{vm.council.parseCalled} parse-fails</span></div>
          <div style={sub}>
            {vm.council.roundtrips} full round-trips · {se.providerDrops} provider drops · <b>{se.cleanLine}</b>
          </div>
          <div className="font-mono" style={{ fontSize: 11.5, color: "#414956", marginTop: 10 }}>
            {vm.council.models}
            {se.understudy.configured && (
              <> · understudy <span style={{ color: se.understudy.fired ? signal.warn.text : signal.ok.text }}>{se.understudy.fired ? `FIRED ×${se.understudy.fired}` : "dormant"}</span></>
            )}
          </div>
          {!councilOk && <div style={{ ...sub, color: signal.warn.text }}>worth a look — see Risk &amp; Feeds</div>}
        </Tile>

        <Tile label={`LLM spend · ${vm.spend.month}`} chip={vm.spend.anyPage ? "tripwire" : "under tripwire"} chipLevel={vm.spend.anyPage ? "warn" : "ok"}>
          <div style={big}>{vm.spend.totalMtd} {vm.spend.totalCap && <span style={small}>/ {vm.spend.totalCap}</span>}</div>
          <div className="flex flex-col" style={{ gap: 5, marginTop: 10 }}>
            {vm.spend.rows.filter((r) => r.cap).map((r) => (
              <div key={r.provider} className="flex items-center" style={{ gap: 8 }}>
                <span className="font-mono" style={{ width: 64, fontSize: 11, color: "#414956" }}>{r.provider}</span>
                <div style={{ flex: 1, height: 6, background: "#edf0f4", borderRadius: 3, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${Math.min(100, (r.frac ?? 0) * 100)}%`, background: r.page ? signal.warn.text : color.accent, borderRadius: 3 }} />
                </div>
                <span className="font-mono" style={{ width: 92, textAlign: "right", fontSize: 11, color: "#414956" }}>{r.mtd} / {r.cap}</span>
              </div>
            ))}
          </div>
        </Tile>
      </div>

      <Card style={{ padding: "20px 22px" }}>
        <div className="flex items-baseline justify-between flex-wrap" style={{ gap: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>
            What the council decided
            <span style={{ color: "#6a7280", fontWeight: 400 }}> · session {se.runId != null ? `#${se.runId}` : "—"} · {se.rows.length} names judged, {vm.funnel.council.toGate} reached the gate</span>
          </div>
          <div className="flex items-center" style={{ gap: 8 }}>
            <span className="font-mono" style={{ fontSize: 12, color: "#414956" }}>profile</span>
            {se.profile.map((p) => <Chip key={p.level} level={p.level === "MODERATE+" && p.n > 0 ? "acc" : "mute"}>{p.n} {p.level}</Chip>)}
          </div>
        </div>
        <div style={{ fontSize: 12, color: "#414956", marginTop: 3, lineHeight: 1.5 }}>
          Every name below floor is healthy behaviour — the gate only buys convexity the council can ground. The <b>Streak</b> column is the
          signal: names the strategist keeps rating LOW are the theses inching toward a trade.
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_.8fr]" style={{ gap: 24, marginTop: 14 }}>
          <SessionTable session={se} lastCol="streak" />
          <div style={{ borderLeft: "1px solid #edf0f4", paddingLeft: 22 }}>
            <LowHistory session={se} />
            <div style={{ marginTop: 18 }}>
              <div style={{ fontSize: 12, color: "#414956", fontWeight: 500 }}>Why nothing passes</div>
              <div style={{ fontSize: 11, color: "#6a7280", marginTop: 2, lineHeight: 1.5 }}>the three criteria the strategist must all confirm · {legs?.n ?? 0} deliberated</div>
              <div style={{ marginTop: 8 }}><CriteriaLegs legs={legs} compact /></div>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr_1fr]" style={{ gap: 14 }}>
        <Tile label={vm.positions.length > 1 ? `Open positions · ${vm.positions.length}` : "Open position"} chip={pos ? (bled != null ? `${bled}% bled` : "no mark") : "empty"} chipLevel={pos ? (bled != null && bled >= 50 ? "warn" : "acc") : "mute"}>
          {pos ? (
            <>
              <div className="flex items-baseline" style={{ gap: 10, marginTop: 9 }}>
                <span className="font-mono" style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-.5px", color: "#141b28" }}>{pos.symbol}</span>
                <span style={{ fontSize: 11, fontWeight: 500, color: pos.dir === "bearish" ? signal.bad.text : signal.ok.text }}>{pos.dir === "bearish" ? "PUT" : "CALL"}</span>
                <span style={{ fontSize: 12, color: "#414956" }}>{pos.theme ?? "—"}</span>
              </div>
              <div style={sub}>{pos.conviction ?? "—"} at entry{pos.opened ? ` · opened ${pos.opened}` : ""}{vm.positions.length > 1 ? ` · +${vm.positions.length - 1} more in Book` : ""}</div>
              <div className="grid grid-cols-3" style={{ gap: 10, marginTop: 12 }}>
                <div><div style={{ fontSize: 11, color: "#6a7280" }}>days left</div><div className="font-mono" style={{ fontSize: 15, fontWeight: 500, color: "#141b28" }}>{pos.dte ?? "—"}</div></div>
                <div><div style={{ fontSize: 11, color: "#6a7280" }}>mark ÷ entry</div><div className="font-mono" style={{ fontSize: 15, fontWeight: 500, color: pos.mark != null && pos.mark < 1 ? signal.warn.text : signal.ok.text }}>{pos.mark != null ? `${pos.mark.toFixed(2)}×` : "—"}</div></div>
                <div><div style={{ fontSize: 11, color: "#6a7280" }}>running</div><div className="font-mono" style={{ fontSize: 15, fontWeight: 500, color: running != null && running < 0 ? signal.warn.text : signal.ok.text }}>{running == null ? "—" : `${running < 0 ? "−" : "+"}$${Math.abs(Math.round(running)).toLocaleString("en-US")}`}</div></div>
              </div>
              <div style={{ ...sub, marginTop: 10 }}>A far-OTM option is expected to sit near zero for most of its life; the read is the tail at expiry, not the mark today.</div>
            </>
          ) : (
            <div style={{ ...sub, marginTop: 12 }}>The book stays empty until a genuinely cheap, grounded idea clears the gate — a clean state, not a problem.</div>
          )}
        </Tile>

        <Tile label={c ? `Canary · ${c.symbol} iv/rv` : "Canary"} chip={c?.cheap == null ? "no read" : c.cheap ? "still gate-cheap" : "gate-rich"} chipLevel={c?.cheap == null ? "mute" : c.cheap ? "acc" : "mute"}>
          {c && c.latest != null ? (
            <>
              <div style={big}>{c.latest.toFixed(3)}</div>
              <div style={sub}>{c.trend === "up" ? "moving up off parity" : c.trend === "down" ? "compressing toward parity" : "flat"}{c.skew != null ? ` · skew ${c.skew.toFixed(2)}` : ""}</div>
              <CanarySpark series={c.series} gateLine={c.gateLine} />
              <div style={{ fontSize: 11, color: "#6a7280" }}>{c.gateLine} is the gate line · 1.0 = implied equals realized</div>
            </>
          ) : (
            <div style={{ ...sub, marginTop: 12 }}>no canary reads yet</div>
          )}
        </Tile>

        <Tile label="Feed tripwires" chip={wires.length ? `${wiresClear} / ${wires.length} clear` : "no sessions"} chipLevel={wires.length && wiresClear === wires.length ? "ok" : wires.length ? "bad" : "mute"}>
          <div style={{ ...big, fontSize: 22 }}>
            {vm.dualread.opraCov != null ? Math.round(vm.dualread.opraCov * 100) : "—"}<span style={small}>% of names read both arms</span>
          </div>
          <div style={sub}>OPRA gate vs INDICATIVE shadow · Δ iv/rv median {vm.dualread.medianD ?? "—"}, max {vm.dualread.maxD ?? "—"}</div>
          <div className="font-mono" style={{ fontSize: 11.5, color: "#414956", marginTop: 10 }}>
            wing mismatch: {vm.wingMismatch.length ? vm.wingMismatch.join(", ") : "none"} {vm.wingMismatch.length > 0 && <span style={{ color: "#6a7280" }}>(expiry choice only)</span>}
          </div>
        </Tile>
      </div>

      <T4Road vm={vm} />
    </div>
  );
}

function CanarySpark({ series, gateLine }: { series: number[]; gateLine: number }) {
  if (series.length < 2) return <div style={{ height: 44 }} />;
  const W = 220, H = 36;
  const lo = Math.min(1.0, ...series), hi = Math.max(gateLine, ...series);
  const x = (i: number) => 10 + (i / (series.length - 1)) * (W - 20);
  const y = (v: number) => H - 4 - ((v - lo) / (hi - lo || 1)) * (H - 8);
  const pts = series.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <svg width="100%" height="48" viewBox={`0 0 ${W} ${H + 12}`} style={{ marginTop: 8, display: "block" }}>
      <line x1="0" y1={y(1.0)} x2={W} y2={y(1.0)} stroke="#edf0f4" strokeWidth="1" />
      <polyline points={pts} fill="none" stroke={color.accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={x(series.length - 1)} cy={y(series[series.length - 1])} r="4" fill={color.accent} stroke="#ffffff" strokeWidth="2" />
      <text x="10" y={H + 10} fontFamily="Roboto Mono" fontSize="9" fill="#6a7280">{series[0].toFixed(3)}</text>
      <text x={W - 36} y={H + 10} fontFamily="Roboto Mono" fontSize="9" fill="#6a7280">{series[series.length - 1].toFixed(3)}</text>
    </svg>
  );
}
