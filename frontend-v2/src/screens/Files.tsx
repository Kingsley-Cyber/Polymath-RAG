import { api } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { controlReady, docVnext, semanticReady, vnextReady } from "../lib/readiness";
import { ReadinessTriad } from "../components/ReadinessTriad";
import { Pill } from "../components/Pill";

/**
 * F8 — Files (FRONTEND-V2-PLAN §7).
 *
 * Three DISTINCT readiness concepts, never one badge, and per document the backend's
 * own counts: Graph · Profile · Atoms · pMAP (eligible/mapped/excluded/unresolved).
 * An under-mapped document renders RED. Nothing here is manufactured green.
 */
export function Files({ corpusId }: { corpusId: string }) {
  const cp = useAsync((s) => api.controlPlane(corpusId, s), [corpusId]);
  const sr = useAsync((s) => api.semanticReadiness(corpusId, s), [corpusId]);
  const docs = useAsync((s) => api.documentSummaries(corpusId, s), [corpusId]);

  const summaries = docs.data?.summaries ?? {};
  const ids = Object.keys(summaries);
  const readyCount = ids.filter((id) => summaries[id]!.vnext_ready).length;

  return (
    <div className="screen screen--wide">
      <div className="screen__head">
        <h1 className="screen__title">Files</h1>
        <p className="screen__sub">
          <span className="mono">{corpusId}</span> — {ids.length} documents,{" "}
          <b>{readyCount}</b> vNext-ready, <b>{ids.length - readyCount}</b> blocked
        </p>
      </div>

      <ReadinessTriad
        control={controlReady(cp.data?.control_ready)}
        semantic={semanticReady(sr.data)}
        vnext={vnextReady(sr.data)}
      />

      {docs.error && <div className="banner banner--bad" style={{ marginTop: 14 }}>{docs.error}</div>}

      <div className="card" style={{ marginTop: 14, overflowX: "auto" }}>
        <table className="t">
          <thead>
            <tr>
              <th>Document</th><th>vNext</th><th>Parents</th><th>Children</th>
              <th>pMAP eligible</th><th>mapped</th><th>excluded</th><th>unresolved</th>
              <th>Profile</th><th>Graph ent.</th><th>Graph rel.</th>
            </tr>
          </thead>
          <tbody>
            {ids.map((id) => {
              const d = summaries[id]!;
              const v = docVnext(d);
              return (
                <tr key={id}>
                  <td className="mono" title={id}>{id.slice(0, 18)}…</td>
                  <td><Pill v={v} /></td>
                  <td className="mono">{d.parents}</td>
                  <td className="mono">{d.children}</td>
                  <td className="mono">{d.map_eligible}</td>
                  <td className="mono">{d.map_active}</td>
                  <td className="mono">{d.map_excluded}</td>
                  <td className="mono" style={{ color: d.map_unresolved > 0 ? "var(--bad)" : undefined }}>
                    {d.map_unresolved}
                  </td>
                  <td className="mono">
                    {d.profile_vnext ? <span className="pill pill--ready">vNext</span>
                      : d.profile_present ? <span className="pill pill--degraded">legacy</span>
                      : <span className="pill pill--blocked">none</span>}
                  </td>
                  <td className="mono">{d.graph_entities}</td>
                  <td className="mono">{d.graph_relations}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!ids.length && !docs.loading && <div className="empty">No documents in this corpus.</div>}
      </div>

      <div className="faint" style={{ marginTop: 10, fontSize: 12 }}>
        Atoms and pMAP are ROUTING artifacts — they explain why a source is findable, not what an answer rests on.
      </div>
    </div>
  );
}
