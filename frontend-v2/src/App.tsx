import { useCallback, useEffect, useMemo, useState } from "react";
import "./styles/tokens.css";
import "./styles/app.css";
import { api, ApiError, AUTH_REQUIRED_EVENT } from "./lib/api";
import { useAppearance } from "./lib/appearance";
import { auth, LEGACY_OWNER, privateLibrary, type Me } from "./lib/auth";
import { useAsync } from "./lib/useAsync";
import { controlReady } from "./lib/readiness";
import { Pill } from "./components/Pill";
import { Overview } from "./screens/Overview";
import { Chat } from "./screens/Chat";
import { stopStream } from "./lib/chat";
import { Files } from "./screens/Files";
import { ControlPlane } from "./screens/ControlPlane";
import { Graph } from "./screens/Graph";
import { Compare } from "./screens/Compare";
import { Models } from "./screens/Models";
import { ChangePassword, Login } from "./screens/Login";
import { Settings } from "./screens/Settings";
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

/** FRIENDS-ACCESS-V1: screens whose data is owner-only on the server (control plane, LLM providers) — hidden from friends. */
const OWNER_SCREENS = new Set<ScreenId>(["overview", "control", "models"]);

const COLLAPSE_KEY = "polymath-v2.nav-collapsed";
const CORPUS_KEY = "polymath-v2.corpus";

/** Screens whose data is scoped to a corpus. These render only once a valid corpus is
 *  resolved from `/corpora`, so no corpus-scoped request ever fires for an unresolved
 *  or non-existent id (FRONTEND-V2-CORPUS-RESOLUTION). Models/Settings are corpus-free. */
const CORPUS_SCREENS = new Set<ScreenId>(["overview", "chat", "compare", "files", "control", "graph"]);

/** FRIENDS-ACCESS-V1 — the sign-in gate. The server's web boundary decides who is calling; this asks `/auth/me`, shows
 *  the sign-in screen on 401, the first-password change when required, and the workspace otherwise. The owner on
 *  http://127.0.0.1:7200 is signed in by being local (no login exists there). */
export function App() {
  useAppearance();                           // keeps System mode in step with the OS setting, on every screen incl. sign-in
  const [me, setMe] = useState<Me | null>(null);
  const [state, setState] = useState<"loading" | "signin" | "ready" | "error">("loading");
  const [error, setError] = useState("");

  const check = useCallback(async () => {
    try {
      setMe(await auth.me());
      setState("ready");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { setMe(null); setState("signin"); return; }
      if (e instanceof ApiError && e.status === 404) { setMe(LEGACY_OWNER); setState("ready"); return; }   // no logins on this backend
      setError(e instanceof ApiError ? e.detailMessage : String(e));
      setState("error");
    }
  }, []);

  useEffect(() => { void check(); }, [check]);
  useEffect(() => {
    const onAuth = () => { setMe(null); setState("signin"); };
    window.addEventListener(AUTH_REQUIRED_EVENT, onAuth);
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, onAuth);
  }, []);

  async function signOut() {
    try { await auth.logout(); } catch { /* the cookies are cleared either way */ }
    setMe(null);
    setState("signin");
  }

  if (state === "loading") return <div className="auth"><div className="card auth__card">Loading…</div></div>;
  if (state === "error") return <div className="auth"><div className="card auth__card banner banner--bad">{error}</div></div>;
  if (state === "signin" || !me) return <Login onSignedIn={(m) => { setMe(m); setState("ready"); }} />;
  if (me.must_change_password) return <ChangePassword me={me} forced onChanged={setMe} onSignOut={() => void signOut()} />;
  return <Workspace me={me} onMeChanged={setMe} onSignOut={() => void signOut()} />;
}

function Workspace({ me, onMeChanged, onSignOut }: { me: Me; onMeChanged: (me: Me) => void; onSignOut: () => void }) {
  const owner = me.is_owner;
  const nav = useMemo(() => NAV.filter((n) => owner || !OWNER_SCREENS.has(n.id)), [owner]);
  const [screen, setScreen] = useState<ScreenId>(owner ? "overview" : "chat");
  // Never hardcode a corpus. Start from the persisted choice (validated against the
  // backend below); "" means "unresolved" until /corpora answers.
  const [corpusId, setCorpusId] = useState<string>(() => {
    try { return localStorage.getItem(CORPUS_KEY) ?? ""; } catch { return ""; }
  });
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === "1"; } catch { return false; }
  });

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
    // reuse a blank "New chat" if one is already open, instead of stacking more blanks
    const blank = sessions.find((s) => s.turns.length === 0);
    if (blank) {
      setActiveChatId(blank.id);
      setScreen("chat");
      return;
    }
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
    stopStream(id);
    setSessions((xs) => xs.filter((s) => s.id !== id));
    setActiveChatId((cur) => (cur === id ? "" : cur));
  }

  /** Apply `fn` to one chat's turns. App owns the turns, keyed by chat id, and Chat.tsx only shows them:
   *  a stream writes here through a functional update, so its answer still lands in ITS chat after the
   *  user opens another one (which unmounts the Chat screen that sent it). */
  function updateTurns(id: string, fn: (turns: ChatSession["turns"]) => ChatSession["turns"]) {
    setSessions((xs) =>
      xs.map((s) => {
        if (s.id !== id) return s;
        const turns = fn(s.turns);
        return { ...s, turns, updatedAt: Date.now(), title: titleFor({ ...s, turns }) };
      }),
    );
  }

  const [corporaNonce, setCorporaNonce] = useState(0);
  const corpora = useAsync((s) => api.corpora(s), [corporaNonce]);

  // /corpora is the backend authority for which corpora exist and are query-enabled.
  const corpusList = useMemo(() => {
    const list = corpora.data ?? [];
    const mine = privateLibrary(me);
    if (!mine || list.some((c) => c.corpus_id === mine)) return list;
    return [...list, { corpus_id: mine, purpose: "private", query_enabled: false, documents: 0, query_ready: false, name: mine }];
  }, [corpora.data, me]);
  const corporaLoaded = corpora.data != null || corpora.error != null;
  const corpusValid = corpusId !== "" && corpusList.some((c) => c.corpus_id === corpusId);

  // Resolve the session before mounting Chat. Creating it after the first pending
  // turn changed Chat's key mid-stream and discarded the component receiving SSE.
  useEffect(() => {
    if (screen === "chat" && corpusValid && !activeChat) startChat();
  }, [screen, corpusValid, activeChat]);

  // CORPUS RESOLUTION — derive the active corpus from backend authority, never a
  // hardcoded name. Priority: (1) the persisted/current corpus if it still exists,
  // (2) the first query-enabled corpus, (3) the first corpus, (4) none → empty state.
  // Runs once /corpora loads and again whenever the current id stops being valid
  // (e.g. the selected corpus was just deleted).
  useEffect(() => {
    if (!corpora.data) return;              // wait for the backend authority
    if (corpusValid) return;                // a still-valid persisted/current id wins
    const next = corpusList.find((c) => c.query_ready)?.corpus_id
      ?? corpusList[0]?.corpus_id ?? "";    // "" only when the backend has no corpora
    setCorpusId(next);
  }, [corpora.data, corpusValid, corpusList]);

  // Persist the resolved corpus so a refresh/deep-link re-resolves to it (priority 1).
  useEffect(() => {
    if (corpusId) { try { localStorage.setItem(CORPUS_KEY, corpusId); } catch { /* private mode */ } }
  }, [corpusId]);

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

  // Only probe control-plane readiness once a real corpus is resolved — never for the
  // unresolved "" or a stale persisted id (that was the transient 404 on cold load).
  const cp = useAsync(
    (s) => (corpusValid && owner ? api.controlPlane(corpusId, s) : Promise.resolve(null)),
    [corpusId, corpusValid, owner],
  );
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

        {nav.map((n) =>
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
          <select value={corpusValid ? corpusId : ""} onChange={(e) => setCorpusId(e.target.value)}>
            {!corpusValid && (
              <option value="" disabled>
                {!corporaLoaded ? "Loading…" : corpusList.length ? "Select corpus…" : "No corpora"}
              </option>
            )}
            {corpusList.map((c) => (
              <option key={c.corpus_id} value={c.corpus_id}>
                {c.corpus_id} ({c.documents})
              </option>
            ))}
          </select>
          {owner && (
            <button className="btn nav__corpus-del" onClick={() => void deleteCorpus()}
                    title={`Delete corpus ${corpusId}`} disabled={!corpusValid}>
              Delete corpus
            </button>
          )}
        </div>

        {owner && (
          <div className="nav__health">
            <span className="label">Control</span>
            <Pill v={control} />
          </div>
        )}
      </nav>

      <main className="main">
        {CORPUS_SCREENS.has(screen) && !corpusValid ? (
          <div className="screen">
            <div className="screen__head">
              <h1 className="screen__title">
                {corporaLoaded && !corpusList.length ? "No corpora yet" : "Resolving corpus…"}
              </h1>
              <p className="screen__sub">
                {corporaLoaded && !corpusList.length
                  ? "Nothing is indexed on this backend yet — ingest a corpus to begin."
                  : "Reading the corpus list from the backend."}
              </p>
            </div>
          </div>
        ) : (
          <>
        {screen === "overview" && owner && <Overview corpusId={corpusId} />}
        {screen === "chat" && activeChat && (
          <Chat
            key={activeChat.id}
            corpusId={corpusId}
            session={activeChat}
            onUpdateTurns={(fn) => updateTurns(activeChat.id, fn)}
          />
        )}
        {screen === "compare" && <Compare corpusId={corpusId} />}
        {screen === "files" && <Files corpusId={corpusId} />}
        {screen === "control" && owner && <ControlPlane corpusId={corpusId} />}
        {screen === "graph" && <Graph corpusId={corpusId} />}
        {screen === "models" && owner && <Models />}

        {screen === "settings" && <Settings me={me} onMeChanged={onMeChanged} onSignOut={onSignOut} />}
          </>
        )}
      </main>
    </div>
  );
}
