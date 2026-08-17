---
owner: worker
last_reviewed: 2026-08-16
last_touched: 2026-08-16
status: recorded
---

# Experiment 0006: Extraction diagnostic deep-dive (evidence/architecture analysis)

Gate: documentation-only commit (no behavior change). Evidence base:
QUALITY-PROBE-001/002, I4R staged measurements (A–D + combined), frozen
I4, SEMANTIC-CHUNKING-V2 qualification + I4 regression, vocabulary
probes (experiment 0005), 476 extraction-observability-v1 trace events
across two traced runs. Epistemic discipline: every claim below is
tagged MEASURED FACT / INTERPRETATION / PROPOSED NEXT LEVER.

## 1. Where the loss actually sits

MEASURED FACT (QUALITY-PROBE-001 funnel): 123 spaCy noun chunks →
42 GLiNER mentions → 10 durable entities → 7 relation candidates →
0 accepted facts; text RAG preserved 5/5 questions (4/5 exact rank-1).

MEASURED FACT (QUALITY-PROBE-002, FULL trace): for the sentence "A
robust implementation uses bounded leases, deterministic stage
contracts, and transactional claim operations": trigger `uses` fired;
binding reported left_candidates=0, right_candidates=1; first loss =
argument_binding / SUBJECT_ENDPOINT_UNAVAILABLE. "robust
implementation" was proposed by GLiNER as Technology (0.773) and
admitted CORPUS_SCOPED; no uses-signature accepts a Technology subject
(subject_core = Person/Organization/Method/Process/Product).
"deterministic stage contracts" → Document (0.730); "transactional
claim operations" → Process (0.661); uses.object_core excludes both
Document and Process; uses.subject_core INCLUDES Process (measured
signature asymmetry, recorded for post-vocabulary inspection).

INTERPRETATION: discovery is not currently the dominant observed
bottleneck. The dominant observed loss is the chain
span → raw GLiNER label → canonical type → predicate slot
compatibility. (Precise wording, per governance: current observed
losses are dominated by vocabulary/type alignment under the frozen
model/query policy — future vocabulary/context changes may reclassify
what is currently counted as a discovery miss.)

## 2. Vocabulary sensitivity — three independent evidence sources

MEASURED FACT: (a) Crestline alias probe (experiment 0005):
"Crestline Automation" bare-NP query under ["Organization"] returns
zero predictions; under ["Company"] returns the full span at 0.821 —
same model, same frozen threshold, only the label string differs.
(b) Rescue refusal measurements: 5/5 refused on QUALITY-PROBE-001,
13/15 refused on frozen I4, all with raw_predictions=[] (GLiNER
returns nothing under identity labels at 0.5). (c) QUALITY-PROBE
typing behavior: word-association typings ("contracts"→Document,
"operations"→Process, "implementation"→Technology) on otherwise
correct spans.

INTERPRETATION: the label vocabulary, not the span detector, is the
strongest observed lever.

## 3. Semantic chunking: structurally superior, semantically behavior-changing

MEASURED FACT (CHUNKING-V2-QUALIFICATION, dev + sealed): semantic_v2
required-break recall 1.0 vs legacy 0.0; legacy shows 3 heading
contaminations, 6 cross-section chunks, and 7 offset failures (its
space-joined chunk text was never an exact source substring);
semantic_v2: zero hard-boundary violations, 100% offset roundtrip,
5-run determinism at every parameter point.

MEASURED FACT (frozen-I4 regression, chunking isolated — all else the
I4R-D configuration): TP 12→14, FP 5→11, FN 14→12, P .706→.560,
R .462→.538, envelope 7/8→6/8, must-not 18/18.

DECISION (per promotion bar): semantic_v2 remains UNPROMOTED; default
stays legacy_v1.

INTERPRETATION: the recall gain matches the header-merged FN class
recovering (the structural fix works). The precision regression is
currently attributed to an evidence-backed hypothesis of context
starvation / genericized endpoints — NOT yet a proven final causal
mechanism. Supporting observations: new FPs are "the company employs
three new instructors" (anaphor whose antecedent sits in the preceding
chunk) and "nimbus cloud uses container platform" (genericized object
where the specific "Kubernetes" lies near a boundary GLiNER no longer
sees).

## 4. Architectural distinction

STORAGE UNIT != MODEL CONTEXT WINDOW (analysis, not yet qualified):
semantic chunks may remain the provenance/storage unit while GLiNER
may later receive a versioned bounded context envelope (preceding
semantic context + heading/section metadata + optional small next
context), with only focal-span predictions retained and offsets mapped
back to focal source coordinates. Chunk identity, replay, and
exact-evidence provenance are unaffected by construction (envelope is
a pure function of document structure, pinned into the extraction
contract hash).

STATUS: the semantic-v2 regression produces an evidence-backed
context-starvation hypothesis that requires an independently frozen
qualification gate (EXTRACTION-CONTEXT-V1). It is NOT proven.

## 5. Ranked experimental sequence (frozen plan)

1. GLINER-QUERY-VOCAB-v2 (concrete/descriptive/leaf labels; threshold
   stays 0.50; versioned PROVIDER_ALIASES data through the named gate)
2. re-run quality probe / traces
3. EXTRACTION-CONTEXT-V1 (semantic chunk authoritative; GLiNER
   receives bounded surrounding context) — measure independently
4. re-run quality probe + frozen I4
5. inspect observability waterfall
6. predicate-signature changes ONLY if correctly typed endpoints are
   still rejected (e.g. the uses subject/object Process asymmetry)
7. combined I4 → bars → freeze extraction → I5 sealed

## 6. Lane separation

CP2.1 automatic supervision (detect death → restart → health check →
re-register → resume tickets) remains a separate operational lane and
must not be mixed with extraction-quality experiments. Evidence for
its need: five long-lived processes died silently during the 2026-08-16
session (GLiNER, embedder, reranker, spaCy sidecar, orchestrator) and
required manual restart.

## 7. Observability as the required diagnostic mechanism

EXTRACTION-OBSERVABILITY-V1 is now required for future extraction
gates. Future extraction reports must include: funnel, first-loss
distribution, rejection waterfall, TP/FP/FN trace attribution, and
unexplained outcomes — target: unexplained outcomes = 0 (discovery
miss surfaces carry GLINER_NO_PROPOSAL by construction, which counts
as explained).
