import type { Corpus, Mode, Synthesizer } from "../types";

export const THEMES = [
  { id: "obsidian", color: "#6c9ef8" },
  { id: "nord", color: "#88c0d0" },
  { id: "forest", color: "#6fd08c" },
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
  theme,
  onCorpus,
  onMode,
  onSynthesizer,
  onTheme,
}: {
  corpora: Corpus[];
  corpus: string;
  mode: Mode;
  synthesizers: Synthesizer[];
  synthesizer: string;
  theme: string;
  onCorpus: (c: string) => void;
  onMode: (m: Mode) => void;
  onSynthesizer: (s: string) => void;
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
              {c.corpus_id} ({c.documents}
              {c.query_ready ? " · ready" : " · not ready"})
            </option>
          ))}
        </select>
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
