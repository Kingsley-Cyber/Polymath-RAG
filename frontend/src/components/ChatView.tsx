import { useEffect, useRef, useState } from "react";
import type { Chat } from "../types";
import MessageBubble from "./MessageBubble";

export default function ChatView({
  chat,
  busy,
  onSend,
}: {
  chat: Chat | null;
  busy: boolean;
  onSend: (text: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chat?.messages, busy]);

  const send = () => {
    const text = draft.trim();
    if (!text || busy || !chat) return;
    setDraft("");
    onSend(text);
  };

  return (
    <>
      <div className="chat-scroll" ref={scrollRef}>
        <div className="chat-inner">
          {!chat || chat.messages.length === 0 ? (
            <div className="empty">
              <span className="brand-dot" />
              <b>Grounded answers, exact evidence.</b>
              <span>
                Pick a corpus and a retrieval layer, then ask. Unsupported
                questions abstain — by design.
              </span>
            </div>
          ) : (
            chat.messages.map((m) => <MessageBubble key={m.id} msg={m} />)
          )}
        </div>
      </div>
      <div className="composer">
        <div className="composer-inner">
          <textarea
            ref={taRef}
            rows={1}
            placeholder={
              chat?.corpus
                ? `Ask ${chat.corpus} (${chat.mode})…`
                : "Select a corpus first…"
            }
            value={draft}
            disabled={!chat?.corpus}
            onChange={(e) => {
              setDraft(e.target.value);
              const ta = taRef.current;
              if (ta) {
                ta.style.height = "auto";
                ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          <button className="send" disabled={busy || !draft.trim() || !chat?.corpus} onClick={send}>
            {busy ? "…" : "Send"}
          </button>
        </div>
        <div className="hint">
          Enter to send · Shift+Enter for a newline · answers cite exact
          source spans
        </div>
      </div>
    </>
  );
}
