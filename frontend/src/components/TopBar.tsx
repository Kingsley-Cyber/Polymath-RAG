import type { Corpus, Mode, ReasoningModeInfo, Synthesizer } from "../types";

export const THEMES = [
  { id: "obsidian", color: "#7da2f5" },
  { id: "espresso", color: "#d29a63" },
  { id: "graphite", color: "#9db4d8" },
  { id: "champagne", color: "#a67c37" },
  { id: "nord", color: "#88c0d0" },
  { id: "solar", color: "#b58900" },
  { id: "rose", color: "#ea9ac6" },
  { id: "slate", color: "#3b6fe0" },
  { id: "paper", color: "#a4661b" },
];

const MODES: Mode[] = ["VECTOR", "HYBRID", "GRAPH", "ASK"];

export default function TopBar({
  corpora,
  corpus,
  mode,
  synthesizers,
  synthesizer,
  reasoningModes,
  reasoning,
  theme,
  onCorpus,
  onMode,
  onSynthesizer,
  onReasoning,
  onTheme,
}: {
  corpora: Corpus[];
  corpus: string;
  mode: Mode;
  synthesizers: Synthesizer[];
  synthesizer: string;
  reasoningModes: ReasoningModeInfo[];
  reasoning: string;
  theme: string;
  onCorpus: (c: string) => void;
  onMode: (m: Mode) => void;
  onSynthesizer: (s: string) => void;
  onReasoning: (r: string) => void;
  onTheme: (t: string) => void;
}) {
  return (
    <div className="topbar">
      <div className="control">
        <label>Corpus</label>
        <select value={corpus} onChange={(e) => onCorpus(e.target.value)}>
          <option value="">— select —</option>
          {corpora.map((c) => (
            <option key={c.corpus_id} value={c.corpus_id}>
              {c.name || c.corpus_id} ({c.documents}
              {c.query_ready ? " · ready" : " · not ready"})
            </option>
          ))}
        </select>
        <button
          className="chunk-chip"
          title="Create a new corpus: pick an id, then drop files into it in the Files tab — the corpus is created on first upload."
          onClick={() => {
            const id = window.prompt(
              "New corpus id (lowercase letters, digits, dashes):");
            if (!id) return;
            const slug = id.trim().toLowerCase();
            if (!/^[a-z0-9][a-z0-9-]{1,60}$/.test(slug)) {
              window.alert("Invalid id — use lowercase letters, digits, dashes.");
              return;
            }
            onCorpus(slug);
            window.alert(
              `Corpus "${slug}" selected. Go to Files and drop documents in — the corpus is created with the first upload.`);
          }}
        >
          ＋ new
        </button>
      </div>
      <div className="control">
        <label>Retrieval</label>
        <div className="mode-pills">
          {MODES.map((m) => (
            <button
              key={m}
              className={`mode-pill${m === mode ? " active" : ""}`}
              onClick={() => onMode(m)}
              title={
                m === "VECTOR"
                  ? "Hierarchical dense retrieval"
                  : m === "HYBRID"
                    ? "Dense + lexical"
                    : m === "GRAPH"
                      ? "Hybrid + canonical fact graph"
                      : "Stored knowledge objects"
              }
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      {reasoningModes.length > 0 && (
        <div className="control">
          <label>Reasoning</label>
          <select
            value={reasoning}
            onChange={(e) => onReasoning(e.target.value)}
          >
            {reasoningModes.map((r) => (
              <option key={r.id} value={r.id} title={r.description}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="control">
        <label>Model</label>
        <select
          value={synthesizer}
          onChange={(e) => onSynthesizer(e.target.value)}
        >
          {synthesizers.map((s) => (
            <option key={s.id} value={s.id} title={s.description}>
              {s.label}
            </option>
          ))}
        </select>
      </div>
      <div className="spacer" />
      <div className="control">
        <label>Theme</label>
        <div className="themes">
          {THEMES.map((t) => (
            <button
              key={t.id}
              className={`theme-swatch${t.id === theme ? " active" : ""}`}
              style={{ background: t.color }}
              title={t.id}
              onClick={() => onTheme(t.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
