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

import re

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
    # Phrasal pass ("is a kind of", "part of the"): TOKEN-BOUNDED so "has"
    # cannot fire inside "has_no_effect_on", "part" inside "counterpart",
    # "before" inside "not before". Longest alias first, then table order.
    low = key.lower().replace("_", " ")
    for pattern, target in _ALIAS_PATTERNS:
        if pattern.search(low):
            return target, "alias"
    return LAST_RESORT, "related_fallback"


def _alias_patterns() -> list[tuple[re.Pattern[str], str]]:
    items = list(PREDICATE_ALIASES.items())
    # stable sort: longest alias wins ties by insertion order
    items.sort(key=lambda kv: -len(kv[0]))
    return [(re.compile(r"(?<![a-z0-9])" + re.escape(alias.replace("_", " "))
                        + r"(?![a-z0-9])"), target)
            for alias, target in items]


_ALIAS_PATTERNS = _alias_patterns()


# Contrastive disambiguation for adjacent enum slots — measured error
# classes from the 2026-08-30 production receipts (PRODUCES misfires,
# "consists of" landing on HAS_PROPERTY, RELATED_TO fallback rate 31% on
# the 4B / 4% on the 397B). Contrasts teach CHOICE, not vocabulary.
PROMPT_CONTRASTS: tuple[str, ...] = (
    "CONSTRAINED_BY, never PRODUCES: applying/adding/imposing a rule or "
    "constraint on X (e.g. 'apply NOT NULL on the column') means X "
    "CONSTRAINED_BY the constraint — nothing new is created.",
    "PART_OF, not HAS_PROPERTY: 'consists of / composed of / made up of / "
    "contains' expresses composition — the parts are PART_OF the whole.",
    "PRODUCES means creates a NEW output that did not exist before "
    "('generates reports', 'produces alerts'). Supplying, offering or "
    "hosting something existing is USES or ACTS_ON.",
    "OPPOSES is correct for explicit contrast or counteraction: 'not "
    "responsible for', 'not the root cause', 'prevents', 'counteracts'.",
    "RELATED_TO is the LAST RESORT ONLY — if any other id above fits "
    "even loosely, use that id instead.",
)


def prompt_block() -> str:
    """The prompt fragment that teaches the enum (id + definition + the
    measured contrastive disambiguations)."""
    lines = [f"{pid}: {defn}" for pid, defn in RELATION_ONTOLOGY.items()]
    lines.append("")
    lines.append("Disambiguation rules (follow exactly):")
    lines.extend(f"- {c}" for c in PROMPT_CONTRASTS)
    return "\n".join(lines)


def check_relation(rel: RelationProposal) -> tuple[str, str]:
    """Gate helper: (canonical_predicate, method) for one proposal."""
    return normalize_predicate(rel.predicate)
