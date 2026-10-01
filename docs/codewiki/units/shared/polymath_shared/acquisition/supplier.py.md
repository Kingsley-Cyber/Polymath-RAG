# unit: shared/polymath_shared/acquisition/supplier.py
anchor: shared/polymath_shared/acquisition/supplier.py:1-164

## purpose
Read-only supplier lookup tools (`supplier_search`, `supplier_product`, `supplier_freight`, `supplier_warehouses`) for any harness connected to Polymath's MCP servers, owner-approved 2026-09-27 — owner only, because they spend the owner's CJ account and quota; a principal key is refused. shared/polymath_shared/acquisition/supplier.py:1-3 [DERIVED]
Search covers CJ's catalogue (source "cj") or alibaba.com pages via local SearXNG (source "alibaba"); product/freight/warehouses are CJ-only. Built on `cj_api` and `searxng`, never CJ's own MCP server; nothing creates, confirms, pays, deletes, lists or disputes; no host-browser fallback; keys come from the environment only and never reach a result, error or log. shared/polymath_shared/acquisition/supplier.py:5-14 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| authorize | def | (principal_id: str \| None) -> None | shared/polymath_shared/acquisition/supplier.py:43-46 | internal: search:79, product:113, freight:134, warehouses:155 |
| search | def | keyword-only (principal_id, query, source="cj", limit=SEARCH_LIMIT_DEFAULT, env=None, cj=None, alibaba=None) -> dict | shared/polymath_shared/acquisition/supplier.py:75-77 | orchestrator/orchestrator/api/acquisition.py (module importer, FACTS) |
| product | def | keyword-only (principal_id, product_id, env=None, cj=None) -> dict | shared/polymath_shared/acquisition/supplier.py:110-111 | orchestrator/orchestrator/api/acquisition.py (module importer, FACTS) |
| freight | def | keyword-only (principal_id, variant_id, country, quantity=1, from_country="CN", env=None, cj=None) -> dict | shared/polymath_shared/acquisition/supplier.py:131-132 | orchestrator/orchestrator/api/acquisition.py (module importer, FACTS) |
| warehouses | def | keyword-only (principal_id, env=None, cj=None) -> dict | shared/polymath_shared/acquisition/supplier.py:153 | orchestrator/orchestrator/api/acquisition.py (module importer, FACTS) |
| CONTRACT | const | "supplier-tools-v1" | shared/polymath_shared/acquisition/supplier.py:32 | — |
| SOURCES | const | {"cj": (cj_api.SITE, "cj_listings"), "alibaba": (searxng.SITE, "alibaba_listings")} | shared/polymath_shared/acquisition/supplier.py:34 | search:87 |
| TOOLS | const | ("supplier_search", "supplier_product", "supplier_freight", "supplier_warehouses") | shared/polymath_shared/acquisition/supplier.py:35 | no use in this file |

## contracts

**authorize(principal_id)** — shared/polymath_shared/acquisition/supplier.py:43-46
- in: `principal_id: str | None`.
- post: returns None when `principal_id is None`; otherwise raises `AcquisitionRefused(403, "OWNER_ONLY", "the supplier tools use the owner's CJ account and quota; a principal key may not use them")`. shared/polymath_shared/acquisition/supplier.py:45-46 [DERIVED]

**search(...)** — shared/polymath_shared/acquisition/supplier.py:75-107
- pre: authorize (79); `source` must be in `SOURCES` else 422 `UNKNOWN_SOURCE` (80-81); query normalized via `service._query` (82); `n = max(1, min(int(limit if limit is not None else SEARCH_LIMIT_DEFAULT), SEARCH_LIMIT_MAX))`, TypeError/ValueError → 422 `BAD_LIMIT` (83-86). [DERIVED]
- in: `Target(operation="listings", reader="cj_listings"|"alibaba_listings", site, query=q, source_class="supplier_listing")` (87-88); cj → `cj_api.CJListings(cj or cj_api.client_from_env(env))` (89-92); alibaba → `alibaba or searxng.SearXNGListings(searxng.base_url(env))` (93-96). [DERIVED]
- out: `{contract, tool: "supplier_search", source, site, query, retrieved_at, status, sources, items, completeness, limitations}` — body from `service.shape(t, raw, action={}, search_intent_id=None, retrieved_at=..., used=0, cap=0, limit=n)` (104-107). [DERIVED]
- post: reader is None → `raw = {"state": "unavailable", "note": NO_CJ_KEY|NO_SEARXNG}` (97-98); `ApiFailed` → note `"the {reader.label} could not answer ({exc.reason}: {exc.detail})"` (102-103). [DERIVED]

**product(...)** — shared/polymath_shared/acquisition/supplier.py:110-128
- pre: authorize (113); `product_id` validated by `cj_api.valid_id` else 422 `BAD_ID` ("6 to 64 letters, digits and hyphens") (114, 53-57). [DERIVED]
- post: no client → `UNAVAILABLE` + `NO_CJ_KEY` (116-117); `ApiFailed` → `UNAVAILABLE` with reason (120-121); `client.product(pid)` returns None → `status: "NOT_FOUND"`, `product: None`, `variants: []` (122-124). [DERIVED]
- out: OK → `{**head, product_id, retrieved_at: now_iso(), status: "OK", **cj_api.product_view(data), limitations: [CJ-api note, UNTRUSTED]}` (125-128). [DERIVED]

**freight(...)** — shared/polymath_shared/acquisition/supplier.py:131-150
- pre: authorize (134); `variant_id` via `_id` else `BAD_ID` (135); `country`/`from_country` via `_country` else 422 `BAD_COUNTRY` (136); `quantity` must be int, not bool, `1 <= quantity <= QUANTITY_MAX` else 422 `BAD_QUANTITY` (137-138). [DERIVED]
- in: `request = {"variant_id", "from_country", "to_country", "quantity"}` (139); `client.freight(vid, to, quantity, start)` (144). [DERIVED]
- post: no client → `UNAVAILABLE` + `NO_CJ_KEY` (141-142); `ApiFailed` → `UNAVAILABLE` (145-146); empty options → `status: "EMPTY"` plus limitation `"CJ offers no shipping option for this variant from {start} to {to}"` (147, 150). [DERIVED]
- out: `{**head, request, retrieved_at, status "OK"|"EMPTY", options: [cj_api.freight_view(o)...], limitations}` (147-150). [DERIVED]

**warehouses(...)** — shared/polymath_shared/acquisition/supplier.py:153-164
- pre: authorize (155). [DERIVED]
- post: no client → `UNAVAILABLE` + `NO_CJ_KEY` (157-158); `ApiFailed` → `UNAVAILABLE` (161-162). [DERIVED]
- out: `{**head, retrieved_at, status "OK"|"EMPTY", warehouses: [cj_api.warehouse_view(w)...], limitations: ["CJ's warehouse list from the CJ Dropshipping API"]}` (163-164). [DERIVED]

## effect surface
- Network (CJ REST API via `cj_api.CJClient`): `client.product(pid)` shared/polymath_shared/acquisition/supplier.py:119, `client.freight(...)` :144, `client.warehouses()` :160, `reader.read(t, n)` :101 [DERIVED]
- Network (SearXNG): `searxng.SearXNGListings(url)` :95, read at :101 [DERIVED]
- Env: `CJ_API_KEY` via `cj_api.client_from_env` :90 (absence → `NO_CJ_KEY` :37); `SEARXNG_URL` via `searxng.base_url` :94 (off → `NO_SEARXNG` :38); `env=None` falls back to `os.environ` :49-50 [DERIVED]
- Postgres: none (`tables_read: []`, `tables_written: []` in FACTS); Qdrant, files, subprocess: none visible in SOURCE [DERIVED]

## invariants
INVARIANT: authorize calls per public tool = 1 — search:79, product:113, freight:134, warehouses:155; `principal_id is not None` → 403 `OWNER_ONLY` :46 — shared/polymath_shared/acquisition/supplier.py:79-155 [DERIVED]
  fails-if: a friend's principal key spends the owner's CJ account and quota.
INVARIANT: n = max(1, min(int(limit), 50)); SEARCH_LIMIT_MAX = 50, SEARCH_LIMIT_DEFAULT = 10 — shared/polymath_shared/acquisition/supplier.py:36,84 [DERIVED]
  fails-if: limit=0 silently becomes 1; non-numeric limit raises 422 `BAD_LIMIT` :86.
INVARIANT: 1 <= quantity <= 10000 and isinstance(quantity, int) and not isinstance(quantity, bool) — QUANTITY_MAX = 10000 — shared/polymath_shared/acquisition/supplier.py:36,137 [DERIVED]
  fails-if: 422 `BAD_QUANTITY` :138 (bool check needed because bool subclasses int).
INVARIANT: country and from_country match `[A-Za-z]{2}` fullmatch and return uppercased — shared/polymath_shared/acquisition/supplier.py:40,62-64 [DERIVED]
  fails-if: 422 `BAD_COUNTRY` :63.
INVARIANT: every returned dict has contract == "supplier-tools-v1" — shared/polymath_shared/acquisition/supplier.py:32,68,105 [DERIVED]
  fails-if: MCP consumers that version-dispatch on `contract` break.
INVARIANT: product status ∈ {"OK", "NOT_FOUND", "UNAVAILABLE"}; freight/warehouses status ∈ {"OK", "EMPTY", "UNAVAILABLE"} — shared/polymath_shared/acquisition/supplier.py:123,126,147,163 [DERIVED]
  fails-if: callers switching on `status` hit an unhandled value.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: reader.read :101, client.product :119, client.freight :144, client.warehouses :160; clock: `now_iso()` :72,104,126,147,163; env: `client_from_env` :90,115,140,156, `searxng.base_url` :94)
idempotency: SAFE (read-only lookups; "Nothing here creates, confirms, pays, deletes, lists or disputes" shared/polymath_shared/acquisition/supplier.py:12)

## failure behaviour
- `ApiFailed` from any reader/client is swallowed and converted to a normal dict with `status: "UNAVAILABLE"` and the reason in `limitations` — the caller never sees the exception. shared/polymath_shared/acquisition/supplier.py:102-103,120-121,145-146,161-162 [DERIVED]
- Missing config returns UNAVAILABLE, not an error: no `CJ_API_KEY` → `NO_CJ_KEY` (:37, :117, :142, :158); SearXNG off → `NO_SEARXNG` (:38, :98). [DERIVED]
- CJ returns no product → `NOT_FOUND` dict with `product: None`, `variants: []`. shared/polymath_shared/acquisition/supplier.py:122-124 [DERIVED]
- Raised error codes: 403 `OWNER_ONLY` :46; 422 `BAD_ID` :56; 422 `BAD_COUNTRY` :63; 422 `UNKNOWN_SOURCE` :81; 422 `BAD_LIMIT` :86; 422 `BAD_QUANTITY` :138. [DERIVED]

## dumb-code flags
- `TOOLS` (:35) is defined but never referenced in this file — dead here unless an importer reads it. shared/polymath_shared/acquisition/supplier.py:35 [DERIVED]
- `_head` hardcodes `"source": "cj"` (:68) while `search` builds its own header dict (:105) — two places construct the contract header. shared/polymath_shared/acquisition/supplier.py:68,105 [DERIVED]
- `UNTRUSTED` (:39) is appended only by `product` (:128); search/freight/warehouses limitations (:107, :148-150, :164) carry no untrusted-text note despite the blanket claim at :39. shared/polymath_shared/acquisition/supplier.py:39,128 [DERIVED]
- `_COUNTRY` is just `[A-Za-z]{2}` (:40) but the error text claims "ISO 3166-1 alpha-2" (:63) — any 2-letter pair (e.g. "ZZ") passes. shared/polymath_shared/acquisition/supplier.py:40,63 [INFERRED] (regex cannot check ISO membership)
- `BAD_ID` message hardcodes the rule prose "6 to 64 letters, digits and hyphens" (:56) while enforcement lives in `cj_api.valid_id` (:54) — the rule can drift from its description. shared/polymath_shared/acquisition/supplier.py:54-56 [DERIVED]
- Magic default `from_country: str = "CN"` (:131); `quantity: int = 1`. shared/polymath_shared/acquisition/supplier.py:131 [DERIVED]

## refactor notes
- The dict keys in each docstring (:78, :112, :133, :154) plus `CONTRACT = "supplier-tools-v1"` (:32) are the wire format for MCP harnesses; renaming any key or the contract string breaks consumers. shared/polymath_shared/acquisition/supplier.py:32,78,112,133,154 [DERIVED]
- `SOURCES` reader names `"cj_listings"` / `"alibaba_listings"` (:34) must stay valid for `service.shape`'s reader registry (used via `Target` at :87-88, shaped at :104). [DERIVED]
- Private cross-module import `_query` from `polymath_shared.acquisition.service` (:24-30) — renaming it in service breaks this file. shared/polymath_shared/acquisition/supplier.py:24-30 [DERIVED]
- Sole known importer: orchestrator/orchestrator/api/acquisition.py (FACTS.importers) — the likely MCP exposure layer; any signature change (all params are keyword-only) ripples there. [DERIVED]
- `shape(t, raw, action={}, search_intent_id=None, used=0, cap=0, limit=n)` (:104) couples to `service.shape`'s signature. shared/polymath_shared/acquisition/supplier.py:104 [DERIVED]
- Keys-never-logged / no-browser-fallback (:12-14) is a stated property; refactors that log env or raw errors violate it. shared/polymath_shared/acquisition/supplier.py:12-14 [DERIVED]

## VERIFY
```verify
grep -Fq 'CONTRACT = "supplier-tools-v1"' shared/polymath_shared/acquisition/supplier.py
grep -Fq 'SEARCH_LIMIT_DEFAULT, SEARCH_LIMIT_MAX, QUANTITY_MAX = 10, 50, 10000' shared/polymath_shared/acquisition/supplier.py
grep -Fq 'raise AcquisitionRefused(403, "OWNER_ONLY"' shared/polymath_shared/acquisition/supplier.py
grep -Fq 'from_country: str = "CN"' shared/polymath_shared/acquisition/supplier.py
grep -Fq '"status": "OK" if options else "EMPTY"' shared/polymath_shared/acquisition/supplier.py
test "$(grep -c -F 'AcquisitionRefused(422' shared/polymath_shared/acquisition/supplier.py)" -ge 5
! grep -Fq 'subprocess' shared/polymath_shared/acquisition/supplier.py
```
