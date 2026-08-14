"""R3a: deterministic evidence-bundle assembly (no stores).

Takes retrieval artifacts — graph facts from the Neo4j expansion lane
and child evidence from the dense/lexical lanes — and assembles a
deterministic EvidenceBundle where every candidate claim is traceable
to fact/entity IDs, source document, exact evidence span, provenance,
epistemics, applicability, and retrieval lane.

Invariant: no answer claim exists downstream unless this assembler can
point to the evidence that supports it. A claim item therefore
REQUIRES a resolvable fact row, at least one evidence row, resolvable
entities/document/chunk, and non-empty provenance. Any violation is a
typed AssemblyError — loud, never a silent omission.

Boundary rule: this module assembles evidence. It does NOT decide what
the final prose answer should say (R3b owns that).

Determinism: bundle items are ordered by (kind, knowledge_id,
evidence_id); duplicates collapse by identity; conflicting claims
coexist as separate items. Identical inputs produce identical output.
"""
from __future__ import annotations

from typing import Callable, Optional

ASSEMBLY_VERSION = "1.0.0"
CONTRACT_ID = "answer/evidence_bundle/v1"
LEXICAL_CONTRACT_ID = "lexical-v1"

GRAPH_LANE = "graph"
DENSE_LANE = "dense"
LEXICAL_LANE = "lexical"


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
) -> dict:
    """Assemble the R3a bundle. Pure and deterministic given the resolvers.

    graph_facts rows:   {fact_id, predicate, subject, object} (Neo4j
                        expansion lane; surfaces are fallback only —
                        Postgres entity resolution is authoritative).
    child_evidence rows: {chunk_id, doc_id, parent_id, text,
                          contract_ids} (dense/lexical lanes).

    Resolvers return None for a missing row; the assembler raises the
    matching typed error instead of emitting an unsupported claim.
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
                "kind": "claim",
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

    # -- evidence-only items (retrieved chunks without a fact) --------------
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
            raise UnresolvedChunkError(chunk_id, "retrieved child evidence")
        doc = resolve_document(row.get("doc_id") or chunk.get("doc_id") or "")
        if doc is None:
            raise UnresolvedDocumentError(
                row.get("doc_id") or chunk.get("doc_id") or "",
                f"evidence chunk {chunk_id}",
            )
        lanes = sorted({
            (LEXICAL_LANE if cid == LEXICAL_CONTRACT_ID else DENSE_LANE)
            for cid in (row.get("contract_ids") or [])
        })
        items.append({
            "kind": "evidence",
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

    # -- deterministic ordering: claims first, then evidence ----------------
    items.sort(key=lambda i: (0 if i["kind"] == "claim" else 1, i["knowledge_id"] or ""))
    return {
        "query": query,
        "evidence_bundle": items,
        "meta": {
            "contract_id": CONTRACT_ID,
            "assembly_version": ASSEMBLY_VERSION,
            "claim_count": sum(1 for i in items if i["kind"] == "claim"),
            "evidence_count": sum(1 for i in items if i["kind"] == "evidence"),
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
