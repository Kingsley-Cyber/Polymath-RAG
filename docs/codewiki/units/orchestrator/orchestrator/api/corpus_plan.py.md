# unit: orchestrator/orchestrator/api/corpus_plan.py
anchor: orchestrator/orchestrator/api/corpus_plan.py:1-215
## purpose
CORPUS-PLAN-V1 (2026-09-03): a consumer sends ONE signal; this module compiles 3–5 deterministic reformulations (seed / tension / communities / invariant / contrast, padded for short signals), runs each through the EXPLORE evidence view, and returns merged rows stamped with the query ids that found them — orchestrator/orchestrator/api/corpus_plan.py:1-9 [DERIVED].
The compiler is a byte-for-byte port of TRAIL OS `python/corpus_queries.py` (same hashing, same ids); parity is pinned by `contracts/retrieve/v1/corpus_plan_fixture.json` in both repos. No LLM, no state: same signal, same plan — orchestrator/orchestrator/api/corpus_plan.py:6-9 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| stable_id | def | (*parts) -> str | orchestrator/orchestrator/api/corpus_plan.py:24-25 | in-file only (compile_queries:75) |
| compile_queries | def | (state: dict, policies: dict) -> list[dict] | orchestrator/orchestrator/api/corpus_plan.py:65-111 | in-file (corpus_query_compiler:115, compile_plan:122) |
| corpus_query_compiler | def | (state: dict, policies: dict) -> str | orchestrator/orchestrator/api/corpus_plan.py:114-117 | — (module imported by orchestrator/orchestrator/main.py, FACTS.importers) |
| compile_plan | def | (signal: str, communities: list \| None = None, min_queries: int = 3, max_queries: int = 5) -> list[dict] | orchestrator/orchestrator/api/corpus_plan.py:120-123 | in-file (_retrieve_plan_impl:185) |
| PlanRequest | class | pydantic BaseModel: signal, corpus_id=None, corpus_ids=None, limit=24, explore=True, communities=[], min_queries=3, max_queries=5, document_ids=None, scope=None | orchestrator/orchestrator/api/corpus_plan.py:129-141 | retrieve_plan:145 |
| retrieve_plan | route/def | POST /retrieve/plan; async (req: PlanRequest, request: Request = None) -> dict | orchestrator/orchestrator/api/corpus_plan.py:144-169 | router mounted via orchestrator/orchestrator/main.py (FACTS.importers) |
| _retrieve_plan_impl | def | async (req: PlanRequest) -> dict | orchestrator/orchestrator/api/corpus_plan.py:172-215 | in-file (retrieve_plan:149, :158) |

Private text helpers: `_sentences` :36-38, `_section` :41-47, `_keywords` :50-57, `_trim` :60-62; module constants `_STOP` :27-31, `_SENT` :33 — orchestrator/orchestrator/api/corpus_plan.py:27-62 [DERIVED].

## contracts
**compile_queries / compile_plan** (orchestrator/orchestrator/api/corpus_plan.py:65-123)
- in: `state["data"].get("signal")`; `policies["corpus"]["min_queries"]`/`["max_queries"]` (:66, :96-97); compile_plan wraps these from its own args (:121-122) [DERIVED].
- seed section = `_section(signal, "SEED")` or whole signal; latent = `_section(signal, "LATENT INTERPRETATION")` (:67-68); a section ends at a blank line or the next `LATENT INTERPRETATION`/`SEED` marker followed by `(` (:46) [DERIVED].
- out: list of `{"id": stable_id("cq", kind, text), "kind", "query", "why"}` dicts, capped by `return out[:hi]` (:75, :111); kinds emitted: `seed` (:79, :106), `tension` (:82), `communities` (:86), `invariant` (:91), `contrast` (:95, requires `len(kws) >= 4` from `_keywords(seed + " " + latent, 10)`), `sentence` (:102), `keywords` (:109), `behaviour` (:110) [DERIVED].
- pre: none in the compiler — a short/plain signal still gets a plan (seed verbatim, keywords, behaviour probe, `minlen=3`); never an empty corpus lane by design (:103-110) [DERIVED]. The HTTP layer rejects empty signal first (:176-177).
- post: duplicate query text is skipped (`any(q["query"] == text for q in out)`, :73); query id = sha256 hex of `"cq|kind|text"` truncated to 12 chars (:24-25, :75) [DERIVED].

**retrieve_plan / _retrieve_plan_impl** (orchestrator/orchestrator/api/corpus_plan.py:144-215)
- in: PlanRequest fields as listed above (:130-141); corpus list = `req.corpus_ids or ([req.corpus_id] if req.corpus_id else [])` (:153, :178) [DERIVED].
- pre: 422 `"signal is required"` if stripped signal empty (:175-177); 422 `"corpus_id or corpus_ids is required"` if no corpus (:178-180); `require_corpora(corpus_ids)` FRIENDS-ACCESS-V1 D5 (:181-182); `_role_scope_or_422(req)` K1 — malformed scope refused up front (:183-184) [DERIVED].
- per (query, corpus): `RetrieveRequest(query=q["query"], corpus_id=cid, limit=int(req.limit), mode="EXPLORE" if req.explore else None, evidence=True, document_ids=req.document_ids, scope=req.scope)` (:190-192); `document_ids` and `scope` are threaded into every reformulation (:138-141) [DERIVED].
- out: `{"plan", "plan_contract": "corpus-plan-v1", "evidence_rows", "evidence_contract": "retrieve-evidence-rows-v1", "corpus_ids", "per_query", "errors"}` plus echoed `document_ids` when set (:210-214), wrapped by `echo_scope(out, req.scope)` K1b (:215) [DERIVED].
- merge: rows keyed by `row["id"]`; rows without id skipped (:200-202); re-found rows only append the new `query_ids` entry (:203-206); `per_query` records `new_rows` per (query, corpus) (:209) [DERIVED].
- post: exactly one query receipt per HTTP call — kind `retrieve`, `meta.route` `retrieve/plan` (:146-147, :161-163, :167-168); an in-process call (`request is None`) writes none (:148-149) [DERIVED].

## effect surface
- Postgres: no tables named by static analysis (FACTS.tables_read/tables_written = `[]`); DB writes only via `record_query_receipt(tx, ...)` with `tx` from `polymath_shared.db` — orchestrator/orchestrator/api/corpus_plan.py:150-151, :161-163, :167-168 [DERIVED].
- Qdrant / files / subprocess: none in this file — not present in SOURCE [DERIVED].
- Inbound HTTP: `POST /retrieve/plan` (:144); reads header `user-agent` default `""` (:155) [DERIVED].
- Outbound work: in-process `await _retrieve_impl(rreq)` per (query, corpus) pair — orchestrator/orchestrator/api/corpus_plan.py:173, :188-194 [DERIVED].
- Clock: `time.perf_counter` (:162), error-path `wall_ms` only; success path uses `Timer` `t.ms` (:156, :168) [DERIVED].
- Env flags: none read in this file [DERIVED].

## invariants
INVARIANT: len(compile_plan result) ≤ max_queries — enforced by `return out[:hi]` — orchestrator/orchestrator/api/corpus_plan.py:111 [DERIVED]
  fails-if: consumers run more retrieves than budgeted; retrieve calls = len(plan) × len(corpus_ids) (:188-189).
INVARIANT: same signal → same query ids — id = `hashlib.sha256("|".join(...)).hexdigest()[:12]` over `("cq", kind, text)`; "No LLM, no state" — orchestrator/orchestrator/api/corpus_plan.py:9, :24-25, :75 [DERIVED]
  fails-if: fixture parity with TRAIL OS `python/corpus_queries.py` breaks (:7-8).
INVARIANT: duplicate evidence appears once, carrying all matching ids — `if rid in merged: ... append(q["id"])` — orchestrator/orchestrator/api/corpus_plan.py:203-206 [DERIVED]
  fails-if: repeated rows or lost query_ids in `evidence_rows`.
INVARIANT: defaults agree — min_queries 3 / max_queries 5 in `compile_queries` (:97), `compile_plan` (:120), `PlanRequest` (:136-137); route limit default 24, explore default True (:133-134) — orchestrator/orchestrator/api/corpus_plan.py:97-137 [DERIVED]
  fails-if: plan size or row counts change silently for callers relying on defaults.
INVARIANT: one receipt per HTTP call (success or error path), zero for in-process calls — orchestrator/orchestrator/api/corpus_plan.py:146-149, :161-168 [DERIVED]
  fails-if: receipt-based audit/billing drifts from actual traffic.
INVARIANT: every reformulation retrieve carries the same `document_ids` and `scope` as the request — orchestrator/orchestrator/api/corpus_plan.py:190-192 [DERIVED]
  fails-if: retrieval escapes the requested document/knowledge-role scope (DOCUMENT-SCOPED-RETRIEVE-V1, K1).

## determinism & idempotency
determinism: NONDETERMINISTIC at the route (clock `time.perf_counter` orchestrator/orchestrator/api/corpus_plan.py:162; db receipt writes :161, :167; results depend on `_retrieve_impl` corpus state :194) — FACTS.nondeterminism [DERIVED]. The compiler sub-path (:24-123) is pure string/hashing work: DETERMINISTIC — orchestrator/orchestrator/api/corpus_plan.py:9, :65-123 [DERIVED].
idempotency: UNSAFE for the HTTP route — each call writes one query receipt, so retries duplicate receipts — orchestrator/orchestrator/api/corpus_plan.py:146-147, :167-168 [DERIVED]. The compiler functions are SAFE (no state mutation except `corpus_query_compiler` writing `state["data"]["corpus_queries"]` at :116) [DERIVED].

## failure behaviour
- Broad handler `except Exception as exc` (:159, FACTS.fallbacks "handled: assign, expr, raise"): builds `detail = getattr(exc, "detail", None)`, records a receipt with `error=f"{type(exc).__name__}: ..."` and `wall_ms=(time.perf_counter() - t.t0) * 1000.0`, then re-raises unchanged — orchestrator/orchestrator/api/corpus_plan.py:159-164 [DERIVED]. Caller sees the original exception; a receipt row exists either way.
- Per-retrieve `except HTTPException as exc` (:195): swallowed into `errors.append({"query_id", "corpus_id", "status", "detail": str(exc.detail)[:200]})`, `continue` — one failing (query, corpus) pair never aborts the plan — orchestrator/orchestrator/api/corpus_plan.py:195-197 [DERIVED]. Final response is still returned with `errors` included (:210, :212).
- Raised here: `HTTPException(status_code=422, detail="signal is required")` (:177); `HTTPException(status_code=422, detail="corpus_id or corpus_ids is required")` (:180) — orchestrator/orchestrator/api/corpus_plan.py:177, :180 [DERIVED].
- Delegated guards (exceptions raised in their own modules, not visible here): `require_corpora` (:182), `_role_scope_or_422` (:184) — orchestrator/orchestrator/api/corpus_plan.py:181-184 [DERIVED].

## dumb-code flags
- `communities` is accepted (`PlanRequest.communities` :135, stored in state at :121) but `compile_queries` reads only `state["data"]["signal"` — the `communities` key is never read in this file — orchestrator/orchestrator/api/corpus_plan.py:66, :121, :135 [INFERRED: only "signal" is read at :66; no other reader of "communities" exists in SOURCE].
- Two clocks for the same metric: error path `time.perf_counter` (:162) vs success path `Timer` `t.ms` (:168) — orchestrator/orchestrator/api/corpus_plan.py:162, :168 [DERIVED].
- Receipt `question` differs by path: error uses `req.signal or ""` (:161), success uses `req.signal` (:167) — orchestrator/orchestrator/api/corpus_plan.py:161, :167 [DERIVED].
- Magic numbers: sentence filter `> 20` (:38); `_trim` 220 (:60); `add` default `minlen=12` vs fallback `minlen=3` (:71, :106, :109-110); `_keywords` default `n=8` never used in-file (called with 10 and 6) (:50, :93, :107); contrast uses top 6 keywords, behaviour top 4 (:95, :110); `detail[:200]` (:196) — orchestrator/orchestrator/api/corpus_plan.py:38-196 [DERIVED].
- Duplicated defaults: min/max queries literals `3`/`5` appear in three places (:97, :120, :136-137) — orchestrator/orchestrator/api/corpus_plan.py:97-137 [DERIVED].
- Padding then truncation: plan is padded up to `lo` (:98-110) then sliced to `hi` (:111); if a caller passes `min_queries > max_queries` the padding work is discarded — orchestrator/orchestrator/api/corpus_plan.py:98-111 [INFERRED: order of operations is visible; no `lo <= hi` check exists].
- `request: Request = None` with `# type: ignore[assignment]` selects the no-receipt in-process branch by falsy Request (:145, :148) — orchestrator/orchestrator/api/corpus_plan.py:145-149 [DERIVED].

## refactor notes
- Query ids are contractual: `stable_id("cq", kind, text)` with `hexdigest()[:12]` must stay byte-identical; parity is pinned by `contracts/retrieve/v1/corpus_plan_fixture.json` against TRAIL OS — any change to `_trim`, `_sentences`, `_keywords`, `_STOP`, or template strings (`"why do people keep "`, `"how people cope with "`) changes ids — orchestrator/orchestrator/api/corpus_plan.py:7-8, :24-25, :60-110 [DERIVED].
- Response contract keys consumers/receipts depend on: `"corpus-plan-v1"`, `"retrieve-evidence-rows-v1"`, `meta.route` `"retrieve/plan"` — orchestrator/orchestrator/api/corpus_plan.py:166, :210-211 [DERIVED].
- The router is imported by `orchestrator/orchestrator/main.py` (FACTS.importers); moving the path `/retrieve/plan` or the handler name breaks that mount — orchestrator/orchestrator/api/corpus_plan.py:126, :144 [DERIVED].
- Receipt shape (`kind="retrieve"`, `question`, `scope_corpora`, `scope_kind`, `wall_ms`, `out=view`, `client`) is written on both success and error paths — change both together — orchestrator/orchestrator/api/corpus_plan.py:161-168 [DERIVED].
- K1 scope + document scoping are threaded into every reformulation's `RetrieveRequest` and echoed back (:214-215); removing them silently unscopes retrieval — orchestrator/orchestrator/api/corpus_plan.py:138-141, :190-192, :213-215 [DERIVED].

## VERIFY
```verify
grep -Fq 'hexdigest()[:12]' orchestrator/orchestrator/api/corpus_plan.py
grep -Fq 'return out[:hi]' orchestrator/orchestrator/api/corpus_plan.py
grep -Fq '@router.post("/retrieve/plan")' orchestrator/orchestrator/api/corpus_plan.py
grep -Fq 'plan_contract": "corpus-plan-v1' orchestrator/orchestrator/api/corpus_plan.py
grep -Fq 'detail="corpus_id or corpus_ids is required"' orchestrator/orchestrator/api/corpus_plan.py
! grep -Fq 'import random' orchestrator/orchestrator/api/corpus_plan.py
test "$(grep -c -F 'record_query_receipt' orchestrator/orchestrator/api/corpus_plan.py)" -ge 3
```
