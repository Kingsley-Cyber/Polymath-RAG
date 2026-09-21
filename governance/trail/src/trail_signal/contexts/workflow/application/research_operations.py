"""Bounded synchronous research operations (ADR-063, HR3). The polymath principal calls registry.project, gaps.compile,
evidence.admit, hypotheses.judge, territory.project, opportunity.qualify, and opportunity.score through the shared daemon; each
maps Polymath's wire payload onto the planning, evidence, or scoring contracts, runs one pure deterministic function over the
compiled registry snapshot, and atomically commits one terminal audit operation and one immutable result (no Temporal state).
No response carries a secret, cookie, page body, storage path, or provider payload: results are typed contracts only."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

from trail_signal.contexts.evidence.public.contracts import (
    AdmissionPolicy, AdmittedObservationV1, EvidenceAdmissionRequestV1, HypothesisRef, QualificationRequestV1, QualificationStage,
    RegistrySnapshotRef as EvidenceSnapshotRef, ResearchStage as EvidenceStage,
)
from trail_signal.contexts.evidence.public.ports import admit_evidence, qualify
from trail_signal.contexts.planning.public.contracts import (
    AdmittedEvidenceView, EvidenceGap, HypothesisJudgementRequestV1, HypothesisJudgementV1, HypothesisView, JudgementStage, PhysicalJob,
    ProductTerritoryProjectionV1, RegistryProjectionRequestV1, RegistryProjectionV1, ResearchDirectiveV1, ResearchStage, TrailRegistrySnapshotV1,
)
from trail_signal.contexts.platform.public.contracts import PrincipalCapabilityV6, PrincipalContextV6
from trail_signal.contexts.scoring.public.contracts import (
    EvidenceSignalInput, OpportunityScoreRefusalV1, OpportunityScoreRequestV1, OpportunityScoreV1, QualificationView, ScoreRefused, ScoreWeights, SnapshotRef as ScoringSnapshotRef, refuse_score, score_opportunity,
)
from trail_signal.contexts.workflow.public.operations import (
    BoundedResearchRequestV1, BoundedResearchResultV1, OperationExecutionAuthorityV1, OperationOutputKindV3, OperationOutputRefV3, OperationPhase, OperationStatusV4, OperationTerminalOutcomeV2,
    ResearchCauseRefV1, ResearchKnowledgeGapV1, ResearchPriorV1, ResearchResultV1, ResearchSnapshotRefV1, ResearchTerritoryV1, ResearchVerdictV1,
)
from trail_signal.kernel.contracts import BoundaryModel

RESEARCH_OPERATIONS = ("registry.project", "gaps.compile", "evidence.admit", "hypotheses.judge", "territory.project", "opportunity.qualify", "opportunity.score")
STAGE_BY_WIRE = {"field_evidence": ResearchStage.FIELD_EVIDENCE, "product_reality": ResearchStage.PRODUCT_REALITY, "supply": ResearchStage.SUPPLY}
QUALIFICATION_STAGE_BY_WIRE = {"market_delta": QualificationStage.MARKET_DELTA, "supply": QualificationStage.SUPPLY}


class ResearchRefused(PermissionError):
    """The operation is refused with a typed reason code (capability, policy, snapshot, gate, or shape)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


def canonical_text(value: BoundaryModel | dict) -> str:
    """Canonical JSON text (sorted keys, no whitespace); the SHA-256 of its UTF-8 form is the identity of every stored row."""
    payload = value.model_dump(mode="json") if isinstance(value, BoundaryModel) else value
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_of(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _from_wire(model, fields: dict):
    """Strict contracts accept enum members only; wire strings validate in JSON mode, the wire's own encoding."""
    return model.model_validate_json(json.dumps(fields))


@dataclass(frozen=True)
class ResearchOperationRecord:
    """The audit operation row as the workflow application writes it (canonical JSON text + SHA-256 are the truth)."""
    operation_id: str
    principal_id: str
    audit_identity: str
    operation_kind: str
    idempotency_key: str
    request_id: str
    run_ref: str
    purpose_ref: str
    registry_snapshot_id: str
    registry_snapshot_hash: str
    request_sha256: str
    request_json: str
    status_json: str
    committed_at: datetime


@dataclass(frozen=True)
class ResearchResultRecord:
    operation_id: str
    result_schema_name: str
    result_sha256: str
    result_json: str
    committed_at: datetime


class CommittedOperation(Protocol):
    operation_id: str
    request_sha256: str
    registry_snapshot_hash: str


class CommittedResult(Protocol):
    result_json: str


class ResearchStorePort(Protocol):
    """Data OS commits one audit operation and one immutable result atomically and replays the first commit for the same identity."""
    async def commit(self, operation: ResearchOperationRecord, result: ResearchResultRecord) -> tuple[CommittedOperation, CommittedResult]: ...
    async def load(self, operation_id: str) -> tuple[CommittedOperation, CommittedResult | None] | None: ...


@dataclass(frozen=True)
class ResearchFunctions:
    """The planning context's pure functions, handed in by the composition root: the workflow application only ever imports public surfaces."""
    derive_registry_coordinates: Callable[[TrailRegistrySnapshotV1, RegistryProjectionRequestV1], RegistryProjectionV1]
    compile_research_directive: Callable[..., ResearchDirectiveV1]
    judge_hypotheses: Callable[[TrailRegistrySnapshotV1, HypothesisJudgementRequestV1], HypothesisJudgementV1]
    map_product_territories: Callable[[TrailRegistrySnapshotV1, RegistryProjectionRequestV1], ProductTerritoryProjectionV1]
    prior_record_ids: Callable[[TrailRegistrySnapshotV1], frozenset[str]]


def _id(prefix: str, value: str) -> str:
    return f"{prefix}:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def admission_policy(snapshot: TrailRegistrySnapshotV1, prior_ids: frozenset[str]) -> AdmissionPolicy:
    """The evidence context's projection of the registry snapshot (source roles, prior ids, hard gates) — registry data, never code."""
    roles = tuple({"source_id": r.source_id, "source_class": r.source_class, "domains_or_patterns": r.domains_or_patterns,
                   "supported_research_stages": tuple(EvidenceStage(s.value) for s in r.supported_research_stages), "supported_evidence_roles": r.supported_evidence_roles,
                   "freshness_policy": r.freshness_policy, "independence_group": r.independence_group, "limitations": r.limitations, "enabled": r.enabled,
                   "registry_backed": r.registry_backed} for r in snapshot.source_roles)
    gates = tuple({"id": g.id, "name": g.name, "minimum": g.minimum, "unit": g.unit} for g in snapshot.scoring_policy.hard_gates)
    return AdmissionPolicy(registry_snapshot=EvidenceSnapshotRef(snapshot_id=snapshot.snapshot_id, content_hash=snapshot.content_hash), source_roles=roles,
                           prior_record_ids=tuple(sorted(prior_ids)), hard_gates=gates, promotion_rule=snapshot.scoring_policy.promotion_rule)


@dataclass
class ResearchOperationService:
    store: ResearchStorePort
    snapshot: TrailRegistrySnapshotV1
    weights: ScoreWeights
    maximum_request_bytes: int
    functions: ResearchFunctions
    clock: Callable[[], datetime] = _utc_now
    policy: AdmissionPolicy = field(init=False)
    admitted: dict[str, tuple[AdmittedObservationV1, ...]] = field(default_factory=dict)  # admission_id -> admitted records (this daemon's memory of its own commits)

    def __post_init__(self) -> None:
        self.policy = admission_policy(self.snapshot, self.functions.prior_record_ids(self.snapshot))

    # ── envelope helpers
    def _snapshot_ref(self) -> ResearchSnapshotRefV1:
        return ResearchSnapshotRefV1(snapshot_id=self.snapshot.snapshot_id, content_hash=self.snapshot.content_hash)

    def _authorize(self, principal: PrincipalContextV6, kind: str) -> None:
        if kind not in RESEARCH_OPERATIONS:
            raise ResearchRefused("OPERATION_UNKNOWN", kind)
        if PrincipalCapabilityV6(kind) not in principal.capabilities:
            raise ResearchRefused("CAPABILITY_DENIED", f"{kind} denied for {principal.principal_id}")

    def _check_snapshot(self, request: BoundedResearchRequestV1) -> None:
        if request.operation_kind != "registry.project" and request.registry_snapshot_id != self.snapshot.snapshot_id:
            raise ResearchRefused("SNAPSHOT_MISMATCH", f"caller reasons against {request.registry_snapshot_id}; this build compiled {self.snapshot.snapshot_id}")
        if len(canonical_text(request).encode("utf-8")) > self.maximum_request_bytes:
            raise ResearchRefused("REQUEST_TOO_LARGE", f"request exceeds {self.maximum_request_bytes} canonical bytes")

    @staticmethod
    def _hypotheses(request: BoundedResearchRequestV1) -> tuple[HypothesisView, ...]:
        return tuple(HypothesisView(hypothesis_id=h.hypothesis_id, revision=h.revision, status=h.status, statement=h.statement, knowledge_support_count=0) for h in request.payload.hypotheses)

    @staticmethod
    def _gaps(gaps, hypotheses) -> tuple[EvidenceGap, ...]:
        fallback = hypotheses[0].hypothesis_id if hypotheses else None
        out = []
        for index, gap in enumerate(gaps):
            hypothesis_id = gap.hypothesis_id or fallback
            if hypothesis_id is None:
                continue
            out.append(_from_wire(EvidenceGap, {"gap_id": gap.gap_id or f"gap_{index}", "hypothesis_id": hypothesis_id, "question": gap.question, "evidence_role": gap.evidence_role}))
        return tuple(out)

    def _admitted_views(self, ids: tuple[str, ...]) -> tuple[AdmittedEvidenceView, ...]:
        wanted = set(ids); views = []
        for records in self.admitted.values():
            for a in records:
                if a.admitted_evidence_id in wanted and a.duplicate_of is None:
                    views.append(_from_wire(AdmittedEvidenceView, {"admitted_evidence_id": a.admitted_evidence_id, "hypothesis_ids": a.hypothesis_ids, "independence_group": a.independence_group.replace(" ", "_")[:256],
                                                                  "polarity": a.polarity.value, "evidence_role": a.evidence_role}))
        views.sort(key=lambda v: v.admitted_evidence_id)  # canonical order, independent of self.admitted iteration order (HR4 restart determinism)
        return tuple(views)

    def _admitted_records(self, ids: tuple[str, ...]) -> tuple[AdmittedObservationV1, ...]:
        wanted = set(ids)
        # Canonical lineage order (HR4): sort by admitted_evidence_id so every persisted evidence-id tuple (a qualification's
        # supporting/contradicting ids, a score's admitted_evidence_ids) is byte-identical regardless of self.admitted iteration
        # order — which differs between a live daemon (commit order) and a restarted one (load_admitted rebuild order). Scoring
        # is set-based so the score value is unchanged; only the recorded lineage order is made deterministic.
        return tuple(sorted((a for records in self.admitted.values() for a in records if a.admitted_evidence_id in wanted),
                            key=lambda a: a.admitted_evidence_id))

    async def _ensure_admitted(self, run_ref: str) -> None:
        """Rebuild the in-memory admitted-record view from the durable store (HR4). A restarted daemon recovers every
        evidence.admit committed for this run so a resumed run judges, qualifies and scores against the same evidence it had
        before the restart. load_admitted yields the results in ascending (committed_at, operation_id) order and the last write
        for a given admission_id wins — matching the live path's keep-last policy, so a re-admitted corrected receipt overrides
        the earlier one identically whether the daemon stayed up or restarted."""
        for result_json in await self.store.load_admitted(run_ref):
            envelope = (BoundedResearchResultV1.model_validate_json(result_json) if isinstance(result_json, (str, bytes, bytearray))
                        else BoundedResearchResultV1.model_validate(result_json))  # the durable store yields result JSON text; tolerate a decoded mapping too
            admission = envelope.result.evidence_admission
            if admission is not None:
                self.admitted[admission.admission_id] = admission.admitted

    # ── the seven operations (pure functions over the snapshot; nothing here fetches, schedules, or scores outside the scoring context)
    def _run(self, request: BoundedResearchRequestV1, principal: PrincipalContextV6, operation_id: str) -> ResearchResultV1:
        payload = request.payload; kind = request.operation_kind; hypotheses = self._hypotheses(request)
        if kind == "registry.project":
            stage = STAGE_BY_WIRE.get(payload.stage or "", ResearchStage.FIELD_EVIDENCE)
            projection = self.functions.derive_registry_coordinates(self.snapshot, RegistryProjectionRequestV1(stage=stage, hypotheses=hypotheses, admitted_evidence_ids=payload.admitted_evidence_ids,
                                                                                                    max_priors_per_hypothesis=payload.max_priors_per_hypothesis or 12, physical_jobs=(), geography=None, language=None))
            return ResearchResultV1(registry_snapshot=self._snapshot_ref(), priors=tuple(ResearchPriorV1(registry_record_id=p.registry_record_id, prior_role=p.prior_role, hypothesis_ids=p.hypothesis_ids) for p in projection.priors),
                                    redundancy_groups=projection.redundancy_groups, unsupported_hypothesis_ids=projection.unsupported_hypothesis_ids)
        if kind == "gaps.compile":
            stage = STAGE_BY_WIRE.get(payload.stage or "", ResearchStage.FIELD_EVIDENCE)
            directive = self.functions.compile_research_directive(self.snapshot, stage=stage, gaps=self._gaps(payload.knowledge_gaps + payload.open_gaps, hypotheses), hypotheses=hypotheses, geography=None, language=None)
            return ResearchResultV1(registry_snapshot=self._snapshot_ref(), research_directive=directive)
        if kind == "evidence.admit":
            if payload.receipt is None or payload.action_id is None:
                raise ResearchRefused("RECEIPT_MISSING", "evidence.admit needs the harness receipt and its action id")
            stage = STAGE_BY_WIRE.get(payload.stage or "", ResearchStage.FIELD_EVIDENCE)
            admission = admit_evidence(EvidenceAdmissionRequestV1(stage=EvidenceStage(stage.value), action_id=payload.action_id, run_id=request.run_ref, trail_operation_id=operation_id,
                                                                  evaluated_at=self.clock(), receipt=payload.receipt,
                                                                  hypotheses=tuple(HypothesisRef(hypothesis_id=h.hypothesis_id, revision=h.revision, status=h.status) for h in payload.hypotheses),
                                                                  policy=self.policy))
            self.admitted[admission.admission_id] = admission.admitted
            return ResearchResultV1(registry_snapshot=self._snapshot_ref(), evidence_admission=admission)
        if kind == "hypotheses.judge":
            stage = JudgementStage.FILTER if (payload.stage or "") in ("", "filter", "field_evidence") and payload.latest_admission_id is None else JudgementStage.REVISION
            judgement = self.functions.judge_hypotheses(self.snapshot, HypothesisJudgementRequestV1(stage=stage, hypotheses=hypotheses, admitted_evidence_ids=payload.admitted_evidence_ids,
                                                                                     admitted_evidence=self._admitted_views(payload.admitted_evidence_ids), redundancy_groups=payload.redundancy_groups,
                                                                                     latest_admission_id=payload.latest_admission_id))
            verdicts = tuple(ResearchVerdictV1(hypothesis_id=v.hypothesis_id, kind=v.kind.value, polymath_transition=v.polymath_transition, cause_refs=tuple(ResearchCauseRefV1(kind=c.kind, id=c.id) for c in v.cause_refs),
                                               reason_code=v.reason_code, into_hypothesis_id=v.into_hypothesis_id) for v in judgement.verdicts)
            gaps = tuple(ResearchKnowledgeGapV1(gap_id=g.gap_id, hypothesis_id=g.hypothesis_id, question=g.question, evidence_role=g.evidence_role) for g in judgement.open_gaps)
            return ResearchResultV1(registry_snapshot=self._snapshot_ref(), verdicts=verdicts, open_gaps=gaps)
        if kind == "territory.project":
            jobs = tuple(PhysicalJob(hypothesis_id=j.hypothesis_id, job=j.job, mechanism=j.mechanism) for j in payload.physical_jobs)
            projection = self.functions.map_product_territories(self.snapshot, RegistryProjectionRequestV1(stage=ResearchStage.PRODUCT_REALITY, hypotheses=hypotheses, admitted_evidence_ids=payload.admitted_evidence_ids,
                                                                                            max_priors_per_hypothesis=payload.max_priors_per_hypothesis or 12, physical_jobs=jobs, geography=None, language=None))
            territories = tuple(ResearchTerritoryV1(territory_id=t.registry_record_id, territory=t.prior_role, hypothesis_ids=t.hypothesis_ids) for t in projection.territories)
            return ResearchResultV1(registry_snapshot=self._snapshot_ref(), territories=territories, research_directive=projection.research_directive)
        if kind == "opportunity.qualify":
            stage = QUALIFICATION_STAGE_BY_WIRE.get(payload.stage or "")
            if stage is None or not hypotheses:
                raise ResearchRefused("QUALIFICATION_SHAPE", "opportunity.qualify needs a qualification stage and at least one hypothesis")
            policy = self.policy
            records = self._admitted_records(payload.admitted_evidence_ids)
            # Portfolio (ADR-063 HR4, owner 2026-09-15): qualify EVERY live hypothesis independently, in authoritative order.
            # No implicit hypotheses[0] winner — evidence tagged to any hypothesis is qualified against that hypothesis.
            qualifications = tuple(
                qualify(QualificationRequestV1(stage=stage, record_id=_id("qualification", f"{operation_id}:{stage.value}:{h.hypothesis_id}"),
                                               hypothesis_id=h.hypothesis_id, registry_snapshot=policy.registry_snapshot, admitted=records, policy=policy))
                for h in hypotheses)
            gaps = tuple(ResearchKnowledgeGapV1(gap_id=g.gap_id, hypothesis_id=g.hypothesis_id, question=g.question, evidence_role=g.evidence_role)
                         for q in qualifications for g in q.open_gaps)
            return ResearchResultV1(registry_snapshot=self._snapshot_ref(), qualifications=qualifications, open_gaps=gaps)
        if kind == "opportunity.score":
            if not hypotheses:
                raise ResearchRefused("SCORE_SHAPE", "opportunity.score needs at least one hypothesis")
            records = self._admitted_records(payload.admitted_evidence_ids)
            inputs = tuple(EvidenceSignalInput(admitted_evidence_id=a.admitted_evidence_id, evidence_role=a.evidence_role, source_class=a.source_class, independence_group=a.independence_group,
                                               polarity=a.polarity.value, hypothesis_ids=a.hypothesis_ids, anchored_at=a.anchored_at) for a in records if a.duplicate_of is None)
            snapshot_ref = ScoringSnapshotRef(snapshot_id=self.snapshot.snapshot_id, content_hash=self.snapshot.content_hash)
            as_of = self.clock()
            # Portfolio (ADR-063 HR4, owner 2026-09-15): score EVERY hypothesis whose qualifications pass the scoring hard gates;
            # a hypothesis that refuses (unmet gate, no admitted evidence) records a per-hypothesis refusal and never blocks the rest.
            # No implicit hypotheses[0] winner and no model-selected winner — ranking is derived from the deterministic scores afterward.
            scores: list[OpportunityScoreV1] = []
            refusals: list[OpportunityScoreRefusalV1] = []
            for h in hypotheses:
                mine = tuple(q for q in payload.qualifications if h.hypothesis_id in q.hypothesis_ids)
                views = tuple(QualificationView(record_id=q.record_id, stage=q.stage.value, state=q.state.value, gate_results=tuple({"name": g.name, "minimum": g.minimum, "observed": g.observed, "passed": g.passed} for g in q.gate_results)) for q in mine)
                record_id = _id("score", f"{operation_id}:{h.hypothesis_id}")
                try:
                    scores.append(score_opportunity(OpportunityScoreRequestV1(record_id=record_id, hypothesis_id=h.hypothesis_id, registry_snapshot=snapshot_ref,
                                                                              as_of=as_of, admitted=inputs, qualifications=views), self.weights))
                except ScoreRefused as exc:
                    refusals.append(refuse_score(record_id=record_id, hypothesis_id=h.hypothesis_id, registry_snapshot=snapshot_ref, as_of=as_of, error=exc))
            return ResearchResultV1(registry_snapshot=self._snapshot_ref(), trail_scores=tuple(scores), score_refusals=tuple(refusals))
        raise ResearchRefused("OPERATION_UNKNOWN", kind)

    async def operate(self, request: BoundedResearchRequestV1, principal: PrincipalContextV6) -> BoundedResearchResultV1:
        self._authorize(principal, request.operation_kind); self._check_snapshot(request)
        operation_id = _id("operation", f"{principal.principal_id}:{request.idempotency_key}:{request.operation_kind}")
        existing = await self.store.load(operation_id)
        if existing is not None and existing[1] is not None:
            operation, result = existing
            if operation.request_sha256 != sha256_of(canonical_text(request)):
                raise ResearchRefused("IDEMPOTENCY_CONFLICT", "the idempotency key was already used for a different request")
            return BoundedResearchResultV1.model_validate_json(result.result_json)
        await self._ensure_admitted(request.run_ref)  # HR4: a restarted daemon rebuilds the admitted view before it runs the operation
        body = self._run(request, principal, operation_id)
        now = self.clock()
        status = OperationStatusV4(operation_id=operation_id, execution_authority=OperationExecutionAuthorityV1.SYNCHRONOUS, phase=OperationPhase.TERMINAL,
                                   terminal_outcome=OperationTerminalOutcomeV2.SUCCEEDED, waiting_reason=None,
                                   output_refs=(OperationOutputRefV3(output_kind=OperationOutputKindV3.DATASET_QUERY, output_id=operation_id, generation=None),),  # ADR-034/037 synchronous pattern: one bounded query output = the immutable result row
                                   issue_refs=(), revision=1, updated_at=now, terminal_at=now, failure_code=None)
        envelope = BoundedResearchResultV1(operation_id=operation_id, operation_kind=request.operation_kind, status_revision=1, registry_snapshot=self._snapshot_ref(), result=body,
                                           result_sha256=sha256_of(canonical_text(body)))
        request_text = canonical_text(request)
        operation = ResearchOperationRecord(operation_id=operation_id, principal_id=principal.principal_id, audit_identity=principal.audit_identity, operation_kind=request.operation_kind,
                                         idempotency_key=request.idempotency_key, request_id=request.request_id, run_ref=request.run_ref, purpose_ref=request.purpose_ref,
                                         registry_snapshot_id=self.snapshot.snapshot_id, registry_snapshot_hash=self.snapshot.content_hash, request_sha256=sha256_of(request_text),
                                         request_json=request_text, status_json=canonical_text(status), committed_at=now)
        result_row = ResearchResultRecord(operation_id=operation_id, result_schema_name="trail_signal.bounded_research_result_v1.v1", result_sha256=sha256_of(canonical_text(envelope)),
                                       result_json=canonical_text(envelope), committed_at=now)
        committed_operation, committed_result = await self.store.commit(operation, result_row)
        return BoundedResearchResultV1.model_validate_json(committed_result.result_json)
