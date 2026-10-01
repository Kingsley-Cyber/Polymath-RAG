# unit: shared/polymath_shared/contraction_resolution.py
anchor: shared/polymath_shared/contraction_resolution.py:1-178

## purpose
In-document entity contraction resolution (Phase 3): when one document admits a full name ("Crestline Automation") and later a contracted form ("Crestline"), this module reuses the existing longer identity instead of creating a separate graph node — shared/polymath_shared/contraction_resolution.py:1-14 [DERIVED]. Explicitly NOT dedup and NOT similarity matching (RapidFuzz / GLinker / embeddings unused); matching is exact token containment only — shared/polymath_shared/contraction_resolution.py:16-25 [DERIVED]. Sole importer: shared/polymath_shared/execution.py (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `MergeDecision` | class(str, Enum) | members `SAME_ENTITY = "SAME_ENTITY"`, `ABSTAIN = "ABSTAIN"` | shared/polymath_shared/contraction_resolution.py:46-48 | shared/polymath_shared/execution.py (module import) |
| `ContractionResult` | @dataclass(frozen=True) | fields `decision`, `short_surface`, `resolved_to=None`, `shape=None`, `evidence=()`, `candidates=()`, `contract=CONTRACTION_CONTRACT` | shared/polymath_shared/contraction_resolution.py:51-59 | shared/polymath_shared/execution.py (module import) |
| `resolve_contraction` | def | `(short_surface: str, short_type: str, candidates: list[tuple[str, str]]) -> ContractionResult` | shared/polymath_shared/contraction_resolution.py:84-129 | shared/polymath_shared/execution.py (module import) |
| `CanonicalMembership` | @dataclass(frozen=True) | fields `surface`, `core_type`, `canonical_id`, `is_anchor`, `basis`, `contract=CONTRACTION_CONTRACT` | shared/polymath_shared/contraction_resolution.py:141-154 | shared/polymath_shared/execution.py (module import) |
| `canonical_id_for` | def | `(surface: str) -> str` | shared/polymath_shared/contraction_resolution.py:157-158 | shared/polymath_shared/execution.py (module import) |
| `build_memberships` | def | `(admitted: list[tuple[str, str]]) -> dict[str, CanonicalMembership]` | shared/polymath_shared/contraction_resolution.py:161-178 | shared/polymath_shared/execution.py (module import) |

Private helpers: `_tokens` (:62-63), `_is_prefix` (:66-67), `_is_head_preserving_subsequence` (:70-81).

## contracts

**resolve_contraction** — shared/polymath_shared/contraction_resolution.py:84-129
- in: `short_surface` str; `short_type` str; `candidates` list of `(surface, core_type)` pairs already admitted in the SAME document (:89-91).
- pre: candidates carry the same core_type vocabulary as `short_type`; mismatched types are skipped, not errored (:99-101).
- out: `ContractionResult`; `SAME_ENTITY` only when exactly one type-compatible longer candidate contains the short form by exact token identity (:122-128); `ABSTAIN` for empty surface (:93-96), no container (:110-114), or ambiguity (:115-120).
- post: `resolved_to` is verbatim one of the input candidate surfaces; "Never synthesises text" (:90-91).

**build_memberships** — shared/polymath_shared/contraction_resolution.py:161-178
- in: `admitted` list of `(surface, ctype)` pairs.
- out: dict keyed by every admitted surface -> `CanonicalMembership`; contracted forms get `canonical_id_for(r.resolved_to)` with `is_anchor=False`; anchors get `canonical_id_for(surface)` with `is_anchor=True` (:170-177).
- post: every surface retained, nothing rewritten, nothing dropped (:163-165, :167-178).

**canonical_id_for** — shared/polymath_shared/contraction_resolution.py:157-158
- out: `"ent_" + "_".join(_tokens(surface))` — lowercase-alphanumeric token join.

## effect surface
- Postgres tables: none (FACTS.tables_read and tables_written empty).
- Qdrant / files / network / subprocess / env flags: none visible; imports are only `re`, `dataclass`, `Enum` — shared/polymath_shared/contraction_resolution.py:39-41 [DERIVED].

## invariants
INVARIANT: anchor-prefix match requires `len(short) < len(long)` — shared/polymath_shared/contraction_resolution.py:67 [DERIVED]
  fails-if: equal-length token lists could be admitted as contractions of each other.
INVARIANT: head-preserving elision requires `len(short) >= 2` AND `short[0] == long[0]` AND `short[-1] == long[-1]` — shared/polymath_shared/contraction_resolution.py:76-79 [DERIVED]
  fails-if: a lone token like `engine` or a middle-token-only overlap merges unrelated entities.
INVARIANT: candidate `ctype != short_type` -> skipped before any token comparison — shared/polymath_shared/contraction_resolution.py:99-101 [DERIVED]
  fails-if: cross-type merges (e.g. an ORG absorbing a PRODUCT).
INVARIANT: candidate with `lt == st` (identical token lists) -> skipped as "same surface" — shared/polymath_shared/contraction_resolution.py:102-104 [DERIVED]
  fails-if: self-merge / circular resolution.
INVARIANT: `len(matches) == 1` required for `SAME_ENTITY`; `0` and `> 1` both yield `ABSTAIN` — shared/polymath_shared/contraction_resolution.py:110-128 [DERIVED]
  fails-if: ambiguity would silently pick one long form over another equally valid one.
INVARIANT: tokenization lowercases before comparison (`surface.lower()` inside `_tokens`) — shared/polymath_shared/contraction_resolution.py:63 [DERIVED]
  fails-if: case variants of the same name would become separate identities.
INVARIANT: `contract` on both dataclasses defaults to `CONTRACTION_CONTRACT = "contraction-resolution-v1"` — shared/polymath_shared/contraction_resolution.py:43, :59, :154 [DERIVED]
  fails-if: consumers version-checking the contract string would reject or mis-tag results.
INVARIANT: output dict key set == input `admitted` surface set — shared/polymath_shared/contraction_resolution.py:167-178 [DERIVED]
  fails-if: a mention silently disappears from canonical mapping.

## determinism & idempotency
determinism: DETERMINISTIC (pure string/regex + dataclass logic; no clock/random/uuid/network/db/env/concurrency anywhere in :39-178)
idempotency: SAFE (no side effects; frozen dataclasses at :51, :141; `build_memberships` builds a fresh dict at :167)

## failure behaviour
No try/except and no raised error codes anywhere in the file; nothing is swallowed — degradation is by return value, not exception [DERIVED, whole file :1-178].
- Empty surface -> `ABSTAIN` with evidence `("empty surface",)` — :93-96.
- No container -> `ABSTAIN` with evidence `"no longer in-document identity contains this form by exact token containment"` — :110-114.
- Ambiguous (multiple containers) -> `ABSTAIN` with `candidates=tuple(sorted(...))` — :115-120. Caller always receives a `ContractionResult`.

## dumb-code flags
- Dead filter: `if t` in `_tokens` can never drop an item — the regex `[A-Za-z0-9][A-Za-z0-9\-]*` cannot match an empty string — shared/polymath_shared/contraction_resolution.py:63 [INFERRED: pattern starts with a mandatory character class].
- Canonical-id collision: two admitted surfaces with identical lowercase tokens are skipped as "same surface" (:102-104) yet BOTH become anchors, each with `is_anchor=True` and the identical id `canonical_id_for(surface)` — silent merge at the graph join key — shared/polymath_shared/contraction_resolution.py:103, :157-158, :175-177 [INFERRED: lowercasing at :63 makes distinct strings token-equal].
- Asymmetric `candidates` on ABSTAIN: ambiguity path fills it with sorted surfaces (:120) while no-match and empty-surface paths leave `candidates=()` — consumers cannot assume it is populated on every abstain — shared/polymath_shared/contraction_resolution.py:95-96, :111-114, :117-120 [DERIVED].
- Shape labels `"anchor-prefix"` and `"head-preserving elision"` are free-form strings embedded into `basis` via f-string — no enum/contract for their format — shared/polymath_shared/contraction_resolution.py:106, :108, :173 [DERIVED].

## refactor notes
- Signatures and class shapes above are consumed by shared/polymath_shared/execution.py (FACTS.importers); renames or signature changes break that importer — blast radius includes at least execution.py.
- `canonical_id` is "what the graph joins on" (:146-147); changing the `"ent_" + "_".join(_tokens(surface))` format at :158 re-keys every existing graph entity — shared/polymath_shared/contraction_resolution.py:146-147, :157-158.
- `CONTRACTION_CONTRACT = "contraction-resolution-v1"` is the default tag on every `ContractionResult` and `CanonicalMembership`; changing it changes serialized contract tags — :43, :59, :154.
- Phase 3 settlement policy (:132-138): resolution merges canonical identity only and must never rewrite a mention/fact surface to pick a preferred label (frozen gold canonicalizes `CareChart EMR` short but `FreightNet routing platform` long); display-label selection stays a separate concern — do not add label rewriting here — shared/polymath_shared/contraction_resolution.py:132-138.

## VERIFY
```verify
grep -Fq 'CONTRACTION_CONTRACT = "contraction-resolution-v1"' shared/polymath_shared/contraction_resolution.py
grep -Fq 'return "ent_" + "_".join(_tokens(surface))' shared/polymath_shared/contraction_resolution.py
grep -Fq 'if short[0] != long[0] or short[-1] != long[-1]:' shared/polymath_shared/contraction_resolution.py
grep -Fq 'return all(t in it for t in short)' shared/polymath_shared/contraction_resolution.py
! grep -Fq 'import rapidfuzz' shared/polymath_shared/contraction_resolution.py
test "$(grep -c -F 'MergeDecision.ABSTAIN' shared/polymath_shared/contraction_resolution.py)" -ge 3
```
