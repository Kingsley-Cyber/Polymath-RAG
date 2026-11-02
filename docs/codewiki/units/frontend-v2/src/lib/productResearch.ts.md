# unit: frontend-v2/src/lib/productResearch.ts
anchor: frontend-v2/src/lib/productResearch.ts:1-241

All anchors below are `productResearch.ts:<lines>` = this file. Per-symbol "used by" is module-level only (FACTS.importers); the per-symbol split is not in FACTS.

## purpose
Pure view-model layer (no React) for a product question answered in chat: reads the answer frame's `result.product_research` (contract `product-search-v1`) defensively into drawable shapes — productResearch.ts:1-4 [DERIVED]. Also builds the handoff prompt that continues a governed research run from the web in the person's own agent, and words for a failed run start — productResearch.ts:192-196, :214-218 [DERIVED]. Importers: `frontend-v2/src/lib/chat.ts`, `frontend-v2/src/lib/productReport.ts` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| ProductRunRef | interface | `{ run_id: string; adapter_id?: string; status?: string; started_at?: number }` | productResearch.ts:7-8 | chat.ts, productReport.ts |
| text | function | `(v: unknown) -> string` | productResearch.ts:14-18 | chat.ts, productReport.ts |
| texts | function | `(v: unknown, unique = false) -> string[]` | productResearch.ts:21-24 | chat.ts, productReport.ts |
| countText | function | `(v: unknown) -> string` | productResearch.ts:28-38 | chat.ts, productReport.ts |
| httpUrl | function | `(v: unknown) -> string \| null` | productResearch.ts:42-51 | chat.ts, productReport.ts |
| Tone | type | `"ready" \| "degraded" \| "blocked" \| "unknown"` | productResearch.ts:55 | chat.ts, productReport.ts |
| cjStatus | function | `(code: string) -> { tone: Tone; words: string }` | productResearch.ts:66-72 | chat.ts, productReport.ts |
| cjEmptyWords | function | `(code: string) -> string` | productResearch.ts:75-82 | chat.ts, productReport.ts |
| CommandView | interface | `{ run, what, forEach, then: string }` | productResearch.ts:86 | chat.ts, productReport.ts |
| ReachView | interface | `{ reasonCode, why, runOn, never, repo, verify, how, walls: string; commands: CommandView[] }` | productResearch.ts:87-93 | chat.ts, productReport.ts |
| ItemView | interface | `{ key, title, price, discount, moq, supplier, stores, stock: string; image, url: string \| null }` | productResearch.ts:94-97 | chat.ts, productReport.ts |
| HypothesisView | interface | `{ key, title, problem, audience: string; tags, terms: string[]; cj, alibaba: {...} \| null }` | productResearch.ts:98-102 | chat.ts, productReport.ts |
| OfferView | interface | `{ adapterId: string; input: Obj; note, whoDrives: string }` | productResearch.ts:103 | chat.ts, productReport.ts |
| ProductView | interface | `{ contract, seed, audience, geography, noTerminalNote, repo, verify: string; corpusIds, limitations: string[]; hypotheses: HypothesisView[]; offer: OfferView \| null }` | productResearch.ts:104-112 | chat.ts, productReport.ts |
| productView | function | `(data: unknown) -> ProductView \| null` | productResearch.ts:165-190 | chat.ts, productReport.ts |
| agentPrompt | function | `(run: ProductRunRef, opts: { seed?: string; repo?: string; verify?: string } = {}) -> string` | productResearch.ts:196-211 | chat.ts, productReport.ts |
| startErrorWords | function | `(e: unknown) -> string` | productResearch.ts:214-218 | chat.ts, productReport.ts |

Not exported (private): `obj` (:11), `CJ_STATUS` (:58-64), `commandsOf` (:115-122), `reachOf` (:124-133), `itemsOf` (:139-152), `offerOf` (:156-162), `serverMessage` (:222-240). Sole import: `ApiError` from `./api` — productResearch.ts:5 [DERIVED].

## contracts

**productView(data) -> ProductView | null** — productResearch.ts:165-190
- in: the answer's `result.product_research`; any field may be missing, a listing's text is the supplier's own — productResearch.ts:1-3 [DERIVED]
- out: `null` when `data` is not a plain object (arrays rejected by `obj`, :11) — productResearch.ts:166-167 [DERIVED]
- out: `null` when none of `hypotheses.length || offer || limitations.length || noTerminalNote` is truthy — productResearch.ts:189 [DERIVED]
- post: `cj.status` and `alibaba.status` forced `.toUpperCase()` — productResearch.ts:178-179 [DERIVED]
- post: `repo`/`verify` resolve as `install` → first reach fallback carrying repo or verify → `""` — productResearch.ts:182, :186 [DERIVED]
- pre: none — every field read through `text`/`texts`/`countText`/`httpUrl`/`obj`, which never throw — productResearch.ts:13-51, :139-152 [DERIVED]

**agentPrompt(run, opts = {}) -> string** — productResearch.ts:196-211
- in: `run_id` required; `adapter_id`, `seed`, `repo`, `verify` optional — productResearch.ts:7-8, :196-199 [DERIVED]
- out: paragraphs joined `"\n\n"`: "do not start a new run"; `adapter_next("${id}")`; `adapter_submit` with kind `"reasoning"` for AGENT_REASON / `"receipt"` for HARNESS_ACTION; resubmit same step after rejection; `adapter_result("${id}")`; "a refusal or a gap is a finding, not an error"; local Agent Reach "never your built-in web search"; guide `polymath://adapter/guide` — productResearch.ts:202-210 [DERIVED]
- post: install sentence emitted only when `opts.repo || opts.verify` — productResearch.ts:198-200 [DERIVED]

**startErrorWords(e) -> string** — productResearch.ts:214-218
- `e instanceof ApiError` -> `` `HTTP ${e.status}: ${serverMessage(e.body) || "the server sent no message"}` `` — productResearch.ts:215 [DERIVED]
- other `Error` -> `e.message || e.name`; anything else -> `String(e)` — productResearch.ts:216-217 [DERIVED]

**Coercion helpers**

| fn | rule | anchor |
|---|---|---|
| text(v) | string -> trimmed; finite number -> `String(v)`; object/array/boolean/other -> `""` | productResearch.ts:14-17 |
| texts(v, unique=false) | array -> `text()` of entries, blanks dropped; `unique` -> `new Set` dedupe | productResearch.ts:21-23 |
| countText(v) | finite number -> `toLocaleString()`; string matching `/^\d{4,15}$/` -> `Number(s).toLocaleString()`; other string as written; array -> entries joined `" · "`; object -> `"k v"` entries joined `" · "` | productResearch.ts:29-37 |
| httpUrl(v) | only `https:`/`http:` URLs return `u.href`; scheme-relative `"//host/path"` read as `https:`; parse failure or any other scheme -> `null` | productResearch.ts:42-50 |

**CJ status mapping**

| code | tone | words | anchor |
|---|---|---|---|
| `OK` | ready | Listings found | productResearch.ts:59 |
| `PARTIAL` | degraded | Partly searched | productResearch.ts:60 |
| `EMPTY` | unknown | No listings | productResearch.ts:61 |
| `UNAVAILABLE` | blocked | Unavailable here | productResearch.ts:62 |
| `AGENT_REACH_REQUIRED` | degraded | Needs Agent Reach | productResearch.ts:63 |
| `""` | unknown | Status not given | productResearch.ts:69 |
| other | unknown | code with `[_.]` -> space, lowercased, first letter capitalized | productResearch.ts:70-71 |

**cjEmptyWords(code)** literals — productResearch.ts:77-81 [DERIVED]: `EMPTY` -> "No CJ Dropshipping listing matched this idea's search terms."; `UNAVAILABLE` -> "CJ Dropshipping could not be searched from here."; `AGENT_REACH_REQUIRED` -> "This CJ Dropshipping search runs through Agent Reach on your own device."; `PARTIAL` -> "Only part of the CJ Dropshipping search ran, and it found no listing."; default -> "No CJ Dropshipping listing to show."

**serverMessage(body)** (private, feeds startErrorWords) — productResearch.ts:222-240: parses `detail`; string as is; `{message}`; `{loc, msg}` -> `` `${loc.join(".")}: ${msg}` ``; `{rejected: [...]}` recursively; other objects -> `JSON.stringify`; list -> entries joined `"; "`; non-JSON body (a proxy's page) -> tags stripped `/<[^>]*>/g`, whitespace collapsed, capped at 300 chars; final result capped at 600 chars — productResearch.ts:225-239 [DERIVED].

## effect surface
- Postgres tables: none read, none written (FACTS `tables_read: []`, `tables_written: []`) [DERIVED].
- Qdrant / files / network / subprocess / env flags: none in SOURCE lines 1-240 [INFERRED: full-file scan, no such calls or reads].
- Module dependency: `ApiError` from `./api` — productResearch.ts:5 [DERIVED].

## invariants

INVARIANT: `CJ_STATUS` key count = 5 (`OK`, `PARTIAL`, `EMPTY`, `UNAVAILABLE`, `AGENT_REACH_REQUIRED`) — productResearch.ts:58-63 [DERIVED]
  fails-if: a new backend status falls into the unknown path and renders tone `"unknown"` with a humanized code — productResearch.ts:69-71
INVARIANT: `httpUrl(v) !== null` ⟹ protocol ∈ {`"https:"`, `"http:"`} — productResearch.ts:47 [DERIVED]
  fails-if: `javascript:`/`data:` URLs in supplier listing text become linkable/loadable — productResearch.ts:40-41
INVARIANT: digit grouping applies only to strings matching `/^\d{4,15}$/` — productResearch.ts:32 [DERIVED]
  fails-if: `"1203"` ungrouped vs `"12030"` grouped — visible discontinuity at 3 vs 4 digits
INVARIANT: `productView` returns non-null ⟺ `hypotheses.length ∨ offer ∨ limitations.length ∨ noTerminalNote` — productResearch.ts:189 [DERIVED]
  fails-if: importer renders an empty frame or drops a renderable one
INVARIANT: `OfferView` exists only when `adapter_id` trims to non-empty — productResearch.ts:158-159 [DERIVED]
  fails-if: an offer with no adapter would show a start control with nothing to start
INVARIANT: every `offer.input` value ≠ null and ≠ undefined — productResearch.ts:160 [DERIVED]
  fails-if: adapter input schema rejects a null where it wants a string — productResearch.ts:154-155
INVARIANT: item discount rendered only when `discount !== price` (string compare) — productResearch.ts:146 [DERIVED]
  fails-if: equal strings hide the discount; differently-formatted equal amounts both render
INVARIANT: item field lookup order = `it[name] ?? it[rawName] ?? it.listing[name] ?? it.listing[rawName]` — productResearch.ts:142 [DERIVED]
  fails-if: raw unrenamed `listing_record` fields (from `shared/polymath_shared/acquisition/cj_api.py`, :135-137) stop displaying
INVARIANT: `serverMessage` output ≤ 600 chars; non-JSON path ≤ 300 chars — productResearch.ts:239, :227 [DERIVED]
  fails-if: oversized proxy error pages leak into tooltips

## determinism & idempotency
determinism: NONDETERMINISTIC (env: host locale via `Number.toLocaleString()` at productResearch.ts:29 and :32 — digit grouping varies; all other logic is pure string/data transformation with no clock, random, uuid, network or db, lines 1-240 [INFERRED: full-file scan])
idempotency: SAFE (no writes or external effects; header declares the module pure, no React — productResearch.ts:3 [DERIVED])

## failure behaviour
- URL parse failure swallowed by `try/catch` -> `httpUrl` returns `null` — productResearch.ts:45-49 [DERIVED].
- `JSON.parse` failure in `serverMessage` swallowed -> body HTML-stripped as text — productResearch.ts:226-227 [DERIVED].
- `ApiError` whose body yields no message -> literal `"the server sent no message"` — productResearch.ts:215 [DERIVED].
- Unrecognized `detail` shapes -> `JSON.stringify` fallback, never a throw — productResearch.ts:232, :236 [DERIVED].
- Missing/malformed answer fields -> `""`/`[]`/`null` via `text`/`texts`/`itemsOf`/`commandsOf`; `commandsOf` drops entries with empty `run` — productResearch.ts:14-17, :139-140, :121 [DERIVED].
- No `throw` statement and no error codes raised in SOURCE lines 1-240 [INFERRED: full-file scan].

## dumb-code flags
- Magic numbers: `4,15` digit-length window — productResearch.ts:32; `300` and `600` char caps — productResearch.ts:227, :239 [DERIVED].
- Duplicated literals: `" · "` join separator at two sites — productResearch.ts:34, :37; `"CJ Dropshipping"` ×4 — productResearch.ts:77-80 [DERIVED].
- Install `repo`/`verify` precedence decided in three places: `reachOf` (`own` → `install`), `productView` (`install` → first reach), `agentPrompt` (opts → sentence) — productResearch.ts:130, :186, :198-199 [DERIVED]. A precedence change must touch all three.
- Tone `"unknown"` carries two meanings: known `EMPTY` and unrecognized code — productResearch.ts:61, :69-71 [DERIVED].
- `key` = `` `${i}:${id}` `` mixes array index with product id — productResearch.ts:146 [DERIVED]; reordering `items` changes keys.
- Asymmetric dedupe: `texts(h.evidence_tags, true)` vs `texts(h.search_terms)` without unique — productResearch.ts:177 [DERIVED].
- Regex HTML stripping `/<[^>]*>/g` on non-JSON bodies — fragile on malformed tags — productResearch.ts:227 [DERIVED].

## refactor notes
- `itemsOf`'s dual-name read (`price`/`price_as_listed`, `discount_price`/`discount_price_as_listed`, `moq`/`minimum_order_as_listed`, `stores_listing`/`listed_by_stores`, `warehouse_stock`/`warehouse_inventory`, `product_id`/`ref`) exists because raw `listing_record` from `shared/polymath_shared/acquisition/cj_api.py` may arrive unrenamed — productResearch.ts:135-137, :142-149 [DERIVED]. Dropping either name breaks raw-record display.
- `productView`'s nothing-to-show null gate (:189) is the render switch for both importers (chat.ts, productReport.ts per FACTS.importers); loosening it changes chat rendering.
- `agentPrompt` strings name tools `adapter_next`, `adapter_submit`, `adapter_result`, kinds `"reasoning"`/`"receipt"`, and resource `polymath://adapter/guide` — agents match on these literals — productResearch.ts:204-209 [DERIVED].
- `ProductView.corpusIds` feeds PRODUCT-DECISION-REPORT-V1 B6 ("a report built from it uses the same ones") — productResearch.ts:106 [DERIVED]; productReport.ts is an importer (FACTS.importers).
- `ProductRunRef` is persisted on the turn so `run_id` and the prompt survive a reload — productResearch.ts:7 [DERIVED]; renaming its fields breaks stored turns.
- `startErrorWords` depends on `ApiError`'s `status` and `body` shape from `./api` — productResearch.ts:5, :215, :222 [DERIVED]; an api.ts change ripples here.
- Every export is consumed via chat.ts / productReport.ts (FACTS.importers); any signature change has that two-file blast radius at minimum.

## VERIFY
```verify
grep -Fq 'product-search-v1' frontend-v2/src/lib/productResearch.ts
grep -Fq 'AGENT_REACH_REQUIRED' frontend-v2/src/lib/productResearch.ts
grep -Fq 'Number(s).toLocaleString()' frontend-v2/src/lib/productResearch.ts
grep -Eq 'slice\(0, (300|600)\)' frontend-v2/src/lib/productResearch.ts
grep -Fq 'adapter_next(' frontend-v2/src/lib/productResearch.ts
! grep -Fq 'fetch(' frontend-v2/src/lib/productResearch.ts
test "$(grep -c -F 'CJ Dropshipping' frontend-v2/src/lib/productResearch.ts)" -ge 4
```
