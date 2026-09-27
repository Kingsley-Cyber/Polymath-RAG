import { useEffect, useMemo, useRef, type KeyboardEvent, type ReactNode } from "react";
import { loadSessions, type ChatSession } from "../../lib/chatStore";
import { listReports, plural, presetLabel } from "../../lib/deep";
import { EmptyState } from "../../ui/states";
import "../../styles/deep.css";

/** DEEP-RESEARCH-MODE-V1 §11.2 part 5 (DR7e) — the Reports tab of the Research section: this browser's deep research turns,
 *  read from the chat history (CHAT-HISTORY-V1 keeps it in this browser on purpose, so the reports follow the same rule).
 *  Opening one goes to its chat, at that turn. */

export type ResearchTab = "runs" | "reports";

/** The two views render their own page, so the tab list remounts on a switch: the new one takes the focus back. */
let refocus = false;

export function ResearchTabs({ tab, onTab }: { tab: ResearchTab; onTab: (t: ResearchTab) => void }) {
  const selected = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (refocus) { refocus = false; selected.current?.focus(); }
  }, []);
  const tabs: { id: ResearchTab; label: string }[] = [{ id: "runs", label: "Runs" }, { id: "reports", label: "Reports" }];
  const go = (next: ResearchTab) => { if (next !== tab) { refocus = true; onTab(next); } };
  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    go(tab === "runs" ? "reports" : "runs");
  }
  return (
    <div className="tabs research-tabs" role="tablist" aria-label="Research views" onKeyDown={onKey}>
      {tabs.map((x) => (
        <button key={x.id} type="button" role="tab" className="tab" aria-selected={tab === x.id} tabIndex={tab === x.id ? 0 : -1}
                ref={tab === x.id ? selected : undefined} onClick={() => go(x.id)}>
          {x.label}
        </button>
      ))}
    </div>
  );
}

function when(ms: number): string {
  if (!ms) return "—";
  const d = new Date(ms);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function ReportsList({ sessions, onOpen, tabs }: {
  /** App's live chat history; without it (a test, a standalone render) the saved history is read */
  sessions?: ChatSession[];
  onOpen?: (chatId: string, turnIndex: number) => void;
  tabs: ReactNode;
}) {
  const reports = useMemo(() => listReports(sessions ?? loadSessions()), [sessions]);
  return (
    <div className="screen screen--wide">
      <div className="screen__head">
        <h1 className="screen__title">Research</h1>
        <p className="screen__sub">Your deep research reports, newest first. Open one to read it in its chat.</p>
      </div>
      {tabs}
      <p className="reports-note faint">Reports are kept in this browser only, like your chats.</p>
      {reports.length === 0 ? (
        <div className="card">
          <EmptyState title="No deep research reports yet">
            In Chat, turn on Deep research and ask a question: its report is listed here.
          </EmptyState>
        </div>
      ) : (
        <div className="stack">
          {reports.map((r) => (
            <button key={`${r.chatId}-${r.index}`} type="button" className="card report-row" onClick={() => onOpen?.(r.chatId, r.index)}>
              <span className="report-row__title">{r.question}</span>
              <span className="report-row__meta faint">
                {when(r.at)} · {r.libraries.join(", ") || "—"} · {presetLabel(r.preset) || "—"} · {r.findings === null
                  ? "findings not counted" : plural(r.findings, "finding")}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
