# unit: shared/polymath_shared/raw_evidence.py
anchor: shared/polymath_shared/raw_evidence.py:1-246

## purpose
V5 L1 raw-evidence ledger: records what the provider said and decides nothing; filtering decides knowledge, never evidence survival — shared/polymath_shared/raw_evidence.py:1-8 [DERIVED].
Deliberately NOT in `_SEMANTIC_AUTHORITY_MODULES`; a qualification gate asserts adding it must not move the semantic bundle hash — shared/polymath_shared/raw_evidence.py:3-5 [DERIVED].
Module-level importer (FACTS): `workers/workers/extract_worker.py`.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `RAW_EVIDENCE_CONTRACT` | const | `"raw-evidence-ledger-v1"` | shared/polymath_shared/raw_evidence.py:16 | — |
| `BUNDLE_CONTRACT` | const | `"document-evidence-bundle-v1"` | shared/polymath_shared/raw_evidence.py:120 | — |
| `provider_contract` | def | (provider, model_id, revision, task, threshold, labels) -> dict | shared/polymath_shared/raw_evidence.py:19-29 | — |
| `proposal_row` | def | (doc_id, chunk_id, item, contract) -> tuple(9) | shared/polymath_shared/raw_evidence.py:32-48 | — |
| `evidence_row` | def | (doc_id, chunk_id, item, contract) -> tuple(9) | shared/polymath_shared/raw_evidence.py:51-53 | — |
| `bulk_write` | def | (conn, table, rows) -> int | shared/polymath_shared/raw_evidence.py:70-77 | — |
| `ledger_hash` | def | (conn, doc_ids) -> dict | shared/polymath_shared/raw_evidence.py:80-91 | — |
| `hypothesis_row` | def | (doc_id, h) -> tuple(13) | shared/polymath_shared/raw_evidence.py:94-109 | — |
| `IncompleteEvidence` | class | RuntimeError subclass | shared/polymath_shared/raw_evidence.py:139-141 | — |
| `bundle_manifest` | def | (conn, doc_id, require_slices=True) -> dict | shared/polymath_shared/raw_evidence.py:144-165 | — |
| `write_bundle` | def | (conn, doc_id, require_slices=True) -> dict | shared/polymath_shared/raw_evidence.py:168-184 | — |
| `relation_candidate_row` | def | (doc_id, chunk_id, candidate, decision) -> tuple(19) | shared/polymath_shared/raw_evidence.py:187-226 | — |

Per-symbol callers not in FACTS; only the module-level importer `workers/workers/extract_worker.py` is recorded.

## contracts
`provider_contract` — shared/polymath_shared/raw_evidence.py:19-29
- in: keyword-only `provider: str, model_id: str, revision: str, task: str, threshold: float, labels: list[str]`.
- out: dict with `contract=RAW_EVIDENCE_CONTRACT`, plus the inputs and `labels_sha256 = content_hash({"labels": sorted(labels)})` — shared/polymath_shared/raw_evidence.py:21-28.
- post: label order does not change `labels_sha256` (sorted) — shared/polymath_shared/raw_evidence.py:28 [DERIVED].

`proposal_row` — shared/polymath_shared/raw_evidence.py:32-48
- in: `item` needs keys `start, end, text, label, score`; `contract` dict.
- out: 9-tuple `(pid, doc_id, chunk_id, int(start), int(end), text, label, float(score), json.dumps(contract, sort_keys=True))` — shared/polymath_shared/raw_evidence.py:46-48.
- post: `pid = "rawent_" + content_hash({doc, chunk, start, end, surface, label, score(round 6dp), provider: labels_sha256+revision+task})`; replay of the same observation hits the same primary key; changed provider/labels/threshold creates new rows — shared/polymath_shared/raw_evidence.py:38-44, 33-37.

`evidence_row` — shared/polymath_shared/raw_evidence.py:51-53
- out: identical 9-tuple with id `"rawev_" + row[0][len("rawent_"):]`.

`bulk_write` — shared/polymath_shared/raw_evidence.py:70-77
- in: `table` must be a key of `_INSERT`; rows must match that INSERT's column order.
- out: `len(rows)` inserted, `0` on empty input.
- post: runs inside the caller's stage transaction (commits/rolls back with the stage); `ON CONFLICT ... DO NOTHING` — shared/polymath_shared/raw_evidence.py:71-72, 61, 66, 117, 246.

`ledger_hash` — shared/polymath_shared/raw_evidence.py:80-91
- out: per-table `{count, sha256}` over ordered ids for exactly `raw_entity_proposals` and `raw_predicate_evidence`; `created_at` excluded by construction — shared/polymath_shared/raw_evidence.py:84-90, 81-82.

`hypothesis_row` — shared/polymath_shared/raw_evidence.py:94-109
- in: `h` needs `chunk_id, mechanism, proposed_char_start, proposed_char_end, proposed_surface, status, disposition`; optional `source_char_start, source_char_end, source_surface, evidence`.
- out: 13-tuple matching the `span_hypotheses` INSERT; id `"hyp_" + content_hash(...)` — shared/polymath_shared/raw_evidence.py:104-109, 112-117, 98-103.

`bundle_manifest` — shared/polymath_shared/raw_evidence.py:144-165
- pre: `counts["chunks"] == 0` raises `IncompleteEvidence`; `require_slices=True` and `counts["sentence_slices"] == 0` raises `IncompleteEvidence` — shared/polymath_shared/raw_evidence.py:155-161.
- out: `{doc_id, evidence_contract=BUNDLE_CONTRACT, bundle_sha256, member_hashes, counts}` where each member hash covers ordered, stringified rows — shared/polymath_shared/raw_evidence.py:159-165, 151-154.
- `require_slices=False` is the LLM-DIRECT (`llm_live`) contract; MEASURED 2026-08-30: the first live llm_live ingest failed every extract attempt at this point — shared/polymath_shared/raw_evidence.py:145-149.

`write_bundle` — shared/polymath_shared/raw_evidence.py:168-184
- post: upsert into `document_evidence_bundles` with `ON CONFLICT (doc_id) DO UPDATE SET bundle_sha256, member_hashes, counts, updated_at=now()` — shared/polymath_shared/raw_evidence.py:171-180.

`relation_candidate_row` — shared/polymath_shared/raw_evidence.py:187-226
- in: `candidate` needs `evidence, subject, object, sentence_index`; `decision` needs `decision`; optional `fact, rule_id` and `trigger_token_id, subject_token_id, object_token_id, dependency_path, sentence_id`.
- out: 19-tuple matching the `relation_candidates` INSERT; id `"relc_" + content_hash(...)` — shared/polymath_shared/raw_evidence.py:199-226, 239-246, 191-198.
- trigger column value: `getattr(evidence, "trigger_lemma", None) or getattr(evidence, "text", None)` — shared/polymath_shared/raw_evidence.py:210-211.
- `sentence_id` fallback: `f"{chunk_id}#s{candidate.sentence_index}"` when truthy — shared/polymath_shared/raw_evidence.py:224-226.

## effect surface
- Postgres read: `chunks` (:123), `sentence_slices` (:124-126), `document_layout` (:127-129), `raw_entity_proposals` (:84, :130-131), `raw_predicate_evidence` (:85, :132-133), `span_hypotheses` (:134-135); all inside `bundle_manifest`/`ledger_hash` — shared/polymath_shared/raw_evidence.py:122-136, 83-88.
- Postgres written: `raw_entity_proposals` (:58-61), `raw_predicate_evidence` (:62-66), `span_hypotheses` (:112-117), `document_evidence_bundles` (:171-180), `relation_candidates` (:239-246).
- Qdrant / files / network / subprocess / env flags: none in SOURCE.
- FACTS.tables_written lists `set` — no such table in SOURCE; likely a parser artifact of the `SET` clause at shared/polymath_shared/raw_evidence.py:177 [INFERRED].

## invariants
INVARIANT: proposal_row tuple arity 9 == `%s` count 9 in `raw_entity_proposals` INSERT — shared/polymath_shared/raw_evidence.py:46-48, 60 [DERIVED]
  fails-if: column shift; every value lands in the wrong column.
INVARIANT: evidence_row tuple arity 9 == `%s` count 9 in `raw_predicate_evidence` INSERT — shared/polymath_shared/raw_evidence.py:53, 65 [DERIVED]
  fails-if: same column-shift corruption.
INVARIANT: hypothesis_row tuple arity 13 == 13 `%s` in `span_hypotheses` INSERT — shared/polymath_shared/raw_evidence.py:104-109, 116 [DERIVED]
  fails-if: same column-shift corruption.
INVARIANT: relation_candidate_row tuple arity 19 == 19 `%s` in `relation_candidates` INSERT — shared/polymath_shared/raw_evidence.py:199-226, 245 [DERIVED]
  fails-if: same column-shift corruption.
INVARIANT: bundle member tables == 6 (`chunks, sentence_slices, layout, raw_entity_proposals, raw_predicate_evidence, span_hypotheses`) — shared/polymath_shared/raw_evidence.py:122-136 [DERIVED]
  fails-if: adding a ledger table without adding it here changes `bundle_sha256` coverage silently.
INVARIANT: `bundle_sha256` covers exactly the 6 member hashes; no timestamp input — shared/polymath_shared/raw_evidence.py:151-164 [DERIVED]
  fails-if: bundle hash becomes time-dependent and replay comparison breaks.
INVARIANT: proposal id hashes `round(float(item["score"]), 6)` but the row stores unrounded `float(item["score"])` — shared/polymath_shared/raw_evidence.py:42 vs 47 [DERIVED]
  fails-if: two observations differing only below 1e-6 in score collide on one id; `DO NOTHING` keeps the first score and silently drops the second.

## determinism & idempotency
determinism: NONDETERMINISTIC (db clock `now()` in the bundle upsert — shared/polymath_shared/raw_evidence.py:176-179). All ids are content hashes, all queries `ORDER BY`, all JSON `sort_keys=True` — shared/polymath_shared/raw_evidence.py:38, 98, 191, 123-135, 48.
idempotency: SAFE — ledger inserts `ON CONFLICT ... DO NOTHING` (shared/polymath_shared/raw_evidence.py:61, 66, 117, 246); bundle row upserts `ON CONFLICT (doc_id) DO UPDATE` (shared/polymath_shared/raw_evidence.py:176-179); writes run inside the caller's stage transaction (shared/polymath_shared/raw_evidence.py:71-72).

## failure behaviour
- `IncompleteEvidence(RuntimeError)`: raised on `counts["chunks"] == 0` and on `require_slices` with `counts["sentence_slices"] == 0`; the missing slice manifest may NOT be reconstructed — shared/polymath_shared/raw_evidence.py:139-141, 155-161.
- No `try/except` anywhere in the module; nothing is swallowed, DB errors propagate to the caller — shared/polymath_shared/raw_evidence.py:1-246 [DERIVED].
- `bulk_write` with a `table` not in `_INSERT` raises KeyError on the dict lookup — shared/polymath_shared/raw_evidence.py:74-76 [INFERRED: bare `_INSERT[table]` lookup].

## dumb-code flags
- `import json` duplicated inside three function bodies instead of module level — shared/polymath_shared/raw_evidence.py:45, 97, 169.
- Schema column named `trigger_surface` but the value written is `trigger_lemma`/`text`; the in-code comment records 34,655 of 34,655 historical rows NULL, including all 8,834 ACCEPT/QUALIFY, because the old code read an attribute `EvidenceSpan` never defined — shared/polymath_shared/raw_evidence.py:241, 210-211, 201-209.
- Score rounding mismatch: id uses 6-dp rounded score, column stores full float — shared/polymath_shared/raw_evidence.py:42, 47.
- Magic truncation `str(decision.reason or "")[:400]` — shared/polymath_shared/raw_evidence.py:215.
- `evidence_row` prefix surgery `row[0][len("rawent_"):]` hard-couples to the literal `"rawent_"` — shared/polymath_shared/raw_evidence.py:53, 38.
- `_INSERT` is built in three passes across the file (initial dict, then `span_hypotheses`, then `relation_candidates`) — order-sensitive module layout — shared/polymath_shared/raw_evidence.py:56-67, 112-117, 239-246.
- Silent `getattr(..., None)` defaults for syntax-provenance fields; legacy candidates carry `None`, which is called out as the measurable signal — shared/polymath_shared/raw_evidence.py:219-222, 217-218.

## refactor notes
- Tuple/INSERT column alignment is load-bearing for all four tables; any column change must edit both the row builder and `_INSERT` — shared/polymath_shared/raw_evidence.py:46-48/58-61, 53/62-66, 104-109/112-117, 199-226/239-246.
- Changing the `"rawent_"` prefix breaks `evidence_row` id derivation — shared/polymath_shared/raw_evidence.py:38, 53.
- Adding this module to `_SEMANTIC_AUTHORITY_MODULES` moves the semantic bundle hash and violates the asserted gate — shared/polymath_shared/raw_evidence.py:3-5.
- `require_slices=False` is the `llm_live` contract; flipping the default re-breaks LLM-DIRECT ingest (first live run failed every extract attempt) — shared/polymath_shared/raw_evidence.py:145-149.
- 34,655 existing `relation_candidates` rows have NULL trigger provenance; the `trigger_lemma or text` fallback defines audit semantics for back-fill — shared/polymath_shared/raw_evidence.py:201-211.
- `bulk_write` must stay inside the caller's transaction for stage-atomic commit/rollback — shared/polymath_shared/raw_evidence.py:71-72.

## VERIFY
```verify
grep -Fq 'RAW_EVIDENCE_CONTRACT = "raw-evidence-ledger-v1"' shared/polymath_shared/raw_evidence.py
grep -Fq 'BUNDLE_CONTRACT = "document-evidence-bundle-v1"' shared/polymath_shared/raw_evidence.py
grep -Fq 'require_slices: bool = True' shared/polymath_shared/raw_evidence.py
grep -Fq 'class IncompleteEvidence(RuntimeError):' shared/polymath_shared/raw_evidence.py
grep -Fq 'getattr(candidate.evidence, "trigger_lemma", None)' shared/polymath_shared/raw_evidence.py
! grep -Fq 'except' shared/polymath_shared/raw_evidence.py
test "$(grep -c -F 'ON CONFLICT' shared/polymath_shared/raw_evidence.py)" -ge 5
```
