// @vitest-environment jsdom
/**
 * CHAT-UI-RESTORE (2026-09-22) — pins the chat surface the owner reported broken:
 * answers render as Markdown (no raw asterisks, real tables), the process rail streams
 * steps + live reasoning and collapses when done, the model picker names the backend's
 * real default, the retrieval selector offers the five modes and no dead Intent control,
 * and a blank "New chat" is never persisted as history.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../App";
import { AnswerBody } from "../components/AnswerBody";
import { ModelPicker } from "../components/ModelPicker";
import { ProcessRail } from "../components/ProcessRail";
import { newTurn, runTurn, type Turn } from "../lib/chat";
import { emptySession, loadSessions, saveSessions } from "../lib/chatStore";
import type { Synthesizer } from "../lib/contracts";

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

function turn(patch: Partial<Turn>): Turn {
  return { ...newTurn("q", "HYBRID"), ...patch };
}

it("renders the answer as Markdown: bold, lists and GFM tables — never raw asterisks or pipes", () => {
  const html = renderToStaticMarkup(<AnswerBody models={[]} t={turn({
    done: true,
    answerText: "**Continuity of custody** matters.\n\n- charge batteries\n- test media\n\n| Moment | Risk |\n|---|---|\n| hand-off | lost card |\n",
    receipt: { mode: "HYBRID", engine: "chat-retrieval-v2", evidence_count: 3, chat_plan: { intent: "SYNTHESIS" } },
  })} />);
  expect(html).toContain("<strong>Continuity of custody</strong>");
  expect(html).toContain("<li>charge batteries</li>");
  expect(html).toContain("<table>");
  expect(html).toContain("<td>lost card</td>");
  expect(html).not.toContain("**");
  expect(html).not.toContain("|---|");
  // the meta row: mode, intent as a READ-ONLY badge, evidence chip; the trace stays one collapsed line
  expect(html).toContain("⌖ synthesis");
  expect(html).toContain("⛁ 3 chunks");
  expect(html).toContain("Query trace");
});

it("process rail: live shows the steps and the streaming reasoning; done collapses to 'Worked for …'", () => {
  const phases = [
    { stage: "compile", label: "Query compiled", at: 5, data: { queries: 3 } },
    { stage: "retrieve", label: "GNN retrieval over cinema…", at: 9, data: {} },
  ];
  const live = renderToStaticMarkup(<ProcessRail phases={phases} live reasoning="Weighing the batteries passage" />);
  expect(live).toContain("Working · 2 steps");
  expect(live).toContain("Weighing the batteries passage");
  expect(live).toContain("GNN retrieval over cinema…");
  expect(live).toContain("3 queries");
  const done = renderToStaticMarkup(<ProcessRail phases={phases} live={false} reasoning="x" />);
  expect(done).toContain("Worked for");
  expect(done).toContain("2 steps");
});

it("streams token frames into the answer and reasoning frames into the rail as they arrive", async () => {
  const sse = [
    'event: phase\ndata: {"stage":"retrieve","label":"HYBRID retrieval over cinema…"}\n\n',
    'event: reasoning\ndata: {"text":"The user asks"}\n\n',
    'event: token\ndata: {"token":"Keep spares "}\n\n',
    'event: token\ndata: {"token":"on your body."}\n\n',
  ];
  let ctrl!: ReadableStreamDefaultController<Uint8Array>;
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ReadableStream<Uint8Array>({ start(c) { ctrl = c; } }))));
  const seen: Partial<Turn>[] = [];
  const done = runTurn({ message: "q" }, (p) => seen.push(p));
  await new Promise((r) => setTimeout(r, 0));
  for (const f of sse) ctrl.enqueue(new TextEncoder().encode(f));
  ctrl.enqueue(new TextEncoder().encode(
    'event: answer\ndata: {"result":{"answer":"Keep spares on your body.","model":"anthropic/deepseek-v4-flash-0731","meta":{"verdict":"generated"}},"retrieval":{"mode":"HYBRID"}}\n\nevent: done\ndata: {}\n\n'));
  ctrl.close();
  await done;
  expect(seen.some((p) => p.phases?.[0]?.label === "HYBRID retrieval over cinema…")).toBe(true);
  expect(seen.some((p) => p.reasoningText === "The user asks")).toBe(true);
  expect(seen.some((p) => p.answerText === "Keep spares ")).toBe(true);        // live, before the final frame
  const final = seen.find((p) => p.model);
  expect(final).toMatchObject({ answerText: "Keep spares on your body.", model: "anthropic/deepseek-v4-flash-0731", verdict: "generated" });
  expect(seen.at(-1)).toMatchObject({ done: true });
});

const CATALOG: Synthesizer[] = [
  { id: "litellm:openai/glm-5-free", kind: "litellm", provider: "opencode", provider_label: "OpenCode", model: "glm-5-free" },
  { id: "litellm:anthropic/deepseek-v4-flash-0731", kind: "litellm", provider: "anthropic", provider_label: "Anthropic", model: "deepseek-v4-flash-0731", default: true },
];

it("model picker names the backend's real default instead of 'backend default'", () => {
  const html = renderToStaticMarkup(<ModelPicker synthesizers={CATALOG} value="" onChange={() => {}} />);
  expect(html).toContain("Anthropic");
  expect(html).toContain("deepseek-v4-flash-0731");
  expect(html).toContain("default");
  expect(html).not.toContain("backend default");
  const picked = renderToStaticMarkup(<ModelPicker synthesizers={CATALOG} value="litellm:openai/glm-5-free" onChange={() => {}} />);
  expect(picked).toContain("glm-5-free");
  expect(picked).not.toContain("· default");
});

it("chat controls: five retrieval modes, FAST first, and no dead Intent dropdown", async () => {
  vi.stubGlobal("fetch", vi.fn(async (path: string) => Response.json(
    path === "/corpora" ? { corpora: [{ corpus_id: "cinema", documents: 1, query_ready: true }] }
      : path === "/synthesizers" ? { synthesizers: CATALOG }
      : path === "/reasoning_modes" ? { modes: [], default: "none" }
      : {})));
  await act(async () => root.render(<App />));
  const chat = [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === "Chat")!;
  await act(async () => chat.click());
  const labels = [...host.querySelectorAll(".label")].map((l) => l.textContent);
  expect(labels).toContain("Retrieval");
  expect(labels).not.toContain("Intent");
  const modes = [...host.querySelectorAll("select")].find((s) => [...s.options].some((o) => o.value === "GNN"))!;
  expect([...modes.options].map((o) => o.value)).toEqual(["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"]);
  expect(host.textContent).toContain("deepseek-v4-flash-0731");
});

it("a blank New chat is never persisted as history", () => {
  const blank = emptySession("cinema");
  const real = { ...emptySession("cinema"), turns: [turn({ done: true, answerText: "a" })] };
  saveSessions([blank, real]);
  expect(loadSessions().map((s) => s.id)).toEqual([real.id]);
});
