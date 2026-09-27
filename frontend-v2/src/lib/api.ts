/**
 * The ONE backend client. FRONTEND-V2-PLAN §0.2 — screens call these functions and
 * render what comes back; no screen fetches directly and no screen recomputes a
 * backend number.
 */
import type {
  CompareResponse, ControlPlane, Corpus, DocSummary, DocumentsResponse, GraphEntities,
  GraphRelationships, LlmProvider, LlmTestResult, PoolLanes, ProviderUpsertBody,
  ReasoningMode, RetrieveResponse, ReviewResponse, SemanticReadiness, Synthesizer,
  UploadResult, RunSummary, RunView } from "./contracts";

export class ApiError extends Error {
  constructor(readonly status: number, readonly path: string, readonly body: string) {
    super(`${path} -> ${status}: ${body}`);
    this.name = "ApiError";
  }

  /** The backend's stable `detail.error_code` (FRIENDS-ACCESS-V1 routes), or null. */
  get code(): string | null {
    try {
      const d = (JSON.parse(this.body) as { detail?: { error_code?: string } }).detail;
      return d?.error_code ?? null;
    } catch {
      return null;
    }
  }

  /** The backend's human message, else the raw body. */
  get detailMessage(): string {
    try {
      const d = (JSON.parse(this.body) as { detail?: { message?: string } | string }).detail;
      return typeof d === "string" ? d : d?.message ?? this.body;
    } catch {
      return this.body;
    }
  }
}

/** FRIENDS-ACCESS-V1: the session's CSRF token (a readable cookie the server set at sign-in). Every state-changing
 *  request echoes it in `X-Polymath-CSRF`; the web boundary refuses one that does not. Empty for the owner on 127.0.0.1. */
export function csrfToken(): string {
  const m = (typeof document === "undefined" ? "" : document.cookie).match(/(?:^|;\s*)polymath_csrf=([^;]+)/);
  const raw = m?.[1];
  return raw ? decodeURIComponent(raw) : "";
}

function csrfHeader(): Record<string, string> {
  const t = csrfToken();
  return t ? { "x-polymath-csrf": t } : {};
}

/** A 401 anywhere means the session ended: the app shell listens and shows the sign-in screen. */
export const AUTH_REQUIRED_EVENT = "polymath:auth-required";

async function checked(r: Response, path: string): Promise<Response> {
  if (r.ok) return r;
  const body = (await r.text()).slice(0, 600);
  if (r.status === 401 && typeof window !== "undefined") window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT));
  throw new ApiError(r.status, path, body);
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const r = await checked(await fetch(path, { signal, headers: { accept: "application/json" } }), path);
  return (await r.json()) as T;
}

async function send<T>(method: string, path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const r = await checked(await fetch(path, {
    method, signal,
    headers: { "content-type": "application/json", accept: "application/json", ...csrfHeader() },
    body: JSON.stringify(body),
  }), path);
  return (await r.json()) as T;
}

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return send<T>("POST", path, body, signal);
}

async function put<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return send<T>("PUT", path, body, signal);
}

/** Multipart POST — the browser sets the `content-type` boundary itself, so we must
 *  NOT set a content-type header (doing so drops the boundary and the server rejects
 *  the body). `/upload` is the only multipart route. */
async function postForm<T>(path: string, form: FormData, signal?: AbortSignal): Promise<T> {
  const r = await checked(await fetch(path, {
    method: "POST", signal, headers: { accept: "application/json", ...csrfHeader() }, body: form,
  }), path);
  return (await r.json()) as T;
}

async function del<T>(path: string, signal?: AbortSignal): Promise<T> {
  const r = await checked(await fetch(path, {
    method: "DELETE", signal, headers: { accept: "application/json", ...csrfHeader() },
  }), path);
  return (await r.json()) as T;
}

/** The raw verbs, for the account / settings client (lib/auth.ts). Screens still call `api` or `auth`. */
export const http = { get, post, put, del };

export const api = {
  // TRAIL-INTERFACE-V1: governed runs, newest first (a friend sees only their own), and one run's view
  adapterRuns: (limit = 50, s?: AbortSignal) =>
    get<{ runs: RunSummary[] }>(`/adapter/runs?limit=${limit}`, s).then((d) => d.runs),
  adapterView: (runId: string, s?: AbortSignal) => get<RunView>(`/adapter/${encodeURIComponent(runId)}/view`, s),
  adapterCancel: (runId: string, s?: AbortSignal) =>
    post<Record<string, unknown>>(`/adapter/${encodeURIComponent(runId)}/cancel`, {}, s),
  corpora: (s?: AbortSignal) => get<{ corpora: Corpus[] }>("/corpora", s).then((d) => d.corpora),
  // DELETE /corpora/{id} — OWNER-DESTRUCTIVE: wipes the corpus and everything derived
  // (PG rows, Qdrant collection, Neo4j substrate). The backend requires confirm==corpus_id,
  // so the UI makes the user type the corpus name.
  deleteCorpus: (corpusId: string, confirm: string, s?: AbortSignal) =>
    del<Record<string, unknown>>(
      `/corpora/${encodeURIComponent(corpusId)}?confirm=${encodeURIComponent(confirm)}`, s),
  semanticReadiness: (corpusId: string, s?: AbortSignal) =>
    get<SemanticReadiness>(`/semantic_readiness?corpus_id=${encodeURIComponent(corpusId)}`, s),
  documentSummaries: (corpusId: string, s?: AbortSignal) =>
    get<{ corpus_id: string; summaries: Record<string, DocSummary> }>(
      `/documents/summary?corpus_id=${encodeURIComponent(corpusId)}`, s),
  // GET /documents — identity/list authority (source_name, media_type, bytes, created_at).
  documents: (corpusId: string, s?: AbortSignal) =>
    get<DocumentsResponse>(`/documents?corpus_id=${encodeURIComponent(corpusId)}`, s),
  // POST /upload — canonical ingestion (.md .txt .html .pdf .epub .docx). `allowNearDuplicate`
  // rides the "keep both" override; byte-identical files are refused server-side (409) regardless.
  upload: (corpusId: string, file: File, allowNearDuplicate = false, s?: AbortSignal) => {
    const form = new FormData();
    form.append("corpus_id", corpusId);
    form.append("file", file, file.name);
    if (allowNearDuplicate) form.append("allow_near_duplicate", "1");
    return postForm<UploadResult>("/upload", form, s);
  },
  // DELETE /documents/{doc_id} — confirm token is the doc_id OR the source_name (a
  // 64-char hash is not human-typable, so the human filename is a valid confirm).
  deleteDocument: (docId: string, confirm: string, s?: AbortSignal) =>
    del<Record<string, unknown>>(
      `/documents/${encodeURIComponent(docId)}?confirm=${encodeURIComponent(confirm)}`, s),
  // CONTINUATION (§0a enrich buttons) — re-drive processing to push a corpus/document
  // toward vNext ready. POST /corpora/{id}/enrich (whole corpus) and
  // POST /documents/{id}/enrich (one doc); both queue work off the latest run.
  enrichCorpus: (corpusId: string, s?: AbortSignal) =>
    post<{ status: string }>(`/corpora/${encodeURIComponent(corpusId)}/enrich`, {}, s),
  enrichDocument: (docId: string, s?: AbortSignal) =>
    post<{ status: string }>(`/documents/${encodeURIComponent(docId)}/enrich`, {}, s),
  controlPlane: (corpusId: string, s?: AbortSignal) =>
    get<ControlPlane>(`/control_plane?corpus_id=${encodeURIComponent(corpusId)}`, s),
  poolLanes: (fn: string, s?: AbortSignal) =>
    get<PoolLanes>(`/control_plane/pool/${encodeURIComponent(fn)}`, s),
  synthesizers: (s?: AbortSignal) =>
    get<{ synthesizers: Synthesizer[] }>("/synthesizers", s).then((d) => d.synthesizers),
  reasoningModes: (s?: AbortSignal) =>
    get<{ modes: ReasoningMode[]; default: string }>("/reasoning_modes", s),
  ready: (s?: AbortSignal) =>
    get<{ ready: boolean; sidecars: Record<string, boolean> }>("/ready", s),
  pipelineHealth: (s?: AbortSignal) => get<Record<string, unknown>>("/health/pipeline", s),
  retrieve: (body: { query: string; corpus_id: string; mode: string }, s?: AbortSignal) =>
    post<RetrieveResponse>("/retrieve", body, s),
  predicates: (corpusId: string, limit: number, s?: AbortSignal) =>
    get<Record<string, unknown>>(
      `/control_plane/predicates?corpus_id=${encodeURIComponent(corpusId)}&limit=${limit}`, s),
  capabilities: (s?: AbortSignal) => get<Record<string, unknown>>("/capabilities", s),
  graphEntities: (corpusId: string, q: string, limit: number, s?: AbortSignal) =>
    get<GraphEntities>(
      `/graph/entities?corpus_id=${encodeURIComponent(corpusId)}&q=${encodeURIComponent(q)}&limit=${limit}`, s),
  graphRelationships: (entityId: string, corpusId: string, limit: number, s?: AbortSignal) =>
    get<GraphRelationships>(
      `/graph/entity/${encodeURIComponent(entityId)}/relationships?corpus_id=${encodeURIComponent(corpusId)}&limit=${limit}`, s),
  // LLM provider management (the legacy /ui "Models" screen — F1 in V2). The backend
  // never returns a raw key, and an empty api_key on upsert keeps the stored one.
  llmProviders: (s?: AbortSignal) =>
    get<{ providers: LlmProvider[] }>("/llm/providers", s).then((d) => d.providers),
  saveProvider: (body: ProviderUpsertBody, s?: AbortSignal) =>
    post<{ saved: string }>("/llm/providers", body, s),
  deleteProvider: (providerId: string, s?: AbortSignal) =>
    del<{ deleted: string; existed: boolean }>(
      `/llm/providers/${encodeURIComponent(providerId)}`, s),
  testModel: (model: string, s?: AbortSignal) =>
    post<LlmTestResult>("/llm/test", { model }, s),
  compare: (body: { message: string; corpus_id: string; modes: string[] }, s?: AbortSignal) =>
    post<CompareResponse>("/compare", body, s),
  review: (body: {
    question: string; answer: string; citations: string[];
    evidence: unknown[]; retrieval_meta: Record<string, unknown>; reviewer?: string;
  }, s?: AbortSignal) => post<ReviewResponse>("/review", body, s),
};

/* ── SSE ──────────────────────────────────────────────────────────────────── */

export interface SseFrame { event: string; data: unknown }

/**
 * Read `/chat/stream` as it arrives. The backend emits `phase` frames, then one
 * `answer`, then `done`; this yields them in order and never buffers the whole body
 * (the SSE-gzip buffering bug is a backend concern, but a streaming reader is the
 * only way the phases are visible as they happen).
 */
export async function* chatStream(
  body: Record<string, unknown>, signal?: AbortSignal,
): AsyncGenerator<SseFrame> {
  const r = await checked(await fetch("/chat/stream", {
    method: "POST", signal,
    headers: { "content-type": "application/json", accept: "text/event-stream", ...csrfHeader() },
    body: JSON.stringify(body),
  }), "/chat/stream");
  if (!r.body) throw new ApiError(r.status, "/chat/stream", "no response body");
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let sep: number;
    // SSE frames are separated by a blank line; keep the tail for the next chunk.
    while ((sep = buf.indexOf("\n\n")) !== -1) {
      const raw = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      const frame = parseFrame(raw);
      if (frame) yield frame;
    }
  }
  const tail = parseFrame(buf);
  if (tail) yield tail;
}

function parseFrame(raw: string): SseFrame | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return null;
  const text = dataLines.join("\n");
  try { return { event, data: JSON.parse(text) }; } catch { return { event, data: text }; }
}
