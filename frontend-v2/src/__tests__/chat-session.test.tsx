// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../App";
import { loadSessions } from "../lib/chatStore";
import { QueryTrace } from "../components/QueryTrace";

let host: HTMLDivElement;
let root: Root;
let stream: ReadableStreamDefaultController<Uint8Array>;
let sent: Record<string, unknown>;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  // Node's optional Web Storage global is not the document's storage in jsdom.
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    if (path === "/chat/stream") {
      sent = JSON.parse(String(init?.body));
      return new Response(new ReadableStream<Uint8Array>({ start(c) { stream = c; } }));
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

it.each(["Chat", "＋ New chat"])("keeps the first streamed answer when entered through %s", async (entry) => {
  await act(async () => root.render(<App />));
  await act(async () => button(entry).click());
  const textarea = host.querySelector("textarea")!;
  expect(textarea).not.toBeNull();
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(textarea, "How do camera crews work?");
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => button("Send").click());
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
