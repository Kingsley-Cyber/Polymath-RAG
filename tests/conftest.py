"""Shared pytest fixtures."""
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
