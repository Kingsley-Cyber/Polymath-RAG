# unit: shared/polymath_shared/product_search/intent.py
anchor: shared/polymath_shared/product_search/intent.py:1-375

## purpose
Decides whether a chat message is a request to FIND products to sell (or suppliers for one) and extracts the request's slots; deterministic regex only, no model — shared/polymath_shared/product_search/intent.py:1-2 [DERIVED]. A match switches the chat turn into product mode (`product_search.service.ProductTurn`); this module only decides and extracts, never retrieves — shared/polymath_shared/product_search/intent.py:5-7 [DERIVED]. Fires on requests, never on knowledge questions about products — shared/polymath_shared/product_search/intent.py:9-13 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ProductIntent` | class (frozen dataclass) | fields kind, rule, seed, seed_kind, audience, geography, search_terms, source, vetoed | intent.py:181-192 | — |
| `ProductIntent.as_dict` | method | () -> dict[str, Any] | intent.py:194-197 | — |
| `search_terms_for` | def | (seed: str \| None, seed_kind: str \| None, audience: str \| None) -> tuple[str, ...] | intent.py:313-325 | — |
| `detect` | def | (message: str, history: Iterable[Any] \| None = None, *, force: bool = False) -> ProductIntent \| None | intent.py:348-375 | — |

Module importers (FACTS): `shared/polymath_shared/product_search/_small-modules`, `shared/polymath_shared/product_search/service.py`.

## contracts
### detect — intent.py:348-375
- in: `message` raw text; `history` turns exposing `role`/`content` as attributes or dict keys — intent.py:329-331 [DERIVED]; `force` keyword-only, default `False` — intent.py:348 [DERIVED]
- out: `ProductIntent`, or `None` when no rule matched and `force` off — intent.py:368-370 [DERIVED]
- pre: none
- post: `force=True` with no rule ⇒ `rule="forced"`, `kind="forced"`, `source="forced"` — intent.py:370-371 [DERIVED]; `kind` falls back to `"find_products"` when falsy — intent.py:373 [DERIVED]; a follow-up inherits `seed`/`audience`/`geography` from the last user turn, message's own values win — intent.py:361-364 [DERIVED]

### search_terms_for — intent.py:313-325
- in: `seed`, `seed_kind`, `audience` (all `str | None`)
- out: deduped tuple (`dict.fromkeys`), truncated to `MAX_TERMS`, each term `len >= 2` — intent.py:325 [DERIVED]
- post: seed with `seed_kind != "product"` gets `" products"` appended — intent.py:318 [DERIVED]; audience-only path emits `"<root> products"` and `"<root> accessories"` — intent.py:324 [DERIVED]

### ProductIntent.as_dict — intent.py:194-197
- out: keys `contract`, `kind`, `rule`, `seed`, `seed_kind`, `audience`, `geography`, `search_terms`, `source`; `vetoed` is omitted — intent.py:195-197 [DERIVED]

## effect surface
- None. Docstring: `Pure: no I/O.` — intent.py:27 [DERIVED]; `tables_read`/`tables_written` empty (FACTS). No env flags, no network, no files, no subprocess.

## invariants
INVARIANT: len(KINDS) = 7 — `("sell", "dropship", "suppliers", "product_ideas", "find_products", "follow_up", "forced")` — intent.py:36 [DERIVED]
  fails-if: receipt `kind` values appear that receivers of `as_dict` do not know.
INVARIANT: len(search_terms_for(...)) <= MAX_TERMS = 3 — intent.py:37, intent.py:325 [DERIVED]
  fails-if: CJ fallback searches exceed 3 per intent.
INVARIANT: len(_phrase(...)) <= MAX_PHRASE_TOKENS = 5 — intent.py:38, intent.py:236 [DERIVED]
  fails-if: seed/audience/niche phrases absorb unrelated trailing words.
INVARIANT: follow-up fires only when word count <= FOLLOW_UP_MAX_WORDS = 14 AND `_DEICTIC` AND `_FOLLOW_UP_WORDS` match — intent.py:39, intent.py:345 [DERIVED]
  fails-if: long or non-deictic messages get misclassified as follow-ups.
INVARIANT: STRONG rules (`sell_object`, `dropship_object`, `supplier_request`) always return vetoed = [] — intent.py:214-219 [DERIVED]
  fails-if: a knowledge veto suppresses an explicit first-person selling/sourcing request.
INVARIANT: detect returns None iff rule is None and force is False — intent.py:368-371 [DERIVED]
  fails-if: non-product messages enter product mode (or product messages get dropped).
INVARIANT: STRONG rules are tested before VETOABLE rules — intent.py:214-228 [DERIVED]
  fails-if: a vetoable pattern shadows a strong match and gets wrongly vetoed.

## determinism & idempotency
determinism: DETERMINISTIC (regex + dict lookups only; no clock/random/db/network — intent.py:27 [DERIVED])
idempotency: SAFE (pure functions, frozen result dataclass — intent.py:181, intent.py:27 [DERIVED])

## failure behaviour
- No try/except anywhere; the failure signal is `detect` returning `None` — intent.py:368-370 [DERIVED]. No error codes raised.
- `_last_user_turn` tolerates object-or-dict turns and empty history by returning `None` — intent.py:328-334 [DERIVED].
- `detect` never raises for non-string history content; `str(content or "")` coerces — intent.py:331-332 [DERIVED].

## dumb-code flags
- Magic number `[:6]` (max words per CJ term) and `[:60]` (char clip) in `_clip_term` — intent.py:309-310 [DERIVED].
- Magic threshold `len(t) >= 2` (min term length) — intent.py:325 [DERIVED].
- Supplier-noun list `suppliers?|vendors?|manufacturers?|wholesalers?` duplicated in `_SUPPLIER`, `_SEED_AFTER`, `_FOLLOW_UP_WORDS` — intent.py:58, intent.py:265, intent.py:102 [DERIVED].
- `_PEOPLE` and `_AUDIENCE_ROOT` keys overlap heavily; a `_PEOPLE` word absent from `_AUDIENCE_ROOT` yields root `""` via `.get(..., "")` and no terms — intent.py:125-138, intent.py:140-153, intent.py:322 [DERIVED].
- Kind `"dropship"` is produced by two different rules (`dropship_object`, `dropship_noun`) — intent.py:214, intent.py:222 [DERIVED].
- `_NOT_GEO_AFTER` guards `american` without a trailing-noun lookahead, but `british`/`english`/`german`/`french` require one — intent.py:166-172 [DERIVED].
- Redundant guard `_tokens(seed)[-1:] != []` — `seed` is already truthy from `_clean_seed`, so the slice is never empty — intent.py:285-287 [INFERRED: `seed` passed the `if seed and` check and `_clean_seed` joins a non-empty word list].

## refactor notes
- `CONTRACT = "product-intent-v1"` is emitted in every receipt via `as_dict` — intent.py:35, intent.py:195; changing it breaks downstream receipt consumers.
- Rule names (`sell_object`, `dropship_object`, `supplier_request`, `product_ideas`, `dropship_noun`, `request_products`, `terse_products`, `follow_up`, `forced`) are receipt vocabulary per the docstring ("each named in the receipt as `rule`") — intent.py:14, intent.py:214-223, intent.py:370.
- `KINDS` is an external enum — intent.py:36.
- Blast radius: `service.py` and `_small-modules` import this module (FACTS.importers); signature changes to `detect`/`search_terms_for`/`ProductIntent` must update both.
- The keyword-only `force` gate mirrors POST /product/search semantics — intent.py:348-349.

## VERIFY
```verify
grep -Fq 'CONTRACT = "product-intent-v1"' shared/polymath_shared/product_search/intent.py
grep -Fq 'FOLLOW_UP_MAX_WORDS = 14' shared/polymath_shared/product_search/intent.py
grep -Fq '@dataclass(frozen=True)' shared/polymath_shared/product_search/intent.py
grep -Fq 'def detect(message: str, history: Iterable[Any] | None = None, *, force: bool = False) -> ProductIntent | None:' shared/polymath_shared/product_search/intent.py
grep -Eq 'tuple\(dict\.fromkeys\(t for t in terms if len\(t\) >= 2\)\)\[:MAX_TERMS\]' shared/polymath_shared/product_search/intent.py
test "$(grep -c -F 'dropship' shared/polymath_shared/product_search/intent.py)" -ge 5
! grep -Fq 'import requests' shared/polymath_shared/product_search/intent.py
```
