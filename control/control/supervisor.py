"""Sidecar supervisor. Watches /ready, restarts via systemd.

This replaces the v3.3 autoheal band-aid. The supervisor is allowed to
call systemctl restart <unit> when a sidecar's /ready returns non-OK
for more than N consecutive probes.
"""
from __future__ import annotations

import asyncio
import logging

import httpx


logger = logging.getLogger(__name__)


async def supervise_sidecars() -> None:
    """Loop forever. Watch every sidecar in sidecars/*.toml.

    For each:
      - GET /ready
      - if not ok, increment failure counter
      - if counter > threshold, systemctl restart the unit
    """
    raise NotImplementedError
