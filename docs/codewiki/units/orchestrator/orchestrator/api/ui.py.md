# unit: orchestrator/orchestrator/api/ui.py
anchor: orchestrator/orchestrator/api/ui.py:1-5064

## purpose
The UI support layer (POLYMATH-UI-V1): thin FastAPI endpoints the web chat needs on top of the existing query product — corpus/file management, spool-streamed upload, model catalog, and the single chat runtime `chat_events` (scope → compiler → retrieval composition → graph/wildcard → assemble → carry → synthesize → answer) exposed as SSE frames or one drained JSON body. orchestrator/orchestrator/api/ui.py:1-32 [DERIVED]

## public surface

| symbol | kind | signature | anchor | used by |
|---|---|---|---|---|
| corpora | route GET /corpora | (all: bool = False) -> dict | orchestrator/orchestrator/api/ui.py:154-205 | web chat corpus picker (orchestrator/orchestrator/api/ui.py:4) |
| rename_corpus | route PATCH /corpora/{corpus_id} | (corpus_id: str, req: RenameCorpusRequest) -> dict | orchestrator/orchestrator/api/ui.py:212-237 | — |
| set_query_enabled | route PATCH /corpora/{corpus_id}/query_enabled | (corpus_id: str, req: QueryEnableRequest) -> dict | orchestrator/orchestrator/api/ui.py:244-277 | — |
| enrich_corpus | route POST /corpora/{corpus_id}/enrich | (corpus_id: str) -> dict | orchestrator/orchestrator/api/ui.py:296-301 | — |
| enrich_document | route POST /documents/{doc_id}/enrich | (doc_id: str) -> dict | orchestrator/orchestrator/api/ui.py:304-316 | — |
| document_sections | route GET /documents/{doc_id}/sections | (doc_id: str) -> dict | orchestrator/orchestrator/api/ui.py:319-364 | — |
| documents | route GET /documents | (corpus_id: str) -> dict | orchestrator/orchestrator/api/ui.py:367-441 | file-manager listing (orchestrator/orchestrator/api/ui.py:5) |
| upload | route POST /upload | (corpus_id, file, allow_near_duplicate) | orchestrator/orchestrator/api/ui.py:533-603 | multipart upload, spool claim-check (orchestrator/orchestrator/api/ui.py:6-10) |
| synthesizers | route GET /synthesizers | () -> dict | orchestrator/orchestrator/api/ui.py:948-969 | frontend takes `synths[0]` as default (orchestrator/orchestrator/api/ui.py:57-59) |
| chat_events | def (the ONE chat runtime) | (req, route, receipt) | orchestrator/orchestrator/api/ui.py:3947-4974 | chat_stream, run_chat |
| chat_stream | route POST /chat/stream | (req) | orchestrator/orchestrator/api/ui.py:4978-4983 | SSE transport (orchestrator/orchestrator/api/ui.py:15) |
| run_chat | def (drains frames) | (req, route, receipt) -> dict | orchestrator/orchestrator/api/ui.py:5005-5063 | `/chat` and MCP `ask` (orchestrator/orchestrator/api/ui.py:25-26) |

Other route handlers whose paths are truncated in the material: document_status_view (445-471), control_plane (475-490), control_plane_pool (494-499), control_plane_predicates (503-512), documents_summary (516-526), delete_document (688-697), save_generated (886-905), reasoning_modes (909-927), ui_pulse (931-944), llm_providers (981-992), llm_provider_upsert (996-1018), llm_provider_delete (1022-1026), llm_test (1034-1066), delete_corpus (1134-1156). Pydantic models: RenameCorpusRequest:208, QueryEnableRequest:240, GeneratedPage:880, ProviderUpsert:972, LlmTest:1029, HistoryTurn:1337, CarriedChunk:1342, StreamChatRequest:1350. orchestrator/orchestrator/api/ui.py:445-1402 [DERIVED]

## contracts

**corpora(all)** — orchestrator/orchestrator/api/ui.py:154-205
- in: query param `all: bool = False` (155).
- pre: `ensure_own_private_library()` runs once per process (161-162); visible rows filtered by `can_see(r[0])` FRIENDS-ACCESS-V1 D5 (190).
- effect: one SELECT over `corpora` with two independent LEFT JOIN subqueries (documents COUNT, runs COUNT WHERE status = 'query_ready') (166-181).
- out: `{"corpora": [{corpus_id, purpose, query_enabled, documents, query_ready, in_all_libraries, private, name}], "notes": CORPORA_NOTES}` (199-204, 143-151).
- post: default listing hides empty non-production corpora; `listed(r)` = `all or docs > 0 or (purpose == "production" and not (owner_view and is_private_library))` (183-197).

**rename_corpus(corpus_id, req)** — orchestrator/orchestrator/api/ui.py:212-237
- in: body `{name: str}` (208-209).
- pre: `name.strip()` non-empty else 422 `invalid_name` (218-222); `len(name) > 120` else 422 `invalid_name` (223-226).
- effect: `UPDATE corpora SET name = %s, updated_at = now() ... RETURNING corpus_id, name` — display name ONLY (228-231, 213-217).
- out: `{corpus_id, name}` (236); 404 `QUERY_SCOPE_UNKNOWN` when the row is absent (233-236).

**set_query_enabled(corpus_id, req)** — orchestrator/orchestrator/api/ui.py:244-277
- in: body `{query_enabled: bool}` (240-241).
- effect: `UPDATE corpora SET query_enabled = %s, updated_at = now() ... RETURNING corpus_id, query_enabled, purpose, EXISTS (SELECT 1 FROM runs r WHERE r.corpus_id = corpora.corpus_id AND r.status = 'query_ready')` (258-265).
- out: `in_all_libraries` = `in_all_libraries(purpose, query_enabled, query_ready)` AND `all_libraries_view([corpus_id])` (270); explanatory `note` when enabled but not a member (273-276).
- guarantee: never limits a query that NAMES the corpus (246-248).

**_mint_enrichment(conn, corpus_id, doc_id)** — orchestrator/orchestrator/api/ui.py:280-293
- pre: picks latest run `ORDER BY (status='query_ready') DESC, created_at DESC LIMIT 1`; none → 404 `no_run_for_corpus` (284-291).
- effect: delegates to `polymath_shared.latent.trigger.mint_parent_enrichment` — the same path AUTO-ENRICH uses at promotion (292-293, 280-282).
- callers: enrich_corpus / enrich_document return `{"status": "queued", ...}` (300-301, 315-316).

**document_sections(doc_id)** — orchestrator/orchestrator/api/ui.py:319-364
- pre: `require_document(conn, doc_id)` FRIENDS-ACCESS-V1 D5 (327).
- reads: `retrieval_summaries rs LEFT JOIN chunks c ON c.chunk_id = rs.parent_id WHERE rs.doc_id = %s AND rs.kind = 'section_retrieval_summary' AND rs.active ORDER BY COALESCE(c.chunk_index, 0), rs.parent_id` (329-340); child counts from `chunks ... tier = 'child'` (341-345).
- out: per section `{parent_id, title, heading_path, summary, keywords, coverage, children}` with `summary[:400]`, `keywords[:8]`, title = last heading segment else `summary.split(". ")[0][:80]` else `pid[:16]` (347-364).

**_default_synthesizer()** — orchestrator/orchestrator/api/ui.py:83-92
- out: first `_PREFERRED_DEFAULTS` entry present in offered ids `[*_litellm_models(), *_ollama_models()]`; else `offered[0]`; else `_PREFERRED_DEFAULT` (88-92).
- rule: "a request that names nothing must never be routed to a hidden provider" — measured failure: empty synthesizer fell to `litellm:openai/glm-5-free` with the OpenCode key unset → LiteLLM "Missing credentials" (84-87).

**chat_events(req, route, receipt)** — orchestrator/orchestrator/api/ui.py:3947-4974
- single authority for a chat turn; `/chat/stream` streams its frames, `/chat`/MCP `ask` drains them (24-26).
- post: same request → same compiled plan, retrieval decision, evidence ids, carry admission, executed mode, degraded list and synthesis contract on every route; only the transport differs (26-29).
- scope stays fail-closed through the shared resolver (30-31).

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres `corpora` | read (listing SELECT); write UPDATE `name`/`updated_at`; write UPDATE `query_enabled`/`updated_at` | orchestrator/orchestrator/api/ui.py:166-181, 228-231, 258-264 |
| Postgres `documents` | read COUNT per corpus; read `corpus_id` by `doc_id` | orchestrator/orchestrator/api/ui.py:167-170, 308-310 |
| Postgres `runs` | read COUNT `status = 'query_ready'`; EXISTS readiness; latest-run pick | orchestrator/orchestrator/api/ui.py:175-178, 261-264, 284-287 |
| Postgres `retrieval_summaries` | read `kind = 'section_retrieval_summary' AND active` | orchestrator/orchestrator/api/ui.py:329-340 |
| Postgres `chunks` | read heading_path/chunk_index join; child COUNT `tier = 'child'` | orchestrator/orchestrator/api/ui.py:330-345 |
| network | `httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)` daemon probe | orchestrator/orchestrator/api/ui.py:110-111 |
| network | LiteLLM provider streaming (`_litellm_generate`), local Ollama streaming (`_ollama_generate`) | orchestrator/orchestrator/api/ui.py:3447-3561, 3646-3675 |
| files | spool volume: upload streams bytes out of Postgres ("Postgres never holds the bytes") | orchestrator/orchestrator/api/ui.py:5-10 |
| Qdrant | no direct access; derived collection names keyed by `corpus_id` only | orchestrator/orchestrator/api/ui.py:215-217 |
| env | `POLYMATH_OLLAMA_URL` = `"http://127.0.0.1:11434"`; `POLYMATH_DEFAULT_SYNTHESIZER` = `"litellm:anthropic/deepseek-v4-flash-0731,litellm:openai/big-pickle,litellm:openai/mimo-v2.5-free,litellm:openai/nemotron-3.5-lightning-free,ollama:gemma4:31b-cloud"`; `POLYMATH_OLLAMA_MODELS` = `""`; `POLYMATH_CHAT_BRIDGE_COMPILER`; `POLYMATH_CORPUS_EXPLORER` | orchestrator/orchestrator/api/ui.py:54-55, 77-79, 100-103, 2133, 2232 |

## invariants
INVARIANT: /corpora aggregates use independent subqueries, never a documents×runs join — a joined form measured "60s+ on 12k runs" — orchestrator/orchestrator/api/ui.py:164-169 [DERIVED]
  fails-if: /corpora becomes unusably slow as runs grow.
INVARIANT: `len(name) <= 120` and non-empty after strip — orchestrator/orchestrator/api/ui.py:218-226 [DERIVED]
  fails-if: 422 `invalid_name`.
INVARIANT: rename_corpus mutates only `corpora.name`/`updated_at`; `corpus_id` is immutable — orchestrator/orchestrator/api/ui.py:213-231 [DERIVED]
  fails-if: FK chains, run scoping and derived Qdrant collection names orphan.
INVARIANT: default synthesizer ∈ offered set unless nothing is offered — orchestrator/orchestrator/api/ui.py:88-92 [DERIVED]
  fails-if: turns fail at LiteLLM with "Missing credentials" (86-87).
INVARIANT: Ollama daemon probe bounded at `timeout=3`, exceptions degrade to `set()` — orchestrator/orchestrator/api/ui.py:110-114 [DERIVED]
  fails-if: model listing blocks on a dead daemon.
INVARIANT: section `summary` ≤ 400 chars, `keywords` ≤ 8 entries — orchestrator/orchestrator/api/ui.py:359-360 [DERIVED]
  fails-if: UI section-tree payload bloat.
INVARIANT: same request → same plan, evidence ids, executed mode, degraded list on `/chat/stream` and `/chat` — orchestrator/orchestrator/api/ui.py:26-29 [DERIVED]
  fails-if: MCP `ask` answers diverge from the UI stream.

## determinism & idempotency
determinism: NONDETERMINISTIC (db reads via `tx()` orchestrator/orchestrator/api/ui.py:163; Ollama daemon HTTP orchestrator/orchestrator/api/ui.py:110-111; LLM network streaming orchestrator/orchestrator/api/ui.py:3447-3561, 3646-3675; env-read defaults orchestrator/orchestrator/api/ui.py:54-55, 77-79, 100-103; session scope `allowed_corpora`/`can_see` orchestrator/orchestrator/api/ui.py:156-157, 189-190)
idempotency: UNSAFE (every PATCH bumps `updated_at = now()` orchestrator/orchestrator/api/ui.py:228-231, 258-264; each enrich call mints new queued work orchestrator/orchestrator/api/ui.py:300-301, 315-316)

## failure behaviour
- `_ollama_registered` swallows every exception → `set()`; unregistered models still list with the pull command in `description`, flagged `available: false` — orchestrator/orchestrator/api/ui.py:112-114, 117-131 [DERIVED]
- 404 `QUERY_SCOPE_UNKNOWN`: rename_corpus (233-236), set_query_enabled (266-269), documents (373-375) — orchestrator/orchestrator/api/ui.py:233-236, 266-269, 373-375 [DERIVED]
- 404 `no_run_for_corpus` from `_mint_enrichment` — orchestrator/orchestrator/api/ui.py:288-291 [DERIVED]
- 404 `unknown_document` from enrich_document — orchestrator/orchestrator/api/ui.py:311-314 [DERIVED]
- 422 `invalid_name` (empty or >120 chars) from rename_corpus — orchestrator/orchestrator/api/ui.py:219-226 [DERIVED]
- `_ollama_stream_plain`: fallback stream without `think` for models that reject it — orchestrator/orchestrator/api/ui.py:3740-3747 [DERIVED]
- `_run_compiler_lanes`: tries attempts in order, returns the first REAL plan (transport failures fall through) — orchestrator/orchestrator/api/ui.py:1777-1814 [DERIVED]
- delete paths map lock timeouts via `_lock_timeout_or_409` / `_raise_if_lock_timeout` (DELETE-LOCK-TIMEOUT-V1) — orchestrator/orchestrator/api/ui.py:1069-1085 [DERIVED]

## dumb-code flags
- Comment vs code mismatch: comment states "OpenCode's glm-5-free is the owner's first choice" but `_PREFERRED_DEFAULTS[0]` is `litellm:anthropic/deepseek-v4-flash-0731` and `glm-5-free` is absent from the list — orchestrator/orchestrator/api/ui.py:73-79 [DERIVED]
- Magic numbers: `timeout=3` (111), `120` (223), `[:400]` (359), `[:8]` (360), `[:80]` / `pid[:16]` (353-354) — orchestrator/orchestrator/api/ui.py:111, 223, 353-360 [DERIVED]
- Readiness computed two different ways: `COUNT(*) ... status = 'query_ready'` in corpora vs `EXISTS (SELECT 1 FROM runs ...)` in set_query_enabled — orchestrator/orchestrator/api/ui.py:175-178, 261-264 [DERIVED]
- `"ollama:gemma4:31b-cloud"` literal appears as the hard fallback `_PREFERRED_DEFAULT` (80), inside the default preference list (79), and in `OLLAMA_FREE_CLOUD_MODELS` (96) — orchestrator/orchestrator/api/ui.py:79-80, 96 [DERIVED]
- Stale dated decision comments stacked in one block (STUDY-DEFAULT-2026-08-27, CHAT-MODEL-CATALOG-V1 2026-09-06) over the same constant — orchestrator/orchestrator/api/ui.py:57-76 [DERIVED]

## refactor notes
- Never rename `corpus_id`: it keys FK chains, run scoping and derived Qdrant collection names — renaming identity orphans the stores — orchestrator/orchestrator/api/ui.py:214-217 [DERIVED]
- Keep /corpora aggregates as independent subqueries; a documents+runs join measured "60s+ on 12k runs" — orchestrator/orchestrator/api/ui.py:164-169 [DERIVED]
- documents() subquery shape is a measured fix (DOCUMENTS-LIST-SUBQUERY-V1, corpus `cinema`: 67 documents / 79,787 chunks / 1,968 enrichments) — orchestrator/orchestrator/api/ui.py:376-378 [DERIVED]
- `chat_events` is the single chat authority; `chat_stream` and `run_chat` are transports — runtime changes must preserve frame parity and the fail-closed scope resolver — orchestrator/orchestrator/api/ui.py:24-31, 4978-4983, 5005-5063 [DERIVED]
- `_default_synthesizer` must stay in lockstep with the dropdown default (frontend takes `synths[0]`) — orchestrator/orchestrator/api/ui.py:57-59, 84-87 [DERIVED]
- `_mint_enrichment` shares the AUTO-ENRICH promotion mint path (`mint_parent_enrichment`); changing its run-selection order changes both surfaces — orchestrator/orchestrator/api/ui.py:280-293 [DERIVED]

## VERIFY
```verify
grep -Fq 'POLYMATH_DEFAULT_SYNTHESIZER' orchestrator/orchestrator/api/ui.py
grep -Fq 'http://127.0.0.1:11434' orchestrator/orchestrator/api/ui.py
grep -Fq 'name must be 120 characters or fewer' orchestrator/orchestrator/api/ui.py
grep -Fq 'section_retrieval_summary' orchestrator/orchestrator/api/ui.py
grep -Eq 'def (corpora|rename_corpus|set_query_enabled|chat_events|chat_stream|run_chat)' orchestrator/orchestrator/api/ui.py
test "$(grep -c -F 'QUERY_SCOPE_UNKNOWN' orchestrator/orchestrator/api/ui.py)" -ge 3
test "$(grep -c -F 'gemma4:31b-cloud' orchestrator/orchestrator/api/ui.py)" -ge 3
```
