# unit: shared/polymath_shared/adapter/_small-modules
anchor: shared/polymath_shared/adapter/__init__.py:1-16

## purpose
Package root of COGNITIVE-ADAPTER-V1 (ADR-0018): "the pure, I/O-free core of the Polymath cognitive-adapter runtime" — manifests, JSON-Schema validation against `contracts/adapter/v1`, the CLOSED step vocabulary, run/step transition rules. — shared/polymath_shared/adapter/__init__.py:1-6 [DERIVED]
`contracts.py` holds contract access (schema loading, validation, canonical hashing, "Pure.") plus the ADR-0019 closed vocabulary constants. — shared/polymath_shared/adapter/contracts.py:1, shared/polymath_shared/adapter/contracts.py:23-31 [DERIVED]
Callers: the orchestrator (MCP tools) and the adapter step worker compose these with Postgres receipts/outbox/lease primitives. — shared/polymath_shared/adapter/__init__.py:5-6 [DERIVED]

## public surface
Direct importers of `contracts.py` (14, from FACTS.importers): mcp_server/polymath_mcp.py; orchestrator/orchestrator/api/acquisition.py, adapter.py, web_settings.py; orchestrator/orchestrator/mcp_server.py; shared/polymath_shared/adapter/{dossier,hypotheses,manifest,research_gaps,run_view,semantic_view,service,transitions}.py; workers/workers/adapter_step_worker.py.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| schema | function | (name: str) -> dict[str, Any] | shared/polymath_shared/adapter/contracts.py:54-59 | FACTS.imports; re-exported shared/polymath_shared/adapter/__init__.py:8-9 |
| validate | function | (name: str, instance: Any) -> list[str] | shared/polymath_shared/adapter/contracts.py:67-70 | FACTS.imports; shared/polymath_shared/adapter/__init__.py:8 |
| assert_valid | function | (name: str, instance: Any) -> None | shared/polymath_shared/adapter/contracts.py:73-76 | FACTS.imports; shared/polymath_shared/adapter/__init__.py:9 |
| bounded_text | function | (text: Any, limit: int) -> str | shared/polymath_shared/adapter/contracts.py:79-88 | — (absent from FACTS.imports and from re-exports shared/polymath_shared/adapter/__init__.py:8-9) |
| stable_hash | function | (obj: Any) -> str | shared/polymath_shared/adapter/contracts.py:91-93 | FACTS.imports; shared/polymath_shared/adapter/__init__.py:9 |
| ContractViolation | class(ValueError) | __init__(name: str, errors: list[str]) -> None | shared/polymath_shared/adapter/contracts.py:45-51 | FACTS.imports; shared/polymath_shared/adapter/__init__.py:9 |
| _validator | function (private) | (name: str) -> jsonschema.Draft202012Validator | shared/polymath_shared/adapter/contracts.py:62-64 | internal only |

Closed vocabulary constants:

| constant | literal value | anchor | used by |
|---|---|---|---|
| STEP_TYPES | ("POLYMATH_RETRIEVE", "POLYMATH_COMPILE_PLAN", "POLYMATH_GRAPH_EXPAND", "EXTERNAL_OPERATION", "DOMAIN_OPERATION", "AGENT_REASON", "HARNESS_ACTION", "VALIDATE", "BRANCH", "COMPILE_RESULT") | shared/polymath_shared/adapter/contracts.py:16-17 | FACTS.imports; shared/polymath_shared/adapter/__init__.py:8 |
| AGENT_ANSWERED_STEP_TYPES | frozenset({"AGENT_REASON", "HARNESS_ACTION"}) | shared/polymath_shared/adapter/contracts.py:20 | — |
| AUTOMATIC_STEP_TYPES | frozenset(STEP_TYPES) - AGENT_ANSWERED_STEP_TYPES | shared/polymath_shared/adapter/contracts.py:21 | — |
| RUN_STATUSES | ("created", "running", "awaiting_agent", "awaiting_harness", "completed", "terminal_gap", "cancelled", "failed") | shared/polymath_shared/adapter/contracts.py:22 | FACTS.imports; shared/polymath_shared/adapter/__init__.py:8 |
| HARNESS_ACTION_KINDS | ("AGENT_RESEARCH", "PRODUCT_REALITY_CHECK", "SUPPLIER_RESEARCH") | shared/polymath_shared/adapter/contracts.py:24 | — |
| THETA_OPS | ("generate_hypotheses", "derive_mechanisms", "cross_map_frictions", "derive_physical_jobs", "derive_analogies", "split_hypotheses", "generate_product_mechanisms") | shared/polymath_shared/adapter/contracts.py:25-26 | — |
| PHI_OPS | ("reject", "merge", "deduplicate", "weaken", "strengthen", "challenge", "require_evidence", "promote") | shared/polymath_shared/adapter/contracts.py:27 | — |
| HYPOTHESIS_STATUSES | ("proposed", "filtered", "retained", "revised", "split", "merged", "weakened", "strengthened", "contradicted", "killed", "promoted") | shared/polymath_shared/adapter/contracts.py:28-29 | — |
| TRANSITION_KINDS | ("GENERATE", "REVISE", "SPLIT", "MERGE", "WEAKEN", "STRENGTHEN", "CONTRADICT", "KILL", "PROMOTE") | shared/polymath_shared/adapter/contracts.py:30 | — |
| TRANSITION_ACTORS | ("theta", "phi", "runtime") | shared/polymath_shared/adapter/contracts.py:31 | — |
| EVIDENCE_ROLE_PATTERN | r"^[a-z][a-z0-9_]{1,40}$" | shared/polymath_shared/adapter/contracts.py:33 | — |
| CITABLE_EVIDENCE_KINDS | frozenset({"chunk", "document", "graph_fact", "graph_hop", "parent_map", "field_evidence"}) | shared/polymath_shared/adapter/contracts.py:35 | — |
| PRIOR_EVIDENCE_KINDS | frozenset({"trail_prior"}) | shared/polymath_shared/adapter/contracts.py:36 | — |
| ORIGIN_ID_FIELDS | ("lead_ids", "latent_structure_ids") | shared/polymath_shared/adapter/contracts.py:40 | — |
| TERMINAL_RUN_STATUSES | frozenset({"completed", "terminal_gap", "cancelled", "failed"}) | shared/polymath_shared/adapter/contracts.py:41 | FACTS.imports; shared/polymath_shared/adapter/__init__.py:8 |
| STEP_STATUSES | ("issued", "accepted", "rejected", "executed", "failed", "skipped") | shared/polymath_shared/adapter/contracts.py:42 | FACTS.imports; shared/polymath_shared/adapter/__init__.py:8 |

## contracts

**schema(name)** — shared/polymath_shared/adapter/contracts.py:54-59
- in: `name: str`; out: parsed dict from `CONTRACT_DIR / f"{name}.schema.json"`.
- pre: schema file exists, else `KeyError(f"unknown adapter contract {name!r}")` — shared/polymath_shared/adapter/contracts.py:56-58.
- post: cached via `@lru_cache(maxsize=None)`; repeat calls return the same object — shared/polymath_shared/adapter/contracts.py:54.

**validate(name, instance)** — shared/polymath_shared/adapter/contracts.py:67-70
- out: `list[str]`; empty list = valid; each entry `"/".join(map(str, e.path)) or "$" + ": " + e.message`.
- post: deterministic order — sorted by `(list(map(str, e.path)), e.message)` — shared/polymath_shared/adapter/contracts.py:69.

**assert_valid(name, instance)** — shared/polymath_shared/adapter/contracts.py:73-76
- out: `None` iff `validate` returned `[]`; otherwise raises `ContractViolation(name, errors)`.

**bounded_text(text, limit)** — shared/polymath_shared/adapter/contracts.py:79-88
- out: whole string when `len(text) <= limit`; else head `keep * 2 // 3`, tail `keep - head`, marker `f" …[+{len(text) - keep} chars elided]… "`.
- post: result length never exceeds `limit` — shared/polymath_shared/adapter/contracts.py:84-88.

**stable_hash(obj)** — shared/polymath_shared/adapter/contracts.py:91-93
- out: sha256 hexdigest over `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`; docstring: "the receipt/submission hash".

**ContractViolation** — shared/polymath_shared/adapter/contracts.py:45-51
- subclass of `ValueError`; message = `f"{name}: " + "; ".join(errors[:5])`; attributes `.name`, `.errors` (full list).

## effect surface
- Files read: `{repo}/contracts/adapter/v1/{name}.schema.json`; repo root = `Path(__file__).resolve().parents[3]` — shared/polymath_shared/adapter/contracts.py:12-14, 56-57.
- In-memory caches: `lru_cache(maxsize=None)` on `schema` and `_validator` — shared/polymath_shared/adapter/contracts.py:54, 62.
- Postgres tables read/written: none — FACTS.tables_read = [], FACTS.tables_written = [].
- Qdrant / network / subprocess / env flags: none — "No database, no HTTP, no provider call lives here" — shared/polymath_shared/adapter/__init__.py:4-5 [DERIVED]

## invariants
INVARIANT: len(bounded_text(text, limit)) <= limit — shared/polymath_shared/adapter/contracts.py:84-88 [INFERRED: `keep` subtracts the marker's longest form `f" …[+{len(text)} chars elided]… "` while the emitted marker uses `len(text) - keep`, so the emitted marker is never longer than assumed]
  fails-if: oversized receipt errors / failure or gap messages would violate the schema maxLength they must fit — shared/polymath_shared/adapter/contracts.py:80-82.
INVARIANT: TERMINAL_RUN_STATUSES ⊆ RUN_STATUSES ({completed, terminal_gap, cancelled, failed} ⊂ the 8-value tuple) — shared/polymath_shared/adapter/contracts.py:22, 41 [DERIVED]
  fails-if: a run could enter a status the run-status contract rejects.
INVARIANT: AGENT_ANSWERED_STEP_TYPES ∪ AUTOMATIC_STEP_TYPES == STEP_TYPES and the two sets are disjoint — shared/polymath_shared/adapter/contracts.py:16-21 [DERIVED]
  fails-if: a step type becomes both agent-answered (via adapter_submit) and runtime-executed, or neither.
INVARIANT: validate(name, instance) == [] ⟺ assert_valid(name, instance) returns normally — shared/polymath_shared/adapter/contracts.py:67-76 [DERIVED]
  fails-if: valid submissions rejected or invalid ones accepted at submission boundaries.
INVARIANT: stable_hash(obj) depends only on canonical JSON (sort_keys=True, separators=(",", ":"), ensure_ascii=False) — shared/polymath_shared/adapter/contracts.py:93 [DERIVED]
  fails-if: equal receipts/submissions hash differently, breaking hash comparison and dedup.
INVARIANT: CITABLE_EVIDENCE_KINDS ∩ PRIOR_EVIDENCE_KINDS = ∅ ("trail_prior is a coordinate, never evidence") — shared/polymath_shared/adapter/contracts.py:34-36 [DERIVED]
  fails-if: a trail_prior coordinate could pass a citation check as evidence.

## determinism & idempotency
determinism: DETERMINISTIC — the only external input is repo-local schema JSON, cached (shared/polymath_shared/adapter/contracts.py:54, 56-57); error order forced by `sorted(...)` (shared/polymath_shared/adapter/contracts.py:69); hash over canonical JSON (shared/polymath_shared/adapter/contracts.py:93); no clock/random/uuid/network/db/env in either file.
idempotency: SAFE — no writes anywhere; caches are read-only and keyed by contract name (shared/polymath_shared/adapter/contracts.py:54, 62).

## failure behaviour
- `schema(name)` raises `KeyError(f"unknown adapter contract {name!r}")` for a missing schema file — shared/polymath_shared/adapter/contracts.py:56-58.
- `assert_valid` raises `ContractViolation` (a ValueError) carrying `.name` and the full `.errors` list — shared/polymath_shared/adapter/contracts.py:45-46, 73-76.
- `validate` never raises on schema mismatch; it returns error strings, root path rendered as `"$"` — shared/polymath_shared/adapter/contracts.py:67-70.
- No try/except or fallback handler exists in either file; nothing is swallowed. — shared/polymath_shared/adapter/__init__.py:1-16, shared/polymath_shared/adapter/contracts.py:1-93 [DERIVED]

## dumb-code flags
- Magic number `5`: message truncation `errors[:5]` — shared/polymath_shared/adapter/contracts.py:49.
- Magic split `head = keep * 2 // 3` (2/3 head, 1/3 tail) — shared/polymath_shared/adapter/contracts.py:87.
- No guard for tiny `limit`: `keep = limit - len(f" …[+{len(text)} chars elided]… ")` can go ≤ 0 and the function still slices — shared/polymath_shared/adapter/contracts.py:86-88 [INFERRED: pure arithmetic, no branch on `keep`]
- EVIDENCE_ROLE_PATTERN `^[a-z][a-z0-9_]{1,40}$` matches 2–41 characters total (1 + up to 40), not 40 — shared/polymath_shared/adapter/contracts.py:33 [DERIVED]
- Repo root computed positionally as `parents[3]`; moving the file silently repoints CONTRACT_DIR — shared/polymath_shared/adapter/contracts.py:12-14 [INFERRED: no existence check on the derived root]
- Unbounded `lru_cache(maxsize=None)` on both `schema` and `_validator` — shared/polymath_shared/adapter/contracts.py:54, 62 [INFERRED: growth bounded only by the number of files in CONTRACT_DIR]
- `bounded_text` has no importer in FACTS.imports and no use inside the unit — shared/polymath_shared/adapter/__init__.py:8-9 [DERIVED]

## refactor notes
- 14 direct importers (FACTS.importers): renaming any of schema / validate / assert_valid / stable_hash / ContractViolation / STEP_TYPES / RUN_STATUSES / STEP_STATUSES / TERMINAL_RUN_STATUSES breaks mcp_server, orchestrator APIs, all sibling adapter modules and workers/workers/adapter_step_worker.py.
- `__all__` is derived from `dir()` — shared/polymath_shared/adapter/__init__.py:15: any new underscore-free name in .contracts / .manifest (line 10) / .transitions (lines 11-13) silently widens the package surface.
- Changing STEP_TYPES or AGENT_ANSWERED_STEP_TYPES silently re-derives AUTOMATIC_STEP_TYPES — shared/polymath_shared/adapter/contracts.py:20-21 — flipping which steps the runtime executes versus which the agent/harness answers.
- bounded_text output must stay within the maxLength values of contracts/adapter/v1; changing the marker format changes worst-case output length — shared/polymath_shared/adapter/contracts.py:80-88.
- Moving contracts.py breaks the `parents[3]` repo-root computation and hence CONTRACT_DIR — shared/polymath_shared/adapter/contracts.py:12-14.
- Vocabulary constants are the engine-side mirror of the "CLOSED step vocabulary" contract set — shared/polymath_shared/adapter/__init__.py:3-4 — edits must be checked against the schema files loaded from CONTRACT_DIR.

## VERIFY
```verify
grep -Fq 'AGENT_ANSWERED_STEP_TYPES = frozenset({"AGENT_REASON", "HARNESS_ACTION"})' shared/polymath_shared/adapter/contracts.py
grep -Fq 'sort_keys=True, separators=(",", ":"), ensure_ascii=False' shared/polymath_shared/adapter/contracts.py
grep -Fq 'head = keep * 2 // 3' shared/polymath_shared/adapter/contracts.py
grep -Fq 'unknown adapter contract' shared/polymath_shared/adapter/contracts.py
grep -Fq '__all__ = [n for n in dir() if not n.startswith("_")]' shared/polymath_shared/adapter/__init__.py
! grep -Fq 'os.environ' shared/polymath_shared/adapter/contracts.py
```
