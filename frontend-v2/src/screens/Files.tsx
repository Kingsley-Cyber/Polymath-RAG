import { useRef, useState } from "react";
import { api, ApiError } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { controlReady, docVnext, semanticReady, vnextReady } from "../lib/readiness";
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
export function Files({ corpusId }: { corpusId: string }) {
  const [nonce, setNonce] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const cp = useAsync((s) => api.controlPlane(corpusId, s), [corpusId, nonce]);
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
    if (!window.confirm(`Delete "${label}"?\n\nThis removes the document and everything derived from it (chunks, vectors, graph substrate, receipts). It cannot be undone.`)) return;
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

  return (
    <div className="screen screen--wide">
      <div className="screen__head files__head">
        <div>
          <h1 className="screen__title">Files</h1>
          <p className="screen__sub">
            <span className="mono">{corpusId}</span> — {rows.length} documents,{" "}
            <b>{readyCount}</b> vNext-ready, <b>{rows.length - readyCount}</b> not ready
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
          <button
            className="btn btn--primary"
            disabled={!!busy}
            onClick={() => fileInput.current?.click()}
          >
            ＋ Add Files
          </button>
        </div>
      </div>

      <ReadinessTriad
        control={controlReady(cp.data?.control_ready)}
        semantic={semanticReady(sr.data)}
        vnext={vnextReady(sr.data)}
      />

      {busy && <div className="banner" style={{ marginTop: 14 }}>{busy}</div>}
      {notice && <div className="banner banner--ok" style={{ marginTop: 14 }}>{notice}</div>}
      {err && <div className="banner banner--bad" style={{ marginTop: 14 }}>{err}</div>}
      {docs.error && <div className="banner banner--bad" style={{ marginTop: 14 }}>{docs.error}</div>}

      <div className="card" style={{ marginTop: 14, overflowX: "auto" }}>
        <table className="t">
          <thead>
            <tr>
              <th>File</th><th>Type</th><th>Added</th><th>Size</th><th>Status</th>
              <th>Parents</th><th>Children</th>
              <th>pMAP mapped</th><th>excluded</th><th>unresolved</th>
              <th>Profile</th><th>Graph ent.</th><th>Graph rel.</th><th></th>
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
                  <td>
                    <button
                      className="btn files__del"
                      disabled={!!busy}
                      title={`Delete ${r.source_name || r.doc_id}`}
                      onClick={() => void onDelete(r.doc_id, r.source_name)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!rows.length && !docs.loading && (
          <div className="empty">No documents in this corpus yet — use ＋ Add Files to ingest one.</div>
        )}
      </div>

      <div className="faint" style={{ marginTop: 10, fontSize: 12 }}>
        Accepted: .md .txt .html .pdf .epub .docx. Atoms and pMAP are ROUTING artifacts —
        they explain why a source is findable, not what an answer rests on.
      </div>
    </div>
  );
}
