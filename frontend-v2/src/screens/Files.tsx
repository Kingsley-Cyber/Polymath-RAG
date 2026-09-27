import { useRef, useState } from "react";
import { ConfirmByName, Dialog } from "../ui/Dialog";
import { EmptyState, ErrorState, Skeleton } from "../ui/states";
import { api, ApiError } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { controlReady, docVnext, semanticReady, vnextReady, settled } from "../lib/readiness";
import { ReadinessTriad } from "../components/ReadinessTriad";
import { Pill, StatePill } from "../components/Pill";
import type { DocSummary } from "../lib/contracts";

const ACCEPT = ".md,.txt,.html,.pdf,.epub,.docx";

function fmtBytes(n: number): string {
  if (!n) return "—";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0, v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v >= 10 || i === 0 ? Math.round(v) : v.toFixed(1)} ${u[i]}`;
}

function fmtDate(iso: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  return new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function typeOf(sourceName: string, mediaType: string): string {
  const ext = sourceName.includes(".") ? sourceName.split(".").pop()!.toUpperCase() : "";
  if (ext) return ext;
  const m = /([a-z0-9.-]+)$/i.exec(mediaType || "");
  return (m?.[1] || "—").toUpperCase();
}

/**
 * F8 — Files (FRONTEND-V2-PLAN §7 + FRONTEND-V2-FILES-OPS-01).
 *
 * `GET /documents` is the IDENTITY authority: the human `source_name` is the primary
 * column (never a truncated content hash), plus type/size/added. `/documents/summary`
 * is merged in by doc_id for the operational detail (Graph · Profile · pMAP · vNext).
 * The lifecycle controls the backend already exposes are wired back in: `+ Add Files`
 * (POST /upload) and per-row Delete (DELETE /documents/{doc_id}, confirmed by filename).
 * A just-uploaded document appears immediately from /documents even before it has a
 * summary. Nothing here is manufactured green.
 */
/** `isOwner`: pipeline status and continuation (owner-only routes) and the library's danger zone. `canWrite`: adding and
 *  deleting files (the owner everywhere; a friend only in their private library). Controls a person cannot use are not shown. */
export function Files({ corpusId, isOwner = true, canWrite = true, onLibraryDeleted }: {
  corpusId: string; isOwner?: boolean; canWrite?: boolean; onLibraryDeleted?: (id: string) => void;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<{ docId: string; sourceName: string } | null>(null);
  const [details, setDetails] = useState(false);                     // owner: the pipeline columns
  const [nonce, setNonce] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const cp = useAsync((s) => (isOwner ? api.controlPlane(corpusId, s) : Promise.resolve(null)), [corpusId, nonce, isOwner]);
  const sr = useAsync((s) => api.semanticReadiness(corpusId, s), [corpusId, nonce]);
  const docs = useAsync((s) => api.documents(corpusId, s), [corpusId, nonce]);
  const sum = useAsync((s) => api.documentSummaries(corpusId, s), [corpusId, nonce]);

  const rows = docs.data?.documents ?? [];
  const summaries: Record<string, DocSummary> = sum.data?.summaries ?? {};
  const refresh = () => setNonce((n) => n + 1);
  const readyCount = rows.filter((r) => summaries[r.doc_id]?.vnext_ready).length;

  function describeError(e: unknown): string {
    if (e instanceof ApiError) {
      try {
        const body = JSON.parse(e.message.slice(e.message.indexOf("{")));
        if (body?.message) return `${body.error_code ?? "error"}: ${body.message}`;
      } catch { /* not a JSON body — fall through to the raw message */ }
      return e.message;
    }
    return e instanceof Error ? e.message : String(e);
  }

  async function onFilesPicked(list: FileList | null) {
    if (!list || !list.length) return;
    const files = Array.from(list);
    setErr(null); setNotice(null);
    const failures: string[] = [];
    let ok = 0;
    for (const [i, f] of files.entries()) {
      setBusy(`Uploading ${f.name} (${i + 1} of ${files.length})…`);
      try {
        await api.upload(corpusId, f);
        ok++;
      } catch (e) {
        failures.push(`${f.name}: ${describeError(e)}`);
      }
    }
    setBusy(null);
    if (ok) setNotice(`${ok} file${ok > 1 ? "s" : ""} submitted for ingestion — processing.`);
    if (failures.length) setErr(failures.join("  ·  "));
    if (fileInput.current) fileInput.current.value = "";
    refresh();
  }

  async function onDelete(docId: string, sourceName: string) {
    const label = sourceName || docId;
    setErr(null); setNotice(null);
    setBusy(`Deleting ${label}…`);
    try {
      // The confirm token accepts the source_name; fall back to the doc_id if the file
      // has no human name (the backend accepts either).
      await api.deleteDocument(docId, sourceName || docId);
      setNotice(`Deleted "${label}".`);
    } catch (e) {
      setErr(describeError(e));
    } finally {
      setBusy(null);
      refresh();
    }
  }

  // CONTINUATION control 1 of 2 — corpus-level: re-drive processing for every document.
  async function onContinueCorpus() {
    setErr(null); setNotice(null); setBusy(`Continuing ${corpusId}…`);
    try {
      await api.enrichCorpus(corpusId);
      setNotice(`Continuation queued for all documents in ${corpusId}.`);
    } catch (e) {
      setErr(describeError(e));
    } finally {
      setBusy(null);
      refresh();
    }
  }

  // CONTINUATION control 2 of 2 — per-document: re-drive one incomplete document.
  async function onContinueDoc(docId: string, sourceName: string) {
    setErr(null); setNotice(null); setBusy(`Continuing ${sourceName || docId}…`);
    try {
      await api.enrichDocument(docId);
      setNotice(`Continuation queued for "${sourceName || docId}".`);
    } catch (e) {
      setErr(describeError(e));
    } finally {
      setBusy(null);
      refresh();
    }
  }

  const incompleteCount = rows.filter((r) => !summaries[r.doc_id]?.vnext_ready).length;

  return (
    <div className="screen screen--wide">
      <div className="screen__head files__head">
        <div>
          <h1 className="screen__title">Files</h1>
          <p className="screen__sub">
            <span className="mono">{corpusId}</span> ·{" "}
            {docs.data == null ? "loading documents…" : <>{rows.length} documents · <b>{readyCount}</b> ready{rows.length - readyCount ? <>, <b>{rows.length - readyCount}</b> still processing</> : null}</>}
          </p>
        </div>
        <div className="files__actions">
          <input
            ref={fileInput}
            type="file"
            accept={ACCEPT}
            multiple
            hidden
            onChange={(e) => void onFilesPicked(e.target.files)}
          />
          {isOwner && <button
            className="btn"
            disabled={!!busy || !incompleteCount}
            title={incompleteCount
              ? `Continue processing the ${incompleteCount} not-ready document(s) in this corpus`
              : "All documents are vNext ready"}
            onClick={() => void onContinueCorpus()}
          >
            ▸ Continue corpus{incompleteCount ? ` (${incompleteCount})` : ""}
          </button>}
          {canWrite && <button
            className="btn btn--primary"
            disabled={!!busy}
            onClick={() => fileInput.current?.click()}
          >
            ＋ Add Files
          </button>}
        </div>
      </div>

      {isOwner && <ReadinessTriad
        control={settled(cp, (d) => controlReady(d?.control_ready))}
        semantic={settled(sr, semanticReady)}
        vnext={settled(sr, vnextReady)}
      />}
      {!canWrite && (
        <div className="banner banner--info" style={{ marginTop: 14 }}>
          This library is shared with you to read. You can add files to your own private library.
        </div>
      )}

      {busy && <div className="banner" style={{ marginTop: 14 }}>{busy}</div>}
      {notice && <div className="banner banner--ok" style={{ marginTop: 14 }}>{notice}</div>}
      {err && <div className="banner banner--bad" style={{ marginTop: 14 }}>{err}</div>}

      {isOwner && rows.length > 0 && (
        <label className="chip-field chip-field--toggle" style={{ marginTop: 14 }}>
          <input type="checkbox" checked={details} onChange={(e) => setDetails(e.target.checked)} />
          <span className="label">Pipeline details</span>
        </label>
      )}
      {docs.data == null && !docs.error ? (
        <div className="card" style={{ marginTop: 14 }}><Skeleton rows={5} label="Loading documents…" /></div>
      ) : docs.error && docs.data == null ? (
        <div className="card" style={{ marginTop: 14 }}><ErrorState message={docs.error} onRetry={refresh} /></div>
      ) : !rows.length ? (
        <div className="card" style={{ marginTop: 14 }}>
          <EmptyState title="No documents yet"
                      action={canWrite ? <button className="btn btn--primary" onClick={() => fileInput.current?.click()}>Add files</button> : undefined}>
            {canWrite ? "Add Markdown, text, HTML, PDF, EPUB or Word files to this library." : "Nothing has been added to this library yet."}
          </EmptyState>
        </div>
      ) : (
      <div className="card" style={{ marginTop: 14, overflowX: "auto" }}>
        <table className="t">
          <thead>
            <tr>
              <th>File</th><th>Type</th><th>Added</th><th>Size</th><th>Status</th>
              {details && <><th>Parents</th><th>Children</th>
              <th>pMAP mapped</th><th>excluded</th><th>unresolved</th>
              <th>Profile</th><th>Graph ent.</th><th>Graph rel.</th></>}<th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const d = summaries[r.doc_id];
              return (
                <tr key={r.doc_id}>
                  <td>
                    <div className="files__name" title={r.source_name || r.doc_id}>
                      {r.source_name || `${r.doc_id.slice(0, 18)}…`}
                    </div>
                    <div className="files__docid mono" title={r.doc_id}>{r.doc_id.slice(0, 12)}…</div>
                  </td>
                  <td className="mono">{typeOf(r.source_name, r.media_type)}</td>
                  <td className="mono">{fmtDate(r.created_at)}</td>
                  <td className="mono">{fmtBytes(r.bytes)}</td>
                  <td>{d ? <Pill v={docVnext(d)} /> : <StatePill state="degraded" label="PROCESSING" />}</td>
                  {details && <>
                  <td className="mono">{d ? d.parents : r.parents}</td>
                  <td className="mono">{d ? d.children : r.chunks}</td>
                  <td className="mono">{d ? d.map_active : r.map_active}</td>
                  <td className="mono">{d ? d.map_excluded : "—"}</td>
                  <td className="mono" style={{ color: d && d.map_unresolved > 0 ? "var(--bad)" : undefined }}>
                    {d ? d.map_unresolved : "—"}
                  </td>
                  <td className="mono">
                    {!d ? <span className="pill pill--degraded">pending</span>
                      : d.profile_vnext ? <span className="pill pill--ready">vNext</span>
                      : d.profile_present ? <span className="pill pill--degraded">legacy</span>
                      : <span className="pill pill--blocked">none</span>}
                  </td>
                  <td className="mono">{d ? d.graph_entities : "—"}</td>
                  <td className="mono">{d ? d.graph_relations : "—"}</td>
                  </>}
                  <td>
                    <div className="row" style={{ gap: 6 }}>
                      {isOwner && !d?.vnext_ready && (
                        <button
                          className="btn files__continue"
                          disabled={!!busy}
                          title={`Continue processing ${r.source_name || r.doc_id}`}
                          onClick={() => void onContinueDoc(r.doc_id, r.source_name)}
                        >
                          ▸ Continue
                        </button>
                      )}
                      {canWrite && <button
                        className="btn files__del"
                        disabled={!!busy}
                        title={`Delete ${r.source_name || r.doc_id}`}
                        onClick={() => setPendingDelete({ docId: r.doc_id, sourceName: r.source_name })}
                      >
                        Delete
                      </button>}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      )}

      <div className="faint" style={{ marginTop: 10, fontSize: 12 }}>
        Accepted: .md .txt .html .pdf .epub .docx. Atoms and pMAP are ROUTING artifacts —
        they explain why a source is findable, not what an answer rests on.
      </div>

      {isOwner && (
        <section className="card danger-zone" aria-labelledby="danger-zone-title">
          <div>
            <h2 className="settings__title" id="danger-zone-title">Delete this library</h2>
            <p className="dim" style={{ margin: "4px 0 0" }}>
              Removes <span className="mono">{corpusId}</span> and everything in it: documents, vectors and graph. This can't be undone.
            </p>
          </div>
          <button type="button" className="btn btn--danger" onClick={() => setConfirmDelete(true)}>Delete library…</button>
        </section>
      )}
      <Dialog open={!!pendingDelete} title={`Delete ${pendingDelete?.sourceName || pendingDelete?.docId || ""}?`}
              onClose={() => setPendingDelete(null)} actions={<>
        <button type="button" className="btn" onClick={() => setPendingDelete(null)}>Cancel</button>
        <button type="button" className="btn btn--danger-solid" onClick={() => {
          const p = pendingDelete; setPendingDelete(null); if (p) void onDelete(p.docId, p.sourceName);
        }}>Delete</button>
      </>}>
        <p className="dialog__text">This removes the document and everything made from it: chunks, vectors, graph and receipts. It can't be undone.</p>
      </Dialog>
      {isOwner && <ConfirmByName
        open={confirmDelete}
        title={`Delete the library ${corpusId}?`}
        name={corpusId}
        what={<>Every document in <span className="mono">{corpusId}</span>, its vectors and its graph are deleted for good.</>}
        action="Delete library"
        onClose={() => setConfirmDelete(false)}
        onConfirm={async () => { await api.deleteCorpus(corpusId, corpusId); onLibraryDeleted?.(corpusId); }}
      />}
    </div>
  );
}
