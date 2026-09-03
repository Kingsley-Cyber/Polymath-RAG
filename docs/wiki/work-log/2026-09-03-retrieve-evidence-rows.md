---
change_id: RETRIEVE-EVIDENCE-ROWS-V1
owner: governance
date: 2026-09-03
status: DONE (live-probed; tests green)
architecture_impact: /retrieve gains a contract-ready evidence view (`evidence: true`) and an ideation mode (`mode: EXPLORE`); documents carry parsed frontmatter (migration 0051); the MCP `retrieve` tool exposes both. Retrieval ranking is untouched.
last_reviewed: 2026-09-03
---

# WORK LOG — RETRIEVE-EVIDENCE-ROWS-V1: retrieval returns evidence, not ids

Owner (2026-09-03): "overall the rag needs to return evidence not ids & make it
transcript aware. i think a ideation mode is important to have for abstract
pull and breadth." Consumer = TRAIL OS `corpus_retrieve` (docs/18 contract
`{id, summary, source}` + docs/19 provenance), but the view is generic.

## Contract

1. `POST /retrieve` with `evidence: true` (or `explore: true`, or `mode:
   "EXPLORE"`) adds `evidence_rows` + `evidence_contract:
   "retrieve-evidence-rows-v1"`. Rows are re-resolvable by id, carry a
   human-auditable `source` (title · channel · upload date · timecode) and
   NEVER a filesystem path. Schema: `contracts/retrieve/v1/evidence_row.schema.json`.
2. Row kinds: `chunk` (text + `text_clean` with `[m:ss - m:ss]` timecodes
   stripped into `timecode`), `document` (only when a document summary
   exists; the summariser's `<file> — ` prefix is stripped), `graph_fact`
   (only with attesting evidence rows), `graph_hop` (EXPLORE only: facts
   sharing an entity with a retrieved fact, from documents not yet seen).
3. EXPLORE = breadth: `limit` floored at 24, per-document cap 2 (4 in the
   precision view), documents interleaved round-robin, graph hops on.
   Answer precision (`/chat`, HYBRID/FAST/DEEP) is unchanged.
4. Frontmatter (`title`, `channel`, `upload_date`, `video_id`, `url`, …) is
   parsed ONCE by `polymath_shared.frontmatter.parse_frontmatter` — intake
   stamps `documents.frontmatter` (migration 0051) for new documents;
   `scripts/backfill_frontmatter.py` stamps existing ones; the view falls
   back to the first child chunk when the column is null.
5. MCP `retrieve(query, corpus_id, mode, limit, latent, explore)` returns
   `{evidence_rows, evidence_contract, graph_facts}` when the view is on
   (text trimmed to 1200 chars per row for tool budgets).

## Changes

- `orchestrator/orchestrator/api/evidence_rows.py` (NEW): `strip_timecodes`,
  `display_title`, `_source_label`, `_fetch_docs` (frontmatter column →
  first-chunk fallback → document_summaries join), `_fact_provenance`,
  `_graph_hop`, `build_evidence_rows(conn, response, corpus_ids, limit, explore)`.
- `orchestrator/orchestrator/api/retrieve.py`: `RetrieveRequest.evidence`,
  `.explore`; `mode=EXPLORE` rewrite; rows attached after the response dict.
- `orchestrator/orchestrator/mcp_server.py`: `explore` flag + rows passthrough.
- `shared/polymath_shared/frontmatter.py` (NEW): the single parser.
- `workers/workers/intake_worker.py`: `documents.frontmatter` stamped at insert.
- `stores/postgres/migrations/0051_document_frontmatter.sql` (APPLIED live).
- `scripts/backfill_frontmatter.py` (NEW; dry-run default; ran `--execute`
  on mark-builds-brands-v1 (6 docs) and ecom-meta-v1 (10 docs)).
- `contracts/retrieve/v1/evidence_row.schema.json` (NEW).
- Tests: `tests/determinism/test_evidence_rows.py` (parser, timecodes,
  titles/source labels), `tests/integration/test_retrieve_evidence_rows.py`
  (live `/retrieve` evidence + EXPLORE against a query_ready corpus; skips
  when none). TREE rows + `scripts/README.md` row added.

## Proof

- `pytest tests/determinism/test_evidence_rows.py tests/integration/test_retrieve_evidence_rows.py` → 5 passed.
- Live probe (mark-builds-brands-v1, fleet restarted): precision view = 14
  rows (8 chunk + 6 document), sources such as
  `1 product. 3 AI tools… · Mark Builds Brands · 20250709 · 3:15–3:47`;
  EXPLORE across mark-builds-brands-v1 + ecom-meta-v1 = 38 rows over 11
  documents (17 chunk, 10 document, 11 graph_fact with provenance, 0 graph_hop).
- `scripts/repo_guard.py` → `repo guard: ok` (unpiped).
- Consumer proof lives in TRAIL OS (`python/corpus_polymath.py`
  `rows_from_evidence_rows`, harness section 13): rows map 1:1 onto the
  docs/18 contract with `can_establish` / `cannot_establish` and query provenance.

## Rejected claims

- "Return more chunks per doc for breadth" — rejected: breadth is documents,
  not chunks; EXPLORE caps per document at 2 and interleaves.
- "Emit graph facts without provenance" — rejected: a fact with no attesting
  chunk is a note, not evidence (TRAIL triage codes it CORPUS_ROW_NOT_EVIDENCE).
- "Parse frontmatter at read time only" — rejected as the steady state: the
  read-time fallback stays, but intake stamps the column so the view is O(1)
  per document and auditable.

## Open contract gaps

- `graph_hop` returned 0 rows on the probe corpora (entities rarely shared
  across the 16 documents); the lane is exercised only by the unit path.
- Document rows for transcripts depend on `document_summaries`; corpora
  ingested before the summary stage stamps rows show chunk rows only.
- The MCP tool trims row text to 1200 chars; a consumer needing full chunk
  text re-resolves by id via `/retrieve` (no `evidence/{id}` endpoint yet).
