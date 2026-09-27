// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Chat } from "../screens/Chat";
import { emptySession } from "../lib/chatStore";
import { setComposerSettings } from "../lib/composerSettings";

/** HEADER-CONTROLS (owner, 2026-09-27): the composer keeps ONLY Deep research (with its depth while on) and Reasoning;
 *  Retrieval, Model and Corpus Explore moved to the top bar (header-controls.test.tsx) and reach this screen through the
 *  per-browser store. The phone "Options" fold of DR7f went with them: two chips fit one row at 375 px, and the row wraps
 *  (app.css `.composer__chips`) rather than scrolling sideways when Depth joins. */

let host: HTMLDivElement;
let root: Root;
let posts: { path: string; body: Record<string, unknown> }[];

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  posts = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") posts.push({ path, body: JSON.parse(String(init.body)) as Record<string, unknown> });
    if (path === "/chat/stream") return new Response(new ReadableStream<Uint8Array>({ start(c) {
      c.enqueue(new TextEncoder().encode('event: answer\ndata: {"result":{"answer":"An answer."},"retrieval":{"mode":"HYBRID"}}\n\nevent: done\ndata: {}\n\n'));
      c.close();
    } }));
    return Response.json(path === "/reasoning_modes" ? { modes: [{ id: "low", label: "Low", description: "a little" }], default: "none" } : {});
  }));
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function showChat(corpusExploreAvailable = false) {
  await act(async () => root.render(
    <Chat corpusId="cinema" session={emptySession("cinema")} onUpdateTurns={() => {}} models={[]} corpusExploreAvailable={corpusExploreAvailable} />));
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

const chipLabels = () => [...host.querySelectorAll(".composer .chip-field .label")].map((l) => l.textContent);

async function send(q: string) {
  const box = host.querySelector("textarea.composer__input") as HTMLTextAreaElement;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(box, q);
    box.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => (host.querySelector('button[aria-label="Send"]') as HTMLButtonElement).click());
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

it("the composer's chips are Deep research and Reasoning only, with Depth while deep research is on, and no fold", async () => {
  await showChat(true);                                                     // even with Corpus Explore on offer
  expect(chipLabels()).toEqual(["Deep research", "Reasoning"]);
  expect(host.querySelector(".composer__fold")).toBeNull();                 // the phone "Options" button is gone
  expect(host.querySelector(".composer__chips")).not.toBeNull();            // one wrapping row
  const deep = [...host.querySelectorAll("label")].find((l) => l.textContent?.includes("Deep research"))!.querySelector("input")!;
  await act(async () => deep.click());
  expect(chipLabels()).toEqual(["Deep research", "Depth", "Reasoning"]);
  await act(async () => deep.click());
  expect(chipLabels()).toEqual(["Deep research", "Reasoning"]);
});

it("sends the top bar's stored mode, model and Corpus Explore, the last only when the server offers it", async () => {
  setComposerSettings({ mode: "GRAPH", model: "litellm:openai/glm-5-free", corpusExplore: true });
  await showChat(true);
  await send("How do crews work?");
  expect(posts[0]!.body).toEqual({ message: "How do crews work?", corpus_id: "cinema", mode: "GRAPH", require_retrieval: true,
                                   synthesizer: "litellm:openai/glm-5-free", corpus_explorer: true });
  await act(async () => root.unmount());
  root = createRoot(host);
  await showChat(false);                                                    // the capability is off: the stored switch is ignored
  await send("How do crews work?");
  expect(posts[1]!.body).toEqual({ message: "How do crews work?", corpus_id: "cinema", mode: "GRAPH", require_retrieval: true,
                                   synthesizer: "litellm:openai/glm-5-free" });
});

it("Reasoning stays the composer's own and rides on the same request", async () => {
  await showChat();
  const reasoning = [...host.querySelectorAll("select")].find((s) => [...s.options].some((o) => o.value === "low"))!;
  await act(async () => { reasoning.value = "low"; reasoning.dispatchEvent(new Event("change", { bubbles: true })); });
  await send("Why?");
  expect(posts[0]!.body).toEqual({ message: "Why?", corpus_id: "cinema", mode: "HYBRID", require_retrieval: true, reasoning: "low" });
});
