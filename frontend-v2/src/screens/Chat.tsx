import { useRef, useState } from "react";
import { api } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { PUBLIC_MODES } from "../lib/contracts";
import type { PublicMode } from "../lib/contracts";
import { newTurn, runTurn, type Turn } from "../lib/chat";
import { QueryTrace } from "../components/QueryTrace";
import { EvidenceInspector } from "../components/EvidenceInspector";

/**
 * F2 + F3 — Chat with corpus, retrieval mode, intent, model, reasoning and streaming.
 *
 * FRONTEND-V2-PLAN §2: VECTOR is NOT offered; it is a backend primitive. Intent is
 * Auto — the compiler classifies it and we display it READ-ONLY, because there is no
 * intent-override contract and POLYMATH_CHAT_INTENT_POLICY is off, so a displayed
 * intent is honest but inert for routing. The UI says exactly that rather than
 * implying a control that does not exist.
 */
export function Chat({ corpusId }: { corpusId: string }) {
  const [mode, setMode] = useState<PublicMode>("HYBRID");
  const [model, setModel] = useState<string>("");
  const [reasoning, setReasoning] = useState<string>("");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);

  const synths = useAsync((s) => api.synthesizers(s), []);
  const reasons = useAsync((s) => api.reasoningModes(s), []);

  async function send() {
    const q = question.trim();
    if (!q || busy) return;
    setBusy(true);
    setQuestion("");
    const idx = turns.length;
    setTurns((t) => [...t, newTurn(q, mode)]);
    const ac = new AbortController();
    abort.current = ac;
    const body: Record<string, unknown> = { message: q, corpus_id: corpusId, mode };
    if (model) body.synthesizer = model;
    if (reasoning) body.reasoning = reasoning;
    await runTurn(body, (patch) => {
      setTurns((ts) => ts.map((t, i) => (i === idx ? { ...t, ...patch } : t)));
    }, ac.signal);
    setBusy(false);
    abort.current = null;
  }

  return (
    <div className="screen screen--wide">
      <div className="screen__head">
        <h1 className="screen__title">Chat</h1>
        <p className="screen__sub">
          Corpus <span className="mono">{corpusId}</span> · retrieval runs on the final core
        </p>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <div className="row" style={{ gap: 14, alignItems: "flex-end" }}>
          <div className="field">
            <span className="label">Retrieval</span>
            <select value={mode} onChange={(e) => setMode(e.target.value as PublicMode)}>
              {PUBLIC_MODES.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div className="field">
            <span className="label">Intent</span>
            <select value="auto" disabled title="The compiler classifies intent; there is no override contract.">
              <option value="auto">Auto (classified)</option>
            </select>
          </div>
          <div className="field" style={{ minWidth: 260 }}>
            <span className="label">Model</span>
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="">backend default</option>
              {(synths.data ?? []).map((s) => {
                const id = s.id ?? s.name ?? "";
                return <option key={id} value={id}>{id}</option>;
              })}
            </select>
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
        </div>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <div className="row">
          <input
            type="text" style={{ flex: 1, minWidth: 300 }}
            placeholder={`Ask ${corpusId}…`}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") void send(); }}
            disabled={busy}
          />
          <button className="btn btn--primary" onClick={() => void send()} disabled={busy || !question.trim()}>
            {busy ? "Streaming…" : "Send"}
          </button>
          {busy && <button className="btn" onClick={() => abort.current?.abort()}>Stop</button>}
        </div>
      </div>

      {turns.length === 0 && <div className="empty">No turns yet.</div>}

      <div className="stack">
        {turns.slice().reverse().map((t, i) => <TurnView key={turns.length - 1 - i} t={t} />)}
      </div>
    </div>
  );
}

function TurnView({ t }: { t: Turn }) {
  const intent = t.receipt?.chat_plan?.intent;
  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong>{t.question}</strong>
        <span className="row" style={{ gap: 6 }}>
          <span className="pill pill--unknown">{t.mode}</span>
          {intent && (
            <span className="pill pill--unknown" title="Classified by the compiler. POLYMATH_CHAT_INTENT_POLICY is OFF, so this is honest but inert for routing.">
              ⌖ {String(intent)}
            </span>
          )}
          {t.receipt?.engine && <span className="pill pill--unknown">{t.receipt.engine}</span>}
          {t.latencyMs != null && <span className="faint mono">{(t.latencyMs / 1000).toFixed(1)}s</span>}
        </span>
      </div>

      {t.phases.length > 0 && !t.done && (
        <div className="row mono faint" style={{ marginTop: 8, gap: 6 }}>
          {t.phases.map((p, i) => <span key={i}>{p.name}{i < t.phases.length - 1 ? " ›" : " …"}</span>)}
        </div>
      )}

      {t.error && <div className="banner banner--bad" style={{ marginTop: 10 }}>{t.error}</div>}

      {t.answerText && (
        <div style={{ marginTop: 12, whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{t.answerText}</div>
      )}

      {t.receipt && (
        <>
          <details style={{ marginTop: 12 }}>
            <summary className="label" style={{ cursor: "pointer" }}>Query trace</summary>
            <div style={{ marginTop: 10 }}>
              <QueryTrace receipt={t.receipt} requestedMode={t.mode} />
            </div>
          </details>
          <details style={{ marginTop: 8 }}>
            <summary className="label" style={{ cursor: "pointer" }}>Evidence</summary>
            <div style={{ marginTop: 10 }}>
              <EvidenceInspector receipt={t.receipt} />
            </div>
          </details>
        </>
      )}
    </div>
  );
}
