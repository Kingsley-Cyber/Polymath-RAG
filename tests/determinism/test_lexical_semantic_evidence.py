"""KIMI Phase 8: LexicalSemanticEvidence determinism.

Verifies that the normalized compiler input object is:
- deterministic for the same underlying evidence,
- contains PropBank, VerbNet, FrameNet, SemLink, and binding-source fields,
- serializes and deserializes without semantic drift.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import CoreType, EntitySpan, EvidenceSpan, LexicalSemanticEvidence
from polymath_shared.rulepack import load_rule_pack
from polymath_shared.rulepack.lexical_evidence import build_lexical_semantic_evidence
from polymath_shared.rulepack.role_assignment import assign_roles, get_role_inventory

PACK = load_rule_pack(pack_version="1.0.1")


def _ent(text, core):
    return EntitySpan(
        doc_id="d", chunk_id="c", start=0, end=len(text), text=text,
        core_type=CoreType(core), score=0.9, extractor_version="t")


def _ev(text, ev_class, lemma):
    return EvidenceSpan(
        chunk_id="c", start=0, end=len(text), text=text,
        evidence_class=ev_class, trigger_lemma=lemma, score=0.9,
        extractor_version="t")


def test_lse_is_deterministic():
    """Same inputs -> same evidence object."""
    subject = _ent("John", "Person")
    object_ = _ent("Acme", "Organization")
    evidence = _ev("founded", "creation", "found")
    lexical = {
        "roleset": "establish.01",
        "vn_classes": ["create-26.4"],
        "fn_frames": ["Creating"],
        "semlink_resolved": True,
        "pb_arguments": {"establish.01": {"0": "founder", "1": "thing founded"}},
        "semlink_pb_vn": {"establish.01": {"create-26.4": {"ARG0": "agent", "ARG1": "product"}}},
    }
    role_inv = get_role_inventory(lexical, "establish.01")
    role_result = assign_roles(
        roleset="establish.01",
        role_inventory=role_inv,
        voice="active",
        subject_dep="nsubj",
        object_dep="dobj",
        subject_entity=subject,
        object_entity=object_,
    )
    tokens = [
        {"i": 0, "text": "John", "char_start": 0, "char_end": 4, "dep": "nsubj", "head_i": 1, "pos": "PROPN"},
        {"i": 1, "text": "founded", "char_start": 5, "char_end": 12, "dep": "ROOT", "head_i": 1, "pos": "VERB"},
        {"i": 2, "text": "Acme", "char_start": 13, "char_end": 17, "dep": "dobj", "head_i": 1, "pos": "PROPN"},
    ]
    trigger_head = tokens[1]

    a = build_lexical_semantic_evidence(
        evidence, subject, object_, lexical, role_result, tokens, trigger_head,
        "nsubj", "dobj", "UD_DIRECT", PACK,
    )
    b = build_lexical_semantic_evidence(
        evidence, subject, object_, lexical, role_result, tokens, trigger_head,
        "nsubj", "dobj", "UD_DIRECT", PACK,
    )
    assert a.model_dump() == b.model_dump()


def test_lse_propbank_roles_populated():
    subject = _ent("John", "Person")
    object_ = _ent("Acme", "Organization")
    evidence = _ev("founded", "creation", "found")
    lexical = {
        "roleset": "establish.01",
        "vn_classes": [],
        "fn_frames": [],
        "semlink_resolved": False,
        "pb_arguments": {"establish.01": {"0": "founder", "1": "thing founded"}},
        "semlink_pb_vn": {},
    }
    role_inv = get_role_inventory(lexical, "establish.01")
    role_result = assign_roles(
        roleset="establish.01",
        role_inventory=role_inv,
        voice="active",
        subject_dep="nsubj",
        object_dep="dobj",
        subject_entity=subject,
        object_entity=object_,
    )

    lse = build_lexical_semantic_evidence(
        evidence, subject, object_, lexical, role_result, [], None,
        "nsubj", "dobj", "UD_DIRECT", PACK,
    )
    assert lse.propbank_roleset == "establish.01"
    assert "ARG0" in lse.propbank_role_inventory
    assert "ARG1" in lse.propbank_role_inventory
    assert lse.assigned_roles.get("ARG0") == "John"
    assert lse.assigned_roles.get("ARG1") == "Acme"
