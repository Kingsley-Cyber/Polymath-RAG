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

from polymath_shared.contracts import BindingSource, EntitySpan, EvidenceSpan
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
from polymath_shared.rulepack.role_assignment import (
    assign_roles,
    get_role_inventory,
)
from polymath_shared.rulepack.lexical_evidence import build_lexical_semantic_evidence

# spaCy ClearNLP + UD dependency relations that fill predicate argument slots
SUBJECT_DEPS = frozenset({"nsubj", "nsubj:pass"})
OBJECT_DEPS = frozenset({"dobj", "obj", "iobj"})
OBLIQUE_DEPS = frozenset({"obl", "obl:agent", "obl:tmod"})
PREP_DEPS = frozenset({"prep", "agent"})
AGENT_OBJECT_DEPS = frozenset({"pobj", "obl"})


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
            elif tok["dep"] in PREP_DEPS:
                # preposition / agent → look for pobj/obl under it
                for child in tokens:
                    if child["head_i"] == tok["i"] and child["dep"] in AGENT_OBJECT_DEPS:
                        args["prep_object"].append(child)
            elif tok["dep"] in OBLIQUE_DEPS:
                args["oblique"].append(tok)

    # coordination: conj dependents of subject/object heads
    for role_toks in (args["subject"], args["object"]):
        for head_tok in list(role_toks):
            for tok in tokens:
                if tok["head_i"] == head_tok["i"] and tok["dep"] == "conj":
                    role_toks.append(tok)

    # Propagate shared arguments from a governing predicate to a conjunct
    # predicate.  If the trigger head is a conjunct of another predicate,
    # and the conjunct lacks a subject/object, borrow the governor's subject
    # or object.  This handles "John founded Acme and later joined Beta"
    # where 'joined' shares the subject 'John' with 'founded'.
    for tok in tokens:
        if tok["head_i"] == trig_idx and tok["dep"] == "conj":
            args["coordination"].append(tok)
    _propagate_shared_arguments(tokens, trig_idx, args)

    return args


def _propagate_shared_arguments(
    tokens: list[dict], trig_idx: int, args: dict[str, list[dict]]
) -> None:
    """Fill missing subject/object slots of a conjunct from its governor.

    Walks up one step on a `conj` edge and copies the governor's nsubj/dobj
    when the conjunct lacks them.  Only fills truly empty slots so the
    conjunct's own explicit arguments are never overwritten.
    """
    trigger_tok = next((t for t in tokens if t["i"] == trig_idx), None)
    if trigger_tok is None:
        return
    if trigger_tok.get("dep") != "conj":
        return
    governor_idx = trigger_tok.get("head_i")
    if governor_idx is None:
        return

    governor_args: dict[str, list[dict]] = {
        "subject": [],
        "object": [],
    }
    for tok in tokens:
        if tok["head_i"] == governor_idx:
            if tok["dep"] in SUBJECT_DEPS:
                governor_args["subject"].append(tok)
            elif tok["dep"] in OBJECT_DEPS:
                governor_args["object"].append(tok)

    if not args["subject"] and governor_args["subject"]:
        args["subject"].extend(governor_args["subject"])
    if not args["object"] and governor_args["object"]:
        args["object"].extend(governor_args["object"])


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
    identities: dict | None = None,
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
            oblique_spans: list[EntitySpan] = []
            # Reset per evidence. Python loop variables outlive their
            # block, so without this a trigger in a sentence with no
            # tokens would silently reuse the PREVIOUS sentence's head.
            trig_head = None
            binding_source = BindingSource.BOUNDED_LINEAR_RECALL

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
                            oblique_spans.append(ent)

                    if subjects or objects:
                        binding_source = BindingSource.UD_DIRECT

                    # -- Phase 5: record what the UD tree itself bound,
                    # BEFORE any recall net runs, so the trace separates
                    # "the tree found it" from "the window found it".
                    if observer:
                        for slot, bound, code in (
                            ("subject", subjects, "UD_SUBJECT_BOUND"),
                            ("object", objects, "UD_OBJECT_BOUND"),
                        ):
                            observer.record_candidate_outcome(
                                sl, evidence,
                                code if bound else "UD_NO_ARGUMENT_IN_SLOT",
                                {"slot": slot,
                                 "spans": [e.text for e in bound],
                                 "binding_source": binding_source,
                                 "kimi_v1": True})
                        if oblique_spans:
                            observer.record_candidate_outcome(
                                sl, evidence, "UD_OBLIQUE_BOUND", {
                                    "slot": "oblique",
                                    "spans": [e.text for e in oblique_spans],
                                    "binding_source": binding_source,
                                    "kimi_v1": True})
                elif observer:
                    observer.record_candidate_outcome(
                        sl, evidence, "UD_NO_ARGUMENT_IN_SLOT", {
                            "slot": "trigger_head",
                            "binding_source": binding_source,
                            "kimi_v1": True})

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
                    binding_source = BindingSource.BOUNDED_LINEAR_RECALL

            if not objects:
                right_entities = sorted(
                    [e for e in sl.entities
                     if e.start >= evidence.end and e.start - rel_start <= right_bound],
                    key=lambda e: (e.start, e.end),
                )
                if right_entities:
                    objects = [right_entities[0]]
                    binding_source = BindingSource.BOUNDED_LINEAR_RECALL

            # -- definite description recall (subject slot) ------------
            if not subjects and objects and doc_entities_history:
                resolved = _resolve_definite_description(
                    sentence, rel_ev_start, left_bound, doc_entities_history)
                if resolved is not None:
                    subjects = [resolved]
                    binding_source = BindingSource.SAFE_LOCAL_PATTERN

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
            # Kimi-corrected position: cheap evidence-class signature-union
            # filter on already-bound argument pairs. Because role-based
            # direction may invert passive pairs, a pair is viable if EITHER
            # orientation can satisfy a signature of the evidence class.
            compatible_pairs: list[tuple[EntitySpan, EntitySpan]] = []
            is_frame = (getattr(evidence, "trigger_lexical_class", "")
                        or "").upper() == "FRAME"
            for s in subjects:
                for o in objects:
                    if s.text == o.text and s.core_type == o.core_type:
                        continue
                    if is_frame:
                        # PREDICATE-COMPILER-V2: frame spans skip the
                        # rule-pack class signature precheck — the
                        # ontology signature validation at compile time
                        # is the authority (fail-closed there).
                        compatible_pairs.append((s, o))
                        continue
                    forward_ok = _type_compatible(
                        s.core_type.value, o.core_type.value,
                        evidence.evidence_class, rule_pack)
                    reverse_ok = _type_compatible(
                        o.core_type.value, s.core_type.value,
                        evidence.evidence_class, rule_pack)
                    if forward_ok or reverse_ok:
                        compatible_pairs.append((s, o))
                        if observer:
                            observer.record_candidate_outcome(
                                sl, evidence, "TYPE_PRECHECK_PASS", {
                                    "subject": s.text, "subject_type": s.core_type.value,
                                    "object": o.text, "object_type": o.core_type.value,
                                    "evidence_class": evidence.evidence_class,
                                    "orientation": ("forward" if forward_ok else "reverse"),
                                    "binding_source": binding_source,
                                    "kimi_v1": True})
                    elif observer:
                        # Plan Phase 5 names this TYPE_PRECHECK_FAIL. The
                        # older TYPE_PRECHECK_IMPOSSIBLE stays registered in
                        # ALL_CODES so traces recorded before this gate still
                        # validate, but is no longer emitted.
                        observer.record_candidate_outcome(
                            sl, evidence, "TYPE_PRECHECK_FAIL", {
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
                subject_id = _allocate(subject_span, sl, doc_id, corpus_id,
                                       identities)
                object_id = _allocate(object_span, sl, doc_id, corpus_id,
                                      identities)
                if observer:
                    observer.record_candidate_outcome(sl, evidence, "CANDIDATE_CREATED", {
                        "subject": subject_span.text, "object": object_span.text,
                        "binding_source": binding_source,
                        "roleset": _lexical.get("roleset"),
                        "kimi_v1": True})
                # -- PropBank semantic-role assignment (Phase 3) -----
                role_inv = get_role_inventory(_lexical, _lexical.get("roleset"))
                voice = "passive" if (sl.parse or {}).get("voice") == "passive" else "active"
                subj_dep = None
                obj_dep = None
                agent_span: Any | None = None
                if tokens and trig_head is not None:
                    for tok in tokens:
                        if tok["head_i"] == trig_head["i"]:
                            if tok["dep"] in SUBJECT_DEPS:
                                subj_dep = tok["dep"]
                            elif tok["dep"] in OBJECT_DEPS:
                                obj_dep = tok["dep"]
                            elif tok["dep"] in PREP_DEPS:
                                # agent preposition: find its object
                                for child in tokens:
                                    if (child["head_i"] == tok["i"]
                                            and child["dep"] in AGENT_OBJECT_DEPS):
                                        agent_span = _token_to_entity(child, sl.entities, sl)

                role_result = assign_roles(
                    roleset=_lexical.get("roleset"),
                    role_inventory=role_inv,
                    voice=voice,
                    subject_dep=subj_dep,
                    object_dep=obj_dep,
                    subject_entity=subject_span,
                    object_entity=object_span,
                    agent_entity=agent_span,
                )

                # -- Phase 8: normalized lexical-semantic evidence object ----
                lse = build_lexical_semantic_evidence(
                    evidence=evidence,
                    subject=subject_span,
                    object=object_span,
                    lexical=_lexical,
                    role_result=role_result,
                    tokens=tokens,
                    trigger_head=trig_head,
                    subj_dep=subj_dep,
                    obj_dep=obj_dep,
                    binding_source=binding_source,
                    rule_pack=rule_pack,
                )

                if observer:
                    observer.record_candidate_outcome(sl, evidence, "ROLE_ASSIGNED", {
                        "subject": subject_span.text, "object": object_span.text,
                        "roleset": _lexical.get("roleset"),
                        "role_inventory": role_inv,
                        "assigned_roles": {r: getattr(e, 'text', str(e))
                                           for r, e in role_result["assigned"].items()},
                        "voice": voice,
                        "orientation": role_result["orientation"],
                        "subj_dep": subj_dep, "obj_dep": obj_dep,
                        "vn_matches": lse.verbnet_matches[:3],
                        "fn_matches": lse.framenet_matches[:3],
                        "semlink_status": lse.semlink_status,
                        "binding_source": binding_source,
                        "kimi_v1": True})

                # -- Phase 5: one event per role actually assigned, so a
                # trace can answer "which endpoint became ARG0?" without
                # re-deriving it from the summary event's detail blob.
                if observer:
                    for role_label in ("ARG0", "ARG1", "ARG2"):
                        bound = role_result["assigned"].get(role_label)
                        if bound is None:
                            continue
                        observer.record_candidate_outcome(
                            sl, evidence, f"ROLE_{role_label}_ASSIGNED", {
                                "role": role_label,
                                "entity": getattr(bound, "text", str(bound)),
                                "roleset": _lexical.get("roleset"),
                                "voice": voice,
                                "syntactic_path": _role_path(
                                    bound, subject_span, object_span,
                                    agent_span, subj_dep, obj_dep),
                                "binding_source": binding_source,
                                "kimi_v1": True})
                    if role_result["orientation"] == "no_roleset":
                        observer.record_candidate_outcome(
                            sl, evidence, "ROLE_NO_ROLESET", {
                                "trigger_lemma": evidence.trigger_lemma,
                                "binding_source": binding_source,
                                "kimi_v1": True})
                    elif role_result["orientation"] == "incomplete":
                        observer.record_candidate_outcome(
                            sl, evidence, "ROLE_ORIENTATION_INCOMPLETE", {
                                "roleset": _lexical.get("roleset"),
                                "assigned": sorted(role_result["assigned"]),
                                "unassigned_roles": role_result["unassigned_roles"],
                                "binding_source": binding_source,
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
                    semlink_mapping={
                        "roleset": _lexical.get("roleset"),
                        "vn_classes": _lexical.get("vn_classes", []),
                        "fn_frames": _lexical.get("fn_frames", []),
                        "semlink_pb_vn": _lexical.get("semlink_pb_vn", {}),
                    },
                    scope=scope,
                    ontology_profile=ontology_profile,
                    assigned_roles=role_result["assigned"],
                    lexical_semantic_evidence=lse,
                ))

    return candidates


def _lookup_trigger_lemma(evidence: EvidenceSpan, sl: SentenceSlice) -> str | None:
    """Fallback trigger lemma from the evidence surface."""
    return evidence.text.split()[0].lower() if evidence.text else None


def _role_path(bound, subject_span, object_span, agent_span,
               subj_dep, obj_dep) -> str | None:
    """Name the dependency that actually supplied this role.

    Role label alone is not enough: under passive voice ARG0 comes from
    the by-agent and ARG1 from the surface subject, so keying the path off
    "ARG0 -> subj_dep" would mislabel every passive."""
    if agent_span is not None and bound is agent_span:
        return "agent"
    if bound is subject_span:
        return subj_dep
    if bound is object_span:
        return obj_dep
    return None


def active_pipeline() -> str:
    """legacy_v1 (positional binding + early type veto),
    kimi_v1 (UD binding + post-structural type precheck), or
    kimi_v2 (token-originated, UD-only binding — no recall nets)."""
    return os.environ.get("POLYMATH_RELATION_PIPELINE", "legacy_v1")


def build_candidates_dispatch(
    slices: list[SentenceSlice], **kwargs
) -> list[RelationCandidate]:
    """Dispatch to the active relation pipeline."""
    if active_pipeline() == "kimi_v2":
        from workers.kimi_v2_candidates import build_candidates_kimi_v2
        return build_candidates_kimi_v2(slices, **kwargs)
    if active_pipeline() == "kimi_v1":
        return build_candidates_kimi(slices, **kwargs)
    from workers.candidates import build_candidates
    return build_candidates(slices, **kwargs)
