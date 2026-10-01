# unit: shared/polymath_shared/discourse_reference.py
anchor: shared/polymath_shared/discourse_reference.py:1-362

## purpose

Deterministic classifier for one LOCAL_REFERENCE mention: returns exactly one of `ANTECEDENT_RESOLVED | DOCUMENT_CONSTITUTED | EXTERNAL_UNRESOLVED | AMBIGUOUS` via evidence rules E1–E6 — shared/polymath_shared/discourse_reference.py:1-29 [DERIVED]. Explicitly NOT coreference resolution; nearest-compatible-noun, repeated-mention, same-type, embeddings/neural coreference are forbidden inferences — shared/polymath_shared/discourse_reference.py:10-15 [DERIVED]. Implements PHASE 2B of `docs/wiki/plans/REFERENTIAL-ADMISSION-V2-PLAN.md` — shared/polymath_shared/discourse_reference.py:3 [DERIVED]. Module is imported by `admission_interpreter.py` and `execution.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `resolve` | def | (target: str, context: list[str], *, admitted_anchors=None, syntax=None, target_tokens=None) -> DiscourseResult | shared/polymath_shared/discourse_reference.py:200-361 | shared/polymath_shared/admission_interpreter.py, shared/polymath_shared/execution.py (module importers) |
| `DiscourseResult` | class | frozen dataclass(basis: ReferenceBasis, resolves_to=None, evidence=(), candidates=(), contract=DISCOURSE_CONTRACT) | shared/polymath_shared/discourse_reference.py:136-142 | same two importers |
| `DISCOURSE_CONTRACT` | const | `"discourse-reference-v1"` | shared/polymath_shared/discourse_reference.py:41 | — |
| `POLICY_VERSION` | const | from policy JSON key `"version"` | shared/polymath_shared/discourse_reference.py:70 | — |
| `POLICY_SHA256` | const | `"4694c626adb79bdc052298b457b204bb8d5993dbfef1724132d043bc0bce93e7"` | shared/polymath_shared/discourse_reference.py:54 | — |

All other symbols (`_load_policy`, `_is_ordinal_partition`, `_content`, `_is_definite`, `_head`, `_np_candidates`) are private helpers — FACTS.symbols.

## contracts

### resolve(target, context, *, admitted_anchors=None, syntax=None, target_tokens=None) -> DiscourseResult
- in: `context` = ordered sentences up to AND INCLUDING the target's sentence; `admitted_anchors` = `(surface, core_type)` pairs already admitted in this document — shared/polymath_shared/discourse_reference.py:205-209 [DERIVED]
- pre: none enforced; a target without a definite/demonstrative determiner short-circuits to `EXTERNAL_UNRESOLVED` with evidence `("no definite/demonstrative determiner",)` — shared/polymath_shared/discourse_reference.py:218-220 [DERIVED]
- out: frozen `DiscourseResult`; every return path carries a non-empty `evidence` tuple — shared/polymath_shared/discourse_reference.py:136-142, 219-220, 229-230, 313-314, 359-361 [DERIVED]
- post: candidate multiplicity never collapses to a pick — `len(compat) > 1` yields `AMBIGUOUS`, same for E3/E4b/E5 — shared/polymath_shared/discourse_reference.py:231-233, 253-256, 303-305, 315-317 [DERIVED]
- post: ordinal-modified definites (`the second group`) return `AMBIGUOUS` with evidence prefix `ordinal_set_partition:` before E6 is reached — shared/polymath_shared/discourse_reference.py:319-329 [DERIVED]

### DiscourseResult
- fields: `basis: ReferenceBasis`, `resolves_to: str | None = None`, `evidence: tuple[str, ...] = ()`, `candidates: tuple[str, ...] = ()`, `contract: str = DISCOURSE_CONTRACT`; frozen — shared/polymath_shared/discourse_reference.py:136-142 [DERIVED]

## effect surface

- File read: `resources/discourse/discourse-reference-policy-v1.json` via `Path(__file__).resolve().parents[2] / "resources" / "discourse" / ...` — shared/polymath_shared/discourse_reference.py:52-53 [DERIVED]
- The read + sha256 check runs at import time (`_POLICY = _load_policy()`) — shared/polymath_shared/discourse_reference.py:69, 57-58 [DERIVED]
- Postgres tables read/written: none (FACTS.tables_read, FACTS.tables_written empty)
- Qdrant / network / subprocess / env flags: none visible in SOURCE

## invariants

INVARIANT: sha256(discourse-reference-policy-v1.json) == `"4694c626adb79bdc052298b457b204bb8d5993dbfef1724132d043bc0bce93e7"` — shared/polymath_shared/discourse_reference.py:54, 57-66 [DERIVED]
  fails-if: `RuntimeError("discourse policy pack drifted: ...")` at import; both importers cannot load the module.
INVARIANT: DiscourseResult.contract == DISCOURSE_CONTRACT == `"discourse-reference-v1"` — shared/polymath_shared/discourse_reference.py:41, 142 [DERIVED]
  fails-if: downstream consumers keyed on the contract string reject results.
INVARIANT: noun-chunk candidate token count <= 6 and no token with pos in `{"VERB", "AUX", "SCONJ"}` — shared/polymath_shared/discourse_reference.py:184-187 [DERIVED]
  fails-if: clause-crossing spans reintroduce the fabricated-antecedent failure documented at 163-174.
INVARIANT: E6 requires len(_content(target)) >= 2 — shared/polymath_shared/discourse_reference.py:344-347 [DERIVED]
  fails-if: bare repeated nouns (`the system` x3) get constituted as participants, violating REVISION 2 at 342-343.
INVARIANT: E5 fires only when exactly 1 prior sentence matches a source verb; > 1 -> AMBIGUOUS — shared/polymath_shared/discourse_reference.py:308-317 [DERIVED]
  fails-if: multiple candidate source events silently pick one event.
INVARIANT: `_NOMINALIZATION` is a closed table of 6 keys (failure, stoppage, outage, migration, deployment, restart) — shared/polymath_shared/discourse_reference.py:126-133 [DERIVED]
  fails-if: morphological guessing outside the table changes E5 coverage.
INVARIANT: heads in `_EXTERNAL_PARTY` or `GENERIC_HEAD` can never reach E6 DOCUMENT_CONSTITUTED — shared/polymath_shared/discourse_reference.py:332-341 [DERIVED]
  fails-if: parties existing independently of the document get constituted by mere repetition.

## determinism & idempotency

determinism: DETERMINISTIC — all logic is regex/string operations over the arguments (shared/polymath_shared/discourse_reference.py:218-361); the only I/O is one hash-pinned JSON read at import (shared/polymath_shared/discourse_reference.py:57-69); no clock/random/uuid/network/db/env access visible [DERIVED]
idempotency: SAFE — no writes anywhere; `_load_policy` only reads (shared/polymath_shared/discourse_reference.py:58) [DERIVED]

## failure behaviour

- Sole raise: `RuntimeError` from `_load_policy` on sha256 drift, message begins `"discourse policy pack drifted:"` and instructs "update the pin deliberately with a gate rerun, never silently" — shared/polymath_shared/discourse_reference.py:60-64 [DERIVED]. It fires at import (line 69), so callers see an import failure, not a per-call error.
- `resolve` never raises in SOURCE; overload is returned as `ReferenceBasis.AMBIGUOUS` with evidence — shared/polymath_shared/discourse_reference.py:232, 254, 304, 316, 325 [DERIVED]
- Degradation path: when `syntax` is falsy, `_np_candidates` falls back to a tight regex bounded by `(?:[a-z]+\s+){0,2}` (≤3 tokens) — shared/polymath_shared/discourse_reference.py:191-197 [DERIVED]
- No try/except blocks exist in the unit.

## dumb-code flags

- E3 matches on ANY shared content word (`tw & set(_content(a))`); the comment itself calls this "lexical relatedness, not identity" and says a fix exists on `candidate/rescue-discourse-v1-failed` but "not promoted" — shared/polymath_shared/discourse_reference.py:223-227 [DERIVED]
- E4b header says "NOT IN THE LIVE V2 COMPOSITION" (235) yet the E4b branch sits unconditionally inside `resolve` and returns results — shared/polymath_shared/discourse_reference.py:235-246, 247-277 [INFERRED: comment and reachable code path disagree; either the comment or the wiring is stale]
- Determiner literals duplicated across `_DET` (43) and `_STOP` (44-45) — shared/polymath_shared/discourse_reference.py:43-45 [DERIVED]
- `_DET` members carry trailing spaces (`"the "`) to make `startswith` work; `any(d in x.lower() ...)` at 351 is substring matching without word boundaries — shared/polymath_shared/discourse_reference.py:43, 151, 348-351 [DERIVED]
- Substring anchor matching `a.lower() in low` with no word boundary — shared/polymath_shared/discourse_reference.py:288 [DERIVED]
- Magic bounds: NP cap `len(toks) > 6` (186); fallback regex span `{0,2}` (193) — shared/polymath_shared/discourse_reference.py:186, 193 [DERIVED]

## refactor notes

- Signature/keyword-only args of `resolve` (200-204) and `DiscourseResult` field names (136-142) are the API consumed by `admission_interpreter.py` and `execution.py` (FACTS.importers) — renaming ripples into both.
- `ReferenceBasis` members referenced: `EXTERNAL_UNRESOLVED`, `ANTECEDENT_RESOLVED`, `AMBIGUOUS`, `DOCUMENT_CONSTITUTED` — shared/polymath_shared/discourse_reference.py:219, 229, 254, 313, 334, 354, 359; renaming in `entity_harbor` breaks this unit [DERIVED]
- `GENERIC_HEAD` imported from `entity_admission`, used at 337 — shared/polymath_shared/discourse_reference.py:38, 337 [DERIVED]
- Policy JSON keys consumed at import: `version`, `type_noun`, `indefinite_markers`, `external_party` — shared/polymath_shared/discourse_reference.py:70-72, 80 [DERIVED]; schema changes break import before any call.
- `POLICY_SHA256` pin must be updated deliberately "with a gate rerun" — shared/polymath_shared/discourse_reference.py:62-64 [DERIVED]
- Do not loosen the `_np_candidates` fallback regex: spaCy noun chunks are the authority, the regex is a "TIGHT diagnostic fallback" — shared/polymath_shared/discourse_reference.py:170-174, 191-197 [DERIVED]

## VERIFY

```verify
grep -Fq 'DISCOURSE_CONTRACT = "discourse-reference-v1"' shared/polymath_shared/discourse_reference.py
grep -Fq 'POLICY_SHA256 = "4694c626adb79bdc052298b457b204bb8d5993dbfef1724132d043bc0bce93e7"' shared/polymath_shared/discourse_reference.py
grep -Fq 'def resolve(target: str, context: list[str]' shared/polymath_shared/discourse_reference.py
grep -Fq 'if len(toks) > 6:' shared/polymath_shared/discourse_reference.py
grep -Fq 'raise RuntimeError(' shared/polymath_shared/discourse_reference.py
test "$(grep -c -F 'ReferenceBasis.AMBIGUOUS' shared/polymath_shared/discourse_reference.py)" -ge 4
! grep -Fq 'import requests' shared/polymath_shared/discourse_reference.py
```
