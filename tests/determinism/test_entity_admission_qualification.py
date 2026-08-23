"""ENTITY-ADMISSION-QUALIFICATION — owner-mandated checkpoint.

Gates P2+ progression. If this fails, everything downstream is stopped,
because relation quality depends on identity quality. Inputs and
expected outcomes are the owner's, verbatim.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.scientific_concept import (  # noqa: E402
    named_concept_evidence,
)

MUST_ACCEPT = ["Tree of Thoughts", "GPT-4", "March 2023", "Version 3.8"]
MUST_REJECT = ["state", "thought"]


def test_qualification_accepts_named_scientific_surfaces():
    refused = [s for s in MUST_ACCEPT if named_concept_evidence(s) is None]
    assert not refused, (
        f"Entity admission qualification FAILED: {refused} must be accepted "
        "as durable scientific entities. Downstream phases stay blocked "
        "until identity quality holds.")


def test_qualification_rejects_bare_generic_nouns():
    leaked = [s for s in MUST_REJECT if named_concept_evidence(s) is not None]
    assert not leaked, (
        f"Entity admission qualification FAILED: {leaked} are bare generic "
        "nouns and must not become durable entities.")


def test_version_and_temporal_identity_patterns():
    r = named_concept_evidence("Version 3.8")
    assert r["pattern"] == "version_identity"
    r = named_concept_evidence("March 2023")
    assert r["pattern"] == "date_expression"
    r = named_concept_evidence("Qwen3-Embedding-0.6B")
    assert r is not None and r["pattern"] == "versioned_compound"
