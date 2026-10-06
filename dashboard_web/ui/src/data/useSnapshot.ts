import { useCallback, useEffect, useState } from "react";

import type { Snapshot } from "./types";

// Same-origin by default (the Vite dev proxy / the built bundle's host forwards /api → the FastAPI service).
const API_BASE = import.meta.env.VITE_API_BASE ?? "";
const MIN_SPIN_MS = 650; // keep the 3px indeterminate bar visible long enough to read as a refresh
// E1: opt-in auto-refresh so an always-on surface shows a degradation without a human clicking ↻. Aligned with
// the server's ~60s TTL cache (so a poll usually hits the cache, not a rebuild). Set VITE_POLL_MS=0 to disable.
const POLL_MS = Number(import.meta.env.VITE_POLL_MS ?? 60_000);

export interface SnapshotState {
  snapshot: Snapshot | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** One read-only fetch of the whole snapshot; `refresh()` re-fetches (bypassing the server cache). Polls every
 *  POLL_MS while the tab is visible (silent — no loading flash), and refetches on tab re-focus. */
export function useSnapshot(): SnapshotState {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (opts?: { bypassCache?: boolean; silent?: boolean }) => {
    if (!opts?.silent) setLoading(true);
    setError(null);
    const started = Date.now();
    try {
      const url = `${API_BASE}/api/snapshot${opts?.bypassCache ? "?nocache=1" : ""}`;
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSnapshot((await res.json()) as Snapshot);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (!opts?.silent) {
        const wait = Math.max(0, MIN_SPIN_MS - (Date.now() - started));
        window.setTimeout(() => setLoading(false), wait);
      }
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Auto-refresh while visible; pause when hidden, refetch on re-focus (don't poll a backgrounded tab).
  useEffect(() => {
    if (!POLL_MS) return;
    const tick = () => {
      if (document.visibilityState === "visible") void load({ silent: true });
    };
    const id = window.setInterval(tick, POLL_MS);
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [load]);

  return { snapshot, loading, error, refresh: () => void load({ bypassCache: true }) };
}
