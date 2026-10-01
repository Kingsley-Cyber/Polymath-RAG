# unit: shared/polymath_shared/canonicalizer.py
anchor: shared/polymath_shared/canonicalizer.py:1-266

## purpose
C1: deterministic Stage-2 corpus canonicalization policy, pure module. Turns document-local entities into a canonical registry without erasing source-local identity (ADR 0009), preserving the chain `canonical_entity -> membership -> local entity -> fact -> evidence -> source document/span` — shared/polymath_shared/canonicalizer.py:1-7 [DERIVED]. Consumed by `workers/workers/canonicalize_worker.py` (FACTS.importers). Policy: conservative — false merges are worse than missed merges; no fuzzy matching, no LLM, no string-similarity merges — shared/polymath_shared/canonicalizer.py:9, 22-23 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `normalize_surface` | def | `(surface: str) -> str` | shared/polymath_shared/canonicalizer.py:54-59 | workers/workers/canonicalize_worker.py |
| `CanonicalEntityRow` | class (frozen dataclass) | fields: `corpus_id, canonical_id, canonical_type, normalized_name, canonicalizer_version` | shared/polymath_shared/canonicalizer.py:62-68 | workers/workers/canonicalize_worker.py |
| `MembershipRow` | class (frozen dataclass) | fields: `corpus_id, canonical_id, local_entity_id, decision, confidence, basis, canonicalizer_version` | shared/polymath_shared/canonicalizer.py:71-79 | workers/workers/canonicalize_worker.py |
| `DecisionRow` | class (frozen dataclass) | fields: `corpus_id, decision_id, local_entity_a, local_entity_b, decision, confidence, basis, canonical_id, canonicalizer_version` | shared/polymath_shared/canonicalizer.py:82-92 | workers/workers/canonicalize_worker.py |
| `CanonicalizationOutput` | class (dataclass) | fields: `corpus_id, canonicalizer_version`, lists default `[]` | shared/polymath_shared/canonicalizer.py:95-101 | workers/workers/canonicalize_worker.py |
| `canonicalize` | def | `(corpus_id: str, entities: list[dict], aliases: dict[str, list[str]] | None = None) -> CanonicalizationOutput` | shared/polymath_shared/canonicalizer.py:126-266 | workers/workers/canonicalize_worker.py |

Module constants: `CANONICALIZER_VERSION = "1.0.0"` (line 41), `MERGEABLE_CORE_TYPES = frozenset({"Organization", "Location", "Product", "Technology", "Document"})` (43-45), `ABSTAIN_CORE_TYPES = frozenset({"Person", "Concept", "Event", "Method", "Process", "Measurement", "TimeReference"})` (46-49). Private helpers `_canonical_id` (104-114), `_pair_decision_id` (117-123).

## contracts

**`normalize_surface(surface)`** — shared/polymath_shared/canonicalizer.py:54-59
- in: any str; `None`/empty coerced via `str(surface or "")` (57).
- out: NFC normalize → collapse whitespace + lowercase → strip edge punctuation via `_PUNCT_EDGE_RE = re.compile(r"^[\W_]+|[\W_]+$")` (51, 57-59).
- post: never a fuzzy match (docstring 55-56).

**`canonicalize(corpus_id, entities, aliases=None)`** — shared/polymath_shared/canonicalizer.py:126-266
- in: `entities` rows are dicts `{entity_id, core_type, normalized_surface}` (133-135); `aliases` maps normalized canonical surface -> list of normalized alias surfaces, explicit corpus-profile declarations only, never inferred (134-136).
- pre: each entity row must contain key `"entity_id"` — direct index at 149 raises KeyError if absent; `core_type`/`normalized_surface` default to `""` via `.get` (150-151).
- post: outputs sorted — `canonical_entities` by `(normalized_name, canonical_id)`, `memberships` by `local_entity_id`, `decisions` by `decision_id` (263-265).
- post: membership/pair decisions are exactly one of `SELF`, `ALIAS_OF`, `SAME_AS`, `AMBIGUOUS`, `UNRESOLVED` (11-20, 177-239).
- post: merge rule — mergeable type class merges on exact normalized name (162-163); abstain classes merge only if an explicit alias was declared (164-166, `merge = alias_declared`); unknown/empty type never merges (168).
- post: abstain branch emits singleton canonical entities with pairwise `AMBIGUOUS` (abstain types) or `UNRESOLVED` (unknown type) decisions, `canonical_id=None` in the decision row (210-240).

## effect surface
- Postgres tables read/written: none — `tables_read: []`, `tables_written: []` (FACTS) [DERIVED].
- Qdrant / files / network / subprocess / env flags: none — imports are only `re`, `unicodedata`, `dataclasses`, `polymath_shared.identity.content_hash` (35-39) [DERIVED].

## invariants
INVARIANT: MERGEABLE_CORE_TYPES ∩ ABSTAIN_CORE_TYPES = ∅ (5 types vs 7 types, disjoint) — shared/polymath_shared/canonicalizer.py:43-49 [DERIVED]
  fails-if: a type in both sets hits the `core_type in MERGEABLE_CORE_TYPES` branch first (162) and silently merges instead of abstaining.
INVARIANT: merge-branch membership confidence = 1.0 always — shared/polymath_shared/canonicalizer.py:188-190 [DERIVED]
  fails-if: downstream filtering `confidence < 1.0` would drop merged members.
INVARIANT: abstain-branch membership confidence = `1.0 if decision == "SELF" else 0.0` — shared/polymath_shared/canonicalizer.py:225 [DERIVED]
  fails-if: UNRESOLVED singleton rows would look confirmed at 1.0.
INVARIANT: canonical_id = `"cent_" + content_hash({v, corpus, type, name})`; abstain singletons add `"local": local_entity_id` — shared/polymath_shared/canonicalizer.py:106-114, 214 [DERIVED]
  fails-if: mergeable-class ids embedding the member list would rehash on every added document (stability claim, docstring 29-31).
INVARIANT: decision_id is symmetric — `x, y = sorted((a, b))` — shared/polymath_shared/canonicalizer.py:118 [DERIVED]
  fails-if: (a,b) and (b,a) yield two decision rows for the same pair.
INVARIANT: input entities grouped in `entity_id`-sorted order and groups iterated `sorted(groups)` — shared/polymath_shared/canonicalizer.py:148, 158, 270 [DERIVED]
  fails-if: same entity set produces different output depending on input order (docstring 27-28).
INVARIANT: every row carries `canonicalizer_version` = `CANONICALIZER_VERSION` — shared/polymath_shared/canonicalizer.py:171-175, 188-191, 206-209 [DERIVED]
  fails-if: mixed-version registries cannot be distinguished downstream.

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/network/db/env; ids are content hashes (`polymath_shared.identity.content_hash`, import at 39) over version-keyed dicts, inputs sorted (148, 158, 118), outputs re-sorted (263-265).
idempotency: SAFE — pure function, no writes, no side effects; same entity set yields identical output (docstring 27-28).

## failure behaviour
No try/except handlers exist in the unit; nothing is swallowed. Malformed entity rows raise `KeyError` at `entity["entity_id"]` (149) and propagate to the caller — shared/polymath_shared/canonicalizer.py:149 [INFERRED: no handler between raise and caller]. `normalize_surface` never raises on empty/None input (57).

## dumb-code flags
- Type-class lists duplicated: docstring policy lines 11-19 repeat the member names of `MERGEABLE_CORE_TYPES`/`ABSTAIN_CORE_TYPES` (43-49) — drift risk when a type is added [DERIVED].
- Magic confidence literals `1.0` / `0.0` repeated at 190, 225, 240, 259-260 with no named constant [DERIVED].
- All four row dataclasses have empty docstrings (`doc: ""` in FACTS symbols) [DERIVED].
- Abstain branch computes membership confidence via conditional although `decision` there is only `SELF` or `UNRESOLVED` (216-220, 225) — the `0.0` arm fires only for `UNRESOLVED` [DERIVED].

## refactor notes
- `workers/workers/canonicalize_worker.py` imports this module (FACTS.importers); renaming/reordering the frozen dataclass fields or the `canonicalize` signature breaks that worker positionally — shared/polymath_shared/canonicalizer.py:62-101, 126-130.
- `CANONICALIZER_VERSION` is baked into every id basis (`"v": CANONICALIZER_VERSION`, 107 and 120) and every row — bumping `"1.0.0"` regenerates all `cent_`/`dec_` ids; any stored downstream ids need migration — shared/polymath_shared/canonicalizer.py:41, 107, 120 [INFERRED: ids are hashes over the version key].
- `"cent_"` (114) and `"dec_"` (123) prefixes are part of the id contract.
- Group key `(canon_surface, core_type)` (153) and the three sort keys (263-265) define output byte-identity; changing them changes any hash-of-output checks.
- The alias-override rule `merge = alias_declared` for abstain classes (166) is the only place explicit declarations beat homonym risk — removing it makes Persons/Concepts unmergeable.

## VERIFY
```verify
grep -Fq 'CANONICALIZER_VERSION = "1.0.0"' shared/polymath_shared/canonicalizer.py
grep -Fq 'return "cent_" + content_hash(basis)' shared/polymath_shared/canonicalizer.py
grep -Fq 'x, y = sorted((a, b))' shared/polymath_shared/canonicalizer.py
grep -Fq 'from polymath_shared.identity import content_hash' shared/polymath_shared/canonicalizer.py
! grep -Fq 'import random' shared/polymath_shared/canonicalizer.py
test "$(grep -c -F 'SAME_AS' shared/polymath_shared/canonicalizer.py)" -ge 4
```
