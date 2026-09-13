import { Fragment, useState } from "react";
import { chunkIdOf } from "../lib/chunkid";
import type { RetrievalReceipt } from "../lib/contracts";

/**
 * F4 — Evidence Inspector (FRONTEND-V2-PLAN §4).
 *
 * Per row: source document · section/parent · source child · exact text · rerank score
 * where available · evidence role · arrivals/provenance · citation.
 *
 * THE RULE THIS SCREEN ENFORCES: Profiles, Atoms and pMAP explain WHY A SOURCE WAS
 * FOUND. They are routing artifacts, never factual evidence. Lanes whose candidates
 * are summaries or cards (document_summary, section_summary, entity_card, the pMAP
 * profile lanes) are therefore labelled ROUTING and visually separated from the
 * SOURCE rows an answer may actually rest on.
 */
const ROUTING_LANES = new Set([
  "DOCUMENT_SUMMARY", "SECTION_SUMMARY", "ENTITY_CARD",
  "PROFILE", "DOC_PROFILE", "PARENT_MAP", "PMAP", "RESOLUTION_LIFT", "SEEALSO_FANOUT",
]);

interface Row {
  chunkId: string;
  docId?: string;
  sourceName?: string;
  headingPath?: string;
  title?: string;
  locator?: string;
  humanLocator?: string;
  preview?: string;
  kind?: string;
  score?: number;
  arrivals: string[];
  tag?: string;
}

export function EvidenceInspector({ receipt }: { receipt: RetrievalReceipt }) {
  const [open, setOpen] = useState<string | null>(null);

  const chunks = (receipt.chunks ?? []) as Record<string, unknown>[];
  const final = (receipt.final_detail ?? []) as Record<string, unknown>[];
  const legend = (receipt.legend ?? []) as Record<string, unknown>[];

  const byId = new Map<string, Row>();
  const put = (id: string): Row => {
    let r = byId.get(id);
    if (!r) { r = { chunkId: id, arrivals: [] }; byId.set(id, r); }
    return r;
  };

  for (const c of chunks) {
    const id = chunkIdOf(c);
    if (!id) continue;
    const r = put(id);
    r.docId = str(c.doc_id); r.sourceName = str(c.source_name); r.title = str(c.title);
    r.headingPath = str(c.heading_path); r.locator = str(c.locator);
    r.humanLocator = str(c.human_locator); r.preview = str(c.preview); r.kind = str(c.kind);
  }
  for (const d of final) {
    const id = chunkIdOf(d);
    if (!id) continue;
    const r = put(id);
    r.docId ??= str(d.doc_id);
    if (typeof d.rerank_score === "number") r.score = d.rerank_score;
    r.arrivals = (d.arrivals as string[]) ?? r.arrivals;
  }
  for (const l of legend) {
    const id = chunkIdOf(l);
    if (!id) continue;
    const r = put(id);
    r.tag = str(l.tag);
    r.locator ??= str(l.locator);
    r.headingPath ??= str(l.breadcrumb);
  }

  // Only rows that reached the FINAL selection are evidence for an answer; the rest
  // are candidates the reader can still inspect, clearly separated.
  const finalIds = new Set(final.map((d) => chunkIdOf(d)));
  const rows = [...byId.values()];
  const selected = rows.filter((r) => finalIds.has(r.chunkId))
    .sort((a, b) => (b.score ?? -1e9) - (a.score ?? -1e9));
  const others = rows.filter((r) => !finalIds.has(r.chunkId));

  if (!rows.length) return <div className="empty">This turn carried no evidence rows.</div>;

  return (
    <>
      <Section title={`Selected evidence (${selected.length})`} rows={selected} open={open} setOpen={setOpen} />
      {others.length > 0 && (
        <details style={{ marginTop: 12 }}>
          <summary className="label" style={{ cursor: "pointer" }}>
            Candidates not selected ({others.length})
          </summary>
          <div style={{ marginTop: 8 }}>
            <Section title="" rows={others} open={open} setOpen={setOpen} />
          </div>
        </details>
      )}
    </>
  );
}

function Section({ title, rows, open, setOpen }: {
  title: string; rows: Row[]; open: string | null; setOpen: (v: string | null) => void;
}) {
  if (!rows.length) return null;
  return (
    <>
      {title && <div className="label" style={{ margin: "12px 0 6px" }}>{title}</div>}
      <table className="t">
        <thead>
          <tr>
            <th>Cite</th><th>Document</th><th>Section / parent</th>
            <th>Score</th><th>Provenance</th><th>Kind</th><th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const routing = r.arrivals.length > 0 && r.arrivals.every((a) => ROUTING_LANES.has(a));
            return (
              <Fragment key={r.chunkId}>
                <tr>
                  <td className="mono">{r.tag ? <span className="pill pill--ready">{r.tag}</span> : <span className="faint">—</span>}</td>
                  <td>{r.sourceName ?? r.title ?? <span className="faint mono">{(r.docId ?? "").slice(0, 16)}</span>}</td>
                  <td className="dim">{r.headingPath || <span className="faint">—</span>}</td>
                  <td className="mono">{r.score != null ? r.score.toFixed(2) : <span className="faint">—</span>}</td>
                  <td className="mono faint" style={{ maxWidth: 240 }}>
                    {r.arrivals.length ? r.arrivals.join(", ") : "—"}
                    {routing && <div><span className="pill pill--degraded" title="Routing artifact — explains why this source was FOUND; it is not factual evidence.">ROUTING</span></div>}
                  </td>
                  <td className="mono faint">{r.kind ?? "—"}</td>
                  <td>
                    <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }}
                      onClick={() => setOpen(open === r.chunkId ? null : r.chunkId)}>
                      {open === r.chunkId ? "hide" : "text"}
                    </button>
                  </td>
                </tr>
                {open === r.chunkId && (
                  <tr>
                    <td colSpan={7} style={{ background: "var(--bg-sunken)" }}>
                      <div className="mono faint" style={{ marginBottom: 6 }}>
                        {r.humanLocator ?? r.locator ?? r.chunkId}
                      </div>
                      <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
                        {r.preview || <span className="faint">No text carried on this row (the receipt did not include a preview).</span>}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </>
  );
}

function str(v: unknown): string | undefined {
  return typeof v === "string" && v ? v : undefined;
}
