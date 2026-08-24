"""S4 — the SINGLE live admission authority.

Before S4, admission was called inline at five sites and `decide()` was
the de-facto authority. That name now means HISTORICAL semantics, which is
exactly how a future caller reaches for it from production by accident.
Everything therefore routes through ONE explicitly contract-dispatched
entry point:

    interpret_admission(contract_version=...)
        admission-harbor-v2  -> the qualified V2 stack   (current ingestion)
        admission-v1.1       -> historical interpreter   (pinned replay ONLY)
        anything else        -> FAIL

There is no fallback. `if V2 fails: try v1.1` is forbidden — it would make
graph semantics depend on which interpreter happened to succeed.

The V2 composition, in order:

    proposal_surface (raw, case-bearing)
      -> referential envelope (REFERENTIAL-SPAN-V1)
      -> IDENTITY-PRECISION-V2   decisive identity?
           yes -> IDENTITY
           no  -> ENTITY-HARBOR
                    definite/deictic -> DISCOURSE-REFERENCE-V1
                    bare generic     -> GENERIC
                    else             -> CONCEPT-EVIDENCE-V1 or ABSTAIN
      -> graph_eligible()   (the one authority)

`normalized_surface` is NEVER an input to any of this.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

ADMISSION_INTERPRETER_CONTRACT = "admission-interpreter-v1"
_DEF = ("the ", "this ", "that ", "these ", "those ", "our ", "its ", "their ")
_IDENT_REASONS = frozenset({"acronym_identity", "versioned_identity_structure",
                            "proper_name_identity"})


class UnknownAdmissionContract(Exception):
    """An unpinned or unrecognised semantic contract. Never guess."""


@dataclass(frozen=True)
class AdmissionResult:
    proposal_surface: str
    referential_surface: str
    core_type: str
    anchor_kind: str
    decision_status: str
    scope: str
    reference_basis: str | None
    graph_eligible: bool
    admission_reason: str
    semantic_contract: str
    resolves_to: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    interpreter: str = ADMISSION_INTERPRETER_CONTRACT


def interpret_admission(*, contract_version: str, proposal_surface: str,
                        core_type: str, span: tuple[int, int] | None = None,
                        sentence_text: str = "", syntax: dict | None = None,
                        document_text: str = "", discourse_context: list[str] | None = None,
                        discourse_syntax: list[dict] | None = None,
                        admitted_anchors: list[tuple[str, str]] | None = None,
                        extraction_score: float = 0.0,
                        sentence_initial: bool = False,
                        heading_context: bool = False) -> AdmissionResult:
    """THE live authority. Dispatches on the pinned semantic contract."""
    from polymath_shared.execution import SEMANTIC_CONTRACT_V1_1, SEMANTIC_CONTRACT_V2

    if contract_version == SEMANTIC_CONTRACT_V2:
        return _interpret_v2(
            proposal_surface, core_type, span, sentence_text, syntax,
            document_text, discourse_context or [], admitted_anchors or [],
            discourse_syntax, heading_context)
    if contract_version == SEMANTIC_CONTRACT_V1_1:
        return _interpret_v1_1_historical(
            proposal_surface, core_type, extraction_score, sentence_initial)
    raise UnknownAdmissionContract(
        f"no interpreter for semantic contract {contract_version!r}. "
        f"Current ingestion must pin {SEMANTIC_CONTRACT_V2!r}; "
        f"{SEMANTIC_CONTRACT_V1_1!r} is available for explicitly pinned "
        f"historical replay only. Guessing an interpreter is forbidden.")


def _interpret_v2(proposal_surface, core_type, span, sentence_text, syntax,
                  document_text, discourse_context, admitted_anchors,
                  discourse_syntax=None, heading_context=False):
    from polymath_shared.concept_evidence import admit_concept
    from polymath_shared.discourse_reference import resolve
    from polymath_shared.generic_classification import classify_generic
    from polymath_shared.entity_harbor import (
        AnchorKind, DecisionStatus, HarborDecision, ReferenceBasis, Referentiality,
        graph_eligible,
    )
    from polymath_shared.execution import SEMANTIC_CONTRACT_V2
    from polymath_shared.identity_evidence import identity_evidence
    from polymath_shared.referential_span import derive
    from polymath_shared.syntax_readiness import assert_syntax_available

    # S3 (C): the execution assertion. A sidecar can die between claim and
    # use; nothing semantic may be produced without syntax.
    assert_syntax_available({"semantic_contract": SEMANTIC_CONTRACT_V2}, syntax,
                            where="admission-harbor-v2 interpretation")

    start, end = span if span else (0, len(proposal_surface))
    env = derive(proposal_surface, start, end, sentence_text or proposal_surface, syntax)
    toks = [t for t in (syntax or {}).get("tokens", [])
            if t.get("char_start") is not None
            and t["char_start"] >= start and t["char_end"] <= end]

    def _result(d: HarborDecision, reason: str, ev: dict) -> AdmissionResult:
        return AdmissionResult(
            proposal_surface, env.referential_surface, core_type,
            d.anchor_kind.value, d.decision_status.value, d.scope,
            d.reference_basis.value if d.reference_basis else None,
            graph_eligible(d), reason, SEMANTIC_CONTRACT_V2,
            d.resolves_to, ev)

    # PRONOUN-ADMISSION-BAN (owner E-1, 2026-08-24): personal/demonstrative
    # pronouns are never durable entities. They previously slipped through
    # as GLOBAL ("You", "I" admitted in transcript corpora) contaminating
    # every conversation-derived graph. Fail-closed to MENTION_ONLY with
    # an explicit reason; no gate is weakened by this.
    _PRONOUN_SURFACES = {"i", "you", "we", "it", "he", "she", "they",
                         "me", "him", "her", "them", "us"}
    if proposal_surface.strip().lower() in _PRONOUN_SURFACES:
        d = HarborDecision(proposal_surface, AnchorKind.UNKNOWN,
                           Referentiality.UNRESOLVED, "MENTION_ONLY",
                           DecisionStatus.ABSTAINED)
        return _result(d, "pronoun_admission_ban: pronouns are never "
                          "durable entities (E-1)", {})

    # SUBTOKEN-SPAN-ADMISSION-V1 (ledger 75). An empty `toks` list has TWO
    # causes that previously shared one (wrong) outcome:
    #
    #   syntax truly unavailable      -> a dependency OUTAGE: retryable, and
    #                                    the stage must fail (kept, below)
    #   syntax PRESENT, span covers   -> a SETTLED structural fact about the
    #   no complete token                span (nested inside a larger token,
    #                                    e.g. `instagram` inside a URL token,
    #                                    or overlapping nothing)
    #
    # identity_evidence's require_syntax guard cannot tell these apart — it
    # only sees the empty list — so the second case raised
    # RetryableDependencyUnavailable and failed the extract stage
    # DETERMINISTICALLY on any URL-bearing document; retries could never
    # succeed. The distinction is drawn HERE, where the sentence's syntax is
    # in hand. A sub-token span abstains, fail-closed: the containing token
    # describes the larger token, not this surface, so it is recorded as
    # evidence but never promoted to identity — and the proposal surface is
    # preserved verbatim, never rewritten to the containing token.
    if not toks:
        sent_toks = [t for t in (syntax or {}).get("tokens", [])
                     if t.get("char_start") is not None]
        if sent_toks:
            containing = next((t for t in sent_toks
                               if t["char_start"] < end and t["char_end"] > start),
                              None)
            d = HarborDecision(proposal_surface, AnchorKind.UNKNOWN,
                               Referentiality.UNRESOLVED, "MENTION_ONLY",
                               DecisionStatus.ABSTAINED)
            return _result(
                d,
                "abstain: span covers no complete syntax token"
                + (" (nested inside a larger token)" if containing
                   else " (no overlapping token)"),
                {"contract": "subtoken-span-admission-v1",
                 "covering_tokens": 0,
                 "overlapping_token": (containing["text"][:60]
                                       if containing else None)})
        # sentence produced NO tokens at all: that is a syntax-production
        # failure, not a property of this span — fall through so the
        # retryable dependency path fires exactly as before.

    # 1. decisive identity on the RAW proposal (never the envelope, never normalized)
    ident = identity_evidence(proposal_surface, tokens=toks, require_syntax=True,
                              heading_context=heading_context)
    if ident.is_identity:
        d = HarborDecision(proposal_surface, AnchorKind.IDENTITY,
                           Referentiality.SPECIFIC, "GLOBAL")
        return _result(d, f"identity: {ident.reasons[0]}",
                       {"kind": ident.kind.value if ident.kind else None,
                        "envelope": env.referential_surface})

    # 2. definite/deictic envelope -> discourse consumer
    if env.referential_surface.lower().startswith(_DEF):
        # E4 BOUNDARY REPAIR: the consumer must receive syntax so antecedent
        # candidates come from bounded noun chunks, not the fallback regex.
        r = resolve(env.referential_surface, discourse_context or [sentence_text],
                    admitted_anchors=admitted_anchors,
                    syntax=discourse_syntax, target_tokens=toks)
        settled = r.basis is not ReferenceBasis.AMBIGUOUS
        established = r.basis in (ReferenceBasis.ANTECEDENT_RESOLVED,
                                  ReferenceBasis.DOCUMENT_CONSTITUTED)
        if established:
            # GENERIC must NEVER override a resolved or document-constituted
            # LOCAL_REFERENCE. `the engineering group` stays a bounded
            # discourse participant.
            d = HarborDecision(env.referential_surface, AnchorKind.LOCAL_REFERENCE,
                               Referentiality.UNRESOLVED, "DOCUMENT_SCOPED",
                               DecisionStatus.RESOLVED, r.basis,
                               resolves_to=r.resolves_to)
            return _result(d, f"discourse: {r.evidence[0] if r.evidence else r.basis.value}",
                           {"basis": r.basis.value, "candidates": list(r.candidates)})
        # EXTERNAL_UNRESOLVED / AMBIGUOUS establish nothing, so a plural class
        # expression may still be attributed GENERIC — "The regional
        # dispatchers" is a population, not a withheld particular party.
        gen_lr = classify_generic(proposal_surface, tokens=toks)
        if not gen_lr.is_generic:
            d = HarborDecision(env.referential_surface, AnchorKind.LOCAL_REFERENCE,
                               Referentiality.UNRESOLVED, "DOCUMENT_SCOPED",
                               DecisionStatus.ABSTAINED if r.basis is ReferenceBasis.AMBIGUOUS
                               else DecisionStatus.RESOLVED, r.basis)
            return _result(d, f"discourse: {r.evidence[0] if r.evidence else r.basis.value}",
                           {"basis": r.basis.value, "candidates": list(r.candidates)})
        d = HarborDecision(proposal_surface, AnchorKind.GENERIC,
                           Referentiality.GENERIC, "MENTION_ONLY")
        return _result(d, f"generic: {gen_lr.reasons[0]}",
                       {"evidence": gen_lr.evidence.value if gen_lr.evidence else None,
                        "discourse_basis": r.basis.value})

    # 3. auditable concept evidence — CONCEPT outranks GENERIC so a
    #    document-defined term is never demoted to a class term.
    ev = admit_concept(proposal_surface, document_text=document_text)
    if ev is not None:
        d = HarborDecision(proposal_surface, AnchorKind.CONCEPT,
                           Referentiality.GENERIC, "CORPUS_SCOPED")
        return _result(d, f"concept: {ev.kind.value}",
                       {"authority": ev.kind.value, "quote": ev.quote[:160]})

    # 3b. SCIENTIFIC-KAG-V1 named-concept gate — multi-token technical
    #     compounds and named concepts are auditable concept sources even
    #     without a document definition ("thought generator", "Tree of
    #     Thoughts"). Bare generic nouns and plurals decline here and fall
    #     through to generic classification unchanged.
    from polymath_shared.scientific_concept import named_concept_evidence
    sci = named_concept_evidence(proposal_surface, toks)
    if sci is not None:
        d = HarborDecision(proposal_surface, AnchorKind.CONCEPT,
                           Referentiality.GENERIC, "CORPUS_SCOPED")
        return _result(d, f"scientific-concept: {sci['pattern']}", sci)

    # 4. GENERIC-CLASSIFICATION-V1 — attribution only. Reached ONLY after
    #    IDENTITY, LOCAL_REFERENCE and CONCEPT have all declined, so it can
    #    never override an established interpretation. Eligibility is
    #    unchanged: GENERIC and UNKNOWN are both refused.
    gen = classify_generic(proposal_surface, tokens=toks,
                           has_identity_anchor=bool(admitted_anchors) and any(
                               a.lower() in proposal_surface.lower()
                               for a, _ in admitted_anchors))
    if gen.is_generic:
        d = HarborDecision(proposal_surface, AnchorKind.GENERIC,
                           Referentiality.GENERIC, "MENTION_ONLY")
        return _result(d, f"generic: {gen.reasons[0]}",
                       {"evidence": gen.evidence.value if gen.evidence else None})

    d = HarborDecision(proposal_surface, AnchorKind.UNKNOWN, Referentiality.UNRESOLVED,
                       "DOCUMENT_SCOPED", DecisionStatus.CONTEXT_REQUIRED)
    return _result(d, "abstain: no auditable concept or generic evidence", {})


def _interpret_v1_1_historical(proposal_surface, core_type, extraction_score,
                               sentence_initial):
    """Historical replay ONLY. Never reachable as a V2 fallback."""
    from polymath_shared.entity_admission import decide_v1_1_historical
    from polymath_shared.execution import SEMANTIC_CONTRACT_V1_1

    d = decide_v1_1_historical(proposal_surface, core_type, extraction_score,
                               sentence_initial=sentence_initial)
    return AdmissionResult(
        proposal_surface, proposal_surface, core_type,
        anchor_kind="UNSPECIFIED_V1_1", decision_status="RESOLVED",
        scope=d.reference_class, reference_basis=None,
        graph_eligible=d.reference_class != "MENTION_ONLY",
        admission_reason=f"v1.1 historical: {d.reasons[0]}",
        semantic_contract=SEMANTIC_CONTRACT_V1_1,
        evidence={"policy_version": d.policy_version})
