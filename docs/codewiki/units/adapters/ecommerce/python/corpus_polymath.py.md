# unit: adapters/ecommerce/python/corpus_polymath.py
anchor: adapters/ecommerce/python/corpus_polymath.py:1-794

## purpose
Reference corpus adapter (docs/18) that the AGENT — not the controller — runs at `corpus_retrieve` nodes: it queries the Polymath orchestrator, keeps only contract rows `{id, summary, source}`, dedupes by id across lanes, and prints the payload `controller.py submit --node corpus` accepts — adapters/ecommerce/python/corpus_polymath.py:2-10 [DERIVED].
v2.2.0 evidence boundary (docs/22): asks Polymath for EVIDENCE, never an answer; no synthesis route is reachable, and every request is counted so a run can prove `polymath_chat_calls == 0` — adapters/ecommerce/python/corpus_polymath.py:12-18 [DERIVED].
A dead/empty backend yields the docs/18 §6 capability_failure payload; the run continues with an honest deficit — adapters/ecommerce/python/corpus_polymath.py:9-10 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| set_run_tag | def | (run_id, node) -> None | adapters/ecommerce/python/corpus_polymath.py:61-64 | — |
| call_ledger | def | () -> dict | adapters/ecommerce/python/corpus_polymath.py:98-105 | — |
| retrieve | def | (url, corpus, query, limit=12, bearer, timeout=120.0, explore=True, document_ids) -> dict | adapters/ecommerce/python/corpus_polymath.py:108-119 | — |
| probe_capabilities | def | (url, bearer=None, timeout=15.0) -> dict \| None | adapters/ecommerce/python/corpus_polymath.py:122-131 | — |
| backend_record | def | (caps, url) -> dict | adapters/ecommerce/python/corpus_polymath.py:134-140 | — |
| retrieve_plan | def | (url, corpus, signal, communities, limit, bearer, timeout, explore=True, document_ids) -> dict | adapters/ecommerce/python/corpus_polymath.py:143-150 | — |
| list_corpora | def | (url, bearer=None, timeout=30.0) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:153-158 | — |
| resolve_corpora | def | (url, wanted, bearer=None) -> tuple[list[str], dict] | adapters/ecommerce/python/corpus_polymath.py:161-173 | — |
| explore_corpus | def | (url, corpus, need, bearer, timeout, mode="WILDCARD", corpus_explorer=True) -> dict | adapters/ecommerce/python/corpus_polymath.py:176-184 | — |
| packet_errors | def | (resp) -> list[str] | adapters/ecommerce/python/corpus_polymath.py:187-206 | — |
| rows_from_packet | def | (packet, corpus, need_id=None, need=None) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:209-247 | — |
| packet_record | def | (packet, need, corpus, row_ids, rows, wall_ms=None) -> dict | adapters/ecommerce/python/corpus_polymath.py:250-274 | — |
| rows_from_evidence_rows | def | (resp, corpus) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:306-346 | — |
| document_titles | def | (url, corpus, bearer=None, timeout=30.0) -> dict | adapters/ecommerce/python/corpus_polymath.py:349-365 | — |
| rows_from_response | def | (resp, corpus, titles=None, include_facts=False) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:407-456 | — |
| collect | def | (url, corpus, queries, limit, bearer, include_facts, timeout, explore=True, seen, document_ids, merge_into) -> tuple[list[dict], list[str]] | adapters/ecommerce/python/corpus_polymath.py:459-501 | — |
| presence_audit | def | (url, corpora, concepts, state, bearer, timeout, limit=40) -> list[dict] | adapters/ecommerce/python/corpus_polymath.py:504-538 | — |
| stable_id_local | def | (*parts) -> str | adapters/ecommerce/python/corpus_polymath.py:296-297 | — |
| main | def | () -> int | adapters/ecommerce/python/corpus_polymath.py:541-789 | — |

No `importers` recorded in FACTS; lazy sibling imports: `import models as _models` (:205), `import provenance as _prov` (:510).

## contracts

**explore_corpus** — adapters/ecommerce/python/corpus_polymath.py:176-184
- in: POST `/chat/evidence` with body `{"message": need, "corpus_id": corpus, "mode": mode, "corpus_explorer": bool(corpus_explorer)}` (:183)
- pre: submit the ORIGINAL need — Polymath owns retrieval planning, θ owns reasoning (:180-181)
- out: raw response; caller must pass it through `packet_errors` before consuming

**packet_errors** — adapters/ecommerce/python/corpus_polymath.py:187-206
- in: response from the evidence route
- out: `[]` = lawful; any violation → non-empty list; packet is never repaired, partially consumed, or replaced by another lane (:188-190)
- checks: `schema_version == "evidence-packet-v1"` (:197), `packet.synthesis_performed is False` (:199), response-level `synthesis_performed` false if present (:201), then `models.validate(packet, "evidence_packet")[:8]` (:205-206)

**retrieve** — adapters/ecommerce/python/corpus_polymath.py:108-119
- in: POST `/retrieve` body `{"query", "corpus_id", "limit", "evidence": True}` + optional `document_ids` (DOCUMENT-SCOPED-RETRIEVE-V1, :116) and `mode: "EXPLORE"` (:118)

**rows_from_packet** — adapters/ecommerce/python/corpus_polymath.py:209-247
- in: EvidencePacket dict
- pre: rows without `chunk_id` or blank text are skipped (:217-220)
- out: id `f"polymath:chunk:{cid}"`, `summary[:1200]`, verbatim `text`, `utility_role`, `ca4_grade`, `c4_valid`, `origin`, `lineage[:8]`, `provenance`, `packet_query_ids[:8]`, `text_truncated`/`text_chars`, `can_establish`/`cannot_establish` (:220-237)

**collect** — adapters/ecommerce/python/corpus_polymath.py:459-501
- in: queries as strings or `{id, query, kind}` dicts; shared `seen` set dedupes ids across queries and corpora (:462-464)
- out: `(rows, errors)`; default qid = `"q_" + sha1(qtext)[:10]` (:472); HTTPError → error string with code + 160-byte body (:476)
- post: same-id rows from a second lane merge via `_merge_row` into `merge_into` (:492-493)

**call_ledger** — adapters/ecommerce/python/corpus_polymath.py:98-105
- out: `{"calls", "polymath_chat_calls", "polymath_evidence_calls", "timings_ms"}`; `polymath_chat_calls` = POSTs whose path is NOT in `ALLOWED_POST_PATHS` (:101-103) — measured from the same ledger every request passes through, not asserted (:99-100)

**presence_audit** — adapters/ecommerce/python/corpus_polymath.py:504-538
- in: state containing `product_concepts`; existing endpoints only — GET `/documents` (timeout floor `max(timeout, 300.0)`, :514) and POST `/retrieve` with `explore=False` for each concept's normalized phrase (:526); never the opportunity retrieval path (:508-509)
- out: CorpusPresenceReceipt via `_prov.corpus_presence(..., method_version=f"{_prov.PRESENCE_METHOD}:retrieve-lexical")` plus `backend_rows` (:530-532)

## effect surface
- Network POST: `/chat/evidence`, `/retrieve`, `/retrieve/plan` — the only paths `_post` allows — adapters/ecommerce/python/corpus_polymath.py:49, :82-88
- Network GET: `/capabilities` (:128), `/corpora?all=true` (:156), `/corpora/{corpus}/documents` and `/documents?corpus_id={corpus}` (:352, :514)
- Env: `POLYMATH_URL` default `"http://127.0.0.1:7200"` (:41); `POLYMATH_API_KEY` default None → Bearer header (:560, :86-87)
- Files: reads `--state` run JSON (:564-565); writes `--out` JSON payload, truncating (`"w"`) (:589)
- In-process mutable state: `CALLS` Counter and `TIMINGS` list grow per request (:56-57, :72, :78)
- Postgres/Qdrant: none — `tables_read`/`tables_written` empty in FACTS

## invariants
INVARIANT: POST paths ⊆ {`/chat/evidence`, `/retrieve`, `/retrieve/plan`} — checked before any I/O — adapters/ecommerce/python/corpus_polymath.py:49, :82-83 [DERIVED]
  fails-if: `ValueError` raised pre-request; evidence boundary unprovable.
INVARIANT: `polymath_chat_calls == 0` for any completed invocation, because `_post` raises before the request is counted — adapters/ecommerce/python/corpus_polymath.py:82-83, :103 [DERIVED]
  fails-if: a synthesis route was reached; the run can no longer prove θ-only reasoning.
INVARIANT: emitted row `summary` length ≤ 1200 chars — adapters/ecommerce/python/corpus_polymath.py:220, :319, :423, :437 [DERIVED]
  fails-if: contract rows exceed the submit payload's consumer assumptions.
INVARIANT: a packet is consumed only when `packet_errors` returns `[]` (schema `evidence-packet-v1`, `synthesis_performed` false at both levels) — adapters/ecommerce/python/corpus_polymath.py:197-206 [DERIVED]
  fails-if: partial repair or lane substitution would break fail-closed handling.
INVARIANT: same chunk id ⇒ one row; merge unions `query_ids`/`tags`, longer `source`/`text`/`summary` wins — adapters/ecommerce/python/corpus_polymath.py:277-293 [DERIVED]
  fails-if: duplicate rows across lanes; text provenance regresses to the shorter excerpt.
INVARIANT: `graph_fact`/`graph_hop` rows without `evidence` are dropped — adapters/ecommerce/python/corpus_polymath.py:316-317 [DERIVED]
  fails-if: unattested graph facts enter corpus rows as notes-as-facts.
INVARIANT: packet-lane and retrieve-lane chunk rows share the id space `polymath:chunk:{chunk_id}` — adapters/ecommerce/python/corpus_polymath.py:213-214, :220, :437 [DERIVED]
  fails-if: cross-lane dedupe silently stops matching.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.perf_counter` :73, :78, :668, :686; network `urllib.request.urlopen`/`Request` :75, :84, :92; env `POLYMATH_URL` :41, `POLYMATH_API_KEY` :560)
idempotency: SAFE — all POSTs are retrieval queries, no backend writes; local side effects are the `--out` file truncate (:589) and monotonic in-process `CALLS`/`TIMINGS` counters (:56-57), so repeated calls in one process accumulate counts.

## failure behaviour
- `probe_capabilities`: any Exception swallowed → `None` → caller falls to generic mode — adapters/ecommerce/python/corpus_polymath.py:130, :134-136 [DERIVED]
- `list_corpora`: any Exception swallowed → `[]` → `resolve_corpora` passes unknown names through unchanged — adapters/ecommerce/python/corpus_polymath.py:157, :171 [DERIVED]
- `document_titles`: per-path Exception swallowed → tries the alternate path, may return `{}` — adapters/ecommerce/python/corpus_polymath.py:355, :349-351 [DERIVED]
- `collect`: `HTTPError` → error string with code + body snippet; other Exceptions → recorded deficit, never hidden — adapters/ecommerce/python/corpus_polymath.py:476-480 [DERIVED]
- `presence_audit`: document-fetch and retrieve errors recorded into the receipt (`errors`, `documents_note`) — adapters/ecommerce/python/corpus_polymath.py:516-517, :528-529 [DERIVED]
- `main`: handled Exception → continue at :671 and :711, assign at :757 (source beyond provided excerpt; per FACTS.fallbacks) — adapters/ecommerce/python/corpus_polymath.py:671, :711, :757 [DERIVED]
- `_post` raises `ValueError` for a path outside `ALLOWED_POST_PATHS` — adapters/ecommerce/python/corpus_polymath.py:83 [DERIVED]

## dumb-code flags
- Docstring/code drift: `explore_corpus` docstring says "The body is exactly these five fields" including `product: false`, but the body at :183 has four keys and no `product` — adapters/ecommerce/python/corpus_polymath.py:181-183 [DERIVED]
- Degenerate ternary: `(key if key in ids or not rows else key)` always evaluates to `key`; whole expression reduces to `by_name.get(key.lower(), key)` — adapters/ecommerce/python/corpus_polymath.py:171 [DERIVED]
- Magic cap `1200` repeated as a bare literal on summaries — adapters/ecommerce/python/corpus_polymath.py:220, :319, :423, :437 [DERIVED]
- Slice caps: `[:8]` on lineage, `packet_query_ids`, and validate errors; `evidence[:5]`; User-Agent cut at `[:118]` — adapters/ecommerce/python/corpus_polymath.py:232-233, :206, :342, :64 [DERIVED]
- `_HINT_STOP` (:300-301), `MAX_NEED_CHARS` (:50), `UTILITY_ROLES`/`CA4_GRADES` (:52-53) have no use in the visible range :1-597; `main` continues to :789, so use is plausible there but unconfirmed — adapters/ecommerce/python/corpus_polymath.py:300-303 [INFERRED]
- Timeout defaults disagree by call: 120.0 (`retrieve`, `--timeout`), 30.0 (`list_corpora`, `document_titles`), 15.0 (`probe_capabilities`); `presence_audit` floors `/documents` at 300.0 but passes plain timeout to `/retrieve` — adapters/ecommerce/python/corpus_polymath.py:108, :557, :153, :349, :122, :514, :526 [DERIVED]
- `DEFAULT_MAX_EVIDENCE_CALLS = 12` is commented as mirroring external `policies lived_world.max_questions` — cross-repo coupling — adapters/ecommerce/python/corpus_polymath.py:51 [DERIVED]
- `main` recomputes presence limit as `max(int(args.limit or 12), 40)` against the function default 40 — adapters/ecommerce/python/corpus_polymath.py:504, :552, :586 [DERIVED]

## refactor notes
- `ALLOWED_POST_PATHS` is the evidence-boundary enforcement, pinned by `tests/run_all.py §17` per the comment; changing it changes the provable `polymath_chat_calls == 0` claim — adapters/ecommerce/python/corpus_polymath.py:47-49 [DERIVED]
- `CALLS` keys use the format `"METHOD /path"` and `call_ledger` parses with `k.split(" ", 1)[1]`; changing the key format breaks the ledger — adapters/ecommerce/python/corpus_polymath.py:72, :101-103 [DERIVED]
- Row id namespaces `polymath:doc:` / `polymath:chunk:` / `polymath:fact:` / `polymath:{kind}:` are the cross-lane dedupe keys and the `controller.py submit --node corpus` payload contract — adapters/ecommerce/python/corpus_polymath.py:8, :220, :423, :437, :439, :311 [DERIVED]
- Lazy runtime imports `models` and `provenance` (incl. `_prov.PRESENCE_METHOD`) — renames fail only at call time — adapters/ecommerce/python/corpus_polymath.py:205, :510, :531 [DERIVED]
- CLI is a test surface: `--presence` writes `corpus_presence` consumed by `tests/calibration_acceptance.py --presence`; `--document-id` implements docs/26 §8 scoping where the evidence route is skipped under an active scope — adapters/ecommerce/python/corpus_polymath.py:553, :555 [DERIVED]
- `main`'s summary output references `polymath_chat_calls`/`polymath_evidence_calls` at :770 (beyond provided excerpt, per FACTS) — adapters/ecommerce/python/corpus_polymath.py:770 [INFERRED — FACTS list these names at that line; exact statement not visible]

## VERIFY
```verify
grep -Fq 'ALLOWED_POST_PATHS = frozenset({EVIDENCE_PATH, "/retrieve", "/retrieve/plan"})' adapters/ecommerce/python/corpus_polymath.py
grep -Fq 'DEFAULT_URL = os.environ.get("POLYMATH_URL", "http://127.0.0.1:7200")' adapters/ecommerce/python/corpus_polymath.py
grep -Fq 'PACKET_SCHEMA_VERSION = "evidence-packet-v1"' adapters/ecommerce/python/corpus_polymath.py
grep -Eq 'key if key in ids or not rows else key' adapters/ecommerce/python/corpus_polymath.py
! grep -Fq '"product":' adapters/ecommerce/python/corpus_polymath.py
test "$(grep -c -F 'polymath:chunk:' adapters/ecommerce/python/corpus_polymath.py)" -ge 2
test "$(grep -c -F 'synthesis_performed' adapters/ecommerce/python/corpus_polymath.py)" -ge 4
```
