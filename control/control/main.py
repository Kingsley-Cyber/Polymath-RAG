"""Control plane entrypoint. See AGENTS.md §1 and ADR-0004.

Role: control. Owns: scheduling + heartbeat. Never serves user requests.
"""
from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress

from .census import run_census
from .heartbeat import write_heartbeat
from .scheduler import enqueue_census_gaps
from .supervisor import supervise_sidecars


logger = logging.getLogger(__name__)


async def _main_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            census = await run_census()
            await enqueue_census_gaps(census)
        except Exception:
            logger.exception("control tick failed")
        await write_heartbeat()
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=30.0)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stop = asyncio.Event()
    loop = asyncio.new_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    supervisor_task = loop.create_task(supervise_sidecars())
    try:
        loop.run_until_complete(_main_loop(stop))
    finally:
        supervisor_task.cancel()
        with suppress(asyncio.CancelledError):
            loop.run_until_complete(supervisor_task)
        loop.close()


if __name__ == "__main__":
    main()
