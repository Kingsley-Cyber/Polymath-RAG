"""QUERY-ROUTER-V1: deterministic query-intent classification.

Routes a user question to the knowledge representation that answers it:
  FACT_QUERY      -> graph + fact evidence
  PROCEDURE_QUERY -> procedure artifacts (steps/tools) + sources
  CONCEPT_QUERY   -> concept artifacts + document context
  POLYMATH_QUERY  -> corpus map expansion + concept lanes + graph

Pure lexicon/pattern rules over the question text — the same discipline
as the document-side classifier. No models, no LLM. Same input always
yields the same route.
"""
from __future__ import annotations

import re
from typing import Optional

ROUTE_FACT = "FACT_QUERY"
ROUTE_PROCEDURE = "PROCEDURE_QUERY"
ROUTE_CONCEPT = "CONCEPT_QUERY"
ROUTE_POLYMATH = "POLYMATH_QUERY"
QUERY_ROUTER_VERSION = "query-router-v1"

_PROCEDURE_PATTERNS = (
    r"\bhow (do|to|can) (i|we|you)\b",
    r"\bsteps? (to|for|of)\b",
    r"\bconfigure|set ?up|install|deploy\b",
    r"\bsop|procedure|workflow|runbook\b",
)
_CONCEPT_PATTERNS = (
    r"\bwhat is\b",
    r"\bwhat are the principles?\b",
    r"\bdefine|definition of|meaning of\b",
    r"\bconcept(s)? (of|behind|like)\b",
    r"\bphilosophy|framework|doctrine|theory of\b",
)
_POLYMATH_PATTERNS = (
    r"\brelate[sd]? to|connection[s]? between|how (do|does|can) .+ "
    r"(connect|relate|apply)\b",
    r"\bconnect\w*\b|\brelat\w* between\b",
    r"\bacross domains?\b|\bbetween .+ and .+\b",
    r"\bcombine|synthes[ie]z|bridg\w*\b",
)
_FACT_PATTERNS = (
    r"\bwho (created|developed|trained|evaluated|introduced)\b",
    r"\bwhich benchmark|what benchmark|which dataset\b",
    r"\bwhen was .+ (released|published|introduced)\b",
    r"\bevaluated on|trained on|outperform\w*\b",
)


def _hits(text: str, patterns: tuple[str, ...]) -> int:
    return sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))


def classify_query(question: str) -> dict:
    q = (question or "").strip()
    proc = _hits(q, _PROCEDURE_PATTERNS)
    conc = _hits(q, _CONCEPT_PATTERNS)
    poly = _hits(q, _POLYMATH_PATTERNS)
    fact = _hits(q, _FACT_PATTERNS)

    scores = {
        ROUTE_PROCEDURE: proc * 2,
        ROUTE_CONCEPT: conc * 2,
        ROUTE_POLYMATH: poly * 3,   # cross-domain signals dominate
        ROUTE_FACT: fact * 2,
    }
    # "What is X" + a domain bridge => polymath beats concept
    if poly and (conc or proc):
        scores[ROUTE_POLYMATH] += 2

    best = max(scores.items(), key=lambda kv: (kv[1], kv[0]))
    if best[1] == 0:
        # default: conceptual exploration is the safest breadth route
        route = ROUTE_CONCEPT
    else:
        route = best[0]
    return {
        "router_version": QUERY_ROUTER_VERSION,
        "route": route,
        "signals": {"procedure": proc, "concept": conc,
                    "polymath": poly, "fact": fact},
        "confidence": round(min(1.0, best[1] / 3.0), 3),
    }
