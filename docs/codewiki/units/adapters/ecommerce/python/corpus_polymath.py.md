# unit: adapters/ecommerce/python/corpus_polymath.py
anchor: adapters/ecommerce/python/corpus_polymath.py:1-794

## purpose
Reference corpus adapter (docs/18, v2.2.0) that the AGENT runs at `corpus_retrieve` nodes when the corpus is Polymath: it queries the orchestrator, keeps only contract rows (`{id, summary, source}`), dedupes by id across lanes, and prints the payload `controller.py submit --node corpus` accepts. A dead/empty backend yields the docs/18 §6 `capability_failure` payload — the run continues with an honest deficit (adapters/ecommerce/python/corpus_polymath.py:2-10) [DERIVED].
Evidence boundary (docs/22, v2.2.0): asks Polymath for EVIDENCE, never an answer — no synthesis route is reachable, and every request is counted so a run can prove `polymath_chat_calls == 0` (adapters/ecommerce/python/corpus_polymath.py:12-18, 47-49) [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| main | def | () -> int | adapters/ecommerce/python/corpus_polymath.py:541-789 | CLI (`python3 python/corpus_polymath.py`) |
| set_run_tag | def | (run_id, node) -> None | adapters/ecommerce/python/corpus_polymath.py:61-64 | — |
| call_ledger | def | () -> dict | adapters/ecommerce/python/corpus_polymath.py:98-105 | main (stderr summary) |
| retrieve | def | (url, corpus, query, limit=12, bearer=None, timeout=120.0, explore=True, document_ids=None) -> dict | adapters/ecommerce/python/corpus_polymath.py:108-119 | collect, presence_audit |
| retrieve_plan | def | (url, corpus, signal, communities, limit, bearer, timeout, explore=True, document_ids=None) -> dict | adapters/ecommerce/python/corpus_polymath.py:143-150 | main |
| explore_corpus | def | (url, corpus, need, bearer, timeout, mode="WILDCARD", corpus_explorer=True) -> dict | adapters/ecommerce/python/corpus_polymath.py:176-184 | main |
| probe_capabilities | def | (url, bearer=None, timeout=15.0) -> dict \| None | adapters/ecommerce/python/corpus_polymath.py:122-131 | main |
| backend_record | def | (caps, url) -> dict | adapters/ecommerce/python/corpus_polymath.py:134-140 | main |
| list_corpora | def | (url, bearer=None, timeout=30.0) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:153-158 | resolve_corpora |
| resolve_corpora | def | (url, wanted, bearer=None) -> tuple[list[str], dict] | adapters/ecommerce/python/corpus_polymath.py:161-173 | main |
| packet_errors | def | (resp) -> list[str] | adapters/ecommerce/python/corpus_polymath.py:187-206 | main |
| rows_from_packet | def | (packet, corpus, need_id=None, need=None) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:209-247 | main |
| packet_record | def | (packet, need, corpus, row_ids, rows, wall_ms=None) -> dict | adapters/ecommerce/python/corpus_polymath.py:250-274 | main |
| rows_from_evidence_rows | def | (resp, corpus) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:306-346 | collect, presence_audit |
| rows_from_response | def | (resp, corpus, titles=None, include_facts=False) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:407-456 | collect (older backend lane) |
| document_titles | def | (url, corpus, bearer=None, timeout=30.0) -> dict | adapters/ecommerce/python/corpus_polymath.py:349-365 | collect |
| collect | def | (url, corpus, queries, limit, bearer, include_facts, timeout, explore=True, seen=None, document_ids=None, merge_into=None) -> tuple[list[dict], list[str]] | adapters/ecommerce/python/corpus_polymath.py:459-501 | main |
| presence_audit | def | (url, corpora, concepts, state, bearer, timeout, limit=40) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:504-538 | main (`--presence`) |
| stable_id_local | def | (*parts) -> str | adapters/ecommerce/python/corpus_polymath.py:296-297 | packet_record |
| _merge_row | def | (existing, incoming) -> None | adapters/ecommerce/python/corpus_polymath.py:277-293 | collect |
| _post / _get / _open | def | HTTP wrappers -> dict | adapters/ecommerce/python/corpus_polymath.py:71-95 | all network callers |

## contracts
**retrieve** (adapters/ecommerce/python/corpus_polymath.py:108-119)
- in: POST `/retrieve` body `{"query", "corpus_id", "limit", "evidence": True}` + optional `document_ids` (DOCUMENT-SCOPED-RETRIEVE-V1) + `mode: "EXPLORE"` when `explore`.
- out: raw response dict; caller branches on `resp.get("evidence_rows") is not None` (adapters/ecommerce/python/corpus_polymath.py:481).
- pre: path `/retrieve` ∈ `ALLOWED_POST_PATHS`, else `ValueError` before any I/O (adapters/ecommerce/python/corpus_polymath.py:82-83).

**explore_corpus** (adapters/ecommerce/python/corpus_polymath.py:176-184)
- in: POST `/chat/evidence` with exactly five body fields: `message`, `corpus_id`, `mode`, `corpus_explorer`, `product: False`.
- post: response must satisfy `packet_errors` — `schema_version == "evidence-packet-v1"`, `packet.synthesis_performed is False`, `resp.synthesis_performed is False`, then `models.validate(packet, "evidence_packet")[:8]` (adapters/ecommerce/python/corpus_polymath.py:196-206). Empty error list = lawful; violations are never repaired or partially consumed — caller records `capability_failure` (adapters/ecommerce/python/corpus_polymath.py:188-190).

**rows_from_packet** (adapters/ecommerce/python/corpus_polymath.py:209-247)
- in: EvidencePacket dict, corpus id, optional need_id/need.
- out: rows id `polymath:chunk:{chunk_id}`, `summary[:1200]`, verbatim `text`, `utility_role`, `ca4_grade`, `c4_valid`, `origin`, `lineage[:8]`, `provenance`, `packet_query_ids[:8]`, `text_truncated`, `text_chars`, `can_establish`/`cannot_establish` stamps; `None` values dropped.
- pre: skips evidence with empty `chunk_id` or blank text (adapters/ecommerce/python/corpus_polymath.py:217-220).

**collect** (adapters/ecommerce/python/corpus_polymath.py:459-501)
- in: list of queries (strings or `{id, query, kind}` dicts); shared `seen` set; `merge_into` dict of existing rows.
- out: `(rows, errors)`; rows deduped by id across queries AND corpora; each row carries `query_ids` (retrieval provenance, docs/19); a row already held by the evidence lane is merged via `_merge_row` instead of duplicated (adapters/ecommerce/python/corpus_polymath.py:485-493).

**call_ledger** (adapters/ecommerce/python/corpus_polymath.py:98-105)
- out: `{"calls": {...}, "polymath_chat_calls": <POSTs to non-allowed paths>, "polymath_evidence_calls": <POSTs to /chat/evidence>, "timings_ms": {...}}` — measured from the same `CALLS` counter every request passes through, not asserted.

**resolve_corpora** (adapters/ecommerce/python/corpus_polymath.py:161-173)
- in: wanted names or ids; out `(ids, names)`. Case-insensitive display-name match first, then id; unknown entries pass through unchanged (adapters/ecommerce/python/corpus_polymath.py:163-164).

**presence_audit** (adapters/ecommerce/python/corpus_polymath.py:504-538)
- in: uses only existing backend calls — `GET /documents` (documents_checked) and `POST /retrieve` with the concept's `provenance.normalize_phrase(name)`; never the opportunity retrieval path (no evidence call, no plan, no new index) (adapters/ecommerce/python/corpus_polymath.py:505-509, 522, 526).
- out: CorpusPresenceReceipt per `ProductConcept` via `provenance.corpus_presence(..., method_version=f"{_prov.PRESENCE_METHOD}:retrieve-lexical")` (adapters/ecommerce/python/corpus_polymath.py:530-531).

## effect surface
- Network (all against `$POLYMATH_URL`, default `http://127.0.0.1:7200`, adapters/ecommerce/python/corpus_polymath.py:41): POST limited to `/chat/evidence`, `/retrieve`, `/retrieve/plan` (adapters/ecommerce/python/corpus_polymath.py:49); GET `/capabilities` (adapters/ecommerce/python/corpus_polymath.py:128), `/corpora?all=true` (adapters/ecommerce/python/corpus_polymath.py:156), `/corpora/{corpus}/documents` and `/documents?corpus_id={corpus}` (adapters/ecommerce/python/corpus_polymath.py:352), `/documents?corpus_id={corpus}` with timeout `max(timeout, 300.0)` (adapters/ecommerce/python/corpus_polymath.py:514).
- Env: `POLYMATH_URL` = `'http://127.0.0.1:7200'` (adapters/ecommerce/python/corpus_polymath.py:41); `POLYMATH_API_KEY` = None default, sent as `Authorization: Bearer` (adapters/ecommerce/python/corpus_polymath.py:560, 87, 94).
- Files: reads `--state` run JSON (adapters/ecommerce/python/corpus_polymath.py:564); writes `--out` payload else stdout; stderr summary (adapters/ecommerce/python/corpus_polymath.py:589-591).
- Process state: `CALLS` Counter, `TIMINGS` list, `_UA` dict mutated per request (adapters/ecommerce/python/corpus_polymath.py:56-58, 72, 78).
- Postgres tables: none; Qdrant collections: none (FACTS `tables_read`/`tables_written` empty).

## invariants
INVARIANT: `ALLOWED_POST_PATHS` == {`/chat/evidence`, `/retrieve`, `/retrieve/plan`} — adapters/ecommerce/python/corpus_polymath.py:49 [DERIVED]
  fails-if: adding a synthesis route lets θ nest a second synthesis; `polymath_chat_calls` becomes non-zero and the evidence boundary (pinned by tests/run_all.py §17) breaks.
INVARIANT: `polymath_chat_calls` == 0 in a lawful run, because it counts only POSTs outside `ALLOWED_POST_PATHS` and `_post` rejects those — adapters/ecommerce/python/corpus_polymath.py:82-83, 101-104 [DERIVED]
  fails-if: ledger can no longer prove the run made zero synthesis calls.
INVARIANT: packet `schema_version` == `"evidence-packet-v1"` and `synthesis_performed` is `False` at both packet and response level — adapters/ecommerce/python/corpus_polymath.py:197-202 [DERIVED]
  fails-if: packet_errors reports, caller must record capability_failure (fail closed), never consume partially.
INVARIANT: `DEFAULT_MAX_EVIDENCE_CALLS` (12) == policies `lived_world.max_questions` — adapters/ecommerce/python/corpus_polymath.py:51 [DERIVED]
  fails-if: question mode spends more evidence calls per run than policy allows.
INVARIANT: User-Agent tag length ≤ 118 chars (`[:118]`) — adapters/ecommerce/python/corpus_polymath.py:64 [DERIVED]
  fails-if: backend query-receipt ledger truncates or drops the run/node attribution.
INVARIANT: every row `summary` ≤ 1200 chars (`[:1200]`, 4 occurrences) — adapters/ecommerce/python/corpus_polymath.py:227, 319, 423, 437 [DERIVED]
  fails-if: oversized summaries leak into the submit payload consumed by controller.py.
INVARIANT: chunk ids share one namespace across lanes — `polymath:chunk:{cid}` in rows_from_packet (adapters/ecommerce/python/corpus_polymath.py:220), rows_from_response (adapters/ecommerce/python/corpus_polymath.py:437), `polymath:{kind}:{rid.split(":", 1)[-1]}` in rows_from_evidence_rows (adapters/ecommerce/python/corpus_polymath.py:311) [DERIVED]
  fails-if: the same chunk reached by two lanes becomes two rows; cross-lane dedupe (`seen`, `merge_into`) and `_merge_row` never fire.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.perf_counter` at adapters/ecommerce/python/corpus_polymath.py:73, 78, 668, 686; network `urllib.request.urlopen`/`Request` at adapters/ecommerce/python/corpus_polymath.py:75, 84, 92)
idempotency: SAFE (backend calls are retrieval routes, no writes; but `CALLS`/`TIMINGS`/`_UA` are per-invocation mutable module state, so `call_ledger()` output grows with each request — adapters/ecommerce/python/corpus_polymath.py:56-58, 72) [INFERRED: routes are named retrieve/evidence and carry no mutation semantics]

## failure behaviour
- `probe_capabilities`: any Exception swallowed → `return None` → `backend_record` emits mode `"generic"`, `plan_source: "local"` (adapters/ecommerce/python/corpus_polymath.py:130-131, 135-136).
- `list_corpora`: any Exception swallowed → `return []` → `resolve_corpora` passes unknown entries through unchanged (adapters/ecommerce/python/corpus_polymath.py:157-158, 164, 171).
- `document_titles`: per-path Exception → `continue`; both paths failing → `{}` and rows fall back to the doc id (adapters/ecommerce/python/corpus_polymath.py:355, 350-351).
- `collect`: `HTTPError` → error string `"HTTP {code} {body[:160]}"`; other Exception → `"{type}: {exc}"`; both `continue` — reported as a deficit, never hidden (adapters/ecommerce/python/corpus_polymath.py:476-480).
- `presence_audit`: `/documents` failure → `doc_notes`; per-corpus retrieve failure → `errors` on the receipt (adapters/ecommerce/python/corpus_polymath.py:516-517, 528-529).
- `_post` to a path outside `ALLOWED_POST_PATHS` raises `ValueError` before any I/O (adapters/ecommerce/python/corpus_polymath.py:82-83).
- `main` handles Exception with assign (adapters/ecommerce/python/corpus_polymath.py:757) and expr/continue (adapters/ecommerce/python/corpus_polymath.py:671, 711) per FACTS.fallbacks.

## dumb-code flags
- Magic number `1200` duplicated 4× as the summary cap (adapters/ecommerce/python/corpus_polymath.py:227, 319, 423, 437).
- Timeout defaults disagree per call site: `120.0` retrieve/--timeout (adapters/ecommerce/python/corpus_polymath.py:109, 557), `15.0` probe (adapters/ecommerce/python/corpus_polymath.py:123), `30.0` list_corpora/document_titles (adapters/ecommerce/python/corpus_polymath.py:154, 349), `max(timeout, 300.0)` presence (adapters/ecommerce/python/corpus_polymath.py:514).
- `UTILITY_ROLES` and `CA4_GRADES` overlap on `"DIRECT"`/`"RELATED"` but are distinct tuples (adapters/ecommerce/python/corpus_polymath.py:52-53).
- `_HINT_STOP` (adapters/ecommerce/python/corpus_polymath.py:300-301) and `MAX_NEED_CHARS = 2000` (adapters/ecommerce/python/corpus_polymath.py:50) have no use in the shown excerpt (file shown through ~line 597; `main` spans 541-789) — usage, if any, is in the unshown tail. [INFERRED]
- presence limit silently forced: `max(int(args.limit or 12), 40)` overrides the documented default 12 (adapters/ecommerce/python/corpus_polymath.py:552, 586).
- id-prefix construction differs by lane: f-string prefix in two mappers vs `rid.split(":", 1)[-1]` reparse in the third (adapters/ecommerce/python/corpus_polymath.py:220, 311, 437).

## refactor notes
- `ALLOWED_POST_PATHS` is the evidence boundary, pinned by tests/run_all.py §17 — adding/removing a path changes whether a run can prove `polymath_chat_calls == 0` (adapters/ecommerce/python/corpus_polymath.py:47-49).
- Row id namespaces (`polymath:doc:`, `polymath:chunk:`, `polymath:fact:`) are the dedupe keys across lanes and corpora in `collect`/`_merge_row`; changing the format breaks cross-lane merge and the submit payload contract (adapters/ecommerce/python/corpus_polymath.py:220, 311, 437, 446).
- `call_ledger` keys (`calls`, `polymath_chat_calls`, `polymath_evidence_calls`, `timings_ms`) are consumed downstream in main's stderr summary and ledger emit (adapters/ecommerce/python/corpus_polymath.py:98-105, 590, 770) — rename breaks run accounting.
- `packet_errors` delegates to `models.validate(packet, "evidence_packet")` — schema coupling to `schemas/evidence_packet.json`; the `[:8]` error cap is part of the contract (adapters/ecommerce/python/corpus_polymath.py:205-206).
- `presence_audit` depends on lazy imports `provenance.normalize_phrase`, `provenance.corpus_presence`, `provenance.PRESENCE_METHOD` (adapters/ecommerce/python/corpus_polymath.py:510, 522, 530-531).
- User-Agent format (`opportunity-research/{ADAPTER_VERSION} corpus_polymath run:{id} node:{node}`) is recorded by the backend's receipt ledger — backend-side parsing depends on it (adapters/ecommerce/python/corpus_polymath.py:58, 62-64, 566).
- `DEFAULT_MAX_EVIDENCE_CALLS` must track policies `lived_world.max_questions` — a change here without a policy change shifts the per-run evidence budget (adapters/ecommerce/python/corpus_polymath.py:51).
- `packet_record` has no `answer` field and no abstention flag by design — an empty packet means the corpus does not support the need (adapters/ecommerce/python/corpus_polymath.py:251-253).

## VERIFY
```verify
grep -Fq 'ALLOWED_POST_PATHS = frozenset({EVIDENCE_PATH, "/retrieve", "/retrieve/plan"})' adapters/ecommerce/python/corpus_polymath.py
grep -Fq 'ADAPTER_VERSION = "2.2.0"' adapters/ecommerce/python/corpus_polymath.py
grep -Fq 'PACKET_SCHEMA_VERSION = "evidence-packet-v1"' adapters/ecommerce/python/corpus_polymath.py
grep -Fq 'DEFAULT_MAX_EVIDENCE_CALLS = 12' adapters/ecommerce/python/corpus_polymath.py
grep -Fq 'http://127.0.0.1:7200' adapters/ecommerce/python/corpus_polymath.py
test "$(grep -c -F '[:1200]' adapters/ecommerce/python/corpus_polymath.py)" -ge 4
```
