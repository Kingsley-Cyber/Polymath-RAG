import { useCallback, useEffect, useState } from "react";
import {
  enrichCorpus,
  enrichDocument,
  fetchCorpora,
  fetchDocuments,
  fetchDocumentStatus,
  fetchReadiness,
  fetchSections,
  setQueryEnabled,
  uploadFile,
  UploadError,
} from "../api";
import type { SectionRow } from "../api";
import type { DocumentRow, DocumentStatus, RunRow } from "../types";

const ACCEPTED_EXT = /\.(md|txt|html|pdf|epub|docx)$/i;

/** Files from a drop, descending into dropped FOLDERS (webkitGetAsEntry);
 * falls back to the flat file list where the directory API is absent.
 * Unsupported extensions are skipped here so a folder of mixed files
 * does not spray 422s. */
async function collectDroppedFiles(dt: DataTransfer): Promise<File[]> {
  const items = Array.from(dt.items ?? []);
  const entries = items
    .map((it) => (it as any).webkitGetAsEntry?.())
    .filter(Boolean);
  if (entries.length === 0 || !entries.some((e: any) => e.isDirectory)) {
    return Array.from(dt.files ?? []);
  }
  const out: File[] = [];
  const readEntry = (entry: any): Promise<void> =>
    new Promise((resolve) => {
      if (entry.isFile) {
        entry.file((f: File) => {
          if (ACCEPTED_EXT.test(f.name)) out.push(f);
          resolve();
        }, () => resolve());
      } else if (entry.isDirectory) {
        const reader = entry.createReader();
        const readBatch = () =>
          reader.readEntries(async (batch: any[]) => {
            if (!batch.length) return resolve();
            for (const e of batch) await readEntry(e);
            readBatch();
          }, () => resolve());
        readBatch();
      } else resolve();
    });
  for (const e of entries) await readEntry(e);
  return out;
}

/** The typed duplicate refusals (DUPLICATE-DOCUMENT-GUARD layers 2 and 3)
 * as the intake FAILURE receipt records them. */
const DUP_RE = /(NEAR_DUPLICATE_DOCUMENT|DUPLICATE_DOCUMENT):\s*([^]*?)(?:\s+<-\s|$)/;
const NEAR_MATCH_RE = /contained in (['"])(.+?)\1/;
const SAME_MATCH_RE = /same content as (['"])(.+?)\1/;
const EXACT_MATCH_RE = /already in the corpus as (['"])(.+?)\1/;
const PCT_RE = /is ([0-9.]+)% contained/;

type DupKind = "exact" | "same_text" | "near";
/** Parse a run's stored error into a duplicate verdict, or null. */
function duplicateVerdict(err?: string | null): { kind: DupKind; match: string; pct?: string } | null {
  if (!err) return null;
  const m = err.match(DUP_RE);
  if (!m) return null;
  if (m[1] === "NEAR_DUPLICATE_DOCUMENT") {
    return { kind: "near", match: m[2].match(NEAR_MATCH_RE)?.[2] ?? "?", pct: m[2].match(PCT_RE)?.[1] };
  }
  return { kind: "same_text", match: m[2].match(SAME_MATCH_RE)?.[2] ?? "?" };
}
function dupLabel(v: { kind: DupKind; match: string; pct?: string }): string {
  if (v.kind === "exact") return `already in corpus (same bytes as '${v.match}')`;
  if (v.kind === "same_text") return `already in corpus (same text as '${v.match}')`;
  return `already in corpus (near-duplicate of '${v.match}'${v.pct ? ` — ${v.pct}% contained` : ""})`;
}

type UploadRow = {
  name: string;
  state: string;
  run?: string;
  file?: File;
  kind?: "uploading" | "ingesting" | "ingested" | "exact" | "same_text" | "near" | "failed";
  match?: string;
};

/** Reconcile an upload row with its run's terminal state (the intake worker
 * decides layers 2 and 3 asynchronously, after the upload has returned). */
function deriveUpload(u: UploadRow, runs: { run_id: string; status: string; error?: string | null }[]): UploadRow {
  if (!u.run) return u;
  const r = runs.find((x) => x.run_id === u.run);
  if (!r) return u;
  if (r.status === "query_ready") return { ...u, kind: "ingested", state: "ingested — query-ready" };
  // The intake receipt is the verdict: a refused copy carries its typed error
  // while the run is still `intake` (retries) and after it turns `failed`. A
  // run that moved past intake (e.g. after `keep both` admitted the same
  // document) is no longer a refusal, whatever its receipt history says.
  const v = r.status === "intake" || r.status === "failed" ? duplicateVerdict(r.error) : null;
  if (v) return { ...u, kind: v.kind, match: v.match, state: dupLabel(v) };
  if (r.status === "failed") return { ...u, kind: "failed", state: `failed: ${(r.error ?? "").slice(0, 80)}` };
  return u;
}

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
  const [uploads, setUploads] = useState<UploadRow[]>([]);

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

  const handleFiles = async (
    files: FileList | File[] | null,
    opts: { allowNearDuplicate?: boolean } = {},
  ) => {
    if (!files || !corpus) return;
    for (const file of Array.from(files)) {
      setUploads((u) => [
        ...u.filter((x) => x.name !== file.name),
        { name: file.name, state: "uploading…", kind: "uploading", file },
      ]);
      try {
        const out = await uploadFile(corpus, file, opts);
        setUploads((u) =>
          u.map((x) =>
            x.name === file.name
              ? { ...x,
                  kind: out.already_exists ? "exact" : "ingesting",
                  state: out.already_exists
                    ? "already in corpus — no new run"
                    : opts.allowNearDuplicate ? "ingesting (keeping both)" : "ingesting",
                  run: out.run_id }
              : x,
          ),
        );
      } catch (e: any) {
        const dup = e instanceof UploadError && e.code === "duplicate_document";
        const match = dup ? String(e.message).match(EXACT_MATCH_RE)?.[2] : undefined;
        setUploads((u) =>
          u.map((x) =>
            x.name === file.name
              ? dup
                ? { ...x, kind: "exact", match,
                    state: match ? dupLabel({ kind: "exact", match }) : "already in corpus (same bytes)" }
                : { ...x, kind: "failed", state: `failed: ${String(e.message).slice(0, 80)}` }
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
              const dt = e.dataTransfer;
              collectDroppedFiles(dt).then((files) => handleFiles(files));
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
            Drop files or a folder here (md · txt · html · pdf · epub · docx)
            or click to browse. Each file goes through the full evidence-first
            pipeline; a copy already in the corpus is refused, not re-ingested.
          </div>
          {uploads.length > 1 && (() => {
            const rows = uploads.map((u) => deriveUpload(u, runs));
            const n = (k: UploadRow["kind"][]) => rows.filter((r) => k.includes(r.kind)).length;
            const parts = [
              `${rows.length} files`,
              `${n(["ingested"])} ingested`,
              `${n(["ingesting", "uploading"])} in flight`,
              `${n(["exact", "same_text"])} already in corpus`,
              `${n(["near"])} near-duplicates`,
              `${n(["failed"])} failed`,
            ].filter((p, i) => i < 2 || !p.startsWith("0 "));
            return (
              <div className="phase-detail" style={{ marginTop: 8 }} data-testid="upload-summary">
                {parts.join(" · ")}
              </div>
            );
          })()}
          {uploads.map((u0, i) => {
            const u = deriveUpload(u0, runs);
            const dup = u.kind === "exact" || u.kind === "same_text" || u.kind === "near";
            return (
              <div key={i} className="chunk-row" style={{ marginTop: 8 }}>
                <b>{u.name}</b> —{" "}
                <span className={dup ? "status-pill st-duplicate" : undefined}>{u.state}</span>
                {u.run && !dup && <span className="mono"> {u.run.slice(0, 20)}…</span>}
                {u.kind === "near" && u.file && (
                  <button
                    className="chunk-chip"
                    style={{ marginLeft: 8 }}
                    title="Ingest this file anyway, alongside the document it near-duplicates"
                    onClick={() => handleFiles([u.file!], { allowNearDuplicate: true })}
                  >
                    keep both
                  </button>
                )}
              </div>
            );
          })}
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
              {runs.slice(0, 8).map((r) => {
                const dup = r.status === "intake" || r.status === "failed" ? duplicateVerdict(r.error) : null;
                const note = dup ? dupLabel(dup) : r.error ?? "";
                return (
                <tr key={r.run_id}>
                  <td className="mono">{r.run_id.slice(0, 26)}…</td>
                  <td>
                    <span className={`status-pill ${dup ? "st-duplicate" : `st-${r.status}`}`}>
                      {dup ? "duplicate" : r.status}
                    </span>
                  </td>
                  <td className="mono">{r.created_at.slice(0, 19)}</td>
                  <td>
                    {note && (
                      <span
                        className="phase-detail"
                        title={r.error ?? note}
                        style={{ color: dup ? "var(--warn)" : "var(--accent)" }}
                      >
                        {note.slice(0, 90)}
                        {note.length > 90 ? "…" : ""}
                      </span>
                    )}
                  </td>
                </tr>
                );
              })}
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
  const [status, setStatus] = useState<DocumentStatus | null>(null);
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
    if (next && status === null) {
      try {
        setStatus(await fetchDocumentStatus(d.doc_id));
      } catch {
        /* status panel is best-effort; sections still render */
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
          <EnrichBadge d={d} />{" "}
          <MapBadge d={d} />
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
            <StatusPanel status={status} />
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

/** vNext pMAP coverage badge (RAG-PIPELINE-FINISH Phase 18): active parent maps vs
 * sections. Green when every section carries a parent map; the full per-doc status
 * (profile / unresolved / blockers) is in the expanded StatusPanel. */
function MapBadge({ d }: { d: DocumentRow }) {
  const maps = d.map_active ?? 0;
  const parents = d.parents ?? 0;
  if (parents === 0) return null;
  const done = maps >= parents;
  return (
    <span className={`status-pill ${done ? "st-query_ready" : "st-reconciling"}`}
          title={`${maps} of ${parents} sections have a vNext parent map (pMAP). Expand the row for full status.`}>
      🗺 {maps}/{parents}
    </span>
  );
}

/** CANONICAL-DOCUMENT-STATUS-V1 panel (Phase 18): the document's vNext readiness,
 * profile state, pMAP arithmetic, contract versions and ordered blockers. */
function StatusPanel({ status }: { status: DocumentStatus | null }) {
  if (status === null) return <div className="phase-detail">loading status…</div>;
  if (!status.found) return <div className="phase-detail">no status</div>;
  const p = status.profile ?? { present: false, valid: false, vnext: false };
  const m = status.pmap ?? {};
  const ready = status.vnext_ready;
  const profileTxt = !p.present ? "missing"
    : `${p.vnext ? "vNext✓" : "present"}${p.valid === false ? " (invalid)" : ""}`
      + (typeof p.quality === "number" ? ` q${p.quality.toFixed(2)}` : "");
  return (
    <div className="phase-detail" style={{ marginBottom: 8 }}>
      <span className={`status-pill ${ready ? "st-query_ready" : "st-reconciling"}`}>
        {ready ? "vNext ready" : "vNext incomplete"}
      </span>{" "}
      <span title="LLM document profile">profile: {profileTxt}</span>{" · "}
      <span title="parent maps (pMAP)">
        pMAP: {m.mapped_active ?? 0}/{m.eligible ?? 0} mapped
        {(m.excluded ?? 0) ? `, ${m.excluded} excluded` : ""}
        {(m.unresolved ?? 0) ? `, ${m.unresolved} unresolved` : ""}
        {(m.batches_total ?? 0) ? ` (${m.batches_done ?? 0}/${m.batches_total} batches)` : ""}
      </span>
      {status.blockers && status.blockers.length > 0 && (
        <div style={{ marginTop: 4, opacity: 0.85 }}>blockers: {status.blockers.join(" · ")}</div>
      )}
      {p.present && p.prompt_version && (
        <div style={{ marginTop: 2, opacity: 0.6, fontSize: 11 }}>
          contract: profile {p.prompt_version}/{p.compiler_version}
        </div>
      )}
    </div>
  );
}
