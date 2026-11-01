# unit: shared/polymath_shared/acquisition/service.py
anchor: shared/polymath_shared/acquisition/service.py:1-418

## purpose
Policy + shaping layer for RESEARCH ACQUISITION (`research-acquisition-v1`): an owner-only, read-only catalog (`catalog`, `web_search`, `comments`, `listings`) read through a host-browser backend, with per-action query budgeting and a receipt-ready result shape for the harness/TrailSignal downstream. — shared/polymath_shared/acquisition/service.py:1-36 [DERIVED]

Module importers (FACTS): `orchestrator/orchestrator/api/acquisition.py`, `shared/polymath_shared/acquisition/_small-modules`, `cj_api.py`, `opencli.py`, `supplier.py`. — shared/polymath_shared/acquisition/service.py:1 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `acquire` | def | `(*, principal_id, action, operation, target, site=None, search_intent_id=None, limit=None, backend=None) -> dict` | shared/polymath_shared/acquisition/service.py:389-417 | orchestrator/orchestrator/api/acquisition.py [DERIVED] |
| `resolve` | def | `(operation, target, site=None) -> Target` | shared/polymath_shared/acquisition/service.py:145-168 | — |
| `bind` | def | `(action, target, search_intent_id) -> None` | shared/polymath_shared/acquisition/service.py:171-182 | — |
| `take_query` | def | `(action) -> tuple[int, int]` | shared/polymath_shared/acquisition/service.py:190-202 | — |
| `refund_query` | def | `(action) -> int` | shared/polymath_shared/acquisition/service.py:205-210 | — |
| `shape` | def | `(t, raw, *, action, search_intent_id, retrieved_at, used, cap, limit) -> dict` | shared/polymath_shared/acquisition/service.py:243-350 | — |
| `catalog` | def | `(host=None) -> dict` | shared/polymath_shared/acquisition/service.py:221-235 | — |
| `authorize` | def | `(principal_id) -> None` | shared/polymath_shared/acquisition/service.py:119-123 | — |
| `agent_reach_handoff` | def | `(t, action, search_intent_id) -> dict` | shared/polymath_shared/acquisition/service.py:363-386 | — |
| `default_backend` | def | `() -> Backend` | shared/polymath_shared/acquisition/service.py:354-360 | — |
| `AcquisitionRefused` | class | `(status: int, code: str, message: str)` | shared/polymath_shared/acquisition/service.py:82-87 | — |
| `Target` | dataclass | fields: `operation, reader, site=None, url=None, query=None, ident=(), source_class=None` | shared/polymath_shared/acquisition/service.py:90-98 | — |
| `Backend` | Protocol | `status() -> dict`, `read(target, limit) -> dict` | shared/polymath_shared/acquisition/service.py:101-103 | cj_api.py, opencli.py, supplier.py [INFERRED: they are module importers and implement/read the protocol] |

## contracts

**`acquire`** — shared/polymath_shared/acquisition/service.py:389-417
- in: keyword-only args as in the table; `backend=None` selects `default_backend()`. [DERIVED]
- pre: `principal_id is None` (owner only, 403 `OWNER_ONLY` otherwise) — :119-123; `operation` ∈ `OPERATIONS` — :147-148; target/site must pass `resolve` — :392.
- post: returns dict with keys `contract, run_id, action_id, operation, site, target, retrieved_at, status, sources, items, completeness, limitations, human_action, tool_trace, budget, acquisition_id` — :248-254; status ∈ {`OK`, `EMPTY`, `PARTIAL`, `HUMAN_ACTION_REQUIRED`, `UNAVAILABLE`, `AGENT_REACH_REQUIRED`} — :271, :277, :349, :620-area (289), :375. [DERIVED]
- post: `listings` on a site in `AGENT_REACH_SITES` returns the handoff (nothing read, `query_count: 0`, no budget spent) — :393-396, :363-386. [DERIVED]
- post: on `HUMAN_ACTION_REQUIRED` or `UNAVAILABLE` the query is refunded (`refunded: True`, `query_count: 0`) — :412-416. [DERIVED]

**`resolve`** — shared/polymath_shared/acquisition/service.py:145-168
- in: `operation` string, `target` string, optional `site`.
- out: one `Target`, or `AcquisitionRefused`.
- pre: `operation` in `("catalog", "web_search", "comments", "listings")` — :53, :147.
- rules: `web_search` query = `f"site:{host} {q}"` when host given, else `q` — :154; `comments` target must `re.fullmatch` one of `COMMENT_PAGES` (tiktok/instagram/youtube/reddit permalinks) — :156-163; `listings` site must be a key of `LISTING_SITES` (`alibaba.com`, `cjdropshipping.com`, `amazon.com`) — :75-76, :164-166. [DERIVED]

**`bind`** — shared/polymath_shared/acquisition/service.py:171-182
- pre: `action` is a dict with truthy `action_id` (else 409 `NO_OPEN_RESEARCH_STEP`); `target.source_class` not in `action["disallowed_source_roles"]` (else 403 `SOURCE_DISALLOWED`); `search_intent_id` non-empty (422 `MISSING_SEARCH_INTENT`) and present in the action's `search_intents` (422 `UNKNOWN_SEARCH_INTENT`). [DERIVED]

**`take_query`** — shared/polymath_shared/acquisition/service.py:190-202
- in: action dict; cap = `budget.max_queries or 20`.
- out: `(used + 1, cap)`; raises 429 `QUERY_BUDGET_SPENT` when `used >= cap`, 429 `ATTEMPTS_SPENT` when `tried >= 3 * cap`. [DERIVED]

**`shape`** — shared/polymath_shared/acquisition/service.py:243-350
- pure: backend raw dict -> acquisition result dict; no I/O in body. [DERIVED]
- filters challenge-looking rows for `listings`/`web_search` via `looks_like_challenge`; a listings read left with nothing else becomes `human_check` — :259-268. [DERIVED]
- one source per `(url, source_date)`: `sid = "src_" + _sha(f"{url}|{source_date or ''}")[:12]` — :316; items deduped on `item_id` hash — :297-300. [DERIVED]

## effect surface
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty). — shared/polymath_shared/acquisition/service.py:1-418 [DERIVED]
- Network: none directly; delegated to `Backend.read` (default = `listing_apis.wrap(opencli.OpenCLIBackend(), os.environ)`, i.e. the host browser with supplier listing APIs in front). — shared/polymath_shared/acquisition/service.py:354-360 [DERIVED]
- In-process mutable state: `_USED`, `_TRIED` (module dicts) guarded by `_USED_LOCK`; a restart forgets the counts. — shared/polymath_shared/acquisition/service.py:185-187 [DERIVED]
- Env flag: `POLYMATH_ACQUISITION` = `'1'` default; values `"0"`, `"false"`, `"off"` disable acquisition (returns `opencli.Disabled`). — shared/polymath_shared/acquisition/service.py:357-359 [DERIVED]
- Imports: `challenge.looks_like_challenge` (top-level, :49); `listing_apis`, `opencli` (:357), `agent_reach` (:366) imported lazily inside functions. — shared/polymath_shared/acquisition/service.py:49,357,366 [DERIVED]

## invariants
INVARIANT: `OPERATIONS` == `("catalog", "web_search", "comments", "listings")` — shared/polymath_shared/acquisition/service.py:53 [DERIVED]
  fails-if: `resolve` accepts an operation no backend implements, or rejects a documented one.
INVARIANT: query length ∈ `[2, QUERY_MAX]` where `QUERY_MAX = 300` — shared/polymath_shared/acquisition/service.py:54,126-129 [DERIVED]
  fails-if: over-long or 1-char queries reach the backend.
INVARIANT: attempts limit == `3 * cap` where cap = `max_queries or 20` — shared/polymath_shared/acquisition/service.py:192,198-199 [DERIVED]
  fails-if: a caller loops forever on walls without the 429 `ATTEMPTS_SPENT` stop.
INVARIANT: result limit clamped to `[1, LIMIT_MAX]` with `LIMIT_DEFAULT = 20`, `LIMIT_MAX = 50` — shared/polymath_shared/acquisition/service.py:58,213-218 [DERIVED]
  fails-if: a huge `limit` pulls unbounded rows into `shape`.
INVARIANT: `AGENT_REACH_SITES` ⊆ `LISTING_SITES` keys (`{"alibaba.com"}` vs `{alibaba.com, cjdropshipping.com, amazon.com}`) — shared/polymath_shared/acquisition/service.py:75-76,78 [DERIVED]
  fails-if: a site in `AGENT_REACH_SITES` but not `LISTING_SITES` is refused at `resolve` and never reaches the handoff branch at :393.
INVARIANT: one `sources` row per `(url, source_date)` — sid hash input is exactly `f"{url}|{source_date or ''}"` — shared/polymath_shared/acquisition/service.py:316 [DERIVED]
  fails-if: two items with different dates share a source row, overstating freshness.
INVARIANT: items without an exact own date and no page date get `source_id = None` (not receipt-ready) — shared/polymath_shared/acquisition/service.py:309-313 [DERIVED]
  fails-if: TrailSignal would date an undated item at read time.
INVARIANT: `agent_reach_handoff` budget spend == 0 (`query_count: 0`, no `take_query` call) — shared/polymath_shared/acquisition/service.py:363-371,382 [DERIVED]
  fails-if: an Agent-Reach-only site silently consumes the action's query budget.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `datetime.now(timezone.utc)` at :106-107, used by `now_iso` at :367 and :403; env: `POLYMATH_ACQUISITION` at :358; concurrency: shared `_USED`/`_TRIED` mutated under `_USED_LOCK` at :194,:201,:208) — shared/polymath_shared/acquisition/service.py:107,358,185-210 [DERIVED]
idempotency: UNSAFE (each `acquire` call spends one query via `take_query`; only `HUMAN_ACTION_REQUIRED`/`UNAVAILABLE` outcomes are refunded at :412-416, so blind retries on other statuses burn budget) — shared/polymath_shared/acquisition/service.py:402,412-416 [DERIVED]

## failure behaviour
- Broad `except Exception` around `backend.read`/`shape`: the exception is swallowed, logged via `log.exception`, and reshaped as an `UNAVAILABLE` result with `note = f"the read failed ({type(exc).__name__}: ...)"`; the query is then refunded — shared/polymath_shared/acquisition/service.py:408-416 [DERIVED]
- `AcquisitionRefused(status, code, message)` carries a client-stable `code` and HTTP `status` — :82-87. Raised codes: `OWNER_ONLY` 403 (:122), `SOURCE_DISALLOWED` 403 (:175), `NO_OPEN_RESEARCH_STEP` 409 (:173), `BAD_QUERY` 422 (:129,:131), `BAD_SITE` 422 (:141), `UNKNOWN_OPERATION` 422 (:147), `TARGET_NOT_PERMITTED` 422 (:162), `SITE_NOT_SUPPORTED` 422 (:165), `MISSING_SEARCH_INTENT` 422 (:178), `UNKNOWN_SEARCH_INTENT` 422 (:181), `QUERY_BUDGET_SPENT` 429 (:196), `ATTEMPTS_SPENT` 429 (:198), `BAD_LIMIT` 422 (:216). [DERIVED]
- Wall states `sign_in` / `human_check` become `HUMAN_ACTION_REQUIRED` with an instruction and `retry: True`; never bypassed — :239-240,:269-275. [DERIVED]

## dumb-code flags
- Default budget `20` written twice as a bare literal: `or 20` in `take_query` (:192) and in `agent_reach_handoff` (:383); no named constant, while the unrelated `LIMIT_DEFAULT = 20` (:58) shares the value. — shared/polymath_shared/acquisition/service.py:192,383,58 [DERIVED]
- Magic multiplier `3` in `3 * cap` (:198) and its message (:199). — shared/polymath_shared/acquisition/service.py:198-199 [DERIVED]
- Hash-suffix lengths hardcoded and differing: `[:12]` for item/source ids (:298,:316), `[:10]` for `author_key` (:325), `[:24]` for `acquisition_id` (:254,:385). — shared/polymath_shared/acquisition/service.py:298,316,325,254,385 [DERIVED]
- `acquisition_id` construction duplicated verbatim in `shape` (:254) and `agent_reach_handoff` (:385). — shared/polymath_shared/acquisition/service.py:254,385 [DERIVED]
- Ad-hoc clip lengths: `url[:2000]` (:317), `_clip(..., 40)` for `date_shown` (:320), `[:n]` via `EXCERPT_MAX=600`/`TITLE_MAX=300` (:54). — shared/polymath_shared/acquisition/service.py:317,320,54 [DERIVED]
- `out["budget"]["refunded"] = True` (:413) keys a field `shape`'s initial dict never sets (:248-253) — schema grows only on the refund path. — shared/polymath_shared/acquisition/service.py:248-253,413 [DERIVED]

## refactor notes
- `AcquisitionRefused.code`/`status` are declared client-stable (:83) and consumed by `orchestrator/orchestrator/api/acquisition.py`; renaming any code breaks the route's HTTP mapping. — shared/polymath_shared/acquisition/service.py:82-87 [DERIVED]
- `CONTRACT = "research-acquisition-v1"` names the wire contract; every result carries it (:253,:254) and receipt consumers (`HarnessResearchReceiptV1`, docstring :26-28) match on it. — shared/polymath_shared/acquisition/service.py:51 [DERIVED]
- `shape`'s output schema (`sources`, `items`, `tool_trace`) feeds the harness receipt path; field changes ripple to `orchestrator/orchestrator/api/acquisition.py` and the `_small-modules`/`supplier.py` importers. — shared/polymath_shared/acquisition/service.py:243-350 [DERIVED]
- `_USED`/`_TRIED` are process-local by design ("a restart forgets the count", :9); persisting or relocating them changes the budget semantics all callers rely on. — shared/polymath_shared/acquisition/service.py:185-187 [DERIVED]
- `COMMENT_PAGES` patterns and `LISTING_SITES` keys define the entire read surface; adding a site requires both the `resolve` table (:62-76) and a matching backend reader. — shared/polymath_shared/acquisition/service.py:62-78 [DERIVED]

## VERIFY
```verify
grep -Fq 'CONTRACT = "research-acquisition-v1"' shared/polymath_shared/acquisition/service.py
grep -Fq 'AGENT_REACH_SITES = frozenset({"alibaba.com"})' shared/polymath_shared/acquisition/service.py
grep -Eq 'if tried >= 3 \* cap' shared/polymath_shared/acquisition/service.py
grep -Fq 'status AGENT_REACH_REQUIRED' shared/polymath_shared/acquisition/service.py
test "$(grep -c -F 'AcquisitionRefused(' shared/polymath_shared/acquisition/service.py)" -ge 10
! grep -Fq 'INSERT INTO' shared/polymath_shared/acquisition/service.py
```
