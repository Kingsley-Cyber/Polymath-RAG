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
    RESEARCH_GROUP = "ResearchGroup"
    PAPER = "Paper"
    DATASET = "Dataset"
    CORPUS = "Corpus"
    BENCHMARK = "Benchmark"
    METRIC = "Metric"
    TASK = "Task"
    MODEL = "Model"
    ALGORITHM = "Algorithm"
    FRAMEWORK = "Framework"
    ARCHITECTURE = "Architecture"
    THEORY = "Theory"
    TECHNIQUE = "Technique"
    COMPONENT = "Component"
    SOFTWARE = "Software"
    LIBRARY = "Library"
    TOOL = "Tool"
    EXPERIMENT = "Experiment"
    RELEASE = "Release"
    TRAINING_RUN = "TrainingRun"
    DATE = "Date"
    TIME_PERIOD = "TimePeriod"
    VERSION = "Version"


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
    # Raw provider label preserved verbatim alongside the canonical
    # mapping (semantic-query-policy-v1): never discard the provider
    # result. pass_kind marks how the span was produced (discovery,
    # boundary_rescue, missing_argument_rescue, type_reconciliation).
    raw_label: Optional[str] = None
    pass_kind: str = "discovery"


class EvidenceSpan(BaseModel):
    """GLiNER pass-2 output — a coarse evidence class, never a predicate.

    I3R-R1 typed trigger contract: when localization (evidence_proposer.
    localize_trigger) authorizes a trigger, it records WHICH lexical arm
    of WHICH predicate produced it (trigger_lexical_class in
    {VERB, NOUN, MULTIWORD}, trigger_predicate_id, trigger_match_source
    in {"verbs","nouns","multiword"}). The compiler then tests ONLY that
    arm of that predicate. Spans without these fields (legacy frozen
    harnesses) fall back to the untyped all-arm behavior unchanged."""
    chunk_id: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str
    evidence_class: str
    trigger_lemma: Optional[str] = None
    trigger_lexical_class: Optional[str] = None
    trigger_predicate_id: Optional[str] = None
    trigger_match_source: Optional[str] = None
    score: float = Field(ge=0, le=1)
    extractor_version: str


class SemanticRole(str, Enum):
    ARG0 = "ARG0"
    ARG1 = "ARG1"
    ARG2 = "ARG2"
    ARGM_LOC = "ARGM-LOC"
    ARGM_TMP = "ARGM-TMP"


class BindingSource(str, Enum):
    UD_DIRECT = "UD_DIRECT"
    UD_PREPOSITIONAL = "UD_PREPOSITIONAL"
    UD_PASSIVE = "UD_PASSIVE"
    UD_COORDINATION = "UD_COORDINATION"
    SAFE_LOCAL_PATTERN = "SAFE_LOCAL_PATTERN"
    BOUNDED_LINEAR_RECALL = "BOUNDED_LINEAR_RECALL"
    UD_DEPENDENCY = "UD_DEPENDENCY"
    NOMINAL_DEPENDENCY = "NOMINAL_DEPENDENCY"
    CONTROL_SUBJECT = "CONTROL_SUBJECT"
    CONTROL_OBJECT = "CONTROL_OBJECT"
    DISCOURSE_ANAPHORA = "DISCOURSE_ANAPHORA"


V2_BINDING_SOURCES = frozenset(
    {BindingSource.UD_DEPENDENCY, BindingSource.NOMINAL_DEPENDENCY,
     BindingSource.CONTROL_SUBJECT, BindingSource.CONTROL_OBJECT,
     BindingSource.DISCOURSE_ANAPHORA}
)


def v2_binding_refusal(candidate) -> Optional[str]:
    """PREDICATE-COMPILER-V2 hard rule: a relation candidate exists only
    when a spaCy token licensed it and dependency structure bound its
    arguments. No token id -> NO_TRIGGER_TOKEN. Any binding source
    outside the V2 set (proximity recall, surface patterns) ->
    UNLICENSED_BINDING_SOURCE. Returns the refusal reason or None."""
    if getattr(candidate, "trigger_token_id", None) is None:
        return "NO_TRIGGER_TOKEN"
    source = getattr(candidate, "binding_source", None)
    if source not in V2_BINDING_SOURCES:
        return "UNLICENSED_BINDING_SOURCE"
    return None


class RoleAssignment(BaseModel):
    role: SemanticRole
    entity_ref: str
    syntactic_path: str  # e.g. "nsubj:pass", "obl:agent"
    weak: bool = False   # roleset unknown -> syntax-only orientation


class ArgumentEndpoint(BaseModel):
    entity_ref: str
    surface: str
    core_type: str
    syntactic_path: str
    binding_source: BindingSource
    role: Optional[SemanticRole] = None


class LexicalSemanticEvidence(BaseModel):
    """KIMI Phase 8: one normalized, versioned compiler input.

    This object collects every piece of lexical-semantic evidence that
    already exists in the pipeline and presents it to the compiler as a
    single deterministic structure. It does not invent new semantics; it
    exposes the evidence that the UD parse, PropBank, VerbNet, FrameNet,
    SemLink, and type precheck have already produced.
    """
    # evidence identity
    evidence_class: str
    evidence_surface: str
    evidence_start: int
    evidence_end: int

    # trigger identity
    trigger_surface: str
    trigger_lemma: Optional[str] = None
    trigger_pos: Optional[str] = None

    # syntax / voice
    voice: str = "active"
    dependency_head: Optional[dict] = None
    dependency_paths: list[dict] = Field(default_factory=list)

    # PropBank
    propbank_roleset: Optional[str] = None
    propbank_role_inventory: dict[str, str] = Field(default_factory=dict)
    assigned_roles: dict[str, str] = Field(default_factory=dict)

    # VerbNet / FrameNet / SemLink
    verbnet_classes: list[str] = Field(default_factory=list)
    verbnet_matches: list[tuple[str, str]] = Field(default_factory=list)
    framenet_frames: list[str] = Field(default_factory=list)
    framenet_matches: list[tuple[str, str]] = Field(default_factory=list)
    semlink_mapping: dict = Field(default_factory=dict)
    semlink_status: str = "SEMLINK_UNAVAILABLE"

    # argument binding
    argument_endpoints: list[ArgumentEndpoint] = Field(default_factory=list)
    binding_sources: list[BindingSource] = Field(default_factory=list)

    # endpoint types for precheck
    endpoint_types: dict[str, str] = Field(default_factory=dict)

    # contracts
    lexical_resource_contract: Optional[str] = None
    syntax_contract: Optional[str] = None
    evidence_pass_contract: Optional[str] = None


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
    # KIMI Phase 3: PropBank-assigned semantic roles {ARG0: span, ARG1: span}
    assigned_roles: dict | None = None
    # KIMI Phase 7: SemLink mapping identity used for cross-resource alignment
    semlink_mapping: dict | None = None
    # KIMI Phase 8: normalized lexical-semantic evidence object consumed by compiler
    lexical_semantic_evidence: LexicalSemanticEvidence | None = None
    ontology_profile: str
    sentence_text: str = ""
    sentence_start: int = 0
    sentence_index: int = 0
    # PREDICATE-COMPILER-V2 provenance (slice 1). Optional so the frozen
    # legacy_v1/kimi_v1 pipelines keep constructing candidates unchanged;
    # v2_binding_refusal makes these mandatory on the V2 path only.
    document_id: Optional[str] = None
    sentence_id: Optional[str] = None
    trigger_token_id: Optional[int] = None
    subject_token_id: Optional[int] = None
    object_token_id: Optional[int] = None
    dependency_path: Optional[str] = None
    binding_source: Optional[BindingSource] = None


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
    # semantic-query-policy-v1: identity of the provider-facing label
    # vocabulary that produced the proposals. Canonical ontology never
    # changes with it.
    query_policy: str = "semantic-query-policy-v1"


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
