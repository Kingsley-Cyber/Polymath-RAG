import { useCallback, useEffect, useState } from "react";
import {
  enrichCorpus,
  enrichDocument,
  fetchCorpora,
  fetchDocuments,
  fetchReadiness,
  fetchSections,
  setQueryEnabled,
  uploadFile,
} from "../api";
import type { SectionRow } from "../api";
import type { DocumentRow, RunRow } from "../types";

function fmtBytes(n: number): string {
  if (n > 1_048_576) return `${(n / 1_048_576).toFixed(1)} MB`;
  if (n > 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${n} B`;
}


/** Human lines for readiness pending-codes (in-flight vs broken). */
const PENDING_LABELS: Record<string, string> = {
  no_query_ready_run: "final census pending",
  document_summaries_0_of_2: "document summaries queued",
  no_parent_summaries: "parent summaries queued",
  no_corpus_map: "corpus map queued",
  unprojected_procedures_61: "procedures compiled — awaiting projection",
  unprojected_concepts_15: "concepts compiled — awaiting projection",
};
function pendingLabel(code: string): string {
  if (PENDING_LABELS[code]) return PENDING_LABELS[code];
  if (code.startsWith("unprojected_procedures")) return "procedures compiled — awaiting projection";
  if (code.startsWith("unprojected_concepts")) return "concepts compiled — awaiting projection";
  if (code.startsWith("document_summaries")) return "document summaries queued";
  return code.replace(/_/g, " ");
}
function verdictLine(r: any): string {
  if (!r) return "";
  const busy = (r.pending ?? []).length > 0
    && (r.pending ?? []).every((p: string) =>
      /queued|map|census|summar|unprojected|no_query_ready/.test(pendingLabel(p)));
  if (r.verdict === "SEMANTIC_COMPLETE") return "✓ complete — corpus is query-ready";
  if (busy) return "⏳ ingesting — downstream stages in flight, not an error";
  return "incomplete";
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
  const [queryEnabled, setQueryEnabledState] = useState<boolean | null>(null);
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
      const row = (await fetchCorpora(true)).find(
        (c) => c.corpus_id === corpus,
      );
      setQueryEnabledState(row ? !!(row as any).query_enabled : null);
    } catch {
      setDocs([]);
      setRuns([]);
      setReadiness(null);
    }
  }, [corpus]);

  useEffect(() => {
    refresh();
    // Poll fast while any run/upload is active, slow when idle; refetch
    // immediately when the tab regains focus (staleness fix 2026-08-30).
    let alive = true;
    const tick = async () => {
      if (!alive) return;
      const busy = uploads.some((u) => u.state === "uploading…" || u.state === "ingesting")
        || (runs ?? []).some((r: any) => r.status !== "query_ready" && r.status !== "failed");
      refresh();
      timer = setTimeout(tick, busy ? 4_000 : 12_000);
    };
    let timer = setTimeout(tick, 4_000);
    const onVis = () => { if (document.visibilityState === "visible") refresh(); };
    document.addEventListener("visibilitychange", onVis);
    return () => { alive = false; clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVis); };
  }, [refresh, uploads, runs]);

  const handleFiles = async (files: FileList | null) => {
    if (!files || !corpus) return;
    for (const file of Array.from(files)) {
      setUploads((u) => [...u, { name: file.name, state: "uploading…" }]);
      try {
        const out = await uploadFile(corpus, file);
        setUploads((u) =>
          u.map((x) =>
            x.name === file.name
              ? { ...x, state: out.already_exists
                    ? "already in corpus — no new run"
                    : "ingesting", run: out.run_id }
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
          <h3>
            Upload → {corpus}
            <button
              className="chunk-chip"
              style={{ marginLeft: 10 }}
              title="Add files to this corpus"
              onClick={() => {
                const inp = document.createElement("input");
                inp.type = "file";
                inp.multiple = true;
                inp.accept = ".md,.txt,.html,.pdf,.epub,.docx";
                inp.onchange = () => handleFiles(inp.files);
                inp.click();
              }}
            >
              ＋ Add files
            </button>
          </h3>
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
            <p style={{ opacity: 0.85, fontSize: 13 }}>
              {verdictLine(readiness)}
            </p>
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
                in flight: {readiness.pending.map(pendingLabel).join(" · ")}
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
                <DocRows key={d.doc_id} d={d} corpus={corpus} refresh={refresh} />
              ))}
            </tbody>
          </table>
        </div>


        {queryEnabled !== null && (
          <div className="panel">
            <h3>Retrieval visibility</h3>
            <div className="readiness" style={{ alignItems: "center", gap: 10 }}>
              <span
                className={`status-pill ${queryEnabled ? "st-query_ready" : "st-reconciling"}`}
              >
                {queryEnabled ? "ENABLED" : "HIDDEN"}
              </span>
              <span style={{ opacity: 0.85, fontSize: 13 }}>
                {queryEnabled
                  ? "This corpus answers chat and retrieval queries."
                  : "Uploads default to hidden — chat cannot see this corpus until enabled."}
              </span>
              <button
                className="chunk-chip"
                onClick={async () => {
                  const out = await setQueryEnabled(corpus, !queryEnabled);
                  setQueryEnabledState(out.query_enabled);
                }}
              >
                {queryEnabled ? "Hide from retrieval" : "Enable retrieval"}
              </button>
              {(() => {
                const totalParents = docs.reduce(
                  (n, d) => n + (d.parents ?? 0), 0);
                const totalEnriched = docs.reduce(
                  (n, d) => n + (d.enriched ?? 0), 0);
                const remaining = totalParents - totalEnriched;
                if (totalParents > 0 && remaining <= 0)
                  return (
                    <span className="status-pill st-query_ready"
                          title="Every section carries latent retrieval surfaces">
                      ✨ fully enriched
                    </span>
                  );
                if (remaining <= 0) return null;
                return (
                  <button
                    className="chunk-chip"
                    title="Enrich remaining sections: latent abstractions, mechanisms and transfer questions. Auto-runs after ingest; this re-sweeps anything that failed or changed."
                    onClick={async () => {
                      try {
                        await enrichCorpus(corpus);
                        window.alert(
                          `Enrichment queued — ${remaining} section${remaining === 1 ? "" : "s"} remaining.`);
                      } catch (e: any) {
                        window.alert(`Enrich failed: ${String(e.message)}`);
                      }
                    }}
                  >
                    ✨ Enrich ({remaining} remaining)
                  </button>
                );
              })()}
            </div>
          </div>
        )}

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
                  <td>
                    {r.error && (
                      <span
                        className="phase-detail"
                        title={r.error}
                        style={{ color: "var(--accent)" }}
                      >
                        {r.error.slice(0, 70)}
                        {r.error.length > 70 ? "…" : ""}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}


/** UI-V3 §4.2: a document row that expands into its section tree —
 * section title + card summary + child count, hash ids demoted to a
 * copy affordance. Sections come from the compiled parent cards
 * (ONE-SUMMARY-AUTHORITY); legacy docs without heading_path render
 * summary-head titles (PRD §2 NULL fallback). */
function DocRows({
  d,
  corpus,
  refresh,
}: {
  d: DocumentRow;
  corpus: string;
  refresh: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [sections, setSections] = useState<SectionRow[] | null>(null);
  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && sections === null) {
      try {
        setSections((await fetchSections(d.doc_id)).sections);
      } catch {
        setSections([]);
      }
    }
  };
  return (
    <>
      <tr>
        <td>
          <button className="chunk-chip" onClick={toggle} style={{ marginRight: 6 }}>
            {open ? "▾" : "▸"}
          </button>
          {d.source_name}{" "}
          <EnrichBadge d={d} />
        </td>
        <td className="mono">{d.media_type}</td>
        <td>{fmtBytes(d.bytes)}</td>
        <td>{d.chunks}</td>
        <td className="mono">{d.created_at.slice(0, 19)}</td>
        <td>
          <button
            className="chunk-chip"
            title="Copy document id"
            onClick={() => navigator.clipboard?.writeText(d.doc_id)}
          >
            ⧉ id
          </button>{" "}
          <EnrichCell d={d} />{" "}
          <button
            className="chunk-chip"
            title="Delete this document everywhere (vectors, graph, facts evidenced only here). Same bytes become re-ingestable."
            onClick={async () => {
              const typed = window.prompt(
                `Delete "${d.source_name}" from ${corpus}?\nType the file name to confirm:\n${d.source_name}`,
              );
              if (typed !== d.source_name && typed !== d.doc_id) return;
              const r = await fetch(
                `/documents/${encodeURIComponent(d.doc_id)}?confirm=${encodeURIComponent(typed)}`,
                { method: "DELETE" },
              );
              if (r.ok) { refresh(); return; }
              const body = await r.json().catch(() => ({}));
              if (body?.detail?.error_code === "runs_in_flight")
                window.alert("Extraction is in flight for this document — retry once ingestion finishes.");
              else
                window.alert(`Delete failed: ${body?.detail?.message ?? r.status}`);
            }}
          >
            ✕
          </button>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={6} style={{ padding: "0 0 8px 28px" }}>
            {sections === null ? (
              <div className="phase-detail">loading sections…</div>
            ) : sections.length === 0 ? (
              <div className="phase-detail">no compiled sections yet</div>
            ) : (
              <div className="chunks-panel">
                {sections.map((sec) => (
                  <div className="chunk-row" key={sec.parent_id}>
                    <div className="chunk-loc">
                      <b>{sec.title}</b>
                      {"  ·  "}{sec.children} chunk{sec.children === 1 ? "" : "s"}
                      <button
                        className="copy-btn"
                        title="Copy section (parent) id"
                        onClick={() =>
                          navigator.clipboard?.writeText(sec.parent_id)
                        }
                      >
                        ⧉ id
                      </button>
                    </div>
                    {sec.summary && (
                      <div className="chunk-preview">{sec.summary}</div>
                    )}
                    {sec.keywords.length > 0 && (
                      <div className="phase-detail">
                        {sec.keywords.join(" · ")}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}


/** Enrichment indicator: sections that carry latent retrieval surfaces.
 * Green = every section enriched; amber = partial (auto-enrich runs at
 * ingest; failures/edits leave a remainder); nothing = no sections yet. */
function EnrichBadge({ d }: { d: DocumentRow }) {
  const parents = d.parents ?? 0;
  const enriched = d.enriched ?? 0;
  if (parents === 0) return null;
  if (enriched >= parents)
    return (
      <span className="status-pill st-query_ready"
            title="All sections carry latent retrieval surfaces">
        ✨ enriched
      </span>
    );
  return (
    <span className="status-pill st-reconciling"
          title={`${enriched} of ${parents} sections enriched${
            (d.enrich_failed ?? 0) > 0
              ? ` · ${d.enrich_failed} failed (re-run below)` : ""}`}>
      ✨ {enriched}/{parents}
    </span>
  );
}

/** The per-document enrich button renders ONLY while sections remain
 * un-enriched (ingest errors, transient provider failures, edits). */
function EnrichCell({ d }: { d: DocumentRow }) {
  const parents = d.parents ?? 0;
  const enriched = d.enriched ?? 0;
  const remaining = parents - enriched;
  if (parents === 0 || remaining <= 0) return null;
  return (
    <button
      className="chunk-chip"
      title={`Enrich ${remaining} remaining section${remaining === 1 ? "" : "s"} (latent retrieval surfaces)`}
      onClick={async () => {
        try {
          await enrichDocument(d.doc_id);
          window.alert(`Enrichment queued for ${d.source_name} — ${remaining} section${remaining === 1 ? "" : "s"} remaining.`);
        } catch (e: any) {
          window.alert(`Enrich failed: ${String(e.message)}`);
        }
      }}
    >
      ✨ {remaining}
    </button>
  );
}
