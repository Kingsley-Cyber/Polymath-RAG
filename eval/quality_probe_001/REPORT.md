# QUALITY-PROBE-001 — full-pipeline layer diagnostic (actual outputs)

Source: 02_technical_event_pipeline.md
(sha256 be5ddfe310d6bfde13e90517b3faca204c3325442d25f1a9523e481cd7ac4a5b),
one document, live stack: semantic_v2 chunks (t=0.65/w3, chunk-contract-v2)
→ GLiNER pass 1 (frozen) → spaCy syntax → rescue (all four stages) →
mentions → admission → candidates → compiler (pack 1.3.0 + frames) →
projections. Converged query_ready through CONTROL-PLANE-V2.

## Layer-by-layer (the actual transition record)

CHUNKS: 10 children + 3 parents. Heading isolated (heading_path =
["Designing a Restart-Safe Event Processing Pipeline"], zero "###" in
any chunk text). Exact offset roundtrip on all 10. Sentence boundaries
clean (27 sentences; zero heading/body fusion — the class that cost 4
I4 FNs is structurally gone). OBSERVATION: chunk [1155:2369] spans
three paragraphs (idempotency + projections + concurrency) — t0.65/w3
under-segments long multi-topic stretches of THIS document.

GLINER PASS 1: 42 durable mentions, raw labels preserved
(raw=Dataset→Document, raw=Model→Product mappings visible). Strong
technical phrases proposed as full spans: "deterministic stage
contracts" (0.730), "bounded leases" (0.797), "transactional claim
operations" (0.661), "graph databases" (0.822), "vector index",
"graph store", "workflow database", "projection worker",
"orchestration layer", "storage layer", "search indexes",
"transactional database" (0.502), "message broker". Never proposed:
"restart-safe event pipeline", "workflow authority", "idempotent
identities", "deterministic identifiers", "at-least-once delivery",
"outbox" as a bare concept (only "the outbox" 0.554).

SPACY: 123 noun chunks / 111 unique over 27 sentences — INCLUDING
every phrase GLiNER missed ("workflow authority", "idempotent
identities", "deterministic identifiers", "at-least-once delivery",
"exactly-once delivery", "restart-safe event pipeline", "the next
outbox event", "durable records"). The evidence layer is complete even
where the mention layer is not.

RESCUE: boundary 5 candidates / 0 accepted / 5 refused — GLiNER
returned ZERO predictions on every bare-NP re-query ("next outbox
event", "Two workers", "one worker", "losing worker", "same
document"), all under identity labels at the frozen 0.5. This is the
known frozen-threshold/vocabulary class, unchanged.

MENTIONS→ADMISSION: 42 mentions → 10 durable (8 CORPUS_SCOPED + 2
GLOBAL: "documents", "search indexes") + 32 MENTION_ONLY. Every
generic noun ("worker" ×7, "document", "database", "batch", "event",
"system", "pipeline", "verifier", "replay") held at MENTION_ONLY.

CANDIDATES→COMPILER: 7 audit entries, ALL rejected, each defensibly:
- worker --creation--> remote service: type_violation (Person→Technology) — correct
- The outbox --classification--> message broker ×2: scope_gate negated/speculative
  ("without making the message broker itself the source of truth") — correct
- graph databases / Search indexes --classification--> workflow database ×4:
  scope_gate conditional ("SHOULD be treated differently" — normative,
  not factual) — correct under the precision-first contract
The strongest assertible sentence ("A robust implementation uses
bounded leases, deterministic stage contracts, and transactional claim
operations") never produced a candidate — the pre-candidate filters
(type pre-check / trigger localization) are silent, an observability
gap recorded below.

FACTS: 0 accepted. GRAPH: 13 chunk/document nodes, 0 semantic edges.

RETRIEVAL (FAST, 5/5 answered from probe chunks):
- workflow authority/transactional db → rank-1 EXACT ([564:850])
- deterministic identifiers/replay → rank-1 EXACT ([1155:2369])
- vector/graph as derived projections → rank-1 contains the passage
- bounded leases/concurrency → rank-1 EXACT ([2370:2743])
- failure tests → evidence at rank-2 ([2857:3456]); rank-1 is the
  topically-adjacent opening paragraph. 4/5 exact rank-1.

## Five quality questions

1. WORTH REMEMBERING? YES at the evidence/mention layer: 14 of the
   ~18 expected technical phrases appear as mentions; the remaining
   ones all appear as spaCy noun chunks + retrievable text. Not
   "mostly worker/system/state" — generics exist but are quarantined.
2. BOUNDARIES? MOSTLY GOOD: "deterministic stage contracts",
   "transactional claim operations", "bounded leases" as full phrases.
   Weak edges: "the outbox" (determiner retained), "database" alone
   (from "a transactional database"), "correctness model"→Product
   (mis-typed but CORPUS_SCOPED).
3. SELECTIVE? EXTREMELY: 123 NPs > 42 mentions > 10 durable > 0 graph
   entities > 0 facts. If anything, over-abstinent at the fact layer
   for normative prose.
4. FACTS USEFUL? Nothing false was asserted; no edge spam. But 0 facts
   from a document with several assertible uses-relations means the
   fact layer added nothing here; trust preserved, utility unproven
   on this genre.
5. TEXT RAG LOST ANYTHING? NO. 5/5 questions return the right
   evidence; the graph abstained; the knowledge did not disappear.

## Engineering review

GOOD MISS: every zero-fact concept remains a mention and a retrievable
chunk (restart-safe pipeline design prose is normative; the predicate
pack lacks faithful predicates for most of it).
MILD BAD MISS: "workflow authority"/"idempotent identities"/"at-
least-once delivery" never became MENTIONS (GLiNER never proposed
them) — preserved only at the syntax/chunk layer.
GOOD REJECTION: "worker"/"system"/"pipeline" held MENTION_ONLY;
normative "should be treated differently" gated conditional;
negated source-of-truth clauses gated.
BAD PROMOTION: none observed ("documents"/"search indexes" GLOBAL is
borderline-generous but typed and corpus-useful).
GOOD/BAD FACT: none — zero facts.

## Verdict

The pipeline behaved like a careful-but-very-conservative reader:
rich, correctly-bounded, correctly-generic-quarantined memory at the
mention/evidence layer; total abstention at the fact layer on
normative prose; full text recall through the chunk layer. The
dominant real gap remains the frozen-vocabulary refusal class (rescue
0/5 accepted), now confirmed on fresh material. The candidate layer's
silent pre-filters are the observability gap to close next.

## Infrastructure findings surfaced BY the probe (honest record)

The probe required repeated manual intervention, each item a real
defect found and fixed: (1) claim starvation — LIMIT applied before
ticket gating in claim_ticket_events; (2) ticket events must carry the
original stage payload, not identity-only; (3) intake 'plan' unbound on
the semantic path; (4) uniform contract gating requires the entire
fleet (and control plane) to share the deployment env — including
workers that never touch chunks; (5) generation barrier blast radius —
one wedged corpus blocked promotion of every healthy corpus (now
per-corpus). Additionally, five long-lived processes (GLiNER, embedder,
reranker, spaCy sidecar, orchestrator) died silently during the
session and required manual restart — the supervisor-marks-but-does-
not-restart gap is now the top operational risk.
