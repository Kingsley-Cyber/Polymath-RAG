# unit: orchestrator/orchestrator/mcp_principals.py
anchor: orchestrator/orchestrator/mcp_principals.py:1-316

## purpose
Smallest durable per-principal authorization layer for the one public MCP door (Server A): principals with action scopes and corpus/adapter allowlists, stored in one JSON file outside the repo — orchestrator/orchestrator/mcp_principals.py:1-18 [DERIVED]. Pure policy + file store; the gate that calls it lives in `mcp_server.py`; run ownership (`adapter_runs.owner_principal_id`) is enforced elsewhere — orchestrator/orchestrator/mcp_principals.py:15-17 [DERIVED]. Default deny; the pre-existing `POLYMATH_MCP_API_KEY` is the built-in OWNER (admin) principal — orchestrator/orchestrator/mcp_principals.py:9-11 [DERIVED].

Module importers (FACTS.importers): `orchestrator/orchestrator/api/web_auth.py`, `orchestrator/orchestrator/mcp_server.py`, `orchestrator/orchestrator/web_accounts.py`, `orchestrator/orchestrator/_small-modules`.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Principal` | class (frozen dataclass) | fields: `principal_id, name="", scopes, corpus_ids, adapter_ids, writable_corpus_ids, rate_per_minute=None, is_admin=False` | orchestrator/orchestrator/mcp_principals.py:72-80 | importers above |
| `Decision` | class (frozen dataclass) | `allowed: bool, reason="ok", message=""` | orchestrator/orchestrator/mcp_principals.py:88-91 | mcp_server.py (gate) |
| `OWNER` | constant | `Principal(principal_id="prn_owner", name="owner", scopes=frozenset(SCOPES), is_admin=True)` | orchestrator/orchestrator/mcp_principals.py:84 | — |
| `hash_key` | def | `(raw: str) -> str` | orchestrator/orchestrator/mcp_principals.py:101-102 | — |
| `authorize` | def | `(p: Principal, tool: str, arguments: dict | None) -> Decision` | orchestrator/orchestrator/mcp_principals.py:105-131 | mcp_server.py (gate, :16) |
| `principal_from_record` | def | `(rec: dict) -> Principal` | orchestrator/orchestrator/mcp_principals.py:142-157 | — |
| `PrincipalStore` | class | `.authenticate(bearer: str | None, now: datetime | None = None) -> Principal | None` | orchestrator/orchestrator/mcp_principals.py:176-240 | mcp_server.py (gate) |
| `RateLimiter` | class | `.allow(p: Principal, now: float | None = None) -> tuple[bool, int]` | orchestrator/orchestrator/mcp_principals.py:243-262 | — |
| `store_from_env` | def | `(owner_key: str) -> PrincipalStore` | orchestrator/orchestrator/mcp_principals.py:265-267 | — |
| `new_bearer` | def | `() -> tuple[str, dict]` | orchestrator/orchestrator/mcp_principals.py:271-275 | scripts/mcp_principals.py (:270) |
| `read_registry` | def | `(path: Path) -> dict` | orchestrator/orchestrator/mcp_principals.py:282-288 | scripts/mcp_principals.py (:270) |
| `write_registry` | def | `(path: Path, doc: dict) -> None` | orchestrator/orchestrator/mcp_principals.py:291-308 | scripts/mcp_principals.py (:270) |
| `write_secret_file` | def | `(path: Path, raw: str) -> None` | orchestrator/orchestrator/mcp_principals.py:311-316 | scripts/mcp_principals.py (:270) |

Key constants: `SCHEMA = "polymath_mcp_principals.v1"` (:34), `OWNER_ID = "prn_owner"` (:38), `PRINCIPAL_HEADER = "x-polymath-principal"` (:39, loopback-only Server A -> orchestrator), `TOOL_POLICY` (:56-68), `FRIEND_PROFILE` (:51), `PROFILES = {"friend": FRIEND_PROFILE}` (:52).

## contracts

**`authorize(p, tool, arguments)` — orchestrator/orchestrator/mcp_principals.py:105-131**
- in: frozen `Principal`, tool name, arbitrary args dict (non-dict coerced to `{}` :110).
- out: `Decision`; `reason` is a stable machine code, never resource details (:90).
- pre: none; post: `p.is_admin` ⇒ `ALLOW` immediately (:108-109). Tool absent from `TOOL_POLICY` ⇒ deny `"tool_not_permitted"` (:111-113). No overlapping scope ⇒ `"insufficient_scope"` (:115-116). Kind `CORPUS` ⇒ `args["corpus_id"]` must be a non-empty str in `p.corpus_ids` else `"corpus_not_allowed"` (:117-118, :134-135). Kind `WRITE_CORPUS` ⇒ checked against `p.writable_corpus_ids`, else `"corpus_not_writable"` (:119-120). Kind `START` ⇒ `adapter_id` in `p.adapter_ids` else `"adapter_not_allowed"`; corpus ids from `input.corpus_ids` + `request_options.corpus_ids` must be non-empty (else `"corpus_required"`) and all in `p.corpus_ids` (:121-130). Kinds `RUN`/others ⇒ `ALLOW` for the static part; run ownership decided by the gate (:106-107, :131).

**`PrincipalStore.authenticate(bearer, now)` — orchestrator/orchestrator/mcp_principals.py:223-240**
- in: raw bearer or None; optional now (default `datetime.now(timezone.utc)` :234).
- out: `Principal` or `None`. Owner key matched with `hmac.compare_digest` ⇒ `OWNER` (:228-229); else bearer must match `BEARER_RE`, key `secret_sha256` compared constant-time, `key_id` match, key not revoked (`revoked_at`), record `_active` (:230-239).

**`principal_from_record(rec)` — orchestrator/orchestrator/mcp_principals.py:142-157**
- pre: `principal_id` matches `^prn_[a-z0-9][a-z0-9_-]{1,58}$` and is not `prn_owner` (:35, :144); scopes ⊆ `SCOPES`, no `admin` (:147-151); `rate_per_minute` is a positive int (bool rejected) if present (:152-154).
- post: raises `ValueError` on any violation; returns frozen `Principal`.

**`PrincipalStore._load()` — orchestrator/orchestrator/mcp_principals.py:186-221**
- reload trigger: mtime tuple `(st_mtime_ns, st_ino, st.st_size)` change — atomic replace = new inode, never missed (:195). File mode with any group/other bit (`st_mode & 0o077`) ⇒ rejected (:199-200). Validates schema, duplicate `principal_id`, duplicate/malformed `key_id`, `secret_sha256` = 64-hex, and rejects any raw-secret field named `secret`/`key`/`bearer` (:202-217).

**`RateLimiter.allow(p, now)` — orchestrator/orchestrator/mcp_principals.py:250-262**
- admin or `rate_per_minute` falsy ⇒ `(True, 0)` (:251-252). Fixed 60s window; over limit ⇒ `(False, max(1, int(60 - (t % 60))))` (:254-260).

**`new_bearer()` — orchestrator/orchestrator/mcp_principals.py:271-275**
- `key_id = secrets.token_hex(6)`; raw = `f"pmk_{key_id}_{secrets.token_urlsafe(32)}"`; record `{"key_id", "secret_sha256": hash_key(raw), "created_at": _now_iso(), "revoked_at": None}`.

**`write_registry(path, doc)` — orchestrator/orchestrator/mcp_principals.py:291-308** — validates every record via `principal_from_record` (:293-294), writes temp `.name.pid.tmp` with `O_EXCL` mode `0o600`, `os.replace`, then `os.chmod(path, 0o600)` (:296-308).

**`write_secret_file(path, raw)` — orchestrator/orchestrator/mcp_principals.py:311-316** — `O_CREAT | O_EXCL`, refuses overwrite, owner-only file (:312-314).

**`read_registry(path)` — orchestrator/orchestrator/mcp_principals.py:282-288** — missing path ⇒ `{"schema": SCHEMA, "principals": []}`; wrong schema ⇒ `ValueError`.

## effect surface
- env: `POLYMATH_MCP_PRINCIPALS_FILE` = `""` (default) — orchestrator/orchestrator/mcp_principals.py:266 [DERIVED].
- files: the principals JSON registry (mtime-watched, required mode 0600) — :199-201; one-time raw-secret files mode 0600 — :313-316; temp registry file `.{name}.{pid}.tmp` — :296.
- network: none ("no network, no database, no MCP import") — :15 [DERIVED].
- Postgres tables: none read/written (FACTS `tables_read`/`tables_written` empty).
- In-memory state: `RateLimiter._windows` dict + `threading.Lock` — :247-248; `PrincipalStore._records`/`_mtime` under lock — :181-183.
- subprocesses: none in SOURCE.

## invariants
INVARIANT: `BEARER_RE` key_id pattern `[a-f0-9]{8,32}` ⊇ `secrets.token_hex(6)` output (12 hex chars) — :37, :273 [INFERRED: token_hex(6) yields 12 hex chars].
  fails-if: a bearer minted by `new_bearer` would not parse in `authenticate`.
INVARIANT: `token_urlsafe(32)` secret length ≥ 32-char minimum of `BEARER_RE` group 2 — :37, :274 [INFERRED: base64url of 32 bytes is 43 chars].
  fails-if: minted bearers rejected at authentication.
INVARIANT: registry key dicts never contain a field named `secret`, `key`, or `bearer` — :216-217 [DERIVED].
  fails-if: raw bearer material persisted in the registry.
INVARIANT: principals file mode has zero group/other bits (`st_mode & 0o077` falsy) — :199-200 [DERIVED].
  fails-if: whole principal set discarded at load (`_records = []`).
INVARIANT: record `principal_id` ≠ `OWNER_ID` (`"prn_owner"`), and `admin` scope appears in no record — :144, :150-151 [DERIVED].
  fails-if: a file principal could impersonate or equal the env-key owner.
INVARIANT: tool ∉ `TOOL_POLICY` ⇒ denied for every non-admin — :111-113 [DERIVED]; `upload_document` ∉ `TOOL_POLICY` ⇒ admin-only — :67 [DERIVED].
  fails-if: default-deny collapses; host-path reads become principal-reachable.
INVARIANT: `FRIEND_PROFILE` = the 3 `knowledge.*` scopes + 6 `adapter.*` scopes, excluding `upload.text`, `history.read`, `admin`, `adapter.cancel` — :42-51 [DERIVED].
  fails-if: friend-profile principals gain write/history/admin reach.
INVARIANT: failed/unreadable registry load ⇒ `_records == []` and `last_error` set — never the previous revoked set — :177-178, :219-220 [DERIVED].
  fails-if: revoked principals keep authenticating.
INVARIANT: unreadable `expires_at` ⇒ treated as expired (`return False`, fail closed) — :166-168 [DERIVED].
  fails-if: malformed expiry silently extends a principal's life.
INVARIANT: secret comparisons are constant time — owner key :228, key digest :237 (`hmac.compare_digest`) [DERIVED].
  fails-if: timing side channel on bearer/owner key.

## determinism & idempotency
determinism: NONDETERMINISTIC (random: `secrets.token_hex` :273, `secrets.token_urlsafe` :274; clock: `time.time` :253, `datetime.now` :234, :279)
idempotency: `authenticate`/`read_registry`/`_load` SAFE (read-only); `write_registry` SAFE (atomic replace, same content in ⇒ same registry out) — :291-308; `write_secret_file` UNSAFE to repeat (O_EXCL refuses overwrite on an existing path) — :313-314.

## failure behaviour
- `PrincipalStore._load` swallows `(OSError, ValueError, AttributeError, TypeError)` into `_records = []` + `last_error` string — :219-220; caller of `authenticate` then sees `None` for every file principal (owner key still works) — :177-178, :226-229.
- `authenticate` returns `None` for missing bearer, non-matching key, revoked key (`revoked_at`), disabled/revoked/expired record — :226-227, :238, :160-172.
- `principal_from_record` raises `ValueError` with messages `"invalid principal_id ..."`, `"... unknown scopes ..."`, `"... the admin scope belongs to the owner key only"`, `"... rate_per_minute must be a positive integer"` — :145, :149, :151, :154.
- `read_registry` raises `ValueError("... expected schema ...")` on schema mismatch — :287.
- Deny codes produced by `authorize`: `tool_not_permitted`, `insufficient_scope`, `corpus_not_allowed`, `corpus_not_writable`, `adapter_not_allowed`, `corpus_required` — :113, :116, :118, :120, :128, :130.
- `RateLimiter.allow` over limit returns `(False, retry_seconds)` — no exception — :259-260.

## dumb-code flags
- FACTS "collections" lists `polymath_search`/`polymath_explore`/`polymath_answer` (:57-59) and `polymath_mcp_principals` (:34) — these are `TOOL_POLICY` dict keys and the `SCHEMA` string, not data collections; static-analysis artifact [DERIVED].
- `authenticate` does not break after a match; the loop keeps scanning all records/keys — :235-240 [DERIVED].
- Mode literals repeated: `0o077` (:199), `0o600` (:297, :308, :314); 60-second window literal appears twice (:254, :260).
- `RateLimiter._windows` is never pruned of stale windows — :247, :256-258 [INFERRED: unbounded dict growth per principal_id].
- `Decision.reason` default `"ok"` plus singleton `ALLOW = Decision(True)` — :90, :94.

## refactor notes
- `TOOL_POLICY` keys ("polymath_search", "retrieve", "retrieve_evidence", "ask", "adapter_start", ...) must stay identical to the MCP tool names dispatched by the gate in `mcp_server.py` — :56-68, :15-16; renaming either side silently makes tools admin-only (default deny).
- `Decision.reason` codes are stable machine strings; the gate and its tests match on them — :90, :113-130.
- `PRINCIPAL_HEADER = "x-polymath-principal"` is the loopback trust contract between Server A and the orchestrator — :39; changing it requires updating both sides.
- `SCHEMA = "polymath_mcp_principals.v1"` is checked by exact equality on both read paths (`_load` :202, `read_registry` :286-287); a bump invalidates every existing principals file.
- Importers `api/web_auth.py`, `mcp_server.py`, `web_accounts.py` (FACTS.importers) depend on `Principal`/`Decision`/`authorize`/`PrincipalStore` shapes; signature changes ripple there.
- Registry helpers are the CLI contract of `scripts/mcp_principals.py` (raw secret returned once, written only via `write_secret_file`) — :270, :311-312.

## VERIFY
```verify
grep -Fq 'SCHEMA = "polymath_mcp_principals.v1"' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'PRINCIPAL_HEADER = "x-polymath-principal"' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'return _deny("corpus_required", "name the corpus ids this run may use (request_options.corpus_ids)")' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'raw = f"pmk_{key_id}_{secrets.token_urlsafe(32)}"' orchestrator/orchestrator/mcp_principals.py
test "$(grep -c -F 'hmac.compare_digest' orchestrator/orchestrator/mcp_principals.py)" -ge 2
! grep -Fq 'import requests' orchestrator/orchestrator/mcp_principals.py
```
