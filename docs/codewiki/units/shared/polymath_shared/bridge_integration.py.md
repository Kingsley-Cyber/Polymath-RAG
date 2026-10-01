# unit: shared/polymath_shared/bridge_integration.py
anchor: shared/polymath_shared/bridge_integration.py:1-149

## purpose
WLK2C C3 stage: turns admitted concept-bridges into `BRIDGE`-origin subqueries appended to a compiled chat plan, mirroring PROFILE-EXPANSION-V1 under a tiered policy (reuse covered concepts; compile only the uncovered rest) — shared/polymath_shared/bridge_integration.py:1-17 [DERIVED]. Pure except one injected `generate` model call; the live gemma call and invocation live in the orchestrator, flag-gated — shared/polymath_shared/bridge_integration.py:1-2 [DERIVED]. Downstream C4/C5 decide whether bridge candidates survive — shared/polymath_shared/bridge_integration.py:16-17 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `concepts_from_nominations` | def | `(nominations, *, max_concepts=8) -> list` | :35-54 | — |
| `covered_concept_keys` | def | `(plan_queries, root_query: str) -> set` | :57-74 | — |
| `bridges_to_subqueries` | def | `(bridges, concepts_by_key, *, start_index=0, weight=0.55, origin="BRIDGE", id_prefix="br") -> list` | :77-99 | CORPUS-EXPLORER-V1 (reuses with `origin="CORPUS_EXPLORE"`/`id_prefix="ce"`) — :83-84 [DERIVED] |
| `plan_bridge_expansion` | def | `(plan, nominations, *, generate, max_add=MAX_BRIDGES, weight=0.55) -> dict` | :102-140 | orchestrator/orchestrator/api/ui.py, shared/polymath_shared/_small-modules-1 (module importers, FACTS.importers) |
| `BRIDGE_SUBQUERY_WEIGHT` | const | `0.55` | :31 | — |
| `MAX_CONCEPTS` | const | `8` | :32 | — |

## contracts
`concepts_from_nominations` (:35-54)
- in: iterable of nomination dicts or objects (`_g` duck-types `.get`/`getattr`, :38-39); `None`/empty tolerated (`nominations or ()`, :42).
- out: deduped by `doc_id` (`seen`, :43-44), bounded by `max_concepts` (:51-52).
- label preference order: `representative_text` → `title` → `source_name` → `representative_surface` → `did` (:48-49); whitespace-normalized, truncated `[:200]` (:50).
- each entry is `Concept(key=did, label=..., source=did)` — `source` always equals `key` (:50). [DERIVED]

`covered_concept_keys` (:57-74)
- skips subqueries with `type == "PRIMARY"` or `origin == "BRIDGE"` (:63); skips empty `inspired_by_profile` (:64-66).
- a key counts as covered only if `structural_bridge_admissibility(DiscoveryPath(...), root_query).admissible` (:67-72); `DiscoveryPath` is built with `query_id` and `bridge_id` both set to `str(q.id)` (:69). [DERIVED]

`bridges_to_subqueries` (:77-99)
- query = first `MAX_QUERY_WORDS` whitespace-joined words of `b.bridge_query` (:89); bridges with empty normalized query are skipped (:90-91).
- each `CompiledQuery`: `id=f"{id_prefix}{start_index + i}"`, `type="ENTITY"`, `role="bridge"`, `origin=origin` (:93-94); `inspired_by_profile=[concept.source]` or `[]` (:95); `derived_from=concept.key` else `b.derived_from` (:97); `reason=f"bridge/{b.proposed_role.lower()} <- {b.derived_from}: {b.relation_to_q0}"` truncated `[:200]` (:98).
- no model call; `CompiledQuery`/`MAX_QUERY_WORDS` imported lazily from `polymath_shared.chat_plan` (:85). [DERIVED]

`plan_bridge_expansion` (:102-140)
- pre: plan needs `.queries` (default `[]`, :108), `.intent` (:113); `root = primary_text(queries)` (:114).
- no `PRIMARY` subquery → returns `{"added": 0, "eligible": False, "reason": "no_primary"}` (:110-112).
- ineligible per `compiler_eligible(intent, concepts, covered)` → diag adds `"intent"`, `"concepts"`, `"covered"` counts (:117-121).
- compiler input: only uncovered concepts, `existing_subqueries` = non-PRIMARY query texts, `graph_relations=[]` (:122-126).
- post: append-only (`plan.queries.append`, :135); duplicate lowercase query text skipped (:129-134); existing queries and q0 untouched (:13-14 docstring). [DERIVED]
- returns diag; success keys: `added, eligible, reason, intent, concepts, uncovered, generated, admitted, dropped_invented, dropped_structural` (:136-139); diag also stashed on `plan.compiler["bridge_expansion"]` (:140, :147).
- docstring: "never raises" (:105). [DERIVED]

## effect surface
- Postgres: none (FACTS `tables_read`/`tables_written` empty). [DERIVED]
- Network/model: none in-module; the ONE model call is the injected `generate` executed inside `compile_bridges` (:127; docstring :104). [DERIVED]
- Object mutation: `plan.queries.append(sq)` (:135); `plan.compiler["bridge_expansion"] = diag` only when `plan.compiler` is a dict (:145-147).
- Files / subprocesses / env flags: none visible.

## invariants
INVARIANT: len(concepts_from_nominations out) <= 8 (default `max_concepts`) — :32, :51-52 [DERIVED]
  fails-if: compiler input exceeds intended bound; unbounded model cost downstream.
INVARIANT: BRIDGE_SUBQUERY_WEIGHT == 0.55 (below a USER aspect; q0 stays primary) — :31 [DERIVED]
  fails-if: bridge subqueries outrank user-authored aspects in C5 ranking.
INVARIANT: label length <= 200 and reason length <= 200 — :50, :98 [DERIVED]
  fails-if: oversized surfaces leak into lineage/diagnostics.
INVARIANT: every emitted subquery has type="ENTITY" and role="bridge" — :93-94 [DERIVED]
  fails-if: downstream role/portfolio logic (C5) misclassifies.
INVARIANT: no PRIMARY in plan.queries ⇒ diag["added"] == 0 — :110-112 [DERIVED]
  fails-if: expansion overrides q0 authority.
INVARIANT: diag["added"] == number of appended subqueries — :135-136 [DERIVED]
  fails-if: diagnostics under-report actual plan growth.
INVARIANT: covered_concept_keys excludes keys from PRIMARY or BRIDGE-origin subqueries — :63 [DERIVED]
  fails-if: covered concepts re-compiled (duplicate work) or bridge subqueries feed their own coverage.

## determinism & idempotency
determinism: DETERMINISTIC except the injected `generate` callback (single model call via `compile_bridges` at :127; no clock/random/uuid/db/env use in the unit) [DERIVED]
idempotency: UNSAFE — re-running re-invokes `generate`; `covered_concept_keys` deliberately skips BRIDGE-origin subqueries (:63), so previously added concepts stay "uncovered" and get re-compiled; only the lowercase text dedup (:129-134) prevents duplicate query strings [INFERRED]

## failure behaviour
- `except Exception: pass` in `_stash` swallows all exceptions (FACTS.fallbacks "SWALLOWED: pass", :148-149): the diag stash on `plan.compiler` is silently absent; the caller still receives the diag via return — :143-149 [DERIVED].
- No other try/except exists in the unit; a raise from `generate`/`compile_bridges` would propagate despite the "never raises" docstring claim (:105) [INFERRED].

## dumb-code flags
- Magic number `200` duplicated for two unrelated truncations (label :50, reason :98).
- Deferred import `from polymath_shared.chat_plan import MAX_QUERY_WORDS, CompiledQuery` inside the function (:85) — all other imports are top-level (:21-29); likely circular-import avoidance [INFERRED].
- `graph_relations=[]` hardwired (:126); tier-2 graph-path bridges are declared "future" (:9) — dead branch.
- `query_id` and `bridge_id` both `str(getattr(q, "id", ""))` in the DiscoveryPath probe (:69) — same value in two fields.
- `# noqa: BLE001` suppresses the blanket-except linter (:148).
- Label chain treats `representative_surface` as last-resort because it is only the atom KIND, e.g. "THEORY" (comment E2, :46-47).

## refactor notes
- Module importers: orchestrator/orchestrator/api/ui.py and shared/polymath_shared/_small-modules-1 (FACTS.importers) — any signature change to the public defs breaks them.
- `bridges_to_subqueries` is reused by CORPUS-EXPLORER-V1 with `origin="CORPUS_EXPLORE"`/`id_prefix="ce"` (:83-84); the BRIDGE defaults keep "the existing WLK2C path byte-identical" (:84) — do not change defaults or keyword names.
- diag key names (`added/eligible/reason/intent/concepts/covered/uncovered/generated/admitted/dropped_invented/dropped_structural`, :111, :119-120, :136-139) are stashed on `plan.compiler` (:147) and consumed downstream — renaming breaks diagnostics readers [INFERRED].
- Changing the label preference order or `[:200]` truncations silently changes compiler inputs (:46-50).
- Changing the skip rule in `covered_concept_keys` (:63) changes which concepts are re-compiled — cost and duplicate behavior.

## VERIFY
```verify
grep -Fq 'BRIDGE_SUBQUERY_WEIGHT = 0.55' shared/polymath_shared/bridge_integration.py
grep -Fq 'MAX_CONCEPTS = 8' shared/polymath_shared/bridge_integration.py
grep -Fq 'origin: str = "BRIDGE", id_prefix: str = "br"' shared/polymath_shared/bridge_integration.py
grep -Fq 'comp["bridge_expansion"] = diag' shared/polymath_shared/bridge_integration.py
grep -Fq 'graph_relations=[]' shared/polymath_shared/bridge_integration.py
grep -Eq 'dropped_(invented|structural)' shared/polymath_shared/bridge_integration.py
grep -Fq 'def _stash(plan, diag: dict) -> None:' shared/polymath_shared/bridge_integration.py
```
