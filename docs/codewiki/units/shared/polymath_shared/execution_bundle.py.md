# unit: shared/polymath_shared/execution_bundle.py
anchor: shared/polymath_shared/execution_bundle.py:1-159

## purpose
Identity card for the exact code + configuration a worker process is executing (EXECUTION-BUNDLE-FENCE-V1) — shared/polymath_shared/execution_bundle.py:1-8 [DERIVED]. A worker's `build_sha == HEAD` does not prove its in-memory code matches the repo; this module gives every worker a computed-at-boot bundle plus a cheap per-tick fingerprint so drift becomes loud refusal instead of silent divergence — shared/polymath_shared/execution_bundle.py:3-8 [DERIVED]. Claimed property: same repo state + same env => same bundle hash — shared/polymath_shared/execution_bundle.py:10 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `_sha256_file` | def | `(path: Path) -> str` | shared/polymath_shared/execution_bundle.py:45-50 | — (private helper) |
| `git_state` | def | `() -> dict[str, str]` | shared/polymath_shared/execution_bundle.py:53-71 | — |
| `semantic_file_hashes` | def | `() -> dict[str, str]` | shared/polymath_shared/execution_bundle.py:74-87 | — |
| `config_fingerprint` | def | `() -> dict[str, str]` | shared/polymath_shared/execution_bundle.py:90-91 | — |
| `fast_code_fingerprint` | def | `() -> str` | shared/polymath_shared/execution_bundle.py:99-132 | — |
| `compute_execution_bundle` | def | `() -> dict[str, Any]` | shared/polymath_shared/execution_bundle.py:135-154 | — |
| `bundle_id` | def | `(bundle: dict[str, Any]) -> str` | shared/polymath_shared/execution_bundle.py:157-158 | — |

Module imported by: `shared/polymath_shared/conformance/evidence.py`, `shared/polymath_shared/execution.py`, `shared/polymath_shared/worker_runtime.py`, `workers/workers/extract_worker.py`, `workers/workers/knowledge_artifacts.py` — FACTS.importers [DERIVED]. Per-symbol usage not in FACTS.

## contracts

**git_state()** — shared/polymath_shared/execution_bundle.py:53-71
- in: none; env `POLYMATH_BUILD_SHA` (default `''`) — :56 [DERIVED]
- out: `{"git_sha": <str>, "tree_dirty": <str(bool)>}` — :71 [DERIVED]
- pre: `git` callable in `cwd=str(ROOT)` when env sha empty — :60-67 [DERIVED]
- post: on any Exception, `sha = sha or "unknown"` and `dirty = True` ("cannot prove cleanliness -> refuse to look clean") — :68-70 [DERIVED]

**semantic_file_hashes()** — shared/polymath_shared/execution_bundle.py:74-87
- in: none
- out: keys `"scientific-predicate-ontology-v2.yaml"` and `"trigger_allowlist"`; value = sha256 hexdigest or literal `"missing"` — :82-86 [DERIVED]
- post: covers non-Python semantic authorities that escape the semantic-authority code hash — :75-78 [DERIVED]

**config_fingerprint()** — shared/polymath_shared/execution_bundle.py:90-91
- out: `{k: os.environ.get(k, "") for k in _CONFIG_ENV_KEYS}` — :91 [DERIVED]
- post: 5 keys: `POLYMATH_QUERY_POLICY`, `POLYMATH_CHUNKER`, `POLYMATH_EXTRACTION_CONTEXT`, `POLYMATH_WORKER_EXTRACTION_PROVIDER`, `POLYMATH_EXTRACTION_ATTESTATION` — :36-41 [DERIVED]

**fast_code_fingerprint()** — shared/polymath_shared/execution_bundle.py:99-132
- out: sha256 hexdigest truncated `[:16]` — :132 [DERIVED]
- scope: `*.py/*.yaml/*.yml` under 3 dirs (`shared/polymath_shared`, `workers/workers`, `control/control`), `__pycache__` excluded — :26-31, :114-119 [DERIVED]
- post: content-addressed (same bytes => same fingerprint); per-file cache keyed `(size, mtime_ns)`; unreadable file => sha `"unreadable"` — :108-111, :123-129 [DERIVED]

**compute_execution_bundle()** — shared/polymath_shared/execution_bundle.py:135-154
- out: dict with keys `git_sha`, `tree_dirty`, `semantic_authority`, `rule_pack_file`, `ontology_file`, `trigger_allowlist`, `config`, `contracts`, plus `execution_bundle_hash` = sha256 of `json.dumps(bundle, sort_keys=True, separators=(",", ":"))` truncated `[:16]` — :141-153 [DERIVED]
- pre: lazy import of `polymath_shared.execution.semantic_authority_sha256` and `worker_contracts` — :136-139 [DERIVED]

**bundle_id(bundle)** — shared/polymath_shared/execution_bundle.py:157-158
- out: `f"bundle_{bundle.get('execution_bundle_hash', 'unknown')}"` — :158 [DERIVED]

## effect surface
- subprocess: `["git", "rev-parse", "--short", "HEAD"]` — shared/polymath_shared/execution_bundle.py:60-63; `["git", "status", "--porcelain"]` — shared/polymath_shared/execution_bundle.py:64-67 (both `timeout=5`, `cwd=str(ROOT)`)
- env read: `POLYMATH_BUILD_SHA = ''` default — shared/polymath_shared/execution_bundle.py:56
- files read: `config/ontology/scientific-predicate-ontology-v2.yaml` — :82; `resources/predicates/trigger_allowlist.yaml` — :84-85; all fingerprint-suffix files under the 3 pinned dirs — :114-119
- in-process state: `_CONTENT_HASH_CACHE: dict[str, tuple[int, int, str]]` — :96, :275
- Postgres tables read/written: none (FACTS.tables_read/tables_written empty) [DERIVED]
- network: none visible

## invariants
INVARIANT: `execution_bundle_hash` length == 16 (`hexdigest()[:16]`) — shared/polymath_shared/execution_bundle.py:152-153 [DERIVED]
  fails-if: `bundle_id` output format and cross-build hash comparisons break.
INVARIANT: `fast_code_fingerprint` length == 16 — shared/polymath_shared/execution_bundle.py:132 [DERIVED]
  fails-if: stored per-tick fingerprints no longer match running workers.
INVARIANT: `_CONFIG_ENV_KEYS` count == 5 — shared/polymath_shared/execution_bundle.py:36-41 [DERIVED]
  fails-if: an unlisted extraction-semantics env knob changes behavior without changing the bundle hash (undetected config drift).
INVARIANT: `_FINGERPRINT_DIRS` count == 3 (`shared/polymath_shared`, `workers/workers`, `control/control`) — shared/polymath_shared/execution_bundle.py:27-29 [DERIVED]
  fails-if: dropping a dir leaves drift on that surface invisible to the fence.
INVARIANT: same file bytes => same fingerprint (content hash, not stat) — shared/polymath_shared/execution_bundle.py:108-111, :123-131 [DERIVED]
  fails-if: content-preserving rewrite (e.g. determinism suite re-serializing the ontology yaml) quarantines the fleet as `BUNDLE_STALE_CODE_DRIFT` — :103-106.
INVARIANT: `git_state` keys == `{"git_sha", "tree_dirty"}`, `tree_dirty` value is `str(bool(...))` — shared/polymath_shared/execution_bundle.py:71 [DERIVED]
  fails-if: consumers parsing `tree_dirty` as a boolean type break.

## determinism & idempotency
determinism: NONDETERMINISTIC (git subprocesses — shared/polymath_shared/execution_bundle.py:60, :64; env `POLYMATH_BUILD_SHA` — :56; repo filesystem contents — :114-131). Deterministic only given fixed repo state + env — shared/polymath_shared/execution_bundle.py:10 [DERIVED]
idempotency: SAFE (no external writes; only the in-process `_CONTENT_HASH_CACHE` grows, and unchanged `(size, mtime_ns)` reuses the cached sha — shared/polymath_shared/execution_bundle.py:96, :123-124, :275)

## failure behaviour
- Broad `except Exception` in `git_state` — shared/polymath_shared/execution_bundle.py:68 — swallows any git failure; FACTS.fallbacks: "handled: assign, assign". Caller then sees `git_sha == "unknown"` and `tree_dirty == "True"` (refuse to look clean) — :69-71 [DERIVED]
- `OSError` during fingerprint hashing -> sha `"unreadable"` — shared/polymath_shared/execution_bundle.py:128-129 — deliberate fingerprint change so drift trips loudly [DERIVED]
- Missing authority file -> `"missing"` sentinel feeds `ontology_file`/`trigger_allowlist` and the bundle hash — shared/polymath_shared/execution_bundle.py:83, :86 [DERIVED]
- No error codes raised; all degradation is via sentinel strings [DERIVED]

## dumb-code flags
- `"rule_pack_file": ""` hard-coded empty placeholder still hashed into the bundle; comment says the rule-pack package is deleted — shared/polymath_shared/execution_bundle.py:145, :79-80 [DERIVED]
- Truncation literal `[:16]` duplicated at :132 and :153 [DERIVED]
- `timeout=5` duplicated at :63 and :66 [DERIVED]
- `tree_dirty` serialized as strings `"True"`/`"False"` via `str(bool(dirty))` while the name implies boolean — shared/polymath_shared/execution_bundle.py:71 [DERIVED]
- `git rev-parse --short HEAD` returns an abbreviated sha while the docstring says "HEAD sha" — shared/polymath_shared/execution_bundle.py:61, :54 [DERIVED]
- Three distinct sentinels for degradation: `"unknown"` (:63, :69, :216), `"missing"` (:83, :86), `"unreadable"` (:129) [DERIVED]

## refactor notes
- Any change to bundle keys or to the canonical JSON (`sort_keys=True, separators=(",", ":")`) changes `execution_bundle_hash`; 5 importer files depend on this module (FACTS.importers) — shared/polymath_shared/execution_bundle.py:141-153 [DERIVED]
- `bundle_id` output format `"bundle_{hash}"` is a downstream-visible contract — shared/polymath_shared/execution_bundle.py:158 [DERIVED]
- Widening/narrowing `_FINGERPRINT_DIRS` or `_FINGERPRINT_SUFFIXES` changes fence coverage: too wide quarantines the fleet (`BUNDLE_STALE_CODE_DRIFT`), too narrow hides drift — shared/polymath_shared/execution_bundle.py:26-31, :103-106 [DERIVED]
- `_CONFIG_ENV_KEYS` must be extended whenever a new extraction-semantics env var is introduced, or config drift becomes undetectable — shared/polymath_shared/execution_bundle.py:33-42 [INFERRED: keys are the only config-drift signal hashed]
- `ROOT = Path(__file__).resolve().parents[2]` bakes in repo layout depth — shared/polymath_shared/execution_bundle.py:21 [DERIVED]

## VERIFY
```verify
grep -Fq 'EXECUTION-BUNDLE-FENCE-V1' shared/polymath_shared/execution_bundle.py
grep -Fq 'BUNDLE_STALE_CODE_DRIFT' shared/polymath_shared/execution_bundle.py
grep -Fq 'POLYMATH_BUILD_SHA' shared/polymath_shared/execution_bundle.py
grep -Fq 'scientific-predicate-ontology-v2.yaml' shared/polymath_shared/execution_bundle.py
grep -Eq 'hexdigest\(\)\[:16\]' shared/polymath_shared/execution_bundle.py
test "$(grep -c -F 'timeout=5' shared/polymath_shared/execution_bundle.py)" -ge 2
! grep -Fq 'rule_pack_sha256' shared/polymath_shared/execution_bundle.py
```
