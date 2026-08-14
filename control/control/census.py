"""Artifact census. See AGENTS.md §2 and ADR-0004.

Computes desired-vs-observed for every (corpus, doc) pair. The result
is the input to the scheduler.
"""
from __future__ import annotations

from typing import Iterable

from .contracts import CensusReport, CorpusCensus


async def run_census() -> CensusReport:
    """Walk every run row and compute missing artifacts.

    This is a pure function over Postgres state plus the same predicates
    the stage planners use. The algorithm is identical to v3.3's
    desired_state.py; the substrate is Postgres.
    """
    raise NotImplementedError
