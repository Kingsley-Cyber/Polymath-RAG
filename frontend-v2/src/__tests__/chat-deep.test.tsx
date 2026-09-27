// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../App";

/** DEEP-RESEARCH-MODE-V1 DR3 — the composer's Deep research switch: the turn goes to /research/deep (never /chat/stream)
 *  with the chosen depth, the progress shows as the process rail, and the report lists the sources its ids resolve to. */

let host: HTMLDivElement;
let root: Root;
let posts: { path: string; body: Record<string, unknown> }[];
let deepStatus = 200;

const FRAMES = [
  'event: phase\ndata: {"stage":"deep_start","label":"Deep research over cinema","t":0}\n\n',
  'event: phase\ndata: {"stage":"deep_plan","label":"Planning searches","t":10}\n\n',
  ": keep-alive\n\n",
  'event: token\ndata: {"token":"Effort has four factors [c1]. "}\n\n',
  'event: answer\ndata: ' + JSON.stringify({
    kind: "deep", latency_ms: 42000,
    result: { text: "Effort has four factors [c1].", model: "litellm:fake/model", unknown_citations: ["c9"],
              citations: [{ cid: "c1", id: "chunk_aaa", title: "Laban", source: "Laban · ch. 1", text: "Effort has four factors." }],
              meta: { verdict: "supported", deep_research: { learnings: 3, retrievals: 9, stop_reason: "no_new_followups" } } },
    retrieval: null }) + "\n\n",
  "event: done\ndata: {}\n\n",
].join("");

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  posts = [];
  deepStatus = 200;
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") posts.push({ path, body: JSON.parse(String(init.body)) as Record<string, unknown> });
    if (path === "/research/deep") {
      if (deepStatus !== 200) return Response.json({ detail: { error_code: "DEEP_RESEARCH_BUSY", message: "one deep research run at a time" } }, { status: deepStatus });
      return new Response(new ReadableStream<Uint8Array>({ start(c) { c.enqueue(new TextEncoder().encode(FRAMES)); c.close(); } }));
    }
    return Response.json(path === "/auth/me" ? { username: "king", display_name: "King", is_owner: true, must_change_password: false, principal_id: "prn_owner", local: true }
      : path === "/corpora" ? { corpora: [{ corpus_id: "cinema", documents: 1, query_ready: true }] }
      : path === "/synthesizers" ? { synthesizers: [] } : path === "/reasoning_modes" ? { modes: [], default: "none" } : {});
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

async function settle() { await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); }

async function askDeep(question: string, depth = "thorough") {
  await act(async () => root.render(<App />));
  await settle();
  const chat = [...host.querySelectorAll(".nav__item")].find((b) => b.textContent?.trim() === "Chat") as HTMLButtonElement;
  await act(async () => chat.click());
  await settle();
  const toggle = [...host.querySelectorAll("label")].find((l) => l.textContent?.includes("Deep research"))!.querySelector("input")!;
  await act(async () => toggle.click());
  const depthSelect = [...host.querySelectorAll("select")].find((s) => [...s.options].some((o) => o.value === "thorough")) as HTMLSelectElement;
  await act(async () => { depthSelect.value = depth; depthSelect.dispatchEvent(new Event("change", { bubbles: true })); });
  const box = host.querySelector("textarea.composer__input") as HTMLTextAreaElement;
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
  await act(async () => { setter.call(box, question); box.dispatchEvent(new Event("input", { bubbles: true })); });
  expect(box.placeholder).toContain("in depth");
  await act(async () => (host.querySelector('button[aria-label="Send"]') as HTMLButtonElement).click());
  await settle();
  await settle();
}

it("sends a deep research turn to its own route with the chosen depth", async () => {
  await askDeep("How does Laban write effort?");
  expect(posts.map((p) => p.path)).toEqual(["/research/deep"]);                    // never /chat/stream
  expect(posts[0]!.body).toEqual({ question: "How does Laban write effort?", corpus_id: "cinema", preset: "thorough", mode: "HYBRID" });
});

it("shows the progress, the report and the sources its ids resolve to", async () => {
  await askDeep("How does Laban write effort?");
  const text = host.textContent ?? "";
  expect(text).toContain("DEEP · thorough");
  expect(text).toContain("Effort has four factors");
  expect(host.querySelector(".sources")!.textContent).toContain("Laban");
  expect(text).toContain("3 findings from 9 searches, stopped: no new followups");
  expect(text).toContain("Cited but not found in the research: c9");
});

it("a second run at the same time is reported, not swallowed", async () => {
  deepStatus = 409;
  await askDeep("Another question");
  expect(host.textContent).toContain("one deep research run at a time");
});
