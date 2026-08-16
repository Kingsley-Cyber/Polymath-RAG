"""E3B deterministic endpoint-binding guards (relation-general).

GLiNER PROPOSES. DETERMINISTIC CODE DECIDES. These guards tighten the
compiler's relation admission WITHOUT a new learned model:

  1. predicate endpoint-type families (has_role / instance_of / owns)
  2. surface-weak trigger locality (trigger between endpoints,
     sentence-local attachment)
  3. title/body pairing restriction (a heading entity cannot pair
     with body text outside its own heading line)
  4. coordination-aware binding (endpoints and trigger must share
     one coordinated clause)

No name blacklists; no hardcoded entities; no ontology changes.
has_role object family maps to concept-like core types because the
ontology has no Role type — recorded as a documented family mapping
(ONTOLOGY_UNREPRESENTABLE only where no family exists at all).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Optional

BINDING_GATES_VERSION = "endpoint-binding-v1"

_CLASS_LIKE = {"Concept", "Process", "Method", "Technology", "Measurement", "Event"}
_OWNER_LIKE = {"Person", "Organization"}
_OWNABLE = {"Organization", "Product", "Technology", "Document", "Location", "Concept"}

_SURFACE_WEAK_MAX_ENDPOINT_DISTANCE = 100

_COORDINATION_SPLIT_RE = re.compile(r",\s+while\s+|,\s+but\s+|;\s+")

_PREDICATE_FAMILIES: dict[str, tuple[set[str], set[str]]] = {
    "has_role": ({"Person"}, _CLASS_LIKE),
    "instance_of": (None, _CLASS_LIKE),
    "owns": (_OWNER_LIKE, _OWNABLE),
}


@dataclass(frozen=True)
class BindingVerdict:
    ok: bool
    reason: str


def predicate_endpoint_types_ok(predicate: str, subject_type: str,
                                object_type: str) -> BindingVerdict:
    family = _PREDICATE_FAMILIES.get(predicate)
    if family is None:
        return BindingVerdict(True, "no_type_family_defined")
    subj_family, obj_family = family
    if subj_family is not None and subject_type not in subj_family:
        return BindingVerdict(False, f"{predicate}: subject {subject_type} not owner-like")
    if object_type not in obj_family:
        return BindingVerdict(False, f"{predicate}: object {object_type} not role/class/ownable-like")
    return BindingVerdict(True, "type_family_ok")


def surface_weak_locality_ok(trigger_start: int, trigger_end: int,
                             subject_start: int, subject_end: int,
                             object_start: int, object_end: int) -> BindingVerdict:
    """Trigger must lie between the endpoints and both endpoints must be
    sentence-local to the trigger (no cross-sentence surface pairing)."""
    lo = min(subject_start, object_start)
    hi = max(subject_end, object_end)
    if not (lo <= trigger_start <= hi or lo <= trigger_end <= hi):
        return BindingVerdict(False, "trigger_outside_endpoint_span")
    if (trigger_start - subject_end) > _SURFACE_WEAK_MAX_ENDPOINT_DISTANCE and \
            (trigger_start - object_end) > _SURFACE_WEAK_MAX_ENDPOINT_DISTANCE:
        return BindingVerdict(False, "endpoints_not_local_to_trigger")
    return BindingVerdict(True, "locality_ok")


def title_pairing_ok(chunk_text: str, subject_text: str, subject_start: int,
                     object_text: str, object_start: int,
                     chunk_char_start: int = 0) -> BindingVerdict:
    """A heading-line entity cannot pair with body text outside its own
    heading line (title-as-entity wrong-edge family)."""
    lines = chunk_text.splitlines()
    heading_lines: list[tuple[int, int, str]] = []  # (start, end, text)
    pos = 0
    for line in lines:
        stripped = line.strip()
        is_heading = stripped.startswith("#") or stripped.upper().startswith("TITLE:")
        if is_heading and stripped:
            heading_lines.append((pos, pos + len(line), stripped))
        pos += len(line) + 1

    def in_heading(text: str, start: int) -> Optional[int]:
        for i, (hs, he, htext) in enumerate(heading_lines):
            if hs <= start < he and text.strip() in htext:
                return i
        return None

    s_head = in_heading(subject_text, subject_start)
    o_head = in_heading(object_text, object_start)
    if s_head is not None and o_head is None:
        return BindingVerdict(False, "title_subject_paired_with_body")
    if o_head is not None and s_head is None:
        return BindingVerdict(False, "title_object_paired_with_body")
    return BindingVerdict(True, "title_pairing_ok")


def coordination_aware_ok(sentence_text: str, trigger_start: int,
                          subject_start: int, subject_end: int,
                          object_start: int, object_end: int) -> BindingVerdict:
    """Trigger and both endpoints must share one coordinated clause."""
    matches = list(_COORDINATION_SPLIT_RE.finditer(sentence_text))
    if not matches:
        return BindingVerdict(True, "single_clause")
    segment_bounds: list[tuple[int, int]] = []
    cursor = 0
    for m in matches:
        segment_bounds.append((cursor, m.start()))
        cursor = m.end()
    segment_bounds.append((cursor, len(sentence_text)))

    def seg_of(start: int, end: int) -> Optional[int]:
        for i, (bs, be) in enumerate(segment_bounds):
            if bs <= start < be:
                return i
        return None

    t_seg = seg_of(trigger_start, trigger_start)
    s_seg = seg_of(subject_start, subject_end)
    o_seg = seg_of(object_start, object_end)
    if t_seg is None:
        return BindingVerdict(True, "trigger_unlocated")
    if s_seg != t_seg or o_seg != t_seg:
        return BindingVerdict(False, "endpoints_outside_trigger_clause")
    return BindingVerdict(True, "clause_ok")


def binding_gate_violation(
    rule: dict,
    subject_type: str,
    object_type: str,
    orientation: str,
    candidate: Any,
    agent_cand: Any,
    patient_cand: Any,
) -> Optional[str]:
    """All E3B gates; returns a rejection reason or None.

    Design grounded in the FROZEN rule pack:
      has_role   = person holds a role IN AN ORGANIZATION — requires the
                   trigger to be the rule's own role inventory (verbs/
                   nouns/multiword). Surface pairings with arbitrary
                   triggers ("working through", "assigned") are rejected.
      owns       = 'control' lemma is ambiguous (noun/verb); under
                   surface_weak it cannot authorize possession.
      instance_of= an Organization object requires the specific
                   multiword phrasing, never a bare 'be'.
      title/body, coordination, and surface-weak locality gates apply
      on top (relation-general)."""
    ev = candidate.evidence
    subj_span = agent_cand.span
    obj_span = patient_cand.span
    pid = rule["id"]
    inventory = rule.get("evidence") or {}

    def trigger_in_inventory() -> bool:
        surface = (ev.text or "").strip().lower()
        lemma = (ev.trigger_lemma or "").strip().lower()
        verbs = {v.lower() for v in inventory.get("verbs", [])}
        nouns = {n.lower() for n in inventory.get("nouns", [])}
        multi = {m.lower() for m in inventory.get("multiword", [])}
        if any(surface == m or m in surface or surface in m for m in multi):
            return True
        if lemma in verbs:
            return True
        if any(surface == n or n in surface for n in nouns):
            return True
        return False

    if pid == "has_role":
        if not trigger_in_inventory():
            return "binding:has_role trigger not in role inventory"
        if orientation == "surface_weak":
            # bare noun triggers ("engineer", "manager") do not authorize
            # a role edge without syntactic attachment — verb or
            # multiword triggers only (CEO of / works for / serves).
            surface = (ev.text or "").strip().lower()
            lemma = (ev.trigger_lemma or "").strip().lower()
            verbs = {v.lower() for v in inventory.get("verbs", [])}
            multi = {m.lower() for m in inventory.get("multiword", [])}
            if lemma not in verbs and not any(
                    surface == m or m in surface or surface in m for m in multi):
                return "binding:has_role noun trigger requires syntactic attachment"
    elif pid == "owns":
        if (ev.trigger_lemma or "").strip().lower() == "control" \
                and orientation == "surface_weak":
            return "binding:owns control-trigger requires syntactic attachment"
    elif pid == "instance_of" and object_type == "Organization":
        multi = {m.lower() for m in inventory.get("multiword", [])}
        surface = (ev.text or "").strip().lower()
        if not any(surface == m or m in surface or surface in m for m in multi):
            return "binding:instance_of org-object requires specific instance phrasing"

    sentence_text = getattr(candidate, "sentence_text", None) or ""
    sentence_start = getattr(candidate, "sentence_start", 0)

    if sentence_text:
        rel_s = max(0, subj_span.start - sentence_start)
        rel_o = max(0, obj_span.start - sentence_start)
        rel_t = max(0, ev.start - sentence_start)
        tv = title_pairing_ok(
            sentence_text, subj_span.text, rel_s,
            obj_span.text, rel_o,
        )
        if not tv.ok:
            return f"binding:{tv.reason}"
        cv = coordination_aware_ok(
            sentence_text, rel_t, rel_s, rel_s + max(0, subj_span.end - subj_span.start),
            rel_o, rel_o + max(0, obj_span.end - obj_span.start),
        )
        if not cv.ok:
            return f"binding:{cv.reason}"

    if orientation == "surface_weak":
        lv = surface_weak_locality_ok(
            max(0, ev.start - sentence_start), max(0, ev.end - sentence_start),
            max(0, subj_span.start - sentence_start), max(0, subj_span.end - sentence_start),
            max(0, obj_span.start - sentence_start), max(0, obj_span.end - sentence_start),
        )
        if not lv.ok:
            return f"binding:{lv.reason}"
    return None
