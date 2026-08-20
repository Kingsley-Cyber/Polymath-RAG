"""PropBank semantic-role assignment (KIMI-REALIGNMENT-COMPLETION-V1 Phase 3).

Bridges the compiled PropBank roleset argument inventory to actual
endpoint spans. The runtime assigns ARG0/ARG1/ARG2 based on:
- the selected roleset's argument inventory
- the UD dependency structure (voice-aware)
- the syntactic argument binding from kimi_v1

This module is deterministic, lookup-only (no model calls), and
accounts for active/passive voice so paraphrases converge.
"""
from __future__ import annotations

from typing import Any

# Map from syntactic relation to default PropBank role (active voice)
_ACTIVE_VOICE_MAP = {
    "nsubj": "ARG0",
    "nsubj:pass": None,  # handled by passive logic
    "dobj": "ARG1",
    "obj": "ARG1",
    "iobj": "ARG2",
}

# Map from syntactic relation to default PropBank role (passive voice)
_PASSIVE_VOICE_MAP = {
    "nsubj:pass": "ARG1",  # passive subject fills the patient role
    "agent": "ARG0",        # by-phrase agent fills the agent role
    "obl:agent": "ARG0",
    "dobj": "ARG1",
    "obj": "ARG1",
}


def get_role_inventory(lexical: dict, roleset: str | None) -> dict[str, str]:
    """Get the PropBank argument inventory for a roleset.

    Returns {role_label: gloss} from the compiled pb_arguments table.
    The compiled table stores numeric keys ('0', '1', ...) or already
    canonical ARG labels; normalize to ARG0/ARG1/ARG2.
    Example: use.01 -> {"ARG0": "user, agent", "ARG1": "thing used"}
    """
    if not lexical or not roleset:
        return {}
    pb_args = lexical.get("pb_arguments", {})
    roleset_args = pb_args.get(roleset, {})
    if not isinstance(roleset_args, dict):
        return {}
    normalized: dict[str, str] = {}
    for k, v in roleset_args.items():
        if k.isdigit():
            normalized[f"ARG{k}"] = str(v)
        elif k.startswith("ARG"):
            normalized[k] = str(v)
    return normalized


def assign_roles(
    roleset: str | None,
    role_inventory: dict[str, str],
    voice: str,
    subject_dep: str | None,
    object_dep: str | None,
    subject_entity: Any,
    object_entity: Any,
    agent_entity: Any | None = None,
) -> dict[str, Any]:
    """Assign PropBank semantic roles to endpoints.

    Voice-aware: active maps nsubj→ARG0, dobj→ARG1.
    Passive maps nsubj:pass→ARG1, agent→ARG0 (swapped from surface).

    Returns {"assigned": {role: entity}, "orientation": str,
             "ambiguous": bool, "unassigned_roles": [roles]}
    """
    assigned: dict[str, Any] = {}
    ambiguous = False
    unassigned: list[str] = []

    if not role_inventory:
        return {
            "assigned": {},
            "orientation": "no_roleset",
            "ambiguous": True,
            "unassigned_roles": [],
        }

    if voice == "passive":
        role_map = _PASSIVE_VOICE_MAP
        # passive: surface subject = patient (ARG1), agent = ARG0
        if subject_dep in ("nsubj:pass", "nsubj"):
            if agent_entity is not None or object_dep in ("agent", "obl:agent"):
                # "Acme was founded by John": surface subj=Acme(ARG1), agent=John(ARG0)
                if "ARG1" in role_inventory:
                    assigned["ARG1"] = subject_entity
                if "ARG0" in role_inventory:
                    assigned["ARG0"] = agent_entity if agent_entity is not None else object_entity
            else:
                # passive without explicit agent — assign what we can
                if subject_dep and "ARG1" in role_inventory:
                    assigned["ARG1"] = subject_entity
                if object_dep and "ARG1" in role_inventory and "ARG1" not in assigned:
                    assigned["ARG1"] = object_entity
                ambiguous = "ARG0" not in assigned
    else:
        # active (or unknown voice — default to active mapping)
        role_map = _ACTIVE_VOICE_MAP
        if subject_dep and subject_dep in role_map:
            role = role_map[subject_dep]
            if role and role in role_inventory:
                assigned[role] = subject_entity
        if object_dep and object_dep in role_map:
            role = role_map[object_dep]
            if role and role in role_inventory and role not in assigned:
                assigned[role] = object_entity
        # active with explicit agent (rare, e.g., causative) — map to ARG0
        if agent_entity is not None and "ARG0" in role_inventory and "ARG0" not in assigned:
            assigned["ARG0"] = agent_entity

    # identify unassigned required roles
    for role_label in role_inventory:
        if role_label.startswith("ARGM"):
            continue  # adjuncts are optional
        if role_label not in assigned:
            unassigned.append(role_label)

    # orientation: ARG0→ARG1 is canonical direction
    if "ARG0" in assigned and "ARG1" in assigned:
        orientation = "role_canonical"
    elif "ARG1" in assigned and voice == "passive":
        orientation = "passive_agent_elided"
    else:
        orientation = "incomplete"

    return {
        "assigned": assigned,
        "orientation": orientation,
        "ambiguous": ambiguous or bool(unassigned),
        "unassigned_roles": unassigned,
    }


def check_verbnet_compatibility(
    candidate_vn_classes: list[str],
    rule_vn_classes: list[str],
) -> str:
    """VN_CLASS_MATCH / VN_CLASS_MISMATCH / VN_UNAVAILABLE.

    The candidate carries VN classes from the compiled lexicon lookup.
    The rule cites VN classes. Overlap = converging evidence."""
    if not candidate_vn_classes or not rule_vn_classes:
        return "VN_UNAVAILABLE"
    if set(candidate_vn_classes) & set(rule_vn_classes):
        return "VN_CLASS_MATCH"
    return "VN_CLASS_MISMATCH"


def check_framenet_compatibility(
    candidate_fn_frames: list[str],
    rule_fn_frames: list[str],
) -> str:
    """FN_FRAME_MATCH / FN_FRAME_MISMATCH / FN_FRAME_UNAVAILABLE."""
    if not candidate_fn_frames or not rule_fn_frames:
        return "FN_FRAME_UNAVAILABLE"
    if set(candidate_fn_frames) & set(rule_fn_frames):
        return "FN_FRAME_MATCH"
    return "FN_FRAME_MISMATCH"


def check_semlink_consistency(
    roleset: str | None,
    vn_classes: list[str],
    fn_frames: list[str],
    semlink_pb_vn: dict,
) -> str:
    """SEMLINK_CONSISTENT / SEMLINK_CONFLICT / SEMLINK_UNAVAILABLE.

    When SemLink maps the roleset to VN/FN, check that the candidate's
    evidence aligns with at least one mapping."""
    if not roleset or not semlink_pb_vn:
        return "SEMLINK_UNAVAILABLE"
    mapped = semlink_pb_vn.get(roleset, [])
    if not mapped:
        return "SEMLINK_UNAVAILABLE"
    if vn_classes and set(mapped) & set(vn_classes):
        return "SEMLINK_CONSISTENT"
    if not vn_classes and not fn_frames:
        return "SEMLINK_UNAVAILABLE"
    # roleset has SemLink mappings but none match candidate's VN
    if vn_classes:
        return "SEMLINK_CONFLICT"
    return "SEMLINK_UNAVAILABLE"
