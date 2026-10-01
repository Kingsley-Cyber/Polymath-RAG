# unit: shared/polymath_shared/query_intent.py
anchor: shared/polymath_shared/query_intent.py:1-205

## purpose
Deterministic 10-intent classifier over the query-compiler output; folds compiler signals (`task_type`, subquery `qtype`s, `graph_useful`, `exact_terms`, `entities`, `response_type`) plus `query_router` lexical families into one canonical intent — shared/polymath_shared/query_intent.py:1-13 [DERIVED]. No new classifier LLM; runtime policy is INTENT × PROFILE-FIELD × TECHNIQUE × BUDGET — shared/polymath_shared/query_intent.py:3-9 [DERIVED]. Consumers: `orchestrator/orchestrator/api/retrieve.py`, `orchestrator/orchestrator/api/ui.py`, `shared/polymath_shared/chat_plan.py`, `shared/polymath_shared/deep_research/_small-modules` (FACTS.importers) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `QUERY_INTENT_VERSION` | constant | `= "query-intent-v1"` | shared/polymath_shared/query_intent.py:27 | — |
| `INTENTS` | constant tuple | 10 names: `EXACT, DEFINITION, MECHANISM, RELATIONSHIP, COMPARISON, PROCEDURE, APPLICATION, SYNTHESIS, RECALL, EXPLORATORY` | shared/polymath_shared/query_intent.py:31-34 | — |
| `classify_intent` | def | `(resolved_request, *, task_type=None, qtypes=(), graph_useful=False, exact_terms=(), entities=(), response_type="answer") -> str` | shared/polymath_shared/query_intent.py:69-118 | module importers (above) |
| `IntentPolicy` | dataclass(frozen=True) | fields `dualread: bool`, `micro_latent: bool`, `breadth="MULTI_PREFERRED"`, `resolution_lift="normal"`, `graph="off"`, `atom_kinds=()`, `seealso_fanout=False` | shared/polymath_shared/query_intent.py:124-135 | module importers |
| `INTENT_POLICY` | dict | `dict[str, IntentPolicy]`, one row per intent | shared/polymath_shared/query_intent.py:148-159 | module importers |
| `policy_for` | def | `(intent: str) -> IntentPolicy \| None` | shared/polymath_shared/query_intent.py:162-163 | module importers |
| `apply_intent_policy` | def | `(intent: str, budget) -> budget` | shared/polymath_shared/query_intent.py:166-191 | module importers |
| `intent_of_plan` | def | `(plan) -> str` (duck-typed ChatPlan) | shared/polymath_shared/query_intent.py:194-205 | module importers |

Private helpers: `_has_identifier` :61-62, `_any` :65-66.

## contracts

**classify_intent** — shared/polymath_shared/query_intent.py:69-118
- in: `qtypes` normalized to an uppercase set (`str(t).upper()`) :75; `exact_terms` tuple :76; `resolved_request` None-tolerant via `(resolved_request or "").strip()` :74.
- out: exactly one of the ten `INTENTS` strings :31-34, :118.
- pre: none — tolerates `None`/empty for every signal :74-76.
- post: never raises; unmatched input returns `"EXPLORATORY"` (floor) :13, :118. Precedence fixed, first satisfied rule wins: EXACT → COMPARISON → RECALL → SYNTHESIS → RELATIONSHIP → PROCEDURE → APPLICATION → MECHANISM → DEFINITION → EXPLORATORY :78-118. EXACT additionally requires: identifier-like exact term, `not graph_useful`, qtypes disjoint from `{"COMPARISON", "COUNTERPOINT", "BRIDGE"}`, no `_PROCEDURE_PATTERNS` hit, no `why`/`how (does|do|can)` :80-82.

**apply_intent_policy** — shared/polymath_shared/query_intent.py:166-191
- in: `intent: str`; `budget` duck-typed (mutated via `dataclasses.replace`) :171, :191.
- out: copy of `budget`; unknown intent (policy_for → `None`) returns `budget` unchanged :172-174.
- post: overrides applied only when the attribute exists: `dualread_enabled=p.dualread`, `latent_enabled=p.micro_latent` :175; `breadth` :177-178; `atom_kinds` :179-180; `resolution_lift_enabled = p.resolution_lift != "off"` :181; `seealso_fanout_enabled = p.seealso_fanout` :183; `graph_dest_enabled = p.graph in ("auto", "strong")` :185; `rerank_round_robin = p.breadth != "SINGLE_OK"` :190.

**policy_for** — shared/polymath_shared/query_intent.py:162-163
- in: any string; uppercased before lookup.
- out: `IntentPolicy` row or `None`.

**intent_of_plan** — shared/polymath_shared/query_intent.py:194-205
- in: plan duck-typed via `getattr`; `qtypes` from `q.type` of `plan.queries`; `resolved_request` falls back to `original_request`; defaults `graph_useful=False`, `exact_terms=()`, `entities=()`, `response_type="answer"` :196-204.

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`) [DERIVED].
- Qdrant / files / network / subprocess: none visible; imports are `re`, `collections.abc`, `dataclasses`, and `polymath_shared.query_router`/`surface_registry` only — shared/polymath_shared/query_intent.py:17-25, :121, :140 [DERIVED].
- Env flags: none read.

## invariants
INVARIANT: count of `resolution_lift="off"` rows = 10 = count of intents — shared/polymath_shared/query_intent.py:149-158 [DERIVED]
  fails-if: lift re-enabled before the PRECISION repair reintroduces the audited defect (0 of 7,806 candidates into evidence, ~1 s and ~3 judge seats per turn) — shared/polymath_shared/query_intent.py:143-147
INVARIANT: `dualread=True` in 10/10 policy rows — shared/polymath_shared/query_intent.py:149-158 [DERIVED]
  fails-if: an intent loses the DOCUMENT_PROFILE→PARENT_MAP→CHILD spine (lane E) at runtime
INVARIANT: `micro_latent=False` only for {EXACT, DEFINITION}; True for the other 8 — shared/polymath_shared/query_intent.py:149-158 [DERIVED]
  fails-if: latent micro-search (lane D) runs on identifier lookups, adding cost to precision lanes
INVARIANT: `breadth="SINGLE_OK"` only {EXACT, DEFINITION}; `"MULTI_REQUIRED"` only {COMPARISON, SYNTHESIS}; rest `"MULTI_PREFERRED"` — shared/polymath_shared/query_intent.py:149-158 [DERIVED]
  fails-if: `rerank_round_robin` flipped wrongly via :190, breaking doc-fair diversity for MULTI_* intents
INVARIANT: `graph="auto"` only RELATIONSHIP; `graph="off"` for {EXACT, DEFINITION, RECALL}; rest `"conditional"` — shared/polymath_shared/query_intent.py:149-158 [DERIVED]
  fails-if: `graph_dest_enabled` (:185) turns on for an intent whose row never asked for the graph lane
INVARIANT: `seealso_fanout=True` only {RELATIONSHIP, EXPLORATORY} — shared/polymath_shared/query_intent.py:152, :158 [DERIVED]
INVARIANT: len(INTENT_POLICY) keys = len(INTENTS) = 10 — shared/polymath_shared/query_intent.py:31-34, :148-159 [DERIVED]
  fails-if: `classify_intent` returns an intent with no row → `policy_for` → `None` → `apply_intent_policy` silently no-ops :172-174
INVARIANT: classify_intent precedence is source-ordered and first-match-wins; `INTENTS` tuple order is documentation only — shared/polymath_shared/query_intent.py:12-13, :29-30 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC — pure regex/dataclass logic over inputs; "Pure, order-stable: same inputs → same intent" — shared/polymath_shared/query_intent.py:10 [DERIVED]
idempotency: SAFE — no mutation of inputs or globals; `apply_intent_policy` returns a new object via `replace` :191; `IntentPolicy` is frozen :124 [DERIVED]

## failure behaviour
- `classify_intent` never raises; EXPLORATORY is the guaranteed floor — shared/polymath_shared/query_intent.py:13, :118 [DERIVED].
- None-swallowing at every edge: `t or ""` in `_has_identifier` :62; `(resolved_request or "")` :74; `qtypes or ()` / `exact_terms or ()` :75-76; `getattr(...) or ()` in `intent_of_plan` :201-203.
- `policy_for` on unknown/None intent returns `None` :162-163; caller then sees the budget unchanged from `apply_intent_policy` :172-174.
- No exceptions raised anywhere in the module.

## dumb-code flags
- Mid-file imports after function definitions: `from dataclasses import dataclass, replace` at :121 and `from polymath_shared.surface_registry import ...` at :140 — shared/polymath_shared/query_intent.py:121, :140 [DERIVED].
- `classify_intent` accepts `entities` but the body never reads it — shared/polymath_shared/query_intent.py:69-76 vs :78-118 [DERIVED].
- `_IDENTIFIER` first alternative `\d` matches any digit, so the later `\b\d+(?:mm|ms|fps|px|k|K|GB|MB)\b` alternative can never add a match — shared/polymath_shared/query_intent.py:58 [INFERRED: `\d` subsumes the unit alternative].
- `INTENTS` tuple order ≠ classification precedence order; comment says order is documentation only — shared/polymath_shared/query_intent.py:29-30 [DERIVED].
- Declared-but-unused policy values: no row sets `graph="strong"`, `resolution_lift` to `high`/`very_high` (prior values recorded only in a comment) — shared/polymath_shared/query_intent.py:131-133, :143-147 [DERIVED].
- `response_type` checked only against the literal `"artifact"` — shared/polymath_shared/query_intent.py:107 [DERIVED].

## refactor notes
- Renaming any of the 10 intent strings breaks `INTENT_POLICY` keys and the four importers (retrieve.py, ui.py, chat_plan.py, deep_research/_small-modules per FACTS.importers) — shared/polymath_shared/query_intent.py:31-34, :148 [DERIVED].
- Module imports private symbols from `query_router`: `_CONCEPT_PATTERNS`, `_POLYMATH_PATTERNS`, `_PROCEDURE_PATTERNS`, `_hits` — shared/polymath_shared/query_intent.py:20-25 [DERIVED]; renaming them there breaks this module.
- `atom_kinds` tuples must match `surface_registry` `ATOM_KINDS`/`MECHANISM_KINDS` (single source, P4a) — shared/polymath_shared/query_intent.py:138-140 [DERIVED].
- `apply_intent_policy`'s contract is the budget field names (`dualread_enabled`, `latent_enabled`, `breadth`, `atom_kinds`, `resolution_lift_enabled`, `seealso_fanout_enabled`, `graph_dest_enabled`, `rerank_round_robin`); the `hasattr` guards mean a budget-field rename silently drops the override instead of failing — shared/polymath_shared/query_intent.py:175-190 [DERIVED].
- Changing `classify_intent` rule order changes intents for inputs matching multiple rules (first rule wins) — shared/polymath_shared/query_intent.py:12-13 [DERIVED].

## VERIFY
```verify
grep -Fq 'QUERY_INTENT_VERSION = "query-intent-v1"' shared/polymath_shared/query_intent.py
test "$(grep -c -F 'resolution_lift="off"' shared/polymath_shared/query_intent.py)" -ge 10
test "$(grep -c -F 'dualread=True' shared/polymath_shared/query_intent.py)" -ge 10
grep -Fq 'return "EXPLORATORY"' shared/polymath_shared/query_intent.py
! grep -Fq 'resolution_lift="high"' shared/polymath_shared/query_intent.py
grep -Fq 'from dataclasses import dataclass, replace' shared/polymath_shared/query_intent.py
grep -Eq 'rerank_round_robin.*SINGLE_OK' shared/polymath_shared/query_intent.py
```
