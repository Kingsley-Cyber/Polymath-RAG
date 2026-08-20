"""ENTITY-HARBOR-V1 — admission contract types (PHASE 2 scaffolding).

Plan: `docs/wiki/plans/REFERENTIAL-ADMISSION-V2-PLAN.md`, REVISION 3b.

This module defines the VOCABULARY and the FUNCTION INTERFACE only. It
deliberately contains **no classifier**. PHASE 1 proved some Harbor
decisions are impossible from surface text alone, so guessing them from
morphology is explicitly forbidden:

    THE INVARIANT
    If the required classification depends on discourse context, the
    system MUST consume discourse context or return CONTEXT_REQUIRED.
    It must NEVER infer the answer from morphology because the test
    harness happens to expect one.

Two axes that answer different questions, never collapsed:

    anchor_kind  what KIND of thing the expression denotes
    scope        how WIDELY its identity is valid

    Model 3       IDENTITY        + DOCUMENT_SCOPED
    PostgreSQL    IDENTITY        + GLOBAL
    vector index  CONCEPT         + CORPUS_SCOPED
    this service  LOCAL_REFERENCE + DOCUMENT_SCOPED
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

HARBOR_CONTRACT = "entity-harbor-v1"


class AnchorKind(str, Enum):
    """WHAT KIND of referent the expression denotes.

    PHASE 2A: `CONTEXT_REQUIRED` was removed from this enum. It answered a
    different question — "do I have enough evidence yet?" — and pairing a
    decision STATE with referent TYPES made `CONTEXT_REQUIRED -> IDENTITY`
    look like a change of entity type rather than the arrival of evidence.
    That distinction now lives in `DecisionStatus`."""

    IDENTITY = "IDENTITY"                # a particular identifiable thing
    CONCEPT = "CONCEPT"                  # a reusable kind / type / abstraction
    LOCAL_REFERENCE = "LOCAL_REFERENCE"  # discourse-specific, identity not independently established
    GENERIC = "GENERIC"                  # a class / plurality / existential set
    UNKNOWN = "UNKNOWN"                  # kind not yet determined — see DecisionStatus


class DecisionStatus(str, Enum):
    """WHETHER the classification is settled, and if not, why."""

    RESOLVED = "RESOLVED"                    # evidence sufficed
    CONTEXT_REQUIRED = "CONTEXT_REQUIRED"    # needs discourse context not supplied
    ABSTAINED = "ABSTAINED"                  # context supplied but insufficient/ambiguous


class Referentiality(str, Enum):
    SPECIFIC = "SPECIFIC"
    GENERIC = "GENERIC"
    UNRESOLVED = "UNRESOLVED"


class ReferenceBasis(str, Enum):
    """Only meaningful for LOCAL_REFERENCE. All three are DISCOURSE
    properties — none can be derived from a surface string."""

    ANTECEDENT_RESOLVED = "ANTECEDENT_RESOLVED"    # reuse the existing anchor; never re-create
    DOCUMENT_CONSTITUTED = "DOCUMENT_CONSTITUTED"  # document establishes a bounded participant
    EXTERNAL_UNRESOLVED = "EXTERNAL_UNRESOLVED"    # external referent, identity withheld
    AMBIGUOUS = "AMBIGUOUS"                        # >1 plausible antecedent — abstain, never guess


@dataclass(frozen=True)
class StructuralEvidence:
    """Deterministically observable from the span alone.

    RECORDED, NEVER DECISIVE. In particular `named_anchor_present` must
    NOT imply IDENTITY: `Polymath retrieval system` is one system,
    `Qwen3 embedding model` may be a family. Only context separates them
    (fixtures ctx-08 / ctx-09)."""

    head_lemma: str = ""
    generic_head: bool = False
    named_anchor_present: bool = False
    identifier_present: bool = False
    acronym_present: bool = False
    determiner: str | None = None
    is_plural: bool = False
    multiword: bool = False


@dataclass(frozen=True)
class HarborDecision:
    surface: str
    anchor_kind: AnchorKind
    referentiality: Referentiality
    scope: str
    decision_status: DecisionStatus = DecisionStatus.RESOLVED
    reference_basis: ReferenceBasis | None = None
    resolves_to: str | None = None
    reasons: tuple[str, ...] = ()
    structural: StructuralEvidence | None = None
    # E4 BOUNDARY REPAIR: resolution and eligibility are SEPARATE. If the
    # resolved anchor is itself non-eligible (a GENERIC population such as
    # "others"), the reference inherits that. Successful anaphora must never
    # manufacture identity. None = unknown/not applicable.
    resolved_anchor_eligible: bool | None = None
    contract: str = HARBOR_CONTRACT

    def __post_init__(self) -> None:
        if self.reference_basis is not None and self.anchor_kind is not AnchorKind.LOCAL_REFERENCE:
            raise ValueError("reference_basis is only meaningful for LOCAL_REFERENCE")
        if self.resolves_to is not None and self.reference_basis is not ReferenceBasis.ANTECEDENT_RESOLVED:
            raise ValueError("resolves_to requires ANTECEDENT_RESOLVED")
        if self.anchor_kind is AnchorKind.UNKNOWN and self.decision_status is DecisionStatus.RESOLVED:
            raise ValueError("UNKNOWN anchor_kind cannot be RESOLVED")

    @property
    def settled(self) -> bool:
        return self.decision_status is DecisionStatus.RESOLVED


def graph_eligible(decision: HarborDecision) -> bool:
    """THE single eligibility authority (REVISION 2, OPEN-2 settled).

    No stored `graph_eligible` column exists; every consumer — projector,
    control census, verifier and canonical fact promotion — calls THIS
    function so the four cannot drift apart.

    A decision that still needs context is NEVER eligible: abstention is
    the safe direction for a precision gate.
    """
    if not decision.settled:
        return False
    if decision.anchor_kind in (AnchorKind.GENERIC, AnchorKind.UNKNOWN):
        return False
    if decision.scope == "MENTION_ONLY":
        return False
    if decision.anchor_kind is AnchorKind.LOCAL_REFERENCE:
        if decision.reference_basis is ReferenceBasis.ANTECEDENT_RESOLVED:
            # inherit the anchor's eligibility — resolving to a generic
            # population does not create a canonical entity
            return decision.resolved_anchor_eligible is not False
        return decision.reference_basis is ReferenceBasis.DOCUMENT_CONSTITUTED
    return decision.anchor_kind in (AnchorKind.IDENTITY, AnchorKind.CONCEPT)


def classify(surface: str, *, core_type: str,
             structural: StructuralEvidence | None = None,
             discourse: object | None = None) -> HarborDecision:
    """PHASE 2 interface. NOT IMPLEMENTED — deliberately.

    REVISION 3b withholds authorization for a CONCEPT-vs-LOCAL_REFERENCE
    classifier built from surface strings, because that would recreate the
    two-token bug in a more sophisticated form. Implementing this requires
    an auditable concept source (canonical vocabulary/ontology entry,
    previously admitted concept, deterministic terminology evidence) and a
    discourse consumer for `reference_basis`. Until both exist the honest
    return value is CONTEXT_REQUIRED, so this raises rather than shipping
    a guess."""
    raise NotImplementedError(
        "ENTITY-HARBOR classify() is not authorized (REVISION 3b). "
        "Requires an auditable concept source and a discourse consumer; "
        "morphological inference is explicitly forbidden."
    )


def canonical_fact_admissible(subject: HarborDecision,
                              obj: HarborDecision) -> tuple[bool, str]:
    """PHASE 2C: the canonical-fact gate.

    Calls the SAME `graph_eligible()` contract that projection, the control
    census and the verifier use — it does not re-interpret eligibility, and
    no `graph_eligible` value is stored anywhere. One authority, four
    consumers.

    A MENTION_ONLY-endpoint fact may still exist as evidence: candidate
    generation, diagnostics, syntax binding, evaluation and provenance are
    all unaffected. It simply may not be asserted as canonical knowledge.

    Returns (admissible, reason).
    """
    if not graph_eligible(subject):
        return False, f"subject not graph-eligible: {_why(subject)}"
    if not graph_eligible(obj):
        return False, f"object not graph-eligible: {_why(obj)}"
    return True, "both endpoints graph-eligible"


def _why(d: HarborDecision) -> str:
    if not d.settled:
        return f"{d.decision_status.value} ({d.anchor_kind.value})"
    if d.anchor_kind is AnchorKind.GENERIC:
        return "GENERIC — a class/plurality, not one entity"
    if d.anchor_kind is AnchorKind.UNKNOWN:
        return "UNKNOWN anchor kind"
    if d.scope == "MENTION_ONLY":
        return "scope MENTION_ONLY"
    if d.anchor_kind is AnchorKind.LOCAL_REFERENCE:
        return f"LOCAL_REFERENCE/{d.reference_basis.value if d.reference_basis else 'no basis'}"
    return "eligible"
