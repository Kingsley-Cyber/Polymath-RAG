import type { ChatAnswer, Corpus, DocumentRow, Mode, Phase, RunRow, Synthesizer } from "./types";

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

export const fetchCorpora = () =>
  getJSON<{ corpora: Corpus[] }>("/corpora").then((d) => d.corpora);

export const fetchSynthesizers = () =>
  getJSON<{ synthesizers: Synthesizer[] }>("/synthesizers").then(
    (d) => d.synthesizers,
  );

export const fetchDocuments = (corpus: string) =>
  getJSON<{ documents: DocumentRow[]; runs: RunRow[] }>(
    `/documents?corpus_id=${encodeURIComponent(corpus)}`,
  );

export const fetchReadiness = (corpus: string) =>
  getJSON<{ verdict: string; counts: Record<string, number>; pending: string[] }>(
    `/semantic_readiness?corpus_id=${encodeURIComponent(corpus)}`,
  );

export async function uploadFile(corpus: string, file: File) {
  const form = new FormData();
  form.append("corpus_id", corpus);
  form.append("file", file);
  const r = await fetch("/upload", { method: "POST", body: form });
  if (!r.ok) throw new Error(`upload → ${r.status}: ${await r.text()}`);
  return r.json() as Promise<{ run_id: string; accepted: boolean }>;
}

export interface StreamHandlers {
  onPhase: (p: Phase) => void;
  onToken: (t: string) => void;
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
    history: { role: string; content: string }[];
    carry_context: { locator: string; preview: string }[];
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
      else if (event === "answer") handlers.onAnswer(payload);
      else if (event === "error") handlers.onError(payload);
      else if (event === "done") handlers.onDone();
    }
  }
  handlers.onDone();
}
