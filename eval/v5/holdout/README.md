# Holdout grading (LLM-DIRECT-CANON P5)

The system is graded on ANSWERS to gold questions, never on fact-tuple
self-consistency. Two sets:

- `dev_questions.json` — development seed set, written by the executor from
  the corpora. NEVER release evidence; the grader writes
  `DEV-RESULTS-<timestamp>.json` under `/private/tmp/polymath_fleet/holdout/`
  (`POLYMATH_HOLDOUT_OUT`), never into the repository.
- `sealed/<name>.json` — owner-supplied, written without looking at retrieval
  output, hashed (sha256 of the file bytes). Only a sealed run may write
  `eval/v5/release_evidence/sealed_holdout.json` (release_gates SEALED_HOLDOUT):
  `grade_holdout.py --questions sealed/x.json --sealed --manifest-sha256 <sha>`.

Question schema (one object per question):
```json
{"id": "sb-01", "corpus_id": "ecom-meta-v1", "question": "...",
 "expected_docs": ["Building_a_StoryBrand_Miller.md"],      // any cited source_name must match one (substring, case-insensitive)
 "must_include_any": ["guide", "hero"],                     // answer must contain at least one phrase (case-insensitive)
 "must_not_include": ["villain is the customer"],           // optional: presence = WRONG
 "expects_abstain": false}                                  // true for nonce / out-of-corpus questions
```
Verdict per question: `supported` (cited an expected doc AND a required
phrase is present; or abstained when expected), `wrong` (a forbidden
phrase, or answered when abstention was expected, or cited only unexpected
documents while asserting), `unexplained` (anything else: no citations,
error, phrase missing without contradiction). Zero-tolerance counters:
`foreign_corpus_citations`, `answers_without_citations`, `errors`.
Gate thresholds (release_gates): supported ≥ 90 %, wrong ≤ 5 %,
unexplained = 0, every zero-tolerance counter = 0.
