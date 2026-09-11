import { useState } from "react";
import { api } from "../lib/api";
import { useAsync } from "../lib/useAsync";

/**
 * F9 — Graph (FRONTEND-V2-PLAN §8).
 *
 * "Only source-attested relationships may appear as canonical truth."
 *
 * What the backend actually serves today is the PREDICATE DISTRIBUTION
 * (`/control_plane/predicates`). There is NO entity-search or relationship-browse
 * contract — `/openapi.json` has no graph route at all (GAP-7, recorded in the F0
 * inventory). The one place graph relationships reach a user WITH their supporting
 * source chunks is a GRAPH-mode chat turn, whose receipt carries `graph_fact_count`,
 * `graph_seeds` and `graph_bounds`.
 *
 * So this screen shows what exists and names what does not, rather than rendering an
 * entity browser over data the backend cannot attest.
 */
export function Graph({ corpusId, onOpenChat }: { corpusId: string; onOpenChat: () => void }) {
  const [n, setN] = useState(25);
  const preds = useAsync((s) => api.predicates(corpusId, n, s), [corpusId, n]);
  const caps = useAsync((s) => api.capabilities(s), []);

  const rows = extractRows(preds.data);

  return (
    <div className="screen">
      <div className="screen__head">
        <h1 className="screen__title">Graph</h1>
        <p className="screen__sub">
          Source-attested relationships for <span className="mono">{corpusId}</span>
        </p>
      </div>

      <div className="banner banner--info" style={{ marginBottom: 14 }}>
        <b>Entity search and relationship browsing have no backend contract yet</b> (GAP-7): there is no graph
        route in the API. Graph relationships reach a reader today through a <b>GRAPH-mode chat turn</b>, whose
        receipt carries the graph facts and the source chunks that attest them.{" "}
        <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }} onClick={onOpenChat}>
          Open Chat in GRAPH mode
        </button>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
          <div className="label">Predicate distribution (what the extractor actually produced)</div>
          <select value={n} onChange={(e) => setN(Number(e.target.value))}>
            {[10, 25, 50].map((k) => <option key={k} value={k}>top {k}</option>)}
          </select>
        </div>
        {preds.error && <div className="banner banner--bad">{preds.error}</div>}
        {preds.loading && <div className="faint">loading…</div>}
        {rows.length > 0 && (
          <table className="t">
            <thead><tr><th>Predicate</th><th>Count</th><th>Share</th></tr></thead>
            <tbody>
              {rows.map(([name, count]) => {
                const total = rows.reduce((a, [, c]) => a + c, 0) || 1;
                return (
                  <tr key={name}>
                    <td className="mono">{name}</td>
                    <td className="mono">{count.toLocaleString()}</td>
                    <td className="mono faint">{((count / total) * 100).toFixed(1)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        {!preds.loading && !rows.length && !preds.error && (
          <div className="empty">No predicate distribution returned for this corpus.</div>
        )}
      </div>

      {caps.data != null && (
        <details style={{ marginTop: 14 }}>
          <summary className="label" style={{ cursor: "pointer" }}>Backend capabilities</summary>
          <pre className="mono" style={{ marginTop: 8, fontSize: 11.5, background: "var(--bg-sunken)",
                                          padding: 10, borderRadius: 6, overflow: "auto", maxHeight: 260 }}>
            {JSON.stringify(caps.data, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

/** The predicates payload shape is not pinned by a contract; accept the obvious forms. */
function extractRows(d: unknown): [string, number][] {
  if (!d || typeof d !== "object") return [];
  const o = d as Record<string, unknown>;
  for (const key of ["predicates", "rows", "distribution", "top"]) {
    const v = o[key];
    if (Array.isArray(v)) {
      return v.map((x) => {
        const r = x as Record<string, unknown>;
        const name = String(r.predicate ?? r.name ?? r.key ?? "?");
        const cnt = Number(r.count ?? r.n ?? r.total ?? 0);
        return [name, cnt] as [string, number];
      }).filter(([, c]) => Number.isFinite(c));
    }
    if (v && typeof v === "object") {
      return Object.entries(v as Record<string, unknown>)
        .map(([k, c]) => [k, Number(c)] as [string, number])
        .filter(([, c]) => Number.isFinite(c));
    }
  }
  return [];
}
