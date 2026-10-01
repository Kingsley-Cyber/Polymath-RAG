# unit: orchestrator/orchestrator/api/ui.py
anchor: orchestrator/orchestrator/api/ui.py:1-4844

## purpose
UI support layer (POLYMATH-UI-V1): the thin HTTP endpoints the web chat frontend needs on top of the query product — corpus/document management, upload, model registry, and the single CHAT-RUNTIME-V1 chat turn (scope → compiler → retrieval → assemble → carry → synthesize → answer) exposed as SSE frames or one JSON body. [DERIVED] ui.py:1-32

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | var | `APIRouter()` — all routes below mount through it | ui.py:48 | host app (—) |
| `corpora` | def | `(all: bool = False) -> dict` | ui.py:142 | GET /corpora |
| `rename_corpus` | def | `(corpus_id: str, req: RenameCorpusRequest) -> dict` | ui.py:181 | PATCH /corpora/{corpus_id} |
| `set_query_enabled` | def | `(corpus_id: str, req: QueryEnableRequest) -> dict` | ui.py:213 | PATCH /corpora/{corpus_id}/query_enabled |
| `enrich_corpus` | def | `(corpus_id: str) -> dict` | ui.py:249 | POST /corpora/{corpus_id}/enrich |
| `enrich_document` | def | `(doc_id: str) -> dict` | ui.py:257 | POST /documents/{doc_id}/enrich |
| `document_sections` | def | `(doc_id: str) -> dict` | ui.py:272 | GET /documents/{doc_id}/sections |
| `documents` | def | `(corpus_id: str) -> dict` | ui.py:320 | GET /documents |
| `document_status_view` | def | `(doc_id) -> dict` | ui.py:397 | GET /documents/{doc_id}/status (ui.py:353) |
| `upload` | def | `(corpus_id, file, allow_near_duplicate) -> dict` | ui.py:467 | POST /upload (ui.py:6) |
| `documents_summary` | def | `(corpus_id) -> dict` | ui.py:453 | Files list |
| `control_plane` | def | `(corpus_id, request) -> dict` | ui.py:414 | drill-down |
| `delete_document` | def | `(doc_id, confirm) -> dict` | ui.py:622 | delete button |
| `delete_corpus` | def | `(corpus_id, confirm) -> dict` | ui.py:1068 | delete button |
| `save_generated` | def | `(req: GeneratedPage) -> dict` | ui.py:820 | GENERATED-LAUNCH-V1 |
| `reasoning_modes` | def | `() -> dict` | ui.py:843 | UI dropdown |
| `ui_pulse` | def | `() -> dict` | ui.py:865 | frontend ping |
| `synthesizers` | def | `() -> dict` | ui.py:882 | GET /synthesizers (ui.py:11) |
| `llm_providers` / `llm_provider_upsert` / `llm_provider_delete` / `llm_test` | def | provider CRUD + one-shot test | ui.py:915 / 930 / 956 / 968 | provider settings UI |
| `chat_events` | def | `(req, route, receipt) -> frames` | ui.py:3830 | internal single authority |
| `chat_stream` | def | `(req) -> StreamingResponse` | ui.py:4758 | POST /chat/stream (ui.py:15) |
| `run_chat` | def | `(req, route, receipt) -> dict` | ui.py:4785 | `/chat` and MCP `ask` (ui.py:26) |

Request models: `RenameCorpusRequest` ui.py:176, `QueryEnableRequest` ui.py:208, `GeneratedPage` ui.py:814, `ProviderUpsert` ui.py:906, `LlmTest` ui.py:963, `HistoryTurn`/`CarriedChunk`/`StreamChatRequest` ui.py:1271-1284, `_AttemptOutcome` ui.py:3467. [DERIVED]

## contracts

### `corpora` — ui.py:142-173
- in: query param `all: bool = False`
- out: `{"corpora": [{corpus_id, purpose, query_enabled, documents, query_ready, name}]}` ui.py:168-172
- pre: none
- post: a row is listed iff `(all or docs > 0 or purpose == 'production') and can_see(corpus_id)` ui.py:172; aggregates computed as two separate LEFT JOIN subqueries, never one joined query ui.py:144-159

### `rename_corpus` — ui.py:181-205
- in: path `corpus_id`, body `{name}`
- out: `{corpus_id, name}` of the updated row ui.py:205
- pre: name non-empty and ≤ 120 chars, else `422 invalid_name` ui.py:186-194
- post: only `corpus.name` and `updated_at` change; `corpus_id` untouched ui.py:197-199; unknown id → `404 QUERY_SCOPE_UNKNOWN` ui.py:202-204

### `set_query_enabled` — ui.py:213-229
- in: path `corpus_id`, body `{query_enabled: bool}`
- out: `{corpus_id, query_enabled}` ui.py:229
- pre: corpus exists, else 404 ui.py:226-228
- post: flips ONLY `query_enabled`; `purpose` untouched ui.py:214-218

### `_mint_enrichment` — ui.py:232-245
- in: `conn`, `corpus_id`, `doc_id | None`
- out: dict from shared `mint_parent_enrichment(conn, corpus_id=…, run_id=…, doc_id=…)` ui.py:244-245
- pre: corpus has ≥ 1 run (picks `ORDER BY (status='query_ready') DESC, created_at DESC LIMIT 1`), else `404 no_run_for_corpus` ui.py:236-243
- post: same mint path AUTO-ENRICH uses at promotion ui.py:233-234

### `document_sections` — ui.py:272-316
- in: path `doc_id`
- out: `{doc_id, sections: [{parent_id, title, heading_path, summary, keywords, coverage, children}]}` ui.py:307-316
- pre: `require_document(conn, doc_id)` passes ui.py:279
- post: only rows with `kind = 'section_retrieval_summary' AND active`, ordered `COALESCE(c.chunk_index, 0), rs.parent_id` ui.py:288-289; NULL heading falls back to summary head so the tree always renders ui.py:275-277

### `documents` — ui.py:320-393
- in: query param `corpus_id`
- out: per-doc counts (children/parents/enriched/enrich_failed/map_active) + last 25 runs with error ui.py:335-377
- pre: `require_corpus(corpus_id)` and corpus row exists, else 404 ui.py:321-327
- post: counts come from correlated `(doc_id)`-indexed subqueries, identical numbers to the old join form ui.py:328-335

### `_default_synthesizer` — ui.py:83-92
- in: none
- out: the first entry of `_PREFERRED_DEFAULTS` present in the offered list, else `offered[0]`, else the raw `_PREFERRED_DEFAULT` ui.py:88-92
- post: a request naming nothing is never routed to a hidden provider ui.py:84-87

### chat runtime — `chat_events` / `chat_stream` / `run_chat`
- one authority: `/chat/stream` streams `chat_events` frames; `/chat` (and MCP `ask`) drains them via `run_chat` ui.py:24-30
- post: same request → same compiled plan, retrieval decision, evidence ids, carry admission, executed mode, degraded list, synthesis contract on every route; only transport differs ui.py:27-30

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | `corpora`, `documents`, `runs` | ui.py:146-160, 323, 361-377, 237-239 |
| Postgres read | `retrieval_summaries`, `chunks` | ui.py:282-297 |
| Postgres read | `parent_enrichments`, `document_parent_maps`, `receipts`, `stage_tickets` | ui.py:343-355, 364-372 |
| Postgres write | `UPDATE corpora SET name/query_enabled, updated_at = now()` | ui.py:197-199, 221-223 |
| Postgres write (delegated) | enrichment rows via `polymath_shared.latent.trigger.mint_parent_enrichment` | ui.py:235, 244-245 |
| Files | upload streams bytes to the spool volume in 1 MiB chunks (SPOOL-CLAIM-CHECK-V1; Postgres never holds bytes) | ui.py:6-10, 467 |
| Network | `httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)` | ui.py:111 |
| Network | Ollama daemon generation; LiteLLM provider streaming | ui.py:3529, 3330 |
| env | `POLYMATH_OLLAMA_URL` = `http://127.0.0.1:11434` | ui.py:54-55 |
| env | `POLYMATH_DEFAULT_SYNTHESIZER` = `litellm:anthropic/deepseek-v4-flash-0731,litellm:openai/big-pickle,litellm:openai/mimo-v2.5-free,litellm:openai/nemotron-3.5-lightning-free,ollama:gemma4:31b-cloud` | ui.py:77-79 |
| env | `POLYMATH_OLLAMA_MODELS` = `` (empty → `OLLAMA_FREE_CLOUD_MODELS`) | ui.py:101-102 |
| env | `POLYMATH_CHAT_BRIDGE_COMPILER`, `POLYMATH_CORPUS_EXPLORER` (defaults not shown) | ui.py:2044, 2143 |

## invariants

INVARIANT: rename `name` length ≤ 120 chars — ui.py:191-194 [DERIVED]
  fails-if: `422 invalid_name`, corpus keeps old name.
INVARIANT: `corpus_id` is never rewritten; rename touches `name` + `updated_at` only — ui.py:182-185, 197-199 [DERIVED]
  fails-if: FK chains, run scoping and derived Qdrant collection names orphan (stated in docstring).
INVARIANT: corpora listing row visible iff `(all or docs > 0 or purpose == 'production') and can_see(corpus_id)` — ui.py:172 [DERIVED]
  fails-if: empty non-production husks invisible and undeletable (8 stragglers found after 2026-08-26 purge) — ui.py:164-167.
INVARIANT: documents AND runs aggregates computed in separate subqueries, never one join — ui.py:144-159 [DERIVED]
  fails-if: cross-multiplied counts, measured 60 s+ on 12k runs — ui.py:144-146.
INVARIANT: per-doc counts = correlated `(doc_id)` subqueries producing identical numbers to the old cross-product join — ui.py:329-335 [DERIVED]
  fails-if: 80 s Files view (old) vs 25 ms (new) on cinema corpus 67 docs / 79,787 chunks / 1,968 enrichments.
INVARIANT: `_default_synthesizer` result ∈ offered list whenever offered is non-empty — ui.py:88-92 [DERIVED]
  fails-if: request routed to hidden provider → LiteLLM `Missing credentials` (measured 2026-09-06) — ui.py:86-87.
INVARIANT: `_ollama_registered` failure → empty set, never raises — ui.py:110-114 [DERIVED]
  fails-if: synthesizer listing would error whenever the daemon is down; instead unregistered names list with a pull hint — ui.py:130-131.
INVARIANT: section rows restricted to `kind = 'section_retrieval_summary' AND active` — ui.py:288 [DERIVED]
  fails-if: stale/other-kind summaries leak into the section tree.
INVARIANT: enrichment binds to newest run, query_ready preferred: `ORDER BY (status='query_ready') DESC, created_at DESC LIMIT 1` — ui.py:237-239 [DERIVED]
  fails-if: enrichment minted against an older run.
INVARIANT: run error column = first failed `receipts.error`, else newest `stage_tickets.last_error_note` — ui.py:363-373 [DERIVED]
  fails-if: run list shows no error for a failed run.

## determinism & idempotency
determinism: NONDETERMINISTIC (env defaults ui.py:54-55/77-79/101; network tags call ui.py:111; db reads via `tx()` ui.py:143; clock `updated_at = now()` ui.py:197/221; streaming concurrency in `chat_events` ui.py:3830) [DERIVED]
idempotency: SAFE — GET listings/sections, PATCH rename and query_enabled (same payload → same row). UNSAFE — POST enrich (mints a new enrichment each call ui.py:244-245) and POST upload (streams new spool bytes ui.py:467). [DERIVED]

## failure behaviour
- `except Exception: return set()` in `_ollama_registered` swallows all daemon errors — callers see an empty registered set, models still list as unavailable ui.py:110-114.
- Error codes raised: `422 invalid_name` (empty/oversize name) ui.py:188-194; `404 QUERY_SCOPE_UNKNOWN` (unknown corpus) ui.py:202-204, 226-228, 326-327; `404 no_run_for_corpus` ui.py:241-243; `404 unknown_document` ui.py:264-266.
- Ollama model rows for unregistered names degrade to a description containing the pull command, not an error ui.py:130-131.
- Run errors surface through the COALESCE fallback rather than a raise ui.py:363-373.

## dumb-code flags
- `"ollama:gemma4:31b-cloud"` duplicated: last entry of the default preference list ui.py:79 and the bare fallback in ui.py:80.
- Comment says "OpenCode's glm-5-free is the owner's first choice" ui.py:75, but the `POLYMATH_DEFAULT_SYNTHESIZER` default list contains no `glm-5-free` entry; its first entry is `litellm:anthropic/deepseek-v4-flash-0731` ui.py:79.
- Dead-but-kept branch: `deterministic-template-v3` no longer OFFERED (owner request 2026-08-27) but its execution path is kept for explicit API callers ui.py:62-65.
- Magic truncations: `summary[:400]` ui.py:311, `keywords[:8]` ui.py:312, title `[:80]` / `pid[:16]` ui.py:306, breadcrumb ≤ 90 chars ui.py:1592, runs `LIMIT 25` ui.py:376, tags `timeout=3` ui.py:111, name cap `120` ui.py:191.

## refactor notes
- `chat_events` is the single authority ui.py:24-30: any plan/retrieval/carry/synthesis change must land there; touching only `chat_stream` or only `run_chat` diverges SSE vs JSON vs MCP `ask` behaviour.
- `corpus_id` immutability is structural (FK chains, run scoping, Qdrant collection names) ui.py:182-185 — any rename refactor must stay display-name-only.
- Frontend contract: `App.tsx` takes `synths[0]` as the new-chat default ui.py:57-58 — the ORDER of `synthesizers()`/`_litellm_models()` + `_ollama_models()` output is behaviour, not presentation.
- `documents()` count rewrite must preserve identical numbers to the old join form (DOCUMENTS-LIST-SUBQUERY-V1) ui.py:328-335.
- Visibility helpers `can_see` / `require_corpus` / `require_document` (FRIENDS-ACCESS-V1 D5) must stay on every listing and detail path ui.py:52, 172, 279, 321 — dropping one leaks hidden corpora.
- `_mint_enrichment` shares `mint_parent_enrichment` with the AUTO-ENRICH promotion path ui.py:233-235 — changing one mint changes both surfaces.

## VERIFY
```verify
grep -Fq 'POLYMATH_DEFAULT_SYNTHESIZER' orchestrator/orchestrator/api/ui.py
grep -Fq 'http://127.0.0.1:11434' orchestrator/orchestrator/api/ui.py
grep -Fq 'mint_parent_enrichment' orchestrator/orchestrator/api/ui.py
grep -Fq 'deterministic-template-v3' orchestrator/orchestrator/api/ui.py
! grep -Fq 'UPDATE corpora SET corpus_id' orchestrator/orchestrator/api/ui.py
test "$(grep -c -F 'QUERY_SCOPE_UNKNOWN' orchestrator/orchestrator/api/ui.py)" -ge 2
```
