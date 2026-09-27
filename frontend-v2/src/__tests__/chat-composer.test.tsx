// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Chat } from "../screens/Chat";
import { emptySession } from "../lib/chatStore";
import type { Synthesizer } from "../lib/contracts";

/** Tuning after DR7f (live, 2026-09-27): at 375 px the composer's option chips (Retrieval, Model, Reasoning, Deep research,
 *  Corpus Explore, Depth) took about 40% of the screen height. On a narrow screen (≤ 560 px, a media query in app.css) they
 *  fold behind one "Options" button with a one-line summary; wider screens never show the button. jsdom has no media
 *  queries, so this pins the structure and the state: the button, `aria-expanded`, the open class, the summary. */

const CATALOG: Synthesizer[] = [
  { id: "litellm:openai/glm-5-free", kind: "litellm", provider: "opencode", provider_label: "OpenCode", model: "glm-5-free" },
  { id: "litellm:anthropic/deepseek-v4-flash-0731", kind: "litellm", provider: "anthropic", provider_label: "Anthropic",
    model: "deepseek-v4-flash-0731", default: true },
];

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async (path: string) => Response.json(
    path === "/synthesizers" ? { synthesizers: CATALOG } : path === "/reasoning_modes" ? { modes: [], default: "none" } : {})));
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function showChat() {
  await act(async () => root.render(<Chat corpusId="cinema" session={emptySession("cinema")} onUpdateTurns={() => {}} />));
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

const fold = () => host.querySelector<HTMLButtonElement>("button.composer__fold")!;
const chips = () => host.querySelector<HTMLDivElement>(".composer__chips")!;
const summary = () => fold().querySelector(".composer__fold-summary")!.textContent;

function selectWith(value: string): HTMLSelectElement {
  return [...host.querySelectorAll("select")].find((s) => [...s.options].some((o) => o.value === value))!;
}

async function choose(select: HTMLSelectElement, value: string) {
  await act(async () => { select.value = value; select.dispatchEvent(new Event("change", { bubbles: true })); });
}

async function click(el: HTMLElement) {
  await act(async () => el.click());
}

it("folds the option chips behind one Options button that opens and closes them", async () => {
  await showChat();
  const button = fold();
  expect(button.tagName).toBe("BUTTON");
  expect(button.type).toBe("button");                                      // a real button: focusable, Enter and Space
  expect(button.querySelector(".composer__fold-label")!.textContent).toBe("Options");
  expect(chips().id).not.toBe("");
  expect(button.getAttribute("aria-controls")).toBe(chips().id);
  expect(button.getAttribute("aria-expanded")).toBe("false");
  expect(chips().classList.contains("composer__chips--open")).toBe(false);
  expect(chips().querySelector("select")).not.toBeNull();                  // the chips are all still there, only folded
  await click(button);
  expect(button.getAttribute("aria-expanded")).toBe("true");
  expect(chips().classList.contains("composer__chips--open")).toBe(true);
  expect(document.activeElement).not.toBe(host.querySelector("textarea")); // the tap never lands in the message box
  await click(button);
  expect(button.getAttribute("aria-expanded")).toBe("false");
  expect(chips().classList.contains("composer__chips--open")).toBe(false);
});

it("the folded summary names the mode, a short model name, and the depth while deep research is on", async () => {
  await showChat();
  expect(summary()).toBe("HYBRID · deepseek-v4-flash-0731");               // nothing picked: the backend's default, named
  await choose(selectWith("GNN"), "GRAPH");
  expect(summary()).toBe("GRAPH · deepseek-v4-flash-0731");
  await click(host.querySelector<HTMLButtonElement>(".mp__button")!);
  await click([...host.querySelectorAll<HTMLButtonElement>(".mp__group")].find((b) => b.textContent?.includes("OpenCode"))!);
  await click([...host.querySelectorAll<HTMLButtonElement>(".mp__item")].find((b) => b.textContent === "glm-5-free")!);
  expect(summary()).toBe("GRAPH · glm-5-free");
  const deep = [...host.querySelectorAll("label")].find((l) => l.textContent?.includes("Deep research"))!.querySelector("input")!;
  await click(deep);
  expect(summary()).toBe("GRAPH · glm-5-free · Deep · Standard");
  await choose(selectWith("thorough"), "thorough");
  expect(summary()).toBe("GRAPH · glm-5-free · Deep · Thorough");
  await click(deep);
  expect(summary()).toBe("GRAPH · glm-5-free");
});
