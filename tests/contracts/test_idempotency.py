"""Re-running the same content produces the same IDs."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def test_fact_id_is_deterministic(repo_root: Path) -> None:
    sys.path.insert(0, str(repo_root / "shared"))
    from polymath_shared.identity import fact_id

    a = fact_id("FOUNDED", "ent_alice", "ent_acme", {"valid_from": "2012"})
    b = fact_id("FOUNDED", "ent_alice", "ent_acme", {"valid_from": "2012"})
    assert a == b


def test_fact_id_changes_with_qualifier(repo_root: Path) -> None:
    sys.path.insert(0, str(repo_root / "shared"))
    from polymath_shared.identity import fact_id

    a = fact_id("FOUNDED", "ent_alice", "ent_acme", {"valid_from": "2012"})
    b = fact_id("FOUNDED", "ent_alice", "ent_acme", {"valid_from": "2013"})
    assert a != b
