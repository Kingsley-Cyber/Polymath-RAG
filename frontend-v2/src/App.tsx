import { useEffect, useMemo, useState } from "react";
import "./styles/app.css";
import "./styles/themes.css";
import { api } from "./lib/api";
import { useAsync } from "./lib/useAsync";
import { controlReady } from "./lib/readiness";
import { Pill } from "./components/Pill";
import { PhaseStub } from "./components/PhaseStub";
import { Overview } from "./screens/Overview";
import { Chat } from "./screens/Chat";
import { Files } from "./screens/Files";
import { ControlPlane } from "./screens/ControlPlane";
import { Graph } from "./screens/Graph";
import { Compare } from "./screens/Compare";

/** FRONTEND-V2-PLAN §1 — Chat · Files · Graph │ Control Plane · Settings.
 *  `glyph` is the collapsed-rail label (owner request 2026-09-12: side panel collapse). */
const NAV = [
  { id: "overview", label: "Overview", glyph: "◎" },
  { id: "chat", label: "Chat", glyph: "✦" },
  { id: "compare", label: "Compare", glyph: "⇄" },
  { id: "files", label: "Files", glyph: "▤" },
  { id: "graph", label: "Graph", glyph: "◈" },
  { id: "rule", label: "", glyph: "" },
  { id: "control", label: "Control Plane", glyph: "⚙" },
  { id: "settings", label: "Settings", glyph: "⋯" },
] as const;

type ScreenId = (typeof NAV)[number]["id"];

/** The nine palettes in styles/themes.css; the dot is that theme's accent. */
const THEMES = [
  { id: "", color: "#4c9aff", label: "V2 default" },
  { id: "obsidian", color: "#7da2f5", label: "Obsidian" },
  { id: "espresso", color: "#d29a63", label: "Espresso" },
  { id: "graphite", color: "#9db4d8", label: "Graphite" },
  { id: "champagne", color: "#a67c37", label: "Champagne" },
  { id: "nord", color: "#88c0d0", label: "Nord" },
  { id: "solar", color: "#b58900", label: "Solar" },
  { id: "rose", color: "#ea9ac6", label: "Rose" },
  { id: "slate", color: "#3b6fe0", label: "Slate" },
  { id: "paper", color: "#a4661b", label: "Paper" },
];

const THEME_KEY = "polymath-v2.theme";
const COLLAPSE_KEY = "polymath-v2.nav-collapsed";

export function App() {
  const [screen, setScreen] = useState<ScreenId>("overview");
  const [corpusId, setCorpusId] = useState<string>("rag-canary");
  const [theme, setTheme] = useState<string>(() => {
    try { return localStorage.getItem(THEME_KEY) ?? ""; } catch { return ""; }
  });
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === "1"; } catch { return false; }
  });

  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* private mode */ }
  }, [theme]);

  useEffect(() => {
    try { localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0"); } catch { /* private mode */ }
  }, [collapsed]);

  const corpora = useAsync((s) => api.corpora(s), []);
  const cp = useAsync((s) => api.controlPlane(corpusId, s), [corpusId]);
  const control = useMemo(() => controlReady(cp.data?.control_ready), [cp.data]);

  return (
    <div className={`shell${collapsed ? " shell--collapsed" : ""}`}>
      <nav className="nav">
        <div className="nav__top">
          <div className="nav__brand">Polymath</div>
          <button
            className="nav__collapse"
            onClick={() => setCollapsed((c) => !c)}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? "»" : "«"}
          </button>
        </div>

        {NAV.map((n) =>
          n.id === "rule" ? (
            <div className="nav__rule" key="rule" />
          ) : (
            <button
              key={n.id}
              className="nav__item"
              data-glyph={n.glyph}
              title={collapsed ? n.label : undefined}
              aria-current={screen === n.id ? "page" : undefined}
              onClick={() => setScreen(n.id)}
            >
              <span>{n.label}</span>
            </button>
          ),
        )}

        <div className="nav__spacer" />

        <div className="field nav__corpus" style={{ padding: "0 10px 10px" }}>
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

        <div className="nav__themes">
          <span className="label">Theme</span>
          <div className="themes">
            {THEMES.map((t) => (
              <button
                key={t.id || "default"}
                className="theme-swatch"
                style={{ background: t.color }}
                aria-pressed={theme === t.id}
                title={t.label}
                aria-label={t.label}
                onClick={() => setTheme(t.id)}
              />
            ))}
          </div>
        </div>

        <div className="nav__health">
          <span className="label">Control</span>
          <Pill v={control} />
        </div>
      </nav>

      <main className="main">
        {screen === "overview" && <Overview corpusId={corpusId} />}
        {screen === "chat" && <Chat corpusId={corpusId} />}
        {screen === "compare" && <Compare corpusId={corpusId} />}
        {screen === "files" && <Files corpusId={corpusId} />}
        {screen === "control" && <ControlPlane corpusId={corpusId} />}
        {screen === "graph" && <Graph corpusId={corpusId} />}

        {screen === "settings" && (
          <div className="screen">
            <div className="screen__head">
              <h1 className="screen__title">{NAV.find((n) => n.id === screen)?.label}</h1>
              <p className="screen__sub">Corpus <span className="mono">{corpusId}</span></p>
            </div>
            {screen === "settings" && <PhaseStub phase="F1" title="Settings — backend target, policy flags (read-only mirrors of the server's own state)" />}
          </div>
        )}
      </main>
    </div>
  );
}
