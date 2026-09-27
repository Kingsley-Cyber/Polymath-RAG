/**
 * DEEP-RESEARCH-MODE-V1 §11 (DR7c–e) — the research experience's client model, kept apart from the views so it can be tested
 * alone: the moves in plain words, the plan card's draft and the confirmed plan, the live view read from the stream's frames,
 * the sentence split the audit's indices refer to, the Markdown export, the reports list, and the one browser setting
 * ("start deep research without showing the plan"). Nothing here judges the evidence: the backend's evidence model
 * (`report_model`) and audit are drawn as they come; the UI re-reads the prose only to place the audit's marks.
 *
 * Every field read from the backend is optional, so a turn saved before DR7 (or a stream from an older backend) still draws.
 */
import { useSyncExternalStore } from "react";
import { ApiError } from "./api";
import type { DeepCitation, Phase, Turn } from "./chat";
import type { ChatSession } from "./chatStore";
import type { DeepAudit, DeepCoverage, DeepReportModel, DeepResearchPlan } from "./contracts";

/* ── moves and presets ───────────────────────────────────────────────────────────────────────────────────────────────── */

export const MOVES = ["broad", "deep", "adjacent", "inverse"] as const;
export type Move = (typeof MOVES)[number];

/** §11.2: each move in plain words, as the plan card names it (the process rail of older turns says Broad / Deep / …). */
export const MOVE_WORDS: Record<Move, string> = {
  broad: "Main answer", deep: "Deeper", adjacent: "Connections", inverse: "Counter-evidence",
};

export function isMove(m: unknown): m is Move {
  return typeof m === "string" && (MOVES as readonly string[]).includes(m);
}

/** "single_source" → "Single source" (the backend's own words, formatted, never paraphrased). */
export function words(id: string): string {
  const s = id.replace(/[_.]/g, " ").trim().toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function moveWords(move: unknown): string {
  if (typeof move !== "string" || !move) return "";
  return isMove(move) ? MOVE_WORDS[move] : words(move);
}

/** §3: breadth × depth, and the time estimate (the top of each range) for a run sent without a plan. */
const PRESETS: Record<string, { label: string; breadth: number; depth: number; seconds: number }> = {
  quick: { label: "Quick", breadth: 3, depth: 1, seconds: 40 },
  standard: { label: "Standard", breadth: 3, depth: 2, seconds: 120 },
  thorough: { label: "Thorough", breadth: 4, depth: 2, seconds: 150 },
};

export function presetLabel(p: string | null | undefined): string {
  return (p && PRESETS[p]?.label) || (p ? words(p) : "");
}

export function presetSeconds(p: string | null | undefined): number | null {
  return (p && PRESETS[p]?.seconds) || null;
}

/** §11.3: a confirmed plan holds at most 2 × breadth items. */
export function maxPlanItems(p: string | null | undefined): number {
  return 2 * ((p && PRESETS[p]?.breadth) || 3);
}

/* ── the setting: start without showing the plan (this browser) ─────────────────────────────────────────────────────── */

export const SKIP_PLAN_KEY = "polymath.deep-research.skip-plan";
const skipListeners = new Set<() => void>();

function storage(): Storage | null {
  try { return typeof localStorage === "undefined" ? null : localStorage; } catch { return null; }
}

/** Never throws (private mode, a blocked store): the card then keeps showing. */
export function loadSkipPlan(): boolean {
  try { return storage()?.getItem(SKIP_PLAN_KEY) === "1"; } catch { return false; }
}

export function setSkipPlan(on: boolean): void {
  try {
    const s = storage();
    if (on) s?.setItem(SKIP_PLAN_KEY, "1"); else s?.removeItem(SKIP_PLAN_KEY);
  } catch { /* private mode: the setting does not stick */ }
  skipListeners.forEach((l) => l());
}

function subscribeSkip(l: () => void): () => void {
  skipListeners.add(l);
  const onStorage = (e: StorageEvent) => { if (e.key === SKIP_PLAN_KEY) l(); };
  if (typeof window !== "undefined") window.addEventListener("storage", onStorage);
  return () => {
    skipListeners.delete(l);
    if (typeof window !== "undefined") window.removeEventListener("storage", onStorage);
  };
}

/** The plan card and Settings share one value. */
export function useSkipPlan(): [boolean, (on: boolean) => void] {
  return [useSyncExternalStore(subscribeSkip, loadSkipPlan, () => false), setSkipPlan];
}

/* ── a research turn's own state ────────────────────────────────────────────────────────────────────────────────────── */

/** What Send captured, so Start sends the same request whatever the composer shows by then. */
export interface DeepRunRequest { corpusId: string; preset: string; mode: string; synthesizer?: string }
/** One part on the plan card, as the person edits it (`key` is React's, never sent). */
export interface PlanDraftGoal { key: string; goal: string; query: string; move: string }
/** One part of the confirmed plan, in the order sent. `id` is the id the backend gives it (see confirmedIds). */
export interface DeepGoal { id: string; goal: string; query: string; move: string }

export interface DeepRunState {
  /** planning: waiting for /research/deep/plan · ready: the card waits for Start · running: the stream was opened */
  status: "planning" | "ready" | "running" | "cancelled";
  request: DeepRunRequest;
  plan?: DeepResearchPlan | null;
  draft?: PlanDraftGoal[] | null;
  /** the person focused or edited the card: it no longer starts by itself */
  touched?: boolean;
  goals?: DeepGoal[] | null;
  estimateS?: number | null;
  /** Date.now() when the stream was opened (the elapsed clock, the reports list's date) */
  startedAt?: number | null;
  finishing?: boolean;
  note?: string | null;
}

/** A turn the research views draw: one sent since DR7 (it carries `deepRun`), or any whose answer has a report model. A deep
 *  turn saved before DR7 has neither, and keeps the process rail and the sources list. */
export function isResearchTurn(t: Turn): boolean {
  return !!t.deepRun || !!reportModelOf(t);
}

/* ── the plan ───────────────────────────────────────────────────────────────────────────────────────────────────────── */

export function draftFromPlan(plan: DeepResearchPlan | null | undefined): PlanDraftGoal[] {
  return (plan?.goals ?? []).filter((g) => g && typeof g === "object").map((g, i) => {
    const goal = String(g.goal || g.query || "");
    return { key: String(g.id || `p${i + 1}`), goal, query: String(g.query || goal), move: String(g.move || "broad") };
  });
}

/** The ids a confirmed plan's goals get. §11.3 sends the plan WITHOUT ids and the backend numbers the level-1 searches in plan
 *  order, so the UI numbers them the same way, in the plan response's own scheme: "1.1, 1.2, 1.3" stays "1.1, 1.2, …" after
 *  a part is removed or added. A scheme it cannot read falls back to g1, g2, … (coverage frames then map by position). */
export function confirmedIds(plan: DeepResearchPlan | null | undefined, n: number): string[] {
  const ids = (plan?.goals ?? []).map((g) => String(g?.id ?? ""));
  const m = /^(.*?)(\d+)$/.exec(ids[0] ?? "");
  const prefix = m?.[1] ?? "g";
  const first = m ? Number(m[2]) : 1;
  const readable = !!m && ids.every((id, i) => id === `${prefix}${first + i}`);
  return Array.from({ length: n }, (_, i) => (readable ? `${prefix}${first + i}` : `g${i + 1}`));
}

export function confirmPlan(draft: PlanDraftGoal[], plan: DeepResearchPlan | null | undefined): DeepGoal[] {
  const ids = confirmedIds(plan, draft.length);
  return draft.map((d, i) => {
    const goal = d.goal.trim();
    return { id: ids[i] ?? `g${i + 1}`, goal, query: (d.query.trim() || goal).slice(0, 300), move: d.move || "broad" };
  });
}

/** Why Start cannot run yet (§11.3: 1 … 2 × breadth items, each query 3–300 characters), or null. */
export function planProblem(draft: PlanDraftGoal[], max: number): string | null {
  if (!draft.length) return "Add at least one part.";
  if (draft.length > max) return `At most ${max} parts at this depth.`;
  if (draft.some((d) => d.goal.trim().length < 3)) return "Each part needs a few words.";
  return null;
}

/** An older backend has no plan route: FastAPI's own 404 / 405 (no error code), or an older web boundary's 403 for a route
 *  it does not classify. Deep research then sends straight away, as before DR7. */
export function olderPlanBackend(e: unknown): boolean {
  if (!(e instanceof ApiError)) return false;
  if (e.status === 404 || e.status === 405) return e.code == null;
  return e.status === 403 && e.code === "ROUTE_NOT_ALLOWED";
}

/* ── reading an answer ──────────────────────────────────────────────────────────────────────────────────────────────── */

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const str = (v: unknown): string => (typeof v === "string" ? v : "");
const obj = (v: unknown): Record<string, unknown> | null =>
  (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null);
/** `documents` is a count, or the doc ids themselves. */
export const countOf = (v: unknown): number | null => (Array.isArray(v) ? v.length : num(v));

export function reportModelOf(t: Turn): DeepReportModel | null {
  return obj(t.deep?.summary?.report_model) as DeepReportModel | null;
}

export function auditOf(t: Turn): DeepAudit | null {
  return obj(t.deep?.summary?.audit) as DeepAudit | null;
}

/** DR6 §10.5: what the counter-evidence (inverse) searches found — `meta.deep_research.moves.inverse`. */
export function inverseOf(t: Turn): { searched: number; learnings: number } | null {
  const inv = obj(obj(t.deep?.summary?.moves)?.inverse);
  const searched = num(inv?.searched);
  return inv && searched !== null ? { searched, learnings: num(inv.learnings) ?? 0 } : null;
}

export function openQuestionsOf(report: DeepReportModel | null): string[] {
  const out: string[] = [];
  for (const q of report?.open_questions ?? []) {
    const text = typeof q === "string" ? q : str(obj(q)?.question) || str(obj(q)?.text);
    if (text.trim() && !out.includes(text.trim())) out.push(text.trim());
  }
  return out.slice(0, 5);
}

export type Confidence = { key: "strong" | "single" | "contested" | "other"; label: string; why: string };

/** §11.4's badge, from the finding's `confidence` (strong | single_source | contested; any case, `single` accepted). */
export function confidenceOf(v: unknown): Confidence | null {
  if (typeof v !== "string" || !v.trim()) return null;
  const k = v.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (k === "strong") return { key: "strong", label: "Strong", why: "Passages from two or more books support it." };
  if (k === "single_source" || k === "single") return { key: "single", label: "Single source", why: "One book supports it." };
  if (k === "contested") return { key: "contested", label: "Contested", why: "The research also found counter-evidence for this part." };
  return { key: "other", label: words(v), why: "" };
}

/** "cancelled" → "Research stopped."; a JSON error body → its message. */
export function errorWords(error: string): string {
  if (error === "cancelled") return "Research stopped.";
  const m = /"message"\s*:\s*"((?:[^"\\]|\\.)*)"/.exec(error);
  if (!m) return error;
  try { return JSON.parse(`"${m[1]}"`) as string; } catch { return m[1] ?? error; }
}

/** 1 finding · 2 findings · 2 searches. */
export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : /(s|x|z|ch|sh)$/.test(word) ? "es" : "s"}`;
}

/** 92 → "1:32". */
export function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** 40 → "40 s", 120 → "2 min", 150 → "2.5 min". */
export function roughly(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  const m = Math.round((seconds / 60) * 2) / 2;
  return `${m} min`;
}

/* ── the live view, read from the stream's frames ──────────────────────────────────────────────────────────────────── */

export interface LiveGoal {
  id: string; text: string; move: string;
  learnings: number | null; documents: number | null; searches: number; active: boolean;
}
export interface LiveSearch {
  kind: "search"; key: string; query: string; move: string; goalId: string;
  rows: number | null; findings: number | null; status: "searching" | "read" | "empty" | "failed";
}
export interface LiveNote { kind: "note"; key: string; text: string }
export interface LiveState {
  goals: LiveGoal[]; feed: (LiveSearch | LiveNote)[]; searches: number;
  findings: number | null; passages: number | null; books: number | null;
  /** the step now, in words · whether the report is being written */
  step: string; writing: boolean;
}

/** A search's query: the frame's own field (DR6), else the label's text after "Searching: ". */
function queryOf(p: Phase): string {
  const q = str(p.data?.query);
  if (q) return q;
  const i = p.label.indexOf(": ");
  return i >= 0 ? p.label.slice(i + 2) : "";
}

/** The latest coverage: an `event: coverage` frame (kept on the turn), else a phase frame that carries `goals`. */
export function coverageOf(t: Turn): DeepCoverage | null {
  if (t.deepCoverage && Array.isArray(t.deepCoverage.goals)) return t.deepCoverage;
  for (let i = t.phases.length - 1; i >= 0; i--) {
    const d = t.phases[i]?.data ?? {};
    if (Array.isArray(d.goals)) return d as unknown as DeepCoverage;
  }
  return null;
}

export function stepWords(p: Phase | undefined): string {
  if (!p) return "";
  const move = moveWords(p.data?.move);
  return move && p.stage === "deep_retrieve" ? `${move} · ${queryOf(p)}` : p.label;
}

export function liveState(t: Turn): LiveState {
  const live = !t.done;
  const planned = t.deepRun?.goals?.length ? t.deepRun.goals : null;
  const goals: LiveGoal[] = (planned ?? []).map((g) => ({
    id: g.id, text: g.goal, move: g.move, learnings: null, documents: null, searches: 0, active: false }));
  const byId = new Map(goals.map((g) => [g.id, g]));
  const alias = new Map<string, LiveGoal>();                // a frame's goal id → the checklist row it names
  const cov = coverageOf(t);

  // coverage names the goals in plan order: an id the confirmed plan does not know maps by its position
  const covGoals = (cov?.goals ?? []).filter((g) => g && typeof g === "object");
  const anyKnown = covGoals.some((g) => byId.has(String(g.id)));
  covGoals.forEach((g, i) => {
    const id = String(g.id ?? "");
    let row = byId.get(id) ?? (planned && !anyKnown ? goals[i] : undefined);
    if (!row && !planned) {
      row = { id, text: "", move: "", learnings: null, documents: null, searches: 0, active: false };
      goals.push(row);
      byId.set(id, row);
    }
    if (!row) return;
    alias.set(id, row);
    row.learnings = num(g.learnings);
    row.documents = countOf(g.documents);
  });
  const goalOf = (id: string): LiveGoal | undefined => {
    if (!id) return undefined;
    let row = alias.get(id) ?? byId.get(id);
    if (!row && !planned) {                                  // a run without a confirmed plan: goals come from the frames
      row = { id, text: "", move: "", learnings: null, documents: null, searches: 0, active: false };
      goals.push(row);
      byId.set(id, row);
    }
    return row;
  };

  const feed: (LiveSearch | LiveNote)[] = [];
  const searches = new Map<string, LiveSearch>();
  let levelFindings: number | null = null;
  let active: LiveGoal | undefined;
  for (const p of t.phases) {
    const stage = p.stage.replace(/^deep_/, "");
    const d = p.data ?? {};
    const gid = str(d.goal_id);
    if (stage === "retrieve" || stage === "extract") {
      const query = queryOf(p);
      const key = query || `${stage}-${p.at}-${feed.length}`;
      let s = searches.get(key);
      if (!s) {
        s = { kind: "search", key, query, move: str(d.move), goalId: gid, rows: null, findings: null, status: "searching" };
        searches.set(key, s);
        feed.push(s);
      }
      s.move ||= str(d.move);
      s.goalId ||= gid;
      const rows = num(d.rows);
      if (rows !== null) s.rows = rows;
      const status = str(d.status);
      if (stage === "retrieve") {
        if (status === "empty" || rows === 0) s.status = "empty";
        else if (status === "error") s.status = "failed";
      } else {
        s.status = status === "error" ? "failed" : "read";
        const found = num(d.new_learnings) ?? num(d.learnings);
        if (found !== null) s.findings = found;
      }
      const g = goalOf(s.goalId);
      if (g) {
        if (!g.text && s.query) g.text = s.query;           // an unplanned goal is named by its first search
        g.move ||= s.move;
        active = g;
      }
    } else if (stage === "gate") {
      feed.push({ kind: "note", key: `gate-${p.at}-${feed.length}`, text: p.label });
    } else if (stage === "level_done") {
      const n = num(d.new_learnings);
      if (n !== null) levelFindings = (levelFindings ?? 0) + n;
    } else if (stage === "plan" && gid) {
      active = goalOf(gid) ?? active;
    }
  }
  for (const s of searches.values()) {
    const g = goalOf(s.goalId);
    if (g) g.searches += 1;
  }
  const last = t.phases[t.phases.length - 1];
  const writing = last?.stage === "deep_report";
  if (live && active && !writing) active.active = true;
  goals.forEach((g, i) => { if (!g.text) g.text = `Part ${i + 1}`; });

  // the counters: coverage when the backend sends it, else what the frames say; the answer's own counts once it is in
  const list = [...searches.values()];
  const perGoal = covGoals.map((g) => num(g.learnings));
  let findings: number | null = perGoal.length && perGoal.every((n) => n !== null)
    ? perGoal.reduce<number>((a, n) => a + (n ?? 0), 0)
    : levelFindings ?? (list.some((s) => s.findings !== null) ? list.reduce((a, s) => a + (s.findings ?? 0), 0) : null);
  let passages: number | null = num(cov?.passages)
    ?? (list.some((s) => s.rows !== null) ? list.reduce((a, s) => a + (s.rows ?? 0), 0) : null);
  let books: number | null = num(cov?.documents);
  if (books === null && covGoals.length && covGoals.every((g) => Array.isArray(g.documents))) {
    books = new Set(covGoals.flatMap((g) => g.documents as string[])).size;
  }
  let count = list.length;
  const summary = t.deep?.summary ?? null;
  if (summary) {
    findings = num(summary.learnings) ?? findings;
    passages = num(summary.seen_rows) ?? passages;
    count = num(summary.retrievals) ?? count;
    const sources = reportModelOf(t)?.sources;
    if (Array.isArray(sources)) books = sources.length;
  }
  return { goals, feed, searches: count, findings, passages, books, step: stepWords(last), writing };
}

/* ── the sentence audit ─────────────────────────────────────────────────────────────────────────────────────────────── */

/** One prose sentence: [start, end) in the report text, and its text. */
export interface Sentence { start: number; end: number; text: string }

const CITATION = /\[([^[\]]+)\](?!\()/g;

/* The audit's sentence split mirrors the backend's `deep_research.evidence.split_sentences` exactly — `audit.uncited` indexes
 * its list. The line rules and the sentence pattern are the backend's own strings; `src/__tests__/deep-sentence-split.test.ts`
 * and `tests/contracts/test_deep_research_sentence_split.py` pin both sides to one fixture. */
const FENCE = /^\s{0,3}(?:```|~~~)/;
const HEADING = /^\s{0,3}#{1,6}(?:\s|$)/;
const RULE = /^\s{0,3}(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,}|(?:=\s*){3,})$/;
const TABLE = /^\s*\|/;
const MARKER = /^\s*(?:>\s?)*\s*(?:(?:[-*+]|\d{1,3}[.)])\s+)?/;
/** One sentence (the backend's SENTENCE_PATTERN, run with the flags "gis"). */
export const SENTENCE_PATTERN = String.raw`\S.*?(?:(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\bcf)(?<!\bdr)(?<!\bmr)(?<!\bmrs)(?<!\bpp)(?<!\bch)(?<!\bvol)(?<!\bfig)(?<!\bapprox)[.!?]+[\"'\u201d\u2019)*_]*(?:\s*\[[^\[\]]*\])*(?=\s|$)|$)`;

/**
 * The audit's sentences, in order (DR7b/d):
 *  1. Lines (a trailing "\r" dropped). Skipped: a line on or inside a ``` / ~~~ fence, a blank line, a heading (`#`), a
 *     horizontal rule, a table row.
 *  2. A kept line loses its leading blockquote marks and one list marker.
 *  3. Its sentences are the matches of SENTENCE_PATTERN, each trimmed; a sentence never spans lines.
 */
export function auditSentences(md: string): Sentence[] {
  const out: Sentence[] = [];
  let fence = false;
  let at = 0;
  for (const raw of md.split("\n")) {
    const base = at;
    at += raw.length + 1;
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (FENCE.test(line)) { fence = !fence; continue; }
    if (fence || !line.trim() || HEADING.test(line) || RULE.test(line) || TABLE.test(line)) continue;
    const lead = MARKER.exec(line)?.[0].length ?? 0;
    for (const m of line.slice(lead).matchAll(new RegExp(SENTENCE_PATTERN, "gis"))) {
      const piece = m[0];
      const text = piece.trim();
      if (!text) continue;
      const start = base + lead + (m.index ?? 0) + (piece.length - piece.trimStart().length);
      out.push({ start, end: start + text.length, text });
    }
  }
  return out;
}

/** Every id a text cites as [c1] or [c1, c2], first appearance first (Markdown links and footnote marks are not citations). */
export function citationIds(text: string): string[] {
  const out: string[] = [];
  for (const m of text.matchAll(CITATION)) {
    const inner = (m[1] ?? "").trim();
    if (inner.startsWith("^")) continue;
    for (const id of inner.replace(/^cids?\s*[:=]\s*/i, "").split(/[,;\s]+/)) if (id && !out.includes(id)) out.push(id);
  }
  return out;
}

export interface AuditView {
  /** none: no audit · marks: the uncited sentences are found in the prose · counts: they could not be matched reliably */
  mode: "none" | "marks" | "counts";
  sentences: number | null; cited: number | null; uncited: number;
  marks: Sentence[]; invalid: string[];
}

/** Place the audit's uncited sentences in the prose — only when the split agrees with the backend's: the same sentence count,
 *  and each flagged sentence really carries no valid citation. Otherwise the view shows the counts alone. */
export function auditView(text: string, audit: DeepAudit | null, valid: ReadonlySet<string>): AuditView {
  const invalid = Array.isArray(audit?.invalid_cids) ? audit.invalid_cids.map(String) : [];
  if (!audit || !Array.isArray(audit.uncited)) {
    return { mode: "none", sentences: null, cited: null, uncited: 0, marks: [], invalid };
  }
  const idx = [...new Set(audit.uncited.filter((n): n is number => Number.isInteger(n)))].sort((a, b) => a - b);
  const total = num(audit.sentences);
  const cited = num(audit.cited) ?? (total !== null ? total - idx.length : null);
  const mine = auditSentences(text);
  const fits = total === mine.length
    && idx.every((i) => i >= 0 && i < mine.length && !citationIds(mine[i]!.text).some((id) => valid.has(id)));
  return { mode: fits ? "marks" : "counts", sentences: total, cited, uncited: idx.length,
           marks: fits ? idx.map((i) => mine[i]!) : [], invalid };
}

/* ── the TL;DR block ────────────────────────────────────────────────────────────────────────────────────────────────── */

export interface ProsePart { text: string; start: number }

const TLDR_HEADING = /^(tl;?\s?dr|summary|in short|short answer|the short answer|the answer|answer|bottom line|key takeaways?)\b/i;

/** The report's TL;DR (§11.2: "an answer-first TL;DR of 2–4 cited sentences"): the section under a TL;DR / Summary heading
 *  that opens the report, else the prose before the first heading. `start` keeps each part's place in the whole prose, so the
 *  audit's marks land in the right sentence. No heading at all: no separate block. */
export function splitTldr(md: string): { tldr: ProsePart | null; rest: ProsePart } {
  const whole = { tldr: null, rest: { text: md, start: 0 } };
  const heads: { start: number; end: number; title: string }[] = [];
  let at = 0;
  let fence = false;
  for (const line of md.split("\n")) {
    const t = line.trim();
    if (/^(```|~~~)/.test(t)) fence = !fence;
    else if (!fence && /^#{1,6}\s/.test(t)) heads.push({ start: at, end: at + line.length + 1, title: t.replace(/^#{1,6}\s+/, "") });
    at += line.length + 1;
  }
  const first = md.search(/\S/);
  const h0 = heads[0];
  if (first < 0 || !h0) return whole;
  if (h0.start <= first && TLDR_HEADING.test(h0.title.replace(/[*_`:]/g, "").trim())) {
    const next = heads[1]?.start ?? md.length;
    const end = Math.min(h0.end, md.length);
    const body = md.slice(end, next);
    return body.trim() ? { tldr: { text: body, start: end }, rest: { text: md.slice(next), start: next } } : whole;
  }
  if (first < h0.start) return { tldr: { text: md.slice(0, h0.start), start: 0 }, rest: { text: md.slice(h0.start), start: h0.start } };
  return whole;
}

/* ── Markdown export ────────────────────────────────────────────────────────────────────────────────────────────────── */

function footnote(c: DeepCitation | undefined): string {
  if (!c) return "cited, but not found in the research";
  const clean = (s: string) => s.replace(/\s+/g, " ").trim();
  const title = clean(c.title || c.id || c.cid);
  const where = clean(c.source ?? "");
  return where && where !== title ? `${title} — ${where}` : title;
}

/** DR7d: the report as a Markdown file — the question as its title, the prose with each [cN] turned into a footnote mark
 *  [^cN] (code left alone), and the footnotes `[^cN]: Title — where` in the order first cited. */
export function reportMarkdown(question: string, text: string, citations: DeepCitation[]): string {
  const known = new Map(citations.map((c) => [c.cid, c]));
  const order: string[] = [];
  let fence = false;
  const body = text.split("\n").map((line) => {
    if (/^\s*(```|~~~)/.test(line)) { fence = !fence; return line; }
    if (fence) return line;
    return line.split("`").map((seg, i) => (i % 2 ? seg : seg.replace(CITATION, (whole: string, inner: string) => {
      const ids = inner.trim().split(/[,;\s]+/).filter(Boolean);
      if (!ids.length || !ids.every((id) => /^c\d{1,4}$/.test(id))) return whole;
      ids.forEach((id) => { if (!order.includes(id)) order.push(id); });
      return ids.map((id) => `[^${id}]`).join("");
    }))).join("`");
  }).join("\n").trim();
  const notes = order.map((id) => `[^${id}]: ${footnote(known.get(id))}`);
  return [`# ${question.replace(/\s+/g, " ").trim()}`, "", body, ...(notes.length ? ["", ...notes] : []), ""].join("\n");
}

export function reportFileName(question: string): string {
  const slug = question.toLowerCase().normalize("NFKD").replace(/[^\p{L}\p{N}]+/gu, "-").replace(/^-+|-+$/g, "")
    .slice(0, 60).replace(/-+$/, "");
  return `deep-research${slug ? `-${slug}` : ""}.md`;
}

/* ── the Method tab, in plain words ─────────────────────────────────────────────────────────────────────────────────── */

const STOP_WORDS: Record<string, string> = {
  frontier_empty: "there were no more leads to follow",
  no_new_followups: "a round raised no new questions",
  budget: "the search budget was spent",
  deadline: "the time limit was reached",
  cancelled: "it was stopped",
  coverage_complete: "every part had at least 2 findings from 2 books",
  finished_early: "you pressed Finish now",
};

/** Searches per move, from `moves.levels[].searched` (DR6) or a flat `{broad: n, …}`. */
function searchesByMove(v: unknown): string {
  const o = obj(v);
  if (!o) return "";
  const per: Record<string, number> = {};
  const add = (d: unknown) => {
    for (const [k, n] of Object.entries(obj(d) ?? {})) if (typeof n === "number") per[k] = (per[k] ?? 0) + n;
  };
  if (Array.isArray(o.levels)) o.levels.forEach((l) => add(obj(l)?.searched));
  else add(o);
  return MOVES.filter((m) => per[m]).map((m) => `${MOVE_WORDS[m]} ${per[m]}`).join(" · ");
}

export function presetOf(t: Turn): string {
  return t.deepRun?.request?.preset || /^DEEP\s*·\s*(\S+)/.exec(t.mode)?.[1] || "";
}

/** The Method tab: `report_model.method` first, then the run's counts (`meta.deep_research`) and DR6's `moves` block. */
export function methodLines(t: Turn): string[] {
  const s = (t.deep?.summary ?? {}) as Record<string, unknown>;
  const m = (reportModelOf(t)?.method ?? {}) as Record<string, unknown>;
  const moves = obj(s.moves);
  const out: string[] = [];
  const preset = str(m.preset) || presetOf(t);
  const shape = PRESETS[preset];
  if (preset) {
    out.push(`Depth: ${presetLabel(preset)}${shape ? `, up to ${shape.breadth} searches wide and ${plural(shape.depth, "round")} deep` : ""}.`);
  }
  const intent = str(m.intent) || str(moves?.intent);
  const evaluative = (m.evaluative ?? moves?.evaluative) === true;
  if (intent) {
    out.push(`Question type: ${words(intent).toLowerCase()}${evaluative
      ? "; it asks for a judgement, so the research also looked for counter-evidence" : ""}.`);
  }
  const searches = num(m.searches) ?? num(s.retrievals);
  const mix = searchesByMove(m.moves ?? moves);
  if (searches !== null || mix) out.push(`Searches: ${searches ?? "—"}${mix ? ` (${mix})` : ""}.`);
  const learnings = num(m.learnings) ?? num(s.learnings);
  const seen = num(s.seen_rows);
  const cited = num(s.cited_rows);
  if (learnings !== null) {
    out.push(`Findings: ${learnings}${seen !== null ? `, from ${plural(seen, "passage")} read` : ""}${
      cited !== null ? `; the findings rest on ${plural(cited, "passage")}` : ""}.`);
  }
  const gate = obj(m.gate) ?? obj(moves?.gate);
  const scored = num(gate?.scored);
  if (gate && scored !== null) {
    const dropped = num(gate.dropped) ?? 0;
    const kept = num(gate.user_kept) ?? 0;
    const open = num(gate.failed_open) ?? 0;
    out.push(`Relevance check: ${plural(scored, "planned search")} scored against your question, ${dropped
      ? `${dropped} dropped as off the question` : "none dropped"}${kept ? `; ${kept} of your own parts kept even so` : ""}${
      open ? `; ${open} went ahead unchecked when the check failed` : ""}.`);
  }
  const droppedLearnings = num(s.dropped_learnings);
  if (droppedLearnings) {
    out.push(`${plural(droppedLearnings, "finding")} left out because ${droppedLearnings === 1 ? "its citation" : "their citations"} did not match the passages read.`);
  }
  const stop = str(m.stop_reason) || str(s.stop_reason);
  if (stop) out.push(`Stopped because ${STOP_WORDS[stop] ?? words(stop).toLowerCase()}.`);
  const secs = num(m.elapsed_s) ?? (t.latencyMs != null ? t.latencyMs / 1000 : num(s.elapsed_s));
  if (secs !== null) out.push(`Time: ${clock(secs)}.`);
  const model = str(m.model) || t.model || "";
  if (model) out.push(`Report written by ${model.split("/").pop()}.`);
  return out;
}

/* ── the reports list (DR7e): this browser's deep research turns ────────────────────────────────────────────────────── */

export interface ReportEntry {
  chatId: string; index: number; question: string; at: number;
  libraries: string[]; preset: string; findings: number | null;
}

export function findingsOf(t: Turn): number | null {
  const goals = reportModelOf(t)?.goals;
  if (Array.isArray(goals)) return goals.reduce((n, g) => n + (Array.isArray(g?.findings) ? g.findings.length : 0), 0);
  return num(t.deep?.summary?.learnings);
}

/** Every finished deep research report in the chat history, newest first. A turn saved before DR7 has no start time: its
 *  chat's last change stands in for it, and its chat's library for its libraries. */
export function listReports(sessions: ChatSession[]): ReportEntry[] {
  const out: ReportEntry[] = [];
  for (const s of sessions) {
    (s.turns ?? []).forEach((t, index) => {
      if (!t?.deep || !t.done || !t.answerText) return;
      const lib = t.deepRun?.request?.corpusId || s.corpusId;
      out.push({ chatId: s.id, index, question: t.question, at: t.deepRun?.startedAt ?? s.updatedAt ?? s.createdAt ?? 0,
                 libraries: lib ? [lib] : [], preset: presetOf(t), findings: findingsOf(t) });
    });
  }
  return out.sort((a, b) => b.at - a.at);
}
