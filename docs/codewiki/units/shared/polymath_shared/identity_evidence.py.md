# unit: shared/polymath_shared/identity_evidence.py
anchor: shared/polymath_shared/identity_evidence.py:1-186

## purpose
Decides whether a candidate span is a GLOBAL identity from positive evidence only (established alias, PROPN anchor, acronym, identifier), under contract `"identity-precision-v2"` — identity_evidence.py:35 [DERIVED].
Replaces `entity-admission-v1.1`'s sentence-initial-capitalization rule, which promoted `I`, `That`, `Researchers`, `Two documents` etc. to GLOBAL — "Roughly 69%" of identity admissions on two probe documents were false — identity_evidence.py:3-7 [DERIVED].
Consumers: `shared/polymath_shared/admission_interpreter.py`, `shared/polymath_shared/execution.py` (FACTS.importers) [DERIVED].
Scope is the identity predicate ONLY; GLiNER, Harbor anchor kinds, reference_basis, discourse-reference-v1, concept-evidence-v1, compiler, binding, canonicalization are frozen — identity_evidence.py:25-27 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `identity_evidence` | function | (surface: str, *, tokens=None, aliases=None, require_syntax=False, heading_context=False) -> IdentityDecision | identity_evidence.py:75-185 | admission_interpreter.py, execution.py* |
| `IdentityDecision` | dataclass (frozen=True) | is_identity: bool, kind=None, reasons=(), exclusions=(), contract=IDENTITY_CONTRACT | identity_evidence.py:45-51 | admission_interpreter.py, execution.py* |
| `IdentityEvidenceKind` | enum (str, Enum) | PROPER_NAME, ACRONYM, IDENTIFIER, ESTABLISHED_ALIAS | identity_evidence.py:38-42 | admission_interpreter.py, execution.py* |
| `RetryableDependencyUnavailable` | exception | subclass of Exception | identity_evidence.py:65-68 | admission_interpreter.py, execution.py* |
| `IDENTITY_CONTRACT` | constant | `"identity-precision-v2"` | identity_evidence.py:35 | admission_interpreter.py, execution.py* |
| `_content` | function (private) | (tokens: list[dict]) -> list[dict] | identity_evidence.py:71-72 | internal |

*module-level importers per FACTS.importers; per-symbol call sites not in FACTS.

## contracts
`identity_evidence` — identity_evidence.py:75-185
- in: positional `surface: str`; keyword-only `tokens: list[dict] | None = None`, `aliases: set[str] | None = None`, `require_syntax: bool = False`, `heading_context: bool = False` — identity_evidence.py:75-78 [DERIVED]. `tokens` are syntax-evidence-v1 tokens covering the span — identity_evidence.py:81 [DERIVED].
- pre: `require_syntax=True` implies tokens truthy, else raises `RetryableDependencyUnavailable` — identity_evidence.py:103-108 [DERIVED].
- post (decision order, tokens present):
  - case-insensitive alias exact match -> True/ESTABLISHED_ALIAS — identity_evidence.py:113-115 [DERIVED]
  - E1 head pos in `_NON_NOMINAL_HEAD` — identity_evidence.py:127-129; E2 any PRON, or single token in `{"DET","SCONJ","PRON"}` — identity_evidence.py:131-134; E3 first pos == `"NUM"` or lemma in `_QUANTIFIER` — identity_evidence.py:137-141; any exclusion -> False — identity_evidence.py:142-143 [DERIVED]
  - PROPN (filtered by `independently_capitalized` when `heading_context` — identity_evidence.py:148-157) -> True/PROPER_NAME — identity_evidence.py:158-161; acronym shape -> True/ACRONYM — identity_evidence.py:162-164; identifier shape -> True/IDENTIFIER — identity_evidence.py:165-167; else False with non-empty exclusions — identity_evidence.py:168-172 [DERIVED]
- post (degraded, tokens falsy; kept only for the frozen 55-item gold — identity_evidence.py:90-91): acronym — identity_evidence.py:175-177, identifier — identity_evidence.py:178-180, capitalized word `len(w) > 1` -> PROPER_NAME — identity_evidence.py:181-184, else False — identity_evidence.py:185 [DERIVED].
- out: frozen `IdentityDecision`; `contract` always `"identity-precision-v2"` — identity_evidence.py:35,45,51 [DERIVED].

`_content` — identity_evidence.py:71-72
- in: token dicts with `"pos"` key; out: tokens with pos not in `{"PUNCT", "SPACE"}`, order preserved [DERIVED].

## effect surface
- Postgres: none (FACTS.tables_read=[], tables_written=[]) [DERIVED]
- Qdrant / files / network / subprocess: none — module imports only `re`, `dataclasses.dataclass`, `enum.Enum` — identity_evidence.py:31-33 [DERIVED]
- env flags: none read — no `os`/`environ` in identity_evidence.py:1-185 [DERIVED]
- lazy runtime import: `from polymath_shared.layout_evidence import independently_capitalized`, executed only when `heading_context` and propn list non-empty — identity_evidence.py:149-153 [DERIVED]

## invariants
INVARIANT: | `_NON_NOMINAL_HEAD` | = 10 tags {"PRON","DET","SCONJ","ADP","ADV","AUX","VERB","PART","CCONJ","INTJ"} — identity_evidence.py:55-56 [DERIVED]
  fails-if: dropping e.g. "VERB" lets clausal heads ("When attention shifts") pass E1 — identity_evidence.py:126-129 — and admit as identity.
INVARIANT: | `_QUANTIFIER` | = 14 lemmas {"one","two","three","several","many","few","every","each","all","some","both","various","multiple","numerous"} — identity_evidence.py:58-60 [DERIVED]
  fails-if: a missing lemma lets a quantified plurality ("Several laboratory studies") inherit singular identity — identity_evidence.py:137-141.
INVARIANT: tokens non-empty => capitalization alone never yields is_identity=True (capitalized-word rule reachable only when tokens falsy) — identity_evidence.py:120-185 [DERIVED]
  fails-if: returns to the "Roughly 69%" false-admission regime — identity_evidence.py:5-7.
INVARIANT: require_syntax=True AND not tokens => raise, never a decision — identity_evidence.py:103-108 [DERIVED]
  fails-if: same span yields `Researchers -> GENERIC` with a healthy sidecar and `Researchers -> GLOBAL` without one — identity_evidence.py:83-88.
INVARIANT: decision.contract = "identity-precision-v2" on every return — identity_evidence.py:35,51 [DERIVED]
  fails-if: importer contract comparisons in admission_interpreter.py / execution.py mismatch silently.
INVARIANT: is_identity=True => kind not None; is_identity=False => kind = None (default) — identity_evidence.py:47-48 and all constructor calls identity_evidence.py:111-185 [DERIVED]
  fails-if: callers reading decision.kind.value on a False decision crash.

## determinism & idempotency
determinism: DETERMINISTIC — pure function of (surface, tokens, aliases, flags); no clock/random/uuid/network/db/env use; imports are re/dataclass/Enum only — identity_evidence.py:31-33 [DERIVED]. Sole cross-module call `independently_capitalized` — identity_evidence.py:151.
idempotency: SAFE — no writes (FACTS tables empty), returns a frozen dataclass — identity_evidence.py:45 [DERIVED].

## failure behaviour
- Raises `RetryableDependencyUnavailable` when `require_syntax` and not tokens; message contains "under admission-harbor-v2 requires" and "syntax-evidence-v1 tokens" — identity_evidence.py:103-108 [DERIVED]; intended to be retried without spending an attempt — identity_evidence.py:66-68 [DERIVED].
- No try/except anywhere in the unit; nothing swallowed — identity_evidence.py:1-185 [DERIVED].
- ImportError from the lazy import at identity_evidence.py:151 propagates uncaught to the caller [INFERRED — no handler exists in this file].
- Non-identity is a value, not an error: False decisions carry reasons/exclusions — identity_evidence.py:111,123,143,168-172,185 [DERIVED].

## dumb-code flags
- `_IDENTIFIER_RE = re.compile(r"^[A-Za-z]*\d[A-Za-z0-9.\-]*$")`: leading `[A-Za-z]*` may be empty, so bare digits ("7", "42") match => IDENTIFIER identity in both modes — identity_evidence.py:62,117-118,165-167,178-180 [DERIVED].
- POS set duplicated: inline `{"DET","SCONJ","PRON"}` is a subset of `_NON_NOMINAL_HEAD`; two places to keep in sync — identity_evidence.py:133 vs 55-56 [DERIVED].
- min-length-2 rule written twice in different forms: `^[A-Z][A-Z0-9]{1,}$` and `re.match(r"^[A-Z]", w) and len(w) > 1` — identity_evidence.py:61 vs 181 [DERIVED].
- Alias gate runs before E1-E3, so a quantified surface present verbatim in aliases returns ESTABLISHED_ALIAS despite E3's "two John Smith" intent — identity_evidence.py:113-115 vs 135-141 [DERIVED].
- Degraded capitalization branch reachable only with require_syntax=False and tokens falsy; retained solely for the frozen 55-item gold — identity_evidence.py:90-91,181-184 [DERIVED].
- Stray blank line between guard `if require_syntax and not tokens:` and its `raise` — identity_evidence.py:103-105 [DERIVED].

## refactor notes
- Blast radius: module imported by shared/polymath_shared/admission_interpreter.py and shared/polymath_shared/execution.py (FACTS.importers); signature or `IdentityDecision` field changes hit both.
- `IDENTITY_CONTRACT` (identity_evidence.py:35) is the default of `IdentityDecision.contract` (identity_evidence.py:51); changing the string silently re-contracts every emitted decision.
- Decision precedence is behavior: aliases before exclusions — identity_evidence.py:113-115 vs 126-143; PROPN before acronym/identifier — identity_evidence.py:158-167 (e.g. "PostgreSQL 14" returns PROPER_NAME, not IDENTIFIER). Reordering flips kinds.
- The raise at identity_evidence.py:103-108 is the admission-harbor-v2 S3(D) dependency; deleting it re-opens capitalization fallback under sidecar failure — identity_evidence.py:83-88.
- `independently_capitalized` is imported lazily — identity_evidence.py:151; moving `polymath_shared.layout_evidence` breaks at runtime on the heading path only, not at import time.
- Extending `_NON_NOMINAL_HEAD` / `_QUANTIFIER` — identity_evidence.py:55-60 — changes E1/E3 outcomes for every caller.

## VERIFY
```verify
grep -Fq 'IDENTITY_CONTRACT = "identity-precision-v2"' shared/polymath_shared/identity_evidence.py
grep -Eq 'def identity_evidence\(surface: str, \*, tokens' shared/polymath_shared/identity_evidence.py
grep -Fq 'class RetryableDependencyUnavailable(Exception):' shared/polymath_shared/identity_evidence.py
grep -Fq 'from polymath_shared.layout_evidence import independently_capitalized' shared/polymath_shared/identity_evidence.py
test "$(grep -c -F 'IdentityDecision(' shared/polymath_shared/identity_evidence.py)" -ge 12
! grep -Fq 'GENERIC_HEAD = ' shared/polymath_shared/identity_evidence.py
! grep -Fq 'import random' shared/polymath_shared/identity_evidence.py
```
