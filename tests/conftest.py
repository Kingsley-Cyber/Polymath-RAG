"""Shared pytest fixtures and environment-sensitive test gates."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def shared_on_path(repo_root: Path) -> None:
    p = repo_root / "shared"
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def pytest_collection_modifyitems(config, items) -> None:
    """Skip only the source-archive rebuild proof when raw vendor inputs are absent.

    Raw lexical archives are intentionally not committed to GitHub; runtime uses
    the pinned compiled resource contract. Local qualification environments that
    have the archives still execute the two-pass flatten determinism gate.
    """
    root = Path(__file__).resolve().parents[1]
    vendor = root / "resources" / "vendor"
    required = [
        vendor / "verbnet-3.3.zip",
        vendor / "propbank-frames.zip",
        vendor / "semlink.zip",
        vendor / "nltk" / "corpora" / "framenet_v17.zip",
    ]
    if all(path.exists() for path in required):
        return

    target = "test_lexical_resource_gates.py::TestGate1Determinism::test_two_flatten_passes_are_byte_identical"
    marker = pytest.mark.skip(
        reason="raw vendor archives are not committed; run locally after scripts/fetch_resources.py"
    )
    for item in items:
        if item.nodeid.endswith(target):
            item.add_marker(marker)
