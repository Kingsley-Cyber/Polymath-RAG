// @vitest-environment jsdom
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";
import { AnswerBody } from "../components/AnswerBody";
import { newTurn, runTurn, type Turn } from "../lib/chat";
import type { ChatGapCheck, ChatSynthesis, RetrievalReceipt } from "../lib/contracts";

/** FACET-RETRIEVAL-V1 F5 / F6 — a synthesis answer carries `meta.synthesis` (and `meta.gap_check`): the answer body gains the
 *  facet badges (strong / single source / contested / not covered) and a "Sources by document" panel drawn with the deep
 *  report's sources rendering, the [S#] chips resolving through the chat receipt; the gap check's line names what was
 *  searched again. A turn without `meta.synthesis` (QA, older turns) renders exactly as before. */

const RECEIPT: RetrievalReceipt = {
  mode: "HYBRID", engine: "chat-retrieval-v2", evidence_count: 4,
  legend: [
    { tag: "S1", chunk_id: "c1", locator: "chunk:c1@0:9", breadcrumb: "Adweek Copywriting › Emotional copy" },
    { tag: "S2", chunk_id: "c2", locator: "chunk:c2@0:9", breadcrumb: "Ogilvy on Advertising › Headlines" },
    { tag: "S3", chunk_id: "c9", locator: "chunk:c9@100:190", breadcrumb: "handbook › Motion core › Granular motion control" },
  ],
  chunks: [
    { locator: "chunk:c1@0:9", doc_id: "doc_a", title: "Emotional copy", source_name: "Adweek Copywriting.pdf", preview: "Attention follows feeling." },
    { locator: "chunk:c2@0:9", doc_id: "doc_b", title: "Headlines", source_name: "Ogilvy on Advertising.pdf", preview: "The headline earns the second sentence." },
    { locator: "chunk:c9@100:190", doc_id: "doc_h", title: "Granular motion control", source_name: "handbook.html", preview: "A table of control dialects per model.", kind: "gap_check" },
  ],
};

const SYNTHESIS: ChatSynthesis = {
  contract: "chat-synthesis-v1", task_type: "GROUNDED_SYNTHESIS",
  facets: [
    { id: "f1", name: "emotional storytelling in ads", covered: true, docs: ["doc_a", "doc_b"], tags: ["S1", "S2"], sentences: 2, confidence: "strong" },
    { id: "f2", name: "directing the AI video model", covered: true, docs: ["doc_h"], tags: ["S3"], sentences: 1, confidence: "single_source" },
    { id: "f3", name: "when emotion-first ads fail", covered: true, docs: ["doc_b"], tags: ["S2"], sentences: 1, confidence: "contested" },
    { id: "f4", name: "sound design for ads", covered: false, docs: [], tags: [], sentences: 0, confidence: null },
  ],
  sources: [
    { doc_id: "doc_a", title: "Adweek Copywriting", cids: ["S1"], findings: 2 },
    { doc_id: "doc_b", title: "Ogilvy on Advertising", cids: ["S2"], findings: 2 },
    { doc_id: "doc_h", title: "handbook", cids: ["S3"], findings: 1 },
  ],
  documents: { in_evidence: 3, cited: 3, multi_doc_sentences: 1 },
  share: { top_doc: "doc_a", top_title: "Adweek Copywriting", top_share: 0.5, doc_counts: { doc_a: 2, doc_b: 1, doc_h: 1 } },
  sentences: 4, uncited: 0,
};

const GAP: ChatGapCheck = {
  contract: "chat-gap-check-v1", section_added: true,
  claims: [{ text: "The library doesn't bridge emotional direction to video model controls.", source: "sentence",
             query: "bridge emotional direction video model controls", found: 1, cited_added: ["S3"], refuted: true, edited: "subject_do+pointer" }],
  searches: [{ query: "bridge emotional direction video model controls", returned: 3, above_floor: 1, ms: 812 }],
};

const TEXT = "Emotion sells because attention follows feeling [S1][S2]. The passages first found don't bridge emotional direction to video model controls (more below: [S3]).\n\n**More on this.** The handbook maps emotional direction to per-model control dialects [S3].";

function turn(patch: Partial<Turn>): Turn {
  return { ...newTurn("q", "HYBRID"), ...patch };
}

it("a synthesis answer shows a badge per facet and the sources by document, its chips resolving through the receipt", () => {
  const html = renderToStaticMarkup(<AnswerBody models={[]} t={turn({ done: true, answerText: TEXT, receipt: RECEIPT, synthesis: SYNTHESIS, gapCheck: GAP })} />);
  expect(html).toContain("Sources by document (3)");
  expect(html).toContain("1 sentence cites two or more books");
  // the facets, each with its confidence badge (the deep report's §11.4 badges) and its book count
  expect(html).toContain("emotional storytelling in ads");
  expect(html).toContain("conf--strong");
  expect(html).toContain(">Strong<");
  expect(html).toContain("conf--single");
  expect(html).toContain(">Single source<");
  expect(html).toContain("conf--contested");
  expect(html).toContain(">Contested<");
  expect(html).toContain("sound design for ads");
  expect(html).toContain(">Not covered<");
  expect(html).toContain("2 books");
  // the books, most findings first, with their passages as citation chips (deep report's rendering) and the passage text
  const adweek = html.indexOf("Adweek Copywriting");
  const handbook = html.indexOf("<strong>handbook</strong>");
  expect(adweek).toBeGreaterThan(-1);
  expect(handbook).toBeGreaterThan(adweek);
  expect(html).toContain("supports 2 findings · 1 passage used");
  expect(html).toContain('aria-label="Source S3: Granular motion control"');   // the chip resolves through the receipt's legend + chunks
  expect(html).toContain("A table of control dialects per model.");
  expect(html).toContain("Granular motion control");
  // the gap check's line
  expect(html).toContain("Gap check: 1 claim searched again, 1 found more in the library — see “More on this”.");
  // the answer itself still renders its citations as chips
  expect(html).toContain("<strong>More on this.</strong>");
});

it("a turn without meta.synthesis renders as before: no facet badges, no sources panel", () => {
  const html = renderToStaticMarkup(<AnswerBody models={[]} t={turn({ done: true, answerText: "Emotion sells [S1].", receipt: RECEIPT })} />);
  expect(html).not.toContain("Sources by document");
  expect(html).not.toContain("facet-chip");
  expect(html).not.toContain("Gap check");
  expect(html).toContain("⛁ 4 chunks");
  // a gap check without a synthesis block (a multi-facet QA turn) is not shown either — the panel is the synthesis answer's
  const qa = renderToStaticMarkup(<AnswerBody models={[]} t={turn({ done: true, answerText: "x [S1].", receipt: RECEIPT, gapCheck: GAP })} />);
  expect(qa).not.toContain("Gap check");
});

it("the answer frame's meta.synthesis and meta.gap_check land on the turn; a frame without them leaves both null", async () => {
  async function stream(meta: Record<string, unknown>): Promise<Partial<Turn> | undefined> {
    const body = 'event: answer\ndata: ' + JSON.stringify({ kind: "llm", latency_ms: 10,
      result: { answer: "Emotion sells [S1].", model: "ollama:fake", meta: { verdict: "generated", ...meta } }, retrieval: RECEIPT }) + "\n\nevent: done\ndata: {}\n\n";
    vi.stubGlobal("fetch", vi.fn(async () => new Response(new ReadableStream<Uint8Array>({
      start(c) { c.enqueue(new TextEncoder().encode(body)); c.close(); },
    }))));
    const seen: Partial<Turn>[] = [];
    await runTurn({ message: "q" }, (p) => seen.push(p));
    vi.unstubAllGlobals();
    return seen.find((p) => p.model);
  }
  const withBlocks = await stream({ synthesis: SYNTHESIS, gap_check: GAP });
  expect(withBlocks?.synthesis?.contract).toBe("chat-synthesis-v1");
  expect(withBlocks?.synthesis?.facets?.map((f) => f.confidence)).toEqual(["strong", "single_source", "contested", null]);
  expect(withBlocks?.gapCheck?.claims?.[0]?.refuted).toBe(true);
  const without = await stream({});
  expect(without?.synthesis).toBeNull();
  expect(without?.gapCheck).toBeNull();
  expect(without?.verdict).toBe("generated");
});
