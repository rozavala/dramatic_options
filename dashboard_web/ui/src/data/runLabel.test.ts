import { describe, expect, it } from "vitest";

import { etDate, formatEtStamp, formatRunLabel, parseBackendTs, runLabel } from "./runLabel";

describe("run label formatter (#354)", () => {
  it("formats the canonical example: L1 #1816 · Mon 2026-10-26 15:45 ET", () => {
    expect(formatRunLabel(1816, "2026-10-26T19:45:00+00:00")).toBe("L1 #1816 · Mon 2026-10-26 15:45 ET");
  });

  it("treats SQLite's naive datetime('now') as UTC", () => {
    expect(parseBackendTs("2026-09-04 19:45:04")).toBe(Date.parse("2026-09-04T19:45:04Z"));
    expect(formatEtStamp("2026-09-04 19:45:04")).toBe("Fri 2026-09-04 15:45 ET");
  });

  // The whole point of rendering in ET: the UTC calendar date and the ET calendar date differ for 4–5h a night.
  it("near-midnight UTC: 02:30Z on the 27th is still Monday the 26th in ET", () => {
    expect(formatEtStamp("2026-10-27T02:30:00+00:00")).toBe("Mon 2026-10-26 22:30 ET");
    expect(etDate("2026-10-27 02:30:00")).toBe("2026-10-26");
  });

  it("near-midnight UTC: 03:59Z → 23:59 ET the day before; 04:00Z → 00:00 ET (EDT, no 24:00)", () => {
    expect(formatEtStamp("2026-10-27T03:59:00Z")).toBe("Mon 2026-10-26 23:59 ET");
    expect(formatEtStamp("2026-10-27T04:00:00Z")).toBe("Tue 2026-10-27 00:00 ET");
  });

  it("near-midnight UTC across the fall-back: 04:30Z on 11-02 is EST (UTC-5) → Sun 11-01 23:30", () => {
    expect(formatEtStamp("2026-11-02T04:30:00Z")).toBe("Sun 2026-11-01 23:30 ET");
  });

  it("a year-boundary run keeps its ET year", () => {
    expect(etDate("2027-01-01T03:00:00Z")).toBe("2026-12-31");
  });

  it("never prints a bare run id: an undated run says so", () => {
    expect(formatRunLabel(7, null)).toBe("L1 #7 · date unavailable");
    expect(formatRunLabel(7, "not a date")).toBe("L1 #7 · date unavailable");
    expect(formatRunLabel(null, "2026-10-26T19:45:00Z")).toBe("—");
  });

  it("looks the date up in the snapshot's run_dates map; tolerates an {error} / missing map", () => {
    const dates = { "1816": "2026-10-26 19:45:03" };
    expect(runLabel(dates, 1816)).toBe("L1 #1816 · Mon 2026-10-26 15:45 ET");
    expect(runLabel(dates, 1817)).toBe("L1 #1817 · date unavailable");
    expect(runLabel({ error: "OperationalError: boom" }, 1816)).toBe("L1 #1816 · date unavailable");
    expect(runLabel(null, 1816)).toBe("L1 #1816 · date unavailable");
    expect(runLabel(dates, null)).toBe("—");
  });
});
