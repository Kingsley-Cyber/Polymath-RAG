# unit: orchestrator/orchestrator/api/evidence.py
anchor: orchestrator/orchestrator/api/evidence.py:1-373

## purpose
POST /evidence endpoint (R3a): runs the same four retrieval lanes as /retrieve plus the graph-expansion lane, then assembles a deterministic EvidenceBundle via `assemble_evidence_bundle`; every claim is traceable to fact/entity IDs, source document, exact span, provenance, epistemics, scope, and lane. — orchestrator/orchestrator/api/evidence.py:1-13 [DERIVED]
Assembles evidence only; final answer prose belongs to R3b (/chat). Missing provenance or unresolvable references fail loudly (502 with an error code), never silently dropped. — orchestrator/orchestrator/api/evidence.py:8-13 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | APIRouter instance | module global | orchestrator/orchestrator/api/evidence.py:59 | orchestrator/orchestrator/api/ui.py, orchestrator/orchestrator/main.py (module importers; specific symbol not shown) |
| `evidence` | async route handler | `evidence(req: EvidenceRequest) -> dict`, route POST /evidence | orchestrator/orchestrator/api/evidence.py:74-75 | HTTP callers via `router` |
| `EvidenceRequest` | pydantic BaseModel | `query: str; corpus_id=None; corpus_ids=None; workspace=None; all_authorized=False; limit=10; mode=None; scope=None` | orchestrator/orchestrator/api/evidence.py:62-71 | request body of POST /evidence |

## contracts

`evidence(req)` — orchestrator/orchestrator/api/evidence.py:75-294
- in: `req.query` stripped; empty → 422 `"query is required"` — orchestrator/orchestrator/api/evidence.py:76-78
- pre: `resolve_http_scope(conn, req)` — :80-81; `_role_scope_or_422(req)` (malformed scope → 422, K1) — :82-83; `validate_mode(req.mode)` — :89; GRAPH and HYBRID require single corpus via `single_corpus_or_422(scope, mode)` — :91, :170
- compute: three arms — GRAPH (v2 `chat_retrieve_mode("GRAPH", ...)` :104 / v1 `graph_retrieve(...)` :123), FAST/HYBRID (`fast_retrieve` multi-corpus F8 :168; HYBRID v2 :181 / v1 `hybrid_fast_retrieve` :185), default fall-through (`run_lanes` :228-234 + `graph_expansion` :236-242 + `apply_rerank` :252-255)
- out: bundle dict from `assemble_evidence_bundle` with `bundle["meta"]["mode"]` set on GRAPH (:162) and FAST/HYBRID (:214), returned through `echo_scope(bundle, req.scope)` (K1b) — :163, :215, :294
- post: every `AssemblyError` → 502 `{"error_code": type(exc).__name__, "message": str(exc)}` — :158-161, :210-213, :285-292

`_section_summaries_from_parent_ids(parent_ids)` — orchestrator/orchestrator/api/evidence.py:44-57
- in: `list[str]`; empty → `[]` (:49-50); out: `[{chunk_id, doc_id, summary}]` with `summary` defaulting to `""` (:57)
- read: `chunks c JOIN documents d` constrained by `chunk_visible_sql("c", "d")` (:52-56); docstring: display lookup over already-selected ids, not new retrieval (:45-48)

`_resolve_fact` :297-314, `_resolve_evidence_rows` :317-334, `_resolve_entity` :337-345, `_resolve_document` :348-356, `_resolve_chunk` :359-373
- in: id str; out: dict or `None` when row missing (:307-308, :343-344, :354-355, :366-367); `_resolve_evidence_rows` returns `list[dict]` (:327-333)
- only `_resolve_chunk` and the section join apply `chunk_visible_sql` (:363-364, :53-54); fact/evidence/entity/document lookups are unfiltered by-id (:300-304, :320-324, :340, :351)

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | `chunks`, `documents`, `entities`, `evidence`, `facts` | FACTS.tables_read; SQL at orchestrator/orchestrator/api/evidence.py:52-56, 300-304, 320-324, 340, 351, 361-365 |
| Postgres write | none | FACTS.tables_written = [] |
| vector search | `_qdrant_search(query, corpus_ids, limit, **scope_kwargs(role_scope))` | orchestrator/orchestrator/api/evidence.py:233 |
| retrieval engines | `fast_retrieve` :168, `hybrid_fast_retrieve` :185, `graph_retrieve` :123, `chat_retrieve_mode("GRAPH")` :104, `chat_retrieve_mode("HYBRID")` :181 | orchestrator/orchestrator/api/evidence.py:104-185 |
| env flag | `retrieve_engine_flag() == "v2"` selects engine branch; flag name/default not visible in this file | orchestrator/orchestrator/api/evidence.py:97, 174 |
| reranker | `apply_rerank(query, result.selected_documents, result.selected_children)`; on failure sets `orchestrator.api.fast._RERANK_DEGRADED` | orchestrator/orchestrator/api/evidence.py:250-257 |
| graph expansion | `graph_expand_or_502(surfaces, corpus_ids, [c["chunk_id"] for c in result.selected_children[:10]])` | orchestrator/orchestrator/api/evidence.py:236-242 |

## invariants
INVARIANT: Postgres tables written == 0 — orchestrator/orchestrator/api/evidence.py:1-373 (FACTS.tables_written = []) [DERIVED]
  fails-if: any write appears; read-only/idempotent claim becomes false.
INVARIANT: FAST/HYBRID graph_facts == `[]` — orchestrator/orchestrator/api/evidence.py:197-199 [DERIVED]
  fails-if: graph facts leak into a FAST/HYBRID bundle, breaking "the graph lane is empty by FAST contract" (:85-86).
INVARIANT: v2 GRAPH child_evidence keys {chunk_id, doc_id, parent_id} (:110-113) != v1 GRAPH keys {chunk_id, doc_id} (:129-133), despite the "SAME ... shape" comment (:92-96) [DERIVED]
  fails-if: consumers assuming uniform `parent_id` break on the v1 branch.
INVARIANT: default-arm `evidence_order` is non-None only if all(`"rerank_score" in c` for selected_children) — orchestrator/orchestrator/api/evidence.py:261-263 [DERIVED]
  fails-if: one child without `rerank_score` silently drops rerank ordering from the bundle.
INVARIANT: `bundle["meta"]["mode"]` set on 2 of 3 arms (GRAPH :162, FAST/HYBRID :214); never set on the default arm (:217-294) [DERIVED]
  fails-if: meta.mode consumers mislabel or KeyError on default-mode bundles.
INVARIANT: `getattr(req, "latent", None)` == None always — `EvidenceRequest` declares no `latent` field (:62-71) [DERIVED]
  fails-if: latent-budget branches (:102-103, :123, :179-180, :185) are unreachable; a latent request flag is silently ignored.
INVARIANT: `_RERANK_DEGRADED` payload length <= 300 (`str(exc)[:300]`) — orchestrator/orchestrator/api/evidence.py:257 [DERIVED]
  fails-if: longer degradation diagnostics are truncated.

## determinism & idempotency
determinism: NONDETERMINISTIC (db reads via `tx()` at :51, :80, :218, :298, :318, :338, :350, :360; vector search :233; reranker call :253; engine/graph calls :104, :123, :168, :181, :185, :238; env flag `retrieve_engine_flag()` :97, :174) [DERIVED]
idempotency: SAFE — zero table writes (FACTS.tables_written = []); one shared-state write: `_RERANK_DEGRADED.set(str(exc)[:300])` on rerank degradation (:256-257) [DERIVED]

## failure behaviour
- `AssemblyError` → 502 with `error_code` = exception class name and `message` = str(exc); never swallowed — orchestrator/orchestrator/api/evidence.py:158-161, 210-213, 285-292 [DERIVED]
- `RerankUnavailable` → swallowed; degrades to fusion order (`selected_children = result.selected_children`), reason recorded in `_RERANK_DEGRADED`; caller still gets a bundle (NEVER-ERROR-ON-A-COLD-MODEL) — orchestrator/orchestrator/api/evidence.py:244-258 [DERIVED]
- 422 paths: empty query :77-78; malformed role scope via `_role_scope_or_422` :83; multi-corpus GRAPH/HYBRID via `single_corpus_or_422` :91, :170 [DERIVED]
- graph expansion failure surfaces as 502 per the helper name `graph_expand_or_502` — orchestrator/orchestrator/api/evidence.py:238-241 [INFERRED: behaviour lives in .retrieve, name only]
- `_resolve_*` return `None` for missing rows (:307, :343, :354, :366); docstring says unresolvable references fail loudly (:12-13) — the raise itself happens inside `assemble_evidence_bundle` [INFERRED]

## dumb-code flags
- `getattr(req, 'latent', None)` at :102, :123, :179, :185 but `EvidenceRequest` (62-71) has no `latent` field → dead latent-budget branches; flag silently ignored — orchestrator/orchestrator/api/evidence.py:102-185 [DERIVED]
- `limit: int = 10` (:68) is never read in the handler; the only `limit` in the body is the lambda parameter `lambda limit:` (:232); may be consumed inside `resolve_http_scope` (not visible here) — orchestrator/orchestrator/api/evidence.py:68, 232 [DERIVED absence; INFERRED consumer]
- HYBRID shares FAST's `graph_facts = []` (:197-199) although the empty-graph-lane comment cites only the FAST contract (:85-86) [DERIVED]
- Default arm leaves `meta.mode` unset (:217-294 vs :162, :214) [DERIVED]
- Magic numbers: `[:10]` graph seed cap :240; `[:300]` message truncation :257; `limit = 10` :68 [DERIVED]
- Triple-duplicated wiring: resolve-* lambdas :150-154, :202-206, :269-273; AssemblyError→502 block :158-161, :210-213, :285-292 [DERIVED]
- Function-local `from orchestrator.api.retrieve import _role_scope_or_422` (:82) although `.retrieve` is already imported at :30-40 [DERIVED]
- Visibility asymmetry: only chunk reads apply `chunk_visible_sql` (:53-54, :363-364); facts/evidence/entities/documents reads unfiltered (:300-351) [DERIVED]

## refactor notes
- Importers `orchestrator/orchestrator/api/ui.py` and `orchestrator/orchestrator/main.py` (FACTS.importers) — renaming `router`, `evidence`, `EvidenceRequest`, or the POST /evidence path breaks both [DERIVED]
- Nine private symbols of `.retrieve` are hard imports: `_entity_surfaces`, `_fetch_children_rows`, `_fetch_parents`, `_fetch_profiles`, `_qdrant_search`, `graph_expand_or_502`, `resolve_http_scope`, `retrieve_engine_flag`, `single_corpus_or_422` (:30-40), plus `_role_scope_or_422` (:82) — renaming any of them breaks this file [DERIVED]
- Writes into `orchestrator.api.fast._RERANK_DEGRADED` (:250, :257) — changing that global's protocol breaks degradation reporting [DERIVED]
- Output contract varies per arm: `meta.mode` presence (:162, :214 vs none), `evidence_order` source (:149, :201, :261-267), child_evidence keys (:110-113 vs :129-133 vs :186-189) — bundle consumers depend on these [DERIVED]
- Engine switch `retrieve_engine_flag() == "v2"` (:97, :174): removing either engine must delete its branch pair while preserving the shared graph_facts/child_evidence/document_summaries/section_summaries shape (:92-96) [DERIVED]

## VERIFY
```verify
grep -Fq '@router.post("/evidence")' orchestrator/orchestrator/api/evidence.py
grep -Fq 'limit: int = 10' orchestrator/orchestrator/api/evidence.py
grep -Fq 'if retrieve_engine_flag() == "v2":' orchestrator/orchestrator/api/evidence.py
grep -Eq 'bundle\["meta"\]\["mode"\] = ' orchestrator/orchestrator/api/evidence.py
test "$(grep -c -F 'status_code=502' orchestrator/orchestrator/api/evidence.py)" -ge 3
test "$(grep -c -F 'getattr(req,' orchestrator/orchestrator/api/evidence.py)" -ge 4
! grep -Fq 'latent: ' orchestrator/orchestrator/api/evidence.py
grep -Fq 'query is required' orchestrator/orchestrator/api/evidence.py
```
