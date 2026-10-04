// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { newTurn, type Turn } from "../lib/chat";
import { emptySession } from "../lib/chatStore";
import { Chat } from "../screens/Chat";

/** COPY-ON-HOVER-V1 (the owner, 2026-10-04: "there should be an input and output simple button that shows up when I hover
 *  with mouse to simply copy"): a copy button beside the question (input) and under the answer (output), hidden until the
 *  pointer is over the message. Before: only the answer had one, always showing; the question had none. */

let host: HTMLDivElement;
let root: Root;
let written: string[];

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const dom = (globalThis as unknown as { jsdom: { window: Window } }).jsdom;
  vi.stubGlobal("localStorage", dom.window.localStorage);
  localStorage.clear();
  written = [];
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({})));
  Object.defineProperty(navigator, "clipboard", { configurable: true,
    value: { writeText: vi.fn(async (t: string) => { written.push(t); }) } });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  vi.useRealTimers();
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

const ANSWER = "**Continuity** matters.\n\n- charge batteries\n- test media";

function turn(patch: Partial<Turn> = {}): Turn {
  return { ...newTurn("How do crews work?", "HYBRID"), done: true, answerText: ANSWER, ...patch };
}

async function show(turns: Turn[]) {
  await act(async () => root.render(
    <Chat corpusId="cinema" session={{ ...emptySession("cinema"), turns }} onUpdateTurns={() => {}} models={[]} corpusExploreAvailable={false} />));
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

const copyButton = (label: string) => host.querySelector(`button[aria-label="${label}"]`) as HTMLButtonElement | null;

it("a question and an answer each carry a copy button that the stylesheet shows on hover", async () => {
  await show([turn()]);
  const q = copyButton("Copy question")!;
  const a = copyButton("Copy answer")!;
  expect(q).not.toBeNull();
  expect(a).not.toBeNull();
  expect(q.classList.contains("copy-btn--hover")).toBe(true);
  expect(a.classList.contains("copy-btn--hover")).toBe(true);
  // the question's button follows its bubble (so the bubble's :hover reveals it); the answer's sits in the answer block
  expect(q.previousElementSibling?.classList.contains("msg-user__bubble")).toBe(true);
  expect(a.closest(".msg-assistant")).not.toBeNull();
});

it("copying the question puts exactly the question on the clipboard, says Copied, stays shown, then goes back", async () => {
  await show([turn()]);
  const q = copyButton("Copy question")!;
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  await act(async () => q.click());
  expect(written).toEqual(["How do crews work?"]);
  expect(q.getAttribute("aria-label")).toBe("Copied");
  expect(q.classList.contains("copy-btn--done")).toBe(true);           // the stylesheet keeps it visible while Copied
  await act(async () => { vi.advanceTimersByTime(2000); });
  expect(q.getAttribute("aria-label")).toBe("Copy question");
  expect(q.classList.contains("copy-btn--done")).toBe(false);
});

it("copying the answer puts the Markdown as written on the clipboard", async () => {
  await show([turn()]);
  await act(async () => copyButton("Copy answer")!.click());
  expect(written).toEqual([ANSWER]);
});

it("an answer still streaming offers no answer copy (the text is incomplete) but its question can be copied", async () => {
  await show([turn({ done: false, answerText: "partial" })]);
  expect(copyButton("Copy answer")).toBeNull();
  expect(copyButton("Copy question")).not.toBeNull();
});

it("a deep-research turn's question has the copy button too", async () => {
  const t = turn({ deepRun: { status: "running", request: { corpusId: "cinema", preset: "quick", mode: "HYBRID" } } });
  await show([t]);
  const q = copyButton("Copy question");
  expect(q).not.toBeNull();
  expect(q!.previousElementSibling?.textContent).toBe("How do crews work?");
});

it("the stylesheet hides the button until hover, and keeps it for keyboard focus, the Copied moment and touch screens", () => {
  const css = readFileSync("src/styles/app.css", "utf8")   // vitest runs from frontend-v2;
  expect(css).toMatch(/\.copy-btn--hover\s*\{\s*opacity:\s*0;/);
  const reveal = css.slice(css.indexOf(".msg-user__bubble:hover + .copy-btn--hover"));
  const rule = reveal.slice(0, reveal.indexOf("}"));
  for (const selector of [".msg-user__bubble:hover + .copy-btn--hover", ".msg-assistant:hover .copy-btn--hover",
                          ".copy-btn--hover:focus-visible", ".copy-btn--hover.copy-btn--done"]) {
    expect(rule, selector).toContain(selector);
  }
  expect(rule).toMatch(/opacity:\s*1/);
  expect(css).toMatch(/@media \(hover: none\)\s*\{\s*\.copy-btn--hover\s*\{\s*opacity:\s*1;/);
});
