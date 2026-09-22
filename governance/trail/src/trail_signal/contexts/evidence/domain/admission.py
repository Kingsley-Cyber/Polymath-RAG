"""Evidence admission (ADR-063, HR2): pure, deterministic, offline. Every harness observation is evaluated against the
registry-derived admission policy for source suitability, research stage, evidence role, supply-only handling,
hypothesis linkage, freshness against the routed source's policy, provenance, independence group, duplicates,
polarity, and limitations. Rejections stay traceable with a reason code. A registry prior is never evidence."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_serializer, model_validator
from typing_extensions import Self

from trail_signal.kernel.contracts import BoundaryModel, Identifier, NonEmptyText, ReasonCode, Sha256

EvidenceRole = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,40}$")]
LongText = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
NonNegInt = Annotated[int, Field(strict=True, ge=0)]
PosInt = Annotated[int, Field(strict=True, ge=1)]
Unit = Annotated[float, Field(ge=0.0, le=1.0)]
# docs/domain/03_evidence_standard.md: live price/availability 30 days; social and marketplace trend 14 days; operations and risk
# 90 days; stable behaviour, friction, workarounds, and contradictions are retained for a year. Used only when a routed source
# declares no freshness policy.
ROLE_FRESHNESS_DAYS = {"price": 30, "competition": 30, "supply": 30, "demand": 14, "seasonality": 14, "operations": 90, "risk": 90,
                       "friction": 365, "workaround": 365, "behavior": 365, "contradiction": 365}
NEGATION = ("no ", "not ", "never ", "nobody ", "none ")


class ResearchStage(StrEnum):
    FIELD_EVIDENCE = "field_evidence"
    PRODUCT_REALITY = "product_reality"
    SUPPLY = "supply"


class Polarity(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"


class ReceiptSource(BoundaryModel):
    source_id: Identifier
    url: LongText
    source_class: Identifier
    retrieved_at: datetime
    published_at_if_known: datetime | None


class ReceiptMetric(BoundaryModel):
    name: Identifier
    value: float
    unit: NonEmptyText
    sample_n: NonNegInt | None


class HypothesisRelation(BoundaryModel):
    """ADR-069: what ONE observation means for ONE hypothesis. The evidence role says what kind of evidence it is; the relation says
    which way it cuts for that hypothesis. One observation may support H1, contradict H2 and be neutral to H3."""
    hypothesis_id: Identifier
    relation: Literal["SUPPORTS", "CONTRADICTS", "NEUTRAL"]


class ReceiptObservation(BoundaryModel):
    observation_id: Identifier
    source_id: Identifier
    claim: LongText
    paraphrase_or_excerpt: LongText
    metric_if_present: ReceiptMetric | None
    context: LongText
    evidence_role_claimed: EvidenceRole | None
    hypothesis_ids: tuple[Identifier, ...]
    hypothesis_relations: tuple[HypothesisRelation, ...] = ()  # ADR-069: optional; absent = the legacy global polarity rule decides


class ReceiptToolTrace(BoundaryModel):
    search_intent_id: Identifier
    tool_class: Identifier
    query_count: NonNegInt | None


class HypothesisRef(BoundaryModel):
    hypothesis_id: Identifier
    revision: NonNegInt
    status: Identifier


class RegistrySnapshotRef(BoundaryModel):
    snapshot_id: Identifier
    content_hash: Sha256


class SourceRolePolicy(BoundaryModel):
    """The registry snapshot's source-role row as the evidence context reads it (registry data, never code)."""
    source_id: Identifier
    source_class: Identifier | None
    domains_or_patterns: tuple[NonEmptyText, ...]
    supported_research_stages: tuple[ResearchStage, ...]
    supported_evidence_roles: tuple[EvidenceRole, ...]
    freshness_policy: Identifier | None
    independence_group: NonEmptyText
    limitations: LongText | None
    enabled: bool
    registry_backed: bool


class HardGatePolicy(BoundaryModel):
    id: Identifier
    name: Identifier
    minimum: PosInt
    unit: NonEmptyText


class AdmissionPolicy(BoundaryModel):
    """Projection of one TrailRegistrySnapshotV1 (source roles, prior ids, hard gates); every record carries the snapshot ref."""
    registry_snapshot: RegistrySnapshotRef
    source_roles: tuple[SourceRolePolicy, ...]
    prior_record_ids: tuple[Identifier, ...]
    hard_gates: tuple[HardGatePolicy, ...]
    promotion_rule: Identifier


class RejectedObservation(BoundaryModel):
    observation_id: Identifier
    reason_code: ReasonCode
    detail: LongText


class AdmittedObservation(BoundaryModel):
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
    hypothesis_relations: tuple[HypothesisRelation, ...] = ()  # ADR-069: stated relations of the LINKED hypotheses only

    def polarity_for(self, hypothesis_id: str) -> Polarity | None:
        """The polarity of this observation FOR ONE hypothesis: its stated relation when the receipt gave one (NEUTRAL -> None: it
        neither supports nor contradicts), else the observation's global polarity (the pre-ADR-069 rule, unchanged)."""
        return relation_polarity(self.hypothesis_relations, hypothesis_id, self.polarity)

    @model_serializer(mode="wrap")
    def _omit_absent_relations(self, handler):
        """A record without stated relations serialises exactly as it did before ADR-069 (recorded envelopes and replays stay byte-stable)."""
        data = handler(self)
        if not data.get("hypothesis_relations"):
            data.pop("hypothesis_relations", None)
        return data

    @model_validator(mode="after")
    def _linked_and_supply_bound(self) -> Self:
        if not self.hypothesis_ids:
            raise ValueError("admitted evidence links to at least one hypothesis")
        if self.evidence_role == "supply" and self.stage_relevance != ResearchStage.SUPPLY:
            raise ValueError("supply evidence belongs to the supply stage only")
        return self


def relation_polarity(relations, hypothesis_id: str, fallback: Polarity) -> Polarity | None:
    for r in relations:
        if r.hypothesis_id == hypothesis_id:
            return {"SUPPORTS": Polarity.SUPPORTING, "CONTRADICTS": Polarity.CONTRADICTING}.get(r.relation)
    return fallback


def normalise_claim(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split())


def host_of(url: str) -> str:
    stripped = re.sub(r"^[a-z]+://", "", url.lower()).split("/", 1)[0].split("@")[-1].split(":")[0]
    return stripped[4:] if stripped.startswith("www.") else stripped


def route_source(policy: AdmissionPolicy, source: ReceiptSource) -> SourceRolePolicy | None:
    host = host_of(source.url)
    for role in policy.source_roles:
        if role.enabled and any(pattern not in ("*", "-") and (host == pattern or host.endswith("." + pattern) or pattern in source.url) for pattern in role.domains_or_patterns):
            return role
    for role in policy.source_roles:  # class-level wildcard rows (forums, retailers, manufacturer sites, interviews)
        if role.enabled and role.source_class == source.source_class and any(pattern in ("*", "-") for pattern in role.domains_or_patterns):
            return role
    return None


def freshness_days(role: EvidenceRole, source: SourceRolePolicy) -> int | None:
    match = re.search(r"-(\d+)d$", source.freshness_policy or "")
    return int(match.group(1)) if match else ROLE_FRESHNESS_DAYS.get(role)


def evidence_id(action_id: str, observation_id: str) -> str:
    return "fev_" + hashlib.sha256(f"{action_id}:{observation_id}".encode("utf-8")).hexdigest()[:12]


def admit_observations(*, stage: ResearchStage, action_id: str, run_id: str, operation_id: str, evaluated_at: datetime, policy: AdmissionPolicy,
                       sources: tuple[ReceiptSource, ...], observations: tuple[ReceiptObservation, ...], hypotheses: tuple[HypothesisRef, ...],
                       ) -> tuple[tuple[AdmittedObservation, ...], tuple[RejectedObservation, ...]]:
    live = tuple(h.hypothesis_id for h in hypotheses if h.status not in ("killed", "merged"))
    by_id = {s.source_id: s for s in sources}
    priors = set(policy.prior_record_ids)
    admitted: list[AdmittedObservation] = []
    rejected: list[RejectedObservation] = []
    first_seen: dict[tuple[str, str], str] = {}

    def reject(observation: ReceiptObservation, code: str, detail: str) -> None:
        rejected.append(RejectedObservation(observation_id=observation.observation_id, reason_code=code, detail=detail))

    for observation in observations:
        source = by_id.get(observation.source_id)
        if source is None:
            reject(observation, "SOURCE_UNLISTED", "the observation names no listed receipt source"); continue
        if observation.source_id in priors or any(token in priors for token in observation.claim.split()):
            reject(observation, "PRIOR_IS_NOT_EVIDENCE", "a registry prior is not an observation, demand, proof, or market reality"); continue
        routed = route_source(policy, source)
        if routed is None:
            reject(observation, "SOURCE_UNREGISTERED", f"no enabled registry source routes {source.url}"); continue
        if stage not in routed.supported_research_stages:
            reject(observation, "SOURCE_STAGE_UNSUITABLE", f"{routed.source_id} does not serve stage {stage.value}"); continue
        role = observation.evidence_role_claimed or (routed.supported_evidence_roles[0] if routed.supported_evidence_roles else "")
        if role == "demand" and routed.source_class == "supplier_listing":
            reject(observation, "SUPPLY_IS_NOT_DEMAND", "a supplier observation is supply evidence, never demand"); continue
        if role not in routed.supported_evidence_roles:
            reject(observation, "SOURCE_ROLE_UNSUITABLE", f"{routed.source_id} cannot support the evidence role {role or 'none'}"); continue
        if role == "supply" and stage != ResearchStage.SUPPLY:
            reject(observation, "SUPPLY_IS_NOT_DEMAND", "supply evidence is admitted in the supply stage only"); continue
        linked = tuple(h for h in observation.hypothesis_ids if h in live) if observation.hypothesis_ids else (live if len(live) == 1 else ())
        if not linked:
            reject(observation, "HYPOTHESIS_LINK_MISSING", "the observation links to no live hypothesis"); continue
        anchor = source.published_at_if_known or source.retrieved_at
        age_days = (evaluated_at - anchor).days
        window = freshness_days(role, routed)
        if window is not None and age_days > 2 * window:
            reject(observation, "STALE_BEYOND_POLICY", f"{age_days} days old against a {window}-day policy"); continue
        fresh = "fresh" if window is None or age_days <= window else "stale_within_policy"
        group = routed.independence_group.replace("{domain}", host_of(source.url) or "unknown").replace("{participant}", observation.observation_id)
        key = (group, normalise_claim(observation.claim))
        new_id = evidence_id(action_id, observation.observation_id)
        duplicate_of = first_seen.get(key)
        first_seen.setdefault(key, new_id)
        contradicting = role == "contradiction" or observation.claim.lower().startswith(NEGATION)
        admitted.append(AdmittedObservation(
            admitted_evidence_id=new_id, observation_id=observation.observation_id, source_id=source.source_id, evidence_role=role,
            source_class=routed.source_class or source.source_class, source_suitability="suitable" if routed.registry_backed else "conditional",
            freshness=fresh, provenance="recorded", independence_group=group, duplicate_of=duplicate_of,
            polarity=Polarity.CONTRADICTING if contradicting else Polarity.SUPPORTING, hypothesis_ids=linked, stage_relevance=stage,
            anchored_at=anchor, limitations=(routed.limitations,) if routed.limitations else (),
            trail_admission_record_id=f"adm-{operation_id}-{observation.observation_id}", authority_class="ADMITTED_OBSERVATION",
            hypothesis_relations=tuple(r for r in observation.hypothesis_relations if r.hypothesis_id in linked)))
    return tuple(admitted), tuple(rejected)


def admission_id(run_id: str, action_id: str) -> str:
    return "hadm_" + hashlib.sha256(f"{run_id}:{action_id}".encode("utf-8")).hexdigest()[:12]
