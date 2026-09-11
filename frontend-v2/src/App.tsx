import { useMemo, useState } from "react";
import "./styles/app.css";
import { api } from "./lib/api";
import { useAsync } from "./lib/useAsync";
import { controlReady } from "./lib/readiness";
import { Pill } from "./components/Pill";
import { PhaseStub } from "./components/PhaseStub";
import { Overview } from "./screens/Overview";
import { Chat } from "./screens/Chat";

/** FRONTEND-V2-PLAN §1 — Chat · Files · Graph │ Control Plane · Settings. */
const NAV = [
  { id: "overview", label: "Overview" },
  { id: "chat", label: "Chat" },
  { id: "files", label: "Files" },
  { id: "graph", label: "Graph" },
  { id: "rule", label: "" },
  { id: "control", label: "Control Plane" },
  { id: "settings", label: "Settings" },
] as const;

type ScreenId = (typeof NAV)[number]["id"];

export function App() {
  const [screen, setScreen] = useState<ScreenId>("overview");
  const [corpusId, setCorpusId] = useState<string>("rag-canary");

  const corpora = useAsync((s) => api.corpora(s), []);
  const ready = useAsync((s) => api.ready(s), []);
  const pipeline = useAsync((s) => api.pipelineHealth(s), []);
  const control = useMemo(() => controlReady(ready.data, pipeline.data), [ready.data, pipeline.data]);

  return (
    <div className="shell">
      <nav className="nav">
        <div className="nav__brand">Polymath</div>

        {NAV.map((n) =>
          n.id === "rule" ? (
            <div className="nav__rule" key="rule" />
          ) : (
            <button
              key={n.id}
              className="nav__item"
              aria-current={screen === n.id ? "page" : undefined}
              onClick={() => setScreen(n.id)}
            >
              {n.label}
            </button>
          ),
        )}

        <div className="nav__spacer" />

        <div className="field" style={{ padding: "0 10px 10px" }}>
          <span className="label">Corpus</span>
          <select value={corpusId} onChange={(e) => setCorpusId(e.target.value)}>
            {(corpora.data ?? []).map((c) => (
              <option key={c.corpus_id} value={c.corpus_id}>
                {c.corpus_id} ({c.documents})
              </option>
            ))}
            {!corpora.data && <option value={corpusId}>{corpusId}</option>}
          </select>
        </div>

        <div className="nav__health">
          <span className="label">Control</span>
          <Pill v={control} />
        </div>
      </nav>

      <main className="main">
        {screen === "overview" && <Overview corpusId={corpusId} />}
        {screen === "chat" && <Chat corpusId={corpusId} />}

        {screen !== "overview" && screen !== "chat" && (
          <div className="screen">
            <div className="screen__head">
              <h1 className="screen__title">{NAV.find((n) => n.id === screen)?.label}</h1>
              <p className="screen__sub">Corpus <span className="mono">{corpusId}</span></p>
            </div>
            {screen === "files" && <PhaseStub phase="F8" title="Files — Control / Semantic / vNext readiness per document, plus Graph, Profile, Atoms, pMAP" />}
            {screen === "graph" && <PhaseStub phase="F9" title="Graph — entity search, relationships, source-attested supporting chunks" />}
            {screen === "control" && <PhaseStub phase="F10" title="Control Plane — GRAPH_EXTRACTION, DOCUMENT_PROFILE, PMAP, CHAT function cards" />}
            {screen === "settings" && <PhaseStub phase="F1" title="Settings — backend target, policy flags (read-only mirrors of the server's own state)" />}
          </div>
        )}
      </main>
    </div>
  );
}
