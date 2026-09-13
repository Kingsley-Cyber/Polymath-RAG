---
change_id: COGNITIVE-ADAPTER-TRAIL-E2E-V1-E0
owner: king
date: 2026-09-13
last_reviewed: 2026-09-13
status: E0 deliverable — evidence-backed two-repo gap matrix (no runtime change)
architecture_impact: none by itself; names the smallest admissible E1/E2 Polymath slice, the Trail subgraph the E2E needs, and the exact owner actions
---

# COGNITIVE-ADAPTER-TRAIL-E2E-V1 — E0 two-repo evidence gap matrix

Every claim below carries a FILE:SYMBOL or ledger reference from a read-only audit of BOTH repositories (2026-09-13). "Not found"
means searched and absent. Nothing here was inferred from prose alone. Plan of record: `COGNITIVE-ADAPTER-TRAIL-E2E-V1-PLAN.md`.

## 1. Reconciliation (plan §2 gate, START-HERE bootstrap steps 1-8)

| fact | value |
| --- | --- |
| Polymath branch / HEAD | `handoff/unified-adapter-trail-e2e` (linked worktree `../polymath-v4-handoff`) = production `architecture/evidence-first-v5` 6b1edd5 + plan admission (11.257) + this E0. Production fleet runs from `polymath-v4` and never sees a branch switch. |
| Polymath status | worktree clean; guards green; register 11.258 after this slice |
| Forensic hold (plan §2 items 2-4) | **RECONCILED, not bypassed**: audit executed (11.253); hold LIFTED by owner directive and cinema pMAP backfill COMPLETE (11.255, 3,810 → 0 unresolved); control tick repaired (11.256). `AGENTS.md` item 000 now states this; the 0a hold text is historical. No frozen boundary blocks an adapter slice confined to `contracts/` + non-bundle `shared/` + `orchestrator/` + `workers/` + migrations. |
| TrailSignal authority | `origin/main` **6d7ef2a** (graph v2.8; PR #1 + PR #2 merged 2026-09-13 17:13/17:23Z). The owner's checkout `~/trail-signal-os` is at c5dd8a6, **75 commits behind**, with pre-existing uncommitted local edits (left untouched); the audit used a detached read-only worktree `~/trail-signal-os-worktrees/origin-main-e0`. |
| TrailSignal status | `agentctl doctor`/`status` PASS; ACTIVE_TASK A29 `complete`; ledger ends 2026-07-30 `A29 VERIFIED`; no open task; 1 recorded pre-existing failure ("P4V intentionally BLOCKED"). |
| TrailSignal corrected handoff | `docs/build/COGNITIVE_ADAPTER_E2E_GOAL.md` + `…_AND_TRAIL_E2E_PLAN.md` are SUPERSEDED pointers to the Polymath plan (owner correction 2026-09-13): Polymath is the composition root; Trail is a required internal subgraph entered only when dependency-admissible. |
| OCP / Polymath-bridge branches | `codex/ocp1-*`, `codex/ocp2-read-only-polymath-bridge`, `codex/a31-*` exist LOCALLY only (never pushed, not merged); `ResearchOperationBindingV1`, `EvidenceIngressManifestV1`, "opportunity control plane" — **not found on origin/main**. They are not authority. |

## 2. POLYMATH — current truth (audited at `architecture/evidence-first-v5` 6b1edd5 = handoff c32e43e runtime)

### 2.1 Production MCP surface
| item | evidence |
| --- | --- |
| server | `orchestrator/orchestrator/mcp_server.py` (POLYMATH-MCP-V2), `MCPServer(name="polymath")` line 69, `mcp>=2,<3` |
| process | supervisor slot `mcp` (`control/control/process_supervisor.py:71-72`), port `POLYMATH_MCP_PORT`=8930, bound 127.0.0.1, public host `mcp.kingsleylab.xyz`; backend `POLYMATH_ORCH_URL`=127.0.0.1:7200 |
| auth | `BearerGate` (`mcp_server.py:493`) — fail-closed: no `POLYMATH_MCP_API_KEY` ⇒ 503, mismatch ⇒ 401; `/health` outside the gate |
| tools (18) | `list_corpora`, `list_documents`, `upload_document`, `upload_text`, `document_status`, `corpus_status`, `retrieve` (FAST\|HYBRID\|GRAPH\|EXPLORE), `capabilities`, `compile_plan`, `retrieve_evidence`, `research_init/step/submit/status/corpus/report`, `ask`, `recent_queries` — canonical list `mcp_server.py:_TOOL_NAMES` (520), advertised by `capabilities.py:MCP_TOOLS` (33) |
| legacy surface | `mcp_server/polymath_mcp.py` (POLYMATH-MCP-V1): no supervisor slot; auth NOT fail-closed (empty key ⇒ open) — a liability the adapter migration closes |

### 2.2 `research_*` — the existing agent-driven loop (migration input, plan §10)
| concern | evidence |
| --- | --- |
| execution | OUT of process: `mcp_server.py:338 _research_cli` → `subprocess.run(research/python/controller.py …)`, env `OPPORTUNITY_RESEARCH_DB=research/state/mcp_runs.sqlite3` |
| workflow | `research/graph/control_graph.yaml` (`opportunity_research` v2.0.0, entry `understand`): node types transform×11 / reason×7 / agent×5 / retrieve×2 / gate×2 / terminal×1; ~40 deterministic executors `research/python/executors.py:EXECUTORS`; edge FACTS in `transitions.py`; `loop.yaml` terminals `SUCCESS, NO_OP, NO_DEFENSIBLE_BRIDGE, REJECTED, BLOCKED, STALLED, EXHAUSTED`, budgets max_cycles 8 / research_rounds 4; 39 JSON output schemas `research/schemas/*.json` |
| persistence | **no Postgres**: per-run JSON `research/state/{run_id}.json`; SQLite `runs / work_nodes / work_edges / actions (one live action per run) / events / checks / context_envelopes` (`research/sql/001_initial.sql`, `002_context.sql`); derived `_corpus_payload.json`, `_report_model.json`, `_report.html`. `research/state/` is `repo_guard` IGNORED (ungoverned, unbacked) |
| step issue / submit | `controller.py:364 cmd_step` (terminal immutability → pause → `memory.check_drift` fail-closed on graph/policy/loop/schema/prompt hashes → frozen ContextEnvelope + `needs{prompt_file, submit_keys}`); `controller.py:201 cmd_submit` (in-order only; per-item JSON-Schema validation; lineage refs fail-closed; `capability_failure` only on agent/retrieve nodes) |
| Polymath seam | HTTP only — `research/python/corpus_polymath.py`: `POST /retrieve`, `POST /retrieve/plan`, `POST /chat`, `GET /capabilities` |
| tests | `research/tests/run_all.py` (+ CI `research-harness.yml`); **no test of the `research_*` MCP handlers or the subprocess seam** (`tests/determinism/test_mcp_server_v2.py` covers auth + tool existence only) → the §10 equivalence proof has no baseline harness yet |

### 2.3 Reusable run / receipt / artifact / control primitives (what can host an adapter run)
| primitive | records | hosts a generic adapter run + typed steps without a new table? |
| --- | --- | --- |
| `runs` (0001:8, 0012, 0015, 0029) | run_id, **corpus_id NOT NULL**, status CHECK `intake/reconciling/query_ready/degraded/failed/superseded`, execution/semantic contract pins, supersession chain | **No** — ingestion-shaped identity and lifecycle; no adapter/workflow/schema versions, no typed gap, no agent identity |
| `stage_tickets` (0012 +0027/0032/0052) | stage (free text), event_type, generation, required_artifacts/receipts JSONB, lease, status CHECK `pending/ready/leased/done/failed/repair/superseded`; `UNIQUE(run_id, stage, generation)` | **No** — no step_id/step_type, **no per-step payload/schema**, no external-operation ref; re-entering a step type collides with the UNIQUE key |
| `artifacts` (0002:104) | `artifact_id = sha256(run\|stage\|payload)`, payload JSONB, `UNIQUE(run,stage,contract_hash)`; ON CONFLICT **merges** payloads | Partly — can hold `AdapterResultV1`; no step_id; merge-not-version semantics |
| `receipts` (0002:115) | status CHECK `committed/failed`, error, wall_clock | **No** — no typed gap, model/agent identity, step id |
| `outbox_events` (0002:131) | event_type free text, payload JSONB, `idempotency_key` UNIQUE (content hash) | **Yes** — the step-dispatch bus as-is |
| `llm_provider_attempts` (0056) | correlation/run/ticket, lane/provider/model/account_env, admitted/dispatched/status | nearest `ExternalOperationReceiptV1` analogue but LLM-shaped (no external_system/operation_id/record_ids/poll cursor) |
| `stage_attempts`, `worker_registrations`, `control_leases`, `dead_letter_archive` | retry ledger, worker identity, leases | reusable as-is |
| control tick | `control/control/tickets.py` `STAGE_DAG` (static linear list, minted whole by `ensure_run_tickets`), `NON_BLOCKING_STAGES`, side stages that **mint their own READY tickets** (`doc_parent_map`, `parent_enrichment` — the existing non-chain producer precedent; guarded 11.256) | **BRANCH/loop cannot be expressed** in the chain; the side-stage pattern is the admissible shape for an adapter step producer (not a second scheduler) |
| worker runtime | `worker_runtime.claim_ticket_events` (107, FOR UPDATE SKIP LOCKED, fail-closed on `ready`), `complete_ticket` (266), `_lease_keeper` (289), `run_worker` (359); `receipts.stage_transaction` (41) = artifact + receipt + status + outbox in ONE transaction | reuse unchanged — this is the typed-step commit point |

### 2.4 Knowledge entry points an adapter step calls in-process
| step | entry point |
| --- | --- |
| POLYMATH_RETRIEVE | `orchestrator/api/retrieve.py:722 retrieve` / `:169 _retrieve_impl`; modes `shared/polymath_shared/retrieval_modes.py` (FAST/HYBRID/GRAPH/LEGACY/WILDCARD; **DEFAULT = LEGACY, frozen** → always pass a mode); evidence rows `orchestrator/api/evidence_rows.py:211 build_evidence_rows` per `contracts/retrieve/v1/evidence_row.schema.json` |
| POLYMATH_COMPILE_PLAN | `orchestrator/api/corpus_plan.py:117 compile_plan` (deterministic 3–5 reformulations), chat compiler `shared/polymath_shared/chat_plan.py:512` |
| POLYMATH_GRAPH_EXPAND | `orchestrator/api/retrieve.py:630 _neo4j_expand` (one hop, corpus-authorized, HIGH_MEDIUM allowlist; `retrieval.py:297 graph_expansion`, caps 8 seeds / 20 facts) |
| parent-MAP localization | `shared/polymath_shared/document_profile/parent_map_projection.py` (`search_parent_maps`), rows `document_parent_maps` (0054) — cinema now 100% covered (11.255) |
| latent / enrichment | `shared/polymath_shared/latent/*` (gate, runtime, compiler, projection, trigger) |
| provenance identities | `documents`, `chunks`, `facts`, `evidence` (0002), `claim_sets` + `entity_merge_receipts` (0026), `query_receipts` (0047) |
| capability advertisement | `orchestrator/api/capabilities.py:CONTRACTS/ENDPOINTS/MCP_TOOLS` — where `adapter_*` must be declared |

### 2.5 Admission machinery an adapter boundary must satisfy
- `ARCHITECTURE.md §4` (10 owned paths): "No top-level path is added directly … name its owner, update `architecture/dependencies.json`, add a refactor entry, declare in TREE."
- `architecture/dependencies.json`: owners contracts/shared/orchestrator/worker/control/sidecar/store/governance with `may_depend_on`; 10 forbidden import pairs; change triggers (contracts→verification+work log; dependencies.json→ADR+refactor+changelog+work log; migrations→replay proof+rollback+work log; scripts→registry+work log).
- **Ownership hole**: `research/` and `mcp_server/` are NOT owners → `repo_guard.check_forbidden_imports` skips them (`repo_guard.py:212,219`). The adapter must live under existing owners (`contracts/`, `shared/`, `orchestrator/`, `workers/`), never in an unowned tree.
- Companion cascade (`repo_guard.py:261`): touching `ARCHITECTURE.md` or `dependencies.json` ⇒ changelog + ADR + refactor + work log; `scripts/` ⇒ registry + work log; `contracts/`, migrations ⇒ work log. Next free ADR = **0018**; next refactor = **0012**.
- Contracts: `contracts/README.md` — version N frozen at release; new domain `contracts/adapter/v1/` with `*.schema.json` + `*.example.json` + a `tests/contracts/` test (CI `contracts.yml`).
- CI to keep green: `repo-governance`, `contracts`, `determinism` (Postgres 16 + all migrations), `agent-preflight`, `research-harness` (paths research/**).

### 2.6 Frozen / forbidden boundaries in force
| fence | rule for the adapter |
| --- | --- |
| `config/semantic_bundle.lock` (8 members: entity_admission_policy.yaml, entity_knowledge_admission.py, llm_extraction/gate.py, workers/llm_direct.py, identity_allocation.py, entity_harbor.py, admission_interpreter.py, source_region.py) | never touch; pinned per run as `runs.semantic_bundle_sha256` |
| stale-bundle fence (`process_supervisor.py` ~515-555) | any `workers/` or bundle-member `shared/` edit ⇒ fleet bounce; orchestrator/control-only edits do not trip it (work-log 2026-09-12 retrieve-graph-wildcard) |
| Parent-MAP forensic hold | **RECONCILED**: audit executed (11.253); hold LIFTED by owner directive and the cinema backfill COMPLETED (11.255). `AGENTS.md` item 0a still carries the STOPPED text — corrected in this slice. The adapter never touches the pMAP path anyway (`contracts/` + non-bundle `shared/` + `orchestrator/` + migrations). |
| frozen eval assets | `i4/gold/`, `admission/artifacts/`, `sealed/` — never read/write from adapter tests |
| frozen retrieval default | `DEFAULT_MODE = MODE_LEGACY` — a retrieve step passes an explicit mode |

## 3. TRAILSIGNAL — current truth (audited at origin/main 6d7ef2a)

### 3.1 Governance a Polymath caller must respect
- **LAW 1** (`docs/build/laws.md`): "An LLM never computes, assigns, ranks, normalizes, weights, or writes an opportunity score"; scoring code cannot import provider/MCP/planning/acquisition/extraction adapters. **LAW 2**: every derived artifact has immutable lineage to every input; orphans cannot be promoted/scored. "These laws are not relaxed by an ADR."
- Admission (`docs/build/autonomous_build_contract.md` §1-4): read gate with content hashes → `gap_matrix.csv` (closed status vocabulary MISSING/PLACEHOLDER/TEST_ONLY/PARTIAL/WORKING/BLOCKED/UNKNOWN/SUPERSEDED) → `slice.yaml` (owners, adrs, gap_claims, contracts, production_entrypoint, change_baseline, rollback_boundary) → immutable baseline via `scripts/architecture/validate_v2_governance.py --capture-run-baseline` → VERIFIED only when the PUBLIC production path passes (fixtures/direct calls = TEST_ONLY). Build-run dir = exactly `intent.md, gap_matrix.csv, slice.yaml, journal.jsonl (append-only), verification.json, rollback.md`; secrets/cookies/page bodies/raw provider results forbidden in run records.
- Guard-protected paths (`.agent-control/policy.json:guard.protected_paths`): `AGENTS.md, build_graph_v2.yaml, progress_ledger_v2.csv, docs/adr, docs/build/laws.md, db/migrations/v2, schemas/registry.yaml, scripts/architecture, gates, fixtures/cassettes`. An agent may draft a Proposed ADR but cannot accept it (`docs/adr/README.md:Lifecycle`).
- Polymath may: call the authenticated MCP tools below, poll, page, hold Trail ids. Polymath may not: score, receive raw bytes/credentials, treat discovery output as evidence, write CSV/Postgres/blob, promote without a registered deterministic mapping.

### 3.2 Build graph state (`build_graph_v2.yaml` v2.8 ↔ `progress_ledger_v2.csv`, no drift)
| node | rank | status | depends_on | note |
| --- | --- | --- | --- | --- |
| A0–A29, M1 | 10–78 | VERIFIED | — | governance chain complete through ADR-060 (owner-accepted 2026-07-29) |
| P1 | 50 | BLOCKED | A3 | superseded by P1R |
| **P1R** static raw crawl | 57 | **VERIFIED** | A4 | `crawl.submit` → Temporal `TrailSignalStaticCrawlV1` |
| **P2** deterministic extraction | 65 | **VERIFIED** | A7 | `extract.submit` → `TrailSignalDeterministicExtractionV1` |
| **P3** static batch streaming | 70 | **VERIFIED** | A10 | `scrape.submit` (1–64 items) → `TrailSignalStaticBatchV1` |
| P4 bounded dataset query/export | 95 | BLOCKED | A25 | ADR-056 terminalized honestly; P4V sole successor |
| P4V | 108 | BLOCKED | A28 | "security remediation boundary": 22 unreviewed Go advisories in MinIO/mc source pins; resolved by **ADR-060 (Accepted) + A29 (VERIFIED)** → successor P4W |
| **P4W** | 112 | PENDING (admissible) | A29 ✅ | signed snapshot, READY advisory receipt, MCP→HTTP export canary, Graphify, two full suites — **agent work, no owner action outstanding** |
| **P5** SearXNG discovery | 91 | **VERIFIED** (2026-07-27) | P1R + A14–A21 | `discover.submit` → `TrailSignalSearxngDiscoveryV1`, queue `trail-signal-v2-discovery`; needs the EXISTING SearXNG at `:8080` (never a second instance) |
| P6/P7/P8 | — | SUPERSEDED | — | by P7R / [P6R,P7R] / P8R (ADR-039: external engines, one engine per physical request) |
| **P6R** Crawl4AI PUBLIC_JS capture | 100 | PENDING (admissible; **lowest by selection rule**) | P3, A13 | JS-rendered pages |
| **P7R** Playwright-MCP recipes | 110 | PENDING (admissible) | P3, A13 | `browser.run_recipe`; logged-in / interaction-gated sources |
| **P8R** governed semantic extraction | 120 | PENDING (admissible) | P2, A13 | Crawl4AI/LiteLLM with registered `schema_ref` or bounded `ad_hoc_spec`; **provider egress + credential rotation** required |
| P9 generic platform canary | 130 | PENDING | M1, P4W, P5, P6R, P7R, P8R | `system.status` tool (`tools/system.py` — not found) |
| P10 media | 140 | PENDING | P8R + **ADR-014 (Proposed)** | not on the product-discovery path |
| **C1** commerce planning evidence | 150 | PENDING | P9 | `commerce.research.submit/status` — evidence promotion + hard gates |
| **C2** deterministic score + dossier | 160 | PENDING | C1 | `commerce.research.result` — the ONLY lawful score source (LAW 1) |
| **Q1** commerce graph + search | 170 | PENDING | C1 | projections |
| **C3** commerce production canary | 180 | PENDING | C2, Q1 | end-to-end commerce canary |
| S-* sources, AP1/AP2 | 190–260 | PENDING | P9 (+P10 / ADR-011) | breadth, after the core |

Graph invariant: "Commerce is a workload and cannot be a prerequisite for the generic platform core."

### 3.3 Working / verified production operations today
| capability | state | public contract | durability |
| --- | --- | --- | --- |
| discovery | **WORKING** (P5) | `discover.submit(DiscoveryRequestV1{query ≤512B, categories[general], language, time_range, safe_search, page_number 1-10, maximum_candidates 1-64, purpose_ref, idempotency_key}) → OperationRefV1`; results via `result.page(ResultPageRequestV4{target_kind:"URL_CANDIDATE_RESULT"}) → OperationResultPageV2.url_candidate_page` (≤64/page, cursor `^cursor:[A-Za-z0-9_-]{32,128}$`) | Temporal; raw SearXNG bytes committed to blob first |
| lead record | **hard-typed non-evidence**: `UrlCandidateV1.record_class = "OPERATIONAL_LEAD"`, `evidence_eligible = False` (frozen Literals); lineage parents enforced (LAW 2) | — | — |
| acquisition (static) | **WORKING** (P1R, P3) | `crawl.submit(CrawlRequestV1)`, `scrape.submit(BatchCrawlRequestV1 1–64 items)` → `OperationRefV1` | Temporal |
| extraction (deterministic, stored artifact) | **WORKING** (P2) | `extract.submit(ExtractionRequestV1)` → `OperationRefV1`; results paged | Temporal |
| operation lifecycle | **WORKING** | `operation.get(OperationRefV1) → OperationStatusV4`; `operation.command(OperationCommandV1{CANCEL\|PAUSE\|RESUME, expected_revision, idempotency_key})`; FAILED/CANCELLED expose **no outputs** | — |
| datasets (bounded query / export / HTTP export read) | **REGISTERED, NOT VERIFIED** (P4/P4V BLOCKED; retained publication fail-closed, advisory NOT_READY) | `dataset.query → DatasetQueryDeliveryV1` (≤64 rows, single-use 1-h cursors), `dataset.export → OperationRefV1`, `GET/HEAD /v2/exports/{id}` | do not depend on it until P4W |
| JS / browser / semantic extraction | **MISSING** (P6R/P7R/P8R) | — | — |
| evidence promotion + gates, deterministic scoring, experiment/report/portfolio | **v1 CSV ONLY, not reachable from v2**: `signal_engine/score.py` has zero importers in `src/`; runs only via `niche-research score --input data/niche_candidates.csv` (`src/niche_research/cli.py`) — inside ACP prohibited paths (`data/`, `signal_engine/`) | none in v2 (C1/C2) | — |
| `system.status` / platform canary | **MISSING** (P9) | — | — |

### 3.4 Data authority
v1 `data/*.csv` (append-only ledger for the v1 toolkit) and v2 Postgres (`db/migrations/v2/1000…1006`, 38 `v2_*`/`platform_*` tables: operations, raw_artifacts, lineage_edges, document_results, datasets, snapshots, query results/cursor grants, export manifests/fences/read decisions) + immutable blob (`trail-signal-raw` via VersityGW `:7070`; `trail-signal-exports` MinIO Object-Lock behind HAProxy `:19000`) are **disjoint truths; a v1 record is never dual-written into v2** (`AGENTS.md:File behavior`). Raw-first: bytes are hashed and committed before parsing; ≤8 MiB activity-local reads; "raw bytes never enter Temporal, MCP, contracts, logs, or evidence storage".

### 3.5 Public contracts Polymath may lawfully call (all at origin/main)
- Transport: one authenticated FastMCP streamable-HTTP daemon, `http://127.0.0.1:8767/mcp` (`.mcp.json` and daemon default now agree; 8766 = v1 history), `stateless_http`, `json_response`, `strict_input_validation`, JWT HS256 (`config/v2/principals.yaml`, `default_authorization: deny`), request-body byte ceiling.
- Tools register by `principal_contract_major`: `crawl.submit`, `extract.submit` (always); `scrape.submit`, `dataset.query`, `dataset.export` (≥3); `operation.get`, `operation.command`, `result.page`, `discover.submit` (≥5). All four existing principals (`codex-local`, `claude-code-local`, `opencode-local`, `zai-local`) carry the 10-capability `PrincipalCapabilityV5` set → v5 branch live. Budget `p1-static-default-v1`: 4 concurrent ops, 3600 s, 8 MiB, 5 redirects, 3 attempts.
- **No Polymath principal exists.** Adding one = `config/v2/principals.yaml` entry + bearer alias in `config/v2/secrets.yaml` (scoped to `http://127.0.0.1:8767/mcp`) — a config edit under guard/ACP-protected `config/v2` → **owner action** (or an owner-authorized task with `authorized_protected_paths`).
- Idempotency: every submit carries `idempotency_key`; `operation.command` carries `expected_revision`; duplicates + restarts yield one logical operation.

### 3.6 Trail blockers (owner vs agent)
| # | blocker | class |
| --- | --- | --- |
| T1 | No Polymath principal/secret | **owner/config** (protected path) |
| T2 | Temporal `127.0.0.1:7233` ns `trail-signal-v2` (6 queues), Postgres `:15433`, VersityGW `:7070`, MinIO/HAProxy `:19000`, SearXNG `:8080`, Docker engine + macOS LaunchAgent export worker | **external services** must be up for any live run |
| T3 | P4W (datasets/export) unverified — READY advisory receipt + canaries + two skip-free suites | agent work (A29/ADR-060 already accepted) |
| T4 | P6R / P7R / P8R unbuilt (JS, browser, semantic extraction); P8R needs provider egress + rotation of a disclosed credential | agent work + **owner secret rotation** |
| T5 | P9 unbuilt (`system.status`, canary) | agent work |
| T6 | **C1 → C2/Q1 → C3 unbuilt** — no v2 evidence promotion, no v2 deterministic score, no `commerce.*` tools | agent work, behind P9 |
| T7 | Selection-rule tension: lowest admissible = P6R (100) while ADR-060/A29 narrate P4W (112) next | **owner/governance call** on ordering |
| T8 | 14 pre-existing full-suite failures carried since `6cd1070` (owning slices must remediate) | pre-existing debt |

## 4. CROSS-SYSTEM — proposed boundary, ownership, semantics, acceptance

### 4.1 One contract boundary: Polymath → TrailSignal
Polymath calls TrailSignal ONLY through Trail's authenticated FastMCP streamable-HTTP daemon (`/mcp`, JWT HS256, a dedicated
Polymath principal with the capability set below; port pinned explicitly — the checked-in `.mcp.json` says 8766, the daemon
default is 8767). The connector is ONE owned worker-side client (`workers/…` or a shared typed client that `workers` may
import), never a private import of Trail code, never a Trail CSV/Postgres/blob access.

| Polymath step (closed vocabulary) | Trail public operation used | Trail contract in → out |
| --- | --- | --- |
| EXTERNAL_OPERATION `trail.discover` | `discover.submit` (P5 — see §3) → `operation.get` → `result.page` | discovery request → `OperationRefV1` → `OperationStatusV2` → paged **leads** (never evidence) |
| EXTERNAL_OPERATION `trail.crawl` | `crawl.submit` / `scrape.submit` (1–64 items) → `operation.get` → `result.page` | `CrawlRequestV1` / `BatchCrawlRequestV1` → `OperationRefV1` → `ResultPageResponseV1` (raw-artifact refs; bytes never cross) |
| EXTERNAL_OPERATION `trail.extract` | `extract.submit` → `operation.get` → `result.page` / `dataset.query` | `ExtractionRequestV1` → `OperationRefV1` → document results / dataset rows (≤64 rows, ≤131,072 bytes, single-use 1-h cursors) |
| EXTERNAL_OPERATION `trail.evidence` / `trail.score` | `commerce.research.submit/status/result` (C1/C2 — **planned, not built**) | promotion + deterministic score by Trail only (LAW 1) |
| cancel | `operation.command {CANCEL, expected_revision, idempotency_key}` | `OperationStatusV2` |

Every Trail call carries a Polymath-minted `idempotency_key` derived from `(adapter_run_id, step_id, attempt)` so a retried
step re-attaches to the same Trail operation instead of double-submitting (Trail checks idempotency before cursor consumption).

### 4.2 What Polymath stores vs what Trail owns
| Polymath stores (inside the adapter run) | Trail owns (never copied) |
| --- | --- |
| `ExternalOperationReceiptV1`: `external_system="trailsignal"`, `operation_id`, `operation_kind`, `temporal_workflow_id/run_id`, `status_revision`, submitted/terminal timestamps, terminal phase+outcome, the `idempotency_key`, `principal`, and the list of **record/dataset/export ids** returned | raw artifacts, lineage edges, datasets, snapshots, query results, export manifests, evidence promotion state, gates, scores, Temporal history |
| bounded **projections** of Trail results needed for reasoning (lead URLs + titles, extracted fields per record id, score values with record ids) — each row keyed by the Trail record id it came from | the records themselves and their bytes |
| Polymath evidence lineage (`evidence_row` ids: doc_id/chunk_id/fact ids, query receipts) for every knowledge step | — |
| the terminal `AdapterResultV1` joining Polymath evidence ids + Trail operation/record ids + Trail scores + experiments | — |

### 4.3 Failure / cancel / retry / idempotency (end to end)
| situation | behaviour |
| --- | --- |
| Trail submit fails (4xx/5xx/timeout) | step receipt = typed failure (`EXTERNAL_SUBMIT_FAILED`); bounded retry with the SAME idempotency key; after budget → run status `terminal_gap` with the gap typed, never a fabricated result |
| Trail operation FAILED / CANCELLED | Trail exposes **no outputs** for those (`OperationStatusV1.validate_lifecycle`); Polymath records the terminal receipt and either branches (evidence-gap loop) or ends with a typed gap; a Trail FAILED is never re-labelled a source gap |
| Trail operation PARTIAL | partial outputs paged; the step records `partial=true` and the contradiction/unknown survives into the result |
| adapter_cancel | Polymath marks the run `cancelled`, then issues `operation.command CANCEL` for every non-terminal Trail operation it owns (best effort, receipted); accepted submissions are kept (immutable), never rolled back |
| orchestrator/worker restart mid-step | steps are `stage_tickets`-leased; the lease keeper renews; an expired lease returns the ticket to READY; an in-flight Trail operation is re-polled by `operation_id` (never re-submitted) |
| agent submits twice / out of order | `adapter_submit` is idempotent on `(run_id, step_id, submission_hash)`; out-of-order or already-accepted steps are rejected with the current `AdapterRunStatusV1` |
| poll storms | `operation.get` on a bounded backoff (Trail budget: 4 concurrent ops / principal); cursors are single-use — a replayed page must reuse the rotated token, never the consumed one |

### 4.4 Final acceptance commands (what "done" is measured by)
```text
# Polymath (one MCP connection, bearer POLYMATH_MCP_API_KEY)
adapter_list()                                  -> contains trail.product_discovery + substack.article_development
adapter_start("trail.product_discovery", input) -> AdapterRunRefV1{run_id}
loop: adapter_next(run_id) -> AdapterStepV1 (AGENT_REASON ...) ; adapter_submit(run_id, step_id, payload)
adapter_status(run_id)                          -> terminal
adapter_result(run_id)                          -> AdapterResultV1 with Polymath evidence ids + Trail operation/record ids + Trail scores
# restart proof: kill the adapter worker (and the orchestrator) between adapter_next and adapter_submit; the same run resumes
# Trail side (read-only verification, never called by the client): operation.get on every operation_id in the result
```
Observable proof list = plan §"FINAL PRODUCTION ACCEPTANCE" items 1–10, each mapped to a receipt row or log line.

## 5. GAPS — dependency-ordered, both repositories

### 5.1 Polymath gaps to a generic adapter run (ranked)
1. **No adapter run identity** — `runs` is corpus-scoped with an ingestion-only status CHECK; no adapter/workflow/retrieval-policy/schema versions, typed gap, agent identity.
2. **No typed step object** — `stage_tickets` has no step_id/step_type/per-step payload-or-schema; `UNIQUE(run_id, stage, generation)` forbids re-entering a step type.
3. **No branch/loop authority** — `STAGE_DAG` is a static linear chain minted whole; `BRANCH` cannot be expressed; the admissible shape is the existing side-stage "mint your own READY ticket" producer, not a second scheduler.
4. **No external-operation reference** — nothing joins a run/step to `{external_system, operation_id, record_ids, terminal receipt, poll cursor}` (`llm_provider_attempts` is LLM-shaped).
5. **`receipts` cannot express a step receipt** (status `committed/failed` only; no typed gap, model/agent identity, step id).
6. **Two workflow authorities already exist** (Postgres tickets vs `research/` SQLite+JSON, bridged by subprocess); plan §10 forbids leaving both.
7. **Research state is ungoverned** (`research/state/` repo_guard-ignored; no migrations/backup).
8. **`research/` and `mcp_server/` sit outside the layer map** (import guard skips them); the adapter must live under owned trees.
9. **No `contracts/adapter/v1`** and no contract tests.
10. **No `adapter_list` capability channel** (`capabilities.py:MCP_TOOLS`).
11. **No MCP-level test of the `research_*` loop** → no equivalence baseline for §10 migration.
12. **Restart survival is proven for ingestion stages only**; no `awaiting_submission`-style state exists for a step waiting on an external agent.

### 5.2 Trail missing path to a scored candidate (dependency-ordered)
P6R → P7R → P4W → P8R → P9 (`system.status`) → C1 (evidence promotion + gates, `commerce.research.submit/status`) → C2 (deterministic score, `commerce.research.result`) ∥ Q1 → C3. **Today Polymath can lawfully obtain: discovery leads, static acquisition, deterministic extraction, paging, cancellation. It cannot obtain a Trail-authored score or Trail-promoted evidence from any v2 call.** The plan's final acceptance items 5-6 (real evidence/scoring; deterministic non-LLM score) are therefore gated on Trail E3 completing at least through C2.

### 5.3 Owner actions (cannot be done by the agent)
| # | action | unblocks |
| --- | --- | --- |
| O1 | Add a `polymath` principal + bearer secret alias in Trail `config/v2/{principals,secrets}.yaml` (or authorize a task with those protected paths) | E4 connector auth against the live daemon |
| O2 | Decide Trail ordering: P6R first (selection rule) vs P4W first (ADR-060/A29 narrative) | E3 sequencing |
| O3 | Rotate the disclosed LongCat credential and authorize provider egress for P8R | E3 semantic extraction |
| O4 | Confirm the external services for a live E2E (Temporal, Postgres :15433, VersityGW, MinIO/HAProxy, SearXNG :8080, Docker/LaunchAgent) are to be run on this host | any live acceptance run |
| O5 | Merge PR #3 when green (owner directive: only when green) and accept ADR-0018 (Polymath adapter boundary) when proposed | E1 |

## 6. Smallest admissible E1/E2 slice (Polymath) — what E1 will propose
Reuse unchanged: `receipts.stage_transaction` (artifact + receipt + status + outbox in one transaction), `outbox_events` (content-hash idempotency) as the step bus, `stage_tickets` leasing + `_lease_keeper` for crash resume, `artifacts` for `AdapterResultV1`, the side-stage own-ticket precedent, in-process knowledge entry points (`corpus_plan.compile_plan`, `evidence_rows.build_evidence_rows`, `retrieve._neo4j_expand`, `retrieval.graph_expansion`), `mcp_server.BearerGate` + `_TOOL_NAMES` + `capabilities.MCP_TOOLS`.
Add (minimum): `contracts/adapter/v1/*` (manifest, run_ref, run_status, step, submission, step_receipt, external_operation_receipt, result) + examples + `tests/contracts/test_adapter_contract_v1.py`; `shared/polymath_shared/adapter/` (pure: closed step enum of 8, manifest loader, JSON-Schema submission validator, transition table — `shared` may depend on `contracts`, so no `ARCHITECTURE.md`/`dependencies.json` edit); ONE migration `0061_adapter_runs.sql` (`adapter_runs`, `adapter_steps` with step receipts and an `external_operation_ref JSONB` reserved for E4 — justified by gaps 1/2/4/5); seven thin MCP tools in `orchestrator/mcp_server.py` (orchestrator-only edits do not trip the stale-bundle fence); `workers/workers/adapter_step_worker.py` on `worker_runtime.run_worker` (fleet bounce at the end); ADR-0018 + refactor 0012 + work-log; tests incl. one integration test start → POLYMATH_RETRIEVE → AGENT_REASON issue → forced restart → submit → COMPILE_RESULT. Out of E1/E2: any Trail call, any `research_*` deletion (equivalence baseline first), any bundle-member edit.

## 7. Verification commands (exit codes at time of writing)
```text
polymath (handoff worktree): agent_preflight.py 0 · repo_guard.py 0 · wiki_worm.py --check 0 · determinism (CI) — see PR #3 checks
trail (origin/main worktree, read-only): agentctl doctor 0 · agentctl status 0 (A29 complete; no open task)
```
