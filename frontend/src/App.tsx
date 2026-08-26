import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCorpora, fetchSynthesizers, streamChat } from "./api";
import ChatView from "./components/ChatView";
import FilesView from "./components/FilesView";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import type { Chat, Corpus, Message, Mode, Synthesizer } from "./types";

const STORE = "polymath.chats.v1";
const THEME_KEY = "polymath.theme";

const uid = () => Math.random().toString(36).slice(2, 10);

function loadChats(): Chat[] {
  try {
    return JSON.parse(localStorage.getItem(STORE) || "[]");
  } catch {
    return [];
  }
}

export default function App() {
  const [chats, setChats] = useState<Chat[]>(loadChats);
  const [activeId, setActiveId] = useState<string | null>(
    () => loadChats()[0]?.id ?? null,
  );
  const [view, setView] = useState<"chat" | "files">("chat");
  const [corpora, setCorpora] = useState<Corpus[]>([]);
  const [synths, setSynths] = useState<Synthesizer[]>([]);
  const [busy, setBusy] = useState(false);
  const [theme, setTheme] = useState(
    () => localStorage.getItem(THEME_KEY) || "obsidian",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(STORE, JSON.stringify(chats.slice(0, 60)));
  }, [chats]);

  useEffect(() => {
    fetchCorpora().then(setCorpora).catch(() => setCorpora([]));
    fetchSynthesizers()
      .then(setSynths)
      .catch(() =>
        setSynths([
          {
            id: "deterministic-template-v3",
            label: "Deterministic · grounded",
            description: "",
          },
        ]),
      );
  }, []);

  const active = useMemo(
    () => chats.find((c) => c.id === activeId) ?? null,
    [chats, activeId],
  );

  const patchChat = useCallback((id: string, fn: (c: Chat) => Chat) => {
    setChats((cs) => cs.map((c) => (c.id === id ? fn(c) : c)));
  }, []);

  const newChat = useCallback(() => {
    const c: Chat = {
      id: uid(),
      title: "",
      created: Date.now(),
      corpus: active?.corpus ?? "",
      mode: active?.mode ?? "HYBRID",
      synthesizer:
        active?.synthesizer ?? synths[0]?.id ?? "deterministic-template-v3",
      messages: [],
    };
    setChats((cs) => [c, ...cs]);
    setActiveId(c.id);
    setView("chat");
  }, [active, synths]);

  // ensure one chat exists
  useEffect(() => {
    if (chats.length === 0) newChat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = useCallback(
    (text: string) => {
      if (!active || busy) return;
      const chatId = active.id;
      const userMsg: Message = { id: uid(), role: "user", text };
      const asstMsg: Message = {
        id: uid(),
        role: "assistant",
        text: "",
        phases: [],
        pending: true,
        mode: active.mode,
      };
      patchChat(chatId, (c) => ({
        ...c,
        title: c.title || text.slice(0, 42),
        messages: [...c.messages, userMsg, asstMsg],
      }));
      setBusy(true);

      const patchAsst = (fn: (m: Message) => Message) =>
        patchChat(chatId, (c) => ({
          ...c,
          messages: c.messages.map((m) => (m.id === asstMsg.id ? fn(m) : m)),
        }));

      streamChat(
        {
          message: text,
          corpus_id: active.corpus,
          mode: active.mode,
          synthesizer: active.synthesizer,
        },
        {
          onPhase: (p) =>
            patchAsst((m) => ({ ...m, phases: [...(m.phases ?? []), p] })),
          onAnswer: (a) => patchAsst((m) => ({ ...m, answer: a })),
          onError: (e) => patchAsst((m) => ({ ...m, error: e })),
          onDone: () => {
            patchAsst((m) => ({ ...m, pending: false }));
            setBusy(false);
          },
        },
      ).catch((e) => {
        patchAsst((m) => ({
          ...m,
          pending: false,
          error: { message: String(e) },
        }));
        setBusy(false);
      });
    },
    [active, busy, patchChat],
  );

  return (
    <div className="app">
      <Sidebar
        chats={chats}
        activeId={activeId}
        view={view}
        onSelect={(id) => {
          setActiveId(id);
          setView("chat");
        }}
        onNew={newChat}
        onDelete={(id) =>
          setChats((cs) => {
            const next = cs.filter((c) => c.id !== id);
            if (activeId === id) setActiveId(next[0]?.id ?? null);
            return next;
          })
        }
        onView={setView}
      />
      <div className="main">
        <TopBar
          corpora={corpora}
          corpus={active?.corpus ?? ""}
          mode={active?.mode ?? "HYBRID"}
          synthesizers={synths}
          synthesizer={active?.synthesizer ?? synths[0]?.id ?? ""}
          theme={theme}
          onCorpus={(v) =>
            active && patchChat(active.id, (c) => ({ ...c, corpus: v }))
          }
          onMode={(m: Mode) =>
            active && patchChat(active.id, (c) => ({ ...c, mode: m }))
          }
          onSynthesizer={(s) =>
            active && patchChat(active.id, (c) => ({ ...c, synthesizer: s }))
          }
          onTheme={setTheme}
        />
        {view === "chat" ? (
          <ChatView chat={active} busy={busy} onSend={send} />
        ) : (
          <FilesView corpus={active?.corpus ?? ""} />
        )}
      </div>
    </div>
  );
}
