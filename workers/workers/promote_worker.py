"""Promote worker. Writes to Qdrant + Neo4j, issues query_ready.

Role: worker. Idempotent. The last stage.
"""
from __future__ import annotations

import asyncio
import logging


logger = logging.getLogger(__name__)


async def handle_promote(job: dict) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    asyncio.run(handle_promote({}))
