# unit: orchestrator/orchestrator/api/ui.py
anchor: orchestrator/orchestrator/api/ui.py:1-5091

## purpose
UI support layer (POLYMATH-UI-V1): the thin HTTP endpoints the web chat needs on top of the query product — corpus/document management, upload, model registry, and the single chat runtime streamed as SSE frames — orchestrator/orchestrator/api/ui.py:1-31. `chat_events` is the ONE authority for a chat turn; `/chat/stream` streams its frames, `/chat` (and MCP `ask`) drains them and returns the answer frame — orchestrator/orchestrator/api/ui.py:24-31. [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | APIRouter | module-level FastAPI router | orchestrator/orchestrator/api/ui.py:49 | FastAPI app mounting |
| `corpora` | def GET /corpora | (all: bool = False) -> dict | orchestrator/orchestrator/api/ui.py:156 | — |
| `rename_corpus` | def PATCH /corpora/{corpus_id} | (corpus_id: str, req: RenameCorpusRequest) -> dict | orchestrator/orchestrator/api/ui.py:214 | — |
| `set_query_enabled` | def PATCH /corpora/{corpus_id}/query_enabled | (corpus_id: str, req: QueryEnableRequest) -> dict | orchestrator/orchestrator/api/ui.py:246 | — |
| `enrich_corpus` | def POST /corpora/{corpus_id}/enrich | (corpus_id: str) -> dict | orchestrator/orchestrator/api/ui.py:298 | — |
| `enrich_document` | def POST /documents/{doc_id}/enrich | (doc_id: str) -> dict | orchestrator/orchestrator/api/ui.py:306 | — |
| `document_sections` | def GET /documents/{doc_id}/sections | (doc_id: str) -> dict | orchestrator/orchestrator/api/ui.py:321 | — |
| `documents` | def GET /documents | (corpus_id: str) -> dict | orchestrator/orchestrator/api/ui.py:369 | — |
| `upload` | def POST /upload | (corpus_id, file, allow_near_duplicate) -> … | orchestrator/orchestrator/api/ui.py:534 | — |
| `delete_document` | def | (doc_id, confirm) -> … | orchestrator/orchestrator/api/ui.py:689 | — |
| `delete_corpus` | def | (corpus_id, confirm) -> … | orchestrator/orchestrator/api/ui.py:1135 | — |
| `save_generated` | def | (req: GeneratedPage) -> … | orchestrator/orchestrator/api/ui.py:887 | — |
| `llm_providers` / `llm_provider_upsert` / `llm_provider_delete` / `llm_test` | def | provider CRUD + one-shot model test | orchestrator/orchestrator/api/ui.py:982-1035 | — |
| `chat_events` | def | (req, route, receipt) -> … | orchestrator/orchestrator/api/ui.py:3968 | `chat_stream`, `run_chat` |
| `chat_stream` | def POST /chat/stream | (req) -> StreamingResponse | orchestrator/orchestrator/api/ui.py:5005 | SSE clients |
| `run_chat` | def POST /chat | (req, route, receipt) -> … | orchestrator/orchestrator/api/ui.py:5032 | MCP `ask` (docstring, orchestrator/orchestrator/api/ui.py:26) |
| `RenameCorpusRequest` / `QueryEnableRequest` / `GeneratedPage` / `HistoryTurn` / `CarriedChunk` / `StreamChatRequest` / `ProviderUpsert` / `LlmTest` | class | pydantic request models | orchestrator/orchestrator/api/ui.py:209, 241, 881, 1338, 1343, 1351, 973, 1030 | — |
| `OLLAMA_FREE_CLOUD_MODELS` | const | tuple of 6 model names | orchestrator/orchestrator/api/ui.py:97-98 | `_ollama_allowlist` |

## contracts

`_default_synthesizer()` — orchestrator/orchestrator/api/ui.py:84-93
- in: nothing; reads env + live model lists.
- out: first entry of `_PREFERRED_DEFAULTS` that appears in `offered = [e["id"] for e in (*_litellm_models(), *_ollama_models())]`; else `offered[0]`; else `_PREFERRED_DEFAULT`.
- post: a request naming no synthesizer is never routed to a provider whose key is missing (docstring: measured empty synthesizer fell to `litellm:openai/glm-5-free` with unset OpenCode key → "Missing credentials").

`rename_corpus(corpus_id, req)` — orchestrator/orchestrator/api/ui.py:214-238
- pre: `req.name.strip()` non-empty and ≤ 120 chars, else 422 `invalid_name`.
- out: `{"corpus_id", "name"}` from `UPDATE … RETURNING`; 404 `QUERY_SCOPE_UNKNOWN` if no row.
- post: only `corpora.name` and `updated_at = now()` change; `corpus_id` identity untouched.

`set_query_enabled(corpus_id, req)` — orchestrator/orchestrator/api/ui.py:246-278
- in: boolean `query_enabled`; flips ONLY that column.
- out: `{corpus_id, query_enabled, purpose, query_ready, in_all_libraries}` plus a `note` explaining why an enabled corpus is still out of all-library searches (purpose ≠ production, not query_ready, or friend-private).
- post: a query that NAMES the corpus is never limited by this switch.

`corpora(all)` — orchestrator/orchestrator/api/ui.py:156-206
- out: rows `{corpus_id, purpose, query_enabled, documents, query_ready, in_all_libraries, private, name}` + `notes` (CORPORA_NOTES).
- pre: rows filtered by `can_see` (FRIENDS-ACCESS-V1 D5); default listing hides empty non-production corpora, `all=true` lifts it so empty husks stay visible and deletable.

`document_sections(doc_id)` — orchestrator/orchestrator/api/ui.py:321-365
- out: one section row per active `retrieval_summaries` row of kind `section_retrieval_summary` (ONE-SUMMARY-AUTHORITY), ordered by `COALESCE(c.chunk_index, 0), rs.parent_id`.
- post: heading from parent chunk `heading_path`; NULL falls back to the summary head, so the tree always renders.

`chat_events(req, route, receipt)` — orchestrator/orchestrator/api/ui.py:3968-5001 (CHAT-RUNTIME-V1 §3.7 / §4 P1.f)
- out: phase / token / answer frames plus the retrieved-chunk inventory in the final event.
- post: same request → same compiled plan, retrieval decision, evidence ids, carry admission, executed mode, degraded list, synthesis contract on every route; only transport differs.

## effect surface
- Postgres via `polymath_shared.db.tx` (orchestrator/orchestrator/api/ui.py:47, 164): `corpora` read 168-182 / updated 229-233, 259-266; `documents` counted 173-175, read 309-311; `runs` counted 176-179, read 285-288; `retrieval_summaries` read 330-341; `chunks` read 342-346.
- Network: `httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)` — orchestrator/orchestrator/api/ui.py:112; Ollama grounded streaming (`_ollama_generate` orchestrator/orchestrator/api/ui.py:3667-3696, `_ollama_stream_plain` 3761-3768); any-provider streaming through LiteLLM (`_litellm_generate` orchestrator/orchestrator/api/ui.py:3468-3582).
- Files: upload streams bytes to the spool volume in 1 MiB chunks (SPOOL-CLAIM-CHECK-V1, orchestrator/orchestrator/api/ui.py:534, 6-9); Postgres never holds the bytes — intake carries a content reference through the same `submit_intake` writer path as `/intake`.
- Env flags read: `POLYMATH_OLLAMA_URL` = `"http://127.0.0.1:11434"` (55-56); `POLYMATH_DEFAULT_SYNTHESIZER` = `"litellm:anthropic/deepseek-v4-flash-0731,litellm:openai/big-pickle,litellm:openai/mimo-v2.5-free,litellm:openai/nemotron-3.5-lightning-free,ollama:gemma4:31b-cloud"` (78-80); `POLYMATH_OLLAMA_MODELS` = `""` (101-104); `POLYMATH_CHAT_BRIDGE_COMPILER` (2134 docstring); `POLYMATH_CORPUS_EXPLORER` (2233 docstring); provider keys via `env:NAME` indirection (633-639).

## invariants
INVARIANT: `len(OLLAMA_FREE_CLOUD_MODELS)` == 6 — orchestrator/orchestrator/api/ui.py:97-98 (comment "the six names below", 71) [DERIVED]
  fails-if: comment/allowlist drift; default Ollama list no longer matches the documented free tier.
INVARIANT: display-name length <= 120 — orchestrator/orchestrator/api/ui.py:224-227 [DERIVED]
  fails-if: 422 `invalid_name`, rename rejected.
INVARIANT: Ollama tags timeout == 3 s — orchestrator/orchestrator/api/ui.py:111-112 [DERIVED]
  fails-if: a hung daemon blocks every /synthesizers render for that long per call.
INVARIANT: section `summary` slice <= 400 chars and `keywords` <= 8 items — orchestrator/orchestrator/api/ui.py:359-360 [DERIVED]
  fails-if: payload bloat in the section tree endpoint.
INVARIANT: `query_ready` == (`COALESCE(r.ready, 0)` > 0 over runs with `status = 'query_ready'`) — orchestrator/orchestrator/api/ui.py:176-179 [DERIVED]
  fails-if: a corpus without a converged run is reported searchable.
INVARIANT: `_PREFERRED_DEFAULT` == `_PREFERRED_DEFAULTS[0]` or `"ollama:gemma4:31b-cloud"` when the env list is empty — orchestrator/orchestrator/api/ui.py:80-81 [DERIVED]
  fails-if: unset env yields a synthesizer id no provider offers.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: Ollama `/api/tags` + generation calls, orchestrator/orchestrator/api/ui.py:112, 3667; db: Postgres reads/writes via `tx()`, 164; env: `POLYMATH_*`, 55, 78, 102; clock: `updated_at = now()` in SQL, 230, 260; `uuid`/`time` imported, 39-40)
idempotency: UNSAFE (POST `/corpora/{id}/enrich` and `/documents/{id}/enrich` mint a new enrichment each call — `"status": "queued"`, orchestrator/orchestrator/api/ui.py:301-302, 316; PATCH rename/query_enabled repeat to the same state)

## failure behaviour
- `_ollama_registered` swallows every exception → returns `set()` (orchestrator/orchestrator/api/ui.py:113-115): daemon down still lists models, flagged `available: false` with the pull command in the description (126-137).
- 404 `QUERY_SCOPE_UNKNOWN`: `rename_corpus` 235-237, `set_query_enabled` 268-270, `documents` 374-376.
- 422 `invalid_name` (empty or >120 chars): `rename_corpus` 220-227.
- 404 `no_run_for_corpus`: `_mint_enrichment` 289-292.
- 404 `unknown_document`: `enrich_document` 312-315.
- `_lock_timeout_or_409` / `_raise_if_lock_timeout` (1070-1086): DELETE-LOCK-TIMEOUT-V1 turns a stage lock timeout into an HTTP conflict [INFERRED — from the name and the "bounded wait" docstring at 689-698].
- DELETE-WINS (owner directive 2026-08-30): `_quiesce_doc` 1089-1100 and `_quiesce_corpus` 1103-1130 supersede in-flight tickets before a delete.

## dumb-code flags
- `"ollama:gemma4:31b-cloud"` appears as a literal in 3 independent places: env-default string 80, `_PREFERRED_DEFAULT` fallback 81, tuple member 97 — changing one leaves the others stale. [DERIVED]
- Comment drift: block comment 58-77 says the default order was measured with "OpenCode's glm-5-free is the owner's first choice", but the actual env default's first entry is `litellm:anthropic/deepseek-v4-flash-0731` (80); comment also cites "deepseek-v4-flash 3.6 s" vs the shipped `deepseek-v4-flash-0731` id. [DERIVED]
- Magic numbers: name cap `120` (224), daemon timeout `3` (112), summary cap `400` (359), keyword cap `8` (360), breadcrumb cap `90` chars (FACTS 1665 docstring), 1 MiB upload chunk (FACTS 534).
- `'›'` separator logic duplicated: `" › ".join(...)` at 349 and `rsplit("›", 1)` at 354 — changing the separator in one place breaks title extraction. [DERIVED]
- Retired-but-kept path: `deterministic-template-v3` no longer OFFERED (owner request 2026-08-27) but its execution path stays for explicit API callers — orchestrator/orchestrator/api/ui.py:62-66. [DERIVED]

## refactor notes
- `corpus_id` is immutable identity: it keys FK chains, run scoping and derived Qdrant collection names; renaming it orphans the stores — orchestrator/orchestrator/api/ui.py:215-218.
- Keep `documents` and `runs` as separate LEFT JOIN subqueries in `corpora`; the joined form cross-multiplies (measured 60s+ on 12k runs) — orchestrator/orchestrator/api/ui.py:165-166.
- `chat_events` is the single chat authority: `/chat/stream`, `/chat` and MCP `ask` must keep sharing it; the same request must yield the same plan, evidence ids, carry admission, executed mode, degraded list and synthesis contract — orchestrator/orchestrator/api/ui.py:24-31.
- `_default_synthesizer` mirrors the dropdown default rule (frontend App.tsx takes `synths[0]`, orchestrator/orchestrator/api/ui.py:58-59); changing one without the other splits default synthesizers.
- `CORPORA_NOTES` keys (`query_ready`, `in_all_libraries`, `query_enabled`, `purpose`, `private`) are read by agents from the answer itself — orchestrator/orchestrator/api/ui.py:142-152; renaming a key breaks consumers.
- Upload must keep the claim-check shape (spool volume bytes, `submit_intake` reference) — orchestrator/orchestrator/api/ui.py:6-9.

## VERIFY
```verify
grep -Fq 'OLLAMA_FREE_CLOUD_MODELS = ("gemma4:31b-cloud", "gpt-oss:120b-cloud", "gpt-oss:20b-cloud",' orchestrator/orchestrator/api/ui.py
grep -Fq 'name must be 120 characters or fewer' orchestrator/orchestrator/api/ui.py
grep -Fq 'http://127.0.0.1:11434' orchestrator/orchestrator/api/ui.py
grep -Fq 'section_retrieval_summary' orchestrator/orchestrator/api/ui.py
grep -Fq 'QUERY_SCOPE_UNKNOWN' orchestrator/orchestrator/api/ui.py
test "$(grep -c -F 'gemma4:31b-cloud' orchestrator/orchestrator/api/ui.py)" -ge 3
! grep -Fq 'renam_corpus' orchestrator/orchestrator/api/ui.py
```
