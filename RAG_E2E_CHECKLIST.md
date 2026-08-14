# RAG E2E Checklist

Release gates for the local-first GraphRAG system. A gate is marked
COMPLETE only when its acceptance evidence exists in the repository
(evaluation artifacts, tests, guards). Partial work is NOT marked
complete.

Status vocabulary: COMPLETE / IN PROGRESS / NOT STARTED / BLOCKED.

Two milestones gate the release path:

- **MILESTONE A — CORPUS_INGEST_READY**: C1 + C2 + Q1 + I1 + I2 all
  COMPLETE. This is the current priority: the system must be able to
  mass-ingest the real corpus confidently.
- **MILESTONE B — RAG_V1_E2E**: the remaining application gates
  (R2, M1–M5, R4, O2, O1, A1) + the V1 checkpoint.

R2/MCP are NOT prerequisites for CORPUS_INGEST_READY.

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

## Retrieval and answer gates

| Gate | Question | Status | Evidence |
|---|---|---|---|
| R0 | Is document routing parallel and never a recall gate? | COMPLETE | G1: golden trace frozen; child-survives-zero-doc test |
| R1 | Does the G2 neural dense lane pass its contract gates? | COMPLETE | embedding-contract tests + live zero-overlap query proof (gate 7e) |
| R3a | Can every answer claim assemble from traceable EvidenceBundle evidence? | COMPLETE | POST /evidence + `shared/polymath_shared/evidence_assembly.py`; live E2E traceable bundle; loud 502 on unresolved/missing-provenance |
| R3b | Is there a working answer generation + `/chat` path end to end? | COMPLETE | POST /chat: R3a bundle → deterministic propose/validate/render; citations reference bundle items with locators; live E2E cited grounded answer + abstention |

## MILESTONE A — CORPUS_INGEST_READY

| Gate | Question | Status | Evidence |
|---|---|---|---|
| C1 | Does Stage-2 corpus-level canonicalization merge cross-document entities deterministically? | COMPLETE | ADR 0009 + migration 0005 + `canonicalize` stage: content-hash canonical ids, conservative SAME_AS/ALIAS_OF/DISTINCT/AMBIGUOUS policy, full lineage, replay-safe, order-independent (live E2E) |
| C2 | Does the canonical KG carry source/provenance links to every fact? | NOT STARTED | projects C1 registry into Neo4j (rebuildable); next gate |
| Q1 | Does extraction qualify on a heterogeneous corpus (mixed domains/types) with measured quality gates? | NOT STARTED | corpus qualification not run |
| I1 | Does a manifest drive bulk ingestion of many documents idempotently? | NOT STARTED | no manifest-based bulk controller |
| I2 | Does a corpus-scale integrity run prove receipts/projections/canonicalization converge at scale? | NOT STARTED | scale integrity not run |

**CORPUS_INGEST_READY = C1 + C2 + Q1 + I1 + I2 all COMPLETE.**

## MILESTONE B — RAG_V1_E2E

| Gate | Question | Status | Evidence |
|---|---|---|---|
| R2 | Do fused candidates get cross-representation reranking? | NOT STARTED | G3 reranker is a stub. BYPASSABLE for first /chat E2E; must be evaluated before becoming a default |
| M1 | Is the Polymath MCP contract defined (tools, inputs/outputs, versioning)? | NOT STARTED | no contract file exists |
| M2 | Does the Polymath MCP server implement the contract against the real orchestrator? | NOT STARTED | no server exists |
| M3 | Does Claude MCP E2E work against the server? | NOT STARTED | qualification not run |
| M4 | Does Hermes Agent MCP E2E work against the server? | NOT STARTED | qualification not run |
| M5 | Are MCP read/write/admin permission boundaries enforced and tested? | NOT STARTED | no boundary policy exists |
| R4 | Is graph expansion bounded and useful at real corpus scale? | IN PROGRESS | monotonicity unit-tested; scale/hub qualification not run |
| O2 | Are model weights pinned with recorded digests in production? | IN PROGRESS | TOFU digests; `POLYMATH_REQUIRE_PINNED=0` until digests recorded |
| O1 | Can a clean machine reproduce the pinned system and recover its data? | NOT STARTED | launchd/Makefile exist; clean-clone startup gate + backup drill not proven |
| A1 | Does a fresh agent on a fresh machine bootstrap, run the E2E, and pass acceptance? | NOT STARTED | full new-agent/new-machine acceptance drill |
| V1 | Is the RAG v1.0 checkpoint recorded with all evidence above? | NOT STARTED | release checkpoint |

## Empirical gates (the measured-delta discipline)

| Gate | Question | Status | Evidence |
|---|---|---|---|
| H1 | Does resource enrichment add correct facts without unacceptable incorrect ones? | COMPLETE (answered: NO) | Phase H v1.0 + v1.1; verdict REJECT for hybrid default; Δ +1/+4/−4 |

## Deferred measured improvement (NOT on the critical path)

| Gate | Question | Status | Evidence |
|---|---|---|---|
| E1-a | Do class-expanded triggers require resolved-roleset compatibility? | NOT STARTED | hypothesis only; `coin`-class trap fix experiment |
| E1-b | Must the FN anchor filter not reject on composed-only frame mismatch? | NOT STARTED | hypothesis only; restores 2 suppressed `developed` facts |
| D1 | Can additional controllers/providers be added without changing ingestion semantics? | NOT STARTED | deferred in PLAN.md |

E1 may be pulled back onto the critical path only if an E2E acceptance
test demonstrates that one of those extraction defects blocks the
production lexical path.

## The next unchecked gate

**C2** — canonical KG + provenance projection (Milestone A). Then
Q1 → I1 → I2 → **CORPUS_INGEST_READY**, then Milestone B
(R2 → M1–M5 → R4 → O2 → O1 → A1 → V1).

## Marking policy

- Mark COMPLETE only when the named evidence artifact exists and its
  tests pass at the checkpoint commit.
- Do not mark a gate COMPLETE because a related gate passed.
- A gate whose verdict was negative (H1) is COMPLETE when the question
  was answered with measured evidence — the verdict itself is recorded
  in CURRENT_STATE.md.
