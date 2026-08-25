---
change_id: RETRIEVAL-CONTRACT-DOCS-V1
owner: governance
date: 2026-08-25
status: implemented
architecture_impact: none (documentation of actual behavior)
---

# RETRIEVAL CONTRACT AUDITS — CHUNK HIERARCHY + STORAGE (2026-08-25)

## Contract

docs/contracts/RETRIEVAL-CHUNK-HIERARCHY-V1.md and
RETRIEVAL-STORAGE-CONTRACT-V1.md document ACTUAL production behavior
(audited from code + live stores at 9331f9a), per charter Stage B/C.
No runtime behavior changed in this slice.

## Changes

1. Chunk-hierarchy audit: legacy_v1 packing (1200-char target, fanout
   4, sentence-aligned, no overlap, headings via layout evidence,
   content-addressed ids, parent text = two-level centroid summary),
   frozen params pinned by intake contract hash.
2. Storage audit: Postgres authoritative tables enumerated; Qdrant
   contracts/payloads/lanes audited against the LIVE server (153
   collections; BOTH hash-embed-v1 and neural-embed-v1 in use; default
   is hash — flagged GAP G1); lexical layer measured as Python
   term-overlap with NO inverted index (GAP G4); Neo4j rules restated;
   GRAPH_HOPS=2 vs charter hop1 flagged.

## Proof

- Code paths cited in both docs (chunker.py, intake_worker.py,
  summarizer.py, project_qdrant_worker.py, embedding_contracts.py,
  retrieval.py).
- Live Qdrant collection listing (153) + contract-id resolution run
  against the real server during the audit.
- No code modified ⇒ existing test suite state unchanged (38/38 focused
  core green earlier this session).

## Rejected claims

- NOT claiming semantic quality for hash-embedded corpora; GAP G1 says
  the opposite and must drive an explicit contract cutover decision.
- NOT freezing BM25 behavior as acceptable; G4 records it as a
  structural gap pending benchmark measurements.

## Open contract gaps

G1 mixed embedding contracts across corpora · G2 missing charter
metadata fields in point payloads · G3 concept alias fields · G4 no
lexical index · GRAPH hop2-vs-hop1 policy unmeasured.
