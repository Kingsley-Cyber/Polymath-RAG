# unit: shared/polymath_shared/entity_harbor.py
anchor: shared/polymath_shared/entity_harbor.py:1-202

## purpose
Defines the ENTITY-HARBOR-V1 admission-contract vocabulary (enums + frozen dataclasses) and two gates: `graph_eligible` (the single graph-eligibility authority for projector, control census, verifier, and canonical fact promotion) and `canonical_fact_admissible` (PHASE 2C canonical-fact gate) — shared/polymath_shared/entity_harbor.py:1-31,124-133,169-175 [DERIVED].
Deliberately contains no classifier: `classify` always raises; inferring classification from morphology is forbidden by the module invariant — shared/polymath_shared/entity_harbor.py:5-15,149-166 [DERIVED].
Importers: `shared/polymath_shared/admission_interpreter.py`, `shared/polymath_shared/discourse_reference.py`, `shared/polymath_shared/execution.py` (FACTS.importers, module granularity).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `HARBOR_CONTRACT` | constant | `= "entity-harbor-v1"` | entity_harbor.py:31 | module importers |
| `AnchorKind` | class (str, Enum) | IDENTITY / CONCEPT / LOCAL_REFERENCE / GENERIC / UNKNOWN | entity_harbor.py:34-47 | module importers |
| `DecisionStatus` | class (str, Enum) | RESOLVED / CONTEXT_REQUIRED / ABSTAINED | entity_harbor.py:50-55 | module importers |
| `Referentiality` | class (str, Enum) | SPECIFIC / GENERIC / UNRESOLVED | entity_harbor.py:58-61 | module importers |
| `ReferenceBasis` | class (str, Enum) | ANTECEDENT_RESOLVED / DOCUMENT_CONSTITUTED / EXTERNAL_UNRESOLVED / AMBIGUOUS | entity_harbor.py:64-71 | module importers |
| `StructuralEvidence` | frozen dataclass | 8 fields, all defaulted (e.g. `head_lemma: str = ""`, `determiner: str | None = None`) | entity_harbor.py:74-90 | module importers |
| `HarborDecision` | frozen dataclass | + `__post_init__`, property `settled -> bool` | entity_harbor.py:93-121 | module importers |
| `graph_eligible` | def | `(decision: HarborDecision) -> bool` | entity_harbor.py:124-146 | module importers |
| `classify` | def | `(surface: str, *, core_type: str, structural=None, discourse=None) -> HarborDecision` — raises | entity_harbor.py:149-166 | — (unimplemented) |
| `canonical_fact_admissible` | def | `(subject: HarborDecision, obj: HarborDecision) -> tuple[bool, str]` | entity_harbor.py:169-188 | module importers |
| `_why` | def (private) | `(d: HarborDecision) -> str` | entity_harbor.py:191-202 | `canonical_fact_admissible` |

## contracts

`HarborDecision.__post_init__` — entity_harbor.py:111-117 [DERIVED]
- pre: `reference_basis is None` OR `anchor_kind is AnchorKind.LOCAL_REFERENCE`, else `ValueError("reference_basis is only meaningful for LOCAL_REFERENCE")` — :112-113
- pre: `resolves_to is None` OR `reference_basis is ReferenceBasis.ANTECEDENT_RESOLVED`, else `ValueError("resolves_to requires ANTECEDENT_RESOLVED")` — :114-115
- pre: NOT (`anchor_kind is AnchorKind.UNKNOWN` AND `decision_status is DecisionStatus.RESOLVED`), else `ValueError("UNKNOWN anchor_kind cannot be RESOLVED")` — :116-117

`graph_eligible` — entity_harbor.py:124-146 [DERIVED]
- in: one `HarborDecision`; out: `bool`; no side effects, no stored value — :126-129
- order of checks: (1) `not decision.settled` → `False` :134-135; (2) `anchor_kind in (GENERIC, UNKNOWN)` → `False` :136-137; (3) `scope == "MENTION_ONLY"` → `False` :138-139; (4) `LOCAL_REFERENCE` + `ANTECEDENT_RESOLVED` → `decision.resolved_anchor_eligible is not False` :140-144; (5) other `LOCAL_REFERENCE` → basis is `DOCUMENT_CONSTITUTED` :145; (6) else → `anchor_kind in (IDENTITY, CONCEPT)` :146

`classify` — entity_harbor.py:149-166 [DERIVED]
- always raises `NotImplementedError("ENTITY-HARBOR classify() is not authorized (REVISION 3b). ...")` — :162-166
- authorization precondition (per docstring): "an auditable concept source ... and a discourse consumer for `reference_basis`" — :156-159

`canonical_fact_admissible` — entity_harbor.py:169-188 [DERIVED]
- in: two `HarborDecision`; out: `(False, "subject not graph-eligible: ...")` / `(False, "object not graph-eligible: ...")` / `(True, "both endpoints graph-eligible")` — :184-188
- delegates to the same `graph_eligible` for both endpoints; no eligibility value stored — :172-175

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`)
- Qdrant collections, files, network, subprocess, env flags: none — only stdlib imports `dataclasses.dataclass`, `dataclasses.field`, `enum.Enum` — entity_harbor.py:26-29 [DERIVED]

## invariants
INVARIANT: `HarborDecision.contract` default == `HARBOR_CONTRACT` == `"entity-harbor-v1"` — entity_harbor.py:31,109 [DERIVED]
  fails-if: decisions from another contract version pass through gates indistinguishably.
INVARIANT: `decision_status != RESOLVED` ⇒ `graph_eligible == False` — entity_harbor.py:134-135 [DERIVED]
  fails-if: unsettled/abstained mentions get promoted to graph entities.
INVARIANT: `anchor_kind in (GENERIC, UNKNOWN)` ⇒ `graph_eligible == False` — entity_harbor.py:136-137 [DERIVED]
  fails-if: a plurality ("others") becomes a canonical entity (E4 note :104-108).
INVARIANT: `scope == "MENTION_ONLY"` ⇒ `graph_eligible == False` — entity_harbor.py:138-139 [DERIVED]
  fails-if: mere mentions asserted as canonical knowledge.
INVARIANT: `reference_basis is not None` ⇒ `anchor_kind is LOCAL_REFERENCE` — entity_harbor.py:112-113 [DERIVED]
  fails-if: basis set on non-local kinds, silently corrupting eligibility logic.
INVARIANT: `resolves_to is not None` ⇒ `reference_basis is ANTECEDENT_RESOLVED` — entity_harbor.py:114-115 [DERIVED]
  fails-if: anaphora links created without a resolved antecedent.
INVARIANT: `anchor_kind is UNKNOWN` ⇒ `decision_status != RESOLVED` — entity_harbor.py:116-117 [DERIVED]
  fails-if: "RESOLVED but unknown kind" — evidence-arrival looks like type change (PHASE 2A rationale :37-41).
INVARIANT: LOCAL_REFERENCE + ANTECEDENT_RESOLVED ⇒ eligible == `resolved_anchor_eligible is not False` (None inherits eligibility; only explicit `False` blocks) — entity_harbor.py:140-144 [DERIVED]
  fails-if: "successful anaphora must never manufacture identity" — :104-107.

## determinism & idempotency
determinism: DETERMINISTIC — pure functions over enums/frozen dataclasses; no clock/random/uuid/network/db/env reads (only imports `dataclasses`, `enum`) — entity_harbor.py:26-29 [DERIVED]. `classify` is a deterministic raise — entity_harbor.py:162-166 [DERIVED].
idempotency: SAFE — `StructuralEvidence` and `HarborDecision` are `@dataclass(frozen=True)`, no state mutated — entity_harbor.py:74,93 [DERIVED].

## failure behaviour
- No try/except in the unit; nothing is swallowed — entity_harbor.py:1-202 [DERIVED].
- `classify` raises `NotImplementedError` on every call with the full message "ENTITY-HARBOR classify() is not authorized (REVISION 3b). Requires an auditable concept source and a discourse consumer; morphological inference is explicitly forbidden." — entity_harbor.py:162-166 [DERIVED].
- `HarborDecision` construction raises `ValueError` on 3 invariant violations — entity_harbor.py:113,115,117 [DERIVED].
- `graph_eligible` abstains (returns `False`) instead of raising for unsettled decisions: "abstention is the safe direction for a precision gate" — entity_harbor.py:131-132,134-135 [DERIVED].

## dumb-code flags
- `"MENTION_ONLY"` is a bare magic string compared twice (`== "MENTION_ONLY"` at :139 and :199); `scope: str` is untyped (:98), not an enum — typo risk — entity_harbor.py:98,139,199 [DERIVED].
- Member name `GENERIC` exists in two enums with different meanings: `AnchorKind.GENERIC` (:46) vs `Referentiality.GENERIC` (:60) — entity_harbor.py:46,60 [DERIVED].
- `resolved_anchor_eligible: bool | None = None` is a tri-state; `None` means "unknown/not applicable" (:108) but is treated as eligible by `is not False` (:144) — entity_harbor.py:108,144 [DERIVED].
- `classify` is a permanent raise (dead by design, REVISION 3b) — any runtime path reaching it fails — entity_harbor.py:152-166 [DERIVED].
- `StructuralEvidence` docstring hardcodes test fixture ids `ctx-08 / ctx-09` in production code — entity_harbor.py:80 [DERIVED].

## refactor notes
- `graph_eligible` is "THE single eligibility authority" for four consumers (projector, control census, verifier, canonical fact promotion, :127-129; "One authority, four consumers" :175-176) — changing its logic changes all four simultaneously — entity_harbor.py:124-146,169-188 [DERIVED].
- Adding any stored/cached `graph_eligible` value ("no `graph_eligible` value is stored anywhere", :175) creates a second authority — must not — entity_harbor.py:127-128,175 [DERIVED].
- Signature/type changes to `HarborDecision`, `graph_eligible`, `canonical_fact_admissible` hit the three importers: `shared/polymath_shared/admission_interpreter.py`, `shared/polymath_shared/discourse_reference.py`, `shared/polymath_shared/execution.py` (FACTS.importers) [DERIVED].
- Implementing `classify` requires an auditable concept source + a discourse consumer; surface-string inference recreates "the two-token bug" and violates the module invariant — entity_harbor.py:11-15,154-159 [DERIVED].
- Changing `HARBOR_CONTRACT` value changes the default on every new `HarborDecision` and orphans existing ones carrying the old string — entity_harbor.py:31,109 [DERIVED].
- Moving `CONTEXT_REQUIRED` back into `AnchorKind` undoes PHASE 2A: it answers decision state, not referent type — entity_harbor.py:37-41 [DERIVED].

## VERIFY
```verify
grep -Fq 'HARBOR_CONTRACT = "entity-harbor-v1"' shared/polymath_shared/entity_harbor.py
grep -Fq 'def graph_eligible(decision: HarborDecision) -> bool:' shared/polymath_shared/entity_harbor.py
grep -Fq 'raise NotImplementedError(' shared/polymath_shared/entity_harbor.py
grep -Fq 'if decision.scope == "MENTION_ONLY":' shared/polymath_shared/entity_harbor.py
test "$(grep -c -F 'ValueError' shared/polymath_shared/entity_harbor.py)" -ge 3
test "$(grep -c -F 'MENTION_ONLY' shared/polymath_shared/entity_harbor.py)" -ge 2
! grep -Fq 'self.graph_eligible' shared/polymath_shared/entity_harbor.py
```
