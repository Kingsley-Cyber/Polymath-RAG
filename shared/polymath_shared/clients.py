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


class LocalLlmConnectionError(RuntimeError):
    """Configured local model is absent, remote, or contract-invalid."""


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

    def wait_ready(self, timeout_s: float = 120.0, poll_s: float = 2.0) -> bool:
        """SIDECAR-READINESS-GATE-V1 (measured 2026-09-02): the autopilot
        wakes a projection worker and its sidecar in the same tick; the
        worker claimed its ticket and failed it THREE times in eight
        seconds while the embedder was still loading (breaker open), so a
        routine latent re-projection burned its whole retry budget and the
        summary tail behind it froze. A worker that depends on a sidecar
        waits for /ready (bounded) before it spends an attempt. Polls
        BYPASS the breaker; success clears the breaker for this host."""
        deadline = time.monotonic() + timeout_s
        while True:
            if self.ready():
                SidecarClient._refused_until.pop(self.base_url, None)
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll_s)

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

    #: FAIL-FAST-BREAKER-V1 (2026-09-01, from the 97s-query live
    #: incident): when NOTHING is listening (connection refused), the
    #: 2s+4s backoff sleeps below bought no recovery — refused is
    #: instant and deterministic within a tick — yet every call site
    #: paid ~6s, and a retrieval that consults the reranker at many
    #: points paid ~97s per query while degrading correctly. Refused
    #: connections now retry without sleeping, and a terminal
    #: refused-failure opens a per-host breaker: for the next
    #: _BREAKER_OPEN_S seconds every request to that host raises
    #: SidecarUnavailable IMMEDIATELY, feeding the caller's existing
    #: degraded path at full speed. Any success closes the breaker.
    #: ReadTimeout/5xx keep the original sleep-backoff semantics — a
    #: BUSY or mid-restart sidecar still deserves patience (P0-C).
    _BREAKER_OPEN_S = 15.0
    _refused_until: dict[str, float] = {}

    def request(self, method: str, path: str, *, attempts: int = 3,
                **kwargs: Any) -> httpx.Response:
        """Bounded, pool-invalidating request. Terminal failure is typed."""
        _bkey = getattr(self, "base_url", None) or ""   # breaker key; some clients skip SidecarClient.__init__
        opened = SidecarClient._refused_until.get(_bkey, 0.0)
        remaining = opened - time.monotonic()
        if remaining > 0:
            raise SidecarUnavailable(
                f"{_bkey}{path} skipped: connection-refused "
                f"breaker open for {remaining:.1f}s more")
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                # Dispatch by verb (client.post/get) rather than
                # client.request: it is the same call for httpx and keeps
                # the narrower interface that test doubles implement.
                r = getattr(self._client, method.lower())(path, **kwargs)
                r.raise_for_status()
                SidecarClient._refused_until.pop(_bkey, None)
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
            if attempt < attempts - 1 and not isinstance(last, httpx.ConnectError):
                time.sleep(min(2.0 * (2 ** attempt), 8.0))
        if isinstance(last, httpx.ConnectError):
            SidecarClient._refused_until[_bkey] = (
                time.monotonic() + self._BREAKER_OPEN_S)
        raise SidecarUnavailable(
            f"{_bkey}{path} unreachable after {attempts} attempts: "
            f"{type(last).__name__}: {last}")

    def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/infer", json=payload).json()


class OllamaLocalClient(SidecarClient):
    """Read-only LOCAL-LLM-EXTRACTION-V1 connection verifier.

    Free-LLM documents Ollama's local OpenAI-compatible endpoint. The
    native model catalog is used for preflight because it distinguishes a
    downloaded model from an Ollama remote-model alias.
    """

    def __init__(self) -> None:
        settings = get_settings().sidecars
        super().__init__(
            settings.local_llm_url,
            timeout=settings.sidecar_timeout_s,
            require_pin=False,
        )
        self.model = settings.local_llm_model.strip()

    def models(self) -> list[dict[str, Any]]:
        try:
            payload = self.request("GET", "/api/tags", attempts=2).json()
        except ValueError as exc:
            raise LocalLlmConnectionError(
                "Ollama /api/tags did not return JSON"
            ) from exc
        models = payload.get("models")
        if not isinstance(models, list):
            raise LocalLlmConnectionError(
                "Ollama /api/tags response has no models list"
            )
        return [dict(item) for item in models if isinstance(item, dict)]

    def configured_release(self) -> dict[str, str]:
        if not self.model:
            raise LocalLlmConnectionError("no local Ollama model is configured")
        match = next(
            (
                item for item in self.models()
                if item.get("name") == self.model or item.get("model") == self.model
            ),
            None,
        )
        if match is None:
            raise LocalLlmConnectionError(
                f"configured Ollama model {self.model!r} is not installed"
            )
        if match.get("remote_host") or match.get("remote_model"):
            raise LocalLlmConnectionError(
                f"configured Ollama model {self.model!r} is remote; local-only mode refuses it"
            )
        digest = str(match.get("digest") or "").strip()
        if not digest:
            raise LocalLlmConnectionError(
                f"configured Ollama model {self.model!r} has no release digest"
            )
        return {"model": self.model, "digest": digest}

    def verify_pin(self) -> None:
        self.configured_release()

    def ready(self) -> bool:
        try:
            self.configured_release()
            return True
        except Exception:
            return False


def probe_local_llm() -> dict[str, str]:
    """Return the read-only local provider connection verdict."""
    settings = get_settings().sidecars
    if settings.local_llm_provider == "disabled":
        return {"status": "disabled"}
    with OllamaLocalClient() as client:
        release = client.configured_release()
    return {"status": "ready", **release}


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


class RerankerClient(SidecarClient):
    """Client for the G3 reranker sidecar (cross-encoder).

    Scores (query, candidate) pairs; returns scores + the reordered
    index list + the pinned model identity. The caller keeps rank-based
    fusion and applies the scores ordinally — this client never
    invents calibrated weights.

    Inherits SidecarClient so `rerank()` goes through the same bounded,
    pool-invalidating `request()` as every other sidecar call. It
    previously carried its own bare `httpx.Client` while calling
    `self.request(...)`, so every rerank raised AttributeError and the
    orchestrator answered 502 `rerank_unavailable` on FAST, HYBRID and
    GRAPH alike. Nothing caught it because no test and no acceptance run
    had exercised retrieval since the client was refactored.
    """
    POST_PATH = "/rerank"

    def __init__(self, timeout: float = 60.0) -> None:
        super().__init__(get_settings().sidecars.reranker_url, timeout=timeout)

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
