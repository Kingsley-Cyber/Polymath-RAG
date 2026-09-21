"""Planning research contracts (ADR-063, HR1). Exactly the eight owned boundary contracts: registry snapshot, registry
projection request/result, evidence-gap compile request, research directive, hypothesis judgement request/result, and
product-territory projection. Strict, versioned, registered in ``schemas/registry.yaml``, generated into
``schemas/generated/v2``. Nested value models live in the planning domain and are embedded in the generated schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator
from typing_extensions import Self

from trail_signal.contexts.planning.domain.gap_compiler import (
    EvidenceGap, FreshnessRequirement, HypothesisView, PhysicalJob, PriorCoordinates, ResearchBudget, SearchIntent,
)
from trail_signal.contexts.planning.domain.judgement import AdmittedEvidenceView, HypothesisVerdict, JudgementStage
from trail_signal.contexts.planning.domain.registry_compiler import (
    RegistrySnapshotRef, ResearchStage, ScoringPolicy, SnapshotPrior, SnapshotSearchIntent, SnapshotSourceRole,
)
from trail_signal.kernel.contracts import BoundaryModel, Identifier, NonEmptyText, Sha256

LongText = Annotated[str, Field(min_length=1, max_length=4096)]
PositiveInt = Annotated[int, Field(strict=True, ge=1)]


def _sorted_unique(values: tuple[str, ...], name: str) -> None:
    if len(values) != len(set(values)) or list(values) != sorted(values):
        raise ValueError(f"{name} must be unique and sorted")


class TrailRegistrySnapshotV1(BoundaryModel):
    schema_version: Literal["1.0"]
    snapshot_id: Identifier
    compiler_version: Identifier
    content_hash: Sha256
    compiled_at: datetime
    activity_taxonomy: tuple[SnapshotPrior, ...]
    niche_seeds: tuple[SnapshotPrior, ...]
    friction_primitives: tuple[SnapshotPrior, ...]
    product_territories: tuple[SnapshotPrior, ...]
    search_intents: tuple[SnapshotSearchIntent, ...]
    source_roles: tuple[SnapshotSourceRole, ...]
    prior_candidates: tuple[SnapshotPrior, ...]
    seasonal_priors: tuple[SnapshotPrior, ...]
    scoring_policy: ScoringPolicy


class RegistryProjectionRequestV1(BoundaryModel):
    """Registry coordinates for live hypotheses; with physical_jobs it also drives the product-territory mapping."""
    stage: ResearchStage | None
    hypotheses: tuple[HypothesisView, ...]
    admitted_evidence_ids: tuple[Identifier, ...]
    max_priors_per_hypothesis: PositiveInt
    physical_jobs: tuple[PhysicalJob, ...]
    geography: NonEmptyText | None
    language: Identifier | None


class RegistryProjectionV1(BoundaryModel):
    registry_snapshot: RegistrySnapshotRef
    priors: tuple[PriorCoordinates, ...]
    redundancy_groups: tuple[tuple[Identifier, ...], ...]
    unsupported_hypothesis_ids: tuple[Identifier, ...]


class EvidenceGapCompileRequestV1(BoundaryModel):
    stage: ResearchStage
    hypotheses: tuple[HypothesisView, ...]
    admitted_evidence_ids: tuple[Identifier, ...]
    knowledge_gaps: tuple[EvidenceGap, ...]
    open_gaps: tuple[EvidenceGap, ...]
    geography: NonEmptyText | None
    language: Identifier | None


class ResearchDirectiveV1(BoundaryModel):
    directive_id: Identifier
    stage: ResearchStage
    objective: LongText
    hypothesis_ids: tuple[Identifier, ...]
    evidence_gaps: tuple[EvidenceGap, ...]
    search_intents: tuple[SearchIntent, ...]
    preferred_source_roles: tuple[Identifier, ...]
    disallowed_source_roles: tuple[Identifier, ...]
    freshness_requirement: FreshnessRequirement
    geography: NonEmptyText | None
    language: Identifier | None
    minimum_independent_sources: PositiveInt
    success_condition: LongText
    falsification_condition: LongText
    budget: ResearchBudget
    routed_source_ids: tuple[Identifier, ...]
    registry_snapshot: RegistrySnapshotRef

    @model_validator(mode="after")
    def _closed(self) -> Self:
        _sorted_unique(self.routed_source_ids, "routed_source_ids")
        _sorted_unique(self.preferred_source_roles, "preferred_source_roles")
        _sorted_unique(self.disallowed_source_roles, "disallowed_source_roles")
        if not self.search_intents:
            raise ValueError("a directive names at least one search intent")
        if set(self.preferred_source_roles) & set(self.disallowed_source_roles):
            raise ValueError("a source role cannot be both preferred and disallowed")
        return self


class HypothesisJudgementRequestV1(BoundaryModel):
    """Judgement inputs; admitted_evidence carries the admitted view for every id in admitted_evidence_ids."""
    stage: JudgementStage
    hypotheses: tuple[HypothesisView, ...]
    admitted_evidence_ids: tuple[Identifier, ...]
    admitted_evidence: tuple[AdmittedEvidenceView, ...]
    redundancy_groups: tuple[tuple[Identifier, ...], ...]
    latest_admission_id: Identifier | None

    @model_validator(mode="after")
    def _views_match_ids(self) -> Self:
        if {view.admitted_evidence_id for view in self.admitted_evidence} != set(self.admitted_evidence_ids):
            raise ValueError("admitted_evidence must carry exactly the admitted_evidence_ids")
        return self


class HypothesisJudgementV1(BoundaryModel):
    registry_snapshot: RegistrySnapshotRef
    stage: JudgementStage
    verdicts: tuple[HypothesisVerdict, ...]
    open_gaps: tuple[EvidenceGap, ...]


class ProductTerritoryProjectionV1(BoundaryModel):
    registry_snapshot: RegistrySnapshotRef
    territories: tuple[PriorCoordinates, ...]
    research_directive: ResearchDirectiveV1
