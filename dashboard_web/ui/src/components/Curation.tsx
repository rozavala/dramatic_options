import type { CSSProperties } from "react";
import { useState } from "react";

import { color, signal } from "../theme/tokens";
import { Card } from "./primitives";

// Same-origin in prod; the Vite dev proxy forwards /api → :8602 (mirrors useSnapshot).
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

interface ScreenResult {
  kind: "screen";
  tickers: string[];
  command: string;
  dropped: number;
}
interface ThemeResult {
  kind: "theme";
  key: string;
  entry: Record<string, unknown>;
  json: string;
  valid: boolean;
  problems: string[];
  warnings: string[];
}

// POST the form input to the PURE draft endpoint (no fetch/write/keys server-side — it reuses the same
// tested dashboard_data builders). Drafting is not writing: the operator runs the screen on the box, and a
// new theme lands via a PR + the §11 admission rule + the gate.
async function postDraft(body: Record<string, unknown>): Promise<ScreenResult | ThemeResult> {
  const res = await fetch(`${API_BASE}/api/curation/draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as ScreenResult | ThemeResult;
}

const inputStyle: CSSProperties = {
  width: "100%", padding: "9px 12px", borderRadius: 9, border: `1px solid ${color.navy600}`,
  background: "#0b1426", color: "#eaf1ff", fontSize: 13.5, outline: "none",
};
const labelStyle: CSSProperties = { fontSize: 12, color: "#9aa6bd", marginBottom: 5, display: "block" };
const btnStyle: CSSProperties = {
  padding: "9px 18px", borderRadius: 9, border: "none", background: color.accent, color: "#fff",
  fontSize: 13.5, fontWeight: 500, cursor: "pointer", flex: "none",
};
const preStyle: CSSProperties = {
  marginTop: 12, padding: "12px 14px", borderRadius: 9, background: "#0b1426",
  border: `1px solid ${color.navy700}`, color: "#cfe0ff", fontFamily: "'Roboto Mono', monospace",
  fontSize: 12.5, whiteSpace: "pre-wrap", wordBreak: "break-word", userSelect: "all",
};

/** Interactive curation tools — keyless drafting only (no fetch/write); the server endpoint is pure. */
export function Curation() {
  const [tickers, setTickers] = useState("");
  const [screen, setScreen] = useState<ScreenResult | null>(null);
  const [screenErr, setScreenErr] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [cluster, setCluster] = useState("");
  const [thesis, setThesis] = useState("");
  const [falsifier, setFalsifier] = useState("");
  const [source, setSource] = useState("");
  const [theme, setTheme] = useState<ThemeResult | null>(null);
  const [themeErr, setThemeErr] = useState<string | null>(null);

  async function onScreen() {
    setScreenErr(null);
    try {
      setScreen((await postDraft({ kind: "screen", tickers })) as ScreenResult);
    } catch (e) {
      setScreenErr(e instanceof Error ? e.message : String(e));
    }
  }
  async function onTheme() {
    setThemeErr(null);
    try {
      setTheme((await postDraft({ kind: "theme", name, cluster, thesis, falsifier, source })) as ThemeResult);
    } catch (e) {
      setThemeErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="flex flex-col" style={{ gap: 18 }}>
      <Card style={{ padding: 22 }}>
        <div style={{ fontSize: 15, fontWeight: 500, color: "#fff", marginBottom: 4 }}>Feasibility screen</div>
        <div style={{ fontSize: 12.5, color: "#9aa6bd", marginBottom: 14 }}>
          Tickers → the command to run on the box (the screen needs live quotes; this surface is keyless).
          Only clean tickers survive — the command is shell-pasted, so no shell metacharacter is kept.
        </div>
        <label style={labelStyle}>tickers (space/comma separated)</label>
        <div className="flex" style={{ gap: 10 }}>
          <input style={inputStyle} value={tickers} onChange={(e) => setTickers(e.target.value)}
                 placeholder="AMBA MBLY CF MOS IPI" />
          <button style={btnStyle} onClick={() => void onScreen()}>Build command</button>
        </div>
        {screenErr && <div style={{ marginTop: 10, color: signal.bad.text, fontSize: 12.5 }}>draft failed: {screenErr}</div>}
        {screen && (
          <>
            <pre style={preStyle}>{screen.command || "(no valid tickers)"}</pre>
            {screen.dropped > 0 && (
              <div style={{ marginTop: 6, fontSize: 11.5, color: "#7c89a1" }}>
                {screen.dropped} token(s) dropped — only clean tickers kept.
              </div>
            )}
          </>
        )}
      </Card>

      <Card style={{ padding: 22 }}>
        <div style={{ fontSize: 15, fontWeight: 500, color: "#fff", marginBottom: 4 }}>New theme</div>
        <div style={{ fontSize: 12.5, color: "#9aa6bd", marginBottom: 14 }}>
          Draft a <span className="font-mono">universe_register.json</span> entry for a PR. This never writes —
          admission still runs the §11 source∩screen∩OTM rule, and the gate disposes on cheapness.
        </div>
        <div className="grid grid-cols-2" style={{ gap: 12, marginBottom: 12 }}>
          <div>
            <label style={labelStyle}>theme name (snake_case)</label>
            <input style={inputStyle} value={name} onChange={(e) => setName(e.target.value)} placeholder="av_autonomy" />
          </div>
          <div>
            <label style={labelStyle}>cluster (blank → theme name)</label>
            <input style={inputStyle} value={cluster} onChange={(e) => setCluster(e.target.value)} placeholder="ai_compute" />
          </div>
        </div>
        <label style={labelStyle}>thesis (the secular backdrop)</label>
        <textarea style={{ ...inputStyle, minHeight: 56, marginBottom: 12 }} value={thesis}
                  onChange={(e) => setThesis(e.target.value)} />
        <label style={labelStyle}>falsifier (what would kill it)</label>
        <textarea style={{ ...inputStyle, minHeight: 56, marginBottom: 12 }} value={falsifier}
                  onChange={(e) => setFalsifier(e.target.value)} />
        <label style={labelStyle}>source (ETF holdings URL / constituent file)</label>
        <input style={{ ...inputStyle, marginBottom: 14 }} value={source} onChange={(e) => setSource(e.target.value)} />
        <button style={btnStyle} onClick={() => void onTheme()}>Draft theme entry</button>
        {themeErr && <div style={{ marginTop: 10, color: signal.bad.text, fontSize: 12.5 }}>draft failed: {themeErr}</div>}
        {theme && !theme.valid && (
          <div style={{ marginTop: 10, color: signal.warn.text, fontSize: 12.5 }}>
            Incomplete — {theme.problems.join("; ")}
          </div>
        )}
        {theme && theme.valid && (
          <>
            <pre style={preStyle}>{theme.json}</pre>
            {theme.warnings.length > 0 && (
              <div style={{ marginTop: 8, color: signal.warn.text, fontSize: 12 }}>⚠ {theme.warnings.join(" ")}</div>
            )}
            <div style={{ marginTop: 6, fontSize: 11.5, color: "#7c89a1" }}>
              Copy into a PR against universe_register.json — or paste it to your agent to open the PR.
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
