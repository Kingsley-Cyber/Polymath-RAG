# Polymath v4 architecture

Status: accepted baseline  
Change policy: frozen by default  
Machine-readable dependency map: `architecture/dependencies.json`

This document defines the target system. A generated file, placeholder,
test, or directory does not prove that a capability works. `PLAN.md`
records the dependency-ordered path from this scaffold to production.

## 1. Outcomes and boundaries

Polymath is a local-first GraphRAG workbench. It ingests source material,
extracts evidence-backed facts, builds searchable projections, and serves
answers that retain document and span provenance.

The rebuild has five required outcomes:

1. A restart cannot erase accepted work or strand a run.
2. GPU and Apple Silicon models run as host-native processes, not inside
   Docker.
3. One registry answers where every model service lives and which release
   it runs.
4. Relation semantics come from a deterministic compiler. Models propose
   spans; they never choose graph predicates.
5. Every run can be traced through structured logs and durable Postgres
   receipts using the same identifiers.

The first release is local-first and single-operator. Remote CUDA and cloud
providers are later adapters behind the same sidecar contract. They are not
allowed to create a second workflow, identity scheme, or persistence path.

## 2. Physical topology

The Mac is the initial application and model host.

```text
macOS host
  polymath-api       HTTP intake and read surface
  polymath-control   desired-state census and scheduling
  polymath-worker-*  durable stage consumers
  gliner-runtime     one resident GLiNER model, called twice per chunk
  embedder           one resident embedding model
  reranker           one resident reranking model
  launchd            process supervision and stable startup

Docker Compose
  Postgres           workflow authority and receipts
  Redis              wakeups and disposable cache
  Qdrant             vector projection
  Neo4j              graph projection
```

Compose binds store ports to loopback for host-native clients. No model,
control loop, worker, or API process lives in Compose. A later deployment
may containerize CPU-only application processes, but that requires an ADR
and a clean-clone deployment proof.

Remote hardware registers as another sidecar URL with a pinned manifest.
The application does not contain hostnames, LAN addresses, or provider-
specific routing branches. Those values live in `sidecars/*.toml`.

## 3. Process roles

| Role | Owns | Must not own |
|---|---|---|
| `orchestrator` | HTTP validation, intake, reads | scheduling or model loading |
| `worker` | one durable stage and its receipt | user-facing HTTP or process supervision |
| `sidecar-gpu` | one resident model and inference contract | workflow state or predicate policy |
| `sidecar-cpu` | one CPU service and inference contract | GPU state or workflow authority |
| `store` | persistence for one engine | business decisions |
| `control` | census, scheduling, recovery, heartbeats | user requests or inference |

Every running process has one role. Shared packages are libraries, not a
seventh process. Repository governance is a change lane, not a runtime role.

## 4. Directory ownership

| Path | Authority |
|---|---|
| `contracts/` | versioned wire schemas between processes |
| `architecture/` | machine-readable owners and dependency edges |
| `orchestrator/` | API entrypoints only |
| `workers/` | stage consumers and deterministic orchestration |
| `control/` | desired-state reconciliation and recovery |
| `sidecars/` | registry entries and one-model runtimes |
| `shared/` | identity, receipts, typed clients, logging |
| `stores/` | migrations and projection-specific setup |
| `docs/wiki/` | decisions, refactors, experiments, work logs |
| `scripts/` | declared repository management commands |

No top-level path is added directly. The change must first name its owner,
update `architecture/dependencies.json`, add a refactor entry, and declare
the path in the scaffold `TREE`.

## 5. Stack and authority

| Concern | Choice | Authority rule |
|---|---|---|
| Language | Python, with the supported floor pinned in each package | one lock set must reproduce every host process |
| API | FastAPI, Pydantic, Uvicorn | API validates and delegates; it does not schedule |
| Model runtime | GLiNER through PyTorch on macOS MPS or CPU | one resident model in `gliner-runtime` |
| Workflow state | Postgres | only source of truth for runs, attempts, receipts, outbox, settings, and heartbeats |
| Wakeups | Postgres outbox plus Redis notification | Redis loss cannot lose accepted work |
| Vector search | Qdrant | rebuildable projection from Postgres-backed artifacts |
| Graph search | Neo4j | rebuildable projection from accepted facts |
| Observability | JSON logs, OpenTelemetry context, Loki-compatible collection, Grafana views | logs explain execution; Postgres proves state |
| Tests | pytest and JSON Schema validation | tests traverse public contracts and remain immutable during fixes |
| Deployment | launchd for host processes, Compose for stores | clean-clone startup is a release gate |

Postgres replaces Mongo because the commit point spans the stage result,
receipt, status transition, and outbox event. Those writes belong in one
transaction. JSONB is used for payloads that do not need relational columns.

## 6. Authoritative data model

`runs` records accepted work and its current certified state.
`stage_attempts` records a stage execution keyed by canonical input and
contract release. `outbox` records work that must be delivered. The control
heartbeat records which controller instance last completed a census.

The first migration is a scaffold, not a final schema. Each production
stage must prove this transaction:

```text
write durable stage artifact
write or complete stage receipt
transition run state
append outbox event when downstream work is required
commit once
```

Qdrant and Neo4j do not become authorities. Projection writers record their
source artifact identity and compiler release, then emit receipts. The
control plane can compare desired artifacts with observed receipts and
schedule repair without trusting a process-local queue.

## 7. Ingestion and extraction path

The production path is deliberately narrow:

```text
POST /ingest
  -> normalize bytes and compute document identity
  -> persist source artifact plus run and outbox event
  -> intake worker parses and chunks
  -> extract worker calls gliner-runtime with task=entity
  -> extract worker calls the same runtime with task=evidence
  -> predicate compiler joins spans and applies versioned rules
  -> accepted facts and evidence are persisted with a receipt
  -> projection workers update Qdrant and Neo4j
  -> control census certifies query_ready when required receipts exist
```

The API returns after the intake transaction commits. It does not wait for
model inference. A process crash after commit leaves enough Postgres state
for the controller to schedule the missing stage again.

## 8. Two-pass GLiNER contract

The two passes are logical tasks served by one host-native runtime. Loading
the same weights in two Mac processes would duplicate memory and model
startup cost. A measured experiment may justify separate processes later;
until then one resident model is the accepted topology.

Pass 1 returns typed entity spans. Its label set is the core ontology plus
the active domain profile. Pass 2 returns evidence spans from a versioned
evidence-label inventory. Both responses include source offsets, scores,
model identity, model revision, label-set release, and request identity.

The deterministic compiler owns:

- argument pairing and direction;
- predicate selection;
- negation, modality, attribution, and temporal qualifiers;
- ontology validation;
- stable fact and evidence identifiers;
- the decision to emit no fact.

The compiler input and output are versioned contracts. The same normalized
input, compiler release, rule pack, and ontology release must produce the
same bytes. Model scores are evidence for a proposal, not graph policy.

Performance and quality are release evidence, not guessed configuration.
`PLAN.md` requires a target-Mac experiment that records model load time,
resident memory, per-pass latency, combined latency, throughput, and an
error review on an approved corpus sample. Thresholds and batching are not
pinned until that experiment exists.

## 9. Control plane

`polymath-control` is independent from the API and workers. It reads the
desired artifact set for each active run, compares it with committed
receipts, and schedules only missing work. Scheduling uses the outbox so a
database commit and a notification cannot drift apart.

The controller does not directly perform stages. It does not keep the only
copy of a timer, lease, or retry counter in memory. A controller restart
reconstructs its next action from Postgres. Only one active controller may
own a scheduling lease; the lease mechanism must be a Postgres contract and
must be proven before multiple controller instances are allowed.

## 10. Sidecar discovery and readiness

Each sidecar registry entry names a stable URL, contract path, device class,
and pinned release. At startup, a consumer fetches `/manifest`, compares the
runtime identity with the registry pin, and refuses inference on mismatch.

`/health` proves the process loop responds. `/ready` proves the loaded model
can execute the same runtime path used by `/infer`. Readiness probes must be
cheap enough for operations and meaningful enough to catch a poisoned or
unloaded model. The exact probe payload and cadence are established by the
model qualification experiment.

## 11. Logs, traces, and work records

Every runtime log is one JSON object. Required fields are `timestamp`,
`level`, `service`, `event`, `trace_id`, `run_id`, `stage`, `attempt_id`,
`provider`, `model_release`, `device`, `duration_ms`, and `error_code`.
Fields that do not apply are null; names do not change between processes.
Documents and secrets never enter logs.

Trace context crosses HTTP and queue boundaries. Operators search by
`run_id` for one ingestion or by `trace_id` for one request chain. Runtime
logs are diagnostic. Postgres receipts remain the proof that a transition
committed.

Repository work uses a separate append-only log under
`docs/wiki/work-log/`. Each mutating change records its contract, changed
paths, proof, rejected claims, and remaining gaps. `scripts/repo_guard.py`
checks the record and the related architecture artifacts.

## 12. Dependency and refactor triggers

`architecture/dependencies.json` defines which package may depend on which
owner. Cross-process behavior travels through `contracts/`, never a private
module import.

| Changed authority | Required companion change |
|---|---|
| public contract | compatibility decision, reverse-dependent proof, work log |
| dependency edge | dependency map, ADR, refactor entry, architecture changelog |
| model manifest | model qualification receipt and readiness proof |
| Postgres schema | append-only migration, replay proof, rollback note |
| deployment manifest | clean-clone configuration proof and startup canary |
| management script | `scripts/README.md`, work log, governance check |

## 13. Release proof

The architecture is implemented only when a clean clone can start the
stores and host processes, ingest a real source through both GLiNER passes,
compile and persist an evidence-backed fact, recover after a controlled
process restart, rebuild its projections, and show the run in structured
logs. Until that path passes, the repository is a scaffold and must be
described as such.

## 14. Temporal durability of extraction (semantic-query-policy-v1)

Stable: immutable source evidence, canonical ontology, canonical
predicate semantics, versioned contracts, provenance, deterministic
acceptance. Replaceable: GLiNER (model/revision/labels), spaCy (or any
syntax provider), rule packs, query vocabularies, corpora.

- **Canonical types are not model wording.** Every GLiNER query —
  discovery pass 1 and every rescue query — resolves provider-facing
  labels through the versioned semantic query policy
  (`shared/polymath_shared/query_policy.py`); raw provider labels map
  back to canonical types through the same policy. The compiler,
  predicates, and canonicalizer never see provider aliases
  ("Company"/"Corporation"/...). Alias vocabularies are policy data
  that enter only through a named evidence gate
  (GLINER-QUERY-VOCAB-vN) with a version bump — never a code branch,
  never an ontology change.
- **Raw provider output is preserved.** Every mention stores
  raw_label + query_policy_version + pass_kind (discovery |
  boundary_rescue | missing_argument_rescue | type_reconciliation)
  alongside the canonical core_type (migration 0011). The durable
  syntax artifact (syntax-evidence-v1 stage artifact) identifies
  provider, model/version, backend, and contract version.
- **One extraction contract identity.** The extract stage contract
  hash includes every input that can change semantic output: chunk
  contract, GLiNER model/revision/threshold, query policy version +
  aliases, syntax provider + contract, rule pack, argument frames,
  admission policy, rescue policy (including its disabled state), and
  compiler versions. Any interpretation is reproducibly attributable.
- **Source evidence is immutable; interpretations are versioned.** A
  document may carry multiple extraction interpretations (contract
  v1/v2/...); each is attributable to its contract identity through
  receipts/manifests. Upgrades follow OBSERVE -> FREEZE BASELINE ->
  VERSIONED POLICY/CONTRACT -> REPROCESS -> DIFF -> EVALUATE ->
  PROMOTE/REJECT -> FREEZE RESULT. History is never silently
  overwritten; promotion rebuilds disposable projections
  deterministically from the promoted authoritative Postgres state
  (Qdrant/Neo4j never hold authority).
- **Predicate signatures constrain acceptance; they never manufacture
  semantic compatibility.** Model answers are queried under the normal
  qualified policy; the predicate contract then validates or rejects
  the canonical result.
