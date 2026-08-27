"""KNOWLEDGE ARTIFACT LAYER — grounded representations beyond facts.

DECISION (owner, POLYMATH_KNOWLEDGE_ARTIFACT_PHASE): the extraction
engine gains artifact types alongside CanonicalFact:

    EvidenceSpan -> KnowledgeArtifact(FACT | PROCEDURE | CONCEPT)

Non-negotiables honored here: every artifact carries full source
lineage (document_id, source_chunk_ids, evidence_span_ids),
content-addressed artifact_id, created_by, provenance dict. Artifacts
NEVER create facts and NEVER bypass admission — they are additional
grounded representations compiled from accepted evidence.

No I/O, no models: pure compilation from provided inputs.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field


def _artifact_id(kind: str, document_id: str, body: Any) -> str:
    h = hashlib.sha256(json.dumps(
        {"kind": kind, "doc": document_id, "body": body},
        sort_keys=True, default=str).encode()).hexdigest()
    return f"{kind[:4].lower()}_{h[:32]}"


class KnowledgeArtifact(BaseModel):
    """Base lineage contract for every grounded knowledge artifact."""
    artifact_id: str
    artifact_type: str          # FACT | PROCEDURE | CONCEPT
    document_id: str
    corpus_id: str = ""
    source_chunk_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    created_by: str = "knowledge-artifact-compiler"
    provenance: dict = Field(default_factory=dict)


def finalize(artifact: "KnowledgeArtifact",
             body: dict) -> "KnowledgeArtifact":
    """Stamp content-addressed id once body fields are set."""
    object.__setattr__(artifact, "artifact_id",
                       _artifact_id(artifact.artifact_type,
                                    artifact.document_id,
                                    body))
    return artifact
