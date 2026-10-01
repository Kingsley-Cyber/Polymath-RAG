# unit: shared/polymath_shared/query_constraints.py
anchor: shared/polymath_shared/query_constraints.py:1-310

## purpose
Deterministic, no-LLM constraint-aware retrieval for the query pipeline: CA0 detects explicit SOURCE constraints in the raw query q0 ("according to X", "in X's book"), CA1 resolves them to doc_ids by lexical identity, CA3 reorders already-reranked evidence by constraint satisfaction, CA4 grades evidence support roles and produces the epistemic state for the answerability gate — shared/polymath_shared/query_constraints.py:2-11,118,207,261 [DERIVED]. Consumed by `shared/polymath_shared/chat_plan.py` and `orchestrator/orchestrator/api/ui.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Constraint` | class | (kind: str, value: str, strength: str, resolved_targets: list[str] = [], confidence: float = 0.0, reason: str = "") -> dataclass | query_constraints.py:24-40 | chat_plan.py, ui.py (module importers) |
| `detect_explicit_constraints` | def | (q0: str) -> list[Constraint] | query_constraints.py:97-115 | chat_plan.py, ui.py |
| `resolve_constraint_targets` | def | (constraints, source_index: Mapping[str, str], *, scout_nominations=None, corpus_id=None) -> list[Constraint] | query_constraints.py:173-204 | chat_plan.py, ui.py |
| `align_by_constraint` | def | (evidence: list[dict], targets: set[str] | list[str], strength: str) -> list[dict] | query_constraints.py:222-243 | chat_plan.py, ui.py |
| `align_evidence_for_constraints` | def | (evidence: list[dict], constraints: list[Constraint]) -> list[dict] | query_constraints.py:246-258 | chat_plan.py, ui.py |
| `grade_evidence` | def | (evidence: list[dict], plan) -> tuple[dict[str, str], dict] | query_constraints.py:276-309 | chat_plan.py, ui.py |
| `CONSTRAINT_KINDS` | const | ("SOURCE", "DOCUMENT", "SCOPE") | query_constraints.py:19 | — |
| `CONSTRAINT_STRENGTHS` | const | ("HARD", "SOFT", "EXPLORATORY") | query_constraints.py:20 | — |
| `EVIDENCE_ROLES` | const | ("DIRECT", "PARTIAL", "RELATED") | query_constraints.py:273 | — |

## contracts
**detect_explicit_constraints** — query_constraints.py:97-115
- in: raw query `q0` (any string; `(q0 or "")` tolerated) — :101
- out: SOURCE constraints; strongest matching tier wins for all sources it names; at most one constraint per distinct source — :98-100,109-111,114
- pre: none
- post: no trigger ⇒ `[]`, never a fabricated HARD constraint — :100,115; strength/confidence come from the tier table (("HARD", 0.9), ("SOFT", 0.7), ("EXPLORATORY", 0.6)) — :81

**resolve_constraint_targets** — query_constraints.py:173-204
- in: constraints; `source_index` = {doc_id: source_name} already scoped to the active corpus (shared/ does no I/O) — :125-126,178
- out: new Constraints via `replace` with `resolved_targets` (doc_ids) + resolution `confidence` filled; kind/value/strength/reason preserved — :176-178,203
- pre: caller supplies corpus-scoped index; scout_nominations optional — :174-175,180
- post: unique top score ≥ `_IDENTITY_FLOOR` (0.9) ⇒ 1 target, conf 0.95 (exact) or 0.85 (containment); weak unique top ≥ 0.6 in `scout[:3]` ⇒ conf 0.5; tie at top or weak-unconfirmed ⇒ `resolved_targets=[]`, never an exception — :132-137,193-203

**align_by_constraint** — query_constraints.py:222-243
- in: already-reranked evidence dicts carrying `doc_id`; targets; strength
- out: reordered evidence; HARD ⇒ satisfying items first then rest (order preserved within each); SOFT ⇒ best source chunk lifted to just behind rank 1 only if below rank 2; EXPLORATORY ⇒ identity — :230-243
- pre: evidence is in rerank order (cross-encoder stays the semantic authority) — :208-212
- post: never adds/removes an item, only reorders; identity when no targets, unknown strength, or no source evidence present — :224,227-232

**align_evidence_for_constraints** — query_constraints.py:246-258
- in: evidence, constraints; only resolved SOURCE constraints act — :250
- out: applies `align_by_constraint` under the strongest present tier (HARD > SOFT > EXPLORATORY), unioning that tier's targets; identity when nothing resolved — :253-258

**grade_evidence** — query_constraints.py:276-309
- in: evidence items carrying `chunk_id`, `doc_id`, `query_ids`, `rerank_score`; plan carrying `queries` (id, origin) and `explicit_constraints` — :277-286
- out: ({chunk_id: role}, epistemic dict) with keys `directly_established`, `establishes_need`, `n_direct`, `n_partial`, `n_related` — :305-308
- pre: none (getattr defaults "USER"/None tolerate missing plan fields) — :281,283
- post: DIRECT = user-origin retrieval AND `rerank_score > 0` AND satisfies all resolved HARD targets; PARTIAL = user + relevant but not the named source; else RELATED; 0 DIRECT and 0 PARTIAL ⇒ answer must state the gap — :291-300,279-280

## effect surface
- Postgres tables: none (FACTS.tables_read/tables_written empty)
- Qdrant / files / network / subprocess / env flags: none — module is pure in-memory; "shared/ does no I/O" — query_constraints.py:125-126 [DERIVED]

## invariants
INVARIANT: detection confidence HARD 0.9 > SOFT 0.7 > EXPLORATORY 0.6 — query_constraints.py:81 [DERIVED]
  fails-if: tier confidences collapse; callers gating on `confidence` misrank constraints.
INVARIANT: author-containment identity score 0.92 ≥ `_IDENTITY_FLOOR` 0.9 — query_constraints.py:167,135 [DERIVED]
  fails-if: author-name matches drop to the weak path and would need Scout confirmation to resolve.
INVARIANT: title-fragment score 0.6 == `_WEAK_FLOOR` 0.6 and < `_IDENTITY_FLOOR` 0.9 — query_constraints.py:169,136,135 [DERIVED]
  fails-if: mention-like fragments auto-resolve without Scout, producing wrong-source HARD filtering.
INVARIANT: tie at top of identity scores ⇒ `resolved_targets == []` — query_constraints.py:195-202,124-125 [DERIVED]
  fails-if: a confidently-wrong doc_id becomes a HARD filter and erases the correct answer.
INVARIANT: len(align_by_constraint output) == len(evidence input) — query_constraints.py:224,230-243 [DERIVED]
  fails-if: evidence silently dropped or duplicated into synthesis.
INVARIANT: invalid `strength` is coerced to "SOFT", never "HARD" — query_constraints.py:37-38 [DERIVED]
  fails-if: a malformed constraint silently hard-filters evidence to the wrong source.
INVARIANT: SOFT lift places the best source chunk at index ≤ 1 — query_constraints.py:238-241 [DERIVED]
  fails-if: the "bounded preference" becomes domination of the ranked answer.

## determinism & idempotency
determinism: DETERMINISTIC — pure regex + dataclass logic; resolution sort breaks ties by doc_id ("deterministic: strongest first, doc_id tiebreak") — query_constraints.py:186-189; no clock/random/uuid/network/db/env reads anywhere in the unit.
idempotency: SAFE — pure functions; inputs not mutated (`ev = list(evidence)` :226; `replace(c, ...)` :203).

## failure behaviour
- `resolve_constraint_targets`: fail-open — unresolved/ambiguous source yields `resolved_targets=[]`, never an exception — query_constraints.py:179,195-202.
- `align_by_constraint` / `align_evidence_for_constraints`: fail-open identity when source absent from evidence or nothing resolved — query_constraints.py:231-232,251-252.
- `detect_explicit_constraints`: no trigger ⇒ `[]` — query_constraints.py:115.
- `grade_evidence`: tolerates missing plan attributes via `getattr` defaults — query_constraints.py:281,283; no `raise` anywhere in the unit.
- No error codes raised; the only caller-visible failure signal is the epistemic state (`establishes_need: false` forces a stated gap) — query_constraints.py:279-280,305-306.

## dumb-code flags
- `corpus_id` parameter accepted but never referenced in the function body — query_constraints.py:174-175 vs 180-204 [DERIVED].
- 0.6 duplicated: `_WEAK_FLOOR = 0.6` and the hardcoded title-fragment `return 0.6` — changing one silently diverges from the other — query_constraints.py:136,169 [DERIVED].
- Magic number 0.92 (author containment) with no named constant — query_constraints.py:167 [DERIVED].
- DOCUMENT/SCOPE kinds are declared and accepted but nothing produces them; V1 detects SOURCE only — query_constraints.py:10,19,34-36 [DERIVED].
- `confidence` field carries two different scales: detection (0.9/0.7/0.6, :81) overwritten by resolution (0.95/0.85/0.5, :198,:201) in the same field — query_constraints.py:31,81,198-205 [DERIVED].
- EXPLORATORY branch of `align_by_constraint` is a no-op `return ev` — query_constraints.py:243 [DERIVED].
- Rank bound expressed as bare index comparison `if pos > 1:` — query_constraints.py:240 [DERIVED].

## refactor notes
- Both importers (`orchestrator/orchestrator/api/ui.py`, `shared/polymath_shared/chat_plan.py`, FACTS.importers) break on any signature change to the six public symbols.
- `Constraint` is the receipt-serialization contract ("`asdict` round-trips through the receipt") — field renames break persisted receipts — query_constraints.py:26 [DERIVED].
- `grade_evidence` consumes the plan shape `queries[].id`/`.origin` and `explicit_constraints`, plus evidence keys `chunk_id`/`doc_id`/`query_ids`/`rerank_score` — plan or evidence schema changes ripple into the answerability gate — query_constraints.py:277-286 [DERIVED].
- Epistemic keys (`directly_established`, `establishes_need`, `n_direct`, `n_partial`, `n_related`) drive the gate consumer; renames break it — query_constraints.py:279-280,305-308 [DERIVED].
- Scout confirmation couples to `scout_nominations` ordering with K=3 — query_constraints.py:137,199-201 [DERIVED].
- Adding DOCUMENT/SCOPE kinds touches: :19, :34-36 (coercion), :182-185 (resolve skip), :250 (align filter), :285 (grade hard filter).

## VERIFY
```verify
grep -Fq 'CONSTRAINT_KINDS = ("SOURCE", "DOCUMENT", "SCOPE")' shared/polymath_shared/query_constraints.py
grep -Fq '_IDENTITY_FLOOR = 0.9' shared/polymath_shared/query_constraints.py
grep -Fq 'EVIDENCE_ROLES = ("DIRECT", "PARTIAL", "RELATED")' shared/polymath_shared/query_constraints.py
grep -Fq 'never an exception' shared/polymath_shared/query_constraints.py
grep -Eq 'def (detect_explicit_constraints|resolve_constraint_targets|align_by_constraint|align_evidence_for_constraints|grade_evidence)' shared/polymath_shared/query_constraints.py
test "$(grep -c -F 'align_by_constraint' shared/polymath_shared/query_constraints.py)" -ge 2
! grep -Fq 'raise' shared/polymath_shared/query_constraints.py
```
