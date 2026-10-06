import type { CheapnessPanel } from "../data/types";
import { color } from "../theme/tokens";
import { Card } from "./primitives";

// Finding #1's instrument (PREREG_CHEAPNESS_WATCH), ported from the Streamlit :8601 dashboard. Read-only.
export function CheapnessWatch({ data }: { data: CheapnessPanel | null }) {
  return (
    <Card style={{ padding: 18 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: "#141b28" }}>Cheapness-watch (finding #1)</div>
      <div style={{ fontSize: 11.5, color: "#5f6675", margin: "3px 0 12px", lineHeight: 1.45 }}>
        When a staged name breaks, is there a cheap-entry window that co-occurs with stale markers (the §7.1
        harm)? <b>insufficient_N</b> is the expected reading — the harm is conjunctively rare; interpretable
        only once curation gives the cohort break-capable names.
      </div>
      {!data ? (
        <div style={{ fontSize: 12, color: "#7c89a1" }}>accruing — no cheapness observations yet.</div>
      ) : (
        <>
          <div className="flex items-center" style={{ gap: 14, flexWrap: "wrap" }}>
            <span className="font-mono" style={{ fontSize: 16, fontWeight: 700, color: color.ink }}>{data.verdict}</span>
            <span style={{ fontSize: 12, color: "#5f6675" }}>
              breaks {data.n_breaks} · qualifying {data.n_qualifying} · never-cheap {data.n_never_cheap} · fresh{" "}
              {data.n_fresh_marker}
              {data.qualifying_per_quarter != null ? ` · ${data.qualifying_per_quarter.toFixed(2)}/qtr` : ""}
            </span>
          </div>
          {data.latest_by_name && data.latest_by_name.length > 0 && (
            <table style={{ width: "100%", marginTop: 12, fontSize: 11.5, borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ color: "#7c89a1", textAlign: "left" }}>
                  <th style={{ padding: "4px 8px" }}>symbol</th>
                  <th style={{ padding: "4px 8px" }}>as of</th>
                  <th style={{ padding: "4px 8px" }}>cheap</th>
                  <th style={{ padding: "4px 8px" }}>iv/rv</th>
                  <th style={{ padding: "4px 8px" }}>marker age (d)</th>
                </tr>
              </thead>
              <tbody>
                {data.latest_by_name.map((r) => (
                  <tr key={r.symbol} style={{ borderTop: "1px solid #eef2f8" }}>
                    <td className="font-mono" style={{ padding: "4px 8px", fontWeight: 600 }}>{r.symbol}</td>
                    <td style={{ padding: "4px 8px" }}>{(r.as_of ?? "").slice(0, 10)}</td>
                    <td style={{ padding: "4px 8px" }}>{r.cheap == null ? "—" : r.cheap ? "yes" : "no"}</td>
                    <td style={{ padding: "4px 8px" }}>{r.iv_rv == null ? "—" : r.iv_rv.toFixed(2)}</td>
                    <td style={{ padding: "4px 8px" }}>{r.marker_age_days == null ? "—" : r.marker_age_days.toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </Card>
  );
}
