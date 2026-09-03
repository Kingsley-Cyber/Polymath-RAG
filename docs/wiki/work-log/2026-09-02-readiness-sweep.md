---
change_id: READINESS-SWEEP-0902 + LLM-DIRECT-PRONOUN-GATE-V1
owner: governance
date: 2026-09-02
status: complete (final suite numbers appended below)
architecture_impact: llm-direct fact path gains the pronoun gate (entities + endpoints, counted); 13 live facts retired; two same-day regressions fixed; test hygiene
last_reviewed: 2026-09-02
---

# WORK LOG — "is Polymath bug free and 100% ready?"

## Contract
Owner (2026-09-02 evening): after the day's fixes, "is the polymath bug
free and 100% ready?" Answer with measurements, not adjectives: run the
full determinism suite, classify every failure, fix what is real, record
what is not.

## Changes (what the sweep found, and what was done about each)
The full suite reported 12 failures. Classification:
1. TWO REGRESSIONS FROM TODAY (fixed): the projection worker's new
   readiness gate assumed every embedder client has `wait_ready`
   (hermetic fakes do not) → `getattr` guard; the fail-fast breaker keyed
   on `self.base_url`, which `GlinerClient` never sets → `getattr` key.
2. ONE LIVE PRODUCTION DEFECT (fixed): `test_no_active_fact_has_a_pronoun_endpoint`
   — 13 ACCEPT facts written by the llm-direct path on 09-01/09-02 had
   unresolved closed-class pronoun endpoints ("adam ACTS_ON me", "me IS_A
   british luxury designer"). LLM-DIRECT-FACTS-V1 bypassed the entity-
   admission pronoun rule the GLiNER-era path enforced. Fix:
   `llm_direct.materialize` drops pronoun ENTITIES and any relation with a
   pronoun ENDPOINT, counting both in the stage artifact
   (`pronoun_entities_dropped`, `pronoun_endpoints_dropped`); the 13 live
   facts were retired (decision REJECT, qualifiers note
   `retired: unresolved_closed_class_pronoun`; rows and mentions kept —
   retirement is not deletion). Test: test_llm_direct_pronoun_gate.
3. TEST HYGIENE (fixed): the census tests run autocommit and left probe
   runs behind (`census_probe_rollback` reappeared 24 s into the suite —
   the same debris hand-deleted twice today) → purge on teardown;
   `test_embed_batching` pinned a literal 32 while the worker's measured
   optimum has been 16 since 2026-08-27 → derives from EMBED_BATCH.
4. PRE-EXISTING / STALE (chip-tracked, unchanged): killchain child-span
   gaps; llm_controller stale fake; sval doc01 ×3; syntax_readiness_v3 ×2
   (DB-state flake, pass on rerun); `test_retirement_preserved_raw_observations`
   expects `relation_candidates` rows that only the GLiREL-era writer
   produced (empty since llm_live, 2026-08-30); `test_evidence_truncation`
   flags one concept artifact of the AWS book whose 159 supporting chunks
   no longer exist — the 09-01 Phase-0 re-ingest re-chunked the book and
   compile_objects never superseded the old artifacts (cascade gap, not
   from today's deletes).

5. GRAPH-ELIGIBILITY-DECISION-V1 (found while retiring the 13): REL edges
   carry only predicate + fact_id, the GRAPH lane does not consult
   decisions, and the P9 reconciler keeps any edge whose fact row still
   exists — so the retired facts kept their 13 edges through a reconcile
   and stayed servable. `fact_eligible_sql` (the ONE predicate shared by
   projector, census and verify) now also requires `decision <> 'REJECT'`;
   QUALIFY stays eligible (P9 pin). Reconcile after the change: 0 edges
   carry any of the 96 REJECT facts (1,562 REL edges remain).
6. Graph/PG test debris noted, not touched: `fact_d2a_shared`,
   `fact_d2a_use`, `fact_d2b_use` (tests/integration/test_corpus_scoped_graph.py)
   are committed fixtures with live edges — owner call to purge.

## Proof
- Targeted reruns after the fixes: pronoun gate test green; pronoun
  eligibility gate green (0 active pronoun endpoints); embed batching,
  batched pass1, sidecar readiness gate, census module all green.
- FULL SUITE, final (post-fix code, 1,617 collected): pytest's counts line was not emitted in this environment; counted from the progress marks: 1597 passed, 9 failed, 11 skipped, 0 errors.
  9 failures, all classified above: evidence_truncation (re-ingest orphan
  artifact), retirement/relation_candidates (GLiREL-era table), killchain gaps,
  llm_controller stale fake, sval doc01 ×3, syntax_readiness_v3 ×2 (DB-state
  flake; pass on rerun). Zero failures attributable to today's changes.

## Rejected claims
- "Bug free / 100 % ready" — not a claim any evidence supports for a
  system this size; the honest statement is: every defect found today is
  fixed with a test and a live receipt, and the known remaining failures
  are listed above with their causes.
- Editing the retirement/relation_candidates test to pass — its premise
  (a GLiREL-era table) is the thing that is stale; changing the assertion
  without the owner deciding the table's future would hide that.

## Open contract gaps
- Pre-existing failures above (chip task_93a468e4) — owner decision on
  the llm-era semantics of the sval/killchain/relation_candidates pins.
- RE-INGEST should supersede concept_artifacts of the previous chunking.
- Graph edges of the 13 retired facts: the projector selects by fact row;
  the reconciler's REJECT handling should prune them on its next pass —
  verify on the next graph reconcile.
- launchd auto-boot: still an owner action (TCC).
