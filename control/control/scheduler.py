"""Scheduler. Takes a CensusReport, enqueues stage jobs.

The scheduler is the only writer to the ingest queue. It uses the
idempotency key (run_id, stage, contract_hash) so re-enqueueing the
same gap is a no-op.
"""
from __future__ import annotations

from .contracts import CensusReport


async def enqueue_census_gaps(census: CensusReport) -> None:
    """For each missing artifact, enqueue a stage job.

    The job's idempotency key is content-addressed; the queue backend
    (Redis in v1) enforces the dedup.
    """
    raise NotImplementedError
