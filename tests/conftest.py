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


# PROVIDER-ATTEMPT-LEDGER-V1 test isolation.
#
# The ledger records at `LLMExtractionClient.complete_one`, which unit tests exercise
# with fake lanes. With POLYMATH_PG_DSN set (it is, because tests run against the dev
# database) those fakes wrote real rows into `llm_provider_attempts` — two rows for
# lanes named `cp_success` / `cp_refused` were found in the production ledger during the
# 2026-09-12 bootstrap. An accounting ledger polluted by test fixtures cannot be
# reconciled against, so the whole test session opts out at import time.
import os as _os

_os.environ.setdefault("POLYMATH_ATTEMPT_LEDGER", "0")
_os.environ["POLYMATH_ATTEMPT_LEDGER"] = "0"
