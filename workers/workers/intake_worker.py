"""Intake worker. Parses the source and produces chunks.

Role: worker. Idempotent. Crash-safe.
"""
from __future__ import annotations

import asyncio
import json
import logging


logger = logging.getLogger(__name__)


async def handle_intake(job: dict) -> None:
    """Parse the source, write chunks, write a stage_attempts receipt.

    The transaction is: insert chunks -> insert stage_attempt -> commit.
    If any step fails, Postgres rolls back; the run stays in `intake`
    and the control plane re-enqueues.
    """
    raise NotImplementedError


if __name__ == "__main__":
    asyncio.run(handle_intake({}))
