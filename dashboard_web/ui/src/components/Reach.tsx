import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";

import { color, signal } from "../theme/tokens";
import { Card, Chip, Skeleton } from "./primitives";

// ── The Reach panel: RENDER-ONLY (charter: records/2026-07-14_reach_channels_charter_RATIFIED.md) ──
// Shows the newest weekly survivor-cards document (primary) and the newest weekly digest (secondary,
// collapsed "raw layer — audit trail"). NO action affordances anywhere — no pick buttons, no forms,
// no write path; picks happen in the operator's session. NO ranking/reordering — the documents render
// verbatim in document order.

// Same-origin in prod; the Vite dev proxy forwards /api → :8602 (mirrors useSnapshot/Curation).
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export interface ReachDoc {
  available: boolean;
  reason?: string;
  filename?: string;
  week?: string;
  content?: string;
  mtime?: string;
  generated?: string | null;
}
export interface ReachPayload {
  cards: ReachDoc;
  digest: ReachDoc;
}

// Staleness honesty (the dashboards' n=0 rule generalized): the digest cadence is weekly, so a
// digest older than 8 days means a missed week → an explicit "stale" pill, never a silent old doc.
export const STALE_AFTER_DAYS = 8;

/** The document's own generation stamp when present, else the file mtime (a checkout resets mtime). */
export function docTimestamp(doc: ReachDoc | null | undefined): Date | null {
  const iso = doc?.generated ?? doc?.mtime;
  if (!iso) return null;
  const t = new Date(iso);
  return Number.isNaN(t.getTime()) ? null : t;
}

export function isStale(doc: ReachDoc | null | undefined, now: Date = new Date()): boolean {
  const t = docTimestamp(doc);
  if (!t) return false; // unknown age renders as "—", not as a false alarm
  return now.getTime() - t.getTime() > STALE_AFTER_DAYS * 24 * 3600 * 1000;
}

function fmtTime(t: Date | null): string {
  return t ? t.toISOString().slice(0, 16).replace("T", " ") + "Z" : "—";
}

// ── Minimal SAFE markdown renderer ─────────────────────────────────────────────────────────────
// The documents are machine-generated (survivor_cards.assemble_cards / digest.assemble), but they
// embed fetched headline text, so everything renders through React TEXT NODES (auto-escaped) —
// NO dangerouslySetInnerHTML anywhere. The only elements created are headings/paragraphs/list rows,
// plus anchors for tokens that are verbatim http(s) URLs. Line order is preserved (no reordering).

const linkStyle: CSSProperties = { color: color.accent, textDecoration: "none", wordBreak: "break-all" };

function linkify(text: string, keyBase: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /https?:\/\/[^\s)]+/g;
  let last = 0;
  let i = 0;
  for (let m = re.exec(text); m !== null; m = re.exec(text)) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    parts.push(
      <a key={`${keyBase}-a${i++}`} href={m[0]} target="_blank" rel="noopener noreferrer" style={linkStyle}>
        {m[0]}
      </a>,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

const h1Style: CSSProperties = { fontSize: 17, fontWeight: 600, color: "#141b28", margin: "2px 0 10px", letterSpacing: "-.2px" };
const h2Style: CSSProperties = { fontSize: 14.5, fontWeight: 600, color: "#141b28", fontFamily: "'Roboto Mono', monospace", margin: "18px 0 8px", paddingTop: 14, borderTop: "1px solid #edf0f4" };
const h3Style: CSSProperties = { fontSize: 12.5, fontWeight: 600, color: "#414956", margin: "12px 0 6px" };
const pStyle: CSSProperties = { fontSize: 12.5, color: "#2c3645", lineHeight: 1.6, margin: "6px 0" };

/** Line-based markdown → React elements, in document order. Exported for the vitest render test. */
export function renderMarkdown(md: string): ReactNode[] {
  const out: ReactNode[] = [];
  md.split("\n").forEach((raw, n) => {
    const key = `l${n}`;
    const line = raw.replace(/\s+$/, "");
    if (!line.trim()) return; // spacing comes from block margins
    if (line.startsWith("### ")) {
      out.push(<div key={key} role="heading" aria-level={3} style={h3Style}>{linkify(line.slice(4), key)}</div>);
      return;
    }
    if (line.startsWith("## ")) {
      out.push(<div key={key} role="heading" aria-level={2} style={h2Style}>{linkify(line.slice(3), key)}</div>);
      return;
    }
    if (line.startsWith("# ")) {
      out.push(<div key={key} role="heading" aria-level={1} style={h1Style}>{linkify(line.slice(2), key)}</div>);
      return;
    }
    const li = /^(\s*)- (.*)$/.exec(line);
    if (li) {
      const depth = Math.min(4, Math.floor(li[1].length / 2));
      out.push(
        <div key={key} className="flex" style={{ gap: 8, padding: "1.5px 0", paddingLeft: depth * 18, fontSize: 12.5, color: depth ? "#414956" : "#2c3645", lineHeight: 1.55 }}>
          <span aria-hidden="true" style={{ flex: "none", color: "#8b919b" }}>{depth ? "·" : "•"}</span>
          <span style={{ minWidth: 0, wordBreak: "break-word" }}>{linkify(li[2], key)}</span>
        </div>,
      );
      return;
    }
    // italic convention used by the Stage-B seam: _(…)_ → <em>
    const em = /^_(.*)_$/.exec(line.trim());
    if (em) {
      out.push(<div key={key} style={{ ...pStyle, fontStyle: "italic", color: "#5f6675" }}>{linkify(em[1], key)}</div>);
      return;
    }
    out.push(<div key={key} style={pStyle}>{linkify(line, key)}</div>);
  });
  return out;
}

// ── The panel ──────────────────────────────────────────────────────────────────────────────────

function AbsentCard({ what, doc, hint }: { what: string; doc: ReachDoc; hint: string }) {
  return (
    <Card style={{ padding: "20px 22px" }}>
      <div className="flex items-center" style={{ gap: 12 }}>
        <span style={{ fontSize: 20, color: "#8b919b" }}>◌</span>
        <div>
          <div style={{ fontSize: 13.5, fontWeight: 500, color: "#2c3645" }}>No {what} yet</div>
          <div className="font-mono" style={{ fontSize: 11.5, color: "#5f6675", marginTop: 3 }}>{doc.reason ?? "unavailable"}</div>
          <div style={{ fontSize: 11.5, color: "#5f6675", marginTop: 3 }}>{hint}</div>
        </div>
      </div>
    </Card>
  );
}

export function Reach() {
  const [payload, setPayload] = useState<ReachPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [digestOpen, setDigestOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/reach`, { headers: { Accept: "application/json" } });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body = (await res.json()) as ReachPayload;
        if (alive) setPayload(body);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (error) {
    return (
      <Card style={{ borderColor: signal.bad.border, padding: 20 }}>
        <div style={{ color: signal.bad.text, fontSize: 13 }}>Couldn’t load /api/reach: {error}. Is the API running on :8602?</div>
      </Card>
    );
  }
  if (!payload) {
    return (
      <div className="flex flex-col" style={{ gap: 16 }}>
        <Skeleton height={64} />
        <Skeleton height={280} />
      </div>
    );
  }

  const { cards, digest } = payload;
  const cardsTime = docTimestamp(cards);
  const digestTime = docTimestamp(digest);
  const stale = isStale(digest);

  return (
    <div className="flex flex-col" style={{ gap: 16 }}>
      {/* header: week stamp + generated time + staleness hint. Render-only — no pick affordances. */}
      <Card style={{ padding: "16px 20px" }}>
        <div className="flex items-center flex-wrap" style={{ gap: 10 }}>
          <div style={{ flex: 1, minWidth: 220 }}>
            <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>Weekly reach documents</div>
            <div style={{ fontSize: 12, color: "#414956", marginTop: 2, lineHeight: 1.5 }}>
              Survivor cards (primary) over the raw digest (audit trail). Render-only — picks happen in the
              operator’s session, never here.
            </div>
          </div>
          <Chip level="acc">{cards.week ?? digest.week ?? "no week yet"}</Chip>
          <Chip level="mute">
            <span className="font-mono">cards {fmtTime(cardsTime)} · digest {fmtTime(digestTime)}</span>
          </Chip>
          {stale && <Chip level="warn">stale — digest older than {STALE_AFTER_DAYS} days</Chip>}
        </div>
      </Card>

      {/* primary: the survivor-cards document, verbatim document order */}
      {cards.available && cards.content ? (
        <Card style={{ padding: "20px 22px" }}>
          <div className="flex items-baseline justify-between" style={{ gap: 10, marginBottom: 6 }}>
            <div style={{ fontSize: 14, fontWeight: 500, color: "#141b28" }}>
              Survivor cards <span style={{ color: "#6a7280", fontWeight: 400 }}>· charter §3b — no ranking, document order</span>
            </div>
            <span className="font-mono" style={{ fontSize: 11, color: "#5f6675" }}>records/cards/{cards.filename}</span>
          </div>
          <div>{renderMarkdown(cards.content)}</div>
        </Card>
      ) : (
        <AbsentCard
          what="survivor-cards document"
          doc={cards}
          hint="Run scripts/survivor_cards_run.py after the weekly digest lands."
        />
      )}

      {/* secondary: the raw digest, collapsed by default (a view toggle, not an action) */}
      <Card style={{ padding: 0 }}>
        <button
          onClick={() => setDigestOpen((o) => !o)}
          aria-expanded={digestOpen}
          className="w-full flex items-center text-left"
          style={{ gap: 10, padding: "16px 20px", background: "none", border: "none", cursor: "pointer" }}
        >
          <span aria-hidden="true" style={{ color: "#5f6675", fontSize: 11 }}>{digestOpen ? "▾" : "▸"}</span>
          <span style={{ flex: 1, fontSize: 14, fontWeight: 500, color: "#141b28" }}>
            Raw digest <span style={{ color: "#6a7280", fontWeight: 400 }}>· raw layer — audit trail</span>
          </span>
          <span className="font-mono" style={{ fontSize: 11, color: "#5f6675" }}>
            {digest.available ? `records/digests/${digest.filename}` : "unavailable"}
          </span>
        </button>
        {digestOpen &&
          (digest.available && digest.content ? (
            <div style={{ padding: "0 20px 18px", maxHeight: 520, overflowY: "auto", borderTop: "1px solid #edf0f4" }}>
              {renderMarkdown(digest.content)}
            </div>
          ) : (
            <div style={{ padding: "0 20px 18px", borderTop: "1px solid #edf0f4" }}>
              <div style={{ fontSize: 12.5, color: "#5f6675", paddingTop: 12 }}>
                No digest document yet — <span className="font-mono">{digest.reason ?? "unavailable"}</span>. Run
                scripts/digest_weekly.py.
              </div>
            </div>
          ))}
      </Card>
    </div>
  );
}
