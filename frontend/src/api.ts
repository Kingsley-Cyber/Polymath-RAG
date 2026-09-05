import type { ChatAnswer, Corpus, DocumentRow, Mode, Phase, ReasoningModeInfo, RunRow, Synthesizer } from "./types";

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

export const fetchCorpora = (all = false) =>
  getJSON<{ corpora: Corpus[] }>(`/corpora${all ? "?all=true" : ""}`).then(
    (d) => d.corpora,
  );

/** Rename a corpus's display name (identity is immutable). */
export async function renameCorpus(corpus: string, name: string) {
  const r = await fetch(`/corpora/${encodeURIComponent(corpus)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!r.ok) throw new Error(`rename → ${r.status}: ${await r.text()}`);
  return r.json() as Promise<{ corpus_id: string; name: string }>;
}

export const fetchSynthesizers = () =>
  getJSON<{ synthesizers: Synthesizer[] }>("/synthesizers").then(
    (d) => d.synthesizers,
  );

export const fetchReasoningModes = () =>
  getJSON<{ modes: ReasoningModeInfo[]; default: string }>(
    "/reasoning_modes",
  );

export const fetchDocuments = (corpus: string) =>
  getJSON<{ documents: DocumentRow[]; runs: RunRow[] }>(
    `/documents?corpus_id=${encodeURIComponent(corpus)}`,
  );

export const fetchReadiness = (corpus: string) =>
  getJSON<{ verdict: string; counts: Record<string, number>; pending: string[] }>(
    `/semantic_readiness?corpus_id=${encodeURIComponent(corpus)}`,
  );

export interface SectionRow {
  parent_id: string;
  title: string;
  heading_path: string;
  summary: string;
  keywords: string[];
  coverage: unknown;
  children: number;
}

export const fetchSections = (docId: string) =>
  getJSON<{ doc_id: string; sections: SectionRow[] }>(
    `/documents/${encodeURIComponent(docId)}/sections`,
  );

/** UI-V3 F13: flip retrieval visibility for a corpus. */
export async function setQueryEnabled(corpus: string, enabled: boolean) {
  const r = await fetch(
    `/corpora/${encodeURIComponent(corpus)}/query_enabled`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query_enabled: enabled }),
    },
  );
  if (!r.ok) throw new Error(`query_enabled → ${r.status}`);
  return r.json() as Promise<{ corpus_id: string; query_enabled: boolean }>;
}

/** §0a enrichment triggers — corpus- and document-scoped. */
export async function enrichCorpus(corpus: string) {
  const r = await fetch(`/corpora/${encodeURIComponent(corpus)}/enrich`,
    { method: "POST" });
  if (!r.ok) throw new Error(`enrich → ${r.status}`);
  return r.json();
}

export async function enrichDocument(docId: string) {
  const r = await fetch(`/documents/${encodeURIComponent(docId)}/enrich`,
    { method: "POST" });
  if (!r.ok) throw new Error(`enrich → ${r.status}`);
  return r.json();
}

export async function uploadFile(corpus: string, file: File) {
  const form = new FormData();
  form.append("corpus_id", corpus);
  form.append("file", file);
  const r = await fetch("/upload", { method: "POST", body: form });
  if (!r.ok) throw new Error(`upload → ${r.status}: ${await r.text()}`);
  return r.json() as Promise<{
    run_id: string; accepted: boolean; already_exists?: boolean;
  }>;
}

export interface StreamHandlers {
  onPhase: (p: Phase) => void;
  onToken: (t: string) => void;
  /** Model thinking tokens — streamed into the reasoning card. */
  onReasoning?: (t: string) => void;
  onAnswer: (a: ChatAnswer) => void;
  onError: (e: { error_code?: string; message?: string; status?: number }) => void;
  onDone: () => void;
}

/** POST /chat/stream and dispatch SSE events. EventSource cannot POST,
 * so the stream is parsed off a fetch body reader. */
export async function streamChat(
  body: {
    message: string;
    corpus_id: string;
    mode: Mode;
    synthesizer: string;
    reasoning?: string;
    latent?: boolean;                 // LATENT-TRANSFER D10 flag
    history: { role: string; content: string }[];
    carry_context: { locator: string; preview: string; chunk_id?: string }[];
  },
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch("/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok || !r.body) {
    let detail: any = {};
    try {
      detail = (await r.json()).detail ?? {};
    } catch {
      /* not json */
    }
    handlers.onError({ status: r.status, ...detail });
    handlers.onDone();
    return;
  }
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7).trim();
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (!data) continue;
      let payload: any;
      try {
        payload = JSON.parse(data);
      } catch {
        continue;
      }
      if (event === "phase") handlers.onPhase(payload);
      else if (event === "token") handlers.onToken(payload.token ?? "");
      else if (event === "reasoning")
        handlers.onReasoning?.(payload.text ?? "");
      else if (event === "answer") handlers.onAnswer(payload);
      else if (event === "error") handlers.onError(payload);
      else if (event === "done") handlers.onDone();
    }
  }
  handlers.onDone();
}
