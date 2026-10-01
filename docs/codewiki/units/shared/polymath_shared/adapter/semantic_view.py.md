# unit: shared/polymath_shared/adapter/semantic_view.py
anchor: shared/polymath_shared/adapter/semantic_view.py:1-267
(anchors below use `semantic_view.py` = shared/polymath_shared/adapter/semantic_view.py)

## purpose
Builds `OpportunitySemanticViewV1`: a DERIVED, READ-ONLY projection over state the runtime already owns — the hypothesis ledger's newest revisions, the run's step outputs, and stored admissions — joined BY ID, never by name or prose (semantic_view.py:1-8). Four consumer projections: `agent_projection` (reasoning steps, `config.show` path `semantics.*`), `query_projection` (research planning, `config.inputs` path `context.semantics.*`), `product_reality_projection` (concept → marketplace research), `trail_projection` (Trail's closed 4-field wire) (semantic_view.py:10-13). Nothing here is persisted, revised, or sent to Trail as-is (semantic_view.py:3). Sole module importer: `shared/polymath_shared/adapter/service.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `known_origin_ids` | def | (outputs, order=()) -> dict[str, set[str]] | semantic_view.py:65-70 | — |
| `for_hypothesis` | def | (state, outputs, *, order=(), field_rows=()) -> dict | semantic_view.py:99-173 | — |
| `build` | def | (current, outputs, *, order=(), step_outputs=(), run_id=None, include_absorbed=False) -> dict | semantic_view.py:176-186 | — |
| `agent_projection` | def | (view) -> dict | semantic_view.py:190-192 | — |
| `query_projection` | def | (view) -> dict | semantic_view.py:195-204 | — |
| `product_reality_projection` | def | (view) -> dict | semantic_view.py:207-213 | — |
| `trail_projection` | def | (hypothesis) -> dict | semantic_view.py:216-220 | — |
| `trail_wire` | def | (view, *, friction_family_ids=()) -> dict | semantic_view.py:229-242 | — |
| `scope` | def | (view, *, friction_family_ids=()) -> dict | semantic_view.py:258-266 | — |
| `VIEW_VERSION` | const | `"opportunity_semantic_view.v1"` | semantic_view.py:25 | — |
| `TRAIL_WIRE_FIELDS` | const | 4-tuple `("hypothesis_id", "revision", "status", "statement")` | semantic_view.py:29 | — |
| `TRAIL_WIRE_EXTENDED_FIELDS` | const | `TRAIL_WIRE_FIELDS` + 7 candidate/support keys | semantic_view.py:225-226 | — |
| `PROJECTIONS` | const | `{"agent", "query", "product_reality"}` → functions | semantic_view.py:255 | — |

Per-symbol callers are not in FACTS; the module's only importer is `shared/polymath_shared/adapter/service.py` (FACTS.importers).

## contracts
**`for_hypothesis(state, outputs, *, order=(), field_rows=())`** (semantic_view.py:99-173)
- in: `state` = the NEWEST ledger revision, chosen by the caller (semantic_view.py:101); `outputs` = step outputs keyed by step id; `order` = acceptance order.
- pre: `state` must carry `hypothesis_id`, `revision`, `status`, `statement` (direct subscripts at semantic_view.py:103, semantic_view.py:145) — KeyError otherwise [INFERRED: direct subscript, no guard].
- out: dict with exactly 13 top-level keys: `view_version, hypothesis, origin, semantics, knowledge, transduction, bridge, jobs, mechanisms, concepts, trail, field_evidence, missing` (semantic_view.py:143-172).
- post: `missing` lists every `SEMANTIC_FIELDS` name whose state value is falsy (semantic_view.py:106), plus `"origin"` when no declared `lead_ids`/`latent_structure_ids` (semantic_view.py:118-119), plus `"bridge"` when no bridge carries this `hypothesis_id` (semantic_view.py:130-131).
- post: origin uses DECLARED ids only; each id resolved against what the run produced; unresolved ids land in `origin.unresolved_ids`; structures sharing evidence appear with basis `"SHARED_EVIDENCE"` (semantic_view.py:108-117, semantic_view.py:149, semantic_view.py:155-156).

**`build(current, outputs, *, order=(), step_outputs=(), run_id=None, include_absorbed=False)`** (semantic_view.py:176-186)
- in: `current` = hypothesis_id → NEWEST revision in the store's order (semantic_view.py:178-179).
- post: inputs never mutated — deep copies at semantic_view.py:180-181.
- out: `{"view_version", "run_id", "authority": "DERIVED_READ_ONLY — the ledger and the step outputs are the record", "hypotheses"}` in generation order (semantic_view.py:185-186).
- post: hypotheses with status in `ABSORBED_STATUSES` are skipped unless `include_absorbed=True` (semantic_view.py:183-184).

**`trail_projection(hypothesis)`** (semantic_view.py:216-220)
- in: a view, a view's `hypothesis` block, a ledger state, or a thin context entry (semantic_view.py:217-218).
- out: CLOSED — exactly `{"hypothesis_id": str, "revision": int, "status", "statement"}`; anything else dropped on purpose (semantic_view.py:217-220). Trail's wire models are `extra="forbid"` (semantic_view.py:13).

**`trail_wire(view, *, friction_family_ids=())`** (semantic_view.py:229-242)
- out: `TRAIL_WIRE_EXTENDED_FIELDS` keys minus empties — any value `in (None, [])` is removed (semantic_view.py:242).
- post: `candidate_friction_families` non-empty only when the normalized `suspected_friction` (`strip().lower().replace(" ", "_")`) IS a member of `friction_family_ids` — exact-id rule, free text never guessed into a family (semantic_view.py:231-233, semantic_view.py:236-238).
- post: `candidate_predicates` filtered by `_identifier` regex `[A-Za-z0-9][A-Za-z0-9._:/-]*` and capped at `MAX_ITEMS` (semantic_view.py:240, semantic_view.py:252); `candidate_product_territories` is always `[]` (semantic_view.py:241).
- post: absent values stay absent so Trail's lexical path decides (semantic_view.py:233-234).

**`agent_projection(view)`** — everything except the `"trail"` key (semantic_view.py:190-192).
**`query_projection(view)`** — requires the FULL view (reads `view["trail"]["territories"]`); emits vocabulary only: no evidence text, no concepts (semantic_view.py:195-196, semantic_view.py:204).
**`product_reality_projection(view)`** — concepts + mechanisms carrying `product_terms` (semantic_view.py:207-213).
**`scope(view, *, friction_family_ids=())`** — manifest-addressable paths: `semantics.hypotheses` (agent), `semantics.query`, `semantics.product_reality`, `semantics.trail` (ADR-069 wire), `semantics.by_id.<hypothesis_id>` (full view) (semantic_view.py:258-266).
**`known_origin_ids(outputs, order=())`** — `{"lead_ids", "latent_structure_ids"}` from the newest `population_leads` + `community_leads` + `latent_structures` (semantic_view.py:65-70).

## effect surface
- Postgres tables read: none; written: none (FACTS `tables_read: []`, `tables_written: []`).
- Qdrant / files / network / subprocess / env flags: none — module imports are `copy`, `typing`, `.evidence_boundary as EB`, `.hypotheses.ABSORBED_STATUSES` only (semantic_view.py:19-23); the one lazy import is `re` (semantic_view.py:251).
- Reads in-memory only: ledger revisions, step outputs, and stored admissions via `EB._index_rows` over `step_outputs` (semantic_view.py:96).

## invariants
INVARIANT: len(TRAIL_WIRE_FIELDS) == 4 — semantic_view.py:29 [DERIVED]
  fails-if: `trail_projection` emits a 5th key and Trail's `extra="forbid"` model rejects the wire.
INVARIANT: len(TRAIL_WIRE_EXTENDED_FIELDS) == 11 == 4 wire fields + 7 candidate/support keys — semantic_view.py:225-226 [DERIVED]
  fails-if: ADR-069 wire shape drifts between this module and Trail's model.
INVARIANT: len(SEMANTIC_FIELDS) == 6 — semantic_view.py:30 [DERIVED]
INVARIANT: len(PRIMITIVE_FAMILIES) == 10 and len(RUN_LEVEL_FAMILIES) == 2 — semantic_view.py:32-35 [DERIVED]
INVARIANT: candidate_friction_families ⊆ set(friction_family_ids) — semantic_view.py:236-238 [DERIVED]
  fails-if: free-text friction is guessed into a registry family, breaking the exact-id rule.
INVARIANT: open_knowledge_gap_count == number of gaps with status "open" counted BEFORE the MAX_ITEMS cut — semantic_view.py:140-141, semantic_view.py:153 [DERIVED]
  fails-if: a hypothesis whose first dozen gaps were closed shows `knowledge_gaps` truncated to look empty while the true open count is hidden (bug hunt B-13).
INVARIANT: displayed strings ≤ 400 chars (TEXT_CHARS), list items ≤ 12 (MAX_ITEMS), evidence rows ≤ 24 (MAX_FIELD_EVIDENCE) — semantic_view.py:26-28, semantic_view.py:38-45, semantic_view.py:152, semantic_view.py:170 [DERIVED]
INVARIANT: build never mutates its inputs — `copy.deepcopy` at semantic_view.py:180-181 [DERIVED]
  fails-if: caller's ledger/step-output dicts are aliased into the read-only view.

## determinism & idempotency
determinism: DETERMINISTIC (pure functions of the passed mappings; no clock/random/uuid/db/env/network anywhere in semantic_view.py:1-267; only imports are copy/typing/re — semantic_view.py:19-23, semantic_view.py:251)
idempotency: SAFE (read-only projection, nothing persisted or revised — semantic_view.py:3; inputs deep-copied — semantic_view.py:180-181)

## failure behaviour
- No try/except and no fallback handlers exist in the unit (semantic_view.py:1-267; FACTS lists no fallbacks) — exceptions propagate to the caller.
- Absent step-output key → `None`, never fabricated: `_newest` returns `None` (semantic_view.py:58); module rule "a value that does not exist is reported as missing — never fabricated" (semantic_view.py:16).
- Absent ledger field → reported in `view["missing"]` (semantic_view.py:106, semantic_view.py:119, semantic_view.py:131); absent bridge → `"bridge": None` (semantic_view.py:158-160).
- Required keys raise: `state["hypothesis_id"]` (semantic_view.py:103); `int(state["revision"])` raises ValueError on non-numeric (semantic_view.py:145); `view["hypothesis"]`/`view["semantics"]` KeyError in projections (semantic_view.py:197, semantic_view.py:209).

## dumb-code flags
- Two text budgets in one file: `TEXT_CHARS = 400` (semantic_view.py:26) vs `_short`'s `text[:512]` (semantic_view.py:247) — the trail candidates get a longer budget than every other clipped string.
- `TRAIL_WIRE_FIELDS` at semantic_view.py:29 but `TRAIL_WIRE_EXTENDED_FIELDS` at semantic_view.py:225-226 — one wire contract split 196 lines apart; FACTS.constants omits the extended tuple entirely (extraction gap, not a code bug).
- `import re` inside `_identifier`'s body (semantic_view.py:251) — re-imported on every call.
- `trail_wire` always sets `"candidate_product_territories": []` (semantic_view.py:241) which the empties filter (semantic_view.py:242) then always strips — dead key.
- Cross-module private access: `EB._index_rows` (semantic_view.py:96); the comment concedes "one reader of that shape, not two" (semantic_view.py:93-94).
- `view["missing"]` mixes semantic field names with the sentinels `"origin"` and `"bridge"` (semantic_view.py:106, semantic_view.py:119, semantic_view.py:131) — consumers cannot tell a field name from a structural gap by value alone.

## refactor notes
- Only importer is `shared/polymath_shared/adapter/service.py` (FACTS.importers) — any signature/return-shape change here must be mirrored there.
- `_newest` is documented as "the same rule as `service._gather`" (semantic_view.py:49) — changing the newest-first/top-level-then-one-down lookup in one place requires checking the other.
- Trail's wire is CLOSED (`extra="forbid"`) (semantic_view.py:13, semantic_view.py:217, semantic_view.py:223-225): adding a wire key means extending `TRAIL_WIRE_EXTENDED_FIELDS` and Trail's model together; absent values must stay absent (semantic_view.py:233-234).
- `scope()` output paths (`semantics.hypotheses`, `semantics.query`, `semantics.product_reality`, `semantics.trail`, `semantics.by_id.<hypothesis_id>`) are addressed by manifests via `config.show` `semantics.*` and `config.inputs` `context.semantics.*` (semantic_view.py:10-12, semantic_view.py:259-260) — renaming any path breaks manifests.
- `query_projection` reads `view["trail"]["territories"]` (semantic_view.py:204) while `agent_projection` strips `"trail"` (semantic_view.py:192) — `query_projection` must receive the full view, not an agent projection.
- `VIEW_VERSION = "opportunity_semantic_view.v1"` (semantic_view.py:25) is stamped into every view and `build`/`scope` output (semantic_view.py:144, semantic_view.py:185, semantic_view.py:262) — version consumers must be updated in lockstep.

## VERIFY
```verify
grep -Fq 'VIEW_VERSION = "opportunity_semantic_view.v1"' shared/polymath_shared/adapter/semantic_view.py
grep -Fq 'TEXT_CHARS = 400' shared/polymath_shared/adapter/semantic_view.py
grep -Fq 'MAX_ITEMS = 12' shared/polymath_shared/adapter/semantic_view.py
grep -Fq 'MAX_FIELD_EVIDENCE = 24' shared/polymath_shared/adapter/semantic_view.py
grep -Fq 'return {k: v for k, v in out.items() if v not in (None, [])}' shared/polymath_shared/adapter/semantic_view.py
test "$(grep -c -F 'MAX_FIELD_EVIDENCE' shared/polymath_shared/adapter/semantic_view.py)" -ge 4
grep -Fq 'from .hypotheses import ABSORBED_STATUSES' shared/polymath_shared/adapter/semantic_view.py
```
