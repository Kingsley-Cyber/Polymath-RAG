# unit: orchestrator/orchestrator/mcp_principals.py
anchor: orchestrator/orchestrator/mcp_principals.py:1-394

## purpose
Pure policy + file-store layer for per-principal authorization on the one public door (Server A): principals with bearer keys (`pmk_<key_id>_<secret>`), action scopes, corpus/adapter grants, default-deny tool policy, an mtime-reloaded JSON registry, and a fixed-window rate limiter. The MCP gate that calls it lives in mcp_server.py. No network, no database, no MCP import. — orchestrator/orchestrator/mcp_principals.py:1-31 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| CorpusGrant | class (frozenset subclass) | `__contains__(corpus_id) -> bool`, `.every -> bool` | 109-126 | web_scope (per docstring 22-23) |
| Principal | dataclass(frozen=True) | fields: principal_id, name, scopes, corpus_ids, adapter_ids, writable_corpus_ids, rate_per_minute, is_admin | 130-142 | importers below |
| Decision | dataclass(frozen=True) | fields: allowed, reason="ok", message | 150-153 | importers below |
| OWNER | constant | `Principal(principal_id="prn_owner", ..., is_admin=True)` | 146 | — |
| TOOL_POLICY | dict | tool -> ((any-of scopes, resource kind)) | 84-106 | gate in mcp_server.py (docstring 29) |
| authorize | def | (p: Principal, tool: str, arguments: dict) -> Decision | 167-199 | mcp_server.py |
| hash_key | def | (raw: str) -> sha256 hexdigest | 163-164 | — |
| principal_from_record | def | (rec: dict) -> Principal (raises ValueError) | 217-235 | importers below |
| PrincipalStore | class | `authenticate(bearer, now=None) -> Principal \| None` | 254-318 | web_auth.py, mcp_server.py |
| RateLimiter | class | `allow(p, now=None) -> (bool, int)` | 321-340 | — |
| store_from_env | def | (owner_key: str) -> PrincipalStore | 343-345 | — |
| new_bearer | def | () -> (raw, {"key_id", "secret_sha256", "created_at", "revoked_at"}) | 349-353 | scripts/mcp_principals.py (comment 348) |
| read_registry | def | (path: Path) -> dict | 360-366 | scripts |
| write_registry | def | (path: Path, doc: dict) -> None | 369-386 | scripts |
| write_secret_file | def | (path: Path, raw: str) -> None | 389-394 | scripts |

Importers (FACTS): orchestrator/orchestrator/api/web_auth.py, orchestrator/orchestrator/mcp_server.py, orchestrator/orchestrator/web_accounts.py, orchestrator/orchestrator/web_scope.py.

## contracts
**authorize(p, tool, arguments) -> Decision** — 167-199
- in: any Principal, tool name, arguments dict or None.
- pre: `p.is_admin` short-circuits to `ALLOW` (170-171); non-dict arguments treated as `{}` (172).
- out: `Decision(False, reason, message)` with reason one of `"tool_not_permitted"`, `"insufficient_scope"`, `"corpus_not_allowed"`, `"corpus_not_writable"`, `"adapter_not_allowed"`; else `ALLOW` (175-199).
- post: run ownership (kind RUN) is NOT decided here — gate asks the adapter runtime (168-169, docstring 29-30).

**PrincipalStore.authenticate(bearer, now=None) -> Principal | None** — 301-318
- in: raw bearer or None; owner key matched first via `hmac.compare_digest` (306-307).
- out: Principal for a live key whose `key_id` matches `BEARER_RE` group 1 and sha256 matches and `not key.get("revoked_at")` and `_active(rec, now)` (316); else None.
- pre: registry re-read only when `(st_mtime_ns, st_ino, st_size)` changes (273-275).

**principal_from_record(rec) -> Principal** — 217-235
- raises `ValueError` on: bad/owner-colliding principal_id (219-220), unknown scopes (223-224), `ADMIN` in scopes (225-227), non-positive `rate_per_minute` (231-232).
- post: profile-tagged records union the profile's CURRENT scopes: `scopes | frozenset(PROFILES.get(...))` (229).

**write_registry(path, doc)** — 369-386
- pre: every record validated via `principal_from_record` (371-372).
- post: temp file mode `0o600`, `os.fsync`, `os.replace`, then `os.chmod(path, 0o600)` (375-387).

**RateLimiter.allow(p, now=None) -> (bool, int)** — 328-340
- admin or no `rate_per_minute` -> `(True, 0)` (329-330).
- deny returns retry seconds `max(1, int(60 - (t % 60)))` (338).

## effect surface
- env: `POLYMATH_MCP_PRINCIPALS_FILE` = `''` (missing = no principals file) — 343-345.
- files: principals JSON read (`read_text`, 280) and written atomically (369-386); raw bearer written once to a new owner-only file (389-394).
- network / Postgres / Qdrant: none — "no network, no database" (28); FACTS `tables_read`/`tables_written` empty. The FACTS "collections" strings (`polymath_search`, etc.) are TOOL_POLICY keys / the SCHEMA literal, not vector stores — 48, 84-88.
- imports: `polymath_shared`, `polymath_shared.query_scope` (46).

## invariants
INVARIANT: SCHEMA == `"polymath_mcp_principals.v1"` and both loader and reader reject any other schema — 48, 280-281, 364-365 [DERIVED]
  fails-if: registry silently ignored (loader) or `read_registry` raises ValueError.
INVARIANT: stored records with `ADMIN` in scopes == 0 — 226-227 [DERIVED]
  fails-if: ValueError at load; `_load` fail-closes to `_records = []` (297-299).
INVARIANT: `pid == OWNER_ID` ("prn_owner") never accepted from a record — 52, 219-220 [DERIVED]
  fails-if: a file record could impersonate the env-key owner principal.
INVARIANT: `secret_sha256` matches `[0-9a-f]{64}`; `key_id` matches `^[a-f0-9]{8,32}$`; bearer matches `^pmk_([a-f0-9]{8,32})_([A-Za-z0-9_-]{32,128})$` — 50-51, 289-293 [DERIVED]
  fails-if: invalid registry rejected at load; malformed bearer never authenticates (308).
INVARIANT: registry key objects containing `"secret"`, `"key"`, or `"bearer"` == 0 — 294-295 [DERIVED]
  fails-if: ValueError — a raw secret can never live in the registry.
INVARIANT: `st.st_mode & 0o077 == 0` for the principals file — 277-278 [DERIVED]
  fails-if: load treated as invalid → no principals (fail closed).
INVARIANT: `_allowed(value, ...)` is False when `value == WILDCARD` ("*" names no library) — 76, 203 [DERIVED]
  fails-if: a caller could name `"*"` as a corpus_id and bypass the explicit-id check.
INVARIANT: RateLimiter denies iff `count >= p.rate_per_minute` in window `int(t // 60)` — 332-338 [DERIVED]
  fails-if: per-principal rate cap stops being enforced.
INVARIANT: unreadable `expires_at` ⇒ `_active` returns False — 244-246 [DERIVED]
  fails-if: fail-closed expiry would become fail-open.

## determinism & idempotency
determinism: NONDETERMINISTIC (random: `secrets.token_hex` 351, `secrets.token_urlsafe` 352; clock: `time.time` 331, `datetime.now` 312, `datetime.now` 357) [DERIVED]
idempotency: SAFE for `authenticate`/`read_registry` (read-only) and `write_registry` (atomic `os.replace`); UNSAFE for `RateLimiter.allow` (each call increments the window counter, 339) and `write_secret_file` (`os.O_EXCL` refuses a second write to the same path, 393) [DERIVED]

## failure behaviour
- `_load` catches `(OSError, ValueError, AttributeError, TypeError)` → `_records = []`, `last_error = "<ExcType>: msg"`; callers see zero principals, never the previous possibly-revoked set — 297-299 [DERIVED].
- Missing file → no principals, owner key still works — 270-272, docstring 12-13 [DERIVED].
- `authenticate` returns None (no exception) for unknown/disabled/revoked/expired — 301-318 [DERIVED].
- `principal_from_record`, `read_registry` raise `ValueError` with messages naming the principal_id — 220-232, 365 [DERIVED].
- `os.open(..., os.O_EXCL)` in `write_registry`/`write_secret_file` raises if the tmp/secret path exists — 375, 393 [DERIVED].

## dumb-code flags
- Kinds `CORPUS_FILTER` and `ADAPTER_FILTER` are declared (79) and used by TOOL_POLICY (`list_corpora` 89, `adapter_list` 92) but `authorize` has no branch for them — they pass on scope check alone and fall through to `return ALLOW` (199). Same fall-through for `NONE`. [DERIVED]
- Double permission-setting in `write_registry`: `os.open(..., 0o600)` (375) plus `os.chmod(path, 0o600)` after replace (387). [DERIVED]
- `WILDCARD = QS.ALL_LIBRARIES` — two names for one value across modules (76). [DERIVED]
- `SUPPLIER_SCOPES = (*ANY_KNOWLEDGE, ADAPTER_START)` duplicates the scope union already embedded in FRIEND_PROFILE/FRIEND_SCOPES (68-75). [DERIVED]
- One physical line 84 packs three tool entries (`polymath_search`, `retrieve`, `retrieve_evidence`) — grep-per-line tool lookups will miss two of three. [DERIVED]

## refactor notes
- Four importers (api/web_auth.py, mcp_server.py, web_accounts.py, web_scope.py) compile against `Principal`, `PrincipalStore`, `authorize` — signature changes hit all four (FACTS.importers). [DERIVED]
- `CorpusGrant.__contains__` delegates to `QS.grant_allows` (46, 126): any change to `polymath_shared.query_scope` semantics changes every corpus check here and in the web scope (docstring 22-23). [DERIVED]
- Deny reasons (`"corpus_not_allowed"`, `"insufficient_scope"`, ...) are stable machine codes; clients may match them — renaming breaks consumers (152, 175-198). [DERIVED]
- `PRINCIPAL_HEADER = "x-polymath-principal"` is trusted loopback-only (Server A → orchestrator); must never be accepted off-loopback (53). [DERIVED]
- A tool absent from TOOL_POLICY is admin-only (78, 173-175): adding a tool without a policy entry silently restricts it to the owner key. [DERIVED]
- `Decision.reason` default is `"ok"`, and `ALLOW = Decision(True)` relies on that default (152, 156). [DERIVED]

## VERIFY
```verify
grep -Fq 'POLYMATH_MCP_PRINCIPALS_FILE' orchestrator/orchestrator/mcp_principals.py
grep -Fq '"polymath_mcp_principals.v1"' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'x-polymath-principal' orchestrator/orchestrator/mcp_principals.py
grep -Eq 'def authorize\(p: Principal, tool: str' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'hmac.compare_digest' orchestrator/orchestrator/mcp_principals.py
test "$(grep -c -F 'corpus_not_allowed' orchestrator/orchestrator/mcp_principals.py)" -ge 2
! grep -Fq 'print(' orchestrator/orchestrator/mcp_principals.py
```
