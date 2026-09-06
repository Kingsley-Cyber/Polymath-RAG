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
  // FOLLOW-TAIL-V1: auto-scroll only while the reader is near the bottom.
  // Scrolling up during a stream stops the following; scrolling back near
  // the bottom (or sending a message) resumes it. Streaming tokens no
  // longer yank the viewport away from what the reader is looking at.
  const followRef = useRef(true);
  const [following, setFollowing] = useState(true);
  const NEAR_BOTTOM_PX = 80;

  const scrollToBottom = () => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
    if (near !== followRef.current) {
      followRef.current = near;
      setFollowing(near);
    }
  };

  useEffect(() => {
    if (followRef.current) scrollToBottom();
  }, [chat?.messages, busy]);

  // A different chat: start at its tail.
  useEffect(() => {
    followRef.current = true;
    setFollowing(true);
    scrollToBottom();
  }, [chat?.id]);

  const send = () => {
    const text = draft.trim();
    if (!text || busy || !chat) return;
    setDraft("");
    followRef.current = true;
    setFollowing(true);
    onSend(text);
  };

  return (
    <>
      <div className="chat-scroll" ref={scrollRef} onScroll={onScroll}>
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
        {!following && (
          <button
            className="jump-latest"
            onClick={() => {
              followRef.current = true;
              setFollowing(true);
              scrollToBottom();
            }}
          >
            ↓ {busy ? "Follow the answer" : "Jump to latest"}
          </button>
        )}
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
