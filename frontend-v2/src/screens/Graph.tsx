import { useState } from "react";
import { api } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import type { GraphEntity } from "../lib/contracts";

/**
 * F9 — Graph (FRONTEND-V2-PLAN §8), on GRAPH-BROWSE-V1.
 *
 * "Only source-attested relationships may appear as canonical truth." The backend
 * enforces that: a relationship is served only when Postgres `evidence` ties its
 * fact to a chunk in THIS corpus. Anything unattested is withheld and COUNTED, so
 * the absence is visible rather than silent.
 */
export function Graph({ corpusId }: { corpusId: string }) {
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const [picked, setPicked] = useState<GraphEntity | null>(null);

  const ents = useAsync((s) => api.graphEntities(corpusId, term, 25, s), [corpusId, term]);
  const rels = useAsync(
    (s) => (picked?.entity_id
      ? api.graphRelationships(picked.entity_id, corpusId, 25, s)
      : Promise.resolve(null)),
    [picked?.entity_id, corpusId]);

  return (
    <div className="screen screen--wide">
      <div className="screen__head">
        <h1 className="screen__title">Graph</h1>
        <p className="screen__sub">
          Source-attested relationships in <span className="mono">{corpusId}</span>
        </p>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <div className="row">
          <input type="text" style={{ flex: 1, minWidth: 260 }}
                 placeholder="Search entities by surface…"
                 value={q} onChange={(e) => setQ(e.target.value)}
                 onKeyDown={(e) => { if (e.key === "Enter") setTerm(q); }} />
          <button className="btn btn--primary" onClick={() => setTerm(q)}>Search</button>
          {term && <button className="btn" onClick={() => { setQ(""); setTerm(""); setPicked(null); }}>Clear</button>}
        </div>
      </div>

      <div className="grid grid--2">
        <div className="card">
          <div className="label" style={{ marginBottom: 8 }}>
            Entities {term ? <>matching <span className="mono">{term}</span></> : "(most attested)"}
          </div>
          {ents.error && <div className="banner banner--bad">{ents.error}</div>}
          {ents.loading && <div className="faint">loading…</div>}
          <table className="t">
            <thead><tr><th>Surface</th><th>Type</th><th>Mentions</th><th>Docs</th></tr></thead>
            <tbody>
              {(ents.data?.entities ?? []).map((e) => (
                <tr key={e.normalized_surface}
                    style={{ cursor: e.entity_id ? "pointer" : "default",
                             background: picked?.normalized_surface === e.normalized_surface ? "var(--accent-dim)" : undefined }}
                    onClick={() => e.entity_id && setPicked(e)}>
                  <td>{e.surface.replace(/\s+/g, " ")}</td>
                  <td className="mono faint">{e.core_type ?? "—"}</td>
                  <td className="mono">{e.mentions}</td>
                  <td className="mono">{e.documents}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!ents.loading && !(ents.data?.entities ?? []).length && <div className="empty">No entities matched.</div>}
        </div>

        <div className="card">
          <div className="label" style={{ marginBottom: 8 }}>
            {picked ? <>Relationships — <span className="mono">{picked.surface.replace(/\s+/g, " ")}</span></> : "Relationships"}
          </div>
          {!picked && <div className="empty">Pick an entity to see its source-attested relationships.</div>}
          {rels.error && <div className="banner banner--bad">{rels.error}</div>}
          {rels.loading && picked && <div className="faint">loading…</div>}
          {rels.data && (
            <>
              {rels.data.dropped_unattested > 0 && (
                <div className="banner" style={{ marginBottom: 10 }}>
                  <b>{rels.data.dropped_unattested}</b> relationship(s) withheld — nothing in this corpus
                  attests them, so they are not canonical truth.
                </div>
              )}
              {rels.data.relationships.map((r) => (
                <div key={r.fact_id} style={{ borderBottom: "1px solid var(--line-soft)", padding: "9px 0" }}>
                  <div className="row" style={{ gap: 8 }}>
                    <span className="mono">{r.subject.replace(/\s+/g, " ")}</span>
                    <span className="pill pill--unknown">{r.predicate}</span>
                    <span className="mono">{r.object.replace(/\s+/g, " ")}</span>
                    <span className="faint mono">({r.direction})</span>
                  </div>
                  {r.sources.map((s) => (
                    <div key={s.chunk_id} className="faint" style={{ marginTop: 6, fontSize: 12 }}>
                      <div className="mono">{s.source_name ?? s.doc_id.slice(0, 16)}</div>
                      <div style={{ marginTop: 3, lineHeight: 1.5 }}>{s.text.slice(0, 260)}…</div>
                    </div>
                  ))}
                </div>
              ))}
              {!rels.data.relationships.length && (
                <div className="empty">No source-attested relationships for this entity in this corpus.</div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
