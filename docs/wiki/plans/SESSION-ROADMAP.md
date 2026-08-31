---
change_id: SESSION-ROADMAP
owner: governance
date: 2026-08-31
status: living
architecture_impact: none (ordering authority for the post-latent backlog)
last_reviewed: 2026-08-31
---

# SESSION ROADMAP — post-latent execution order (owner-approved 2026-08-31)

Grouping law: batch by FAILURE DOMAIN, not by size. Control-plane
correctness before query-path polish before qualification.

## SESSION A — control/enrichment reliability (NOW)

1. **1C successor carry-gap** (task chip task_d2e2c5ba): make artifact/
   attempt lookups follow supersedes_run_id lineage (or copy carried
   attempt rows at mint). ACCEPTANCE IS END-TO-END, not a unit test:
   construct run A → project artifacts → change contract → successor B
   minted → B reconciles inherited artifacts → corpus reaches
   query_ready with NO manual re-pin. (The manual surgery of
   2026-08-31 — parked successors, re-pinned originals, restored
   tickets — is exactly what this test must make impossible.)
2. **`desired_projection_ids()` — ONE want-set authority.** The F6
   children-only rule lived in THREE hand-synced copies (verify /
   census / tickets) and wedged promotion; latent kinds and entity
   cards have their own desired-sets in the verifier — same drift
   class. One deterministic helper, all consumers call it, one test.
3. **Failover on parse/gate rejection** (before any large-scale
   enrichment): today a lane fails over only on transport errors; a
   200 carrying garbage stops dead. New semantics: parse+gate REJECT →
   ONE retry on the other group lane → parse+gate → typed failure.
   Eligibility by REAL gate class:
   - failover-eligible (model-specific): ENRICH_UNPARSEABLE,
     ENRICH_UNKNOWN_REF, ENRICH_GISTS_BELOW_FLOOR, ENRICH_EMPTY
   - NOT eligible (source conditions another model cannot repair):
     ENRICH_INPUT_OVER_CEILING
   One cross-lane retry only — never a model-repair loop. Expected to
   clear the one stuck Learning SQL section.

## SESSION B — query-path batch (after A is green)

4. HYBRID /retrieve response gains the presentation fields (FAST and
   the chat bundle already have them).
5. `retrieval.latent` answer-frame DIAGNOSTICS — not a boolean:
   {enabled, parents_nominated, parents_survived, children_admitted,
   kinds:{abstraction,transfer}}. This is the INSTRUMENT Session C's
   headline metric needs (survival attribution does not exist today);
   UI renders a small chip from it.
6. Latent query-bar toggle (flag is plumbed end-to-end already).
7. Single query embedding: thread pass1's qvec to the latent rescue
   (removes the second ~0.2 s embed). Query-path seam, so it rides
   THIS batch, not A.

## SESSION C — P6 qualification (after B)

- ≥20 owner-authored cases; HYBRID latent:false vs latent:true.
- Metrics: recall/relevant-evidence gain, unique useful evidence gain,
  false-analogy rate, evidence displacement, latency delta,
  no-result/failure rate, abstraction-vs-transfer attribution, and the
  HEADLINE: **parent nominated → ≥1 original child survives rerank**
  (nominated 100 / survived ~8 = noise; nominated 100 / survived ~55
  with high unique-useful and low false-analogy = real transfer).
- Output: LATENT-TRANSFER-P6-RESULTS.md → owner GO/NO-GO.

## AFTER GO

- Enable latent by default in HYBRID (latent_retrieval_enabled=true).
- Split the pseudo-query vector into latent_query ONLY if attribution
  says questions earn their own lane.
- VECTOR stays the FROZEN non-latent baseline regardless of GO.
- **REJECTED (owner 2026-08-31: "leave the summaries")**: the
  enhanced-summary idea (preferring an LLM-enriched summary over the
  deterministic parent card as the active summary vector). The
  deterministic summaries STAY the one authority — this also would
  have re-opened the F5 two-authorities class and diluted VECTOR's
  control-group purity. Do not resurrect without a new owner directive.

## THEN

- Phase 0: canonical tier_chunker swap + re-ingest (also populates
  heading_path → real section titles in the UI trees).

## Standing watch items (not sessions)

- First corpus-scale ingest on the 5-Groq fleet: AIMD lanes + the
  EXTRACTION_LANE_FAILOVER / ENRICHMENT_LANE_FAILOVER counters.
- Pre-existing 8 test failures (llm_controller, sval x3 need the
  retired spaCy sidecar — candidates for skip-when-absent; 4 others
  predate this work).
- Materializer gaps with NO plan yet: scanned-PDF OCR; DOCX tables are
  silently dropped (w:tbl skipped).
