# unit: orchestrator/orchestrator/api/product.py
anchor: orchestrator/orchestrator/api/product.py:1-183

## purpose
POST `/product/search` (contract `product-search-v1`): product search over ANY corpus for agent callers (MCP servers on this host, or relayed web requests). Without `hypotheses`: ONE chat-runtime turn (`ui.run_chat`) in forced product mode with the default LLM synthesizer. With `hypotheses`: only the caller's CJ / Alibaba lookups — no retrieval, no model. One query receipt per call, kind `product`. — orchestrator/orchestrator/api/product.py:1-17 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | APIRouter | `router = APIRouter()` | orchestrator/orchestrator/api/product.py:31 | module importers: orchestrator/orchestrator/api/product_report.py, orchestrator/orchestrator/main.py (FACTS.importers) |
| `refuse_rebinding` | def | (request: Request, what: str = "product search") -> None | orchestrator/orchestrator/api/product.py:36-47 | called at orchestrator/orchestrator/api/product.py:145 |
| `ProductHypothesisIn` | class (BaseModel) | title: str; search_terms: list[str] = []; problem: str \| None = None; audience: str \| None = None | orchestrator/orchestrator/api/product.py:50-54 | nested in `ProductSearchRequest.hypotheses` |
| `ProductSearchRequest` | class (BaseModel) | message: str; corpus_id: str \| None = None; corpus_ids: list[str] \| None = None; geography: str \| None = None; model: str \| None = None; hypotheses: list[ProductHypothesisIn] \| None = None; limit_per_hypothesis: int \| None = None | orchestrator/orchestrator/api/product.py:57-64 | request body of `product_search` |
| `product_search` | async def, POST /product/search | (req: ProductSearchRequest, request: Request) -> dict | orchestrator/orchestrator/api/product.py:141-182 | FastAPI route registration :141 |
| `_options` | def (private) | (req) -> dict[str, Any] (`geography`, `limit_per_hypothesis`) | orchestrator/orchestrator/api/product.py:67-68 | :105, :120 |
| `_named` | def (private) | (req) -> bool | orchestrator/orchestrator/api/product.py:71-72 | :84, :119 |
| `_scope_kind` | def (private) | (req) -> str | orchestrator/orchestrator/api/product.py:75-76 | :169, :179 |
| `_resolve_corpora` | def (private) | (req) -> list[str] | orchestrator/orchestrator/api/product.py:79-86 | :95 |
| `_with_agent_hypotheses` | def (private) | (req, message: str, principal: str \| None) -> tuple[dict[str, Any], dict] | orchestrator/orchestrator/api/product.py:89-111 | :165 |
| `_forced_turn` | def (private) | (req, message: str, receipt, *, route: str = ROUTE) -> dict[str, Any] | orchestrator/orchestrator/api/product.py:114-138 | :173 |

## contracts

**product_search — POST /product/search** — orchestrator/orchestrator/api/product.py:141-182
- in: `ProductSearchRequest` body (:57-64) plus `Request`.
- pre: `refuse_rebinding(request)` runs before anything — "no receipt, no lookup, no model for a re-bound page" (:145).
- pre: message whitespace-normalized: `" ".join(str(req.message or "").split())` (:146).
- pre: empty message → 422 `{"error_code": "message_required", "message": "message is the user's product request"}` (:156-157).
- pre: hypotheses supplied AND every title blank → 422 `bad_hypotheses` (:158-160).
- post: returns dict with keys `contract, route, answer, verdict, model, product_research, evidence, retrieval, phases, kind` — forced path adds `latency_ms`, `runtime` (:130-138); agent path adds `source: "agent_hypotheses"` and sets `model: None` (:109-110).
- post: exactly one query receipt, kind `product`, meta.route `product/search`, meta.product_search = "counts and statuses only" (:16-17, :152, :167-170, :178-181).
- execution: principal captured on the event loop (:148), re-established in the worker thread via `principal_context.acting_as(principal)` (:163), run under `run_in_threadpool` (:174).

**refuse_rebinding** — orchestrator/orchestrator/api/product.py:36-47
- in: request, `what` defaulting to `"product search"`.
- post: delegates to `refuse_unless_mcp_or_web(request, what=what, tools="tools")` (:43-44); on HTTPException re-raises same status with detail `{"error_code": detail.get("code"), **detail}` (:45-47).
- failure modes (docstring): 403 `NON_LOOPBACK_HOST`, 403 `PROXIED_CALLER` (:40-41).

**_with_agent_hypotheses** — orchestrator/orchestrator/api/product.py:89-111
- pre: scope resolution errors re-raise when a corpus was named or the code is not `QUERY_SCOPE_EMPTY` / `QUERY_SCOPE_REQUIRED` (:96-99); otherwise `corpora = []` and a note is appended to `block["limitations"]` (:100-104, :107-108).
- out: response tuple plus receipt meta `{"verdict", "product_search", "route": ROUTE}` (:109-111).

**_forced_turn** — orchestrator/orchestrator/api/product.py:114-138
- in: req, message, receipt, `route` defaulting to `ROUTE`.
- builds `StreamChatRequest(message, corpus_id, corpus_ids, all_authorized=not _named(req), mode="HYBRID", synthesizer=req.model or None, product=True, product_options=_options(req))` (:119-120); runs `run_chat(sreq, route=route, receipt=receipt)` (:122) — its typed errors "pass through" (:121).
- out: evidence via `compact_evidence(retrieval.get("legend") or [], text_of, previews)` (:127); retrieval block corpus_ids fallback `(research or {}).get("corpus_ids") or list(req.corpus_ids or ([req.corpus_id] if req.corpus_id else []))` (:131-136).

## effect surface
- Postgres: no tables read/written directly (FACTS `tables_read: []`, `tables_written: []`); `tx()` connections opened in `_resolve_corpora` (:85-86) and passed to `record_query_receipt` (:152, :167, :178) — writes happen inside those callees. [DERIVED]
- Network (downstream of this file): CJ Dropshipping searched per hypothesis, Alibaba handed to the user's local Agent Reach (:8-9), model synthesis inside `run_chat` (:122); routes "spend the owner's CJ / eBay / model accounts" (:37). [DERIVED]
- Clocks: `time.perf_counter` (:166, :180).
- Threads: `run_in_threadpool` (:174).
- Qdrant collections / files / subprocesses / env flags: none in this file.

## invariants
INVARIANT: ROUTE value `"product/search"` (:32) == registered route path `"/product/search"` (:141) — [DERIVED]
  fails-if: receipt meta.route (:111) and response `route` (:109, :130) name an endpoint that no longer exists.
INVARIANT: query receipts per call == 1 — success paths record then append to `receipted` (:152, :167-171); failure path records only `if not receipted` (:176-181) — [DERIVED]
  fails-if: duplicate or missing receipts for kind `product`.
INVARIANT: `_named(req)` == False ⟹ `all_authorized=True` in both the scope probe (:84) and the StreamChatRequest (:119) — [DERIVED]
  fails-if: the two request paths resolve different corpora for the same unnamed request.
INVARIANT: agent-hypotheses response has `model=None, evidence=[], retrieval=None, phases=[]` (:109-110) — [DERIVED]
  fails-if: an agent parsing the forced-turn shape hits missing keys.
INVARIANT: `_scope_kind` output ∈ {"corpus", "corpora", "all_authorized"} (:76) — [DERIVED]
  fails-if: receipt `scope_kind` becomes an unparseable value.
INVARIANT: 422 `bad_hypotheses` fires only when EVERY hypothesis has a blank title — `not any(h.title.strip() for h in req.hypotheses)` (:158) — [DERIVED]
  fails-if: a request mixing one titled with several untitled hypotheses proceeds into CJ lookups with title-less entries.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.perf_counter` :166, :180; supplier/model network via `turn.finish_agent` :106 and `run_chat` :122; db via `tx` :85)
idempotency: UNSAFE — every call writes a query receipt (:152, :167, :178) and spends owner supplier/model accounts per the docstring (:37)

## failure behaviour
- Broad `except Exception` (:175-182, FACTS fallbacks): records one error receipt — `error=f"{type(exc).__name__}: {detail if detail is not None else exc}"`, wall_ms from perf_counter — only when nothing was receipted yet, then re-raises unchanged (`# noqa: BLE001`). Nothing swallowed.
- Error codes raised/reshaped here: 403 `NON_LOOPBACK_HOST`, 403 `PROXIED_CALLER` (raised inside `refuse_unless_mcp_or_web`, detail reshaped so `error_code` sits beside `code`) (:40-41, :46-47); 422 `message_required` (:157); 422 `bad_hypotheses` (:159-160).
- `QUERY_SCOPE_EMPTY` / `QUERY_SCOPE_REQUIRED`: re-raised when corpora were named; otherwise degraded to `corpora = []` plus a limitations note naming `list_corpora` (:96-104).

## dumb-code flags
- Literal `"agent_hypotheses"` duplicated as receipt marker (:171) and response `source` value (:110).
- Three-way corpus_ids fallback at :136 re-implements the `_named`/`_scope_kind` logic (:71-76).
- `ProductHypothesisIn.problem` and `.audience` accepted (:53-54) but never read in this file — the whole model is dumped at :106.
- `_with_agent_hypotheses` hardcodes `"route": ROUTE` (:111) while `_forced_turn` takes `route` as a parameter (:114) — inconsistent generality. [INFERRED: the parameter exists so a caller can pass a different route]
- Docstring promises evidence `text <= 400 chars` (:12-13) but the truncation lives in imported `compact_evidence` (:118), not here.
- `what: str = "product search"` default (:36); the only in-file call site (:145) never overrides it.

## refactor notes
- Importers orchestrator/orchestrator/api/product_report.py and orchestrator/orchestrator/main.py (FACTS.importers) depend on `router` (:31), `ROUTE` (:32), `KIND` (:33) — renaming any of them breaks both.
- `_forced_turn`'s `route` keyword (:114) is the seam another route (e.g. product_report) plausibly reuses; changing its signature or response keys (:130-138) ripples. [INFERRED]
- The response key set (:109-110, :130-138, documented :12-13) is versioned as `product-search-v1` via `CONTRACT` (:87, :118) — key changes are contract breaks for agent callers.
- KIND `"product"` is persisted in every receipt (:152, :167, :178) — changing it forks receipt history.
- `refuse_rebinding`'s detail shape (`error_code` beside the upstream `code`, :46-47) is documented as caller-facing (:40-41); reshaping it breaks error parsing.

## VERIFY
```verify
grep -Fq 'ROUTE = "product/search"' orchestrator/orchestrator/api/product.py
grep -Fq 'KIND = "product"' orchestrator/orchestrator/api/product.py
grep -Fq '@router.post("/product/search")' orchestrator/orchestrator/api/product.py
grep -Fq 'message_required' orchestrator/orchestrator/api/product.py
grep -Fq 'bad_hypotheses' orchestrator/orchestrator/api/product.py
grep -Fq 'QUERY_SCOPE_EMPTY' orchestrator/orchestrator/api/product.py
test "$(grep -c -F 'time.perf_counter' orchestrator/orchestrator/api/product.py)" -ge 2
```
