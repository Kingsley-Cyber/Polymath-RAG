# unit: workers/workers/canonicalize_worker.py
anchor: workers/workers/canonicalize_worker.py:1-184

## purpose
Worker for the `canonicalize` stage: builds the corpus-level canonical registry (C1, ADR 0009) by consuming `canonicalize.v1` outbox events scheduled by the census after `verify_projections` — workers/workers/canonicalize_worker.py:1-8 [DERIVED]. Recomputation is deterministic and replay is a no-op; the registry is additive and never mutates local entity/fact/evidence rows — workers/workers/canonicalize_worker.py:4-12 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `process_event` | def | `(conn: Connection, event: dict) -> None` | workers/workers/canonicalize_worker.py:143-167 | passed to `run_worker` at :180 |
| `run_forever` | def | `(poll_interval_s: float = 2.0, batch_size: int = 1) -> None` | workers/workers/canonicalize_worker.py:170-181 | `__main__` at :183-184 |

Private helpers (not for external use): `_corpus_entities` :43-61, `_corpus_aliases` :64-78, `_apply_registry` :81-140. No FACTS importers listed.

## contracts

`process_event(conn, event)` — workers/workers/canonicalize_worker.py:143-167
- in: `event` dict must contain `"run_id"` — :144 [DERIVED]
- pre: `runs` row for `run_id` must exist, else `StageFailed(run_id, STAGE)` — :145-149 [DERIVED]
- out: `None`; writes artifact `{corpus_id, canonicalizer_version, canonical_entities, memberships, decisions}` and sets run status `"reconciling"` — :162-167 [DERIVED]
- post: canonical tables for the corpus exactly match `canonicalize(corpus_id, entities, aliases)` output — :157-161 [DERIVED]

`_apply_registry(conn, corpus_id, out)` — workers/workers/canonicalize_worker.py:81-140
- in: `out` with `.canonical_entities`, `.memberships`, `.decisions` — :98/:110/:122 [DERIVED]
- pre: caller holds the stage transaction (atomic boundary) — :82-85 [DERIVED]
- out: `{"canonical_entities": len(...), "memberships": len(...), "decisions": len(...)}` — :136-140 [DERIVED]
- post: all prior corpus rows deleted, then inserts applied — :86-97, :98-135 [DERIVED]

`_corpus_entities(conn, corpus_id)` -> `list[dict]` with keys `entity_id`, `core_type`, `normalized_surface`, ordered by `e.entity_id` — :43-61 [DERIVED].
`_corpus_aliases(conn, corpus_id)` -> `dict[str, list[str]]` from `corpora.profile["canonical_aliases"]`; `{}` on missing corpus or non-dict — :64-78 [DERIVED].
`run_forever` delegates to `run_worker('canonicalize', [EVENT_TYPE], process_event, poll_interval_s=..., batch_size=...)` — :178-181 [DERIVED].

## effect surface

| effect | detail | anchor |
|---|---|---|
| PG read | `runs` (run_id -> corpus_id) | workers/workers/canonicalize_worker.py:146 |
| PG read | `corpora` (profile) | workers/workers/canonicalize_worker.py:66 |
| PG read | `entities` JOIN `facts` JOIN `evidence` JOIN `documents` | workers/workers/canonicalize_worker.py:46-54 |
| PG write | DELETE+INSERT `canonicalization_decisions`, `canonical_memberships`, `canonical_entities` | workers/workers/canonicalize_worker.py:86-135 |

No Qdrant collections, files, network calls, subprocesses, or env flags visible in this unit.

## invariants
- INVARIANT: default `batch_size` = `1` — matches docstring "claim depth 1" — workers/workers/canonicalize_worker.py:170-177 [DERIVED]
  fails-if: batch_size > 1 lets a long stage hold claimed events past `claim_ttl_s`, which the reaper expires — :171-177.
- INVARIANT: canonicalized entity has `admission_class IS DISTINCT FROM 'MENTION_ONLY'` AND `IS DISTINCT FROM 'DOCUMENT_SCOPED'` — workers/workers/canonicalize_worker.py:52-53 [DERIVED]
  fails-if: mention-only or document-scoped entities enter the registry and shift canonical ids.
- INVARIANT: entity eligible only with ≥1 fact (subject or object) that has evidence on a document of the corpus — workers/workers/canonicalize_worker.py:48-51 [INFERRED: inner joins drop unevidenced entities]
  fails-if: an entity with no evidenced fact silently disappears from canonicalization input.
- INVARIANT: artifact counts == `len(out.canonical_entities)` / `len(out.memberships)` / `len(out.decisions)` == rows inserted for the corpus — workers/workers/canonicalize_worker.py:87-97, :136-140 [DERIVED]
  fails-if: counts lie about table state (e.g. `ON CONFLICT DO NOTHING` skip at :130 makes decisions count exceed inserted rows — :122-135, :139) [INFERRED: conflict skip breaks count==rows for `decision_id` collisions].
- INVARIANT: contract hash input = `{"contract_version": "1.0.0", "canonicalizer_version": CANONICALIZER_VERSION}` under `STAGE` — workers/workers/canonicalize_worker.py:152-155 [DERIVED]
  fails-if: receipt verification against a different hash rejects the stage.
- INVARIANT: successful stage always sets run status `"reconciling"` — workers/workers/canonicalize_worker.py:167 [DERIVED]
  fails-if: downstream state machine waiting on another literal stalls.

## determinism & idempotency
determinism: DETERMINISTIC — `canonicalize()` output is a pure function of corpus state per module docstring — workers/workers/canonicalize_worker.py:4-8; entity query has `ORDER BY e.entity_id` — :54; no clock/random/uuid/network use in this unit (imported `time` is never referenced — :18) [DERIVED].
idempotency: SAFE — full delete of corpus rows plus `ON CONFLICT DO NOTHING` inserts inside one `stage_transaction` makes replay state-identical — :82-97, :105, :117, :130, :157 [DERIVED].

## failure behaviour
- `StageFailed(run_id, STAGE)` raised when `run_id` not found in `runs` — workers/workers/canonicalize_worker.py:148-149 [DERIVED].
- `stage_transaction` is the atomic boundary: partial registry writes roll back with the transaction — :157 [DERIVED].
- Nothing is swallowed in this unit; claim/retry handling lives in `run_worker` (not visible here) — :178-181 [INFERRED: `claim_events` imported but unused in this file].

## dumb-code flags
- Unused imports: `time` (:18), `psycopg` (:20, only `Connection` sub-import used), `tx` (:27), `configure_logging` (:28), `claim_events` (:31); unused module var `log` (:40) — workers/workers/canonicalize_worker.py:18-40 [DERIVED].
- Docstring says "delete stale rows, insert missing ones" but code deletes ALL corpus rows then re-inserts (full replace, not diff) — :82-85 vs :86-97; module docstring repeats "delete-stale + insert-missing" at :7-8 [DERIVED].
- `ON CONFLICT (corpus_id, canonical_id) DO NOTHING` and `ON CONFLICT (corpus_id, local_entity_id) DO NOTHING` are dead branches — the same corpus rows were just deleted at :86-97 — :105, :117 [INFERRED: conflict unreachable single-writer].
- `ON CONFLICT (decision_id) DO NOTHING` is NOT corpus-scoped — a `decision_id` collision across corpora is silently skipped and the artifact count still reports it — :130, :139 [INFERRED].

## refactor notes
- `EVENT_TYPE = "canonicalize.v1"` must stay in sync with the census scheduler that emits it — :37, :3-4 [INFERRED: mismatch orphans all events].
- `CONTRACT_VERSION` ("1.0.0") and `CANONICALIZER_VERSION` feed `stage_contract_hash`; changing either invalidates existing receipts — :38, :152-155 [INFERRED].
- `writer.run_status("reconciling")` literal is a cross-stage protocol value — :167 [INFERRED].
- `_apply_registry` signature/return shape is consumed by `process_event` only; `out` must keep `.canonical_entities/.memberships/.decisions` field names used in SQL — :98-135 [DERIVED].
- `run_worker('canonicalize', [EVENT_TYPE], ...)` binds worker type name `'canonicalize'` — :180 [DERIVED].

## VERIFY
```verify
grep -Fq 'STAGE = "canonicalize"' workers/workers/canonicalize_worker.py
grep -Fq 'EVENT_TYPE = "canonicalize.v1"' workers/workers/canonicalize_worker.py
grep -Fq 'CONTRACT_VERSION = "1.0.0"' workers/workers/canonicalize_worker.py
grep -Fq 'poll_interval_s: float = 2.0, batch_size: int = 1' workers/workers/canonicalize_worker.py
grep -Fq 'writer.run_status("reconciling")' workers/workers/canonicalize_worker.py
grep -Fq 'ON CONFLICT (decision_id) DO NOTHING' workers/workers/canonicalize_worker.py
test "$(grep -c -F 'DELETE FROM canonical' workers/workers/canonicalize_worker.py)" -ge 3
```
