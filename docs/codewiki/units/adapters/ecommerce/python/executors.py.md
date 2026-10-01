# unit: adapters/ecommerce/python/executors.py
anchor: adapters/ecommerce/python/executors.py:1-879

## purpose
Deterministic transform/gate executors for the `python.*` graph nodes: lens gating, gap compilation, query compilation, observation curation, supplier normalization, scoring — everything here must be reproducible from state + registry + policies alone; no LLM calls, ever. adapters/ecommerce/python/executors.py:1-6 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| load_lenses | def | () -> dict | 25-27 [DERIVED] | lens_gate (59) |
| load_csv | def | (name: str) -> list[dict] | 30-32 [DERIVED] | — |
| lens_gate | def | (state, policies) -> str | 53-66 [DERIVED] | — |
| signal_gate | def | (state, policies) -> str | 70-78 [DERIVED] | — |
| structural_lookup | def | (state, policies) -> str | 81-125 [DERIVED] | — |
| triage | def | (state, policies) -> str | 169-189 [DERIVED] | — |
| channel_queries | def | (gid, question, state, policies, id_prefix="q", short=None) -> list[dict] | 295-318 [DERIVED] | gap_compiler (351) |
| gap_compiler | def | (state, policies) -> str | 321-361 [DERIVED] | — |
| comments | def | (state, policies) -> str | 365-427 [DERIVED] | — |
| sourcing_plan_compiler | def | (state, policies) -> str | 495-519 [DERIVED] | — |
| sourcing_coverage | def | (state) -> list[dict] | 543-554 [DERIVED] | supplier (538), scoring (642) |
| supplier | def | (state, policies) -> str | 557-590 [DERIVED] | — |
| scoring | def | (state, policies) -> str | 594-648 [DERIVED] | — |
| join_leads | def | (mech, d, pol) -> list[dict] | 651-674 [DERIVED] | scoring (615), governed binding (652-653) |
| interleave_leads | def | (leads) -> list | 677-693 [DERIVED] | scoring (620) |
| apply_evaluations | def | (state, policies) -> ? | 730-732 [DERIVED] | — (body beyond line 662 not in excerpt) |
| frontier_gate | def | (state, policies) -> ? | 736-743 [DERIVED] | — (body not shown) |
| voi_gate | def | (state, policies) -> ? | 746-756 [DERIVED] | — (body not shown) |
| portfolio_gate | def | (state, policies) -> ? | 759-774 [DERIVED] | — (body not shown) |
| discovery_loop_gate | def | (state, policies) -> ? | 777-800 [DERIVED] | — (body not shown) |
| loadout_ready | def | (state, policies) -> ? | 803-842 [DERIVED] | — (body not shown) |

## contracts

**lens_gate** — 53-66
- in: `state["data"]["signal"]` + each `corpus_evidence` item's `summary` or `text`, lowercased — 55-57
- pre: `registry/lenses.yaml` readable — 26
- out: writes `state["data"]["lenses"] = [{"name", "question"}]` — 61, 65
- post: at least 1 lens; empty selection falls back to `"minimal-interference"` — 62-64

**signal_gate** — 70-78
- in: `state["data"]["primitives"]` — 73-74
- out: sets `state["verdict"] = "NO_GENERATIVE_SIGNAL"` when no `generative_signal`; only the edge routes on it — 74-76

**structural_lookup** — 81-125
- pre: `require_invariant_for_transfer` (default `True`) and no `transferable_invariants` → writes `[]`, skips — 86-88
- out: `state["data"]["cross_domain_analogies"] = registry hits + corpus hits`, total capped at `max_cross_domain_analogies` default `8` — 117-123

**triage** — 169-189
- in: hypotheses with status `WORKING_HYPOTHESIS`/`WORKING_ANALOGY`/`CHALLENGED` — 173-174
- out: `research_priority` = min(falsifiers,2)+min(gaps,2)+alternatives+exploratory; keeps top `max_research_ready` (default `3`) with priority ≥ `min_priority` (default `2`); rest → `HOLD` — 176-188

**channel_queries** — 295-318
- out: one query dict per channel enabled in `policies.evidence_channels` (default: all 8 template order: reddit, amazon_reviews, youtube, tiktok, instagram, xiaohongshu, twitter, forum) — 201-254, 303-305
- each row carries `tools`, `identity`, `freshness_hint`, `where`, `collect`, optional `law`/`limits`, and fixed `cannot_satisfy = ["SUPPLIER_AVAILABILITY", "PRICE_EVIDENCE", "MOQ_EVIDENCE", "CURRENT_PRODUCT_REFERENCE"]` — 311-317
- `short` defaults to first 6 gap keywords; governed runs pass a precompiled `short` — 300-301, 297-299

**gap_compiler** — 321-361
- pre: hypotheses with status `REJECTED`/`HOLD` skipped — 326-327
- out: gap id = `stable_id("gap", h["id"], gap_q)`; `required_freshness = ["LIVE"]` for genesis `TREND_LED`/`SHIFT_LED`, else `["FAST", "LIVE"]`; up to 6 `registry_query_grammars` attached — 329, 333-338, 347-350
- post: `queries` interleaved via `allocation.interleave_queries`; `research_allocation` stored — 355-358

**comments** — 365-427
- dedupe key: (`quote_ref` lowercased, or `stable_id("obs", source, problem)`, `gap_id`) — 386-387
- gap closure: `contradicted` when against > support; `supported` when independent groups ≥ `policies["evidence"]["min_independent_sources"]`, with `required_freshness` and role filters enforced — 398-415
- post: `state["rounds"]["research"] += 1`; satisfaction + allocation recomputed — 417-422

**supplier** — 557-590
- listing key: (`concept_id`, `url`, `product_name` lower, `supplier_name` lower); twins fill missing `price_raw`/`moq_raw` into the survivor — 563-571
- out: parsed `price_usd_low/high`, `moq_units`; channel MOQ default via `policies.supplier.moq_default_by_channel` with `moq_note`; `_resolve_concept` stamps `concept_id` only on a unique name match — 572-579

**scoring** — 594-648
- verdict `NO_DEFENSIBLE_BRIDGE` when no `SUPPORTED` mechanisms, coverage missing, or observations < `min_total_observations` — 600-606
- score = support count + `purchase_language_bonus` × purchase-language observations — 610-612
- out verdicts: `QUALIFIED_LEADS` / `PROVISIONAL_LEADS` / provenance echo (default `"CORPUS_ECHO_UNGROUNDED"`) / `MECHANISM_WITHOUT_SUPPLY` — 630-638

**join_leads** — 651-674
- filters: `require_price` → needs `price_usd_low`; `require_moq` → needs `moq_units`; `require_mechanism_fit` (default `True`) → `_supplier_fits` — 657-662

## effect surface
- file read: `adapters/ecommerce/registry/lenses.yaml` (`ROOT` = parent of `python/`, `REG = ROOT/registry`) — 20-21, 26 [DERIVED]
- file read: `adapters/ecommerce/registry/<name>` CSVs via `load_csv` — 31 [DERIVED]
- file read (via sibling module): `registry.load_snapshot()` — 90-91, 341-342, 372-373 [DERIVED]
- DB tables read/written: none (FACTS `tables_read`/`tables_written` empty)
- subprocess/network: none executed; `opencli`/`mcporter`/`curl`/`python3 sourcing_exa.py` strings are template data only — 205-254, 487-492 [DERIVED]
- env flags read: none in shown lines 1-662 (`os` used only for paths) — 20-21 [DERIVED]
- state mutation: `state["data"]` keys `lenses`, `cross_domain_analogies`, `gaps`, `queries`, `research_allocation`, `observations`, `sourcing_plan`, `supplier_candidates`, `sourcing_coverage`, `leads`, `utilization`; `state["verdict"]`; `state["rounds"]["research"]` — 65, 123, 338-358, 392, 417, 518, 580-581, 603, 624, 644 [DERIVED]

## invariants
INVARIANT: len(registry hits) + len(corpus hits) ≤ `max_cross_domain_analogies` default `8` — 117, 122 [DERIVED]
  fails-if: corpus analogies get budget `8 - len(hits)`; a raised cap without touching both callsites over/under-fills the list.
INVARIANT: kept triage set ≤ `max_research_ready` default `3` AND each kept `research_priority` ≥ `min_priority` default `2` — 183-184 [DERIVED]
  fails-if: hypotheses below the floor are held and never get research budget.
INVARIANT: gap `supported` only when `independence_groups(support) >= policies["evidence"]["min_independent_sources"]` — 393, 412-415 [DERIVED]
  fails-if: three URLs from one author would close a gap (the exact bug the comment describes).
INVARIANT: gap `contradicted` only when `len(against) > len(support)` — 413-414 [DERIVED]
INVARIANT: `lens_gate` result length ≥ 1 (fallback name `"minimal-interference"`) — 62-64 [DERIVED]
  fails-if: run proceeds lens-less if the fallback key is removed from lenses.yaml.
INVARIANT: `_parse_moq` returns `int > 0` or `None`; never parses a decimal or `$`-containing string — 462-474 [DERIVED]
INVARIANT: `_parse_price` returns `(None, None)` on any non-USD marker (`¥€£₹₩`, `A$/C$/HK$/NZ$/S$`, RMB/CNY/EUR/…); an explicit `US$`/`USD` amount always wins — 436-440, 448-453 [DERIVED]
INVARIANT: lead requires `price_usd_low` (when `require_price`) and `moq_units` (when `require_moq`) — 657-660 [DERIVED]
INVARIANT: final leads length ≤ `min(effective max_leads, pol max_leads + 2)` — 622-624 [DERIVED]
INVARIANT: one sourcing job per concept × channel; concepts never borrow listings — 495-499, 510-517 [DERIVED]
INVARIANT: corpus analogies only from rows with non-`None`, non-`IRRELEVANT` `row_relevance` (fail-closed) — 140-143 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC (module contract "reproducible from state + registry + policies alone… No LLM calls, ever" — 3-5; shown lines 1-662 use only re/csv/yaml/unicodedata over inputs) [DERIVED]
idempotency: UNSAFE (comments increments `state["rounds"]["research"] += 1` each call — 417; supplier mutates the surviving row's `price_raw`/`moq_raw` in place from twins — 567-571)

## failure behaviour
- `structural_lookup`: `import registry`/`load_snapshot()` wrapped in `except Exception` → `snap = None` → returns `"no registry snapshot — structural pass skipped"`, analogies `[]` — 89-96 [DERIVED] (FACTS fallback line 92)
- `gap_compiler`: snapshot failure → `_grammars = []` → gaps carry no `registry_query_grammars` — 340-346 [DERIVED] (FACTS fallback line 345)
- `comments`: snapshot failure → `_lex = set()` → no `lexicon_flags` emitted — 371-376 [DERIVED] (FACTS fallback line 375)
All three swallow into defaults; the caller sees a normal `str` return, never an exception.

## dumb-code flags
- `_MOQ = _MOQ_UNIT` legacy alias "kept for callers that imported the old name" — 443 [DERIVED]
- `SOURCING_SITES` declares `"1688": "1688.com"` but `_SOURCING_TOOLS` has no `"1688"` key → a 1688 channel job gets `tools: []` — 485-492, 513 [DERIVED]
- two overlapping hand-rolled stopword sets `_CQ_STOP` and `_GAP_STOP` — 128-129, 259-262 [DERIVED]
- `score` computed before the `min_mechanism_support` guard discards the mechanism — 610-614 [DERIVED]
- magic slack `pol["supplier"]["max_leads"] + 2` in the lead cap — 624 [DERIVED]
- `len(plan)//max(1,len(channels))` assumes a uniform concept×channel grid — 519 [DERIVED]
- scattered truncation literals: `kw[:6]`, `hints[:6]`, `terms[:8]`, `[:5]` quotes, `[:4]` lexicon flags, `[:6]` grammars — 301, 310, 513, 617, 382, 350 [DERIVED]

## refactor notes
- `join_leads` is called by both standalone `scoring` and the governed binding — its params/return shape are a two-caller contract — 615, 651-654 [DERIVED]
- `channel_queries(short=...)` is the governed-run hook from `query_semantics.py`; changing the `kw[:6]` default changes every emitted search string — 297-301 [DERIVED]
- verdict literals (`NO_GENERATIVE_SIGNAL`, `NO_DEFENSIBLE_BRIDGE`, `QUALIFIED_LEADS`, `PROVISIONAL_LEADS`, `CORPUS_ECHO_UNGROUNDED`, `MECHANISM_WITHOUT_SUPPLY`) are the graph's routing contract — 75, 603, 630-638 [DERIVED]
- lens fallback key `"minimal-interference"` must exist in `registry/lenses.yaml` — 63-64 [DERIVED]
- "independent" is defined once in `verifiers.independence_groups`; gap closure and coverage must keep sharing it — 408-412 [DERIVED]
- sibling modules (`registry`, `allocation`, `satisfaction`, `settings`, `provenance`, `candidates`, `utilization`) are imported inside function bodies — 90, 341, 355, 418, 621, 629, 639, 643; hoisting to top level may create import cycles [INFERRED: in-function imports usually exist to break cycles]
- `_MOQ` alias removal breaks any external caller still importing the old name — 443 [DERIVED]

## VERIFY
```verify
grep -Fq 'No LLM calls, ever' adapters/ecommerce/python/executors.py
grep -Fq '_MOQ = _MOQ_UNIT' adapters/ecommerce/python/executors.py
grep -Fq 'minimal-interference' adapters/ecommerce/python/executors.py
grep -Fq 'CORPUS_ECHO_UNGROUNDED' adapters/ecommerce/python/executors.py
grep -Fq '"max_cross_domain_analogies", 8' adapters/ecommerce/python/executors.py
grep -Fq 'state["rounds"]["research"] += 1' adapters/ecommerce/python/executors.py
test "$(grep -c -F 'except Exception' adapters/ecommerce/python/executors.py)" -ge 3
```
