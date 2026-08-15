# D4.1 Answer-Support / Entailment Model Qualification — REPORT (REJECT)

Frozen 2026-08-15. Verdict: **REJECT — no candidate model demonstrates a
defensible precision-first support separation.** No production wiring
was performed (answer_synthesis.py, evidence_assembly.py, contracts,
and /chat untouched).

## Frozen data

- Pair set: `eval/d4/artifacts/d41_pairs.jsonl` — 794 (query, passage)
  pairs over the frozen D4 queries + I2 corpus, sha256
  `1f67a5f8685982ce47b8342955e72f876785e5a55e8315130cc0ed1d32bf5898`.
  Labels: SUPPORTS=43, TOPIC_ONLY=177, IRRELEVANT=559,
  CONTRADICTS=15. Includes child_chunk, section_summary, and
  document_summary candidates and 3 frozen contradiction queries
  (c1-c3) built from natural corpus semantics.
- D4 frozen query set hash:
  `7731f57573aa511543d9b2e4742692c99d71de48d546c8323e79423f692e9e74`.

## Models tested (bounded set, deterministic inference, MPS)

| model | task | num_labels | license | deterministic |
|---|---|---|---|---|
| cross-encoder/nli-deberta-v3-xsmall | NLI 3-way | 3 | Apache-2.0 | yes |
| cross-encoder/nli-deberta-v3-base | NLI 3-way | 3 | Apache-2.0 | yes |
| cross-encoder/qnli-distilroberta-base | QNLI question-passage | 1 (sigmoid) | Apache-2.0 | yes |
| cross-encoder/qnli-electra-base | QNLI question-passage | 1 (sigmoid) | Apache-2.0 | yes |

## Findings

NLI models (premise-hypothesis task): entailment probability ≈ 0 for
virtually all question-passage pairs (SUPPORTS max 0.30/0.96 tail
spikes, p50 0.001-0.007). Task misalignment; recall ~0 at every
threshold. REJECT.

QNLI models (the correct task family):

- distributions ARE separated: negatives p50 ≈ 0.01-0.03 vs SUPPORTS
  p90 ≈ 0.98 (both models).
- precision at any threshold: distilroberta max P=0.80 (t=0.99,
  R=0.09); electra max P=0.58 (t=0.99, R=0.26). No threshold reaches
  the precision-first bar.
- Failure modes (frozen error analysis):
  1. CONTRADICTS pairs score 0.94-0.99 as support — binary QNLI
     cannot separate "answers yes" from "answers no".
  2. Model hallucination on abstract term pairs ("correspondence" →
     "reconciles" gives 0.95 to an unrelated systems passage).
  3. q4 (terminology-mismatch) fails outright: 0 support hits vs
     24-29 false supports (electra).
  4. Some "false supports" are gold-strictness artifacts
     (retrieval_practice partially answers q4) — recorded, not used
     to inflate results.
- Latency (MPS, post-G3 compatible): qnli-distilroberta ~0.5ms/pair
  (794 pairs in ~2s), electra ~1.4ms/pair. Size ~82M/~110M params.

## Query-level controls at t=0.95 (best zero-ish-FP operating point)

- qnli-distilroberta: q1/q2/q6 covered; q3 has 1 negative above
  threshold; q4 uncovered; c1/c3 contradictions leak.
- qnli-electra: q1/q2/q3/q5/q7 covered; q6 has 1 negative; q4 fails
  catastrophically; contradictions leak.
- Unsupported u1-u4 and same-domain u5/u6: rejection ≥ 0.994 at
  t=0.95 (both models).

## Verdict

PROMOTE_CANDIDATE: none. REJECT. The QNLI family is the right task
alignment and separates the bulk of negatives, but no off-the-shelf
candidate provides a defensible precision-first operating point for
authorizing synthesis. Contradiction detection needs a 3-way head;
abstract-term hallucination and the q4 failure mode need either
fine-tuning on support-labeled data or an explicit 3-way
supports/topic_only/contradicts classifier — both are future user
decisions, not implemented here.

## Exposure record

d41_pairs.jsonl: authored from the D4 development set + I2 corpus
content; first scored use 2026-08-15. Not held out. Artifacts frozen
under eval/d4/artifacts/ (eval outputs, analysis, pair set + sha256).
