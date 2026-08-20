"""LexicalSemanticEvidence construction (KIMI Phase 8).

This module owns the deterministic transformation from the existing
pipeline evidence (EvidenceSpan, UD tokens, PropBank/VerbNet/FrameNet/
SemLink lookups, role assignment) into the single normalized compiler
input: LexicalSemanticEvidence.

The transformation is pure and deterministic: same inputs produce the
same evidence object, byte for byte.
"""
from __future__ import annotations

from typing import Any, Union

from polymath_shared.contracts import (
    ArgumentEndpoint,
    BindingSource,
    EntitySpan,
    EvidenceSpan,
    LexicalSemanticEvidence,
    SemanticRole,
)
from polymath_shared.rulepack.role_assignment import (
    check_framenet_compatibility,
    check_semlink_consistency,
    check_verbnet_compatibility,
    get_role_inventory,
)


def build_lexical_semantic_evidence(
    evidence: EvidenceSpan,
    subject: EntitySpan,
    object: EntitySpan,
    lexical: dict[str, Any],
    role_result: dict[str, Any],
    tokens: list[dict],
    trigger_head: dict | None,
    subj_dep: str | None,
    obj_dep: str | None,
    binding_source: str,
    rule_pack: dict,
) -> LexicalSemanticEvidence:
    """Normalize all existing Kimi evidence into one compiler input object.

    `lexical` is the output of `workers.candidates._lookup_for`.
    `role_result` is the output of `role_assignment.assign_roles`.
    `tokens` is the syntax-evidence-v1 token list for the sentence.
    `trigger_head` is the trigger's head token.
    """
    assigned = role_result.get("assigned", {})

    # Build argument endpoints with binding sources and roles.
    argument_endpoints: list[ArgumentEndpoint] = []
    endpoint_types: dict[str, str] = {}

    def _add_endpoint(span: EntitySpan, dep: str | None, role_label: str | None):
        role = SemanticRole(role_label) if role_label else None
        src = BindingSource(binding_source)
        if dep in ("pobj", "obl") and src == BindingSource.UD_DIRECT:
            src = BindingSource.UD_PREPOSITIONAL
        if src == BindingSource.UD_DIRECT and subj_dep == "nsubj:pass":
            src = BindingSource.UD_PASSIVE
        argument_endpoints.append(ArgumentEndpoint(
            entity_ref=getattr(span, "text", str(span)),
            surface=span.text,
            core_type=span.core_type.value,
            syntactic_path=dep or "unknown",
            binding_source=src,
            role=role,
        ))
        endpoint_types[role_label or dep or span.text] = span.core_type.value

    _add_endpoint(subject, subj_dep, next(
        (r for r, e in assigned.items() if getattr(e, "text", str(e)) == subject.text), None))
    _add_endpoint(object, obj_dep, next(
        (r for r, e in assigned.items() if getattr(e, "text", str(e)) == object.text), None))

    # Compute VN/FN/SemLink matches against applicable rules.
    applicable_rules = [
        rule for rule in rule_pack["predicates"].values()
        if evidence.evidence_class in rule["evidence"].get("classes", [])
    ]
    vn_matches: list[tuple[str, str]] = []
    fn_matches: list[tuple[str, str]] = []
    for rule in applicable_rules:
        vn_status = check_verbnet_compatibility(
            lexical.get("vn_classes", []),
            rule["evidence"].get("verbnet_classes", []))
        fn_status = check_framenet_compatibility(
            lexical.get("fn_frames", []),
            rule["evidence"].get("framenet_frames", []))
        if vn_status != "VN_UNAVAILABLE":
            vn_matches.append((rule["id"], vn_status))
        if fn_status != "FN_FRAME_UNAVAILABLE":
            fn_matches.append((rule["id"], fn_status))

    semlink_status = check_semlink_consistency(
        lexical.get("roleset"),
        lexical.get("vn_classes", []),
        lexical.get("fn_frames", []),
        lexical.get("semlink_pb_vn", {}),
    )

    assigned_roles = {
        r: getattr(e, "text", str(e))
        for r, e in assigned.items()
    }

    return LexicalSemanticEvidence(
        evidence_class=evidence.evidence_class,
        evidence_surface=evidence.text,
        evidence_start=evidence.start,
        evidence_end=evidence.end,
        trigger_surface=trigger_head["text"] if trigger_head else evidence.text,
        trigger_lemma=evidence.trigger_lemma,
        trigger_pos=trigger_head.get("pos") if trigger_head else None,
        voice=role_result.get("orientation", "active"),
        dependency_head=trigger_head,
        dependency_paths=[
            {"token": t["text"], "dep": t["dep"], "head": t.get("head_i")}
            for t in tokens if t.get("head_i") == (trigger_head or {}).get("i")
        ] if trigger_head and tokens else [],
        propbank_roleset=lexical.get("roleset"),
        propbank_role_inventory=get_role_inventory(lexical, lexical.get("roleset")),
        assigned_roles=assigned_roles,
        verbnet_classes=lexical.get("vn_classes", []),
        verbnet_matches=vn_matches,
        framenet_frames=lexical.get("fn_frames", []),
        framenet_matches=fn_matches,
        semlink_mapping=dict(lexical.get("semlink_pb_vn", {})),
        semlink_status=semlink_status,
        argument_endpoints=argument_endpoints,
        binding_sources=[BindingSource(binding_source)],
        endpoint_types=endpoint_types,
        lexical_resource_contract=rule_pack.get("resource_contract_id"),
        syntax_contract="syntax-evidence-v1",
        evidence_pass_contract=evidence.extractor_version,
    )
