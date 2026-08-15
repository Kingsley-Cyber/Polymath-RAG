---
owner: governance
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: accepted
---

# ADR 0012: Typed evidence support lanes (TEXT and GRAPH)

## Context

The live admission smoke gate exposed that the answer path treated
textual retrieval evidence as second-class: R3b synthesized answers
only from graph facts, and a corpus whose facts were all parked (or
sparse) abstained even when its chunks directly contained the answer.
The architectural constraint for the fix: textual evidence must be a
first-class, typed EvidenceBundle lane — never a special-case fallback
that dumps chunks at a generator when graph facts are missing.

## Decision

The EvidenceBundle (R3a) and answer synthesis (R3b) contracts become
v2 with two INDEPENDENT support lanes:

| Lane | Items | Support semantics |
|---|---|---|
| GRAPH | compiler facts, graph-expanded facts (kind=claim) | fact triple claims: every meaningful token must appear in supporting claim surfaces (unchanged) |
| TEXT | document summary, section summary, child chunk, lexical/dense retrieval evidence (kind=evidence) | verbatim passage claims: claim text must be a verbatim, case-insensitive substring of a supporting passage (fail-closed excerpting) |

- Either lane may support an answer independently; both combine when
  available. Graph evidence AUGMENTS textual retrieval and never gates
  it. Abstention only when both lanes are empty.
- Mixed-lane support for a single claim is rejected (fail-closed).
- The default proposer (deterministic-template-v2) emits one GRAPH
  claim per graph claim item and one TEXT passage claim per text item;
  text claims are excerpts cut from the passage itself (deterministic
  window around the query's rarest long token, word-boundary trimmed)
  so no fabricated text can survive validation.
- Renderer: graph sentences first, then cited passages
  (`Relevant passage: "..." [n]`). Citations reference bundle item ids
  with exact locators (chunk:<id>@<start>:<end>, doc:<doc_id>,
  section:<parent_chunk_id>).
- Contract bump: `answer/evidence_bundle/v2`,
  `answer/chat_response/v2` (schemas under `contracts/answer/v2/`).

## Consequences

- Frozen tests that locked graph-gating were updated deliberately
  (evidence-only abstention and evidence-only claim rejection now
  assert the TEXT lane's independent support); contract validation
  suites point at v2 schemas.
- The smoke corpus now answers all six gate queries with cited,
  in-corpus passages (0 foreign citations); the vague "system" query
  gains no graph authority.
- G3 reranking, HIGH_MEDIUM graph policy, hop1, and the graph lane's
  grounding rules are unchanged.
