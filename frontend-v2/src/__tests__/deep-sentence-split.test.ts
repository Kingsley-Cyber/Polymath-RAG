import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { auditSentences, SENTENCE_PATTERN } from "../lib/deep";

/** DR7 sentence audit — the page's split must equal the backend's (`deep_research.evidence.split_sentences`), or the uncited
 *  marks land on the wrong sentences. One fixture, written from the backend's own output, pins both sides
 *  (`tests/contracts/test_deep_research_sentence_split.py` reads the same file). */

const shared = JSON.parse(readFileSync(new URL("./fixtures/deep-sentence-split.json", import.meta.url), "utf8")) as
  { pattern: string; fixture: string; expected: string[] };

it("uses the backend's sentence pattern, character for character", () => {
  expect(SENTENCE_PATTERN).toBe(shared.pattern);
});

it("splits the shared fixture exactly as the backend does, and each sentence's offsets point at its text", () => {
  const got = auditSentences(shared.fixture);
  expect(got.map((s) => s.text)).toEqual(shared.expected);
  for (const s of got) expect(shared.fixture.slice(s.start, s.end)).toBe(s.text);
});
