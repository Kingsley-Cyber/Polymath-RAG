# unit: shared/polymath_shared/execution.py
anchor: shared/polymath_shared/execution.py:1-322

## purpose
Worker identity and lease fence for CONTROL-PLANE-V2 (ADR-0014): workers advertise WHO they are (build SHA + contract versions), runs pin WHAT they require (execution contract), and `compatible()` refuses an incompatible or stale worker instead of silently serving it — shared/polymath_shared/execution.py:1-7 [DERIVED].
Also pins the semantic-authority surface (PRODUCTION-WIRING-GATE S2): same source + same pinned bundle must reproduce the same identities and facts — shared/polymath_shared/execution.py:43-52 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| semantic_authorities | def | () -> dict[str, Any] | shared/polymath_shared/execution.py:43-99 | — |
| semantic_authority_sha256 | def | () -> str | shared/polymath_shared/execution.py:133-150 | — |
| semantic_bundle_sha256 | def | () -> str | shared/polymath_shared/execution.py:153-159 | — |
| worker_contracts | def | () -> dict[str, Any] | shared/polymath_shared/execution.py:162-188 | — |
| worker_identity | def | (worker_type: str) -> dict[str, Any] | shared/polymath_shared/execution.py:196-214 | — |
| register_worker | def | (conn: Connection, identity: dict[str, Any]) -> None | shared/polymath_shared/execution.py:217-254 | — |
| heartbeat | def | (conn, worker_id, *, current_ticket=_TICKET_UNSET, processed_count=None, last_error=None) -> None | shared/polymath_shared/execution.py:265-268 | — |
| compatible | def | (worker_contracts: dict, execution_contract: dict) -> bool | shared/polymath_shared/execution.py:291-292 | — |
| default_execution_contract | def | () -> dict[str, Any] | shared/polymath_shared/execution.py:317-317 | — |
| STALE_AFTER_S | const | 90.0 | shared/polymath_shared/execution.py:19-19 | — |
| SEMANTIC_CONTRACT_V1_1 | const | "admission-v1.1" | shared/polymath_shared/execution.py:39-39 | — |
| SEMANTIC_CONTRACT_V2 | const | "admission-harbor-v2" | shared/polymath_shared/execution.py:40-40 | — |
| _SEMANTIC_AUTHORITY_MODULES | const | 10-name tuple | shared/polymath_shared/execution.py:105-116 | — |
| _TICKET_UNSET | const | object() sentinel | shared/polymath_shared/execution.py:262-262 | — |

Module importers (FACTS.importers, per-module not per-symbol): control/control/_small-modules, control/control/reconciliation.py, control/control/tickets.py, shared/polymath_shared/admission_interpreter.py, shared/polymath_shared/execution_bundle.py, shared/polymath_shared/observability.py, shared/polymath_shared/worker_runtime.py, workers/workers/adapter_step_worker.py — FACTS.importers [DERIVED].

## contracts

**semantic_authorities()** — shared/polymath_shared/execution.py:43-99
- out: dict with `semantic_contract` = `SEMANTIC_CONTRACT_V2` (71), 11 contract/policy fields incl. `identity_precision_contract`, `entity_harbor_contract`, `discourse_reference_policy_sha256` (72-83), `authority_code_sha256` (90), `graph_eligibility_contract` = HARBOR_CONTRACT (93), `canonical_fact_gate_contract` = HARBOR_CONTRACT (94).
- pre: the 8 authority modules + settings importable (54-67); the 10 authority `.py` files readable (124-130).
- post: no `syntax_model` key is present in the returned dict (71-99).

**semantic_authority_sha256()** — shared/polymath_shared/execution.py:133-150
- out: sha256 of `json.dumps(surface, sort_keys=True, default=str)` where surface = `semantic_authorities()` minus key `syntax_model` (147-150).
- post: excludes probed/live values from the claim gate by design (137-143).

**semantic_bundle_sha256()** — shared/polymath_shared/execution.py:153-159
- out: sha256 over the FULL `semantic_authorities()` surface, same json canonicalization (158-159).

**worker_contracts()** — shared/polymath_shared/execution.py:162-188
- out keys: `query_policy` = `active_policy_version()` (172), `chunker` = `s.worker.chunker` (173), `semantic_bundle` = `semantic_authority_sha256()` (177), `ontology_file_sha` = `files["scientific-predicate-ontology-v2.yaml"]` (182), `extraction_gate` = `f"{GATE_VERSION}/{attestation_policy()}"` (187, 191-193).
- out: no `build_sha` key (171-188).

**worker_identity(worker_type)** — shared/polymath_shared/execution.py:196-214
- out: `worker_id` = `f"{worker_type}-{os.getpid()}-{uuid.uuid4().hex[:8]}"` (204), `host` = `socket.gethostname()` (207), `build_sha` = `_build_sha()` (208, top-level, NOT inside `contracts`), `contracts` = `worker_contracts()` (209), `started_at` = `time.time()` (210), `execution_bundle` + `execution_bundle_id` (212-213).

**register_worker(conn, identity)** — shared/polymath_shared/execution.py:217-254
- pre: identity shaped like `worker_identity()` output.
- post: execution_bundles row upserted `ON CONFLICT (bundle_hash) DO UPDATE SET last_seen_at = now()` (221-227); worker_registrations row upserted `ON CONFLICT (worker_id)` with `status = 'healthy'` (237-249).
- side: `tree_dirty` compared as string `== "True"` (232).

**heartbeat(...)** — shared/polymath_shared/execution.py:265-288
- in: `processed_count` is a DELTA (pass 1 per completed ticket), not absolute (271-273).
- post: `heartbeat_at = now()` (280); `status` revived `'stale'` -> `'healthy'` (281); `current_ticket` rewritten only when arg is not `_TICKET_UNSET` (275-276, 282); `processed_count = processed_count + COALESCE(%s, 0)` (283); `last_error` overwritten (284).

**compatible(worker_contracts, execution_contract)** — shared/polymath_shared/execution.py:291-314
- out False if: `worker_build` pinned and `worker_contracts["build_sha"]` differs (297-299); `semantic_bundle` pinned (not None) and differs (306-308); `query_policy` or `chunker` pinned and differs (309-312).
- out True otherwise; unspecified run requirements pass (296, 314).

**default_execution_contract()** — shared/polymath_shared/execution.py:317-321
- out: `dict(worker_contracts())` — fleet's CURRENT config captured by the control plane at ticket creation, not by the worker (318-320).

## effect surface
- Postgres writes: `execution_bundles` (INSERT upsert, 221-236), `worker_registrations` (INSERT upsert 237-254; UPDATE 277-288). Reads: none in this file (FACTS.tables_read = []).
- Subprocess: `git rev-parse --short HEAD`, `timeout=5`, `cwd=repo_root` (30-33).
- Files: reads 10 authority module sources `here/{name}.py` via `read_bytes` (124-130).
- Env: `POLYMATH_BUILD_SHA` = `''` default (24).
- Host info: `socket.gethostname()` (207). No Qdrant, no network calls.

## invariants
INVARIANT: STALE_AFTER_S == 90.0 ("~3 control ticks + margin") — shared/polymath_shared/execution.py:19-19 [DERIVED]
  fails-if: staleness window drifts from control-tick cadence; workers marked stale too early/late.
INVARIANT: heartbeat processed_count applied as delta `processed_count + COALESCE(%s, 0)` — shared/polymath_shared/execution.py:283-283 [DERIVED]
  fails-if: absolute assignment resets every worker to a lifetime count of 1 (the old bug, 271-273).
INVARIANT: current_ticket untouched unless caller passes a value; `_TICKET_UNSET` distinguishes "leave alone" from explicit None — shared/polymath_shared/execution.py:262-262, 275-276 [DERIVED]
  fails-if: idle workers keep advertising their last ticket and look mid-stage (measured in STALL-2026-08-27, 258-261).
INVARIANT: compatible() returns False when execution_contract `semantic_bundle` is not None and differs — shared/polymath_shared/execution.py:306-308 [DERIVED]
  fails-if: semantic cutover becomes silently mixed across the fleet (301-303).
INVARIANT: _authority_code_sha256 hashes name + b"\x00" + sha256(file bytes) for all 10 modules in fixed tuple order — shared/polymath_shared/execution.py:105-116, 126-130 [DERIVED]
  fails-if: an authority edited without a version bump stops changing the advertised bundle (84-89).
INVARIANT: `graph_eligibility_contract` == `canonical_fact_gate_contract` == HARBOR_CONTRACT, named separately for a future split — shared/polymath_shared/execution.py:93-94, 91-92 [DERIVED]
  fails-if: eligibility and fact gate drift apart invisibly when Harbor is split.

## determinism & idempotency
determinism: NONDETERMINISTIC (uuid4 in worker_id 204; time.time 210; git subprocess 30; env POLYMATH_BUILD_SHA 24; DB writes 221-254, 277-288; working-tree file contents fed into hashes 129-130; socket.gethostname 207). The hash functions themselves are pure given fixed inputs: 126-130, 147-150, 158-159.
idempotency: register_worker SAFE (both writes are upserts, 227, 243); heartbeat UNSAFE for `processed_count` (a retried call re-applies the delta, 283), SAFE for heartbeat_at/status/ticket.

## failure behaviour
- `_build_sha` swallows every Exception and returns `"unknown"` (35-36); git failure (`returncode != 0`) also yields `"unknown"` (34). Caller then sees build_sha `"unknown"`, which can never equal a pinned `worker_build` — shared/polymath_shared/execution.py:34-36 [DERIVED]; consequence for leasing [INFERRED: 297-299 compares for equality].
- No other broad handlers in this file (FACTS.fallbacks lists only this one).

## dumb-code flags
- Dead filter: `semantic_authority_sha256` strips key `syntax_model` (147-149), but `semantic_authorities()` returns no `syntax_model` key (71-99) — the filter is a no-op today. [INFERRED: both sides visible, filter matches nothing]
- Contradictory comments: 95-98 say syntax is a HARD dependency of V2 and promise a spaCy-contract pin (no such dict entry exists, 71-99); 313 says S3 syntax claim-eligibility was retired with the spaCy sidecar (ADR-0017). One of the two is stale. [DERIVED for both comments; INFERRED contradiction]
- `compatible()` reads `worker_contracts.get("build_sha")` (298), but `worker_contracts()` emits no `build_sha` key (171-188) and `worker_identity` puts build_sha outside `contracts` (208-209); `default_execution_contract()` pins no `worker_build` (317-321) — the build fence only fires if a submitter hand-adds `worker_build`. [INFERRED: all values visible, wiring gap]
- `compatible()` never checks `ontology_file_sha` or `extraction_gate` (297-312), though both are pinned by `worker_contracts()`/`default_execution_contract()` (182, 187) — drift there must be caught by contract reconciliation, not the lease. [INFERRED]
- `SEMANTIC_CONTRACT_V1_1` = `"admission-v1.1"` (39) is unreferenced elsewhere in this file. [DERIVED in-file; external use unknown]
- String-boolean compare: `bundle.get("tree_dirty") == "True"` (232).
- Duplicated literals: `"unknown"` at 34 and 36; `'healthy'` at 242, 247, 281; `'stale'` at 281; HARBOR_CONTRACT aliased into 3 keys (73, 93, 94).
- FACTS.tables_written includes `"set"` — that is the SQL keyword from `UPDATE ... SET` (279), not a table; parser artifact. [INFERRED]

## refactor notes
- 8 importers depend on this module (FACTS.importers): control/control/_small-modules, control/control/reconciliation.py, control/control/tickets.py, shared/polymath_shared/admission_interpreter.py, shared/polymath_shared/execution_bundle.py, shared/polymath_shared/observability.py, shared/polymath_shared/worker_runtime.py, workers/workers/adapter_step_worker.py — changing `worker_contracts()` keys or `compatible()` semantics hits all of them.
- `register_worker` persists `json.dumps(identity["contracts"])` (253): any key change in `worker_contracts()` changes the stored shape AND every worker's `semantic_bundle`/hash, i.e. a fleet-wide re-claim boundary (105-116, 177).
- `_TICKET_UNSET` sentinel is part of `heartbeat`'s public default; callers rely on "no arg = leave ticket" (262, 275-276).
- Never add a probed/live value (e.g. a sidecar probe) to `semantic_authorities()` — the claim gate is deliberately free of them (137-143).
- Historical runs keep `semantic_contract` NULL and are never rewritten to claim V2 (51-52) — any migration must preserve this.

## VERIFY
```verify
grep -Fq 'STALE_AFTER_S = 90.0' shared/polymath_shared/execution.py
grep -Fq 'admission-harbor-v2' shared/polymath_shared/execution.py
grep -Fq 'processed_count = processed_count + COALESCE(%s, 0)' shared/polymath_shared/execution.py
grep -Fq 'ON CONFLICT (bundle_hash) DO UPDATE SET last_seen_at = now()' shared/polymath_shared/execution.py
! grep -Fq '"syntax_model":' shared/polymath_shared/execution.py
grep -Fq 'scientific-predicate-ontology-v2.yaml' shared/polymath_shared/execution.py
test "$(grep -c -F 'HARBOR_CONTRACT' shared/polymath_shared/execution.py)" -ge 4
```
