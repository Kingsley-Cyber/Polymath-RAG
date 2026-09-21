---
change_id: EXTERNAL-REVIEW-M1-VERIFICATION
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none — evidence record only. An external reviewer model (read-only, mission M1: failure modes of the governed loop) reported 12 findings; each was turned into a reproduction test on an ISOLATED branch. No production file, existing test, Trail file, manifest or contract was changed. Nothing merged, deployed, bounced or pushed. NO fix is part of this slice."
last_reviewed: 2026-09-20
---

## Contract
Owner word 2026-09-20: "Proceed with recording the findings and the smallest isolated fix for M1-04. Defer M2 until this slice
is resolved. First, reconcile the verification record … Record only evidence-supported claims in the register and work-log,
preserving those distinctions. Preserve the reproduction tests and their results in the isolated worktree. … Check the
unresolved HALT instruction before implementation. If it prohibits this isolated fix, finish the evidence record and quote the
exact unresolved decision."

- Evidence vocabulary used below: **EXECUTED** = behaviour observed by running code · **READ** = concluded from reading code,
  never run · **STUBBED INPUT** = the behaviour was executed, but the input that provoked it came from a test double, so the
  claim "production produces this input" is READ.
- A red test shows the behaviour it executes. It does not by itself establish claims about production Trail, the worker
  process or the fleet.
- Reproductions: branch `review/m1-reproductions` @ `eb63bef` (worktree `pmv4-m1-repro`), `tests/review_m1/`; results under
  `tests/review_m1/results/` (unmodified pytest output of ONE run + the parsed assertions).
- Sources outside the repo (not authority): reviewer report
  `handoff-drafts/external-review/out/REVIEW-M1-20260920-1330.md`; triage `…/out/TRIAGE-M1-20260920.md`.

## Changes
- This work-log, register 11.361, scaffold `TREE`, a pointer in CONTINUITY. Docs only.
- Branch `review/m1-reproductions` (`eb63bef`): 27 files under `tests/review_m1/` only. Never merged.

## Proof

### 1. Resources the verification touched — and a correction of what I told the owner
I told the owner the verifiers "make no live calls". **That was wrong as worded.** What I had actually imposed on them was: no
HTTP, no MCP, no LLM, no Docker, no service control — and Postgres ONLY "through the existing test-fixture pattern". A database
the running fleet uses is a live resource; I summarized my constraint more strongly than I had set it, and I did not isolate
the database. No isolated database was used at any point.

| Resource | Shared with the running fleet? | Who | What happened |
|---|---|---|---|
| Local Postgres, database `polymath` (the existing fixture's default DSN; the DSN was never printed) | **YES** — same instance the fleet's `adapter_step` worker polls (the verifier saw that worker, pid 43391) | M1-04..08 tests (Postgres parameter) | one connection, ONE outer transaction, a savepoint per unit, always ROLLED BACK; teardown asserts no run leaked. Rows existed only inside uncommitted transactions. |
| same | YES | M1-09 tests | **COMMITTED** probe runs (rows in the adapter tables for their own run ids) while parked `awaiting_agent` / `awaiting_harness` or terminal `cancelled` — never `running`, the only state `claim_run` selects — then DELETED exactly those run ids at fixture teardown (`store.delete_run`). The in-process FastAPI route's pool was pointed at the same database. |
| same | YES | M1-10 / 11 / 12 tests | used the fixture connection, no commit (rollback only). |
| same | YES | the primary agent | re-ran the WHOLE Polymath-side directory once (so every access above happened a second time) and ran read-only `SELECT`s on `adapter_runs`, `adapter_steps`, `adapter_admitted_evidence`, `worker_registrations` four times around the verification, with the fleet's DSN loaded into the shell from `.env` (never printed). |
| Trail code `A41` | read-only files | M1-01..03 stage 1 | imported and EXECUTED in-process under Trail's venv with an in-memory store and the compiled registry read from disk. No Trail daemon, no Trail database. 0 `.pyc` files were written into `A41/src` (filesystem check). `git status` clean. |
| Orchestrator `:7200`, MCP `:8930`, Trail daemon `:8767`, LLM providers, Docker, Qdrant, Neo4j | — | nobody | not called. Static check of all 20 test / rig files: 0 references to those ports; transports are `httpx.MockTransport` or an in-process `TestClient`. |

Observed afterwards (already-collected observations, not new calls): `adapter_runs` by status was identical before and after
(`cancelled 1 · completed 9 · terminal_gap 15`), 0 runs created in the window remained, run R2a still had 30 steps / 8
admitted rows, the adapter worker was healthy, both git trees clean.
NOT established: that the fixture's database and the fleet's are the same instance was not re-verified for this note (it would
need a live call or reading `.env`); the risk that a committed probe could be claimed was avoided by construction (READ in the
test code), not measured.

### 2. Findings — the exact failing assertion, and what is EXECUTED versus READ
Common to M1-04..12: Polymath's REAL `service` / `hypotheses` / worker code and the UNCHANGED manifest were executed; Trail was
a test double whose response shapes were modelled by READING `A41` — so every "production Trail returns this" is READ unless
stated. Common to M1-01..03: Trail's REAL `ResearchOperationService.operate` was executed in-process (stage 1) and its real
serialized output was replayed through Polymath's real translation + ledger code (stage 2) with an in-memory store;
`service.advance` itself was NOT driven — the harness mirrors its issuance and automatic-step unit.

| ID | Verbatim failing assertion (trimmed) | EXECUTED | READ / STUBBED INPUT |
|---|---|---|---|
| M1-01 | `a lawful Trail CHALLENGE ended L_judge with a typed gap: {'code': 'PHI_VERDICT_INVALID', 'message': 'transition 0: CONTRADICT needs contradictions with evidence_ids'}` · Trail side: `Trail's wire verdict dropped ['contradictions', 'field_evidence_ids'] from a lawful CHALLENGE/CONTRADICT determination` | real Trail emits the domain fields and its wire verdict lacks them; unchanged Polymath refuses that verdict and applies it correctly when the fields are present | the second variant (2 supports + 2 contradictions) was checked in a scratch script only |
| M1-02 | `L_judge ended with a typed gap after Trail admitted a duplicate it then refused to judge: {'code': 'TRAIL_REFUSED', 'message': 'hypotheses.judge: invalid tool input'}` · Trail side: `hypotheses.judge raised on ids Trail itself admitted (one is duplicate_of the other): ValidationError … HypothesisJudgementRequestV1` | real Trail admits both observations, marks one `duplicate_of`, then its own judge request fails set-equality | that Trail's MCP input sanitiser hides the cause from Polymath; how often two same-claim observations occur |
| M1-03 | `Trail's deduplication batch killed the run at E_filter: {'code': 'PHI_VERDICT_INVALID', 'message': 'transition 2: hyp_… is proposed and cannot transition'} \| batch=[('MERGE','a4d613'),('WEAKEN','ead0f0'),('WEAKEN','a4d613')]` · pure domain: `WEAKEN targets hyp_b which this batch already absorbed` | real Trail filter emits DEDUPLICATE then WEAKEN for the absorbed id; Polymath refuses the whole batch | that an agent will emit two statements equal after Trail's normalisation |
| M1-04 | `advance leaked ContractViolation (harness_action: evidence_gaps/0/question: 'q…(2001)' is too long) instead of recording a typed outcome; the unit rolled back and the durable run is still 'running' at 'H_gaps' (gap=None, failure=None)` · second trigger: `… evidence_gaps/0/hypothesis_id: 'H1' does not match '^hyp_[0-9a-f]{8,64}$' …` · third: `a 1500-char executor error was not recorded as STEP_EXECUTOR_ERROR — advance leaked ContractViolation (adapter_step_receipt: validation/errors/0 … is too long)` | for BOTH triggers, on the in-memory store and on Postgres (uncommitted): `G_mechanisms` accepts the payload, `advance` raises, the unit rolls back, the run row stays `running` with no gap and no failure, a second `advance` raises again | **INFERRED, not reproduced:** the worker process exits (`process_one` has no handler), the poisoned run is re-claimed first on every restart (`claim_run` orders by `updated_at`), the supervisor quarantines the `adapter_step` slot after > 5 exits / 300 s, so every adapter run stops. STUBBED INPUT: that production Trail returns the long question / the foreign id unchanged |
| M1-05 | `the run is parked 'awaiting_agent' at 'C_hypotheses' with 0 citable evidence refs and NO lawful answer — all 4 honest payloads [...] are rejected … expires_at=None` | real plan / retrieve / graph executors against an orchestrator double returning lawful empty results; 4 honest payloads rejected; run parked | how often production returns nothing on all three lanes (not checked: it needs a live call) |
| M1-06 | `adapter_submit ACCEPTED a 176511-byte receipt that is inside the issued budget (80/80 observations), then J_admit ended the run 'failed': STEP_EXECUTOR_ERROR — ValueError: evidence.admit request exceeds Trail's 65536-byte canonical JSON ceiling … calls that reached Trail: 0. The receipt can no longer be corrected.` · same at **81,631 bytes** | both receipts were accepted at submit and killed `J_admit` locally before any Trail call; a corrected receipt was then refused (`run is terminal (failed)`); 81 observations against `max_observations = 80` validate | **Demonstrated condition (replaces "any realistic receipt"):** a schema-valid receipt within the 80-observation budget whose `evidence.admit` request exceeds 65,536 bytes of canonical JSON — shown at 81,631 bytes (80 observations of 240 / 400 / 200-char claim / excerpt / context) and 176,511 bytes (80 × 2,000-char claims). "33 maximum-length claims cannot fit" is arithmetic. That Trail enforces the same ceiling is READ |
| M1-07 | `S_supply handed the harness an action compiled from the O_territory PRODUCT_REALITY directive — source roles both PREFERRED and DISALLOWED: ['supplier_listing']; objective is the PRODUCT_REALITY one … on a SUPPLIER_RESEARCH action; no search intent targets the supply evidence role` | GIVEN a qualify result without a directive, the runtime reuses the older directive and emits that action; the pure `_compile_harness_action` test is red too | STUBBED INPUT: that production `opportunity.qualify` returns no directive (READ at `A41 research_operations.py:249-263`) — so "every production run" is an inference |
| M1-08 | `W_interpret asks the agent to 'Using the qualification and score records only, explain the outcome by record id…' but 8/8 of the authoritative Trail values are in NO public pre-terminal read (adapter_next incl. evidence, adapter_status)` | with a stubbed `V_score` output, none of its record ids / reason codes appear in `adapter_next` or `adapter_status`; `service.result` raises `NotTerminal`; a green characterization shows an INVENTED `trail_score_refs` entry is accepted into the result | the shape of production `V_score` output |
| M1-09 | `after the 422 no durable row records the rejected attempt (brief.receipt=None) \| after the accepted retry … no trace of the rejected attempt` · `the committed rejection receipt was replaced by the accepted one` | through the in-process public route: the rejection receipt is rolled back; even a committed one is overwritten by the accepted receipt | that both MCP servers reach `submit` only through this route |
| M1-10 | `the determination is erased; step output keys=['hypothesis_verdicts','open_gaps','operation_kind','trail_operation_id']` · `NO_ADMITTED_EVIDENCE in row=False` | the worker's translation drops a `REQUIRE_EVIDENCE` verdict and the persisted `L_judge` row keeps neither it nor its reason; green compat tests show the existing pin stays valid if the raw verdict moves to a new key | STUBBED INPUT: the verdict shape (READ; present in `A41 judgement.py:125`) |
| M1-11 | (a) `failed result omits failure ['code','message','step_id']` · (b) `open gap 'g-final' from the last permitted pass is absent from the terminal result \| the two terminal results are IDENTICAL once run-specific ids are blanked` · (c) `result.contradictions=[]` (two variants) | all three on real `_compile_result`; (c) also reproduced through an agent-authored contradiction, i.e. without M1-01 | — |
| M1-12 | `the first call validated (2 rows, contract.valid) but the executor returned only ['gap']` · `failing-call identity absent` · `F_retrieve output=null` | real `exec_retrieve` with a stubbed orchestrator: first packet valid, second `synthesis_performed: true` | — |

### 3. Counts
Polymath side: 34 red `correct_behaviour` tests, 0 collection errors. Trail side: 4 red. Every finding has ≥ 1 red test. All
green tests in that directory are characterizations, controls or rig sanity checks.

## Rejected claims
- "12 / 12 confirmed" as a bare statement. Correct statement: for all 12, the executed behaviour in the table is reproduced;
  the READ column is not.
- "The verifiers made no live calls." They used the shared Postgres (table above).
- "M1-04 takes the whole adapter fleet down." INFERRED from reading the worker, `claim_run` and the supervisor. Reproduced
  is: the exception escapes `advance` and the run stays `running`.
- "M1-06 is triggered by any realistic receipt." Demonstrated only at 81,631 and 176,511 bytes against the 65,536-byte ceiling.
- "M1-07 / M1-08 fire on every production run." They fire whenever Trail returns what the test double returns; that production
  Trail does so is READ.
- Severity labels are the verifiers' and mine, not measurements.

## Open contract gaps
Dispositions: no contract changed. `ADAPTER_RUNTIME` — DEFERRED defects M1-04..M1-12 (Polymath side) recorded; Trail-side
M1-01..03 belong to Trail governance (TG7), untouched. Everything else NOT_AFFECTED.

- **M1-04 fix — contract DEFINED, NOT implemented (blocked, below).** When a step cannot be issued because ITS OWN payload
  violates its contract (demonstrated: a gap question longer than HarnessActionV1 allows; a gap `hypothesis_id` that is not a
  ledger id), or when recording a failure would itself violate the receipt contract, the runtime must: (1) end that unit with
  a DURABLE typed outcome on the run — never leave it `running` with no reason; (2) PRESERVE the reason: which field, which
  rule, which step — without echoing an oversized value, without truncating the agent's question, without inventing or
  repairing an id, without a new limit; (3) let no exception escape `advance`, so the worker can take the next run. Both
  triggers, on both backends, must satisfy (1)–(3). Existing tests stay unchanged. Validation plan: the existing M1-04
  reproductions with `-k memory` only (no database).
- **BLOCKED BY THE HALT INSTRUCTION.** Its text: "HALT CURRENT EXECUTION. Do not continue the current R2a workflow, do not
  patch `PHI_VERDICT_INVALID`, do not start another run, and do not make additional architecture changes until this instruction
  has been incorporated into the plan of record." and "HALT implementation now. Update the plan and produce the
  requirements/gap matrix first." The M1-04 change is neither a `PHI_VERDICT_INVALID` patch, a run, nor an architecture
  change — but it IS implementation, and the instruction orders the plan update and the requirements / gap matrix FIRST.
  Neither exists: the instruction arrived inside a tool result, its authorship was never confirmed, and I did not act on it.
  **The exact unresolved decision, as put to the owner and never answered:** "Did you send that HALT message? — Yes: I leave
  Item 2D parked and first add the dossier requirements to the plan of record (docs only), then produce the requirement /
  exists / source / contract / renderer / gap / change / owner matrix and the tool-parity table, read-only … No implementation
  and no L_judge fix until you have seen the matrix. — No: I resume Item 2D."
- Remaining gaps the M1-04 containment would NOT close: `G_mechanisms` still accepts what `I_research` cannot carry (bounds
  and id checks are not aligned across manifest, HarnessActionV1 and Trail); a run ended this way loses its research
  opportunity instead of letting the agent correct the payload; the inferred worker / supervisor behaviour is untested.
- The reproductions for M1-04..12 still depend on the shared Postgres unless run with `-k memory` (M1-04..08) — M1-09..12
  need an isolated database before they are run again.
