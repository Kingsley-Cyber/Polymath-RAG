# unit: adapters/ecommerce/python/corpus_polymath.py
anchor: adapters/ecommerce/python/corpus_polymath.py:1-788

## purpose
Reference corpus adapter (docs/18) that turns Polymath backend responses into contract rows `{id, summary, source}`; the AGENT runs it at `corpus_retrieve` nodes — the controller never talks to a corpus — and it prints the exact payload `controller.py submit --node corpus` accepts. — adapters/ecommerce/python/corpus_polymath.py:2-10 [DERIVED]
v2.2.0 EVIDENCE BOUNDARY (docs/22): asks Polymath for evidence, never an answer; the only POST paths reachable are `ALLOWED_POST_PATHS`, and every request is counted so a run can prove `polymath_chat_calls == 0`. — adapters/ecommerce/python/corpus_polymath.py:12-18 [DERIVED]
A dead or empty backend yields the docs/18 §6 capability_failure payload — the run continues with an honest deficit, never a faked corpus. — adapters/ecommerce/python/corpus_polymath.py:8-10 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| set_run_tag | def | (run_id, node) -> None | adapters/ecommerce/python/corpus_polymath.py:61-64 | — |
| call_ledger | def | () -> dict | adapters/ecommerce/python/corpus_polymath.py:98-105 | — |
| retrieve | def | (url, corpus, query, limit=12, bearer=None, timeout=120.0, explore=True, document_ids=None) -> dict | adapters/ecommerce/python/corpus_polymath.py:108-119 | — |
| probe_capabilities | def | (url, bearer=None, timeout=15.0) -> dict \| None | adapters/ecommerce/python/corpus_polymath.py:122-131 | — |
| backend_record | def | (caps, url) -> dict | adapters/ecommerce/python/corpus_polymath.py:134-140 | — |
| retrieve_plan | def | (url, corpus, signal, communities, limit, bearer, timeout, explore=True, document_ids=None) -> dict | adapters/ecommerce/python/corpus_polymath.py:143-150 | — |
| list_corpora | def | (url, bearer=None, timeout=30.0) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:153-158 | — |
| resolve_corpora | def | (url, wanted, bearer=None) -> tuple[list[str], dict] | adapters/ecommerce/python/corpus_polymath.py:161-173 | — |
| explore_corpus | def | (url, corpus, need, bearer, timeout, mode="WILDCARD", corpus_explorer=True) -> dict | adapters/ecommerce/python/corpus_polymath.py:176-183 | — |
| packet_errors | def | (resp) -> list[str] | adapters/ecommerce/python/corpus_polymath.py:186-205 | — |
| rows_from_packet | def | (packet, corpus, need_id=None, need=None) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:208-246 | — |
| packet_record | def | (packet, need, corpus, row_ids, rows, wall_ms=None) -> dict | adapters/ecommerce/python/corpus_polymath.py:249-273 | — |
| stable_id_local | def | (*parts) -> str | adapters/ecommerce/python/corpus_polymath.py:295-296 | — |
| rows_from_evidence_rows | def | (resp, corpus) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:305-345 | — |
| document_titles | def | (url, corpus, bearer=None, timeout=30.0) -> dict | adapters/ecommerce/python/corpus_polymath.py:348-364 | — |
| rows_from_response | def | (resp, corpus, titles=None, include_facts=False) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:406-455 | — |
| collect | def | (url, corpus, queries, limit, bearer, include_facts, timeout, explore=True, seen=None, document_ids=None, merge_into=None) -> tuple[list[dict], list[str]] | adapters/ecommerce/python/corpus_polymath.py:458-500 | — |
| presence_audit | def | (url, corpora, concepts, state, bearer, timeout, limit=40) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:503-537 | — |
| main | def | () -> int | adapters/ecommerce/python/corpus_polymath.py:540-788 | — |

Local imports: `models` (packet validation) adapters/ecommerce/python/corpus_polymath.py:204, `provenance` (normalize_phrase, corpus_presence, PRESENCE_METHOD) adapters/ecommerce/python/corpus_polymath.py:509-530 [DERIVED].

## contracts

**retrieve** — adapters/ecommerce/python/corpus_polymath.py:108-119
- in: POST `/retrieve` body `{"query", "corpus_id", "limit", "evidence": True}`; optional `"document_ids"` (DOCUMENT-SCOPED-RETRIEVE-V1) and `"mode": "EXPLORE"` — adapters/ecommerce/python/corpus_polymath.py:114-118 [DERIVED]
- pre: `"/retrieve"` must be in `ALLOWED_POST_PATHS`, checked BEFORE any I/O, else `ValueError` — adapters/ecommerce/python/corpus_polymath.py:82-83 [DERIVED]
- post: `CALLS["POST /retrieve"]` incremented and one TIMINGS row appended — adapters/ecommerce/python/corpus_polymath.py:72,78 [DERIVED]

**explore_corpus** — adapters/ecommerce/python/corpus_polymath.py:176-183
- in: body exactly `{"message", "corpus_id", "mode", "corpus_explorer"}` — the ORIGINAL need, four fields — adapters/ecommerce/python/corpus_polymath.py:182 [DERIVED]
- out: POST to `EVIDENCE_PATH` = `"/chat/evidence"`; counted under `polymath_evidence_calls` — adapters/ecommerce/python/corpus_polymath.py:44,104,183 [DERIVED]

**packet_errors** — adapters/ecommerce/python/corpus_polymath.py:186-205
- out: list of contract violations; empty = lawful — adapters/ecommerce/python/corpus_polymath.py:187-190 [DERIVED]
- post: on `schema_version` or `synthesis_performed` mismatch returns immediately (fail closed, no repair, caller records capability_failure); otherwise delegates to `models.validate(packet, "evidence_packet")[:8]` — adapters/ecommerce/python/corpus_polymath.py:187-198 [DERIVED]

**rows_from_packet** — adapters/ecommerce/python/corpus_polymath.py:208-246
- out: docs/18 rows with `id = f"polymath:chunk:{cid}"`, `summary[:1200]`, `lineage[:8]`, `packet_query_ids[:8]`, `can_establish`/`cannot_establish` stamped — adapters/ecommerce/python/corpus_polymath.py:226-236 [DERIVED]

**collect** — adapters/ecommerce/python/corpus_polymath.py:458-500
- in: `queries` items are strings or `{id, query, kind}` dicts; shared `seen` set dedupes ids ACROSS queries and corpora — adapters/ecommerce/python/corpus_polymath.py:460-463 [DERIVED]
- out: `(rows, errors)`; each row records the `query_ids` that produced it — adapters/ecommerce/python/corpus_polymath.py:487-499 [DERIVED]
- post: a row whose id already exists in `merge_into` is merged via `_merge_row` (retrieve lane enriches the evidence-lane row) — adapters/ecommerce/python/corpus_polymath.py:491-492,276-292 [DERIVED]

**resolve_corpora** — adapters/ecommerce/python/corpus_polymath.py:161-173
- out: `(ids, names)`; case-insensitive display-name match first, then id; unknown entries pass through unchanged — adapters/ecommerce/python/corpus_polymath.py:162-165,169-172 [DERIVED]

**presence_audit** — adapters/ecommerce/python/corpus_polymath.py:503-537
- in: only existing backend calls: GET `/documents` and POST `/retrieve` with `explore=False` for the concept's normalized phrase; never the opportunity retrieval path — adapters/ecommerce/python/corpus_polymath.py:503-508,513,525 [DERIVED]
- out: one CorpusPresenceReceipt per concept with `backend_rows`, optional `errors`/`documents_note` — adapters/ecommerce/python/corpus_polymath.py:529-536 [DERIVED]

**call_ledger** — adapters/ecommerce/python/corpus_polymath.py:98-105
- out: `{"calls", "polymath_chat_calls", "polymath_evidence_calls", "timings_ms"}`; chat-call count is measured from the same ledger every request passes through, not asserted — adapters/ecommerce/python/corpus_polymath.py:98-105 [DERIVED]

## effect surface
- Network POST, only: `/chat/evidence`, `/retrieve`, `/retrieve/plan` (`ALLOWED_POST_PATHS`) — adapters/ecommerce/python/corpus_polymath.py:44,49 [DERIVED]
- Network GET: `/capabilities` adapters/ecommerce/python/corpus_polymath.py:128; `/corpora?all=true` adapters/ecommerce/python/corpus_polymath.py:156; `/corpora/{corpus}/documents` and `/documents?corpus_id={corpus}` adapters/ecommerce/python/corpus_polymath.py:351,513 [DERIVED]
- Env: `POLYMATH_URL` = `"http://127.0.0.1:7200"` default adapters/ecommerce/python/corpus_polymath.py:41; `POLYMATH_API_KEY` (bearer, default None) adapters/ecommerce/python/corpus_polymath.py:559 [DERIVED]
- Files: reads `--state` JSON adapters/ecommerce/python/corpus_polymath.py:563-564; writes `--out` JSON or stdout adapters/ecommerce/python/corpus_polymath.py:587-588 [DERIVED]
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty). Ledger keys `polymath_chat_calls` / `polymath_evidence_calls` are emitted into payloads at adapters/ecommerce/python/corpus_polymath.py:103-104 and again at adapters/ecommerce/python/corpus_polymath.py:769 [DERIVED]

## invariants
INVARIANT: ALLOWED_POST_PATHS == frozenset({"/chat/evidence", "/retrieve", "/retrieve/plan"}) — adapters/ecommerce/python/corpus_polymath.py:49 [DERIVED]
  fails-if: `_post` raises `ValueError` naming the disallowed path before any I/O — adapters/ecommerce/python/corpus_polymath.py:82-83
INVARIANT: polymath_chat_calls == 0 for every lawful invocation — adapters/ecommerce/python/corpus_polymath.py:18,103 [DERIVED]
  fails-if: a synthesis route was reached, i.e. the evidence boundary was broken
INVARIANT: packet.synthesis_performed is False at both packet and response level, and schema_version == "evidence-packet-v1" — adapters/ecommerce/python/corpus_polymath.py:196-201 [DERIVED]
  fails-if: `packet_errors` returns violations and the caller records capability_failure instead of consuming the packet
INVARIANT: DEFAULT_MAX_EVIDENCE_CALLS (12) == policies.lived_world.max_questions — adapters/ecommerce/python/corpus_polymath.py:51 [DERIVED]
  fails-if: evidence-call cap drifts from the policy's question budget
INVARIANT: every emitted row id starts with "polymath:" and summary length <= 1200 chars — adapters/ecommerce/python/corpus_polymath.py:226,317-318,415,429 [DERIVED]
  fails-if: cross-lane dedup by id (collect/_merge_row) misses, or rows exceed the contract summary budget
INVARIANT: same chunk reached by two lanes is ONE row (shared id space) — adapters/ecommerce/python/corpus_polymath.py:212-213,276-279,491-492 [DERIVED]
  fails-if: duplicate evidence rows inflate the corpus view
INVARIANT: set_run_tag User-Agent is truncated to 118 chars — adapters/ecommerce/python/corpus_polymath.py:64 [DERIVED]
  fails-if: backend receipt-ledger attribution loses the run/node tag
INVARIANT: presence_audit floor timeouts/limits at max(timeout, 300.0) and max(limit, 40) — adapters/ecommerce/python/corpus_polymath.py:513,585 [DERIVED]
  fails-if: presence receipts computed from a truncated document scan

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.perf_counter` adapters/ecommerce/python/corpus_polymath.py:73,78,667,685; network `urllib.request.urlopen` :75 and `urllib.request.Request` :84,92; env `POLYMATH_URL` :41, `POLYMATH_API_KEY` :559) [DERIVED]
idempotency: SAFE — the adapter only issues retrieval/capability routes through `_post`/`_get`; its sole persistent write is the local `--out` file (overwrites) at adapters/ecommerce/python/corpus_polymath.py:49,587-588 [INFERRED: no mutating route is reachable, but backend-side effects of POST are not observable here]

## failure behaviour
- `probe_capabilities`: any Exception -> `return None` (SWALLOWED; endpoint absence is information, lane falls to generic mode) — adapters/ecommerce/python/corpus_polymath.py:130-131 [DERIVED]
- `list_corpora`: any Exception -> `return []` (SWALLOWED; resolve_corpora then passes ids through unchanged) — adapters/ecommerce/python/corpus_polymath.py:157-158,171 [DERIVED]
- `document_titles`: per-path Exception -> `continue`; both paths failing -> `{}` and rows fall back to the doc id — adapters/ecommerce/python/corpus_polymath.py:353-357,364 [DERIVED]
- `collect`: `urllib.error.HTTPError` -> error string with `exc.code` plus a 160-byte body excerpt; other Exception -> `"{type}: {exc}"`; the query is skipped, the loop continues — adapters/ecommerce/python/corpus_polymath.py:474-479 [DERIVED]
- `presence_audit`: `/documents` Exception -> `doc_notes`; retrieve Exception -> `errors` list, both surfaced on the receipt — adapters/ecommerce/python/corpus_polymath.py:514-516,526-528 [DERIVED]
- `main`: handled Exception blocks at adapters/ecommerce/python/corpus_polymath.py:670 (continue), :710 (continue), :756 (assign) — bodies lie beyond the shown source; FACTS.fallbacks only [DERIVED]
- `_post` raises `ValueError` for a path outside `ALLOWED_POST_PATHS` before any I/O — adapters/ecommerce/python/corpus_polymath.py:82-83 [DERIVED]
- Dead/empty backend -> docs/18 §6 capability_failure payload, never a faked corpus — adapters/ecommerce/python/corpus_polymath.py:8-10 [DERIVED]

## dumb-code flags
- `"polymath:"` id prefix built independently in 5 places: `f"polymath:chunk:{cid}"` :226,:429; `f"polymath:{kind}:{rid...}"` :317; `f"polymath:doc:{doc}"` :415; `f"polymath:fact:{fid}"` :437 — adapters/ecommerce/python/corpus_polymath.py:226,317,415,429,437 [DERIVED]
- Magic summary cap `[:1200]` duplicated 4x — adapters/ecommerce/python/corpus_polymath.py:226,318,415,429 [DERIVED]
- Magic cap `[:8]` appears 3x with three different meanings (validate errors, lineage, packet_query_ids) — adapters/ecommerce/python/corpus_polymath.py:198,231,232 [DERIVED]; evidence cap `[:5]` — adapters/ecommerce/python/corpus_polymath.py:341 [DERIVED]
- Default URL literal duplicated: `"http://127.0.0.1:7200"` in `DEFAULT_URL` and `"127.0.0.1:7200"` again in the `--url` help text — adapters/ecommerce/python/corpus_polymath.py:41,542 [DERIVED]
- Mixed container styles: `UTILITY_ROLES`/`CA4_GRADES` tuples :52-53 vs `CAN_ESTABLISH`/`CANNOT_ESTABLISH` lists :301-302, reconciled only by `list()` at :236 — adapters/ecommerce/python/corpus_polymath.py:52-53,236,301-302 [DERIVED]
- `_HINT_STOP` word set declared with no visible use in lines 1-599 — adapters/ecommerce/python/corpus_polymath.py:299-300 [DERIVED]; possible use inside main (:540-788) is not shown, so not claimed dead
- `--limit` default 12 in argparse matches `retrieve`'s `limit=12` default only by copy — adapters/ecommerce/python/corpus_polymath.py:108,551 [DERIVED]

## refactor notes
- `ALLOWED_POST_PATHS` is pinned by tests/run_all.py §17 per the comment — changing the allowed set or `EVIDENCE_PATH` updates that test — adapters/ecommerce/python/corpus_polymath.py:47-49 [DERIVED]
- Packet contract: `PACKET_SCHEMA_VERSION = "evidence-packet-v1"` validated against `schemas/evidence_packet.json` via `models.validate` — a version bump fail-closes every native-lane consumer into capability_failure — adapters/ecommerce/python/corpus_polymath.py:45,187-198,204 [DERIVED]
- Row id scheme `polymath:chunk:<chunk_id>` is the cross-lane dedup key; `collect`, `_merge_row`, and `merge_into` all key on it — an id-format change silently breaks dedup — adapters/ecommerce/python/corpus_polymath.py:212-213,276-292,487-492 [DERIVED]
- Presence payload key `"corpus_presence"` is consumed by tests/calibration_acceptance.py `--presence` — adapters/ecommerce/python/corpus_polymath.py:554 [DERIVED]
- Ledger keys `polymath_chat_calls`/`polymath_evidence_calls` are emitted at :103-104 and reassembled at :769 (FACTS) — renaming breaks run receipts — adapters/ecommerce/python/corpus_polymath.py:103-104,769 [DERIVED]
- User-Agent format from `set_run_tag` is recorded by the backend's query-receipt ledger — adapters/ecommerce/python/corpus_polymath.py:62-64 [DERIVED]

## VERIFY
```verify
grep -Fq 'ADAPTER_VERSION = "2.2.0"' adapters/ecommerce/python/corpus_polymath.py
grep -Fq 'ALLOWED_POST_PATHS = frozenset({EVIDENCE_PATH, "/retrieve", "/retrieve/plan"})' adapters/ecommerce/python/corpus_polymath.py
grep -Fq 'PACKET_SCHEMA_VERSION = "evidence-packet-v1"' adapters/ecommerce/python/corpus_polymath.py
grep -Fq 'DEFAULT_MAX_EVIDENCE_CALLS = 12' adapters/ecommerce/python/corpus_polymath.py
test "$(grep -c -F 'polymath:chunk:' adapters/ecommerce/python/corpus_polymath.py)" -ge 2
test "$(grep -c -F '[:1200]' adapters/ecommerce/python/corpus_polymath.py)" -ge 4
! grep -Fq 'corpus_plmath' adapters/ecommerce/python/corpus_polymath.py
```
