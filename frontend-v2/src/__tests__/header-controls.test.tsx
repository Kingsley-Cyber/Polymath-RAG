// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../App";
import { COMPOSER_SETTINGS_KEY } from "../lib/composerSettings";
import type { Synthesizer } from "../lib/contracts";

/** HEADER-CONTROLS (owner, 2026-09-27: "in the ui only deep research should be in the chatbox and reasoning; everything
 *  else should be in the header top next to corpus selector"). Retrieval, Model and Corpus Explore live in the top bar
 *  right after the library while the Chat screen is active, are kept per browser under one key, and the composer sends
 *  them as before (the same request fields). Below 1100 px (app.css) the three sit behind one "Chat options" button; jsdom
 *  has no media queries, so this pins the structure and the state: the button, aria-expanded, the open class. */

const CATALOG: Synthesizer[] = [
  { id: "litellm:openai/glm-5-free", kind: "litellm", provider: "opencode", provider_label: "OpenCode", model: "glm-5-free" },
  { id: "litellm:anthropic/deepseek-v4-flash-0731", kind: "litellm", provider: "anthropic", provider_label: "Anthropic",
    model: "deepseek-v4-flash-0731", default: true },
];
const ANSWER = 'event: answer\ndata: {"result":{"answer":"An answer [S1]."},"retrieval":{"mode":"HYBRID","evidence_count":1,"chunks":[]}}\n\nevent: done\ndata: {}\n\n';

let host: HTMLDivElement;
let root: Root;
let posts: { path: string; body: Record<string, unknown> }[];
let capabilities: Record<string, unknown>;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  localStorage.setItem("polymath.deep-research.skip-plan", "1");   // DR7a: a deep turn sends straight away (the plan card has its own tests)
  posts = [];
  capabilities = {};
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") posts.push({ path, body: JSON.parse(String(init.body)) as Record<string, unknown> });
    if (path === "/chat/stream" || path === "/research/deep") {
      return new Response(new ReadableStream<Uint8Array>({ start(c) { c.enqueue(new TextEncoder().encode(ANSWER)); c.close(); } }));
    }
    return Response.json(path === "/auth/me" ? { username: "king", display_name: "King", is_owner: true, must_change_password: false, principal_id: "prn_owner", local: true }
      : path === "/corpora" ? { corpora: [{ corpus_id: "cinema", documents: 1, query_ready: true }] }
      : path === "/synthesizers" ? { synthesizers: CATALOG }
      : path === "/reasoning_modes" ? { modes: [], default: "none" }
      : path === "/capabilities" ? capabilities : {});
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

async function openApp() {
  await act(async () => root.render(<App />));
  await settle();
}

async function go(screen: string) {
  const b = [...host.querySelectorAll(".nav__item")].find((x) => x.textContent?.trim() === screen) as HTMLButtonElement;
  await act(async () => b.click());
  await settle();
}

const topbar = () => host.querySelector(".topbar")!;
const controls = () => topbar().querySelector<HTMLDivElement>(".topbar__controls");
const labelsIn = (el: Element | null) => [...(el?.querySelectorAll(".chip-field .label") ?? [])].map((l) => l.textContent);
const retrieval = () => [...topbar().querySelectorAll("select")].find((s) => [...s.options].some((o) => o.value === "GNN"))!;
const chatOptions = () => topbar().querySelector<HTMLButtonElement>('button[aria-label="Chat options"]')!;

async function choose(select: HTMLSelectElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!.call(select, value);
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

async function pickModel(name: string, group = "OpenCode") {
  await act(async () => topbar().querySelector<HTMLButtonElement>(".mp__button")!.click());
  await act(async () => [...topbar().querySelectorAll<HTMLButtonElement>(".mp__group")].find((b) => b.textContent?.includes(group))!.click());
  await act(async () => [...topbar().querySelectorAll<HTMLButtonElement>(".mp__item")].find((b) => b.textContent === name)!.click());
}

async function ask(q: string) {
  const box = host.querySelector("textarea.composer__input") as HTMLTextAreaElement;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(box, q);
    box.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => (host.querySelector('button[aria-label="Send"]') as HTMLButtonElement).click());
  await settle();
  await settle();
}

it("the top bar's chat controls show on the Chat screen only, right after the library", async () => {
  await openApp();                                                          // the owner starts on Overview
  expect(controls()).toBeNull();
  await go("Chat");
  expect(labelsIn(controls())).toEqual(["Retrieval", "Model"]);            // Corpus Explore: not advertised here
  expect(topbar().querySelector("select")!.closest(".topbar__library")).not.toBeNull();   // the library is still first
  expect(topbar().querySelector(".topbar__library")!.nextElementSibling!.classList.contains("topbar__chat")).toBe(true);
  expect([...retrieval().options].map((o) => o.value)).toEqual(["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"]);
  expect(topbar().textContent).toContain("deepseek-v4-flash-0731");         // the picker names the backend's default
  expect(labelsIn(host.querySelector(".composer"))).toEqual(["Deep research", "Reasoning"]);
  await go("Files");
  expect(controls()).toBeNull();
});

it("Retrieval in the top bar sets the mode of the next chat request, and of a deep research run", async () => {
  await openApp();
  await go("Chat");
  await ask("A first question");
  expect(posts[0]!.body).toMatchObject({ mode: "HYBRID" });
  await choose(retrieval(), "GRAPH");
  await ask("How do crews work?");
  expect(posts[1]).toEqual({ path: "/chat/stream", body: { message: "How do crews work?", corpus_id: "cinema", mode: "GRAPH", require_retrieval: true } });
  const deep = [...host.querySelectorAll(".composer label")].find((l) => l.textContent?.includes("Deep research"))!.querySelector("input")!;
  await act(async () => deep.click());
  await ask("In depth?");
  expect(posts[2]).toEqual({ path: "/research/deep", body: { question: "In depth?", corpus_id: "cinema", preset: "standard", mode: "GRAPH" } });
});

it("the Model picker in the top bar sets the synthesizer of the next request", async () => {
  await openApp();
  await go("Chat");
  await pickModel("glm-5-free");
  await ask("Which model?");
  expect(posts[0]!.body).toMatchObject({ synthesizer: "litellm:openai/glm-5-free" });
  await act(async () => topbar().querySelector<HTMLButtonElement>(".mp__button")!.click());
  await act(async () => [...topbar().querySelectorAll<HTMLButtonElement>(".mp__item")].find((b) => b.textContent?.startsWith("Default"))!.click());
  await ask("And now?");
  expect(posts[1]!.body).not.toHaveProperty("synthesizer");                 // the backend's default: no field
});

it("Corpus Explore shows only when the server advertises it, and sets corpus_explorer on the next request", async () => {
  await openApp();
  await go("Chat");
  expect(labelsIn(controls())).not.toContain("Corpus Explore");
  await act(async () => root.unmount());
  capabilities = { contracts: { "corpus-explorer": { version: 1 } } };
  root = createRoot(host);
  await openApp();
  await go("Chat");
  const toggle = [...controls()!.querySelectorAll("label")].find((l) => l.textContent?.includes("Corpus Explore"))!.querySelector("input")!;
  expect(toggle.checked).toBe(false);
  await act(async () => toggle.click());
  await ask("Explore?");
  expect(posts[0]!.body).toMatchObject({ corpus_explorer: true });
});

it("the choices survive a remount: one key per browser", async () => {
  await openApp();
  await go("Chat");
  await choose(retrieval(), "GNN");
  await pickModel("glm-5-free");
  expect(JSON.parse(localStorage.getItem(COMPOSER_SETTINGS_KEY)!)).toEqual({ mode: "GNN", model: "litellm:openai/glm-5-free", corpusExplore: false });
  await act(async () => root.unmount());
  root = createRoot(host);
  await openApp();
  await go("Chat");
  expect(retrieval().value).toBe("GNN");
  expect(topbar().querySelector(".mp__button")!.textContent).toContain("glm-5-free");
  await ask("Still?");
  expect(posts[0]!.body).toMatchObject({ mode: "GNN", synthesizer: "litellm:openai/glm-5-free" });
});

it("a stored model the catalog no longer offers goes back to the backend's default", async () => {
  localStorage.setItem(COMPOSER_SETTINGS_KEY, JSON.stringify({ mode: "HYBRID", model: "litellm:gone/model", corpusExplore: false }));
  await openApp();
  await go("Chat");
  expect(JSON.parse(localStorage.getItem(COMPOSER_SETTINGS_KEY)!).model).toBe("");
  expect(topbar().querySelector(".mp__button")!.textContent).toContain("deepseek-v4-flash-0731");
  await ask("Which model?");
  expect(posts[0]!.body).not.toHaveProperty("synthesizer");
});

it("the phone button opens the controls in a panel and Escape, a click outside or the button closes it", async () => {
  await openApp();
  await go("Chat");
  const button = chatOptions();
  expect(button.getAttribute("aria-expanded")).toBe("false");
  expect(button.getAttribute("aria-controls")).toBe(controls()!.id);
  expect(controls()!.id).not.toBe("");
  expect(controls()!.classList.contains("topbar__controls--open")).toBe(false);
  await act(async () => button.click());
  expect(button.getAttribute("aria-expanded")).toBe("true");
  expect(controls()!.classList.contains("topbar__controls--open")).toBe(true);
  expect(controls()!.querySelector("select")).not.toBeNull();               // the same controls, not a copy
  await act(async () => { window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })); });
  expect(button.getAttribute("aria-expanded")).toBe("false");
  await act(async () => button.click());
  await act(async () => { host.querySelector("textarea")!.dispatchEvent(new MouseEvent("mousedown", { bubbles: true })); });
  expect(button.getAttribute("aria-expanded")).toBe("false");
  await act(async () => button.click());
  await act(async () => { retrieval().dispatchEvent(new MouseEvent("mousedown", { bubbles: true })); });   // inside: stays open
  expect(button.getAttribute("aria-expanded")).toBe("true");
  await act(async () => button.click());
  expect(button.getAttribute("aria-expanded")).toBe("false");
});
