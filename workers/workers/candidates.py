"""Evidence-anchored candidate-pair generation (docx §14, I3R-R2).

I3R-R2: TRIGGER-SCOPED ARGUMENT FRAMES replace the unbounded
left×right Cartesian product. Each evidence span binds AT MOST ONE
candidate pair under a deterministic surface frame:

  SUBJ_BEFORE_OBJ_AFTER
      subject = nearest entity left of the trigger (within its
      predicate region), object = nearest entity right of the trigger.
  ARG1_AFTER_ARG2_AFTER_PREP   (evidence_class == "association")
      "connect X to Y" — ARG1 = nearest entity between the trigger and
      the first following preposition, ARG2 = nearest entity after it.
      The frame requires REFERENTIAL (non-MENTION_ONLY) arguments.

Predicate-region boundaries (R2B): a coordinator (and/but/or/while,
optionally comma-prefixed, or ';') opens a NEW predicate region only
when the content word immediately after it is itself a rule-pack
trigger surface ("installed X ... and connected Y" splits; "The
frontend and backend are part of Z" does not — that 'and' joins an
entity list).

Entity lists (R2B): when exactly ONE side of a trigger binds a list
(2-3 entities between the same region boundaries) and the other side
binds exactly one, one candidate is emitted per list member. When BOTH
sides are lists the binding is ambiguous -> NO candidate (fail-closed,
R2C).

surface_weak (R2C): with no syntactic parse, every frame is a
surface frame and the pairing above is the ONLY authority — at most
one unambiguous binding per trigger, else no fact.
"""
from __future__ import annotations

import re
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
MAX_LIST_MEMBERS = 3

# coordinators that can open a new predicate region; the region split
# only occurs when the next content word is a trigger surface (see
# _predicate_region_boundaries)
_COORD_RE = re.compile(r"(?:,\s*)?\b(?:and|but|or|while)\b|;")
_WORD_RE = re.compile(r"[a-z]+")
_PREPOSITIONS = {"to", "with", "of", "into", "from", "in", "on", "onto",
                 "between", "for", "by", "at"}

# I3R-R2: prepositional relation frames require referential arguments
# (no MENTION_ONLY definites like "the workflow" anchoring a relation).
_REFERENTIAL_FRAMES = {"association"}

# I3R-R3: bounded local definite-description resolver. Only definite
# descriptions of 1-3 content words are considered; resolution is
# alias-only (reuses the existing entity identity — never creates a
# canonical entity named "company"/"gateway").
_DEFINITE_DESCRIPTION_RE = re.compile(
    r"\bthe\s+([a-z][a-z0-9]*(?:\s+[a-z0-9]+){0,2})\b", re.IGNORECASE)
_ORG_DESCRIPTIONS = {"company", "firm", "business", "organization",
                     "vendor", "retailer", "startup", "provider",
                     "operator", "maker"}


def _resolve_definite_description(
    sentence: str,
    rel_ev_start: int,
    left_bound: int,
    history: list[EntitySpan],
) -> EntitySpan | None:
    """I3R-R3: resolve 'the X' immediately left of a trigger against the
    document entity history.

    Rules (bounded, deterministic, abstain on ambiguity):
      1. head match: description's last word equals the last word of
         exactly ONE history entity's normalized surface;
      2. org description: description's last word is a closed-class
         org term and exactly ONE history entity has core_type
         Organization.
    Anything else (zero or multiple matches) abstains."""
    window = sentence[left_bound:rel_ev_start]
    matches = list(_DEFINITE_DESCRIPTION_RE.finditer(window))
    if not matches:
        return None
    desc = matches[-1].group(1).lower().strip()
    words = desc.split()
    head = words[-1]
    candidates: list[EntitySpan] = []
    if head in _ORG_DESCRIPTIONS:
        orgs = [e for e in history if e.core_type.value == "Organization"]
        if len(orgs) == 1:
            return orgs[0]
        if orgs:
            return None  # ambiguous
    for e in history:
        surf_words = e.text.lower().split()
        if surf_words and surf_words[-1] == head:
            candidates.append(e)
    if len(candidates) == 1:
        return candidates[0]
    return None


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


def _trigger_surfaces(rule_pack: dict) -> dict[str, set[str]]:
    """Index of every trigger surface in the pack: {word -> set of arms}.

    Verb surfaces are the bounded inflection forms of the verb lemmas
    (same contract as evidence_proposer); noun/multiword surfaces are
    the literal entries (multiword indexed by first word)."""
    idx: dict[str, set[str]] = {}
    for rule in rule_pack["predicates"].values():
        ev = rule["evidence"]
        for phrase in ev.get("multiword", []):
            idx.setdefault(phrase.split()[0].lower(), set()).add("multiword")
        for noun in ev.get("nouns", []):
            idx.setdefault(noun.lower(), set()).add("noun")
        for verb in ev.get("verbs", []):
            for form in _bounded_forms(verb.lower()):
                idx.setdefault(form, set()).add("verb")
    return idx


def _bounded_forms(lemma: str) -> set[str]:
    forms = {lemma, lemma + "s", lemma + "es", lemma + "d", lemma + "ed", lemma + "ing"}
    if lemma.endswith("e"):
        forms |= {lemma[:-1] + "ing", lemma[:-1] + "d"}
    if lemma.endswith("y"):
        forms |= {lemma[:-1] + "ies", lemma[:-1] + "ied"}
    if (len(lemma) >= 3 and lemma[-3] not in "aeiou"
            and lemma[-2] in "aeiou" and lemma[-1] not in "aeiouy"):
        forms |= {lemma + lemma[-1] + "ed", lemma + lemma[-1] + "ing"}
    return forms


def _predicate_region_boundaries(sentence: str, trigger_index: dict[str, set[str]]) -> list[int]:
    """Positions (end of coordinator) where a NEW predicate region opens:
    the coordinator is immediately followed by a trigger surface."""
    boundaries: list[int] = []
    lowered = sentence.lower()
    for m in _COORD_RE.finditer(sentence):
        tail = lowered[m.end():]
        wm = _WORD_RE.search(tail)
        if wm and tail[:wm.start()].strip() == "" and wm.group(0) in trigger_index:
            boundaries.append(m.end())
    return boundaries


def _admission_class_of(span: EntitySpan, sl: SentenceSlice, doc_id: str,
                        corpus_id: str) -> str:
    """Reuse the frozen admission classifier to decide referentiality of
    a frame argument (I3R-R2 referential-frame gate)."""
    from polymath_shared.entity_admission import decide
    leading = sl.text[: len(sl.text) - len(sl.text.lstrip())]
    sentence_initial = span.start <= sl.sentence_start + len(leading)
    return decide(span.text, span.core_type.value, span.score,
                  sentence_initial=sentence_initial).reference_class


def build_candidates(
    slices: list[SentenceSlice],
    *,
    doc_id: str,
    corpus_id: str = "eval",
    ontology_profile: str,
    extractor_version: str,
    rule_pack: dict,
    enrich: bool = True,
    doc_entities_history: list[EntitySpan] | None = None,
) -> list[RelationCandidate]:
    """Deterministic, trigger-scoped candidate generation (I3R-R2).

    One candidate per (evidence span, unambiguous frame binding).
    Total order: (sentence, evidence, list member) — reproducible from
    the same spans and the same history."""
    trigger_index = _trigger_surfaces(rule_pack)
    candidates: list[RelationCandidate] = []
    for sl in slices:
        sentence = sl.text
        rel_start = sl.sentence_start
        boundaries = _predicate_region_boundaries(sentence, trigger_index)
        for evidence in sl.evidence:
            scope = analyze_scope(
                sentence,
                evidence.start - rel_start,
                evidence.end - rel_start,
            )
            evidence.trigger_lemma = evidence.trigger_lemma or _head_trigger(evidence, sl)
            _lexical = _lookup_for(rule_pack, evidence) if enrich else {
                "roleset": None, "vn_classes": [], "fn_frames": [], "semlink_resolved": False,
            }

            rel_ev_start = evidence.start - rel_start
            rel_ev_end = evidence.end - rel_start
            left_bound = max([b for b in boundaries if b <= rel_ev_start], default=0)
            right_bound = min([b for b in boundaries if b >= rel_ev_end],
                              default=len(sentence))

            left = sorted(
                [e for e in sl.entities
                 if e.end <= evidence.start and e.start - rel_start >= left_bound],
                key=lambda e: (-e.end, -e.start),
            )
            right = sorted(
                [e for e in sl.entities
                 if e.start >= evidence.end and e.end - rel_start <= right_bound],
                key=lambda e: (e.start, e.end),
            )

            # -- frame selection --------------------------------------
            subjects: list[EntitySpan] = []
            objects: list[EntitySpan] = []
            referential_gate = evidence.evidence_class in _REFERENTIAL_FRAMES

            if evidence.evidence_class == "association":
                # "connect X to Y": prepositional frame when a preposition
                # follows the trigger inside the region
                tail = sentence[rel_ev_end:right_bound].lower()
                prep_m = None
                for prep in sorted(_PREPOSITIONS, key=len, reverse=True):
                    pm = re.search(r"\b" + re.escape(prep) + r"\b", tail)
                    if pm:
                        prep_m = (rel_ev_end + pm.start(), prep)
                        break
                if prep_m is not None:
                    prep_pos, _prep = prep_m
                    arg1 = [e for e in right if e.start >= evidence.end
                            and e.end <= rel_start + prep_pos]
                    arg2 = [e for e in right if e.start >= rel_start + prep_pos]
                    if arg1:
                        # arg1 is the trigger-adjacent entity (nearest)
                        arg1 = [arg1[0]]
                    if arg2:
                        arg2 = [arg2[0]]
                    if arg1 and arg2:
                        subjects, objects = arg1, arg2

            if not subjects or not objects:
                subjects = left[:1]
                objects = right[:1]

            if not subjects and objects and doc_entities_history:
                # I3R-R3: bounded local definite-description resolution
                # for the subject slot ('The gateway uses Envoy Proxy'
                # after 'Meridian API Gateway routes traffic').
                resolved = _resolve_definite_description(
                    sentence, rel_ev_start, left_bound, doc_entities_history)
                if resolved is not None:
                    subjects = [resolved]

            if not subjects or not objects:
                # fail-closed: no unambiguous surface binding
                continue

            # -- list expansion (bounded, single-sided only) -----------
            if len(left) > 1 and len(right) > 1:
                # ambiguous: entity lists on BOTH sides of the trigger
                # -> fail-closed, no fact (R2C)
                continue
            if len(left) > 1 and len(right) <= 1 and len(objects) == 1 and not (
                    evidence.evidence_class == "association" and subjects is left[:1]):
                subjects = left[:MAX_LIST_MEMBERS]
            elif len(right) > 1 and len(left) <= 1 and len(subjects) == 1:
                objects = right[:MAX_LIST_MEMBERS]
            if len(subjects) > MAX_LIST_MEMBERS or len(objects) > MAX_LIST_MEMBERS:
                continue  # ambiguous list binding

            # referential gate: prepositional frames require
            # non-MENTION_ONLY arguments
            if referential_gate:
                if any(_admission_class_of(s, sl, doc_id, corpus_id) == "MENTION_ONLY"
                       for s in subjects + objects):
                    continue

            for subject_span in subjects:
                for object_span in objects:
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
                        sentence_text=sentence,
                        sentence_start=rel_start,
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
