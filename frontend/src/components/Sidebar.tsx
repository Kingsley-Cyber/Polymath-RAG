import type { Chat } from "../types";

type View = "chat" | "files" | "corpora" | "models" | "control";

/** SIDEBAR-COLLAPSE-V1 (owner request 2026-09-06): the side panel collapses to a
 * narrow rail — brand dot, new chat, the five views as icons, and the toggle —
 * so the reading column gets the width. State lives in App (persisted); ⌘/Ctrl+B
 * toggles it. Icons are inline strokes on currentColor, no icon font. */

const ICONS: Record<View | "new" | "collapse" | "expand", string> = {
  chat: "M4 5h16v10H9l-5 4z",
  files: "M6 3h8l4 4v14H6z M14 3v4h4",
  corpora: "M4 5h16v4H4z M4 10h16v4H4z M4 15h16v4H4z",
  models: "M8 8h8v8H8z M4 10h4 M4 14h4 M16 10h4 M16 14h4 M10 4v4 M14 4v4 M10 16v4 M14 16v4",
  control: "M12 4v5 M5 20v-5h14v5 M4 9h16 M8 15v-6 M16 15v-6",
  new: "M12 5v14 M5 12h14",
  collapse: "M15 6l-6 6 6 6 M4 4v16",
  expand: "M9 6l6 6-6 6 M20 4v16",
};

function Icon({ name }: { name: keyof typeof ICONS }) {
  return (
    <svg className="sb-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"
         fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d={ICONS[name]} />
    </svg>
  );
}

const TABS: { id: View; label: string }[] = [
  { id: "chat", label: "Chats" },
  { id: "files", label: "Files" },
  { id: "corpora", label: "Corpora" },
  { id: "models", label: "Models" },
  { id: "control", label: "Control Plane" },
];

export default function Sidebar({
  chats,
  activeId,
  view,
  collapsed,
  onToggle,
  onSelect,
  onNew,
  onDelete,
  onView,
}: {
  chats: Chat[];
  activeId: string | null;
  view: View;
  collapsed: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onView: (v: View) => void;
}) {
  const toggle = (
    <button
      type="button"
      className="sb-toggle"
      onClick={onToggle}
      aria-expanded={!collapsed}
      aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      title={`${collapsed ? "Expand" : "Collapse"} sidebar (⌘B / Ctrl+B)`}
    >
      <Icon name={collapsed ? "expand" : "collapse"} />
    </button>
  );

  if (collapsed) {
    return (
      <div className="sidebar collapsed" aria-label="Sidebar (collapsed)">
        <button type="button" className="brand brand-btn" onClick={onToggle} title="Expand sidebar">
          <span className="brand-dot" />
        </button>
        <button type="button" className="rail-btn new" onClick={onNew} title="New chat" aria-label="New chat">
          <Icon name="new" />
        </button>
        <div className="rail-tabs" role="tablist" aria-label="Views">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={view === t.id}
              className={`rail-btn${view === t.id ? " active" : ""}`}
              onClick={() => onView(t.id)}
              title={t.label}
              aria-label={t.label}
            >
              <Icon name={t.id} />
            </button>
          ))}
        </div>
        <div className="rail-spacer" />
        {toggle}
      </div>
    );
  }

  return (
    <div className="sidebar">
      <div className="brand">
        <span className="brand-dot" />
        <b>POLYMATH</b>
        <span className="brand-spacer" />
        {toggle}
      </div>
      <button className="new-chat" onClick={onNew}>
        ＋ New chat
      </button>
      <div className="nav-tabs" role="tablist" aria-label="Views">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={view === t.id}
            className={`nav-tab${view === t.id ? " active" : ""}`}
            onClick={() => onView(t.id)}
          >
            {t.label}
          </button>
        ))}
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
