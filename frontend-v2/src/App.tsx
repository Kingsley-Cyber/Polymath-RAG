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
import { Models } from "./screens/Models";
import {
  emptySession, loadSessions, saveSessions, titleFor, type ChatSession,
} from "./lib/chatStore";

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
  { id: "models", label: "Models", glyph: "❋" },
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

  // CHAT-HISTORY-V1 — sessions live at app level so the sidebar can list them.
  const [sessions, setSessions] = useState<ChatSession[]>(() => loadSessions());
  const [activeChatId, setActiveChatId] = useState<string>("");

  useEffect(() => { saveSessions(sessions); }, [sessions]);

  const activeChat =
    sessions.find((s) => s.id === activeChatId) ?? null;

  function startChat() {
    const s = emptySession(corpusId);
    setSessions((xs) => [s, ...xs]);
    setActiveChatId(s.id);
    setScreen("chat");
  }

  function openChat(id: string) {
    setActiveChatId(id);
    setScreen("chat");
  }

  function deleteChat(id: string) {
    setSessions((xs) => xs.filter((s) => s.id !== id));
    setActiveChatId((cur) => (cur === id ? "" : cur));
  }

  /** Chat.tsx owns the live turns; it hands them back so they persist. */
  function updateChat(id: string, turns: ChatSession["turns"]) {
    setSessions((xs) =>
      xs.map((s) =>
        s.id === id
          ? { ...s, turns, updatedAt: Date.now(), title: titleFor({ ...s, turns }) }
          : s,
      ),
    );
  }

  const [corporaNonce, setCorporaNonce] = useState(0);
  const corpora = useAsync((s) => api.corpora(s), [corporaNonce]);

  // OWNER-DESTRUCTIVE: wipe a corpus and everything derived from it. The backend requires
  // confirm==corpus_id, so we make the user type the corpus name — a typed confirm, not a
  // one-click delete. On success we refetch the list and switch to another corpus.
  async function deleteCorpus() {
    const typed = window.prompt(
      `Permanently delete corpus "${corpusId}" and EVERYTHING in it — documents, vectors, ` +
      `graph substrate? This cannot be undone.\n\nType the corpus name to confirm:`);
    if (typed == null) return;
    if (typed !== corpusId) { window.alert(`"${typed}" does not match "${corpusId}" — nothing deleted.`); return; }
    try {
      await api.deleteCorpus(corpusId, corpusId);
      const remaining = (corpora.data ?? []).filter((c) => c.corpus_id !== corpusId);
      setCorporaNonce((n) => n + 1);
      if (remaining[0]) setCorpusId(remaining[0].corpus_id);
    } catch (e) {
      window.alert(`Delete failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

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

        <button className="nav__newchat" data-glyph="＋" onClick={startChat}
                title={collapsed ? "New chat" : undefined}>
          <span>＋ New chat</span>
        </button>

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

        {sessions.length > 0 && (
          <div className="nav__chats">
            <span className="label">Chats</span>
            {sessions.map((s) => (
              <div
                key={s.id}
                className="nav__chat"
                aria-current={screen === "chat" && s.id === activeChatId ? "page" : undefined}
              >
                <button className="nav__chat-open" title={s.title} onClick={() => openChat(s.id)}>
                  {s.title}
                </button>
                <button className="nav__chat-del" title="Delete chat"
                        aria-label={`Delete ${s.title}`} onClick={() => deleteChat(s.id)}>
                  ✕
                </button>
              </div>
            ))}
          </div>
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
          <button className="btn nav__corpus-del" onClick={() => void deleteCorpus()}
                  title={`Delete corpus ${corpusId}`} disabled={!corpusId}>
            Delete corpus
          </button>
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
        {screen === "chat" && (
          <Chat
            key={activeChat?.id ?? "scratch"}
            corpusId={corpusId}
            session={activeChat}
            onTurns={(turns) => {
              if (activeChat) updateChat(activeChat.id, turns);
              else {
                // first message with no session selected starts one
                const s = { ...emptySession(corpusId), turns };
                setSessions((xs) => [{ ...s, title: titleFor(s) }, ...xs]);
                setActiveChatId(s.id);
              }
            }}
          />
        )}
        {screen === "compare" && <Compare corpusId={corpusId} />}
        {screen === "files" && <Files corpusId={corpusId} />}
        {screen === "control" && <ControlPlane corpusId={corpusId} />}
        {screen === "graph" && <Graph corpusId={corpusId} />}
        {screen === "models" && <Models />}

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
