# unit: shared/polymath_shared/adapter/_small-modules
anchor: shared/polymath_shared/adapter/__init__.py:1-16

## purpose
`__init__.py` exposes the pure, I/O-free core of the cognitive-adapter runtime (COGNITIVE-ADAPTER-V1, ADR-0018): manifest loading, JSON-Schema validation against `contracts/adapter/v1`, the closed step vocabulary, and run/step transition rules — "No database, no HTTP, no provider call lives here" (shared/polymath_shared/adapter/__init__.py:1-7) [DERIVED]. Consumers are the orchestrator (MCP tools) and the adapter step worker, which compose these with Postgres receipts/outbox/lease primitives (shared/polymath_shared/adapter/__init__.py:5-7) [DERIVED]. `contracts.py` supplies schema access, validation, canonical hashing (shared/polymath_shared/adapter/contracts.py:1) [DERIVED]. `domain.py` is the one I/O exception: the DOMAIN_OPERATION runner (ADR-0020) that executes domain bindings out of process; it is NOT re-exported by `__init__` (shared/polymath_shared/adapter/domain.py:1-9; shared/polymath_shared/adapter/__init__.py:8-13) [DERIVED].

## public surface
"Unit importers" = the 15 files in FACTS.importers (mcp_server, 5 orchestrator modules, 8 adapter modules, adapter_step_worker).

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| ContractViolation | class (ValueError) | (name: str, errors: list[str]) | contracts.py:45-51 | unit importers |
| schema | func (lru_cache) | (name: str) -> dict[str, Any] | contracts.py:54-59 | unit importers |
| validate | func | (name: str, instance: Any) -> list[str] | contracts.py:67-70 | unit importers |
| assert_valid | func | (name: str, instance: Any) -> None | contracts.py:73-76 | unit importers |
| bounded_text | func | (text: Any, limit: int) -> str | contracts.py:79-88 | not re-exported in `__init__` (contracts.py only) |
| stable_hash | func | (obj: Any) -> str | contracts.py:91-93 | unit importers |
| DomainCrash | class (RuntimeError) | message only | domain.py:38-40 | adapter_step_worker, service.py (domain.py:7-9) |
| request | func | (*, domain, operation, run_id, step_id, run_input, scope, config) -> dict | domain.py:53-61 | step worker, service.start, service.submit (domain.py:7-9) |
| binding | func | (domain: str, domains_dir: Path | None = None) -> Path | None | domain.py:64-70 | internal + step worker |
| run | func | (domain, operation, req, *, domains_dir=None, timeout_s=None) -> dict | domain.py:73-111 | step worker (`exec_domain`), `service.start`, `service.submit` (domain.py:7-9) |

`__init__` re-exports (shared/polymath_shared/adapter/__init__.py:8-13) [DERIVED]: from contracts — `STEP_TYPES, RUN_STATUSES, STEP_STATUSES, TERMINAL_RUN_STATUSES, schema, validate, assert_valid, ContractViolation, stable_hash`; from manifest — `Manifest, ManifestError, load_manifest, list_manifests, graph_integrity_errors, ADAPTER_DIR`; from transitions — `RunState, SubmissionRejected, BudgetExhausted, evaluate_predicate, next_step_id, issue_step, validate_submission, accept_submission, record_automatic_output, cancel_run, terminal_gap, start_run, complete_run, run_status_view`. `__all__ = [n for n in dir() if not n.startswith("_")]` (shared/polymath_shared/adapter/__init__.py:16) [DERIVED].

Closed vocabularies (exact literals):

| constant | value | anchor |
|---|---|---|
| STEP_TYPES | `("POLYMATH_RETRIEVE", "POLYMATH_COMPILE_PLAN", "POLYMATH_GRAPH_EXPAND", "EXTERNAL_OPERATION", "DOMAIN_OPERATION", "AGENT_REASON", "HARNESS_ACTION", "VALIDATE", "BRANCH", "COMPILE_RESULT")` | contracts.py:16-17 |
| AGENT_ANSWERED_STEP_TYPES | `frozenset({"AGENT_REASON", "HARNESS_ACTION"})` | contracts.py:20 |
| AUTOMATIC_STEP_TYPES | `frozenset(STEP_TYPES) - AGENT_ANSWERED_STEP_TYPES` | contracts.py:21 |
| RUN_STATUSES | `("created", "running", "awaiting_agent", "awaiting_harness", "completed", "terminal_gap", "cancelled", "failed")` | contracts.py:22 |
| HARNESS_ACTION_KINDS | `("AGENT_RESEARCH", "PRODUCT_REALITY_CHECK", "SUPPLIER_RESEARCH")` | contracts.py:24 |
| THETA_OPS | `("generate_hypotheses", "derive_mechanisms", "cross_map_frictions", "derive_physical_jobs", "derive_analogies", "split_hypotheses", "generate_product_mechanisms")` | contracts.py:25-26 |
| PHI_OPS | `("reject", "merge", "deduplicate", "weaken", "strengthen", "challenge", "require_evidence", "promote")` | contracts.py:27 |
| HYPOTHESIS_STATUSES | `("proposed", "filtered", "retained", "revised", "split", "merged", "weakened", "strengthened", "contradicted", "killed", "promoted")` | contracts.py:28-29 |
| TRANSITION_KINDS | `("GENERATE", "REVISE", "SPLIT", "MERGE", "WEAKEN", "STRENGTHEN", "CONTRADICT", "KILL", "PROMOTE")` | contracts.py:30 |
| TRANSITION_ACTORS | `("theta", "phi", "runtime")` | contracts.py:31 |
| EVIDENCE_ROLE_PATTERN | `r"^[a-z][a-z0-9_]{1,40}$"` | contracts.py:33 |
| CITABLE_EVIDENCE_KINDS | `frozenset({"chunk", "document", "graph_fact", "graph_hop", "parent_map", "field_evidence"})` | contracts.py:35 |
| PRIOR_EVIDENCE_KINDS | `frozenset({"trail_prior"})` | contracts.py:36 |
| ORIGIN_ID_FIELDS | `("lead_ids", "latent_structure_ids")` | contracts.py:40 |
| TERMINAL_RUN_STATUSES | `frozenset({"completed", "terminal_gap", "cancelled", "failed"})` | contracts.py:41 |
| STEP_STATUSES | `("issued", "accepted", "rejected", "executed", "failed", "skipped")` | contracts.py:42 |
| DOMAINS_DIR | `_REPO / "adapters"` | domain.py:25 |
| DOMAIN_RE | `re.compile(r"^[a-z][a-z0-9_]{1,40}$")` | domain.py:26 |
| REQUEST_VERSION | `"domain_operation_request.v1"` | domain.py:27 |
| TIMEOUT_S | `float(os.environ.get("POLYMATH_DOMAIN_OPERATION_TIMEOUT_S", "120"))` | domain.py:28 |
| OUTPUT_MAX_BYTES | `1_000_000` | domain.py:29 |
| _CODE | `re.compile(r"^[A-Z][A-Z0-9_]{2,60}$")` | domain.py:30 |
| RESERVED_KEYS | `(frozenset(TC.RESULT_FIELDS) - {"research_directive"}) | {"hypothesis_verdicts", "hypothesis_transition_ids", "operation_kind", "qualification"}` | domain.py:34-35 |

## contracts
**schema(name)** — contracts.py:54-59
- in: contract name; out: parsed JSON dict from `CONTRACT_DIR / f"{name}.schema.json"`.
- pre: file exists, else `KeyError(f"unknown adapter contract {name!r}")` (contracts.py:56-58).
- post: cached `@lru_cache(maxsize=None)`; CONTRACT_DIR = `_REPO / "contracts" / "adapter" / "v1"`, `_REPO = Path(__file__).resolve().parents[3]` (contracts.py:12-14).

**validate(name, instance)** — contracts.py:67-70
- out: list of `"/".join(path): message` strings, `"$"` at root; sorted by `(str(path parts), message)` — deterministic order; empty list = valid.

**assert_valid(name, instance)** — contracts.py:73-76
- post: raises `ContractViolation(name, errors)` iff validate non-empty; `str(exc)` shows only `errors[:5]` joined by `"; "` (contracts.py:49); full list on `.errors`.

**bounded_text(text, limit)** — contracts.py:79-88
- out: `str(text)` whole when `len(text) <= limit`; else head = `keep * 2 // 3` chars + `" …[+N chars elided]… "` + tail = `keep - head` chars, where `keep = limit - len(f" …[+{len(text)} chars elided]… ")` (contracts.py:86-88).
- post: result never exceeds `limit` — the marker is budgeted at its longest form (comment, contracts.py:86).

**stable_hash(obj)** — contracts.py:91-93
- out: sha256 hexdigest over `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")` — the receipt/submission hash.

**request(...)** — domain.py:53-61 (all keyword-only)
- out keys: `schema_version` (= REQUEST_VERSION), `domain`, `operation`, `run_id`, `step_id`, `input` (= `dict(run_input or {})`), `inputs`, `config` (domain.py:57-61).
- `inputs`: `name -> _path(scope, sel)` or a list of `_path` values when `sel` is a list; a missing dotted segment resolves to `None` (domain.py:59-60; 43-50).
- `config`: step config minus keys `"domain"`, `"operation"`, `"inputs"` (domain.py:61).

**binding(domain, domains_dir=None)** — domain.py:64-70
- out: resolved `adapters/<domain>/binding.py` path, else `None`.
- pre: `DOMAIN_RE` matches AND `root in path.parents` AND `path.is_file()` (domain.py:66-70) — traversal guard.

**run(domain, operation, req, ...)** — domain.py:73-111
- out: `{"output": {...}}` with injected `output["_domain"] = {"domain", "operation", "binding_sha256": sha256(path.read_bytes())}` (domain.py:110), or `{"gap": {"code", "message"}}`.
- gap codes returned: `DOMAIN_BINDING_INVALID` (bad name, domain.py:78), `DOMAIN_BINDING_MISSING` (no binding, domain.py:81), binding's own typed code matched against `_CODE`, message capped `[:2000]` (domain.py:100-103).
- child exec: `[sys.executable, str(path)]`, req JSON on stdin, `cwd=str(path.parent)`, `env = {"PATH": ..., "LANG": ..., "PYTHONDONTWRITEBYTECODE": "1"}`, timeout = `timeout_s or TIMEOUT_S` (domain.py:82-86).
- raises `DomainCrash` on: timeout; `returncode != 0` (stderr tail `[-600:]`); stdout `> OUTPUT_MAX_BYTES`; non-JSON stdout; no boolean `ok`; refusal code not matching `_CODE`; `ok` without dict `output`; output keys starting `"_"`/`"trail_"` or in RESERVED_KEYS (domain.py:87-109).

## effect surface
- subprocess: `subprocess.run` spawning the domain binding (FACTS.nondeterminism; domain.py:85) — `sys.executable` runs `adapters/<domain>/binding.py` (domain.py:25, 85).
- files read: `contracts/adapter/v1/<name>.schema.json` (contracts.py:14, 56-59); binding file existence, bytes hashed (domain.py:69, 110).
- env read: `POLYMATH_DOMAIN_OPERATION_TIMEOUT_S` = `"120"` (domain.py:28); `PATH` = `""` (domain.py:82); `LANG` = `"en_US.UTF-8"` (domain.py:82).
- env passed to child: only `PATH`, `LANG`, `PYTHONDONTWRITEBYTECODE="1"` — "no DSN, no token, no key" (domain.py:82; 4-5) [DERIVED].
- Postgres tables: none (FACTS.tables_read, FACTS.tables_written both empty). Network: none in SOURCE [DERIVED].

## invariants
INVARIANT: `len(bounded_text(text, limit)) <= limit` for all inputs — contracts.py:84-88 [DERIVED]
  fails-if: receipt error / gap message violates its schema `maxLength` → ContractViolation on write.
INVARIANT: TERMINAL_RUN_STATUSES (4 members) ⊆ RUN_STATUSES (8 members) — contracts.py:22, 41 [DERIVED]
  fails-if: a terminal status no transition reaches, or a non-terminal status treated as terminal.
INVARIANT: AUTOMATIC_STEP_TYPES = STEP_TYPES (10) − AGENT_ANSWERED_STEP_TYPES (2) = 8 — contracts.py:16-21 [DERIVED]
  fails-if: a step type neither the runtime nor agent/harness answers → run stuck in `awaiting_agent`/`awaiting_harness`.
INVARIANT: gap message from run() has length ≤ 2000 — domain.py:103 [DERIVED]
  fails-if: oversized refusal text breaks the gap contract.
INVARIANT: child env ⊆ {PATH, LANG, PYTHONDONTWRITEBYTECODE} — domain.py:82 [DERIVED]
  fails-if: secrets reach the domain binding; ADR-0020 process isolation broken (domain.py:4-5).
INVARIANT: run() output contains no key starting `_`/`trail_` and none in RESERVED_KEYS, before `_domain` injection — domain.py:107-110 [DERIVED]
  fails-if: a domain impersonates TrailSignal/runtime fields (bug hunt B-69, domain.py:31-35).
INVARIANT: DOMAIN_RE pattern string == EVIDENCE_ROLE_PATTERN string (`^[a-z][a-z0-9_]{1,40}$`) — domain.py:26, contracts.py:33 [DERIVED]
  fails-if: name rules diverge; a domain name valid in one place rejected in the other.

## determinism & idempotency
determinism: contracts.py + `__init__` DETERMINISTIC (pure functions, `lru_cache`, sorted error order — contracts.py:54, 62, 69) [DERIVED]; domain.py NONDETERMINISTIC (subprocess spawn domain.py:85; env PATH/LANG domain.py:82; wall-clock timeout domain.py:28, 87).
idempotency: contracts functions SAFE (pure, no state); `run()` SAFE at module level — writes nothing, fresh subprocess per call — but the binding's own side effects are uncontrolled [INFERRED: module touches no store; child process is opaque].

## failure behaviour
- `ContractViolation(ValueError)` from assert_valid: carries `name` + full `errors`; `str()` truncates to `errors[:5]` (contracts.py:45-51).
- `KeyError("unknown adapter contract …")` from schema() for a missing contract file (contracts.py:56-58).
- `DomainCrash(RuntimeError)`, 8 raise sites in run(): timeout, nonzero exit, oversize stdout, non-JSON, no boolean `ok`, untyped refusal, `ok` without output dict, reserved output keys (domain.py:88-109). Caller records it as a step failure `STEP_EXECUTOR_ERROR`, or — for a submit-time law — falls back to the normal path (domain.py:39-40) [DERIVED].
- Typed gaps returned instead of raised: `DOMAIN_BINDING_INVALID`, `DOMAIN_BINDING_MISSING`, binding refusal code (domain.py:78, 81, 103).
- `_path` swallows missing dotted segments → returns `None`, no error (domain.py:43-50).

## dumb-code flags
- Duplicated regex literal `^[a-z][a-z0-9_]{1,40}$` in two modules — contracts.py:33, domain.py:26 [DERIVED].
- `TIMEOUT_S` reads env once at import; later env changes have no effect (module-level assignment, domain.py:28) [INFERRED].
- Magic numbers: `errors[:5]` contracts.py:49; stderr tail `[-600:]` domain.py:90; gap message `[:2000]` domain.py:103; reserved list `[:10]` domain.py:109; head split `keep * 2 // 3` contracts.py:87.
- Reflective `__all__ = [n for n in dir() if not n.startswith("_")]` — any future public import silently becomes package API (shared/polymath_shared/adapter/__init__.py:16) [DERIVED].
- `bounded_text` is public in contracts.py but absent from the `__init__` re-export list (shared/polymath_shared/adapter/__init__.py:8-13) [DERIVED].

## refactor notes
- 15 importers depend on the `__init__` re-exports (FACTS.importers: mcp_server/polymath_mcp.py, 5 orchestrator modules, 8 adapter modules, workers/workers/adapter_step_worker.py); renaming/removing any name in `__init__.py:8-13` breaks them all.
- `stable_hash` is the receipt/submission hash — changing `sort_keys`/`separators`/`ensure_ascii` invalidates every stored hash (contracts.py:91-93).
- domain.py imports the private `contracts._REPO` (domain.py:23) and derives RESERVED_KEYS from `trail_client.RESULT_FIELDS` (domain.py:34) — renaming either breaks domain.py.
- The `research_directive` carve-out in RESERVED_KEYS is deliberate (B-69: domains enrich it, governance fields untouched) — domain.py:31-35.
- bounded_text's 2/3-head / 1/3-tail split exists because validator messages name the field first and the rule last (contracts.py:80-82); a different split can cut the rule out of the diagnostic.

## VERIFY
```verify
grep -Fq 'OUTPUT_MAX_BYTES = 1_000_000' shared/polymath_shared/adapter/domain.py
grep -Fq '_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,60}$")' shared/polymath_shared/adapter/domain.py
grep -Fq 'POLYMATH_DOMAIN_OPERATION_TIMEOUT_S' shared/polymath_shared/adapter/domain.py
grep -Fq 'def bounded_text(text: Any, limit: int) -> str:' shared/polymath_shared/adapter/contracts.py
grep -Fq 'separators=(",", ":")' shared/polymath_shared/adapter/contracts.py
grep -Fq 'trail_prior' shared/polymath_shared/adapter/contracts.py
! grep -Fq 'bounded_text' shared/polymath_shared/adapter/__init__.py
test "$(grep -c -F 'DomainCrash' shared/polymath_shared/adapter/domain.py)" -ge 5
```
