// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AnswerBody } from "../components/AnswerBody";
import { newTurn, type Turn } from "../lib/chat";

/** FRONTEND-REFRESH-V1 U4b — citation markers become focusable chips with a hover card naming the source; code is left
 *  alone; a deep research report resolves its own ids. */

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

function turn(over: Partial<Turn>): Turn {
  return { ...newTurn("How is effort written?", "HYBRID"), done: true, ...over };
}

it("a chat marker names its source and shows the passage", async () => {
  const t = turn({
    answerText: "Effort has four factors [S1]. See `[S2]` in code.",
    receipt: { engine: "chat-retrieval-v2", mode: "HYBRID",
               legend: [{ tag: "S1", chunk_id: "chunk_aaa", breadcrumb: "Chapter 1 > Effort" }],
               chunks: [{ chunk_id: "chunk_aaa", title: "Laban", preview: "Effort is weight, time, space and flow." }] },
  });
  await act(async () => root.render(<AnswerBody t={t} models={[]} />));
  const btn = host.querySelector(".cite__btn") as HTMLButtonElement;
  expect(btn.textContent).toBe("[S1]");                                        // the model's own marker, kept verbatim
  expect(btn.getAttribute("aria-label")).toBe("Source S1: Laban");
  const card = host.querySelector(".cite__card")!;
  expect(card.textContent).toContain("Chapter 1 > Effort");
  expect(card.textContent).toContain("Effort is weight, time, space and flow.");
  expect(host.querySelector("code")!.textContent).toBe("[S2]");               // code keeps its brackets
  expect(host.querySelectorAll(".cite__btn")).toHaveLength(1);
  await act(async () => btn.click());
  expect(host.querySelector(".cite--open")).not.toBeNull();                  // click pins the card
});

it("a deep research marker resolves from the report's own citations", async () => {
  const t = turn({
    answerText: "Notation writes time [c2].", receipt: null,
    deep: { citations: [{ cid: "c2", title: "Benesh", source: "Benesh · p. 12", text: "Notation writes time and weight." }],
            unknown: [], summary: null },
  });
  await act(async () => root.render(<AnswerBody t={t} models={[]} />));
  expect(host.querySelector(".cite__btn")!.getAttribute("aria-label")).toBe("Source c2: Benesh");
  expect(host.querySelector(".cite__card")!.textContent).toContain("Benesh · p. 12");
});

it("an unknown marker is still a chip, without a card", async () => {
  await act(async () => root.render(<AnswerBody t={turn({ answerText: "Claim [S9].", receipt: null })} models={[]} />));
  expect(host.querySelector(".cite__btn")!.getAttribute("aria-label")).toBe("Source S9");
  expect(host.querySelector(".cite__card")).toBeNull();
});
