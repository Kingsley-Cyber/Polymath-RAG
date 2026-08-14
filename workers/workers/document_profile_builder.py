"""Deterministic document retrieval-profile builder (Phase G1).

Bottom-up, no LLM, no model call:

    child chunks -> parent summaries -> document aggregation
    -> RetrievalProfile

Inputs: filename, ingestion profile, parent summaries, top entities,
predicate distribution, and the heading tree implied by chunk text.
Output: the document's SEMANTIC ADDRESS — why this whole source should
be considered for a query. It is not a chunk description; the parent
summaries own topic localization and the children own exact evidence.

The profile contract (`document-summary-v1`) is versioned: a neural
summarizer may later produce richer text behind the same JSON shape —
that is a contract addition, never a silent swap.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from polymath_shared.contracts import RetrievalProfile
from workers.summarizer import summarize

SUMMARY_CONTRACT = "document-summary-v1"

MODULE_DOMAINS: dict[str, list[str]] = {
    "software_tech": ["software_engineering", "systems_design"],
    "psych_cognition": ["cognitive_science", "learning_science"],
    "facs_body": ["facial_action_coding", "biomechanics"],
    "commerce_marketing": ["marketing", "consumer_behavior"],
    "media_film": ["film_media", "generative_media"],
    "academic": ["research_methodology", "scholarly_communication"],
}

PREDICATE_METHOD_PHRASES: dict[str, str] = {
    "founded": "founding and establishing organizations",
    "created": "creating artifacts",
    "developed": "developing technology",
    "uses": "applying tools and frameworks",
    "implemented_with": "implementation technology selection",
    "depends_on": "dependency analysis",
    "causes": "causal analysis",
    "enables": "capability enablement",
    "part_of": "composition and modular analysis",
    "is_a": "classification and typing",
    "has_role": "role and leadership analysis",
    "employs": "employment and staffing",
    "acquired": "acquisition analysis",
    "transforms_into": "transformation and conversion",
    "measured_by": "quantitative evaluation",
    "stated_in": "provenance and citation tracking",
    "influences": "influence analysis",
    "located_in": "geographic grounding",
}

PREDICATE_PROBLEMS: dict[str, str] = {
    "founded": "origin tracking for organizations",
    "depends_on": "dependency and requirement modeling",
    "causes": "root-cause attribution",
    "part_of": "structure decomposition",
    "is_a": "ontology and taxonomy construction",
    "uses": "technology selection",
    "measured_by": "evaluation and benchmarking",
    "stated_in": "provenance and auditability",
    "associated_with": "graph pollution control",
}


def _top(items: Counter, cap: int) -> list[str]:
    return [item for item, _ in items.most_common(cap)]


def build_profile(
    *,
    doc_id: str,
    source_name: str,
    ingestion_profile: dict,
    parent_chunks: list[dict],
    entities: list[tuple[str, str]],
    predicate_counts: list[tuple[str, int]],
) -> RetrievalProfile:
    """Pure function: same inputs, same profile, byte for byte."""
    parent_ids = [c["chunk_id"] for c in parent_chunks]
    parent_texts = [c["summary"] or c["text"] for c in parent_chunks]
    joined = "\n".join(parent_texts)

    modules = ingestion_profile.get("active_modules", []) or []
    primary = [domain for m in modules for domain in MODULE_DOMAINS.get(m, [m])]

    secondary: list[str] = []
    for other_id, domains in MODULE_DOMAINS.items():
        if other_id in modules:
            continue
        for domain in domains:
            if domain and domain.split("_")[0] in joined.lower():
                secondary.append(domain)
    secondary = sorted(set(secondary))

    entity_counter = Counter()
    for surface, _core in entities:
        entity_counter[surface.lower()] += 1
    core_concepts = _top(entity_counter, 10)

    pred_counter = Counter(dict(predicate_counts))
    methods = [
        PREDICATE_METHOD_PHRASES.get(pred, pred.replace("_", " "))
        for pred, _ in pred_counter.most_common(6)
    ]
    problems = [
        PREDICATE_PROBLEMS.get(pred, f"{pred.replace('_', ' ')} modeling")
        for pred, _ in pred_counter.most_common(6)
    ]

    use_for: list[str] = []
    for method in methods[:4]:
        use_for.append(f"how to {method}")
    for concept in core_concepts[:4]:
        use_for.append(f"questions about {concept}")

    connects = [d for d in primary] + secondary
    for module, domains in MODULE_DOMAINS.items():
        if any(kw in joined.lower() for kw in [module.replace("_", " ").split()[0]]):
            if domains and domains[0] not in connects:
                connects.append(domains[0])

    semantic_summary = summarize(joined, max_sentences=5, max_chars=1100)

    return RetrievalProfile(
        document_id=doc_id,
        semantic_summary=semantic_summary,
        primary_domains=primary,
        secondary_domains=secondary,
        core_concepts=core_concepts,
        methods=methods,
        problems_addressed=problems,
        use_for_questions_about=use_for[:8],
        connects_to_domains=connects[:8],
        parent_ids=parent_ids,
        source_parent_count=len(parent_ids),
        summarized_parent_count=len(parent_ids),
        coverage=1.0,
        summary_contract=SUMMARY_CONTRACT,
    )
