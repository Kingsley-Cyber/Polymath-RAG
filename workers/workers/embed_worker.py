"""Embed worker. Calls the embedder sidecar.

Role: worker. Idempotent. Uses shared/polymath_shared/clients.py for
the sidecar call; never hand-rolls HTTP.
"""
from __future__ import annotations

import asyncio
import logging


logger = logging.getLogger(__name__)


async def handle_embed(job: dict) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    asyncio.run(handle_embed({}))
