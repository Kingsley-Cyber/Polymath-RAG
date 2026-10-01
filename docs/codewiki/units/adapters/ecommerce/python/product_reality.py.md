# unit: adapters/ecommerce/python/product_reality.py
anchor: adapters/ecommerce/python/product_reality.py:1-190

## purpose
Pure planning + joining module (no I/O) for the ecommerce adapter's product-reality lane: `plan` turns validated concepts + TrailSignal stage templates into per-concept research jobs; `join` turns admitted observations back into per-concept existing-product records — adapters/ecommerce/python/product_reality.py:1-16 [DERIVED]. Generates no concepts, reorders no stages, scores and decides nothing; TrailSignal keeps roles, sources, freshness, budget, qualification and the only score — adapters/ecommerce/python/product_reality.py:4-7 [DERIVED]. Mirrors the supply lane shape `supply.plan` -> research -> `supply.leads` — adapters/ecommerce/python/product_reality.py:3 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `variation_id` | def | `(concept_id: str, index: int) -> str` | adapters/ecommerce/python/product_reality.py:33-35 | — |
| `market_phrase` | def | `(concept, mechanism, *, extra: str = "") -> str` | adapters/ecommerce/python/product_reality.py:38-43 | — |
| `plan` | def | `(concepts, mechanisms, views, trail_intents) -> tuple[list[list[dict]], list[dict]]` | adapters/ecommerce/python/product_reality.py:46-105 | — |
| `intent_for` | def | `(job, concept_name: str) -> dict[str, Any]` | adapters/ecommerce/python/product_reality.py:108-112 | — |
| `concept_ref` | def | `(tag: str \| None, concept_ids) -> str \| None` | adapters/ecommerce/python/product_reality.py:115-123 | — |
| `join` | def | `(admitted, observations, sources, concepts, mechanisms, jobs, context_field) -> dict[str, Any]` | adapters/ecommerce/python/product_reality.py:126-189 | — |

## contracts

**plan** — adapters/ecommerce/python/product_reality.py:46-105
- in: `concepts` (`id`, `mechanism_id`, optional `hypothesis_id`, `variations`, `name`, `form_factor`), `mechanisms` (`id`, `hypothesis_id`, `product_terms`), `views` keyed by hypothesis_id (`jobs`, `task`, `population`), `trail_intents` (`intent_id`, `template`, `evidence_goal`, `evidence_roles`) — adapters/ecommerce/python/product_reality.py:50-84 [DERIVED]
- out: `(per_concept, unresolved)`; every job carries `job_id, concept_id, variation_id, hypothesis_id, mechanism_id, job_class, query, host_intent_id, evidence_goal, evidence_roles` — adapters/ecommerce/python/product_reality.py:48-49, 66, 78-79 [DERIVED]
- pre: none enforced; concept with empty `id` or unresolvable hypothesis -> `unresolved` entry `{"concept_id": cid or None, "missing": ["mechanism -> hypothesis"]}`, no jobs — adapters/ecommerce/python/product_reality.py:62-65 [DERIVED]; template whose slots `QS.bind_template` cannot fill -> `unresolved` with `missing` — adapters/ecommerce/python/product_reality.py:74-76 [DERIVED]
- post: per concept, jobs sorted `:direct` job first (key 0), then job_class rank `competition:1, price:2, substitute:3, direct_competitor:4`, else 5 — adapters/ecommerce/python/product_reality.py:95-97 [DERIVED]; a query repeated for a later concept is flagged `same_query_as_concept` (first owner unflagged) — adapters/ecommerce/python/product_reality.py:99-103 [DERIVED]

**join** — adapters/ecommerce/python/product_reality.py:126-189
- in: `admitted` (`observation_id`, `admitted_evidence_id`, `evidence_role`, optional `hypothesis_ids`), `observations` (`context`, `claim`, `source_id`, `metric_if_present`), `sources` (`url`), flat `jobs` list, `context_field(context, key)` reader — adapters/ecommerce/python/product_reality.py:126-127, 140-173 [DERIVED]
- out: `{"existing_products": products, "concept_reality": reality, "joined": stats, "unjoined": unjoined[:50]}`; stats keys `admitted, without_observation, without_concept_tag, unknown_concept, joined` — adapters/ecommerce/python/product_reality.py:136, 189 [DERIVED]
- pre: none; missing observation -> counted `without_observation`, skipped — adapters/ecommerce/python/product_reality.py:141-143 [DERIVED]
- post: every concept in `concepts` gets a reality row with status `EXISTING_PRODUCT_CONTESTS` / `EXISTING_PRODUCTS_FOUND` / `NO_EXISTING_PRODUCT_JOINED` / `NOT_RESEARCHED` — adapters/ecommerce/python/product_reality.py:179-188 [DERIVED]; a product links to a concept only via the `concept:` context tag; no tag -> reason `NO_CONCEPT_TAG`, unknown tag -> `UNKNOWN_CONCEPT` in `unjoined` — adapters/ecommerce/python/product_reality.py:145-151 [DERIVED]

**concept_ref** — adapters/ecommerce/python/product_reality.py:115-123
- in: tag string or None; any iterable of concept ids.
- out: exact id if `t in concept_ids`; else first token matching `[A-Za-z0-9][\w.\-]*` (trailing `.-` stripped) matched case-insensitively; else None — adapters/ecommerce/python/product_reality.py:118-123 [DERIVED]. Mirrors `binding._concept_ref`, gap B-34 — adapters/ecommerce/python/product_reality.py:116-117 [DERIVED].

**market_phrase** — adapters/ecommerce/python/product_reality.py:38-43
- out: `QS._merge(QS.keywords(extra, 3), QS.keywords(form_factor, 3), QS.keywords(primary, 4), cap=6)` joined by space; `primary` = first non-blank string in `mechanism["product_terms"]`, else `concept["name"]` — adapters/ecommerce/python/product_reality.py:41-43 [DERIVED]. Never a registry territory id — adapters/ecommerce/python/product_reality.py:39-40 [DERIVED].

**intent_for** — adapters/ecommerce/python/product_reality.py:108-112
- out: `{"intent_id": job_id[:200], "evidence_goal", "evidence_roles", "intent": ...[:500], "template": query[:500]}`; `intent` embeds `CONTEXT_CONVENTION.format(concept_id=..., variation=...)` — adapters/ecommerce/python/product_reality.py:109-112 [DERIVED].

**variation_id** — adapters/ecommerce/python/product_reality.py:33-35
- out: `f"{concept_id}.v{index + 1}"` — adapters/ecommerce/python/product_reality.py:35 [DERIVED].

## effect surface
- None. Module docstring: "Pure; no I/O." — adapters/ecommerce/python/product_reality.py:1 [DERIVED]; FACTS `tables_read`/`tables_written` empty.
- No Qdrant, files, network, subprocess, or env reads visible; only imports `re`, `typing`, `query_semantics as QS`, `polarity_for` from `adapter_receipt` — adapters/ecommerce/python/product_reality.py:19-23 [DERIVED].

## invariants
INVARIANT: `contests_concept` == (`relation == "solves"` OR `polarity == "contradicting"`) — adapters/ecommerce/python/product_reality.py:160 [DERIVED]
  fails-if: a contradicting product stops contesting (or vice versa); status flips to/from `EXISTING_PRODUCT_CONTESTS`.
INVARIANT: substitute jobs per hypothesis <= 1 (enforced by `substitute_planned` set, gated `hid not in substitute_planned`) — adapters/ecommerce/python/product_reality.py:58, 85-87 [DERIVED]
  fails-if: duplicate word-for-word searches per sibling concept, exactly what the comment forbids — adapters/ecommerce/python/product_reality.py:86-87 [DERIVED].
INVARIANT: joined product count per concept == len(products where `cid in applies_to_concepts`) — adapters/ecommerce/python/product_reality.py:180, 188 [DERIVED]
  fails-if: substitute fan-out (`applies_to_concepts`, same-hypothesis filter) drops siblings -> status understates reality — adapters/ecommerce/python/product_reality.py:164-167 [DERIVED].
INVARIANT: `stats["admitted"]` == `joined + without_observation + without_concept_tag + unknown_concept` (every branch increments exactly one counter) — adapters/ecommerce/python/product_reality.py:138-151, 174 [INFERRED: each `continue` path bumps one counter before skipping].
INVARIANT: `variation_id(cid, n)` == `f"{cid}.v{n + 1}"` and join only accepts `variation_id` values present in the rebuilt `variations` map — adapters/ecommerce/python/product_reality.py:35, 132, 169 [DERIVED]
  fails-if: plan/join disagree on variation indexing -> every product gets `variation_id: None`.
INVARIANT: `unjoined` report capped at 50 entries — adapters/ecommerce/python/product_reality.py:189 [DERIVED]
  fails-if: callers relying on unjoined completeness beyond 50 silently lose rows (stats counters still full).

## determinism & idempotency
determinism: DETERMINISTIC (no clock/random/uuid/network/db/env in the module; output depends only on inputs and the imported `QS` / `polarity_for` helpers — adapters/ecommerce/python/product_reality.py:1, 22-23 [INFERRED: helper purity not visible here])
idempotency: SAFE (pure functions, no writes; same inputs -> equal structures — adapters/ecommerce/python/product_reality.py:1 [DERIVED])

## failure behaviour
- No raised error codes in this module; all defects become data: `unresolved` (missing `mechanism -> hypothesis`, unbindable template slots) — adapters/ecommerce/python/product_reality.py:63-64, 74-76 [DERIVED]; `unjoined` with reasons `NO_CONCEPT_TAG` / `UNKNOWN_CONCEPT` plus truncated `claim[:200]` — adapters/ecommerce/python/product_reality.py:148-150 [DERIVED].
- Missing observation swallowed into `without_observation` — adapters/ecommerce/python/product_reality.py:141-143 [DERIVED]; missing source tolerated via `or {}` (product `url` becomes None) — adapters/ecommerce/python/product_reality.py:156, 172 [DERIVED].
- Unknown/blank relation normalizes to `ROLE_DEFAULT_RELATION.get(evidence_role, "competitor")` — adapters/ecommerce/python/product_reality.py:153-155 [DERIVED].
- Crash surface [INFERRED: direct indexing]: `ti["intent_id"]`, `ti["evidence_goal"]` (:78-79), `competition["intent_id"]` (:81-83), `job["concept_id"]`/`job["evidence_goal"]` (:109-111) raise KeyError if the producer omitted the key; nothing guards them.

## dumb-code flags
- Truncation magic numbers: `[:200]` intent_id and unjoined claim, `[:400]` product claim, `[:500]` intent/template, `[:50]` unjoined cap — adapters/ecommerce/python/product_reality.py:111-112, 150, 172, 189 [DERIVED].
- Default `"competitor"` for any untagged relation under roles outside `{"competition", "price"}` — a `price`-role observation also defaults to `"competitor"` — adapters/ecommerce/python/product_reality.py:27, 154-155 [DERIVED].
- Cross-module private call `QS._merge` — adapters/ecommerce/python/product_reality.py:43, 89 [DERIVED].
- Duplicated rule: `concept_ref` re-implements `binding._concept_ref` (comment, gap B-34) — the two copies can drift — adapters/ecommerce/python/product_reality.py:116-117 [DERIVED].
- Duplicated sibling/hypothesis logic: plan builds `siblings` (:54-57, 89) but join re-derives same-hypothesis membership inline (:166-167) — adapters/ecommerce/python/product_reality.py:54-57, 166-167 [DERIVED].
- Sort key special-cases the literal suffix `:direct` inside `job_id` — job ordering silently depends on the id format built at :83 — adapters/ecommerce/python/product_reality.py:83, 97 [DERIVED].
- `same_query_as_concept` only marks later duplicates; the first concept owning a query is never flagged — adapters/ecommerce/python/product_reality.py:100-103 [DERIVED].
- `CONTEXT_CONVENTION` is a `str.format` template with exactly `{concept_id}`/`{variation}` placeholders; any added brace crashes `intent_for` — adapters/ecommerce/python/product_reality.py:28-30, 110 [INFERRED: `.format` placeholder set must match].

## refactor notes
- Job dict shape is the wire contract between `plan`, `intent_for`, and `join` (keys listed at :48-49; plus `applies_to_concepts` :89 and `same_query_as_concept` :102). `join` reads `job_id`/`job_class`/`applies_to_concepts`/`concept_id` — adapters/ecommerce/python/product_reality.py:134, 165-167, 175-177 [DERIVED].
- `job_id` formats `f"{intent_id}:{cid}"`, `...:direct`, `...:substitute`, `f"{intent_id}:{vid}"` are load-bearing: the `:direct` suffix drives sort order (:97) and `:substitute` ids are matched against context `intent:` tags for provenance (:161, 165) — adapters/ecommerce/python/product_reality.py:78, 83, 88, 93 [DERIVED].
- Context vocabulary is paired: `CONTEXT_CONVENTION` text (:28-30) must stay in sync with the keys join parses — `concept`, `variation`, `relation`, `product`, `price as listed`, `intent` — adapters/ecommerce/python/product_reality.py:145, 152-153, 161, 171-172 [DERIVED]; and with `RELATIONS` — adapters/ecommerce/python/product_reality.py:25 [DERIVED].
- Status strings and stats keys are output API for downstream consumers — adapters/ecommerce/python/product_reality.py:136, 182, 189 [DERIVED].
- External couplings: `QS.has_unbound_slot`/`QS.bind_template`/`QS.keywords`/`QS._merge` (:22, 43, 71-74, 84-89) and `adapter_receipt.polarity_for` with ADR-069 semantics (gap B-11) (:23, 158-159) — adapters/ecommerce/python/product_reality.py:22-23, 158 [DERIVED].
- `join` expects a flat jobs list; `plan` returns grouped lists — the caller must flatten — adapters/ecommerce/python/product_reality.py:98, 175-177 [INFERRED: shapes differ, no flatten in-module].

## VERIFY
```verify
grep -Fq 'RELATIONS = ("competitor", "substitute", "current_solution", "validates", "solves")' adapters/ecommerce/python/product_reality.py
grep -Fq 'ROLE_DEFAULT_RELATION = {"competition": "competitor", "price": "competitor"}' adapters/ecommerce/python/product_reality.py
grep -Fq 'return f"{concept_id}.v{index + 1}"' adapters/ecommerce/python/product_reality.py
grep -Fq 'contests = relation == "solves" or polarity == "contradicting"' adapters/ecommerce/python/product_reality.py
grep -Fq 'rank = {"competition": 1, "price": 2, "substitute": 3, "direct_competitor": 4}' adapters/ecommerce/python/product_reality.py
grep -Fq 'status = "EXISTING_PRODUCT_CONTESTS" if solved else "EXISTING_PRODUCTS_FOUND" if mine else "NO_EXISTING_PRODUCT_JOINED" if planned.get(cid) else "NOT_RESEARCHED"' adapters/ecommerce/python/product_reality.py
test "$(grep -c -F 'applies_to_concepts' adapters/ecommerce/python/product_reality.py)" -ge 4
! grep -Fq 'import requests' adapters/ecommerce/python/product_reality.py
```
