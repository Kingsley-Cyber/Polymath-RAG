# unit: shared/polymath_shared/product_search/report_store.py
anchor: shared/polymath_shared/product_search/report_store.py:1-488

## purpose
Postgres store for PRODUCT-DECISION-REPORT-V1 (B4b, plan §4.6) decision reports over tables `product_reports` / `product_report_uploads` (migration 0068) — shared/polymath_shared/product_search/report_store.py:1-2 [DERIVED].
Mints report ids and upload tokens (sha256-only storage), enforces capability checks, upload caps, status compare-and-set and principal privacy — shared/polymath_shared/product_search/report_store.py:5-31 [DERIVED].
Every function takes an open psycopg connection from `polymath_shared.db.tx`; the caller owns the transaction — shared/polymath_shared/product_search/report_store.py:3-4 [DERIVED].
No network, no model — shared/polymath_shared/product_search/report_store.py:31 [DERIVED].

## public surface
Sole importer (module-level, from FACTS.importers): `orchestrator/orchestrator/api/product_report.py`; per-symbol use not in FACTS.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| UnknownReport | class | LookupError; no report for this caller | shared/polymath_shared/product_search/report_store.py:73-74 | product_report.py* |
| UploadRefused | class | (code, status, message); .detail() -> {error_code, message} | shared/polymath_shared/product_search/report_store.py:77-85 | product_report.py* |
| MintTooSoon | class | (mint_after: datetime) | shared/polymath_shared/product_search/report_store.py:88-93 | product_report.py* |
| BadTransition | class | (current, wanted) -> RuntimeError | shared/polymath_shared/product_search/report_store.py:96-101 | product_report.py* |
| create | def | (conn, *, owner_principal_id, request, candidates, host=None, at=None) -> (row, raw token) | shared/polymath_shared/product_search/report_store.py:281-293 | product_report.py* |
| mint_token | def | (conn, report_id, *, at=None, every_s=None) -> str | shared/polymath_shared/product_search/report_store.py:296-312 | product_report.py* |
| mark_used | def | (conn, report_id, token, *, at=None) -> None | shared/polymath_shared/product_search/report_store.py:315-321 | product_report.py* |
| get | def | (conn, report_id, *, principal_id, for_update=False, with_html=False) -> dict | shared/polymath_shared/product_search/report_store.py:324-335 | product_report.py* |
| well_formed_capability | def | (report_id, token) -> bool | shared/polymath_shared/product_search/report_store.py:338-339 | product_report.py* |
| check_capability | def | (row, token, at=None) -> None (raises) | shared/polymath_shared/product_search/report_store.py:342-350 | product_report.py* |
| check_upload | def | (size, packet_id, *, replaced, held) -> None (raises) | shared/polymath_shared/product_search/report_store.py:353-361 | product_report.py* |
| by_capability | def | (conn, report_id, token, *, at=None, for_update=False) -> dict | shared/polymath_shared/product_search/report_store.py:364-373 | product_report.py* |
| list_for | def | (conn, principal_id, *, limit=50, before=None) -> list[dict] | shared/polymath_shared/product_search/report_store.py:376-395 | product_report.py* |
| html_of | def | (conn, report_id, *, principal_id) -> str \| None | shared/polymath_shared/product_search/report_store.py:398-400 | product_report.py* |
| save_candidates / save_host / save_model / save_verdicts / save_html | def | (conn, report_id, value) -> None | shared/polymath_shared/product_search/report_store.py:408-425 | product_report.py* |
| transition | def | (conn, report_id, wanted, *, current, at=None) -> None | shared/polymath_shared/product_search/report_store.py:428-439 | product_report.py* |
| advance_round | def | (conn, report_id, *, current) -> bool | shared/polymath_shared/product_search/report_store.py:442-448 | product_report.py* |
| uploads | def | (conn, report_id, *, round_=None) -> list[dict] | shared/polymath_shared/product_search/report_store.py:452-458 | product_report.py* |
| add_upload | def | (conn, report_id, *, packet_id, round_, source, kind, raw, status, parsed, refused, at=None) -> dict | shared/polymath_shared/product_search/report_store.py:461-488 | product_report.py* |
| now / iso / stamp | def | time helpers; iso -> "Z"-suffixed seconds; stamp -> "%Y-%m-%dT%H:%M:%S.%fZ" | shared/polymath_shared/product_search/report_store.py:105-129 | product_report.py* |
| new_report_id / new_upload_token | def | () -> "rpt_"+24 hex / token_urlsafe(32) | shared/polymath_shared/product_search/report_store.py:118-123 | product_report.py* |
| tokens_of / held / last_minted / with_token / touched | def | token-list helpers | shared/polymath_shared/product_search/report_store.py:132-169 | product_report.py* |
| token_sha256 / content_sha256 | def | (x) -> sha256 hexdigest | shared/polymath_shared/product_search/report_store.py:172-177 | product_report.py* |
| strip_nul | def | (value) -> value without U+0000 | shared/polymath_shared/product_search/report_store.py:180-188 | product_report.py* |
| uploads_digest | def | (rows) -> sha256 over sorted "packet_id:sha256" pairs | shared/polymath_shared/product_search/report_store.py:195-199 | product_report.py* |
| expired / capability_state | def | (row, ...) -> bool / 'absent'\|'invalid'\|'expired'\|'valid' | shared/polymath_shared/product_search/report_store.py:214-227 | product_report.py* |
| check_transition | def | (current, wanted) -> None (raises BadTransition) | shared/polymath_shared/product_search/report_store.py:230-232 | product_report.py* |
| upload_counts | def | (rows) -> {total, by_round, by_source} | shared/polymath_shared/product_search/report_store.py:235-246 | product_report.py* |
| round_targets | def | (rows, round_=1) -> list of next-round targets | shared/polymath_shared/product_search/report_store.py:249-264 | product_report.py* |
| parsed_by_candidate | def | (rows, candidate_ids) -> {cid: {source: [records]}} | shared/polymath_shared/product_search/report_store.py:267-277 | product_report.py* |

\* FACTS.importers (module import only).

## contracts
**create** — shared/polymath_shared/product_search/report_store.py:281-293
- in: conn; owner_principal_id str\|None; request, candidates Mapping; host Mapping\|None = None; at datetime\|None = None.
- out: (report row, RAW upload token) — token returned once, only sha256 stored — :283-284, :292.
- post: row status 'collecting', round 1, upload_expires_at = at + UPLOAD_TTL — :286-292.

**mint_token** — shared/polymath_shared/product_search/report_store.py:296-312
- pre: caller already checked who may see the report — :299-300.
- out: RAW token (shown once, never stored) — :299-300, :309-312.
- post: row locked `FOR UPDATE`, hash joins held list — :301, :306-311.
- raises: UnknownReport :302-303; MintTooSoon(mint_after) when newest token younger than every_s — :304-308.

**get** — shared/polymath_shared/product_search/report_store.py:324-335
- principal_id None = owner, sees any report; a principal only its own; anything else UnknownReport (one answer for missing and foreign) — :324-334, :14-16.
- for_update appends `FOR UPDATE`; with_html adds the `html` column — :328-332.

**check_capability / by_capability** — shared/polymath_shared/product_search/report_store.py:342-350, :364-373
- 403 UPLOAD_TOKEN_INVALID for no row / malformed / unheld token (other report's or dropped included); 410 UPLOAD_EXPIRED only for a held token past expiry — :342-350.
- expired() treats upload_expires_at None as expired — :214-218.

**add_upload** — shared/polymath_shared/product_search/report_store.py:461-488
- pre: caller holds the report row lock (`get(..., for_update=True)`) so the count cannot race — :22-24, :460-466.
- out: {replaced, kept_earlier, bytes, sha256, uploads} — :483-488.
- post: upsert ON CONFLICT (report_id, packet_id); a stored OK row is never replaced by a non-OK upload — :473-485.

**transition / advance_round** — shared/polymath_shared/product_search/report_store.py:428-448
- CAS `current` -> `wanted` along TRANSITIONS only; move to 'compiling' stamps compile_started_at — :428-437; BadTransition when rowcount != 1 — :438-439.
- round current -> current+1 at most MAX_ROUND; returns False at cap — :442-448.

**list_for** — shared/polymath_shared/product_search/report_store.py:376-395
- newest first, limit clamped to 1..200, `before` is a report_id cursor; `compiled` = `html IS NOT NULL`; no HTML or capability hash leaves — :386-395.

**uploads_digest** — shared/polymath_shared/product_search/report_store.py:195-199
- identity of stored uploads; a compiled report is stale when the digest changes — :196-197.

## effect surface
- Postgres read: `product_reports`, `product_report_uploads` (FACTS.tables_read) — e.g. shared/polymath_shared/product_search/report_store.py:301, :329-332, :369, :388-394, :453, :468-470.
- Postgres written: `product_reports`, `product_report_uploads` (FACTS.tables_written) — shared/polymath_shared/product_search/report_store.py:287-292, :306-311, :316-321, :400, :424-425, :429-437, :446-447, :473-484.
- FACTS.tables_written also lists `set`: SQL `UPDATE ... SET` keyword, not a table — shared/polymath_shared/product_search/report_store.py:400 [INFERRED].
- Qdrant / files / network / subprocess: none — shared/polymath_shared/product_search/report_store.py:31 [DERIVED].
- env flags read: none visible.
- nondeterminism calls (FACTS): `_dt.datetime.now` :106; `secrets.token_urlsafe` :123; `secrets.token_hex` :119 — shared/polymath_shared/product_search/report_store.py:105-123.

## invariants
INVARIANT: len(upload_tokens) <= MAX_TOKENS (30) after any mint — shared/polymath_shared/product_search/report_store.py:53-54, :157-164 [DERIVED]
  fails-if: unbounded jsonb token list; eviction of active uploaders' tokens.
INVARIANT: token entry = {sha256, minted_at, used_at}; raw token never stored — shared/polymath_shared/product_search/report_store.py:161, :299-300 [DERIVED]
  fails-if: a database read yields a usable upload capability.
INVARIANT: upload_expires_at = at + UPLOAD_TTL (6 h); every token dies with it — shared/polymath_shared/product_search/report_store.py:52, :285, :292 [DERIVED]
  fails-if: expired() misclassifies; 410 vs valid flips.
INVARIANT: REPORT_ID_RE `^rpt_[0-9a-f]{24}$` matches new_report_id() = "rpt_" + secrets.token_hex(12) — shared/polymath_shared/product_search/report_store.py:63, :118-119 [DERIVED]
  fails-if: get() raises UnknownReport on real ids.
INVARIANT: TOKEN_RE `^[A-Za-z0-9_-]{43}$` matches secrets.token_urlsafe(32) — shared/polymath_shared/product_search/report_store.py:64, :122-123 [DERIVED]
  fails-if: held() rejects valid tokens, uploads get 403.
INVARIANT: NEW packet only while held < MAX_UPLOADS (300); re-upload of a held packet does not count — shared/polymath_shared/product_search/report_store.py:359-361, :467-471 [DERIVED]
  fails-if: unbounded packet rows.
INVARIANT: len(raw) <= MAX_UPLOAD_BYTES (2 * 1024 * 1024) — shared/polymath_shared/product_search/report_store.py:57-58, :356-357 [DERIVED]
  fails-if: oversize writes; drift from agent_reach.MAX_REPORT_BYTES.
INVARIANT: status moves only along TRANSITIONS (compiled->compiling and failed->compiling allowed) as a CAS — shared/polymath_shared/product_search/report_store.py:46-51, :230-232, :428-439 [DERIVED]
  fails-if: concurrent status overwrites.
INVARIANT: round <= MAX_ROUND (2) — shared/polymath_shared/product_search/report_store.py:444-445 [DERIVED]
  fails-if: endless re-fetch rounds.
INVARIANT: stored OK upload row never replaced by a non-OK one — shared/polymath_shared/product_search/report_store.py:477-485 [DERIVED]
  fails-if: keyless re-run destroys good packets.
INVARIANT: token hash compares constant-time via hmac.compare_digest — shared/polymath_shared/product_search/report_store.py:142 [DERIVED]
  fails-if: timing oracle over held hashes.
INVARIANT: U+0000 stripped from every JSON write and the HTML — shared/polymath_shared/product_search/report_store.py:180-192, :424-425 [DERIVED]
  fails-if: Postgres jsonb/text rejects the write.
INVARIANT: mint rate — at most one mint per report per MINT_EVERY_S (60) for callers without a token (contract C1) — shared/polymath_shared/product_search/report_store.py:6-8, :55-56, :304-308 [DERIVED]
  fails-if: token mint spam via the status route.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `_dt.datetime.now(_dt.UTC)` shared/polymath_shared/product_search/report_store.py:106; random `secrets.token_hex` :119 and `secrets.token_urlsafe` :123; db — row locks :301, :318 and CAS rowcount :438, :446-448) [DERIVED]
idempotency: add_upload SAFE per (report_id, packet_id) — re-upload replaces the row shared/polymath_shared/product_search/report_store.py:473-481; create UNSAFE to retry (mints a new report_id each call) :286; mint_token UNSAFE to blind-retry within every_s (MintTooSoon) :304-308 [DERIVED]

## failure behaviour
No FACTS.fallbacks present; visible swallow points:
- mark_used silently no-ops when the report row is gone — shared/polymath_shared/product_search/report_store.py:315-321.
- add_upload's upsert keeps the earlier OK row and reports it only via kept_earlier=True, no error — shared/polymath_shared/product_search/report_store.py:481-485.

| error | HTTP | trigger | anchor |
|---|---|---|---|
| UPLOAD_TOKEN_INVALID | 403 | no row, malformed token, unheld hash (another report's / dropped included) | shared/polymath_shared/product_search/report_store.py:342-347 |
| UPLOAD_EXPIRED | 410 | held token, capability past expiry | shared/polymath_shared/product_search/report_store.py:348-350 |
| UPLOAD_TOO_LARGE | 413 | len(raw) > 2 MiB | shared/polymath_shared/product_search/report_store.py:356-357 |
| UNKNOWN_PACKET | 404 | packet_id fails PACKET_ID_RE | shared/polymath_shared/product_search/report_store.py:358-359 |
| UPLOAD_LIMIT_REACHED | 409 | NEW packet at 300 held | shared/polymath_shared/product_search/report_store.py:360-361 |
| UnknownReport (LookupError) | — | missing / another principal's / malformed report_id | shared/polymath_shared/product_search/report_store.py:73-74, :326-327, :333-334 |
| MintTooSoon | — | newest token younger than every_s; carries mint_after | shared/polymath_shared/product_search/report_store.py:88-93, :304-308 |
| BadTransition (RuntimeError) | — | illegal edge or CAS lost | shared/polymath_shared/product_search/report_store.py:96-101, :434-439 |

## dumb-code flags
- FACTS.tables_written contains `set` — UPDATE ... SET keyword parsed as a table, not a write target — shared/polymath_shared/product_search/report_store.py:400 [INFERRED: static parser misread].
- add_upload calls check_upload twice: first with replaced=False, held=0 so size/packet-id refuse before any read, then with real values — shared/polymath_shared/product_search/report_store.py:467, :471.
- `held` is a module function :136 and also a parameter name in check_upload :353 and a local in add_upload :470 — shadowing — shared/polymath_shared/product_search/report_store.py:136, :353, :470.
- MAX_UPLOAD_BYTES (2 MiB) duplicated as agent_reach.MAX_REPORT_BYTES; a test pins the two, no import — shared/polymath_shared/product_search/report_store.py:57-58.
- list_for clamps limit inline: `max(1, min(int(limit), 200))` — literal 200, no named constant — shared/polymath_shared/product_search/report_store.py:394.
- Token list departs from plan §4.6's single `upload_token_sha256` — unapproved deviation, flagged in the module docstring — shared/polymath_shared/product_search/report_store.py:9-12.

## refactor notes
- Sole importer: orchestrator/orchestrator/api/product_report.py (FACTS.importers); column JSON shapes are that service's: `candidates` {status, source, items, error, ...}, `host` {status, started_at, finished_at, error, data}, `model` {compiled_at, decision, ...}, `verdicts` {by, items} — shared/polymath_shared/product_search/report_store.py:29-30.
- Never open/commit a transaction inside: every function assumes the caller's psycopg connection — shared/polymath_shared/product_search/report_store.py:3-4.
- add_upload depends on the caller holding the report row lock (`get(..., for_update=True)`) for the count race — shared/polymath_shared/product_search/report_store.py:22-24, :460-466.
- Keep MAX_UPLOAD_BYTES == agent_reach.MAX_REPORT_BYTES (test-pinned) — shared/polymath_shared/product_search/report_store.py:57-58.
- Token entry shape {sha256, minted_at, used_at} is load-bearing across held/last_minted/_activity/with_token/touched; stamp format "%Y-%m-%dT%H:%M:%S.%fZ" is fixed-width so stamps order as strings — shared/polymath_shared/product_search/report_store.py:126-169.
- TRANSITIONS re-allows compile (compiled -> compiling, failed -> compiling); stale-compile recovery reads compile_started_at — shared/polymath_shared/product_search/report_store.py:45-51, :429-434.

## VERIFY
```verify
grep -Fq 'MAX_TOKENS = 30' shared/polymath_shared/product_search/report_store.py
grep -Fq 'MAX_UPLOADS = 300' shared/polymath_shared/product_search/report_store.py
grep -Fq 'UPLOAD_TTL = _dt.timedelta(hours=6)' shared/polymath_shared/product_search/report_store.py
grep -Fq 'TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")' shared/polymath_shared/product_search/report_store.py
grep -Fq 'frozenset({"compiling", "failed"})' shared/polymath_shared/product_search/report_store.py
test "$(grep -c -F 'UploadRefused(' shared/polymath_shared/product_search/report_store.py)" -ge 5
! grep -Fq 'import requests' shared/polymath_shared/product_search/report_store.py
```
