"""Grounded evidence assembly for R3a.

This module is intentionally downstream of retrieval and upstream of answer
writing.  It does not score, rerank, summarize, or generate prose.  It only
turns already-retrieved passages and graph facts into a deterministic bundle
whose support can be resolved back to authoritative source text and compiler
provenance.

Postgres remains the authority for facts/evidence/source spans.  Neo4j and
Qdrant may nominate candidates, but they are never accepted as provenance on
their own.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EvidenceAssemblyError(RuntimeError):
    """Raised when a retrieved candidate cannot be grounded safely."""


class SourceSpan(BaseModel):
    document_id: str
    source_name: str
    chunk_id: str
    char_start: int
    char_end: int
    text: str
    evidence_offsets: dict[str, Any] = Field(default_factory=dict)


class RetrievalPath(BaseModel):
    lane: str
    representation_kind: str = ""
    contract_id: str = ""
    rank: int = -1
    raw_score: float | None = None
    parent_id: str = ""


class EvidenceBundleItem(BaseModel):
    support_id: str
    support_kind: Literal["passage", "fact"]
    knowledge_id: str
    fact_id: str | None = None
    evidence_id: str | None = None
    claim_candidate: dict[str, Any] | None = None
    source_span: SourceSpan
    provenance: dict[str, Any] = Field(default_factory=dict)
    epistemics: dict[str, Any] = Field(default_factory=dict)
    applicability: dict[str, Any] = Field(default_factory=dict)
    retrieval: list[RetrievalPath] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    query: str
    evidence_bundle: list[EvidenceBundleItem] = Field(default_factory=list)


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvidenceAssemblyError(f"missing required {label}")
    return value


def _require_int(value: Any, label: str) -> int:
    if not isinstance(value, int):
        raise EvidenceAssemblyError(f"missing required {label}")
    return value


def _paths(raw: Any) -> list[RetrievalPath]:
    paths: list[RetrievalPath] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        paths.append(RetrievalPath(
            lane=str(item.get("lane") or ""),
            representation_kind=str(item.get("representation_kind") or ""),
            contract_id=str(item.get("contract_id") or ""),
            rank=int(item.get("rank", -1)),
            raw_score=(
                float(item["raw_score"])
                if item.get("raw_score") is not None
                else None
            ),
            parent_id=str(item.get("parent_id") or ""),
        ))
    return sorted(
        paths,
        key=lambda p: (
            p.rank if p.rank >= 0 else 1_000_000,
            p.lane,
            p.contract_id,
            p.parent_id,
        ),
    )


def _passage_item(row: dict[str, Any]) -> EvidenceBundleItem:
    chunk_id = _require_text(row.get("chunk_id"), "passage.chunk_id")
    doc_id = _require_text(row.get("doc_id"), "passage.doc_id")
    source_name = _require_text(row.get("source_name"), "passage.source_name")
    text = _require_text(row.get("text"), "passage.text")
    char_start = _require_int(row.get("char_start"), "passage.char_start")
    char_end = _require_int(row.get("char_end"), "passage.char_end")
    if char_end < char_start:
        raise EvidenceAssemblyError(f"invalid passage span for {chunk_id}")

    paths = _paths(row.get("retrieval_paths"))
    if not paths:
        raise EvidenceAssemblyError(f"missing retrieval provenance for passage {chunk_id}")

    return EvidenceBundleItem(
        support_id=f"passage:{chunk_id}",
        support_kind="passage",
        knowledge_id=chunk_id,
        claim_candidate={"kind": "source_passage", "text": text},
        source_span=SourceSpan(
            document_id=doc_id,
            source_name=source_name,
            chunk_id=chunk_id,
            char_start=char_start,
            char_end=char_end,
            text=text,
        ),
        provenance={
            "chunk_id": chunk_id,
            "contract_ids": sorted(set(row.get("contract_ids") or [])),
            "source_kind": "retrieved_source_text",
        },
        retrieval=paths,
    )


def _fact_item(row: dict[str, Any], graph_rank: int) -> EvidenceBundleItem:
    fact_id = _require_text(row.get("fact_id"), "fact.fact_id")
    evidence_id = _require_text(row.get("evidence_id"), "fact.evidence_id")
    doc_id = _require_text(row.get("doc_id"), "fact.doc_id")
    chunk_id = _require_text(row.get("chunk_id"), "fact.chunk_id")
    source_name = _require_text(row.get("source_name"), "fact.source_name")
    text = _require_text(row.get("text"), "fact.source_text")
    char_start = _require_int(row.get("char_start"), "fact.char_start")
    char_end = _require_int(row.get("char_end"), "fact.char_end")
    if char_end < char_start:
        raise EvidenceAssemblyError(f"invalid fact source span for {fact_id}")

    predicate = _require_text(row.get("predicate"), "fact.predicate")
    subject_id = _require_text(row.get("subject_id"), "fact.subject_id")
    object_id = _require_text(row.get("object_id"), "fact.object_id")
    subject = _require_text(row.get("subject"), "fact.subject")
    obj = _require_text(row.get("object"), "fact.object")

    provenance = row.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        raise EvidenceAssemblyError(f"missing compiler provenance for fact {fact_id}")

    span_offsets = row.get("span_offsets") or {}
    if not isinstance(span_offsets, dict):
        raise EvidenceAssemblyError(f"invalid evidence offsets for fact {fact_id}")

    qualifiers = row.get("qualifiers") or {}
    if not isinstance(qualifiers, dict):
        raise EvidenceAssemblyError(f"invalid qualifiers for fact {fact_id}")

    rule_id = _require_text(row.get("rule_id"), "fact.rule_id")
    rule_version = _require_text(row.get("rule_version"), "fact.rule_version")

    combined_provenance = dict(provenance)
    combined_provenance.update({
        "fact_rule_id": rule_id,
        "fact_rule_version": rule_version,
        "evidence_rule_id": str(row.get("evidence_rule_id") or ""),
        "evidence_extractor_version": str(row.get("extractor_version") or ""),
        "evidence_id": evidence_id,
    })

    return EvidenceBundleItem(
        support_id=f"fact:{fact_id}:{evidence_id}",
        support_kind="fact",
        knowledge_id=fact_id,
        fact_id=fact_id,
        evidence_id=evidence_id,
        claim_candidate={
            "kind": "relation",
            "subject_id": subject_id,
            "subject": subject,
            "predicate": predicate,
            "object_id": object_id,
            "object": obj,
        },
        source_span=SourceSpan(
            document_id=doc_id,
            source_name=source_name,
            chunk_id=chunk_id,
            char_start=char_start,
            char_end=char_end,
            text=text,
            evidence_offsets=span_offsets,
        ),
        provenance=combined_provenance,
        epistemics={"decision": str(row.get("decision") or "")},
        applicability={"qualifiers": qualifiers},
        retrieval=[RetrievalPath(
            lane="graph_expansion",
            representation_kind="canonical_fact",
            contract_id="neo4j-projection",
            rank=graph_rank,
        )],
    )


def assemble_evidence_bundle(
    query: str,
    *,
    passages: list[dict[str, Any]],
    graph_facts: list[dict[str, Any]],
    fact_support_rows: list[dict[str, Any]],
) -> EvidenceBundle:
    """Build a deterministic, fail-closed evidence bundle.

    `graph_facts` nominates fact ids and defines their graph-expansion rank.
    `fact_support_rows` MUST come from the authoritative Postgres join over
    facts + evidence + chunks + documents + subject/object entities.

    Duplicate retrieval nominations are collapsed by stable support id.
    Semantically conflicting facts are intentionally *not* collapsed.
    """
    clean_query = query.strip()
    if not clean_query:
        raise EvidenceAssemblyError("query is required")

    fact_ranks: dict[str, int] = {}
    for rank, fact in enumerate(graph_facts):
        fact_id = fact.get("fact_id") if isinstance(fact, dict) else None
        if fact_id and fact_id not in fact_ranks:
            fact_ranks[str(fact_id)] = rank

    rows_by_fact: dict[str, list[dict[str, Any]]] = {}
    for row in fact_support_rows:
        fact_id = row.get("fact_id")
        if fact_id:
            rows_by_fact.setdefault(str(fact_id), []).append(row)

    # Every graph-nominated fact must resolve back to authoritative support.
    for fact_id in sorted(fact_ranks):
        if not rows_by_fact.get(fact_id):
            raise EvidenceAssemblyError(
                f"graph fact {fact_id} has no authoritative Postgres evidence"
            )

    items: dict[str, EvidenceBundleItem] = {}

    for passage in passages:
        item = _passage_item(passage)
        items.setdefault(item.support_id, item)

    for fact_id, graph_rank in sorted(
        fact_ranks.items(), key=lambda kv: (kv[1], kv[0])
    ):
        for row in sorted(
            rows_by_fact[fact_id],
            key=lambda r: (str(r.get("evidence_id") or ""), str(r.get("chunk_id") or "")),
        ):
            item = _fact_item(row, graph_rank)
            items.setdefault(item.support_id, item)

    def order(item: EvidenceBundleItem) -> tuple:
        best_rank = min(
            (p.rank for p in item.retrieval if p.rank >= 0),
            default=1_000_000,
        )
        kind_order = 0 if item.support_kind == "fact" else 1
        return (best_rank, kind_order, item.support_id)

    return EvidenceBundle(
        query=clean_query,
        evidence_bundle=sorted(items.values(), key=order),
    )
