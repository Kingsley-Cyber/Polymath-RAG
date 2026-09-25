---
change_id: CANONICAL-SURFACE-REGISTRY-V1
owner: king
date: 2026-09-17
status: complete
status_note: "Done: one taxonomy source, behaviour-identical; group is used by the scout; graph_policy waits on the deferred graph work. (was: implemented)"
architecture_impact: one deterministic registry becomes the single source for typed-surface treatment
last_reviewed: 2026-09-17
---

## Contract

Librarian checklist P4a (part 1). The typed-surface taxonomy was defined in THREE places —
`projection.DENSE/MULTI_SURFACES`, `profile_atom.ATOM_KINDS`/families/`_ATTR_TO_KIND`, and an
inlined copy in `query_intent._MECH`/`_ALL_ATOMS` (commented "inlined to avoid an import
cycle"). A single deterministic `SurfaceRegistry` now declares each surface's storage /
projection / retrieval treatment once; the three sites read from it. Behaviour is byte-for-byte
preserved (asserted). The registry also adds forward-declared policy the later slices consume:
per-surface `group` (direct/semantic/discovery/lexical/identity) and a `graph` policy
(`off` | `resolve_on_use`) so discovery surfaces (SEEALSO/BRIDGE/TENSION) can become a
`PROFILE_SYNTHETIC` Neo4j edge ONLY after endpoint resolution — never a direct edge from text.

## Changes

- `shared/polymath_shared/surface_registry.py` (NEW): leaf module (dataclass only, no
  document_profile/query_intent imports → the cycle that forced the inline copy is gone).
  Ordered `SURFACES` reproduces `DENSE_SURFACES`, `MULTI_SURFACES`, `ATOM_KINDS`,
  `MECHANISM/RELATIONAL/REDISCOVERY_KINDS`, and `ATTR_TO_KIND` exactly; adds
  `GRAPH_RESOLVABLE_KINDS`, `group_surfaces()`, `graph_policy()`.
- `document_profile/profile_atom.py`: imports the taxonomy from the registry (removed the
  literal ATOM_KINDS/families/_ATTR_TO_KIND).
- `document_profile/projection.py`: `DENSE_SURFACES`/`MULTI_SURFACES` now come from the registry.
- `query_intent.py`: `_MECH`/`_ALL_ATOMS` now come from the registry (inline duplication removed).
- `tests/determinism/test_surface_registry.py` (NEW): asserts derived == historical literals,
  every consumer reads from the registry, graph policy = resolve_on_use only for SEEALSO/BRIDGE/
  TENSION (never a text edge), and the semantic groups.

## Proof

`pytest test_surface_registry test_profile_atom test_profile_selection
test_document_profile_projection test_document_profile_stage test_query_intent
test_candidate_engine test_u1_intent_routing_contract` → 108 passed, 3 skipped. The registry is
`is`-identical to the consumer constants (`profile_atom.ATOM_KINDS is registry.ATOM_KINDS`, etc.).

## Rejected claims

- "Model the surfaces as an ontology / inference layer." Rejected per owner directive — the
  registry is a deterministic data table; the compiler still types, the registry only routes.
- "Derive ANSWER_SURFACES/EXPLORATION_SURFACES from group." Deferred — those are retrieval-time
  surface SETS (a nomination policy), left literal in projection.py to preserve behaviour; the
  registry supplies the intrinsic per-surface policy only.

## Open contract gaps

- The `graph` policy and `group` classification are DECLARED but not yet CONSUMED (P3b Neo4j
  discovery edges and P5/P8 surface sets read them in later slices).
- No live-path change in this slice (pure single-source refactor); nothing to live-qualify.
