# unit: shared/polymath_shared/adapter/trail_client.py
anchor: shared/polymath_shared/adapter/trail_client.py:1-342

## purpose
Typed Polymath → TrailSignal connector over Trail's public production boundary: an authenticated FastMCP streamable-HTTP daemon (`POST {url}/mcp`, stateless JSON-RPC 2.0 `tools/call`, HS256 bearer JWT). Exposes seven bounded synchronous operations plus pure request/receipt builders; never touches Trail's CSV, Postgres, blob store or private modules. [DERIVED] shared/polymath_shared/adapter/trail_client.py:1-11

Module imported by: `orchestrator/orchestrator/api/adapter.py`, `shared/polymath_shared/adapter/run_view.py`, `shared/polymath_shared/adapter/service.py`, `workers/workers/adapter_step_worker.py` [DERIVED] FACTS.importers

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `fills` | def | `(operation_kind: str \| None, key: str) -> bool` | :55-62 | — |
| `identifier` | def | `(*parts: str, max_len: int = 200) -> str` | :100-106 | — |
| `credential_binding_hash` | def | `(principal_id: str, binding_secret: str \| None = None) -> str` | :109-112 | — |
| `mint_principal_jwt` | def | `(secret, *, principal_id="polymath", audit_identity=None, capabilities=POLYMATH_CAPABILITIES, policy_ref=POLICY_REF, budget_ref=BUDGET_REF, binding_hash=None, ttl_s=3600, now=None) -> str` | :115-128 | — |
| `token_expires_within` | def | `(token: str \| None, seconds: float) -> bool` | :131-139 | — |
| `token_from_env` | def | `(env: dict[str, str] \| None = None) -> str \| None` | :142-150 | — |
| `bounded_request` | def | `(kind, payload, *, key, run_ref, registry_snapshot_id=None, purpose_ref=PURPOSE_REF) -> dict` | :167-176 | — |
| `admission_overflow` | def | `(payload, *, key, run_ref, registry_snapshot_id=None, purpose_ref=PURPOSE_REF) -> dict \| None` | :186-216 | — |
| `operation_reference` | def | `(ref, *, minimum_revision: int = 0) -> dict` | :219-224 | — |
| `cancel_command` | def | `(operation_id, *, expected_revision: int, key, reason_code="CLIENT_CANCELLED") -> dict` | :227-230 | — |
| `receipt_from_ref` | def | `(run_id, step_id, ref, *, idempotency_key, principal) -> dict` | :234-241 | — |
| `receipt_after_poll` | def | `(receipt, status, *, record_ids=None) -> dict` | :244-257 | — |
| `bounded_receipt` | def | `(run_id, step_id, kind, response, *, idempotency_key, principal, record_ids=None) -> dict` | :260-269 | — |
| `TrailError` / `TrailTransportError` / `TrailProtocolError` / `TrailInternalError` / `TrailUnreachable` / `TrailToolError` | class | `RuntimeError` hierarchy | :71-96 | — |
| `TrailMCPClient` | class | `__init__(url=DEFAULT_URL, token=None, *, timeout_s=30.0, transport=None)`; `from_env(env=None, **kw)`; `call_tool(name, arguments)`; `operate(kind, request)`; `status(ref, *, minimum_revision=0)`; `cancel(command)`; property `configured` | :273-341 | — |

## contracts

**`fills(operation_kind, key)`** :55-62
- in: `operation_kind: str | None`, `key: str`
- out: `True` when `key` maps (via `_DERIVED_FROM`) to a field not in `RESULT_FIELDS`, or `operation_kind` is falsy, or the field is in `FIELDS_BY_OPERATION[operation_kind]`; else `False` [DERIVED] :59-62
- post: `False` means an unfilled envelope default that must never shadow an earlier operation's value [DERIVED] :57-58

**`identifier(*parts, max_len=200)`** :100-106
- in: parts joined with `":"`; `_` → `-`; chars matching `[^A-Za-z0-9._:/-]` → `-`; stripped of `._:/-`; prefixed `"p"` when empty or non-`[A-Za-z0-9]`-leading; truncated to `max_len` [DERIVED] :102-105
- post: matches Trail `Identifier` shape `^[A-Za-z0-9][A-Za-z0-9._:/-]*$, 1..256` [DERIVED] :101

**`mint_principal_jwt(...)`** :115-128
- pre: `len(secret) >= 32` else `ValueError` [DERIVED] :121-122
- out: HS256 JWT with claims `sub, audit_identity, capabilities, policy_ref, budget_ref, credential_binding_hash, iat, exp, iss="trail-signal", aud="trail-signal-mcp"`; `exp = iat + ttl_s`; no `nbf` [DERIVED] :117-127

**`token_expires_within(token, seconds)`** :131-139
- out: `True` iff JWT body has numeric `exp` (bool excluded) with `exp - time.time() < seconds`; parse failure → `False`; non-JWT tokens "never expire" (`False`) [DERIVED] :134-139

**`token_from_env(env=None)`** :142-150
- in: env defaults to `os.environ`
- out: `TRAIL_SIGNAL_MCP_TOKEN_POLYMATH` if set; else mint from `TRAIL_SIGNAL_MCP_JWT_SECRET` with `POLYMATH_TRAIL_PRINCIPAL` (default `"polymath"`) and `POLYMATH_TRAIL_AUDIT_IDENTITY` (default = principal); else `None` [DERIVED] :144-150

**`bounded_request(kind, payload, ...)`** :167-176
- pre: `kind in BOUNDED_OPERATIONS` else `ValueError(kind)`; canonical bytes (sorted-key compact JSON, UTF-8) `<= 65536` else `ValueError` [DERIVED] :171-175
- out: envelope with `request_id`, `idempotency_key`, `purpose_ref`, `run_ref`, `operation_kind`, `registry_snapshot_id`, `payload` [DERIVED] :159-160

**`admission_overflow(payload, ...)`** :186-216
- out: `None` when `size(payload) <= 65536`, where size = canonical envelope bytes + `_trail_measure_headroom` [DERIVED] :193-199
- out on overflow: `{"bytes", "limit_bytes", "observations", "observations_that_fit"}`; `observations_that_fit` found by binary search keeping the invariant "keep(lo) fits, keep(hi) does not"; `None` when even `keep(0)` overflows; sources pruned to those still cited [DERIVED] :204-215
- post: pure — payload never mutated, nothing trimmed (owner decision 2026-09-26: refusal, not trimming) [DERIVED] :188-192

**`TrailMCPClient.call_tool(name, arguments)`** :293-327
- pre: `self.token` set else `TrailError`; raw JSON-RPC body `<= 65536` bytes else `TrailError` [DERIVED] :294-300
- post: returns `structuredContent`, else first `text` content parsed as JSON, else `{}`; a dict whose only key is `"result"` is unwrapped [DERIVED] :321-326

**`TrailMCPClient.operate(kind, request)`** :330-335
- pre: `kind in BOUNDED_OPERATIONS` else `ValueError(kind)` [DERIVED] :333-334
- out: immutable result envelope `{operation_id, operation_kind, status_revision, registry_snapshot?, result}` [DERIVED] :331-332

## effect surface
- network: one `httpx.Client` POST per `call_tool` — `follow_redirects=False, trust_env=False`, timeout `30.0` default [DERIVED] :304-305, :276
- env flags: `POLYMATH_TRAIL_MCP_URL` = `"http://127.0.0.1:8767/mcp"` [DERIVED] :31, :285-287; `TRAIL_SIGNAL_MCP_TOKEN_POLYMATH` (no default) [DERIVED] :144-145; `TRAIL_SIGNAL_MCP_JWT_SECRET` (no default) [DERIVED] :146-149; `POLYMATH_TRAIL_PRINCIPAL` = `"polymath"` [DERIVED] :148; `POLYMATH_TRAIL_AUDIT_IDENTITY` = default = principal [DERIVED] :149
- Postgres tables read/written: none [DERIVED] FACTS.tables_read/tables_written empty
- Qdrant / files / subprocesses: none visible in SOURCE

## invariants
INVARIANT: `len(RESULT_FIELDS) = 12` — :40-41 [DERIVED] (registry_snapshot, priors, redundancy_groups, unsupported_hypothesis_ids, research_directive, evidence_admission, verdicts, open_gaps, territories, qualifications, trail_scores, score_refusals)
  fails-if: a field rename in Trail breaks `fills` shadow-prevention and FIELDS_BY_OPERATION coverage.
INVARIANT: `len(BOUNDED_OPERATIONS) = 7` — :33-34 [DERIVED]
  fails-if: an eighth operation would bypass `bounded_request`/`operate` validation.
INVARIANT: `FIELDS_BY_OPERATION[kind] ⊆ RESULT_FIELDS` for all 7 kinds — :42-50 [DERIVED]
  fails-if: a field outside RESULT_FIELDS would make `fills` return True for an unknown key and let an empty envelope shadow a real value.
INVARIANT: `REQUEST_BYTES_MAX = 65536` enforced both in `bounded_request` (canonical envelope, :174) and `call_tool` (raw wire body, :299) [DERIVED]
  fails-if: divergence lets a request pass client validation and be refused by Trail (or vice versa).
INVARIANT: identifier output length `<= 200` (default) while Trail ceiling is `256` — :101, :106 [INFERRED: 200 is conservative slack under the documented 256 limit]
  fails-if: raising the default past 256 would produce ids Trail rejects.
INVARIANT: `exp = iat + ttl_s`, `ttl_s` default `3600` — :117, :127 [DERIVED]
  fails-if: a long-lived worker using the default token sees auth failures after an hour (bug hunt B-67, :132).
INVARIANT: `len(secret) >= 32` or mint refuses — :121-122 [DERIVED]
  fails-if: Trail rejects shorter-key JWTs at AuthRuntime.
INVARIANT: `credential_binding_hash` stable per principal, "must never rotate mid-run" — :110 [DERIVED]
  fails-if: rotation mid-run breaks Trail's operation-ownership keying.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `time.time` :123, :139; `_dt.datetime.now` :155 via `_utc_now` used in :238, :242, :264; network: `httpx.Client` POST :304-305). All envelope/receipt builders and `fills`/`identifier`/`admission_overflow` are pure of these. [DERIVED]
idempotency: SAFE — every operation envelope carries `idempotency_key` (:159); `TrailInternalError` and `TrailUnreachable` are documented replay-safe with the SAME request (:86-87, :91-92). [DERIVED]

## failure behaviour
- No token → `TrailError("no Trail principal token ...")` :294-295.
- Network (`httpx.NetworkError`, `RemoteProtocolError`, `ConnectTimeout`, `PoolTimeout`) → `TrailUnreachable` (transient, retry-safe); a read timeout is explicitly NOT this class — the daemon had the request :92, :306-307.
- HTTP status `>= 400` → `TrailTransportError(status, text[:300])` :77, :308-309.
- Non-JSON response → `TrailProtocolError` :312-313.
- JSON-RPC `error` object → `TrailInternalError` when code `== -32603` (retryable, never a refusal), else `TrailProtocolError` :314-316, :85-87.
- `result.isError` → `TrailToolError(msg[:400])` — Trail refused (policy, validation, permission, unknown tool) :318-320, :95-96.
- Swallowed: `token_expires_within` catches `IndexError, ValueError, TypeError, AttributeError` and returns `False` :137-138.
- Fallback: missing `structuredContent` falls back to first text content parsed as JSON, else `{}` :321-324.

## dumb-code flags
- `_URL_BAD_QUERY_KEYS` defined :68, never referenced anywhere in this file — dead constant. [DERIVED]
- Headroom magic numbers `1024 + 256*hypotheses + 32*observations` :183 estimate Trail's server-side measure (~26 B/observation, ~200 B/hypothesis, ~170 B/payload, ~110 B/wrapper per :182) — pinned to a core version, not the real server measure. [DERIVED]
- Two identifier ceilings in one docstring: default `max_len=200` vs Trail `1..256` :101, :100. [DERIVED]
- Truncation limits disagree: `text[:300]` (:77), `[:300]` (:307), `[:400]` (:316), `[:400]` (:320), `[:200]` (:313), `[:60]` (:246) — six magic slice bounds. [DERIVED]
- `import jwt` lazily inside `mint_principal_jwt` :120 — PyJWT import error deferred to first mint. [DERIVED]
- `POLICY_REF, BUDGET_REF` assigned mid-file at :63, away from the constants block :31-68. [DERIVED]

## refactor notes
- `RESULT_FIELDS` + `FIELDS_BY_OPERATION` are pinned to Trail's `research_operations.py`; a test re-derives the map from pinned source (:37-39) — changing one without the other breaks `fills`. [DERIVED]
- `_DERIVED_FROM = {"hypothesis_verdicts": "verdicts"}` mirrors the worker storing `verdicts` under the key `hypothesis_verdicts` (:51-52); `fills` callers depend on it. [DERIVED]
- `POLYMATH_CAPABILITIES` must match Trail ADR-063 PrincipalCapabilityV6 (:35-36). [DERIVED]
- `identifier()` rewrites underscores to `-` (:103) — Polymath ids do not round-trip; callers must not compare raw. [DERIVED]
- Retry semantics of `TrailInternalError`/`TrailUnreachable` (:86-92) are a contract for all four importers (FACTS.importers). [DERIVED]
- `REQUEST_BYTES_MAX` mirrors `config/v2/limits.yaml mcp.maximum_request_bytes` (:65) — two places to update. [DERIVED]

## VERIFY
```verify
grep -Fq 'REQUEST_BYTES_MAX = 65536' shared/polymath_shared/adapter/trail_client.py
grep -Fq 'DEFAULT_URL = "http://127.0.0.1:8767/mcp"' shared/polymath_shared/adapter/trail_client.py
grep -Fq '_DERIVED_FROM = {"hypothesis_verdicts": "verdicts"}' shared/polymath_shared/adapter/trail_client.py
grep -Eq 'class TrailInternalError\(TrailProtocolError\)' shared/polymath_shared/adapter/trail_client.py
grep -Fq 'return 1024 + 256 * len(payload.get("hypotheses") or []) + 32 * len((payload.get("receipt") or {}).get("observations") or [])' shared/polymath_shared/adapter/trail_client.py
! grep -Fq 'import requests' shared/polymath_shared/adapter/trail_client.py
test "$(grep -c -F 'BOUNDED_OPERATIONS' shared/polymath_shared/adapter/trail_client.py)" -ge 4
```
