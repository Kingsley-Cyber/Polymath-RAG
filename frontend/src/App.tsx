import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCorpora, fetchReasoningModes, fetchSynthesizers, streamChat } from "./api";
import ChatView from "./components/ChatView";
import CorporaView from "./components/CorporaView";
import ModelsView from "./components/ModelsView";
import FilesView from "./components/FilesView";
import FleetView from "./components/FleetView";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import type { Chat, Corpus, Message, Mode, ReasoningModeInfo, Synthesizer } from "./types";

const STORE = "polymath.chats.v1";
const THEME_KEY = "polymath.theme";

const uid = () => Math.random().toString(36).slice(2, 10);

function loadChats(): Chat[] {
  try {
    const chats: Chat[] = JSON.parse(localStorage.getItem(STORE) || "[]");
    // The deterministic stitcher is no longer offered; saved chats
    // pointing at it fall through to the server's default LLM.
    return chats.map((c) =>
      c.synthesizer === "deterministic-template-v3"
        ? { ...c, synthesizer: "" }
        : c,
    );
  } catch {
    return [];
  }
}

export default function App() {
  const [chats, setChats] = useState<Chat[]>(loadChats);
  const [activeId, setActiveId] = useState<string | null>(
    () => loadChats()[0]?.id ?? null,
  );
  const [view, setView] = useState<"chat" | "files" | "corpora" | "models" | "fleet">("chat");
  const [corpora, setCorpora] = useState<Corpus[]>([]);
  const [synths, setSynths] = useState<Synthesizer[]>([]);
  const [reasoningModes, setReasoningModes] = useState<ReasoningModeInfo[]>([]);
  const [busy, setBusy] = useState(false);
  const [theme, setTheme] = useState(
    () => {
      const saved = localStorage.getItem(THEME_KEY) || "obsidian";
      return saved === "forest" ? "obsidian" : saved;
    },
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(STORE, JSON.stringify(chats.slice(0, 60)));
  }, [chats]);

  // Presence pulse: while the tab is open and visible, the autopilot
  // keeps the embedder warm so the first query never pays a sidecar
  // cold start. Ages out server-side when the app closes.
  useEffect(() => {
    const pulse = () => {
      if (document.visibilityState === "visible")
        fetch("/ui_pulse").catch(() => {});
    };
    pulse();
    const t = setInterval(pulse, 60_000);
    document.addEventListener("visibilitychange", pulse);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", pulse);
    };
  }, []);

  useEffect(() => {
    fetchCorpora().then(setCorpora).catch(() => setCorpora([]));
    fetchSynthesizers()
      .then(setSynths)
      .catch(() => setSynths([]));
    fetchReasoningModes()
      .then((d) => setReasoningModes(d.modes))
      .catch(() => setReasoningModes([]));
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
      synthesizer: active?.synthesizer || synths[0]?.id || "",
      reasoning: active?.reasoning ?? "none",
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

      // context for LLM generation: prior turns + evidence carried
      // from earlier answers in THIS chat (so "build me a test from
      // what we studied" can use the whole session's material)
      const history = active.messages.slice(-12).map((m) => ({
        role: m.role,
        content:
          m.role === "user"
            ? m.text
            : (m.answer?.result?.answer ?? m.text ?? "").slice(0, 4000),
      }));
      // CARRY-V2 (CHAT-QUERY-COMPILER-PLAN §3.5, P0.e): carry only the
      // evidence the model actually USED ([S#]-cited) in earlier answers
      // of THIS chat, newest first, cap 8, with its chunk id. The backend
      // re-hydrates, reranks it against the resolved request and drops
      // what falls below the admission floor. The retrieved inventory is
      // never carried (measured 2026-09-05: turn-1 noise became turn-3
      // "evidence" and the prompt grew 32k → 47k chars in three turns).
      const seenLoc = new Set<string>();
      const carry: { locator: string; preview: string; chunk_id?: string }[] = [];
      for (const m of [...active.messages].reverse()) {
        const ret = m.answer?.retrieval;
        if (!ret) continue;
        const used = new Set(ret.used_evidence ?? []);
        const previewByLoc = new Map(
          (ret.chunks ?? []).map((c) => [c.locator, c.preview ?? ""] as const),
        );
        for (const e of ret.legend ?? []) {
          if (
            e.chunk_id &&
            used.has(e.chunk_id) &&
            e.locator &&
            !seenLoc.has(e.locator) &&
            carry.length < 8
          ) {
            seenLoc.add(e.locator);
            carry.push({
              locator: e.locator,
              preview: previewByLoc.get(e.locator) ?? "",
              chunk_id: e.chunk_id,
            });
          }
        }
      }

      streamChat(
        {
          message: text,
          corpus_id: active.corpus,
          mode: active.mode,
          synthesizer: active.synthesizer,
          reasoning:
            active.reasoning && active.reasoning !== "none"
              ? active.reasoning
              : undefined,
          latent: active.latent,
          history,
          carry_context: carry,
        },
        {
          onPhase: (p) =>
            patchAsst((m) => ({ ...m, phases: [...(m.phases ?? []), p] })),
          onToken: (t) => patchAsst((m) => ({ ...m, text: m.text + t })),
          onReasoning: (t) =>
            patchAsst((m) => ({ ...m, reasoning: (m.reasoning ?? "") + t })),
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
          corpora={
            active?.corpus &&
            !corpora.some((c) => c.corpus_id === active.corpus)
              ? [...corpora,
                 { corpus_id: active.corpus, name: active.corpus,
                   documents: 0, query_ready: false } as any]
              : corpora
          }
          corpus={active?.corpus ?? ""}
          mode={active?.mode ?? "HYBRID"}
          synthesizers={synths}
          synthesizer={active?.synthesizer || synths[0]?.id || ""}
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
          reasoningModes={reasoningModes}
          latent={active?.latent ?? false}
          onLatent={(v: boolean) =>
            active && patchChat(active.id, (c) => ({ ...c, latent: v }))
          }
          reasoning={active?.reasoning ?? "none"}
          onReasoning={(r) =>
            active && patchChat(active.id, (c) => ({ ...c, reasoning: r }))
          }
          onTheme={setTheme}
        />
        {view === "chat" ? (
          <ChatView chat={active} busy={busy} onSend={send} />
        ) : view === "models" ? (
          <ModelsView
            onChanged={() => {
              fetchSynthesizers().then(setSynths).catch(() => {});
            }}
          />
        ) : view === "fleet" ? (
          <FleetView />
        ) : view === "corpora" ? (
          <CorporaView
            onChanged={() => {
              fetchCorpora().then(setCorpora).catch(() => {});
            }}
          />
        ) : (
          <FilesView
            corpus={active?.corpus ?? ""}
            onCorpusDeleted={() => {
              fetchCorpora().then(setCorpora).catch(() => {});
              if (active)
                patchChat(active.id, (c) => ({ ...c, corpus: "" }));
            }}
          />
        )}
      </div>
    </div>
  );
}
