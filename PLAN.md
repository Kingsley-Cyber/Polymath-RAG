# Polymath v4 implementation plan

Status: scaffolded, production path not yet proven

This plan is ordered by dependency. Agents admit one vertical slice at a
time. A phase advances only when its public entrypoint, durable outcome,
and verifier pass through the production path.

## Planning rules

1. Do not port v3.3 modules by directory. Port a named behavior only after
   its contract and owner are clear.
2. Do not add a provider, store, queue, or schema that creates a second
   authority.
3. Do not call a stub, mock, test-only path, or direct internal function a
   working capability.
4. Record every repository mutation in `docs/wiki/work-log/`.
5. Stop a slice when its stated contract is satisfied and proven.

## Phase A: repository contract

Outcome: a clean scaffold has one directory source of truth and executable
governance.

Required work:

- keep every managed path in the scaffold `TREE`;
- keep package ownership in `architecture/dependencies.json`;
- validate scripts, wiki metadata, work logs, and undeclared paths;
- keep architecture changes tied to an ADR, refactor entry, changelog, and
  work log.

Exit proof:

```bash
python3 scripts/scaffold_polymath_v4.py
python3 scripts/agent_preflight.py
python3 scripts/repo_guard.py
python3 scripts/wiki_worm.py --check
```

## Phase B: contracts, identity, state, and logging

Depends on: Phase A.

Outcome: all later stages share one identity scheme, one transaction
boundary, one sidecar contract, and one log field set.

Required work:

- freeze the canonical byte normalization and content-hash contract;
- define run, stage attempt, receipt, outbox, and artifact schemas;
- implement a Postgres transaction that writes artifact, receipt, status,
  and outbox together;
- make sidecar manifests expose model, revision, weights digest, runtime,
  device, and wire schema;
- propagate `trace_id`, `run_id`, `stage`, and `attempt_id` across HTTP and
  queued work;
- replace model and deployment placeholders only with measured or pinned
  values.

Exit proof: a public intake call commits one run and outbox event; replaying
the same canonical input does not create a second run; logs and rows share
the same identifiers.

Rollback boundary: the initial Postgres migration and the v1 contracts.

## Phase C: qualify GLiNER on the target Mac

Depends on: Phase B contracts and logging.

Outcome: the local runtime topology and inference settings are based on
measurements from the deployment Mac.

Required work:

- pin the GLiNER model revision and weights digest;
- build an approved evaluation sample with expected entity spans and
  evidence classes;
- measure one resident process serving both passes;
- compare separate-process execution only if memory or concurrency evidence
  gives a reason to test it;
- record load time, resident memory, per-pass latency, combined latency,
  throughput, and reviewed extraction errors;
- select label sets, thresholds, batching, and readiness payload from the
  recorded experiment.

Exit proof: an experiment entry contains the command, hardware identity,
model release, input digest, raw results, review notes, and ship or reject
decision.

Rollback boundary: the sidecar manifest release.

## Phase D: first complete ingestion slice

Depends on: Phases B and C.

Outcome: one real text source becomes one persisted, evidence-backed fact.

Production path:

```text
HTTP intake
  -> source persistence
  -> chunk
  -> entity pass
  -> evidence pass
  -> deterministic compiler
  -> Postgres fact, evidence, receipt, status, outbox
  -> searchable structured log
```

Required work:

- replace the intake placeholder with the real transactional path;
- implement one worker entrypoint for the admitted stages;
- implement the compiler as a pure function over versioned rule data;
- retain document, chunk, and character offsets on every accepted fact;
- emit explicit no-fact and ambiguous outcomes without inventing edges.

Exit proof: a public request produces a durable fact and evidence record;
replay is a no-op; a rejected relation remains absent; the entire run is
searchable by one `run_id`.

Rollback boundary: disable the v1 intake route and preserve committed source
artifacts for replay.

## Phase E: independent control and recovery

Depends on: Phase D receipts and outbox.

Outcome: accepted work continues or resumes when the API, worker, model
runtime, or controller restarts.

Required work:

- implement desired-versus-observed artifact census from Postgres;
- schedule only missing stages through the outbox;
- add a Postgres-owned controller lease before multiple controller
  instances are allowed;
- supervise host processes with launchd and expose liveness separately from
  readiness;
- keep recovery decisions visible in logs and stage attempts.

Exit proof: controlled restarts at each process boundary leave one accepted
result and no duplicate receipt.

Rollback boundary: stop the controller; existing read paths and committed
state remain available.

## Phase F: rebuildable search projections

Depends on: Phase D accepted facts and Phase E recovery.

Outcome: Qdrant and Neo4j are projections that can be deleted and rebuilt
from authoritative artifacts and receipts.

Required work:

- write vectors with corpus, document, chunk, model, and source digests;
- write graph facts with compiler rule and evidence identities;
- record projection receipts;
- compare the desired projection census with observed receipts;
- provide replay and projection-rebuild commands.

Exit proof: rebuild both projections from the same accepted source and
produce the same logical identities.

Rollback boundary: discard projection collections or databases; Postgres
authority remains intact.

## Phase G: retrieval and answer path

Depends on: Phase F.

Outcome: focused, hybrid, and graph retrieval consume the new projections
without bypassing provenance.

Required work:

- port one retrieval behavior at a time behind a public contract;
- preserve corpus boundaries and embedding-release compatibility;
- attach source evidence to every returned fact;
- add reranking only after base retrieval has a recorded verifier;
- keep answer generation outside retrieval scoring and graph policy.

Exit proof: each retrieval mode returns source-linked results through its
public endpoint and refuses incompatible projection releases.

## Phase H: remote compute adapters

Depends on: the local path passing Phases D through G.

Outcome: remote CUDA or cloud compute can replace local inference without
changing workflow state, graph semantics, or client contracts.

Required work:

- register remote services through the same sidecar manifest;
- prove release mismatch refusal, unreachable-provider behavior, and local
  recovery;
- measure cost and latency before accepting automatic routing;
- keep provider credentials outside logs and repository files.

Exit proof: the same input and compiler release preserve fact identity when
only the inference provider changes, subject to the recorded proposal set.

## Deferred until admitted

- v3.3 bulk migration;
- automatic cloud overflow;
- multi-controller operation;
- a second GLiNER process on the Mac;
- removal of the v3.3 repository.
