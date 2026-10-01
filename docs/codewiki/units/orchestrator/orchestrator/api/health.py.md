# unit: orchestrator/orchestrator/api/health.py
anchor: orchestrator/orchestrator/api/health.py:1-158

## purpose
FastAPI router of operator/health endpoints: liveness (`/health`), traffic readiness (`/ready`), sidecar registry detail (`/sidecars`), per-corpus semantic-completion verdict (`/semantic_readiness`), semantic-lane health (`/health/semantic`), and pipeline BLOCKED-vs-IDLE (`/health/pipeline`). Liveness/readiness split is the ISSUES_REPORT §3.3 fix — autoheal acts only on `/live` failures, `/ready` reports sidecar readiness without punishing startup. — orchestrator/orchestrator/api/health.py:1-6 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | module attr | `APIRouter()` | orchestrator/orchestrator/api/health.py:11 | orchestrator/orchestrator/main.py (FACTS.importers) |
| `health` | def + route | `() -> dict` — GET `/health` | orchestrator/orchestrator/api/health.py:14-16 | HTTP |
| `ready` | def + route | `(request: Request) -> dict` — GET `/ready` | orchestrator/orchestrator/api/health.py:19-26 | HTTP |
| `semantic_readiness` | def + route | `(corpus_id: str) -> dict` — GET `/semantic_readiness` | orchestrator/orchestrator/api/health.py:29-63 | HTTP |
| `sidecars` | def + route | `(request: Request) -> dict` — GET `/sidecars` | orchestrator/orchestrator/api/health.py:66-80 | HTTP |
| `semantic_health` | def + route | `(corpus_id: str | None = None) -> dict` — GET `/health/semantic` | orchestrator/orchestrator/api/health.py:83-143 | HTTP |
| `pipeline` | def + route | `() -> dict` — GET `/health/pipeline` | orchestrator/orchestrator/api/health.py:146-158 | HTTP |

## contracts

**`semantic_readiness(corpus_id)`** — SEMANTIC-READINESS-V1 verdict (orchestrator/orchestrator/api/health.py:31-37)
- pre: `require_corpus(corpus_id)` runs before any DB access — FRIENDS-ACCESS-V1 D5 — orchestrator/orchestrator/api/health.py:41
- pre: corpus row must exist in `corpora` (`SELECT 1 FROM corpora WHERE corpus_id = %s`) — orchestrator/orchestrator/api/health.py:44-46
- out: dict from `semantic_completion(conn, corpus_id)` — orchestrator/orchestrator/api/health.py:54
- post: if `out["vnext"]` is a dict and `served_profiles(corpus_id)` returns non-None, `vnext["vnext_served"] = min(int(v.get("documents") or 0), sum(1 for c in served.values() if c.get("writer") == "vnext"))` — orchestrator/orchestrator/api/health.py:60-62
- effect: `served_profiles` executed off the event loop via `run_in_threadpool` — orchestrator/orchestrator/api/health.py:58-59

**`semantic_health(corpus_id)`** — POLYMATH-HEALTH-SURFACE-V1 (orchestrator/orchestrator/api/health.py:85-92)
- in: `corpus_id` optional; when set, lane query filtered `WHERE corpus_id = %s` — orchestrator/orchestrator/api/health.py:97-98
- out: `{"contract": "polymath-health-surface-v1", "lanes": {...}}`; per lane: `status`, `opportunities`, `accepted`, `capture_ratio`, `documents`, `capped_documents`, `last_attempt_at` — orchestrator/orchestrator/api/health.py:116-128
- out: lane `status` from `semantic_lane_status(opportunities=opps, accepted=acc, capped_documents=capped, documents=docs)` — orchestrator/orchestrator/api/health.py:119-121
- out: `capture_ratio = round(acc / opps, 4) if opps else None` — orchestrator/orchestrator/api/health.py:124
- out: `out["lanes"]["fact"]` rebuilt from the durable funnel (relation_candidates → fact_admission_decisions → facts, plus evidence) with `semantic_lane_status(opportunities=candidates, accepted=facts)` — orchestrator/orchestrator/api/health.py:129-140
- post: `out["suspect"]` = every lane name with `status == "SUSPECT"` — orchestrator/orchestrator/api/health.py:141-142

**`pipeline()`** — PIPELINE-BLOCKED-HEALTH-V1: makes a stalled pipeline say BLOCKED with cause vs IDLE — orchestrator/orchestrator/api/health.py:148-153
- out: dict from `pipeline_health(conn)` — orchestrator/orchestrator/api/health.py:158

**`ready(request)`**
- out: `{"ready": True, "sidecars": {name: s.is_ready()}}` — always `True`; sidecar readiness reported, not gating — orchestrator/orchestrator/api/health.py:25-26

## effect surface
- Postgres read via `polymath_shared.db.tx`: `corpora` (:45), `knowledge_lane_attempts` (:106), `relation_candidates` (:111), `fact_admission_decisions` (:112), `facts` (:113), `evidence` (:114) — orchestrator/orchestrator/api/health.py:43-114
- Postgres written: none — FACTS `tables_written: []`
- App state read: `request.app.state.sidecars` — orchestrator/orchestrator/api/health.py:22, :69
- Threadpool: `run_in_threadpool(served_profiles, corpus_id)` — orchestrator/orchestrator/api/health.py:59
- Env flags: none visible.

## invariants
INVARIANT: `/health` response == `{"status": "ok"}` unconditionally — orchestrator/orchestrator/api/health.py:16 [DERIVED]
  fails-if: liveness probe sees anything else; autoheal contract (§3.3) breaks.
INVARIANT: `/ready` always returns `"ready": True` — orchestrator/orchestrator/api/health.py:26 [DERIVED]
  fails-if: if a failing sidecar ever flipped `ready` to False, startup would be punished, undoing the §3.3 split.
INVARIANT: `vnext_served` <= `vnext.documents` — enforced by `min()` — orchestrator/orchestrator/api/health.py:62 [DERIVED]
  fails-if: badge could show more served vNext files than documents claimed complete.
INVARIANT: `vnext_served` <= count of served cards with `writer == "vnext"` — orchestrator/orchestrator/api/health.py:62 [DERIVED]
  fails-if: a refused vNext card would paint the library green.
INVARIANT: `capture_ratio` == `round(accepted/opportunities, 4)` or `None` iff `opportunities == 0` — orchestrator/orchestrator/api/health.py:124, :139 [DERIVED]
  fails-if: ZeroDivisionError on empty lanes.
INVARIANT: `out["suspect"]` == set of lane names where `status == "SUSPECT"` — orchestrator/orchestrator/api/health.py:141-142 [DERIVED]
  fails-if: operator alerting misses dead lanes.
INVARIANT: `out["lanes"]["fact"]` after the handler equals the funnel-derived dict, not the `knowledge_lane_attempts` row — orchestrator/orchestrator/api/health.py:132 [INFERRED: dict assignment overwrites any same-key lane from the loop]
  fails-if: if the overwrite is removed, fact liveness falls back to the attempts table, bypassing the candidates→decisions→facts funnel.

## determinism & idempotency
determinism: NONDETERMINISTIC (DB contents via `tx()` :43, :96, :157; `request.app.state.sidecars` :22, :69; threadpool execution of `served_profiles` :59). Response shape and key names are fixed literals.
idempotency: SAFE — all handlers are GET routes; `tables_written` is empty (FACTS); no mutation of app state.

## failure behaviour
- `AttributeError` on missing `request.app.state.sidecars` is swallowed → defaults to `{}`; `/ready` then returns `{"ready": True, "sidecars": {}}` — orchestrator/orchestrator/api/health.py:23-24; same pattern in `sidecars` :70-71.
- Unknown corpus in `semantic_readiness` raises `HTTPException(status_code=404)` with `detail {"error_code": "QUERY_SCOPE_UNKNOWN", "message": f"corpus {corpus_id!r} not found"}` — orchestrator/orchestrator/api/health.py:50-53.
- If `served_profiles` returns `None`, `vnext_served` is silently not set — the `vnext` dict keeps its original shape — orchestrator/orchestrator/api/health.py:61-62.
- No handlers around `semantic_health`/`pipeline` bodies; DB errors propagate to the router — orchestrator/orchestrator/api/health.py:96-114, :157-158.

## dumb-code flags
- Corpus-scoping asymmetry: lane aggregates filter by `corpus_id` (:97-98, :106) but the fact-funnel subqueries over `relation_candidates`/`fact_admission_decisions`/`facts`/`evidence` have no WHERE — a per-corpus call mixes scoped lanes with fleet-wide fact counts — orchestrator/orchestrator/api/health.py:110-114 [DERIVED]
- Duplicated sidecar-registry fallback: identical try/AttributeError/`{}` block in `ready` and `sidecars` — orchestrator/orchestrator/api/health.py:22-24 vs :69-71 [DERIVED]
- `from polymath_shared.db import tx` repeated inline in three handlers — orchestrator/orchestrator/api/health.py:39, :93, :154 [DERIVED]
- `HTTPException` imported lazily inside the 404 branch while `APIRouter`/`Request` are top-level imports — orchestrator/orchestrator/api/health.py:48 vs :9 [DERIVED]
- Magic rounding constant `4` in both capture_ratio sites — orchestrator/orchestrator/api/health.py:124, :139 [DERIVED]
- `int(v.get("documents") or 0)` collapses `None` and `0` identically — orchestrator/orchestrator/api/health.py:62 [DERIVED]
- f-string SQL interpolation `{where}` — safe here because `where` is only `""` or the parameterized literal, but the pattern invites injection if extended — orchestrator/orchestrator/api/health.py:100-107 [INFERRED]

## refactor notes
- `router` is mounted by `orchestrator/orchestrator/main.py` (FACTS.importers); adding/removing/renaming any of the 6 GET paths changes the externally served surface — orchestrator/orchestrator/api/health.py:14-146.
- `"contract": "polymath-health-surface-v1"` (:116) and the `vnext_served` key (:62) are consumed downstream — the comment states "the badge reads this" (:55-56); renaming either breaks readers.
- `require_corpus(corpus_id)` must stay first, before the corpora SELECT — FRIENDS-ACCESS-V1 D5 — orchestrator/orchestrator/api/health.py:41-46.
- The `out["lanes"]["fact"]` overwrite must stay after the lane loop, or the funnel-derived status is clobbered — orchestrator/orchestrator/api/health.py:117-132.
- `served_profiles` must remain off the event loop (`run_in_threadpool`) per the None-safe comment — orchestrator/orchestrator/api/health.py:55-59.

## VERIFY
```verify
grep -Fq '{"status": "ok"}' orchestrator/orchestrator/api/health.py
grep -Fq 'QUERY_SCOPE_UNKNOWN' orchestrator/orchestrator/api/health.py
grep -Fq 'polymath-health-surface-v1' orchestrator/orchestrator/api/health.py
grep -Fq 'vnext_served' orchestrator/orchestrator/api/health.py
grep -Eq 'router\.get\("/(health|ready|semantic_readiness|sidecars|health/semantic|health/pipeline)"\)' orchestrator/orchestrator/api/health.py
test "$(grep -c -F 'semantic_lane_status' orchestrator/orchestrator/api/health.py)" -ge 3
test "$(grep -c -F 'request.app.state.sidecars' orchestrator/orchestrator/api/health.py)" -ge 2
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/health.py
```
