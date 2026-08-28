"""QUERY-SHAPE-V1: deterministic question-shape detection.

The Pass-1 plan is tuned for BREADTH — five documents, two sections
each, three children per section. That is the right shape for "what is
X": spread across sources, take the best-supported answer.

It is the wrong shape for COMPLETENESS. "What are all the domains and
subdomains of CySA+" is answered by one contiguous run inside ONE
document (an objectives map, a procedure, a table). Under the breadth
plan at most six chunks can come from any single document, so the
answer arrives as a fragment no matter how well it ranked. MEASURED
2026-08-27: the objectives map was retrieved, delivered subdomains
1.1-1.5, and the continuation (domains 2/3/4, the very next chunk) was
never admitted.

Detection is DETERMINISTIC and free — no model call, no LLM round trip
(measured: an LLM planning hop costs 1-3 s, while the whole retrieval
including reranking is ~2.6 s). It is deliberately conservative: a
false negative costs the old behaviour, a false positive costs a few
extra chunks of context.
"""
from __future__ import annotations

import re
from dataclasses import replace

#: Enumeration/completeness markers. Anchored on the ASK, not on nouns,
#: so ordinary questions that merely contain "all" ("is all traffic
#: encrypted") do not trip it.
_ENUMERATION_RE = re.compile(
    r"\b("
    r"list (?:all|every|the)|"
    r"what are (?:all|the) |"
    r"name (?:all|every)|"
    r"enumerate|"
    r"all (?:of )?the \w+s\b|"
    r"every \w+\b|"
    r"(?:full|complete|entire) (?:list|set|breakdown)|"
    r"how many \w+"
    r")",
    re.IGNORECASE,
)

#: Structured-content nouns whose answers are inherently contiguous.
#: These raise confidence but are not sufficient alone.
_STRUCTURE_RE = re.compile(
    r"\b(domains?|subdomains?|objectives?|sections?|chapters?|steps?|"
    r"phases?|stages?|requirements?|controls?|categories|"
    r"components?|procedures?)\b",
    re.IGNORECASE,
)


def is_enumeration_query(query: str) -> bool:
    """True when the question asks for a COMPLETE set rather than an
    explanation. Deterministic; no model call."""
    q = (query or "").strip()
    if not q:
        return False
    if _ENUMERATION_RE.search(q):
        return True
    # "domains and subdomains of X" — plural structure nouns joined by
    # "and" read as a completeness ask even without an explicit "all".
    return bool(
        _STRUCTURE_RE.search(q)
        and re.search(r"\b\w+s\s+and\s+\w+s\b", q, re.IGNORECASE)
    )


def depth_plan(plan):
    """The DEPTH profile: same engine, caps re-shaped for completeness.

    Breadth is preserved (max_documents unchanged) — this only stops the
    per-document caps from truncating a contiguous answer, and turns on
    neighbour expansion so a run that crosses a chunk boundary arrives
    whole. Nothing here changes scoring, fusion, or ordering.
    """
    return replace(
        plan,
        max_sections_per_document=4,   # was 2
        max_children_per_section=4,    # was 3
        final_max_children=16,         # was 10
        final_max_total_items=24,      # was 12 (dead code at 10 children)
        neighbor_expansion=1,          # off by default; ±1 chunk here
        neighbor_expansion_max=8,
    )


def plan_for_query(query: str, plan):
    """Pick the retrieval profile for this question. Breadth by default."""
    return depth_plan(plan) if is_enumeration_query(query) else plan
