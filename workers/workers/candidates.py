"""Evidence-anchored candidate-pair generation (docx §14).

Generation is evidence-anchored, not pair-anchored: one candidate per
(evidence span, compatible argument pairing), so a sentence with two
evidence spans yields two independent candidates ("John founded Acme and
remains its CEO" -> FOUNDED + HAS_ROLE).

Deterministic filters:
  - same-entity check (no self-edges);
  - entity-pair type compatibility pre-check against the union of the
    predicate signatures for the evidence class (cheap rejection of
    impossible pairings before the compiler);
  - sentence anchoring: candidates never cross a sentence boundary —
    cross-sentence relations are UNSUPPORTED by design in v1 (docx §22).

This module only builds candidates. It never selects predicates.
"""
from __future__ import annotations

from dataclasses import dataclass

from polymath_shared.contracts import (
    EntitySpan,
    EvidenceSpan,
    RelationCandidate,
    RoleAssignment,
    SemanticRole,
    ScopeFlags,
)
from polymath_shared.rulepack.negation import analyze_scope

MAX_SYNTAX_DISTANCE = 4


@dataclass(frozen=True)
class SentenceSlice:
    """One sentence's pass-1 + pass-2 output, char offsets absolute in the chunk."""
    text: str
    sentence_start: int
    sentence_end: int
    entities: list[EntitySpan]
    evidence: list[EvidenceSpan]
    parse: dict | None


def _type_compatible(
    subject_type: str,
    object_type: str,
    evidence_class: str,
    rule_pack: dict,
) -> bool:
    """Cheap pre-filter: does ANY predicate signature for this evidence
    class accept this entity-type pair? Rejects impossible pairings before
    the compiler runs."""
    for rule in rule_pack["predicates"].values():
        if evidence_class not in rule["evidence"].get("classes", []):
            continue
        for sig in rule["signatures"]:
            if subject_type in sig.get("subject_core", []) and object_type in sig.get("object_core", []):
                return True
    return False


def build_candidates(
    slices: list[SentenceSlice],
    *,
    doc_id: str,
    corpus_id: str = "eval",
    ontology_profile: str,
    extractor_version: str,
    rule_pack: dict,
    enrich: bool = True,
) -> list[RelationCandidate]:
    """Deterministic candidate generation over sentence slices.

    Pairs are evidence-anchored (docx §14): the subject candidate is the
    entity nearest to the LEFT of the evidence span, the object candidate
    the entity nearest to the RIGHT. This fixes direction by surface
    linear order — a deterministic heuristic, marked weak in provenance
    unless the syntactic record supplies voice normalization.

    `enrich=False` is the Phase H lexical BASELINE arm: candidates carry
    no resource-derived evidence (roleset/VN/FN/SemLink all empty).

    Total order: (sentence, evidence, subject, object) — reproducible
    from the same spans.
    """
    candidates: list[RelationCandidate] = []
    for sl in slices:
        for evidence in sl.evidence:
            scope = analyze_scope(
                sl.text,
                evidence.start - sl.sentence_start,
                evidence.end - sl.sentence_start,
            )
            evidence.trigger_lemma = evidence.trigger_lemma or _head_trigger(evidence, sl)
            _lexical = _lookup_for(rule_pack, evidence) if enrich else {
                "roleset": None, "vn_classes": [], "fn_frames": [], "semlink_resolved": False,
            }

            left = sorted(
                [e for e in sl.entities if e.end <= evidence.start],
                key=lambda e: (-e.end, -e.start),
            )
            right = sorted(
                [e for e in sl.entities if e.start >= evidence.end],
                key=lambda e: (e.start, e.end),
            )
            for subject_span in left:
                for object_span in right:
                    if subject_span.text == object_span.text and subject_span.core_type == object_span.core_type:
                        continue
                    if not _type_compatible(
                        subject_span.core_type.value,
                        object_span.core_type.value,
                        evidence.evidence_class,
                        rule_pack,
                    ):
                        continue

                    subject_id = _allocate(subject_span, sl, doc_id, corpus_id)
                    object_id = _allocate(object_span, sl, doc_id, corpus_id)
                    candidates.append(RelationCandidate(
                        evidence=evidence,
                        subject=_entity_candidate(subject_span, subject_id),
                        object=_entity_candidate(object_span, object_id),
                        roles=_role_assignments(subject_span, object_span, sl.parse),
                        roleset=_lexical["roleset"],
                        verbnet_classes=_lexical["vn_classes"],
                        framenet_frames=_lexical["fn_frames"],
                        semlink_resolved=_lexical["semlink_resolved"],
                        scope=scope,
                        ontology_profile=ontology_profile,
                    ))
    return candidates


def _allocate(span, sl: SentenceSlice, doc_id: str, corpus_id: str) -> str:
    """Entity admission boundary (E2/C1.1): identity by reference class.

    GLOBAL -> global canonical id; CORPUS_SCOPED -> corpus+type+surface;
    DOCUMENT_SCOPED -> corpus+doc+type+surface; MENTION_ONLY -> stable
    evidence mention id (never a durable graph identity)."""
    from polymath_shared.entity_admission import allocate_entity_id

    leading = sl.text[: len(sl.text) - len(sl.text.lstrip())]
    sentence_initial = span.start <= sl.sentence_start + len(leading)
    decision = allocate_entity_id(
        span.text,
        span.core_type.value,
        corpus_id=corpus_id,
        doc_id=span.doc_id or doc_id,
        chunk_id=span.chunk_id,
        span_start=span.start,
        span_end=span.end,
        extraction_score=span.score,
        sentence_initial=sentence_initial,
    )
    return decision.mention_id


def _entity_candidate(span: EntitySpan, resolved_id: str):
    from polymath_shared.contracts import EntityCandidate

    return EntityCandidate(span=span, resolved_entity_id=resolved_id)


def _role_assignments(subject: EntitySpan, object: EntitySpan, parse: dict | None) -> list[RoleAssignment]:
    if not parse:
        return []
    roles: list[RoleAssignment] = []
    if parse.get("voice") == "passive":
        if parse.get("subject"):
            roles.append(RoleAssignment(
                role=SemanticRole.ARG1, entity_ref=subject.text,
                syntactic_path="nsubj:pass", weak=not parse.get("roleset_known", False),
            ))
        if parse.get("agent"):
            roles.append(RoleAssignment(
                role=SemanticRole.ARG0, entity_ref=object.text,
                syntactic_path="obl:agent", weak=not parse.get("roleset_known", False),
            ))
    else:
        if parse.get("subject"):
            roles.append(RoleAssignment(
                role=SemanticRole.ARG0, entity_ref=subject.text,
                syntactic_path="nsubj", weak=not parse.get("roleset_known", False),
            ))
        if parse.get("object"):
            roles.append(RoleAssignment(
                role=SemanticRole.ARG1, entity_ref=object.text,
                syntactic_path="obj", weak=not parse.get("roleset_known", False),
            ))
    return roles


def _lookup_for(rule_pack: dict, evidence: EvidenceSpan) -> dict:
    """Real-resource lemma lookup (compiled tables): VerbNet classes,
    PropBank rolesets, composed FrameNet frames, SemLink resolution.
    A single roleset disambiguates; several stay ambiguous (compiler
    abstains). Missing data is absence, never a gate (docx §9)."""
    from polymath_shared.rulepack.compiler import lexical_lookup

    lemma = evidence.trigger_lemma
    if not lemma:
        return {"roleset": None, "vn_classes": [], "fn_frames": [], "semlink_resolved": False}
    lookup = lexical_lookup(rule_pack, lemma)
    rolesets = lookup["propbank_rolesets"]
    return {
        "roleset": rolesets[0] if len(rolesets) == 1 else None,
        "vn_classes": lookup["verbnet_classes"],
        "fn_frames": lookup["framenet_frames"],
        "semlink_resolved": lookup["semlink_resolved"],
    }


def _head_trigger(evidence: EvidenceSpan, sl: SentenceSlice) -> str | None:
    from polymath_shared.rulepack.compiler import normalize_trigger

    return normalize_trigger(evidence.text)
