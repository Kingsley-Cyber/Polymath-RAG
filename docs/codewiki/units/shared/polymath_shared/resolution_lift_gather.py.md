# unit: shared/polymath_shared/resolution_lift_gather.py
anchor: shared/polymath_shared/resolution_lift_gather.py:1-177

## purpose
Turns a query's precision surfaces (§11: profile topics/terms, map `semantic_hooks`/`exact_identifiers`, atom terminology, heading paths, entity aliases) into ranked `LiftCandidate`s, top `k` (≤3), per FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §10–§12 — shared/polymath_shared/resolution_lift_gather.py:3-12 [DERIVED].
Gathering is split from ranking so the store reads can be faked in tests; `gather_lift_candidates` is pure over an injected `sources` object, `LiveLiftSources` implements the reads against Postgres + Qdrant — shared/polymath_shared/resolution_lift_gather.py:7-12 [DERIVED].
No hardcoded domain vocabulary: every candidate term comes from a corpus record — shared/polymath_shared/resolution_lift_gather.py:8-9 [DERIVED].
Sole known consumer: orchestrator/orchestrator/api/chat_retrieval.py (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `gather_lift_candidates` | def | (query, *, doc_ids: Sequence[str], corpus_id: str, sources, top_evidence_docs=(), query_exact_terms=(), k=3, corpus_doc_count=None, atom_kinds=None) -> list[LiftCandidate] | shared/polymath_shared/resolution_lift_gather.py:21-24 [DERIVED] | orchestrator/orchestrator/api/chat_retrieval.py (FACTS.importers) |
| `LiveLiftSources` | class | (conn, client, *, corpus_id, embedding_contract_id, map_contract=None, profile_contract=None, compute_df=False); methods: `__init__`, `profile_terms`, `map_terms`, `atom_terms`, `headings`, `aliases`, `doc_frequency` | shared/polymath_shared/resolution_lift_gather.py:80-92 [DERIVED] | — (injected as `sources`) |

## contracts

`gather_lift_candidates`
- in: `sources` must provide `profile_terms(doc)->(topics,terms)`, `map_terms(doc)->(hooks,ids)`, `atom_terms(doc,kinds)->[(kind,text)]`, `headings(doc)->[str]`, `aliases(corpus)->[(canonical,[alias,...])]`, `doc_frequency(term)->int|None` — shared/polymath_shared/resolution_lift_gather.py:26-28 [DERIVED]
- in: defaults `top_evidence_docs=()`, `query_exact_terms=()`, `k=3`, `corpus_doc_count=None`, `atom_kinds=None` — shared/polymath_shared/resolution_lift_gather.py:22-24 [DERIVED]
- out: `list[LiftCandidate]` ranked by `rank_lift_candidates(cands, query, query_exact_terms=..., k=k, corpus_doc_count=...)` — shared/polymath_shared/resolution_lift_gather.py:76-77 [DERIVED]
- pre: none beyond the six-method protocol; every `sources` call is individually exception-wrapped — shared/polymath_shared/resolution_lift_gather.py:40-43,48-51,56-60,61-65,67-74 [DERIVED]
- post: per-doc kinds `TERM`/`TOPIC`/`MAP_ID`/`MAP_HOOK`/`ATOM`/`HEADING` carry `doc_id` and `in_top_evidence=local`; corpus kinds `ENTITY` (canonical_name) and `ALIAS` carry `canonical=True` and no `doc_id` — shared/polymath_shared/resolution_lift_gather.py:29,45-63,68-72 [DERIVED]

`LiveLiftSources`
- in: `conn` (Postgres), `client` (Qdrant), `corpus_id`, `embedding_contract_id`; optional `map_contract=None`, `profile_contract=None`, `compute_df=False` — shared/polymath_shared/resolution_lift_gather.py:90-92 [DERIVED]
- out: `profile_terms` -> (topics, terms) from Qdrant payload `["topics", "terms"]`; `map_terms` -> (hooks, ids) from active `document_parent_maps` rows; `atom_terms` -> [(kind, text)]; `headings` -> order-preserving deduped strings; `aliases` -> [(canonical, [alias,...])]; `doc_frequency` -> int|None — shared/polymath_shared/resolution_lift_gather.py:110-117,122-129,131-134,140-145,150-154,159-176 [DERIVED]
- post: read-only; `_df_cache` memoizes only non-None DF results; `_alias_cache` computed at most once per instance — shared/polymath_shared/resolution_lift_gather.py:81,104-105,148,154,157,174-175 [DERIVED]

## effect surface

| store | object | operation | anchor |
|---|---|---|---|
| Postgres | `document_parent_maps` | SELECT `semantic_hooks, exact_identifiers` WHERE doc_id AND active (+ optional `AND map_contract=%s`) | shared/polymath_shared/resolution_lift_gather.py:122-124 [DERIVED] |
| Postgres | `chunks` | SELECT DISTINCT `heading_path` | shared/polymath_shared/resolution_lift_gather.py:137-139 [DERIVED] |
| Postgres | `concept_families` ⋈ `concept_aliases` | SELECT canonical_name + array_agg(alias), GROUP BY concept_id, canonical_name | shared/polymath_shared/resolution_lift_gather.py:150-153 [DERIVED] |
| Postgres | `chunks` + `documents` | SELECT count(DISTINCT doc_id) ... `text ILIKE %s` (pattern `f"%{t}%"`) | shared/polymath_shared/resolution_lift_gather.py:168-171 [DERIVED] |
| Qdrant | collection = `PJ.collection_name(embedding_contract_id)`, point = `PJ.point_id(doc_id)` | retrieve, `with_payload=["topics", "terms"]` | shared/polymath_shared/resolution_lift_gather.py:110-111 [DERIVED] |

- Writes: none — tables_written = [] (FACTS); "Read-only" — shared/polymath_shared/resolution_lift_gather.py:81 [DERIVED]
- Files / network / subprocess / env flags: none present in SOURCE.

## invariants
INVARIANT: returned candidate count ≤ k, default k = 3 — shared/polymath_shared/resolution_lift_gather.py:6,23,76-77 [DERIVED]
  fails-if: callers relying on "≤3" get unbounded lists if `rank_lift_candidates` stops honoring `k`.
INVARIANT: candidate kinds = {TERM, TOPIC, MAP_ID, MAP_HOOK, ATOM, HEADING} per doc, plus {ENTITY, ALIAS} corpus-level — shared/polymath_shared/resolution_lift_gather.py:45-63,68-72 [DERIVED]
  fails-if: kind-string-keyed scoring in `resolution_lift` sees unknown kinds.
INVARIANT: HEADING candidates get no `doc_frequency`; every other kind gets `doc_frequency=_df(t)` — shared/polymath_shared/resolution_lift_gather.py:63 vs 45-58,70-72 [DERIVED]
  fails-if: ranking that assumes DF present mis-scores headings.
INVARIANT: `compute_df=False` (default) ⇒ `doc_frequency(term)` returns None for every term — shared/polymath_shared/resolution_lift_gather.py:92,160-161 [DERIVED]
  fails-if: enabling DF by default makes the per-term ILIKE scan (:168-171) dominate query latency.
INVARIANT: `map_terms` reads only rows with `active` set — shared/polymath_shared/resolution_lift_gather.py:123-124 [DERIVED]
  fails-if: inactive/legacy hooks and identifiers leak into candidates.
INVARIANT: `aliases()` runs its SQL at most once per instance — shared/polymath_shared/resolution_lift_gather.py:148,154,157 [DERIVED]
  fails-if: vocabulary edits mid-instance are invisible; or removing memo floods Postgres.
INVARIANT: only non-None DF results are cached — shared/polymath_shared/resolution_lift_gather.py:174-175 [DERIVED]
  fails-if: a term whose ILIKE scan fails re-runs that scan on every candidate occurrence.

## determinism & idempotency
determinism: NONDETERMINISTIC (db — Postgres SELECTs shared/polymath_shared/resolution_lift_gather.py:122-124,137-139,150-153,168-171 and Qdrant retrieve shared/polymath_shared/resolution_lift_gather.py:110-111; output depends on live store contents) [DERIVED]
idempotency: SAFE (no writes; tables_written = [] per FACTS; "Read-only" shared/polymath_shared/resolution_lift_gather.py:81) [DERIVED]

## failure behaviour
All handlers are `except Exception` (9 sites, each `# noqa: BLE001`).

| anchor (FACTS.fallbacks) | handler | effect caller sees |
|---|---|---|
| shared/polymath_shared/resolution_lift_gather.py:35-36 | SWALLOWED: return None (`_df`) | candidate ranked with `doc_frequency=None` ("rarity falls back to mid") |
| shared/polymath_shared/resolution_lift_gather.py:42-43 | handled: assign (profile_terms) | no TERM/TOPIC from that doc |
| shared/polymath_shared/resolution_lift_gather.py:50-51 | handled: assign (map_terms) | no MAP_ID/MAP_HOOK from that doc |
| shared/polymath_shared/resolution_lift_gather.py:59-60 | SWALLOWED: pass (atom_terms) | no ATOM from that doc |
| shared/polymath_shared/resolution_lift_gather.py:64-65 | SWALLOWED: pass (headings) | no HEADING from that doc |
| shared/polymath_shared/resolution_lift_gather.py:73-74 | SWALLOWED: pass (aliases) | no ENTITY/ALIAS candidates |
| shared/polymath_shared/resolution_lift_gather.py:112-113 | SWALLOWED: return ([], []) (`LiveLiftSources.profile_terms`) | empty surfaces, no error |
| shared/polymath_shared/resolution_lift_gather.py:155-156 | handled: assign (`LiveLiftSources.aliases`) | `self._alias_cache = []` — empty vocabulary cached for the instance lifetime |
| shared/polymath_shared/resolution_lift_gather.py:172-173 | handled: assign (`LiveLiftSources.doc_frequency`) | `n = None`, not cached |

- `LiveLiftSources.map_terms`, `atom_terms`, `headings` have NO internal handler; DB errors propagate and are only caught by `gather_lift_candidates`' wrappers — shared/polymath_shared/resolution_lift_gather.py:119-145 vs 48-51,56-60,61-65 [DERIVED]
- No error codes raised in this file [DERIVED].

## dumb-code flags
- `profile_contract` accepted and stored but never read anywhere in the file — dead plumbing — shared/polymath_shared/resolution_lift_gather.py:91,98 [DERIVED]
- DF disabled by default; comment admits the on-the-fly ILIKE scan "is too slow for query time", GATED behind a nonexistent "persisted corpus vocabulary index" — shared/polymath_shared/resolution_lift_gather.py:99-103 [DERIVED]
- Failed DF lookups not cached ⇒ same failing term repeats the ILIKE scan each call — shared/polymath_shared/resolution_lift_gather.py:172-175 [DERIVED]
- Eight bare kind literals `"TERM"`, `"TOPIC"`, `"MAP_ID"`, `"MAP_HOOK"`, `"ATOM"`, `"HEADING"`, `"ENTITY"`, `"ALIAS"`, no enum — shared/polymath_shared/resolution_lift_gather.py:45-72 [DERIVED]
- `map_terms` SQL built by string concatenation with conditional `"AND map_contract=%s"` — shared/polymath_shared/resolution_lift_gather.py:120-124 [DERIVED]

## refactor notes
- Blast radius: sole importer is orchestrator/orchestrator/api/chat_retrieval.py (FACTS.importers); any signature/protocol change must update it [DERIVED from FACTS].
- The six-method `sources` protocol is duplicated knowledge: `LiveLiftSources` and any test fakes must stay in sync with the call sites — shared/polymath_shared/resolution_lift_gather.py:26-28,34,41,49,57,62,68 [DERIVED]
- Ranking semantics and the `k` cap live in `polymath_shared.resolution_lift.rank_lift_candidates` (imported :18, invoked :76-77) — score changes are out-of-file — shared/polymath_shared/resolution_lift_gather.py:18,76-77 [DERIVED]
- Qdrant point/collection naming delegated to `polymath_shared.document_profile.projection` (`PJ.point_id`, `PJ.collection_name`); atom reads to `document_profile.profile_atom.active_atoms` — shared/polymath_shared/resolution_lift_gather.py:108-111,132-133 [DERIVED]
- `_alias_cache` pins the alias vocabulary for the instance lifetime with no invalidation; owners must recreate instances to see vocabulary changes — shared/polymath_shared/resolution_lift_gather.py:148,154-157 [INFERRED: cache is per-instance and never reset in this file]

## VERIFY
```verify
grep -Fq 'def gather_lift_candidates(query: str, *, doc_ids' shared/polymath_shared/resolution_lift_gather.py
grep -Fq 'k: int = 3, corpus_doc_count: int | None = None' shared/polymath_shared/resolution_lift_gather.py
grep -Fq 'compute_df: bool = False' shared/polymath_shared/resolution_lift_gather.py
grep -Fq 'SELECT DISTINCT heading_path FROM chunks WHERE doc_id=%s AND heading_path IS NOT NULL' shared/polymath_shared/resolution_lift_gather.py
! grep -Fq 'INSERT INTO' shared/polymath_shared/resolution_lift_gather.py
test "$(grep -c -F 'noqa: BLE001' shared/polymath_shared/resolution_lift_gather.py)" -ge 9
grep -Fq 'LiftCandidate(t, "HEADING", doc_id=d, in_top_evidence=local)' shared/polymath_shared/resolution_lift_gather.py
test "$(grep -c -F 'profile_contract' shared/polymath_shared/resolution_lift_gather.py)" -eq 2
```
