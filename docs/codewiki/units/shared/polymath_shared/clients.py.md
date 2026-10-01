# unit: shared/polymath_shared/clients.py
anchor: shared/polymath_shared/clients.py:1-335

## purpose
Typed HTTP clients for the sidecar processes (embedder, G3 reranker, local Ollama). Every client validates the sidecar `/manifest` against the registry pin before first use, so a wrong release fails fast at call time instead of mid-incident (module docstring, shared/polymath_shared/clients.py:1-5) [DERIVED]. Consumed by the orchestrator API and the workers (see importers below) [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| SidecarClient | class | (base_url: str, *, timeout: float = 30.0, pin_release: str \| None = None, require_pin: bool \| None = None) -> None | shared/polymath_shared/clients.py:45-53 | module importers (below) |
| SidecarClient.manifest | method | () -> dict[str, Any] | shared/polymath_shared/clients.py:78-79 | — |
| SidecarClient.verify_pin | method | () -> None | shared/polymath_shared/clients.py:81-92 | — |
| SidecarClient.ready | method | () -> bool | shared/polymath_shared/clients.py:94-99 | — |
| SidecarClient.wait_ready | method | (timeout_s: float = 120.0, poll_s: float = 2.0) -> bool | shared/polymath_shared/clients.py:101-117 | — |
| SidecarClient.request | method | (method: str, path: str, *, attempts: int = 3, **kwargs: Any) -> httpx.Response | shared/polymath_shared/clients.py:152-153 | — |
| SidecarClient.infer | method | (payload: dict[str, Any], headers: dict[str, str] \| None = None) -> dict[str, Any] | shared/polymath_shared/clients.py:190-192 | — |
| OllamaLocalClient | class | () -> None; models() -> list[dict]; configured_release() -> dict[str, str] | shared/polymath_shared/clients.py:195-259 | — |
| probe_local_llm | function | () -> dict[str, str] | shared/polymath_shared/clients.py:262-269 | — |
| EmbedderClient | class | (pin_release: str \| None = None, *, priority: str = BACKGROUND); embed(texts: list[str], representation_kind: str, priority: str \| None = None) -> dict[str, Any] | shared/polymath_shared/clients.py:272-295 | — |
| RerankerClient | class | (timeout: float = 60.0, *, priority: str = BACKGROUND); rerank(query: str, documents: list[str], top_k: int \| None = None, priority: str \| None = None) -> dict[str, Any] | shared/polymath_shared/clients.py:298-334 | — |
| SidecarPinMismatch / SidecarUnavailable / LocalLlmConnectionError | exceptions | RuntimeError subclasses | shared/polymath_shared/clients.py:18-19, 22-28, 31-32 | — |

Module importers (FACTS): orchestrator/orchestrator/api/fast.py, orchestrator/orchestrator/api/retrieve.py, orchestrator/orchestrator/api/ui.py, shared/polymath_shared/rerank.py, shared/polymath_shared/worker_runtime.py, workers/workers/doc_profile_worker.py, workers/workers/project_qdrant_worker.py, workers/workers/semantic_chunker.py — shared/polymath_shared/clients.py:1-335 [DERIVED]

## contracts

**SidecarClient.request** — shared/polymath_shared/clients.py:152-188
- in: HTTP verb + path; `attempts: int = 3` (152-153); any httpx kwargs
- pre: connection-refused breaker for `base_url` is closed, else immediate raise (156-161)
- out: `httpx.Response` that passed `raise_for_status()` (168-171); breaker entry popped on success (170)
- raises: `httpx.HTTPStatusError` re-raised when `status_code < 500` or last attempt (175-178); `SidecarUnavailable` after all attempts (186-188); terminal `httpx.ConnectError` opens the breaker for `_BREAKER_OPEN_S` (183-185)

**SidecarClient.verify_pin** — shared/polymath_shared/clients.py:81-92
- pre: `require_pin` defaults from `settings.sidecars.sidecar_pin_required` when arg is `None` (63); no-op when false (83-84)
- in: `GET /manifest` with `attempts=2` (79)
- post: `manifest["identity"]["version"]` is set, does not start with `"__PIN_"` (86-88), and equals `pin_release` when a pin is configured (89-92)
- raises: `SidecarPinMismatch` (88, 90-92)

**SidecarClient.ready / wait_ready** — shared/polymath_shared/clients.py:94-117
- ready: `GET /ready` with `timeout=2.0`; True iff status `200` and `json()["ready"]` truthy (96-97)
- wait_ready: polls `ready()` every `poll_s=2.0` until `timeout_s=120.0`; success pops the breaker entry for `base_url` (112-114); timeout returns `False` (115-116); polls go through `_client.get` directly, so they bypass the breaker in `request()` (96 vs 156-161) [INFERRED: `ready()` never touches `_refused_until` before wait_ready clears it]

**OllamaLocalClient.configured_release** — shared/polymath_shared/clients.py:226-249
- in: `GET /api/tags` with `attempts=2` (214)
- out: `{"model": self.model, "digest": digest}` (249)
- raises `LocalLlmConnectionError` when: model empty (227-228), model not in catalog (236-239), `remote_host`/`remote_model` set (240-243), digest empty (244-248), non-JSON or missing `models` list (215-223)
- constructed with `require_pin=False` (208); overrides `verify_pin` to just call `configured_release()` (251-252)

**probe_local_llm** — shared/polymath_shared/clients.py:262-269
- `settings.sidecars.local_llm_provider == "disabled"` -> `{"status": "disabled"}` (265-266)
- else -> `{"status": "ready", **release}` (267-269)

**EmbedderClient.embed** — shared/polymath_shared/clients.py:288-295
- POST `/infer` with payload keys exactly `{"texts", "representation_kind"}` (292-294); vectors carry the frozen contract id, replayable only by the identical contract (273-275)
- priority header via `priority_headers(priority or self.priority)`; class default `BACKGROUND` (278, 286, 289-295)

**RerankerClient.rerank** — shared/polymath_shared/clients.py:321-334
- POST `"/rerank"` (constant `POST_PATH = "/rerank"`, 314) with `{"query", "documents", "top_k"}` (330-334)
- returns scores + reordered index list + pinned model identity; caller keeps rank-based fusion — client never invents calibrated weights (300-307)

## effect surface
- Network out: `embedder_url` (279), `reranker_url` (318), `local_llm_url` (206); paths `/manifest` (79), `/ready` (96), `/infer` (192), `/rerank` (330), `/api/tags` (214); two `httpx.Client` constructions (61, 134) [DERIVED]
- Settings/env via `get_settings().sidecars`: `sidecar_pin_required` (63), `local_llm_provider` (265), `local_llm_url` (206), `sidecar_timeout_s` (207), `local_llm_model` (210), `embedder_url` (279), `reranker_url` (318) [DERIVED]
- Postgres tables: none read, none written (FACTS tables_read/tables_written empty) [DERIVED]
- Files, Qdrant, subprocess: none [DERIVED]
- Process-wide state: class attribute `SidecarClient._refused_until: dict[str, float] = {}` shared by all instances (150) [DERIVED]

## invariants
INVARIANT: connect/pool timeout == min(5.0, timeout) <= timeout — shared/polymath_shared/clients.py:59-60 [DERIVED]
  fails-if: a dead or restarted sidecar is no longer detected in seconds (comment 56-58)
INVARIANT: EmbedderClient read budget == INFERENCE_READ_TIMEOUT_S == 300.0 — shared/polymath_shared/clients.py:42, 279-281 [DERIVED]
  fails-if: measured ~38s embed batches under concurrent GLiNER load time out and burn the ticket (comment 37-41)
INVARIANT: _BREAKER_OPEN_S == 15.0 per host key — shared/polymath_shared/clients.py:149, 184-185 [DERIVED]
  fails-if: refused host either stalls every caller or flaps back into retry storms
INVARIANT: backoff sleep == min(2.0 * (2 ** attempt), 8.0), skipped when last error is httpx.ConnectError — shared/polymath_shared/clients.py:181-182 [DERIVED]
  fails-if: refused connections re-pay ~6s per call site (comment 137-139, the 97s-query incident)
INVARIANT: any successful request pops the breaker entry for its host — shared/polymath_shared/clients.py:170, 113 [DERIVED]
  fails-if: breaker sticks open after the sidecar recovers
INVARIANT: 4xx raises immediately; only 5xx retried — shared/polymath_shared/clients.py:175-178 [DERIVED]
  fails-if: client bugs (4xx) get masked as transient sidecar failures
INVARIANT: manifest/models use attempts=2, general request default attempts=3 — shared/polymath_shared/clients.py:79, 214, 153 [DERIVED]
  fails-if: probe-style calls start paying triple retry latency
INVARIANT: embed payload keys are exactly "texts" and "representation_kind" — shared/polymath_shared/clients.py:292-294 [DERIVED]
  fails-if: contract-id mismatch, index no longer replayable (G2 gate 4, 273-275)

## determinism & idempotency
determinism: NONDETERMINISTIC (network: httpx.Timeout clients.py:59, httpx.Client 61/134; clock: time.monotonic 110, 115, 157, 185; concurrency: shared class-level dict `_refused_until` 150) [DERIVED]
idempotency: SAFE — stateless HTTP probes/inference, no tables or files written (FACTS tables_written empty); note `request()` auto-retries POSTs up to `attempts` on transport faults, re-running remote inference (152-153, 172-174) [INFERRED: no local side effects visible]

## failure behaviour
- `SidecarClient.ready()` swallows every `Exception` -> `return False` (98-99): caller cannot distinguish host down from bad response [DERIVED]
- `_reset_pool()` swallows close `Exception` -> `pass`, always rebuilds the client (130-134) [DERIVED]
- `OllamaLocalClient.ready()` swallows every `Exception` -> `return False` (258-259): all `LocalLlmConnectionError` reasons collapse to "not ready" [DERIVED]
- Typed errors: `SidecarUnavailable` raised on open breaker (159-161) and after exhausted attempts (186-188) — terminal, caller degrades; `SidecarPinMismatch` (88, 90-92); `LocalLlmConnectionError` (216-218, 221-223, 228, 237-239, 241-243, 246-248)
- Retryable transport faults: `httpx.ConnectError, ConnectTimeout, ReadTimeout, WriteTimeout, PoolTimeout, RemoteProtocolError, ReadError, WriteError` each trigger `_reset_pool()` (124-126, 172-174) [DERIVED]

## dumb-code flags
- `getattr(self, "base_url", None) or ""` — comment admits "some clients skip SidecarClient.__init__"; such clients all share breaker key `""` (155) [DERIVED]
- Sentinel prefix `"__PIN_"` used to detect unpinned manifests (87-88) [DERIVED]
- Duplicated `priority or self.priority` plumbing in embed and rerank (289-295, 326-334) [DERIVED]
- Magic numbers: `5.0` connect/pool cap (60), `2.0` ready timeout (96), `120.0`/`2.0` wait_ready defaults (101), `8.0` backoff cap (182), `15.0` breaker (149), `60.0` reranker default timeout (316) [DERIVED]
- Timeout defaults disagree by client: SidecarClient 30.0 (50), RerankerClient 60.0 (316), EmbedderClient fixed 300.0 (42, 280) [DERIVED]
- RerankerClient docstring records a past incident where a bare `httpx.Client` bypassing `request()` made every rerank raise AttributeError -> 502 `rerank_unavailable` on FAST/HYBRID/GRAPH (305-312) [DERIVED]

## refactor notes
- `request()` is the single transport for manifest/verify/infer/rerank/tags (79, 192, 330, 214); changing retry/backoff/breaker semantics hits all 8 importers (FACTS list above) [DERIVED]
- `_refused_until` is class-level and keyed by `base_url` (150, 156): any subclass that calls `request()` without setting `base_url` lands in the shared `""` bucket (155) — keep the key derivation or fix the constructors [INFERRED: from 155's own comment]
- `"representation_kind"` is the frozen embed contract tag (273-275, 293): renaming it breaks index replay (G2 gate 4)
- `OllamaLocalClient` overrides `verify_pin`/`ready` with Ollama-catalog semantics (251-259): changes to `SidecarClient.verify_pin` do not reach it
- `_RETRYABLE` tuple and the `< 500` retry threshold (124-126, 177) define the 4xx-fail-fast contract; relaxing it changes error visibility for every caller

## VERIFY
```verify
grep -Fq 'INFERENCE_READ_TIMEOUT_S = 300.0' shared/polymath_shared/clients.py
grep -Fq '_BREAKER_OPEN_S = 15.0' shared/polymath_shared/clients.py
grep -Fq 'time.sleep(min(2.0 * (2 ** attempt), 8.0))' shared/polymath_shared/clients.py
grep -Fq 'connect=min(5.0, timeout), pool=min(5.0, timeout))' shared/polymath_shared/clients.py
grep -Fq 'POST_PATH = "/rerank"' shared/polymath_shared/clients.py
grep -Fq 'self.request("GET", "/manifest", attempts=2).json()' shared/polymath_shared/clients.py
test "$(grep -c -F 'SidecarPinMismatch' shared/polymath_shared/clients.py)" -ge 3
```
