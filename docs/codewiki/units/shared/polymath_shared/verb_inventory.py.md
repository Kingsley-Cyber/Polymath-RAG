# unit: shared/polymath_shared/verb_inventory.py
anchor: shared/polymath_shared/verb_inventory.py:1-202

## purpose
Supplies `VERBS`, a frozen 190-token frozenset used by `concept_inventory` for "concept-candidate termination" — shared/polymath_shared/verb_inventory.py:1 [DERIVED].
Snapshot of the retired rule pack `core-predicates-v1.5.0`, frozen 2026-09-03; previously rebuilt at import time with a silent EMPTY-set fallback, now pure data — shared/polymath_shared/verb_inventory.py:3-7 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `VERBS` | module-level constant | data, not callable: `VERBS: frozenset[str]` (190 tokens) | shared/polymath_shared/verb_inventory.py:11-202 | shared/polymath_shared/concept_inventory.py (FACTS.importers) |

## contracts
`VERBS` (constant, bound at import):
- in: nothing — no runtime imports; only `from __future__ import annotations` — shared/polymath_shared/verb_inventory.py:9 [DERIVED]
- out: frozenset of exactly 190 quoted lowercase string tokens, `"absorb"` first to `"written"` last — shared/polymath_shared/verb_inventory.py:12,201 [DERIVED]
- pre: none — pure literals, no I/O of any kind — shared/polymath_shared/verb_inventory.py:1-202 [DERIVED]
- post: "deterministic, no dependency, no fallback" — shared/polymath_shared/verb_inventory.py:7 [DERIVED]

## effect surface
None. `tables_read` and `tables_written` are empty (FACTS); no files, network, subprocess, or env flags appear anywhere in shared/polymath_shared/verb_inventory.py:1-202; the only import statement is `from __future__ import annotations` — shared/polymath_shared/verb_inventory.py:9 [DERIVED].

## invariants
INVARIANT: token count = 190 = docstring claim "190 evidence verbs + multiword tokens" — shared/polymath_shared/verb_inventory.py:4,12-201 [DERIVED]
  fails-if: docstring count drifts from data; the frozen-snapshot guarantee (line 3) is silently violated.
INVARIANT: type of `VERBS` = `frozenset[str]` (annotation literal) — shared/polymath_shared/verb_inventory.py:11 [DERIVED]
  fails-if: a mutable set lets any importer mutate shared frozen state; "no fallback" determinism (line 7) unenforceable.
INVARIANT: runtime imports = 0 (sole import is `__future__`) — shared/polymath_shared/verb_inventory.py:9 [DERIVED]
  fails-if: reintroduces the pack dependency and the old import-error fallback path (lines 5-6).
INVARIANT: every token is a lowercase string literal — shared/polymath_shared/verb_inventory.py:12-201 [DERIVED]
  fails-if: mixed-case probes (e.g. `"CEO"` vs `"ceo"` at line 39) miss membership and change concept_inventory termination.

## determinism & idempotency
determinism: DETERMINISTIC — pure literal data; no clock/random/uuid/network/db/env anywhere in shared/polymath_shared/verb_inventory.py:1-202 [DERIVED]
idempotency: SAFE — import binds one constant; no tables written, no side effects (FACTS tables_read/tables_written empty) [DERIVED]

## failure behaviour
No handlers, no fallback in the current file — "no dependency, no fallback" — shared/polymath_shared/verb_inventory.py:7 [DERIVED].
Historical only: the pre-2026-09-03 version "fell back to an EMPTY set on any import error — a silent fallback"; that path is retired — shared/polymath_shared/verb_inventory.py:5-6 [DERIVED].

## dumb-code flags
- Name says VERBS but holds non-verb tokens: `"accuracy"`:14, `"aka"`:21, `"application"`:25, `"ceo"`:39, `"cto"`:63, `"division"`:73, `"kind"`:107, `"offices"`:132, `"subsidiary"`:185, `"type"`:195, `"usage"`:196 — covered by "multiword tokens" in the docstring — shared/polymath_shared/verb_inventory.py:4 [DERIVED]
- Frozen inflection gaps: `"adapted"`:17 present but `"adopted"` absent next to `"adopt"`:18/`"adoption"`:19; `"allows"`:23 present but `"allowed"` absent; `"requires"`:164 present but `"required"` absent (listing is closed at :202) [DERIVED]
- `from __future__ import annotations` (:9) is dead weight — the only annotation `frozenset[str]` (:11) is a builtin generic needing no future import [INFERRED: no forward references exist in the file]

## refactor notes
- Sole consumer is shared/polymath_shared/concept_inventory.py (FACTS.importers): any membership or rename change to `VERBS` alters concept-candidate termination there [DERIVED].
- Content is policy-frozen 2026-09-03 under "LLM-DIRECT-CANON, ADR-0017" — shared/polymath_shared/verb_inventory.py:3,7; edits are data-policy changes, not free refactors [DERIVED].
- Adding/removing a token requires updating the literal "190" in the docstring — shared/polymath_shared/verb_inventory.py:4 [DERIVED].

## VERIFY
```verify
grep -Fq 'VERBS: frozenset[str] = frozenset((' shared/polymath_shared/verb_inventory.py
test "$(grep -c -F '",' shared/polymath_shared/verb_inventory.py)" -ge 190
grep -Fq '"written",' shared/polymath_shared/verb_inventory.py
grep -Fq 'core-predicates-v1.5.0' shared/polymath_shared/verb_inventory.py
! grep -Fq 'def ' shared/polymath_shared/verb_inventory.py
grep -Fq 'verb_inventory' shared/polymath_shared/concept_inventory.py
grep -Fq 'concept-candidate termination' shared/polymath_shared/verb_inventory.py
```
