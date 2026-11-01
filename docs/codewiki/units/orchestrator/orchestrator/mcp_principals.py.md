# unit: orchestrator/orchestrator/mcp_principals.py
anchor: orchestrator/orchestrator/mcp_principals.py:1-383

## purpose
Smallest durable per-principal authorization layer for the ONE public door (Server A): principals with hashed bearer keys, action scopes, allowed corpora/adapters, default deny; the pre-existing `POLYMATH_MCP_API_KEY` stays the built-in OWNER principal (orchestrator/orchestrator/mcp_principals.py:1-14 [DERIVED]). Pure policy + a JSON file store, no network, no database, no MCP import; the gate that calls it lives in `mcp_server.py`, run ownership lives in `adapter_runs.owner_principal_id` (orchestrator/orchestrator/mcp_principals.py:27-30 [DERIVED]).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| CorpusGrant | class (frozenset) | `every -> bool`, `__contains__(corpus_id) -> bool` | orchestrator/orchestrator/mcp_principals.py:105-122 | web_scope.py (docstring 108) |
| Principal | dataclass(frozen) | fields: `principal_id, name, scopes, corpus_ids, adapter_ids, writable_corpus_ids, rate_per_minute, is_admin` | orchestrator/orchestrator/mcp_principals.py:126-134 | all four importers |
| Decision | dataclass(frozen) | `allowed, reason="ok", message=""` | orchestrator/orchestrator/mcp_principals.py:146-149 | gate consumers |
| hash_key | def | `(raw: str) -> str` (sha256 hex) | orchestrator/orchestrator/mcp_principals.py:159-160 | — |
| authorize | def | `(p: Principal, tool: str, arguments: dict\|None) -> Decision` | orchestrator/orchestrator/mcp_principals.py:163-195 | mcp_server.py (docstring 27) |
| principal_from_record | def | `(rec: dict) -> Principal` (raises ValueError) | orchestrator/orchestrator/mcp_principals.py:206-224 | store, web_accounts |
| PrincipalStore | dataclass | `authenticate(bearer: str\|None, now: datetime\|None) -> Principal\|None` | orchestrator/orchestrator/mcp_principals.py:243-307 | mcp_server.py, api/web_auth.py |
| RateLimiter | class | `allow(p: Principal, now: float\|None) -> tuple[bool, int]` | orchestrator/orchestrator/mcp_principals.py:310-329 | mcp_server.py |
| store_from_env | def | `(owner_key: str) -> PrincipalStore` | orchestrator/orchestrator/mcp_principals.py:332-334 | mcp_server.py |
| new_bearer | def | `() -> tuple[str, dict]` | orchestrator/orchestrator/mcp_principals.py:338-342 | scripts/mcp_principals.py (comment 337) |
| read_registry | def | `(path: Path) -> dict` | orchestrator/orchestrator/mcp_principals.py:349-355 | scripts/mcp_principals.py |
| write_registry | def | `(path: Path, doc: dict) -> None` | orchestrator/orchestrator/mcp_principals.py:358-375 | scripts/mcp_principals.py |
| write_secret_file | def | `(path: Path, raw: str) -> None` | orchestrator/orchestrator/mcp_principals.py:378-383 | scripts/mcp_principals.py |

Module importers: `orchestrator/orchestrator/api/web_auth.py`, `orchestrator/orchestrator/mcp_server.py`, `orchestrator/orchestrator/web_accounts.py`, `orchestrator/orchestrator/web_scope.py` (FACTS.importers).

## contracts

**authorize(p, tool, arguments) -> Decision** — orchestrator/orchestrator/mcp_principals.py:163-195
- in: an authenticated `Principal`, a wire tool name, raw tool arguments (non-dict treated as `{}`, line 168).
- pre: bearer authentication already happened; this is static authorization only (docstring 164-165).
- logic: admin -> `ALLOW` unconditionally (166-167); tool not in `TOOL_POLICY` -> `tool_not_permitted` (170-171); scope sets disjoint -> `insufficient_scope` (173-174); kind `CORPUS`/`CORPUS_OPTIONAL`/`WRITE_CORPUS`/`START` each check grants (175-194).
- post: `Decision.reason` is a stable machine code, never carries resource details (148); run ownership (kind `RUN`) is left to the gate (164-165).

**PrincipalStore.authenticate(bearer, now=None) -> Principal|None** — orchestrator/orchestrator/mcp_principals.py:290-307
- in: raw bearer or None; optional injected clock.
- out: `OWNER` if `hmac.compare_digest` matches `owner_key` (295-296); else the record whose key has `key_id == BEARER_RE` group(1), sha256 constant-time match, no `revoked_at`, `_active` record (303-306); else None.
- pre: store re-reads the registry when `(st_mtime_ns, st_ino, st_size)` changes (262-263).

**principal_from_record(rec) -> Principal** — orchestrator/orchestrator/mcp_principals.py:206-224
- out: `Principal` with `corpus_ids` coerced to `CorpusGrant` (223, also 136-138).
- raises `ValueError` for: bad `principal_id` or `pid == OWNER_ID` (208-209), unknown scopes (211-213), `ADMIN` in scopes (214-215), non-positive-int `rate_per_minute` (219-221).
- post: `scopes = scopes | PROFILES[rec["profile"]]` — stored list is a floor, never a ceiling (218).

**RateLimiter.allow(p, now=None) -> (bool, int)** — orchestrator/orchestrator/mcp_principals.py:317-329
- admin or no `rate_per_minute` -> `(True, 0)` (318-319); window = `int(t // 60)` (321); over limit -> `(False, max(1, int(60 - (t % 60))))` (327).

**write_registry(path, doc)** — orchestrator/orchestrator/mcp_principals.py:358-375
- pre: every record validated via `principal_from_record` before any write (360-361).
- post: temp file `.{name}.{pid}.tmp` mode `0o600`, fsync, `os.replace`, final `chmod 0o600` (363-375) — reader sees old or new, never half (docstring 359).

**write_secret_file(path, raw)** — opens `O_WRONLY|O_CREAT|O_EXCL` mode `0o600`; refuses to overwrite (378-383).

## effect surface
- Postgres tables: none read, none written (FACTS.tables_read/tables_written empty).
- Qdrant collections: none. The FACTS "collections" strings (`polymath_search`, `polymath_explore`, `polymath_answer`, `polymath_compare`, `polymath_deep_research`, `polymath_models`) are `TOOL_POLICY` keys / tool names at orchestrator/orchestrator/mcp_principals.py:84-88; `polymath_mcp_principals` is the schema tag string `"polymath_mcp_principals.v1"` at :48. [DERIVED]
- Files: principals JSON registry re-read on mtime change (258-263); atomic registry writes (363-371); new owner-only secret file (378-383).
- Network / subprocess: none — "no network, no database, no MCP import" (27).
- Env: `POLYMATH_MCP_PRINCIPALS_FILE` = `''` default; empty -> `path=None` -> no principals, owner key still works (332-334, 244).
- Nondeterminism: `secrets.token_hex` :340, `secrets.token_urlsafe` :341 (random); `time.time` :320, `datetime.now` :301 and :346 (clock) (FACTS.nondeterminism).

## invariants
INVARIANT: `len(SCOPES)` = 14 scope strings; `FRIEND_SCOPES` = `SCOPES` minus `ADMIN` (13 = 9 FRIEND_PROFILE + 4 added) — orchestrator/orchestrator/mcp_principals.py:56-71 [DERIVED]
  fails-if: a friend record would silently gain or lose "everything but admin" behaviour vs its advertised profile.
INVARIANT: `new_bearer` key_id = `secrets.token_hex(6)` = 12 hex chars, inside `KEY_ID_RE` `{8,32}`; secret = `token_urlsafe(32)` = 43 chars, inside `{32,128}` — orchestrator/orchestrator/mcp_principals.py:50-51,340-341 [INFERRED: hex/urlsafe length arithmetic]
  fails-if: a generated bearer would not parse against `BEARER_RE` and could never authenticate.
INVARIANT: `_allowed` returns False for `value == WILDCARD` — `"*"` names no library — and for empty/non-str — orchestrator/orchestrator/mcp_principals.py:198-199 [DERIVED]
  fails-if: a caller could name `"*"` as a corpus_id and bypass the explicit grant list.
INVARIANT: `principal_from_record` rejects `pid == OWNER_ID` and any record containing `ADMIN` — orchestrator/orchestrator/mcp_principals.py:208-215 [DERIVED]
  fails-if: a registry file could mint a second owner/admin principal.
INVARIANT: unreadable `expires_at` => `_active` False (fail closed) — orchestrator/orchestrator/mcp_principals.py:232-235 [DERIVED]
  fails-if: a corrupt expiry string would keep a revoked-temporarily principal alive forever.
INVARIANT: invalid, unreadable, or group/world-readable registry => `_records == []` + `last_error` set, never the previous possibly-revoked set — orchestrator/orchestrator/mcp_principals.py:266-267,286-287 [DERIVED]
  fails-if: a half-written or chmod-changed file would keep serving stale principals.
INVARIANT: registry file mode has no `0o077` bits (owner-only) — orchestrator/orchestrator/mcp_principals.py:266 [DERIVED]
  fails-if: the list of who may enter becomes readable by group/others.
INVARIANT: authenticate requires `key_id` match AND sha256 constant-time match AND no `revoked_at` AND `_active` — orchestrator/orchestrator/mcp_principals.py:303-306 [DERIVED]
  fails-if: a revoked key or disabled principal would still pass the gate.

## determinism & idempotency
determinism: NONDETERMINISTIC (random `secrets.token_hex` :340, `secrets.token_urlsafe` :341; clock `time.time` :320, `datetime.now` :301, :346; env `POLYMATH_MCP_PRINCIPALS_FILE` :333). `authorize`/`principal_from_record`/`CorpusGrant` are pure functions of inputs. [DERIVED]
idempotency: SAFE — `authorize`, `authenticate`, `read_registry` are reads; `write_registry` is atomic-replace with pre-validation (:358-375). UNSAFE — `write_secret_file` on an existing path (O_EXCL refuses, :381) and `RateLimiter.allow` (each call increments the window count, :328).

## failure behaviour
- `PrincipalStore._load` swallows `(OSError, ValueError, AttributeError, TypeError)` into `_records=[], last_error=f"{type(exc).__name__}: {exc}"` — caller then sees zero principals, owner key still works (286-287, 244-245). [DERIVED]
- `authenticate` returns `None` for missing bearer, unknown key, revoked key/principal — the gate treats it as unauthenticated (290-307). [DERIVED]
- `authorize` deny codes (stable machine strings): `tool_not_permitted` :171, `insufficient_scope` :174, `corpus_not_allowed` :176/181/194, `corpus_not_writable` :183, `adapter_not_allowed` :186; success reason is `"ok"` :148. [DERIVED]
- `ValueError` escapes to callers from `principal_from_record` (invalid id :209, unknown scopes :213, admin scope :215, bad rate :221) and `read_registry` schema mismatch (353-354). [DERIVED]

## dumb-code flags
- `authenticate` loops all records with no `break`; `found` keeps the LAST match — harmless only because `_load` dedupes `key_id` globally (302-306 vs 277-280). [INFERRED]
- `RateLimiter._windows` is only ever written, never pruned — grows with distinct `principal_id`s for the process lifetime (314, 328). [INFERRED]
- `import secrets` is local inside `new_bearer` (339), unlike the top-level import style of the rest.
- Manual `"Z"` -> `"+00:00"` splice before `datetime.fromisoformat` (233).
- `upload_document` and `research_acquire` are denied only by ABSENCE from `TOOL_POLICY`, documented in trailing comments — nothing structural stops someone adding entries (100-101, 78).
- Supplied FACTS label TOOL_POLICY keys as "collections" — mislabel risk when grepping for Qdrant usage (FACTS.collections vs :84-88).

## refactor notes
- Four importers depend on this module: `api/web_auth.py`, `mcp_server.py`, `web_accounts.py`, `web_scope.py` (FACTS.importers) — signature changes to `Principal`, `authorize`, `PrincipalStore.authenticate` hit all four. [DERIVED]
- `WILDCARD = QS.ALL_LIBRARIES` and `CorpusGrant.__contains__` delegate to `QS.grant_allows` (46, 76, 122) — the corpus rule is shared with the web scope; changing `polymath_shared.query_scope` silently changes this gate. [DERIVED]
- `SCHEMA = "polymath_mcp_principals.v1"` is pinned in on-disk registries and checked at load and read (:48, :269, :353) — bumping it orphans every existing principals file. [DERIVED]
- `TOOL_POLICY` keys are wire tool names consumed by the `mcp_server.py` gate; `SUPPLIER_SCOPES` ties six supplier/product tools to `ANY_KNOWLEDGE + ADAPTER_START` (92-99). [DERIVED]
- `PRINCIPAL_HEADER = "x-polymath-principal"` is a trusted loopback-only contract Server A -> orchestrator (53). [DERIVED]
- Profile semantics: stored scopes are a floor unioned with `PROFILES` on read (218) — removing a scope from `FRIEND_SCOPES` does NOT revoke it from records that list it explicitly. [DERIVED]

## VERIFY
```verify
grep -Fq 'SCHEMA = "polymath_mcp_principals.v1"' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'BEARER_RE = re.compile(r"^pmk_([a-f0-9]{8,32})_([A-Za-z0-9_-]{32,128})$")' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'value != WILDCARD and value in allowed' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'FRIEND_SCOPES = tuple(sorted({*FRIEND_PROFILE, UPLOAD_TEXT, HISTORY_READ, ADAPTER_CANCEL, KNOWLEDGE_RESEARCH}))' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'mtime = (st.st_mtime_ns, st.st_ino, st.st_size)' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'if st.st_mode & 0o077:' orchestrator/orchestrator/mcp_principals.py
! grep -Fq 'import requests' orchestrator/orchestrator/mcp_principals.py
test "$(grep -c -F 'return _deny(' orchestrator/orchestrator/mcp_principals.py)" -ge 4
```
