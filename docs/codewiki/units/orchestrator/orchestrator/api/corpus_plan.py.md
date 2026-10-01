# unit: orchestrator/orchestrator/api/corpus_plan.py
anchor: orchestrator/orchestrator/api/corpus_plan.py:1-188

## purpose
CORPUS-PLAN-V1 endpoint: a consumer sends ONE signal; the module compiles 3–5 deterministic reformulations (seed / tension / communities / invariant / contrast, padded for short signals), runs each through the EXPLORE evidence retrieve, and returns merged rows stamped with the query ids that found them — orchestrator/orchestrator/api/corpus_plan.py:1-9 [DERIVED].
Compiler is a byte-for-byte port of TRAIL OS `python/corpus_queries.py` (same hashing, same ids), parity pinned by `contracts/retrieve/v1/corpus_plan_fixture.json`; no LLM, no state — orchestrator/orchestrator/api/corpus_plan.py:7-9 [DERIVED].
Router mounted from orchestrator/orchestrator/main.py (FACTS.importers) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `stable_id` | def | `(*parts) -> str` | orchestrator/orchestrator/api/corpus_plan.py:23-24 | in-file (`add`, :74) |
| `compile_queries` | def | `(state: dict, policies: dict) -> list[dict]` | orchestrator/orchestrator/api/corpus_plan.py:64-110 | in-file (:113, :119) |
| `corpus_query_compiler` | def | `(state: dict, policies: dict) -> str` | orchestrator/orchestrator/api/corpus_plan.py:113-116 | — |
| `compile_plan` | def | `(signal: str, communities: list \| None = None, min_queries: int = 3, max_queries: int = 5) -> list[dict]` | orchestrator/orchestrator/api/corpus_plan.py:119-122 | `retrieve_plan` (:157) |
| `PlanRequest` | class | pydantic BaseModel | orchestrator/orchestrator/api/corpus_plan.py:128-140 | `retrieve_plan` |
| `retrieve_plan` | def (route) | `async (req: PlanRequest) -> dict` — POST `/retrieve/plan` | orchestrator/orchestrator/api/corpus_plan.py:143-187 | orchestrator/orchestrator/main.py [INFERRED: module importer mounts the router] |

## contracts

**compile_queries(state, policies)** — orchestrator/orchestrator/api/corpus_plan.py:64-110
- in: `state["data"].get("signal")` str (:65); `policies["corpus"]` optional, `pol.get("min_queries", 3)`, `pol.get("max_queries", 5)` (:95-96) [DERIVED]
- out: list of `{"id": stable_id("cq", kind, text), "kind": kind, "query": text, "why": why}` (:74), capped `out[:hi]` (:110); kinds ∈ seed / tension / communities / invariant / contrast / sentence / keywords / behaviour (:78, :81, :85, :90, :94, :101, :105, :108-109) [DERIVED]
- pre: `state["data"]` key must exist — accessed as `state["data"].get(...)` (:65) [INFERRED: missing key raises KeyError]
- post: all `query` texts unique (:72); texts `_trim`ed to ≤220 chars (:71, :59-61) [DERIVED]

**compile_plan(signal, communities, min_queries=3, max_queries=5)** — orchestrator/orchestrator/api/corpus_plan.py:119-122
- in: builds `state = {"data": {"signal": signal or "", "communities": list(communities or [])}}`, `policies = {"corpus": {"min_queries": int(min_queries), "max_queries": int(max_queries)}}` (:120-121) [DERIVED]
- out: delegates to `compile_queries` (:122); `communities` is stored but never read downstream (:65 reads only `signal`) [DERIVED]

**corpus_query_compiler(state, policies) -> str** — orchestrator/orchestrator/api/corpus_plan.py:113-116
- post: writes `state["data"]["corpus_queries"] = qs` (:115) — mutates caller state [DERIVED]
- out: `f"compiled {len(qs)} corpus reformulations: " + ", ".join(...kinds...)` (:116) [DERIVED]

**retrieve_plan(req)** — POST `/retrieve/plan` — orchestrator/orchestrator/api/corpus_plan.py:144-187
- in: `PlanRequest` fields: `signal: str`, `corpus_id: Optional[str]`, `corpus_ids: Optional[list[str]]`, `limit: int = 24`, `explore: bool = True`, `communities: list[str] = []`, `min_queries: int = 3`, `max_queries: int = 5`, `document_ids: Optional[list[str]]`, `scope: Optional[dict]` (:129-140) [DERIVED]
- pre: stripped signal non-empty else 422 `"signal is required"` (:147-149); ≥1 corpus id else 422 `"corpus_id or corpus_ids is required"` (:150-152); `require_corpora(corpus_ids)` (:153-154); `_role_scope_or_422(req)` (:155-156) [DERIVED]
- per query × corpus: `RetrieveRequest(query=q["query"], corpus_id=cid, limit=int(req.limit), mode="EXPLORE" if req.explore else None, evidence=True, document_ids=req.document_ids, scope=req.scope)` (:162-164) [DERIVED]
- post: rows merged by row `"id"`; `query_ids` accumulates plan query ids; `corpus_id=row.get("corpus_id") or cid` first writer wins (:170-179); `per_query` counts `new_rows` per (query, corpus) (:181) [DERIVED]
- out: `{"plan", "plan_contract": "corpus-plan-v1", "evidence_rows", "evidence_contract": "retrieve-evidence-rows-v1", "corpus_ids", "per_query", "errors"}` + optional `"document_ids"` echo (:185-186), wrapped by `echo_scope(out, req.scope)` (:187) [DERIVED]

## effect surface
- Postgres: none read, none written (FACTS tables_read / tables_written empty) [DERIVED]
- Qdrant / vector store: not touched here; retrieval delegated to `orchestrator.api.retrieve._retrieve_impl` (:166) [INFERRED]
- Network: inbound route POST `/retrieve/plan` (:143); no outbound calls in this unit — per-query work is an in-process `await _retrieve_impl(rreq)` (:162-166) [DERIVED]
- Files / subprocess / env flags: none visible in source [DERIVED]
- Cross-module calls at request time: `orchestrator.api.retrieve.{RetrieveRequest, _retrieve_impl, _role_scope_or_422}` (:145, :155), `orchestrator.web_scope.require_corpora` (:153), `polymath_shared.code.scope.echo_scope` (:20, :187) [DERIVED]

## invariants
INVARIANT: len(plan) ≤ max_queries — `out[:hi]` with default hi=5 (:110, :96) [DERIVED]
  fails-if: contract consumers expecting ≤5 reformulations per plan break.
INVARIANT: plan size ≥ min_queries whenever signal yields a ≥3-char seed or ≥1 keyword — padding loop (:97-101) then fallback adds with `minlen=3` (:104-109) [DERIVED]
  fails-if: a short signal would return an empty corpus lane (comment :102-103).
INVARIANT: every emitted query text length ≥ 3 and ≤ 220 — `minlen=3` fallback (:105, :108, :109), `_trim` n=220 (:59-61) [DERIVED]
  fails-if: empty/oversized query strings sent to retrieve.
INVARIANT: all `query` texts in one plan are unique — dedup check `any(q["query"] == text for q in out)` (:72) [DERIVED]
  fails-if: duplicate reformulations waste per-query retrieval budget.
INVARIANT: query id == sha256("cq|" + kind + "|" + text)[:12] — (:23-24, :74); same signal ⇒ same ids (docstring :7-9) [DERIVED]
  fails-if: fixture parity with TRAIL OS `corpus_plan_fixture.json` breaks (:8).
INVARIANT: each evidence row appears once per `id`; `query_ids` append-only — (:172-178) [DERIVED]
  fails-if: consumers counting rows-per-query double count.
INVARIANT: error detail truncated to 200 chars — `str(exc.detail)[:200]` (:168) [DERIVED]

## determinism & idempotency
determinism: compile_queries / compile_plan DETERMINISTIC — pure regex + sha256 + freq sort, no clock/random/db/env (hashing :23-24, split :32, sort `(-kv[1], kv[0])` :56; docstring "No LLM, no state: same signal, same plan" :9) [DERIVED]
determinism: retrieve_plan NONDETERMINISTIC — merged `evidence_rows` depend on the retrieval backend behind `await _retrieve_impl(rreq)` (:166) [INFERRED]
idempotency: SAFE — no table writes (FACTS), merge dict built fresh per request (:159); only mutation is `corpus_query_compiler` writing `state["data"]["corpus_queries"]` on its caller's state (:115) [DERIVED]

## failure behaviour
- 422 `"signal is required"` when stripped signal empty (:148-149) [DERIVED]
- 422 `"corpus_id or corpus_ids is required"` when both corpus fields absent (:151-152) [DERIVED]
- `require_corpora(corpus_ids)` gate (FRIENDS-ACCESS-V1 D5) raises before any retrieval (:153-154); exception type defined in `orchestrator.web_scope`, not visible here [DERIVED]
- `_role_scope_or_422(req)` refuses a malformed scope up front (K1) (:155-156) [DERIVED]
- Per (query, corpus) `HTTPException` from `_retrieve_impl` is swallowed into `errors` (`{"query_id", "corpus_id", "status", "detail"[:200]}`) and the loop continues; caller sees HTTP 200 with a non-empty `errors` array (:166-169, :184) [DERIVED]
- Non-`HTTPException` from `_retrieve_impl` is not caught — propagates and aborts the whole request (:166-169) [DERIVED]

## dumb-code flags
- `communities` is dead: stored into `state["data"]["communities"]` (:120) and declared on `PlanRequest` (:134), but `compile_queries` reads only `"signal"` (:65) — no effect on output [DERIVED]
- Default pair `(3, 5)` duplicated in three places: `pol.get("min_queries", 3)` / `pol.get("max_queries", 5)` (:96), `compile_plan` defaults (:119), `PlanRequest` defaults (:135-136) — must stay in sync [DERIVED]
- `_keywords(text, n=8)` default never used — called with 10 (:92) and 6 (:106) [DERIVED]
- Magic lengths: sentence min 20 (:37), trim 220 (:59), detail 200 (:168), id 12 hex chars (:24) [DERIVED]
- `s.split(":", 1)[-1]` for the `communities` query returns the whole sentence when no colon exists (:85) [DERIVED]
- `mode="EXPLORE" if req.explore else None` — `None` silently falls back to `RetrieveRequest`'s own default mode (:163) [DERIVED]

## refactor notes
- Byte-parity pin: any change to `stable_id` parts order (:23-24, :74), kind names (:78-109), trimming (:59-61), or dedup (:72) breaks parity with TRAIL OS `python/corpus_queries.py` and `contracts/retrieve/v1/corpus_plan_fixture.json` (:7-8) — blast radius spans both repos [DERIVED]
- Response contract keys `"plan_contract": "corpus-plan-v1"`, `"evidence_contract": "retrieve-evidence-rows-v1"`, and the `per_query`/`errors` shapes (:182-184) are consumed fields — renaming breaks clients [DERIVED]
- Depends on private symbols of `orchestrator.api.retrieve` (`_retrieve_impl`, `_role_scope_or_422`, :145/:155) — renaming those ripples here [DERIVED]
- Route path `/retrieve/plan` (:143) is served via orchestrator/orchestrator/main.py (FACTS.importers) — path change requires that file [INFERRED: importer mounts router]
- `corpus_query_compiler` mutates caller state (:115); its callers (not visible here) rely on `state["data"]["corpus_queries"]` being set [DERIVED]

## VERIFY
```verify
grep -Fq 'def stable_id(*parts) -> str:' orchestrator/orchestrator/api/corpus_plan.py
grep -Fq '"plan_contract": "corpus-plan-v1"' orchestrator/orchestrator/api/corpus_plan.py
grep -Fq 'lo, hi = int(pol.get("min_queries", 3)), int(pol.get("max_queries", 5))' orchestrator/orchestrator/api/corpus_plan.py
grep -Fq 'str(exc.detail)[:200]' orchestrator/orchestrator/api/corpus_plan.py
grep -Eq 'add\("(seed|tension|communities|invariant|contrast|sentence|keywords|behaviour)"' orchestrator/orchestrator/api/corpus_plan.py
test "$(grep -c -F 'HTTPException(status_code=422' orchestrator/orchestrator/api/corpus_plan.py)" -ge 2
```
