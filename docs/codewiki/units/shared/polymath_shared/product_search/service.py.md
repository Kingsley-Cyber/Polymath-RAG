# unit: shared/polymath_shared/product_search/service.py
anchor: shared/polymath_shared/product_search/service.py:1-607

## purpose
Implements product-search-v1: the product turn's CJ Dropshipping supplier lookups and the `product_research` block every product turn carries — shared/polymath_shared/product_search/service.py:1-18 [DERIVED]. Default flow: product hypotheses from the chosen corpus, one CJ search per hypothesis, an OFFER (never auto-start) of the full governed run `ecommerce.product_research` driven by the user's agent — shared/polymath_shared/product_search/service.py:4-6 [DERIVED]. Driven by the chat runtime (`orchestrator/api/ui.py`) and `POST /product/search`; pure apart from the injected `search` callable (default `polymath_shared.acquisition.supplier.search`) — shared/polymath_shared/product_search/service.py:17-18 [DERIVED].

## public surface
Module imported by `orchestrator/orchestrator/api/product.py` and `shared/polymath_shared/product_search/_small-modules` — material-6152368128-637523477493791.md:358-361 [DERIVED].

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| CONTRACT | const | `"product-search-v1"` | shared/polymath_shared/product_search/service.py:29 | — |
| ADAPTER_ID | const | `"ecommerce.product_research"` | shared/polymath_shared/product_search/service.py:30 | — |
| agent_reach_block | func | () -> dict | shared/polymath_shared/product_search/service.py:58-59 | — |
| fallback_for | func | (site: str, query: str \| None, reason_code: str, why: str) -> dict | shared/polymath_shared/product_search/service.py:68-83 | — |
| item_view | func | (raw: Mapping, sources_by_id: Mapping) -> dict | shared/polymath_shared/product_search/service.py:86-99 | — |
| cj_lookup | func | (term: str, \*, principal_id: str \| None, limit: int, search: Callable) -> dict | shared/polymath_shared/product_search/service.py:106-132 | — |
| alibaba_handoff | func | (term: str \| None) -> dict | shared/polymath_shared/product_search/service.py:135-139 | — |
| _Lookups | class | \_\_init\_\_(\*, principal_id, limit, search, cap); find(terms: list[str]) -> dict | shared/polymath_shared/product_search/service.py:142-180 | this module |
| seed_for | func | (intent: ProductIntent, message: str) -> str | shared/polymath_shared/product_search/service.py:184-196 | — |
| next_block | func | (intent, corpus_ids: list[str], message: str, \*, hypotheses_from: str \| None = None) -> dict | shared/polymath_shared/product_search/service.py:199-225 | — |
| build_block | func | (intent, \*, corpus_ids, message, hypotheses, term_finds=None, lookups=None, parse=None, verdict=None, steer=None, hypotheses_from=None, routing=None, extra_limitations=()) -> dict | shared/polymath_shared/product_search/service.py:232-277 | — |
| verdict_for | func | (hypotheses: list[dict], \*, evidence_count: int, parse_status: str \| None) -> str | shared/polymath_shared/product_search/service.py:280-286 | — |
| finds_markdown | func | (block: Mapping, legend_tags: Iterable[str] \| None = None) -> str | shared/polymath_shared/product_search/service.py:337-361 | — |
| summary | func | (block: Mapping \| None, verdict: str \| None = None) -> dict \| None | shared/polymath_shared/product_search/service.py:364-377 | — |
| agent_steps | func | (block: Mapping) -> list[str] | shared/polymath_shared/product_search/service.py:380-397 | — |
| compact_evidence | func | (legend, text_of=None, previews=None) -> list[dict] | shared/polymath_shared/product_search/service.py:400-416 | — |
| normalize_geography | func | (value: Any) -> str \| None | shared/polymath_shared/product_search/service.py:419-427 | — |
| ProductTurn | class | \_\_init\_\_(intent, \*, message, corpus_ids=(), principal_id=None, options=None, search=None); methods steer_plan, steer_text, contract, route, read_answer, planned_lookups, finish_llm, finish_deterministic, finish_evidence, finish_agent, receipt | shared/polymath_shared/product_search/service.py:438-606 | module importers above |

## contracts

**cj_lookup** — shared/polymath_shared/product_search/service.py:106-132
- in: calls `search(principal_id=principal_id, query=term, source="cj", limit=limit)` — :110 [DERIVED]
- out: keys `{status, search_term, items, fallback, reason_code, limitations}` — :107, :131-132 [DERIVED]
- pre: `principal_id=None` means the owner / a trusted local caller — :8 (docstring) [DERIVED]
- post: status upper-cased (:122); items flattened via `item_view` and truncated to `limit` (:124); any failure degrades to a typed entry, never raises — :11-12, :111-120 [DERIVED]

**item_view** — shared/polymath_shared/product_search/service.py:86-99
- in: one shaped supplier item (`listing` Mapping nested) + sources by id — :90, :97 [DERIVED]
- out: exactly the ITEM_FIELDS names; a missing field is `null`, never invented — :49-50, :92-96 [DERIVED]
- post: `url` kept only when it starts with `https://` or `http://`, else `None` — :98 [DERIVED]

**fallback_for** — shared/polymath_shared/product_search/service.py:68-83
- in: site, query, reason_code, why; delegates to `agent_reach.fallback` — :73-74 [DERIVED]
- out: a Mapping handoff passed through unchanged (:75-76); on any build failure a placeholder with `"kind": "AGENT_REACH"`, `"commands": []`, `"submit": {"tool": "supplier_parse", "route": "POST /supplier/parse"}`, `"placeholder": True`, `build_error` — :79-83 [DERIVED]

**_Lookups.find** — shared/polymath_shared/product_search/service.py:153-180
- in: a hypothesis's term list; picks the first term not yet in `self.results`, else reuses the result for `terms[0]` — :157-159 [DERIVED]
- post: at `cap` searches returns `NOT_SEARCHED` with a note (:160-163); dedups items by `product_id` or `url` or `title` across the turn (:169-176); limitations popped into `self.notes` — :167 [DERIVED]

**seed_for** — shared/polymath_shared/product_search/service.py:184-196
- out: `seed + " for " + audience` when both present and audience not already in seed; else seed; else `"products for <audience>"`; else the message; capped `[:2000]`, minimum length 3 else `"product opportunities from this library"` — :187-196 [DERIVED]

**next_block** — shared/polymath_shared/product_search/service.py:199-225
- out: `next.full_research` with `adapter_id = ADAPTER_ID`, `"auto_start": False`, `"who_drives": "your agent"` — :205-210 [DERIVED]; plus `hypotheses` how-to only when `hypotheses_from` is `"model"` or `"agent"` — :211-224 [DERIVED]

**build_block** — shared/polymath_shared/product_search/service.py:232-277
- out keys: `contract, intent{kind,seed,audience,geography,rule}, corpus_ids, hypotheses, [term_finds], limitations, next, agent_reach, receipts{lookups,statuses{cj,alibaba},deduped,parse,[steer],[routing]}, [verdict]` — :258-276 [DERIVED]
- post: `limitations` always starts with `SUPPLY_NOT_DEMAND` (:240); `HYPOTHESES_NOT_FACTS` only when hypotheses exist (:241-242); geography caveat when `intent.geography` (:243-245) [DERIVED]

**verdict_for** — shared/polymath_shared/product_search/service.py:280-286
- out: `"product_hypotheses_thin"` when no hypotheses, `parse_status == "fallback"`, `evidence_count < THIN_EVIDENCE`, or `cited * 2 < len(hypotheses)`; else `"product_hypotheses"` — :283-285 [DERIVED]

**finds_markdown / summary / compact_evidence** — shared/polymath_shared/product_search/service.py:337-361, :364-377, :400-416
- finds_markdown: header `"### Supplier finds (CJ Dropshipping)"`, ≤ `MD_ITEMS` items per entry, closing offer line — :343, :328, :359-360 [DERIVED]
- summary: counts and statuses only, never item text — :365 (docstring), :371-377 [DERIVED]
- compact_evidence: ≤ `EVIDENCE_ROWS` rows, each `{tag, chunk_id, source, text}` with text ≤ `EVIDENCE_TEXT` chars — :405, :414-415 [DERIVED]

**ProductTurn** — shared/polymath_shared/product_search/service.py:438-606
- `__init__`: geography option normalized and replaces the intent's via `dataclasses.replace` — :445-448; limit from `options["limit_per_hypothesis"]` clamped — :453 [DERIVED]
- `route(candidates, *, embed=None, role_scope=None, **deps)` -> chosen library or `None`; on success sets `self.corpus_ids = [chosen]` — :484-498 [DERIVED]
- `planned_lookups()` = `min(n, MAX_LOOKUPS if hyps else MAX_TERM_LOOKUPS)` — :506-509 [DERIVED]
- `finish_llm(*, legend)` -> `(block, verdict, markdown)`; thin verdict sets `"confidence": "low"` on hypotheses without evidence_tags — :530-556, :539-543 [DERIVED]
- `finish_deterministic(answer)` -> dict: original verdict preserved as `meta.grounded_verdict`, replaced by `VERDICT_TERMS` — :558-574, :567-569 [DERIVED]
- `finish_evidence()` -> `(block, agent_steps)`, `verdict = None` — :576-580 [DERIVED]
- `finish_agent` and `receipt` exist per FACTS methods; bodies past line 580 not shown — material-6152368128-637523477493791.md:293-309 [DERIVED]

## effect surface
- Network: CJ supplier search through the injected callable (default `polymath_shared.acquisition.supplier.search`, lazily imported) — shared/polymath_shared/product_search/service.py:63-65, :110 [DERIVED]
- Alibaba: never searched from this host; only an Agent Reach handoff is built — shared/polymath_shared/product_search/service.py:13-14, :135-139 [DERIVED]
- Postgres tables read/written: none — material-6152368128-637523477493791.md:376-377 [DERIVED]
- Qdrant collections: none accessed; `"polymath_models"` appears only as advice text inside the `chat` suggestion — shared/polymath_shared/product_search/service.py:217 [DERIVED]
- Files, subprocesses, env flags: none visible in lines 1-580 — shared/polymath_shared/product_search/service.py:20-27, :442-580 [DERIVED]
- Lazy imports inside functions: `acquisition.supplier` (:64), `acquisition.agent_reach` (:73), `acquisition.service.AcquisitionRefused` (:108), `dataclasses.replace` (:447), `copy` (:465), `product_search.routing` (:487) — shared/polymath_shared/product_search/service.py:64-487 [DERIVED]

## invariants
INVARIANT: CJ searches per hypothesis turn ≤ MAX_LOOKUPS = 5 (cap passed at finish_llm; enforced in _Lookups.find) — shared/polymath_shared/product_search/service.py:32, :534, :160-163 [DERIVED]
  fails-if: more than ~1 call/second per CJ key; rate limiting or refused calls.
INVARIANT: CJ searches on hypothesis-free turns ≤ MAX_TERM_LOOKUPS = 3 — shared/polymath_shared/product_search/service.py:33, :524, :561, :578 [DERIVED]
  fails-if: turns without hypotheses exceed the smaller CJ budget intended for them.
INVARIANT: verdict == "product_hypotheses_thin" when evidence_count < THIN_EVIDENCE = 3 or cited*2 < len(hypotheses) or parse_status == "fallback" — shared/polymath_shared/product_search/service.py:35, :283-285 [DERIVED]
  fails-if: thin-evidence hypotheses presented as full-confidence.
INVARIANT: every item_view output has all ITEM_FIELDS keys; url non-null only when it startswith `https://` or `http://` — shared/polymath_shared/product_search/service.py:49-50, :92-98 [DERIVED]
  fails-if: downstream code invents or trusts absent CJ fields.
INVARIANT: _limit(value) in [1, MAX_LIMIT = 10]; default DEFAULT_LIMIT = 6 — shared/polymath_shared/product_search/service.py:34, :430-435 [DERIVED]
  fails-if: a request asks for more CJ items per hypothesis than the API budget allows.
INVARIANT: seed_for output length in [3, 2000] — shared/polymath_shared/product_search/service.py:194-196 [DERIVED]
  fails-if: adapter_start rejects the seed (docstring: adapter wants 3 to 2000 characters).
INVARIANT: same CJ term searched at most once per turn (results keyed by term; later hypotheses reuse the stored result) — shared/polymath_shared/product_search/service.py:157-159 [DERIVED]
  fails-if: duplicate CJ calls burn the 5-search cap.
INVARIANT: a product kept once per turn; dedup key = product_id or url or title — shared/polymath_shared/product_search/service.py:169-176 [DERIVED]
  fails-if: the same listing repeats across hypotheses in one answer.
INVARIANT: markdown items per entry ≤ MD_ITEMS = 3 — shared/polymath_shared/product_search/service.py:36, :328 [DERIVED]
  fails-if: answer text bloats beyond the intended short section.
INVARIANT: compact_evidence rows ≤ EVIDENCE_ROWS = 16 and text ≤ EVIDENCE_TEXT = 400 chars — shared/polymath_shared/product_search/service.py:37, :405, :415 [DERIVED]
  fails-if: /product/search evidence payload grows unbounded.
INVARIANT: normalize_geography trims to 60 chars, upper-cases 2-letter codes, maps "UK" -> "GB" — shared/polymath_shared/product_search/service.py:422-426 [DERIVED]
  fails-if: the adapter receives inconsistent geography strings.
INVARIANT: status not in LISTED_STATUSES = ("OK", "PARTIAL") with no upstream fallback ⇒ fallback_for synthesizes one — shared/polymath_shared/product_search/service.py:54, :127-130 [DERIVED]
  fails-if: a failed/empty CJ search reaches the user with no Agent Reach handoff.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: CJ call via injected `search` — shared/polymath_shared/product_search/service.py:110; optional `embed` callable in route — :484-489. No clock/random/uuid usage visible in lines 1-580 — :20-27, :442-580) [DERIVED]
idempotency: SAFE (pure dict-building over inputs; `_Lookups` state — results/seen/deduped/skipped_cap/notes — is per-turn, reusing one instance across turns would distort dedup and the cap) — shared/polymath_shared/product_search/service.py:147-151 [INFERRED: state fields are cumulative with no reset]

## failure behaviour
- fallback_for: any Exception from `agent_reach.fallback` swallowed; caller sees a typed placeholder with `"placeholder": True` and `build_error` — shared/polymath_shared/product_search/service.py:77-83 [DERIVED]
- cj_lookup: `AcquisitionRefused` -> `{"status": "UNAVAILABLE", ...}`, `reason_code = exc.code`, `refused = {code, status, message}`, Agent Reach fallback — :111-116; any other Exception -> `"UNAVAILABLE"`, `reason_code = "CJ_ERROR"` — :117-120. Caller never sees a raise — :11-12 [DERIVED]
- steer_plan: Exception -> `steer = {"mode": "failed", "error": <typename>}`, original compiled plan returned unchanged — :469-471 [DERIVED]
- steer_text: Exception -> original query returned, steer marked failed — :477-479 [DERIVED]
- route: Exception -> `method = "first_candidate"`, chosen = first candidate by sorted id, `notes = ["routing failed (<typename>)"]` — :490-494 [DERIVED]
- compact_evidence: `text_of` Exception -> text falls back to the preview by locator — :411-413 [DERIVED]
- Typed non-results: `_not_searched` -> `status "NOT_SEARCHED"` (:102-103); Alibaba -> `"AGENT_REACH_REQUIRED"` with `reason_code "ALIBABA_AGENT_REACH_ONLY"` (:138-139) [DERIVED]

## dumb-code flags
- `"A listing proves supply, not demand."` hardcoded twice in finds_markdown while the constant `SUPPLY_NOT_DEMAND` exists — shared/polymath_shared/product_search/service.py:44, :345, :352-353 [DERIVED]
- `str(exc)[:160]` magic truncation in fallback_for — shared/polymath_shared/product_search/service.py:78 [DERIVED]
- `cj.pop("limitations", None)` at :179 runs on a copy whose `limitations` were already popped at :167 — defensive no-op — shared/polymath_shared/product_search/service.py:167-168, :179 [INFERRED: pop precedes the dict copy]
- ITEM_FIELDS contains `"url"` but LISTING_FIELDS has no `url` key; url is special-cased outside the mapping, and any ITEM_FIELDS name missing from LISTING_FIELDS silently yields None via `if name in LISTING_FIELDS else None` — shared/polymath_shared/product_search/service.py:49-53, :93, :97-98 [DERIVED]
- `_STATUS_WORDS` duplicates the status vocabulary also written as literals at :103, :113, :119, :138 — shared/polymath_shared/product_search/service.py:301-303 [DERIVED]
- Magic caps: geography trimmed to 60 (:422), seed to 2000 (:195), evidence text 400 / rows 16 (:37) — bare numbers at use sites partially, constants at :37 [DERIVED]

## refactor notes
- Public renames break both known importers: `orchestrator/orchestrator/api/product.py` and `shared/polymath_shared/product_search/_small-modules` — material-6152368128-637523477493791.md:358-361 [DERIVED]
- `CONTRACT = "product-search-v1"` is written into every block and summary; external consumers filter on it — shared/polymath_shared/product_search/service.py:259, :371 [DERIVED]
- ITEM_FIELDS/LISTING_FIELDS are coupled to the acquisition layer's shaped item (`listing` nesting, URL on the source row); changing CJ shaping breaks item_view — shared/polymath_shared/product_search/service.py:48, :86-98 [DERIVED]
- Upstream fallbacks are passed through UNCHANGED; only synthesized when absent — do not re-wrap — shared/polymath_shared/product_search/service.py:10, :125-130 [DERIVED]
- finish_llm/finish_evidence return tuples, finish_deterministic returns a dict; callers per method must match — shared/polymath_shared/product_search/service.py:530-556, :558-574, :576-580 [DERIVED]
- `_default_search` and the other acquisition imports are lazy; moving them to module level changes import order/cycles — shared/polymath_shared/product_search/service.py:63-65, :73, :108 [INFERRED: laziness is deliberate, module stays import-pure per :17-18]
- route's failure path silently picks the first candidate by sorted id; corpus selection order becomes user-visible — shared/polymath_shared/product_search/service.py:491-494 [DERIVED]

## VERIFY
```verify
grep -Fq 'CONTRACT = "product-search-v1"' shared/polymath_shared/product_search/service.py
grep -Fq 'MAX_LOOKUPS = 5' shared/polymath_shared/product_search/service.py
grep -Fq 'LISTED_STATUSES = ("OK", "PARTIAL")' shared/polymath_shared/product_search/service.py
grep -Fq 'source="cj"' shared/polymath_shared/product_search/service.py
test "$(grep -c -F 'product-search-v1' shared/polymath_shared/product_search/service.py)" -ge 2
! grep -Fq 'MAX_LOOKUPS = 6' shared/polymath_shared/product_search/service.py
```
