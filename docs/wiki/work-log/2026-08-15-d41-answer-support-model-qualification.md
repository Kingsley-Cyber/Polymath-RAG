---
change_id: d41-answer-support-model-qualification
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (qualification only; no production wiring)
---

# D4.1: answer-support / entailment model qualification — REJECT

## Contract

Qualify small locally-runnable models for the (query, passage) →
SUPPORTS / TOPIC_ONLY / CONTRADICTS / IRRELEVANT decision on the
frozen D4 data, without touching production. Precision is the
priority; promote only with a defensible precision-first operating
point; otherwise REJECT and report. No production wiring regardless
of outcome.

## Changes

- `eval/d4/build_d41_pairs.py`: frozen 794-pair (query, passage) set
  with 4-way gold labels (+3 natural-semantics contradiction queries),
  sha256 `1f67a5f8…5898`.
- `eval/d4/eval_d41.py` + `eval/d4/analyze_d41.py`: deterministic
  (2-run) candidate evaluation and precision-first analysis.
- `eval/d4/REPORT_D41.md` + frozen artifacts
  (`d41_pairs.jsonl/.sha256`, per-model run JSONs, analysis).

## Proof

Four candidates measured (2 NLI DeBERTa, 2 QNLI cross-encoders):
- NLI models: premise-hypothesis task misalignment — entailment
  probability ≈ 0 for question-passage pairs; recall ≈ 0. REJECT.
- QNLI models: correct task family, distributions separated
  (negatives p50 ≈ 0.01-0.03 vs SUPPORTS p90 ≈ 0.98), latency
  ~0.5-1.4 ms/pair (post-G3 compatible), deterministic. BUT max
  precision at any threshold: 0.80 (distilroberta, R=0.09) /
  0.58 (electra, R=0.26). Failure modes frozen: contradiction pairs
  score as support (binary head), abstract-term hallucination
  ("correspondence"→"reconciles"), q4 terminology-mismatch query
  fails outright, some FPs are gold-strictness artifacts.

Verdict: PROMOTE_CANDIDATE none — REJECT. No threshold, no
integration, no production change. Latency/size of the QNLI family
recorded for a future fine-tune/3-way classifier decision (user
decision, not implemented).

## Rejected claims

- No production file was modified (answer_synthesis.py,
  evidence_assembly.py, EvidenceBundle contracts, /chat untouched).
- No heuristic was composed to force a pass (e.g., no QNLI+contra
  two-model gate) — recorded as observation only.

## Open contract gaps

- TEXT support admission still has no qualified signal. Options for
  the user: (a) fine-tune a 3-way supports/topic_only/contradicts
  classifier on the frozen pair set, (b) accept graph-only
  abstention semantics, (c) other.
