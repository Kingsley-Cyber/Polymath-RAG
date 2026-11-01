# unit: shared/polymath_shared/adapter/service.py
anchor: shared/polymath_shared/adapter/service.py:1-1372

## purpose
The adapter-run service: what the orchestrator routes (`adapter_*`) and the step worker calls. Composes the pure core (transitions/manifest/contracts) with the store; each public function runs inside the caller's transaction. shared/polymath_shared/adapter/service.py:1-2 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| now_iso | def | () -> str | shared/polymath_shared/adapter/service.py:50-51 | — |
| registry | def | (directory: Path \| None = None) -> dict[str, Manifest] | shared/polymath_shared/adapter/service.py:59-60 | — |
| reset_registry | def | () -> None | shared/polymath_shared/adapter/service.py:63-64 | — |
| manifest_for | def | (adapter_id: str, directory: Path \| None = None) -> Manifest | shared/polymath_shared/adapter/service.py:67-71 | — |
| list_adapters | def | (directory: Path \| None = None) -> list[dict[str, Any]] | shared/polymath_shared/adapter/service.py:74-83 | — |
| assert_owner | def | (conn, run_id: str, principal_id: str \| None) -> None | shared/polymath_shared/adapter/service.py:92-99 | — |
| start | def | (conn, *, adapter_id, input_payload, request_options=None, directory=None, owner_principal_id=None, corpus_view=None, catalog=None) -> dict[str, Any] | shared/polymath_shared/adapter/service.py:105-140 | — |
| run_ref | def | (conn, run_id: str) -> dict[str, Any] | shared/polymath_shared/adapter/service.py:202-210 | — |
| status | def | (conn, run_id: str, directory=None) -> dict[str, Any] | shared/polymath_shared/adapter/service.py:221-229 | — |
| next_step | def | (conn, run_id: str, directory=None) -> dict[str, Any] | shared/polymath_shared/adapter/service.py:232-251 | — |
| submit | def | (conn, run_id: str, submission: dict, directory=None) -> dict[str, Any] | shared/polymath_shared/adapter/service.py:382-473 | — |
| cancel | def | (conn, run_id, directory, external_cancel) | shared/polymath_shared/adapter/service.py:658-681 | — |
| expire_idle | def | (conn, idle_s, limit) | shared/polymath_shared/adapter/service.py:696-716 | — |
| result | def | (conn, run_id) | shared/polymath_shared/adapter/service.py:719-731 | — |
| advance | def | (conn, run_id, executors, max_steps, directory) | shared/polymath_shared/adapter/service.py:735-757 | — |
| prepare | def | (conn, run_id, executors, directory) | shared/polymath_shared/adapter/service.py:780-790 | — |
| execute | def | (executors, unit) | shared/polymath_shared/adapter/service.py:793-802 | — |
| apply | def | (conn, run_id, unit, outcome, directory) | shared/polymath_shared/adapter/service.py:805-815 | — |
| fail_run | def | (conn, run_id, code, message, directory) | shared/polymath_shared/adapter/service.py:850-875 | — |
| run_prefetch | def | (executors, unit) | shared/polymath_shared/adapter/service.py:1066-1078 | — |
| apply_prefetch | def | (conn, run_id, unit, result, directory) | shared/polymath_shared/adapter/service.py:1081-1109 | — |
| UnknownAdapter | class | KeyError | shared/polymath_shared/adapter/service.py:38-39 | — |
| UnknownRun | class | KeyError | shared/polymath_shared/adapter/service.py:42-43 | — |
| NotTerminal | class | RuntimeError | shared/polymath_shared/adapter/service.py:46-47 | — |
| NotRunOwner | class | Exception | shared/polymath_shared/adapter/service.py:87-89 | — |
| LeaseLost | class | — | shared/polymath_shared/adapter/service.py:760-762 | — |
| Unit | class | step unit between phases (F7) | shared/polymath_shared/adapter/service.py:766-777 | — |

Module imported by (FACTS, per-module not per-symbol): orchestrator/orchestrator/api/acquisition.py, orchestrator/orchestrator/api/adapter.py, orchestrator/orchestrator/api/web_settings.py, shared/polymath_shared/adapter/run_view.py, workers/workers/adapter_step_worker.py.

## contracts

**start** — shared/polymath_shared/adapter/service.py:105-140
- pre: adapter_id resolves in registry, else `UnknownAdapter` (:117 via :67-71).
- in: payload validated by `assert_valid("adapter_run_request", {"adapter_id", "input", "request_options"})` (:119).
- idem: with `request_options.idempotency_key`, key becomes `f"{key}@{owner_principal_id}"` (:122); store lookup on `f"{adapter_id}:{key}"` (:124) returns the existing run's ref+receipt (:126).
- out: `run_id = "adr_" + hashlib.sha256(seed.encode()).hexdigest()[:32]`, seed `f"{adapter_id}:{key}"` or `f"{adapter_id}:{uuid.uuid4()}"` (:127-128); response = AdapterRunRefV1 with `start_receipt` beside it, never inside (:143-148).
- raises: `CS.StartRefused` typed (code/message/hint), e.g. `"SEED_UNAVAILABLE"` when no seed and no corpus in scope (:173-174).

**assert_owner** — shared/polymath_shared/adapter/service.py:92-99
- pre: `principal_id is None` = legacy trusted caller, returns immediately (:95-96).
- post: run missing OR `owner != principal_id` -> `NotRunOwner`; a NULL owner is legacy state, never "public" (:93-99).

**next_step** — shared/polymath_shared/adapter/service.py:232-251
- out: status `awaiting_agent`/`awaiting_harness` + issued row -> `{"kind": "step", "step", "status", "evidence", [materials], ...beside, [last_rejection]}` (:240-250); otherwise `{"kind": "status", "status"}` (:251).
- `evidence` = READABLE rows for exactly `step.context.evidence_refs`, ids stay the citation contract (:234-235).

**submit** — shared/polymath_shared/adapter/service.py:382-473
- pre: run exists else `UnknownRun` (:384-386); an issued step exists else `SubmissionRejected(["no step has been issued"])` (:389-391).
- in: defaults `submitted_at = now_iso()`, `submission_hash = stable_hash(payload)` (:394-395).
- post (reject): step stays `issued`, rejection receipt on the row, `_touch` marks activity, `SubmissionRejected` raised (:407-412).
- post (AGENT_REASON): law runs at submit via `_law_at_submit`; errors -> rejected + `branch_loops + 1` saved (:418-423).
- post (HARNESS_ACTION): oversized receipt -> rejected, step stays open (:427-432); accepted -> `store.record_receipt(..., stable_hash(rec))` (:433-434).
- error: `ManifestError` (not `ManifestInvalid`) -> `SubmissionRejected(["MANIFEST_VERSION_UNAVAILABLE: ..."])`, run stays parked (:400-405).

**prepare / execute / apply** — shared/polymath_shared/adapter/service.py:780-815
- prepare: phase 1 under the run's row lock — issue next step or find the issued one (:780-790).
- execute: phase 2 OUTSIDE any transaction — returns `{"ok": outcome}` or `{"raised": "Type: message"}` (:793-802).
- apply: phase 3 under the row lock again — records outcome only if the run still stands at THIS issued step (:805-815).

**expire_idle** — shared/polymath_shared/adapter/service.py:696-716
- every run `awaiting_agent`/`awaiting_harness` with no activity for `idle_s` seconds ends typed (F8).

**fail_run** — shared/polymath_shared/adapter/service.py:850-875
- durable typed failure for a run whose step could not complete as one lawful unit (M1-04; bug hunt B-02/B-06).

## effect surface
- Postgres: all DB access via `store.*` on the caller's `conn` — `run_owner` (:97), `find_run_by_idempotency` (:124), `insert_run` (:136), `set_run_owner` (:139), `load_run` (:146, :203, :266, :310, :384), `current_step` (:238, :389), `finish_step` (:410, :421, :430), `save_state` (:422), `record_receipt` (:434), `list_steps` (:342, :376), `current_hypotheses` (:343). No table names in this unit (FACTS `tables_read`/`tables_written` empty).
- Collections (FACTS): `polymath_evidence_ids` appears at shared/polymath_shared/adapter/service.py:921 and shared/polymath_shared/adapter/service.py:1358.
- Files: adapter manifests via `list_manifests(Path(directory))` (:56); default dir `ADAPTER_DIR` (:60); registry cached `@lru_cache(maxsize=4)` keyed by directory string (:54-55).
- Env: `POLYMATH_ADAPTER_IDLE_EXPIRY_S` = `str(24 * 3600)` default, read at shared/polymath_shared/adapter/service.py:693.
- External: `DOMAIN.run` in the start-time seed check (:189); `trail_client` imported (:18).
- Non-determinism: `uuid.uuid4` (:127), `_dt.datetime.now` (:51).

## invariants
INVARIANT: sum(CONTEXT_BUDGET.values()) 80+50+40+30 = 200 = MAX_CONTEXT_REFS — shared/polymath_shared/adapter/service.py:27,31 [DERIVED]
  fails-if: display floors over- or under-subscribe the citation budget; unused-spill arithmetic breaks.
INVARIANT: STEP_CONTEXT_MAX_REFS = 500 > MAX_CONTEXT_REFS = 200 — shared/polymath_shared/adapter/service.py:1118,27 [DERIVED]
  fails-if: the two caps are conflated; the whole-run-citing step (Gap A-12) loses its larger budget.
INVARIANT: idempotency key stored as f"{adapter_id}:{key}" at both lookup and insert — shared/polymath_shared/adapter/service.py:124,136 [DERIVED]
  fails-if: lookup/insert formats diverge -> duplicate runs per key.
INVARIANT: owner-scoped key = f"{key}@{owner_principal_id}" — shared/polymath_shared/adapter/service.py:122 [DERIVED]
  fails-if: one principal's idempotency key returns another principal's run.
INVARIANT: run_id prefix "adr_", body sha256 hex[:32] — shared/polymath_shared/adapter/service.py:128 [DERIVED]
  fails-if: downstream id parsers expecting the 4+32 shape break.
INVARIANT: `last_rejection` errors truncated to [:40] — shared/polymath_shared/adapter/service.py:249 [DERIVED]
  fails-if: an oversized refusal floods the next_step reply.
INVARIANT: beside payload ≤ BESIDE_MAX_BYTES = 800_000; materials ≤ MATERIALS_MAX_BYTES = 400_000 — shared/polymath_shared/adapter/service.py:256,299 [DERIVED]
  fails-if: sibling keys blow the wire size the agent must read.

## determinism & idempotency
determinism: NONDETERMINISTIC (uuid.uuid4 seed when no idempotency key — :127; wall clock in now_iso — :51; lru_cache over the manifest directory — :54-55; DOMAIN.run — :189) [DERIVED]
idempotency: start SAFE when `request_options.idempotency_key` is set (existing run returned :124-126); UNSAFE without it (uuid seed :127 -> new run each call). cancel documented "terminal, idempotent" :658-660. submit UNSAFE — each accepted submission transitions state; rejected submissions receipt on the row and leave the step issued (:409-410).

## failure behaviour
| site | swallowed -> caller sees | anchor |
|---|---|---|
| _beside manifest read | `return {}` | shared/polymath_shared/adapter/service.py:268 |
| _beside outer | `{"beside_error": "Type: msg"[:500]}` | shared/polymath_shared/adapter/service.py:294 |
| _materials opt-in read | `return None` (no key at all) | shared/polymath_shared/adapter/service.py:313 |
| _materials outer | `{"values": {}, "missing": [], "too_large": [], "error": ...[:500]}` | shared/polymath_shared/adapter/service.py:335 |
| _readable_evidence | `{"rows": [], "receipts": [], "error": ...[:500]}` | shared/polymath_shared/adapter/service.py:378 |
| execute phase 2 | `{"raised": "Type: message"}` | shared/polymath_shared/adapter/service.py:801 |
| run_prefetch | `{"error": "Type: msg"}` | shared/polymath_shared/adapter/service.py:1077 |

Raised codes: `UnknownAdapter` (:71), `UnknownRun` (:205, :386), `NotTerminal` (:46), `NotRunOwner` (:99), `SubmissionRejected` (:391, :405, :412, :423, :432), `CS.StartRefused` codes `"SEED_UNAVAILABLE"` (:173) and seed-check codes e.g. `"SEED_NOT_GENERATIVE"` (:196), `HypothesisRejected` (imported :19), `LeaseLost` (:760).

## dumb-code flags
- `f"{adapter_id}:{key}"` built twice (:124, :136) — one literal drifts, idempotency breaks.
- Class names duplicated across three literals: `_context_class` check (:35), `CONTEXT_CLASS_ORDER` (:28), `CONTEXT_BUDGET` keys (:31); `chunk`/`graph_fact` also in `KNOWLEDGE_KINDS` (:26).
- Two sibling caps with different magnitudes: 800_000 beside (:256) vs 400_000 materials (:299); no shared constant.
- Error truncation lengths differ: [:500] (:191, :294, :335, :378) vs [:40] (:249).
- `@lru_cache(maxsize=4)` on manifests requires `reset_registry()` after a redeploy, or stale manifests are served — inferred from cache mechanics (:54-64). [INFERRED]

## refactor notes
- Adding any new reply key to `next_step` output must also update `RESERVED_BESIDE` (:255), or a manifest `config.beside` could shadow it (:254-255, :278-279).
- Start receipt travels beside the ref, never inside AdapterRunRefV1 (:144, :115) — orchestrator API consumers depend on that separation.
- `evidence`, `materials`, beside keys are SIBLINGs of the step; AdapterStepV1 and citation rules must stay unchanged (:234-235, :304-305).
- The three-phase advance (prepare/execute/apply) plus `LeaseLost` (:760-762) is the worker contract; blast radius = workers/workers/adapter_step_worker.py and the orchestrator API importers.
- `CONTEXT_BUDGET` floors are tied to `MAX_CONTEXT_REFS` by sum — change together (:27, :31).
- The owner-namespaced idempotency format `f"{key}@{owner_principal_id}"` (:122) is persisted through `find_run_by_idempotency` (:124); changing it orphans existing runs.

## VERIFY
```verify
grep -Fq 'MAX_CONTEXT_REFS = 200' shared/polymath_shared/adapter/service.py
grep -Fq 'CONTEXT_BUDGET = {"field_evidence": 80, "chunk": 50, "graph_fact": 40, "other": 30}' shared/polymath_shared/adapter/service.py
grep -Fq 'run_id = "adr_" + hashlib.sha256(seed.encode()).hexdigest()[:32]' shared/polymath_shared/adapter/service.py
grep -Fq 'key = f"{key}@{owner_principal_id}"' shared/polymath_shared/adapter/service.py
grep -Fq 'RESERVED_BESIDE = frozenset({"kind", "step", "status", "evidence", "materials", "last_rejection"})' shared/polymath_shared/adapter/service.py
grep -Fq 'BESIDE_MAX_BYTES = 800_000' shared/polymath_shared/adapter/service.py
grep -Eq 'STEP_CONTEXT_MAX_REFS *= *500' shared/polymath_shared/adapter/service.py
test "$(grep -c -F 'polymath_evidence_ids' shared/polymath_shared/adapter/service.py)" -ge 2
```
