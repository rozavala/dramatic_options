import { useState } from "react";

import { relativeAge } from "../data/status";
import type { ConsoleProps } from "../data/types";
import { NAV, TITLES, type SectionId } from "../nav";
import { color, signal } from "../theme/tokens";
import { Book } from "./Book";
import { Edge } from "./Edge";
import { Overview } from "./Overview";
import { Pipeline } from "./Pipeline";
import { Safety } from "./Safety";
import { Banner, Skeleton } from "./primitives";

/** The 252px-rail desktop console (≥ the mobile breakpoint). Data comes from <App>; section state is local. */
export function DesktopConsole({ vm, loading, error, fatal, refresh }: ConsoleProps) {
  const [section, setSection] = useState<SectionId>("overview");
  const asOf = vm?.asOf ? vm.asOf.slice(0, 16).replace("T", " ") : "—";
  const age = relativeAge(vm?.asOf); // E2: "Nh ago" + a staleness tint
  const [title, subtitle] = TITLES[section];

  return (
    <div className="flex h-screen w-full overflow-hidden" style={{ fontSize: 14 }}>
      {/* ░░ LEFT RAIL ░░ */}
      <aside className="flex flex-col h-full" style={{ width: 252, flex: "none", background: color.navy900, borderRight: `1px solid ${color.navy700}` }}>
        <div style={{ padding: "22px 22px 18px", borderBottom: `1px solid ${color.navy700}` }}>
          <div className="flex items-center gap-2.5">
            <div className="flex items-center justify-center font-mono" style={{ width: 27, height: 27, borderRadius: 7, background: color.accent, fontWeight: 700, fontSize: 15, color: "#fff" }}>◭</div>
            <div>
              <div style={{ fontWeight: 500, fontSize: 15, letterSpacing: "-.2px", color: "#fff" }}>Dramatic Options</div>
              <div className="font-mono" style={{ fontSize: 11, color: "#8a98b0", letterSpacing: ".3px" }}>observability · paper</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto" style={{ padding: 12 }}>
          <div style={{ fontSize: 10.5, color: "#6c7a95", textTransform: "uppercase", letterSpacing: "1.2px", padding: "8px 10px 6px", fontWeight: 500 }}>Sections</div>
          {NAV.map((n) => {
            const active = n.id === section;
            return (
              <button
                key={n.id}
                onClick={() => setSection(n.id)}
                aria-current={active ? "page" : undefined}
                className="w-full flex items-center text-left"
                style={{ gap: 11, padding: "10px 12px", marginBottom: 3, borderRadius: 24, border: "none", cursor: "pointer", background: active ? "rgba(120,162,255,.18)" : "transparent" }}
              >
                <span style={{ width: 7, height: 7, borderRadius: "50%", flex: "none", background: active ? color.accent : "#4b5667" }} />
                <span className="flex-1">
                  <span className="block" style={{ fontWeight: active ? 500 : 400, fontSize: 13.5, color: active ? "#eaf1ff" : "#aeb8cc" }}>{n.label}</span>
                  <span className="block" style={{ fontSize: 11, color: "#7c89a1", marginTop: 1 }}>{n.sub}</span>
                </span>
              </button>
            );
          })}
        </nav>
        <div style={{ padding: "14px 18px", borderTop: `1px solid ${color.navy700}`, fontFamily: "'Roboto Mono', monospace" }}>
          <div className="flex items-center" style={{ gap: 6, fontSize: 11, color: "#8a98b0", marginBottom: 7 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#34d27b" }} />read-only · no-fetch · fail-soft
          </div>
          <div style={{ fontSize: 10.5, color: "#6c7a95", wordBreak: "break-all", lineHeight: 1.5 }}>~/dramatic_options/data/dramatic_options.db</div>
        </div>
      </aside>

      {/* ░░ MAIN ░░ */}
      <main className="flex flex-col h-full min-w-0" style={{ flex: 1 }}>
        <header className="flex items-center" style={{ flex: "none", padding: "16px 30px", borderBottom: `1px solid ${color.navy700}`, gap: 20, background: color.navy900 }}>
          <div className="flex-1 min-w-0">
            <div style={{ fontSize: 18, fontWeight: 500, letterSpacing: "-.3px", color: "#fff" }}>{title}</div>
            <div style={{ fontSize: 12.5, color: "#9aa6bd", marginTop: 2 }}>{subtitle}</div>
          </div>
          <button
            onClick={() => refresh()}
            disabled={loading}
            title="Refresh snapshot"
            aria-label="Refresh snapshot"
            className="flex items-center justify-center"
            style={{ background: "rgba(255,255,255,.07)", border: `1px solid ${color.navy600}`, color: "#aeb8cc", width: 36, height: 36, borderRadius: 9, cursor: loading ? "default" : "pointer", opacity: loading ? 0.55 : 1, fontSize: 15, animation: loading ? "spin .7s linear infinite" : undefined }}
          >
            ↻
          </button>
          <div className="font-mono text-right" style={{ fontSize: 11, color: "#8a98b0", lineHeight: 1.5 }}>
            as of {asOf}
            <br />
            <span style={{ color: age.label ? signal[age.level].text : "#8a98b0" }}>{age.label || "—"}</span>
          </div>
        </header>
        {loading && (
          <div style={{ height: 3, flex: "none", background: "#dbe7ff", overflow: "hidden" }}>
            <div style={{ height: "100%", width: "35%", background: color.accent, animation: "indet 1.1s ease-in-out infinite" }} />
          </div>
        )}

        <div className="overflow-y-auto" style={{ flex: 1, padding: "26px 30px 60px" }}>
          <div style={{ maxWidth: 1180, margin: "0 auto" }}>
            {fatal && (
              <div className="flex items-center justify-center" style={{ minHeight: "55vh" }}>
                <div className="bg-white border rounded-card shadow-card text-center" style={{ borderColor: "#f2a99e", padding: "36px 40px", maxWidth: 560 }}>
                  <div style={{ fontSize: 30, marginBottom: 10 }}>⚠</div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: "#d12d1c", marginBottom: 8 }}>Snapshot unavailable</div>
                  <div className="font-mono" style={{ fontSize: 12.5, color: "#5f6675", lineHeight: 1.6, wordBreak: "break-word" }}>{fatal}</div>
                </div>
              </div>
            )}
            {error && !fatal && (
              <div className="bg-white border rounded-card shadow-card" style={{ borderColor: "#f2a99e", padding: 20, color: "#d12d1c" }}>
                Couldn’t load the snapshot: {error}. Is the API running on :8602?
              </div>
            )}
            {vm?.schemaWarning && <div style={{ marginBottom: 14 }}><Banner level="warn">⚠ {vm.schemaWarning}</Banner></div>}
            {vm && vm.degraded.length > 0 && (
              <div style={{ marginBottom: 14 }}>
                <Banner level="bad">
                  {vm.degraded.length} panel{vm.degraded.length > 1 ? "s" : ""} unavailable (fail-soft): {vm.degraded.join(", ")}.
                  These render blank/zero — that is a crash, not “accruing”.
                </Banner>
              </div>
            )}
            {vm && section === "overview" && <Overview vm={vm} onNavigate={setSection} />}
            {vm && section === "safety" && <Safety vm={vm} />}
            {vm && section === "edge" && <Edge vm={vm} />}
            {vm && section === "pipeline" && <Pipeline vm={vm} />}
            {vm && section === "book" && <Book vm={vm} />}
            {!vm && !error && !fatal && loading && (
              <div className="flex flex-col" style={{ gap: 16 }}>
                <Skeleton height={92} />
                <div className="grid grid-cols-4 gap-3.5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} height={120} />)}</div>
                <Skeleton height={220} />
              </div>
            )}
            {!vm && !error && !fatal && !loading && <div style={{ color: "#5f6675" }}>No snapshot.</div>}
          </div>
        </div>
      </main>
    </div>
  );
}
