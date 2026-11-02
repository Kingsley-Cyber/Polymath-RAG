# unit: shared/polymath_shared/product_search/_small-modules
anchor: shared/polymath_shared/product_search/__init__.py:1-12

## purpose
Package facade for product search (product-search-v1): intent detection, product hypotheses, and the CJ/Alibaba service turn driven by the chat runtime — shared/polymath_shared/product_search/__init__.py:1-7 [DERIVED].
`routing.py` adds product-library-routing-v1: a product turn whose resolved scope holds several libraries is routed to the best one before retrieval, instead of the runtime's 422 `mode_requires_single_corpus` — shared/polymath_shared/product_search/routing.py:1-12 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
| CONTRACT (routing) | constant | `"product-library-routing-v1"` | routing.py:18 | unit importers (below) |
| aggregate | def | `(points: Iterable[Any], candidates: list[str]) -> tuple[dict[str, float], int]` | routing.py:25-40 | route_library (internal) |
| query_profiles | def | `(client, collection: str, query_vec, candidates: list[str], *, role_scope=None, limit: int = TOP_DOCS) -> list` | routing.py:43-58 | route_library (internal) |
| make_client | def | `() -> tuple[Any, str]` | routing.py:61-68 | default client_factory |
| ready_counts | def | `(candidates: list[str]) -> dict[str, dict[str, int]]` | routing.py:71-80 | default counts |
| _ready_score | def | `(row: Mapping[str, int] | None) -> int` | routing.py:83-86 | internal |
| route_library | def | `(message: str, candidates: Iterable[str], *, embed=None, client=None, collection=None, client_factory=None, counts=None, role_scope=None) -> dict[str, Any]` | routing.py:89-136 | unit importers (below) |
| INTENT_CONTRACT, ProductIntent, detect, CONTRACT, ProductTurn | re-export | from `intent` / `service` (values not in this material) | __init__.py:8-10 | — |

Unit imported by: orchestrator/orchestrator/api/product.py, orchestrator/orchestrator/api/product_report.py, orchestrator/orchestrator/api/ui.py, shared/polymath_shared/product_search/service.py — FACTS.importers [DERIVED].

## contracts

### route_library — routing.py:89-136
- in: `message: str`, `candidates: Iterable[str]`; keyword-only `embed`, `client`, `collection`, `client_factory`, `counts`, `role_scope`, all default `None` — routing.py:89-91 [DERIVED]
- pre: candidates deduped in order via `dict.fromkeys(str(c) ...)`, falsy entries dropped — routing.py:93 [DERIVED]
- out: receipt `{contract, candidates, chosen, runner_up, scores, method, notes}` plus `documents_read` (method `profile_rrf`) or `counts` (method `most_query_ready_documents`) — routing.py:94-95, 122, 132 [DERIVED]
- post: `method` is one of `METHODS = ("single", "profile_rrf", "most_query_ready_documents", "first_candidate")`; `chosen`/`runner_up` are members of `candidates` — routing.py:22, 96-97, 121-122, 131-132, 134-135 [DERIVED]

### aggregate — routing.py:25-40
- in: `points` (Qdrant points, attribute- or Mapping-style payload), `candidates` — routing.py:31-32 [DERIVED]
- out: `({library: score}, documents read)`; a library scores its best `PER_CORPUS` docs, each doc counted once at its best rank; libraries without a document are absent — routing.py:26-27, 40 [DERIVED]
- post: score = `round(sum(v), 6)` of terms `1.0 / (RRF_K + rank)` — routing.py:39-40 [DERIVED]

## effect surface
- Postgres read: `corpora`, `documents`, `runs` (correlated COUNT subqueries, `status = 'query_ready'`) — routing.py:76-79 [DERIVED]; tables written: none (FACTS `tables_written: []`)
- Qdrant: `client.query_points` over profile collection `polymath_document_profiles_<active embedding contract>`, prefetch per `ANSWER_SURFACES` with `FusionQuery(fusion=qm.Fusion.RRF)`, payload filter on `corpus_id` + `must_not` scope `SCOPE_SECTION`, plus `role_scope` apply — routing.py:7, 51-57 [DERIVED]
- Client construction: `QdrantClient(url=get_settings().stores.qdrant_url, timeout=10)`; collection from `active_contract().contract_id` — routing.py:68 [DERIVED]
- Callable side effects: `embed([message])` invoked — routing.py:108 [DERIVED]

## invariants
INVARIANT: TOP_DOCS = 30 documents read from the one profile query — routing.py:19, 43 [DERIVED]
  fails-if: profile query returns more/fewer candidate docs than the receipt's `documents_read` assumes.
INVARIANT: PER_CORPUS = 3 docs scored per library — routing.py:20, 38 [DERIVED]
  fails-if: a library's score includes a 4th document term.
INVARIANT: score term = 1.0 / (60 + rank), RRF_K = 60 — routing.py:21, 39 [DERIVED]
  fails-if: score values no longer comparable across runs/expectations.
INVARIANT: each doc_id counted at most once (`seen` set) — routing.py:34-36 [DERIVED]
  fails-if: duplicate points for one document inflate that library's score.
INVARIANT: fallback order profile_rrf → most_query_ready_documents → first_candidate — routing.py:120-136 [DERIVED]
  fails-if: a no-profile library wins over one with matching profiles.
INVARIANT: `_ready_score` = `documents` iff `query_ready_runs > 0`, else 0 — routing.py:83-86 [DERIVED]
  fails-if: unindexed libraries outrank query-ready ones in the fallback.
INVARIANT: `len(cands) <= 1` → return with `method: "single"`, no embed/Qdrant/DB calls — routing.py:96-97 [DERIVED]
  fails-if: single-library turns issue network calls or change method.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: Qdrant query_points routing.py:108, embed call routing.py:108; db: Postgres aggregates routing.py:126; exception-dependent fallback selection routing.py:112, 127). `aggregate` alone is DETERMINISTIC given points — routing.py:25-40 [INFERRED: pure loop over inputs].
idempotency: SAFE — read-only: no tables written (FACTS), Qdrant used only via `query_points` routing.py:56-57.

## failure behaviour
- Profile query: any `Exception` → note `"the profile query failed (<Type>: <msg>)"`, degrade to readiness fallback — routing.py:112-113 [DERIVED]
- Readiness count: any `Exception` → note `"the readiness count failed (...)"`, degrade to `first_candidate` — routing.py:127-128 [DERIVED]
- `client.close()`: `Exception` SWALLOWED with `pass` (only when the client was self-made) — routing.py:115-119 [DERIVED]
- No error codes raised on those paths; failures surface only through the `notes` list of an otherwise valid receipt — routing.py:94-95 [DERIVED]

## dumb-code flags
- Bare literal `6` in `round(sum(v), 6)` — routing.py:40 [DERIVED]
- Duplicated truncation literal `[:120]` at routing.py:113 and routing.py:128 [DERIVED]
- Duplicated sort expression `sorted(cands, key=lambda c: (-x, cands.index(c)))` at routing.py:121 and routing.py:131; `cands.index(c)` in the key is O(n²) — [INFERRED: index() per comparison]
- `first_candidate` actually takes `sorted(cands)[0]` (lexicographic first), note text says "the first by id" — routing.py:134-136 [DERIVED]
- `METHODS` lists `"single"` but it only ever appears as the default in the initial `out` dict, never assigned in the multi-candidate path — routing.py:22, 94, 97 [DERIVED]
- Initial `chosen: cands[0]` is dead on every multi-candidate return path; empty candidates yield `chosen: None` — routing.py:94-97 [DERIVED]
- Lazy imports inside `query_profiles` and `make_client` bodies — routing.py:46-50, 63-67 [DERIVED]

## refactor notes
- Receipt keys vary by `method` (`documents_read` vs `counts`); all four unit importers (orchestrator api product.py, product_report.py, ui.py; service.py) consume these receipts — FACTS.importers [DERIVED]
- Injected seams `embed`, `client_factory`, `counts`, `client`, `collection`, `role_scope` are keyword-only; renaming breaks keyword callers — routing.py:89-91 [DERIVED]
- Fallback chain order and the `METHODS` tuple are contractual per the module docstring — routing.py:9-11, 22 [DERIVED]
- The Qdrant filter depends on profile-collection payload keys `corpus_id`, `doc_id`, `scope`; renaming those keys breaks the filter and the aggregation — routing.py:32-33, 51-52, 57 [DERIVED]

## VERIFY
```verify
grep -Fq 'product-library-routing-v1' shared/polymath_shared/product_search/routing.py
grep -Fq 'TOP_DOCS = 30' shared/polymath_shared/product_search/routing.py
grep -Fq 'PER_CORPUS = 3' shared/polymath_shared/product_search/routing.py
grep -Fq 'RRF_K = 60' shared/polymath_shared/product_search/routing.py
test "$(grep -c -F 'except Exception' shared/polymath_shared/product_search/routing.py)" -ge 3
! grep -Fq 'INSERT INTO' shared/polymath_shared/product_search/routing.py
grep -Fq 'nothing ranked the candidate libraries: the first by id was taken' shared/polymath_shared/product_search/routing.py
```
