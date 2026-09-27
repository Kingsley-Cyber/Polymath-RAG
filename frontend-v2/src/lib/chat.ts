/** Chat turn state machine over the `/chat/stream` SSE frames. */
import { chatStream, type SseFrame } from "./api";
import type { AnswerFrame, ChatGapCheck, ChatSynthesis, DeepCoverage, RetrievalReceipt } from "./contracts";
import type { DeepRunState } from "./deep";

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
  /** DEEP-RESEARCH-MODE-V1: the report's resolved citations and the run's counts (null for a chat answer). */
  deep?: DeepAnswer | null;
  /** DR7: the research experience's own state (plan card, confirmed goals, start time, Finish now). Absent on older turns. */
  deepRun?: DeepRunState | null;
  /** DR7c: the latest `coverage` frame, each goal's findings and books so far. */
  deepCoverage?: DeepCoverage | null;
  /** FACET-RETRIEVAL-V1 F5: `meta.synthesis` of a synthesis answer (the facet badges and the sources by document). Absent on
   *  a QA turn and on turns saved before F5, which render as before. */
  synthesis?: ChatSynthesis | null;
  /** F6: `meta.gap_check` — the "not covered" claims searched again. */
  gapCheck?: ChatGapCheck | null;
}

export interface DeepCitation { cid: string; id?: string; title?: string; source?: string; text?: string; corpus_id?: string }
export interface DeepAnswer { citations: DeepCitation[]; unknown: string[]; summary: Record<string, unknown> | null }

export function newTurn(question: string, mode: string): Turn {
  return {
    question, mode, phases: [], reasoningText: "", answerText: "",
    model: null, verdict: null, abstained: false, uncovered: [],
    receipt: null, latencyMs: null, error: null, done: false, deep: null,
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
  stream: (body: Record<string, unknown>, signal?: AbortSignal) => AsyncGenerator<SseFrame> = chatStream,
): Promise<void> {
  const t0 = performance.now();
  const phases: Phase[] = [];
  let streamed = "";               // accumulates `token` frames so the answer renders live
  let reasoning = "";              // accumulates `reasoning` frames so the wait shows live thinking
  try {
    for await (const frame of stream(body, signal)) {
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
      } else if (frame.event === "answer" && (frame.data as { kind?: string })?.kind === "deep") {
        // A deep research report: its text, the citations resolved to their rows, and the run's counts (no chat receipt).
        const result = ((frame.data as { result?: unknown }).result ?? {}) as Record<string, unknown>;
        const meta = (typeof result.meta === "object" && result.meta ? result.meta : {}) as Record<string, unknown>;
        onUpdate({
          answerText: pickAnswer(result) || streamed,
          model: typeof result.model === "string" ? result.model : null,
          verdict: typeof meta.verdict === "string" ? meta.verdict : null,
          receipt: null,
          latencyMs: (frame.data as { latency_ms?: number }).latency_ms ?? Math.round(performance.now() - t0),
          deep: {
            citations: Array.isArray(result.citations) ? (result.citations as DeepCitation[]) : [],
            unknown: Array.isArray(result.unknown_citations) ? (result.unknown_citations as string[]) : [],
            summary: (typeof meta.deep_research === "object" && meta.deep_research ? meta.deep_research : null) as Record<string, unknown> | null,
          },
        });
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
          // FACET-RETRIEVAL-V1 F5 / F6: the graded evidence of a synthesis answer and the gap check, when the turn ran them
          synthesis: (typeof meta.synthesis === "object" && meta.synthesis ? meta.synthesis : null) as ChatSynthesis | null,
          gapCheck: (typeof meta.gap_check === "object" && meta.gap_check ? meta.gap_check : null) as ChatGapCheck | null,
        });
      } else if (frame.event === "coverage") {
        // DR7c: after each research level, each goal's findings and books so far (the live view's checklist)
        const d = (frame.data ?? {}) as DeepCoverage;
        if (Array.isArray(d.goals)) onUpdate({ deepCoverage: d });
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
