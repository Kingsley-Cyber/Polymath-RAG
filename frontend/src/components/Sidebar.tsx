import type { Chat } from "../types";

export default function Sidebar({
  chats,
  activeId,
  view,
  onSelect,
  onNew,
  onDelete,
  onView,
}: {
  chats: Chat[];
  activeId: string | null;
  view: "chat" | "files" | "corpora" | "models";
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onView: (v: "chat" | "files" | "corpora" | "models") => void;
}) {
  return (
    <div className="sidebar">
      <div className="brand">
        <span className="brand-dot" />
        <b>POLYMATH</b>
      </div>
      <button className="new-chat" onClick={onNew}>
        ＋ New chat
      </button>
      <div className="nav-tabs">
        <button
          className={`nav-tab${view === "chat" ? " active" : ""}`}
          onClick={() => onView("chat")}
        >
          Chats
        </button>
        <button
          className={`nav-tab${view === "files" ? " active" : ""}`}
          onClick={() => onView("files")}
        >
          Files
        </button>
        <button
          className={`nav-tab${view === "corpora" ? " active" : ""}`}
          onClick={() => onView("corpora")}
        >
          Corpora
        </button>
        <button
          className={`nav-tab${view === "models" ? " active" : ""}`}
          onClick={() => onView("models")}
        >
          Models
        </button>
      </div>
      <div className="chat-list">
        {chats.map((c) => (
          <button
            key={c.id}
            className={`chat-item${c.id === activeId && view === "chat" ? " active" : ""}`}
            onClick={() => onSelect(c.id)}
          >
            <span>{c.title || "Untitled"}</span>
            <span
              className="del"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(c.id);
              }}
            >
              ✕
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
