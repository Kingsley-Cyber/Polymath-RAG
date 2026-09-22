"""Stage qualification (ADR-063, HR2): the hard gates of config/evidence_gates.json computed over ADMITTED evidence only.
One independence group counts once, duplicates never count, contradictions are preserved and weighed, and a prior never
satisfies a gate. Qualification emits a typed disposition and the open gaps that would close it; it never scores."""
from __future__ import annotations

from enum import StrEnum

from trail_signal.kernel.contracts import BoundaryModel, Identifier

from trail_signal.contexts.evidence.domain.admission import AdmittedObservation, HardGatePolicy, LongText, NonNegInt, Polarity, PosInt, RegistrySnapshotRef


class QualificationStage(StrEnum):
    MARKET_DELTA = "market_delta"
    SUPPLY = "supply"


class QualificationState(StrEnum):
    PROMOTED = "PROMOTED"
    PROVISIONAL = "PROVISIONAL"
    REJECTED = "REJECTED"
    UNPROVEN = "UNPROVEN"
    NO_DEFENSIBLE_BRIDGE = "NO_DEFENSIBLE_BRIDGE"


class GateResult(BoundaryModel):
    gate_id: Identifier
    name: Identifier
    minimum: PosInt
    observed: NonNegInt
    passed: bool


class OpenGap(BoundaryModel):
    gap_id: Identifier
    hypothesis_id: Identifier
    question: LongText
    evidence_role: Identifier


# Which config/evidence_gates.json gates each stage must satisfy, and which evidence roles feed each gate.
STAGE_GATES: dict[QualificationStage, tuple[str, ...]] = {
    QualificationStage.MARKET_DELTA: ("competitor_review_analysis", "current_price_checks"),
    QualificationStage.SUPPLY: ("current_price_checks", "risk_review"),
}
GATE_ROLES: dict[str, tuple[str, ...]] = {
    "independent_complaints": ("friction", "behavior"), "workaround_examples": ("workaround",), "competitor_review_analysis": ("competition",),
    "current_price_checks": ("price", "supply"), "risk_review": ("risk",), "falsification_test": ("contradiction",),
}


def independent_groups(evidence: tuple[AdmittedObservation, ...], roles: tuple[str, ...]) -> int:
    return len({e.independence_group for e in evidence if e.evidence_role in roles})


def observed_count(name: str, supporting: tuple[AdmittedObservation, ...]) -> int:
    if name == "source_diversity":
        return len({e.source_class for e in supporting})
    return independent_groups(supporting, GATE_ROLES.get(name, ()))


def qualify_hypothesis(*, stage: QualificationStage, hypothesis_id: str, admitted: tuple[AdmittedObservation, ...], gates: tuple[HardGatePolicy, ...],
                       ) -> tuple[QualificationState, tuple[GateResult, ...], tuple[AdmittedObservation, ...], tuple[AdmittedObservation, ...], tuple[OpenGap, ...]]:
    by_name = {g.name: g for g in gates}
    mine = tuple(e for e in admitted if hypothesis_id in e.hypothesis_ids and e.duplicate_of is None)
    # ADR-069: what an observation means FOR THIS hypothesis (its stated relation; the global polarity when none was stated)
    supporting = tuple(e for e in mine if e.polarity_for(hypothesis_id) == Polarity.SUPPORTING)
    contradicting = tuple(e for e in mine if e.polarity_for(hypothesis_id) == Polarity.CONTRADICTING)
    results = tuple(GateResult(gate_id=by_name[n].id, name=n, minimum=by_name[n].minimum, observed=observed_count(n, supporting),
                               passed=observed_count(n, supporting) >= by_name[n].minimum) for n in STAGE_GATES[stage] if n in by_name)
    passed = sum(1 for r in results if r.passed)
    if not mine:
        state = QualificationState.NO_DEFENSIBLE_BRIDGE
    elif len(contradicting) > len(supporting):
        state = QualificationState.REJECTED
    elif results and passed == len(results):
        state = QualificationState.PROMOTED
    elif results and passed * 2 >= len(results):
        state = QualificationState.PROVISIONAL
    else:
        state = QualificationState.UNPROVEN
    gaps = tuple(OpenGap(gap_id=f"gap-{hypothesis_id}-{r.name}", hypothesis_id=hypothesis_id,
                         question=f"{r.name}: {r.observed}/{r.minimum} {by_name[r.name].unit}", evidence_role=GATE_ROLES.get(r.name, ("behavior",))[0])
                 for r in results if not r.passed)
    return state, results, supporting, contradicting, gaps


__all__ = ["GateResult", "OpenGap", "QualificationStage", "QualificationState", "RegistrySnapshotRef", "STAGE_GATES", "qualify_hypothesis"]
