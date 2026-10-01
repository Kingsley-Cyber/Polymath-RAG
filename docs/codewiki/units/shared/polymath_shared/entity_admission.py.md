# unit: shared/polymath_shared/entity_admission.py
anchor: shared/polymath_shared/entity_admission.py:1-288

## purpose
Classifies entity mentions into reference-identity classes — GLOBAL, CORPUS_SCOPED, DOCUMENT_SCOPED, MENTION_ONLY — at the boundary between NER recognition and durable graph identity, and allocates deterministic entity ids under contract `entity-identity-v2` (shared/polymath_shared/entity_admission.py:1-23) [DERIVED]. Six modules import it, including the live authority `admission_interpreter` (FACTS.importers; shared/polymath_shared/entity_admission.py:232-235) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `is_unresolved_pronoun` | def | `(surface: str) -> bool` | shared/polymath_shared/entity_admission.py:58-83 | — |
| `EntityAdmissionDecision` | class | frozen dataclass: `mention_id, surface, core_type, extraction_score, reference_class, reasons, policy_version="entity-admission-v1.1"`; `to_record() -> dict` | shared/polymath_shared/entity_admission.py:110-129 | — |
| `content_tokens` | def | `(surface: str) -> list[str]` | shared/polymath_shared/entity_admission.py:136-141 | — |
| `decide_v1_1_historical` (alias `decide`) | def | `(surface: str, core_type: str, extraction_score: float, mention_id: str | None = None, sentence_initial: bool = False) -> EntityAdmissionDecision` | shared/polymath_shared/entity_admission.py:214-236 | — |
| `allocate_entity_id` | def | `(surface, core_type, *, corpus_id, doc_id, chunk_id, span_start: int, span_end: int, extraction_score: float = 0.0, sentence_initial: bool = False) -> EntityAdmissionDecision` | shared/polymath_shared/entity_admission.py:239-287 | — |

Module imported by: `shared/polymath_shared/admission_interpreter.py`, `shared/polymath_shared/concept_inventory.py`, `shared/polymath_shared/discourse_reference.py`, `shared/polymath_shared/knowledge_objects/concept.py`, `shared/polymath_shared/reach.py`, `workers/workers/llm_direct.py` (FACTS.importers) [DERIVED]. Per-symbol attribution not in FACTS.

## contracts

**`is_unresolved_pronoun(surface)`** — shared/polymath_shared/entity_admission.py:58-83
- in: `surface: str`; `None`/empty tolerated via `(surface or "").strip()` (:74) [DERIVED]
- out: `True` iff surface is a single token (no space, :75), `s.isalpha()` (:77), not (`s.isupper()` and `len(s) > 1`) (:79), casing is lowercase or capitalize (:81-82), and `s.lower() in CLOSED_CLASS_PRONOUNS` (:83) [DERIVED]
- post: `You.com`, `WeWork`, `US`/`IT`/`WHO` all return `False` (docstring cases, :64-67) [DERIVED]

**`decide_v1_1_historical(...)`** — shared/polymath_shared/entity_admission.py:214-229
- in: surface, core_type, extraction_score; optional `mention_id=None`, `sentence_initial=False` [DERIVED]
- out: `EntityAdmissionDecision` from `_classify` [DERIVED]
- post: if `mention_id is None`, fallback id = `"mention_" + content_hash({"surface": surface, "type": core_type})[:16]` (:219-221) [DERIVED]

**`allocate_entity_id(...)`** — shared/polymath_shared/entity_admission.py:239-287
- pre: `corpus_id`, `doc_id`, `chunk_id`, `span_start`, `span_end` are keyword-only and required (:242-247) [DERIVED]
- out: decision whose `mention_id` carries the allocated identity: GLOBAL → `"ent_" + content_hash({"core","surface"})`; CORPUS_SCOPED → `"entc_" + content_hash({"corpus","type","surface"})`; DOCUMENT_SCOPED → `"entd_" + content_hash({"corpus","doc","type","surface"})`; else `"mention_" + content_hash({"doc","chunk","type","start","end"})` (:261-279) [DERIVED]
- post: surface normalized as `re.sub(r"\s+", " ", surface).strip().lower()` before hashing (:260) [DERIVED]

**`_classify(surface, sentence_initial)` decision order** — shared/polymath_shared/entity_admission.py:144-211
- pronoun check first → `MENTION_ONLY`/`unresolved_closed_class_pronoun` (:150-151); then acronym → GLOBAL (:186-187); version_identity → GLOBAL (:188-189); proper → GLOBAL (:190-191); deictic with `len(ct) >= 2` → DOCUMENT_SCOPED (:195-196); numbered/generic identifier branch (:198-203); `generic_head and len(discriminative) <= 1` → MENTION_ONLY (:205-206); `len(discriminative) >= 2` → CORPUS_SCOPED (:208-209); else MENTION_ONLY/`insufficient_referential_specificity` (:211) [DERIVED]

**`content_tokens(surface)`** — shared/polymath_shared/entity_admission.py:136-141
- out: word tokens minus `_DET` (`the/a/an`), with all digit runs appended when at least one non-determiner token exists (:137-140) [DERIVED]

## effect surface
- imports: `from polymath_shared.identity import content_hash` (shared/polymath_shared/entity_admission.py:29) [DERIVED]
- tables_read: `[]`, tables_written: `[]` (FACTS) [DERIVED]
- no file I/O, network, subprocess, or env-flag reads visible anywhere in the unit (shared/polymath_shared/entity_admission.py:1-287) [DERIVED]

## invariants
INVARIANT: `POLICY_VERSION` == `"entity-admission-v1.1"` — shared/polymath_shared/entity_admission.py:31 [DERIVED]
  fails-if: decisions stamped with a version downstream consumers do not recognize.
INVARIANT: `IDENTITY_CONTRACT` == `"entity-identity-v2"` — shared/polymath_shared/entity_admission.py:32 [DERIVED]
  fails-if: scoped ids mixed with pre-v2 global-only ids; docstring says they are NOT interchangeable (:13-14).
INVARIANT: CLOSED_CLASS_PRONOUNS has 29 members — shared/polymath_shared/entity_admission.py:50-55 [DERIVED]
  fails-if: adding entries violates the stated policy "this list can never grow to cover a domain" (:49).
INVARIANT: id prefixes per class are exactly `ent_` / `entc_` / `entd_` / `mention_` — shared/polymath_shared/entity_admission.py:261-279 [DERIVED]
  fails-if: prefix change breaks id routing for every stored entity.
INVARIANT: pronoun branch ordering — `is_unresolved_pronoun` is checked before acronym/proper/discriminative branches — shared/polymath_shared/entity_admission.py:145-151 [DERIVED]
  fails-if: pronouns get promoted; comment records three `they` entities previously admitted CORPUS_SCOPED (:43-47, :146-149).
INVARIANT: decide fallback mention id is truncated to 16 hash chars; allocate_entity_id mention ids use the full hash — shared/polymath_shared/entity_admission.py:220 vs :276-279 [DERIVED]
  fails-if: same-mention id formats diverge between the historical and live paths.

## determinism & idempotency
determinism: DETERMINISTIC — pure functions + regex + `content_hash`; docstring states "Deterministic; no model; no numeric fake confidence" (shared/polymath_shared/entity_admission.py:20-21); no clock/random/uuid/network/db/env reads visible [DERIVED]
idempotency: SAFE — no state mutation; each call re-derives the same decision and id from identical inputs (shared/polymath_shared/entity_admission.py:214-287) [DERIVED]

## failure behaviour
No try/except or broad handlers exist in the unit (shared/polymath_shared/entity_admission.py:1-287) [DERIVED]. `None`/empty surface is guarded in `is_unresolved_pronoun` (:74-75); empty token lists are guarded in `_classify` (`head_tokens[-1] ... if head_tokens else ""` :154-155; `toks[0] if toks else ""` :168) [DERIVED]. No error codes raised. FACTS contains no fallbacks key.

## dumb-code flags
- `decide = decide_v1_1_historical` is an explicit HISTORICAL alias; "Production must never call it" and a test asserts no production module imports this name — shared/polymath_shared/entity_admission.py:232-236 [DERIVED]
- decide's fallback mention id hashes only `{"surface", "type"}` and truncates to `[:16]`, ignoring doc/chunk/span — unlike `allocate_entity_id` (:276-279); identical surfaces in different docs collide on mention_id — shared/polymath_shared/entity_admission.py:219-221 [INFERRED: same inputs → same hash, no location key]
- `extraction_score` is accepted and recorded but never passed to `_classify` and never influences the class — shared/polymath_shared/entity_admission.py:144, :214-229, :248 [DERIVED]
- `_ACRONYM_RE = re.compile(r"^[A-Z][A-Z]*$")` — `[A-Z][A-Z]*` is a redundant spelling of `[A-Z]+` — shared/polymath_shared/entity_admission.py:107 [DERIVED]
- `content_tokens` appends digit runs to `ct` (:138-140), so digit-bearing surfaces can pass the `len(ct) >= 2` gates (:195, :198) on digits alone, while digits are always excluded from `discriminative` (:179-183) — shared/polymath_shared/entity_admission.py:136-141 [INFERRED: length gates count digits, discriminative count does not]

## refactor notes
- The hash input key-sets and prefixes at :261-279 ARE the `entity-identity-v2` contract; any change re-keys every stored id, and old global-only ids are declared not interchangeable (:13-18) [DERIVED]
- Reordering `_classify` so the pronoun check is not first re-opens the recorded bug where `they` entities reached CORPUS_SCOPED and carried pronoun edges into Neo4j (:43-47, :145-151) [DERIVED]
- `POLICY_VERSION` is stamped as the default on every `EntityAdmissionDecision` (:118, :31) — changing it silently changes serialized records for all six importers [DERIVED]
- The live authority is `admission_interpreter.interpret_admission(contract_version=...)` (:233-235); refactors here must go through that dispatcher, not the `decide` alias [DERIVED]
- Blast radius for any signature change: `admission_interpreter.py`, `concept_inventory.py`, `discourse_reference.py`, `knowledge_objects/concept.py`, `reach.py`, `workers/workers/llm_direct.py` (FACTS.importers) [DERIVED]

## VERIFY
```verify
grep -Fq 'POLICY_VERSION = "entity-admission-v1.1"' shared/polymath_shared/entity_admission.py
grep -Fq 'IDENTITY_CONTRACT = "entity-identity-v2"' shared/polymath_shared/entity_admission.py
grep -Fq 'return "MENTION_ONLY", ("unresolved_closed_class_pronoun",)' shared/polymath_shared/entity_admission.py
grep -Fq 'decide = decide_v1_1_historical' shared/polymath_shared/entity_admission.py
grep -Eq '"entc_" \+ content_hash' shared/polymath_shared/entity_admission.py
! grep -Fq 'import random' shared/polymath_shared/entity_admission.py
test "$(grep -c -F 'content_hash' shared/polymath_shared/entity_admission.py)" -ge 5
```
