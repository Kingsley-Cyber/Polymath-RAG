# unit: orchestrator/orchestrator/api/polymath_style.py
anchor: orchestrator/orchestrator/api/polymath_style.py:1-201

## purpose
Single-constant module holding the Polymath answer STYLE system prompt, ported VERBATIM from polymath v3.3 `backend/services/chat_orchestrator.py POLYMATH_SYSTEM_PROMPT` at the owner's request (2026-08-27) — orchestrator/orchestrator/api/polymath_style.py:1-3 [DERIVED]. Defines the visual-typography answer grammar (thesis → table/ASCII map → reasoning bridge → caveats, KVP rundowns, h2/h3, marker palette, display contract) consumed by the UI API layer — orchestrator/orchestrator/api/polymath_style.py:3-7 [DERIVED]. The docstring warns: "Do not edit casually — the owner asked for this exact style." — orchestrator/orchestrator/api/polymath_style.py:7 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| POLYMATH_STYLE_PROMPT | module constant (str) | none -> str, one implicitly-concatenated parenthesized literal | polymath_style.py:16-201 | orchestrator/orchestrator/api/ui.py (FACTS.importers) |

## contracts
POLYMATH_STYLE_PROMPT
- in: none — module-level literal, no imports, no parameters — polymath_style.py:16 [DERIVED]
- out: one str; fixed section order: rules opened by `"Follow these rules:"` (19), `"Agent-Zero-inspired chat render style for RAG answers:"` (101), `"Mandatory display contract:"` (182), terminal line `"Sound like a smart friend explaining, not a research assistant producing a report."` (199-200) — polymath_style.py:19,101,182,199-200 [DERIVED]
- pre: none (import-time evaluation only) — polymath_style.py:16 [DERIVED]
- post: module binds exactly one public name; the only other content is the docstring at 1-14 — polymath_style.py:1-14,16 [DERIVED]

## effect surface
- Postgres tables read/written: none — FACTS `tables_read: []`, `tables_written: []`; constant definition at polymath_style.py:16 [DERIVED]
- Qdrant collections / files / network / subprocess / env flags: none — module contains no imports and no statements besides the assignment — polymath_style.py:1-201 [DERIVED]

## invariants
INVARIANT: public symbol count == 1 (`POLYMATH_STYLE_PROMPT`) — polymath_style.py:16 [DERIVED]
  fails-if: rename/move breaks the `orchestrator/orchestrator/api/ui.py` import.
INVARIANT: marker palette size == 3 (`→` reasoning bridges, `✓/✗` binary status, 1 warning marker) — polymath_style.py:81-82 [DERIVED]
  fails-if: answers emit markers the ui.py renderer does not style.
INVARIANT: bold-sentence instructions == 0; opening synthesis is `"(never a bold sentence)"` — polymath_style.py:107 with retirement note 9-13 [DERIVED]
  fails-if: bold opening sentence collides with PRESENTATION-V1 in ui.py, which caps bold at "at most five words" — polymath_style.py:11-12 [DERIVED].
INVARIANT: KVP rundown trigger == "2-6 attributes"; default heading order == "h2 then h3" — polymath_style.py:84-85 [DERIVED]
  fails-if: ui.py renderer drifts from heading/table shapes the prompt promises.

## determinism & idempotency
determinism: DETERMINISTIC — pure string literal; no clock/random/uuid/network/db/env reads, no imports — polymath_style.py:16-201 [DERIVED]
idempotency: SAFE — repeated import rebinds the same constant; no side effects — polymath_style.py:1-201 [INFERRED: file holds only docstring plus one assignment]

## failure behaviour
No handlers, no raises, no fallbacks exist in the module; the only failure mode is an import-time syntax error, which propagates to the importer ui.py — polymath_style.py:1-201 [DERIVED]

## dumb-code flags
- Glyph mismatch: docstring names the palette `->/check/x` (6) while the prompt mandates Unicode `→` and `✓/✗` (81-82) — polymath_style.py:6,81-82 [DERIVED]
- Hardcoded provenance dates in the docstring: 2026-08-27 (3) and 2026-09-06 (9) — polymath_style.py:3,9 [DERIVED]
- Magic thresholds embedded in prompt text: "six sentences" / "2-4 short sections" (66-67), "2-6 attributes" (85), "3-5 columns" (95-96); the "at most five words" bold cap lives only in the docstring's description of ui.py, not in the prompt — polymath_style.py:66-67,85,95-96,11-12 [DERIVED]

## refactor notes
- Value is quasi-frozen: ported VERBATIM from polymath v3.3 `POLYMATH_SYSTEM_PROMPT` and marked "Do not edit casually" — polymath_style.py:1-7 [DERIVED]; text edits are owner-visible style changes, not refactors.
- Blast radius: `orchestrator/orchestrator/api/ui.py` imports `POLYMATH_STYLE_PROMPT` (FACTS.importers); any rename, move, or repackaging breaks it — polymath_style.py:16 [DERIVED].
- Coupled contract with ui.py PRESENTATION-V1: the prompt's bold ban (107) exists because ui.py limits bold to five-word anchors (11-12); reintroducing bold-thesis clauses breaks the visual contract — polymath_style.py:9-13,107 [DERIVED].
- The constant is one parenthesized implicit concatenation (16 opens, 201 closes): a stray comma silently changes the type from str to tuple for every consumer — polymath_style.py:16,201 [INFERRED: comma would make the parenthesized expression a tuple]

## VERIFY
```verify
grep -Fq 'POLYMATH_STYLE_PROMPT' orchestrator/orchestrator/api/polymath_style.py
grep -Fq 'You are a knowledgeable collaborator answering from retrieved context.' orchestrator/orchestrator/api/polymath_style.py
grep -Fq 'Agent-Zero-inspired chat render style for RAG answers:' orchestrator/orchestrator/api/polymath_style.py
grep -Fq 'Mandatory display contract:' orchestrator/orchestrator/api/polymath_style.py
grep -Fq '(never a bold sentence)' orchestrator/orchestrator/api/polymath_style.py
! grep -Fq 'def ' orchestrator/orchestrator/api/polymath_style.py
test "$(grep -c -F '✓/✗' orchestrator/orchestrator/api/polymath_style.py)" -ge 1
```
