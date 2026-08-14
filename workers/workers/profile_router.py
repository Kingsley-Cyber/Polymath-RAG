"""Deterministic document-profile router (docx §2, §3.3).

A document gets a profile: a small set of active domain modules plus the
12-type core backbone. The profile decides which GLiNER label set each
chunk receives. Routing is pure: filename/path hints + keyword priors,
no model call. Mixed-domain chunks are capped by the per-call label
budget so pass 1 never exceeds GLiNER's practical label count.

Label hygiene is a precision decision (docx §3.1): small, mutually
exclusive, internally coherent label sets produce cleaner span proposals.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from polymath_shared.contracts import CoreType, DocumentProfile

CORE_LABELS: list[str] = [t.value for t in CoreType]

MAX_LABELS_PER_CALL = 50  # uni-encoder budget (docx §3.1)


@dataclass(frozen=True)
class DomainModule:
    module_id: str
    version: str
    labels: dict[str, CoreType]  # domain label -> core type (mandatory mapping)
    path_hints: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    extra_module_cap: int = 1  # at most one extra module fires on a chunk


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

_EXTRA_MODULE_PROBES: list[tuple[str, str]] = [
    ("facs_body", r"\bAU\d{1,2}\b"),
    ("software_tech", r"\b[A-Z]{2,8}-\d{3,4}\b"),  # CVE-ish / ISO-ish identifiers
]


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(1 for kw in keywords if kw in lowered)


def route_document(source_name: str, sample_text: str) -> DocumentProfile:
    """Deterministic profile for one document. `sample_text` is the first
    few thousand chars; only keyword priors see it, never a model."""
    lowered_path = source_name.lower()
    active: list[str] = []
    module_versions: dict[str, str] = {}

    for module in MODULES.values():
        if any(hint in lowered_path for hint in module.path_hints):
            active.append(module.module_id)
            module_versions[module.module_id] = module.version

    if not active:
        scored = sorted(
            MODULES.values(),
            key=lambda m: (-_keyword_hits(sample_text[:4000], m.keywords), m.module_id),
        )
        if scored and _keyword_hits(sample_text[:4000], scored[0].keywords) > 0:
            active.append(scored[0].module_id)
            module_versions[scored[0].module_id] = scored[0].version

    profile_id = ",".join(sorted(active)) or "core"
    labels = list(CORE_LABELS)
    if active:
        first = MODULES[active[0]]
        labels.extend(first.labels.keys())
        if len(active) > 1:
            second = MODULES[active[1]]
            labels.extend(second.labels.keys())

    return DocumentProfile(
        profile_id=profile_id,
        active_modules=active,
        label_set=labels[:MAX_LABELS_PER_CALL],
        core_labels=list(CoreType),
    )


def chunk_extra_module(text: str, profile: DocumentProfile) -> str | None:
    """At most one additional module may fire per chunk on a lexical prior
    (docx §3.3). Deterministic: probes are regexes, order is fixed."""
    for module_id, pattern in _EXTRA_MODULE_PROBES:
        if module_id in profile.active_modules:
            continue
        if re.search(pattern, text):
            return module_id
    return None


def chunk_label_set(text: str, profile: DocumentProfile) -> list[str]:
    """Final pass-1 label set for one chunk: profile labels + at most one
    extra module from a lexical prior, capped to the per-call budget."""
    extra = chunk_extra_module(text, profile)
    if not extra:
        return profile.label_set
    merged = list(profile.label_set) + list(MODULES[extra].labels.keys())
    return merged[:MAX_LABELS_PER_CALL]
