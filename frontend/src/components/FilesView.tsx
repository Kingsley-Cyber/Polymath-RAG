import { useCallback, useEffect, useState } from "react";
import { fetchDocuments, fetchReadiness, uploadFile } from "../api";
import type { DocumentRow, RunRow } from "../types";

function fmtBytes(n: number): string {
  if (n > 1_048_576) return `${(n / 1_048_576).toFixed(1)} MB`;
  if (n > 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${n} B`;
}

export default function FilesView({
  corpus,
  onCorpusDeleted,
}: {
  corpus: string;
  onCorpusDeleted?: () => void;
}) {
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [readiness, setReadiness] = useState<any>(null);
  const [drag, setDrag] = useState(false);
  const [uploads, setUploads] = useState<
    { name: string; state: string; run?: string }[]
  >([]);

  const refresh = useCallback(async () => {
    if (!corpus) return;
    try {
      const d = await fetchDocuments(corpus);
      setDocs(d.documents);
      setRuns(d.runs);
      setReadiness(await fetchReadiness(corpus));
    } catch {
      setDocs([]);
      setRuns([]);
      setReadiness(null);
    }
  }, [corpus]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 12_000);
    return () => clearInterval(t);
  }, [refresh]);

  const handleFiles = async (files: FileList | null) => {
    if (!files || !corpus) return;
    for (const file of Array.from(files)) {
      setUploads((u) => [...u, { name: file.name, state: "uploading…" }]);
      try {
        const out = await uploadFile(corpus, file);
        setUploads((u) =>
          u.map((x) =>
            x.name === file.name
              ? { ...x, state: "ingesting", run: out.run_id }
              : x,
          ),
        );
      } catch (e: any) {
        setUploads((u) =>
          u.map((x) =>
            x.name === file.name
              ? { ...x, state: `failed: ${String(e.message).slice(0, 80)}` }
              : x,
          ),
        );
      }
    }
    setTimeout(refresh, 1500);
  };

  if (!corpus)
    return (
      <div className="files">
        <div className="files-inner">
          <div className="panel">Select a corpus in the top bar.</div>
        </div>
      </div>
    );

  return (
    <div className="files">
      <div className="files-inner">
        <div className="panel">
          <h3>Upload → {corpus}</h3>
          <div
            className={`dropzone${drag ? " drag" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              handleFiles(e.dataTransfer.files);
            }}
            onClick={() => {
              const inp = document.createElement("input");
              inp.type = "file";
              inp.multiple = true;
              inp.accept = ".md,.txt,.html,.pdf,.epub,.docx";
              inp.onchange = () => handleFiles(inp.files);
              inp.click();
            }}
          >
            Drop files here (md · txt · html · pdf · epub · docx) or click
            to browse. Each file goes through the full evidence-first
            pipeline.
          </div>
          {uploads.map((u, i) => (
            <div key={i} className="chunk-row" style={{ marginTop: 8 }}>
              <b>{u.name}</b> — {u.state}
              {u.run && <span className="mono"> {u.run.slice(0, 20)}…</span>}
            </div>
          ))}
        </div>

        {readiness && (
          <div className="panel">
            <h3>Semantic readiness</h3>
            <div className="readiness">
              <span
                className={`status-pill ${
                  readiness.verdict === "SEMANTIC_COMPLETE"
                    ? "st-query_ready"
                    : readiness.verdict === "SEMANTIC_FAILED"
                      ? "st-failed"
                      : "st-reconciling"
                }`}
              >
                {readiness.verdict}
              </span>
              <span>
                <b>{readiness.counts?.documents ?? 0}</b> docs
              </span>
              <span>
                <b>{readiness.counts?.facts_accepted ?? 0}</b> facts
              </span>
              <span>
                <b>{readiness.counts?.procedures ?? 0}</b> procedures
              </span>
              <span>
                <b>{readiness.counts?.concepts ?? 0}</b> concepts
              </span>
              <span>
                <b>{readiness.counts?.corpus_map_rows ?? 0}</b> map rows
              </span>
            </div>
            {readiness.pending?.length > 0 && (
              <div className="phase-detail" style={{ marginTop: 6 }}>
                pending: {readiness.pending.join(", ")}
              </div>
            )}
          </div>
        )}

        <div className="panel">
          <h3>Documents ({docs.length})</h3>
          <table className="doc-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Type</th>
                <th>Size</th>
                <th>Chunks</th>
                <th>Added</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.doc_id}>
                  <td>{d.source_name}</td>
                  <td className="mono">{d.media_type}</td>
                  <td>{fmtBytes(d.bytes)}</td>
                  <td>{d.chunks}</td>
                  <td className="mono">{d.created_at.slice(0, 19)}</td>
                  <td>
                    <button
                      className="chunk-chip"
                      title="Delete this document everywhere (vectors, graph, facts evidenced only here). Same bytes become re-ingestable."
                      onClick={async () => {
                        const typed = window.prompt(
                          `Delete "${d.source_name}" from ${corpus}?\nType the doc id to confirm:\n${d.doc_id}`,
                        );
                        if (typed !== d.doc_id) return;
                        const r = await fetch(
                          `/documents/${encodeURIComponent(d.doc_id)}?confirm=${encodeURIComponent(typed)}`,
                          { method: "DELETE" },
                        );
                        if (r.ok) refresh();
                        else window.alert(`Delete failed: ${await r.text()}`);
                      }}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel danger">
          <h3>Danger zone</h3>
          <div className="readiness" style={{ marginBottom: 10 }}>
            Deleting removes this corpus everywhere: documents, chunks,
            facts evidenced only here, summaries, the vector collection
            and the graph substrate. There is no undo.
          </div>
          <button
            className="btn-danger"
            onClick={async () => {
              const typed = window.prompt(
                `Type the corpus id to delete it permanently:\n${corpus}`,
              );
              if (typed !== corpus) return;
              const r = await fetch(
                `/corpora/${encodeURIComponent(corpus)}?confirm=${encodeURIComponent(typed)}`,
                { method: "DELETE" },
              );
              if (r.ok) {
                const out = await r.json();
                window.alert(
                  `Deleted ${corpus}\n` +
                    Object.entries(out.removed ?? {})
                      .map(([k, v]) => `${k}: ${v}`)
                      .join("\n"),
                );
                onCorpusDeleted?.();
              } else {
                window.alert(`Delete failed: ${await r.text()}`);
              }
            }}
          >
            Delete corpus “{corpus}”
          </button>
        </div>

        <div className="panel">
          <h3>Recent runs</h3>
          <table className="doc-table">
            <tbody>
              {runs.slice(0, 8).map((r) => (
                <tr key={r.run_id}>
                  <td className="mono">{r.run_id.slice(0, 26)}…</td>
                  <td>
                    <span className={`status-pill st-${r.status}`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="mono">{r.created_at.slice(0, 19)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
