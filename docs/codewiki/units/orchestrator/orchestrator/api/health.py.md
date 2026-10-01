# unit: orchestrator/orchestrator/api/health.py
anchor: orchestrator/orchestrator/api/health.py:1-149
short form `health.py:NN` below = the full path above.

## purpose
FastAPI router exposing six read-only health endpoints: liveness `/health`, traffic readiness `/ready`, sidecar inventory `/sidecars`, per-corpus semantic completion `/semantic_readiness`, semantic-lane health `/health/semantic`, and pipeline stall detection `/health/pipeline`. Consumers are ops/autoheal (liveness-readiness split per ISSUES_REPORT §3.3) and operators checking lane/pipeline state. [DERIVED] — routes health.py:15-149, docstring health.py:1-6.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| router | APIRouter | module-level instance, 6 GET routes | health.py:11 | orchestrator/orchestrator/main.py |
| health | def, GET /health | () -> dict | health.py:15-16 | via router |
| ready | def, GET /ready | (request: Request) -> dict | health.py:20-26 | via router |
| semantic_readiness | def, GET /semantic_readiness | (corpus_id: str) -> dict | health.py:30-54 | via router |
| sidecars | def, GET /sidecars | (request: Request) -> dict | health.py:58-71 | via router |
| semantic_health | def, GET /health/semantic | (corpus_id: str \| None = None) -> dict | health.py:75-134 | via router |
| pipeline | def, GET /health/pipeline | () -> dict | health.py:138-149 | via router |

Only importer in FACTS: orchestrator/orchestrator/main.py.

## contracts

**health** — health.py:15-16
- out: `{"status": "ok"}` constant; no inputs, no side effects. [DERIVED]

**ready** — health.py:20-26
- in: reads `request.app.state.sidecars`; missing attribute treated as `{}`. health.py:21-24
- out: `{"ready": True, "sidecars": {name: s.is_ready()}}`; `"ready"` is literal `True` regardless of sidecar results. health.py:25-26

**semantic_readiness** — health.py:30-54
- pre: `require_corpus(corpus_id)` must pass (FRIENDS-ACCESS-V1 D5). health.py:41
- pre: `SELECT 1 FROM corpora WHERE corpus_id = %s` must return a row, else HTTPException 404 with `detail={"error_code": "QUERY_SCOPE_UNKNOWN", "message": f"corpus {corpus_id!r} not found"}`. health.py:44-53
- out: `semantic_completion(conn, corpus_id)`; shape owned by polymath_shared.semantic_readiness. health.py:54

**sidecars** — health.py:58-71
- in: reads `request.app.state.sidecars`; missing → `{}`. health.py:59-62
- out per name: `release` = `s.manifest.get("identity", {}).get("version")`, `model` = `...get("model")`, `base_url` = `s.base_url`, `ready` = `s.is_ready()`. health.py:63-70

**semantic_health** — health.py:75-134
- in: optional `corpus_id`; when set, lane query gets `WHERE corpus_id = %s` with scope `(corpus_id,)`, else `""`. health.py:88-89
- per-lane row (grouped from `knowledge_lane_attempts`): `status` = `semantic_lane_status(opportunities=..., accepted=..., capped_documents=..., documents=...)`, `opportunities`, `accepted`, `capture_ratio` = `round(acc / opps, 4)` (None iff opps == 0), `documents`, `capped_documents`, `last_attempt_at` = `str(last)` or None. health.py:108-119
- fact lane (assignment always overwrites any loop-produced `"fact"` key): `status` = `semantic_lane_status(opportunities=candidates, accepted=facts)`, `opportunities` = count(relation_candidates), `decisions` = count(fact_admission_decisions), `accepted` = count(facts), `evidence_rows` = count(evidence), `capture_ratio` = `round(facts / candidates, 4)` (None iff candidates == 0). Counts are global, not corpus-scoped. health.py:100-105, 122-131
- out: `{"contract": "polymath-health-surface-v1", "lanes": {...}, "suspect": [names where status == "SUSPECT"]}`. health.py:107, 132-134

**pipeline** — health.py:138-149
- out: `pipeline_health(conn)`; shape owned by polymath_shared.pipeline_health. health.py:148-149

## effect surface
- Postgres reads via `polymath_shared.db.tx`: `corpora` (health.py:45), `knowledge_lane_attempts` (health.py:91-99), `relation_candidates`, `fact_admission_decisions`, `facts`, `evidence` (health.py:100-105). Writes: none (FACTS tables_written = []). [DERIVED]
- App state: `request.app.state.sidecars` read in ready and sidecars. health.py:22, 60 [DERIVED]
- No env flags, files, Qdrant, network calls, subprocesses (none in SOURCE; FACTS.constants = []). [DERIVED]

## invariants
INVARIANT: tables_written == ∅ (only SELECT statements in module) — health.py:44-45, 91-105 [DERIVED]
  fails-if: monitoring polls mutate state; SAFE idempotency claim breaks.
INVARIANT: /health response == `{"status": "ok"}` for all inputs — health.py:15-16 [DERIVED]
  fails-if: liveness flaps → autoheal restarts a healthy process (split defined at health.py:3-5).
INVARIANT: capture_ratio == None iff opportunities == 0 (per-lane and fact lane) — health.py:115, 130 [DERIVED]
  fails-if: guard removed → ZeroDivisionError on empty lanes.
INVARIANT: suspect ⊆ lanes.keys(), membership iff status == "SUSPECT" — health.py:132-133 [DERIVED]
  fails-if: consumers treating suspect as a separate lane set misread dead lanes.
INVARIANT: `out["lanes"]["fact"]` always comes from funnel counts, never from knowledge_lane_attempts — health.py:123 [DERIVED]
  fails-if: attempts-based "fact" row survives → contradictory fact-lane verdict.

## determinism & idempotency
determinism: NONDETERMINISTIC (db reads via `tx()` at health.py:43, 87, 148; sidecar probes `s.is_ready()` at health.py:25, 68; `app.state.sidecars` at health.py:22, 60; only `/health` returns a constant, health.py:15-16) [DERIVED]
idempotency: SAFE — every handler is a pure read; no writes anywhere in SOURCE (FACTS tables_written = []) [DERIVED]

## failure behaviour
- AttributeError on `request.app.state.sidecars` swallowed → empty registry; /ready still answers `{"ready": True, "sidecars": {}}`, /sidecars answers `{}`. health.py:21-24, 59-62 [DERIVED]
- Unknown corpus on /semantic_readiness → HTTPException status_code=404, `error_code` `"QUERY_SCOPE_UNKNOWN"`. health.py:47-53 [DERIVED]
- No other try/except: DB errors from `conn.execute` and exceptions from `require_corpus`, `semantic_completion`, `semantic_lane_status`, `pipeline_health` propagate to FastAPI. health.py:41-54, 90-105, 148-149 [DERIVED]

## dumb-code flags
- `"ready": True` hardcoded — /ready never reports not-ready even if every sidecar `is_ready()` is False, though the docstring promises "can I serve traffic now" including sidecar readiness. health.py:26 vs health.py:4-5 [DERIVED]
- `corpus_id` scopes the lane query but NOT the fact funnel: relation_candidates/fact_admission_decisions/facts/evidence counts are global in every scoped response. health.py:88-89 vs 100-105 [DERIVED]
- Fact-lane dict shape differs from other lanes: missing `documents`, `capped_documents`, `last_attempt_at`; adds `decisions`, `evidence_rows`. health.py:109-119 vs 123-131 [DERIVED]
- Docstring says autoheal acts on `/live` failures; no `/live` route exists in this file (routes are `/health`, `/ready`, ...). health.py:3 vs 15-149 [DERIVED]
- Sidecar-registry fetch + AttributeError fallback duplicated verbatim in ready and sidecars. health.py:21-24 vs 59-62 [DERIVED]
- `from polymath_shared.db import tx` imported inline three times; `HTTPException` imported inside the 404 branch. health.py:39, 84, 145; health.py:48 [DERIVED]
- SQL assembled via f-string `{where}` — safe today because both variants are code-controlled literals, but the pattern invites a non-parameterized variant later. health.py:89-98 [INFERRED: no injection possible now; risk is future edits]
- Style mix: `semantic_health` and `pipeline` are sync `def` while the other four are `async def`. health.py:75, 138 vs 15, 20, 30, 58 [DERIVED]

## refactor notes
- `router` (health.py:11) is the only import surface; orchestrator/orchestrator/main.py includes it (FACTS.importers). Renaming `router`, changing route paths, or moving handlers breaks app wiring.
- Autoheal contract: liveness/readiness split per health.py:3-5 — do not make `/health` depend on db/sidecars, nor `/ready` fail closed, without revisiting autoheal behavior.
- Versioned contract literal `"polymath-health-surface-v1"` (health.py:107) and status string `"SUSPECT"` (must match `semantic_lane_status` output, health.py:110/125 vs 133) are consumed downstream; changing either is a breaking API change.
- 404 + `QUERY_SCOPE_UNKNOWN` detail shape (health.py:50-53) and the `require_corpus` gate (health.py:41) are API/access surface.
- Lazy imports pin names in polymath_shared (`tx`, `semantic_completion`, `semantic_lane_status`, `pipeline_health`) and `orchestrator.web_scope.require_corpus` (health.py:38-40, 84-85, 145-146); changes there break at call time, not import time.
- Any fix to the fact-funnel corpus scoping (health.py:100-105) changes `/health/semantic` output values for scoped calls — update consumers of `capture_ratio`/`suspect` accordingly.

## VERIFY
```verify
grep -Fq '{"status": "ok"}' orchestrator/orchestrator/api/health.py
grep -Fq 'QUERY_SCOPE_UNKNOWN' orchestrator/orchestrator/api/health.py
grep -Fq 'polymath-health-surface-v1' orchestrator/orchestrator/api/health.py
grep -Fq '"ready": True' orchestrator/orchestrator/api/health.py
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/health.py
test "$(grep -c -F 'from polymath_shared.db import tx' orchestrator/orchestrator/api/health.py)" -ge 3
```
