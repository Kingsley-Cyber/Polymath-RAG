# AGENTS.md: repository and agent contract

Read this file before changing the repository. It defines runtime ownership,
architecture change rules, managed scripts, and the proof required from each
agent. If code or prose conflicts with this file, stop and resolve the
contract conflict before editing.

## 0. Mandatory Bootstrap

A new agent MUST bootstrap from repository state before reasoning from
memory or chat context.

> Chat history is not authoritative project state. Repository bootstrap
> files are.

Before making any code, schema, data, architecture, or evaluation change:

1. Read `AGENTS.md` (this file).
2. Read `CURRENT_STATE.md` (authoritative state snapshot).
3. Read `NEXT_SESSION.md` (last handoff + next authorized task).
4. Read `ARCHITECTURE.md` and `architecture/dependencies.json`.
5. Run `git status`, record the active branch and `HEAD`.
6. Verify every frozen hash listed in `CURRENT_STATE.md` (`shasum -a 256 <file>`).
7. Run the fast verification commands (`make guards` + the test command
   recorded in `CURRENT_STATE.md`).
8. Do not modify anything until repository state and bootstrap state agree.

Never assume:

- never assume the previous agent's branch or HEAD;
- never assume tests are green;
- never assume frozen artifacts are unchanged;
- never treat experimental findings as production defaults;
- never silently change frozen architecture;
- never modify evaluation corpora after freeze;
- never continue from stale documentation without verifying it against
  git and artifacts.

Staleness contract: if current `HEAD` differs from the commit recorded in
`CURRENT_STATE.md`, inspect the commits since that state, determine whether
the state documentation is stale, and update it before relying on it for
consequential work. A changed HEAD does not automatically mean the
documentation is invalid — verify the actual diff.

Where to find things:

| Question | File |
|---|---|
| current state, frozen hashes, evaluations, prohibitions | `CURRENT_STATE.md` |
| next authorized task | `NEXT_SESSION.md` |
| architecture + ownership | `ARCHITECTURE.md`, `architecture/dependencies.json` |
| decisions | `docs/wiki/decisions/` (ADRs 0000–0008) |
| experiments + measured results | `docs/wiki/experiments/`, `eval/phase_h/REPORT*.md` |
| work log (append-only) | `docs/wiki/work-log/` |
| contracts | `contracts/` |
| resource build pipeline | `resources/README.md` |
| managed scripts | `scripts/README.md` |
| tests | `tests/` (+ `tests/integration/` behind `POLYMATH_INTEGRATION=1`) |

If documentation conflicts, resolution order: git state + frozen hashes →
`CURRENT_STATE.md` → ADRs → `ARCHITECTURE.md` → other docs.

## 1. Select one owner

Every runtime change has one process owner.

| Owner | Owns | Forbidden ownership |
|---|---|---|
| `orchestrator` | HTTP intake and reads | scheduling, model loading, long jobs |
| `worker` | one durable stage | user HTTP, supervision, workflow authority |
| `sidecar-gpu` | one resident model and device | predicates, receipts, run state |
| `sidecar-cpu` | one CPU inference service | GPU state, receipts, run state |
| `store` | one persistence engine | application decisions |
| `control` | census, scheduling, recovery, heartbeat | inference and user requests |

Use `governance` only for repository-only changes such as architecture,
scripts, CI, or wiki maintenance. It is not a process role. If one change
needs multiple runtime owners, split it at a versioned contract boundary.

## 2. Non-negotiable rules

1. No model runs in Docker. Model processes are host-native and supervised
   by launchd on macOS or systemd on Linux.
2. One sidecar process loads one model release. The GLiNER entity and
   evidence passes call the same resident GLiNER runtime.
3. Every cross-process payload conforms to a versioned schema in
   `contracts/`. Private package imports never cross process boundaries.
4. Every mutation uses canonical content identity. Replaying identical
   input must not create a second logical result.
5. A stage artifact, receipt, status transition, and required outbox event
   commit in one Postgres transaction.
6. Postgres is workflow authority. Redis, Qdrant, and Neo4j are disposable
   notification, cache, or projection layers.
7. Models propose spans. Only the deterministic compiler selects predicates,
   direction, negation, modality, ontology mapping, and fact identity.
8. Existing tests and evaluation artifacts are immutable unless the user
   explicitly asks to change them. Fix implementation failures in code.
9. Secrets, source text, and credentials never enter logs or work records.
10. Never prune Docker volumes, delete bind-mounted store data, or run
    `docker volume rm` / `docker system prune --volumes` without explicit
    user approval. Report disk usage, volumes by owning store, and cleanup
    candidates first; only volumes the user approves are touched. Removing
    a stopped container that owns no volume still requires listing what it
    owned first.

## 3. Read and verify before editing

Read in this order:

1. `AGENTS.md` (bootstrap section included)
2. `CURRENT_STATE.md`
3. `NEXT_SESSION.md`
4. `ARCHITECTURE.md`
5. `architecture/dependencies.json`
6. `PLAN.md`
7. the ADR, refactor entry, package contract, and latest relevant work log

Then run:

```bash
python3 scripts/agent_preflight.py
python3 scripts/repo_guard.py
python3 scripts/wiki_worm.py --check
```

Record pre-existing failures. Do not lower a check, edit a test, or replace
a production dependency with a mock to create a passing result.

## 4. Admit one change slice

Before a repository mutation, create or update one entry under
`docs/wiki/work-log/`. State:

- the requested outcome and smallest acceptance criteria;
- the single owner and public contract;
- inputs, outputs, persistence effect, and failure modes;
- dependency edges and reverse dependents;
- the verifier and rollback boundary.

Reject any proposed file, abstraction, refactor, test, or safeguard if
deleting it would still leave the outcome satisfied and proven. Do not create
directories or interfaces for unadmitted future work.

## 5. Directory and dependency enforcement

### 5.0 Directory map

Where things live, and which layer owns each. The pipeline runs top to
bottom; each layer has exactly ONE authority and may not do another
layer's job.

```
polymath-v4/
├── POLYMATH_V5_RELEASE_BASELINE.md   ← READ FIRST. Frozen state + work order.
├── AGENTS.md                          this contract
├── CURRENT_STATE.md                   state snapshot
├── NEXT_SESSION.md                    last handoff + next authorized task
├── ARCHITECTURE.md                    layer explanation for humans
│
├── config/
│   ├── runtime_budget.yaml            19 GB allocation, profiles, sidecar caps
│   └── semantic_bundle.lock           hash over 8 semantic authorities
│
├── shared/polymath_shared/            ← DETERMINISTIC POLICY. No I/O, no models.
│   ├── bundle_integrity.py            boot gate; FATAL on drift/unwired gates
│   ├── runtime_budget.py              MPS caps, preflight, footprint
│   ├── metal.py                       shared GPU discipline (OOM split/release)
│   ├── worker_runtime.py              the fleet's single worker loop
│   ├── clients.py                     typed sidecar clients (bounded, retrying)
│   ├── contracts.py                   CoreType, EntitySpan, EvidenceSpan, …
│   ├── entity_knowledge_admission.py  E1–E7  ← IDENTITY authority
│   ├── entity_admission_policy.yaml   E-gate policy (v2)
│   ├── fact_admission.py              F1–F8  ← TRUTH authority
│   ├── fact_admission_policy.yaml     F-gate policy
│   ├── identity_allocation.py         durable-id allocation, canonical_type()
│   ├── entity_harbor.py               graph eligibility
│   ├── admission_interpreter.py       MENTION_ONLY / scoped / global
│   ├── raw_evidence.py                L1–L4 ledger row builders
│   ├── retrieval.py                   FAST/HYBRID/GRAPH lanes
│   └── rulepack/                      ← PREDICATE authority
│       ├── core-predicates-v1.3.0.yaml   28 predicates (LOADED VERSION)
│       ├── compiler.py                   compile_relation, _trigger_matches
│       └── role_assignment.py            subject/object binding
│
├── resources/
│   ├── predicates/trigger_allowlist.yaml  ← TRIGGER authority (allow/deny/suggested)
│   └── compiled/<contract-sha>/           compiled lexical artifacts
│
├── scripts/
│   ├── boot_polymath.sh               THE boot path (integrity gate → supervisor)
│   ├── compile_predicate_rules.py     gate 1-5; gate 5 = suggestion-only
│   └── ingest.py                      manifest-driven ingestion CLI
│
├── control/control/
│   ├── process_supervisor.py          fleet supervision, budget preflight
│   ├── main.py                        control loop, ticket advancement
│   ├── tickets.py                     ticket DAG, lease reaping
│   └── heartbeat.py                   controller lease (owner id = process id)
│
├── workers/workers/                   ← DURABLE STAGES, one per pipeline step
│   ├── extract_worker.py              THE pipeline spine (see 5.1)
│   ├── entity_admission_stage.py      calls E1–E7, emits endpoint verdicts
│   ├── fact_admission_stage.py        calls F1–F8, gates the assertion
│   ├── candidates.py                  relation candidate generation
│   ├── rescue.py                      span widening hypotheses
│   └── project_{neo4j,qdrant,canonical}_worker.py
│
├── sidecars/                          ← MODELS. Untrusted evidence only.
│   ├── gliner_runtime/                candidate spans      (port 8740)
│   ├── embedder/                      vectors              (8742)
│   ├── reranker/                      retrieval rerank     (8743)
│   └── spacy_runtime/                 syntax evidence      (8744)
│
├── stores/postgres/migrations/        0001…0022 (0022 = entity decisions)
│
├── tests/
│   ├── contracts/                     ← ARCHITECTURE INVARIANTS (read these)
│   ├── determinism/                   replay + defect regressions
│   └── integration/                   needs a live fleet
│
└── eval/
    ├── v5/implementation_plan.py      LIVE plan; status probed, not typed
    ├── v5/release_gates.py            release gates
    ├── v5/verify_live_build.py        proves running code == HEAD
    ├── core3/                         the 3-doc A/B bench
    ├── sealed/                        SEALED holdout — never ingest to tune
    └── i4/gold/, admission/artifacts/ FROZEN. Do not modify.
```

### 5.1 The pipeline spine

`workers/workers/extract_worker.py::process_event` is where the layers
meet. Order is load-bearing:

```
chunks → GLiNER proposals → rescue → _allocate_identities
   → apply_entity_admission   (E1–E7, emits endpoint verdicts)
   → _persist_mentions        (evidence survives regardless)
   → build_candidates + compile_relation
   → FactAdmissionStage.admits (F1–F8, consumes those verdicts)
   → _persist_decision        (ONLY if admitted)
   → _fact_stage.flush
```

### 5.2 Layer authority — one job each

| layer | authority | must NOT |
|---|---|---|
| GLiNER | candidate spans | truth, identity, type |
| spaCy | syntax evidence | create entities |
| Entity Admission | identity | relation meaning |
| Predicate Compiler | relation meaning | identity, truth |
| Fact Admission | truth eligibility | identity, syntax |
| Neo4j | settled knowledge | anything not T2 |

**No model ever writes knowledge.** Enforced by
`tests/contracts/test_admission_boundary.py`.

The scaffold `TREE` is the file-placement authority.
`architecture/dependencies.json` is the import and ownership authority.
`ARCHITECTURE.md` explains both for humans.

New paths require all of the following in the same change:

1. an ADR when the architectural boundary changes;
2. a refactor entry naming the trigger and affected dependents;
3. an updated dependency map when an owner or edge changes;
4. an updated scaffold `TREE` and `scripts/README.md` when applicable;
5. an architecture changelog entry and work-log proof.

Place changes by authority:

- public wire payload: `contracts/<domain>/v<N>/`;
- API endpoint: `orchestrator/orchestrator/api/`;
- durable stage: `workers/workers/`;
- model runtime: `sidecars/<name>/` plus `sidecars/<name>.toml`;
- deterministic shared policy: `shared/polymath_shared/`;
- workflow migration: `stores/postgres/migrations/`;
- decision, refactor, experiment, or work record: its matching wiki folder.

Forbidden dependency patterns are checked by `scripts/repo_guard.py`.
Providers do not own state. Orchestrator code does not import worker or
control internals. Workers do not import sidecar implementations. Calls cross
those boundaries through schemas and typed clients.

## 6. Refactor triggers

Changes propagate by dependency, not by guesswork.

| Trigger | Required response |
|---|---|
| contract change | decide compatibility and verify every reverse dependent |
| dependency edge change | update dependency map, ADR, refactor entry, changelog |
| model release change | add qualification evidence and readiness proof |
| schema change | append a migration and record replay plus rollback proof |
| deployment change | prove clean-clone configuration and startup |
| script change | update script registry and work log |

No agent silently rewrites `ARCHITECTURE.md`, changes a frozen contract, or
edits an applied migration.

## 7. Managed scripts

`scripts/README.md` is the script registry. A script must name its owner,
inputs, writes, safe mode, and verifier before it can be added to `TREE`.

- `scaffold_polymath_v4.py` creates missing declared files and never
  overwrites existing files.
- `agent_preflight.py` checks whether an agent may begin work.
- `repo_guard.py` checks declared paths, dependencies, script records, work
  logs, and architecture companion changes.
- `wiki_worm.py --check` audits wiki structure and open work without editing.
- `check_install.sh` reports service reachability and performs no repair.

Agents do not add one-off root scripts. Reusable repository operations live
under `scripts/`, are declared in `TREE`, and are documented in the registry.
Temporary diagnostics stay outside the repository.

## 8. Work logs and runtime logs

Work logs are append-only Markdown records in `docs/wiki/work-log/`. Do not
rewrite an older record to make current work look complete. Add a correction
entry that links to it. Each mutating change records Contract, Changes,
Proof, Rejected claims, and Open contract gaps.

Runtime logs are JSON and use the shared logger. Required field names are:
`timestamp`, `level`, `service`, `event`, `trace_id`, `run_id`, `stage`,
`attempt_id`, `provider`, `model_release`, `device`, `duration_ms`, and
`error_code`. Use null when a field does not apply. Postgres receipts, not
log lines, prove committed state.

## 9. Completion proof

A capability is working only when all four facts are observable:

1. a public production entrypoint is reachable;
2. runtime wiring reaches the real owner;
3. a durable or external outcome exists;
4. a verifier traverses that same path and passes.

Placeholders, direct internal calls, mocked adapters, generated files, and
diagrams do not satisfy this rule. Keep pre-existing failures separate from
regressions. End the change when the admitted contract is satisfied and no
remaining claim is required to prove it.
