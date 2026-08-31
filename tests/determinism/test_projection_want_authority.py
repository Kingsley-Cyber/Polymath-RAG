"""WANT-SET-AUTHORITY-V1 pins: the F6 rule text exists ONCE, and every
consumer imports it (the three-copy drift wedged promotion 2026-08-31)."""
from __future__ import annotations

import pathlib

from polymath_shared.projection_want import chunk_tier_sql

ROOT = pathlib.Path(__file__).resolve().parents[2]

CONSUMERS = (
    "workers/workers/verify_worker.py",
    "control/control/census.py",
    "control/control/tickets.py",
)


def test_rule_values():
    assert chunk_tier_sql("qdrant") == "c.tier = 'child'"
    assert chunk_tier_sql("qdrant", "x") == "x.tier = 'child'"
    assert chunk_tier_sql("neo4j") == ""       # neo4j wants all tiers


def test_every_consumer_imports_the_authority():
    for rel in CONSUMERS:
        src = (ROOT / rel).read_text()
        assert "polymath_shared.projection_want" in src, (
            f"{rel} no longer imports the want-set authority")
        # NOTE: "c.tier = 'child'" may still appear for the
        # routing_child KIND (children by definition of that kind);
        # only the CHUNK-lane want-set is the authority's rule.
