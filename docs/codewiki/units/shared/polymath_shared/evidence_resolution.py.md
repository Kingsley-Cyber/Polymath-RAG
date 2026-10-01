# unit: shared/polymath_shared/evidence_resolution.py
anchor: shared/polymath_shared/evidence_resolution.py:1-195

## purpose
Implements `EVIDENCE-RESOLUTION-V1` (librarian checklist P10): after round-1 evidence is assembled, deterministically detect material gaps among the required claims and fire at most one targeted resolution query per round — bounded, observable, no LLM, no second RAG pipeline. Distinct from the pre-evidence aspect/Resolution-Lift pass, which expands query vocabulary before evidence exists. — shared/polymath_shared/evidence_resolution.py:1-19 [DERIVED]
Consumed by the orchestrator chat UI (module importer: `orchestrator/orchestrator/api/ui.py`). — FACTS.importers [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ClaimState` | class | `(claim_id: str, importance: float, evidence_state: str, next_information_need: str \| None = None)`; methods `__post_init__`, `is_gap` | shared/polymath_shared/evidence_resolution.py:51-65 | orchestrator/orchestrator/api/ui.py (module import) |
| `RetrievalState` | class | `(original_query: str, round: int = 1, ...)` | shared/polymath_shared/evidence_resolution.py:69-81 | orchestrator/orchestrator/api/ui.py (module import) |
| `ResolutionDecision` | class | `(should_resolve: bool, reason: str, claim: ClaimState \| None = None, query: CompiledQuery \| None = None)` | shared/polymath_shared/evidence_resolution.py:85-90 | orchestrator/orchestrator/api/ui.py (module import) |
| `assess_claims` | def | `(must_answer, evidence_texts, *, conflict_ids=(), importance_step=0.15) -> list[ClaimState]` | shared/polymath_shared/evidence_resolution.py:93-117 | orchestrator/orchestrator/api/ui.py (module import) |
| `plan_resolution_round` | def | `(state: RetrievalState, *, max_rounds=MAX_RESOLUTION_ROUNDS, importance_floor=IMPORTANCE_FLOOR) -> ResolutionDecision` | shared/polymath_shared/evidence_resolution.py:128-141 | orchestrator/orchestrator/api/ui.py (module import) |
| `advance_state` | def | `(state, decision, *, new_evidence=(), new_docs=(), resolved_state="SUPPORTED") -> RetrievalState` | shared/polymath_shared/evidence_resolution.py:144-175 | orchestrator/orchestrator/api/ui.py (module import) |
| `resolution_receipt` | def | `(state, decision) -> dict` | shared/polymath_shared/evidence_resolution.py:178-194 | orchestrator/orchestrator/api/ui.py (module import) |

Private helpers: `_content_words` (:46-47), `_resolution_query` (:120-125). [DERIVED]

## contracts

### `assess_claims` — shared/polymath_shared/evidence_resolution.py:93-117
- in: ordered `must_answer` dims, assembled `evidence_texts`, optional `conflict_ids`, `importance_step=0.15`. [DERIVED]
- out: one `ClaimState` per non-empty dim; `claim_id=f"claim_{i}"`; `importance = max(0.3, 1.0 - importance_step * i)`. — :105-107 [DERIVED]
- state rule: `cid in conflict_ids or dim in conflict_ids` → `CONFLICTING`; else lexical coverage = `len(words & evidence_words) / len(words)`: `>= 0.8` → `SUPPORTED`, `>= 0.34` → `PARTIAL`, else `UNSUPPORTED`. — :108-114 [DERIVED]
- pre: `None`/empty tolerated (`must_answer or []`, `evidence_texts or ()`). — :101-105 [DERIVED]
- post: gap states carry `next_information_need=dim`; `SUPPORTED` carries `None`. — :115-116 [DERIVED]
- explicitly a lexical gap *signal*, not a semantic support judgment. — :97-99 [DERIVED]

### `plan_resolution_round` — shared/polymath_shared/evidence_resolution.py:128-141
- in: `RetrievalState`; keyword-only `max_rounds` (module default `2`), `importance_floor` (module default `0.5`). — :128-129, :35-36 [DERIVED]
- out (no-fire): `ResolutionDecision(False, reason="stop:max_rounds({round}>={max_rounds})")` when `state.round >= max_rounds`; `False, "stop:no_material_gap"` when no gap clears `importance >= importance_floor`. — :133-137 [DERIVED]
- out (fire): single top gap, sorted by `(-importance, _SEVERITY[evidence_state], claim_id)`, index `[0]`; `reason=f"gap:{claim_id}:{evidence_state}"`. — :138-141 [DERIVED]
- query: built only from state's unresolved needs via `_resolution_query`: `CompiledQuery(id=f"r{round_no}_{claim.claim_id}", type="MECHANISM", query=need, weight=0.8, role="resolution", target=next_information_need, derived_from=claim_id, origin="EVIDENCE_GAP")`. — :120-125 [DERIVED]

### `advance_state` — shared/polymath_shared/evidence_resolution.py:144-175
- in: `state`, `decision`, `new_evidence=()`, `new_docs=()`, `resolved_state="SUPPORTED"`. — :144-145 [DERIVED]
- out: NEW `RetrievalState` with `round = state.round + 1`, evidence/docs appended, history entry `{"round", "query", "claim", "reason", "added_evidence", "added_docs"}` appended. — :162-175 [DERIVED]
- post: resolved claim moved to `answered_claims` iff `resolved_state == "SUPPORTED"`; otherwise re-tagged with `resolved_state` and kept unresolved. — :154-159 [DERIVED]
- post: `original_query`, `discovered_parents`, `discovered_concepts`, `unexplored_bridges` passed through unchanged (q0 immutable). — :168-174 [DERIVED]
- invalid `resolved_state` silently coerced to `"SUPPORTED"`. — :149-150 [DERIVED]

### `resolution_receipt` — shared/polymath_shared/evidence_resolution.py:178-194
- out: dict `{"contract": "resolution-state-v1", "round", "max_rounds": MAX_RESOLUTION_ROUNDS, "hop_2_fired", "reason", "resolution_query", "resolution_claim", "unresolved": [{claim_id, importance (round 3), evidence_state}], "history"}`; `unresolved` lists only gap-state claims. — :180-193 [DERIVED]

## effect surface
- Postgres tables: none read, none written (FACTS `tables_read=[]`, `tables_written=[]`). [DERIVED]
- Qdrant / files / network / subprocess: none; "no LLM, no I/O". — shared/polymath_shared/evidence_resolution.py:18-19 [DERIVED]
- Import: `polymath_shared.chat_plan.CompiledQuery`. — :27, FACTS.imports [DERIVED]
- Env flags read once at import:

| flag | default | anchor |
|---|---|---|
| `POLYMATH_CHAT_RESOLUTION_MAX_ROUNDS` | `2` | shared/polymath_shared/evidence_resolution.py:35 |
| `POLYMATH_CHAT_RESOLUTION_IMPORTANCE_FLOOR` | `0.5` | shared/polymath_shared/evidence_resolution.py:36 |
| `POLYMATH_CHAT_RESOLUTION_SUPPORT_COVERAGE` | `0.8` | shared/polymath_shared/evidence_resolution.py:37 |
| `POLYMATH_CHAT_RESOLUTION_PARTIAL_COVERAGE` | `0.34` | shared/polymath_shared/evidence_resolution.py:38 |

## invariants
INVARIANT: `_PARTIAL_COVERAGE` (0.34) `<` `_SUPPORT_COVERAGE` (0.8) — shared/polymath_shared/evidence_resolution.py:37-38 [DERIVED]
  fails-if: thresholds invert; every partially-covered claim reads SUPPORTED and gaps vanish.
INVARIANT: gap severity order `UNSUPPORTED`(0) `<` `CONFLICTING`(1) `<` `PARTIAL`(2) — shared/polymath_shared/evidence_resolution.py:33 [DERIVED]
  fails-if: tie-break resolves a shallower gap before a more severe one.
INVARIANT: `RetrievalState.round` starts at 1 and default `MAX_RESOLUTION_ROUNDS` = 2, stop at `round >= max_rounds` → at most 1 resolution hop per turn — shared/polymath_shared/evidence_resolution.py:35,74,133 [DERIVED]
  fails-if: extra hops fire; bounded-turn contract (docstring :16) breaks.
INVARIANT: default `importance = max(0.3, 1.0 - 0.15*i)` vs `importance_floor` 0.5 → only dims i ≤ 3 (importance 1.0/0.85/0.7/0.55) can ever fire; i=4 → 0.4 < 0.5 — shared/polymath_shared/evidence_resolution.py:107,135 [INFERRED: arithmetic on the two literals]
  fails-if: raising the floor or lowering `importance_step` silently zeroes resolution for the tail of a long checklist.
INVARIANT: coverage for a dim with zero content words = 1.0 → auto `SUPPORTED` — shared/polymath_shared/evidence_resolution.py:112 [DERIVED]
  fails-if: a stop-word-only "need" is marked answered without any evidence.
INVARIANT: `advance_state` returns `round = state.round + 1` and unchanged `original_query` — shared/polymath_shared/evidence_resolution.py:168-169 [DERIVED]
  fails-if: q0 mutates or round regresses; unbounded/impure rounds.

## determinism & idempotency
determinism: DETERMINISTIC — pure lexical/regex computation, "no LLM, no I/O" (shared/polymath_shared/evidence_resolution.py:18-19); only env dependence is the 4 thresholds read once at import (:35-38). [DERIVED]
idempotency: SAFE — all functions are pure; `advance_state` builds and returns a new `RetrievalState` (tuple fields), never mutates inputs (:144-175). [DERIVED]

## failure behaviour
- No `try`/`except` and no raised error codes anywhere in the file; nothing is thrown to callers. [DERIVED, absence in SOURCE]
- Invalid `evidence_state` string silently becomes `"UNSUPPORTED"` — shared/polymath_shared/evidence_resolution.py:60-61. [DERIVED]
- Invalid `resolved_state` string silently becomes `"SUPPORTED"` — shared/polymath_shared/evidence_resolution.py:149-150. Caller then sees the claim moved to `answered_claims`. [DERIVED]
- `importance` clamped to `[0.0, 1.0]` — shared/polymath_shared/evidence_resolution.py:59. [DERIVED]
- `decision.claim is None` in `advance_state`: all needs pass through unchanged but a history entry is still appended — shared/polymath_shared/evidence_resolution.py:151-167. [DERIVED]

## dumb-code flags
- `advance_state` coerces any bad `resolved_state` to `"SUPPORTED"` — a typo'd state string marks the claim answered. — shared/polymath_shared/evidence_resolution.py:149-150 [DERIVED]
- `resolution_receipt` reports the module global `MAX_RESOLUTION_ROUNDS`, not the `max_rounds` kwarg `plan_resolution_round` was actually called with — mismatch when a caller overrides it. — shared/polymath_shared/evidence_resolution.py:182 vs :128 [DERIVED]
- Hardcoded `CompiledQuery` literals: `type="MECHANISM"`, `weight=0.8`, `role="resolution"`, `origin="EVIDENCE_GAP"` (tagged `# E7`). — :123-125 [DERIVED]
- Duplicated conflict matching (`cid in conflict_ids or dim in conflict_ids`) — callers must know to pass either form. — :108 [DERIVED]
- `retrieval_history: tuple[dict, ...] = field(default_factory=tuple)` — `default_factory` redundant for an immutable `()` default. — :81 [DERIVED]
- Coverage thresholds `0.8`/`0.34` and floor `0.3`/step `0.15` are magic numbers only tunable via env (two of them) or not at all (the latter two). — :37-38, :93, :107 [DERIVED]
- FACTS lists `_SEVERITY` as `{"CONFLICTING": 1, "PARTIAL": 2, "UNSUPPORTED": 0}` but SOURCE line 33 writes `{"UNSUPPORTED": 0, "CONFLICTING": 1, "PARTIAL": 2}` — FACTS key order does not match the file. — :33 vs FACTS.constants [DERIVED]

## refactor notes
- Importer `orchestrator/orchestrator/api/ui.py` binds to the public names (`assess_claims`, `plan_resolution_round`, `advance_state`, `resolution_receipt`, the three dataclasses); renaming any of them breaks that module. — FACTS.importers [DERIVED]
- Receipt keys are a versioned wire contract (`"contract": "resolution-state-v1"`, `hop_2_fired`, ...) consumed by P11 — shared/polymath_shared/evidence_resolution.py:178,181-193; key renames need a contract bump. [DERIVED]
- `CompiledQuery` kwargs `role="resolution"` / `origin="EVIDENCE_GAP"` are downstream contract literals; changing them changes engine-side routing. — :124-125 [DERIVED]
- Env flag names (:35-38) are deployment-facing and read at import time; renaming or re-defaulting them silently shifts stop/floor/coverage behavior for every process. [DERIVED]
- `plan_resolution_round` defaults bind module constants at def time; kwargs override planning but not the receipt — see dumb-code flag. — :128-129, :182 [DERIVED]

## VERIFY
```verify
grep -Fq 'EVIDENCE-RESOLUTION-V1' shared/polymath_shared/evidence_resolution.py
grep -Fq 'os.environ.get("POLYMATH_CHAT_RESOLUTION_MAX_ROUNDS", "2")' shared/polymath_shared/evidence_resolution.py
grep -Fq '{"UNSUPPORTED": 0, "CONFLICTING": 1, "PARTIAL": 2}' shared/polymath_shared/evidence_resolution.py
grep -Fq 'stop:no_material_gap' shared/polymath_shared/evidence_resolution.py
grep -Fq 'origin="EVIDENCE_GAP"' shared/polymath_shared/evidence_resolution.py
grep -Fq '"contract": "resolution-state-v1"' shared/polymath_shared/evidence_resolution.py
test "$(grep -c -F 'ClaimState' shared/polymath_shared/evidence_resolution.py)" -ge 3
```
