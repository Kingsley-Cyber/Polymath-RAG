# unit: shared/polymath_shared/adapter/research_gaps.py
anchor: shared/polymath_shared/adapter/research_gaps.py:1-180

## purpose
Pure, deterministic per-hypothesis research-gap harvesting (restoration reference §9.1 / §9.2) for the adapter layer. Before this module only a step's top-level `knowledge_gaps` reached Trail's `gaps.compile`; `harvest` gathers ledger, step, agent `open_gaps`, bridge and Trail gate gaps without duplication, keeps or mints a stable id, and refuses a gap no live hypothesis owns — shared/polymath_shared/adapter/research_gaps.py:1-17 [DERIVED]. Projection onto Trail's closed `ResearchKnowledgeGapV1` wire (`trail_gap`, `wire_gap`) and submit-time validation (`unowned_gap_errors`, `gap_wire_errors`) live here too — shared/polymath_shared/adapter/research_gaps.py:120-179 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `gap_id` | def | `(hypothesis_id: str, origin: str, question: str) -> str` | shared/polymath_shared/adapter/research_gaps.py:41-43 | — |
| `harvest` | def | `(current, outputs, *, order=(), default_role="behavior") -> dict` | shared/polymath_shared/adapter/research_gaps.py:54-117 | service.py, adapter_step_worker.py |
| `trail_gap` | def | `(gap) -> dict` | shared/polymath_shared/adapter/research_gaps.py:120-122 | service.py, adapter_step_worker.py |
| `wire_gap` | def | `(gap) -> dict` | shared/polymath_shared/adapter/research_gaps.py:125-132 | service.py, adapter_step_worker.py |
| `trail_gap_payload` | def | `(semantics) -> dict \| None` | shared/polymath_shared/adapter/research_gaps.py:135-142 | service.py, adapter_step_worker.py |
| `unowned_gap_errors` | def | `(payload, live_hypothesis_ids) -> list[str]` | shared/polymath_shared/adapter/research_gaps.py:145-162 | service.py, adapter_step_worker.py |
| `gap_wire_errors` | def | `(payload) -> list[str]` | shared/polymath_shared/adapter/research_gaps.py:165-179 | service.py, adapter_step_worker.py |

Importers are module-level only (FACTS.importers: `shared/polymath_shared/adapter/service.py`, `workers/workers/adapter_step_worker.py`); per-symbol attribution is not in FACTS. Private helpers: `_norm` :37-38, `_is_trail_output` :46-47, `_ordered` :50-51.

## contracts
`harvest` — shared/polymath_shared/adapter/research_gaps.py:54-117
- in: `current` = hypothesis_id -> state Mapping (`status`, `knowledge_gaps`); `outputs` = step name -> output Mapping; kw `order` default `()`; kw `default_role` default `"behavior"` — :54-55 [DERIVED]
- out: keys `knowledge_gaps`, `open_gaps`, `refused`, `dropped_over_cap`, `closed_not_reoffered` — :116-117 [DERIVED]; each kept gap = `{gap_id, hypothesis_id, question, evidence_role, origin}` — :56-57, :86-87 [DERIVED]
- pre: ledger gaps kept only when `g.get("status", "open") == "open"` — :93 [DERIVED]; live = status not in `ABSORBED_STATUSES` — :58 [DERIVED]
- post: first `(hypothesis_id, _norm(question))` wins; buckets capped at `MAX_GAPS` — :79-84, :116 [DERIVED]

`gap_id` — :41-43
- out: `f"gap_{str(hypothesis_id)[4:12]}_{origin[0]}{sha256(_norm(question)).hexdigest()[:8]}"` — :43 [DERIVED]; stable across rounds for the same triple — :42 [DERIVED]

`trail_gap` — :120-122
- out: exactly the keys of `TRAIL_GAP_FIELDS` — :122 [DERIVED]

`wire_gap` — :125-132
- out: `TRAIL_GAP_FIELDS` keys whose value is not `None`; `question` truncated to `QUESTION_MAX` — :129-131 [DERIVED]

`trail_gap_payload` — :135-142
- in: `semantics` Mapping or None; reads key `"research_gaps"` — :138 [DERIVED]
- out: `None` when absent/not a Mapping (caller keeps previous behaviour); else `{"knowledge_gaps": [...], "open_gaps": [...]}` of `trail_gap` projections — :139-142 [DERIVED]

`unowned_gap_errors` — :145-162
- out: message strings for top-level `knowledge_gaps`/`open_gaps` entries whose `hypothesis_id` is missing or not live; non-Mapping entries skipped — :153-161 [DERIVED]

`gap_wire_errors` — :165-179
- out: `GAP_ROLE_INVALID` messages when `evidence_role` is present and fails `_ROLE.match`; `None` role passes (harvest default applies) — :175-177 [DERIVED]

## effect surface
- Postgres: none — FACTS `tables_read: []`, `tables_written: []` [DERIVED]
- Qdrant / files / network / subprocess / env flags: none in SOURCE; only `hashlib`, `re`, `typing` and sibling `.contracts` / `.hypotheses` imports — shared/polymath_shared/adapter/research_gaps.py:20-25 [DERIVED]

## invariants
INVARIANT: len(knowledge_gaps) <= `MAX_GAPS` = 100 and len(open_gaps) <= 100, overflow only counted in `dropped_over_cap` — shared/polymath_shared/adapter/research_gaps.py:27,116-117 [DERIVED]
  fails-if: gaps beyond 100 per bucket are silently dropped; Trail never sees them and the count is the only trace.
INVARIANT: wire `question` length <= `QUESTION_MAX` = 2000 < Trail wire 4096 — shared/polymath_shared/adapter/research_gaps.py:31-32,86,131 [DERIVED]
  fails-if: a longer question would pass Trail but break the harness action bound (`harness_action.evidence_gaps[].question maxLength`) — :31 [DERIVED]
INVARIANT: `trail_gap`/`wire_gap` keys == `TRAIL_GAP_FIELDS` == `("gap_id", "hypothesis_id", "question", "evidence_role")`; `origin` never crosses the wire — shared/polymath_shared/adapter/research_gaps.py:16,30,122,129 [DERIVED]
  fails-if: an extra key (agent `note`, `priority`, …) hits Trail's `extra="forbid"` wire and the run ends `TRAIL_REFUSED` — :128 [DERIVED]
INVARIANT: gap_id = `"gap_" + hypothesis_id[4:12] + "_" + origin[0] + sha256(_norm(question))[:8]`, stable across rounds — shared/polymath_shared/adapter/research_gaps.py:42-43 [DERIVED]
  fails-if: per-round ids (`gap_0`, `gap_1`) return and cross-round gap tracking breaks — :42 [DERIVED]
INVARIANT: dedup key = `(str(hypothesis_id), _norm(question))`, first occurrence wins; offer order = ledger → step → agent_open → bridge → trail_gate — shared/polymath_shared/adapter/research_gaps.py:79-84,89-115 [DERIVED]
  fails-if: duplicate gaps reach Trail; a later origin's differing `evidence_role` is silently ignored.
INVARIANT: a ledger question with `status == "closed"` never re-enters via ledger/step/agent_open/bridge; only `GATE_ORIGIN` may re-offer it — shared/polymath_shared/adapter/research_gaps.py:63-66,78-80 [DERIVED] (gap A-05)
  fails-if: the closed question resurrects under a new origin-based id.
INVARIANT: origins `("ledger", "step", "agent_open", "bridge")` → `knowledge_gaps`; `"trail_gate"` → `open_gaps` — shared/polymath_shared/adapter/research_gaps.py:28-29,116 [DERIVED]
  fails-if: the query compiler can no longer tell semantic questions from governance gate text — :16-17 [DERIVED]
INVARIANT: only the NEWEST Trail output's `open_gaps` and the newest `bridges` list are harvested (`reversed(outs)` first match) — shared/polymath_shared/adapter/research_gaps.py:105,112 [DERIVED]
INVARIANT: Trail output detection = `"trail_operation_id" in out or "operation_kind" in out` — shared/polymath_shared/adapter/research_gaps.py:47 [DERIVED]
INVARIANT: `evidence_role` defaults to `"behavior"` when falsy — shared/polymath_shared/adapter/research_gaps.py:55,86 [DERIVED]
INVARIANT: refused entry question snippet truncated to 300 chars — shared/polymath_shared/adapter/research_gaps.py:74,77 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/network/db/env in SOURCE; only `hashlib.sha256` over `_norm(question)` — shared/polymath_shared/adapter/research_gaps.py:20-25,43 [DERIVED]; iteration order fixed by input dicts plus `order`/`_ordered` — :50-51 [DERIVED]
idempotency: SAFE — pure functions, no writes; same inputs give equal dicts, and `gap_id` is stable across rounds by design — :42,54-117 [DERIVED]

## failure behaviour
- `harvest` never raises on bad gaps; it refuses: `{"code": "GAP_OWNER_MISSING", ...}` (no `hypothesis_id`) and `{"code": "GAP_OWNER_NOT_LIVE", ...}` (owner absorbed) — shared/polymath_shared/adapter/research_gaps.py:34,74,77 [DERIVED]
- An absorbed hypothesis's own ledger gaps are skipped silently, "not a refusal" — shared/polymath_shared/adapter/research_gaps.py:89-90 [DERIVED]
- `trail_gap` raises `KeyError` on a missing field — shared/polymath_shared/adapter/research_gaps.py:122 [INFERRED] (bare `gap[k]` dict access)
- `trail_gap_payload` returns `None` (no exception) when `research_gaps` is absent — shared/polymath_shared/adapter/research_gaps.py:139-140 [DERIVED]
- Validators return typed strings, never raise: `GAP_OWNER_MISSING` :159, `GAP_OWNER_NOT_LIVE` :161, `GAP_ROLE_INVALID` :176-178 [DERIVED]
- Historical failure modes: agent keys crossing the wire ended the run `TRAIL_REFUSED` (bug hunt B-21/B-26) — :128 [DERIVED]; an invalid forwarded `evidence_role` ended the run at the next Trail step (B-22/B-26) — :167-168 [DERIVED]

## dumb-code flags
- Magic literal `300` for refused-question truncation, used twice, unrelated to `QUESTION_MAX` — shared/polymath_shared/adapter/research_gaps.py:74,77 [DERIVED]
- `SEMANTIC_ORIGINS` defined but never referenced in this module; `harvest` hardcodes `"ledger"`/`"step"`/`"agent_open"`/`"bridge"` at the call sites — shared/polymath_shared/adapter/research_gaps.py:28,94,99,104,110 [DERIVED]
- Role shape stated twice: docstring regex `^[a-z][a-z0-9_]{1,40}$` vs compiled `EVIDENCE_ROLE_PATTERN` from contracts — shared/polymath_shared/adapter/research_gaps.py:33,167 [DERIVED]
- `"behavior"` appears as the `default_role` default and again inside the `GAP_ROLE_INVALID` example text — shared/polymath_shared/adapter/research_gaps.py:55,178 [DERIVED]
- `QUESTION_MAX` = 2000 vs Trail wire 4096 — deliberate mismatch documented only in a comment — shared/polymath_shared/adapter/research_gaps.py:31-32 [DERIVED]
- `not_reoffered = [0]` single-element list as a mutable closure counter — shared/polymath_shared/adapter/research_gaps.py:67,81,117 [DERIVED]
- Dense precedence-dependent expression in `unowned_gap_errors`: `payload.get(key) or [] if isinstance(payload.get(key), list) else []` — shared/polymath_shared/adapter/research_gaps.py:154 [DERIVED]
- `_ordered` silently drops non-Mapping outputs; `_norm` maps `None`/empty to `""` — shared/polymath_shared/adapter/research_gaps.py:38,51 [DERIVED]

## refactor notes
- `TRAIL_GAP_FIELDS` is the closed-wire contract for both `trail_gap` and `wire_gap`; Trail's `ResearchKnowledgeGapV1` is `extra="forbid"` — shared/polymath_shared/adapter/research_gaps.py:30,121,129. Any field change must match Trail's schema or the run ends `TRAIL_REFUSED` — :128.
- `gap_id` layout (slice `[4:12]`, `origin[0]`, `sha256[:8]`) is a persisted cross-round identity; changing it orphans existing gap ids — shared/polymath_shared/adapter/research_gaps.py:42-43.
- Importers `shared/polymath_shared/adapter/service.py` and `workers/workers/adapter_step_worker.py` (FACTS.importers) — any signature change to `harvest`/`trail_gap_payload` ripples to both.
- `EVIDENCE_ROLE_PATTERN` and `ABSORBED_STATUSES` come from `.contracts`/`.hypotheses` — shared/polymath_shared/adapter/research_gaps.py:24-25; the definition of "live" moves with `ABSORBED_STATUSES` — :58.
- The origin→bucket routing in `offer(..., bucket=...)` is the semantic/governance split the query compiler relies on; do not merge buckets — shared/polymath_shared/adapter/research_gaps.py:16-17,111-115.

## VERIFY
```verify
grep -Fq 'MAX_GAPS = 100' shared/polymath_shared/adapter/research_gaps.py
grep -Fq 'TRAIL_GAP_FIELDS = ("gap_id", "hypothesis_id", "question", "evidence_role")' shared/polymath_shared/adapter/research_gaps.py
grep -Fq 'default_role: str = "behavior"' shared/polymath_shared/adapter/research_gaps.py
grep -Fq 'gap_{str(hypothesis_id)[4:12]}_{origin[0]}' shared/polymath_shared/adapter/research_gaps.py
grep -Fq 'GAP_ROLE_INVALID' shared/polymath_shared/adapter/research_gaps.py
test "$(grep -c -F 'REFUSAL_NOT_LIVE' shared/polymath_shared/adapter/research_gaps.py)" -ge 3
! grep -Fq 'import random' shared/polymath_shared/adapter/research_gaps.py
```
