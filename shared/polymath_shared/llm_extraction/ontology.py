"""The relation ontology — 17 canonical predicates + RELATED_TO.

Owner-supplied (2026-08-29). The LLM must PICK from this enum; the gate
normalizes what it emits (exact → alias → RELATED_TO as the recorded
last resort). This is the canonical vocabulary for LLM-era relation
evidence. The frozen predicate compiler remains the admission authority —
the ontology labels the proposal, admission still decides.

RELATED_TO is last resort and should stay rare; the gate counts every
fallback so vocabulary drift is visible, never silent.
"""
from __future__ import annotations

from polymath_shared.llm_extraction.contract import RelationProposal

# (id, definition) — definitions are the owner's phrasing, verbatim.
RELATION_ONTOLOGY: dict[str, str] = {
    "IS_A": "X is a kind or instance of Y.",
    "PART_OF": "X is a component/piece of whole Y, not a type of it.",
    "HAS_PROPERTY": "X has attribute, state, or ability Y.",
    "SAME_AS": "X and Y are the same thing under different names.",
    "USES": "X employs Y but could still function without it.",
    "REQUIRES": "X cannot exist or function at all without Y.",
    "PRODUCES": "X creates Y as a new output that didn't exist before.",
    "CAUSES": "X directly brings about a change in existing Y.",
    "REGULATES": "X continuously controls the level/behavior of Y over time.",
    "CORRELATES_WITH": "X and Y vary together, neither claimed to cause the other.",
    "CONSTRAINED_BY": "Y limits or bounds X, without creating or controlling it.",
    "PRECEDES": "X comes before Y in time/order, with no causal claim.",
    "MEASURES": "X assesses, quantifies, or evaluates Y.",
    "LOCATED_IN": "X sits inside the spatial/conceptual boundary of Y.",
    "ALTERNATIVE_TO": "X can replace Y for the same purpose.",
    "OPPOSES": "X contradicts or counteracts Y (antithetical, not just different).",
    "ACTS_ON": "X performs an action affecting Y; verb in the note.",
    "RELATED_TO": "X connects to Y but none above fits (last resort, keep rare).",
}

LAST_RESORT = "RELATED_TO"

# Deterministic normalization for off-enum emissions. First hit wins;
# anything unmatched falls to RELATED_TO and is counted as a fallback.
PREDICATE_ALIASES: dict[str, str] = {
    "kind_of": "IS_A", "type_of": "IS_A", "instance_of": "IS_A",
    "a_kind_of": "IS_A", "is_a_kind_of": "IS_A",
    "component_of": "PART_OF", "member_of": "PART_OF", "part": "PART_OF",
    "has": "HAS_PROPERTY", "has_attribute": "HAS_PROPERTY",
    "has_state": "HAS_PROPERTY", "has_ability": "HAS_PROPERTY",
    "same": "SAME_AS", "aka": "SAME_AS", "also_known_as": "SAME_AS",
    "alias_of": "SAME_AS", "employs": "USES", "leverages": "USES",
    "utilizes": "USES", "depends_on": "REQUIRES", "needs": "REQUIRES",
    "necessitates": "REQUIRES", "creates": "PRODUCES", "generates": "PRODUCES",
    "yields": "PRODUCES", "emits": "PRODUCES",
    "leads_to": "CAUSES", "results_in": "CAUSES", "triggers": "CAUSES",
    "controls": "REGULATES", "modulates": "REGULATES", "governs": "REGULATES",
    "varies_with": "CORRELATES_WITH", "associated_with": "CORRELATES_WITH",
    "correlated_with": "CORRELATES_WITH",
    "limited_by": "CONSTRAINED_BY", "bounded_by": "CONSTRAINED_BY",
    "restricted_by": "CONSTRAINED_BY", "limited": "CONSTRAINED_BY",
    "comes_before": "PRECEDES", "precedes_in_time": "PRECEDES",
    "before": "PRECEDES", "follows": "PRECEDES",
    "quantifies": "MEASURES", "evaluates": "MEASURES", "assesses": "MEASURES",
    "monitors": "MEASURES",
    "inside": "LOCATED_IN", "within": "LOCATED_IN", "located": "LOCATED_IN",
    "housed_in": "LOCATED_IN",
    "replaces": "ALTERNATIVE_TO", "substitute_for": "ALTERNATIVE_TO",
    "competes_with": "ALTERNATIVE_TO",
    "contradicts": "OPPOSES", "counteracts": "OPPOSES", "opposed_to": "OPPOSES",
    "conflicts_with": "OPPOSES", "mitigates": "OPPOSES",
    "acts": "ACTS_ON", "performs": "ACTS_ON", "applies_to": "ACTS_ON",
    "affects": "ACTS_ON", "executes": "ACTS_ON",
    "reported": "ACTS_ON", "reports": "ACTS_ON", "stated": "ACTS_ON",
    "announced": "ACTS_ON", "disclosed": "ACTS_ON", "observed_on": "ACTS_ON",
    "connects_to": "RELATED_TO", "relates_to": "RELATED_TO",
    "mentions": "RELATED_TO", "associated": "CORRELATES_WITH",
}


def normalize_predicate(raw: str) -> tuple[str, str]:
    """Route an emitted predicate onto the ontology.

    Returns (predicate, method): 'enum' (exact), 'alias' (alias table),
    'related_fallback' (last resort — counted by the caller).
    """
    key = (raw or "").strip()
    up = key.upper()
    if up in RELATION_ONTOLOGY:
        return up, "enum"
    hit = PREDICATE_ALIASES.get(key.lower().replace(" ", "_"))
    if hit:
        return hit, "alias"
    # substring pass for phrasal emissions ("is a kind of", "part of the")
    low = key.lower()
    for alias, target in PREDICATE_ALIASES.items():
        if alias in low:
            return target, "alias"
    return LAST_RESORT, "related_fallback"


def prompt_block() -> str:
    """The prompt fragment that teaches the enum (id + definition)."""
    lines = [f"{pid}: {defn}" for pid, defn in RELATION_ONTOLOGY.items()]
    return "\n".join(lines)


def check_relation(rel: RelationProposal) -> tuple[str, str]:
    """Gate helper: (canonical_predicate, method) for one proposal."""
    return normalize_predicate(rel.predicate)
