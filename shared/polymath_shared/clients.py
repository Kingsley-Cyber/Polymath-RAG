"""Typed HTTP clients for sidecars. Use these. Do not hand-roll."""
from __future__ import annotations

from typing import Any

import httpx


class SidecarClient:
    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def manifest(self) -> dict[str, Any]:
        r = self._client.get("/manifest")
        r.raise_for_status()
        return r.json()

    def ready(self) -> bool:
        try:
            r = self._client.get("/ready", timeout=2.0)
            return r.status_code == 200 and r.json().get("ready", False)
        except Exception:
            return False

    def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = self._client.post("/infer", json=payload)
        r.raise_for_status()
        return r.json()
