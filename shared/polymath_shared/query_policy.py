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
# v2 (GLINER-QUERY-VOCAB-v2, dev-selected 2026-08-16): measured label
# competition inside GLiNER suppresses marginal spans when aliases
# compete flat with core names (dev probes 2026-08-16: 25-label flat
# set lost "remediation plan" and the close-sequence Process spans;
# even 8 additives diluted scores broadly). v2 therefore queries the
# model TWICE at the policy level — the identity pass unchanged (v1
# byte-compatible) plus an enriched pass — and unions the proposals
# deterministically (higher raw score wins; identity pass preferred on
# ties). Single-label-per-request regime for rescue (the only regime
# where bare-NP firing was observed).
QUERY_POLICY_V1 = "semantic-query-policy-v1"
QUERY_POLICY_V2 = "semantic-query-policy-v2"
QUERY_POLICY_V3 = "semantic-query-policy-v3"
QUERY_POLICY_VERSION = QUERY_POLICY_V1  # back-compat symbol (prefer active_policy_version)

# SCIENTIFIC-KAG-V1 (phase 1): the proven 12-label identity pass keeps
# its measured budget; scientific-research labels fire in a dedicated
# second pass. Union across passes is deterministic (identity pass
# preferred on ties), exactly like v2's alias passes.
SCIENTIFIC_PASS_LABELS: tuple[str, ...] = tuple(
    t.value for t in CoreType
    if t.value not in {
        "Person", "Organization", "Location", "Product", "Technology",
        "Concept", "Method", "Event", "Document", "Process",
        "Measurement", "TimeReference",
    }
)

PROVIDER_ALIASES_V2: dict[str, tuple[str, ...]] = {
    "Organization": ("Company", "Corporation"),
    "Product": ("Software platform",),
    "Technology": ("Software system", "Technical tool"),
    "Method": ("Implementation method", "Technique", "Procedure"),
    "Process": ("Operation", "Workflow"),
    "Concept": ("Technical concept", "Principle"),
    "Event": ("Incident",),
    "Measurement": ("Metric",),
}


def active_policy_version() -> str:
    import os

    return os.environ.get("POLYMATH_QUERY_POLICY", QUERY_POLICY_V1)


def provider_alias_map() -> dict[str, str]:
    """alias -> canonical (v2 data; empty under v1)."""
    if active_policy_version() == QUERY_POLICY_V1:
        return {}
    return {a: c for c, aliases in PROVIDER_ALIASES_V2.items() for a in aliases}


def provider_passes() -> list[tuple[str, ...]]:
    """Query passes for entity discovery. v1: one identity pass
    (byte-identical baseline). v2: identity pass + enriched alias pass.
    v3 (scientific): legacy identity pass + dedicated scientific pass."""
    core = tuple(CORE_LABELS)
    if active_policy_version() == QUERY_POLICY_V1:
        return [core]
    if active_policy_version() == QUERY_POLICY_V3:
        legacy = tuple(t.value for t in CoreType)[:12]
        return [legacy, core, SCIENTIFIC_PASS_LABELS]
    enriched = tuple(dict.fromkeys(
        [label for canonical in CORE_LABELS
         for label in (canonical,) + PROVIDER_ALIASES_V2.get(canonical, ())]))
    return [core, enriched]


def query_labels_for(core_type: str) -> tuple[str, ...]:
    """Canonical type -> ordered provider-facing query labels (the
    per-alias single-label regime for rescue queries)."""
    if active_policy_version() == QUERY_POLICY_V1:
        return (core_type,)
    return (core_type,) + PROVIDER_ALIASES_V2.get(core_type, ())


def canonical_of(raw_label: str) -> str | None:
    """Raw provider label -> canonical Polymath core type (or None).

    Core names map to themselves; v2 aliases map through the alias
    table; domain-module labels map through the module table. Unknown
    labels are rejected loudly downstream — never silently coerced."""
    if raw_label in _CORE_LABEL_SET:
        return raw_label
    alias_map = provider_alias_map()
    if raw_label in alias_map:
        return alias_map[raw_label]
    for module in MODULES.values():
        core = module.labels.get(raw_label)
        if core is not None:
            return core.value
    return None


def policy_identity() -> dict:
    """The policy's contribution to the extraction contract identity."""
    version = active_policy_version()
    aliases = PROVIDER_ALIASES_V2 if version == QUERY_POLICY_V2 else {}
    return {
        "query_policy_version": version,
        "aliases": {k: list(v) for k, v in sorted(aliases.items())},
        "passes": ("identity+enriched" if version == QUERY_POLICY_V2
                   else "legacy+core+scientific" if version == QUERY_POLICY_V3
                   else "identity"),
    }
