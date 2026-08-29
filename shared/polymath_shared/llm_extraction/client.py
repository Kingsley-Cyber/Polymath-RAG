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
from polymath_shared.llm_extraction.policy import (
    LaneDecision,
    require_cloud_eligible,
)

SYSTEM_PROMPT = """You are an information extraction engine. You read source text and reply with ONE JSON object and nothing else — no prose, no markdown fences.

Output schema (contract polymath-extraction-v1):
{"contract":"polymath-extraction-v1","profile":"volume","items":[{"neighborhood_id":"<repeat the id exactly>","entities":[{"surface":"...","type":"...","quote":"..."}],"relations":[{"subject":"...","predicate":"...","object":"...","quote":"..."}],"digest":{"central_claim":"...","main_mechanism":"...","retrieval_uses":["..."]}}]}

Rules:
1. quote fields MUST be copied VERBATIM from the source text (exact substring; may be the full sentence). Never paraphrase, never invent.
2. surface/subject/object MUST appear verbatim inside the source text.
3. type is open vocabulary — use the most specific natural type (e.g. Product, Organization, Protocol, Attack, Person, Certification, Concept). Do not force-fit.
4. predicate is the relation's own verb phrase as the text expresses it (e.g. "reported", "requires", "mitigated_by").
5. Extract facts the text states. If the text does not state a relation, output none. Quality over quantity; stay lean.
6. digest: central_claim ≤ 1 sentence; main_mechanism ≤ 1 sentence; retrieval_uses ≤ 3 short strings (what queries this passage should answer).
7. One item per neighborhood_id, exactly as given.

LOCKED generation config (plan decision 18, config/extraction_models/qwen35-4b-extraction-v1.yaml):
the local lane sends repetition_penalty=1.15 with repetition_context_size=400 —
this kills exact-repeat degeneration while preserving the JSON-structural
repetition the contract requires."""


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
    lane_decision: LaneDecision | None = field(default=None, repr=False)


class ExtractionTransportError(RuntimeError):
    """The endpoint was unreachable or repeatedly returned garbage."""


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

    def extract(self, neighborhoods: list[tuple[str, list[tuple[str, str]]]],
                *, source_bytes: int, threshold_bytes: int,
                max_tokens: int = 2500) -> LLMCallResult:
        """One extraction call over the given neighborhoods.

        DISPATCH BOUNDARY: the cloud lane refuses to send anything for a
        source at or below the threshold — before any network I/O.
        """
        decision: LaneDecision | None = None
        if self.lane == "cloud":
            decision = require_cloud_eligible(source_bytes, threshold_bytes)
        user_prompt = build_user_prompt(neighborhoods)
        expected = {nid for nid, _ in neighborhoods}
        attempts = 0
        last_raw = ""
        last_sanitize: SanitizeResult | None = None
        tokens_in = tokens_out = 0
        t0 = time.perf_counter()
        while attempts < self.max_attempts:
            attempts += 1
            try:
                raw, tin, tout = self._chat(
                    user_prompt + ("\n\nYour previous reply was not valid "
                                   "JSON under the contract. Re-read the schema "
                                   "and answer again." if attempts > 1 else ""),
                    max_tokens)
            except (httpx.HTTPError, json.JSONDecodeError, KeyError) as exc:
                raise ExtractionTransportError(
                    f"{self.lane} transport failed: {type(exc).__name__}: {exc}") from exc
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
                    lane_decision=decision)
        return LLMCallResult(
            lane=self.lane, model=self.model, raw_text=last_raw, packet=None,
            sanitize=last_sanitize or SanitizeResult(ok=False, error_class="SANITIZE_UNPARSEABLE"),
            wall_ms=int((time.perf_counter() - t0) * 1000),
            tokens_in=tokens_in, tokens_out=tokens_out, attempts=attempts,
            error_class="QUARANTINED_UNPARSEABLE", lane_decision=decision)
