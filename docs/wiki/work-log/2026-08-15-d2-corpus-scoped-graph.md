---
change_id: d2-corpus-scoped-graph
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (defect fix on ADR-0011 boundary)
---

# D2: corpus-authorized graph expansion

## Contract

Fix smoke-gate defect D2 (work log
2026-08-15-smoke-admission-e2e-fail.md): graph expansion must be
corpus-authorized. GLOBAL entity identity is untouched; seed
authorization and traversed facts are restricted to the active
corpus/evidence scope. The canonical directed bidirectional UNION
must never return facts supported exclusively by another corpus.
Seeds resolve from entities attached to retrieved in-scope evidence,
not unrestricted raw-query surface matching. SPO orientation,
fact_id dedupe, hop1, HIGH_MEDIUM allowlist, 8-seed / 20-fact caps,
and G3 are preserved.

## Changes

- `orchestrator/orchestrator/api/retrieve.py`:
  - `_corpus_seed_ids`: seeds are entities attached to facts evidenced
    in the active corpus (MENTION_ONLY excluded; GLOBAL identity
    unchanged). Preference: entities attached to the RETRIEVED
    evidence chunks first, then the corpus pool; ties broken by
    entity_id (deterministic). Surface matching semantics
    (case-insensitive containment, both directions) preserved but
    applied to the Postgres pool, never a raw shared-graph MATCH.
    Cap 8.
  - `_authorized_fact_ids`: a fact is authorized iff supported by
    evidence in the active corpus. Facts supported exclusively by
    another corpus are excluded. Facts with NO evidence anywhere are
    intentionally kept so assembly fails loudly (frozen R3a
    acceptance), never silently hidden.
  - `_neo4j_expand(surfaces, corpus_id=None, preferred_chunk_ids=None)`:
    seed-resolution + the same directed bidirectional CALL () UNION
    (dedupe by fact_id, ORDER BY fact_id, LIMIT 20, HIGH_MEDIUM),
    then the authorization filter. Cross-corpus route
    (corpus_id=None) keeps prior behavior.
  - Call sites in `retrieve.py`, `chat.py`, `evidence.py` pass
    corpus_id + retrieved chunk ids.
- Tests: `tests/integration/test_corpus_scoped_graph.py` — foreign
  generic hub surface yields nothing under the active corpus; shared
  GLOBAL entity surfaces only its active-corpus facts; orientation
  preserved; cross-corpus route still spans corpora.

## Proof

- Integration suites green (29 passed / 1 skipped) including the
  frozen R3a evidence-bundle loud-failure gate, chat E2E, and the G1
  cross-domain routing trace.
- The frozen evidence-bundle test that previously saw 6 claims from a
  1-claim corpus now sees exactly its own corpus's claim.

## Rejected claims

- No seed-eligibility policy change (G4.2 stays rejected); no
  traversal changes beyond authorization; no identity changes.

## Open contract gaps

- None for this defect. Smoke-gate rerun is the remaining proof.
