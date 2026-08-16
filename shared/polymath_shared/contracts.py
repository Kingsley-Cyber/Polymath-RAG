"""Cross-process Pydantic contracts. See ADR-0001 §15-16 and ADR-0005.

Pydantic's role is structural validation at stage boundaries — malformed
spans, missing versions, or illegal type references fail loudly and early.
It is never a semantic component: predicate selection happens only in the
deterministic compiler (shared/polymath_shared/rulepack/compiler.py).
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Extraction contracts (docx §16)
# ---------------------------------------------------------------------------


class CoreType(str, Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    LOCATION = "Location"
    PRODUCT = "Product"
    TECHNOLOGY = "Technology"
    CONCEPT = "Concept"
    METHOD = "Method"
    EVENT = "Event"
    DOCUMENT = "Document"
    PROCESS = "Process"
    MEASUREMENT = "Measurement"
    TIME_REFERENCE = "TimeReference"


DecisionKind = Literal["ACCEPT", "QUALIFY", "REJECT", "AMBIGUOUS", "UNSUPPORTED", "CONFLICT"]


class EntitySpan(BaseModel):
    """GLiNER pass-1 output."""
    doc_id: str
    chunk_id: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str
    core_type: CoreType
    domain_types: list[str] = Field(default_factory=list)
    score: float = Field(ge=0, le=1)
    extractor_version: str


class EvidenceSpan(BaseModel):
    """GLiNER pass-2 output — a coarse evidence class, never a predicate."""
    chunk_id: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str
    evidence_class: str
    trigger_lemma: Optional[str] = None
    score: float = Field(ge=0, le=1)
    extractor_version: str


class SemanticRole(str, Enum):
    ARG0 = "ARG0"
    ARG1 = "ARG1"
    ARG2 = "ARG2"
    ARGM_LOC = "ARGM-LOC"
    ARGM_TMP = "ARGM-TMP"


class RoleAssignment(BaseModel):
    role: SemanticRole
    entity_ref: str
    syntactic_path: str  # e.g. "nsubj:pass", "obl:agent"
    weak: bool = False   # roleset unknown -> syntax-only orientation


class ScopeFlags(BaseModel):
    """§13 modality/negation gate output."""
    negated: bool = False
    speculative: bool = False
    conditional: bool = False
    hypothetical: bool = False
    question: bool = False
    attributed: bool = False
    attribution_source: Optional[str] = None
    comparison: bool = False


class EntityCandidate(BaseModel):
    span: EntitySpan
    resolved_entity_id: str  # after canonicalization (identity.py)


class RelationCandidate(BaseModel):
    """Compiler input — the normalized tuple. The compiler maps this onto a
    CanonicalFact. Never construct facts anywhere else."""
    evidence: EvidenceSpan
    subject: EntityCandidate
    object: EntityCandidate
    roles: list[RoleAssignment] = Field(default_factory=list)
    roleset: Optional[str] = None
    verbnet_classes: list[str] = Field(default_factory=list)
    framenet_frames: list[str] = Field(default_factory=list)
    semlink_resolved: bool = False
    scope: ScopeFlags = Field(default_factory=ScopeFlags)
    ontology_profile: str
    sentence_text: str = ""
    sentence_start: int = 0


class CanonicalFact(BaseModel):
    """Compiler output on ACCEPT/QUALIFY."""
    fact_id: str
    predicate: str
    direction: Literal["forward"] = "forward"
    subject_id: str
    object_id: str
    qualifiers: dict = Field(default_factory=dict)
    decision: DecisionKind
    rule_id: str
    rule_version: str
    provenance: dict = Field(default_factory=dict)


class EvidenceRecord(BaseModel):
    evidence_id: str
    fact_id: str
    doc_id: str
    chunk_id: str
    span_offsets: dict
    extractor_version: str
    ontology_version: str
    rule_version: str
    rule_id: str
    gliner_scores: dict[str, float] = Field(default_factory=dict)


class OntologyProfile(BaseModel):
    profile_id: str
    core_labels: list[CoreType]
    active_modules: list[str] = Field(default_factory=list)
    module_versions: dict[str, str] = Field(default_factory=dict)


class ExtractionManifest(BaseModel):
    """Per-run, immutable. Every stage that touched the run records its
    version here; replay diffs against this manifest."""
    run_id: str
    gliner_model: str
    gliner_revision: str
    parser: str
    parser_version: str
    ontology_version: str
    rule_pack_version: str
    resource_versions: dict[str, str] = Field(default_factory=dict)
    thresholds: dict[str, float] = Field(default_factory=dict)


class CompilerDecision(BaseModel):
    """Full compiler result including non-fact outcomes (docx §11.1)."""
    decision: DecisionKind
    fact: Optional[CanonicalFact] = None
    evidence: Optional[EvidenceRecord] = None
    rule_id: Optional[str] = None
    reason: Optional[str] = None
    alternatives: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Ingestion contracts
# ---------------------------------------------------------------------------


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    parent_id: Optional[str] = None
    chunk_index: int
    tier: Literal["parent", "child"]
    text: str
    summary: str = ""
    char_start: int
    char_end: int


class DocumentProfile(BaseModel):
    profile_id: str
    active_modules: list[str] = Field(default_factory=list)
    label_set: list[str] = Field(default_factory=list)
    core_labels: list[CoreType] = Field(default_factory=list)


class RetrievalProfile(BaseModel):
    """The document's semantic address for cross-domain routing.

    Built bottom-up: child chunks -> parent summaries -> this profile.
    It answers "why should this whole source be considered for a query",
    never "what does one chunk say". Distinct from DocumentProfile (the
    deterministic label-routing artifact); neither is a substitute for
    the other."""
    document_id: str
    semantic_summary: str
    primary_domains: list[str] = Field(default_factory=list)
    secondary_domains: list[str] = Field(default_factory=list)
    core_concepts: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    problems_addressed: list[str] = Field(default_factory=list)
    use_for_questions_about: list[str] = Field(default_factory=list)
    connects_to_domains: list[str] = Field(default_factory=list)
    parent_ids: list[str] = Field(default_factory=list)
    source_parent_count: int = 0
    summarized_parent_count: int = 0
    coverage: float = 1.0
    summary_contract: str = "document-summary-v1"


class IntakeRequest(BaseModel):
    corpus_id: str
    source_name: str
    media_type: str
    content_b64: str  # normalized at intake; identity is doc_<sha256>
    config: dict = Field(default_factory=dict)


class RunRecord(BaseModel):
    run_id: str
    corpus_id: str
    status: Literal["intake", "reconciling", "query_ready", "degraded", "failed"]
    created_at: str
    updated_at: str


class StageAttempt(BaseModel):
    run_id: str
    stage: str
    contract_hash: str
    started_at: str
    completed_at: Optional[str] = None
    outcome: Literal["ok", "failed", "skipped"]
    error: Optional[str] = None
