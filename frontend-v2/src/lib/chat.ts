/** Chat turn state machine over the `/chat/stream` SSE frames. */
import { chatStream } from "./api";
import type { AnswerFrame, RetrievalReceipt } from "./contracts";

/** One pipeline step from a `phase` frame. `data` keeps the raw fields so the
 *  process rail can show per-step detail (chunks, items, corpora, model…). */
export interface Phase {
  stage: string;
  label: string;
  at: number;
  data: Record<string, unknown>;
}

export interface Turn {
  question: string;
  mode: string;
  phases: Phase[];
  reasoningText: string;
  answerText: string;
  /** answer provenance, surfaced in the meta row */
  model: string | null;
  verdict: string | null;
  abstained: boolean;
  uncovered: string[];
  receipt: RetrievalReceipt | null;
  latencyMs: number | null;
  error: string | null;
  done: boolean;
}

export function newTurn(question: string, mode: string): Turn {
  return {
    question, mode, phases: [], reasoningText: "", answerText: "",
    model: null, verdict: null, abstained: false, uncovered: [],
    receipt: null, latencyMs: null, error: null, done: false,
  };
}

/* Live streams by chat session id. Module scope on purpose: a stream outlives the Chat screen
 * that started it (opening another chat unmounts that screen), so Stop has to find it from
 * whichever screen shows its chat now. */
const inflight = new Map<string, AbortController>();

/** Register a new stream for a chat; its signal goes to runTurn. */
export function beginStream(sessionId: string): AbortController {
  const ac = new AbortController();
  inflight.set(sessionId, ac);
  return ac;
}

export function endStream(sessionId: string, ac: AbortController): void {
  if (inflight.get(sessionId) === ac) inflight.delete(sessionId);
}

/** Cancel a chat's live stream, if it has one. */
export function stopStream(sessionId: string): void {
  inflight.get(sessionId)?.abort();
}

/** Pull the human answer text out of the answer frame without guessing a schema. */
function pickAnswer(result: unknown): string {
  if (typeof result === "string") return result;
  if (result && typeof result === "object") {
    const r = result as Record<string, unknown>;
    for (const k of ["answer", "text", "content", "message"]) {
      const v = r[k];
      if (typeof v === "string" && v.trim()) return v;
    }
  }
  return "";
}

export async function runTurn(
  body: Record<string, unknown>,
  onUpdate: (patch: Partial<Turn>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const t0 = performance.now();
  const phases: Phase[] = [];
  let streamed = "";               // accumulates `token` frames so the answer renders live
  let reasoning = "";              // accumulates `reasoning` frames so the wait shows live thinking
  try {
    for await (const frame of chatStream(body, signal)) {
      if (frame.event === "phase") {
        const d = (frame.data ?? {}) as Record<string, unknown>;
        const stage = String(d.stage ?? d.phase ?? d.name ?? "phase");
        const label = String(d.label ?? stage);
        phases.push({ stage, label, at: Math.round(performance.now() - t0), data: d });
        onUpdate({ phases: [...phases] });
      } else if (frame.event === "token") {
        // The backend streams the answer as `token` frames; append them so the bubble fills as it generates.
        const d = (frame.data ?? {}) as Record<string, unknown>;
        const tok = typeof d.token === "string" ? d.token : typeof d.text === "string" ? d.text : "";
        if (tok) { streamed += tok; onUpdate({ answerText: streamed }); }
      } else if (frame.event === "answer") {
        // The final answer frame is authoritative — prefer its clean text, fall back to what we streamed.
        const a = frame.data as AnswerFrame;
        const result = a.result as Record<string, unknown> | undefined;
        const meta = (result && typeof result.meta === "object" && result.meta
          ? result.meta : {}) as Record<string, unknown>;
        onUpdate({
          answerText: pickAnswer(result) || streamed,
          model: typeof result?.model === "string" ? result.model : null,
          verdict: typeof meta.verdict === "string" ? meta.verdict : null,
          abstained: !!meta.abstained,
          uncovered: Array.isArray(meta.uncovered_query_terms) ? (meta.uncovered_query_terms as string[]) : [],
          receipt: a.retrieval ?? null,
          latencyMs: a.latency_ms ?? Math.round(performance.now() - t0),
        });
      } else if (frame.event === "error") {
        onUpdate({ error: JSON.stringify(frame.data).slice(0, 400) });
      } else if (frame.event === "reasoning") {
        // Chain-of-thought — surfaced as the process rail's live "thinking" pane. Never the answer.
        const d = (frame.data ?? {}) as Record<string, unknown>;
        const r = typeof d.text === "string" ? d.text : typeof d.token === "string" ? d.token : "";
        if (r) { reasoning += r; onUpdate({ reasoningText: reasoning }); }
      }
    }
    onUpdate({ done: true });
  } catch (e) {
    if (signal?.aborted) { onUpdate({ done: true, error: "cancelled" }); return; }
    onUpdate({ done: true, error: e instanceof Error ? e.message : String(e) });
  }
}
