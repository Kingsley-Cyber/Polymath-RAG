// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";
import { DeepReport } from "../components/deep/DeepReport";
import { newTurn, type Turn } from "../lib/chat";
import type { DeepReportModel } from "../lib/contracts";
import { auditSentences, confirmedIds, liveState, methodLines, reportFileName, reportMarkdown, splitTldr } from "../lib/deep";

/** DEEP-RESEARCH-MODE-V1 §11.2 parts 3–4 (DR7d) — the report view drawn from a fake `report_model`: the tabs, the TL;DR block,
 *  the confidence badges, counter-evidence and open questions, the sources by book, the method in words, the audit's
 *  "no citation" marks (and the counts alone when the sentences cannot be matched), and the Markdown export with footnotes. */

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
  vi.restoreAllMocks();
});

const PROSE = [
  "## TL;DR",
  "Laban effort has four factors: weight, time, space and flow [c1]. Teachers use effort notation to train expressive movement [c2]. It is taught mostly in dance schools.",
  "",
  "## The four factors",
  "Weight, time, space and flow each run between two poles [c1][c3]. **Flow is the hardest to observe.** Some writers add a fifth factor [c9].",
  "",
  "## Where sources disagree",
  "Critics say the notation is too coarse for film acting [c4].",
].join("\n");

const REPORT: DeepReportModel = {
  goals: [
    { id: "1.1", goal: "The four effort factors", documents: 2, findings: [
      { text: "Effort has four factors: weight, time, space and flow", cids: ["c1", "c3"], confidence: "strong", move: "broad" },
      { text: "Flow is the hardest factor to observe", cids: ["c3"], confidence: "single_source", move: "deep" }] },
    { id: "1.3", goal: "Where effort notation falls short", documents: 1, findings: [
      { text: "The notation is too coarse for film acting", cids: ["c4"], confidence: "contested", move: "inverse" }] },
  ],
  counter: [{ text: "Critics call the notation too coarse for film", cids: ["c4"], goal_id: "1.3" },
            { text: "One school dropped it", cids: ["c2"] }],
  open_questions: ["How is effort notated in film acting?", { question: "Which schools dropped effort notation?" }],
  sources: [{ doc_id: "d1", title: "Laban", cids: ["c1", "c3"], findings: 2 },
            { doc_id: "d2", title: "Teaching Movement", cids: ["c2"], findings: 1 },
            { doc_id: "d3", title: "Film Acting Now", cids: ["c4"], findings: 1 }],
  method: { preset: "standard", intent: "COMPARISON", evaluative: true, searches: 9, stop_reason: "coverage_complete", elapsed_s: 92,
            gate: { scored: 9, dropped: 1, failed_open: 0, user_kept: 1 }, model: "litellm:anthropic/deepseek-v4-flash" },
};

function turn(over: { report?: DeepReportModel; audit?: Record<string, unknown>; text?: string } = {}): Turn {
  return {
    ...newTurn("How does Laban write effort?", "DEEP · standard"), done: true, model: "litellm:anthropic/deepseek-v4-flash",
    latencyMs: 92000, answerText: over.text ?? PROSE,
    deep: {
      citations: [
        { cid: "c1", title: "Laban", source: "Laban · ch. 1", text: "Effort has four factors." },
        { cid: "c2", title: "Teaching Movement", source: "Teaching Movement · p. 40", text: "Teachers train expression with effort." },
        { cid: "c3", title: "Laban", source: "Laban · ch. 3", text: "Flow is hard to see." },
        { cid: "c4", title: "Film Acting Now", source: "Film Acting Now · p. 7", text: "Too coarse for the screen." },
      ],
      unknown: ["c9"],
      summary: {
        learnings: 4, retrievals: 9, seen_rows: 30, cited_rows: 4, stop_reason: "coverage_complete",
        moves: { intent: "COMPARISON", evaluative: true, inverse: { searched: 3, learnings: 1 },
                 levels: [{ level: 1, searched: { broad: 2, deep: 0, adjacent: 0, inverse: 1 } },
                          { level: 2, searched: { broad: 0, deep: 4, adjacent: 0, inverse: 2 } }] },
        report_model: over.report ?? REPORT,
        audit: over.audit ?? { sentences: 7, cited: 4, uncited: [2, 4, 5], invalid_cids: ["c9"] },
      },
    },
  };
}

async function show(t: Turn, onResearchNext = vi.fn()) {
  await act(async () => root.render(<DeepReport t={t} report={(t.deep!.summary!.report_model) as DeepReportModel} onResearchNext={onResearchNext} />));
  return onResearchNext;
}

function tab(name: string): HTMLButtonElement {
  return [...host.querySelectorAll<HTMLButtonElement>('[role="tab"]')].find((b) => b.textContent === name)!;
}

describe("the report tab", () => {
  it("renders the TL;DR first, the prose with citation chips, and the counter-evidence line", async () => {
    await show(turn());
    expect([...host.querySelectorAll('[role="tab"]')].map((b) => b.textContent)).toEqual(["Report", "Evidence", "Sources", "Method"]);
    expect(tab("Report").getAttribute("aria-selected")).toBe("true");
    const tldr = host.querySelector(".tldr")!;
    expect(tldr.querySelector(".tldr__label")!.textContent).toBe("TL;DR");
    expect(tldr.textContent).toContain("Laban effort has four factors");
    expect(tldr.textContent).not.toContain("Weight, time, space and flow each run");
    expect(tldr.compareDocumentPosition(host.querySelector("h2")!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect([...host.querySelectorAll(".tabpanel h2")].map((h) => h.textContent)).toEqual(["The four factors", "Where sources disagree"]);
    expect(host.querySelector('.cite__btn[aria-label="Source c1: Laban"]')).not.toBeNull();
    expect(host.querySelector(".counter-evidence")!.textContent).toBe("Counter-evidence: 1 finding");
  });

  it("underlines each sentence the audit found uncited, with the words \"no citation\"", async () => {
    await show(turn());
    expect([...host.querySelectorAll(".uncited")].map((u) => u.textContent)).toEqual([
      "It is taught mostly in dance schools.", "Flow is the hardest to observe.", "Some writers add a fifth factor [c9]."]);
    expect([...host.querySelectorAll(".uncited__note")].map((n) => n.textContent)).toEqual(["no citation", "no citation", "no citation"]);
    expect(host.querySelector(".tldr .uncited")!.textContent).toBe("It is taught mostly in dance schools.");   // the TL;DR slice maps too
    expect(host.querySelector("strong .uncited")).not.toBeNull();                                            // across emphasis
    const note = host.querySelector(".audit-note")!.textContent!;
    expect(note).toContain("3 of 7 sentences have no citation: underlined below.");
    expect(note).toContain("Cited but not found in the research: c9.");
  });

  it("shows the counts alone when the audit's sentences cannot be matched to the prose", async () => {
    await show(turn({ audit: { sentences: 8, cited: 6, uncited: [2, 4] } }));             // the backend split differently
    expect(host.querySelector(".uncited")).toBeNull();
    expect(host.querySelector(".audit-note")!.textContent).toContain(
      "2 of 8 sentences have no citation. They could not be matched to the text here, so they are not marked.");
    await act(async () => root.unmount());
    root = createRoot(host);
    await show(turn({ audit: { sentences: 7, cited: 6, uncited: [0] } }));                // sentence 0 IS cited: not ours
    expect(host.querySelector(".uncited")).toBeNull();
    expect(host.querySelector(".audit-note")!.textContent).toContain("could not be matched");
  });

  it("says so when every sentence is cited", async () => {
    await show(turn({ audit: { sentences: 7, cited: 7, uncited: [] } }));
    expect(host.querySelector(".audit-note")!.textContent).toContain("Every sentence (7) cites a passage.");
    expect(host.querySelector(".uncited")).toBeNull();
  });
});

describe("the evidence, sources and method tabs", () => {
  it("Evidence: per goal, each finding with its confidence badge; counter-evidence; open questions", async () => {
    await show(turn());
    await act(async () => tab("Evidence").click());
    expect(tab("Evidence").getAttribute("aria-selected")).toBe("true");
    const badges = [...host.querySelectorAll(".conf")];
    expect(badges.map((b) => b.textContent)).toEqual(["Strong", "Single source", "Contested"]);
    expect(badges.map((b) => b.className)).toEqual(["conf conf--strong", "conf conf--single", "conf conf--contested"]);
    const goals = [...host.querySelectorAll(".evidence-goal")];
    expect(goals[0]!.querySelector("h3")!.textContent).toBe("The four effort factors");
    expect(goals[0]!.textContent).toContain("2 findings · 2 books");
    expect(goals[0]!.querySelector('.cite__btn[aria-label="Source c3: Laban"]')).not.toBeNull();
    expect(goals[1]!.querySelector(".counter")!.textContent).toContain("Critics call the notation too coarse for film");
    expect(goals[2]!.textContent).toContain("One school dropped it");                     // counter-evidence without a goal
    const open = goals.find((g) => g.querySelector("h3")?.textContent === "Open questions")!;
    expect([...open.querySelectorAll("li")].map((l) => l.textContent)).toEqual([
      "How is effort notated in film acting?", "Which schools dropped effort notation?"]);
  });

  it("Sources: by book, the passages used and how many findings each supports", async () => {
    await show(turn());
    await act(async () => tab("Sources").click());
    const books = [...host.querySelectorAll(".book")];
    expect(books).toHaveLength(3);
    expect(books[0]!.querySelector(".book__head")!.textContent).toBe("Labansupports 2 findings · 2 passages used");
    expect([...books[0]!.querySelectorAll(".cite-id")].map((c) => c.textContent)).toEqual(["c1", "c3"]);
    expect(books[0]!.textContent).toContain("Laban · ch. 3");
    expect(books[1]!.textContent).toContain("supports 1 finding · 1 passage used");
  });

  it("Method: the run in plain words", async () => {
    await show(turn());
    await act(async () => tab("Method").click());
    expect([...host.querySelectorAll(".method li")].map((l) => l.textContent)).toEqual([
      "Depth: Standard, up to 3 searches wide and 2 rounds deep.",
      "Question type: comparison; it asks for a judgement, so the research also looked for counter-evidence.",
      "Searches: 9 (Main answer 2 · Deeper 4 · Counter-evidence 3).",
      "Findings: 4, from 30 passages read; the findings rest on 4 passages.",
      "Relevance check: 9 planned searches scored against your question, 1 dropped as off the question; 1 of your own parts kept even so.",
      "Stopped because every part had at least 2 findings from 2 books.",
      "Time: 1:32.",
      "Report written by deepseek-v4-flash.",
      "Citation check: 4 of 7 sentences cite a passage.",
    ]);
  });

  it("the tabs follow the arrow keys", async () => {
    await show(turn());
    tab("Report").focus();
    await act(async () => { tab("Report").dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); });
    expect(tab("Evidence").getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tab("Evidence"));
    await act(async () => { tab("Evidence").dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true })); });
    expect(tab("Method").getAttribute("aria-selected")).toBe("true");
    expect(host.querySelector('[role="tabpanel"]')!.getAttribute("aria-labelledby")).toBe(tab("Method").id);
  });
});

describe("the actions", () => {
  it("\"Research this next\" hands the open question to the chat", async () => {
    const pick = await show(turn());
    const chip = [...host.querySelectorAll<HTMLButtonElement>(".next-chip")].map((b) => b.textContent);
    expect(chip).toEqual(["How is effort notated in film acting?", "Which schools dropped effort notation?"]);
    await act(async () => host.querySelector<HTMLButtonElement>(".next-chip")!.click());
    expect(pick).toHaveBeenCalledWith("How is effort notated in film acting?");
  });

  it("the Markdown export turns each citation into a footnote: Title — where", () => {
    const md = reportMarkdown("How does Laban write effort?",
      "## TL;DR\nEffort has four factors [c1]. Teachers use it [c2, c3].\n\nSee `[c1]` in code, [a link](https://example.test) and [c9].",
      [{ cid: "c1", title: "Laban", source: "Laban · ch. 1" }, { cid: "c2", title: "Teaching Movement", source: "Teaching Movement · p. 40" },
       { cid: "c3", title: "Laban", source: "Laban" }]);
    expect(md).toBe([
      "# How does Laban write effort?",
      "",
      "## TL;DR",
      "Effort has four factors [^c1]. Teachers use it [^c2][^c3].",
      "",
      "See `[c1]` in code, [a link](https://example.test) and [^c9].",
      "",
      "[^c1]: Laban — Laban · ch. 1",
      "[^c2]: Teaching Movement — Teaching Movement · p. 40",
      "[^c3]: Laban",
      "[^c9]: cited, but not found in the research",
      "",
    ].join("\n"));
    expect(reportFileName("How does Laban write effort?")).toBe("deep-research-how-does-laban-write-effort.md");
  });

  it("Copy as Markdown and Download .md hand over the footnoted report", async () => {
    const copied: string[] = [];
    vi.stubGlobal("navigator", { clipboard: { writeText: async (s: string) => { copied.push(s); } } });
    const blobs: Blob[] = [];
    const revoked: string[] = [];
    const u = URL as unknown as { createObjectURL?: (b: Blob) => string; revokeObjectURL?: (s: string) => void };
    const saved = { create: u.createObjectURL, revoke: u.revokeObjectURL };
    u.createObjectURL = (b: Blob) => { blobs.push(b); return "blob:report"; };      // jsdom has no object URLs
    u.revokeObjectURL = (s: string) => { revoked.push(s); };
    onTestFinished(() => { u.createObjectURL = saved.create; u.revokeObjectURL = saved.revoke; });
    const clicks: HTMLAnchorElement[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { clicks.push(this); });
    await show(turn());
    await act(async () => [...host.querySelectorAll("button")].find((b) => b.textContent?.includes("Copy as Markdown"))!.click());
    expect(copied[0]).toContain("[^c1]: Laban — Laban · ch. 1");
    expect(copied[0]).toContain("flow [^c1]. Teachers");
    expect(host.textContent).toContain("Copied");
    await act(async () => [...host.querySelectorAll("button")].find((b) => b.textContent?.includes("Download .md"))!.click());
    expect(clicks[0]!.download).toBe("deep-research-how-does-laban-write-effort.md");
    expect(clicks[0]!.getAttribute("href")).toBe("blob:report");
    expect(await blobs[0]!.text()).toBe(copied[0]);
    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
    expect(revoked).toEqual(["blob:report"]);                                          // the object URL is let go
  });
});

describe("the client model", () => {
  it("splits prose into the audit's sentences: headings, code, tables and rules skipped; a trailing citation stays", () => {
    const md = "# Title\nOne fact [c1]. Two facts. [c2] Three?\n\n- Item one [c3].\n- Item two\n```\nCode. Not prose.\n```\n| a | b |\n---\n> Quoted line. Another.";
    const s = auditSentences(md);
    expect(s.map((x) => x.text)).toEqual(["One fact [c1].", "Two facts. [c2]", "Three?", "Item one [c3].", "Item two", "Quoted line.", "Another."]);
    expect(s.every((x) => md.slice(x.start, x.end) === x.text)).toBe(true);
    expect(auditSentences('He said "stop." Then left [c1].\n**Bold claim.** Next one.').map((x) => x.text))
      .toEqual(['He said "stop."', "Then left [c1].", "**Bold claim.**", "Next one."]);
  });

  it("finds the TL;DR under its heading, or before the first heading", () => {
    expect(splitTldr("## TL;DR\nShort answer [c1].\n\n## Detail\nMore.").tldr?.text.trim()).toBe("Short answer [c1].");
    expect(splitTldr("Opening answer [c1].\n\n## Detail\nMore.").tldr?.text.trim()).toBe("Opening answer [c1].");
    expect(splitTldr("## Detail\nMore.").tldr).toBeNull();
    expect(splitTldr("No headings at all.").tldr).toBeNull();
    const md = "## Summary\nA [c1].\n## Rest\nB.";
    const p = splitTldr(md);
    expect(md.slice(p.tldr!.start, p.tldr!.start + p.tldr!.text.length)).toBe(p.tldr!.text);
    expect(md.slice(p.rest.start)).toBe(p.rest.text);
  });

  it("numbers a confirmed plan in the plan's own id scheme", () => {
    const plan = (ids: string[]) => ({ goals: ids.map((id) => ({ id, goal: "g", query: "q", move: "broad" })) });
    expect(confirmedIds(plan(["1.1", "1.2", "1.3"]), 2)).toEqual(["1.1", "1.2"]);
    expect(confirmedIds(plan(["1.1", "1.2", "1.3"]), 4)).toEqual(["1.1", "1.2", "1.3", "1.4"]);
    expect(confirmedIds(plan(["g1", "g2"]), 3)).toEqual(["g1", "g2", "g3"]);
    expect(confirmedIds(plan(["x", "y"]), 2)).toEqual(["g1", "g2"]);
  });

  it("a run without a confirmed plan names its goals from their first search", () => {
    const t: Turn = { ...newTurn("q", "DEEP · quick"), deepRun: { status: "running", request: { corpusId: "cinema", preset: "quick", mode: "HYBRID" } },
      phases: [
        { stage: "deep_retrieve", label: "Searching: effort factors", at: 1, data: { move: "broad", query: "effort factors", goal_id: "1.1" } },
        { stage: "deep_retrieve", label: "Searching: effort in film", at: 2, data: { move: "inverse", query: "effort in film", goal_id: "1.2" } },
        { stage: "deep_gate", label: "Checked the planned searches against the question: 1 dropped as off the question", at: 3, data: { scored: 3, dropped: 1 } },
      ],
      deepCoverage: { goals: [{ id: "1.1", learnings: 2, documents: ["d1", "d2"] }, { id: "1.2", learnings: 1, documents: ["d2"] }] } };
    const s = liveState(t);
    expect(s.goals.map((g) => [g.text, g.move, g.learnings, g.documents])).toEqual([
      ["effort factors", "broad", 2, 2], ["effort in film", "inverse", 1, 1]]);
    expect(s.books).toBe(2);                                                            // the union of the doc ids
    expect(s.findings).toBe(3);
    expect(s.feed.map((x) => x.kind)).toEqual(["search", "search", "note"]);
    expect(s.goals[1]!.active).toBe(true);                                              // the latest search's goal, while live
  });

  it("the Method tab reads an older run's counts when there is no method block", () => {
    const t: Turn = { ...newTurn("q", "DEEP · thorough"), done: true, latencyMs: 61000,
      deep: { citations: [], unknown: [], summary: { learnings: 3, retrievals: 9, stop_reason: "no_new_followups", dropped_learnings: 1 } } };
    expect(methodLines(t)).toEqual([
      "Depth: Thorough, up to 4 searches wide and 2 rounds deep.",
      "Searches: 9.",
      "Findings: 3.",
      "1 finding left out because its citation did not match the passages read.",
      "Stopped because a round raised no new questions.",
      "Time: 1:01.",
    ]);
  });
});
