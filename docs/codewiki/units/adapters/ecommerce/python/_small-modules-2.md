# unit: adapters/ecommerce/python/_small-modules-2
anchor: adapters/ecommerce/python/utilization.py:1-130

## purpose
utilization.py builds the evidence-utilization receipt (docs/21 §1): which corpus rows, evidence packets, primitive/hop citations, observations, gaps and leads earned their keep in a run. Pure, computed at qualify, shown by status, triage-run and the report; it is the instrument for the Polymath-native before/after experiment — no change ships without moving it [DERIVED adapters/ecommerce/python/utilization.py:1-8].
verifiers.py is the deterministic L1/L2 evidence-authority gate: role validity, source suitability, claim-relative freshness, independence grouping; every check can emit a typed receipt so policy changes can be recomputed later; no LLM calls, ever [DERIVED adapters/ecommerce/python/verifiers.py:1-6].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| compute | def | state: dict -> dict | adapters/ecommerce/python/utilization.py:22-91 | status, triage-run, report [DERIVED utilization.py:7] |
| to_markdown | def | u: dict -> str | adapters/ecommerce/python/utilization.py:94-129 | — |
| _kind_of_row | def (private) | rows_by_id: dict, rid: str -> str | adapters/ecommerce/python/utilization.py:15-19 | compute (utilization.py:58-59) |
| receipt | def | check_type: str, level: str, status: str, metrics: dict, reasons: list[str] -> dict | adapters/ecommerce/python/verifiers.py:13-15 | — |
| evidence_admissibility | def | obs: dict, policies: dict -> list[str] | adapters/ecommerce/python/verifiers.py:18-59 | admit_observations (verifiers.py:108) |
| independence_groups | def | observations: list[dict] -> dict | adapters/ecommerce/python/verifiers.py:62-99 | gap closure in executors.comments and coverage in satisfaction [DERIVED verifiers.py:66-67] |
| admit_observations | def | observations: list[dict], policies: dict -> tuple[list[dict], list[str]] | adapters/ecommerce/python/verifiers.py:102-113 | called at submit time [DERIVED verifiers.py:103-104] |

## contracts
**compute(state)** — utilization.py:22-91
- in: `state` dict; reads `state.get("data")` (23), `state.get("rounds")` (71), `state.get("corpus", "")` (39).
- out: dict with keys `"corpus"`, `"citations"`, `"analogies_by_authority"`, `"observations"`, `"gaps"`, `"rounds"`, `"leads"`, `"registry_candidates_by_kind"`, `"lived_world"`, `"interpretation"`, `"corpus_contribution"`, `"provenance"` (38-91).
- pre: none — missing sections default to `{}`/`[]`; non-dict items dropped via isinstance filters (24, 28-31, 36-37).
- post: delegates to `__import__("lived_world").summary(state)` (77) and `__import__("provenance").corpus_contribution(state)` (83).

**to_markdown(u)** — utilization.py:94-129
- in: `u` = compute output; requires keys `corpus`, `citations`, `observations`, `gaps`, `leads` by direct subscript (95).
- out: single markdown table string joined with `"\n"` (96, 129).
- post: LEGACY row only when `c.get("legacy_answers")` truthy (102); lived_world / interpretation / corpus_contribution / provenance sections only when present (115, 121, 123, 126).

**receipt(...)** — verifiers.py:13-15
- out: `{"check_type", "level", "status", "metrics", "reason_codes": reasons, "at": now()}` (14-15); `now` from `models` (10).

**evidence_admissibility(obs, policies)** — verifiers.py:18-59
- out: list of error strings; empty list = admissible (59).
- checks: `evidence_roles` non-empty (24-25); role in `policies["evidence_roles"]["valid"]` (22, 27); `source_identity.source_family` present and in `policies["source_suitability"]` (30-36); family `may_support` covers each valid role (38-43); `freshness.class` present and in `policies["freshness_classes"]` (45-50); per-role `freshness_requirements` satisfied (52-58).

**independence_groups(observations)** — verifiers.py:62-99
- out: `{"independent_groups": len(groups), "source_families": len(families)}` (99).
- rule: union-find merging each obs with `("author", platform, author)` and `("thread", platform, thread)` (93-96); dependent iff shared (platform, author) OR (platform, thread) (66-69).

**admit_observations(observations, policies)** — verifiers.py:102-113
- out: `(ok, all_errors)`; any observation with ≥1 error is excluded from `ok` (107-112).

## effect surface
- Postgres tables: none (FACTS tables_read/tables_written empty).
- Qdrant collections: none — FACTS-listed `polymath_evidence_calls` / `polymath_chat_calls` are receipt dict keys, not stores (utilization.py:51, 53, 101).
- Network/LLM: none in verifiers — "No LLM calls, ever" (verifiers.py:6).
- Imports: `collections` (utilization.py:12), `models.now` (verifiers.py:10), dynamic `__import__("lived_world")` / `__import__("provenance")` (utilization.py:77, 83).
- Clock: `now()` inside receipt (verifiers.py:15).
- Files/subprocess/env flags: none visible.

## invariants
INVARIANT: corpus.packets == corpus.polymath_evidence_calls — both are `len(packets)` — utilization.py:47,51 [DERIVED]
  fails-if: the "evidence / synthesis" Polymath-calls row (utilization.py:101) stops matching actual packet count.
INVARIANT: citations.distinct_corpus_rows_cited <= corpus.rows — cited set only counts refs present in rows_by_id — utilization.py:60,41 [DERIVED]
  fails-if: citation accounting claims rows the corpus lane never returned.
INVARIANT: observations.distinct_threads <= observations.total — threads is a set of (platform, thread_key) pairs — utilization.py:32,64,67 [DERIVED]
  fails-if: inflated thread counts corrupt downstream independence reasoning.
INVARIANT: len(ok) + count(obs with errors) == len(observations) in admit_observations — verifiers.py:107-112 [DERIVED]
  fails-if: inadmissible evidence enters state, violating the submit-time contract (verifiers.py:103-104).
INVARIANT: independence_groups.independent_groups <= len(observations) — union-find only merges nodes, never splits — verifiers.py:93-99 [INFERRED]
  fails-if: dependent voices counted as independent inflate evidence authority.
INVARIANT: gaps.with_corpus_support <= gaps.total — support counts gap ids in gaps_with_corpus — utilization.py:34-35,69-70 [DERIVED]
  fails-if: corpus support overcounted against known gaps.

## determinism & idempotency
determinism: compute/to_markdown DETERMINISTIC (pure per docstring, stdlib Counter + f-strings only — utilization.py:6-7) except delegated `lived_world.summary` / `provenance.corpus_contribution`, not visible here (utilization.py:77, 83). evidence_admissibility / independence_groups / admit_observations DETERMINISTIC (pure dict/list ops, no LLM — verifiers.py:6). receipt NONDETERMINISTIC (clock: `now()` — verifiers.py:15).
idempotency: SAFE — all functions return values, no writes or input mutation visible; re-issuing receipt changes only the `at` timestamp (verifiers.py:15).

## failure behaviour
- compute swallows missing/malformed input: `or {}` / `or []` defaults plus isinstance filters drop non-dict rows, observations, gaps, leads, concepts, packets, legacy answers (utilization.py:23-37); no exception on absent data.
- to_markdown raises KeyError if a required key is absent (`u["corpus"]` etc., utilization.py:95); optional metrics default to `0` / `{}` via `.get` (99-105).
- verifiers never raise for bad evidence — they return message strings prefixed `{oid}:` with `oid` defaulting `"?"` (verifiers.py:21, 25-58).
- compute raises ImportError at runtime if `lived_world` or `provenance` modules are missing [INFERRED: bare dynamic `__import__` with no fallback, utilization.py:77, 83].

## dumb-code flags
- `"chunk"` default duplicated: `_kind_of_row` (utilization.py:18) and the rows_by_kind counter (41).
- Hard-coded defaults: channel `"alibaba"` (74), mode `"generic"` (40), backend name `"polymath"` when `state.get("corpus", "")` startswith `"polymath:"` (39).
- `rows_by_id = {r.get("id"): r for r in rows}` — rows lacking `id` all collide on key `None`, last one wins [INFERRED: utilization.py:25].
- `node = ("obs", id(o))` keys by object identity — the same dict object appearing twice counts once [INFERRED: verifiers.py:93].
- Metric names `polymath_evidence_calls` / `polymath_chat_calls` written in compute (51, 53) and re-read literally in to_markdown (101) — rename must touch both.
- Dynamic `__import__("lived_world")` / `__import__("provenance")` inside compute hides dependencies from static import graphs (77, 83).

## refactor notes
- independence_groups is "THE definition of independence" for the whole skill — executors.comments gap closure and satisfaction coverage both call it; changing the (platform, author)/(platform, thread) merge rule changes both callers (verifiers.py:66-69).
- admit_observations runs at submit time so inadmissible evidence never enters state — moving it relocates the admission gate (verifiers.py:103-104).
- receipt's key set (`check_type`, `level`, `status`, `metrics`, `reason_codes`, `at`) exists so policy changes can be recomputed against original metrics — renaming breaks replay (verifiers.py:5-6, 14-15).
- compute's return keys are the before/after experiment instrument ("no change ships without moving it") and are consumed literally by to_markdown — renames ripple to status/triage-run/report consumers (utilization.py:7-8, 38-91, 95-128).
- evidence_admissibility policy keys (`evidence_roles`, `source_suitability`, `freshness_classes`, `freshness_requirements`) form a policy-schema contract (verifiers.py:22-52).

## VERIFY
```verify
grep -Fq 'polymath_evidence_calls' adapters/ecommerce/python/utilization.py
grep -Eq 'def (compute|to_markdown|_kind_of_row)' adapters/ecommerce/python/utilization.py
grep -Fq 'No LLM calls, ever' adapters/ecommerce/python/verifiers.py
grep -Eq 'def (receipt|evidence_admissibility|independence_groups|admit_observations)' adapters/ecommerce/python/verifiers.py
grep -Fq 'a source proves only what it is qualified to prove' adapters/ecommerce/python/verifiers.py
! grep -Fq 'import requests' adapters/ecommerce/python/verifiers.py
```
