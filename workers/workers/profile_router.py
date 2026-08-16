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

# Provider-facing label vocabulary is query-policy configuration
# (semantic-query-policy-v1), not profile semantics: re-exported here
# for existing importers.
from polymath_shared.query_policy import (  # noqa: F401
    CORE_LABELS,
    MODULES,
    DomainModule,
)

MAX_LABELS_PER_CALL = 50  # uni-encoder budget (docx §3.1)

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
