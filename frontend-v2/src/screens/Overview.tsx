import { api } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { controlReady, semanticReady, vnextReady } from "../lib/readiness";
import { ReadinessTriad } from "../components/ReadinessTriad";

/**
 * F1 landing surface: the readiness triad for the selected corpus, proving the shell
 * reaches real backend authority. The legacy `query_ready` boolean is shown ONLY as a
 * counter-example (plan §7).
 */
export function Overview({ corpusId }: { corpusId: string }) {
  const cp = useAsync((s) => api.controlPlane(corpusId, s), [corpusId]);
  const sr = useAsync((s) => api.semanticReadiness(corpusId, s), [corpusId]);
  const corpora = useAsync((s) => api.corpora(s), []);

  const corpus = corpora.data?.find((c) => c.corpus_id === corpusId);
  const err = cp.error ?? sr.error;

  return (
    <div className="screen">
      <div className="screen__head">
        <h1 className="screen__title">Overview</h1>
        <p className="screen__sub">
          Readiness for <span className="mono">{corpusId}</span> — three distinct concepts, read from the backend.
        </p>
      </div>

      {err && <div className="banner banner--bad" style={{ marginBottom: 14 }}>{err}</div>}

      <ReadinessTriad
        control={controlReady(cp.data?.control_ready)}
        semantic={semanticReady(sr.data)}
        vnext={vnextReady(sr.data)}
      />

      {corpus && (
        <div className="card" style={{ marginTop: 14 }}>
          <div className="label" style={{ marginBottom: 8 }}>Why the legacy badge is not used</div>
          <div className="row">
            <span className="mono dim">query_ready</span>
            <span className="mono">{String(corpus.query_ready)}</span>
            <span className="faint">·</span>
            <span className="mono dim">query_enabled</span>
            <span className="mono">{String(corpus.query_enabled)}</span>
            <span className="faint">·</span>
            <span className="mono dim">documents</span>
            <span className="mono">{corpus.documents}</span>
          </div>
          <div className="dim" style={{ marginTop: 8, fontSize: 12.5 }}>
            <code>query_ready</code> is a single boolean that can read <code>true</code> while the corpus is
            semantically incomplete. V2 never uses it as a readiness signal — the three verdicts above are the
            contract (FRONTEND-V2-PLAN §7).
          </div>
        </div>
      )}

      {sr.data && (
        <div className="card" style={{ marginTop: 14 }}>
          <div className="label" style={{ marginBottom: 8 }}>Semantic counts ({sr.data.contract})</div>
          <table className="t">
            <tbody>
              {Object.entries(sr.data.counts ?? {}).map(([k, v]) => (
                <tr key={k}>
                  <td className="dim" style={{ width: 240 }}>{k}</td>
                  <td className="mono">{typeof v === "number" ? v.toLocaleString() : String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {sr.data.vnext?.pending?.length > 0 && (
            <div className="banner" style={{ marginTop: 12 }}>
              vNext pending: <span className="mono">{sr.data.vnext.pending.join(", ")}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
