import { useEffect, useRef, useState } from "react";

// F2: animate an integer 0 → value with rAF (easeOutCubic, ~450ms). Used for the prominent readiness ring.
// Snaps (no animation) when the user prefers reduced motion or rAF is unavailable (e.g. jsdom in tests), so
// it is safe to render anywhere.
const prefersReduced = (): boolean =>
  typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;

export function useCountUp(value: number, ms = 450): number {
  const [n, setN] = useState(value);
  const prev = useRef(value);

  useEffect(() => {
    const to = value;
    if (to === prev.current || prefersReduced() || typeof requestAnimationFrame !== "function") {
      setN(to);
      prev.current = to;
      return;
    }
    let raf = 0;
    let start = 0;
    const step = (t: number) => {
      if (!start) start = t;
      const p = Math.min(1, (t - start) / ms);
      setN(Math.round(to * (1 - Math.pow(1 - p, 3)))); // count up from 0, easeOutCubic
      if (p < 1) raf = requestAnimationFrame(step);
      else prev.current = to;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);

  return n;
}
