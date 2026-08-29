# Convergence Plan — from audit to freeze

Owner direction, 2026-08-28: stop open-ended forensic discovery. The major
architectural mistakes are found. The goal now is convergence — close the real
defects, freeze, rebuild once, prove end to end, stop.

Board: `eval/v5/killchain/MISSION-STATE.json` · driver: `scripts/mission_next.py`

---

## The rule that governs everything below

> **RELEASE-BLOCKER RULE.** Do not create work because a metric is imperfect.
> A finding blocks release **only** if it demonstrably causes one of: source
> loss, false knowledge, unsupported answers, inability to retrieve
> answer-bearing evidence, corpus leakage, or pipeline failure. Everything else
> is recorded and deferred. No further open-ended forensic audits are
> authorised.

Recorded in `MISSION-STATE.json` under `release_blocker_rule`, applied to every
phase below.

### Why the audit felt worse than it was

The live corpus is still built with the **old** contracts, verified:

| evidence | value | meaning |
|---|---|---|
| `chunks.chunk_contract_version` | NULL for all **8,887** rows | pre-V2 chunking |
| `procedure_artifacts` | 13 rows / 13 documents | old one-per-document contract |
| `concept_artifacts` | 121 rows / 13 documents | old cap-10 contract |

So a report saying "the corpus still shows flattened chunks / giant procedures /
capped concepts" is describing **old data**, not failed new code. Not rebuilding
after every fix was the correct choice; it just makes the ledger read worse than
it is.

---

## Ledger — reclassified

### Closed

| item | evidence |
|---|---|
| Chunk structure V2 | `workers/workers/chunker.py:88,116` · gate `tests/determinism/test_chunk_structure_v2.py` (25) · `dfb0dfd` |
| Procedure extraction V2 | `shared/polymath_shared/knowledge_objects/procedure.py:293,349,395` · gate (20) · `ddc6b69` |
| Concept inventory V2 | `shared/polymath_shared/knowledge_objects/concept.py:294,341` · gate (38) · `413e4f2` |
| Parent-summary entity cap | **not a problem** — routing-only, proven · `P5-ENTITY-CAP-REACHABILITY.json` · `e51985d` |
| Source recovery key | `shared/polymath_shared/blob_spool.py:140,143,162` · gate (6) · `e51985d` |
| **Pronoun facts** | **already closed at P1** — 0 live endpoints, 524 retirements, gate green (26) · `d40b9d7` |

Pronoun facts appeared on the working "still important" list. Re-measured
directly: `facts` joined to `entities` on closed-class surfaces returns **0**
rows with `decision <> 'REJECT'`, against 2,627 active facts. The admission gate
(`shared/polymath_shared/entity_admission.py:150`) decides pronouns **first**, so
the rebuild cannot reintroduce them. It belongs in the closed column.

### Open and blocking

| phase | defect | why it meets the bar |
|---|---|---|
| **P6** | FACT under-recall — clean SVO sentinel sentences gave 3 candidates, 0 accepted | unsupported answers |
| **P8** | `source_sentence[:300]` truncation | inability to retrieve answer-bearing evidence — *bounded check, not a redesign: if it hydrates from the authoritative chunk, close it* |
| **P9** | deletion does not prune derived graph state | false knowledge (stale nodes answer queries) |
| **P10** | bundle-stale quarantine reports IDLE, not BLOCKED | pipeline failure, masked — hit twice already, will be hit by the rebuild |
| **P21** | orchestrator does not load `.env`; falls back to a wrong Postgres password | pipeline failure — `/retrieve` 500s on a normally-launched instance |
| **P23** | summary idempotency — control plane **and** code | false knowledge + pipeline failure during the rebuild |

### Deferred by the rule

| phase | reason |
|---|---|
| P11 killchain invariance | no observed symptom; re-open only if P14/P15 shows non-determinism |
| P18 fault injection | 13 speculative mutations; P1–P5 gates are already mutation-tested |
| P19 crash recovery | no observed symptom; re-open if the rebuild actually crashes |
| P20 unknown-unknown sweep | this is the open-ended discovery that was cancelled; replaced by P22 |

### Recorded, not acted on

P5 measured ~33% of bare entity-name queries missing their exact expected chunk
at top-10, with 13% exact recall against 61–69% surface recall. **This is not a
defect to redesign around.** Retrieval is probabilistic ranking, and the 61–69%
shows the system routinely finds the entity through a different evidence path.
The question is whether final answers are reliably supported — evaluated at P16
against the answer, not against an internal ranking metric.

---

## P23 — the finding that changed classification

I first called duplicate parent summaries "verified not harmful" by looking only
at present-state harm. That was wrong. It is **two defects**:

**Control plane.** `summary_jobs` has no uniqueness beyond the surrogate
`ticket_id` — the only indexes are `summary_jobs_pkey (ticket_id)` and
`summary_jobs_corpus_state_idx (corpus_id, stage, state)`. Measured:

```
PARENT_SUMMARY tickets : 21,315
distinct input_hash    :  3,025      -> same work ticketed 7.0x, up to 12x
distinct parents       :  1,784
```

533 input_hashes carry 12 tickets each; 1,053 carry 8.

**Code.** `shared/polymath_shared/summary_runtime.py:72-79` writes
`parent_summaries` with `ON CONFLICT (summary_id) DO NOTHING`, where
`summary_id` is content-addressed. A parent summarised before its entities were
ready and again after keeps **both** rows, with nothing marking which is
authoritative. Measured: 3,025 rows for 1,784 parents; 1,241 parents hold two
rows written 4h15m apart with different `artifact_hash`.

**Why it blocks P13/P14.** The rebuild re-tickets every parent *while* changing
contract generation. The same mechanism that produced empty-then-populated pairs
can leave one parent holding an old-contract row and a new-contract row
simultaneously — exactly the half-old/half-new generation P13 exists to make
impossible — and inflates P17 reconciliation counts.

**The gate gap, found by dependency routing.**
`tests/integration/test_summary_runtime_d2.py:36::test_lifecycle_and_idempotency`
exists and **passes**. It has two blind spots:

1. It explicitly accepts re-ticketing — its own comment reads *"a retried
   attempt arrives on its OWN ticket"* — so it asserts artifact dedup while
   permitting unlimited ticket re-issue.
2. It never varies the input for a fixed parent, so the two-generations-per-parent
   case is untested.

That is why 7× duplication survived a passing idempotency test.

---

## Dependency routing (graphify)

Installed and wired for this repo. Deterministic AST extraction, **no LLM**.

```bash
graphify update .          # rebuild, ~12s -> 12,224 nodes / 18,132 edges
```

Scope is controlled by `.graphifyignore` (excludes `.venv`, `.venv-gliner2`,
sidecar venvs, `node_modules`). Output `graphify-out/` is generated and
gitignored — never commit it, rebuild it.

**The command that matters for fixing things** — reverse traversal, "what breaks
if I change this":

```bash
graphify affected "run_parent_summary_ticket" --depth 2
graphify affected "_build_pool" --depth 1
graphify path "A" "B"        # shortest path between two symbols
graphify explain "X"         # a node and its neighbours
```

`affected` is the deterministic router: it returns callers with `file:line`. It
is what found the P23 gate gap above — one query surfaced `_do_parents()` at
`workers/workers/summary_worker_impl.py:117` (the ticket issuer) and the passing
idempotency test that permits re-ticketing.

`query` is a broader BFS and is noisier here, because only AST edges exist (no
semantic extraction was run). Prefer `affected`/`path` for dependency questions.

**Working rule for every remaining phase:** before editing a symbol, run
`graphify affected "<symbol>"` and treat the returned callers and tests as the
blast radius to keep green.

---

## The plan

| step | phases | gate to pass |
|---|---|---|
| 1 | ~~pronoun facts~~ | already closed at P1 |
| 2 | **P6** diagnose FACT under-recall; fix only if a real defect | clean positives recover; negation/hedge/quotation hard negatives stay clean; **no global threshold loosening** |
| 3 | **P8, P9, P10, P21, P23** mechanical + correctness defects | each with a mutation-tested gate |
| 4 | **P7** (confidence: drop or declare non-signal), **P13** FREEZE all contracts | full regression green; no half-old/half-new generation possible |
| 5 | **P14** rebuild the 12-book corpus **ONCE** | precondition: `tests/determinism/test_source_recovery_key.py` green |
| 6 | **P12** sealed sentinel, **P15** measurement, **P16** retrieval, **P17** reconciliation | answers reliably supported; missing=0 orphan=0 foreign=0 |
| 7 | **P22** release decision | no finding meets the release-blocker bar → **stop modifying ingestion and retrieval** |

Standing constraints, unchanged:

- Production rebuilds **exactly once**, at P14. Never re-ingest to test a contract.
- Never loosen a threshold to make a number look better — find the mechanism.
- Suite must stay byte-identical to the 83-failure baseline, compared as a
  sorted set of test ids, not as a count.

After P22, the RAG architecture is done unless real usage exposes a regression.

---

## Release-engineering doctrine (owner, 2026-08-28)

Four things matter before the pipeline is finished. Everything else is
subordinate.

| # | Must resolve | Why | Approach |
|---|---|---|---|
| 1 | **P6** FACT under-recall | may be silently destroying valid knowledge | trace to the **first rejection**; fix only that mechanism, and only if the fact should have survived |
| 2 | **P23** summary idempotency | can mix old/new generations during the rebuild and leave summary authority ambiguous | fix ticket identity + persistence uniqueness + deterministic supersede semantics **before** reprocessing |
| 3 | **P21** orchestrator config | correct code that boots with wrong credentials and 500s is not production-ready | one explicit config contract; fail loudly instead of falling back |
| 4 | **P13/P14 + qualification** | V2 contracts exist in code but the live corpus is old-generation | freeze, rebuild once from `source_hash`, reconcile, then prove FAST/HYBRID/GRAPH → evidence → citation → answer |

### Where to look for problems: boundaries, not random code

```
SOURCE →A→ CHUNK →B→ SEMANTIC OBSERVATION →C→ CANDIDATE →D→ ADMISSION
→E→ DURABLE KNOWLEDGE →F→ SUMMARY/REPRESENTATION →G→ QDRANT/NEO4J
→H→ RETRIEVAL →I→ RERANK →J→ EVIDENCE BUNDLE →K→ ANSWER/CITATION
```

At every boundary, exactly four questions:

1. Can valid information disappear here?
2. Can invalid information be created here?
3. Can the same logical thing be produced twice?
4. Can the component fail while appearing healthy?

That is the whole search strategy. No further hypothesis brainstorms.

### What is and is not a defect

**Is:** wrong knowledge · lost valid knowledge · unreachable answer-bearing
evidence · cross-corpus leakage · a pipeline that silently stops · a component
reporting healthy while dead · duplicate data **when authority or idempotency is
ambiguous**.

**Is not:** a weird metric · a low metric · 13% exact-chunk recall when another
authoritative chunk answers correctly · a cap that does not affect reachability ·
old-generation data (that is not evidence new-generation code failed).

### The rule that prevents symptom-chasing

> **Never fix where the symptom appears until you identify the first bad
> boundary upstream.**

```
bad answer        ≠  change the prompt
missing chunk     ≠  raise top_k
missing concept   ≠  raise max_concepts
duplicate summary ≠  SELECT DISTINCT  /  ORDER BY created_at DESC LIMIT 1
missing fact      ≠  lower the admission threshold
```

Trace backward to the first incorrect transformation, repair *that*.

### Finish line

P6 understood and repaired-or-closed → P23 idempotent and generation-aware →
config deterministic → freeze → **one** rebuild → fresh source through chunks,
facts/procedures/concepts, summaries, Qdrant/Neo4j, FAST/HYBRID/GRAPH, evidence,
citations, correct answer.

Passing with no demonstrated source loss, manufactured knowledge, corpus leakage
or answer-breaking retrieval failure → **stop**. Reopen only when real usage or a
targeted regression demonstrates an actual failure.
