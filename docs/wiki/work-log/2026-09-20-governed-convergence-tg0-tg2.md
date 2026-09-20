---
change_id: GOVERNED-CONVERGENCE-V1-TG0-TG2
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "Polymath side only. TG1 adds seven adapter_* proxies to MCP Server B (stdio). TG2a makes adapter_next carry READABLE evidence (a sibling key, no wire-schema change). TG2b adds an OPT-IN evidence-boundary knowledge surface for adapter steps (pure shared module + worker dispatch + manifest 2.2.0 + additive step-ref properties + EvidencePacket JSON Schema + four contract-map rows). Default surface in code stays legacy; kill switch POLYMATH_ADAPTER_KNOWLEDGE_SURFACE=retrieve. Trail untouched."
last_reviewed: 2026-09-20
---

## Contract
Owner goal 2026-09-20 (session 1 of GOVERNED-CONVERGENCE-V1): TG0 + TG1 + TG2, Polymath side only. Done = fleet +
Trail stack up, R0 and R1 fixture runs green, TG1 + TG2 merged, live-proven, ledgered, tagged locally; then STOP
(TG3+ is a separate goal). Plan of record: `docs/wiki/plans/GOVERNED-CONVERGENCE-V1.md`.

- Single owner per change: `governance` (MCP Server B text surface, contracts, manifest, docs) · `worker`
  (`adapter_step` executor dispatch) · `shared` deterministic policy (`adapter/evidence_boundary.py`,
  `adapter/service.py`). The orchestrator's `/adapter/*` routes and `/chat/evidence` are UNCHANGED.
- Inputs/outputs: `adapter_next` gains a sibling `evidence{rows,receipts,coverage}`; adapter step refs gain four
  OPTIONAL properties; `AdapterResultV1.output` gains `evidence_admissions` for `trail.product_discovery` 2.2.0.
- Failure modes are typed: `EVIDENCE_CONTRACT_MISMATCH` (terminal, never a fallback), `EVIDENCE_SURFACE_UNAVAILABLE`
  (terminal when `on_unavailable: gap`), degraded legacy fallback recorded on the step output, empty evidence = success.
- Verifier: worktree unit suites (shared/contracts/config), then live R1 + `scripts/adapter_evidence_boundary_proof.py`.
- Rollback boundary: env kill switch (no deploy), or `git revert` of merge `f206c33` + one bounce.

## Changes
**TG0 — baseline, no code.** Fleet booted with ONE supervisor (`scripts/boot_polymath.sh`): 13 worker types healthy,
one bundle `e43044475a4e`, `/ready` true (embedder + reranker), slots `mcp` (:8930, seven adapter tools) and
`adapter_step` registered, the six live flags confirmed in the ORCHESTRATOR PROCESS env. Trail daemon on :8767 from
`A41` (`de64d84` == `origin/main`, clean, 0 pending migrations). R0 completed (below).

**TG1 — `797caea`.** `mcp_server/polymath_mcp.py`: seven `adapter_*` tools, plain proxies over `/adapter/*` with Server
A's names, parameters, docstrings and error mapping (`{"error","status"}`). NEW
`tests/contracts/test_mcp_adapter_parity.py`. `capabilities.py`: a note that both MCP surfaces serve the adapter tools.

**TG2 — `7f9ae50`.**
- NEW pure `shared/polymath_shared/adapter/evidence_boundary.py`: `ALLOWED_ORCH_PATHS`, `resolve_surface` (default
  legacy; env kill switch only ever forces legacy and says so), `original_needs` (seed, or one need per live
  hypothesis — its signature takes no step output), `plan_calls` (one corpus per call, `max_calls` 3, skips recorded),
  `request_body` (exactly `{message, corpus_id, mode, corpus_explorer}`), `check_response` (fail-closed: version,
  `synthesis_performed`, JSON Schema), `rows_from_packet`, `merge_rows` (graded first), `refs_from_rows`,
  `call_record`, `unavailable_outcome` (`gap` | `continue` → `unknowns`, never `knowledge_gaps`), `hydrate`.
- `adapter/service.py`: `next_step` returns the sibling `evidence` key (hydrated from `store.list_steps`, i.e. every
  bounded-loop pass; a hydration failure is returned as `evidence.error`, never raised); `_compile_result` accepts the
  generic include form `{"collect_all": <key>, "as": <name>}` (reads the stored steps — `state.outputs` keeps only the
  newest pass of a looped step).
- `workers/workers/adapter_step_worker.py`: `_orch_post` is allow-listed, raises typed `OrchUnavailable` (transport /
  timeout / 5xx) or `OrchRejected` (4xx) and sends `User-Agent: polymath-adapter-step/<run>/<step>/<seq>`; NEW
  `exec_evidence`; `exec_retrieve` / `exec_graph_expand` dispatch on `config.surface`; the legacy bodies are kept
  verbatim as `_retrieve_legacy` / `_graph_legacy` (`legacy_mode` preserves the pre-boundary `EXPLORE` call).
- `config/adapters/trail.product_discovery.json` → `adapter_version 2.2.0`, `retrieval_policy_version 2.0.0`
  (workflow 2.0.0, 28 steps, same step ids): `B_retrieve`/`F_retrieve` = `evidence_boundary / WILDCARD /
  corpus_explorer true`; `B_graph`/`F_graph` = `evidence_boundary / GRAPH` unioned with the legacy graph facts; all
  four `max_calls 3, fallback retrieve, on_unavailable gap`; `X_compile.include` gains the collect-all admissions.
  `B_plan`/`F_plan` unchanged. The other two manifests are untouched.
- Contracts: `adapter_step.schema.json` evidence refs gain OPTIONAL `utility_role`, `ca4_grade`, `c4_valid`, `origin`;
  NEW `contracts/evidence/v1/evidence_packet.{schema,example}.json`; the five contract examples carry the new
  identity (an existing pin requires manifest identity == example identity).
- `architecture/contract-dependencies.yaml`: NEW `EVIDENCE_PACKET`, `EVIDENCE_BOUNDARY_API`, `ADAPTER_RUNTIME`,
  `MCP_SURFACE`; `SUBQUERY_PROVENANCE.consumed_by += EVIDENCE_PACKET`.
- Proof tooling: NEW read-only `scripts/adapter_evidence_boundary_proof.py`; `scripts/adapter_mcp_acceptance.py`
  records the LIVE `adapter_next` evidence per step and gains `--require-evidence-text` / `--require-surface`.
- Server A + Server B `adapter_next` docstrings describe the `evidence` key (parity test keeps them identical).

**Deploy.** Drain check: 0 in-flight adapter runs, 0 leased stage tickets (open ingestion runs = the known dormant
HELD backlog: 63 `reconciling` + 1 `intake`, 217 `pending` tickets, none leased). Fleet stopped (TERM; 0 supervisors /
children / listeners) → merge `f206c33` (`--no-ff`) → ONE boot. After: 13 types healthy, one bundle `c0d86509ad39`,
sidecars true, live `/adapter/list` = `trail.product_discovery 2.2.0 / 2.0.0 / 28`, kill switch unset.

## Proof
Proof levels use the bootstrap vocabulary. Import resolution verified on MAIN after the merge
(`workers.adapter_step_worker`, `polymath_shared.adapter.evidence_boundary`, `.service` → the main checkout).

| slice | level | evidence |
|---|---|---|
| TG0 R0 baseline | LIVE_PATH_PROVEN | exit 0; run `adr_1a357ee43e9c2e6750d756d9f2136761` completed 42/42, worker restart `22701→24036`, invented submission refused 422, 1 scored + 1 `HARD_GATE_UNMET`; `eval/governed_convergence/R0-FIXTURE-BASELINE-2026-09-20.json` |
| TG1 parity | UNIT_PROVEN | 6 tests; both servers loaded BY FILE PATH (executed path asserted); negative control: pre-change Server B had 0 adapter tools |
| TG1 Server B | LIVE_PATH_PROVEN (list / status / next / result / cancel + error mapping) | real stdio MCP session spawned with the exact command + args of Claude Code's project registration: 7 tools listed; `adapter_list` shows 2.2.0; 404 mapped to `{"error","status"}`; POST path proven by an idempotent `adapter_cancel` on the already-completed R0 run (row unchanged). `adapter_start` / `adapter_submit` over Server B are NOT live-exercised — that needs a new run, which this goal does not authorize; TG5 exercises them |
| TG2 pure module + service seams + manifest | UNIT_PROVEN | `tests/determinism/test_adapter_evidence_boundary.py` (27), `tests/contracts/test_evidence_packet_contract.py` (4: the REAL producer's packets validate against the consumer's schema) |
| TG2 worker logic | UNIT_PROVEN for the FILE (loaded by file path; executed path asserted) — not a package-import proof | `tests/contracts/test_adapter_worker_evidence_surface.py` (18): AST (no `/chat`, `/chat/stream`, `/ask` literal in worker or module — negative control: the scan flags Server B, which lawfully serves them; every `_orch_post` site allow-listed; httpx only in `_orch_post`; `exec_evidence` never reads a step output) + stubbed-orchestrator behaviour |
| TG2 deployed | MERGED + DEPLOYED | merge `f206c33`, bundle `c0d86509ad39`; the same suites re-run GREEN on MAIN (96 tests incl. adapter contract/pure/loop) |
| TG2 live (R1) | LIVE_PATH_PROVEN | driver exit 0 with `--require-evidence-text --require-surface evidence_boundary`: run `adr_12ddda16f9b589fbdf7dfab9f31efedf` completed 42/42, restart `28101→28591`, 9/9 agent steps carried the `evidence` key WITH text (122,690 chars; 221 rows with `utility_role`), surfaces `evidence_boundary` + `retrieve` (plan lane), not degraded. Proof script exit 0: 6 boundary calls ↔ 6 receipts, ALL `evidence_only`; 0 synthesis receipts; every call `evidence-packet-v1 / synthesis_performed=false / valid`; 715 issued refs carry `utility_role`; result carries 5 `evidence_admissions` (33 admitted, 0 rejected). Negative control: the same script on legacy R0 exits 1 for exactly the three expected reasons. Artifacts `eval/governed_convergence/R1-*.json` |

Guards `agent_preflight` / `repo_guard` / `wiki_worm --check` = 0 and `bundle_integrity` READY, each captured on its
own line, in the worktree before each commit's final state and on MAIN after the merge. Impacted sweep: `tests/contracts`
(104) + 15 determinism suites (145 tests) green, except the two PRE-EXISTING reds below.

Measured cost (R1 vs R0, same fixtures): run wall 315 s vs 181 s (+134 s); 6 boundary calls, 11.6–33.5 s each
(146 s total). The plan estimated ~8 calls / +3–4 min; the fixture has 2 live hypotheses, so `F_*` made 2 calls, not 3.

## Rejected claims
- REJECTED: "R1 proves Corpus Explore enriches the seed." On `B_retrieve` the explorer was REQUESTED and did NOT fire —
  firing receipt `PLAN_FALLBACK` (the compiler fell back; backlog B19). It fired 2/2 on the hypothesis needs. Recorded
  as measured; nothing was tuned, retried or re-run to change it.
- REJECTED: "every packet was re-validated by the proof script." Packets are not stored. The worker validates each one
  against `contracts/evidence/v1` at call time and a failing packet ends the run (`EVIDENCE_CONTRACT_MISMATCH`); the
  script reads that recorded verdict. The producer ⇔ schema pin is the contract test.
- REJECTED: "the worker tests are package-level proof inside the worktree." The editable `.pth` resolves `workers` to
  MAIN; the worker file was loaded BY FILE PATH (asserted). The deployed behaviour is proven by R1, not by that file.
- REJECTED: "`adapter_start` / `adapter_submit` are live-proven on Server B." Only the read tools and the idempotent
  cancel were exercised over stdio; a start is a new live run, outside this goal's R0 + R1 budget.
- REJECTED: tuning anything to pass — no registry, gate, threshold, freshness window, test or fixture was changed.
- FINDING (pre-existing, NOT from this slice; fail identically on untouched `94dbd57`): 
  `test_query_receipts::test_all_three_query_handlers_and_read_surfaces_are_wired` (pins 2 chat receipt writers; 4 since
  `/chat/evidence`) and `test_chat_runtime::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes`
  (subquery tuple gained `origin`). Tests are immutable without the owner's word → left red, flagged to the owner.
- FINDING: `handoff-drafts/trail_stack_up.sh` is a ZSH script (`${=C}`). Invoked as `bash …` (as the plan, CONTINUITY
  and the goal prompt wrote it) every compose / health / migration line aborts with "bad substitution" and the script
  still starts the daemon. Harmless today (stores already healthy, 0 pending migrations — verified read-only), wrong on
  a cold stack. CONTINUITY now says `zsh`. The script itself lives outside this repo and was not edited.

## Open contract gaps
Impact closure for `94dbd57..HEAD` (`scripts/contract_impact.py --range`): changed `ADAPTER_RUNTIME`,
`EVIDENCE_PACKET`, `MCP_SURFACE`; transitive `EVIDENCE_BOUNDARY_API`. One disposition each:

- `ADAPTER_RUNTIME` — **UPDATED** (readable `evidence` sibling; opt-in surface; additive ref properties; collect-all
  include). Unit + LIVE (R1).
- `EVIDENCE_PACKET` — **UPDATED** (first JSON Schema + first external consumer; producer code unchanged). Contract test
  pins producer ⇔ schema; every live packet in R1 passed the consumer check.
- `MCP_SURFACE` — **UPDATED** (Server B serves the seven adapter tools; `adapter_next` docstring on both). Parity test +
  live stdio.
- `EVIDENCE_BOUNDARY_API` — **TESTED_UNCHANGED** (no orchestrator route or runtime code changed; exercised live 6× in R1,
  all `evidence_only`). DEBT on this row: the two pre-existing stale pins above, owner decision pending.
- `SUBQUERY_PROVENANCE` — **NOT_AFFECTED** (only gained a `consumed_by` edge to `EVIDENCE_PACKET`; no code change).

Open, deliberately NOT done here: TG3+ (separate goal) · `output_schema_version` left at 2.1.0 (the manifest's
`output_schema` is open, so `evidence_admissions` is lawful without a schema change; bump it if the owner wants the
new key declared) · the Codex `[mcp_servers.polymath]` entry is the owner's step · the adapter's missing step lease and
terminal-only gaps (plan backlog) · the worker still runs executors inside the run-row transaction, so a boundary step
holds the row for up to ~35 s per call (plan: known cost).
