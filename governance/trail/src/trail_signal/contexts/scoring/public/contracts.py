"""Scoring contracts (ADR-063, HR2; LAW 1). Exactly the two owned boundary contracts: the opportunity score request and the
opportunity score. The score originates only here: it is the retained doc-08 engine over signals composed from ADMITTED evidence
after the qualification gates, and it never reads a model, harness, prior, or Polymath field."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from trail_signal.contexts.scoring.domain.engine import (
    AXES, COMPOSITION_VERSION, SCORING_VERSION, AxisScore, CoverageGap, EvidenceSignalInput, QualificationView, ScoreRefused, ScoreWeights, SnapshotRef, Unit,
    compose_signals, compute_score,
)
from trail_signal.kernel.contracts import BoundaryModel, Identifier, NonEmptyText


class OpportunityScoreRequestV1(BoundaryModel):
    record_id: Identifier
    hypothesis_id: Identifier
    registry_snapshot: SnapshotRef
    as_of: datetime
    admitted: tuple[EvidenceSignalInput, ...]
    qualifications: tuple[QualificationView, ...]


class OpportunityScoreV1(BoundaryModel):
    record_id: Identifier
    hypothesis_id: Identifier
    registry_snapshot: SnapshotRef
    score: Unit
    subscores: tuple[AxisScore, ...]
    confidence: Unit
    coverage_gaps: tuple[CoverageGap, ...]
    hostile_dependent: bool
    scored_from: tuple[Identifier, ...]
    admitted_evidence_ids: tuple[Identifier, ...]
    qualification_record_ids: tuple[Identifier, ...]
    scoring_version: NonEmptyText
    composition_version: NonEmptyText
    weights_version: NonEmptyText
    as_of: datetime
    authority_class: Literal["SCORE"]


class OpportunityScoreRefusalV1(BoundaryModel):
    """A per-hypothesis refusal record (LAW 1): scoring declined for this hypothesis because a hard gate was unmet or an input
    was outside the law. In a portfolio run one hypothesis refusing never blocks the others; each carries its own lineage."""
    record_id: Identifier
    hypothesis_id: Identifier
    registry_snapshot: SnapshotRef
    reason_code: NonEmptyText
    detail: NonEmptyText
    as_of: datetime
    authority_class: Literal["SCORE_REFUSAL"]


def refuse_score(*, record_id: str, hypothesis_id: str, registry_snapshot: SnapshotRef, as_of: datetime, error: ScoreRefused) -> OpportunityScoreRefusalV1:
    """Build the typed refusal record from a domain ScoreRefused. The message is 'REASON_CODE: detail'; the code is the authority."""
    message = str(error)
    reason_code = message.split(":", 1)[0].strip() or "SCORE_REFUSED"
    return OpportunityScoreRefusalV1(record_id=record_id, hypothesis_id=hypothesis_id, registry_snapshot=registry_snapshot,
                                     reason_code=reason_code, detail=message, as_of=as_of, authority_class="SCORE_REFUSAL")


def score_opportunity(request: OpportunityScoreRequestV1, weights: ScoreWeights) -> OpportunityScoreV1:
    """Refuses while any qualification gate is unmet or a qualification stage is missing; then the retained engine scores."""
    stages = {q.stage for q in request.qualifications}
    if stages != {"market_delta", "supply"}:
        raise ScoreRefused("HARD_GATE_UNMET: market_delta and supply qualifications are both required before scoring")
    unmet = [f"{q.stage}:{g.name}" for q in request.qualifications for g in q.gate_results if not g.passed]
    if unmet or any(q.state in ("REJECTED", "NO_DEFENSIBLE_BRIDGE") for q in request.qualifications):
        raise ScoreRefused("HARD_GATE_UNMET: " + (", ".join(unmet) or "a qualification is rejected or has no defensible bridge"))
    mine = tuple(e for e in request.admitted if request.hypothesis_id in e.hypothesis_ids)
    if not mine:
        raise ScoreRefused("NO_ADMITTED_EVIDENCE: a score exists only over admitted evidence linked to the hypothesis")
    outcome = compute_score(compose_signals(mine, weights, niche_id=request.hypothesis_id, as_of=request.as_of), weights, niche_id=request.hypothesis_id, as_of=request.as_of)
    return OpportunityScoreV1(record_id=request.record_id, hypothesis_id=request.hypothesis_id, registry_snapshot=request.registry_snapshot, score=outcome.score,
                              subscores=tuple(AxisScore(axis=a, value=outcome.subscores[a]) for a in AXES), confidence=outcome.confidence, coverage_gaps=outcome.coverage_gaps,
                              hostile_dependent=outcome.hostile_dependent, scored_from=outcome.scored_from, admitted_evidence_ids=tuple(e.admitted_evidence_id for e in mine),
                              qualification_record_ids=tuple(q.record_id for q in request.qualifications), scoring_version=SCORING_VERSION,
                              composition_version=COMPOSITION_VERSION, weights_version=weights.version, as_of=request.as_of, authority_class="SCORE")


__all__ = ["OpportunityScoreRefusalV1", "OpportunityScoreRequestV1", "OpportunityScoreV1", "ScoreRefused", "refuse_score", "score_opportunity"]
