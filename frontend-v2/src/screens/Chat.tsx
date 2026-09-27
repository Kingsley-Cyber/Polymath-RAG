import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Icon } from "../ui/icons";
import { copyText } from "../lib/auth";
import { api, ApiError, deepResearchStream } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { PUBLIC_MODES } from "../lib/contracts";
import type { PublicMode, Synthesizer } from "../lib/contracts";
import { beginStream, endStream, newTurn, runTurn, stopStream, type Turn } from "../lib/chat";
import { ProcessRail } from "../components/ProcessRail";
import { AnswerBody } from "../components/AnswerBody";
import { ModelPicker } from "../components/ModelPicker";
import type { ChatSession } from "../lib/chatStore";
import { isResearchTurn, loadSkipPlan, olderPlanBackend, presetSeconds, type DeepGoal, type DeepRunRequest, type DeepRunState } from "../lib/deep";
import { ResearchTurnView, type ResearchHandlers } from "../components/deep/ResearchTurn";

/**
 * F2 + F3 — Chat with corpus, retrieval mode, model, reasoning and streaming.
 *
 * FRONTEND-V2-PLAN §2: VECTOR is NOT offered by that name; FAST is its public name. Intent is
 * classified by the compiler and shown READ-ONLY as a badge on each answer — there is no
 * intent-override contract, so no control pretends to be one (a disabled one-option
 * "Intent" dropdown used to sit here). Each turn streams through the process rail
 * (steps + live reasoning, collapsing when done) into a Markdown answer (AnswerBody).
 *
 * The turns are the session's, held by App: this screen reads them and writes through
 * `onUpdateTurns`. Opening another chat unmounts this screen but not its stream, and the
 * answer must still land in this chat (owner report 2026-09-22, "only graph worked").
 */
/** Starter questions for an empty chat; clicking one fills the box (nothing is sent until you press Enter). */
const STARTERS = [
  "Give me an overview of this library",
  "What are the key concepts, and how do they relate?",
  "Where do the sources disagree, and on what?",
];

export function Chat({
  corpusId,
  session,
  onUpdateTurns,
  focusTurn = null,
  onFocusDone,
}: {
  corpusId: string;
  /** CHAT-HISTORY-V1: the session being viewed. App creates it before this screen mounts. */
  session: ChatSession;
  /** Apply a change to THIS session's turns in App's store. */
  onUpdateTurns: (fn: (turns: Turn[]) => Turn[]) => void;
  /** DR7e: a turn to bring into view (a report opened from Research → Reports), then `onFocusDone`. */
  focusTurn?: number | null;
  onFocusDone?: () => void;
}) {
  const [mode, setMode] = useState<PublicMode>("HYBRID");
  const [model, setModel] = useState<string>("");
  const [reasoning, setReasoning] = useState<string>("");
  const [corpusExplore, setCorpusExplore] = useState(false);
  const [deep, setDeep] = useState(false);                        // DEEP-RESEARCH-MODE-V1: the composer switch
  const [preset, setPreset] = useState("standard");
  const [question, setQuestion] = useState("");
  const turns = session.turns;
  // Busy is the chat's, not this screen's: a chat reopened mid-answer is still streaming.
  const last = turns[turns.length - 1];
  const busy = !!last && !last.done;

  const synths = useAsync((s) => api.synthesizers(s), []);
  const reasons = useAsync((s) => api.reasoningModes(s), []);
  // CORPUS-EXPLORER-V1: only show the "Corpus Explore" toggle when the server advertises the capability
  // (the deployment kill switch POLYMATH_CORPUS_EXPLORER). The per-request flag is sent only when on.
  const caps = useAsync((s) => api.capabilities(s), []);
  const corpusExploreAvailable = Boolean(
    ((caps.data?.contracts ?? {}) as Record<string, unknown>)["corpus-explorer"],
  );
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // The box grows with the text, like Claude's: one line when empty, taller as you type, and it
  // only scrolls inside once it reaches its CSS max-height.
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    const max = parseFloat(getComputedStyle(el).maxHeight) || 320;
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
    el.style.overflowY = el.scrollHeight > max ? "auto" : "hidden";
  }, [question]);

  // ChatGPT-style thread: newest at the bottom, so follow it as it streams.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns]);

  // DR7e: a report opened from the Reports list lands on its own turn (after the jump to the bottom above).
  useEffect(() => {
    if (focusTurn == null) return;
    scrollRef.current?.querySelectorAll<HTMLElement>(".msg-user")[focusTurn]?.scrollIntoView?.({ block: "start" });
    onFocusDone?.();
  }, [focusTurn]);

  async function send() {
    const q = question.trim();
    if (!q || busy) return;
    setQuestion("");
    if (deep) { void sendDeep(q); return; }
    const idx = turns.length;
    onUpdateTurns((t) => [...t, newTurn(q, mode)]);
    const body: Record<string, unknown> = { message: q, corpus_id: corpusId, mode, require_retrieval: true };
    if (model) body.synthesizer = model;
    if (reasoning) body.reasoning = reasoning;
    if (corpusExplore) body.corpus_explorer = true;
    const id = session.id;
    const ac = beginStream(id);
    try {
      await runTurn(body, (patch) => {
        onUpdateTurns((ts) => ts.map((t, i) => (i === idx ? { ...t, ...patch } : t)));
      }, ac.signal);
    } finally {
      endStream(id, ac);
    }
  }

  /** Patch turn `idx`'s research state (DR7: it lives on the turn, so a chat switch keeps the plan card and the live view). */
  function patchRun(idx: number, patch: Partial<DeepRunState>, turn: Partial<Turn> = {}) {
    onUpdateTurns((ts) => ts.map((t, i) => (i === idx && t.deepRun ? { ...t, ...turn, deepRun: { ...t.deepRun, ...patch } } : t)));
  }

  /** A deep research turn: the same thread and frames, its own route and request. DR7a: the research is planned first and
   *  shown as a plan card the person confirms (it starts by itself after 10 s). The "start without showing the plan" setting,
   *  an older backend with no plan route, or a plan with no parts send it straight away, as before. The plan's wait is
   *  registered like a stream, so Stop in the composer (or Cancel on the card) drops it. */
  async function sendDeep(q: string) {
    const idx = turns.length;
    const request: DeepRunRequest = { corpusId, preset, mode, ...(model ? { synthesizer: model } : {}) };
    const id = session.id;
    const direct = loadSkipPlan();
    onUpdateTurns((ts) => [...ts, { ...newTurn(q, `DEEP · ${preset}`), deepRun: { status: direct ? "running" : "planning", request } }]);
    if (direct) { await startDeep(idx, q, request, null); return; }
    const ac = beginStream(id);
    ac.signal.addEventListener("abort", () => {
      onUpdateTurns((ts) => ts.map((t, i) => (i === idx && t.deepRun && !t.done && t.deepRun.status !== "running"
        ? { ...t, done: true, error: "cancelled", deepRun: { ...t.deepRun, status: "cancelled" } } : t)));
      setQuestion((cur) => cur || q);                    // the question comes back to the box, to edit and send again
    }, { once: true });
    try {
      const plan = await api.deepResearchPlan({ question: q, corpus_id: corpusId, preset, mode }, ac.signal);
      if (ac.signal.aborted) return;
      if (Array.isArray(plan?.goals) && plan.goals.length) { patchRun(idx, { status: "ready", plan }); return; }
      endStream(id, ac);
      await startDeep(idx, q, request, null);
    } catch (e) {
      if (ac.signal.aborted) return;
      endStream(id, ac);
      if (olderPlanBackend(e)) { await startDeep(idx, q, request, null); return; }
      patchRun(idx, { status: "cancelled" }, { done: true, error: e instanceof ApiError ? e.message : String(e) });
    }
  }

  /** Open the research stream for turn `idx`: the request Send captured, plus the confirmed plan (DR7a) when there is one. */
  async function startDeep(idx: number, q: string, request: DeepRunRequest, goals: DeepGoal[] | null, estimateS?: number) {
    patchRun(idx, { status: "running", goals, startedAt: Date.now(), estimateS: estimateS ?? presetSeconds(request.preset) });
    const deepRequest: Record<string, unknown> = { question: q, corpus_id: request.corpusId, preset: request.preset, mode: request.mode };
    if (request.synthesizer) deepRequest.synthesizer = request.synthesizer;
    if (goals) deepRequest.plan = goals.map(({ goal, query, move }) => ({ goal, query, move }));
    const id = session.id;
    const ac = beginStream(id);
    try {
      await runTurn(deepRequest, (patch) => {
        onUpdateTurns((ts) => ts.map((t, i) => (i === idx ? { ...t, ...patch } : t)));
      }, ac.signal, deepResearchStream);
    } finally {
      endStream(id, ac);
    }
  }

  /** DR7d "Research this next": the question goes into the box with Deep research on at the Quick depth; nothing is sent. */
  function researchNext(q: string) {
    setQuestion(q);
    setDeep(true);
    setPreset("quick");
    inputRef.current?.focus();
  }

  /** What a research turn's views may ask of this chat (DR7). */
  const research = (i: number, t: Turn): ResearchHandlers => ({
    onStart: (goals) => {
      if (t.deepRun) void startDeep(i, t.question, t.deepRun.request, goals, t.deepRun.plan?.estimate?.seconds);
    },
    onCancel: () => stopStream(session.id),
    onStop: () => stopStream(session.id),
    onRunPatch: (patch) => patchRun(i, patch),
    onResearchNext: researchNext,
  });

  return (
    <div className="screen screen--wide screen--chat chat">
      <h1 className="sr-only">Chat with {corpusId}</h1>
      <div className="chat__scroll" ref={scrollRef}>
        {turns.length === 0 ? (
          <div className="chat__welcome">
            <h2>Ask {corpusId}</h2>
            <p>Every answer cites the passages it rests on. When the library doesn't cover a question, the answer says so.</p>
            <div className="starters">
              {STARTERS.map((s) => (
                <button key={s} type="button" className="starter" onClick={() => { setQuestion(s); inputRef.current?.focus(); }}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat__thread">
            {turns.map((t, i) => (
              <TurnView key={i} t={t} models={synths.data ?? []} research={research(i, t)} />
            ))}
          </div>
        )}
      </div>

      <div className="chat__composer">
        {/* One rounded box, Claude-style: the text grows upward, the send / stop button sits inside.
            You can type the next question while an answer streams; it sends once that answer is done. */}
        <div className="composer" onClick={() => inputRef.current?.focus()}>
          <textarea
            ref={inputRef}
            className="composer__input"
            rows={1}
            placeholder={deep ? `Research ${corpusId} in depth…` : `Ask ${corpusId}…`}
            aria-label="Message"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              // Enter sends; Shift+Enter is a newline; never send mid IME composition
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <div className="composer__bar">
            <div className="composer__chips" onClick={(e) => e.stopPropagation()}>
              <label className="chip-field" title="How the library is searched">
                <span className="label">Retrieval</span>
                <select value={mode} onChange={(e) => setMode(e.target.value as PublicMode)}>
                  {PUBLIC_MODES.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </label>
              <div className="chip-field chip-field--model">
                <span className="label">Model</span>
                <ModelPicker synthesizers={synths.data ?? []} value={model} onChange={setModel} />
              </div>
              <label className="chip-field" title="How much the model reasons before answering">
                <span className="label">Reasoning</span>
                <select value={reasoning} onChange={(e) => setReasoning(e.target.value)}>
                  <option value="">{reasons.data?.default ?? "default"}</option>
                  {(reasons.data?.modes ?? []).map((m) => (
                    <option key={m.id} value={m.id} title={m.description}>{m.label}</option>
                  ))}
                </select>
              </label>
              <label className="chip-field chip-field--toggle"
                     title="Several rounds of searching and reading your library, then a report that cites every claim (about 1-3 minutes)">
                <input type="checkbox" checked={deep} onChange={(e) => setDeep(e.target.checked)} />
                <span className="label">Deep research</span>
              </label>
              {deep && (
                <label className="chip-field" title="How far the research goes">
                  <span className="label">Depth</span>
                  <select value={preset} onChange={(e) => setPreset(e.target.value)}>
                    <option value="quick">Quick</option>
                    <option value="standard">Standard</option>
                    <option value="thorough">Thorough</option>
                  </select>
                </label>
              )}
              {corpusExploreAvailable && !deep && (
                <label className="chip-field chip-field--toggle"
                       title="Bounded, corpus-grounded exploration: activate related concepts from your library and retrieve through a few grounded sub-questions.">
                  <input type="checkbox" checked={corpusExplore} onChange={(e) => setCorpusExplore(e.target.checked)} />
                  <span className="label">Corpus Explore</span>
                </label>
              )}
            </div>
            {busy ? (
              <button className="composer__send composer__send--stop" aria-label="Stop" title="Stop the answer"
                      onClick={(e) => { e.stopPropagation(); stopStream(session.id); }}>
                <Icon name="stop" size={14} />
              </button>
            ) : (
              <button className="composer__send" aria-label="Send" title="Send (Enter)" disabled={!question.trim()}
                      onClick={(e) => { e.stopPropagation(); void send(); }}>
                <Icon name="send" />
              </button>
            )}
          </div>
        </div>
        <div className="chat__hint">Enter to send · Shift+Enter for a new line</div>
      </div>
    </div>
  );
}

function TurnView({ t, models, research }: { t: Turn; models: Synthesizer[]; research?: ResearchHandlers }) {
  if (research && isResearchTurn(t)) return <ResearchTurnView t={t} models={models} {...research} />;   // DR7
  return (
    <>
      <div className="msg-user">
        <div className="msg-user__bubble">{t.question}</div>
      </div>
      <div className="msg-assistant">
        <ProcessRail phases={t.phases} live={!t.done} reasoning={t.reasoningText} />
        {t.error && <div className="answer answer-error">{t.error}</div>}
        {t.answerText ? (
          <>
            <AnswerBody t={t} models={models} />
            {t.done && <AnswerActions text={t.answerText} />}
          </>
        ) : t.done && !t.error ? (
          <div className="answer empty-answer">
            The model returned no answer text — it spent its token budget reasoning
            without committing a reply. Send again, or pick a lighter model.
          </div>
        ) : null}
      </div>
    </>
  );
}

/** Copy the answer (Markdown as written). The confirmation fades after two seconds. */
function AnswerActions({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="answer-actions">
      <button type="button" className="icon-btn icon-btn--sm" aria-label={copied ? "Copied" : "Copy answer"} title={copied ? "Copied" : "Copy answer"}
              onClick={() => { void copyText(text).then((ok) => { if (ok) { setCopied(true); setTimeout(() => setCopied(false), 2000); } }); }}>
        <Icon name={copied ? "check" : "copy"} size={15} />
      </button>
    </div>
  );
}
