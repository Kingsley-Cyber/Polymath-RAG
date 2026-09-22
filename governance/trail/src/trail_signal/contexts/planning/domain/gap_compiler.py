"""Evidence-gap compilation, registry projection, and product-territory projection (ADR-063, HR1). Pure functions over a
``TrailRegistrySnapshotV1``: ``EvidenceGap[] x stage -> ResearchDirectiveV1`` (search intents from the compiled templates,
preferred/disallowed source roles from the side table, freshness from the strictest routed source, minimum independent
sources and success/falsification conditions from the hard gates). A registry prior can never be cited as admitted
evidence; supply sources never answer demand or friction gaps. No engine, browser, scraper, or SDK is named."""
from __future__ import annotations

import hashlib
import re
from typing import Annotated

from pydantic import Field, StringConstraints

from trail_signal.contexts.planning.domain.registry_compiler import (
    EvidenceRole, LongText, NonNegInt, PosInt, ResearchStage, SnapshotField, prior_record_ids, prior_sections, snapshot_ref,
)
from trail_signal.kernel.contracts import BoundaryModel, Identifier, NonEmptyText

FRESHNESS_DAYS: dict[str, int] = {
    "live-price-30d": 30, "social-7d": 7, "social-14d": 14, "social-30d": 30, "stable-behavior-90d": 90, "stable-behavior-365d": 365,
    "static-90d": 90, "static-365d": 365,
}
STAGE_GATE_ROLES: dict[ResearchStage, tuple[str, ...]] = {
    ResearchStage.FIELD_EVIDENCE: ("friction", "workaround", "behavior"),
    ResearchStage.PRODUCT_REALITY: ("competition", "price"),
    ResearchStage.SUPPLY: ("supply", "price"),
}
STOPWORDS = frozenset({"and", "the", "for", "with", "that", "this", "from", "into", "when", "their", "they", "have", "while"})


class SemanticCandidate(BoundaryModel):
    """ADR-069: structured candidates for one hypothesis (normalised ids and short phrases supplied by the caller). Trail matches
    them field to field; it never infers them from prose."""
    friction_families: tuple[Identifier, ...] = ()
    activity: NonEmptyText | None = None
    task: NonEmptyText | None = None
    context: NonEmptyText | None = None
    predicates: tuple[Identifier, ...] = ()
    product_territories: tuple[Identifier, ...] = ()

    def empty(self) -> bool:
        return not (self.friction_families or self.activity or self.task or self.context or self.predicates or self.product_territories)


class HypothesisView(BoundaryModel):
    hypothesis_id: Identifier
    revision: NonNegInt
    status: Identifier
    statement: LongText
    knowledge_support_count: NonNegInt
    semantic: SemanticCandidate | None = None


class EvidenceGap(BoundaryModel):
    gap_id: Identifier
    hypothesis_id: Identifier
    question: LongText
    evidence_role: EvidenceRole


class SearchIntent(BoundaryModel):
    intent_id: Identifier
    intent: NonEmptyText
    evidence_goal: Identifier
    evidence_roles: tuple[EvidenceRole, ...]
    template: NonEmptyText


class FreshnessRequirement(BoundaryModel):
    max_age_days: PosInt | None
    policy_ref: Identifier


class ResearchBudget(BoundaryModel):
    max_queries: PosInt
    max_sources: PosInt
    max_observations: PosInt


class PriorCoordinates(BoundaryModel):
    registry_record_id: Identifier
    prior_role: Identifier
    hypothesis_ids: tuple[Identifier, ...]
    coordinates: tuple[SnapshotField, ...]


class PhysicalJob(BoundaryModel):
    hypothesis_id: Identifier
    job: NonEmptyText
    mechanism: NonEmptyText


class PriorCitedAsEvidence(ValueError):
    """A registry prior was offered as admitted evidence; priors never satisfy an evidence gate."""


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).strip()


def tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in re.findall(r"[a-z]{3,}", (text or "").lower()) if t not in STOPWORDS)


def derived_id(prefix: str, *parts: str) -> str:
    return prefix + hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:16]


def refuse_prior_citations(snapshot, admitted_evidence_ids: tuple[str, ...]) -> None:
    cited = set(admitted_evidence_ids) & prior_record_ids(snapshot)
    if cited:
        raise PriorCitedAsEvidence(f"registry priors cited as evidence: {sorted(cited)}")


def compile_research_directive(snapshot, *, stage: ResearchStage, gaps: tuple[EvidenceGap, ...], hypotheses: tuple[HypothesisView, ...],
                               admitted_evidence_ids: tuple[str, ...] = (), geography: str | None, language: str | None):
    from trail_signal.contexts.planning.public.contracts import ResearchDirectiveV1

    refuse_prior_citations(snapshot, admitted_evidence_ids)
    roles_needed = sorted({gap.evidence_role for gap in gaps} | set(STAGE_GATE_ROLES[stage]))
    sources = [s for s in snapshot.source_roles if s.enabled and stage in s.supported_research_stages and set(s.supported_evidence_roles) & set(roles_needed)]
    intents = [SearchIntent(intent_id=i.intent_id, intent=i.intent, evidence_goal=i.evidence_goal, evidence_roles=i.evidence_roles, template=i.template)
               for i in snapshot.search_intents if i.enabled and i.research_stage == stage and set(i.evidence_roles) & set(roles_needed)]
    if not intents:  # stage-level fallback: every enabled compiled template of the stage
        intents = [SearchIntent(intent_id=i.intent_id, intent=i.intent, evidence_goal=i.evidence_goal, evidence_roles=i.evidence_roles, template=i.template)
                   for i in snapshot.search_intents if i.enabled and i.research_stage == stage]
    if not intents:  # no curated template covers the stage: intents come from the routed sources' registry-declared search_intent_support
        supported = sorted({value for s in sources for value in s.search_intent_support})
        intents = [SearchIntent(intent_id=value, intent=value.replace("_", " "), evidence_goal=str(stage), evidence_roles=tuple(STAGE_GATE_ROLES[stage]),
                                template="{product_territory} " + value.replace("_", " ")) for value in supported]
    preferred = sorted({s.source_class for s in sources if s.source_class})
    disallowed = {s.source_class for s in snapshot.source_roles if s.source_class and s.source_class not in preferred}
    if stage != ResearchStage.SUPPLY:
        disallowed.add("supplier_listing")  # supply evidence never answers demand or friction gaps
    days = [FRESHNESS_DAYS[s.freshness_policy] for s in sources if s.freshness_policy in FRESHNESS_DAYS]
    gates = {gate.name: gate for gate in snapshot.scoring_policy.hard_gates}
    minimum = {ResearchStage.FIELD_EVIDENCE: gates["source_diversity"].minimum, ResearchStage.PRODUCT_REALITY: gates["competitor_review_analysis"].minimum, ResearchStage.SUPPLY: 2}[stage]
    success = {
        ResearchStage.FIELD_EVIDENCE: f"{gates['independent_complaints'].minimum} independent complaint observations and {gates['workaround_examples'].minimum} workaround examples across {gates['source_diversity'].minimum} source classes",
        ResearchStage.PRODUCT_REALITY: f"{gates['competitor_review_analysis'].minimum} products or substitute categories compared and {gates['current_price_checks'].minimum} current price checks",
        ResearchStage.SUPPLY: "two suppliers with unit price, MOQ, and lead time observed",
    }[stage]
    falsification = {
        ResearchStage.FIELD_EVIDENCE: "independent communities do not report the friction as recurring",
        ResearchStage.PRODUCT_REALITY: "a dominant incumbent already removes the friction at a lower price",
        ResearchStage.SUPPLY: "no supplier meets the target landed cost at a workable MOQ",
    }[stage]
    objective = {
        ResearchStage.FIELD_EVIDENCE: "find first-person field evidence for the live hypotheses",
        ResearchStage.PRODUCT_REALITY: "map current products, alternatives, reviews, prices, and saturation",
        ResearchStage.SUPPLY: "find supply feasibility: supplier, unit price, MOQ, lead time, customization, shipping",
    }[stage]
    return ResearchDirectiveV1(
        directive_id=derived_id("rd-", str(stage), *(g.gap_id for g in gaps), *(h.hypothesis_id for h in hypotheses)), stage=stage, objective=objective,
        hypothesis_ids=tuple(h.hypothesis_id for h in hypotheses), evidence_gaps=gaps,
        search_intents=tuple(intents),
        preferred_source_roles=tuple(preferred), disallowed_source_roles=tuple(sorted(disallowed)),
        freshness_requirement=FreshnessRequirement(max_age_days=min(days) if days else None, policy_ref="strictest-routed-source"),
        geography=geography, language=language, minimum_independent_sources=int(minimum), success_condition=success, falsification_condition=falsification,
        budget=ResearchBudget(max_queries=6 * max(1, len(intents)), max_sources=4 * max(1, len(sources)), max_observations=20 * max(1, len(intents))),
        routed_source_ids=tuple(sorted(s.source_id for s in sources)), registry_snapshot=snapshot_ref(snapshot))


#: ADR-069 field-aware mapping: what an agreement between a candidate dimension and a registry field is worth. An exact friction-family /
#: territory id agreement outweighs any amount of shared vocabulary; phrase dimensions count shared tokens.
ID_WEIGHT, SEED_TERRITORY_WEIGHT, ACTIVITY_WEIGHT, TASK_WEIGHT, CONTEXT_WEIGHT, PREDICATE_WEIGHT, SEED_FAMILY_WEIGHT = 8, 6, 2, 2, 1, 1, 3


def structured_strength(candidate: SemanticCandidate, fields: dict[str, str], section: str = "") -> int:
    """Deterministic field-to-field agreement between one hypothesis's candidates and one registry record. A friction PRIMITIVE or
    a TERRITORY is its id: agreement on the id is decisive. A NICHE SEED is an archetype x activity row — the same friction family
    repeats across hundreds of activities — so a seed counts only when its activity, task or context ALSO agrees with the candidate
    (when the candidate states any); the shared family then adds to it, it never carries a foreign activity on its own."""
    def shared(value: str | None, name: str) -> int:
        return len(tokens(value) & tokens(fields[name])) if value and fields.get(name) else 0

    phrase = ACTIVITY_WEIGHT * shared(candidate.activity, "activity") + TASK_WEIGHT * shared(candidate.task, "task") + CONTEXT_WEIGHT * shared(candidate.context, "context")
    ids = ((ID_WEIGHT if fields.get("friction_family") in candidate.friction_families else 0)
           + (ID_WEIGHT if fields.get("territory") in candidate.product_territories else 0)
           + (SEED_TERRITORY_WEIGHT if fields.get("product_territory") in candidate.product_territories else 0))
    predicates = 0
    if candidate.predicates and fields.get("shared_predicates"):
        predicates = PREDICATE_WEIGHT * len(set(candidate.predicates) & set(re.split(r"[^a-z0-9_]+", fields["shared_predicates"].lower())))
    if section == "niche_seeds":
        if (candidate.activity or candidate.task or candidate.context) and not phrase:
            return 0
        return phrase + (SEED_FAMILY_WEIGHT if ids else 0) + (predicates if phrase else 0)
    return ids + phrase + (predicates if ids or phrase else 0)


def derive_registry_coordinates(snapshot, request):
    """Priors are coordinates for the live hypotheses (lexical overlap with niche seeds, friction primitives, and territories);
    redundancy groups share a normalised statement; unsupported hypotheses have no knowledge support. Nothing here is evidence."""
    from trail_signal.contexts.planning.public.contracts import RegistryProjectionV1

    refuse_prior_citations(snapshot, request.admitted_evidence_ids)
    priors: list[PriorCoordinates] = []
    for hypothesis in request.hypotheses:
        words = tokens(hypothesis.statement)
        candidate = hypothesis.semantic if hypothesis.semantic is not None and not hypothesis.semantic.empty() else None
        scored: list[tuple[int, str, str, str, str]] = []
        structured: list[tuple[int, str, str, str, str]] = []
        for section, section_priors in prior_sections(snapshot):
            if section not in {"friction_primitives", "product_territories", "niche_seeds"}:
                continue
            for prior in section_priors:
                label = next((f.value for f in prior.fields if f.name in {"friction_family", "territory", "activity"}), prior.record_id)
                if candidate is not None:
                    strength = structured_strength(candidate, {f.name: f.value for f in prior.fields}, section)
                    if strength:
                        structured.append((strength, prior.record_id, prior.prior_role, label, section))
                text = " ".join(field.value for field in prior.fields)
                overlap = len(words & tokens(text))
                if overlap:
                    scored.append((overlap, prior.record_id, prior.prior_role, label, section))
        # ADR-069: structured agreement decides when the caller supplied candidates AND any record agrees; otherwise the lexical
        # mapping — unchanged, byte for byte — remains the compatibility path. The coordinate records which path produced it.
        path, ranked = ("structured", structured) if structured else ("lexical", scored)
        for overlap, record_id, role, label, section in sorted(ranked, key=lambda x: (-x[0], x[1]))[: request.max_priors_per_hypothesis]:
            fields = (SnapshotField(name="label", value=label), SnapshotField(name="overlap", value=str(overlap)), SnapshotField(name="section", value=section))
            priors.append(PriorCoordinates(registry_record_id=record_id, prior_role=role, hypothesis_ids=(hypothesis.hypothesis_id,),
                                         coordinates=fields + ((SnapshotField(name="path", value="structured"),) if path == "structured" else ())))
    groups: dict[str, list[str]] = {}
    for hypothesis in request.hypotheses:
        groups.setdefault(normalise(hypothesis.statement), []).append(hypothesis.hypothesis_id)
    redundancy = tuple(tuple(sorted(ids)) for _, ids in sorted(groups.items()) if len(ids) > 1)
    unsupported = tuple(h.hypothesis_id for h in request.hypotheses if h.knowledge_support_count == 0)
    return RegistryProjectionV1(registry_snapshot=snapshot_ref(snapshot), priors=tuple(priors), redundancy_groups=redundancy, unsupported_hypothesis_ids=unsupported)


def map_product_territories(snapshot, request, *, max_per_hypothesis: int = 3):
    """Physical jobs and mechanisms from the knowledge side map onto product_territories priors by lexical overlap; the
    PRODUCT_REALITY_CHECK directive is compiled through the gap compiler so the harness maps incumbents, not demand."""
    from trail_signal.contexts.planning.public.contracts import ProductTerritoryProjectionV1

    refuse_prior_citations(snapshot, request.admitted_evidence_ids)
    hypotheses, physical_jobs, geography, language = request.hypotheses, request.physical_jobs, request.geography, request.language
    territories: list[PriorCoordinates] = []
    for hypothesis in hypotheses:
        jobs = [j for j in physical_jobs if j.hypothesis_id == hypothesis.hypothesis_id]
        words = tokens(" ".join([hypothesis.statement, *(f"{j.job} {j.mechanism}" for j in jobs)]))
        candidate = hypothesis.semantic if hypothesis.semantic is not None and not hypothesis.semantic.empty() else None
        scored: list[tuple[int, str, str]] = []
        structured: list[tuple[int, str, str]] = []
        for prior in snapshot.product_territories:
            fields = {f.name: f.value for f in prior.fields}
            if candidate is not None:
                strength = structured_strength(candidate, fields)
                if strength:
                    structured.append((strength, prior.record_id, fields.get("territory", prior.record_id)))
            overlap = len(words & (tokens(f"{fields.get('territory', '')} {fields.get('definition', '')} {fields.get('preferred_first_product', '')}") | set(fields.get("territory", "").split("_"))))
            if overlap:
                scored.append((overlap, prior.record_id, fields.get("territory", prior.record_id)))
        path, ranked = ("structured", structured) if structured else ("lexical", scored)
        for overlap, record_id, name in sorted(ranked, key=lambda x: (-x[0], x[1]))[:max_per_hypothesis]:
            fields_out = (SnapshotField(name="territory", value=name), SnapshotField(name="overlap", value=str(overlap)))
            territories.append(PriorCoordinates(registry_record_id=record_id, prior_role="product_territory", hypothesis_ids=(hypothesis.hypothesis_id,),
                                              coordinates=fields_out + ((SnapshotField(name="path", value="structured"),) if path == "structured" else ())))
    directive = compile_research_directive(snapshot, stage=ResearchStage.PRODUCT_REALITY, gaps=(), hypotheses=hypotheses, geography=geography, language=language)
    return ProductTerritoryProjectionV1(registry_snapshot=snapshot_ref(snapshot), territories=tuple(territories), research_directive=directive)
