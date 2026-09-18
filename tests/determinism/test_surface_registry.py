"""CANONICAL-SURFACE-REGISTRY-V1 (P4a) — the single source for typed-surface treatment.
Behaviour-preservation: the registry-derived tuples must EXACTLY equal the historical
literals the three definition sites used, and every consumer must now read from it."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import surface_registry as R  # noqa: E402
from polymath_shared.document_profile import profile_atom as A  # noqa: E402
from polymath_shared.document_profile import projection as PJ  # noqa: E402


def test_derived_tuples_match_the_historical_literals():
    assert R.DENSE_SURFACES == ("title", "identity", "theme")
    assert R.MULTI_SURFACES == ("questions", "searches", "theories", "concepts", "seealso")
    assert R.ATOM_KINDS == ("THEORY", "CONCEPT", "LATENT_PATTERN", "BOUNDARY", "SEEALSO",
                            "BRIDGE", "ANCHOR", "TENSION", "INVERSION", "RECALLQ")
    assert R.MECHANISM_KINDS == ("THEORY", "CONCEPT", "LATENT_PATTERN", "BOUNDARY")
    assert R.RELATIONAL_KINDS == ("SEEALSO", "BRIDGE", "ANCHOR", "TENSION", "INVERSION")
    assert R.REDISCOVERY_KINDS == ("RECALLQ",)
    assert R.ATTR_TO_KIND == {
        "theories": "THEORY", "concepts": "CONCEPT", "latent_pattern": "LATENT_PATTERN",
        "boundary": "BOUNDARY", "seealso": "SEEALSO", "bridge": "BRIDGE", "anchor": "ANCHOR",
        "tension": "TENSION", "inversion": "INVERSION", "recallq": "RECALLQ"}


def test_every_consumer_reads_from_the_registry():
    assert A.ATOM_KINDS is R.ATOM_KINDS and A.MECHANISM_KINDS is R.MECHANISM_KINDS
    assert A.RELATIONAL_KINDS is R.RELATIONAL_KINDS and A.REDISCOVERY_KINDS is R.REDISCOVERY_KINDS
    assert PJ.DENSE_SURFACES is R.DENSE_SURFACES and PJ.MULTI_SURFACES is R.MULTI_SURFACES
    # query_intent imports MECHANISM_KINDS as _MECH / ATOM_KINDS as _ALL_ATOMS
    from polymath_shared import query_intent as QI
    assert QI._MECH == R.MECHANISM_KINDS and QI._ALL_ATOMS == R.ATOM_KINDS


def test_graph_policy_is_resolve_on_use_only_for_discovery_relations_never_a_text_edge():
    assert R.GRAPH_RESOLVABLE_KINDS == ("SEEALSO", "BRIDGE", "TENSION")
    assert R.graph_policy("SEEALSO") == "resolve_on_use" and R.graph_policy("THEORY") == "off"
    assert R.graph_policy("unknown") == "off"                      # default: never a direct edge
    # every atom kind has an explicit policy; nothing defaults to minting an edge
    for k in R.ATOM_KINDS:
        assert R.graph_policy(k) in ("off", "resolve_on_use")


def test_semantic_groups_expose_scout_and_mode_surface_material():
    assert R.group_surfaces("direct") == ("questions", "searches", "recallq")
    assert set(R.group_surfaces("discovery")) == {"latent_pattern", "boundary", "seealso", "bridge", "tension", "inversion"}
    assert R.group_surfaces("identity") == ("title", "identity")
