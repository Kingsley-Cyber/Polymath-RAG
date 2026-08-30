# Semantic Corpus Rebuild — Findings Report, P2 through P5

Mission `POLYMATH_FINAL_SEMANTIC_CORPUS_REBUILD_AND_KILLCHAIN_CLOSEOUT_V1`.
Phases 2–5 of 20. Board state at time of writing: 5/20 done, tree clean,
HEAD `cec542e`.

Every number below was measured on this machine against the live
`cysa-study-v1` corpus or the sealed sentinel, never estimated. Nothing was
re-ingested — production rebuilds exactly once, at P14.

| Phase | Verdict | Commit |
|---|---|---|
| P2 CHUNK-STRUCTURE-V2 | new contract promoted | `dfb0dfd` |
| P3 PROCEDURE-ARTIFACT-V2 | new contract promoted | `ddc6b69` |
| P4 CONCEPT-INVENTORY-V2 | ceiling replaced by admission | `413e4f2` |
| P5 PARENT-SUMMARY-ENTITY-CAP | **no change required** | `e51985d` |
| SOURCE-RECOVERY-KEY-V1 | pinned as a P14 precondition | `e51985d` |

---

## P2 — CHUNK-STRUCTURE-V2

### The defect

`_pack_sentences` joined every sentence with a single space
(`workers/workers/chunker.py:205`, inside the frozen v1 packer at
`chunker.py:179`). Consequences measured in the live corpus:

- 0 of 7,085 child chunks contain a newline
- 5,246 of 7,085 (74.0%) carry a markdown heading glued mid-text

### Mechanism — and a correction to the pass-3 report

The prior report claimed `split_sentences` "drops the remainder" after a
glued heading. **That is false and was never measured.** Directly measured
here: 203 characters go in and 203 come out; nothing is deleted.

What actually happens is a **failure to split**. The boundary rule at
`workers/workers/summarizer.py:14` is

```
(?<=[.!?])\s+(?=[A-Z0-9"'(\[])|\n+
```

which requires `.`/`!`/`?` followed by a capital or digit. `#` is neither, so
`… features. ## Definition A vulnerability scanner is …` stays one sentence.
The definition therefore stops *beginning* a sentence, and the concept
patterns anchor on sentence start — so extraction is suppressed by a missing
anchor, not by lost text.

The correction is recorded at `chunker.py:52-62` and in the amended
`tests/determinism/test_killchain_pass2.py::test_line_flattening_suppresses_concept_detection`,
whose original comment asserted the false mechanism.

### The fix

`_reconstruct_separator` (`chunker.py:88`) rebuilds the separator that
actually stood between two packed sentences, using the source offsets the
packer already holds. Line *count* is normalised (one break, or a paragraph
break); the *indentation* of the following line is reproduced exactly
(`chunker.py:112`).

That second half is the part that mattered and was not obvious. Because
`split_sentences` strips every part it returns
(`summarizer.py:32-35`), a code line's leading spaces survive nowhere except
in that gap. **The first V2 draft discarded them and flattened code blocks
and sub-lists just as thoroughly as the space join did.** The gate caught it;
reading the diff did not.

`_pack_sentences_v2` (`chunker.py:116`) keeps v1's packing *decisions* — same
flush rule at `chunker.py:157` — so chunk boundaries stay comparable and the
measured gain cannot be a boundary artefact. Contract stamping is at
`chunker.py:74-85`; `plan_document` selects the generation via
`separator_mode` (`chunker.py:239`, dispatch at `chunker.py:278`) and refuses
an unknown mode (`chunker.py:256`) so no generation can be written without
naming its contract.

### Measured

On a fixture carrying every required structure class:

| | v1 | v2 |
|---|---|---|
| concept opportunities | 1 | 3 |
| procedure opportunities | 0 | 1 |
| chunks with a glued heading | 1 | 0 |
| chunks containing a newline | 0 | 2 |

Structure survival, all PASS under v2: 4- and 8-space code indentation, table
header/row adjacency, nested list hierarchy, transcript turn boundaries,
heading isolation.

Literal coverage at child targets 200/400/1200: zero unexplained loss, zero
overlap, every sentence in exactly one chunk and present verbatim. Heading
layout offsets — recomputed from real separator lengths, the silent-corruption
risk in this change — all land on heading text. v1 default output is
byte-identical to pre-V2.

### Gate

`tests/determinism/test_chunk_structure_v2.py` — 25 tests. Mutation-tested,
**5/5 caught**: separator collapsed to a space (10 red), indentation discarded
(4), default flipped to v2 (2), v1 offset arithmetic reused in v2 (3), packing
decisions diverged (3).

---

## P3 — PROCEDURE-ARTIFACT-V2

### The stated question, and what was actually wrong

The phase asked for local task granularity. Shadow-comparing four segmentation
units with the *same* step detector — so only the unit varied — on
`eval/v5/killchain/sentinel/sentinel_procedures.md` (three plainly separate
tasks, 20 steps):

| mechanism | artifacts | task-mixed | verdict |
|---|---|---|---|
| DOCUMENT | 1 | 1 | reject |
| SECTION | 2 | 1 | reject |
| PARENT_NEIGHBOURHOOD | 1 | 1 | reject |
| LOCAL_TASK_SEGMENTATION | 3 | 0 | **promote** |

SECTION fails because the two shorter tasks share one `##` heading;
PARENT_NEIGHBOURHOOD fails because the whole document fits inside one parent.

But granularity was **not** the main defect. Measuring recall first exposed two
others, both mechanism-level:

1. **Sentence shredding.** `split_step_sentences`
   (`shared/polymath_shared/knowledge_objects/procedure.py:79`) splits on every
   newline, so a hard-wrapped source line became two "sentences" —
   `Select the key` / `you intend to replace.` Steps were being cut in half by
   line wrapping, which is presentation, not structure.
2. **Whitelist recall.** `_is_imperative` (`procedure.py:41`) recognised a step
   only if its verb appeared in the hand-written `_IMPERATIVE` tuple
   (`procedure.py:22`). *generate, revoke, detach, attach, boot, capture,
   collect, record, notify, hand, confirm, close* were all invisible —
   **5 of 20 real steps seen**.

An open-class English verb list can never be completed, so extending it is not
a fix.

### The fix

V2 replaces the whitelist with a **closed-class exclusion** — the same doctrine
`entity_admission.CLOSED_CLASS_PRONOUNS` already uses. `NON_VERB_OPENERS`
(`procedure.py:189`) enumerates the function words that can open a declarative;
anything outside that closed set is treated as a bare verb.
`is_imperative_v2` (`procedure.py:293`) keeps the v1 whitelist as a **positive
override**, so it can only ever add.

Precision comes from subject detection inside `is_imperative_v2`: an admitted
entity opening the sentence, a following auxiliary, a capitalised second token,
a gerund, or third-person `-s` after a capitalised opener all mean token 0 was
the *subject*. That single family of signals separates
`Nessus scans network hosts` from `Scan the network`.

Supporting pieces: `unwrap_soft_lines` (`procedure.py:253`) repairs hard wraps;
`strip_non_prose` (`procedure.py:237`) drops fenced code, headings and table
rows; `_GOAL_MARKER` (`procedure.py:233`) recovers the goal clause *and* the
first step from `To rotate an API credential, open the credential console.`;
`segment_tasks` (`procedure.py:349`) and `compile_procedures`
(`procedure.py:395`) emit one artifact per local task.

**P3 depends on P2.** Table rows, code fences and headings are excludable only
because CHUNK_CONTRACT_V2 preserves line structure — under v1 chunk text,
`| Port | Service | Notes |` and a sentence were the same flat string, and both
were being read as steps.

### Measured

3 artifacts with goals `rotate an API credential`, `restore a host from
backup`, and the containment opener; step sets disjoint; all 20 source steps
recovered, verbatim, in source order. Precision held — the facts, boilerplate
and transcript sentinels each yield **zero** artifacts.

### Wiring

`workers/workers/extract_worker.py:1605` now iterates tasks and accumulates at
`:1625`, replacing a literal `counts["procedures"] = 1`. The opportunity
counter moved to `count_opportunities_v2` (`extract_worker.py:1593`;
`procedure.py:342`) so *accepted* can never exceed *opportunities seen*. The
existing callsite pin in
`tests/determinism/test_semantic_lane_liveness.py` was updated deliberately
rather than bypassed — it correctly blocked the silent swap.

No migration: `procedure_artifacts` is keyed by content-addressed
`procedure_id` (`stores/postgres/migrations/0033_knowledge_artifacts.sql:9`)
and already permits N rows per document.

### Gate

`tests/determinism/test_procedure_artifact_v2.py` — 20 tests. Mutation-tested,
**7/7 caught**: whitelist-only detection (9 red), no soft-wrap repair (3), no
non-prose stripping (2), no subject detection (3), document-scope segmentation
(4), goal from first step (1), worker persists one artifact (1).

---

## P4 — CONCEPT-INVENTORY-V2

### The defect

`max_concepts=10` was a **storage ceiling**, not a summary limit:
`compile_concepts` stopped *scanning sentences* once it held ten, so a
400-page book stored ten concepts and never read the rest of itself.

Live corpus: **12 of 13 documents held exactly 10 concepts** — pinned by
construction — while `knowledge_lane_attempts` recorded **2,210 opportunities
against 120 accepted (5.4%)**.

### The isolation that mattered

Both effects were measured separately across all 18 documents, rebuilt from
the retained spool:

| arm | text | cap | concepts | reading |
|---|---|---|---|---|
| A | v1 | 10 | 121 | what production holds |
| B | v1 | none | 975 | **P4 alone, ×8.1** |
| C | v2 | 10 | 122 | **P2 alone, ×1.0** |
| D | v2 | none | 1,236 | P2+P4, ×10.2 |

**Arm C is the trap.** It reads as "P2 was worthless." It is not: with the
ceiling in place every document is *already* pinned at ten, so structure
preservation cannot show up at all. P2's real contribution is B → D, **+261
concepts (+27%)**, entirely masked while the cap bound. This is precisely why
the phase required the two effects measured separately.

### Why lifting the cap alone would have been wrong

Of the 1,236 uncapped concepts, **32% were not concepts**: sentence fragments
(`exercises as a`, `found in victim environments,`,
`framework called Kansa, as a`), bare generics (`information`, `command`),
participles (`touched`, `running`), subordinate fragments
(`authentication as the sole`).

The cap had been doing quality work **by accident**. Removing it without
replacing that job would have produced exactly the unlimited noun-phrase junk
the phase forbids.

### The fix

`concept_name_admissible`
(`shared/polymath_shared/knowledge_objects/concept.py:294`) takes the job over.
Every rule is a closed-class test and every refusal carries a reason. It
**reuses `entity_admission`'s own lists** — `GENERIC_HEAD`,
`WEAK_MODIFIERS`, `DEICTIC_MODIFIERS` — rather than forking a parallel
vocabulary that would drift (`concept.py:271`, imported at `concept.py:240`).
Supporting closed classes: `_EDGE_FUNCTION` (`concept.py:253`),
`_INTERNAL_SUBORDINATOR` (`concept.py:286`), `_FINITE_VERB` (`concept.py:277`),
`_FRAGMENT_PUNCT` (`concept.py:291`), `_BARE_PARTICIPLE` (`concept.py:274`).

`compile_concept_inventory` (`concept.py:341`) reads every sentence and stamps
`summary_rank` / `in_summary`, so the top-N survives as a **slice** rather than
a storage decision. The v1 early-stop is preserved for positive caps and
disabled for `max_concepts <= 0` (`concept.py:192`).

Result: **1,236 → 844 admitted; 0 of 18 documents now sit at exactly ten.**

### Wiring

`workers/workers/extract_worker.py:1635` stores the inventory with provenance.
The lane no longer reports `capped=counts["concepts"] >= 10`
(`extract_worker.py:1672`): with no ceiling, a shortfall means admission
refused a candidate — a quality decision with a recorded reason, not silent
truncation. No migration; `concept_artifacts.provenance` jsonb already exists
(`0033_knowledge_artifacts.sql:41`).

One document dropped 1 → 0 concepts. Verified a **correct** rejection: the
extracted name was the bare generic `process`, having lost its modifier
upstream.

### Gate

`tests/determinism/test_concept_inventory_v2.py` — 38 tests. Mutation-tested,
**8/8 caught**: ceiling restored (1 red), cap semantics inverted (3),
admission disabled (14), punctuation fragments allowed (3),
generic/participle allowed (5), summary slice decoupled (1), worker back on
the capped compiler (1), vocabulary forked from `entity_admission` (1).

---

## P5 — PARENT-SUMMARY-ENTITY-CAP → **no change required**

### The narrow question

> Can information about entity #11+ become **unreachable** because it was
> omitted from the parent summary?

Not "is 10 too small". The metric is `omitted_entity_query_recall`, never
entities-per-summary.

### Setup

`MAX_ENTITIES = 10` (`shared/polymath_shared/parent_summary.py:47`), applied at
`parent_summary.py:87` to an **alphabetically sorted** set
(`parent_summary.py:84`) — so membership is arbitrary with respect to
importance, which makes it a fair thing to test.

Cap binding, measured: **1,772 of 3,025 parent summaries (58.6%) sit at exactly
10**, against parents holding up to 67 durable surfaces.

Sample: 280 cases across 11 parents holding 26–67 durable entities, drawn at
positions 1–5 and 6–10 (controls, in summary), 11–15, 16–25 and last (omitted).
Queried through FAST and HYBRID, `limit=10`, all lanes live. Reranker confirmed
genuinely active — real `g3_score` values and `pre_g3_order != post_g3_order` —
so this is not a degraded-run artifact.

### Result

| group | n | exact | parent | surface | **unreachable** |
|---|---|---|---|---|---|
| IN summary (entities 1–10) | 85 | 12.9% | 12.9% | 61.2% | **38.8%** |
| OMITTED (entity 11+) | 195 | 13.3% | 13.3% | 69.2% | **30.8%** |

Omission moves unreachability by **−8.0 points**. Entities the cap *dropped*
come back slightly **more** often than the ones it kept.

**The control is what makes this readable.** Without it, "60 of 195 omitted
entities unreachable" looks like proof of loss — and the first automated
verdict in the analysis script said exactly that, OUTCOME B. It was wrong:
33 of 85 in-summary controls are unreachable too. The cap is not the variable.

### Mechanism — why the numbers had to come out this way

- `parent_summaries.entities` is read on **no** retrieval path: zero references
  in `shared/polymath_shared/pass1.py`, `shared/polymath_shared/hybrid.py`,
  `orchestrator/orchestrator/api/fast.py`,
  `orchestrator/orchestrator/api/retrieve.py`.
- Section routing embeds `retrieval_summaries.summary_text`, which is prose
  extracted from the source. The entity list is a separate payload field
  (`parent_summary.py:87`) and never enters the embedded text.
- Therefore summary membership **cannot** influence whether a section is routed
  to. Omitted evidence returned via `MULTI_REPRESENTATION` (36),
  `GLOBAL_CHILD_RESCUE` (8) and `SECTION_LED` (4) — never a summary-entity
  lookup, because no such lookup exists.

### Verdict

**OUTCOME A — routing-only cap.** `MAX_ENTITIES` stays 10; no code changed.
Summaries are compressed routing representations, and being selective is their
job.

Evidence artifact: `eval/v5/killchain/P5-ENTITY-CAP-REACHABILITY.json`.

### Gate

`tests/determinism/test_parent_summary_entity_cap.py` — 5 tests. It pins the
mechanism (no retrieval module may read `parent_summaries`; the entity list may
not enter the summary text), and pins the verdict **together with its control**
so the conclusion cannot be quoted without the comparison that justifies it.

---

## SOURCE-RECOVERY-KEY-V1 — pinned before the one rebuild

A `documents` row carries two hashes and only one addresses a spool object:

- `source_hash` — sha256 of the **original uploaded bytes**. This is the spool
  key; the blob exists.
- `content_hash` — sha256 of the **materialized text**. Nothing was ever
  spooled under it.

Measured on `cysa-study-v1`: **0 of 12 documents resolve via `content_hash`;
12 of 12 via `source_hash`.**

The failure mode is why this earns a permanent gate rather than a comment.
Reaching for `content_hash` does not fail like a lookup bug — it returns "not
found" for every document *simultaneously*, which reads as "the retained corpus
is gone". That turns a fully recoverable rebuild into an apparent data-loss
event, which is the worst available way to be wrong during P14. This cost real
time during P4 before being diagnosed.

Recovery now goes through one authority: `SOURCE_RECOVERY_KEY`
(`shared/polymath_shared/blob_spool.py:140`), `document_source_ref`
(`blob_spool.py:143`) and `read_document_source` (`blob_spool.py:162`), the
last of which inherits `spool_read`'s integrity check.

Gate: `tests/determinism/test_source_recovery_key.py` — 6 tests, including a
live P14 precondition asserting every rebuildable document resolves. Recorded
on the P14 phase in `MISSION-STATE.json`.

Mutation-tested across P5 + source-key, **6/6 caught**: `content_hash` recovery
(3 red, including the live precondition), error stops naming the wrong key (1),
cap widened (1), a retrieval lane reads `parent_summaries` (1), evidence
rewritten so omitted look worse than control (1), separate P16 finding folded
away (1).

---

## Findings carried forward, not fixed here

Recorded in `MISSION-STATE.json` on their owning phases.

**→ P16 RETRIEVAL-QUALIFICATION.** ~33% of bare entity-name queries fail to
surface their evidence at top-10 in either FAST or HYBRID, **independent of the
cap** (controls 38.8% unreachable vs omitted 30.8%). Exact-chunk recall is only
~13% against 61–69% surface recall — the system usually returns a *different*
chunk mentioning the entity. Widening the summary would have aimed at the wrong
mechanism, and the P5 gate actively refuses to let this be folded into the cap.

**→ P17 RECONCILIATION.** 1,241 of 3,025 `parent_summaries` rows are
duplicates: each of those parents carries an empty-entities row *and* a
populated row, same `contract_version`, minutes apart. Reconciliation must
decide which is authoritative and whether the empty row is projected. This also
silently corrupted the first P5 sample until the latest row was selected
explicitly.

**Operational, outside mission scope.** The orchestrator does not auto-load
`.env` (`model_config` has `env_file: None`), so it falls back to a built-in
Postgres password that does not match the deployed one. The long-running
instance on port 7200 returns 500 on `/retrieve` for this reason. P5 was run
against a separate instance on 7201 with the environment loaded; the 7200
process was left untouched.

---

## Corrections issued during this work

1. **`split_sentences` does not drop content.** The pass-3 report's claim was
   false; the mechanism is failure-to-split. Corrected at `chunker.py:52-62`
   and in `test_killchain_pass2.py`.
2. **P5's first automated verdict (OUTCOME B) was wrong**, because it evaluated
   the omitted group without the control. Corrected to OUTCOME A.
3. **Reranker was reported down** during an early probe; re-checked and it was
   genuinely live and reordering. The P5 result stands on a full lane set.
4. **Two P5 mutations first appeared to survive.** Both were harness bugs — a
   quote mismatch in the patch string and an EXIT trap firing inside a command
   substitution — not weak gates. Re-verified individually: all caught.

---

## Reproduction

Suite, excluding five files that cannot be **collected** because the GLiNER
sidecar on `:8740` is down (verified pre-existing at HEAD; none reference the
chunker):

```
.venv/bin/python -m pytest tests/determinism tests/contracts -q \
  --ignore=tests/determinism/test_batched_pass1.py \
  --ignore=tests/determinism/test_i3r_r6_provenance.py \
  --ignore=tests/determinism/test_kimi_observability_phase5.py \
  --ignore=tests/determinism/test_s4b_single_allocation.py \
  --ignore=tests/determinism/test_syntax_batching.py
```

**83 failed** at every phase boundary — byte-identical to the pre-P2 baseline,
compared as a sorted set of test ids, not merely as a count.

New gates added by P2–P5: 94 tests (25 + 20 + 38 + 5 + 6), all passing,
26 mutations applied and 26 caught.
