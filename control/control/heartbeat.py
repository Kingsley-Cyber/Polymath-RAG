"""Heartbeat writer. See ADR-0004.

Writes a row to control_heartbeats every tick. Stale heartbeats are how
operators detect a wedged control plane.
"""
from __future__ import annotations

import datetime as _dt

from .contracts import Heartbeat


async def write_heartbeat() -> None:
    """Insert one heartbeat row. The schema lives in stores/postgres/migrations/."""
    raise NotImplementedError  # populated when stores/postgres lands
