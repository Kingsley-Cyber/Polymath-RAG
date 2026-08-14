# RAG E2E Checklist

Release gates for the local-first GraphRAG system. A gate is marked
COMPLETE only when its acceptance evidence exists in the repository
(evaluation artifacts, tests, guards). Partial work is NOT marked
complete.

Status vocabulary: COMPLETE / IN PROGRESS / NOT STARTED / BLOCKED.

## Foundation gates

| Gate | Question | Status | Evidence |
|---|---|---|---|
| F0 | Does the repository scaffold pass its own governance checks? | COMPLETE | `make guards` green at every checkpoint commit; TREE-driven preflight |
| F1 | Is intake idempotent — one run per canonical input? | COMPLETE | live E2E (Phase B/C): replay returns same `run_id`, `already_exists=true` |
| F2 | Do receipts commit with the stage work in ONE transaction? | COMPLETE | `shared/polymath_shared/receipts.py` + savepoint failure receipts; tested |
| F3 | Does the control plane survive process restarts? | COMPLETE | separate process + Postgres lease + census; live 5/6-stage autonomous run to `query_ready` |
| F4 | Can projections be destroyed and reconstructed exactly? | COMPLETE | 7/7 destructive-reconstruction gates green (`tests/integration/test_projection_reconstruction.py`) |
| F5 | Is replay a no-op (zero duplicate facts/points)? | COMPLETE | gate 4 of F4 + content-hash identities |
| F6 | Are projection receipts append-only with superseded claims? | COMPLETE | migration 0004 + orphan-supersede tests |

## Extraction gates

| Gate | Question | Status | Evidence |
|---|---|---|---|
| X1 | Does the deterministic compiler decide all graph semantics? | COMPLETE | ADR-0007/0008; GLiNER proposes, compiler decides; negation/modality/voice tests |
| X2 | Are lexical resources vendored, pinned, flattened, and build-gated? | COMPLETE | Phase G: contract `03a513ec…`, 10/10 resource gates green |
| X3 | Is runtime independent of raw resources? | COMPLETE | GATE 10 test (vendor/ removed → compiler still loads) |
| X4 | Are facts provably evidence-backed with resource provenance? | COMPLETE | provenance carries rule_id, roleset, resource_contract_id; live proof (founded/establish.01/base-97.1/semlink=true) |

## Retrieval gates

| Gate | Question | Status | Evidence |
|---|---|---|---|
| R0 | Is document routing parallel and never a recall gate? | COMPLETE | G1: golden trace frozen; child-survives-zero-doc test |
| R1 | Does the G2 neural dense lane pass its contract gates? | COMPLETE | embedding-contract tests + live zero-overlap query proof (gate 7e) |
| R2 | Do fused candidates get cross-representation reranking? | NOT STARTED | G3 reranker is a stub |
| R3 | Can every answer claim assemble from traceable EvidenceBundle evidence? | NOT STARTED | G5 not built |
| R4 | Is graph expansion bounded and useful at real corpus scale? | IN PROGRESS | monotonicity unit-tested; scale/hub qualification not run |

## Empirical gates (the measured-delta discipline)

| Gate | Question | Status | Evidence |
|---|---|---|---|
| H1 | Does resource enrichment add correct facts without unacceptable incorrect ones? | COMPLETE (answered: NO) | Phase H v1.0 + v1.1; verdict REJECT for hybrid default; Δ +1/+4/−4 |
| E1 | Which measured extraction gaps are worth changing? | NOT STARTED | two named mechanisms (expanded-trigger roleset constraint; composed-FN filter) — hypotheses only |
| D1 | Can additional controllers/providers be added without changing ingestion semantics? | NOT STARTED | deferred in PLAN.md |

## Operations gates

| Gate | Question | Status | Evidence |
|---|---|---|---|
| O1 | Can a clean machine reproduce the pinned system and recover its data? | NOT STARTED | launchd/Makefile exist; clean-clone startup gate + backup drill not proven |
| O2 | Are model weights pinned with recorded digests in production? | IN PROGRESS | TOFU digests; `POLYMATH_REQUIRE_PINNED=0` until digests recorded |

## The next unchecked gate

**E1** — run the two measured extraction experiments separately on the
frozen v1.1 corpus, each as a before/after delta.

## Marking policy

- Mark COMPLETE only when the named evidence artifact exists and its
  tests pass at the checkpoint commit.
- Do not mark a gate COMPLETE because a related gate passed.
- A gate whose verdict was negative (H1) is COMPLETE when the question
  was answered with measured evidence — the verdict itself is recorded
  in CURRENT_STATE.md.
