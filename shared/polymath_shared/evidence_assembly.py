"""R3a: deterministic evidence-bundle assembly (no stores).

Takes retrieval artifacts — graph facts from the Neo4j expansion lane
and textual evidence (document summaries, section summaries, child
chunks from the dense/lexical lanes) — and assembles a deterministic
EvidenceBundle where every item carries an explicit typed support
lane:

  GRAPH (lane=graph): compiler facts / graph-expanded facts, fully
    traceable to fact/entity IDs, source document, exact evidence
    span, provenance, epistemics, applicability.
  TEXT  (lane=text):  document summary, section summary, child chunk,
    lexical/dense retrieval evidence — first-class support items.

Invariant (D3): the lanes are INDEPENDENT. Either may support an
answer on its own; graph evidence augments textual retrieval and
never gates it. A graph claim still REQUIRES a resolvable fact row,
at least one evidence row, resolvable entities/document/chunk, and
non-empty provenance — any violation is a typed AssemblyError
(loud, never a silent omission).

Boundary rule: this module assembles evidence. It does NOT decide what
the final prose answer should say (R3b owns that).

Determinism: bundle items are ordered by (kind, knowledge_id,
evidence_id); duplicates collapse by identity; conflicting claims
coexist as separate items. Identical inputs produce identical output.
"""
from __future__ import annotations

import logging

from typing import Callable, Optional

ASSEMBLY_VERSION = "2.0.0"
CONTRACT_ID = "answer/evidence_bundle/v2"
LEXICAL_CONTRACT_ID = "lexical-v1"

GRAPH_LANE = "graph"
TEXT_LANE = "text"

TEXT_KIND_DOCUMENT_SUMMARY = "document_summary"
TEXT_KIND_SECTION_SUMMARY = "section_summary"
TEXT_KIND_CHILD_CHUNK = "child_chunk"

DENSE_LANE = "dense"
LEXICAL_LANE = "lexical"
DOCUMENT_SUMMARY_LANE = "document_summary"
SECTION_SUMMARY_LANE = "section_summary"


class AssemblyError(Exception):
    """Base for loud assembly failures. Never caught silently upstream."""


class UnresolvedFactError(AssemblyError):
    def __init__(self, fact_id: str) -> None:
        super().__init__(f"unresolved fact_id: {fact_id}")
        self.fact_id = fact_id


class UnresolvedEvidenceError(AssemblyError):
    def __init__(self, fact_id: str) -> None:
        super().__init__(f"claim with no supporting evidence: {fact_id}")
        self.fact_id = fact_id


class UnresolvedEntityError(AssemblyError):
    def __init__(self, entity_id: str, fact_id: str) -> None:
        super().__init__(f"unresolved entity_id: {entity_id} (fact {fact_id})")
        self.entity_id = entity_id
        self.fact_id = fact_id


class UnresolvedDocumentError(AssemblyError):
    def __init__(self, doc_id: str, context: str) -> None:
        super().__init__(f"unresolved document: {doc_id} ({context})")
        self.doc_id = doc_id


class UnresolvedChunkError(AssemblyError):
    def __init__(self, chunk_id: str, context: str) -> None:
        super().__init__(f"unresolved chunk: {chunk_id} ({context})")
        self.chunk_id = chunk_id


class MissingProvenanceError(AssemblyError):
    def __init__(self, fact_id: str, missing: str) -> None:
        super().__init__(f"missing provenance for fact {fact_id}: {missing}")
        self.fact_id = fact_id
        self.missing = missing


log = logging.getLogger("polymath.evidence_assembly")


def _skip(sink: list[dict], entry: dict) -> None:
    """Record a stale routing hit (document/chunk gone) instead of failing."""
    sink.append(entry)
    log.warning("stale projection hit skipped: %s", entry,
                extra={"error_code": "stale_projection"})


def stale_projection_degradation(unresolved: list[dict]) -> list[dict]:
    """meta.degraded entry for skipped stale hits (empty when none)."""
    if not unresolved:
        return []
    docs = sorted({e.get("doc_id") for e in unresolved if e.get("doc_id")})
    return [{
        "component": "projection",
        "effect": f"{len(unresolved)} stale routing hit(s) from {len(docs)} "
                  "deleted/moved document(s) skipped; answer built from live evidence only",
        "reason": "stale_projection: run scripts/purge_orphan_projections.py --apply",
        "doc_ids": docs[:20],
    }]


def assemble_evidence_bundle(
    query: str,
    graph_facts: list[dict],
    child_evidence: list[dict],
    *,
    resolve_fact: Callable[[str], Optional[dict]],
    resolve_evidence: Callable[[str], list[dict]],
    resolve_entity: Callable[[str], Optional[dict]],
    resolve_document: Callable[[str], Optional[dict]],
    resolve_chunk: Callable[[str], Optional[dict]],
    evidence_order: Optional[list[str]] = None,
    document_summaries: Optional[list[dict]] = None,
    section_summaries: Optional[list[dict]] = None,
    unresolved: Optional[list[dict]] = None,
) -> dict:
    """Assemble the R3a bundle (v2 typed lanes). Pure and deterministic
    given the resolvers.

    graph_facts rows:   {fact_id, predicate, subject, object} (Neo4j
                        expansion lane; surfaces are fallback only —
                        Postgres entity resolution is authoritative).
    child_evidence rows: {chunk_id, doc_id, parent_id, text,
                          contract_ids} (dense/lexical lanes).
    document_summaries: [{doc_id, summary}] — TEXT lane,
                        document-summary granularity.
    section_summaries:  [{chunk_id, doc_id, summary}] — TEXT lane,
                        section (parent-chunk) summary granularity.

    `evidence_order` (G5/G3): optional list of chunk ids giving a
    fused-rerank ordering for text evidence items. Graph claims stay
    identity-ordered first; text items follow the hint order (ids
    absent from the hint fall back to identity order). The candidate
    SET is unchanged by any ordering hint — recall and grounding
    semantics never depend on order. meta.ordering records which
    policy applied.

    Resolvers return None for a missing row; the assembler raises the
    matching typed error instead of emitting an unsupported claim.

    STALE-PROJECTION-TOLERANCE-V1 (2026-08-30): when `unresolved` is a
    list, TEXT-lane items (document/section summaries, child chunks)
    whose document or chunk no longer resolves are SKIPPED and recorded
    there — a routing hit on a deleted document is a projection defect,
    not evidence, and must not fail the whole answer (MEASURED: 23% of
    the production routing collection pointed at moved-out documents).
    Graph-lane facts still raise: a fact citing a missing document is an
    integrity breach. Default None keeps the strict contract.
    """
    items: list[dict] = []

    # -- claim items (graph lane facts) -------------------------------------
    for fact_id in sorted({f.get("fact_id") for f in graph_facts if f.get("fact_id")}):
        graph = next(f for f in graph_facts if f.get("fact_id") == fact_id)
        fact = resolve_fact(fact_id)
        if fact is None:
            raise UnresolvedFactError(fact_id)
        evidence_rows = sorted(resolve_evidence(fact_id), key=lambda r: r.get("evidence_id") or "")
        if not evidence_rows:
            raise UnresolvedEvidenceError(fact_id)
        provenance = fact.get("provenance") or {}
        if not provenance:
            raise MissingProvenanceError(fact_id, "facts.provenance is empty")
        if not fact.get("rule_id"):
            raise MissingProvenanceError(fact_id, "facts.rule_id missing")
        subject = resolve_entity(fact["subject_id"])
        object_ = resolve_entity(fact["object_id"])
        if subject is None:
            raise UnresolvedEntityError(fact["subject_id"], fact_id)
        if object_ is None:
            raise UnresolvedEntityError(fact["object_id"], fact_id)
        qualifiers = fact.get("qualifiers") or {}
        epistemics = _epistemics(fact, qualifiers, provenance)
        conditions = _conditions(qualifiers, provenance)

        for ev in evidence_rows:
            chunk = resolve_chunk(ev["chunk_id"])
            if chunk is None:
                raise UnresolvedChunkError(ev["chunk_id"], f"evidence {ev.get('evidence_id')}")
            doc = resolve_document(chunk.get("doc_id") or ev.get("doc_id") or "")
            if doc is None:
                raise UnresolvedDocumentError(
                    chunk.get("doc_id") or ev.get("doc_id") or "",
                    f"fact {fact_id}",
                )
            items.append({
                "lane": GRAPH_LANE,
                "kind": "claim",
                "text_kind": None,
                "claim_candidate": f"{subject['normalized_surface']} {fact['predicate']} {object_['normalized_surface']}",
                "knowledge_id": fact_id,
                "fact_id": fact_id,
                "entity_ids": {
                    "subject_id": fact["subject_id"],
                    "object_id": fact["object_id"],
                },
                "predicate": fact["predicate"],
                "source_document_id": doc["doc_id"],
                "source_span": _source_span(chunk, ev),
                "provenance": _provenance(fact, ev, provenance),
                "epistemics": epistemics,
                "applicability": {
                    "corpus_id": doc.get("corpus_id"),
                    "source_name": doc.get("source_name"),
                    "conditions": conditions,
                },
                "retrieval": {"lanes": [GRAPH_LANE], "score": None},
            })

    # -- text evidence items (TEXT lane, independent support) -------------
    # document summaries
    for row in sorted(
        (d for d in (document_summaries or []) if d.get("doc_id") and (d.get("summary") or "")),
        key=lambda d: d.get("doc_id") or "",
    ):
        doc_id = row["doc_id"]
        doc = resolve_document(doc_id)
        if doc is None:
            if unresolved is not None:
                _skip(unresolved, {"kind": "document_summary", "doc_id": doc_id})
                continue
            raise UnresolvedDocumentError(doc_id, "document summary")
        summary = row["summary"] or ""
        items.append({
            "lane": TEXT_LANE,
            "kind": "evidence",
            "text_kind": TEXT_KIND_DOCUMENT_SUMMARY,
            "claim_candidate": None,
            "knowledge_id": doc_id,
            "fact_id": None,
            "entity_ids": None,
            "predicate": None,
            "source_document_id": doc_id,
            "source_span": {
                "text": summary,
                "locator": f"doc:{doc_id}",
                "chunk_id": None,
                "char_start": None,
                "char_end": None,
                "offsets_source": "summary",
                "span_offsets": {},
            },
            "provenance": {},
            "epistemics": {"decision": "evidence"},
            "applicability": {
                "corpus_id": doc.get("corpus_id"),
                "source_name": doc.get("source_name"),
                "conditions": [],
            },
            "retrieval": {"lanes": [DOCUMENT_SUMMARY_LANE], "score": None},
        })

    # section summaries
    for row in sorted(
        (s for s in (section_summaries or []) if s.get("chunk_id") and (s.get("summary") or "")),
        key=lambda s: s.get("chunk_id") or "",
    ):
        chunk_id = row["chunk_id"]
        doc_id = row.get("doc_id") or ""
        doc = resolve_document(doc_id)
        if doc is None:
            if unresolved is not None:
                _skip(unresolved, {"kind": "section_summary", "doc_id": doc_id, "chunk_id": chunk_id})
                continue
            raise UnresolvedDocumentError(doc_id, f"section summary {chunk_id}")
        summary = row["summary"] or ""
        items.append({
            "lane": TEXT_LANE,
            "kind": "evidence",
            "text_kind": TEXT_KIND_SECTION_SUMMARY,
            "claim_candidate": None,
            "knowledge_id": chunk_id,
            "fact_id": None,
            "entity_ids": None,
            "predicate": None,
            "source_document_id": doc_id,
            "source_span": {
                "text": summary,
                "locator": f"section:{chunk_id}",
                "chunk_id": chunk_id,
                "char_start": None,
                "char_end": None,
                "offsets_source": "summary",
                "span_offsets": {},
            },
            "provenance": {},
            "epistemics": {"decision": "evidence"},
            "applicability": {
                "corpus_id": doc.get("corpus_id"),
                "source_name": doc.get("source_name"),
                "conditions": [],
            },
            "retrieval": {"lanes": [SECTION_SUMMARY_LANE], "score": None},
        })

    # -- child-chunk text evidence ----------------------------------------
    seen_chunks: set[str] = set()
    for row in sorted(
        (c for c in child_evidence if c.get("chunk_id")),
        key=lambda c: c.get("chunk_id") or "",
    ):
        chunk_id = row["chunk_id"]
        if chunk_id in seen_chunks:
            continue
        seen_chunks.add(chunk_id)
        chunk = resolve_chunk(chunk_id)
        if chunk is None:
            if unresolved is not None:
                _skip(unresolved, {"kind": "child_chunk", "chunk_id": chunk_id, "doc_id": row.get("doc_id") or ""})
                continue
            raise UnresolvedChunkError(chunk_id, "retrieved child evidence")
        doc = resolve_document(row.get("doc_id") or chunk.get("doc_id") or "")
        if doc is None:
            if unresolved is not None:
                _skip(unresolved, {"kind": "child_chunk", "chunk_id": chunk_id, "doc_id": row.get("doc_id") or chunk.get("doc_id") or ""})
                continue
            raise UnresolvedDocumentError(
                row.get("doc_id") or chunk.get("doc_id") or "",
                f"evidence chunk {chunk_id}",
            )
        lanes = sorted({
            (LEXICAL_LANE if cid == LEXICAL_CONTRACT_ID else DENSE_LANE)
            for cid in (row.get("contract_ids") or [])
        })
        items.append({
            "lane": TEXT_LANE,
            "kind": "evidence",
            "text_kind": TEXT_KIND_CHILD_CHUNK,
            "claim_candidate": None,
            "knowledge_id": chunk_id,
            "fact_id": None,
            "entity_ids": None,
            "predicate": None,
            "source_document_id": doc["doc_id"],
            "source_span": _source_span(chunk, {"span_offsets": {}}),
            "provenance": {},
            "epistemics": {"decision": "evidence"},
            "applicability": {
                "corpus_id": doc.get("corpus_id"),
                "source_name": doc.get("source_name"),
                "conditions": [],
            },
            "retrieval": {"lanes": lanes, "score": None},
        })

    # -- deterministic ordering: graph claims first, then text evidence ---
    # G5/G3: text items may follow a fused-rerank hint; the SET never
    # changes. Claims stay identity-ordered (fact grounding is order-free).
    if evidence_order:
        rank = {cid: i for i, cid in enumerate(evidence_order)}
        items.sort(key=lambda i: (
            0 if i["kind"] == "claim" else 1,
            0 if i["kind"] == "claim" else rank.get(i["knowledge_id"], 10**9),
            i["knowledge_id"] or "",
        ))
        ordering = "rerank"
    else:
        items.sort(key=lambda i: (0 if i["kind"] == "claim" else 1, i["knowledge_id"] or ""))
        ordering = "identity"
    return {
        "query": query,
        "evidence_bundle": items,
        "meta": {
            "contract_id": CONTRACT_ID,
            "assembly_version": ASSEMBLY_VERSION,
            "ordering": ordering,
            "claim_count": sum(1 for i in items if i["kind"] == "claim"),
            "evidence_count": sum(1 for i in items if i["kind"] == "evidence"),
            "graph_claim_count": sum(1 for i in items if i.get("lane") == GRAPH_LANE),
            "text_evidence_count": sum(1 for i in items if i.get("lane") == TEXT_LANE),
        },
    }


def _source_span(chunk: dict, ev: dict) -> dict:
    char_start = chunk.get("char_start")
    char_end = chunk.get("char_end")
    chunk_id = chunk.get("chunk_id") or ""
    return {
        "text": chunk.get("text") or "",
        "locator": f"chunk:{chunk_id}@{char_start}:{char_end}",
        "chunk_id": chunk_id,
        "char_start": char_start if isinstance(char_start, int) else None,
        "char_end": char_end if isinstance(char_end, int) else None,
        "offsets_source": "chunk",
        "span_offsets": ev.get("span_offsets") or {},
    }


def _epistemics(fact: dict, qualifiers: dict, provenance: dict) -> dict:
    scope = provenance.get("scope") or {}
    return {
        "decision": fact.get("decision"),
        "certainty": qualifiers.get("certainty"),
        "negated": scope.get("negated"),
        "attributed": qualifiers.get("attributed"),
        "attribution_source": qualifiers.get("attribution_source"),
        "comparison": qualifiers.get("comparison"),
        "valid_from": qualifiers.get("valid_from"),
        "valid_until": qualifiers.get("valid_until"),
    }


def _conditions(qualifiers: dict, provenance: dict) -> list[str]:
    scope = provenance.get("scope") or {}
    conds: list[str] = []
    if scope.get("conditional"):
        conds.append("conditional")
    if scope.get("question"):
        conds.append("question")
    certainty = qualifiers.get("certainty")
    if certainty in ("speculative", "hypothetical"):
        conds.append(certainty)
    if qualifiers.get("attributed"):
        source = qualifiers.get("attribution_source")
        conds.append(f"attributed:{source}" if source else "attributed")
    if qualifiers.get("comparison"):
        conds.append("comparison")
    if qualifiers.get("valid_from"):
        conds.append(f"valid_from:{qualifiers['valid_from']}")
    if qualifiers.get("valid_until"):
        conds.append(f"valid_until:{qualifiers['valid_until']}")
    return sorted(conds)


def _provenance(fact: dict, ev: dict, provenance: dict) -> dict:
    return {
        "rule_id": fact.get("rule_id"),
        "rule_version": fact.get("rule_version"),
        "extractor_version": ev.get("extractor_version"),
        "evidence_id": ev.get("evidence_id"),
        "roleset": provenance.get("roleset"),
        "trigger_lemma": provenance.get("trigger_lemma"),
        "trigger_surface": provenance.get("trigger_surface"),
        "verbnet_classes": provenance.get("verbnet_classes"),
        "framenet_frames": provenance.get("framenet_frames"),
        "semlink_resolved": provenance.get("semlink_resolved"),
        "resource_contract_id": provenance.get("resource_contract_id"),
        "compiled_lexical_sha256": provenance.get("compiled_lexical_sha256"),
        "orientation": provenance.get("orientation"),
        "weak": provenance.get("weak"),
    }
