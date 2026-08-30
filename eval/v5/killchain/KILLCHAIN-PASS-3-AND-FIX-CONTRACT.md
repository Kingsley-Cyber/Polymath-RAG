# KILLCHAIN PASS 3 + FIX CONTRACT

Date: 2026-08-28 · Branch `architecture/evidence-first-v5`
Baseline: `0732fbe` (pass 2)

**Pass 3 built the sealed sentinel and, on its first run, it earned its
keep: it proved a P1 that three prior passes had mis-classified as
cosmetic. Line-flattening does not merely misrepresent structure — it
CAUSALLY DESTROYS semantic extraction.**

Part 1 records the pass-3 findings. Part 2 is the **fix contract** —
each open defect written as an implementable, verifiable unit.

---

# PART 1 — PASS 3 FINDINGS

## The sentinel (Phase 13) — BUILT

`eval/v5/killchain/sentinel/` — four sealed synthetic documents (no
copyrighted text), ingested through the **public production path**
(`POST /upload` → intake → chunk → extract → artifacts → projection).

| document | contains |
|---|---|
| `sentinel_facts.md` | clean SVO facts, passive voice, a negated non-fact, a hedged non-fact, two definitions |
| `sentinel_procedures.md` | two distinct procedures in ONE section, plus a long task |
| `sentinel_transcript.md` | speaker turns, disfluency + self-correction, ambiguous acronym (IR), exact identifiers (CVE-2023-38831, 802.11), a markdown table, a Python block |
| `sentinel_boilerplate.md` | author bio, copyright, marketing — must produce NOTHING |

### Sentinel results

| document | children | procedures | concepts | relation candidates | facts |
|---|---|---|---|---|---|
| boilerplate | 1 | 0 | 0 | 1 | 0 |
| facts | 1 | 0 | **0** | 3 | **0** |
| procedures | 1 | 1 | 0 | 0 | 0 |
| transcript | 1 | 0 | 0 | 0 | 0 |

- **Boilerplate negative: PASS.** Produced no procedure, no concept, no
  fact. The negative case holds.
- **Procedure: PARTIAL.** One artifact from 5 detected opportunities —
  correct that it fired, but the document contains THREE distinct tasks
  and yielded one, confirming the document-scope ceiling on fresh data.
- **Concept: FAIL — and this is the P1 below.**
- **Fact: 3 candidates, 0 accepted.** Clean SVO sentences ("Nessus was
  developed by Tenable") produced candidates but no admitted facts.
  Under-recall, not incorrectness; not separately diagnosed this pass.

## P1 (NEW) — line flattening destroys concept extraction

The sentinel's `knowledge_lane_attempts` row said `concept
opportunities = 0` for `sentinel_facts.md`. The compiler run standalone
on the same file detects **1**. That discrepancy is the whole finding.

**Controlled experiment** (same content, two forms):

```
source form : "A vulnerability scanner is a tool that inspects hosts…"
              -> 1 concept opportunity          DETECTED
stored form : "…exploitation features. ## Definition A vulnerability
               scanner is a tool that inspects hosts…"
              -> 0 concept opportunities        MISSED
```

**Two mechanisms, both caused by the chunker's `" ".join`:**

1. The markdown heading is glued mid-text, so the definition no longer
   begins the sentence and `_DEFINE_PATTERNS` cannot anchor.
2. Worse — `split_sentences` on the glued form returns **one fragment**
   and **drops the remainder entirely**. The definition text does not
   merely fail to match; it disappears from the sentence list.

**Blast radius on live data: 5,246 of 7,085 chunks (74.0%) contain a
heading glued mid-text.**

This re-classifies the pass-1 finding. Structure loss was recorded as
**P2 (misrepresentation)**. It is **P1 (valid knowledge permanently
lost)**, and it is a direct contributor to the 5.43% concept capture
ratio — headings precede definitions throughout technical books, which
is exactly where definitions live.

## Remaining hypotheses

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H33 | Transcript | **PASS (structural)** | transcript ingested through the real path; speaker turns, disfluency, acronym and identifiers survive into chunk text. No parallel truth system. Produced no artifacts — a recall observation, not a failure. |
| H47 | Order dependence | **NOT TESTABLE AS DESIGNED** | identical content cannot exist in two corpora — `CROSS_CORPUS_CONTENT_COLLISION` refused `sentinel-b` (4 runs stuck at `intake`). The duplicate guard working correctly BLOCKS the standard order-dependence experiment. Requires near-duplicate content instead. |
| H36 | Batch / concurrency invariance | **UNAUDITED** | needs controlled re-ingest at varying batch sizes |
| H45 | Irrelevant-data metamorphic | **PARTIAL** | corpus-scoped collections make cross-corpus interference structurally impossible (H27 PASS); same-corpus dilution untested |

**Cumulative: 45 of 50 audited.** Unaudited: H36. Partial: H45, plus
the four from pass 1.

## Operational note

The sentinel ingestion stalled on first attempt with zero tickets
minted — `BUNDLE_STALE_CODE_DRIFT`, because worker code had changed
since the last fleet restart. The execution-bundle fence behaving
exactly as designed. Restart cleared it. Worth knowing: **after editing
worker code, the fleet must be restarted or ingestion silently stops.**

---

# PART 2 — FIX CONTRACT

Each item is written to be implemented and verified independently.
`GATE` is the existing test that proves the fix landed.

---

## FIX-1 · Preserve line structure in chunk text — **P1**

**Defect.** `_pack_sentences` joins sentences with `" "`
(`workers/workers/chunker.py:72`). Zero of 7,085 chunks contain a
newline. 74% carry a heading glued mid-text. This destroys code
indentation, table rows and list hierarchy, AND suppresses concept
detection (proven above).

**Contract.**
- Preserve `\n` between sentences that were separated by a line break in
  the materialized source.
- Never glue a markdown heading to following prose.
- `split_sentences` must not drop content following a heading token.

**Blast radius.** `chunk_id` is content-addressed
(`chunk_id(doc_id, i, spec.text)`). Changing the join **re-identifies
every chunk** and invalidates every downstream artifact, receipt and
citation. This is a NEW CHUNK CONTRACT, not an edit.

**Migration.** Requires re-ingest. Source is retained on the spool
(9.6 MB) — no re-upload needed. Ship under a new
`CHUNK_FROZEN_PARAMS` contract version so old and new generations are
never silently equated.

**GATE.** `test_line_flattening_suppresses_concept_detection` inverts:
the stored form must begin detecting the definition.
Also re-measure concept capture (baseline 5.43%).

**Owner decision required:** yes — re-ingest of the production corpus.

---

## FIX-2 · Reject pronouns as fact endpoints — **P1**

**Defect.** 557 of 3,184 facts (17.5%) carry a pronoun endpoint:
`you --instance_of--> microsoft`, `you --founded--> organization`.
`you` resolves to 747 distinct entity_ids. 7 such facts reached Neo4j;
the fact projection's `MERGE (s:Entity {entity_id: …})` creates the
endpoint node even though entity eligibility refused it — so
`they --uses--> ssh` is answerable.

**Contract.**
- A closed-class pronoun may never be a fact subject or object.
- Closed list, not a heuristic — a `GENERIC_HEAD` vocabulary already
  exists in `shared/polymath_shared/reach.py`; apply it at
  fact-endpoint admission.
- Existing polluted facts: retire, do not silently delete — preserve
  disposition.

**Blast radius.** Removes ~17.5% of the fact ledger. No chunk or
embedding identity changes. No re-ingest.

**GATE.** `test_pronoun_endpoints_in_the_fact_ledger_are_bounded`
(currently pins ≤25%, baseline 17.5%) — tighten to ≤1% after the fix.
Plus: zero pronoun REL edges in Neo4j.

**Owner decision required:** yes — this narrows what counts as a fact.

---

## FIX-3 · Compile procedures at section scope — **P2**

**Defect.** `compile_procedure` returns one artifact per DOCUMENT.
965 opportunities → 12 artifacts (1.24%). Artifacts conflate unrelated
imperatives (172 steps in one). Confirmed on fresh sentinel data: a
document with three distinct tasks yielded one artifact.

**Contract.**
- Compile at section / parent-neighbourhood scope, not document scope.
- A section may contain multiple procedures; one procedure may span
  adjacent neighbourhoods.
- Preserve: goal coherence, step order, source contiguity,
  non-overlapping tasks.

**Method.** SHADOW → QUALIFY → PROMOTE. Shadow candidates: DOCUMENT
(current), SECTION, PARENT_NEIGHBOURHOOD, LOCAL_TASK_SEGMENTATION.
Qualify on the sentinel (known 3-task document) plus real books.

**GATE.** Sentinel `sentinel_procedures.md` must yield **3** artifacts
with disjoint step sets. Capture ratio re-measured via
`scripts/semantic_lane_census.py`.

**Owner decision required:** yes — changes what a PROCEDURE is.

---

## FIX-4 · Separate durable concept inventory from the summary cap — **P2**

**Defect.** `max_concepts=10` per document binds in 12/12 documents.
2,210 opportunities → 120 artifacts (5.43%). A cap is deciding recall.

**Contract.**
- Durable concept inventory is NOT capped by a presentation constant.
- "Top N concepts" remains a SUMMARY/ROUTING concern.
- Admission quality still governs — no unlimited junk.
- Order: FIX-1 first; a large share of the missing 94.6% is expected to
  be recovered by structure preservation alone.

**GATE.** Concept capture ratio re-measured after FIX-1, then after
FIX-4, so the two effects are attributed separately.

**Owner decision required:** yes.

---

## FIX-5 · Make artifact confidence carry information — **P3**

**Defect.** All 12 procedures score exactly `1.00` (8–172 steps); all
121 concepts exactly `0.90`. `min(1.0, 0.6 + 0.05*len(steps))`
saturates at 8 steps. Confidence is a constant.

**Contract.** Either make confidence reflect something (coherence,
provenance density, source contiguity) or **remove it** so nothing
downstream mistakes a constant for a signal. Length must not imply
reliability.

**GATE.** `test_artifact_confidence_carries_no_information_today`
inverts once confidence varies.

---

## FIX-6 · Prune Neo4j on corpus deletion — **P4**

**Defect.** 12,428 Fact nodes vs 3,184 PG facts; stale Entity/Fact
nodes survive corpus deletion (fact projection MERGEs endpoints).

**Contract.** Deletion must prune derived graph state. PG stays
authority; a full wipe-and-rebuild must reproduce current semantics.

**Containment today.** Graph expansion is evidence- AND
corpus-authorized: 30 facts over 3 live queries, **0 unauthorized**.
This is hygiene, not correctness — **unless** FIX-2 is skipped, in
which case stale pronoun edges persist.

**GATE.** `test_graph_authorization_blocks_stale_nodes` (escalates to
P0 automatically if the boundary ever breaks).

---

## FIX-7 · Restart the fleet after worker-code changes — **P4 / operational**

**Defect.** Editing worker code silently stops ingestion: the
execution-bundle fence quarantines workers
(`BUNDLE_STALE_CODE_DRIFT`), zero tickets are minted, and the pipeline
looks idle rather than blocked. Hit twice during this audit.

**Contract.** Surface bundle-stale quarantine in the health surface as
`BLOCKED`, so a stalled pipeline names its own cause.

---

## Priority order

| order | fix | why first |
|---|---|---|
| 1 | **FIX-2** pronoun facts | P1, no re-ingest, removes 17.5% junk, self-contained |
| 2 | **FIX-1** chunk structure | P1, largest quality gain, but needs re-ingest — do it once, with FIX-3/4 ready |
| 3 | **FIX-3** procedure scope | rides the same re-ingest |
| 4 | **FIX-4** concept cap | measure AFTER FIX-1; may be largely solved by it |
| 5 | FIX-5 / FIX-6 / FIX-7 | cheap, independent |

**FIX-1, FIX-3 and FIX-4 should ship in ONE re-ingest**, not three.

## Open state after pass 3

```
HYPOTHESES AUDITED: 45/50   UNAUDITED: H36   PARTIAL: H45 + 4
P0 open: 0
P1 open: 2   (structure-loss knowledge suppression; pronoun facts)
P2 open: 4   (procedure ceiling, concept cap, MAX_ENTITIES=10,
              entity identity fragmentation)
P3 open: 2   (confidence constant, source_sentence[:300])
P4 open: 2   (stale Neo4j nodes, bundle-fence invisibility)
SUITE: 1,086 passed / 83 failed — byte-identical to baseline
```
