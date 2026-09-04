---
change_id: FIELD-EVIDENCE-CORPUS-V1 + TYPED-CLAIMS-V1
owner: governance
date: 2026-09-03
status: BUILT; field corpus ingested; typed claims live after canary + blue/green (receipts below)
architecture_impact: a research skill's curated observations become a Polymath corpus with provenance frontmatter; the extractor labels lived claims (friction / behavior / workaround / purchase_language) in facts.qualifiers and EXPLORE returns them; /capabilities detects both from the stores. Semantic bundle re-frozen (llm_direct.py, gate.py changed).
last_reviewed: 2026-09-03
---

# WORK LOG — steps 3 and 4 of the Polymath-native plan

Owner (2026-09-03): "go build 3 and 4" — after steps 1 (utilization
receipt) and 2 (corpus plan + capabilities) shipped with an Arm 1 receipt of
identical row sets (159/159, parity true).

## Contract

### FIELD-EVIDENCE-CORPUS-V1
- `scripts/ingest_field_evidence.py --state run.json | --csv research_evidence.csv [--corpus field-evidence-v1]`
  builds ONE markdown document per community thread and POSTs it to `/intake`.
  Frontmatter: `title, platform, thread_key, community, source_family:
  community, source_url, exported_at, run_ids, field_evidence: v1`. Body: one
  paragraph per curated observation opening with a machine line
  `FIELD_OBS author=u/<a> roles=A|B purchase=yes|no freshness=<class> gap=<gap_id> obs=<obs_id> [contradicts=yes]`
  followed by the verbatim quote, `problem:`, `workaround:`, `gap question:`.
  Idempotent (content-addressed doc ids; /intake replays return the run).
- `/capabilities.contracts.field-evidence-corpus` = the newest query_ready
  corpus whose id starts with `field-evidence` (detected from `runs`, never hardcoded).
- Evidence rows now always carry `document: {source_name, frontmatter}` so a
  consumer can rebuild the thread identity (platform, thread_key) per row.
- Consumer (TRAIL OS v1.4.1 `python/field_evidence.py`): rows tagged
  `field_evidence` become observation candidates for the current open gaps —
  same gap id on a repeat signal, keyword overlap otherwise — with the
  ORIGINAL author/thread identity, freshness recomputed from `exported_at`
  (LIVE→FAST after 90 days, FAST→SLOW after 730) and `corpus_row_id`.

### TYPED-CLAIMS-V1
- `RelationProposal.claim_kind: friction | behavior | workaround | purchase_language | null`
  (optional; JSON schema updated; prompt rule 9; LEAN form optional 5th element).
- Gate passes `claim_kind` through; `llm_direct.materialize` writes it into
  `facts.qualifiers` (jsonb, no migration). Fact ids ignore it, so a typed
  re-extraction ENRICHES an existing fact: `ON CONFLICT (fact_id) DO UPDATE
  SET qualifiers = facts.qualifiers || EXCLUDED.qualifiers` only when the new
  row carries a kind and the old one does not.
- `evidence_rows`: graph_fact rows carry `claim_kind` (top level and in `fact`).
- `/capabilities.contracts.typed-rows` = the distinct kinds present in `facts`.
- Retrieval ranking untouched; typed rows are a read-time filter for consumers.

## Changes
- `scripts/ingest_field_evidence.py` (NEW), `orchestrator/orchestrator/api/capabilities.py` (live detection),
  `orchestrator/orchestrator/api/evidence_rows.py` (document meta on every row, `_fact_claim_kinds`),
  `shared/polymath_shared/llm_extraction/{contract,client,gate}.py`, `workers/workers/llm_direct.py`,
  `tests/determinism/test_typed_claims.py` (NEW), semantic bundle lock re-frozen `v5-production-004-typed-claims`.

## Proof
- Unit: test_typed_claims (contract, schema+prompts, lean expand, evidence rows) + pronoun gate + materialization contract green.
- Field corpus ingest: 283 observations → 43 thread documents → 43 intake runs (receipt appended below).
- Canary 1 (`canary-llm-direct-0903`, technical chapter) after the first restart: converged, 0 typed facts. Traced
  to TWO causes, both fixed the same hour: (1) `gate._clean_relation` rebuilds relations from a fixed key tuple, so
  `claim_kind` was dropped before `ExtractionPacket.model_validate` — fixed, unit-tested, bundle re-frozen
  `v5-production-005-typed-claims-sanitizer`; (2) the prompt/schema change was not part of the extraction contract,
  so `--blue-green` CARRIED the extract stage (`carried_stages` incl. extract, `regenerated_stages: []`; 6 "extract ok"
  attempts in 0 s = receipt replays) — fixed by appending `|typed_claims=v1` to `_extraction_gate_contract()`.
- In-process probe on a FIELD_OBS paragraph (cloud lane, gemini-3.5-flash-lite, 1.4 s): raw response contains
  `claim_kind`; sanitized packet keeps it (`Epilator ALTERNATIVE_TO shaving · claim_kind=workaround`).
- Field corpus ingest: 283 observations → 43 thread documents → 43 runs; the first 13 typed facts appeared on
  field documents extracted after the prompt went live (`/capabilities.typed-rows` = behavior, friction,
  purchase_language, workaround).
- Typed re-extraction receipts (mark-builds-brands-v1, ecom-meta-v1, field-evidence-v1 under `typed_claims=v1`)
  and the Arm 2 / Arm 3 measurements: appended below by the session once converged.

## Rejected claims
- "Derive claim kinds at read time with a lexicon" — rejected: that is the
  rule-pack the LLM-DIRECT canon deleted (ADR-0017); the extractor labels, the
  reader reads.
- "Add a claim_kind column" — rejected: `qualifiers` is already the fact's
  jsonb side-channel; a column would need a migration for one enum.
- "Make the field corpus rows count as evidence directly" — rejected: rows are
  retrieval; a gap closes on observations with identity, so the consumer
  re-materializes them as observations with the original author/thread.

## Open contract gaps
- Field documents are re-extracted like any corpus; their FIELD_OBS lines
  yield typed claims only after the typed prompt is live (blue/green).
- Freshness after export is an approximation (age since export), not the
  thread's true date; the ledger does not carry post dates yet.
