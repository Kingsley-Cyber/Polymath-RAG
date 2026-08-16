"""semantic-query-policy-v1 contract: canonical ontology is durable,
model-facing vocabulary is versioned configuration. Raw provider labels
are preserved; canonical mapping is policy data; aliases require a new
versioned policy gate. Guards against provider wording leaking into
canonical semantics or hardcoded rescue branches."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.query_policy import (
    MODULES,
    QUERY_POLICY_VERSION,
    canonical_of,
    policy_identity,
    query_labels_for,
)


def test_policy_version_and_identity():
    assert QUERY_POLICY_VERSION == "semantic-query-policy-v1"
    identity = policy_identity()
    assert identity["query_policy_version"] == QUERY_POLICY_VERSION
    assert identity["aliases"] == {}  # v1 is deliberately identity


def test_v1_labels_are_identity_no_aliases():
    for core in ("Organization", "Technology", "Product", "Person"):
        assert query_labels_for(core) == (core,)


def test_canonical_of_maps_core_and_domain_labels():
    assert canonical_of("Organization") == "Organization"
    assert canonical_of("Library") == "Product"  # software_tech module label
    assert canonical_of("Brand") == "Organization"  # commerce module label
    assert canonical_of("NotALabel") is None  # never silently coerced


def test_domain_module_table_is_policy_data():
    # Domain labels live in the policy, not in compiler/worker code.
    assert "software_tech" in MODULES
    assert all(m.version for m in MODULES.values())


def test_extraction_manifest_carries_query_policy():
    from polymath_shared.contracts import ExtractionManifest

    manifest = ExtractionManifest(
        run_id="r", gliner_model="m", gliner_revision="rev",
        parser="p", parser_version="v", ontology_version="core-v1",
        rule_pack_version="1.2.0",
    )
    assert manifest.query_policy == QUERY_POLICY_VERSION


def test_entity_span_preserves_raw_label():
    from polymath_shared.contracts import CoreType, EntitySpan

    span = EntitySpan(
        doc_id="d", chunk_id="c", start=0, end=9, text="Crestline",
        core_type=CoreType.ORGANIZATION, score=0.9,
        extractor_version="gliner-2pass-v1",
    )
    assert span.raw_label is None and span.pass_kind == "discovery"
    typed = span.model_copy(update={"raw_label": "Company", "pass_kind": "boundary_rescue"})
    assert typed.core_type.value == "Organization"  # canonical never changes
    assert typed.raw_label == "Company"  # provider wording preserved


def test_no_provider_aliases_hardcoded_in_deterministic_code():
    """§1/§9 guard: the compiler and rescue code never branch on provider
    alias words. Provider wording belongs to the policy data alone."""
    import workers.rescue as rescue_module
    import polymath_shared.rulepack  # noqa: F401

    source = Path(rescue_module.__file__).read_text()
    for alias in ("Company", "Corporation", "Business"):
        assert alias not in source, f"provider alias {alias!r} hardcoded in rescue code"
