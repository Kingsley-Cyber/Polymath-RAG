# unit: orchestrator/orchestrator/api/ui.py
anchor: orchestrator/orchestrator/api/ui.py:1-4846

## purpose
UI support layer (POLYMATH-UI-V1): the thin HTTP endpoints the web chat adds on top of the existing query product — corpus picker, file-manager listing, spool-streaming upload, synthesizer registry, and the CHAT-RUNTIME-V1 chat turn emitted as phase/token/answer frames so the UI can show what the engine is doing (orchestrator/orchestrator/api/ui.py:1-31) [DERIVED]. `chat_events` is the single authority for a chat turn; `/chat/stream` streams its frames, `/chat` (and MCP `ask`) drains them into one JSON answer (orchestrator/orchestrator/api/ui.py:24-31) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| GET /corpora | route | corpora(all: bool = False) -> dict | ui.py:142 | web chat corpus picker (ui.py:4) |
| PATCH /corpora/{corpus_id} | route | rename_corpus(corpus_id, req) -> dict | ui.py:181 | — |
| PATCH /corpora/{corpus_id}/query_enabled | route | set_query_enabled(corpus_id, req) -> dict | ui.py:213 | — |
| POST /corpora/{corpus_id}/enrich | route | enrich_corpus(corpus_id) -> dict | ui.py:249 | — |
| POST /documents/{doc_id}/enrich | route | enrich_document(doc_id) -> dict | ui.py:257 | — |
| GET /documents/{doc_id}/sections | route | document_sections(doc_id) -> dict | ui.py:272 | — |
| GET /documents | route | documents(corpus_id) -> dict | ui.py:320 | file manager (ui.py:5) |
| GET /documents/{doc_id}/status | route | document_status_view(doc_id) -> dict | ui.py:397 | — |
| POST /upload | route | upload(corpus_id, file, allow_near_duplicate) -> dict | ui.py:467 | spool intake (ui.py:6-10) |
| GET /synthesizers | route | synthesizers() -> dict | ui.py:882 | frontend App.tsx takes synths[0] (ui.py:57-58) |
| ui_pulse | route | ui_pulse() -> dict | ui.py:865 | frontend pings it (ui.py:865 doc) |
| delete_document | route | delete_document(doc_id, confirm) -> dict | ui.py:622 | — |
| delete_corpus | route | delete_corpus(corpus_id, confirm) -> dict | ui.py:1068 | — |
| chat_events | def | chat_events(req, route, receipt) -> frames | ui.py:3830-4756 | chat_stream, run_chat (ui.py:24-27) |
| chat_stream | route | chat_stream(req) -> SSE frames | ui.py:4760 | POST /chat/stream (ui.py:15) |
| run_chat | def | run_chat(req, route, receipt) -> JSON answer | ui.py:4787 | /chat and MCP ask (ui.py:26) |
| RenameCorpusRequest / QueryEnableRequest / ProviderUpsert / LlmTest / HistoryTurn / CarriedChunk / StreamChatRequest / GeneratedPage | class | pydantic request models | ui.py:176, 208, 906, 963, 1271, 1276, 1284, 814 | chat/upload/provider endpoints |

## contracts

**corpora(all=False)** — in: optional `all` flag. Reads `corpora` with pre-aggregated `documents` and `runs` subqueries (never a direct triple join; measured 60s+ on 12k runs) (ui.py:144-162). Out: `{"corpora": [{corpus_id, purpose, query_enabled, documents, query_ready, name}]}` filtered by `(all or documents > 0 or purpose == "production") and can_see(corpus_id)` (ui.py:168-173). Pre: `all=true` required for the corpus manager to see empty non-production rows (ui.py:163-167) [DERIVED].

**rename_corpus(corpus_id, req)** — in: `name: str`. Pre: stripped name non-empty and ≤ 120 chars, else 422 `invalid_name` (ui.py:186-194). Post: only `name` + `updated_at` written; `corpus_id` never changes (ui.py:182-185, 197-199). 404 `QUERY_SCOPE_UNKNOWN` when the corpus is absent (ui.py:201-204).

**set_query_enabled(corpus_id, req)** — in: `query_enabled: bool`. Flips only `query_enabled`, never `purpose`; new uploads default to `purpose='probe'`, `query_enabled=false` (ui.py:214-218, 221-223). 404 `QUERY_SCOPE_UNKNOWN` if missing (ui.py:226-228).

**enrich_corpus / enrich_document** — out: `{"status": "queued", **mint}` (ui.py:253, 268). Shared mint via `polymath_shared.latent.trigger.mint_parent_enrichment` on the corpus's latest run, preferring `status='query_ready'` (ui.py:232-245). Errors: 404 `no_run_for_corpus` (ui.py:241-243), 404 `unknown_document` (ui.py:264-266).

**document_sections(doc_id)** — access-gated by `require_document` (ui.py:279). Reads `retrieval_summaries` rows with `kind = 'section_retrieval_summary' AND active`, joined to parent chunks for `heading_path` (ui.py:280-292). Title chain: heading_path last segment → summary first sentence[:80] → `pid[:16]` (ui.py:305-306). Summary capped at 400 chars, keywords at 8 (ui.py:311-312).

**documents(corpus_id)** — access-gated by `require_corpus` (ui.py:321). Per-document counts as correlated subqueries (children/parents/enriched/enrich_failed/map_active), not joins — measured 80 s → 25 ms on corpus `cinema` (67 docs / 79,787 chunks / 1,968 enrichments) (ui.py:328-360). Runs list capped at 25 with last error from `receipts` or `stage_tickets` (ui.py:361-376).

**upload(corpus_id, file, allow_near_duplicate)** — streams bytes to the spool volume in 1 MiB chunks; Postgres never holds the bytes; same `submit_intake` writer path as `/intake` (ui.py:6-10, 467 doc) [DERIVED].

**_default_synthesizer()** — returns the first id of `_PREFERRED_DEFAULTS` that appears in the offered list (`_litellm_models()` + `_ollama_models()`), else `offered[0]`, else the raw first preference; a provider whose key is missing is skipped so an empty synthesizer can never land on a hidden provider (measured failure: `litellm:openai/glm-5-free` with the OpenCode key unset → LiteLLM "Missing credentials") (ui.py:83-92).

**chat_events / chat_stream / run_chat** — same request yields the same compiled plan, retrieval decision, evidence ids, carry admission, executed mode, degraded list and synthesis contract on every route; only the transport differs (ui.py:27-31). Scope stays fail-closed through the shared resolver (ui.py:30-31).

## effect surface

- Postgres read: `corpora` (ui.py:147-160, 323), `documents` (ui.py:261, 335-357), `runs` (ui.py:236-238, 361-376), `chunks` (ui.py:286, 293-295, 339-342), `retrieval_summaries` (ui.py:280-291), `receipts` (ui.py:364-368), `stage_tickets` (ui.py:369-372), `parent_enrichments` (ui.py:343-349), `document_parent_maps` (ui.py:354-355) [DERIVED]
- Postgres write: `UPDATE corpora SET name, updated_at` (ui.py:197-199), `UPDATE corpora SET query_enabled, updated_at` (ui.py:221-223); enrichment mint through `mint_parent_enrichment` (ui.py:244-245); document/corpus cascade deletes in `_delete_document_tx` / `_delete_corpus_tx` (ui.py:634-811, 1093-1266) [DERIVED]
- Qdrant: no direct call in this unit; only referenced as the reason `corpus_id` is immutable (derived collection names) (ui.py:184) [DERIVED]
- Network: `httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)` (ui.py:111); Ollama streaming generation with a plain-stream fallback (ui.py:3529, 3623); LiteLLM streaming for any provider (ui.py:3330) and one bounded non-streaming gap-check call (ui.py:3673); bridge generator tries Ollama then cloud attempts (ui.py:2000)
- Files: spool volume writes in upload (ui.py:6-10, 467); generated HTML persisted by `save_generated` (ui.py:820)
- Env: `POLYMATH_OLLAMA_URL = "http://127.0.0.1:11434"` (ui.py:54-55); `POLYMATH_DEFAULT_SYNTHESIZER = "litellm:anthropic/deepseek-v4-flash-0731,litellm:openai/big-pickle,litellm:openai/mimo-v2.5-free,litellm:openai/nemotron-3.5-lightning-free,ollama:gemma4:31b-cloud"` (ui.py:77-79); `POLYMATH_OLLAMA_MODELS` default `""` (ui.py:101); `POLYMATH_CHAT_BRIDGE_COMPILER` (ui.py:2044 doc); `POLYMATH_CORPUS_EXPLORER` (ui.py:2143 doc); provider keys via `env:NAME` indirection (ui.py:566 doc), e.g. `env:OPENCODE_API_KEY` (ui.py:68)

## invariants

INVARIANT: len(OLLAMA_FREE_CLOUD_MODELS) == 6, matching the comment "the six names below" — ui.py:70, 96-97 [DERIVED]; fails-if: dropdown drifts from the fixed free-tier catalog the owner pinned.
INVARIANT: _default_synthesizer() ∈ offered ids whenever any preference is offered; never a keyless provider — ui.py:88-92 [DERIVED]; fails-if: empty-synthesizer requests hit "Missing credentials" (ui.py:87).
INVARIANT: corpora row visible ⇔ (all or documents > 0 or purpose == "production") and can_see(corpus_id) — ui.py:172 [DERIVED]; fails-if: empty husks become invisible/undeletable (ui.py:163-167).
INVARIANT: rename_corpus writes only (name, updated_at); corpus_id never in any SET — ui.py:197-199 [DERIVED]; fails-if: FK chains and Qdrant collections orphan (ui.py:182-185).
INVARIANT: display name length ≤ 120 — ui.py:191-194 [DERIVED]; fails-if: 422 invalid_name.
INVARIANT: document_sections rows restricted to kind = 'section_retrieval_summary' AND active — ui.py:288 [DERIVED]; fails-if: legacy/retired summaries leak into the tree.
INVARIANT: runs list length ≤ 25 (LIMIT 25) — ui.py:376 [DERIVED]; fails-if: unbounded listing cost per Files request.
INVARIANT: section summary ≤ 400 chars, keywords ≤ 8, title ≤ summary-head[:80] else pid[:16] — ui.py:305-314 [DERIVED]; fails-if: payload bloat breaks the section tree UI.
INVARIANT: identical chat request ⇒ identical plan / evidence ids / executed mode / degraded list across /chat/stream and /chat — ui.py:27-31 [DERIVED]; fails-if: the two transports disagree and MCP answers diverge from the UI.
INVARIANT: Ollama tags probe timeout = 3 s and any failure ⇒ empty set — ui.py:111-114 [DERIVED]; fails-if: a dead daemon stalls the model list.

## determinism & idempotency

determinism: NONDETERMINISTIC (env `POLYMATH_OLLAMA_URL`/`POLYMATH_DEFAULT_SYNTHESIZER`/`POLYMATH_OLLAMA_MODELS` ui.py:54, 77-79, 101; Ollama HTTP probe ui.py:111; LLM streams ui.py:3330, 3529; `now()` in both UPDATEs ui.py:197, 221; facet call runs on its own thread ui.py:2402 doc; `time`/`uuid` imported ui.py:38-39)
idempotency: UNSAFE mixed — rename_corpus/set_query_enabled converge on the same stored value (only `updated_at` moves, ui.py:197-199, 221-223); enrich_* queue new work on every call (`"status": "queued"` ui.py:253, 268); each chat turn writes ONE receipt payload per turn (ui.py:2574 doc), and the delete endpoints are destructive cascades (ui.py:634-811, 1093-1266 docs).

## failure behaviour

- Ollama daemon unreachable: `except Exception: return set()` — swallowed; allowlisted models still list with `available: false` and a `ollama pull` hint (ui.py:106-114, 117-131) [DERIVED]
- Compiler lanes: attempts tried in order, first REAL plan wins; a transport failure or empty answer is not accepted (ui.py:1669-1725 docs) [DERIVED]
- Facet step late/failed: receipted `facets: None`, not an error (ui.py:2439-2447 doc) [DERIVED]
- Ollama model rejecting `think`: fallback stream without `think` (ui.py:3623-3630) [DERIVED]
- Provider rejecting the token bound (e.g. 'max_tokens: 16000 > 8192'): detected by `_bound_rejected` (ui.py:3460-3464 doc) [DERIVED]
- Stage lock timeout during delete: surfaced via `_lock_timeout_or_409` as an HTTP 409 path (ui.py:1003-1008; name + DELETE-LOCK-TIMEOUT-V1 doc) [INFERRED — handler name says 409]
- HTTP errors raised: 422 `invalid_name` (ui.py:188-194); 404 `QUERY_SCOPE_UNKNOWN` (ui.py:202-204, 226-228, 326-327); 404 `no_run_for_corpus` (ui.py:241-243); 404 `unknown_document` (ui.py:264-266); chat-stream errors mapped by `_error_status` (ui.py:4775)

## dumb-code flags

- Comment claims "OpenCode's glm-5-free is the owner's first choice" (ui.py:74-75) but `_PREFERRED_DEFAULTS[0]` is `litellm:anthropic/deepseek-v4-flash-0731` and no `glm-5-free` entry exists in the list (ui.py:77-79) [DERIVED]
- Docstring says _default_synthesizer is "Same rule as the dropdown's default" (ui.py:85), but the function returns the first *preference* found in offered while the dropdown takes `synths[0]` = offered[0] (ui.py:57-58, 88-92) — they diverge whenever offered[0] is not the first offered preference [INFERRED]
- `_PREFERRED_DEFAULT` fallback literal `"ollama:gemma4:31b-cloud"` duplicates the last entry of the default list (ui.py:79-80) [DERIVED]
- The `deterministic-template-v3` stitcher is no longer OFFERED but its execution path is kept (ui.py:62-65) — retained-by-owner-request dead branch for the dropdown [DERIVED]
- Inline magic numbers: 3 s probe timeout (ui.py:111), 120-char name cap (ui.py:191), 400/80/8/16 truncations (ui.py:305-314), LIMIT 25 (ui.py:376) [DERIVED]
- "New chats take the FIRST" rule stated three times in one comment block (ui.py:57-58, 72-73) [DERIVED]
- 404 responses reuse `error_code: "QUERY_SCOPE_UNKNOWN"` for plain missing-corpus cases like rename (ui.py:202-204) — scope-error vocabulary on a not-found condition [DERIVED]

## refactor notes

- `corpus_id` is immutable identity (FK chains, run scoping, derived Qdrant collection names) — any rename-the-id change orphans the stores (ui.py:182-185) [DERIVED]
- `corpora()` must keep the two pre-aggregated LEFT JOIN subqueries; joining documents AND runs directly cross-multiplies (measured 60s+ on 12k runs) (ui.py:144-146) [DERIVED]
- `documents()` must keep correlated per-document subqueries; the LEFT JOIN + DISTINCT form cost 80 s vs 25 ms on identical data (ui.py:328-334) [DERIVED]
- The `(all or docs>0 or purpose=="production")` filter is load-bearing for the corpus manager; removing `all` hides empty husks (ui.py:163-167, 172) [DERIVED]
- FRIENDS-ACCESS-V1 gates (`can_see`, `require_corpus`, `require_document`) sit on every listing/read path — new endpoints must add them (ui.py:52, 172, 279, 321) [DERIVED]
- `chat_events` is the single authority; `chat_stream` (ui.py:4760) and `run_chat` (ui.py:4787) plus MCP `ask` (ui.py:26) all change behavior together [DERIVED]
- `_mint_enrichment` shares the AUTO-ENRICH promotion mint (`latent/trigger.mint_parent_enrichment`) — changing that signature breaks both the buttons and auto promotion (ui.py:232-235) [DERIVED]
- `/synthesizers` ordering is a frontend contract: App.tsx takes `synths[0]` as the study default (ui.py:57-58) [DERIVED]
- `_receipt_payload` emits ONE payload per turn (ui.py:2574 doc) — receipt consumers depend on that cardinality [DERIVED]

## VERIFY

```verify
grep -Fq 'POLYMATH_DEFAULT_SYNTHESIZER' orchestrator/orchestrator/api/ui.py
grep -Fq 'OLLAMA_FREE_CLOUD_MODELS = ("gemma4:31b-cloud", "gpt-oss:120b-cloud", "gpt-oss:20b-cloud"' orchestrator/orchestrator/api/ui.py
grep -Fq 'httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)' orchestrator/orchestrator/api/ui.py
grep -Fq '"error_code": "QUERY_SCOPE_UNKNOWN"' orchestrator/orchestrator/api/ui.py
grep -Fq 'ORDER BY r.created_at DESC LIMIT 25' orchestrator/orchestrator/api/ui.py
! grep -Fq 'UPDATE corpora SET corpus_id' orchestrator/orchestrator/api/ui.py
test "$(grep -c -F 'invalid_name' orchestrator/orchestrator/api/ui.py)" -ge 2
```
