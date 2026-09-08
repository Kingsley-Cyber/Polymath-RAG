"""QUERY-INTENT-V1 — deterministic 10-intent classification over the compiler output.

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §4/§5/§33/§64: the runtime policy is
INTENT × PROFILE-FIELD × TECHNIQUE × BUDGET. Query INTENT selects which profile fields
matter; fields select the retrieval technique; modes set the budget. Per §5 the intent is
DERIVED from the EXISTING query compiler / typed-subquery system — there is NO new
classifier LLM. This module folds signals the compiler already produces (task_type, the
multiset of subquery `qtype`s, `graph_useful`, `exact_terms`, `entities`, `response_type`)
together with the existing deterministic `query_router` lexical families into ONE of the
plan's ten canonical intents. Pure, order-stable: same inputs → same intent.

The classifier is intentionally ordered most-specific → most-general; the first satisfied
rule wins. It never raises and always returns a valid intent (EXPLORATORY is the floor).
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from polymath_shared.query_router import (
    _CONCEPT_PATTERNS,
    _POLYMATH_PATTERNS,
    _PROCEDURE_PATTERNS,
    _hits,
)

QUERY_INTENT_VERSION = "query-intent-v1"

#: The plan's canonical intent vocabulary (§5). Order here is documentation only; the
#: classifier's own precedence is encoded in `classify_intent`.
INTENTS = (
    "EXACT", "DEFINITION", "MECHANISM", "RELATIONSHIP", "COMPARISON",
    "PROCEDURE", "APPLICATION", "SYNTHESIS", "RECALL", "EXPLORATORY",
)

#: fuzzy-rediscovery phrasing (§31): "there was something in my books about …"
_RECALL_PATTERNS = (
    r"\bthere('?s| was| is)\b.{0,30}\b(something|a (bit|part|section|passage|chapter))\b",
    r"\bi (vaguely )?remember\b", r"\bi (read|saw|recall)\b.{0,20}\b(something|somewhere)\b",
    r"\bsomething (in|about|from)\b.{0,20}\b(my|the)\b.{0,20}\b(books?|notes?|sources?|documents?)\b",
    r"\bwhat was that\b", r"\bcan'?t (quite )?remember\b",
)
#: broad grounded-synthesis phrasing (§30): "what do my books say about …"
_SYNTHESIS_PATTERNS = (
    r"\bwhat do (my|the|our)\b.{0,20}\b(books?|sources?|documents?|notes?|corpus)\b.{0,10}\bsay\b",
    r"\bacross (my|the|all|these)\b.{0,20}\b(books?|sources?|documents?)\b",
    r"\bsummar(ise|ize)\b", r"\btl;dr\b", r"\boverview of\b", r"\brecap\b",
)
_COMPARE_PATTERNS = (r"\bcompare\b", r"\bcontrast\b", r"\bversus\b", r"\b vs\.? \b",
                     r"\b(dis)?agree\b", r"\bdiffer(ence|s)?\b", r"\bwhich is better\b")
_CREATE_PATTERNS = (r"\b(create|write|draft|generate|produce|compose|design)\b.{0,30}"
                    r"\b(prompt|description|scene|caption|copy|brief|outline|artifact|version)\b",
                    r"\bwrite (me|a)\b", r"\bgive me a\b", r"\bmake (a|me)\b")
_MECHANISM_PATTERNS = (r"\bwhy\b", r"\bhow (does|do|can|is|are)\b", r"\bwhat (makes|causes)\b",
                       r"\bmechanism\b", r"\bexplain\b")
#: an exact IDENTIFIER (as opposed to a concept acronym like FACS): carries a digit, or a
#: CVE/RFC/ISO/IEEE tag, or a unit — the tokens §56 requires to keep literal semantics.
_IDENTIFIER = re.compile(r"\d|(?:\b(?:CVE|RFC|ISO|IEEE)\b)|(?:\b\d+(?:mm|ms|fps|px|k|K|GB|MB)\b)|%", re.I)


def _has_identifier(exact_terms: Iterable[str]) -> bool:
    return any(_IDENTIFIER.search(t or "") for t in (exact_terms or ()))


def _any(text: str, patterns: Sequence[str]) -> bool:
    return _hits(text, tuple(patterns)) > 0


def classify_intent(resolved_request: str, *, task_type: str | None = None,
                    qtypes: Iterable[str] = (), graph_useful: bool = False,
                    exact_terms: Iterable[str] = (), entities: Iterable[str] = (),
                    response_type: str = "answer") -> str:
    """Map the compiler's signals to one canonical intent (§33). Most-specific first."""
    q = (resolved_request or "").strip()
    qt = {str(t).upper() for t in (qtypes or ())}
    et = tuple(exact_terms or ())

    # 1. EXACT — a literal identifier lookup: an identifier-like exact term, lookup-shaped
    #    (not relational / comparison / procedural / mechanism). "What is AU21?" (§15).
    if et and _has_identifier(et) and not graph_useful and not (qt & {"COMPARISON", "COUNTERPOINT", "BRIDGE"}):
        if not _any(q, _PROCEDURE_PATTERNS) and not re.search(r"\bwhy\b|\bhow (does|do|can)\b", q, re.I):
            return "EXACT"

    # 2. COMPARISON — comparison / conflict / trade-off (§27).
    if qt & {"COMPARISON", "COUNTERPOINT"} or _any(q, _COMPARE_PATTERNS):
        return "COMPARISON"

    # 3. RECALL — fuzzy rediscovery (§31); distinctive phrasing, checked before generic why/what.
    if _any(q, _RECALL_PATTERNS):
        return "RECALL"

    # 4. SYNTHESIS — broad grounded synthesis (§30); "what do my books say …" outranks an
    #    embedded "why". Also the compiler's own GROUNDED_SYNTHESIS task.
    if task_type == "GROUNDED_SYNTHESIS" or _any(q, _SYNTHESIS_PATTERNS):
        return "SYNTHESIS"

    # 5. RELATIONSHIP — explicit relation between things (§19); graph-useful / BRIDGE / "connection between".
    if graph_useful or "BRIDGE" in qt or _any(q, _POLYMATH_PATTERNS):
        return "RELATIONSHIP"

    # 6. PROCEDURE — "how do I …", steps (§28).
    if "PROCEDURE" in qt or _any(q, _PROCEDURE_PATTERNS):
        return "PROCEDURE"

    # 7. APPLICATION — create a source-grounded artifact (§29).
    if task_type == "CREATE_FROM_KNOWLEDGE" or response_type == "artifact" or _any(q, _CREATE_PATTERNS):
        return "APPLICATION"

    # 8. MECHANISM — why / how-does / causal (§17).
    if qt & {"MECHANISM", "CAUSAL"} or _any(q, _MECHANISM_PATTERNS):
        return "MECHANISM"

    # 9. DEFINITION — what-is / define / concept (§16).
    if "DEFINITION" in qt or _any(q, _CONCEPT_PATTERNS):
        return "DEFINITION"

    # 10. EXPLORATORY — the floor: broad exploration / rediscovery / wildcard-leaning.
    return "EXPLORATORY"


from dataclasses import dataclass, replace


@dataclass(frozen=True)
class IntentPolicy:
    """The §33 intent row, declarative. `dualread`/`micro_latent` are the additive lanes
    that EXIST today (P2b applies them); `resolution_lift`/`graph`/`breadth` are forward-
    declared for later phases (P3/P6/P9) to read — recorded now, applied as they land."""
    dualread: bool                 # activate the DOCUMENT_PROFILE→PARENT_MAP→CHILD spine (lane E)
    micro_latent: bool             # activate the latent micro-search (lane D; §13 default depth)
    breadth: str = "MULTI_PREFERRED"          # SINGLE_OK | MULTI_PREFERRED | MULTI_REQUIRED (§48, P9)
    resolution_lift: str = "normal"           # off | normal | high | very_high (§10/§33, P3)
    graph: str = "off"                        # off | conditional | auto | strong (§37/§38, P6)
    atom_kinds: tuple[str, ...] = ()          # R4 PROFILE_ATOM kinds this intent searches (§33)


#: canonical atom-kind groupings (mirror profile_atom.py; inlined to avoid an import cycle).
_MECH = ("THEORY", "CONCEPT", "LATENT_PATTERN", "BOUNDARY")
_ALL_ATOMS = _MECH + ("SEEALSO", "BRIDGE", "ANCHOR", "TENSION", "INVERSION", "RECALLQ")

#: FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §33 intent matrix, one row per intent.
INTENT_POLICY: dict[str, IntentPolicy] = {
    "EXACT":        IntentPolicy(dualread=True,  micro_latent=False, breadth="SINGLE_OK",      resolution_lift="high",      graph="off",         atom_kinds=()),
    "DEFINITION":   IntentPolicy(dualread=True,  micro_latent=False, breadth="SINGLE_OK",      resolution_lift="high",      graph="off",         atom_kinds=("CONCEPT", "THEORY")),
    "MECHANISM":    IntentPolicy(dualread=True,  micro_latent=True,  breadth="MULTI_PREFERRED", resolution_lift="high",      graph="conditional", atom_kinds=_MECH),
    "RELATIONSHIP": IntentPolicy(dualread=True,  micro_latent=True,  breadth="MULTI_PREFERRED", resolution_lift="high",      graph="auto",        atom_kinds=("CONCEPT", "THEORY", "SEEALSO", "BRIDGE", "ANCHOR", "TENSION")),
    "COMPARISON":   IntentPolicy(dualread=True,  micro_latent=True,  breadth="MULTI_REQUIRED",  resolution_lift="high",      graph="conditional", atom_kinds=("CONCEPT", "BOUNDARY", "TENSION", "INVERSION")),
    "PROCEDURE":    IntentPolicy(dualread=True,  micro_latent=True,  breadth="MULTI_PREFERRED", resolution_lift="high",      graph="conditional", atom_kinds=("THEORY", "BOUNDARY", "INVERSION", "SEEALSO")),
    "APPLICATION":  IntentPolicy(dualread=True,  micro_latent=True,  breadth="MULTI_PREFERRED", resolution_lift="very_high", graph="conditional", atom_kinds=("THEORY", "CONCEPT", "BOUNDARY", "INVERSION", "SEEALSO")),
    "SYNTHESIS":    IntentPolicy(dualread=True,  micro_latent=True,  breadth="MULTI_REQUIRED",  resolution_lift="normal",    graph="conditional", atom_kinds=("THEORY", "CONCEPT", "BOUNDARY", "TENSION")),
    "RECALL":       IntentPolicy(dualread=True,  micro_latent=True,  breadth="MULTI_PREFERRED", resolution_lift="normal",    graph="off",         atom_kinds=("RECALLQ", "CONCEPT", "LATENT_PATTERN", "SEEALSO")),
    "EXPLORATORY":  IntentPolicy(dualread=True,  micro_latent=True,  breadth="MULTI_PREFERRED", resolution_lift="normal",    graph="conditional", atom_kinds=_ALL_ATOMS),
}


def policy_for(intent: str) -> IntentPolicy | None:
    return INTENT_POLICY.get((intent or "").upper())


def apply_intent_policy(intent: str, budget):
    """Return a copy of `budget` with the ACTIVE (already-built) knobs the intent selects:
    the profile→map spine (`dualread_enabled`), the latent micro-search (`latent_enabled`),
    and the `breadth` preference. Forward-declared policy (resolution_lift/graph) is left for
    P3/P6 to read from `policy_for(intent)`; it is NOT applied here. Duck-typed on `budget`
    (uses `dataclasses.replace`) so this module stays decoupled from `CandidateBudget`."""
    p = policy_for(intent)
    if p is None:
        return budget
    overrides = {"dualread_enabled": p.dualread, "latent_enabled": p.micro_latent}
    if hasattr(budget, "breadth"):
        overrides["breadth"] = p.breadth
    if hasattr(budget, "atom_kinds"):
        overrides["atom_kinds"] = p.atom_kinds
    if hasattr(budget, "resolution_lift_enabled"):
        overrides["resolution_lift_enabled"] = p.resolution_lift != "off"   # R6 precision lane per intent
    # P9 task-conditioned breadth (§48/§49/§61): SINGLE_OK (exact/definition) lets one excellent
    # source dominate — turn OFF the doc-fair round-robin; MULTI_* keep it on (evidence-earned
    # diversity, never a hard quota — the composer still fills remaining seats in fusion order).
    if hasattr(budget, "rerank_round_robin"):
        overrides["rerank_round_robin"] = p.breadth != "SINGLE_OK"
    return replace(budget, **overrides)


def intent_of_plan(plan) -> str:
    """Classify a compiled plan (duck-typed ChatPlan — no import cycle)."""
    qtypes = [getattr(q, "type", "") for q in (getattr(plan, "queries", None) or [])]
    return classify_intent(
        getattr(plan, "resolved_request", "") or getattr(plan, "original_request", ""),
        task_type=getattr(plan, "task_type", None),
        qtypes=qtypes,
        graph_useful=bool(getattr(plan, "graph_useful", False)),
        exact_terms=getattr(plan, "exact_terms", ()) or (),
        entities=getattr(plan, "entities", ()) or (),
        response_type=getattr(plan, "response_type", "answer"),
    )
