# D4 Text-Evidence Support Admission — QUALIFICATION REPORT (REJECT)

Frozen 2026-08-15. Verdict: **REJECT — existing signals are insufficient
for text support admission.** No production change made.

## Method

- Frozen development set: `eval/d4/queries.json`
  (sha256 `7731f57573aa511543d9b2e4742692c99d71de48d546c8323e79423f692e9e74`):
  7 answerable + 6 unsupported (incl. 2 same-domain + 1 keyword-trap)
  over the frozen I2 corpus.
- Measurement: `eval/d4/measure.py` captured, per candidate, dense
  score, lexical score, G3 rerank score, pre/post rank, text_kind,
  doc/chunk ids from the FROZEN pipeline (no retrieval change while
  collecting evidence). 779 candidate records, gold-labeled.
- Gold: `eval/d4/artifacts/gold.json` (31 supported labels).

## Signal separation (SUPPORTED vs UNSUPPORTED candidates)

| signal | S p50 | S min | U p95 | U max | zero-FP threshold | TP at zero-FP |
|---|---|---|---|---|---|---|
| dense | 0.380 | 0.201 | 0.353 | 0.613 | >=0.65 | 1/24 |
| lexical | 0.799 | 0.153 | 1.648 | 3.161 | >=3.96 | 2/31 |
| G3 rerank | 5.94 | -2.63 | -1.31 | 6.50 | >=7.19 | 5/16 |

Query-level feasibility interval for a single rerank threshold:
`(6.5, 2.25]` — empty. No threshold admits all answerable queries
while rejecting all unsupported ones.

## Decisive counter-evidence

Same-domain negatives outscore true positives:

- u5 "What does metacognitive scaffolding theory say about error
  monitoring?" → rerank 6.44 on psych/metacognitive_monitoring.md
  (topically related; does NOT answer the question).
- u6 "How does the system manage worker memory pools under load?" →
  rerank 6.50 on systems/worker_pools.md (keyword overlap; does NOT
  answer).
- q5 "What distinction do researchers draw between judging knowledge
  and acting on it?" → its TRUE supporting passage scores 1.25–2.25.

The G3 cross-encoder measures topical relatedness, not answer
support. Dense and lexical are strictly weaker. No frozen signal
separates "answers the question" from "related but silent".

## Conclusion

Per the D4 promotion rule: STOP. Existing retrieval/reranker scores
are insufficient for support admission. No heuristic was invented to
force a PASS. An answerability/entailment signal (a model the frozen
architecture does not yet have) would be required; that is a user
decision, not a D4 implementation choice.

## Exposure record

queries.json: authored against the I2 corpus; first scored use 2026-08-15
(development). Not claimed held out. Artifacts frozen in eval/d4/artifacts/.
