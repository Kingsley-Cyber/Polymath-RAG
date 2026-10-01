# unit: shared/polymath_shared/acquisition/service.py
anchor: shared/polymath_shared/acquisition/service.py:1-379

## purpose
Policy + shaping layer for owner-only, read-only research acquisition over the host browser. Resolves a caller request into exactly one catalog target (web search, comments under a content permalink, supplier/marketplace listings), enforces owner/step/budget rules, and shapes the backend's raw read into a receipt-ready result envelope — shared/polymath_shared/acquisition/service.py:311-342, 354-378 [DERIVED]. Consumed by the orchestrator's acquisition API route and the acquisition backend modules (FACTS.importers) — shared/polymath_shared/acquisition/service.py:1 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| acquire | def | (principal_id, action, operation, target, site=None, search_intent_id=None, limit=None, backend=None) -> dict | shared/polymath_shared/acquisition/service.py:354-378 | orchestrator/orchestrator/api/acquisition.py [INFERRED: only public entry, module is in FACTS.importers] |
| resolve | def | (operation: str, target: str, site: str \| None = None) -> Target | shared/polymath_shared/acquisition/service.py:139-162 | — (module importers only) |
| authorize | def | (principal_id: str \| None) -> None | shared/polymath_shared/acquisition/service.py:113-117 | — |
| bind | def | (action: dict \| None, target: Target, search_intent_id: str \| None) -> None | shared/polymath_shared/acquisition/service.py:165-176 | — |
| take_query | def | (action: dict) -> tuple[int, int] | shared/polymath_shared/acquisition/service.py:184-196 | — |
| refund_query | def | (action: dict) -> int | shared/polymath_shared/acquisition/service.py:199-204 | — |
| catalog | def | (host: dict \| None = None) -> dict | shared/polymath_shared/acquisition/service.py:215-226 | — |
| shape | def | (t, raw, *, action, search_intent_id, retrieved_at, used, cap, limit) -> dict | shared/polymath_shared/acquisition/service.py:234-341 | — |
| default_backend | def | () -> Backend | shared/polymath_shared/acquisition/service.py:345-351 | — |
| AcquisitionRefused | class | (status: int, code: str, message: str) | shared/polymath_shared/acquisition/service.py:76-81 | — |
| Target | dataclass | frozen; operation, reader, site, url, query, ident, source_class | shared/polymath_shared/acquisition/service.py:84-92 | — |
| Backend | Protocol | status() -> dict; read(target, limit) -> dict | shared/polymath_shared/acquisition/service.py:95-97 | acquisition backends (opencli.py, cj_api.py, searxng.py, supplier.py in FACTS.importers) [INFERRED: protocol seam] |

Module importers (FACTS.importers): orchestrator/orchestrator/api/acquisition.py; shared/polymath_shared/acquisition/{_small-modules, cj_api.py, opencli.py, searxng.py, supplier.py} — shared/polymath_shared/acquisition/service.py:1 [DERIVED].

## contracts

**acquire** — shared/polymath_shared/acquisition/service.py:354-378
- in: keyword-only args as listed above — shared/polymath_shared/acquisition/service.py:354-355
- pre: `principal_id is None` (else 403 OWNER_ONLY) — shared/polymath_shared/acquisition/service.py:113-117; `operation` in OPERATIONS — shared/polymath_shared/acquisition/service.py:141-142; non-catalog needs an open action dict with `action_id`, an allowed source class, and a `search_intent_id` from the step — shared/polymath_shared/acquisition/service.py:165-176, 361
- out: envelope with keys `contract, run_id, action_id, operation, site, target, retrieved_at, status, sources, items, completeness, limitations, human_action, tool_trace, budget, acquisition_id` — shared/polymath_shared/acquisition/service.py:239-245
- post: status ∈ {`OK`, `EMPTY`, `PARTIAL`, `HUMAN_ACTION_REQUIRED`, `UNAVAILABLE`} — shared/polymath_shared/acquisition/service.py:262, 268, 281, 340; nothing-read statuses set `budget.refunded = True` and `tool_trace.query_count = 0` — shared/polymath_shared/acquisition/service.py:373-377

**resolve** — shared/polymath_shared/acquisition/service.py:139-162
- in: operation, target, optional site
- out: frozen `Target` (shared/polymath_shared/acquisition/service.py:84-92) or `AcquisitionRefused`
- post: `comments` target must `re.fullmatch` one of 5 COMMENT_PAGES patterns and the URL is rebuilt from the canonical form — shared/polymath_shared/acquisition/service.py:151-155; `web_search` with a site prefixes the query `site:{host} ` — shared/polymath_shared/acquisition/service.py:148; `listings` site must be a LISTING_SITES key — shared/polymath_shared/acquisition/service.py:159-160

**take_query** — shared/polymath_shared/acquisition/service.py:184-196
- in: action dict
- out: `(used + 1, cap)` under `_USED_LOCK`; `cap` defaults to `20` when `budget.max_queries` missing — shared/polymath_shared/acquisition/service.py:186, 195-196
- pre: `used < cap` and `tried < 3 * cap`, else 429 — shared/polymath_shared/acquisition/service.py:190-194

**refund_query** — shared/polymath_shared/acquisition/service.py:199-204
- out: new `_USED[key]`, floored at `0`; `_TRIED[key]` untouched

**bind** — shared/polymath_shared/acquisition/service.py:165-176
- pre: action is a dict with `action_id` (else 409); target's `source_class` not in `disallowed_source_roles` (else 403); non-empty `search_intent_id` present in the step's intents (else 422) — shared/polymath_shared/acquisition/service.py:167-176

**shape** — shared/polymath_shared/acquisition/service.py:234-341
- in: Target + backend raw dict + budget/trace params
- out: full envelope; documented pure ("The backend's raw read -> the acquisition result (pure)") — shared/polymath_shared/acquisition/service.py:236

**default_backend** — shared/polymath_shared/acquisition/service.py:345-351
- out: `opencli.Disabled` when `POLYMATH_ACQUISITION` ∈ {"0","false","off"}; else `listing_apis.wrap(opencli.OpenCLIBackend(), os.environ)` — shared/polymath_shared/acquisition/service.py:349-351

## effect surface
- env: `POLYMATH_ACQUISITION` (default `"1"`) — shared/polymath_shared/acquisition/service.py:349; `CJ_API_KEY`, `SEARXNG_URL` named in the docstring but read downstream in `listing_apis` — shared/polymath_shared/acquisition/service.py:346-347 [DERIVED]
- network: only via `backend.read(t, n)` — shared/polymath_shared/acquisition/service.py:366; backend chain assembled at shared/polymath_shared/acquisition/service.py:361. No HTTP/db/file client imports in this module — shared/polymath_shared/acquisition/service.py:35-43
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty) — shared/polymath_shared/acquisition/service.py:1-378
- process state: module dicts `_USED`/`_TRIED` mutated under `_USED_LOCK` — shared/polymath_shared/acquisition/service.py:179-181
- logging: `log.exception` on read failure; logger `"polymath.acquisition"` — shared/polymath_shared/acquisition/service.py:370, 48
- subprocesses: none in SOURCE

## invariants
INVARIANT: len(query) ∈ [2, QUERY_MAX=300] after whitespace join — shared/polymath_shared/acquisition/service.py:121-123, 50 [DERIVED]
  fails-if: shorter/longer query → 422 BAD_QUERY, no read happens.
INVARIANT: attempts tried ≤ 3 × cap (cap default 20 → at most 60) — shared/polymath_shared/acquisition/service.py:192-194, 186 [DERIVED]
  fails-if: beyond it → 429 ATTEMPTS_SPENT; caller must record the limitation instead of retrying.
INVARIANT: limit ∈ [1, LIMIT_MAX=50], default LIMIT_DEFAULT=20 — shared/polymath_shared/acquisition/service.py:207-212, 54 [DERIVED]
  fails-if: non-numeric → 422 BAD_LIMIT; 0/negative silently clamps to 1.
INVARIANT: records shaped ≤ limit + 1 (the +1 slot holds the page's own post/caption) — shared/polymath_shared/acquisition/service.py:273 [DERIVED]
  fails-if: dropping the +1 loses the page's own caption; keeping more breaks the limit contract.
INVARIANT: one source per (url, source_date); source_id = `"src_" + sha256(url|date)[:12]` — shared/polymath_shared/acquisition/service.py:307 [DERIVED]
  fails-if: items from different dates collapse onto one source, misdating them for TrailSignal.
INVARIANT: `published_at` non-null only when precision == "exact" AND value matches `_ISO` — shared/polymath_shared/acquisition/service.py:294-295, 53 [DERIVED]
  fails-if: a relative "3 weeks ago" becomes a fabricated exact timestamp.
INVARIANT: refund only for status ∈ {"HUMAN_ACTION_REQUIRED", "UNAVAILABLE"}, then `query_count = 0` — shared/polymath_shared/acquisition/service.py:373-377 [DERIVED]
  fails-if: EMPTY results (e.g. web_search whose every row was a challenge wall, shared/polymath_shared/acquisition/service.py:256-259, 281) silently spend budget.
INVARIANT: `_USED` floored at 0 on refund; `_TRIED` never decremented — shared/polymath_shared/acquisition/service.py:203-204 [DERIVED]
  fails-if: refunds could go negative or erase attempt history, unbounding retries.
INVARIANT: comments target fullmatches one of exactly 5 COMMENT_PAGES patterns (tiktok, instagram, youtube ×2, reddit) — shared/polymath_shared/acquisition/service.py:151-155, 58-69 [DERIVED]
  fails-if: any profile/feed/short-link URL must be refused as TARGET_NOT_PERMITTED.
INVARIANT: duplicate items skipped by `item_id = "itm_" + sha256(url|ref|text)[:12]` in a `seen` set — shared/polymath_shared/acquisition/service.py:289-292 [DERIVED]
  fails-if: a comment rendered twice by the page is double-counted.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `datetime.now(timezone.utc)` at shared/polymath_shared/acquisition/service.py:101 feeds `retrieved_at`/`started` at shared/polymath_shared/acquisition/service.py:364-367; concurrency on `_USED`/`_TRIED` under `_USED_LOCK` at shared/polymath_shared/acquisition/service.py:179-181). `shape()` is documented pure — shared/polymath_shared/acquisition/service.py:236.
idempotency: UNSAFE (each non-catalog call increments `_USED`/`_TRIED` at shared/polymath_shared/acquisition/service.py:195; refund only on nothing-read statuses at shared/polymath_shared/acquisition/service.py:373-377; the catalog shortcut at shared/polymath_shared/acquisition/service.py:359-360 is side-effect free).

## failure behaviour
- Broad handler `except Exception` at shared/polymath_shared/acquisition/service.py:369: swallows every backend error → `log.exception` (shared/polymath_shared/acquisition/service.py:370), result shaped as `state: "unavailable"` with note `"the read failed ({type}: {str[:200]})"` (shared/polymath_shared/acquisition/service.py:371-372), then refunded via the UNAVAILABLE path (shared/polymath_shared/acquisition/service.py:373-377). Caller sees `status: "UNAVAILABLE"`, `budget.refunded: True`, `query_count: 0` — never a raw 500.
- `AcquisitionRefused(status, code, message)` carries the HTTP status and a client-stable code — shared/polymath_shared/acquisition/service.py:76-81.

| status | code | raise site |
|---|---|---|
| 403 | OWNER_ONLY | shared/polymath_shared/acquisition/service.py:116 |
| 422 | BAD_QUERY | shared/polymath_shared/acquisition/service.py:123, 125 |
| 422 | BAD_SITE | shared/polymath_shared/acquisition/service.py:135 |
| 422 | UNKNOWN_OPERATION | shared/polymath_shared/acquisition/service.py:142 |
| 422 | TARGET_NOT_PERMITTED | shared/polymath_shared/acquisition/service.py:156 |
| 422 | SITE_NOT_SUPPORTED | shared/polymath_shared/acquisition/service.py:160 |
| 409 | NO_OPEN_RESEARCH_STEP | shared/polymath_shared/acquisition/service.py:168 |
| 403 | SOURCE_DISALLOWED | shared/polymath_shared/acquisition/service.py:170 |
| 422 | MISSING_SEARCH_INTENT | shared/polymath_shared/acquisition/service.py:173 |
| 422 | UNKNOWN_SEARCH_INTENT | shared/polymath_shared/acquisition/service.py:176 |
| 429 | QUERY_BUDGET_SPENT | shared/polymath_shared/acquisition/service.py:191 |
| 429 | ATTEMPTS_SPENT | shared/polymath_shared/acquisition/service.py:193 |
| 422 | BAD_LIMIT | shared/polymath_shared/acquisition/service.py:211 |

## dumb-code flags
- Magic hash-suffix lengths: `[:24]` for acquisition_id (shared/polymath_shared/acquisition/service.py:245), `[:12]` for item/source ids (shared/polymath_shared/acquisition/service.py:289, 307), `[:10]` for author_key (shared/polymath_shared/acquisition/service.py:326).
- Bare clip widths scattered: `2000` url (shared/polymath_shared/acquisition/service.py:308), `40` date_shown (shared/polymath_shared/acquisition/service.py:322), `300` notes/backend_notes (shared/polymath_shared/acquisition/service.py:248, 269, 371's `[:200]` exception text).
- Duplicated canonical-form expansion expression `c.format(*(["<id>"] * c.count("{")))` at shared/polymath_shared/acquisition/service.py:157 and shared/polymath_shared/acquisition/service.py:216.
- Budget default `20` (shared/polymath_shared/acquisition/service.py:186) is the same literal as `LIMIT_DEFAULT = 20` (shared/polymath_shared/acquisition/service.py:54) with unrelated meaning; `QUERY_MAX = TITLE_MAX = 300` (shared/polymath_shared/acquisition/service.py:50).
- Asymmetric wall handling: an all-challenge read flips to `state = "human_check"` (refund) only for `listings`; the same web_search read falls through to `EMPTY` and spends its query — shared/polymath_shared/acquisition/service.py:256-259, 281, 373 [DERIVED].
- Comment tuple order in COMMENT_PAGES is positional (site, pattern, canonical, class, reader); `resolve` loops all 5 patterns per call — shared/polymath_shared/acquisition/service.py:151-155.

## refactor notes
- Refusal codes are documented client-stable ("`code` is stable for clients") — shared/polymath_shared/acquisition/service.py:77 — renaming any code/status breaks orchestrator/orchestrator/api/acquisition.py and its clients.
- Budget counters are process-local by design ("counted per action in this process (a restart forgets the count)") — shared/polymath_shared/acquisition/service.py:9, 179-181; persisting them changes a documented guarantee.
- `shape` purity (shared/polymath_shared/acquisition/service.py:236) is relied on by backend modules that build raw dicts (opencli.py, cj_api.py, searxng.py, supplier.py in FACTS.importers); adding I/O inside shape breaks that seam.
- COMMENT_PAGES / LISTING_SITES each drive three places: validation (shared/polymath_shared/acquisition/service.py:151-160), refusal message text (shared/polymath_shared/acquisition/service.py:156-157, 160), and catalog output (shared/polymath_shared/acquisition/service.py:216, 223) — add a site in all three or the catalog lies.
- `acquire`'s catalog shortcut sits before `bind`/`take_query` (shared/polymath_shared/acquisition/service.py:359-360): catalog requires neither an open research step nor budget; reordering changes that.
- The `Backend` Protocol (shared/polymath_shared/acquisition/service.py:95-97) is the only backend seam; `default_backend` wires `listing_apis.wrap(opencli.OpenCLIBackend(), os.environ)` (shared/polymath_shared/acquisition/service.py:361) — changing the wrap order changes API-vs-browser precedence.

## VERIFY
```verify
grep -Fq 'CONTRACT = "research-acquisition-v1"' shared/polymath_shared/acquisition/service.py
grep -Fq 'OPERATIONS = ("catalog", "web_search", "comments", "listings")' shared/polymath_shared/acquisition/service.py
grep -Fq 'LIMIT_DEFAULT, LIMIT_MAX = 20, 50' shared/polymath_shared/acquisition/service.py
grep -Fq 'if tried >= 3 * cap:' shared/polymath_shared/acquisition/service.py
grep -Fq 'os.environ.get("POLYMATH_ACQUISITION", "1")' shared/polymath_shared/acquisition/service.py
test "$(grep -c -F 'raise AcquisitionRefused(' shared/polymath_shared/acquisition/service.py)" -ge 12
! grep -Fq 'INSERT INTO' shared/polymath_shared/acquisition/service.py
```
