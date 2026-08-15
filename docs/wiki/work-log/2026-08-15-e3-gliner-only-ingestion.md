---
change_id: e3-gliner-only-ingestion
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (qualification only; no production change)
---

# E3: GLiNER-only local ingestion qualification — PASS (with recorded quality findings)

## Contract

Prove the production ingestion pipeline end-to-end with GLiNER as the
ONLY learned extraction model (no vLLM, no generative LLM, no API
extraction, no GLiREL, no alternate encoder). Frozen model:
urchade/gliner_medium-v2.1 @ 40ec4193…; frozen thresholds; lexical-only
compiler posture; no hidden fallback.

## Changes

- `eval/e3/corpus/`: frozen 14-file corpus across 6 domains
  (cybersecurity, software, e-commerce, psychology, cinema,
  transcripts) and 6 formats (md/txt/html/docx/epub/pdf) + the two
  user-provided metacognition documents (SHA256SUMS frozen).
- `eval/e3/verify_e3.py`: 13-phase qualifier (model contract, golden
  path + replay, double-pass audit, scale, determinism, Qdrant/Neo4j
  reconstruction, versioning, isolation, census, failure semantics,
  interrupt/resume) + `_failure_probe.py` subprocess probe.
- `eval/e3/gold/sample_table.json`: inspectable entity/fact decision
  table (16 accepted entities, 8 accepted facts, rejected-sample).

## Proof (all gates)

- model contract: pinned revision verified via sidecar manifest; mps
  device; tofu weights digest (3357a37e…); thresholds 0.5/0.4;
  /ready true.
- golden path: metacognition.md → query_ready in 3.1s (8/8 stages
  ok); replay already_exists + counts identical.
- double-pass audit: production = GLiNER entity pass + DETERMINISTIC
  LEXICAL evidence proposer; the GLiNER evidence pass exists only
  behind evidence_proposal_mode='hybrid' (default lexical) — the
  rejected hybrid experiment is NOT re-enabled.
- scale: 14 docs / 40.3s / 20.8 docs/min; 32 chunks; 8 facts.
- determinism: identical semantic hash across full wipe + re-ingest.
- Qdrant reconstruction 32→32 exact; Neo4j reconstruction 11→11
  exact.
- versioning: modified content → 2 versions under one locator; old
  content preserved; replay no-op.
- isolation: 0 cross-corpus scoped-identity collisions.
- census: GLOBAL 6 / CORPUS_SCOPED 5 / MENTION_ONLY 1; 8 facts
  (instance_of 3, owns 1, has_role 1, associated_with 3); 1 parked
  fact.
- failure semantics: GLiNER unreachable → StageFailed, attempt
  'failed', run reconciling — loud, no fallback, no silent
  query_ready.
- interrupt/resume: 6/6 runs converge after mid-pipeline resume.

## Recorded quality findings (ownership, not patched)

1. Low extraction yield on realistic prose (8 facts / 14 docs) —
   owned to GLiNER medium-v2.1 at frozen threshold 0.5 missing
   lowercase technical compounds (failure budget, distributed queue,
   dead-letter queue, landing URL) and to the lexical trigger
   inventory lacking academic/commerce verbs.
2. Wrong-edge examples: "Zero-Day Response Handbook instance_of
   vendor" (GLiNER proposed the document title as an entity; the
   compiler paired it across the sentence with surface_weak
   orientation). "red team owns identity team" (weak pairing).
   Ownership: GLiNER title-as-entity proposals + compiler
   surface-weak pairing acceptance. Recorded; precision-first rule
   remains "no edge over wrong edge" — these are catalogued cases
   for the next extraction qualification, not patched here.

## Rejected claims

- No other learned model anywhere (verified); no fallback path
  exists (dead-URL probe proves loud failure).
- No threshold tuning; no evidence-pass re-enablement.

## Open contract gaps

- Extraction-quality iteration (title-span exclusion, compound
  recall, surface-weak pairing gates) is a future qualified change.
