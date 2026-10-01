# unit: shared/polymath_shared/lane_liveness.py
anchor: shared/polymath_shared/lane_liveness.py:1-226

## purpose
Conditional liveness monitor for promoted retrieval lanes: classifies each lane per production trace as LIVE / SUSPECT / NO_OPPORTUNITY / DISABLED to catch "present, unit-tested, configured — and delivered nothing" features (module docstring lists six such incidents) — shared/polymath_shared/lane_liveness.py:1-41 [DERIVED].
Also classifies ingestion lanes from durable counters with two extra statuses, LIVE_BUT_CAPPED and UNOBSERVABLE — shared/polymath_shared/lane_liveness.py:191-197 [DERIVED].
Module is imported by `orchestrator/orchestrator/api/fast.py` and `orchestrator/orchestrator/api/health.py` — FACTS.importers [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| Lane | class | frozen dataclass: name: str, rationale: str, enabled/opportunity/contributed: Callable[[dict], bool] | shared/polymath_shared/lane_liveness.py:55-64 | — |
| LANES | tuple[Lane, ...] | 9 lanes (see below) | shared/polymath_shared/lane_liveness.py:77-158 | — |
| LANES_BY_NAME | dict | {lane.name: lane} | shared/polymath_shared/lane_liveness.py:160 | — |
| evaluate_lane | def | (lane: Lane, trace: dict) -> dict | shared/polymath_shared/lane_liveness.py:163-173 | — |
| evaluate | def | (trace: dict) -> dict | shared/polymath_shared/lane_liveness.py:176-188 | — |
| semantic_lane_status | def | (*, opportunities: int \| None, accepted: int, capped_documents: int = 0, documents: int = 0) -> str | shared/polymath_shared/lane_liveness.py:200-225 | — |
| CONTRACT | const | "production-reality-v1" | shared/polymath_shared/lane_liveness.py:47 | — |
| STATUS_LIVE / STATUS_SUSPECT / STATUS_NO_OPPORTUNITY / STATUS_DISABLED | const | "LIVE" / "SUSPECT" / "NO_OPPORTUNITY" / "DISABLED" | shared/polymath_shared/lane_liveness.py:49-52 | — |
| STATUS_CAPPED / STATUS_UNOBSERVABLE | const | "LIVE_BUT_CAPPED" / "UNOBSERVABLE" | shared/polymath_shared/lane_liveness.py:196-197 | — |

Per-symbol usage inside the two importers is not visible in FACTS; only module-level import is.

## contracts
**evaluate(trace) -> dict** — shared/polymath_shared/lane_liveness.py:176-188
- in: trace dict; predicates read only these keys, all via `.get` with `or` fallbacks: `lane_sizes` (keys "document_summary", "section_summary", "global_child", "child_lexical"), `rescue_reserved_slots`, `rescue_candidates`, `rescue_seated`, `rerank_enabled` (default `True`), `pre_g3_order`, `g3_scores`, `neighbor_expansion`, `post_g3_order`, `neighbors_added`, `demote_noisy_regions` (default `False`), `noisy_candidates`, `noisy_demoted`, `mode` (== "GRAPH"), `graph_seed_surfaces`, `graph_fact_count` — shared/polymath_shared/lane_liveness.py:77-158 [DERIVED]
- out: `{"contract": "production-reality-v1", "lanes": [9 dicts], "suspect": [names], "live": [names]}` — shared/polymath_shared/lane_liveness.py:183-187 [DERIVED]
- pre: none; missing keys coerce to 0/empty via `or 0` / `or {}` / `or []` — shared/polymath_shared/lane_liveness.py:67,129 [DERIVED]
- post: one result dict per LANES entry, each status one of the four retrieval statuses — shared/polymath_shared/lane_liveness.py:182 [DERIVED]

**evaluate_lane(lane, trace) -> dict** — shared/polymath_shared/lane_liveness.py:163-173
- precedence: not enabled → DISABLED; else no opportunity → NO_OPPORTUNITY; else contributed → LIVE; else SUSPECT — shared/polymath_shared/lane_liveness.py:165-172 [DERIVED]
- out: `{"lane": name, "status": status, "rationale": rationale}` — shared/polymath_shared/lane_liveness.py:173 [DERIVED]

**semantic_lane_status(*, opportunities, accepted, capped_documents=0, documents=0) -> str** — shared/polymath_shared/lane_liveness.py:200-225
- keyword-only parameters — shared/polymath_shared/lane_liveness.py:200 [DERIVED]
- precedence: opportunities is None → "UNOBSERVABLE"; opportunities <= 0 → "NO_OPPORTUNITY"; accepted <= 0 → "SUSPECT"; `documents and capped_documents >= documents` → "LIVE_BUT_CAPPED"; else "LIVE" — shared/polymath_shared/lane_liveness.py:217-225 [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS.tables_read and tables_written both empty) [DERIVED]
- Files, Qdrant, network, subprocess, env flags: none — module has only `dataclasses`/`typing` imports and pure computation over the passed trace dict — shared/polymath_shared/lane_liveness.py:43-45 [DERIVED]

## invariants
INVARIANT: len(LANES) == 9 — shared/polymath_shared/lane_liveness.py:77-158 [DERIVED]
  fails-if: a lane removed from LANES silently disappears from evaluate() monitoring.
INVARIANT: status check order DISABLED > NO_OPPORTUNITY > LIVE > SUSPECT — shared/polymath_shared/lane_liveness.py:165-172 [DERIVED]
  fails-if: reordered checks misreport disabled lanes as SUSPECT.
INVARIANT: reranker opportunity ⇔ len(pre_g3_order) > 1 — shared/polymath_shared/lane_liveness.py:129 [DERIVED]
  fails-if: single-candidate queries get classified as dead-feature signals.
INVARIANT: graph_hop1 enabled ⇔ trace["mode"] == "GRAPH" — shared/polymath_shared/lane_liveness.py:154 [DERIVED]
  fails-if: non-GRAPH traces produce spurious SUSPECT verdicts.
INVARIANT: rescue opportunity ⇔ global_child lane size > 0 AND rescue_candidates > 0 — shared/polymath_shared/lane_liveness.py:110-111 [DERIVED]
  fails-if: rescue flagged dead on traces where it legitimately had no candidates.
INVARIANT: UNOBSERVABLE ⇔ opportunities is None (0 is NO_OPPORTUNITY, never UNOBSERVABLE) — shared/polymath_shared/lane_liveness.py:208,217-218 [DERIVED]
  fails-if: uninstrumented lane misread as correctly-silent, hiding a dead lane.
INVARIANT: "LIVE_BUT_CAPPED" reachable only when documents != 0 and capped_documents >= documents — shared/polymath_shared/lane_liveness.py:223-224 [DERIVED]
  fails-if: with the default documents=0, a fully-capped lane reports plain LIVE.

## determinism & idempotency
determinism: DETERMINISTIC (pure functions of the trace dict; no clock/random/uuid/db/env anywhere in the module — shared/polymath_shared/lane_liveness.py:43-225) [DERIVED]
idempotency: SAFE (no writes or side effects; same trace in, equal verdict out) [DERIVED]

## failure behaviour
- No `try`/`except` and no `raise` in the module — shared/polymath_shared/lane_liveness.py:1-225 [DERIVED]
- Missing trace keys never raise: every predicate uses `.get` with `or` coercion (e.g. `int((trace.get("lane_sizes") or {}).get(key) or 0)` — shared/polymath_shared/lane_liveness.py:67) [DERIVED]
- Consequence: an emitters' missing key (e.g. absent `g3_scores`) reads falsy and can flip a working lane to SUSPECT — shared/polymath_shared/lane_liveness.py:130 [INFERRED: contributed uses bool(t.get(...)) with no default]

## dumb-code flags
- `_arrivals(trace)` defined but referenced nowhere else in this file — shared/polymath_shared/lane_liveness.py:70-71 [DERIVED defined; INFERRED unused here, possibly imported elsewhere]
- lexical lane repeats the identical `"child_lexical" in (t.get("lane_sizes") or {})` test in both enabled and opportunity; the second copy is unreachable when false because evaluate_lane short-circuits on enabled — shared/polymath_shared/lane_liveness.py:119-120 [INFERRED redundancy]
- neighbor_expansion lane repeats its enabled condition `int(t.get("neighbor_expansion") or 0) > 0` inside opportunity, same short-circuit redundancy — shared/polymath_shared/lane_liveness.py:136-137 [INFERRED redundancy]
- Literal "child_lexical" duplicated 3× within one lane — shared/polymath_shared/lane_liveness.py:119-121 [DERIVED]
- Asymmetric defaults: `rerank_enabled` defaults `True` vs `demote_noisy_regions` defaults `False` — shared/polymath_shared/lane_liveness.py:128,146 [DERIVED]
- Trace key `"neighbor_expansion"` (setting) string-collides with lane name `"neighbor_expansion"` — shared/polymath_shared/lane_liveness.py:133,136-137 [DERIVED]
- Docstring cites the historical rescue failure "configured at 3 and delivering 0" as the motivating dead lane — shared/polymath_shared/lane_liveness.py:9-10,103-105 [DERIVED]

## refactor notes
- All trace-key strings are an implicit contract with whoever emits traces; renaming any key (e.g. `g3_scores`, `pre_g3_order`, `rescue_seated`) silently converts LIVE lanes to SUSPECT/NO_OPPORTUNITY. Blast radius: orchestrator/orchestrator/api/fast.py and orchestrator/orchestrator/api/health.py (FACTS.importers) [INFERRED]
- evaluate() emits `contract: "production-reality-v1"` and raw status strings; consumers comparing these literals break on any rename — shared/polymath_shared/lane_liveness.py:184,49-52 [DERIVED]
- Adding/removing a Lane changes the length of `lanes` and the name lists in `suspect`/`live` — shared/polymath_shared/lane_liveness.py:182-187 [DERIVED]
- semantic_lane_status is keyword-only; positional call sites fail loudly at the call — shared/polymath_shared/lane_liveness.py:200 [DERIVED]
- Lane predicates read "ONLY a production trace — the same dict the live routes already emit"; any refactor to mock-derived input breaks the design intent — shared/polymath_shared/lane_liveness.py:74-76 [DERIVED]

## VERIFY
```verify
grep -Fq 'CONTRACT = "production-reality-v1"' shared/polymath_shared/lane_liveness.py
grep -Fq 'STATUS_CAPPED = "LIVE_BUT_CAPPED"' shared/polymath_shared/lane_liveness.py
test "$(grep -c -F 'name="' shared/polymath_shared/lane_liveness.py)" -ge 9
grep -Fq 'enabled=lambda t: t.get("mode") == "GRAPH"' shared/polymath_shared/lane_liveness.py
grep -Eq 'def semantic_lane_status\(\*, opportunities' shared/polymath_shared/lane_liveness.py
! grep -Fq 'except' shared/polymath_shared/lane_liveness.py
```
