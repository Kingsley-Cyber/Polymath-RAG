"""DOCUMENT-SEMANTIC-INDEX-V1 — vNext global-profile prompt (§18).

Pins the additive vNext profile request: it carries the source-anchored + routing-
inferred field contract (including the new research-index tags), consumes the
DocumentFingerprint block, and keeps its field vocabulary in sync with `fingerprint`
(the single source of truth). Pure — no model, no I/O. The live prompt.py/compiler.py
are untouched (this is a separate module).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import profile_prompt_vnext as PP  # noqa: E402
from polymath_shared.document_profile import fingerprint as FP  # noqa: E402


def _fingerprint():
    parents = [
        {"chunk_id": f"pp-{i}", "chunk_index": i, "char_start": i * 1000,
         "heading_path": [f"Chapter {i + 1}"],
         "text": f"Section {i} introduces ZZTOPIC{i} within the adaptive control framework and its feedback effects.",
         "region_role": "body"}
        for i in range(6)
    ]
    return FP.build_fingerprint({"source_name": "Adaptive Control.pdf",
                                 "frontmatter": {"title": "Adaptive Control"}}, parents, budget_tokens=1500)


def test_system_lists_all_fields_including_research_tags():
    s = PP.SYSTEM
    for label in FP.SOURCE_ANCHORED_FIELDS:
        assert f"{label}:" in s
    for label in FP.ROUTING_INFERRED_FIELDS:
        assert f"{label}:" in s
    for tag in FP.RESEARCH_INDEX_TAGS:              # the new research-index surfaces
        assert f"{tag}:" in s
    assert "LATENT-PATTERN:" in s                    # distinct hyphenated label
    assert "routing hypotheses" in s and "never cited as evidence" in s


def test_user_prompt_consumes_the_fingerprint_block():
    fp = _fingerprint()
    system, user = PP.build_vnext_profile_prompt(fp)
    assert system == PP.SYSTEM
    assert "DOCUMENT" in user
    # the fingerprint's own surfaces appear (identity + a coverage marker)
    assert "Adaptive Control" in user
    assert "ZZTOPIC0" in user or "ZZTOPIC5" in user


def test_output_fields_match_fingerprint_vocabulary():
    fields = PP.output_fields()
    assert fields == FP.SOURCE_ANCHORED_FIELDS + FP.ROUTING_INFERRED_FIELDS
    assert set(FP.RESEARCH_INDEX_TAGS).issubset(set(fields))
    assert not (set(FP.SOURCE_ANCHORED_FIELDS) & set(FP.ROUTING_INFERRED_FIELDS))


def test_deterministic_and_empty_safe():
    fp = _fingerprint()
    assert PP.build_vnext_profile_prompt(fp) == PP.build_vnext_profile_prompt(fp)
    assert "(no document evidence)" in PP.build_vnext_profile_user_prompt("")
