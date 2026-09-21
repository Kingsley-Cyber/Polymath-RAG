"""Evidence contracts (ADR-063, HR2). Exactly the six owned boundary contracts: the harness research receipt, the evidence
admission request/result, the admitted observation, and the qualification request/result. Strict, versioned, registered in
``schemas/registry.yaml``, generated into ``schemas/generated/v2``. Nested value models live in the evidence domain."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import model_validator
from typing_extensions import Self

from trail_signal.contexts.evidence.domain.admission import (
    AdmissionPolicy, EvidenceRole, HypothesisRef, LongText, Polarity, ReceiptObservation, ReceiptSource, ReceiptToolTrace, RegistrySnapshotRef,
    RejectedObservation, ResearchStage,
)
from trail_signal.contexts.evidence.domain.qualification import GateResult, OpenGap, QualificationStage, QualificationState
from trail_signal.kernel.contracts import BoundaryModel, Identifier, NonEmptyText


class HarnessResearchReceiptV1(BoundaryModel):
    """Byte-compatible with Polymath's wire copy (contracts/adapter/v1/harness_receipt.schema.json)."""
    action_id: Identifier
    run_id: Identifier
    harness_id: Identifier
    started_at: datetime
    completed_at: datetime
    sources: tuple[ReceiptSource, ...]
    observations: tuple[ReceiptObservation, ...]
    tool_trace: tuple[ReceiptToolTrace, ...]
    limitations: tuple[LongText, ...]

    @model_validator(mode="after")
    def _bound(self) -> Self:
        listed = {s.source_id for s in self.sources}
        if any(o.source_id not in listed for o in self.observations):
            raise ValueError("every observation names a listed source")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at precedes started_at")
        return self


class EvidenceAdmissionRequestV1(BoundaryModel):
    stage: ResearchStage
    action_id: Identifier
    run_id: Identifier
    trail_operation_id: Identifier
    evaluated_at: datetime
    receipt: HarnessResearchReceiptV1
    hypotheses: tuple[HypothesisRef, ...]
    policy: AdmissionPolicy


class AdmittedObservationV1(BoundaryModel):
    admitted_evidence_id: Identifier
    observation_id: Identifier
    source_id: Identifier
    evidence_role: EvidenceRole
    source_class: Identifier
    source_suitability: Literal["suitable", "conditional"]
    freshness: Literal["fresh", "stale_within_policy"]
    provenance: Literal["recorded", "unverified"]
    independence_group: NonEmptyText
    duplicate_of: Identifier | None
    polarity: Polarity
    hypothesis_ids: tuple[Identifier, ...]
    stage_relevance: ResearchStage
    anchored_at: datetime
    limitations: tuple[LongText, ...]
    trail_admission_record_id: Identifier
    authority_class: Literal["ADMITTED_OBSERVATION"]

    @model_validator(mode="after")
    def _linked_and_supply_bound(self) -> Self:
        if not self.hypothesis_ids:
            raise ValueError("admitted evidence links to at least one hypothesis")
        if self.evidence_role == "supply" and self.stage_relevance != ResearchStage.SUPPLY:
            raise ValueError("supply evidence belongs to the supply stage only")
        return self


class EvidenceAdmissionV1(BoundaryModel):
    admission_id: Identifier
    run_id: Identifier
    action_id: Identifier
    registry_snapshot: RegistrySnapshotRef
    trail_operation_id: Identifier
    admitted: tuple[AdmittedObservationV1, ...]
    rejected: tuple[RejectedObservation, ...]
    evaluated_at: datetime


class QualificationRequestV1(BoundaryModel):
    stage: QualificationStage
    record_id: Identifier
    hypothesis_id: Identifier
    registry_snapshot: RegistrySnapshotRef
    admitted: tuple[AdmittedObservationV1, ...]
    policy: AdmissionPolicy

    @model_validator(mode="after")
    def _same_snapshot(self) -> Self:
        if self.policy.registry_snapshot != self.registry_snapshot:
            raise ValueError("qualification policy and request must cite the same registry snapshot")
        return self


class QualificationV1(BoundaryModel):
    record_id: Identifier
    stage: QualificationStage
    state: QualificationState
    hypothesis_ids: tuple[Identifier, ...]
    gate_results: tuple[GateResult, ...]
    supporting_evidence_ids: tuple[Identifier, ...]
    contradicting_evidence_ids: tuple[Identifier, ...]
    open_gaps: tuple[OpenGap, ...]
    registry_snapshot: RegistrySnapshotRef
    authority_class: str = "QUALIFIED_FINDING"


__all__ = ["AdmittedObservationV1", "EvidenceAdmissionRequestV1", "EvidenceAdmissionV1", "HarnessResearchReceiptV1", "Polarity",
           "QualificationRequestV1", "QualificationV1"]
