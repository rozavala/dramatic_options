import { useCallback, useEffect, useState } from "react";

import type { Snapshot } from "./types";

// Same-origin by default (the Vite dev proxy / the built bundle's host forwards /api → the FastAPI service).
const API_BASE = import.meta.env.VITE_API_BASE ?? "";
const MIN_SPIN_MS = 650; // keep the 3px indeterminate bar visible long enough to read as a refresh

export interface SnapshotState {
  snapshot: Snapshot | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** One read-only fetch of the whole snapshot; `refresh()` re-fetches (the ↻ button). */
export function useSnapshot(): SnapshotState {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const started = Date.now();
    try {
      const res = await fetch(`${API_BASE}/api/snapshot`, { headers: { Accept: "application/json" } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSnapshot((await res.json()) as Snapshot);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      const wait = Math.max(0, MIN_SPIN_MS - (Date.now() - started));
      window.setTimeout(() => setLoading(false), wait);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { snapshot, loading, error, refresh: load };
}
