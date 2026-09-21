"""Hypothesis judgement (ADR-063, HR1): deterministic selective pressure over the registry snapshot and an admitted-evidence
view. It returns typed verdicts with reason codes and cause references and never generates a hypothesis. The verdict
vocabulary is ADR-063's (reject, merge, deduplicate, weaken, strengthen, challenge, require_evidence, promote); each verdict
names the Polymath transition it maps to (or none) so the wire mapping is explicit. A prior is never support."""
from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import model_validator
from typing_extensions import Self

from trail_signal.contexts.planning.domain.gap_compiler import STAGE_GATE_ROLES, EvidenceGap, HypothesisView, normalise, refuse_prior_citations
from trail_signal.contexts.planning.domain.registry_compiler import LongText, ResearchStage, snapshot_ref
from trail_signal.kernel.contracts import BoundaryModel, Identifier, ReasonCode


class JudgementStage(StrEnum):
    FILTER = "filter"
    REVISION = "revision"


class VerdictKind(StrEnum):
    REJECT = "REJECT"
    MERGE = "MERGE"
    DEDUPLICATE = "DEDUPLICATE"
    WEAKEN = "WEAKEN"
    STRENGTHEN = "STRENGTHEN"
    CHALLENGE = "CHALLENGE"
    REQUIRE_EVIDENCE = "REQUIRE_EVIDENCE"
    PROMOTE = "PROMOTE"


class Polarity(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    NEUTRAL = "neutral"


POLYMATH_TRANSITION: dict[VerdictKind, str | None] = {
    VerdictKind.REJECT: "KILL", VerdictKind.MERGE: "MERGE", VerdictKind.DEDUPLICATE: "MERGE", VerdictKind.WEAKEN: "WEAKEN",
    VerdictKind.STRENGTHEN: "STRENGTHEN", VerdictKind.CHALLENGE: "CONTRADICT", VerdictKind.REQUIRE_EVIDENCE: None, VerdictKind.PROMOTE: "PROMOTE",
}
ABSORBED = frozenset({"killed", "merged"})


class CauseRef(BoundaryModel):
    kind: Literal["chunk", "document", "graph_fact", "graph_hop", "parent_map", "field_evidence", "evidence_admission", "hypothesis", "step_output"]
    id: Identifier


class Contradiction(BoundaryModel):
    statement: LongText
    evidence_ids: tuple[Identifier, ...]


class AdmittedEvidenceView(BoundaryModel):
    admitted_evidence_id: Identifier
    hypothesis_ids: tuple[Identifier, ...]
    independence_group: Identifier
    polarity: Polarity
    evidence_role: Identifier


class HypothesisVerdict(BoundaryModel):
    hypothesis_id: Identifier
    kind: VerdictKind
    polymath_transition: Literal["KILL", "MERGE", "WEAKEN", "STRENGTHEN", "CONTRADICT", "PROMOTE"] | None
    cause_refs: tuple[CauseRef, ...]
    reason_code: ReasonCode
    into_hypothesis_id: Identifier | None
    field_evidence_ids: tuple[Identifier, ...]
    contradictions: tuple[Contradiction, ...]

    @model_validator(mode="after")
    def _lineage(self) -> Self:
        if not self.cause_refs:
            raise ValueError("a verdict names at least one cause")
        if (self.kind in {VerdictKind.MERGE, VerdictKind.DEDUPLICATE}) != (self.into_hypothesis_id is not None):
            raise ValueError("MERGE and DEDUPLICATE, and only they, name into_hypothesis_id")
        if self.kind == VerdictKind.CHALLENGE and not self.contradictions:
            raise ValueError("CHALLENGE carries contradictions")
        if self.polymath_transition != POLYMATH_TRANSITION[self.kind]:
            raise ValueError("polymath_transition must match the verdict kind")
        return self


def _verdict(hypothesis_id: str, kind: VerdictKind, causes: tuple[CauseRef, ...], reason: str, *, into: str | None = None,
             evidence: tuple[str, ...] = (), contradictions: tuple[Contradiction, ...] = ()) -> HypothesisVerdict:
    return HypothesisVerdict(hypothesis_id=hypothesis_id, kind=kind, polymath_transition=POLYMATH_TRANSITION[kind], cause_refs=causes, reason_code=reason,
                             into_hypothesis_id=into, field_evidence_ids=evidence, contradictions=contradictions)


def judge_hypotheses(snapshot, request):
    from trail_signal.contexts.planning.public.contracts import HypothesisJudgementV1

    refuse_prior_citations(snapshot, request.admitted_evidence_ids)
    admitted = request.admitted_evidence
    live = [h for h in request.hypotheses if h.status not in ABSORBED]
    verdicts: list[HypothesisVerdict] = []
    open_gaps: list[EvidenceGap] = []
    if request.stage == JudgementStage.FILTER:
        by_statement: dict[str, list[str]] = {}
        for hypothesis in live:
            by_statement.setdefault(normalise(hypothesis.statement), []).append(hypothesis.hypothesis_id)
        for ids in by_statement.values():
            keep = sorted(ids)[0]
            for duplicate in sorted(ids)[1:]:
                verdicts.append(_verdict(duplicate, VerdictKind.DEDUPLICATE, (CauseRef(kind="hypothesis", id=keep),), "REDUNDANT_STATEMENT", into=keep))
        for hypothesis in live:  # a prior alone never supports a hypothesis
            if hypothesis.knowledge_support_count == 0:
                verdicts.append(_verdict(hypothesis.hypothesis_id, VerdictKind.WEAKEN, (CauseRef(kind="hypothesis", id=hypothesis.hypothesis_id),), "NO_KNOWLEDGE_SUPPORT"))
        return HypothesisJudgementV1(registry_snapshot=snapshot_ref(snapshot), stage=request.stage, verdicts=tuple(verdicts), open_gaps=())
    gates = {gate.name: gate for gate in snapshot.scoring_policy.hard_gates}
    stage_roles = STAGE_GATE_ROLES[ResearchStage.FIELD_EVIDENCE]
    for hypothesis in live:
        mine = [a for a in admitted if hypothesis.hypothesis_id in a.hypothesis_ids]
        supporting = [a for a in mine if a.polarity == Polarity.SUPPORTING]
        contradicting = [a for a in mine if a.polarity == Polarity.CONTRADICTING]
        groups = {a.independence_group for a in supporting}
        causes = tuple(([CauseRef(kind="evidence_admission", id=request.latest_admission_id)] if request.latest_admission_id else [])
                       + [CauseRef(kind="field_evidence", id=a.admitted_evidence_id) for a in mine[:5]])
        evidence_ids = tuple(a.admitted_evidence_id for a in mine)
        if not mine:
            verdicts.append(_verdict(hypothesis.hypothesis_id, VerdictKind.REQUIRE_EVIDENCE, (CauseRef(kind="hypothesis", id=hypothesis.hypothesis_id),), "NO_ADMITTED_EVIDENCE"))
            open_gaps.append(EvidenceGap(gap_id=f"gap-{hypothesis.hypothesis_id[-8:]}-evidence", hypothesis_id=hypothesis.hypothesis_id, question="no admitted evidence yet", evidence_role=stage_roles[0]))
        elif len(groups) < 2 and supporting:  # self-corroboration: one independence group is one observation
            verdicts.append(_verdict(hypothesis.hypothesis_id, VerdictKind.WEAKEN, causes, "SINGLE_INDEPENDENCE_GROUP", evidence=evidence_ids))
            open_gaps.append(EvidenceGap(gap_id=f"gap-{hypothesis.hypothesis_id[-8:]}-independence", hypothesis_id=hypothesis.hypothesis_id,
                                         question="corroborate from a second independent source", evidence_role=supporting[0].evidence_role))
        elif contradicting and len(contradicting) >= len(supporting):
            verdicts.append(_verdict(hypothesis.hypothesis_id, VerdictKind.CHALLENGE, causes, "CONTRADICTION_DOMINATES", evidence=evidence_ids,
                                     contradictions=(Contradiction(statement="admitted contradicting evidence outweighs support", evidence_ids=tuple(a.admitted_evidence_id for a in contradicting)),)))
        elif len(supporting) >= gates["independent_complaints"].minimum and len(groups) >= gates["source_diversity"].minimum:
            verdicts.append(_verdict(hypothesis.hypothesis_id, VerdictKind.STRENGTHEN, causes, "HARD_GATE_THRESHOLDS_MET", evidence=evidence_ids))
        else:
            verdicts.append(_verdict(hypothesis.hypothesis_id, VerdictKind.STRENGTHEN, causes, "INDEPENDENT_SUPPORT", evidence=evidence_ids))
            open_gaps.append(EvidenceGap(gap_id=f"gap-{hypothesis.hypothesis_id[-8:]}-volume", hypothesis_id=hypothesis.hypothesis_id,
                                         question=f"reach {gates['independent_complaints'].minimum} independent observations ({len(supporting)} so far)", evidence_role=supporting[0].evidence_role))
    return HypothesisJudgementV1(registry_snapshot=snapshot_ref(snapshot), stage=request.stage, verdicts=tuple(verdicts), open_gaps=tuple(open_gaps))
