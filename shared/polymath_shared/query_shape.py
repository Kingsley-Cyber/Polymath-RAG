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
    # "what are all …" only. A bare "what are the …" is the shape of
    # ordinary comparison questions ("what are the pros and cons of X",
    # "what are the differences between X and Y", "what are the
    # tradeoffs …"), which want a tight answer, not a 24-chunk sweep.
    # The structure-noun branch below still catches "what are the
    # domains and subdomains of X".
    r"what are all\b|"
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


#: DOCUMENT-REGION-V1 escape hatch. Questions ABOUT the document rather
#: than about its subject legitimately want the regions that default
#: retrieval demotes. Deliberately tiny and deterministic — this is not
#: a semantic intent classifier, just the minimum signal needed to stop
#: demotion from making front matter unreachable.
_METADATA_RE = re.compile(
    r"\b("
    r"who (wrote|authored|is the author)|about the author|"
    r"who is the (author|editor|publisher)|"
    r"what does (this|the) (book|document|corpus) cover|"
    r"table of contents|what chapters|list the chapters|"
    r"the (preface|foreword|dedication|acknowledg(e)?ments?)|"
    r"copyright|isbn|publisher|"
    r"(show|what is in) the (bibliography|index|references)"
    r")",
    re.IGNORECASE,
)


def is_document_metadata_query(query: str) -> bool:
    """True for questions about the DOCUMENT (authorship, front matter,
    contents listing) rather than its subject matter."""
    return bool(_METADATA_RE.search(query or ""))


def plan_for_query(query: str, plan):
    """Pick the retrieval profile for this question.

    Breadth by default; depth for completeness questions; and region
    demotion is lifted entirely for document-metadata questions so
    front matter stays reachable when it IS the answer.
    """
    if is_enumeration_query(query):
        plan = depth_plan(plan)
    if is_document_metadata_query(query):
        plan = replace(plan, demote_noisy_regions=False)
    return plan
