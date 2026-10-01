# unit: shared/polymath_shared/identity_allocation.py
anchor: shared/polymath_shared/identity_allocation.py:1-161

## purpose
Turns a settled `AdmissionResult` into a durable (or non-durable) entity id — "scope to durable id". Splits the two questions the plan keeps apart: `interpret_admission()` asks *what is this reference*, `allocate_identity()` asks *may it become durable identity* (shared/polymath_shared/identity_allocation.py:1-12) [DERIVED]. Durability is decided by `graph_eligible()` alone; successful anaphora must not manufacture identity (shared/polymath_shared/identity_allocation.py:8-12) [DERIVED]. Consumed by `shared/polymath_shared/execution.py` and `workers/workers/llm_direct.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `MentionIdentity` | class (frozen dataclass) | `(admission: AdmissionResult, entity_id: str, durable: bool)` | shared/polymath_shared/identity_allocation.py:30-35 | module imported by `shared/polymath_shared/execution.py`, `workers/workers/llm_direct.py` (FACTS.importers; per-symbol use unknown) |
| `MentionIdentity.admission_class` | property | `self -> str` | shared/polymath_shared/identity_allocation.py:37-42 | — |
| `canonical_type` | def | `(result: AdmissionResult) -> str` | shared/polymath_shared/identity_allocation.py:45-83 | — |
| `normalized_for_lookup` | def | `(surface: str) -> str` | shared/polymath_shared/identity_allocation.py:86-87 | — |
| `span_identity_key` | def | `(span, corpus_id: str) -> tuple` | shared/polymath_shared/identity_allocation.py:90-95 | — |
| `allocate_identity` | def | `(result, *, corpus_id: str, doc_id: str, chunk_id: str, span_start: int, span_end: int, inherit_entity_id: str \| None = None) -> MentionIdentity` | shared/polymath_shared/identity_allocation.py:98-161 | — |

## contracts

**`canonical_type(result)`** — shared/polymath_shared/identity_allocation.py:45-83
- in: an `AdmissionResult` with readable `anchor_kind`, `core_type`.
- out: `"CONCEPT"` iff `result.anchor_kind == "CONCEPT"`; otherwise `result.core_type` verbatim (shared/polymath_shared/identity_allocation.py:81-83).
- pre: caller passes a settled `AdmissionResult`.
- post: provider `core_type` is retained (never overwritten) except where a CONCEPT anchor exists — provider type describes, does not define, identity (shared/polymath_shared/identity_allocation.py:46-49, 66-70).

**`normalized_for_lookup(surface)`** — shared/polymath_shared/identity_allocation.py:86-87
- in: any surface string.
- out: `re.sub(r"\s+", " ", surface).strip().lower()` — collapse whitespace, strip, lowercase.
- post: used only as a lookup/id key; never for classification (module docstring forbids classifying from a normalized surface, shared/polymath_shared/identity_allocation.py:14-16).

**`span_identity_key(span, corpus_id)`** — shared/polymath_shared/identity_allocation.py:90-95
- out: 6-tuple `(corpus_id, span.doc_id, span.chunk_id, span.start, span.end, span.core_type.value)`.
- post: identity of a PROPOSAL, not a reference; two consumers on the same span must get the same key or they silently allocate twice (shared/polymath_shared/identity_allocation.py:91-93).

**`allocate_identity(result, *, corpus_id, doc_id, chunk_id, span_start, span_end, inherit_entity_id=None)`** — shared/polymath_shared/identity_allocation.py:98-161
- in: settled `AdmissionResult` plus provenance coordinates; optional `inherit_entity_id`.
- out: `MentionIdentity`.
- pre: `result.reference_basis`, `result.graph_eligible`, `result.scope`, `result.proposal_surface` readable.
- post (branch table):

| condition | entity_id | durable |
|---|---|---|
| `reference_basis == "ANTECEDENT_RESOLVED"` and `inherit_entity_id` set | `inherit_entity_id` | `True` (shared/polymath_shared/identity_allocation.py:122-124) |
| `ANTECEDENT_RESOLVED`, no `inherit_entity_id` | `"mention_" + content_hash({"doc": doc_id, "chunk": chunk_id, "type": result.core_type, "start": span_start, "end": span_end})` | `False` (shared/polymath_shared/identity_allocation.py:125-130) |
| `graph_eligible` and `scope == "GLOBAL"` | `"ent_" + content_hash({"core": core, "surface": surface})` | `True` (shared/polymath_shared/identity_allocation.py:145-146) |
| `graph_eligible` and `scope == "CORPUS_SCOPED"` | `"entc_" + content_hash({"corpus": corpus_id, "type": core, "surface": surface})` | `True` (shared/polymath_shared/identity_allocation.py:147-149) |
| `graph_eligible` and `scope == "DOCUMENT_SCOPED"` | `"entd_" + content_hash({"corpus": corpus_id, "doc": doc_id, "type": core, "surface": surface})` | `True` (shared/polymath_shared/identity_allocation.py:150-153) |
| anything else | `"mention_" + content_hash({"doc": doc_id, "chunk": chunk_id, "type": core, "start": span_start, "end": span_end})` | `False` (shared/polymath_shared/identity_allocation.py:154-158) |

where `surface = normalized_for_lookup(result.proposal_surface)` (shared/polymath_shared/identity_allocation.py:141) and `core = canonical_type(result)` (shared/polymath_shared/identity_allocation.py:142).

## effect surface
- Postgres tables read: none (FACTS.tables_read = `[]`). Written: none (FACTS.tables_written = `[]`).
- Qdrant / files / network / subprocess / env flags: none visible in SOURCE — module imports only `re`, `dataclass`, `AdmissionResult`, `content_hash` (shared/polymath_shared/identity_allocation.py:20-24) [DERIVED].

## invariants
INVARIANT: `admission_class` == `admission.scope` when `durable`, else `"MENTION_ONLY"` — shared/polymath_shared/identity_allocation.py:42 [DERIVED]
  fails-if: a consumer treats an ineligible/abstaining decision as a durable scope (stated at shared/polymath_shared/identity_allocation.py:39-41).
INVARIANT: `durable` == `bool(result.graph_eligible)` on every non-antecedent path — shared/polymath_shared/identity_allocation.py:133, 154-155 [DERIVED]
  fails-if: a resolved-but-ineligible reference would mint an `ent*` id, manufacturing identity from anaphora (shared/polymath_shared/identity_allocation.py:10-12).
INVARIANT: id prefix ∈ {`ent_`, `entc_`, `entd_`, `mention_`} is fully determined by `(durable, scope)` — shared/polymath_shared/identity_allocation.py:145-158 [DERIVED]
  fails-if: same referent hashed into two different namespaces → duplicate nodes.
INVARIANT: id surface basis == normalized `proposal_surface`, never the envelope — shared/polymath_shared/identity_allocation.py:134-141 [DERIVED]
  fails-if: `the CareConnect portal` and `CareConnect portal` hash differently and split one referent (comment at shared/polymath_shared/identity_allocation.py:136-140).
INVARIANT: `reference_basis == "ANTECEDENT_RESOLVED"` + `inherit_entity_id` ⇒ `entity_id == inherit_entity_id` and `durable == True` — shared/polymath_shared/identity_allocation.py:122-124 [DERIVED]
  fails-if: same referent gets different identity → duplicates the node resolution just found (shared/polymath_shared/identity_allocation.py:108-114).
INVARIANT: `mention_` ids are position-keyed (doc/chunk/start/end), `ent*` ids are surface-keyed — shared/polymath_shared/identity_allocation.py:146-158 [DERIVED]
  fails-if: re-chunking or span shifts silently rotate every `mention_` id while `ent*` ids stay stable [INFERRED — keys visibly include `chunk_id`/`span_start`/`span_end`].

## determinism & idempotency
determinism: DETERMINISTIC — pure functions of inputs; only regex normalization plus `content_hash` over literal dict payloads, no clock/random/uuid/network/db/env reads in SOURCE (shared/polymath_shared/identity_allocation.py:86-87, 127-158) [DERIVED].
idempotency: SAFE — no side effects, no I/O, frozen dataclass returned (shared/polymath_shared/identity_allocation.py:30, 160-161).

## failure behaviour
- No try/except anywhere in SOURCE; no error codes raised locally; nothing swallowed by a handler (whole file, shared/polymath_shared/identity_allocation.py:1-161) [DERIVED].
- Silent degrade, not an exception: any unrecognized `scope` string falls to the `else` branch → `mention_` id, `durable=False` (shared/polymath_shared/identity_allocation.py:154-158).
- `ANTECEDENT_RESOLVED` with `inherit_entity_id=None` degrades to a non-durable `mention_` id rather than raising (shared/polymath_shared/identity_allocation.py:125-130).

## dumb-code flags
- Hash payload key for the type value is `"core"` in the `ent_` branch but `"type"` in `entc_`/`entd_`/`mention_` branches — same value, two key names (shared/polymath_shared/identity_allocation.py:146 vs 148, 151-153, 156-158). Cross-namespace, so not a collision today [INFERRED], but a rename trap.
- Antecedent-fallback `mention_` hash uses raw `result.core_type` (shared/polymath_shared/identity_allocation.py:128) while the ineligible-path `mention_` hash uses `canonical_type(result)` output `core` (shared/polymath_shared/identity_allocation.py:142, 156) — the same span shape can hash differently by branch [INFERRED — both branches visible, values differ].
- `span_identity_key` keys on raw `span.core_type.value`, not `canonical_type` output (shared/polymath_shared/identity_allocation.py:94-95) — proposal key and identity namespace can disagree on type basis [INFERRED].
- `IDENTITY_ALLOCATION_CONTRACT` and `TYPE_ALIGNMENT_CONTRACT` are defined but never referenced elsewhere in this file (shared/polymath_shared/identity_allocation.py:26-27) [DERIVED].

## refactor notes
- Changing any id payload (keys or values in the `content_hash` dicts), the `ent_`/`entc_`/`entd_`/`mention_` prefixes, or `normalized_for_lookup` re-keys every stored id; importers `shared/polymath_shared/execution.py` and `workers/workers/llm_direct.py` (FACTS.importers) and anything persisting these ids must move with it (shared/polymath_shared/identity_allocation.py:145-158).
- `admission_class`'s clamp to `"MENTION_ONLY"` is a cross-consumer contract — every `admission_class` consumer must keep going through it, per the docstring's plan reference (shared/polymath_shared/identity_allocation.py:8-12, 39-42).
- `graph_eligible` is the sole durability gate; do not add eligibility conditions here without revisiting the "resolution never manufactures identity" rule (shared/polymath_shared/identity_allocation.py:8-12, 118-120, 133).
- `inherit_entity_id=None` on a resolved antecedent is a designed non-durable fallback, not an error — removing it changes `durable` semantics (shared/polymath_shared/identity_allocation.py:125-130).

## VERIFY
```verify
grep -Fq 'identity-allocation-v1' shared/polymath_shared/identity_allocation.py
grep -Fq 'harbor-type-identity-alignment-v1' shared/polymath_shared/identity_allocation.py
grep -Fq 'return self.admission.scope if self.durable else "MENTION_ONLY"' shared/polymath_shared/identity_allocation.py
grep -Eq '"(ent_|entc_|entd_|mention_)" \+ content_hash' shared/polymath_shared/identity_allocation.py
test "$(grep -c -F 'content_hash' shared/polymath_shared/identity_allocation.py)" -ge 5
! grep -Fq 'import random' shared/polymath_shared/identity_allocation.py
```
