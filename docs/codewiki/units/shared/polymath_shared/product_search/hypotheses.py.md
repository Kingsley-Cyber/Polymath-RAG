# unit: shared/polymath_shared/product_search/hypotheses.py
anchor: shared/polymath_shared/product_search/hypotheses.py:1-353

## purpose
Steers a PRODUCT SEARCH turn end to end: injects hypothesis-material retrieval (frictions, workarounds, unmet jobs) into a compiled plan or raw query text (`steer_plan`/`steer_text`), appends the PRODUCT HYPOTHESIS contract to the synthesis prompt (`contract_block`), and reads the answer's fenced `product-hypotheses` JSON block back into normalized hypotheses plus clean answer text (`parse_block`) — shared/polymath_shared/product_search/hypotheses.py:4-16 [DERIVED]. Imported by `orchestrator/orchestrator/api/product_report.py` and `shared/polymath_shared/product_search/service.py` (FACTS.importers). Pure: no I/O — shared/polymath_shared/product_search/hypotheses.py:17 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `aspects_for` | def | (intent) -> list[tuple[str, str, str]] | shared/polymath_shared/product_search/hypotheses.py:54-73 | — |
| `steer_plan` | def | (plan, intent) -> (plan, dict[str, Any]) | shared/polymath_shared/product_search/hypotheses.py:76-124 | product_report.py, service.py* |
| `steer_text` | def | (query: str, intent) -> tuple[str, dict[str, Any]] | shared/polymath_shared/product_search/hypotheses.py:127-133 | product_report.py, service.py* |
| `contract_block` | def | (intent) -> str | shared/polymath_shared/product_search/hypotheses.py:137-165 | product_report.py, service.py* |
| `HypothesisParse` | dataclass | fields status, reason=None, hypotheses=[], clean_text="", notes=[], tags_dropped=0 | shared/polymath_shared/product_search/hypotheses.py:170-178 | product_report.py, service.py* |
| `HypothesisParse.receipt` | method | () -> dict[str, Any] | shared/polymath_shared/product_search/hypotheses.py:180-182 | product_report.py, service.py* |
| `normalize` | def | (items: Any, legend: set[str] | None = None) -> tuple[list[dict[str, Any]], int] | shared/polymath_shared/product_search/hypotheses.py:286-309 | product_report.py, service.py* |
| `parse_block` | def | (answer_text: str, legend_tags=None) -> HypothesisParse | shared/polymath_shared/product_search/hypotheses.py:322-352 | product_report.py, service.py* |
| `CONTRACT_NAME`, `BLOCK_LABEL`, `STEER_RULE`, `ASPECT_IDS`, `ASPECT_WEIGHT`, `MAX_HYPOTHESES`, `MAX_TERMS`, `CONFIDENCE` | const | :38-46 | shared/polymath_shared/product_search/hypotheses.py:38-46 | — |

\* FACTS lists importers per module, not per symbol.

## contracts

**steer_plan(plan, intent)** — shared/polymath_shared/product_search/hypotheses.py:76-124
- in: compiled plan (`.queries`, optional `.facets`, optional dict `.compiler`); intent read defensively via `getattr(intent, "audience"/"seed", None)` — shared/polymath_shared/product_search/hypotheses.py:50-51 [DERIVED]
- pre: none; a plan that would not retrieve is forced to via `plan_for_evidence_route(plan, override_rule=STEER_RULE)` with `retrieval_override: not retrieving` in the receipt — shared/polymath_shared/product_search/hypotheses.py:81-84 [DERIVED]
- out: aspect queries appended with `weight=ASPECT_WEIGHT` (0.85), `origin="USER"`, `role="complement"`, ids from unused `ASPECT_IDS` (`ps1..ps3`); receipt keys `mode="plan"`, `subject{audience, seed}`, `added`, `replaced`, `facets_added`, `facets_dropped`, `retrieval_override` — shared/polymath_shared/product_search/hypotheses.py:83-84, 99-105 [DERIVED]
- post: `len(plan.queries) <= cap` where `cap = MAX_QUERIES_FACETS if plan.facets else MAX_QUERIES`; room made by dropping lowest-weight non-PRIMARY USER queries (sort key `(q.weight, -position)`), q0 never touched; every kept facet has `query_ids`; receipt written to `plan.compiler["product_search"]` when compiler is a dict — shared/polymath_shared/product_search/hypotheses.py:77-78, 85, 91-96, 119-123 [DERIVED]

**steer_text(query, intent)** — shared/polymath_shared/product_search/hypotheses.py:127-133
- out: `"{query} {subject} frustrations, workarounds and unmet needs"` (subject-less literal when no audience/seed); receipt `mode="text"` — shared/polymath_shared/product_search/hypotheses.py:130-132 [DERIVED]

**contract_block(intent)** — shared/polymath_shared/product_search/hypotheses.py:137-165
- in: intent (audience, seed, geography via `getattr`) — shared/polymath_shared/product_search/hypotheses.py:139-140 [DERIVED]
- out: contract text embedding `CONTRACT_NAME`, demanding 3–5 labelled hypotheses with [S#] citations, ending with exactly one fenced `product-hypotheses` JSON block (fields title/problem/audience/evidence_tags/search_terms/confidence) — shared/polymath_shared/product_search/hypotheses.py:143-165 [DERIVED]

**parse_block(answer_text, legend_tags=None)** — shared/polymath_shared/product_search/hypotheses.py:322-352
- pre: `legend_tags` = the turn's [S#] tags; `None` keeps every tag — shared/polymath_shared/product_search/hypotheses.py:323-326 [DERIVED]
- out: status `ok` (clean labelled block) | `drifted` (repair/label drift/unclosed fence/unfenced array) | `fallback` with reason `unparseable` | `no_hypotheses` | `no_block`; search order: our-labelled fences last-first, then data-labelled fences, then a trailing unfenced `[{` array — shared/polymath_shared/product_search/hypotheses.py:171-172, 327-352 [DERIVED]
- post: `clean_text` = answer minus the block minus an announcing intro line (≤160 chars, trailing `---`-rule also stripped); tags outside legend dropped and counted in `tags_dropped` — shared/polymath_shared/product_search/hypotheses.py:265, 300-301, 312-319 [DERIVED]

**normalize(items, legend=None)** — shared/polymath_shared/product_search/hypotheses.py:286-309
- in: list of objects, or a wrapper dict unwrapped via keys `hypotheses|products|ideas|items|product_hypotheses` — shared/polymath_shared/product_search/hypotheses.py:289-291 [DERIVED]
- out: ≤ `MAX_HYPOTHESES` (5) records with keys `id` (`"h{n}"`), title ≤120, problem ≤400, audience ≤120, evidence_tags, search_terms ≤3 × ≤60 chars, `confidence` ∈ CONFIDENCE else `None`; an object without a title is dropped silently — shared/polymath_shared/product_search/hypotheses.py:45-46, 297-308 [DERIVED]

**aspects_for(intent)** — shared/polymath_shared/product_search/hypotheses.py:54-73
- out: 3 (label, query-type, text) rows picked by audience/seed presence (frictions MECHANISM / workarounds EXAMPLE / unmet_jobs or use_situations), each `_clean_query`-ed, skipped when `_has_instruction_tokens` — shared/polymath_shared/product_search/hypotheses.py:58-73 [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty) [DERIVED]
- Qdrant / files / network / subprocess / env flags: none — "Pure: no I/O." — shared/polymath_shared/product_search/hypotheses.py:17; imports are stdlib (`ast`, `json`, `re`, `dataclasses`, `typing`) plus `polymath_shared` only — shared/polymath_shared/product_search/hypotheses.py:20-36 [DERIVED]

## invariants
INVARIANT: len(normalize(...)[0]) ≤ MAX_HYPOTHESES = 5 — shared/polymath_shared/product_search/hypotheses.py:43, 307-308 [DERIVED]
  fails-if: extra hypotheses overflow the product-search-v1 record set downstream.
INVARIANT: every added aspect query has weight == ASPECT_WEIGHT = 0.85 and origin == "USER" — shared/polymath_shared/product_search/hypotheses.py:42, 100-102 [DERIVED]
  fails-if: origin ≠ "USER" hides aspects from the USER filter at :88, making them undroppable on a later steer.
INVARIANT: len(plan.queries) after steer_plan ≤ cap, cap = MAX_QUERIES_FACETS if plan.facets else MAX_QUERIES — shared/polymath_shared/product_search/hypotheses.py:85, 96, 103 [DERIVED]
  fails-if: plan exceeds the chat_plan compiler cap.
INVARIANT: replaced ⊆ {q : q.origin == "USER" and q.type != "PRIMARY"} — shared/polymath_shared/product_search/hypotheses.py:88, 91-92 [DERIVED]
  fails-if: a PRIMARY query (q0) is removed and the turn loses its core retrieval.
INVARIANT: every facet kept by steer_plan has non-empty query_ids — shared/polymath_shared/product_search/hypotheses.py:119-121 [DERIVED]
  fails-if: an empty facet breaks facet → query descent.
INVARIANT: search_terms per hypothesis ≤ MAX_TERMS = 3, each ≤ TERM_MAX = 60 chars — shared/polymath_shared/product_search/hypotheses.py:44-45, 270-272, 277 [DERIVED]
  fails-if: more/longer terms multiply downstream catalogue searches.
INVARIANT: confidence ∈ ("high", "medium", "low") or is None — shared/polymath_shared/product_search/hypotheses.py:46, 306 [DERIVED]
  fails-if: an unnormalized confidence string leaks into the record.
INVARIANT: evidence_tags ⊆ legend when a legend is given; violations land in tags_dropped — shared/polymath_shared/product_search/hypotheses.py:265, 299-301, 324-326 [DERIVED]
  fails-if: hallucinated [S#] citations pass through as evidence.
INVARIANT: aspect texts deduped case-insensitively against existing plan queries — shared/polymath_shared/product_search/hypotheses.py:86-87 [DERIVED]
  fails-if: duplicate steering queries on a re-run.

## determinism & idempotency
determinism: DETERMINISTIC (no clock/random/uuid/network/db/env; "Pure: no I/O." shared/polymath_shared/product_search/hypotheses.py:17; `id()` at :91-93 used only as a dict key mapped to list position, so ordering follows list order) [DERIVED]
idempotency: SAFE for aspects_for/steer_text/contract_block/normalize/parse_block (pure, return new values); UNSAFE for steer_plan — mutates the passed plan in place (`plan.queries` :103, `plan.semantic_queries` :104, `plan.facets` :110/:117/:121, `plan.compiler["product_search"]` :123) and a second call overwrites the receipt (aspect texts themselves dedupe via :86-87) — shared/polymath_shared/product_search/hypotheses.py:103-123 [DERIVED]

## failure behaviour
- `_loads` swallows `ValueError` from `json.loads` (:210-211) and `(ValueError, SyntaxError, MemoryError, RecursionError)` from `ast.literal_eval` (:226-227), returning `(None, notes)` — shared/polymath_shared/product_search/hypotheses.py:206-228 [DERIVED]
- `parse_block` fallback reasons: `"unparseable"` / `"no_hypotheses"` when a labelled block existed (:337, :351), `"no_block"` otherwise (:352); the caller then searches the intent's own terms, receipted, never silent — shared/polymath_shared/product_search/hypotheses.py:15-16 [DERIVED]
- `_cut` returns `None` when the truncated array holds no complete object (`end > 0` fails) — shared/polymath_shared/product_search/hypotheses.py:231-236 [DERIVED]
- `normalize` silently drops non-dict and title-less objects; `_tags` silently drops non-legend tags but counts them — shared/polymath_shared/product_search/hypotheses.py:265, 295-301 [DERIVED]
- No exception escapes to the caller on bad model output; every failure is a receipted status — shared/polymath_shared/product_search/hypotheses.py:171-172, 349-352 [DERIVED]

## dumb-code flags
- Dead variable: `notes` in `_loads` is initialized (:213) and returned (:228) but never appended — the failure path always reports `[]` — shared/polymath_shared/product_search/hypotheses.py:213, 228 [DERIVED]
- `_TAG = S?\s*(\d{1,3})` matches bare 1–3-digit numbers, so a stray "2024" in an evidence field yields tag "S202" — shared/polymath_shared/product_search/hypotheses.py:190 [INFERRED: the S is optional and unanchored]
- Magic caps without named constants: intro line ≤ 160 (:317), facet-name slice `[:80]` (:117), ≤ 6 words per term (:270), ≤ 5 fallback head words (:281) — shared/polymath_shared/product_search/hypotheses.py:117, 270, 281, 317 [DERIVED]
- Label round-trip: reason `"product hypothesis material: {label}"` (:101) is re-split on `": "` at :105 and :117 to recover the label — changing the reason wording breaks the receipt and facet names — shared/polymath_shared/product_search/hypotheses.py:101, 105, 117 [DERIVED]
- Contract demands "3 to 5" hypotheses (:151) but `normalize` enforces only the max; 0–2 accepted without a note — shared/polymath_shared/product_search/hypotheses.py:151, 307-308 [INFERRED]
- Singular/plural near-duplicate literals: `"product hypothesis material: "` (:101) vs `"product hypotheses: "` (:102, :117) — shared/polymath_shared/product_search/hypotheses.py:101-102, 117 [DERIVED]

## refactor notes
- Renaming any public symbol breaks both importers: `orchestrator/orchestrator/api/product_report.py`, `shared/polymath_shared/product_search/service.py` (FACTS.importers).
- Receipt schema `{mode, subject, added, replaced, facets_added, facets_dropped, retrieval_override}` is persisted on `plan.compiler["product_search"]` — treat as an external contract — shared/polymath_shared/product_search/hypotheses.py:83-84, 123 [DERIVED]
- `normalize`'s record keys (id/title/problem/audience/evidence_tags/search_terms/confidence) are the product-search-v1 schema — shared/polymath_shared/product_search/hypotheses.py:303-306 [DERIVED]
- `BLOCK_LABEL` must keep matching `_LABEL_OURS` and the fence template :158-163; `CONTRACT_NAME` is baked into the prompt — shared/polymath_shared/product_search/hypotheses.py:39, 143-144, 158-163, 186 [DERIVED]
- Caps (`MAX_QUERIES`, `MAX_QUERIES_FACETS`, `MAX_FACETS`) are owned by `polymath_shared.chat_plan`; chat_plan changes silently alter steering room — shared/polymath_shared/product_search/hypotheses.py:27-36, 85, 112 [DERIVED]
- `_field` does a bare `_ALIASES[name]` lookup — a new field name without an `_ALIASES` entry raises `KeyError` — shared/polymath_shared/product_search/hypotheses.py:243-245 [DERIVED]
- `_terms` falls back to `head_terms(title)` from `polymath_shared.acquisition.agent_reach` — its signature is a hidden dependency — shared/polymath_shared/product_search/hypotheses.py:26, 281 [DERIVED]

## VERIFY
```verify
grep -Fq 'ASPECT_WEIGHT = 0.85' shared/polymath_shared/product_search/hypotheses.py
grep -Fq 'CONTRACT_NAME = "product-hypothesis-contract-v1"' shared/polymath_shared/product_search/hypotheses.py
grep -Fq 'STEER_RULE = "product_search:retrieval_required"' shared/polymath_shared/product_search/hypotheses.py
grep -Fq 'plan.compiler["product_search"]' shared/polymath_shared/product_search/hypotheses.py
grep -Eq 'hypothes[ie]s' shared/polymath_shared/product_search/hypotheses.py
! grep -Fq 'requests' shared/polymath_shared/product_search/hypotheses.py
test "$(grep -c -F 'product-hypotheses' shared/polymath_shared/product_search/hypotheses.py)" -ge 3
```
