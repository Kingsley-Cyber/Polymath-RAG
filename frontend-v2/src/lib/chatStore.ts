/** CHAT-HISTORY-V1 (owner request 2026-09-12, "chatgpt style") — named chat
 *  sessions persisted in localStorage, the way the legacy /ui's sidebar list works.
 *
 *  Storage choice: localStorage, deliberately, matching `polymath-v2.theme` and
 *  `polymath-v2.nav-collapsed`. There is no backend contract for chat history —
 *  `query_receipts` is a server-side audit ledger, NOT a per-user thread store
 *  (no user identity, no thread id, and it records `/retrieve` and `/ask` calls
 *  too). Inventing a threads API would be a backend contract this request did not
 *  ask for; localStorage keeps history a client concern and is honest about its
 *  scope: this browser only.
 *
 *  Only the fields needed to REDRAW a thread are persisted. The streaming receipt
 *  is kept (the Query Trace / Evidence panels read it) but nothing derived is
 *  cached, so a schema change in the receipt degrades a stored turn's panels
 *  rather than corrupting the thread.
 */
import type { Turn } from "./chat";

export interface ChatSession {
  id: string;
  title: string;
  corpusId: string;
  createdAt: number;
  updatedAt: number;
  turns: Turn[];
}

const KEY = "polymath-v2.chats";
const MAX_SESSIONS = 50;

export function newSessionId(): string {
  return `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function emptySession(corpusId: string): ChatSession {
  const now = Date.now();
  return { id: newSessionId(), title: "New chat", corpusId, createdAt: now, updatedAt: now, turns: [] };
}

/** First question, trimmed to a sidebar-sized label. */
export function titleFor(s: ChatSession): string {
  const q = s.turns[0]?.question?.trim();
  if (!q) return "New chat";
  return q.length > 42 ? `${q.slice(0, 41)}…` : q;
}

export function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // tolerate rows written by an older/newer shape rather than losing the lot
    return parsed.filter(
      (s): s is ChatSession =>
        !!s && typeof s.id === "string" && Array.isArray(s.turns),
    );
  } catch {
    return [];
  }
}

export function saveSessions(sessions: ChatSession[]): void {
  try {
    const trimmed = [...sessions]
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, MAX_SESSIONS);
    localStorage.setItem(KEY, JSON.stringify(trimmed));
  } catch {
    /* private mode, or the 5MB quota — history is a convenience, never load-bearing */
  }
}
