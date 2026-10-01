# unit: shared/polymath_shared/vocabulary_mapping.py
anchor: shared/polymath_shared/vocabulary_mapping.py:1-241

## purpose
SUMMARY RUNTIME D5 vocabulary mapping worker: groups concept terms from parent summaries into families (canonical + aliases) via support overlap only, gates them, and persists them to Postgres — shared/polymath_shared/vocabulary_mapping.py:1-5 [DERIVED]. It bridges how humans ask questions to how the corpus describes knowledge; it never creates knowledge and never touches entity identity — shared/polymath_shared/vocabulary_mapping.py:2-5 [DERIVED]. Sole known importer: `workers/workers/summary_worker_impl.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `run_vocabulary_ticket` | def | `(conn, *, ticket_id, corpus_id, input_hash, contract_version, worker_id, families) -> dict` | :178-241 | workers/workers/summary_worker_impl.py (module-level importer) |
| `build_concept_families` | def | `(*, corpus_id, parent_summaries, document_summaries, accepted_concepts) -> dict` | :69-154 | workers/workers/summary_worker_impl.py (module-level importer) |
| `admit_family` | def | `(family, *, corpus_id) -> tuple[bool, str]` | :165-175 | internal (called at :197) |
| `MissingSupportIdentity` | class | subclass of `ValueError` | :31-39 | — (raised at :61-65) |
| `_support_identity` | def | `(payload, row) -> str` | :42-66 | internal |
| `_pick_canonical` | def | `(surfaces, members) -> str` | :157-162 | internal |
| `_norm` | def | `(term) -> str` | :27-28 | internal |

## contracts

### build_concept_families
- in: `parent_summaries` rows with `payload` (or bare row) containing `concepts` list plus `support_id`/`parent_id` — :81-83, :58-59 [DERIVED]
- in: `document_summaries` rows with `payload.major_concepts` plus `document_id` or `artifact_id` — :93-95 [DERIVED]
- pre: every parent row carries `support_id` or `parent_id`, else `MissingSupportIdentity` — :60-65 [DERIVED]
- out: `{"contract": "vocabulary-mapping-v1", "corpus_id": corpus_id, "min_supporting_summaries": 2, "families": [...]}` — :151-154 [DERIVED]
- out family shape: `"contract": "concept-family-v1"`, `canonical_name`, `aliases`, `supporting_summaries`, `independent_support_count` — :138-145 [DERIVED]
- post: every returned family has `independent_support_count >= 2` — :149-150 [DERIVED]
- post: document-summary ids stored prefixed `"derived:"` and excluded from `independent_support_count` — :94, :136-137 [DERIVED]

### admit_family
- out: exactly one of `(False, "R1_corpus_isolation")`, `(False, "R2_no_summary_support")`, `(False, "R2_no_canonical")`, `(True, "admitted")` — :169-175 [DERIVED]
- pre: `family` dict with `corpus_id`, `supporting_summaries`, `canonical_name` keys — :169-173 [DERIVED]
- note: code gate is `< 1` supporting summaries, not 2 — :171 [DERIVED]

### run_vocabulary_ticket
- in: `families` = `build_concept_families` output shape (consumed via `families.get("families", [])`) — :196 [DERIVED]
- out: `{"status": "SKIPPED_NOT_CLAIMABLE"}` when `_claim` fails — :183-184 [DERIVED]
- out: `{"status": "EXISTING", "artifact_id": existing[0]}` when `summary_artifacts` has a row with matching `input_hash` — :185-192 [DERIVED]
- out: `{"status": "COMPLETE", "artifact_id": ..., "admitted_count": ..., "rejected_count": ...}` — :239-241 [DERIVED]
- post: `summary_jobs.state='COMPLETE'`, `completed_at=now()` on both EXISTING and COMPLETE paths — :189-191, :237-238 [DERIVED]
- ids: `artifact_id = "voc_" + content_hash({"in": input_hash})[:32]`; `concept_id = "cfm_" + content_hash({"c": corpus_id, "n": fam["canonical_name"]})[:32]` — :195, :203-204 [DERIVED]

## effect surface
- Postgres read: `summary_artifacts` (`SELECT artifact_id ... WHERE input_hash=%s`) — :185-187 [DERIVED]
- Postgres writes: `concept_families` — :205-211; `summary_artifacts` (stage `'VOCABULARY_MAPPING'`) — :212-221; `concept_support` (`artifact_type='vocabulary_mapping'`) — :222-226; `concept_aliases` — :227-231; `summary_jobs` (UPDATE) — :189-191, :237-238 [DERIVED]
- Cross-module calls: `polymath_shared.corpus_mapping._claim` — :24, :183; `polymath_shared.identity.content_hash` — :23, :195, :203 [DERIVED]
- No files, Qdrant, network, subprocess, or env flags visible; FACTS.constants = []

## invariants
INVARIANT: returned family `independent_support_count` >= 2 — :149-150 [DERIVED]
  fails-if: single-mention concepts admit; the vocabulary guard is void.
INVARIANT: document summaries contribute 0 entries to `summaries` support (surfaces only) — :92-98 [DERIVED]
  fails-if: one document creates parent + own derivative = fake support of 2 — :89-91.
INVARIANT: support identity is `support_id` or `parent_id`, never `summary_id` — :54-59 [DERIVED]
  fails-if: parents with two summary rows self-corroborate; measured 3,016 rows cover only 1,775 distinct parent_ids on cysa-study-v1 — :46-52.
INVARIANT: two terms join a family only when their `summaries` sets intersect — :119 [DERIVED]
  fails-if: disjoint-support terms merge, violating R2 — :9-11.
INVARIANT: `aliases` excludes surfaces where `_norm(s) == canonical` — :142 [DERIVED]
INVARIANT: ids prefixed `"derived:"` excluded from independent count — :136-137 [DERIVED]
INVARIANT: `min_supporting_summaries` == 2 matches the guard literal 2 — :153 vs :150 [DERIVED]

## determinism & idempotency
determinism: `build_concept_families` DETERMINISTIC (sorted keys :116, sorted roots :129, alphabetical tie-break :162); `run_vocabulary_ticket` NONDETERMINISTIC (db clock `now()` :190/:238, concurrent claim via `_claim` :183, `ON CONFLICT` outcomes :209/:217/:225/:230)
idempotency: UNSAFE — the EXISTING fast path queries `WHERE input_hash=%s` with the bare `input_hash` (:186-187) but this function writes `summary_artifacts` rows with `input_hash + ":" + fam["canonical_name"]` (:218-219); the fast path can only fire on rows written by some other stage, so re-runs re-execute and rely solely on `ON CONFLICT DO NOTHING` for dedup.

## failure behaviour
- `MissingSupportIdentity(ValueError)` raised, not swallowed, when a parent row has neither `support_id` nor `parent_id`; message includes the row's key set — :60-65 [DERIVED]
- claim loss returns `{"status": "SKIPPED_NOT_CLAIMABLE"}` instead of raising — :183-184 [DERIVED]
- gate rejections are collected into `payload["rejected"]` with `gate_reason`, never raised — :194, :199, :233-234 [DERIVED]
- no try/except anywhere in this unit — nothing else is swallowed [DERIVED]

## dumb-code flags
- Docstring/code mismatch: `admit_family` docstring says "at least two supporting summaries OR one summary + distinct alias surfaces" but the code checks `len(...) < 1` — :166-168 vs :171 [DERIVED]
- Dead variable: `env = {"contract": "vocabulary-envelope-v1", "artifact_id": artifact_id, "payload": payload}` is built and never persisted or returned — :235-236 [DERIVED]
- Dangling reference: `concept_support.artifact_id` gets the outer `artifact_id` (`content_hash({"in": input_hash})`) — :195, :226 — while `summary_artifacts` rows are keyed by `"voc_" + concept_id[4:]` (`content_hash({"c","n"})`) — :218; different hash inputs produce different ids, so `concept_support` points at an artifact row never written [INFERRED — the two content_hash calls hash different dicts]
- Idempotency key mismatch: SELECT on bare `input_hash` — :186 — vs writes with `input_hash + ":" + canonical_name` — :218-219 [DERIVED]
- `accepted_concepts` seed self-support `"summaries": {key}` — :102 — which alone yields `independent_support_count` = 1 and always fails the >= 2 guard; if the key already exists from parent summaries the `setdefault` is a no-op, so this line never changes admission [INFERRED]
- Inline `__import__("json").dumps(fam)` instead of a top-level import — :221 [DERIVED]
- Magic truncations: `[:32]` — :195, :204; `[4:]` — :218; `[:16]` — :220; duplicated literal `2` for guard and `min_supporting_summaries` — :150, :153 [DERIVED]

## refactor notes
- Sole importer is `workers/workers/summary_worker_impl.py` (FACTS.importers); signature changes to `run_vocabulary_ticket` or `build_concept_families` hit it directly.
- Imports the private cross-module symbol `polymath_shared.corpus_mapping._claim` — :24, :183; renaming it in `corpus_mapping` breaks this unit [DERIVED].
- Admission rules R1/R2/R3 are declared frozen by owner — :7-13; the reason strings `"R1_corpus_isolation"`, `"R2_no_summary_support"`, `"R2_no_canonical"`, `"admitted"` are persisted as `gate_reason` — :199 — and are downstream string contracts.
- `MissingSupportIdentity` message embeds payload key names — :63-65; renaming payload keys changes the diagnostic surface.
- INSERT column lists and ON CONFLICT targets assume exact shapes of `concept_families`, `summary_artifacts`, `concept_support`, `concept_aliases`, `summary_jobs` — :205-231, :189, :237.

## VERIFY
```verify
grep -Fq 'f.get("independent_support_count", 0) >= 2' shared/polymath_shared/vocabulary_mapping.py
grep -Fq 'return False, "R1_corpus_isolation"' shared/polymath_shared/vocabulary_mapping.py
grep -Fq 'supporting_summaries", [])) < 1' shared/polymath_shared/vocabulary_mapping.py
grep -Fq 'input_hash + ":" +' shared/polymath_shared/vocabulary_mapping.py
grep -Fq 'vocabulary-envelope-v1' shared/polymath_shared/vocabulary_mapping.py
test "$(grep -c -F 'ON CONFLICT DO NOTHING' shared/polymath_shared/vocabulary_mapping.py)" -ge 2
```
