"""Evidence application ports (ADR-063, HR2): pure, synchronous, deterministic. Every argument and result is a registered
evidence contract. Implementations admit harness observations against the registry-derived policy the request carries and
qualify hypotheses over admitted evidence; they never fetch, schedule, persist, call a model, or score."""
from __future__ import annotations

from abc import abstractmethod
from typing import Protocol

from trail_signal.contexts.evidence.domain.admission import admission_id, admit_observations
from trail_signal.contexts.evidence.domain.qualification import qualify_hypothesis
from trail_signal.contexts.evidence.public.contracts import (
    AdmittedObservationV1, EvidenceAdmissionRequestV1, EvidenceAdmissionV1, QualificationRequestV1, QualificationV1,
)


class EvidenceAdmissionPort(Protocol):
    @abstractmethod
    def admit(self, request: EvidenceAdmissionRequestV1) -> EvidenceAdmissionV1:
        ...


class QualificationPort(Protocol):
    @abstractmethod
    def qualify(self, request: QualificationRequestV1) -> QualificationV1:
        ...


def admit_evidence(request: EvidenceAdmissionRequestV1) -> EvidenceAdmissionV1:
    admitted, rejected = admit_observations(stage=request.stage, action_id=request.action_id, run_id=request.run_id, operation_id=request.trail_operation_id,
                                            evaluated_at=request.evaluated_at, policy=request.policy, sources=request.receipt.sources,
                                            observations=request.receipt.observations, hypotheses=request.hypotheses)
    return EvidenceAdmissionV1(admission_id=admission_id(request.run_id, request.action_id), run_id=request.run_id, action_id=request.action_id,
                               registry_snapshot=request.policy.registry_snapshot, trail_operation_id=request.trail_operation_id,
                               admitted=tuple(AdmittedObservationV1.model_validate(a.model_dump()) for a in admitted), rejected=rejected,
                               evaluated_at=request.evaluated_at)


def qualify(request: QualificationRequestV1) -> QualificationV1:
    state, results, supporting, contradicting, gaps = qualify_hypothesis(stage=request.stage, hypothesis_id=request.hypothesis_id,
                                                                          admitted=request.admitted, gates=request.policy.hard_gates)
    return QualificationV1(record_id=request.record_id, stage=request.stage, state=state, hypothesis_ids=(request.hypothesis_id,), gate_results=results,
                           supporting_evidence_ids=tuple(e.admitted_evidence_id for e in supporting),
                           contradicting_evidence_ids=tuple(e.admitted_evidence_id for e in contradicting), open_gaps=gaps,
                           registry_snapshot=request.registry_snapshot)
