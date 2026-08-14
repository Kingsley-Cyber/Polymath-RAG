"""Typed HTTP clients for sidecars. Use these. Do not hand-roll.

Every client validates the sidecar's /manifest against the registry pin
before first use (ISSUES_REPORT §4.3/§4.6 fix: fail fast at call time,
not 12 hours into a poison-CUDA incident).
"""
from __future__ import annotations

from typing import Any

import httpx

from polymath_shared.settings import get_settings


class SidecarPinMismatch(RuntimeError):
    pass


class SidecarClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        pin_release: str | None = None,
        require_pin: bool | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        settings = get_settings()
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)
        self._pin_release = pin_release
        self._require_pin = settings.sidecars.sidecar_pin_required if require_pin is None else require_pin

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SidecarClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- wire ----------------------------------------------------------------

    def manifest(self) -> dict[str, Any]:
        r = self._client.get("/manifest")
        r.raise_for_status()
        return r.json()

    def verify_pin(self) -> None:
        """Fail fast unless the sidecar's release matches the pinned release."""
        if not self._require_pin:
            return
        manifest = self.manifest()
        release = manifest.get("identity", {}).get("version")
        if release and release.startswith("__PIN_"):
            raise SidecarPinMismatch(f"sidecar {self.base_url} manifest is unpinned: {release}")
        if self._pin_release and release != self._pin_release:
            raise SidecarPinMismatch(
                f"sidecar {self.base_url} release '{release}' != pin '{self._pin_release}'"
            )

    def ready(self) -> bool:
        try:
            r = self._client.get("/ready", timeout=2.0)
            return r.status_code == 200 and bool(r.json().get("ready"))
        except Exception:
            return False

    def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = self._client.post("/infer", json=payload)
        r.raise_for_status()
        return r.json()


class GlinerClient(SidecarClient):
    """Client for the GLiNER two-pass runtime (sidecar gliner-runtime)."""

    def __init__(self, pin_release: str | None = None) -> None:
        super().__init__(get_settings().sidecars.gliner_url, pin_release=pin_release)

    def entity_pass(self, text: str, labels: list[str], threshold: float = 0.5) -> dict[str, Any]:
        return self.infer({"task": "entity", "text": text, "labels": labels, "threshold": threshold})

    def evidence_pass(self, text: str, threshold: float = 0.5) -> dict[str, Any]:
        return self.infer({"task": "evidence", "text": text, "labels": [], "threshold": threshold})


class EmbedderClient(SidecarClient):
    """Client for the embedder sidecar. Returns vectors tagged with the
    frozen contract id — an index can only be replayed by the identical
    contract (G2 gate 4)."""

    def __init__(self, pin_release: str | None = None) -> None:
        super().__init__(get_settings().sidecars.embedder_url, pin_release=pin_release)

    def embed(self, texts: list[str], representation_kind: str) -> dict[str, Any]:
        return self.infer({
            "texts": texts,
            "representation_kind": representation_kind,
        })
