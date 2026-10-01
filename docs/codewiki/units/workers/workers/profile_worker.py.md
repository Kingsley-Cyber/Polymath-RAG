# unit: workers/workers/profile_worker.py
anchor: workers/workers/profile_worker.py:1-331

## purpose
Worker for the `profile_document` stage: consumes `profile_document.v1` outbox events (scheduled by the census after extract) and, per document, builds the retrieval profile (deterministic aggregation over parents, entities, facts, ingestion profile — no LLM) plus SUMMARY-COMPILER-V1 routing cards into `retrieval_summaries`. Coverage fields commit with the profile so an incomplete routing representation is never silently accepted. — workers/workers/profile_worker.py:1-8 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `run_forever` | function | `(poll_interval_s: float = 2.0, batch_size: int = 1) -> None` | workers/workers/profile_worker.py:317-328 | `__main__` (workers/workers/profile_worker.py:330-331) |
| `process_event` | function | `(conn: Connection, event: dict) -> None` | workers/workers/profile_worker.py:261-314 | handed to `run_worker('profile_document', [EVENT_TYPE], process_event, ...)` (workers/workers/profile_worker.py:327) |

Constants: `STAGE = "profile_document"` (:28), `EVENT_TYPE = "profile_document.v1"` (:29), `CONTRACT_VERSION = "1.2.0"` (:30). All helpers below are underscore-private.

## contracts

### process_event — workers/workers/profile_worker.py:261-314
- in: `event["run_id"]` (:262); contract hash over `{"contract_version": CONTRACT_VERSION, "summary_contract": SUMMARY_CONTRACT}` (:264-267)
- pre: extract stage artifacts must exist for digests to be found (`a.stage = 'extract'`, :118); docstring places this stage "after extract" (:3-4)
- out: `writer.artifact({"documents_profiled": len(profiles), "routing_cards": summary_stats})` (:312-313); `writer.run_status("reconciling")` (:314)
- post: per doc, `documents` gets `retrieval_profile`, `profile_contract = SUMMARY_CONTRACT`, `source_parent_count`, `summarized_parent_count`, `profile_coverage` (:285-298); all inside `stage_transaction(conn, run_id=..., stage=STAGE, contract_hash=contract)` (:269)

### _persist_retrieval_summaries — workers/workers/profile_worker.py:167-230
- pre: children filtered by `is_summarizable(c.get("region_role"))`; parents filtered to `live_parent_ids` (:191-194)
- out: stats dict `{"sections", "llm_digest_active", "uncovered", "document", "children_excluded"}` (:195-196); early return of zeros when no parent survives (:197-198)
- post: one SECTION card per surviving parent (:219-220) + one DOC card `source_id=doc_id, parent_id=None, variants=[(doc, True)]` (:227-228)

### _upsert_slot — workers/workers/profile_worker.py:132-164
- pre: slot key = `(doc_id, kind, COALESCE(parent_id, ''))`; docstring cites a "unique partial index" (:135-136)
- post: all prior actives in slot set `active = FALSE` (:140-144); every variant row persisted via `INSERT ... ON CONFLICT (summary_id) DO UPDATE` (:146-157); ids = `summary_id(kind, source_id, c.embed_text)` (:139)

### run_forever — workers/workers/profile_worker.py:317-328
- contract: claim depth 1 (`batch_size` default `1`, :317, :318); parallelism comes from running several workers, not claiming ahead (:320-323)

## effect surface

| layer | object | op | anchor |
|---|---|---|---|
| Postgres | `documents` | read (doc list join `runs`; corpus lookup) | workers/workers/profile_worker.py:38-41, 299-301 |
| Postgres | `documents` | UPDATE 5 profile columns by `doc_id` | workers/workers/profile_worker.py:285-298 |
| Postgres | `runs` | read (joins) | workers/workers/profile_worker.py:40, 115 |
| Postgres | `chunks` | read (`tier = 'parent'` / `tier = 'child'`) | workers/workers/profile_worker.py:52-54, 64-66 |
| Postgres | `evidence` | read (joins by `doc_id`) | workers/workers/profile_worker.py:82, 86, 237-240, 252 |
| Postgres | `facts` | read (joins, `GROUP BY f.predicate`) | workers/workers/profile_worker.py:83, 250-254 |
| Postgres | `entities` | read (subject/object joins) | workers/workers/profile_worker.py:84-85, 239 |
| Postgres | `artifacts` | read (`payload->'llm_extraction'->'digests'`, latest by `created_at DESC LIMIT 1`) | workers/workers/profile_worker.py:113-121 |
| Postgres | `retrieval_summaries` | UPDATE `active = FALSE` + INSERT ON CONFLICT | workers/workers/profile_worker.py:140-163 |

No Qdrant, file, network, subprocess, or env-flag reads appear in this unit. FACTS `tables_written` also lists `"set"` — no such table; it is the `SET active = FALSE` UPDATE keyword misparsed (:141) [INFERRED].

## invariants
INVARIANT: active rows per slot == 1 — deactivate-all (:140-144) then exactly one `True` flag per variant list (:215-217, :228) — workers/workers/profile_worker.py:140-144 [DERIVED]
  fails-if: two active cards for one (doc, kind, parent) route retrieval to divergent summaries.
INVARIANT: section cards written == parents with ≥1 summarizable child — `live_parent_ids` filter (:193-194), early return (:197-198) — workers/workers/profile_worker.py:191-198 [DERIVED]
  fails-if: an all-noise parent gets a card the verifier does not expect (:179-180).
INVARIANT: doc cards per doc ≤ 1 — `stats["document"] = 1` set once after the parent loop (:229) — workers/workers/profile_worker.py:226-229 [DERIVED]
  fails-if: duplicate document routing cards.
INVARIANT: `llm_digest_active` ≤ `sections` — incremented only inside the per-parent loop (:218 vs :221) — workers/workers/profile_worker.py:218-221 [DERIVED]
INVARIANT: `trusted` == (`decision` == `"ACCEPT"`) — workers/workers/profile_worker.py:101 [DERIVED]
  fails-if: non-ACCEPT facts get serialized into `relations` instead of only ranking.
INVARIANT: `summary_id` depends only on (kind, source_id, embed_text) (:139); replay with identical inputs lands on identical ids and flags (:135-137) — workers/workers/profile_worker.py:139 [DERIVED]
  fails-if: replays insert duplicate rows instead of hitting ON CONFLICT.
INVARIANT: default `batch_size` == 1 == "claim depth 1" — workers/workers/profile_worker.py:317-318 [DERIVED]
  fails-if: claiming ahead lets the reaper expire queued tickets when a stage runs past `claim_ttl_s` (:320-323).

## determinism & idempotency
determinism: NONDETERMINISTIC (db: `_digests_for_doc` picks the latest extract artifact via `ORDER BY a.created_at DESC LIMIT 1` (:120-121) and that LLM digest becomes the ACTIVE section variant (:214-217); the document profile itself is deterministic, no LLM (:4-5))
idempotency: SAFE (replay lands on identical ids and flags (:135-137); slot deactivation + `ON CONFLICT (summary_id) DO UPDATE` (:141-144, :153-157); `documents` UPDATE keyed by `doc_id` (:293); all inside one `stage_transaction` (:269))

## failure behaviour
- No `try`/`except` anywhere in the unit; `StageFailed` is imported (:21) but never raised here. Exception handling is delegated to `stage_transaction` / `run_worker` (not visible in this material). — workers/workers/profile_worker.py:21, 269, 327 [DERIVED]
- Silent field-level fallbacks (data swallowed, not errors): `span_offsets` None/str → `{}` (:92); missing digest artifact → `[]` (:126); missing corpus row → `corpus_id=""` (:304); missing parent text → `""` (:224); missing `documents.profile` → `{}` (:46).
- Missing digest lookup degrades to the deterministic variant staying active (`llm is None` → `(det, True)`, :215) — no error surfaced.

## dumb-code flags
- Unused imports: `time` (:13), `psycopg` (:15 — only `Connection` from it is used, :16), `tx` (:18), `configure_logging` (:19), `StageFailed` (:21), `claim_events` (:22). [DERIVED]
- `log = logging.getLogger("profile-document")` (:32) — no `log.*` call anywhere in the file. [DERIVED]
- Duplicated literal: `'profile_document'` hardcoded in the `run_worker` call (:327) while `STAGE` holds the same value (:28).
- Sentinel mismatch: missing chunk order → `10**9` (:102) vs missing start offset → `-1` (:104); both magic numbers on adjacent lines.
- `corpus_id=corpus_row[0] if corpus_row else ""` (:304) — cards can be written with empty-string `corpus_id` if the row vanished mid-transaction.

## refactor notes
- `CONTRACT_VERSION` "1.2.0" + `SUMMARY_CONTRACT` feed `stage_contract_hash` (:264-267) — any change alters the receipt hash; receipt verifiers must move in lockstep.
- Slot identity `(doc_id, kind, COALESCE(parent_id, ''))` (:141-143) must keep matching the `retrieval_summaries` unique partial index cited at :135-136.
- `writer.run_status("reconciling")` (:314) — the next stage is keyed on this status string.
- `_digests_for_doc` joins `r.metadata->>'source_name'` to `d.source_name` (:116-117) — renaming either silently returns no digests (deterministic variant stays active, no error).
- Removing the noise/parent filters (:191-194) changes card counts; the verifier "does not expect one" card for all-noise parents (:179-180).
- `EVENT_TYPE` "profile_document.v1" (:29) is the subscription key passed to `run_worker` (:327); `CONTRACT_VERSION` comment ties "1.2.0" to SUMMARY-COMPILER-V1 cards (:30).

## VERIFY
```verify
grep -Fq 'CONTRACT_VERSION = "1.2.0"' workers/workers/profile_worker.py
grep -Fq '"trusted": decision == "ACCEPT"' workers/workers/profile_worker.py
grep -Fq 'SET active = FALSE' workers/workers/profile_worker.py
grep -Fq 'writer.run_status("reconciling")' workers/workers/profile_worker.py
grep -Fq 'batch_size: int = 1' workers/workers/profile_worker.py
grep -Fq 'chunk_order.get(chunk_id, 10**9)' workers/workers/profile_worker.py
test "$(grep -c -F 'ORDER BY chunk_index' workers/workers/profile_worker.py)" -ge 2
! grep -Fq 'log.info' workers/workers/profile_worker.py
```
