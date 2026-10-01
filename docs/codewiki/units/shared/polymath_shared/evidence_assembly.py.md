# unit: shared/polymath_shared/evidence_assembly.py
anchor: shared/polymath_shared/evidence_assembly.py:1-494

## purpose
R3a deterministic EvidenceBundle assembly for the answer path: takes graph facts (Neo4j expansion lane) plus text evidence (document summaries, section summaries, dense/lexical child chunks) and emits items with explicit typed support lanes `graph`/`text`. — shared/polymath_shared/evidence_assembly.py:1-27 [DERIVED]
Pure module, no stores; row resolvers are injected Callables. Boundary: assembles evidence only, does not decide prose (R3b owns that). — shared/polymath_shared/evidence_assembly.py:1, :22-23, :118-132 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| assemble_evidence_bundle | function | (query: str, graph_facts: list[dict], child_evidence: list[dict], *, resolve_fact, resolve_evidence, resolve_entity, resolve_document, resolve_chunk, evidence_order=None, document_summaries=None, section_summaries=None, unresolved=None) -> dict | :118-132 | — |
| stale_projection_degradation | function | (unresolved: list[dict]) -> list[dict] | :104-115 | — |
| AssemblyError | class | Exception base | :52-53 | — |
| UnresolvedFactError | class | (fact_id: str) | :56-59 | — |
| UnresolvedEvidenceError | class | (fact_id: str) | :62-65 | — |
| UnresolvedEntityError | class | (entity_id: str, fact_id: str) | :68-72 | — |
| UnresolvedDocumentError | class | (doc_id: str, context: str) | :75-78 | — |
| UnresolvedChunkError | class | (chunk_id: str, context: str) | :81-84 | — |
| MissingProvenanceError | class | (fact_id: str, missing: str) | :87-91 | — |

Module imported by: orchestrator/orchestrator/api/evidence.py, orchestrator/orchestrator/api/ui.py (FACTS.importers) — shared/polymath_shared/evidence_assembly.py:1-494 [DERIVED]

Constants (table anchors are line ranges in this file):

| name | value | anchor |
|---|---|---|
| ASSEMBLY_VERSION | "2.0.0" | :35 |
| CONTRACT_ID | "answer/evidence_bundle/v2" | :36 |
| LEXICAL_CONTRACT_ID | "lexical-v1" | :37 |
| GRAPH_LANE / TEXT_LANE | "graph" / "text" | :39-40 |
| TEXT_KIND_DOCUMENT_SUMMARY / SECTION_SUMMARY / CHILD_CHUNK | "document_summary" / "section_summary" / "child_chunk" | :42-44 |
| DENSE_LANE / LEXICAL_LANE | "dense" / "lexical" | :46-47 |
| DOCUMENT_SUMMARY_LANE / SECTION_SUMMARY_LANE | "document_summary" / "section_summary" | :48-49 |

## contracts

**assemble_evidence_bundle** — shared/polymath_shared/evidence_assembly.py:118-400
- in: graph_facts rows `{fact_id, predicate, subject, object}` (Postgres entity resolution authoritative, surfaces fallback only) — :136-138 [DERIVED]
- in: child_evidence rows `{chunk_id, doc_id, parent_id, text, contract_ids}` — :139-140 [DERIVED]
- in: document_summaries `[{doc_id, summary}]`; section_summaries `[{chunk_id, doc_id, summary}]` — :141-144 [DERIVED]
- pre: resolvers return None for a missing row; the assembler then raises the matching typed error — :154-155 [DERIVED]
- post: every graph item requires a resolvable fact row, >=1 evidence row, resolvable entities/document/chunk, non-empty provenance (invariant D3; lanes independent, graph never gates text) — :15-20, :169-208 [DERIVED]
- post: returns `{"query", "evidence_bundle", "meta"}`; meta keys: contract_id, assembly_version, ordering (`"identity"` or `"rerank"`), claim_count, evidence_count, graph_claim_count, text_evidence_count — :388-400 [DERIVED]
- evidence_order: optional chunk-id list; reorders text items only, candidate SET unchanged; claims stay identity-ordered first — :146-152, :374-386 [DERIVED]
- tolerance: when `unresolved` is a list, TEXT items whose doc/chunk no longer resolves are skipped and recorded there; graph facts with zero evidence rows are dropped (reason `"no_supporting_evidence"`); default `None` keeps the strict raise contract — :157-164, :176-183, :242-246, :286-290, :334-347 [DERIVED]

**stale_projection_degradation** — shared/polymath_shared/evidence_assembly.py:104-115
- in: skip entries as produced by `_skip` (keys kind/doc_id/chunk_id/fact_id/reason) — :181, :244, :288, :336, :342 [DERIVED]
- out: `[]` for empty input; else exactly one dict `{component: "projection", effect: "<N> stale routing hit(s) from <M> deleted/moved document(s) skipped; answer built from live evidence only", reason: "stale_projection: run scripts/purge_orphan_projections.py --apply", doc_ids: docs[:20]}` — :106-115 [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS tables_read/tables_written empty; module docstring "no stores") — shared/polymath_shared/evidence_assembly.py:1 [DERIVED]
- Qdrant collections, files, network calls, subprocesses, env flags: none present in SOURCE. [DERIVED by absence]
- Logging only: logger `"polymath.evidence_assembly"`; `_skip` warns `"stale projection hit skipped: %s"` with `extra={"error_code": "stale_projection"}` — shared/polymath_shared/evidence_assembly.py:94, :97-101 [DERIVED]

## invariants
INVARIANT: provenance of every emitted graph claim != empty — else raise MissingProvenanceError("facts.provenance is empty") — shared/polymath_shared/evidence_assembly.py:184-186 [DERIVED]
  fails-if: a claim with no provenance enters the bundle.
INVARIANT: fact.rule_id truthy — else raise MissingProvenanceError("facts.rule_id missing") — shared/polymath_shared/evidence_assembly.py:187-188 [DERIVED]
  fails-if: unattributed extraction rule reaches the answer path.
INVARIANT: claim_count + evidence_count == len(evidence_bundle) (every item kind is "claim" :211 or "evidence" :250/:294/:354) — shared/polymath_shared/evidence_assembly.py:395-396 [DERIVED]
  fails-if: meta counts disagree with shipped items.
INVARIANT: unresolved=None ⇒ every unresolved row raises; unresolved=list ⇒ TEXT rows and evidence-less graph facts skip, but graph chunk/doc/entity failures still raise — shared/polymath_shared/evidence_assembly.py:180-183, :199-208, :242-246 [DERIVED]
  fails-if: strict callers silently get degraded bundles, or tolerant callers crash on projection defects.
INVARIANT: distinct chunk_id count in child-chunk items == distinct chunk_id count in child_evidence input (seen_chunks dedup) — shared/polymath_shared/evidence_assembly.py:324-332 [DERIVED]
  fails-if: duplicate evidence items inflate the bundle.
INVARIANT: all graph items sort before all text items (sort key 0/1 on kind) — shared/polymath_shared/evidence_assembly.py:379-386 [DERIVED]
INVARIANT: stale_projection_degradation([]) == [] — shared/polymath_shared/evidence_assembly.py:106-107 [DERIVED]
INVARIANT: source_span char_start/char_end emitted only when `isinstance(x, int)`, else None — shared/polymath_shared/evidence_assembly.py:434-435 [DERIVED]
  fails-if: non-int offsets leak into locators like `chunk:X@None:None`.

## determinism & idempotency
determinism: DETERMINISTIC — "Pure and deterministic given the resolvers"; no clock/random/uuid/db/env/network reads in SOURCE; only imports are logging/typing — shared/polymath_shared/evidence_assembly.py:29-33, :133-134 [DERIVED]
idempotency: SAFE — no store writes; caveat: appends to the caller-owned `unresolved` list via `_skip`, so re-running with the same list accumulates entries — shared/polymath_shared/evidence_assembly.py:97-99 [DERIVED]

## failure behaviour
- All failures are typed AssemblyError subclasses; base docstring: "Never caught silently upstream" — shared/polymath_shared/evidence_assembly.py:52-53 [DERIVED]
- Raises (strict mode, unresolved=None): UnresolvedFactError :172-173; UnresolvedEvidenceError :183; MissingProvenanceError :186 and :188; UnresolvedEntityError :192-194; UnresolvedChunkError :202, :338; UnresolvedDocumentError :205-208, :246, :290, :344-347 [DERIVED]
- Swallowed-by-design (unresolved=list): stale doc/chunk hits recorded via `_skip` + warning (error_code "stale_projection"); caller sees fewer items plus a degradation entry from stale_projection_degradation — shared/polymath_shared/evidence_assembly.py:97-115 [DERIVED]
- GRAPH-FAIL-OPEN-V1 (§19): graph fact with no supporting evidence chunk is DROPPED, not errored, in tolerant mode; strict still raises — shared/polymath_shared/evidence_assembly.py:176-183 [DERIVED]
- `_presentation` never raises; a missing join renders "" (legacy rows have NULL heading_path; UI falls back) — shared/polymath_shared/evidence_assembly.py:405-408 [DERIVED]
- Motivating measurement baked into the docstring: 23% of the production routing collection pointed at moved-out documents (STALE-PROJECTION-TOLERANCE-V1, 2026-08-30) — shared/polymath_shared/evidence_assembly.py:157-162 [DERIVED]

## dumb-code flags
- Dead assignment: `graph = next(f for f in graph_facts if f.get("fact_id") == fact_id)` is never read afterwards — shared/polymath_shared/evidence_assembly.py:170 [DERIVED]
- Doc/code drift: module docstring says items are "ordered by (kind, knowledge_id, evidence_id)" but no sort key contains evidence_id — shared/polymath_shared/evidence_assembly.py:25-26 vs :379-386 [DERIVED]
- Duplicated literal: `_presentation` compares `text_kind == "document_summary"` instead of the constant TEXT_KIND_DOCUMENT_SUMMARY — shared/polymath_shared/evidence_assembly.py:418 vs :42 [DERIVED]
- Magic number: fallback rank `10**9` for ids absent from evidence_order — shared/polymath_shared/evidence_assembly.py:381 [DERIVED]
- Magic cap: `docs[:20]` truncates the degradation doc_ids list — shared/polymath_shared/evidence_assembly.py:114 [DERIVED]
- Repeated expression: `row.get("doc_id") or chunk.get("doc_id") or ""` written 3× in the child-chunk block — shared/polymath_shared/evidence_assembly.py:339, :342, :345 [DERIVED]
- Literal `{"decision": "evidence"}` duplicated across all three text-item builders — shared/polymath_shared/evidence_assembly.py:268, :312, :364 [DERIVED]

## refactor notes
- Consumers orchestrator/orchestrator/api/evidence.py and orchestrator/orchestrator/api/ui.py depend on the bundle shape (keys "query"/"evidence_bundle"/"meta"), CONTRACT_ID "answer/evidence_bundle/v2", and the lane/kind/text_kind literals — shared/polymath_shared/evidence_assembly.py:36, :209-231, :248-275, :352-371, :388-400; FACTS.importers [DERIVED]
- Skip-entry key shapes are coupled to stale_projection_degradation, which reads only `doc_id` — graph_fact skips (fact_id, reason) contribute no doc_ids today — shared/polymath_shared/evidence_assembly.py:108, :181, :244, :288 [DERIVED]
- The reason string embeds the ops runbook path "scripts/purge_orphan_projections.py --apply"; renaming that script breaks the operator instruction — shared/polymath_shared/evidence_assembly.py:113 [DERIVED]
- Changing default `unresolved=None` to a list silently converts strict callers' raises into skips — shared/polymath_shared/evidence_assembly.py:131, :157-164 [DERIVED]
- Section-summary items validate only resolve_document, never resolve_chunk on chunk_id; adding a chunk check changes skip counts — shared/polymath_shared/evidence_assembly.py:279-290 [INFERRED: only resolve_document appears in that loop]

## VERIFY
```verify
grep -Fq 'answer/evidence_bundle/v2' shared/polymath_shared/evidence_assembly.py
grep -Fq 'no_supporting_evidence' shared/polymath_shared/evidence_assembly.py
grep -Fq 'purge_orphan_projections.py --apply' shared/polymath_shared/evidence_assembly.py
grep -Fq '10**9' shared/polymath_shared/evidence_assembly.py
grep -Fq 'GRAPH-FAIL-OPEN-V1' shared/polymath_shared/evidence_assembly.py
test "$(grep -c -F 'AssemblyError' shared/polymath_shared/evidence_assembly.py)" -ge 7
! grep -Fq 'import requests' shared/polymath_shared/evidence_assembly.py
```
