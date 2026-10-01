# unit: orchestrator/orchestrator/api/ui.py
anchor: orchestrator/orchestrator/api/ui.py:1-4863
## purpose
UI support layer (POLYMATH-UI-V1): thin FastAPI endpoints the web chat needs on top of the query product — corpus/document management, upload, model catalog, and the single CHAT-RUNTIME-V1 chat turn exposed both as SSE (`/chat/stream`) and one JSON body (`/chat`, MCP `ask`) (orchestrator/orchestrator/api/ui.py:1-31). [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| router | var | `APIRouter()` | orchestrator/orchestrator/api/ui.py:48 | FastAPI app (mounts routes) |
| corpora | def (GET /corpora) | `all: bool = False -> dict` | orchestrator/orchestrator/api/ui.py:142 | web chat corpus picker |
| rename_corpus | def (PATCH /corpora/{corpus_id}) | `corpus_id: str, req: RenameCorpusRequest -> dict` | orchestrator/orchestrator/api/ui.py:181 | — |
| set_query_enabled | def (PATCH /corpora/{corpus_id}/query_enabled) | `corpus_id: str, req: QueryEnableRequest -> dict` | orchestrator/orchestrator/api/ui.py:213 | — |
| enrich_corpus | def (POST /corpora/{corpus_id}/enrich) | `corpus_id: str -> dict` | orchestrator/orchestrator/api/ui.py:249 | — |
| enrich_document | def (POST /documents/{doc_id}/enrich) | `doc_id: str -> dict` | orchestrator/orchestrator/api/ui.py:257 | — |
| document_sections | def (GET /documents/{doc_id}/sections) | `doc_id: str -> dict` | orchestrator/orchestrator/api/ui.py:272 | — |
| documents | def (GET /documents) | `corpus_id: str -> dict` | orchestrator/orchestrator/api/ui.py:320 | file-manager listing |
| document_status_view | def (GET /documents/{doc_id}/status) | `doc_id: str -> dict` | orchestrator/orchestrator/api/ui.py:397 | — |
| upload | def (POST /upload) | `corpus_id, file, allow_near_duplicate -> dict` | orchestrator/orchestrator/api/ui.py:485 | spool intake |
| synthesizers | def (GET /synthesizers) | `-> dict` | orchestrator/orchestrator/api/ui.py:900 | model selector |
| llm_providers / llm_provider_upsert / llm_provider_delete | def | provider CRUD | orchestrator/orchestrator/api/ui.py:933-978 | — |
| llm_test | def | `req: LlmTest -> dict` | orchestrator/orchestrator/api/ui.py:986 | — |
| delete_document | def | `doc_id: str, confirm -> dict` | orchestrator/orchestrator/api/ui.py:640 | — |
| delete_corpus | def | `corpus_id: str, confirm -> dict` | orchestrator/orchestrator/api/ui.py:1086 | — |
| chat_events | def | `req, route, receipt -> frames` | orchestrator/orchestrator/api/ui.py:3848 | chat_stream, run_chat |
| chat_stream | def (POST /chat/stream) | `req -> StreamingResponse` | orchestrator/orchestrator/api/ui.py:4778 | SSE transport |
| run_chat | def | `req, route, receipt -> dict` | orchestrator/orchestrator/api/ui.py:4805 | `/chat`, MCP `ask` (module docstring) (orchestrator/orchestrator/api/ui.py:26-27) |
| ui_pulse | def | `-> dict` | orchestrator/orchestrator/api/ui.py:883 | frontend keepalive ping |
| save_generated | def | `req: GeneratedPage -> dict` | orchestrator/orchestrator/api/ui.py:838 | — |
| reasoning_modes | def | `-> dict` | orchestrator/orchestrator/api/ui.py:861 | UI dropdown |

## contracts
**corpora(all=False)** — orchestrator/orchestrator/api/ui.py:142-173
- in: query param `all: bool = False`
- out: `{"corpora": [...]}` rows of `corpus_id, purpose, query_enabled, documents, query_ready, name` (name falls back to corpus_id) (orchestrator/orchestrator/api/ui.py:168-172)
- pre: aggregates computed in separate LEFT JOINs, never one joined query (cross-multiplies; measured 60s+ on 12k runs) (orchestrator/orchestrator/api/ui.py:144-146)
- post: default listing hides empty non-production corpora; `all=true` lifts filter; every row passes `can_see(corpus_id)` (FRIENDS-ACCESS-V1 D5) (orchestrator/orchestrator/api/ui.py:163-172)

**rename_corpus(corpus_id, req)** — orchestrator/orchestrator/api/ui.py:181-205
- in: `name` stripped; non-empty, ≤ 120 chars else 422 `error_code: "invalid_name"` (orchestrator/orchestrator/api/ui.py:186-194)
- out: `{"corpus_id", "name"}` from RETURNING (orchestrator/orchestrator/api/ui.py:200-205)
- pre: only `corpora.name` + `updated_at = now()` mutated; `corpus_id` immutable (keys FK chains, run scoping, Qdrant collection names) (orchestrator/orchestrator/api/ui.py:182-185, 197)
- post: unknown corpus → 404 `error_code: "QUERY_SCOPE_UNKNOWN"` (orchestrator/orchestrator/api/ui.py:201-204)

**set_query_enabled(corpus_id, req)** — orchestrator/orchestrator/api/ui.py:213-229
- in: `query_enabled: bool`; flips ONLY `query_enabled`, never `purpose` (orchestrator/orchestrator/api/ui.py:214-218, 221)
- post: unknown corpus → 404 `"QUERY_SCOPE_UNKNOWN"` (orchestrator/orchestrator/api/ui.py:226-228)

**enrich_corpus / enrich_document** — orchestrator/orchestrator/api/ui.py:249-268
- out: `{"status": "queued", **mint}` (orchestrator/orchestrator/api/ui.py:253, 268)
- pre: shared `_mint_enrichment` → `mint_parent_enrichment` from `polymath_shared.latent.trigger` — same path AUTO-ENRICH uses (orchestrator/orchestrator/api/ui.py:232-235)
- post: no run → 404 `"no_run_for_corpus"`; unknown doc → 404 `"unknown_document"` (orchestrator/orchestrator/api/ui.py:240-243, 263-266)

**document_sections(doc_id)** — orchestrator/orchestrator/api/ui.py:272-316
- in: `require_document` visibility gate (orchestrator/orchestrator/api/ui.py:279)
- out: sections ordered by `COALESCE(c.chunk_index, 0), rs.parent_id`; per section `parent_id, title, heading_path, summary[:400], keywords[:8], coverage, children` (orchestrator/orchestrator/api/ui.py:289, 307-315)
- pre: reads only `retrieval_summaries` rows with `kind = 'section_retrieval_summary' AND rs.active` (ONE-SUMMARY-AUTHORITY) (orchestrator/orchestrator/api/ui.py:285-288)
- post: NULL heading_path (legacy ingests) falls back to summary head so the tree always renders (orchestrator/orchestrator/api/ui.py:275-277, 305-306)

**documents(corpus_id)** — orchestrator/orchestrator/api/ui.py:320-393
- in: `require_corpus` gate; unknown corpus → 404 `"QUERY_SCOPE_UNKNOWN"` (orchestrator/orchestrator/api/ui.py:321, 325-327)
- out: per-document `children/parents/enriched/enrich_failed/map_active` as correlated subqueries + last 25 runs with latest error from `receipts`/`stage_tickets` (orchestrator/orchestrator/api/ui.py:335-377)
- pre: DOCUMENTS-LIST-SUBQUERY-V1 — correlated `(doc_id)`-indexed subqueries, 25 ms vs 80 s for the old JOIN+DISTINCT form (measured 2026-09-05, corpus `cinema`, 67 docs / 79,787 chunks / 1,968 enrichments) (orchestrator/orchestrator/api/ui.py:328-334)

**chat_events / chat_stream / run_chat** — orchestrator/orchestrator/api/ui.py:3848, 4778, 4805
- one runtime: scope → compiler → retrieval composition → graph/wildcard → assemble → carry → synthesize → answer, as phase/token/answer frames (orchestrator/orchestrator/api/ui.py:15-22, 3848)
- post: same request yields same compiled plan, retrieval decision, evidence ids, carry admission, executed mode, degraded list, synthesis contract on every route; only transport differs (frames vs body; receipt `kind`/`client`); scope fail-closed through shared resolver (orchestrator/orchestrator/api/ui.py:24-31)

## effect surface
- Postgres read: `corpora`, `documents`, `runs`, `chunks`, `retrieval_summaries`, `parent_enrichments`, `document_parent_maps`, `receipts`, `stage_tickets` (orchestrator/orchestrator/api/ui.py:146-160, 196-199, 221-224, 237-239, 261, 282-296, 323-376)
- Postgres write: `corpora` (`name`, `query_enabled`, `updated_at = now()`) (orchestrator/orchestrator/api/ui.py:197-199, 221-223); delete paths via `_delete_document_tx` (652-829) and `_delete_corpus_tx` (1111-1284)
- Network: `httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)` to the local Ollama daemon (orchestrator/orchestrator/api/ui.py:108-112)
- Files: upload streams bytes to the spool volume in 1 MiB blocks (SPOOL-CLAIM-CHECK-V1); Postgres never holds the bytes (orchestrator/orchestrator/api/ui.py:6-10, 485)
- Env: `POLYMATH_OLLAMA_URL` = `"http://127.0.0.1:11434"` (orchestrator/orchestrator/api/ui.py:54-55); `POLYMATH_DEFAULT_SYNTHESIZER` = `"litellm:anthropic/deepseek-v4-flash-0731,litellm:openai/big-pickle,litellm:openai/mimo-v2.5-free,litellm:openai/nemotron-3.5-lightning-free,ollama:gemma4:31b-cloud"` (orchestrator/orchestrator/api/ui.py:77-79); `POLYMATH_OLLAMA_MODELS` = `""` (empty → builtin 6-name list) (orchestrator/orchestrator/api/ui.py:100-103); `POLYMATH_CHAT_BRIDGE_COMPILER` (orchestrator/orchestrator/api/ui.py:2062 doc); `POLYMATH_CORPUS_EXPLORER` (orchestrator/orchestrator/api/ui.py:2161 doc)

## invariants
INVARIANT: len(OLLAMA_FREE_CLOUD_MODELS) == 6 — orchestrator/orchestrator/api/ui.py:96-97 [DERIVED]
  fails-if: dropdown/catalog drifts from the daemon's free tier the code promises.
INVARIANT: Ollama tags timeout == 3 seconds — orchestrator/orchestrator/api/ui.py:111 [DERIVED]
  fails-if: a hung daemon blocks every `/synthesizers` request beyond 3 s per call.
INVARIANT: corpus rename name length <= 120 — orchestrator/orchestrator/api/ui.py:191-194 [DERIVED]
  fails-if: 422 `invalid_name` returned to the caller.
INVARIANT: section summary length <= 400, keywords count <= 8 — orchestrator/orchestrator/api/ui.py:311-312 [DERIVED]
  fails-if: oversized cards leak into the section tree payload.
INVARIANT: `_default_synthesizer()` never returns a provider id missing from the offered list unless the offered list is empty — orchestrator/orchestrator/api/ui.py:88-92 [DERIVED]
  fails-if: empty-synthesizer requests route to a hidden provider → LiteLLM "Missing credentials" (incident, 2026-09-06) (orchestrator/orchestrator/api/ui.py:86-87).
INVARIANT: documents-listing counts come from correlated subqueries, not one joined DISTINCT — orchestrator/orchestrator/api/ui.py:328-340 [DERIVED]
  fails-if: regressing to the join form returns the 80 s/row-cross-multiplied Files view.
INVARIANT: `/chat/stream` frames and `/chat` body come from the same `chat_events` runtime — orchestrator/orchestrator/api/ui.py:24-31 [DERIVED]
  fails-if: the two transports disagree on plan, evidence ids, or receipts.

## determinism & idempotency
determinism: NONDETERMINISTIC (env: `POLYMATH_OLLAMA_URL`/`POLYMATH_DEFAULT_SYNTHESIZER`/`POLYMATH_OLLAMA_MODELS` at 54, 77, 101; network: Ollama `/api/tags` probe at 111; db: reads/writes through `tx()` at 143, 195, 219, 251; `updated_at = now()` at 197, 221)
idempotency: UNSAFE (rename/toggle rewrite `updated_at` each call at 197, 221; enrich endpoints queue new enrichment mints at 253, 268; delete paths remove rows)

## failure behaviour
- `_ollama_registered` swallows every `Exception` → returns `set()`; daemon-down degrades to all models flagged `available: false` with pull instructions (orchestrator/orchestrator/api/ui.py:113-114, 123-131)
- 404 `error_code: "QUERY_SCOPE_UNKNOWN"` — rename_corpus, set_query_enabled, documents on unknown corpus (orchestrator/orchestrator/api/ui.py:202-204, 226-228, 325-327)
- 422 `error_code: "invalid_name"` — empty or >120-char rename (orchestrator/orchestrator/api/ui.py:188-194)
- 404 `error_code: "no_run_for_corpus"` — enrich on corpus without runs (orchestrator/orchestrator/api/ui.py:241-243)
- 404 `error_code: "unknown_document"` — enrich on missing doc (orchestrator/orchestrator/api/ui.py:264-266)
- delete paths: DELETE-LOCK-TIMEOUT-V1 bounded wait → 409 on stage-lock timeout via `_lock_timeout_or_409`/`_raise_if_lock_timeout` (orchestrator/orchestrator/api/ui.py:1021-1037); DELETE-WINS supersedes in-flight tickets via `_quiesce_doc`/`_quiesce_corpus` (1040-1081)
- compiler lanes: `_run_compiler_lanes` returns the first REAL plan; transport failure/empty falls through to next attempt (COMPILER-WORKS-WITHOUT-OLLAMA) (orchestrator/orchestrator/api/ui.py:1723-1743)

## dumb-code flags
- Comment drift: the `POLYMATH_DEFAULT_SYNTHESIZER` comment says "OpenCode's glm-5-free is the owner's first choice" but the actual default list's first entry is `litellm:anthropic/deepseek-v4-flash-0731` (orchestrator/orchestrator/api/ui.py:73-79)
- Dead-ish branch: `deterministic-template-v3` no longer OFFERED (owner request 2026-08-27) but execution path kept for API callers naming it explicitly (orchestrator/orchestrator/api/ui.py:62-65)
- Fallback literal `ollama:gemma4:31b-cloud` appears twice — `_PREFERRED_DEFAULT` (line 80) and as last list entry (line 79) (orchestrator/orchestrator/api/ui.py:77-80)
- Magic numbers: 3 (Ollama timeout, line 111), 120 (name cap, 191), 400 (summary cap, 311), 8 (keywords cap, 312), 80 (title cap, 306), 25 (runs LIMIT, 376), 90 (`_clean_crumb` cap, 1610)
- `_ollama_registered` bare `except Exception` hides all daemon errors identically (orchestrator/orchestrator/api/ui.py:113-114)

## refactor notes
- `corpus_id` is identity: renaming it would orphan FK chains, run scoping and Qdrant collection names — only `name` may change (orchestrator/orchestrator/api/ui.py:182-185)
- `/chat`, `/chat/stream` and MCP `ask` all drain `chat_events`; splitting the runtime breaks the same-plan/same-receipt guarantee (orchestrator/orchestrator/api/ui.py:24-31, 3848, 4778, 4805)
- `documents` performance fix depends on correlated `(doc_id)`-indexed subqueries; a JOIN rewrite reintroduces the cross-multiplied 80 s form (orchestrator/orchestrator/api/ui.py:328-334)
- `corpora` aggregates must stay independent subqueries (measured 60s+ joined) (orchestrator/orchestrator/api/ui.py:144-146)
- `_mint_enrichment` shares the AUTO-ENRICH mint in `polymath_shared.latent.trigger`; changing either side changes both buttons and promotion (orchestrator/orchestrator/api/ui.py:232-235)
- `can_see`/`require_corpus`/`require_document` (FRIENDS-ACCESS-V1 D5) gate every listing; new endpoints must add them or leak cross-corpus rows (orchestrator/orchestrator/api/ui.py:172, 279, 321)
- Default-list `_PREFERRED_DEFAULTS` is env-overridable; frontend `App.tsx` takes `synths[0]` as the new-chat default, so list order is user-visible (orchestrator/orchestrator/api/ui.py:57-59, 73)

## VERIFY
```verify
grep -Fq 'POLYMATH_DEFAULT_SYNTHESIZER' orchestrator/orchestrator/api/ui.py
grep -Fq 'litellm:anthropic/deepseek-v4-flash-0731,litellm:openai/big-pickle,litellm:openai/mimo-v2.5-free,litellm:openai/nemotron-3.5-lightning-free,ollama:gemma4:31b-cloud' orchestrator/orchestrator/api/ui.py
grep -Fq 'http://127.0.0.1:11434' orchestrator/orchestrator/api/ui.py
grep -Fq 'nemotron-3-ultra:cloud' orchestrator/orchestrator/api/ui.py
grep -Eq 'timeout=3' orchestrator/orchestrator/api/ui.py
grep -Fq 'section_retrieval_summary' orchestrator/orchestrator/api/ui.py
grep -Fq 'name must be 120 characters or fewer' orchestrator/orchestrator/api/ui.py
grep -Fq 'QUERY_SCOPE_UNKNOWN' orchestrator/orchestrator/api/ui.py
```
