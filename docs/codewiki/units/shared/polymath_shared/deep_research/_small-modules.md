# unit: shared/polymath_shared/deep_research/_small-modules
anchor: shared/polymath_shared/deep_research/__init__.py:1-57

## purpose
Package facade for DEEP-RESEARCH-MODE-V1: multi-round research reports over the caller's libraries; `__init__.py` re-exports `engine`, `evidence`, `moves`, `prompts` — shared/polymath_shared/deep_research/__init__.py:1-7 [DERIVED].
This unit = that facade plus `moves.py`, the deterministic controller that gives every planned search one of four MOVES — `broad`, `deep`, `adjacent`, `inverse` — from the question's intent and run state — shared/polymath_shared/deep_research/moves.py:1-7 [DERIVED].
Importers: `orchestrator/orchestrator/api/deep_research.py`, `shared/polymath_shared/deep_research/engine.py`, `evidence.py`, `prompts.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| deep_research (package) | module | re-exports engine/evidence/moves/prompts; `__all__` of 33 names | shared/polymath_shared/deep_research/__init__.py:9-56 | orchestrator/orchestrator/api/deep_research.py, engine.py, evidence.py, prompts.py (FACTS.importers) |
| MOVES | const tuple | `("broad", "deep", "adjacent", "inverse")` | shared/polymath_shared/deep_research/moves.py:19 | re-exported at shared/polymath_shared/deep_research/__init__.py:40 |
| question_intent | def | `(question: str) -> str` | shared/polymath_shared/deep_research/moves.py:50-54 | re-exported at __init__.py:40 |
| is_evaluative | def | `(question: str) -> bool` | shared/polymath_shared/deep_research/moves.py:57-62 | re-exported at __init__.py:40 |
| default_move | def | `(level: int) -> str` | shared/polymath_shared/deep_research/moves.py:65-67 | engine ("the engine owns WHEN the controller is asked", moves.py:10) [INFERRED] |
| allocate | def | `(weights: Sequence[float], n: int) -> tuple[int, ...]` | shared/polymath_shared/deep_research/moves.py:70-83 | re-exported at __init__.py:40 |
| _live | def (private) | `(weights: Sequence[int], dry: Iterable[str]) -> tuple[int, ...]` | shared/polymath_shared/deep_research/moves.py:86-93 | child_quota (moves.py:117) |
| with_inverse | def | `(quota: Sequence[int]) -> tuple[int, ...]` | shared/polymath_shared/deep_research/moves.py:96-105 | root_quota (moves.py:111) |
| root_quota | def | `(intent: str, n: int, *, evaluative: bool) -> tuple[int, ...]` | shared/polymath_shared/deep_research/moves.py:108-111 | engine [INFERRED: engine owns when the controller runs, moves.py:10] |
| child_quota | def | `(parent_move: str, n: int, *, repeat: bool, dry: Iterable[str] = ()) -> tuple[int, ...]` | shared/polymath_shared/deep_research/moves.py:114-121 | engine [INFERRED, same] |
| is_repeat | def | `(parent_rows: Sequence[str], seen: set[str]) -> bool` | shared/polymath_shared/deep_research/moves.py:124-127 | engine [INFERRED] |
| concentration_anchors | def | `(cited_docs: Sequence[str]) -> tuple[str, ...]` | shared/polymath_shared/deep_research/moves.py:130-136 | engine [INFERRED] |
| is_one_sided | def | `(intent: str, evaluative: bool, learning_moves: Sequence[str]) -> bool` | shared/polymath_shared/deep_research/moves.py:139-142 | engine [INFERRED] |

Only 4 moves names are package-public: `MOVES, allocate, is_evaluative, question_intent` — shared/polymath_shared/deep_research/__init__.py:40 [DERIVED].

## contracts
**question_intent** — in: any question string; out: an intent key present in `INTENT_WEIGHTS`; pre: `classify_intent` importable (lazy import); post: unmapped intent → `"EXPLORATORY"` — shared/polymath_shared/deep_research/moves.py:52-54 [DERIVED].
**is_evaluative** — in: question (None tolerated via `question or ""`); out: `True` iff `_EVALUATIVE` regex matches — shared/polymath_shared/deep_research/moves.py:41-44, 62 [DERIVED].
**default_move** — out: `"broad"` when `level <= 1`, else `"deep"` — shared/polymath_shared/deep_research/moves.py:67 [DERIVED].
**allocate** — out: tuple with `len == len(weights)`, sum `== n`; `n <= 0` → all zeros; total weight 0 → equal weights; negative weights clamped to 0; exact `Fraction` arithmetic, ties in MOVES order — shared/polymath_shared/deep_research/moves.py:71-83 [DERIVED].
**_live** — out: dry moves at 0; if that leaves nothing, non-dry moves at 1; if still nothing, weights as given — shared/polymath_shared/deep_research/moves.py:88-93 [DERIVED].
**with_inverse** — post: result inverse slot `>= 1` (unless already present or quota empty); slot taken from deep if `q[_DEEP] > 0`, else from the largest/later move — shared/polymath_shared/deep_research/moves.py:100-105 [DERIVED].
**root_quota** — out: `allocate(INTENT_WEIGHTS.get(intent, INTENT_WEIGHTS["EXPLORATORY"]), n)`, then `with_inverse` iff `evaluative` — shared/polymath_shared/deep_research/moves.py:110-111 [DERIVED].
**child_quota** — out: `CHILD_WEIGHTS.get(parent_move, CHILD_WEIGHTS[DEEP])` zeroed by `_live`, then if `repeat and q[_DEEP] > 0 and ADJACENT not in dry` one slot moves deep→adjacent — shared/polymath_shared/deep_research/moves.py:117-120 [DERIVED].
**is_repeat** — out: `bool(rows) and len(rows & seen) >= REPEAT_SHARE * len(rows)` — shared/polymath_shared/deep_research/moves.py:126-127 [DERIVED].
**concentration_anchors** — out: unique docs, first-citation order, only when `1..CONCENTRATION_DOCS` and no blank id; else `()` — shared/polymath_shared/deep_research/moves.py:133-136 [DERIVED].
**is_one_sided** — out: `len(learning_moves) >= ONE_SIDED_LEARNINGS and INVERSE not in learning_moves and (evaluative or intent in ONE_SIDED_INTENTS)` — shared/polymath_shared/deep_research/moves.py:141-142 [DERIVED].

## effect surface
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty); "Pure: the route (DR2) supplies retrieval, the LLM lane, the relevance gate" — shared/polymath_shared/deep_research/__init__.py:5 [DERIVED].
- No network, files, subprocesses, clock, or env flags: "no I/O, no model call, no clock" — shared/polymath_shared/deep_research/moves.py:9 [DERIVED].
- One runtime import: `from polymath_shared.query_intent import classify_intent`, executed lazily inside `question_intent` — shared/polymath_shared/deep_research/moves.py:52 [DERIVED].

## invariants
INVARIANT: sum(allocate(weights, n)) == n for n > 0 — shared/polymath_shared/deep_research/moves.py:71, 83 [DERIVED]
  fails-if: a plan's n slots get under/over-filled.
INVARIANT: len(allocate(weights, n)) == len(weights) — shared/polymath_shared/deep_research/moves.py:73-83 [DERIVED]
  fails-if: quota misaligns with MOVES indices used by with_inverse/child_quota.
INVARIANT: INTENT_WEIGHTS and CHILD_WEIGHTS tuple layout == (broad, deep, adjacent, inverse) == MOVES order — shared/polymath_shared/deep_research/moves.py:19, 21-33 [DERIVED]
  fails-if: reordering MOVES silently remaps every quota.
INVARIANT: root_quota(intent, n, evaluative=True) inverse slot >= 1 — shared/polymath_shared/deep_research/moves.py:108-111, 100-105 [DERIVED]
  fails-if: judgement questions plan no inverse search (the DR7f regression, moves.py:39).
INVARIANT: is_repeat threshold == REPEAT_SHARE * len(rows), REPEAT_SHARE = 0.5 — shared/polymath_shared/deep_research/moves.py:35, 127 [DERIVED]
  fails-if: deep→adjacent slot shift (moves.py:118-120) fires too early or never.
INVARIANT: concentration_anchors result length is 1..2 or exactly 0 — shared/polymath_shared/deep_research/moves.py:36, 133-136 [DERIVED]
  fails-if: deep queries anchor on a too-wide or unknown-spread document set.
INVARIANT: is_one_sided requires len(learning_moves) >= 3 and INVERSE not in learning_moves — shared/polymath_shared/deep_research/moves.py:37, 141-142 [DERIVED]
  fails-if: inverse correction injected when evidence is already balanced.

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/network/db/env ("Pure and deterministic: no I/O, no model call, no clock", shared/polymath_shared/deep_research/moves.py:9); exact `Fraction` arithmetic so the same weights always give the same split (moves.py:72); the classifier is regex, no LLM (moves.py:9-10).
idempotency: SAFE — pure functions, no module-level mutable state; `seen` is only read (shared/polymath_shared/deep_research/moves.py:124-127).

## failure behaviour
No try/except in either file; exceptions propagate to the importer — shared/polymath_shared/deep_research/moves.py:1-142 [DERIVED].
Graceful fallbacks instead of errors: unknown intent → `"EXPLORATORY"` (moves.py:54); unknown `parent_move` → `CHILD_WEIGHTS[DEEP]` (moves.py:117); `n <= 0` → zero quota (moves.py:74-75); blank citation doc id → no anchors (moves.py:134).

## dumb-code flags
- `DRY_LEVELS = 2` defined but never referenced anywhere in moves.py — consumer is outside this file — shared/polymath_shared/deep_research/moves.py:38 [DERIVED].
- Evaluative word list duplicated: once in the `_EVALUATIVE` regex, once in the `is_evaluative` docstring — drift risk — shared/polymath_shared/deep_research/moves.py:41-44, 58-61 [DERIVED].
- `"EXPLORATORY"` literal is the fallback in two separate places — shared/polymath_shared/deep_research/moves.py:54, 110 [DERIVED].
- `CHILD_WEIGHTS[BROAD]` and `CHILD_WEIGHTS[DEEP]` are identical tuples `(0, 1, 0, 0)` — the broad/deep distinction is dead in this table — shared/polymath_shared/deep_research/moves.py:33 [DERIVED].
- Tie-breaking is positional magic: allocate sorts by `(-(remainder), i)` (MOVES order), with_inverse by `(q[j], j)` (later move wins) — shared/polymath_shared/deep_research/moves.py:81, 102 [DERIVED].
- Magic weights: 10 hardcoded intent tuples — shared/polymath_shared/deep_research/moves.py:22-29 [DERIVED].

## refactor notes
- MOVES order is positional: `_INVERSE`/`_DEEP`/`_ADJACENT` indices and every weights tuple depend on it — shared/polymath_shared/deep_research/moves.py:19, 45-47 [DERIVED].
- The lazy import in `question_intent` exists so "a moves-off run never loads the classifier"; hoisting it to module scope breaks that property — shared/polymath_shared/deep_research/moves.py:51-52 [DERIVED].
- Package re-export line and `__all__` must stay in sync; importers include orchestrator/orchestrator/api/deep_research.py and sibling engine/evidence/prompts — shared/polymath_shared/deep_research/__init__.py:40, 50-56 (FACTS.importers) [DERIVED].
- New intent keys need an `INTENT_WEIGHTS` entry or they silently degrade to the EXPLORATORY mix — shared/polymath_shared/deep_research/moves.py:53-54, 110 [DERIVED].
- Tuning constants `REPEAT_SHARE`, `CONCENTRATION_DOCS`, `ONE_SIDED_LEARNINGS`, `DRY_LEVELS` change engine quota behaviour module-wide — shared/polymath_shared/deep_research/moves.py:35-38 [DERIVED].

## VERIFY
```verify
grep -Fq 'MOVES = ("broad", "deep", "adjacent", "inverse")' shared/polymath_shared/deep_research/moves.py
grep -Fq 'REPEAT_SHARE = 0.5' shared/polymath_shared/deep_research/moves.py
grep -Fq 'ONE_SIDED_LEARNINGS = 3' shared/polymath_shared/deep_research/moves.py
grep -Fq 'DRY_LEVELS = 2' shared/polymath_shared/deep_research/moves.py
grep -Fq 'from polymath_shared.query_intent import classify_intent' shared/polymath_shared/deep_research/moves.py
grep -Fq 'from .moves import MOVES, allocate, is_evaluative, question_intent' shared/polymath_shared/deep_research/__init__.py
grep -Eq 'def (question_intent|is_evaluative|allocate|with_inverse|root_quota|child_quota|is_repeat|concentration_anchors|is_one_sided)' shared/polymath_shared/deep_research/moves.py
```
