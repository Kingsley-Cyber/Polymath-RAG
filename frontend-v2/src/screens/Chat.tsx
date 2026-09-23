import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { PUBLIC_MODES } from "../lib/contracts";
import type { PublicMode, Synthesizer } from "../lib/contracts";
import { beginStream, endStream, newTurn, runTurn, stopStream, type Turn } from "../lib/chat";
import { ProcessRail } from "../components/ProcessRail";
import { AnswerBody } from "../components/AnswerBody";
import { ModelPicker } from "../components/ModelPicker";
import type { ChatSession } from "../lib/chatStore";

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
export function Chat({
  corpusId,
  session,
  onUpdateTurns,
}: {
  corpusId: string;
  /** CHAT-HISTORY-V1: the session being viewed. App creates it before this screen mounts. */
  session: ChatSession;
  /** Apply a change to THIS session's turns in App's store. */
  onUpdateTurns: (fn: (turns: Turn[]) => Turn[]) => void;
}) {
  const [mode, setMode] = useState<PublicMode>("HYBRID");
  const [model, setModel] = useState<string>("");
  const [reasoning, setReasoning] = useState<string>("");
  const [corpusExplore, setCorpusExplore] = useState(false);
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

  async function send() {
    const q = question.trim();
    if (!q || busy) return;
    setQuestion("");
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

  return (
    <div className="screen screen--wide screen--chat chat">
      <div className="screen__head">
        <h1 className="screen__title">Chat</h1>
        <p className="screen__sub">
          Corpus <span className="mono">{corpusId}</span> · every message searches this corpus
        </p>
      </div>

      <div className="card" style={{ marginBottom: 12 }}>
        <div className="row" style={{ gap: 14, alignItems: "flex-end" }}>
          <div className="field">
            <span className="label">Retrieval</span>
            <select value={mode} onChange={(e) => setMode(e.target.value as PublicMode)}>
              {PUBLIC_MODES.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div className="field" style={{ minWidth: 260 }}>
            <span className="label">Model</span>
            <ModelPicker synthesizers={synths.data ?? []} value={model} onChange={setModel} />
          </div>
          <div className="field">
            <span className="label">Reasoning</span>
            <select value={reasoning} onChange={(e) => setReasoning(e.target.value)}>
              <option value="">{reasons.data?.default ?? "default"}</option>
              {(reasons.data?.modes ?? []).map((m) => (
                <option key={m.id} value={m.id} title={m.description}>{m.label}</option>
              ))}
            </select>
          </div>
          {corpusExploreAvailable && (
            <div className="field">
              <span className="label">Corpus Explore</span>
              <label
                style={{ display: "flex", alignItems: "center", gap: 6, height: 32 }}
                title="Bounded, corpus-grounded exploration: activate related concepts from your library and retrieve through a few grounded sub-questions."
              >
                <input type="checkbox" checked={corpusExplore} onChange={(e) => setCorpusExplore(e.target.checked)} />
                <span>{corpusExplore ? "On" : "Off"}</span>
              </label>
            </div>
          )}
        </div>
      </div>

      <div className="chat__scroll" ref={scrollRef}>
        {turns.length === 0 ? (
          <div className="chat__welcome">
            <h2>Grounded answers, exact evidence.</h2>
            <p>
              Ask <span className="mono">{corpusId}</span> anything. Unsupported questions
              abstain — by design.
            </p>
          </div>
        ) : (
          <div className="chat__thread">
            {turns.map((t, i) => (
              <TurnView key={i} t={t} models={synths.data ?? []} />
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
            placeholder={`Ask ${corpusId}…`}
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
            <span className="composer__meta">{mode} · {corpusId}</span>
            {busy ? (
              <button className="composer__send composer__send--stop" aria-label="Stop" title="Stop the answer"
                      onClick={(e) => { e.stopPropagation(); stopStream(session.id); }}>
                <span aria-hidden="true">■</span>
              </button>
            ) : (
              <button className="composer__send" aria-label="Send" title="Send (Enter)" disabled={!question.trim()}
                      onClick={(e) => { e.stopPropagation(); void send(); }}>
                <span aria-hidden="true">↑</span>
              </button>
            )}
          </div>
        </div>
        <div className="chat__hint">
          Enter to send · Shift+Enter for a newline · answers cite exact source spans
        </div>
      </div>
    </div>
  );
}

function TurnView({ t, models }: { t: Turn; models: Synthesizer[] }) {
  return (
    <>
      <div className="msg-user">
        <div className="msg-user__bubble">{t.question}</div>
      </div>
      <div className="msg-assistant">
        <ProcessRail phases={t.phases} live={!t.done} reasoning={t.reasoningText} />
        {t.error && <div className="answer answer-error">{t.error}</div>}
        {t.answerText ? (
          <AnswerBody t={t} models={models} />
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
