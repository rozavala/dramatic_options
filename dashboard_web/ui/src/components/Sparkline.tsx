import { signal } from "../theme/tokens";

// SVG polyline over an equity series (viewBox 0 0 150 34), green if last ≥ first else red.
// Ported from the prototype's spark(); renders nothing for <2 points.
export function Sparkline({ series, height = 26 }: { series: { equity: number }[]; height?: number }) {
  if (!series || series.length < 2) return null;
  const W = 150;
  const H = 34;
  const ys = series.map((p) => p.equity);
  const mn = Math.min(...ys);
  const mx = Math.max(...ys);
  const rg = mx - mn || 1;
  const n = series.length;
  const d =
    "M" +
    series
      .map((p, i) => `${((i / (n - 1)) * W).toFixed(1)} ${(H - 3 - ((p.equity - mn) / rg) * (H - 6)).toFixed(1)}`)
      .join(" L");
  const up = ys[n - 1] >= ys[0];
  return (
    <svg viewBox="0 0 150 34" preserveAspectRatio="none" style={{ width: "100%", height, display: "block", marginTop: 8, overflow: "visible" }}>
      <path d={d} fill="none" stroke={up ? signal.ok.text : signal.bad.text} strokeWidth={2.5} vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
