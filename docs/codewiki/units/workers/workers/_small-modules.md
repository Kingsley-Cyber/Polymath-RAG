# unit: workers/workers/_small-modules
anchor: workers/workers/__init__.py:1

## purpose
Deterministic library modules for the Polymath ingestion pipeline — document profile routing, document profile building, extractive summarization — plus three worker entrypoints: the `compile_objects` stage worker, the `summaries` fleet worker, and two unimplemented stubs (`embed`, `promote`). Consumed by the ingestion stages and the shared worker runtime. [DERIVED] (workers/workers/profile_router.py:1-11, workers/workers/document_profile_builder.py:1-17, workers/workers/summarizer.py:1-6, workers/workers/compile_objects_worker.py:1-15, workers/workers/summary_worker.py:1-10, workers/workers/__init__.py:1)

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `route_document` | def | (source_name: str, sample_text: str) -> DocumentProfile | workers/workers/profile_router.py:41-76 | — |
| `chunk_extra_module` | def | (text: str, profile: DocumentProfile) -> str \| None | workers/workers/profile_router.py:79-87 | — |
| `chunk_label_set` | def | (text: str, profile: DocumentProfile) -> list[str] | workers/workers/profile_router.py:90-97 | — |
| `CORE_LABELS`, `MODULES`, `DomainModule` | re-export | from `polymath_shared.query_policy` | workers/workers/profile_router.py:22-26 | "existing importers" (comment :20-21) |
| `build_profile` | def | (*, doc_id, source_name, ingestion_profile, parent_chunks, entities, predicate_counts) -> RetrievalProfile | workers/workers/document_profile_builder.py:76-146 | — |
| `split_sentences` | def | (text: str) -> list[str] | workers/workers/summarizer.py:32-35 | — |
| `score_sentences` | def | (sentences: list[list[str]], *, lead_bias: float = 0.6) -> list[float] | workers/workers/summarizer.py:58-74 | — |
| `summarize` | def | (text: str, *, max_sentences: int = 4, max_chars: int = 900) -> str | workers/workers/summarizer.py:77-99 | document_profile_builder (workers/workers/document_profile_builder.py:25) |
| `summarize_children` | def | (children: list[str], *, max_sentences: int = 3, max_chars: int = 600) -> str | workers/workers/summarizer.py:102-107 | — |
| `Sentence` | class | frozen dataclass: index, text, words, score | workers/workers/summarizer.py:24-29 | — |
| `process_event` (compile) | def | (conn: Connection, event: dict) -> None | workers/workers/compile_objects_worker.py:59-118 | `run_forever` (:124) |
| `run_forever` | def | (poll_interval_s: float = 2.0, batch_size: int = 1) -> None | workers/workers/compile_objects_worker.py:121-125 | `__main__` (:128-130) |
| `handle_embed` | def | (job: dict) -> None — raises NotImplementedError | workers/workers/embed_worker.py:15-16 | `__main__` (:20) |
| `handle_promote` | def | (job: dict) -> None — raises NotImplementedError | workers/workers/promote_worker.py:14-15 | `__main__` (:19) |
| `main` (summaries) | def | () -> None | workers/workers/summary_worker.py:18-24 | `__main__` (:27-28) |

Package-level importers per FACTS: `workers/workers/{chunker,extract_worker,intake_worker,knowledge_artifacts,profile_worker,semantic_chunker,summary_worker_impl,tier_chunker}.py`; per-symbol attribution not in FACTS.

## contracts

**route_document** — workers/workers/profile_router.py:41-76
- in: `source_name` (path/filename), `sample_text` = "the first few thousand chars" (:42-43); only `sample_text[:4000]` is ever read (:56, :58).
- pre: none. Path hints checked first (:49); keyword scoring only fires when no path hint matched (:53-60).
- out: `DocumentProfile` with `profile_id = ",".join(sorted(active)) or "core"` (:62); `label_set` = `CORE_LABELS` + labels of at most the first two active modules, capped `[:MAX_LABELS_PER_CALL]` (:63-74); `core_labels = list(CoreType)` (:75).
- post: no model call, deterministic (:5-6).

**chunk_label_set / chunk_extra_module** — workers/workers/profile_router.py:79-97
- out: profile labels + at most one extra module whose regex probe matches, order fixed by `_EXTRA_MODULE_PROBES` (:30-33, :82-86); merged set capped `[:MAX_LABELS_PER_CALL]` (:97).
- pre: probe modules already in `profile.active_modules` are skipped (:83-84).

**build_profile** — workers/workers/document_profile_builder.py:76-146
- in: keyword-only; `parent_chunks` list of dicts with keys `chunk_id` and `summary` or `text` (:86-87); `entities` as `(surface, core)` tuples (:103); `predicate_counts` as `(pred, count)` tuples (:107).
- out: `RetrievalProfile`; `semantic_summary = summarize(joined, max_sentences=5, max_chars=1100)` (:129); `coverage=1.0` (:144); `summary_contract=SUMMARY_CONTRACT` = `"document-summary-v1"` (:27, :145).
- post: "Pure function: same inputs, same profile, byte for byte." (:85).
- domains: `primary` from `ingestion_profile["active_modules"]` expanded via `MODULE_DOMAINS` (:90-91); `secondary` from first-token substring match of other modules' domains in the joined parent text (:93-100).

**summarize** — workers/workers/summarizer.py:77-99
- in: `text`, keyword-only budgets.
- out: highest-scoring `max_sentences` sentences re-joined in original order; ranking `sorted(range(len(raw)), key=lambda i: (-scores[i], i))` — tie-break earlier sentence (:90); empty input returns `""` (:85-86).
- post: output ≤ `max_chars`, cut at a word boundary, then `rstrip(".,;:-")` (:94-99).

**summarize_children** — workers/workers/summarizer.py:102-107
- in: list of child texts.
- out: two-level centroid — per-child `summarize(child, max_sentences=1, max_chars=220)`, then `summarize` of the concatenation with `(max_sentences=3, max_chars=600)` (:106-107); "stable under chunk reorder" (:104-105).

**process_event (compile_objects)** — workers/workers/compile_objects_worker.py:59-118
- in: `event["run_id"]` (:62).
- pre: `runs` row for `run_id` must exist, else `StageFailed(run_id, STAGE)` (:63-67).
- effect: contract hash over `{"contract_version": "1.0.0", "persistence": "knowledge-artifact-persistence-v2"}` (:70-76); per document: child chunks `tier = 'child'` `ORDER BY chunk_index` (:84-90), distinct mention `surface`s (:94-101), then `_persist_knowledge_artifacts` (:102-106).
- post: artifact `{"contract": "compile-objects-v1", ...}` written (:108-117); `writer.run_status("reconciling")` (:118).

**run_forever / main** — workers/workers/compile_objects_worker.py:121-125, workers/workers/summary_worker.py:18-24
- run_worker queues: `"compile_objects"` consuming `["compile_objects.v1"]`; `"summaries"` consuming `["parent_enrichment.v1", "parent_summary.v1", "document_summary.v1", "corpus_summary.v1", "vocabulary.v1"]` delegating to `workers.summary_worker_impl.process_event` (:15).

## effect surface
- Postgres reads (psycopg `Connection`): `runs` (workers/workers/compile_objects_worker.py:64), `document_processing_runs` (:40-43), `documents` (:46-55), `chunks` (:83-90), `mentions` (:94-101). Matches FACTS `tables_read`; `tables_written` is `[]` — writes happen inside `_persist_knowledge_artifacts` (external, lazy import :60) and the `stage_transaction` writer (`polymath_shared.receipts`, :78).
- Qdrant/Neo4j: no calls in code; `promote_worker` names them as intended targets only (workers/workers/promote_worker.py:1-2). `embed_worker` names an embedder sidecar via `shared/polymath_shared/clients.py` (workers/workers/embed_worker.py:1-4) — no HTTP in code.
- No files, subprocesses, or env flags read anywhere in the unit.
- Event-queue polling via `polymath_shared.worker_runtime.run_worker` (workers/workers/compile_objects_worker.py:124, workers/workers/summary_worker.py:19).

## invariants
INVARIANT: `len(profile.label_set)` <= `MAX_LABELS_PER_CALL` = `50` — workers/workers/profile_router.py:28,74,97 [DERIVED]
  fails-if: pass-1 GLiNER calls exceed the uni-encoder label budget (docx §3.1 ref :28); span precision degrades.
INVARIANT: extra modules per chunk <= `1` — workers/workers/profile_router.py:80-86 [DERIVED]
  fails-if: label sets per chunk grow unbounded and nondeterministically.
INVARIANT: `len(summarize output)` <= `max_chars`, never cut mid-word — workers/workers/summarizer.py:94-99 [DERIVED]
  fails-if: downstream routing cards / parent summaries overflow their char budget.
INVARIANT: per-child summary budgets are exactly `(1, 220)` and parent budgets `(3, 600)` — workers/workers/summarizer.py:106-107 [DERIVED]
  fails-if: parent summary contract size changes; two-level centroid stability lost.
INVARIANT: `coverage == 1.0` and `summarized_parent_count == len(parent_ids)` unconditionally — workers/workers/document_profile_builder.py:142-144 [DERIVED]
  fails-if: [INFERRED] reported coverage overstates reality — a parent with `summary = None` falls back to raw `text` (:87) yet is still counted as summarized at coverage 1.0.
INVARIANT: stage contract hash input contains literal `"knowledge-artifact-persistence-v2"` — workers/workers/compile_objects_worker.py:70-76 [DERIVED]
  fails-if: replay after a persister change would not re-ground artifacts (rationale in comment :72-75).
INVARIANT: identical inputs -> byte-identical outputs for `summarize`, `build_profile`, `route_document` — workers/workers/summarizer.py:1-6, workers/workers/document_profile_builder.py:85, workers/workers/profile_router.py:5-6 [DERIVED]
  fails-if: content-addressed artifact ids (compile_objects_worker.py:14) churn or collide.

## determinism & idempotency
determinism:
- summarizer / profile_router / document_profile_builder: DETERMINISTIC — "No LLM, no model call, no randomness" (workers/workers/summarizer.py:1-2); "no model call" (workers/workers/profile_router.py:5-6); "Pure function" (workers/workers/document_profile_builder.py:85).
- compile_objects_worker: NONDETERMINISTIC (db — reads `runs`/`chunks`/`mentions` at :64, :84-90, :94-101; concurrency — `run_worker` poll loop :124).
- summary_worker: NONDETERMINISTIC (db/concurrency via delegation to `summary_worker_impl.process_event`, workers/workers/summary_worker.py:15,19).

idempotency:
- compile_objects: SAFE — "artifact ids are content-addressed; replay writes zero rows" (workers/workers/compile_objects_worker.py:13-14); v2 persister UPSERTs and refreshes `supporting_chunks/source_chunk_ids` on replay (comment :72-75).
- embed/promote: UNSAFE to call at all — `raise NotImplementedError` (workers/workers/embed_worker.py:16, workers/workers/promote_worker.py:15).

## failure behaviour
- `StageFailed(run_id, STAGE)` raised when `run_id` is absent from `runs` — workers/workers/compile_objects_worker.py:63-67. Stage is non-blocking in the ticket DAG: "a failure degrades knowledge objects, never blocks QUERY_READY" (:12-14).
- Documents without child chunks are not failures: recorded as `{"skipped": "no child chunks"}` in the artifact's `per_document` — workers/workers/compile_objects_worker.py:91-92.
- `NotImplementedError` propagates from `handle_embed` / `handle_promote`; their `__main__` blocks call them with `{}` and would always raise — workers/workers/embed_worker.py:16,20, workers/workers/promote_worker.py:15,19.
- No try/except handlers anywhere in the unit; no FACTS fallbacks.

## dumb-code flags
- Two dead stubs whose `__main__` guarantees a crash — workers/workers/embed_worker.py:15-20, workers/workers/promote_worker.py:14-19.
- `coverage=1.0` and `summarized_parent_count=len(parent_ids)` hardcoded even when parent summary is `None` and raw text substituted — workers/workers/document_profile_builder.py:87,142-144.
- `route_document` puts all matched modules into `active_modules` but only the first two ever contribute labels — workers/workers/profile_router.py:64-69; third+ modules silently label-less.
- Substring domain matching: `domain.split("_")[0] in joined.lower()` — any occurrence of e.g. `"marketing"` anywhere flips a secondary domain — workers/workers/document_profile_builder.py:98.
- Redundant single-element list inside `any()`: `for kw in [module.replace("_", " ").split()[0]]` — workers/workers/document_profile_builder.py:125.
- Double truncation in `summarize`: word-boundary cut then `rstrip(".,;:-")` silently shortens below `max_chars` — workers/workers/summarizer.py:96-99.
- Magic numbers, all bare: `4000` sample cap (workers/workers/profile_router.py:56,58); `lead_bias = 0.6` (:58 of summarizer); budgets `4/900`, `3/600`, `1/220` (summarizer.py:77,102,106); `5/1100` (document_profile_builder.py:129); top-`10` concepts (:105), top-`6` predicates (:110,114), `[:8]` caps (:139-140); fallback profile_id literal `"core"` (profile_router.py:62).
- `_run_documents` dual semantics: `document_processing_runs` first, then a corpus-wide legacy fallback keyed on `runs.metadata->>'source_name'` — same run can resolve to different document sets across eras — workers/workers/compile_objects_worker.py:40-56.

## refactor notes
- The `profile_router` re-exports exist "for existing importers" — moving `CORE_LABELS`/`MODULES`/`DomainModule` to direct `polymath_shared.query_policy` imports breaks them — workers/workers/profile_router.py:20-26.
- `compile_objects_worker` depends on the private symbol `workers.knowledge_artifacts._persist_knowledge_artifacts` via a lazy in-function import — a rename fails at runtime, not import time — workers/workers/compile_objects_worker.py:60.
- Changing `CONTRACT_VERSION` (`"1.0.0"`) or the persistence literal changes the stage contract hash and forces every corpus to re-ground artifacts once — workers/workers/compile_objects_worker.py:31,70-76.
- `summary_worker`'s five event literals must stay in sync with control-plane emissions — workers/workers/summary_worker.py:21-22.
- `build_profile` output is the `document-summary-v1` contract; a neural summarizer swap "is a contract addition, never a silent swap" — workers/workers/document_profile_builder.py:13-16,27.
- Package-level blast radius: FACTS importers `chunker.py`, `extract_worker.py`, `intake_worker.py`, `knowledge_artifacts.py`, `profile_worker.py`, `semantic_chunker.py`, `summary_worker_impl.py`, `tier_chunker.py` — any move/rename inside `workers/workers/` ripples to all eight.

## VERIFY
```verify
grep -Fq 'MAX_LABELS_PER_CALL = 50' workers/workers/profile_router.py
grep -Fq 'SUMMARY_CONTRACT = "document-summary-v1"' workers/workers/document_profile_builder.py
grep -Fq '"persistence": "knowledge-artifact-persistence-v2"' workers/workers/compile_objects_worker.py
grep -Fq 'writer.run_status("reconciling")' workers/workers/compile_objects_worker.py
grep -Fq 'lead_bias: float = 0.6' workers/workers/summarizer.py
grep -Fq 'sample_text[:4000]' workers/workers/profile_router.py
grep -Fq 'raise NotImplementedError' workers/workers/embed_worker.py
test "$(grep -c -F 'max_chars' workers/workers/summarizer.py)" -ge 6
```
