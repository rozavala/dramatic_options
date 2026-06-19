// Section identity + chrome copy, shared by the rail, the topbar, and the Overview section cards
// (a neutral module so App and SectionCards don't import each other).

export type SectionId = "overview" | "safety" | "edge" | "pipeline" | "book";

export const NAV: { id: SectionId; label: string; sub: string }[] = [
  { id: "overview", label: "Overview", sub: "status · KPIs · go-live" },
  { id: "safety", label: "Safety & Risk", sub: "limits · council health" },
  { id: "edge", label: "The Edge", sub: "does the brain help?" },
  { id: "pipeline", label: "Pipeline", sub: "where ideas stop" },
  { id: "book", label: "Book & Data", sub: "positions · scanning" },
];

export const TITLES: Record<SectionId, [string, string]> = {
  overview: ["Overview", "One glance: is it healthy, and are we getting closer to go-live?"],
  safety: ["Safety & Risk", "Is the book within its limits, and is the AI council deliberating cleanly?"],
  edge: ["The Edge", "Does the gate + AI council actually beat running brain-off?"],
  pipeline: ["Pipeline", "Where do candidate ideas stop, and why?"],
  book: ["Book & Data", "What’s held, what’s being watched, and what data has accrued."],
};
