# Polymath V5 — live implementation plan

**Generated. Do not edit by hand.** Regenerate with:

```
POLYMATH_PG_DSN=… .venv/bin/python eval/v5/implementation_plan.py --write
```

Build `5cb9846`. Every status below is a PREDICATE evaluated against the running system — source, config, compiled artefacts, database state — never a typed claim.

This file is generated because a hand-maintained plan drifts, and this repository has already paid for that: `SEMANTIC_CONTRACTS.md` declared rule pack v1.3.0 byte-frozen while `settings.py` shipped v1.2.0, and two admission gate chains were reported as qualified while having zero production callers.

`5 done · 11 open · 3 blocked · 0 unknown`

`?` means the probe could not observe the system. It is never folded into done.

## OPERATIONS TRACK — P0

- [ ] **CP1 Model residency / lifecycle manager** — `OPEN`
      Four models hold ~10 GB resident regardless of workload. Memory is sized for the maximum possible workload rather than the current one.
      *probe:* all four models stay resident regardless of workload; memory sized for peak, not current, demand

- [ ] **CP2 Backpressure and bounded batching** — `OPEN`
      300 books must ingest without memory spikes, duplicate work or queue starvation. Intake must slow when memory is high.
      *probe:* intake does not slow under memory/GPU pressure

- [ ] **CP3 Per-stage observability** — `OPEN`
      Every stage reporting in/out/failed/latency/memory. One unclaimable event starved 48 others for 40 minutes while all health was green.
      *probe:* no per-stage in/out/failed/latency/memory record; a starved queue is not visible as a starved queue

- [x] **CP4 Poison-event quarantine** — `DONE`
      A permanently unclaimable event must not block the queue behind it.
      *probe:* unclaimable events are skipped, not re-read forever

- [x] **CP5 Runtime budget enforced at boot** — `DONE`
      An over-committed fleet must be refused, not discovered by thrash.
      *probe:* supervisor refuses an over-committed fleet at boot

- [ ] **CP6 Unattended boot recovery** — `OPEN`
      launchd cannot execute a bootstrap under ~/Documents (exit 126), so the fleet does not come back after reboot.
      *probe:* bootstrap path inside TCC-protected tree (/Documents/); launchd exits 126 and silently does nothing

## SEMANTIC TRACK — P0 activate

- [x] **A1 Close the E6 type inventory** — `DONE` · **new contract required**
      E6 tests membership against 20 admissible types while 12 are reachable. It is a vacuous superset gate; wiring it as-is changes nothing while looking closed.
      *probe:* 12 admissible, all reachable

- [x] **A2 Wire ENTITY-KNOWLEDGE-ADMISSION-V1 (E1-E7)** — `DONE` · **new contract required** · depends on A1
      Built, tested, qualified, frozen -- and zero production callers. 'Figure 4-7' still mints durable graph identities today.
      *probe:* called from workers/workers/entity_admission_stage.py

- [ ] **A3 Wire FACT-ADMISSION-V1 (F1-F8)** — `OPEN` · **new contract required**
      Called only from eval/. Production ships the 38%-wrong graph; the 14.5% figure is a shadow-harness number, not production behaviour.
      *probe:* no worker/control/orchestrator imports fact_admission

- [-] **A4 Flip fact decisions out of shadow** — `BLOCKED` · **new contract required** · depends on A3
      All 8,744 persisted decisions carry shadow=TRUE. Cutover flips a flag; it never rewrites history.
      *probe:* blocked by A3 — 0 live of 8744 decisions (rest shadow)

## SEMANTIC TRACK — P0 repair

- [ ] **D0 Semantic bundle integrity at startup** — `OPEN`
      Declared contract and loaded runtime must be identical or the process must refuse to start. 'Mostly compatible' is how frames ran disabled in production while the docs said enforced.
      *probe:* nothing verifies that the loaded semantic bundle matches the declared contract; drift is silent

- [ ] **D1 Repair the compiled VerbNet trigger expansion** — `OPEN` · **new contract required**
      similar_to is authored with 3 verbs and compiles to 20, including banter, bargain, collaborate. This is the single largest source of wrong facts and it is a build-time bug in our own compiler.
      *probe:* similar_to compiled to 20 triggers from 3 authored (VerbNet class expansion): banter, bargain, collaborate, collide, commiserate, ...

- [ ] **D2 Pin the rule pack the docs declare** — `OPEN` · **new contract required**
      SEMANTIC_CONTRACTS declares v1.3.0 byte-frozen; settings ships 1.2.0, so frame arbitration is inert in production.
      *probe:* settings default 1.2.0 != documented 1.3.0

## SEMANTIC TRACK — P1

- [-] **D3 Restore refused-widening spans to argument binding** — `BLOCKED` · depends on A2, A3
      CORRECTED. Evidence is NOT destroyed: span_hypotheses holds 44,071 REJECTED/SUPPRESSED_SOURCE records with source offsets, durable in L1/L2. What is lost is the span's participation in ARGUMENT BINDING -- coverage, not evidence. The fix was attempted on candidate/rescue-discourse-v1-failed and FAILED its bar: keeping an unresolved-boundary span active produced wrong facts, and with no gate to catch them, 'no edge beats a wrong edge' was right. Once E1-E7 and F1-F8 are wired, the gate rejects those facts instead, so this becomes safe. Retry only after A2/A3, and A/B it on the bench.
      *probe:* blocked by A3 — refused widening still discards the accepted span (destroys upstream evidence on downstream failure)

- [ ] **D4 Stop projecting similar_to into the graph** — `OPEN`
      71% wrong, already T1-only and already excluded from retrieval, but still projected. Subtractive and reversible; evidence survives.
      *probe:* similar_to (71% wrong) still projected into the graph

## SEMANTIC TRACK — P1 entity

- [ ] **E1 Pronouns must fail durable identity** — `OPEN` · **new contract required** · depends on A2
      18.3% of endpoints on the bench are pronouns. Under R2 the answer is not a blacklist: a pronoun must fail durable identity and graph_eligible.
      *probe:* 11.3% of endpoints are pronouns (7868/69354)

- [ ] **E2 Type-stable identity keys** — `OPEN` · **new contract required**
      7.7% fragmentation, 0 wrong merges observed. 63% of F6 signature rejections involve a fragmented surface, so this is a recall win on facts. canonical_type() already does this for CONCEPT.
      *probe:* 7.69% fragmentation (target <= 4%)

## RELEASE

- [x] **R1 Retrieval baseline reproducible** — `DONE`
      FAST/HYBRID/GRAPH answering with zero errors on the bench.
      *probe:* FAST 8/8; HYBRID 8/8; GRAPH 8/8

- [-] **R2 Sealed holdout ingested and adjudicated once** — `BLOCKED` · depends on A4, D1
      The only admissible measurement. Sealed but never ingested, so gate_holdout is UNPROVEN and GRAPH is BLOCKED. Development numbers do not meet the bar even on development data.
      *probe:* blocked by A4, D1 — sealed holdout never ingested; gate_holdout returns UNPROVEN and GRAPH stays BLOCKED

## Sequencing is load-bearing

These orderings are not stylistic:

- **D1 before any span-pair candidate work.** Enumerating endpoint pairs against a contaminated trigger set amplifies the very defect D1 removes.
- **A1 before A2.** Wiring a vacuous E6 changes nothing while creating the impression of a closed gate.
- **A3/A4 and D1 before R2.** The holdout is adjudicated ONCE. Spending it on a build that still projects a 38%-wrong graph wastes the only admissible measurement available.
- **A3/A4 before raising graph depth.** Hop 2 over a graph with 14.5% wrong facts compounds error multiplicatively.

## Standing constraints

Anything marked *new contract required* alters mention interpretation, entity identity, graph eligibility, canonical membership or fact identity. Those get a NEW VERSIONED contract; frozen contracts are never mutated in place. Evidence survives; interpretation may change.
