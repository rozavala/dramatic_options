// Section identity + chrome copy, shared by the rail, the topbar and the mobile tab bar (a neutral module
// so App and the sections don't import each other). Ids are stable (the mobile app switches on them);
// the 2026-09 simplification changed labels/subtitles only.

export type SectionId = "overview" | "safety" | "edge" | "pipeline" | "book" | "reach" | "curation";

export const NAV: { id: SectionId; label: string; sub: string }[] = [
  { id: "overview", label: "Overview", sub: "today · is it safe · go-live" },
  { id: "safety", label: "Risk & Feeds", sub: "frame · clusters · tripwires · spend" },
  { id: "pipeline", label: "Council & Pipeline", sub: "last session · why nothing passed" },
  { id: "book", label: "Book & Watchlist", sub: "positions · sentinels · data" },
  { id: "edge", label: "Edge", sub: "brain-on vs brain-off · accruing" },
  { id: "reach", label: "Reach", sub: "weekly cards · digest" },
  { id: "curation", label: "Tools", sub: "feasibility screen · draft a theme" },
];

export const TITLES: Record<SectionId, [string, string]> = {
  overview: ["Overview", "What changed since yesterday, and is it safe to keep running?"],
  safety: ["Risk & Feeds", "Is the book inside its frame, and are the data feeds and the council behaving?"],
  pipeline: ["Council & Pipeline", "What did the council decide last session, and where do ideas stop?"],
  book: ["Book & Watchlist", "What is held, what is being watched, and what data has actually accrued."],
  edge: ["Edge", "Does gate + council beat brain-off? Nothing has resolved yet — here is when it will."],
  reach: ["Reach", "The weekly survivor cards + raw digest — render-only; picks happen in the operator’s session."],
  curation: ["Tools", "Draft a feasibility-screen command or a new theme — keyless, never writes."],
};
