/** Chat turn state machine over the `/chat/stream` SSE frames. */
import { chatStream } from "./api";
import type { AnswerFrame, RetrievalReceipt } from "./contracts";

export interface Phase { name: string; at: number; detail?: string }

export interface Turn {
  question: string;
  mode: string;
  phases: Phase[];
  answerText: string;
  receipt: RetrievalReceipt | null;
  latencyMs: number | null;
  error: string | null;
  done: boolean;
}

export function newTurn(question: string, mode: string): Turn {
  return { question, mode, phases: [], answerText: "", receipt: null, latencyMs: null, error: null, done: false };
}

/** Pull the human answer text out of the answer frame without guessing a schema. */
function answerText(result: unknown): string {
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
  try {
    for await (const frame of chatStream(body, signal)) {
      if (frame.event === "phase") {
        const d = (frame.data ?? {}) as Record<string, unknown>;
        const name = String(d.phase ?? d.name ?? d.stage ?? "phase");
        phases.push({ name, at: Math.round(performance.now() - t0), detail: typeof d.detail === "string" ? d.detail : undefined });
        onUpdate({ phases: [...phases] });
      } else if (frame.event === "answer") {
        const a = frame.data as AnswerFrame;
        onUpdate({
          answerText: answerText(a.result),
          receipt: a.retrieval ?? null,
          latencyMs: a.latency_ms ?? Math.round(performance.now() - t0),
        });
      } else if (frame.event === "error") {
        onUpdate({ error: JSON.stringify(frame.data).slice(0, 400) });
      }
    }
    onUpdate({ done: true });
  } catch (e) {
    if (signal?.aborted) { onUpdate({ done: true, error: "cancelled" }); return; }
    onUpdate({ done: true, error: e instanceof Error ? e.message : String(e) });
  }
}
