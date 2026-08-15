---
change_id: smoke-admission-e2e-pass
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none
---

# Live entity-admission E2E smoke gate rerun — PASS

## Contract

After D1 (806fe2a) and D2 (44b98fd), rerun the exact frozen
metacognition smoke document (sha256
`4ba7ee1675b4d58a6a8f69d1041dc0978dd36ea2e6a6da8a0e38e1cf140dbea5`)
through the full production stack without modifying the document or
tuning admission/extraction. Require query_ready, corpus-clean
queries, zero foreign citations, no legacy-hub activation, replay
PASS, Neo4j reconstruction PASS, determinism PASS, tests/guards
green.

## Results

- Original stuck run (`run_3f1febc…`, corpus
  `smoke-admission-2026-08-15`) converged to `query_ready` on the
  first census tick after D1 — no more parked-fact re-drive loop.
- Document identity is content-derived: re-ingesting identical bytes
  into a second corpus correctly produced no duplicate logical
  document (ADR-0001); the gate therefore ran against the original
  corpus, and the accidental empty second corpus was disposed.
- All six queries (5 content + vague "How does the system work?")
  corpus-clean: 0 citations, 0 foreign citations, graph_facts = 0
  for every query — the vague query gained no authority from legacy
  generic hubs. Retrieval lanes still return in-corpus child evidence
  (7 dense / 3-4 lexical children).
- Admission census (durable): GLOBAL=1 (Metacognition),
  MENTION_ONLY=2 (learner ×2 mentions, stable mention_ ids); parked
  facts = 2, both Postgres-authoritative, zero Neo4j leakage;
  no system/model/platform hub created by this document.
- Replay: POST /intake same corpus → `already_exists=True`, same
  run_id; counts before/after identical (1 run / 2 facts / 3
  entities); semantic artifact hash identical
  (`bb50600ccb56ba16208d…`).
- Neo4j reconstruction (sanctioned gate-2 sequence: delete corpus
  projection → verify clears receipts → census gap → projector →
  verify): exact equality against the Postgres-authoritative expected
  set — doc 1/1, chunks 7/7, admitted entity 1/1, eligible fact edges
  0/0 (parked excluded), canonical entity 1/1, membership 1/1,
  evidence links 2/2, mention leakage 0; run back to query_ready.
- Determinism: identical content identity + identical semantic
  hashes across the replay.

## Observations (recorded, not patched — out of scope)

- Census re-drive for project_neo4j is fact-receipt-triggered; a
  corpus whose facts are all parked (zero eligible facts) has no
  automatic census trigger for lost chunk nodes — the sanctioned
  gate-2 sequence (verify → census → schedule → project) handles it
  deterministically. Candidate future hardening, not a gate failure.
- Title-case "Metacognitive Monitoring" classifies GLOBAL while
  lowercase "metacognitive monitoring" classifies CORPUS_SCOPED
  (proper-name case signal) — known admission behavior, unchanged.

## Proof

- Unit/determinism/contracts: 0 failures. Integration: 0 failures
  (29 passed / 1 skipped). Guards: preflight / repo guard / wiki
  worm ok.
- Evidence: work logs 2026-08-15-d1-eligibility-receipt-predicate.md,
  2026-08-15-d2-corpus-scoped-graph.md, and this entry.

## Open contract gaps

- I1 manifest-driven bulk ingestion is now UNBLOCKED.
