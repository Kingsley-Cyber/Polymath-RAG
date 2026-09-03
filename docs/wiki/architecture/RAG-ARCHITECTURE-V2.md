---
change_id: RAG-ARCHITECTURE-V2-CORPUS-MAPPING-LAYER
owner: governance
date: 2026-08-29
status: distilled-reference
architecture_impact: documentation of live architecture
last_reviewed: 2026-08-29
---

# RAG ARCHITECTURE V2 — the corpus mapping layer (distilled)

> This is the distilled architecture — how I understand the system's
> reasons and purpose after the 2026-08-29 migration. The authoritative,
> detailed, editable reference is
> `/Users/king/Downloads/polymath-v4-local-migration-plan.md` (rev 4).
> When this page and the plan disagree on detail, the plan wins; when the
> plan disagrees with the live checkout, the checkout wins (AGENTS.md
> resolution order).

## The one-sentence system

**Summaries route, vocabulary translates, source chunks prove** — three
separate subsystems joined by document/parent/chunk IDs, all fed by ONE
extraction pass that generates both the knowledge and the routing signals.

## Why the architecture is shaped this way

1. **Extraction is the only generator.** The LLM reads evidence
   neighborhoods once and emits everything: entities, attested relation
   proposals, and the routing digest. Nothing downstream calls a model
   again. One pass = one cost = one provenance chain.
2. **The model proposes; Python validates.** Every entity surface and
   relation quote must be a verbatim substring of real source text
   (`gate.py` refuses anything unattested). The model never computes
   offsets, never assigns canonical IDs, never writes Neo4j. The safety
   guarantee is *refusing unattested output*, not trusting the model.
3. **Deterministic code keeps authority.** Identity allocation, Harbor
   admission, E1–E7 entity gates, the predicate compiler (trigger
   allowlist), and F1–F8 fact gates are frozen. An LLM proposal is
   *evidence entering* that machinery — never a bypass of it.
4. **The two-lane memory discipline.** Qwen3.5-4B (2.83 GB, local) runs
   the volume pass; `qwen3.5:397b-cloud` (0 GB local) is the quality lane
   for flagged work. Two *local* model windows are never concurrent on
   32 GB; the cloud lane is remote and exempt.

## The corpus mapping layer (owner directive, 2026-08-29)

The mapping layer answers "WHERE should retrieval look?" — and it is
compiled at the **parent-chunk level**, not the document level:

```
parent summary (COMPILED — LLM digest per evidence neighborhood:
                central_claim / main_mechanism / retrieval_uses)
        ↑ routes breadth
child chunks (verbatim source — the evidence, never a summary)
```

- Each LLM extraction item **is** the parent's compiled summary input: the
  digest rides in the same response as the entities/relations — zero
  extra model calls.
- Document-level and corpus-level routing cards remain **deterministic**
  (built from settled facts + entities + child provenance). They are
  embedded pointers, explicitly NOT answer evidence.
- Parent-level compilation is what makes retrieval dual-level: query
  first matches a parent's compact digest (breadth), then descends into
  that parent's children for grounding (depth). This resolves the classic
  chunk-size tradeoff without a second index or a second pipeline —
  hierarchy lives in metadata (`level`, `doc_id`, `parent_id`), one
  store, one search, best level wins, and grounding always resolves back
  to child chunks.

## Lane routing and the 300 KB rule

| source size | lane | model | enforcement |
|---|---|---|---|
| ≤ 300,000 B | local | Qwen3.5-4B MLX 4bit (`:8755`, locked gen config) | cloud selection AND dispatch both refuse, fail-closed |
| > 300,000 B | local *or* cloud (permission, not mandate) | `qwen3.5:397b-cloud` via daemon proxy | dispatch re-checks the threshold immediately before network I/O |

The rule is twice-enforced (`policy.select_lane` at selection,
`require_cloud_eligible` inside the transport) because the owner's
constraint is about *what may leave the machine*, and only a check at the
socket boundary can prove it.

## Entity identity: smart dedup, deletion-safe

- Corpus-scoped identity: the same surface in two corpora stays distinct.
- Dedup merge ladder: exact normalized name → alias/surface intersection
  → embedding-cluster (80–90 band) → keep separate. A merge must *prove*
  it is the same entity; near-misses are recorded, never silently merged.
- Every entity carries `source_document_ids` / `source_parent_ids` /
  `source_chunk_ids`. **Deleting a document only removes its mentions** —
  an entity survives wherever it has other sources, and its provenance
  arrays shrink honestly. Nothing is "owned" by one document.

## What the extraction contract guarantees

`polymath-extraction-v1` (see `contracts/extraction/` and
`shared/polymath_shared/llm_extraction/contract.py`): open-vocabulary
entity types (routed through the frozen query policy, unknown types fall
through to a documented fallback with the raw label preserved), verbatim
quotes everywhere, hard-capped lean output (the speed lever is *stopping*,
which the locked `repetition_penalty=1.15` config achieved: 0%
degeneration, self-terminating ~600-token outputs), and a routing digest
per neighborhood.

## Extraction canon: LLM-direct (ADR-0017, 2026-09-03)

`llm_live` is the default and only canonical extraction provider
(`extractor_version = llm-direct-v1`); the LLM gate
(`llm_extraction/gate.py`) is the sole authority and `llm_direct.materialize`
is the only fact writer. A fact is durable knowledge iff its QUOTE is
attested verbatim in the document; endpoint attestation is a recorded
LEVEL — quote › anchor › neighborhood › document › abstract (every content
token present in the anchor chunk) — never a veto. Junk surfaces,
unattested quotes and interrogatives remain hard rejections. The open
vocabulary (`entities.raw_types`, `provenance.predicate_raw`) is projected
to the graph and displayed; core types and the predicate enum are the
INDEX vocabulary. Replay is graded from the stored raw LLM responses
(`extraction_call_receipts`), retrieval from gold questions — never from
the interpreter view or fact-tuple self-consistency. Plan of record:
`docs/wiki/plans/LLM-DIRECT-CANON-PLAN.md`.

## GLiNER + spaCy: history

The span-tagger path (`extraction_provider=gliner`, spaCy syntax-evidence-v1,
sentence-slice manifest, rule-pack replay) stays selectable for forensics
and is never enforced by a gate, fence or test. Measured justification for
the move: GLiNER's own probe produced 4 candidates / 0 facts on clean
technical prose while the LLM lanes produce hundreds of attested proposals
per book; under the tagger's locality rule 54 % of correct LLM relations
were being rejected (2026-09-03).

## Provenance and recoverability

Every LLM observation lands in the append-only raw ledger
(`raw_entity_proposals` / `raw_predicate_evidence`) with a full provider
contract (lane, model, revision, contract id) — provenance is queryable
per span, per call, per generation. Re-ingestion is a *generation bump*
on the extract stage: old facts remain recoverable by
`extractor_version`; nothing is deleted to make room for the new.
