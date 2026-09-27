// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, onTestFinished, vi } from "vitest";
import { App } from "../App";
import { newTurn, type Turn } from "../lib/chat";
import { saveSessions, type ChatSession } from "../lib/chatStore";
import { SKIP_PLAN_KEY } from "../lib/deep";

/** DEEP-RESEARCH-MODE-V1 §11 (DR7c–e) through the real app: the plan card (edits, Start, the 10 s countdown, Cancel, the
 *  "without the plan" setting, an older backend's 404), the live research view (coverage frames, the activity feed, Finish
 *  now, Stop), "Research this next", an old saved deep turn, and the Reports list. The backend is faked at fetch. */

let host: HTMLDivElement;
let root: Root;
let posts: { path: string; body: Record<string, unknown> }[];
let planReply: () => Response;
let finishReply: () => Response;
let streams: { body: Record<string, unknown>; ctl: ReadableStreamDefaultController<Uint8Array>; signal: AbortSignal | null | undefined }[];

const PLAN = {
  intent: "COMPARISON", evaluative: true, preset: "standard",
  goals: [
    { id: "1.1", goal: "What Laban's four effort factors are", query: "laban effort factors weight time space flow", move: "broad" },
    { id: "1.2", goal: "How effort notation is used in dance teaching", query: "effort notation dance teaching", move: "deep" },
    { id: "1.3", goal: "Where effort notation fails or is criticised", query: "limits of laban effort notation", move: "inverse" },
  ],
  estimate: { searches: 9, llm_calls: 14, seconds: 110 },
};

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  posts = [];
  streams = [];
  planReply = () => Response.json(PLAN);
  finishReply = () => Response.json({ status: "finishing" }, { status: 202 });
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") posts.push({ path, body: JSON.parse(String(init.body)) as Record<string, unknown> });
    if (path === "/research/deep/plan") return planReply();
    if (path === "/research/deep/finish") return finishReply();
    if (path === "/research/deep") {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      return new Response(new ReadableStream<Uint8Array>({
        start(c) {
          streams.push({ body, ctl: c, signal: init?.signal });
          init?.signal?.addEventListener("abort", () => c.error(new DOMException("aborted", "AbortError")));
        },
      }));
    }
    return Response.json(path === "/auth/me" ? { username: "king", display_name: "King", is_owner: true, must_change_password: false, principal_id: "prn_owner", local: true }
      : path === "/corpora" ? { corpora: [{ corpus_id: "cinema", documents: 1, query_ready: true }] }
      : path === "/synthesizers" ? { synthesizers: [] } : path === "/reasoning_modes" ? { modes: [], default: "none" }
      : path.startsWith("/adapter/runs") ? { runs: [] }
      : path === "/admin/friends" ? { friends: [], libraries: ["cinema"], adapters: [], max_active_keys: 3 }
      : path === "/keys" ? { is_owner: true, keys: [], max_active: 3, mcp_url: "" } : path === "/keys/prompt" ? { prompt: "" } : {});
  }));
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function settle() { await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); }

function button(label: string): HTMLButtonElement {
  const b = [...host.querySelectorAll("button")].find((x) => x.textContent?.trim() === label || x.getAttribute("aria-label") === label);
  expect(b, label).toBeDefined();
  return b as HTMLButtonElement;
}

function buttonStarting(text: string): HTMLButtonElement {
  const b = [...host.querySelectorAll("button")].find((x) => x.textContent?.trim().startsWith(text));
  expect(b, text).toBeDefined();
  return b as HTMLButtonElement;
}

async function type(el: HTMLTextAreaElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function choose(el: HTMLSelectElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

async function openApp(screen = "Chat") {
  await act(async () => root.render(<App />));
  await settle();
  const nav = [...host.querySelectorAll(".nav__item")].find((b) => b.textContent?.trim() === screen) as HTMLButtonElement;
  await act(async () => nav.click());
  await settle();
}

function deepToggle(): HTMLInputElement {
  return [...host.querySelectorAll("label")].find((l) => l.textContent?.includes("Deep research"))!.querySelector("input")!;
}

function depthSelect(): HTMLSelectElement | undefined {
  return [...host.querySelectorAll("select")].find((s) => [...s.options].some((o) => o.value === "thorough"));
}

/** Chat → Deep research on → the depth → the question → Send. */
async function askDeep(question: string, depth = "standard") {
  await openApp();
  await act(async () => deepToggle().click());
  await choose(depthSelect()!, depth);
  await type(host.querySelector("textarea.composer__input") as HTMLTextAreaElement, question);
  await act(async () => button("Send").click());
  await settle();
  await settle();
}

function push(i: number, frames: string[]) {
  streams[i]!.ctl.enqueue(new TextEncoder().encode(frames.join("")));
}
const phase = (d: Record<string, unknown>) => `event: phase\ndata: ${JSON.stringify(d)}\n\n`;
const coverage = (goals: Record<string, unknown>[]) => `event: coverage\ndata: ${JSON.stringify({ goals })}\n\n`;

async function frames(i: number, list: string[]) {
  await act(async () => push(i, list));
  await settle();
}

function goalRows(): string[] {
  return [...host.querySelectorAll(".research-goal")].map((r) => r.textContent ?? "");
}

// ── the plan card (DR7a) ─────────────────────────────────────────────────────────────────────────────────────────────

it("plans first, shows the plan card, applies the person's edits and Start sends the confirmed plan", async () => {
  await askDeep("Is Laban effort notation worth learning?");
  expect(posts.map((p) => p.path)).toEqual(["/research/deep/plan"]);                  // nothing runs before Start
  expect(posts[0]!.body).toEqual({ question: "Is Laban effort notation worth learning?", corpus_id: "cinema", preset: "standard", mode: "HYBRID" });
  const card = host.querySelector(".plan-card")!;
  expect(card.textContent).toContain("I'll research this in 3 parts");
  expect(card.textContent).toContain("Library: cinema");
  expect(card.textContent).toContain("Depth: Standard");
  expect(card.textContent).toContain("Estimate: 9 searches, about 2 min");
  const moves = () => [...host.querySelectorAll<HTMLSelectElement>(".plan-goal select")].map((s) => s.selectedOptions[0]?.textContent);
  expect(moves()).toEqual(["Main answer", "Deeper", "Counter-evidence"]);             // each move in plain words
  expect(buttonStarting("Start").textContent).toContain("· 10");                       // the countdown, on the button

  const parts = () => [...host.querySelectorAll<HTMLTextAreaElement>(".plan-goal__text")];
  await type(parts()[1]!, "How teachers use effort notation");                          // edit a part
  expect(buttonStarting("Start").textContent).not.toContain("·");                       // an edit stops the countdown
  await act(async () => button("Remove part 3").click());                                // remove one
  await act(async () => button("Add a part").click());                                   // add one
  expect(document.activeElement).toBe(parts()[2]);
  await type(parts()[2]!, "What Laban wrote about flow");
  await choose(host.querySelectorAll<HTMLSelectElement>(".plan-goal select")[2]!, "adjacent");
  expect(moves()).toEqual(["Main answer", "Deeper", "Connections"]);
  expect(host.querySelector(".plan-card__title")!.textContent).toBe("I'll research this in 3 parts");

  await act(async () => buttonStarting("Start").click());
  await settle();
  expect(posts.map((p) => p.path)).toEqual(["/research/deep/plan", "/research/deep"]);
  expect(posts[1]!.body).toEqual({
    question: "Is Laban effort notation worth learning?", corpus_id: "cinema", preset: "standard", mode: "HYBRID",
    plan: [
      { goal: "What Laban's four effort factors are", query: "laban effort factors weight time space flow", move: "broad" },
      { goal: "How teachers use effort notation", query: "How teachers use effort notation", move: "deep" },
      { goal: "What Laban wrote about flow", query: "What Laban wrote about flow", move: "adjacent" },
    ],
  });
  expect(host.querySelector(".plan-card")).toBeNull();                                  // the card gives way to the live view
  expect(goalRows().map((r) => r.split(" · ")[0])).toEqual([
    "What Laban's four effort factors are", "How teachers use effort notation", "What Laban wrote about flow"]);
});

it("starts by itself after the 10 s countdown when nobody touches the card", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  await askDeep("How does Laban write effort?");
  expect(buttonStarting("Start").textContent).toContain("· 10");
  await act(async () => { vi.advanceTimersByTime(9_000); });
  expect(posts.map((p) => p.path)).toEqual(["/research/deep/plan"]);
  expect(buttonStarting("Start").textContent).toContain("· 1");
  await act(async () => { vi.advanceTimersByTime(1_100); });
  await settle();
  expect(posts.map((p) => p.path)).toEqual(["/research/deep/plan", "/research/deep"]);
  expect(posts[1]!.body.plan).toEqual(PLAN.goals.map(({ goal, query, move }) => ({ goal, query, move })));
});

it("does not start by itself once the person focuses the card", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  await askDeep("How does Laban write effort?");
  await act(async () => host.querySelector<HTMLTextAreaElement>(".plan-goal__text")!.focus());
  await act(async () => { vi.advanceTimersByTime(12_000); });
  await settle();
  expect(posts.map((p) => p.path)).toEqual(["/research/deep/plan"]);
  expect(buttonStarting("Start").textContent).not.toContain("·");
  expect(host.textContent).toContain("Starts when you press Start.");
});

it("Cancel drops the plan, sends nothing more and gives the question back to the box", async () => {
  await askDeep("How does Laban write effort?");
  await act(async () => button("Cancel").click());
  await settle();
  expect(posts.map((p) => p.path)).toEqual(["/research/deep/plan"]);
  expect(host.querySelector(".plan-card")).toBeNull();
  expect(host.textContent).toContain("Research stopped.");
  expect((host.querySelector("textarea.composer__input") as HTMLTextAreaElement).value).toBe("How does Laban write effort?");
  expect(host.querySelector('button[aria-label="Send"]')).not.toBeNull();              // the chat is free again
});

it("the setting skips the card: the run starts at once, as before DR7", async () => {
  localStorage.setItem(SKIP_PLAN_KEY, "1");
  await askDeep("How does Laban write effort?", "thorough");
  expect(host.querySelector(".plan-card")).toBeNull();
  expect(posts.map((p) => p.path)).toEqual(["/research/deep"]);
  expect(posts[0]!.body).toEqual({ question: "How does Laban write effort?", corpus_id: "cinema", preset: "thorough", mode: "HYBRID" });
  expect(host.querySelector(".research-live")).not.toBeNull();
});

it("the card's checkbox and Settings set the same browser setting", async () => {
  await askDeep("How does Laban write effort?");
  const onCard = [...host.querySelectorAll<HTMLLabelElement>(".plan-card__skip")][0]!.querySelector("input")!;
  expect(onCard.checked).toBe(false);
  await act(async () => onCard.click());
  expect(localStorage.getItem(SKIP_PLAN_KEY)).toBe("1");
  const settings = [...host.querySelectorAll(".nav__item")].find((b) => b.textContent?.trim() === "Settings") as HTMLButtonElement;
  await act(async () => settings.click());
  await settle();
  const inSettings = [...host.querySelectorAll("label")].find((l) => l.textContent?.includes("without showing the plan"))!.querySelector("input")!;
  expect(inSettings.checked).toBe(true);
  await act(async () => inSettings.click());
  expect(localStorage.getItem(SKIP_PLAN_KEY)).toBeNull();
});

it.each([
  ["404 (no such route)", () => Response.json({ detail: "Not Found" }, { status: 404 })],
  ["405", () => Response.json({ detail: "Method Not Allowed" }, { status: 405 })],
  ["an older web boundary's 403", () => Response.json({ detail: { error_code: "ROUTE_NOT_ALLOWED", message: "this route is not open through the web" } }, { status: 403 })],
])("an older backend (%s) gets today's direct send", async (_what, reply) => {
  planReply = reply;
  await askDeep("How does Laban write effort?");
  expect(posts.map((p) => p.path)).toEqual(["/research/deep/plan", "/research/deep"]);
  expect(posts[1]!.body).toEqual({ question: "How does Laban write effort?", corpus_id: "cinema", preset: "standard", mode: "HYBRID" });
  expect(host.querySelector(".plan-card")).toBeNull();
  expect(host.querySelector(".research-live")).not.toBeNull();
});

it("a plan the backend refuses is reported, and nothing runs", async () => {
  planReply = () => Response.json({ detail: { error_code: "NO_RESEARCH_LANE", message: "no model lane is configured for research" } }, { status: 503 });
  await askDeep("How does Laban write effort?");
  expect(posts.map((p) => p.path)).toEqual(["/research/deep/plan"]);
  expect(host.querySelector(".answer-error")!.textContent).toBe("no model lane is configured for research");
});

// ── the live research view (DR7c) ────────────────────────────────────────────────────────────────────────────────────

async function started(question = "Is Laban effort notation worth learning?") {
  await askDeep(question);
  await act(async () => buttonStarting("Start").click());
  await settle();
  expect(streams).toHaveLength(1);
}

it("coverage frames and each search's goal_id feed the checklist, the counters and the activity feed", async () => {
  await started();
  expect(host.querySelector(".research-live")!.textContent).toContain("Researching");
  expect(goalRows()).toHaveLength(3);
  expect(goalRows()[0]).toContain("not searched yet");
  await frames(0, [
    phase({ stage: "deep_start", label: "Deep research over cinema", t: 0, preset: "standard" }),
    phase({ stage: "deep_retrieve", label: "Searching: laban effort factors weight time space flow", t: 5, move: "broad",
            query: "laban effort factors weight time space flow", goal_id: "1.1" }),
    phase({ stage: "deep_retrieve", label: "Searching: limits of laban effort notation", t: 6, move: "inverse",
            query: "limits of laban effort notation", goal_id: "1.3" }),
    phase({ stage: "deep_extract", label: "Reading what came back: laban effort factors weight time space flow", t: 9, move: "broad",
            query: "laban effort factors weight time space flow", goal_id: "1.1", new_learnings: 2 }),
    coverage([{ id: "1.1", learnings: 2, documents: 2 }, { id: "1.2", learnings: 0, documents: 0 }, { id: "1.3", learnings: 1, documents: 1 }]),
  ]);
  const rows = goalRows();
  expect(rows[0]).toContain("2 findings · 2 books");
  expect(host.querySelectorAll(".research-goal")[0]!.className).toContain("research-goal--covered");   // 2 findings from 2 books
  expect(rows[1]).toContain("0 findings · 0 books");
  expect(rows[2]).toContain("1 finding · 1 book");
  expect(rows[2]).toContain("Counter-evidence");
  expect(host.querySelector(".research-live__counters")!.textContent).toBe("3 findings");
  const feed = [...host.querySelectorAll(".research-feed__item")].map((r) => r.textContent);
  expect(feed).toEqual([
    "✓Main answer · laban effort factors weight time space flow2 findings",
    "Counter-evidence · limits of laban effort notationsearching…",
  ]);
  await frames(0, [coverage([{ id: "1.1", learnings: 3, documents: 2 }, { id: "1.2", learnings: 1, documents: 1 }, { id: "1.3", learnings: 1, documents: 1 }])]);
  expect(goalRows()[0]).toContain("3 findings · 2 books");
  expect(host.querySelector(".research-live__counters")!.textContent).toBe("5 findings");
  await act(async () => button("Hide activity (2 searches)").click());                    // the feed folds
  expect(host.querySelector(".research-feed__list")).toBeNull();
});

it("coverage ids in an unknown scheme map to the confirmed goals by position", async () => {
  await started();
  await frames(0, [coverage([{ id: "a", learnings: 1, documents: 1 }, { id: "b", learnings: 2, documents: 3 }, { id: "c", learnings: 0, documents: 0 }])]);
  expect(goalRows()).toHaveLength(3);
  expect(goalRows()[1]).toContain("2 findings · 3 books");
});

it("Finish now asks the run to stop searching; the report still arrives", async () => {
  await started();
  await frames(0, [phase({ stage: "deep_retrieve", label: "Searching: x", t: 1, move: "broad", query: "laban effort factors", goal_id: "1.1" })]);
  await act(async () => button("Finish now").click());
  await settle();
  expect(posts.map((p) => p.path)).toContain("/research/deep/finish");
  expect(button("Finishing…").disabled).toBe(true);
  expect(streams[0]!.signal?.aborted).toBe(false);                                        // finishing is not stopping
  await frames(0, [phase({ stage: "deep_report", label: "Writing the report", t: 20 })]);
  expect(host.querySelector(".research-live")!.textContent).toContain("Writing the report");
  expect([...host.querySelectorAll("button")].some((b) => b.textContent === "Finish now" || b.textContent === "Finishing…")).toBe(false);
});

it("Finish now with no live run says so", async () => {
  finishReply = () => Response.json({ detail: { error_code: "NO_RUN", message: "no deep research run" } }, { status: 404 });
  await started();
  await act(async () => button("Finish now").click());
  await settle();
  expect(host.textContent).toContain("Nothing to finish: this research has already stopped searching.");
  expect(button("Finish now").disabled).toBe(false);
});

it("Stop cancels the run", async () => {
  await started();
  await act(async () => button("Stop").click());
  await settle();
  expect(streams[0]!.signal?.aborted).toBe(true);
  expect(host.querySelector(".answer-error")!.textContent).toBe("Research stopped.");
  expect(host.querySelector(".research-live")!.textContent).toContain("Research stopped");
});

// ── a finished report in the chat: "Research this next", and turns saved before DR7 ─────────────────────────────────

function reportTurn(question: string, patch: Partial<Turn> = {}): Turn {
  return {
    ...newTurn(question, "DEEP · standard"), done: true, model: "litellm:fake/model", latencyMs: 61000,
    answerText: "## TL;DR\nEffort has four factors [c1].\n\n## Teaching\nTeachers use it [c2].",
    deep: {
      citations: [{ cid: "c1", title: "Laban", source: "Laban · ch. 1", text: "Effort has four factors." },
                  { cid: "c2", title: "Teaching Movement", source: "Teaching Movement · p. 40", text: "Teachers use effort." }],
      unknown: [],
      summary: {
        learnings: 4, retrievals: 9, stop_reason: "coverage_complete",
        report_model: {
          goals: [{ id: "1.1", goal: "The four factors", findings: [{ text: "Effort has four factors", cids: ["c1"], confidence: "strong" }], documents: 2 },
                  { id: "1.2", goal: "Teaching", findings: [{ text: "Teachers use it", cids: ["c2"], confidence: "single_source" },
                                                         { text: "Classes drill it", cids: ["c2"], confidence: "single_source" }], documents: 1 }],
          counter: [], sources: [{ doc_id: "d1", title: "Laban", cids: ["c1"], findings: 1 }],
          open_questions: ["How is effort notated in film acting?", "Which schools dropped effort notation?"],
          method: { preset: "standard" },
        },
        audit: { sentences: 2, cited: 2, uncited: [] },
      },
    },
    deepRun: { status: "running", request: { corpusId: "cinema", preset: "standard", mode: "HYBRID" }, startedAt: Date.UTC(2026, 8, 20, 10, 0) },
    ...patch,
  };
}

function oldDeepTurn(question: string): Turn {
  return {
    ...newTurn(question, "DEEP · thorough"), done: true, model: "litellm:fake/model", latencyMs: 42000,
    phases: [{ stage: "deep_start", label: "Deep research over cinema", at: 0, data: {} },
             { stage: "deep_plan", label: "Planning searches", at: 10, data: {} }],
    answerText: "Effort has four factors [c1].",
    deep: { citations: [{ cid: "c1", id: "chunk_aaa", title: "Laban", source: "Laban · ch. 1", text: "Effort has four factors." }],
            unknown: [], summary: { learnings: 3, retrievals: 9, stop_reason: "no_new_followups" } },
  };
}

function seed(sessions: Partial<ChatSession>[]) {
  saveSessions(sessions.map((s, i) => ({ id: `c_${i}`, title: s.turns?.[0]?.question ?? "chat", corpusId: "cinema",
                                          createdAt: 1_000 + i, updatedAt: 2_000 + i, turns: [], ...s })));
}

async function openSaved(title: string) {
  await openApp();
  const entry = [...host.querySelectorAll<HTMLButtonElement>(".nav__chat-open")].find((b) => b.title === title)!;
  await act(async () => entry.click());
  await settle();
}

it("\"Research this next\" fills the composer, turns Deep research on at the Quick depth, and sends nothing", async () => {
  seed([{ turns: [reportTurn("How is Laban effort taught?")] }]);
  await openSaved("How is Laban effort taught?");
  expect(host.querySelector(".tabs")).not.toBeNull();                                   // the report view
  expect(deepToggle().checked).toBe(false);
  await act(async () => button("How is effort notated in film acting?").click());
  expect((host.querySelector("textarea.composer__input") as HTMLTextAreaElement).value).toBe("How is effort notated in film acting?");
  expect(deepToggle().checked).toBe(true);
  expect(depthSelect()!.value).toBe("quick");
  expect(posts).toEqual([]);
});

it("a deep turn saved before DR7 (no report model, no research state) still renders as it did", async () => {
  seed([{ turns: [oldDeepTurn("How does Laban write effort?")] }]);
  await openSaved("How does Laban write effort?");
  expect(host.querySelector(".phases")).not.toBeNull();                                 // the process rail, not the live view
  expect(host.querySelector(".research-live")).toBeNull();
  expect(host.querySelector(".tabs")).toBeNull();
  expect(host.querySelector(".sources")!.textContent).toContain("Laban");
  expect(host.textContent).toContain("3 findings from 9 searches, stopped: no new followups");
  expect(host.querySelector(".cite__btn")!.getAttribute("aria-label")).toBe("Source c1: Laban");
});

// ── the Reports list (DR7e) ─────────────────────────────────────────────────────────────────────────────────────────

it("the Reports list reads this browser's chat history and opens a report at its turn", async () => {
  const scrolled: Element[] = [];
  const proto = Element.prototype as unknown as { scrollIntoView?: () => void };
  const had = Object.getOwnPropertyDescriptor(proto, "scrollIntoView");
  proto.scrollIntoView = function (this: Element) { scrolled.push(this); };             // jsdom has no layout
  onTestFinished(() => { if (had) Object.defineProperty(proto, "scrollIntoView", had); else delete proto.scrollIntoView; });
  const chatTurn = { ...newTurn("Plain chat question", "HYBRID"), done: true, answerText: "An answer [S1]." };
  seed([
    { turns: [chatTurn, reportTurn("How is Laban effort taught?")], updatedAt: 5_000 },
    { turns: [oldDeepTurn("How does Laban write effort?")], updatedAt: 4_000 },
  ]);
  await openApp("Research");
  await act(async () => [...host.querySelectorAll<HTMLButtonElement>('[role="tab"]')].find((b) => b.textContent === "Reports")!.click());
  expect(host.textContent).toContain("Reports are kept in this browser only, like your chats.");
  const rows = [...host.querySelectorAll(".report-row")];
  expect(rows).toHaveLength(2);                                                          // the chat turn is not a report
  expect(rows[0]!.textContent).toContain("How is Laban effort taught?");                 // newest first
  expect(rows[0]!.textContent).toContain("cinema · Standard · 3 findings");              // findings from the report model
  expect(rows[1]!.textContent).toContain("How does Laban write effort?");
  expect(rows[1]!.textContent).toContain("cinema · Thorough · 3 findings");               // an old turn: the run's count
  await act(async () => (rows[0] as HTMLButtonElement).click());
  await settle();
  expect(host.querySelector('.nav__item[aria-current="page"]')!.textContent).toBe("Chat");
  expect(host.textContent).toContain("Plain chat question");
  expect(scrolled.at(-1)?.textContent).toBe("How is Laban effort taught?");              // that turn, not the chat's first
});

it("the Research tabs follow the arrow keys and keep the keyboard focus across the switch", async () => {
  await openApp("Research");
  const tabs = () => [...host.querySelectorAll<HTMLButtonElement>('[role="tab"]')];
  const runs = tabs().find((b) => b.textContent === "Runs")!;
  expect(runs.getAttribute("aria-selected")).toBe("true");
  runs.focus();
  await act(async () => { runs.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); });
  const reports = tabs().find((b) => b.textContent === "Reports")!;
  expect(reports.getAttribute("aria-selected")).toBe("true");
  expect(document.activeElement).toBe(reports);                                          // a new tab list, focus kept
  expect(host.textContent).toContain("Reports are kept in this browser only");
});

it("an empty history shows how to make a report", async () => {
  await openApp("Research");
  await act(async () => [...host.querySelectorAll<HTMLButtonElement>('[role="tab"]')].find((b) => b.textContent === "Reports")!.click());
  expect(host.textContent).toContain("No deep research reports yet");
});
