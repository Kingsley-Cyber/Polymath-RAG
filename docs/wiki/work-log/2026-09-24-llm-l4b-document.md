---
change_id: LLM-BACKEND-L4B-DOCUMENT
owner: "@king"
date: 2026-09-24
status: complete
status_note: "The test corpus `l4-canary` stays in the fleet until the owner deletes it (the owner's step; the agent does not delete data)."
architecture_impact: "No code change: one test corpus through the live fleet (4 model calls) + records. Closes the roadmap's L4 slice with L4a (11.468)."
last_reviewed: 2026-09-24
---

# LLM-BACKEND L4b: one document through the fleet on the owned lanes; no shared books

## Contract
- `LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md` §3 row 5, second half: one profile ticket and one small pMAP document land
  only on their owning pairs; gap L-19 (no upload since 2026-09-17 shown to mint parent maps).
- The owner, 2026-09-24: "a, no shared books, push and continue":
  - (a) = a one-document test corpus, not a document in an existing corpus;
  - "no shared books" answers `CODE-RAG-IMPLEMENTATION-V1.md` §6 item 6: no reference book is shared across projects.

## Changes
- `docs/wiki/experiments/llm-backend-l4b-2026-09-24/manifest.yaml`: corpus `l4-canary`, one document
  (`eval/i3_5doc/corpus/01_harborpay_oauth_incident.md`, a small synthetic incident note).
- Ingested through the standard path: `scripts/ingest.py run --manifest …/manifest.yaml`.
- Records: gap L-19 CLOSED, C-26 CLOSED, new row L-23; roadmap row 5 DONE; `CODE-RAG-IMPLEMENTATION-V1.md` §6 item 6
  answered.

## Proof
- The document: `doc_270ded79fc…` in corpus `l4-canary`, run `run_5e40b22d…`, created 2026-09-25 04:32:55 UTC. Every
  stage `done` (intake → … → parent_summary).
- The ledger (`llm_provider_attempts`, 04:32–04:50 UTC): exactly one call per model stage, each HTTP 200 on its owner's
  lane:

  | stage | lane | model | key variable | tokens in / out |
  |---|---|---|---|---|
  | extract | gemini2 | gemini-3.1-flash-lite | GEMINI_API_KEY_2 | 1,419 / 681 |
  | doc_parent_map | map_groq1q | qwen/qwen3.8-27b | GROQ_API_KEY_1 (pMAP slot 1's own pair) | 552 / 36 |
  | doc_profile | profile_groq5 | openai/gpt-oss-120b | GROQ_API_KEY_5 (profile slot 5's own pair) | 942 / 969 |
  | parent_enrichment | openrouter3 | qwen/qwen3.7-flash | OPENROUTER_API_KEY_2 | 592 / 472 |

  - Each row carries its stage, function, lane, model and key variable name (never a value).
  - The profile and pMAP calls landed on their slots' own pairs, as L3 (11.467) assigns: slot N owns profile_groqN,
    map_groqN and map_groqNq.
- `document_status` (read-only, 2026-09-24):
  - pMAP: 1 parent eligible, 1 mapped, 0 excluded, 0 unresolved, 1 batch done, 1 HTTP dispatch, 0 limiter refusals,
    0 HTTP 429, coverage 100%, 1 projection point → **L-19 CLOSED**: a new upload mints parent maps;
  - profile: present, valid, quality 0.88, model `profile_groq5:openai/gpt-oss-120b`, projected.
- The corpus filter on every shared surface (READ, file:line at production `95d7832a`):
  - graph facts: `orchestrator/orchestrator/api/retrieve.py:610-641` (`_authorized_fact_ids`: `d.corpus_id = ANY(%s)`);
  - SEE ALSO / bridge atoms: `shared/polymath_shared/document_profile/profile_atom_projection.py:159-186`
    (`search_atoms`: `corpus_ids` required, inside the Qdrant filter, fail closed);
  - profiles: `shared/polymath_shared/document_profile/projection.py:40-49` (`profile_nominate`: `corpus_id` filter);
  - chunks: every lane's child search passes `corpus_id` in its filter.
  So a test corpus cannot leak into another corpus's answers.
- The slice note's other L4 items were recorded by L4a (11.468): Groq counts prompt + requested output against TPM (what
  L2 reserves); the one org that returned an OTPM 429 (groq_5, qwen) carries `otpm: 1000` in the registry, and every
  qwen lane caps output at 900.

## Rejected claims
- "Test L4b on a document of an existing corpus": the owner chose (a), a corpus of its own, so no live corpus changes.
- "A reference book must join two project corpora" (C-26): the owner's decision is that no book is shared across
  projects, so V1 needs no multi-corpus query and no cross-corpus reference.

## Open contract gaps
- None changed (no code). New confirmed gap L-23: the status page labels pMAP with the registry's first PMAP lane
  (`@cf/qwen/qwen3-30b-a3b-fp8` for this document) instead of the lane that served (`map_groq1q`),
  `shared/polymath_shared/document_status.py:212`. Display only.
- The test corpus stays until the owner deletes it.
