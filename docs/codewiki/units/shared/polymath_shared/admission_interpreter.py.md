# unit: shared/polymath_shared/admission_interpreter.py
anchor: shared/polymath_shared/admission_interpreter.py:1-282

## purpose
S4 — the single live admission authority for Polymath ingestion. Replaces the five inline admission call sites and the old `decide()` de-facto authority, which now means historical semantics `shared/polymath_shared/admission_interpreter.py:1-7` [DERIVED]. All admission routes through one contract-dispatched entry point, `interpret_admission(contract_version=...)`; V2 is current ingestion, V1.1 is pinned historical replay, anything else fails `shared/polymath_shared/admission_interpreter.py:9-15` [DERIVED]. Sole known consumer: `shared/polymath_shared/identity_allocation.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `interpret_admission` | def | keyword-only (contract_version, proposal_surface, core_type, span=None, sentence_text="", syntax=None, document_text="", discourse_context=None, discourse_syntax=None, admitted_anchors=None, extraction_score=0.0, sentence_initial=False, heading_context=False) -> AdmissionResult | shared/polymath_shared/admission_interpreter.py:64-88 | shared/polymath_shared/identity_allocation.py |
| `AdmissionResult` | dataclass (frozen=True) | fields: proposal_surface, referential_surface, core_type, anchor_kind, decision_status, scope, reference_basis, graph_eligible, admission_reason, semantic_contract, resolves_to=None, evidence=dict, interpreter=ADMISSION_INTERPRETER_CONTRACT | shared/polymath_shared/admission_interpreter.py:47-61 | — |
| `UnknownAdmissionContract` | class | Exception subclass | shared/polymath_shared/admission_interpreter.py:43-44 | — |
| `ADMISSION_INTERPRETER_CONTRACT` | const | `"admission-interpreter-v1"` | shared/polymath_shared/admission_interpreter.py:37 | — |

## contracts

### interpret_admission — dispatch
- in: `contract_version` must be exactly `SEMANTIC_CONTRACT_V2` or `SEMANTIC_CONTRACT_V1_1` (constants from `polymath_shared.execution`, values not visible here) — shared/polymath_shared/admission_interpreter.py:74-83 [DERIVED]
- pre: all params keyword-only (`*` in signature) — shared/polymath_shared/admission_interpreter.py:64 [DERIVED]
- post: returns frozen `AdmissionResult` whose `semantic_contract` matches the dispatched branch; `interpreter` defaults to `"admission-interpreter-v1"` — shared/polymath_shared/admission_interpreter.py:61,120,280 [DERIVED]
- post: any other `contract_version` raises `UnknownAdmissionContract`; message ends "Guessing an interpreter is forbidden." — shared/polymath_shared/admission_interpreter.py:84-88 [DERIVED]
- note: V2 branch ignores `extraction_score` and `sentence_initial`; V1.1 branch ignores span/sentence/syntax/document/discourse/heading — shared/polymath_shared/admission_interpreter.py:77-83 [DERIVED]

### _interpret_v2 — pipeline (first match wins)

| # | condition | anchor_kind | scope | status | anchor |
|---|---|---|---|---|---|
| 0 | surface ∈ 12 pronouns `{"i","you","we","it","he","she","they","me","him","her","them","us"}` | UNKNOWN | MENTION_ONLY | ABSTAINED | shared/polymath_shared/admission_interpreter.py:128-135 |
| 0b | span covers no complete token but sentence has tokens (subtoken-span-admission-v1) | UNKNOWN | MENTION_ONLY | ABSTAINED | shared/polymath_shared/admission_interpreter.py:156-174 |
| 1 | `ident.is_identity` (require_syntax=True) | IDENTITY | GLOBAL | from decision | shared/polymath_shared/admission_interpreter.py:180-187 |
| 2a | envelope `startswith(_DEF)` and basis ∈ {ANTECEDENT_RESOLVED, DOCUMENT_CONSTITUTED} | LOCAL_REFERENCE | DOCUMENT_SCOPED | RESOLVED | shared/polymath_shared/admission_interpreter.py:190-208 |
| 2b | def envelope, not generic | LOCAL_REFERENCE | DOCUMENT_SCOPED | ABSTAINED if AMBIGUOUS else RESOLVED | shared/polymath_shared/admission_interpreter.py:214-219 |
| 2c | def envelope, plural class generic | GENERIC | MENTION_ONLY | — | shared/polymath_shared/admission_interpreter.py:220-224 |
| 3 | `admit_concept` returns evidence | CONCEPT | CORPUS_SCOPED | — | shared/polymath_shared/admission_interpreter.py:228-233 |
| 3b | `named_concept_evidence` returns evidence | CONCEPT | CORPUS_SCOPED | — | shared/polymath_shared/admission_interpreter.py:240-245 |
| 4 | `classify_generic(...).is_generic` | GENERIC | MENTION_ONLY | — | shared/polymath_shared/admission_interpreter.py:251-259 |
| 5 | else | UNKNOWN | DOCUMENT_SCOPED | CONTEXT_REQUIRED | shared/polymath_shared/admission_interpreter.py:261-263 |

- pre (V2): default span is `(0, len(proposal_surface))` when span is falsy — shared/polymath_shared/admission_interpreter.py:109 [DERIVED]
- `_DEF` determiners: `("the ", "this ", "that ", "these ", "those ", "our ", "its ", "their ")`, compared via `env.referential_surface.lower().startswith(_DEF)` — shared/polymath_shared/admission_interpreter.py:38,190 [DERIVED]

### _interpret_v1_1_historical — replay only
- in: delegates to `entity_admission.decide_v1_1_historical(proposal_surface, core_type, extraction_score, sentence_initial=...)` — shared/polymath_shared/admission_interpreter.py:269-273 [DERIVED]
- out: `anchor_kind="UNSPECIFIED_V1_1"`, `decision_status="RESOLVED"`, `graph_eligible = d.reference_class != "MENTION_ONLY"` — shared/polymath_shared/admission_interpreter.py:274-281 [DERIVED]

## effect surface
- Postgres tables: none (FACTS `tables_read: []`, `tables_written: []`).
- Qdrant / files / network / subprocess / env flags: none visible in shared/polymath_shared/admission_interpreter.py:31-281 [DERIVED].
- Only side effects: imports of sibling `polymath_shared.*` modules (function-local) and the `UnknownAdmissionContract` raise — shared/polymath_shared/admission_interpreter.py:74,94-103,240,269-270,84 [DERIVED].

## invariants
INVARIANT: accepted `contract_version` values == 2 (`SEMANTIC_CONTRACT_V2`, `SEMANTIC_CONTRACT_V1_1`); every other value raises — shared/polymath_shared/admission_interpreter.py:76-88 [DERIVED]
  fails-if: a V2→V1.1 fallback or silent default appears, making graph semantics depend on which interpreter succeeded (:14-15).
INVARIANT: pronoun set size == 12; all map to scope "MENTION_ONLY" + status "ABSTAINED" — shared/polymath_shared/admission_interpreter.py:128-135 [DERIVED]
  fails-if: "You"/"I" admitted as GLOBAL in transcript corpora, contaminating conversation-derived graphs (:125-127).
INVARIANT: `graph_eligible` on every result comes solely from `entity_harbor.graph_eligible(d)` — shared/polymath_shared/admission_interpreter.py:99,120 [DERIVED]
  fails-if: eligibility computed per-branch drifts from the one authority.
INVARIANT: GENERIC classification reached only after IDENTITY, LOCAL_REFERENCE, CONCEPT all decline — shared/polymath_shared/admission_interpreter.py:247-250 [DERIVED]
  fails-if: a document-defined term ("the engineering group") is demoted to a class term (:200-202, 226-228).
INVARIANT: GENERIC never overrides basis ∈ {ANTECEDENT_RESOLVED, DOCUMENT_CONSTITUTED} — shared/polymath_shared/admission_interpreter.py:197-208 [DERIVED]
  fails-if: resolved discourse participants reclassified as populations.
INVARIANT: subtoken abstain preserves `proposal_surface` verbatim, never rewrites to the containing token — shared/polymath_shared/admission_interpreter.py:152-156 [DERIVED]
  fails-if: `instagram` inside a URL token gets promoted to the URL surface.
INVARIANT: V1.1 `graph_eligible` == (`d.reference_class != "MENTION_ONLY"`) — shared/polymath_shared/admission_interpreter.py:278 [DERIVED]
  fails-if: historical replay diverges from pinned v1.1 semantics.

## determinism & idempotency
determinism: DETERMINISTIC (no clock/random/uuid/network/db/env reads in shared/polymath_shared/admission_interpreter.py:31-281) [DERIVED]
idempotency: SAFE (no external writes; result is a frozen dataclass — shared/polymath_shared/admission_interpreter.py:47) [DERIVED]

## failure behaviour
- `UnknownAdmissionContract` raised for any unrecognized `contract_version`; nothing caught locally — shared/polymath_shared/admission_interpreter.py:84-88 [DERIVED]
- No `try:`/`except` anywhere in the file; nothing swallowed — shared/polymath_shared/admission_interpreter.py:1-281 [DERIVED]
- Comment-documented: `identity_evidence`'s `require_syntax` guard raises `RetryableDependencyUnavailable` when the sentence yields zero tokens; the subtoken branch deliberately falls through to preserve that retryable path — shared/polymath_shared/admission_interpreter.py:147-149,175-177 [DERIVED]
- Sub-token spans (syntax present, no complete covering token) abstain fail-closed instead of raising — shared/polymath_shared/admission_interpreter.py:137-174 [DERIVED]

## dumb-code flags
- `_IDENT_REASONS` frozenset defined, never referenced anywhere in the file — shared/polymath_shared/admission_interpreter.py:39-40 [DERIVED]
- `AdmissionResult` field `graph_eligible` (:56) shares its name with the imported function `graph_eligible` called at :120; construction is positional today, keyword-construction refactor would collide — shared/polymath_shared/admission_interpreter.py:56,99,120 [INFERRED: same identifier, two meanings, one scope chain]
- `span if span else (0, len(proposal_surface))` treats a legitimate falsy span `(0, 0)` as "no span" — shared/polymath_shared/admission_interpreter.py:109 [DERIVED]
- `_DEF` entries carry trailing spaces (`"the "`, `"this "`); match requires the space, casing handled only by `.lower()` at the call site — shared/polymath_shared/admission_interpreter.py:38,190 [DERIVED]
- `extraction_score` (default `0.0`) and `sentence_initial` (default `False`) are dead on the V2 branch — shared/polymath_shared/admission_interpreter.py:70-71,77-80 [DERIVED]

## refactor notes
- Sole known importer is `shared/polymath_shared/identity_allocation.py`; signature changes to `interpret_admission` hit it first (FACTS.importers) [DERIVED].
- Adding any V2→V1.1 fallback is forbidden by contract; `_interpret_v1_1_historical` must stay unreachable from production — shared/polymath_shared/admission_interpreter.py:14-15,268 [DERIVED]
- `normalized_surface` must never become an input to any stage — shared/polymath_shared/admission_interpreter.py:29 [DERIVED]
- Branch ordering (IDENTITY → LOCAL_REFERENCE → CONCEPT → GENERIC → ABSTAIN) is load-bearing; reordering changes graph eligibility — shared/polymath_shared/admission_interpreter.py:179-263 [DERIVED]
- Function-local imports at :74, :94-103, :240, :269-270 likely avoid circular imports; hoisting them may break module load — shared/polymath_shared/admission_interpreter.py:74,94-103 [INFERRED: local-import pattern in an import-heavy module]
- Default `evidence` uses `field(default_factory=dict)`; the dataclass is frozen — mutable field inside a frozen dataclass — shared/polymath_shared/admission_interpreter.py:47,60 [DERIVED]

## VERIFY
```verify
grep -Fq 'ADMISSION_INTERPRETER_CONTRACT = "admission-interpreter-v1"' shared/polymath_shared/admission_interpreter.py
grep -Fq 'if contract_version == SEMANTIC_CONTRACT_V2:' shared/polymath_shared/admission_interpreter.py
grep -Fq 'require_syntax=True' shared/polymath_shared/admission_interpreter.py
grep -Fq 'graph_eligible(d)' shared/polymath_shared/admission_interpreter.py
! grep -Fq 'try:' shared/polymath_shared/admission_interpreter.py
test "$(grep -c -F 'HarborDecision(' shared/polymath_shared/admission_interpreter.py)" -ge 10
```
