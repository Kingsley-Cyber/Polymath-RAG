# unit: shared/polymath_shared/latent/_small-modules
anchor: shared/polymath_shared/latent/__init__.py:1-8

## purpose
LATENT-TRANSFER-LAYER-V1: enrichment routes, children prove. Latent artifacts (abstractions, mechanisms, affordances, questions) are additive retrieval surfaces pointing back at a parent's original children; latent text is never evidence and its absence is invisible at query time (§0b mixed-era union contract) — shared/polymath_shared/latent/__init__.py:1-8 [DERIVED]. The unit holds the output contract, prompt renderers, projection rows, rescue lane, persistence, and the work-ticket mint path for that layer.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `EnrichmentBounds` | class (frozen) | 11 fields, defaults `summary_chars=1000, gist_chars=320, abstraction_chars=400, mechanism_chars=240, affordance_chars=200, question_chars=160, max_mechanisms=2, max_affordances=2, max_questions=3, max_tokens=700, gist_coverage_floor=0.8` | contract.py:17-33 | — |
| `QUALIFICATION_BOUNDS` / `PRODUCTION_BOUNDS` | const | `EnrichmentBounds()` / `EnrichmentBounds(max_tokens=900)` | contract.py:36-37 | — |
| `ChildGist` | class | `ref: int, gist: str` | contract.py:41-43 | — |
| `EnrichmentOutput` | class | `summary, children, abstraction, mechanisms=[], affordances=[], questions=[]` | contract.py:47-54 | — |
| `EnrichmentGateResult` | class | `ok, error_class=None, detail="", gist_coverage=0.0, trimmed=None, raw_chars=0` | contract.py:58-63 | — |
| `latent_point_id` | def | `(enrichment_id: str, kind: str) -> str` | projection.py:15-16 | — |
| `latent_rows` | def | `(conn, run_id: str) -> list[dict]` | projection.py:19-62 | — |
| `stale_point_ids` | def | `(conn, corpus_id: str) -> list[tuple[str, str]]` | projection.py:65-77 | — |
| `render_parent_input` | def | `(parent_id: str, children: list[tuple[int, str]]) -> str` | prompt.py:27-34 | — |
| `prompt_hash` | def | `() -> str` | prompt.py:37-40 | per FACTS.imports |
| `render_microbatch_input` | def | `(parents: list[tuple[str, list[tuple[int, str]]]]) -> str` | prompt.py:77-86 | — |
| `LatentParent` | class | `parent_id, doc_id, source_name, best_score, channels={}, need=""` | rescue.py:23-31 | — |
| `LatentRescue` | class | `parents=[], degraded=None, latency_ms=0.0` | rescue.py:35-38 | — |
| `latent_rescue_parents` | def | `(qvec, *, corpus_id, plan, routing_search, skip_parent_ids=frozenset(), clock=time.monotonic) -> LatentRescue` | rescue.py:41-89 | — |
| `enrichment_contract_id` | def | `(bounds) -> str` | runtime.py:17-33 | — |
| `input_hash_for` | def | `(source_hash: str, contract_id: str) -> str` | runtime.py:36-42 | — |
| `persist_compiled_parent` | def | `(conn, *, corpus_id: str, doc_id: str, compiled: CompiledParent, input_hash: str, provider: str, model: str) -> dict` | runtime.py:45-143 | — |
| `mint_parent_enrichment` | def | `(conn, *, corpus_id: str, run_id: str, doc_id: str | None = None) -> dict` | trigger.py:17-45 | — |

Package imported by (FACTS.importers): `control/control/scheduler.py`, `orchestrator/orchestrator/api/graph.py`, `orchestrator/orchestrator/api/hybrid.py`, `orchestrator/orchestrator/api/ui.py`, `shared/polymath_shared/candidate_engine.py`, `shared/polymath_shared/hybrid.py`, `shared/polymath_shared/latent/compiler.py`, `shared/polymath_shared/latent/gate.py`, `workers/workers/project_qdrant_worker.py`, `workers/workers/summary_worker_impl.py`, `workers/workers/verify_worker.py`.

## contracts

**`persist_compiled_parent`** — runtime.py:45-143
- in: `compiled: CompiledParent` (from `latent.compiler`, an importer of this package), `input_hash`, `provider`, `model`.
- pre: an existing row with same `input_hash` and `status='READY'` is EXISTING only if its `parent_id` chunk still exists (`EXISTS (SELECT 1 FROM chunks ...)`) — runtime.py:58-65.
- effect: orphan rows (parent chunk gone) under this identity are DELETEd first — runtime.py:67-71; prior READY row for the parent flipped `status='STALE', superseded_at=now()` — runtime.py:84-88.
- post: returns `{"status": "EXISTING", "enrichment_id": ...}` / `{"status": "READY", ...}` / `{"status": "INVALID", "error_class": ...}`; READY and INVALID both upsert `ON CONFLICT (enrichment_id) ... WHERE parent_enrichments.status='INVALID'` — runtime.py:98-112, 121, 129-143.
- `enrichment_id = "penr_" + content_hash({"in": input_hash})[:32]` — runtime.py:77.

**`enrichment_contract_id(bounds)`** — runtime.py:17-33
- out: `f"{COMPILER_CONTRACT}|shape={shape}"` where shape joins 10 bound fields (`summary_chars` … `gist_coverage_floor`) with `/` — runtime.py:29-33.
- excludes the lane (provider/model) and `max_tokens` on purpose — runtime.py:18-28.

**`input_hash_for(source_hash, contract_id)`** — runtime.py:36-42
- out: `content_hash({"source": source_hash, "prompt": prompt_hash(), "model": contract_id})`.

**`latent_rows(conn, run_id)`** — projection.py:19-62
- pre: joins `runs r ON r.corpus_id = pe.corpus_id`, filters `r.run_id = %s AND pe.status = 'READY'` — projection.py:22-28.
- post: ≤ 2 rows per enrichment — kind `latent_abstraction` uses `pe.abstraction`; kind `latent_transfer` uses joined `"Mechanisms: … Useful for: … Answers: …"`; a kind is emitted only when its text is non-empty — projection.py:39-57.

**`stale_point_ids(conn, corpus_id)`** — projection.py:65-77
- post: `(enrichment_id, latent_point_id(eid, kind))` pairs for every `status='STALE'` row, both kinds.

**`latent_rescue_parents(...)`** — rescue.py:41-89
- in: `plan` knobs via getattr: `latent_budget_ms` (default `250`), `latent_abstraction_top_k` / `latent_transfer_top_k` (default `8`), `latent_max_parents` (default `3`) — rescue.py:51, 55-58, 87.
- effect: two payload-filtered searches `{"representation_kind": kind, "corpus_id": corpus_id}` with the same `qvec`, collapsed by `parent_id` — rescue.py:53-63.
- post: parents sorted by `(-best_score, parent_id)`, truncated to `latent_max_parents` — rescue.py:85-88.

**`mint_parent_enrichment(...)`** — trigger.py:17-45
- out: `ticket_id = "tkt_" + content_hash({"run": run_id, "stage": "parent_enrichment"})[:40]`; upsert re-arms ticket (`status='ready', lease_owner=NULL, lease_expires_at=NULL`); outbox event with `idempotency_key = f"enrich:{run_id}:{doc_id or '*'}"`; returns `{"run_id", "ticket_id", "scope": doc_id or "corpus"}` — trigger.py:22-45.

**Prompt constants** — `COMPILER_CONTRACT = "parent-enrichment-v1"` contract.py:9; `LATENT_KINDS = ("latent_abstraction", "latent_transfer")` contract.py:10; `PROMPT_VERSION = "parent-enrichment-prompt-v1"` prompt.py:10; `MINIMAL_PROMPT_VERSION = "parent-enrichment-minimal-prompt-v1"` prompt.py:43; `MICROBATCH_PROMPT_VERSION = "parent-enrichment-microbatch-v1"` prompt.py:58; `ARRIVAL_LATENT_RESCUE = "LATENT_RESCUE"` rescue.py:19.

## effect surface
- Postgres read: `chunks` (runtime.py:60, 70), `documents` (projection.py:23), `parent_enrichments` (projection.py:22, 68; runtime.py:58-62), `runs` (projection.py:22).
- Postgres write: `parent_enrichments` (DELETE runtime.py:68; UPDATE→STALE runtime.py:84-88; INSERT/UPSERT runtime.py:89-121, 123-141), `stage_tickets` (trigger.py:24-31), `outbox_events` (trigger.py:37-42). FACTS.tables_written also lists `set` — the SQL `SET` keyword misparsed as a table [INFERRED].
- Vector store: no direct client; rescue queries the routing collection through the injected `routing_search("", qvec, {...})` — rescue.py:62-63; projection rows are destined for the existing routing collection (projection.py:2-4), written by the projector importer `workers/workers/project_qdrant_worker.py` [INFERRED from FACTS.importers].
- No files, subprocesses, or env flags read.

## invariants
INVARIANT: point id == `enrichment_id + ":" + kind`, kind ∈ {`latent_abstraction`, `latent_transfer`} — projection.py:15-16, 71-76 [DERIVED]
  fails-if: `latent_rows` and `stale_point_ids` disagree on the format → projector leaves stale points or deletes live ones.
INVARIANT: routing points per READY enrichment ≤ 2; a kind is skipped when its text is empty — projection.py:46-50 [DERIVED]
  fails-if: an enrichment with no mechanisms/affordances/questions yields only the abstraction point; code assuming 2 points creates dead vectors.
INVARIANT: contract id = `COMPILER_CONTRACT` + 10 shape fields, excludes provider/model and `max_tokens` — runtime.py:18-33 [DERIVED]
  fails-if: hashing the lane re-sharded everything (measured 2026-09-02: 1,309 rows/day for 1,374 parents) — runtime.py:20-22.
INVARIANT: same (`source_hash`, prompt hash, contract id) ⇒ same `input_hash` ⇒ same `enrichment_id` — runtime.py:40-42, 77 [DERIVED]
  fails-if: a transient 429 retry could not upgrade the same content-addressed row in place — runtime.py:72-75.
INVARIANT: EXISTING is returned only when the prior READY row's parent chunk still exists in `chunks` — runtime.py:58-65 [DERIVED]
  fails-if: orphan answers EXISTING and its gists point at dead child ids (measured 2026-09-05: 184 rows landed 3 min after delete, 922 orphans) — runtime.py:51-57.
INVARIANT: rescue defaults `latent_budget_ms=250`, per-kind `top_k=8`, `latent_max_parents=3` — rescue.py:51, 55-58, 87 [DERIVED]
  fails-if: plan without these attrs silently falls back to the defaults.
INVARIANT: `gist_coverage_floor = 0.8`; coverage = covered_refs / sent_refs — contract.py:33, 62 [DERIVED]
  fails-if: gate (importer `latent/gate.py`) accepts under-covered output as fully valid.
INVARIANT: QUALIFICATION `max_tokens=700` < PRODUCTION `max_tokens=900`, and both share one contract id — contract.py:30, 36-37; runtime.py:25-28 [DERIVED]
  fails-if: moving `max_tokens` into the contract id re-enriches a corpus on profile switch.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.monotonic` rescue.py:48; routing-search scores rescue.py:62-63; DB reads/writes runtime.py:45-143, trigger.py:24-42). Pure: prompt renderers, `prompt_hash` (prompt.py:27-40, 77-86), `enrichment_contract_id`/`input_hash_for` (runtime.py:17-42), `latent_point_id` (projection.py:15-16).
idempotency: SAFE — `persist_compiled_parent` is idempotent on `input_hash` (runtime.py:48-49) with upserts gated `WHERE parent_enrichments.status='INVALID'` (runtime.py:98, 129); `mint_parent_enrichment` re-mint re-arms the ticket and re-opens the event (trigger.py:29-31, 40-41).

## failure behaviour
- rescue.py:82 swallows every `Exception` → `LatentRescue(parents=[], degraded=f"{type(exc).__name__}", ...)` — caller sees empty parents plus the exception class name, never a raise — rescue.py:82-84 (FACTS.fallbacks).
- Budget overrun between the two kind lanes → `degraded="budget_exceeded"` — rescue.py:59-61.
- `persist_compiled_parent` raises nothing visible; failures persist as rows `status='INVALID'` carrying `error_class` — runtime.py:123-143.

## dumb-code flags
- Budget check sits at the top of a 2-iteration kind loop; one slow `routing_search` call runs unchecked past the 250 ms budget — rescue.py:59-63 [INFERRED].
- Ticket re-mint unconditionally clears `lease_owner`/`lease_expires_at`, silently stealing any live lease — trigger.py:29-31 [INFERRED].
- `MINIMAL_PROMPT_VERSION`/`MINIMAL_SYSTEM_PROMPT` (prompt.py:43-55), `MICROBATCH_*` (prompt.py:58-74), and `render_microbatch_input` (prompt.py:77-86) have no importer in FACTS.imports (only `PROMPT_VERSION`, `prompt_hash` are listed) — dead here or imported by an uncaptured style [INFERRED].
- `latent_rows` tolerates `mechanisms`/`affordances`/`questions` as either list or JSON string — dual encoding accepted at read — projection.py:36-38 [DERIVED].
- `LatentParent.need` stays `""` when the best hit carries no payload text; only a strictly higher-scoring non-empty hit replaces it — rescue.py:70-79, 29-31 [DERIVED].
- FACTS.tables_written contains `set` — static-analysis artifact of the SQL keyword, not a table [INFERRED].

## refactor notes
- `enrichment_contract_id` must stay byte-identical to `scripts/migrate_enrichment_identity.py` — runtime.py:23-24 [DERIVED].
- Point-id format and kind literals are the store-key contract with the projector (`workers/workers/project_qdrant_worker.py`, FACTS.importers); changing them orphans points in the routing collection — projection.py:15-16, 65-77 [INFERRED].
- Status lifecycle `'READY'`/`'STALE'`/`'INVALID'` spans projection.py:24, 67, runtime.py:62, 85, 111, 126 and the projector's STALE→INVALID flip (projection.py:66-68, runtime.py:4-6) — renaming requires a coordinated migration [DERIVED].
- Microbatch per-item ordinals (`[{i}] {text}` inside each ITEM block) are the isolation contract the model's "child ref" rule depends on — prompt.py:72-73, 80-83 [DERIVED].
- Blast radius: 12 importer files (FACTS.importers), including the control scheduler, three orchestrator APIs, and three workers.

## VERIFY
```verify
grep -Fq 'COMPILER_CONTRACT = "parent-enrichment-v1"' shared/polymath_shared/latent/contract.py
grep -Fq 'return f"{enrichment_id}:{kind}"' shared/polymath_shared/latent/projection.py
grep -Fq 'gist_coverage_floor: float = 0.8' shared/polymath_shared/latent/contract.py
grep -Fq 'degraded="budget_exceeded"' shared/polymath_shared/latent/rescue.py
! grep -Fq 'import random' shared/polymath_shared/latent/runtime.py
test "$(grep -c -F 'parent_enrichments' shared/polymath_shared/latent/runtime.py)" -ge 4
```
