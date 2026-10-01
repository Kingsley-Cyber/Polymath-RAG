# unit: shared/polymath_shared/bridge_compiler.py
anchor: shared/polymath_shared/bridge_compiler.py:1-213

## purpose
Bounded concept-bridge compiler (WLK2C C2): turns nominated corpus concepts into at most `MAX_BRIDGES = 4` grounded retrieval sub-questions via ONE injected structured LLM call. "ACTIVATION, not invention" — bridges may only derive from listed concepts; `parse_and_validate` deterministically drops invented ones. Pure core: the LLM call is injected as `generate`, flag-gated in the orchestrator. — shared/polymath_shared/bridge_compiler.py:1-19 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Concept` | dataclass | `(key, label, source="")` + `to_dict() -> dict` | shared/polymath_shared/bridge_compiler.py:43-50 | bridge_integration.py, _small-modules-1 |
| `BridgeCompilerInput` | dataclass | `(q0, intent, concepts=[], existing_subqueries=[], graph_relations=[])` | shared/polymath_shared/bridge_compiler.py:54-59 | bridge_integration.py, _small-modules-1 |
| `CompiledBridge` | dataclass | `(bridge_id, bridge_query, derived_from, relation_to_q0, proposed_role="COMPLEMENTARY", model_confidence=None)` + `to_dict()` | shared/polymath_shared/bridge_compiler.py:63-74 | bridge_integration.py, _small-modules-1 |
| `compiler_eligible` | def | `(intent, concepts, admissible_existing_bridge_concepts) -> tuple[bool, str]` | shared/polymath_shared/bridge_compiler.py:77-90 | bridge_integration.py, _small-modules-1 |
| `build_prompt` | def | `(inp, *, max_bridges=MAX_BRIDGES) -> str` | shared/polymath_shared/bridge_compiler.py:93-118 | — |
| `parse_and_validate` | def | `(raw, inp, *, max_bridges=MAX_BRIDGES) -> tuple[list, dict]` | shared/polymath_shared/bridge_compiler.py:155-199 | — |
| `compile_bridges` | def | `(inp, *, generate, max_bridges=MAX_BRIDGES) -> tuple[list, dict]` | shared/polymath_shared/bridge_compiler.py:202-213 | bridge_integration.py, _small-modules-1 |

("used by" = FACTS.importers, module-level; per-symbol usage unknown.)

## contracts

**`compiler_eligible`** — shared/polymath_shared/bridge_compiler.py:77-90
- in: `intent` (None-tolerant), `concepts` list, `admissible_existing_bridge_concepts` (key set, None-tolerant).
- out: reason ∈ `{"intent_not_latent", "no_nominated_concepts", "all_concepts_have_admissible_bridge", "eligible"}`.
- post: `True` only when `intent.strip().upper() ∈ LATENT_INTENTS` AND concepts nonempty AND ≥1 concept key not covered.
- concept key read via `getattr(c, "key", c)` — accepts raw strings too.

**`build_prompt`** — shared/polymath_shared/bridge_compiler.py:93-118
- in: `BridgeCompilerInput`.
- out: prompt embedding `q0`, `intent`, concept lines `key=... concept=...`, existing subqueries, graph relations; demands JSON array of AT MOST `max_bridges` objects with fields `bridge_id`, `bridge_query`, `derived_from`, `relation_to_q0`, `proposed_role`, `model_confidence` (shared/polymath_shared/bridge_compiler.py:110-114).

**`parse_and_validate`** — shared/polymath_shared/bridge_compiler.py:155-199
- in: raw model output (list/dict/str), `BridgeCompilerInput`.
- out: `(list[CompiledBridge], diag)`; diag keys: `generated`, `admitted`, `dropped_invented`, `dropped_no_relation`, `dropped_structural`, `dropped_empty`, `dropped_dup`, `json_status`.
- drop order: empty `bridge_query` (:174-175) → `derived_from` not matching a concept key/label (:176-178) → empty `relation_to_q0` (:179-180) → C1 structural gate via `structural_bridge_admissibility(path, inp.q0)` (:181-184) → duplicate normalized query (:185-188).
- post: `len(out) ≤ max_bridges` (:196-197); `derived_from` rewritten to canonical `concept.key` (:193); `proposed_role ∉ PROPOSED_ROLES` → `"COMPLEMENTARY"` (:194); `model_confidence` kept only if `isinstance(conf, (int, float))` else `None` (:195).

**`compile_bridges`** — shared/polymath_shared/bridge_compiler.py:202-213
- pre: `generate` callable taking one prompt string (:210).
- post: never raises. No concepts → `([], {"generated": 0, "admitted": 0, "skipped": "no_concepts"})` (:206-207). `generate` raises → `([], {"generated": 0, "admitted": 0, "error": "<ExceptionTypeName>"})` (:211-212).

## effect surface
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty).
- Network: none in this file — the single LLM call is the injected `generate(prompt)` at shared/polymath_shared/bridge_compiler.py:210 (production: one low-temperature Gemma JSON call per docstring :17, :204).
- Files / Qdrant / subprocess / env flags: none visible in SOURCE.
- Internal deps: `polymath_shared.bridge_admission.structural_bridge_admissibility` (:26, used :183); `polymath_shared.retrieval_lineage.DiscoveryPath` (:27, used :181-182).

## invariants
INVARIANT: admitted bridges ≤ `MAX_BRIDGES` = 4 per call — shared/polymath_shared/bridge_compiler.py:196-197 [DERIVED]
  fails-if: downstream budget/portfolio rules (C5) receive more bridges than contracted.
INVARIANT: every admitted `derived_from` ∈ provided concept keys (rewritten to canonical key) — shared/polymath_shared/bridge_compiler.py:176-178,193 [DERIVED]
  fails-if: ungrounded invented concepts enter retrieval — breaks the activation-not-invention guarantee.
INVARIANT: admitted `bridge_query` values are distinct after `_norm` — shared/polymath_shared/bridge_compiler.py:185-188 [DERIVED]
  fails-if: duplicate retrieval lanes, wasted C4 scoring.
INVARIANT: `model_confidence` is recorded but never read in any admission branch — shared/polymath_shared/bridge_compiler.py:190,195 (no gating use), docstring :10-13 [DERIVED]
  fails-if: confidence becomes authority — contradicts the metadata-not-authority contract.
INVARIANT: admitted `proposed_role` ∈ `("COMPLEMENTARY", "DIVERGENT")` — shared/polymath_shared/bridge_compiler.py:194 [DERIVED]
  fails-if: C5 receives out-of-vocabulary role hints.
INVARIANT: `LATENT_INTENTS` excludes EXACT, DEFINITION, MECHANISM, COMPARISON, PROCEDURE, RECALL — shared/polymath_shared/bridge_compiler.py:32-33 (comment) [DERIVED]
  fails-if: factual/direct-lookup queries reach the compiler and burn the LLM call.

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/db/env in this file; the only nondeterministic step (generation) is injected via `generate` — shared/polymath_shared/bridge_compiler.py:202-213 [DERIVED]
idempotency: SAFE — pure functions, no writes or state; same `raw` + `inp` always yield the same result [INFERRED: no module-level mutable state beyond constants].

## failure behaviour
- `_loads_status`: empty raw → `([], "empty_output")` (:133-134); `json.loads` Exception → last-resort regex `r"\[.*\]"` (:136-142); still failing → `([], "invalid_json")` (:140, 143-144). Distinguishes "model declined" from "garbage output" (CORPUS-EXPLORE-FIRING-V1) (:121-125).
- `compile_bridges`: swallows ANY Exception from `generate` → `([], diag)` with `"error": f"{type(e).__name__}"` (:211-212); the exception message is discarded, caller sees only the type name.
- `compile_bridges` never raises from the generation path (:205, :211); `parse_and_validate` raises nothing by construction — no error codes raised anywhere in the unit.

## dumb-code flags
- Regex `r"\[.*\]"` is greedy; the comment claims "the first JSON array" (:138) — it actually spans first `[` to last `]`, so two arrays in the output yield one broken parse [INFERRED: greedy `.*` semantics].
- `by_key`/`by_label` dict comprehensions (:160-161) silently overwrite concepts sharing a normalized key or label — last one wins, earlier concept's bridges get mis-attributed or dropped [INFERRED: dict collision].
- `DiscoveryPath` gets `bridge_id=f"bridge:{i}"` (:181-182) while `CompiledBridge.bridge_id` may be the model-supplied id (:192) — the two ids for the same bridge can diverge.
- Non-dict items in the parsed array are skipped with `continue` and NO diag counter (:167-169) — `generated` undercounts model output items.
- `compiler_eligible` computes `covered`/`uncovered` (:84-85) before the `if not concepts` early return (:86-87) — wasted work on the empty path.
- diag failure keys are heterogeneous across paths: `"skipped"` (:207) vs `"error"` (:212) vs `"json_status"` (:166).

## refactor notes
- Importers `shared/polymath_shared/bridge_integration.py` and `shared/polymath_shared/_small-modules-1` (FACTS.importers) — changing any public signature or the `CompiledBridge`/`Concept` field names ripples into both.
- `build_prompt` JSON field names (:110-114) and `parse_and_validate` `obj.get` keys (:171-172, :189-190) are an implicit paired contract — renaming one side breaks parsing silently.
- diag key names, especially `json_status` values (`ok`/`empty_output`/`invalid_json`, :123-125), are consumed by diagnostics (CORPUS-EXPLORE-FIRING-V1) — renaming breaks callers [INFERRED: docstring says a caller reads the status].
- `DiscoveryPath(origin="BRIDGE", inspired_by_profile=[concept.source])` (:181-182) feeds retrieval lineage — changing these fields breaks `retrieval_lineage` consumers downstream.
- The C1 gate call `structural_bridge_admissibility(path, inp.q0).admissible` (:183) depends on `bridge_admission` semantics; reordering it relative to the invented-concept check changes which diag counter fires.

## VERIFY
```verify
grep -Fq 'MAX_BRIDGES = 4' shared/polymath_shared/bridge_compiler.py
grep -Fq 'PROPOSED_ROLES = ("COMPLEMENTARY", "DIVERGENT")' shared/polymath_shared/bridge_compiler.py
grep -Fq 'LATENT_INTENTS = ("SYNTHESIS", "APPLICATION", "EXPLORATORY", "RELATIONSHIP")' shared/polymath_shared/bridge_compiler.py
grep -Fq 'dropped_invented' shared/polymath_shared/bridge_compiler.py
grep -Fq 'return [], "invalid_json"' shared/polymath_shared/bridge_compiler.py
grep -Fq '"error": f"{type(e).__name__}"' shared/polymath_shared/bridge_compiler.py
test "$(grep -c -F 'structural_bridge_admissibility' shared/polymath_shared/bridge_compiler.py)" -ge 2
! grep -Fq 'model_confidence >=' shared/polymath_shared/bridge_compiler.py
```
