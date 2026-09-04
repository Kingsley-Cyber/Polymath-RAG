---
change_id: CORPUS-PLAN-V1 + CAPABILITIES-V1
owner: governance
date: 2026-09-03
status: DONE (parity tests green; live-probed after fleet restart)
architecture_impact: Polymath owns the research reformulation plan (`POST /retrieve/plan`) and advertises its contracts (`GET /capabilities`); MCP gains `capabilities`, `compile_plan`, `retrieve_evidence`. Retrieval ranking untouched. Consumers switch on contracts, never on the backend name.
last_reviewed: 2026-09-03
---

# WORK LOG — CORPUS-PLAN-V1 + CAPABILITIES-V1: Polymath becomes the agent layer TRAIL OS can detect

Owner (2026-09-03): "make this polymath native while allowing the skill to
also work in any new versions or work in others … make it aware so it knows
its polymath and allow polymath to own certain things … test with a control
to see before and after."

## Contract

1. `GET /capabilities` → `{backend: "polymath", version: <git short sha>,
   api: "2026-09-03", contracts: {retrieve-evidence-rows: "v1", corpus-plan:
   "v1", explore: true, typed-rows: [], field-evidence-corpus: null},
   endpoints, mcp_tools}`. Additive only: keys are added or versioned up,
   never removed.
2. `POST /retrieve/plan` `{signal, corpus_id | corpus_ids, limit=24,
   explore=true, communities=[]}` → `{plan: [{id, kind, query, why}],
   plan_contract: "corpus-plan-v1", evidence_rows: [... with query_ids],
   evidence_contract: "retrieve-evidence-rows-v1", per_query, errors}`.
   The compiler is a byte-for-byte port of TRAIL OS `python/corpus_queries.py`
   (same sha256 ids); `contracts/retrieve/v1/corpus_plan_fixture.json` pins
   parity and is checked in BOTH repos. Rows are merged by id across
   reformulations; a row found by three reformulations is one row with three
   query ids.
3. Frozen sample response `contracts/retrieve/v1/evidence_rows_sample.json`
   (chunk, chunk, document, attested graph_fact) — validated against the row
   schema here, consumed by TRAIL's adapter test there.
4. MCP: `capabilities()`, `compile_plan(signal, corpus_id, limit, explore,
   communities)`, `retrieve_evidence(query, corpus_id, limit, explore)`.

## Changes

- `orchestrator/orchestrator/api/corpus_plan.py` (NEW): compiler port + `/retrieve/plan`.
- `orchestrator/orchestrator/api/capabilities.py` (NEW): `/capabilities`.
- `orchestrator/orchestrator/main.py`: routers registered.
- `orchestrator/orchestrator/mcp_server.py`: three tools.
- `contracts/retrieve/v1/{corpus_plan_fixture,evidence_rows_sample}.json` (NEW, shared).
- `tests/determinism/test_corpus_plan.py` (parity, determinism, padding, sample-vs-schema),
  `tests/integration/test_retrieve_plan_capabilities.py` (live; skips when down).

## Proof

- Parity: Polymath `compile_plan(signal)` == TRAIL fixture ids/kinds/queries (5 queries).
- Live probe after restart (fleet 2026-09-03, main f7083ea): `GET /capabilities` → backend polymath, contracts
  retrieve-evidence-rows v1 / corpus-plan v1 / explore true / typed-rows [] / field-evidence-corpus null.
  `POST /retrieve/plan` on mark-builds-brands-v1 with the purple-ocean signal: 5 reformulations
  (seed, tension, communities, invariant, contrast; ids identical to TRAIL's local plan), 50 merged rows
  (35 chunk, 6 document, 9 attested graph_fact), 22 rows found by more than one reformulation, 0 errors, 58 s.
- `pytest tests/integration/test_retrieve_plan_capabilities.py tests/determinism/test_corpus_plan.py` → 6 passed live.
- Consumer: TRAIL OS v1.4.0 probes `/capabilities`, uses `/retrieve/plan` in
  native mode, records `corpus_backend {mode, version, plan_source,
  plan_parity}` in the run state; `--generic` forces the docs/18 path as the
  control arm. Both paths are exercised against a stub backend in its harness.

## Rejected claims

- "Switch on the backend name" — rejected: a consumer switches on contracts,
  so a file corpus or an older Polymath keeps working and a newer Polymath is
  adopted without a code change.
- "Move the whole research controller into Polymath" — rejected (owner
  discussion 2026-09-03): retrieval, extraction and memory are Polymath's;
  evidence laws, allocation and the product portfolio are TRAIL's.

## Open contract gaps

- `typed-rows` is advertised empty: extraction does not yet emit
  friction/behavior/workaround/purchase-language claims (step 4 of the plan).
- `field-evidence-corpus` is null: the ledger-ingest script (step 3) is not built.
- `/retrieve/plan` runs reformulations sequentially; 5 queries × 2 corpora took
  ~90 s through the adapter — acceptable for a research lane, not for chat.


## Addendum — CHAT-EVIDENCE-ROWS-V1 (2026-09-03 late)

Owner: "for this workflow i want my full power rag system to be used for my
agent ideation." The plan endpoint and EXPLORE view are retrieval; the full
answer path is `/chat` (hybrid retrieval, rerank, graph + latent lanes,
answer admission, synthesis with citations). `/chat` now takes
`evidence: true` and returns, next to `answer / citations / claims / meta`,
the same chunks, documents and facts as `evidence_rows` in the
RETRIEVE-EVIDENCE-ROWS-V1 shape — built from the answer's own bundle, never
a second retrieval. `/capabilities.chat-evidence = v1`; MCP `ask(...,
evidence=True)`. Abstentions (`meta.abstained`, `uncovered_query_terms`)
are returned as-is: an ideation question the corpus cannot ground is a
finding, and the rows still show what was retrieved.

Corpus naming: ids stay immutable identity; `GET /corpora` carries the
display `name`; `PATCH /corpora/{id}` renames; `ingest_field_evidence.py
--corpus-name` reuses a corpus by name or mints `c_<hash>` and names it.
Consumers resolve names → ids through the listing.

Probe receipts (live, HYBRID + latent): field-evidence-v1 ideation question
→ abstained (uncovered terms frictions/organizers/workarounds; 21 claims
withheld); mark-builds-brands-v1 "what makes an ugly landing page convert"
→ supported, 10 citations, 6 s; ecom-meta-v1 → supported, 21 citations, 7 s.
Note for a later slice: `citations[].human_locators` still print a
filesystem path for transcripts; the evidence rows do not.
