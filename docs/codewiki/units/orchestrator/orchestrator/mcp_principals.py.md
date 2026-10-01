# unit: orchestrator/orchestrator/mcp_principals.py
anchor: orchestrator/orchestrator/mcp_principals.py:1-322

## purpose
Per-principal authorization layer for the single public MCP door (Server A): principals with scoped keys, action scopes, corpus/adapter allowlists, a JSON file store re-read on mtime change, and a fixed-window rate limiter. Pure policy + file store — no network, no database, no MCP import; the enforcing gate lives in `mcp_server.py`. — orchestrator/orchestrator/mcp_principals.py:1-19 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Principal` | class (frozen dataclass) | fields: `principal_id, name, scopes, corpus_ids, adapter_ids, writable_corpus_ids, rate_per_minute, is_admin` | 77-85 | — |
| `Decision` | class (frozen dataclass) | fields: `allowed, reason="ok", message=""` | 93-96 | — |
| `authorize` | def | `(p, tool, arguments) -> Decision` | 110-136 | `orchestrator/orchestrator/mcp_server.py` (the gate) |
| `principal_from_record` | def | `(rec: dict) -> Principal` (raises `ValueError`) | 147-162 | — |
| `PrincipalStore` | class | `authenticate(bearer, now=None) -> Principal \| None` | 181-245 | — |
| `RateLimiter` | class | `allow(p, now=None) -> tuple[bool, int]` | 248-267 | — |
| `store_from_env` | def | `(owner_key: str) -> PrincipalStore` | 270-272 | — |
| `new_bearer` | def | `() -> tuple[str, dict]` (raw bearer, key record) | 276-280 | `scripts/mcp_principals.py` per comment at 275 |
| `read_registry` / `write_registry` | def | `(path, ...) -> dict` / `(path, doc) -> None` | 287-293 / 296-313 | `scripts/mcp_principals.py` per comment at 275 |
| `write_secret_file` | def | `(path, raw) -> None` (refuses overwrite) | 316-321 | `scripts/mcp_principals.py` per comment at 275 |

Module importers (FACTS): `orchestrator/orchestrator/api/web_auth.py`, `orchestrator/orchestrator/mcp_server.py`, `orchestrator/orchestrator/web_accounts.py`, `orchestrator/orchestrator/_small-modules`. — FACTS.importers [DERIVED]

## contracts

**`authorize(p, tool, arguments)` — 110-136**
- in: `Principal`, tool name, arguments dict or None (non-dict coerced to `{}` at 115).
- out: `Decision`; `p.is_admin` short-circuits to `ALLOW` (113-114).
- post: deny reasons emitted: `"tool_not_permitted"` (118), `"insufficient_scope"` (121), `"corpus_not_allowed"` (123, 135), `"corpus_not_writable"` (125), `"adapter_not_allowed"` (128), `"corpus_required"` (133).
- pre/post for `START`: run must name corpus ids in `input.corpus_ids` or `request_options.corpus_ids`; empty means deny `"corpus_required"` — no default corpus (129-133).
- resource kind `RUN` (`adapter_next/submit/status/result/cancel`) returns `ALLOW` for the static part; ownership is decided by the gate via the adapter runtime (111-112, 70, 16-18).

**`PrincipalStore.authenticate(bearer, now=None)` — 228-245**
- in: raw bearer string or None.
- out: `Principal` or None; owner key matched with `hmac.compare_digest` returns `OWNER` (233-234).
- post: key id from `BEARER_RE` group 1 must equal record `key_id`; sha256 of bearer compared constant-time to `secret_sha256`; key not revoked; `_active(rec, now)` true (242-243). Disabled/revoked/expired never authenticate (229-230).

**`principal_from_record(rec)` — 147-162**
- raises `ValueError` on: bad `principal_id` (not `PRINCIPAL_ID_RE` or `== OWNER_ID`, 149-150), unknown scopes (153-154), `ADMIN` in scopes (155-156), `rate_per_minute` not a positive int (157-159).

**`write_registry(path, doc)` — 296-313**
- pre: every record passes `principal_from_record` (298-299).
- post: written via temp file mode `0o600` + `os.replace` + `chmod(path, 0o600)`; reader sees old or new, never half (300-313).

## effect surface
- env: `POLYMATH_MCP_PRINCIPALS_FILE` = default `''` — 271 [DERIVED]
- files read: principals JSON (stat 196, read_text 212); files written: registry JSON (296-313), raw-bearer secret file mode `0o600` (316-321) [DERIVED]
- Postgres tables: none (FACTS.tables_read/tables_written empty); network/subprocess: none — 15 [DERIVED]
- tool names in `TOOL_POLICY` (not storage): `polymath_search`, `polymath_explore`, `polymath_answer`, `polymath_compare`, `polymath_deep_research`, `polymath_models` — 60-64 [DERIVED]
- clock/random: `time.time` 258, `datetime.now` 239/284, `secrets.token_hex` 278, `secrets.token_urlsafe` 279 [DERIVED]

## invariants
- INVARIANT: `OWNER.scopes == set(SCOPES)` (14 scopes) and `is_admin=True` — 89, 48-51 [DERIVED]; fails-if: env owner key loses the admin bypass and gets policy-checked like a friend.
- INVARIANT: `len(FRIEND_PROFILE) == 10` — the 3 `ANY_KNOWLEDGE` + 7 adapter scopes; excludes `HISTORY_READ`, `UPLOAD_TEXT`, `ADMIN`, `KNOWLEDGE_RESEARCH` — 54 [DERIVED]; fails-if: friend profile silently gains history/upload/admin/deep-research.
- INVARIANT: every tool absent from `TOOL_POLICY` is admin-only (default deny) — 57-58, 116-118 [DERIVED]; fails-if: a new tool becomes callable by any authenticated principal.
- INVARIANT: a key record containing `"secret"`, `"key"`, or `"bearer"` is rejected — the registry never holds a raw secret — 221-222 [DERIVED].
- INVARIANT: unreadable or invalid principals file ⇒ `_records == []` (never the previous, possibly revoked set) — 182-183, 224-225 [DERIVED].
- INVARIANT: reload trigger is `(st_mtime_ns, st_ino, st_size)`; an atomic `os.replace` is a new inode, never missed — 200, 309 [DERIVED].
- INVARIANT: principals file with `st_mode & 0o077` bits set is rejected — 204-205 [DERIVED].
- INVARIANT: `new_bearer()` key_id is 12 hex chars (`token_hex(6)`), inside `KEY_ID_RE` `{8,32}`; secret part is `token_urlsafe(32)` inside `{32,128}` — 36-37, 278-279 [DERIVED].
- INVARIANT: rate window length is 60 s fixed (`int(t // 60)`); retry hint `max(1, int(60 - (t % 60)))` — 259, 265 [DERIVED].

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `time.time` 258, `datetime.now` 239/284; random: `secrets.token_hex` 278, `secrets.token_urlsafe` 279; env: `POLYMATH_MCP_PRINCIPALS_FILE` 271; concurrency: `threading.Lock` 188, 253)
idempotency: SAFE — `authorize`/`authenticate` are pure/read-only; `write_registry` is atomic old-or-new via temp+`os.replace` (296-309); UNSAFE — `write_secret_file` re-run fails (`O_EXCL`, refuses overwrite, 319).

## failure behaviour
- `_load` swallows `(OSError, ValueError, AttributeError, TypeError)` into `_records=[]` + `last_error` string — callers see zero principals (fail closed); owner key still authenticates — 224-225, 182-183, 233-234 [DERIVED].
- `authenticate` returns `None` on no match; never raises for bad bearer shape — 228-245 [DERIVED].
- `_active`: unreadable `expires_at` is treated as expired (fail closed) — 171-173 [DERIVED].
- `principal_from_record` / `read_registry` / `write_registry` raise `ValueError` on invalid input — 149-159, 291-292, 298-299 [DERIVED].
- `Decision.reason` is a stable machine code and "never carries resource details" — 95 [DERIVED].

## dumb-code flags
- `_mtime` is committed even when parsing failed (226): an invalid file is not re-parsed until mtime/inode/size changes; `last_error` is sticky — 225-226 [DERIVED].
- `authenticate` keeps scanning after a match; `found` is overwritten, so the last matching record/key wins — 240-244 [DERIVED].
- Inline regex `[0-9a-f]{64}` duplicates the sha256 digest length implied by `hash_key` — 219 vs 106-107 [DERIVED].
- Magic modes repeated: `0o077` at 204, `0o600` at 302, 313, 319 [DERIVED].
- Alias tool names `"retrieve"`, `"retrieve_evidence"`, `"compile_plan"`, `"ask"` duplicate the policy tuples of their canonical tools — 60-62 [DERIVED].
- `upload_document` exists only as a comment (72); its admin-only status is enforced by absence from `TOOL_POLICY`, not by an entry — 57-58, 72 [INFERRED: no entry means default deny].
- `RateLimiter._windows` is never pruned; entries accumulate per `principal_id` — 252 [INFERRED: bounded only by principal count].

## refactor notes
- Signature changes to `Principal`, `PrincipalStore`, `authenticate`, `authorize`, or `store_from_env` hit all four importers (`api/web_auth.py`, `mcp_server.py`, `web_accounts.py`, `_small-modules`) — FACTS.importers [DERIVED].
- `Decision.reason` codes are a machine contract consumed by the gate; renaming them breaks `mcp_server.py` — 95, 15-16 [DERIVED].
- Changing `SCHEMA = "polymath_mcp_principals.v1"` orphans every existing principals file (load and read both require exact match) — 34, 207, 291 [DERIVED].
- `TOOL_POLICY` edits change authorization for every non-admin caller in one place — 57-73 [DERIVED].
- `PRINCIPAL_HEADER = "x-polymath-principal"` is a wire contract, trusted loopback-only (Server A -> orchestrator) — 39 [DERIVED].
- Run ownership must stay out of `authorize`: it is `adapter_runs.owner_principal_id`, persisted/enforced by the adapter runtime from the gate's forwarded principal context — 16-18 [DERIVED].

## VERIFY
```verify
grep -Fq 'SCHEMA = "polymath_mcp_principals.v1"' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'return _deny("corpus_required"' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'x-polymath-principal' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'os.replace(tmp, path)' orchestrator/orchestrator/mcp_principals.py
! grep -Fq 'qdrant' orchestrator/orchestrator/mcp_principals.py
test "$(grep -c -F 'hmac.compare_digest' orchestrator/orchestrator/mcp_principals.py)" -ge 2
```
