# unit: shared/polymath_shared/divergent.py
anchor: shared/polymath_shared/divergent.py:1-282

## purpose
WILDCARD-mode retrieval engine ("DIVERGENT-RETRIEVAL-V1"): finds sources meaningfully DIFFERENT from the query's obvious neighborhood that may still transfer — "reward latent similarity, punish ordinary similarity" — shared/polymath_shared/divergent.py:1-15 [DERIVED]
Validates candidates with a two-hop check (query↔latent surface, surface↔source child via cross-encoder) and inverts direct query↔child similarity as a novelty damper; hard bound of ≤3 bridges in a separate `wildcard` lane that never displaces answer evidence — shared/polymath_shared/divergent.py:17-28 [DERIVED]
Consumed by orchestrator chat retrieval (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `divergent_retrieve` | def | (query, *, embed_query, latent_search, children_of, baseline=None, rerank_pairs=None, plan) -> dict | shared/polymath_shared/divergent.py:266-281 | orchestrator/orchestrator/api/chat_retrieval.py, orchestrator/orchestrator/api/_small-modules (module-level) |
| `divergent_sweep` | def | (qvec, latent_search, plan=DIVERGENT_DEFAULT_PLAN) -> dict[str, dict] | shared/polymath_shared/divergent.py:99-129 | same importers (module-level) |
| `divergent_finish` | def | (query, parents, *, children_of, baseline=None, rerank_pairs=None, plan=DIVERGENT_DEFAULT_PLAN, deadline=None, clock=None) -> dict | shared/polymath_shared/divergent.py:132-263 | same importers (module-level) |
| `DivergentPlan` | dataclass | 9 config fields (see invariants) | shared/polymath_shared/divergent.py:70-80 | — |
| `DIVERGENT_DEFAULT_PLAN` | instance | `DivergentPlan()` | shared/polymath_shared/divergent.py:83 | — |
| `Bridge` | dataclass | parent_id, doc_id, source_name, principle, why_it_may_transfer, source_evidence, scores, channels, verified=True | shared/polymath_shared/divergent.py:86-96 | — |

## contracts

**divergent_sweep** — shared/polymath_shared/divergent.py:99-129
- in: `qvec`; `latent_search(kind, qvec, plan.latent_top_k) -> rows(score, payload)`; `kind` ∈ `{"latent_abstraction", "latent_transfer"}` — shared/polymath_shared/divergent.py:106-108 [DERIVED]
- out: `{parent_id: slot}` in first-seen order; slot keys `parent_id, doc_id, source_name, hop1, channels, abstraction, transfer` — shared/polymath_shared/divergent.py:104,116-121,129 [DERIVED]
- pre: needs only the query vector, no baseline — shared/polymath_shared/divergent.py:100-103 [DERIVED]
- post: `slot["hop1"]` is the max score seen for that parent across both channels; rows whose payload lacks `parent_id` are skipped — shared/polymath_shared/divergent.py:113-115,123 [DERIVED]

**divergent_finish** — shared/polymath_shared/divergent.py:132-263
- in: `query`; `parents` from a finished sweep (read, never mutated); `children_of(parent_id) -> rows`; `baseline` = `{doc_ids, parent_ids, chunk_ids}` of the core result; `rerank_pairs(anchor_text, [texts]) -> [scores]`; `deadline` = monotonic instant after which no NEW validation starts — shared/polymath_shared/divergent.py:133-141 [DERIVED]
- out: `{"wildcard": [vars(Bridge)...], "diagnostics": diag, "plan": plan.plan_version}` — shared/polymath_shared/divergent.py:260-263 [DERIVED]
- pre: parent-level hard exclusion against `baseline.parent_ids`; doc-level exclusion deliberately NOT hard (small-corpus measurement: 36/36 candidates excluded on a 2-doc corpus) — shared/polymath_shared/divergent.py:168-179 [DERIVED]
- post: frontier sorted `(-hop1, parent_id)`, truncated to `plan.candidate_parents`; bridges sorted `(-value, parent_id)`; wildcard length ≤ `plan.max_bridges` — shared/polymath_shared/divergent.py:181-182,259-260 [DERIVED]

**divergent_retrieve** — shared/polymath_shared/divergent.py:266-281
- in/out: same as finish, plus `embed_query(query) -> qvec`; composition embed → sweep → finish, "unchanged contract" — shared/polymath_shared/divergent.py:276-281 [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS tables_read=[], tables_written=[]) [DERIVED]
- Qdrant: none directly; row sources are injected callables `latent_search`/`children_of` — collection names not visible in this file — shared/polymath_shared/divergent.py:108,198 [INFERRED: signatures only, no store access in this unit]
- External model calls via injected callables: `rerank_pairs` (cross-encoder, one call per candidate parent), `embed_query` — shared/polymath_shared/divergent.py:19-20,211,277 [DERIVED]
- Clock: `time.perf_counter` default, injectable via `clock` — shared/polymath_shared/divergent.py:154-155 [DERIVED]
- Files, subprocesses, env flags: none visible [DERIVED]

## invariants

INVARIANT: len(wildcard) ≤ `max_bridges` = 3 — shared/polymath_shared/divergent.py:75,260 [DERIVED]
  fails-if: wildcard floods context, violating the hard bound at :27-28,:75
INVARIANT: len(frontier) ≤ `candidate_parents` = 8 — shared/polymath_shared/divergent.py:74,182 [DERIVED]
  fails-if: more reranker calls than the +2 s frontier budget assumes (:147-149)
INVARIANT: kids per judge call ≤ `children_per_parent` = 8 — shared/polymath_shared/divergent.py:80,202 [DERIVED]
  fails-if: B12 cost regression (was "every child, ≤ 50" per :80)
INVARIANT: reranked survivor has support ≥ `support_floor` = 0.15 — shared/polymath_shared/divergent.py:76,217-220 [DERIVED]
  fails-if: interesting-but-unsupported bridge ships as grounded
INVARIANT: value = hop1 × (support if support is not None else hop1) × novelty — shared/polymath_shared/divergent.py:234-235 [DERIVED]
  fails-if: obvious or ungrounded bridges outrank surprising ones (multiplicative design :24-25)
INVARIANT: novelty ∈ {`borderline_novelty`=0.4 (in-neighborhood or overlap > `obvious_lexical_cap`=0.35), 0.4+(1-0.4)/2=0.7 (same doc), 1.0 (else)} — shared/polymath_shared/divergent.py:77-78,224-233 [DERIVED]
  fails-if: wildcard duplicates the baseline neighborhood instead of diverging
INVARIANT: result keys exactly `wildcard`, `diagnostics`, `plan` — shared/polymath_shared/divergent.py:262-263 [DERIVED]
  fails-if: caller lane wiring in chat_retrieval.py breaks
INVARIANT: new validation starts only while `clock() + max(0.4, mean(durations))` ≤ deadline (est = 0.4 when no durations) — shared/polymath_shared/divergent.py:188-190 [DERIVED]
  fails-if: frontier budget overrun; whole lane abandoned instead of `partial: True` return

## determinism & idempotency
determinism: DETERMINISTIC given fixed embed/latent/rerank outputs and `deadline=None` ("Deterministic given fixed model outputs" :36-38); NONDETERMINISTIC (clock, shared/polymath_shared/divergent.py:154-155) when `deadline` is set — wall time decides which parents are validated (:188-193)
idempotency: SAFE — no writes; `parents` is read, never mutated (:133-134); pure over injected callables

## failure behaviour
- `latent_search` raises → `rows = []` (:108-110): channel silently contributes nothing; caller sees fewer parents, never an error [DERIVED]
- `children_of` raises → `kid_rows = []` (:197-200): candidate has no kids → `continue` (:203-204); skipped without diagnostics beyond `durations` [DERIVED]
- `rerank_pairs` raises → `scores = None` (:210-213): support stays `None`, value substitutes `hop1` (:234-235), `support_filtered` not incremented [DERIVED]
- Module-wide fail-open: "no latent points, reranker down, empty corpus → empty wildcard lane, never an error" (:36-38) [DERIVED]
- No error codes raised in this file; `diag["reranker"]` records whether `rerank_pairs` was supplied (:164) [DERIVED]

## dumb-code flags
- Magic estimate floor `0.4` in the deadline check, not a `DivergentPlan` field; docstring cost estimates are "~0.25 s fresh, 1–2 s" — shared/polymath_shared/divergent.py:148-149,189 [DERIVED]
- `Bridge.verified` default `True` with comment documenting `False` semantics ("shipped without the two-hop judge"), but no code path in this unit assigns `verified=False` — the constructor call omits it — shared/polymath_shared/divergent.py:96,240-256 [DERIVED]
- Two distinct knobs share literal `8`: `candidate_parents` and `children_per_parent` — shared/polymath_shared/divergent.py:74,80 [DERIVED]
- same-doc novelty computed inline as `plan.borderline_novelty + ((1.0 - plan.borderline_novelty) / 2)`; retuning `borderline_novelty` silently shifts same-doc damping — shared/polymath_shared/divergent.py:230-231 [DERIVED]
- `DIVERGENT_DEFAULT_PLAN` is one shared mutable dataclass instance used as the default argument of all three public functions — shared/polymath_shared/divergent.py:83,101,264,274 [INFERRED: any caller mutating it changes defaults everywhere]
- Change-log comment embedded as code comment: "(was every child, ≤ 50)" — shared/polymath_shared/divergent.py:80 [DERIVED]

## refactor notes
- Signature or return-shape changes to `divergent_retrieve`/`divergent_sweep`/`divergent_finish` ripple into orchestrator/orchestrator/api/chat_retrieval.py and orchestrator/orchestrator/api/_small-modules (FACTS.importers).
- Output keys `wildcard`/`diagnostics`/`plan` and `Bridge` field names are the caller contract — shared/polymath_shared/divergent.py:86-96,240-263 [DERIVED]
- The two-stage split is required for the parallel-frontier design: `divergent_sweep` must keep needing only `qvec`; re-merging stages undoes the §3.19 latency win — shared/polymath_shared/divergent.py:41-46,100-103 [DERIVED]
- `diagnostics` keys (`partial`, `parents_skipped`, `skipped_parents`, `support_filtered`, `excluded_obvious`, `parents_validated`) are emitted for observability consumers — shared/polymath_shared/divergent.py:162-166,188-193 [DERIVED]
- `DivergentPlan` defaults are latency tuning: each candidate parent costs one reranker call (~0.25 s fresh, 1–2 s contended), so `candidate_parents`/`children_per_parent` changes alter frontier cost directly — shared/polymath_shared/divergent.py:74,80,147-149 [DERIVED]

## VERIFY
```verify
grep -Fq 'max_bridges: int = 3' shared/polymath_shared/divergent.py
grep -Fq 'support_floor: float = 0.15' shared/polymath_shared/divergent.py
grep -Eq 'novelty = plan\.borderline_novelty \+ \(' shared/polymath_shared/divergent.py
grep -Fq 'est = max(0.4, sum(durations) / len(durations)) if durations else 0.4' shared/polymath_shared/divergent.py
! grep -Fq 'verified=False' shared/polymath_shared/divergent.py
test "$(grep -c -F 'except Exception' shared/polymath_shared/divergent.py)" -ge 3
```
