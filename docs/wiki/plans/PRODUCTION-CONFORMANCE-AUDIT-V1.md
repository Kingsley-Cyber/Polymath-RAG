---
title: "PRODUCTION-CONFORMANCE-AUDIT-V1 — discover, prove, retire"
change_id: PRODUCTION-CONFORMANCE-AUDIT-V1
owner: governance
date: 2026-09-12
last_reviewed: 2026-09-12
status: ACTIVE
register: 11.209
architecture_impact: "Adds an audit framework + a provider ATTEMPT ledger (migration 0056). No retrieval, ranking, readiness or provider policy changed. The one production-path edit is a fail-soft recorder at the LLMExtractionClient dispatch seam."
---

# Production conformance audit

A **re-firable** framework that does three things: discover what exists, prove what
works, and prove what is safe to remove.

The governing constraint: **nothing about the current topology is hardcoded.** Replacing
a model, provider, account, lane, worker, route or fallback means editing configuration
and re-firing the same commands — never editing audit logic.

## 1. Commands

```bash
python scripts/audit_polymath.py --discover                 # topology only
python scripts/audit_polymath.py --no-spend                 # CI-safe: static + live reads
python scripts/audit_polymath.py --full                     # + route probes
python scripts/audit_polymath.py --function PMAP            # narrow (values are DISCOVERED)
python scripts/audit_polymath.py --provider <p> --model <m> --lane <l>
python scripts/audit_polymath.py --retirement-candidates
python scripts/audit_polymath.py --prove-unused <component>
```

Logic lives in `shared/polymath_shared/conformance/`; the script is orchestration only.

## 2. Classification

`WORKING_PROVEN · WORKING_UNQUALIFIED · CONFIGURED_IDLE · BROKEN_REACHABLE · SHADOWED ·
LEGACY_REQUIRED · RETIRE_CANDIDATE · DEAD_PROVEN · NOT_TESTED · UNKNOWN`

**`NOT_TESTED` and `UNKNOWN` are RED.** An audit that renders absence of evidence as
success launders ignorance into confidence, so `classify.GREEN` contains exactly one
state and the report/CI colour-codes from that set.

Proof levels are separate from state:
`IMPLEMENTED → WIRED → LIVE → OBSERVED → CONTRACT_QUALIFIED → PIPELINE_QUALIFIED → E2E_QUALIFIED`.
A PASS at one level is never evidence for a higher one.

## 3. Function contracts are the stable authority

Permanent functions: `GRAPH_EXTRACTION · DOCUMENT_PROFILE · PMAP · CHAT`.
Models qualify **against** functions; functions never adapt to a model.
`parent_enrichment` is transitional/legacy — it is discovered as a stage pin, and the
legacy scan reports its readers rather than assuming it dead.

## 4. The attempt ledger (the gap this framework was built around)

Measured 2026-09-11: a pMAP run recorded **SUCCESS on every batch** while issuing
**181 HTTP 429s**, 145 of them in one ten-minute window — an 82% rejection rate. The
in-run cross-lane failover retries a refused lane on the next lane and only the FINAL
outcome reaches `document_parent_map_batches`, so per-attempt provider pressure was
invisible to every durable counter, to the control plane, and to the backfill's own
stop conditions.

`llm_provider_attempts` (migration 0056) records **one row per provider attempt** —
lane, provider, model, account ENV NAME, attempt ordinal, limiter admission, HTTP
dispatch, status, Retry-After, normalized error, latency, success. Written at
`LLMExtractionClient.complete_one`, the single seam that sees admission, lane, status
and Retry-After together. Fail-soft: a missing table or unreachable DB logs once and
the call proceeds. **No credential is ever stored.**

```
map_groq2 -> 429   attempt 1        }
map_groq3 -> 429   attempt 2        }  all three durable
map_groq5 -> 200   attempt 3        }
PMAP batch -> SUCCESS                  the outcome, not a substitute for the attempts
```

`attempts.reconcile()` names the failure modes as counts: `PROVIDER_PRESSURE`,
`FAILOVER_ATTEMPTS`, `HIDDEN_429`.

## 5. Retirement law

`ELIMINATE READERS → STOP WRITERS → PROVE NO RE-MINT → REMOVE CODE → DELETE STATE AFTER
A ROLLBACK WINDOW.`

`--prove-unused` runs the static half (reader/writer census over tracked source,
migrations excluded, ambiguity counted as a READER because over-counting readers only
delays a retirement while under-counting enables a wrong deletion). It prints, rather
than hides, that static proof alone is **not sufficient** — runtime readers, scheduler
producers, fallback references and rollback need must also be zero.

**Nothing is deleted for being broken.** `BROKEN_REACHABLE` becomes `RETIRE_CANDIDATE`
only when a replacement exists AND the zero-reader proof holds.

## 6. Bundle

Every run writes `artifacts/audit/<audit_id>/`: `manifest.json`, `runtime_topology.json`,
`function_results.json`, `qualification_matrix.json`, `retirement_candidates.json`,
`legacy_scan.json`, `failures.json`, `report.md`. The manifest pins repo SHA, branch,
runtime bundle, config hashes, discovered counts, scope and live-call count.

## 7. Status — what is built and what is not

| slice | state |
|---|---|
| A discovery + topology | **DONE** — 46 lanes / 7 providers / 15 models / 43 routes / 16 workers / all tables, all discovered |
| B attempt telemetry | **DONE** — migration 0056, recorder at the client seam, pMAP tagged, reconciliation readers |
| C conformance engine | **DONE (L0–L1)** — classification, levels, evidence, bundle, report |
| D function live qualification (L2–L3) | **NOT BUILT** — `contract_qualified` / `pipeline_qualified` emit `NOT_TESTED` |
| E product E2E (L5) + re-fire | **NOT BUILT** |
| F retirement removal | **PARTIAL** — candidates + static proof; no removal performed |
| G Control Plane integration | **NOT BUILT** |
| H CI wiring | **PARTIAL** — `--no-spend` runs clean; not yet in a CI job |

The matrix deliberately emits `NOT_TESTED` for every level it has not actually proven.
