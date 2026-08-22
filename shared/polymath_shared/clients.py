"""Typed HTTP clients for sidecars. Use these. Do not hand-roll.

Every client validates the sidecar's /manifest against the registry pin
before first use (ISSUES_REPORT §4.3/§4.6 fix: fail fast at call time,
not 12 hours into a poison-CUDA incident).
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from polymath_shared.settings import get_settings


class SidecarPinMismatch(RuntimeError):
    pass


class SidecarUnavailable(RuntimeError):
    """Terminal, TYPED failure to reach a sidecar (P0-C).

    Raised only after bounded retries with a rebuilt connection pool.
    A stage that sees this fails loudly and is retried by the control
    plane; it never blocks forever on a socket to a process that is gone.
    """


#: Read budget for GPU inference calls. Connect and pool stay short (see
#: SidecarClient.__init__) so a dead or restarted sidecar is still detected
#: in seconds; only the READ phase is patient. Measured need: on the shared
#: MPS device a 32-text embed batch takes ~2.4s idle but ~38s while GLiNER
#: extraction runs, so the generic 30s budget failed every attempt of a
#: projection and burned the ticket. A wedged sidecar is caught by the
#: readiness probe and the supervisor, never by starving this timeout.
INFERENCE_READ_TIMEOUT_S = 300.0


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
        # P0-C: every phase is bounded. `connect` and `pool` stay short so a
        # dead or restarted sidecar is detected in seconds; `read`/`write`
        # carry the caller's budget because real inference is slow.
        self._timeout = httpx.Timeout(
            timeout, connect=min(5.0, timeout), pool=min(5.0, timeout))
        self._client = httpx.Client(base_url=self.base_url, timeout=self._timeout)
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
        return self.request("GET", "/manifest", attempts=2).json()

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

    # -- transport resilience (P0-C) ----------------------------------------

    #: Transport-level faults worth retrying on a FRESH pool. A sidecar
    #: restart leaves half-open sockets in the old pool; reusing one blocks
    #: or fails forever, which is how a 16-hour projection stall began.
    _RETRYABLE = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout,
                  httpx.WriteTimeout, httpx.PoolTimeout, httpx.RemoteProtocolError,
                  httpx.ReadError, httpx.WriteError)

    def _reset_pool(self) -> None:
        """Drop every pooled connection and build a new client."""
        try:
            self._client.close()
        except Exception:
            pass
        self._client = httpx.Client(base_url=self.base_url, timeout=self._timeout)

    def request(self, method: str, path: str, *, attempts: int = 3,
                **kwargs: Any) -> httpx.Response:
        """Bounded, pool-invalidating request. Terminal failure is typed."""
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                # Dispatch by verb (client.post/get) rather than
                # client.request: it is the same call for httpx and keeps
                # the narrower interface that test doubles implement.
                r = getattr(self._client, method.lower())(path, **kwargs)
                r.raise_for_status()
                return r
            except self._RETRYABLE as exc:
                last = exc
                self._reset_pool()
            except httpx.HTTPStatusError as exc:
                # 5xx may be a sidecar mid-restart; 4xx is our own bug.
                if exc.response.status_code < 500 or attempt == attempts - 1:
                    raise
                last = exc
                self._reset_pool()
            if attempt < attempts - 1:
                time.sleep(min(2.0 * (2 ** attempt), 8.0))
        raise SidecarUnavailable(
            f"{self.base_url}{path} unreachable after {attempts} attempts: "
            f"{type(last).__name__}: {last}")

    def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/infer", json=payload).json()


class GlinerClient(SidecarClient):
    """Client for the GLiNER two-pass runtime (sidecar gliner-runtime)."""

    def __init__(self, pin_release: str | None = None) -> None:
        super().__init__(get_settings().sidecars.gliner_url,
                         timeout=INFERENCE_READ_TIMEOUT_S,
                         pin_release=pin_release)

    def entity_pass(self, text: str, labels: list[str], threshold: float = 0.5) -> dict[str, Any]:
        return self.infer({"task": "entity", "text": text, "labels": labels, "threshold": threshold})

    def entity_pass_batch(self, texts: list[str], labels: list[str],
                          threshold: float = 0.5,
                          batch: int = 32) -> list[list[dict[str, Any]]]:
        """PHASE B2 batched pass-1 transport. One HTTP request carries up to
        `batch` chunk texts; the sidecar executes them under its startup-
        probed mode (true model batch only when bit-equivalent, else a
        server-side loop). Results align 1:1 with input order."""
        out: list[list[dict[str, Any]]] = []
        for i in range(0, len(texts), batch):
            body = self.request("POST", "/infer_batch", json={
                "task": "entity", "texts": texts[i:i + batch],
                "labels": labels, "threshold": threshold}).json()
            out.extend([[dict(sp) for sp in row] for row in body["results"]])
        if len(out) != len(texts):
            raise RuntimeError(
                f"batch entity pass returned {len(out)} results for {len(texts)} texts")
        return out

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
        results = self.request(
            "POST", "/rescue", json={"requests": requests}).json().get("results", [])
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
        super().__init__(get_settings().sidecars.embedder_url,
                         timeout=INFERENCE_READ_TIMEOUT_S,
                         pin_release=pin_release)

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
        super().__init__(get_settings().sidecars.spacy_url,
                         timeout=INFERENCE_READ_TIMEOUT_S,
                         pin_release=pin_release)

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
        return self.request("POST", self.POST_PATH, json={
            "query": query,
            "documents": documents,
            "top_k": top_k,
        }).json()
