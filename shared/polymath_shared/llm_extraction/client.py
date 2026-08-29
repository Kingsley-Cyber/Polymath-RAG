"""Direct OpenAI-compatible transport for polymath-extraction-v1.

Deliberately the plan's documented fallback shape (direct calls behind
the Pydantic contract) rather than an Instructor dependency: the
contract, the gate, and the admission pipeline are the load-bearing
parts; this file is swappable.

Lanes:
  local — the MLX extraction sidecar (loopback, no API key)
  cloud — the Ollama daemon proxying the account's cloud model tag.
          AUTH IS THE DAEMON'S SIGNED-IN ACCOUNT — no key handling here.
          `require_cloud_eligible` runs immediately before every dispatch
          (the second of the two 300 KB boundaries; selection happens in
          the worker from documents.byte_length).

Probes carry no document content: `probe()` sends a one-token ping only.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import httpx

from polymath_shared.llm_extraction.contract import (
    CONTRACT_ID,
    ExtractionPacket,
    SanitizeResult,
)
from polymath_shared.llm_extraction.gate import sanitize
from polymath_shared.llm_extraction.limiter import REGISTRY, ProviderLimit
from polymath_shared.llm_extraction.policy import (
    LaneDecision,
    require_cloud_eligible,
)

# Lane → limiter spec seeds (config/extraction_models/limiter.yaml is the
# editable source of truth; these are the code-level fallbacks).
_LANE_LIMITS = {
    "local": ProviderLimit(kind="concurrency", init=2, min=1, max=4,
                           adaptive=True),
    "cloud": ProviderLimit(kind="rate", rpm=120, tpm=200000, conc_cap=8,
                           min=2, max=8, adaptive=True, use_headers=True),
}
_LIMITER_CONFIG = None


def _lane_limit(lane: str) -> ProviderLimit:
    global _LIMITER_CONFIG
    if _LIMITER_CONFIG is None:
        try:
            import yaml
            path = (_limiter_config_path())
            _LIMITER_CONFIG = yaml.safe_load(path.read_text())["providers"]
        except Exception:
            _LIMITER_CONFIG = {}
    cfg = (_LIMITER_CONFIG or {}).get(
        "mlx_local" if lane == "local" else "ollama_cloud")
    if cfg:
        return ProviderLimit(**{**_LANE_LIMITS[lane].__dict__, **cfg})
    return _LANE_LIMITS[lane]


def _limiter_config_path():
    from pathlib import Path
    return Path(__file__).resolve().parents[3] / "config" / "extraction_models" / "limiter.yaml"

def _ontology_text() -> str:
    try:
        from polymath_shared.llm_extraction.ontology import prompt_block
        return prompt_block()
    except Exception:  # pragma: no cover — ontology is in-repo; never fires
        return ""


def _system_prompt() -> str:
    return SYSTEM_PROMPT_TEMPLATE.replace("{{ONTOLOGY}}", _ontology_text())


SYSTEM_PROMPT_TEMPLATE = """You are an information extraction engine. You read source text and reply with ONE JSON object and nothing else — no prose, no markdown fences.

Output schema (contract polymath-extraction-v1):
{"contract":"polymath-extraction-v1","profile":"volume","items":[{"neighborhood_id":"<repeat the id exactly>","entities":[{"surface":"...","type":"...","quote":"..."}],"relations":[{"subject":"...","predicate":"...","object":"...","quote":"..."}],"digest":{"central_claim":"...","main_mechanism":"...","retrieval_uses":["..."]}}]}

Rules:
1. quote fields MUST be copied VERBATIM from the source text (exact substring; may be the full sentence). Never paraphrase, never invent.
2. surface/subject/object MUST appear verbatim inside the source text.
3. type is open vocabulary — use the most specific natural type (e.g. Product, Organization, Protocol, Attack, Person, Certification, Concept). Do not force-fit.
4. predicate MUST be exactly one of these enum ids (UPPERCASE, with underscores), chosen by the definitions given:
{{ONTOLOGY}}
   If the relation's meaning is a performing/actioning verb not covered above, use ACTS_ON. Use RELATED_TO only when nothing else fits — keep it rare.
5. Extract facts the text states. If the text does not state a relation, output none. Quality over quantity; stay lean.
6. digest: central_claim ≤ 1 sentence; main_mechanism ≤ 1 sentence; retrieval_uses ≤ 3 short strings (what queries this passage should answer).
7. One item per neighborhood_id, exactly as given.

LOCKED generation config (plan decision 18, config/extraction_models/qwen35-4b-extraction-v1.yaml):
the local lane sends repetition_penalty=1.15 with repetition_context_size=400 —
this kills exact-repeat degeneration while preserving the JSON-structural
repetition the contract requires."""

SYSTEM_PROMPT = _system_prompt()


@dataclass
class LLMCallResult:
    lane: str
    model: str
    raw_text: str
    packet: ExtractionPacket | None
    sanitize: SanitizeResult
    wall_ms: int
    tokens_in: int = 0
    tokens_out: int = 0
    attempts: int = 1
    error_class: str | None = None
    raw_head: str = ""          # first 200 chars of the last raw response —
                                # quarantine diagnosis without full payload
    lane_decision: LaneDecision | None = field(default=None, repr=False)


class ExtractionTransportError(RuntimeError):
    """The endpoint was unreachable or repeatedly returned garbage."""


def output_budget_for(input_tokens: float) -> int:
    """Per-item output budget that scales with input volume (plan §4.9).

    Anchored: ~400 tokens at 800-token input, up to 3,000 at 15,000-token
    input. Lean pressure never silently loses facts — content that can't
    fit the budget shows up as rejections/flags downstream, and the dense
    items are the quality lane's job.
    """
    return int(max(400, min(3000, 253 + 0.183 * input_tokens)))


def estimate_input_tokens(user_prompt: str) -> int:
    return max(1, int(len(user_prompt) / 4.0))


def build_user_prompt(neighborhoods: list[tuple[str, list[tuple[str, str]]]]) -> str:
    """neighborhoods: (neighborhood_id, [(chunk_id, text), ...]) — the
    evidence neighborhood with chunk markers."""
    parts: list[str] = []
    for nid, chunks in neighborhoods:
        body = "\n\n".join(f"[chunk:{cid}]\n{text}" for cid, text in chunks)
        parts.append(f"[neighborhood:{nid}]\n{body}")
    return "\n\n".join(parts)


class LLMExtractionClient:
    """One client, two lanes. `lane` selects endpoint + model pin."""

    def __init__(self, lane: str, *, url: str, model: str,
                 timeout_s: float = 180.0, max_attempts: int = 2) -> None:
        if lane not in ("local", "cloud"):
            raise ValueError(f"unknown lane: {lane!r}")
        self.lane = lane
        self.model = model
        self.base_url = url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts

    # -- transport ---------------------------------------------------------

    def _chat(self, user_prompt: str, max_tokens: int) -> tuple[str, int, int]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if self.lane == "local":
            # LOCKED (plan decision 18): kills exact-repeat degeneration
            # while preserving the JSON-structural repetition per object.
            payload["repetition_penalty"] = 1.15
            payload["repetition_context_size"] = 400
            # Qwen3.5 emits thinking into a separate `reasoning` field and
            # burns the output budget there; the chat template flag turns
            # it off (measured: 1600-token think → 38-token direct JSON).
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        else:
            # Cloud lane (Ollama daemon proxy): same thinking-burn failure
            # mode, different knob — measured 2026-08-29: without this the
            # 397B spends the entire output budget thinking (finish=length,
            # empty content); with it, direct JSON, finish=stop.
            payload["reasoning_effort"] = "none"
        resp = httpx.post(f"{self.base_url}/v1/chat/completions",
                          json=payload, timeout=self.timeout_s)
        resp.raise_for_status()
        body = resp.json()
        choice = (body.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        usage = body.get("usage") or {}
        return content, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))

    # -- public API --------------------------------------------------------

    def probe(self) -> dict:
        """One-token, no-document liveness + auth probe."""
        t0 = time.perf_counter()
        payload = {"model": self.model, "messages": [
            {"role": "user", "content": "ping"}], "max_tokens": 1, "stream": False}
        resp = httpx.post(f"{self.base_url}/v1/chat/completions",
                          json=payload, timeout=min(self.timeout_s, 30.0))
        wall_ms = int((time.perf_counter() - t0) * 1000)
        resp.raise_for_status()
        body = resp.json()
        return {"ok": True, "lane": self.lane, "model": self.model,
                "wall_ms": wall_ms, "served_model": body.get("model")}

    def _lane_limiter(self):
        return REGISTRY.lane(f"llm_{self.lane}",
                             "default", _lane_limit(self.lane))

    def extract(self, neighborhoods: list[tuple[str, list[tuple[str, str]]]],
                *, source_bytes: int, threshold_bytes: int,
                max_tokens: int | None = None) -> LLMCallResult:
        """One extraction call over the given neighborhoods.

        DISPATCH BOUNDARY: the cloud lane refuses to send anything for a
        source at or below the threshold — before any network I/O.
        ADAPTIVE LIMITING: the call passes the lane's AdaptiveLimiter
        (concurrency slot for local; RPM/TPM buckets for cloud) with AIMD
        feedback from the outcome.
        OUTPUT BUDGET: scales with input volume when max_tokens is None
        (plan §4.9 per-item budget).
        """
        decision: LaneDecision | None = None
        if self.lane == "cloud":
            decision = require_cloud_eligible(source_bytes, threshold_bytes)
        user_prompt = build_user_prompt(neighborhoods)
        if max_tokens is None:
            max_tokens = output_budget_for(estimate_input_tokens(user_prompt))
        expected = {nid for nid, _ in neighborhoods}
        limiter = self._lane_limiter()
        est_tokens = estimate_input_tokens(user_prompt) + max_tokens / 2.0
        attempts = 0
        last_raw = ""
        last_sanitize: SanitizeResult | None = None
        tokens_in = tokens_out = 0
        t0 = time.perf_counter()
        while attempts < self.max_attempts:
            attempts += 1
            if not limiter.acquire(est_tokens=est_tokens):
                # breaker open or non-blocking saturation: report as
                # throttle so the caller can requeue; no network I/O made
                return LLMCallResult(
                    lane=self.lane, model=self.model, raw_text="",
                    packet=None,
                    sanitize=SanitizeResult(ok=False, error_class="LIMITER_REFUSED"),
                    wall_ms=int((time.perf_counter() - t0) * 1000),
                    attempts=attempts, error_class="LIMITER_REFUSED",
                    lane_decision=decision)
            try:
                raw, tin, tout = self._chat(
                    user_prompt + ("\n\nYour previous reply was not valid "
                                   "JSON under the contract. Re-read the schema "
                                   "and answer again." if attempts > 1 else ""),
                    max_tokens)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                limiter.record_failure(
                    retry_after=exc.response.headers.get("retry-after"),
                    headers=dict(exc.response.headers))
                limiter.release()
                if status in (429, 502, 503, 504) and attempts < self.max_attempts:
                    time.sleep(min(float(exc.response.headers.get("retry-after", 0) or 1.5), 15.0))
                    continue
                raise ExtractionTransportError(
                    f"{self.lane} transport failed: HTTP {status}") from exc
            except (httpx.HTTPError, json.JSONDecodeError, KeyError) as exc:
                limiter.record_failure()
                limiter.release()
                raise ExtractionTransportError(
                    f"{self.lane} transport failed: {type(exc).__name__}: {exc}") from exc
            limiter.record_success()
            limiter.release()
            last_raw = raw
            tokens_in += tin
            tokens_out += tout
            s_res, packet = sanitize(raw, expected)
            last_sanitize = s_res
            if packet is not None:
                return LLMCallResult(
                    lane=self.lane, model=self.model, raw_text=raw, packet=packet,
                    sanitize=s_res, wall_ms=int((time.perf_counter() - t0) * 1000),
                    tokens_in=tokens_in, tokens_out=tokens_out, attempts=attempts,
                    raw_head=raw[:200], lane_decision=decision)
        return LLMCallResult(
            lane=self.lane, model=self.model, raw_text=last_raw, packet=None,
            sanitize=last_sanitize or SanitizeResult(ok=False, error_class="SANITIZE_UNPARSEABLE"),
            wall_ms=int((time.perf_counter() - t0) * 1000),
            tokens_in=tokens_in, tokens_out=tokens_out, attempts=attempts,
            error_class="QUARANTINED_UNPARSEABLE", raw_head=last_raw[:200],
            lane_decision=decision)
