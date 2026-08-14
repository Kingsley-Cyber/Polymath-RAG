"""Canonical hashing: key order must not change the hash."""
from __future__ import annotations

import sys
from pathlib import Path


def test_canonicalize_is_key_order_invariant(repo_root: Path) -> None:
    sys.path.insert(0, str(repo_root / "shared"))
    from polymath_shared.identity import content_hash

    a = content_hash({"a": 1, "b": 2, "c": 3})
    b = content_hash({"c": 3, "a": 1, "b": 2})
    assert a == b


def test_unicode_normalization_is_stable(repo_root: Path) -> None:
    sys.path.insert(0, str(repo_root / "shared"))
    from polymath_shared.identity import content_hash

    # Same string, same hash.
    a = content_hash({"name": "café"})
    b = content_hash({"name": "café"})
    assert a == b
