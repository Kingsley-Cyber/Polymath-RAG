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

    def infer_rescue_batch(
        self, requests: list[dict[str, Any]]
    ) -> list[list[dict[str, Any]]]:
        """I4R targeted rescue: batched (text, labels, threshold)
        re-queries against the same resident model via POST /rescue.
        Grouping by label-set fingerprint happens server-side per item;
        results align 1:1 with the input order. The caller decides what
        to ask; the model decides what it is."""
        r = self._client.post("/rescue", json={"requests": requests})
        r.raise_for_status()
        results = r.json().get("results", [])
        if len(results) != len(requests):
            raise RuntimeError(
                f"rescue batch returned {len(results)} results for {len(requests)} requests"
            )
        return [item.get("spans", []) for item in results]


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


class SpacySyntaxClient(SidecarClient):
    """Client for the spaCy syntax sidecar (syntax-evidence-v1).

    Sends the extract worker's EXISTING sentence slices for batched
    annotation and validates the versioned contract id on every
    response. The sidecar never proposes entities or predicates; the
    evidence it returns is syntax only, with offsets relative to the
    supplied sentence text."""

    CONTRACT_ID = "syntax-evidence-v1"

    def __init__(self, pin_release: str | None = None) -> None:
        super().__init__(get_settings().sidecars.spacy_url, pin_release=pin_release)

    def syntax(self, sentences: list[dict[str, str]]) -> dict[str, Any]:
        response = self.infer({"sentences": sentences})
        if response.get("contract") != self.CONTRACT_ID:
            raise RuntimeError(
                f"syntax sidecar returned contract {response.get('contract')!r}, "
                f"expected {self.CONTRACT_ID!r}"
            )
        return response


class RerankerClient:
    """Client for the G3 reranker sidecar (cross-encoder).

    Scores (query, candidate) pairs; returns scores + the reordered
    index list + the pinned model identity. The caller keeps rank-based
    fusion and applies the scores ordinally — this client never
    invents calibrated weights."""
    POST_PATH = "/rerank"

    def __init__(self, timeout: float = 60.0) -> None:
        settings = get_settings()
        self._client = httpx.Client(
            base_url=settings.sidecars.reranker_url.rstrip("/"),
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RerankerClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> dict[str, Any]:
        r = self._client.post(self.POST_PATH, json={
            "query": query,
            "documents": documents,
            "top_k": top_k,
        })
        r.raise_for_status()
        return r.json()
