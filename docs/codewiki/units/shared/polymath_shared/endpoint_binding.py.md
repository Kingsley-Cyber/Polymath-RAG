# unit: shared/polymath_shared/endpoint_binding.py
anchor: shared/polymath_shared/endpoint_binding.py:1-248

## purpose
Deterministic E3B endpoint-binding guards for the relation compiler: "GLiNER PROPOSES. DETERMINISTIC CODE DECIDES." — shared/polymath_shared/endpoint_binding.py:2-5 [DERIVED]
Four guard families tighten relation admission without a new learned model: predicate endpoint-type families (`has_role` / `instance_of` / `owns`), surface-weak trigger locality, title/body pairing restriction, coordination-aware binding — shared/polymath_shared/endpoint_binding.py:5-12 [DERIVED]
No name blacklists, no hardcoded entities, no ontology changes; `has_role` object family maps to concept-like core types as a documented family mapping — shared/polymath_shared/endpoint_binding.py:13-17 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `BindingVerdict` | class (frozen dataclass) | (ok: bool, reason: str) | shared/polymath_shared/endpoint_binding.py:43-46 | — |
| `predicate_endpoint_types_ok` | def | (predicate: str, subject_type: str, object_type: str) -> BindingVerdict | shared/polymath_shared/endpoint_binding.py:49-59 | — |
| `surface_weak_locality_ok` | def | (trigger_start, trigger_end, subject_start, subject_end, object_start, object_end, between_required: bool = True) -> BindingVerdict | shared/polymath_shared/endpoint_binding.py:62-86 | — |
| `title_pairing_ok` | def | (chunk_text: str, subject_text: str, subject_start: int, object_text: str, object_start: int, chunk_char_start: int = 0) -> BindingVerdict | shared/polymath_shared/endpoint_binding.py:89-116 | — |
| `coordination_aware_ok` | def | (sentence_text: str, trigger_start: int, subject_start: int, subject_end: int, object_start: int, object_end: int) -> BindingVerdict | shared/polymath_shared/endpoint_binding.py:119-146 | — |
| `binding_gate_violation` | def | (rule: dict, subject_type: str, object_type: str, orientation: str, candidate: Any, agent_cand: Any, patient_cand: Any) -> Optional[str] | shared/polymath_shared/endpoint_binding.py:149-248 | — |

## contracts

**predicate_endpoint_types_ok** — shared/polymath_shared/endpoint_binding.py:49-59
- in: predicate name; subject/object type strings.
- out: `(True, "no_type_family_defined")` when predicate not in `_PREDICATE_FAMILIES` — :52-53; `(False, f"{predicate}: subject {subject_type} not owner-like")` — :55-56; `(False, f"{predicate}: object {object_type} not role/class/ownable-like")` — :57-58; `(True, "type_family_ok")` — :59.
- pre: none.
- post: unknown predicates always pass — :52-53.

**surface_weak_locality_ok** — shared/polymath_shared/endpoint_binding.py:62-86
- in: six integer offsets; `between_required: bool = True` default — :64.
- out: `"trigger_outside_endpoint_span"` — :80-82; `"endpoints_not_local_to_trigger"` — :83-85; `"locality_ok"` — :86.
- pre: between-ness uses `lo = min(subject_start, object_start)`, `hi = max(subject_end, object_end)` — :78-79; satisfied if either trigger edge lies in `[lo, hi]` — :80-81.
- post: `between_required=False` (RELCL_ANTECEDENT path) skips only the between check; the 100-char distance check still applies — :69-77, :83-85.

**title_pairing_ok** — shared/polymath_shared/endpoint_binding.py:89-116
- in: chunk text plus entity texts and start offsets.
- out: `"title_subject_paired_with_body"` — :113; `"title_object_paired_with_body"` — :115; `"title_pairing_ok"` — :116.
- pre: heading lines detected via `stripped.startswith("#")` or `stripped.upper().startswith("TITLE:")` — :99; entity is in a heading iff `hs <= start < he and text.strip() in htext` — :104-108.
- post: mixed heading/body pair rejected; both-heading or both-body pass — :110-116.

**coordination_aware_ok** — shared/polymath_shared/endpoint_binding.py:119-146
- in: sentence text plus trigger/subject/object offsets.
- out: `(True, "single_clause")` when no split match — :123-125; `(True, "trigger_unlocated")` — :142-143; `(False, "endpoints_outside_trigger_clause")` — :144-145; `(True, "clause_ok")` — :146.
- pre: clause split on `_COORDINATION_SPLIT_RE = re.compile(r",\s+while\s+|,\s+but\s+|;\s+")` — :34.
- post: unlocatable trigger is permissive (returns True) — :142-143.

**binding_gate_violation** — shared/polymath_shared/endpoint_binding.py:149-248
- in: `rule` with key `"id"` and optional `"evidence"` inventory (`verbs`/`nouns`/`multiword` lists) — :174-175, :180-182; `candidate.evidence` (`.text`, `.trigger_lemma`, `.start`, `.end`) — :171, :178-179, :221, :241-242; `agent_cand.span` / `patient_cand.span` (`.start`, `.end`, `.text`) — :172-173, :219-223; `candidate.sentence_text` / `.sentence_start` / `.lexical_semantic_evidence` via getattr with defaults — :215-216, :236.
- out: rejection string (every one prefixed `"binding:"`) or `None` (accepted) — :192-213, :227, :233, :247-248.
- pre: spans/trigger offsets are absolute; converted to sentence-relative via `max(0, x - sentence_start)` — :219-221, :240-243.
- post: predicate-specific gates per `pid`: `has_role` requires trigger in inventory — :191-193; `has_role` + `surface_weak` requires verb lemma or multiword surface — :194-204; `owns` + lemma `"control"` + `surface_weak` rejected — :205-208; `instance_of` + object_type `"Organization"` requires multiword surface — :209-213; `between_required=not tree_licensed_object` where `tree_licensed_object` is any `binding_sources` value `"RELCL_ANTECEDENT"` — :236-244.

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`).
- Qdrant collections, files, network, subprocess: none — pure in-memory functions.
- Env flags read: none; `import os` present but unused — shared/polymath_shared/endpoint_binding.py:21 [DERIVED]

## invariants
INVARIANT: `_SURFACE_WEAK_MAX_ENDPOINT_DISTANCE` == 100 — shared/polymath_shared/endpoint_binding.py:32 [DERIVED]
  fails-if: both `(trigger_start - subject_end)` and `(trigger_start - object_end)` exceed 100 → rejected as `endpoints_not_local_to_trigger` — :83-85
INVARIANT: `_PREDICATE_FAMILIES["has_role"]` == (`{"Person"}`, `_CLASS_LIKE`) — shared/polymath_shared/endpoint_binding.py:37 [DERIVED]
INVARIANT: `_PREDICATE_FAMILIES["instance_of"]` == (`None`, `_CLASS_LIKE`) — no subject constraint — shared/polymath_shared/endpoint_binding.py:38 [DERIVED]
INVARIANT: `_PREDICATE_FAMILIES["owns"]` == (`{"Person", "Organization"}`, `{"Organization", "Product", "Technology", "Document", "Location", "Concept"}`) — shared/polymath_shared/endpoint_binding.py:39 with :29-30 [DERIVED]
INVARIANT: `_CLASS_LIKE` ∩ `_OWNABLE` == `{"Concept", "Technology"}` — a Concept or Technology object satisfies both `has_role` and `owns` object families — shared/polymath_shared/endpoint_binding.py:28,30 [DERIVED]
INVARIANT: unknown predicate -> `(True, "no_type_family_defined")` — shared/polymath_shared/endpoint_binding.py:52-53 [DERIVED]
  fails-if: typo'd predicate name silently bypasses the type gate
INVARIANT: `between_required` default == True; flipped to False only for `RELCL_ANTECEDENT` binding sources — shared/polymath_shared/endpoint_binding.py:64, :236-244 [DERIVED]
INVARIANT: `owns` + trigger_lemma `"control"` + orientation `"surface_weak"` -> always rejected — shared/polymath_shared/endpoint_binding.py:205-208 [DERIVED]
INVARIANT: `BINDING_GATES_VERSION` == `"endpoint-binding-v1"` — shared/polymath_shared/endpoint_binding.py:26 [DERIVED]
  fails-if: gate logic changes without version bump mislabel consumers of gate behavior — [INFERRED] constant exists only to tag gate behavior; no in-file reader

## determinism & idempotency
determinism: DETERMINISTIC — regex + dataclass logic over inputs only; imports are `os`/`re`/`dataclasses`/`typing` with no clock/random/uuid/network/db/env access — shared/polymath_shared/endpoint_binding.py:21-24 [DERIVED]
idempotency: SAFE — stateless predicates returning frozen dataclasses / strings; no mutation — shared/polymath_shared/endpoint_binding.py:43-46 [DERIVED]

## failure behaviour
No try/except anywhere in the unit; failures are returned, not raised — shared/polymath_shared/endpoint_binding.py:149-248 [DERIVED]
Mixed attribute access: `candidate.evidence`, `agent_cand.span`, `patient_cand.span`, `ev.start/ev.end` are direct (AttributeError if absent) — :171-173, :221, :241-243; `sentence_text`/`sentence_start`/`lexical_semantic_evidence` use getattr defaults `None`/`0`/`None` — :215-216, :236 [DERIVED]
Permissive fallbacks visible in SOURCE: unknown predicate family passes — :52-53; trigger segment unlocated passes (`"trigger_unlocated"`) — :142-143; empty `sentence_text` skips both title and coordination gates — :218 [DERIVED]
Error codes raised: none; `binding_gate_violation` returns `Optional[str]` — :149-157, :248 [DERIVED]

## dumb-code flags
`import os` unused — shared/polymath_shared/endpoint_binding.py:21 [DERIVED]
`chunk_char_start: int = 0` parameter of `title_pairing_ok` never referenced in the body — shared/polymath_shared/endpoint_binding.py:91 vs :94-115 [DERIVED]
Locality check one-sided: only `(trigger_start - subject_end/object_end) > 100` tested; endpoints positioned after the trigger are never distance-checked — shared/polymath_shared/endpoint_binding.py:83-84 [DERIVED]
`seg_of(start, end)` ignores its `end` argument (`if bs <= start < be`); `subject_end`/`object_end` params of `coordination_aware_ok` unused for matching — shared/polymath_shared/endpoint_binding.py:133-137 [DERIVED]
Generic rejection text `"not owner-like"` emitted for every predicate including `instance_of` — shared/polymath_shared/endpoint_binding.py:56 [DERIVED]
Title gate invoked with `sentence_text`, where heading markers `"#"`/`"TITLE:"` are unlikely, so the gate is probably inert on this path — shared/polymath_shared/endpoint_binding.py:222-225 vs :99 [INFERRED] gate was written for chunk text but called per-sentence

## refactor notes
Rejection strings prefixed `"binding:"` (:227, :233, :247) and verdict reason literals are the caller-visible contract; renaming breaks downstream matching.
`_PREDICATE_FAMILIES` keys and the `pid` branches (`"has_role"`/`"owns"`/`"instance_of"`) must stay in sync with rule pack ids — :174, :191, :205, :209; a renamed rule id falls through to permissive `"no_type_family_defined"` (:52-53) and skips its specific gate — shared/polymath_shared/endpoint_binding.py:36-40, :191-213 [DERIVED]
`BINDING_GATES_VERSION = "endpoint-binding-v1"` (:26) should change whenever gate behavior changes; consumers are outside this unit — shared/polymath_shared/endpoint_binding.py:26 [INFERRED]
`between_required=False` semantics are coupled to `BindingSource.RELCL_ANTECEDENT` ("SPOKEN-RELATION-ADAPTER-V1"); changing either side changes spoken-relation admission — shared/polymath_shared/endpoint_binding.py:69-77, :236-244 [DERIVED]

## VERIFY
```verify
grep -Fq 'BINDING_GATES_VERSION = "endpoint-binding-v1"' shared/polymath_shared/endpoint_binding.py
grep -Fq '_SURFACE_WEAK_MAX_ENDPOINT_DISTANCE = 100' shared/polymath_shared/endpoint_binding.py
grep -Fq '"has_role": ({"Person"}, _CLASS_LIKE)' shared/polymath_shared/endpoint_binding.py
grep -Fq '"instance_of": (None, _CLASS_LIKE)' shared/polymath_shared/endpoint_binding.py
grep -Fq 'RELCL_ANTECEDENT' shared/polymath_shared/endpoint_binding.py
! grep -Fq 'except' shared/polymath_shared/endpoint_binding.py
test "$(grep -c -F 'BindingVerdict(' shared/polymath_shared/endpoint_binding.py)" -ge 12
```
