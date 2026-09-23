// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../App";
import { newTurn } from "../lib/chat";
import { emptySession, loadSessions, saveSessions } from "../lib/chatStore";
import { QueryTrace } from "../components/QueryTrace";

let host: HTMLDivElement;
let root: Root;
let stream: ReadableStreamDefaultController<Uint8Array>;
let sent: Record<string, unknown>;
/** Every /chat/stream opened, in order. Several can be live at once (one per chat). */
let streams: { body: Record<string, unknown>; ctl: ReadableStreamDefaultController<Uint8Array>; signal: AbortSignal | null | undefined }[];

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  // Node's optional Web Storage global is not the document's storage in jsdom.
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  streams = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    if (path === "/chat/stream") {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      sent = body;
      return new Response(new ReadableStream<Uint8Array>({
        start(c) {
          stream = c;
          streams.push({ body, ctl: c, signal: init?.signal });
          // a real fetch body errors when its request is aborted
          init?.signal?.addEventListener("abort", () => c.error(new DOMException("aborted", "AbortError")));
        },
      }));
    }
    const data = path === "/corpora"
      ? { corpora: [{ corpus_id: "cinema", documents: 1, query_ready: true }] }
      : path === "/synthesizers" ? { synthesizers: [] }
      : path === "/reasoning_modes" ? { modes: [], default: "none" }
      : {};
    return Response.json(data);
  }));
});

it("explains FAST's backend alias without reporting mode drift", () => {
  const trace = renderToStaticMarkup(<QueryTrace requestedMode="FAST" receipt={{ mode: "VECTOR", engine: "chat-retrieval-v2" }} />);
  expect(trace).toContain("VECTOR (FAST)");
  expect(trace).not.toContain("the backend executed a different mode");
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

function button(label: string): HTMLButtonElement {
  const b = [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === label);
  expect(b, label).toBeDefined();
  return b!;
}

/** The sidebar entry of a chat, by its title (the first question). */
function chatNamed(title: string): HTMLButtonElement {
  const b = [...host.querySelectorAll<HTMLButtonElement>(".nav__chat-open")].find((b) => b.title === title);
  expect(b, title).toBeDefined();
  return b!;
}

/** Type a question into the open chat and send it, optionally in a given retrieval mode. */
async function ask(q: string, mode?: string) {
  if (mode) {
    const select = [...host.querySelectorAll("select")].find((s) => [...s.options].some((o) => o.value === "GNN"))!;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!.call(select, mode);
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }
  const textarea = host.querySelector("textarea")!;
  expect(textarea).not.toBeNull();
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(textarea, q);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => button("Send").click());
}

function frames(i: number, text: string) {
  streams[i]!.ctl.enqueue(new TextEncoder().encode(text));
}

/** Deliver stream i's final answer frame and close it. */
function finish(i: number, answer: string) {
  const frame = { result: { answer }, retrieval: { mode: streams[i]!.body.mode, evidence_count: 1, chunks: [] } };
  frames(i, `event: answer\ndata: ${JSON.stringify(frame)}\n\nevent: done\ndata: {}\n\n`);
  streams[i]!.ctl.close();
}

function savedTurn(question: string) {
  return loadSessions().find((s) => s.turns[0]?.question === question)?.turns[0];
}

it.each(["Chat", "＋ New chat"])("keeps the first streamed answer when entered through %s", async (entry) => {
  await act(async () => root.render(<App />));
  await act(async () => button(entry).click());
  await ask("How do camera crews work?");
  expect(sent).toMatchObject({ corpus_id: "cinema", mode: "HYBRID", require_retrieval: true });
  const sessionId = loadSessions()[0]!.id;
  // Deliver after the pending turn has reached App and localStorage. That render
  // used to replace the scratch component and orphan this stream's callback.
  await act(async () => {
    stream.enqueue(new TextEncoder().encode(
      'event: answer\ndata: {"result":{"answer":"Crews coordinate shots [S1]."},"retrieval":{"mode":"HYBRID","evidence_count":1,"chunks":[]}}\n\nevent: done\ndata: {}\n\n',
    ));
    stream.close();
  });
  expect(host.textContent).toContain("Crews coordinate shots [S1].");
  expect(host.textContent).toContain("Query trace");
  expect(loadSessions()).toHaveLength(1);
  expect(loadSessions()[0]).toMatchObject({ id: sessionId, turns: [{ done: true, answerText: "Crews coordinate shots [S1]." }] });
});

// Owner report 2026-09-22: "created 3/4 new chats, same question, different retrieval modes, only GRAPH
// worked". The backend finished every turn (receipts: ok/generated); the answers of the chats the owner
// had navigated away from landed in a Chat component that was already unmounted.
it("an answer lands in its own chat after you open another chat mid-stream", async () => {
  await act(async () => root.render(<App />));
  await act(async () => button("＋ New chat").click());
  await ask("GNN: hat prompt?", "GNN");
  await act(async () => button("＋ New chat").click());   // the first chat leaves the screen; its stream does not end
  await ask("GRAPH: hat prompt?", "GRAPH");
  expect(streams.map((s) => s.body.mode)).toEqual(["GNN", "GRAPH"]);
  await act(async () => finish(0, "The GNN answer [S1]."));   // lands while the GRAPH chat is on screen
  await act(async () => finish(1, "The GRAPH answer [S1]."));
  expect(host.textContent).toContain("The GRAPH answer [S1].");
  expect(host.textContent).not.toContain("The GNN answer");
  await act(async () => chatNamed("GNN: hat prompt?").click());
  expect(host.textContent).toContain("The GNN answer [S1].");
  expect(savedTurn("GNN: hat prompt?")).toMatchObject({ done: true, mode: "GNN", answerText: "The GNN answer [S1].", error: null });
  expect(savedTurn("GRAPH: hat prompt?")).toMatchObject({ done: true, mode: "GRAPH", answerText: "The GRAPH answer [S1].", error: null });
});

it("a chat reopened mid-stream keeps streaming live, and Stop still cancels it", async () => {
  await act(async () => root.render(<App />));
  await act(async () => button("＋ New chat").click());
  await ask("Still streaming?");
  await act(async () => button("＋ New chat").click());
  await act(async () => chatNamed("Still streaming?").click());
  // busy belongs to the turn, not to the screen that sent it
  expect(button("Streaming…").disabled).toBe(true);
  await act(async () => frames(0, 'event: token\ndata: {"token":"Partial answer"}\n\n'));
  expect(host.textContent).toContain("Partial answer");
  await act(async () => button("Stop").click());
  expect(streams[0]!.signal?.aborted).toBe(true);
  expect(savedTurn("Still streaming?")).toMatchObject({ done: true, error: "cancelled", answerText: "Partial answer" });
  expect(button("Send")).toBeDefined();
});

it("a turn a reload cut off reads as interrupted, and its chat is usable again", async () => {
  saveSessions([{ ...emptySession("cinema"), title: "Cut off?", turns: [{ ...newTurn("Cut off?", "GNN"), answerText: "Half an ans" }] }]);
  expect(loadSessions()[0]!.turns[0]).toMatchObject({ done: true, answerText: "Half an ans" });
  expect(loadSessions()[0]!.turns[0]!.error).toMatch(/interrupted/);
  await act(async () => root.render(<App />));
  await act(async () => chatNamed("Cut off?").click());
  expect(host.textContent).toMatch(/interrupted/);
  expect(host.querySelector("textarea")!.disabled).toBe(false);
});
