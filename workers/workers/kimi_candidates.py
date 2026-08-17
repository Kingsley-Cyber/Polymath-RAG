"""KIMI-ARCHITECTURE-REALIGNMENT-V1: UD-anchored candidate generation.

The original Kimi design: candidate arguments derive from the UD
dependency tree (entities whose head tokens are syntactic dependents
of the predicate/trigger head), with a bounded linear window only as
a recall net. Type compatibility runs AFTER structural argument
candidates exist — not as an early hard veto on which entities may
even be considered.

This module provides `build_candidates_kimi()` as the kimi_v1 variant;
the legacy `build_candidates()` remains untouched (legacy_v1). The
active pipeline is selected by POLYMATH_RELATION_PIPELINE env var.
"""
from __future__ import annotations

import os
from typing import Any

from polymath_shared.contracts import EntitySpan, EvidenceSpan
from workers.candidates import (
    MAX_LIST_MEMBERS,
    SentenceSlice,
    RelationCandidate,
    _allocate,
    _entity_candidate,
    _lookup_for,
    _predicate_region_boundaries,
    _resolve_definite_description,
    _role_assignments,
    _trigger_surfaces,
    _type_compatible,
)
from polymath_shared.rulepack.negation import analyze_scope

# spaCy ClearNLP + UD dependency relations that fill predicate argument slots
SUBJECT_DEPS = frozenset({"nsubj", "nsubj:pass"})
OBJECT_DEPS = frozenset({"dobj", "obj", "iobj"})
OBLIQUE_DEPS = frozenset({"obl", "obl:agent", "pobj", "agent", "obl:tmod"})
PREP_DEPS = frozenset({"prep", "agent"})


def _syntax_tokens(sl: SentenceSlice) -> list[dict]:
    """Syntax-evidence-v1 tokens sorted by char_start."""
    syntax = getattr(sl, "syntax", None)
    if not syntax:
        return []
    return sorted(syntax.get("tokens", []), key=lambda t: t["char_start"])


def _trigger_head_token(
    tokens: list[dict], evidence: EvidenceSpan, sl: SentenceSlice
) -> dict | None:
    """Locate the trigger's head token in the UD parse by offset overlap."""
    ev_start = evidence.start - sl.sentence_start
    ev_end = evidence.end - sl.sentence_start
    # find the token whose span overlaps the evidence and whose POS is verb-like
    # or noun-like (for nominal triggers)
    best = None
    for tok in tokens:
        if tok["char_start"] < ev_end and tok["char_end"] > ev_start:
            if tok["pos"] in ("VERB", "AUX", "NOUN"):
                if best is None or tok["pos"] == "VERB":
                    best = tok
    return best


def _find_ud_arguments(
    tokens: list[dict], trigger_head: dict
) -> dict[str, list[dict]]:
    """Find syntactic dependents of the trigger head, classified by
    argument role. Returns {role: [token, ...]} where role is
    'subject', 'object', 'oblique', 'prep_object', or 'coordination'.
    """
    args: dict[str, list[dict]] = {
        "subject": [], "object": [], "oblique": [], "prep_object": [],
        "coordination": [],
    }
    trig_idx = trigger_head["i"]

    # direct dependents
    for tok in tokens:
        if tok["head_i"] == trig_idx:
            if tok["dep"] in SUBJECT_DEPS:
                args["subject"].append(tok)
            elif tok["dep"] in OBJECT_DEPS:
                args["object"].append(tok)
            elif tok["dep"] in OBLIQUE_DEPS:
                args["oblique"].append(tok)
            elif tok["dep"] in PREP_DEPS:
                # preposition → look for pobj under it
                for child in tokens:
                    if child["head_i"] == tok["i"] and child["dep"] in ("pobj", "obl"):
                        args["prep_object"].append(child)

    # coordination: conj dependents of subject/object heads
    for role_toks in (args["subject"], args["object"]):
        for head_tok in list(role_toks):
            for tok in tokens:
                if tok["head_i"] == head_tok["i"] and tok["dep"] == "conj":
                    role_toks.append(tok)

    # coordination of the trigger itself (compound predicates)
    for tok in tokens:
        if tok["head_i"] == trig_idx and tok["dep"] == "conj":
            args["coordination"].append(tok)
            # inherit the conjunct's arguments too
            for child in tokens:
                if child["head_i"] == tok["i"]:
                    if child["dep"] in SUBJECT_DEPS:
                        args["subject"].append(child)
                    elif child["dep"] in OBJECT_DEPS:
                        args["object"].append(child)

    return args


def _token_to_entity(
    tok: dict, entities: list[EntitySpan], sl: SentenceSlice
) -> EntitySpan | None:
    """Find the entity span that contains (or is contained by) this
    token's span. The entity's head token should overlap the argument
    token."""
    tok_start = sl.sentence_start + tok["char_start"]
    tok_end = sl.sentence_start + tok["char_end"]
    # exact containment: token inside entity span
    for ent in entities:
        if ent.start <= tok_start and tok_end <= ent.end:
            return ent
    # entity inside token span (entity is a subspan of the argument NP)
    for ent in entities:
        if tok_start <= ent.start and ent.end <= tok_end:
            return ent
    # overlap (head token partially covers entity)
    for ent in entities:
        if ent.start < tok_end and ent.end > tok_start:
            return ent
    return None


def build_candidates_kimi(
    slices: list[SentenceSlice],
    *,
    doc_id: str,
    corpus_id: str = "eval",
    ontology_profile: str,
    extractor_version: str,
    rule_pack: dict,
    enrich: bool = True,
    doc_entities_history: list[EntitySpan] | None = None,
    observer=None,
) -> list[RelationCandidate]:
    """kimi_v1: UD-anchored, evidence-scoped candidate generation.

    Arguments derive from the dependency tree; type compatibility is
    a cheap post-structural pre-check; PropBank roles inform binding.
    """
    trigger_index = _trigger_surfaces(rule_pack)
    candidates: list[RelationCandidate] = []

    for sl in slices:
        sentence = sl.text
        rel_start = sl.sentence_start
        tokens = _syntax_tokens(sl)
        boundaries = _predicate_region_boundaries(sentence, trigger_index)

        for evidence in sl.evidence:
            scope = analyze_scope(
                sentence,
                evidence.start - rel_start,
                evidence.end - rel_start,
            )
            evidence.trigger_lemma = evidence.trigger_lemma or _lookup_trigger_lemma(evidence, sl)
            _lexical = _lookup_for(rule_pack, evidence) if enrich else {
                "roleset": None, "vn_classes": [], "fn_frames": [],
                "semlink_resolved": False,
            }

            rel_ev_start = evidence.start - rel_start
            rel_ev_end = evidence.end - rel_start
            left_bound = max([b for b in boundaries if b <= rel_ev_start], default=0)
            right_bound = min([b for b in boundaries if b >= rel_ev_end],
                              default=len(sentence))

            subjects: list[EntitySpan] = []
            objects: list[EntitySpan] = []
            binding_source = "BOUNDED_LINEAR_RECALL"  # default fallback

            # -- UD-tree primary binding ------------------------------
            if tokens:
                trig_head = _trigger_head_token(tokens, evidence, sl)
                if trig_head is not None:
                    ud_args = _find_ud_arguments(tokens, trig_head)

                    for tok in ud_args["subject"]:
                        ent = _token_to_entity(tok, sl.entities, sl)
                        if ent is not None and ent not in subjects:
                            subjects.append(ent)
                    for tok in ud_args["object"]:
                        ent = _token_to_entity(tok, sl.entities, sl)
                        if ent is not None and ent not in objects:
                            objects.append(ent)
                    for tok in ud_args["oblique"] + ud_args["prep_object"]:
                        ent = _token_to_entity(tok, sl.entities, sl)
                        if ent is not None and ent not in objects:
                            objects.append(ent)

                    if subjects or objects:
                        binding_source = "UD_DIRECT"

            # -- bounded linear recall (only if UD missed a slot) ------
            if not subjects:
                # nearest entity left of trigger within the predicate region
                left_entities = sorted(
                    [e for e in sl.entities
                     if e.end <= evidence.start and e.start - rel_start >= left_bound],
                    key=lambda e: (-e.end, -e.start),
                )
                if left_entities:
                    subjects = [left_entities[0]]
                    if binding_source == "UD_DIRECT":
                        binding_source = "UD_OBJECT_RECALL_SUBJECT"
                    else:
                        binding_source = "BOUNDED_LINEAR_RECALL"

            if not objects:
                right_entities = sorted(
                    [e for e in sl.entities
                     if e.start >= evidence.end and e.start - rel_start <= right_bound],
                    key=lambda e: (e.start, e.end),
                )
                if right_entities:
                    objects = [right_entities[0]]
                    if binding_source == "UD_DIRECT":
                        binding_source = "UD_SUBJECT_RECALL_OBJECT"
                    else:
                        binding_source = "BOUNDED_LINEAR_RECALL"

            # -- definite description recall (subject slot) ------------
            if not subjects and objects and doc_entities_history:
                resolved = _resolve_definite_description(
                    sentence, rel_ev_start, left_bound, doc_entities_history)
                if resolved is not None:
                    subjects = [resolved]
                    binding_source = "SAFE_LOCAL_PATTERN"

            if not subjects or not objects:
                if observer:
                    reason = ("SUBJECT_ENDPOINT_UNAVAILABLE" if not subjects else
                              "OBJECT_ENDPOINT_UNAVAILABLE")
                    observer.record_candidate_outcome(sl, evidence, reason, {
                        "binding_source": binding_source,
                        "ud_subjects": len(subjects), "ud_objects": len(objects),
                        "kimi_v1": True})
                continue

            # -- coordination expansion (UD conj, already in lists) ----
            if len(subjects) > MAX_LIST_MEMBERS:
                subjects = subjects[:MAX_LIST_MEMBERS]
            if len(objects) > MAX_LIST_MEMBERS:
                objects = objects[:MAX_LIST_MEMBERS]

            # -- TYPE PRE-CHECK: AFTER structural candidates exist ----
            # (the Kimi-corrected position: cheap evidence-class
            # signature-union filter on already-bound argument pairs)
            compatible_pairs: list[tuple[EntitySpan, EntitySpan]] = []
            for s in subjects:
                for o in objects:
                    if s.text == o.text and s.core_type == o.core_type:
                        continue
                    if _type_compatible(s.core_type.value, o.core_type.value,
                                        evidence.evidence_class, rule_pack):
                        compatible_pairs.append((s, o))
                    elif observer:
                        observer.record_candidate_outcome(
                            sl, evidence, "TYPE_PRECHECK_IMPOSSIBLE", {
                                "subject": s.text, "subject_type": s.core_type.value,
                                "object": o.text, "object_type": o.core_type.value,
                                "evidence_class": evidence.evidence_class,
                                "binding_source": binding_source,
                                "kimi_v1": True})

            if not compatible_pairs:
                if observer:
                    observer.record_candidate_outcome(
                        sl, evidence, "TYPE_PRECHECK_NO_VIABLE_PAIR", {
                            "binding_source": binding_source,
                            "subjects": [s.text for s in subjects],
                            "objects": [o.text for o in objects],
                            "kimi_v1": True})
                continue

            # -- candidate creation with role annotation ---------------
            for subject_span, object_span in compatible_pairs:
                subject_id = _allocate(subject_span, sl, doc_id, corpus_id)
                object_id = _allocate(object_span, sl, doc_id, corpus_id)
                if observer:
                    observer.record_candidate_outcome(sl, evidence, "CANDIDATE_CREATED", {
                        "subject": subject_span.text, "object": object_span.text,
                        "binding_source": binding_source,
                        "roleset": _lexical.get("roleset"),
                        "kimi_v1": True})
                candidates.append(RelationCandidate(
                    sentence_text=sentence,
                    sentence_start=rel_start,
                    sentence_index=sl.sentence_index,
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


def _lookup_trigger_lemma(evidence: EvidenceSpan, sl: SentenceSlice) -> str | None:
    """Fallback trigger lemma from the evidence surface."""
    return evidence.text.split()[0].lower() if evidence.text else None


def active_pipeline() -> str:
    """legacy_v1 (positional binding + early type veto) or
    kimi_v1 (UD binding + post-structural type precheck)."""
    return os.environ.get("POLYMATH_RELATION_PIPELINE", "legacy_v1")


def build_candidates_dispatch(
    slices: list[SentenceSlice], **kwargs
) -> list[RelationCandidate]:
    """Dispatch to the active relation pipeline."""
    if active_pipeline() == "kimi_v1":
        return build_candidates_kimi(slices, **kwargs)
    from workers.candidates import build_candidates
    return build_candidates(slices, **kwargs)
