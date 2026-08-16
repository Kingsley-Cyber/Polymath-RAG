"""Semantic query policy (semantic-query-policy-v1).

Temporal-durability boundary: canonical Polymath types are durable
semantics; model-facing label vocabulary is replaceable configuration.
Every GLiNER query — discovery pass 1 and every rescue query — resolves
its labels THROUGH this versioned policy, and every raw provider label
is preserved alongside its canonical mapping. The compiler, predicate
rules, and canonicalizer never see provider aliases.

    canonical type
        ↓  query_labels_for()
    provider-facing GLiNER labels
        ↓  GLiNER (pinned model, frozen threshold)
    raw result (raw_label preserved)
        ↓  canonical_of()
    canonical Polymath type

Alias vocabularies (e.g. Organization -> Company/Corporation) are
versioned POLICY DATA introduced through a named evidence gate
(GLINER-QUERY-VOCAB-vN), never a code branch and never a canonical
ontology change. v1 is deliberately identity: a canonical type queries
under its own name only — byte-identical with the qualified baseline.

The domain-module discovery vocabulary (which labels pass 1 may bring
per document profile) lives here too: it is provider-facing query
configuration, not canonical semantics.
"""
from __future__ import annotations

from dataclasses import dataclass

from polymath_shared.contracts import CoreType

QUERY_POLICY_VERSION = "semantic-query-policy-v1"

CORE_LABELS: list[str] = [t.value for t in CoreType]
_CORE_LABEL_SET = frozenset(CORE_LABELS)


@dataclass(frozen=True)
class DomainModule:
    module_id: str
    version: str
    labels: dict[str, CoreType]  # provider-facing label -> canonical core type
    path_hints: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()


MODULES: dict[str, DomainModule] = {
    m.module_id: m
    for m in [
        DomainModule(
            "software_tech", "1.0.0",
            {"Library": CoreType.PRODUCT, "Framework": CoreType.PRODUCT, "API": CoreType.TECHNOLOGY,
             "Vulnerability": CoreType.CONCEPT, "AttackTechnique": CoreType.METHOD,
             "Model": CoreType.PRODUCT, "Dataset": CoreType.DOCUMENT, "ProgrammingLanguage": CoreType.TECHNOLOGY},
            ("github", "src", "software", "tech"), ("kubernetes", "docker", "api", "software", "compiler"),
        ),
        DomainModule(
            "psych_cognition", "1.0.0",
            {"CognitiveBias": CoreType.CONCEPT, "MetacognitiveStrategy": CoreType.METHOD,
             "EmotionCategory": CoreType.CONCEPT, "VADDimension": CoreType.MEASUREMENT},
            ("psych", "cognition", "mental"), ("metacognition", "cognitive", "emotion", "valence"),
        ),
        DomainModule(
            "facs_body", "1.0.0",
            {"FacialActionUnit": CoreType.CONCEPT, "MuscleAction": CoreType.CONCEPT,
             "FacialExpression": CoreType.CONCEPT, "BodyMovement": CoreType.PROCESS,
             "JointAngle": CoreType.MEASUREMENT},
            ("facs", "body", "movement", "motion"), ("action unit", "facial", "biomechanics", "joint"),
        ),
        DomainModule(
            "commerce_marketing", "1.0.0",
            {"Brand": CoreType.ORGANIZATION, "Campaign": CoreType.EVENT,
             "MarketingTechnique": CoreType.METHOD, "Metric": CoreType.MEASUREMENT,
             "ConsumerBehavior": CoreType.PROCESS},
            ("marketing", "brand", "campaign"), ("marketing", "brand", "campaign", "conversion"),
        ),
        DomainModule(
            "media_film", "1.0.0",
            {"Film": CoreType.DOCUMENT, "Shot": CoreType.CONCEPT,
             "CinematographyTechnique": CoreType.METHOD, "AnimationTechnique": CoreType.METHOD,
             "PromptTechnique": CoreType.METHOD},
            ("film", "video", "media", "animation"), ("cinematography", "animation", "prompt", "veo"),
        ),
        DomainModule(
            "academic", "1.0.0",
            {"Theory": CoreType.CONCEPT, "Finding": CoreType.CONCEPT,
             "StudyDesign": CoreType.METHOD, "Citation": CoreType.DOCUMENT},
            ("paper", "academic", "arxiv"), ("paper", "study", "experiment", "finding"),
        ),
    ]
}

# Provider-facing alias vocabulary per canonical type. v1 = identity.
# Any alias here MUST arrive through a versioned policy gate with probe
# evidence (see docs/wiki/experiments/) and bumps QUERY_POLICY_VERSION.
PROVIDER_ALIASES: dict[str, tuple[str, ...]] = {}


def query_labels_for(core_type: str) -> tuple[str, ...]:
    """Canonical type -> ordered provider-facing query labels."""
    aliases = PROVIDER_ALIASES.get(core_type)
    if aliases:
        return tuple(aliases)
    return (core_type,)


def canonical_of(raw_label: str) -> str | None:
    """Raw provider label -> canonical Polymath core type (or None).

    Core names map to themselves; domain-module labels map through the
    module table. Unknown labels are rejected loudly downstream — never
    silently coerced."""
    if raw_label in _CORE_LABEL_SET:
        return raw_label
    for module in MODULES.values():
        core = module.labels.get(raw_label)
        if core is not None:
            return core.value
    return None


def policy_identity() -> dict:
    """The policy's contribution to the extraction contract identity."""
    return {
        "query_policy_version": QUERY_POLICY_VERSION,
        "aliases": {k: list(v) for k, v in sorted(PROVIDER_ALIASES.items())},
    }
