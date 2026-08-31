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
import os
import time
from dataclasses import dataclass, field

import httpx

from polymath_shared.llm_extraction.contract import (
    ExtractionPacket,
    SanitizeResult,
)
from polymath_shared.llm_extraction.gate import sanitize
from polymath_shared.llm_extraction.limiter import (
    REGISTRY,
    ProviderLimit,
    parse_retry_after,
)
from polymath_shared.llm_extraction.policy import (
    LaneDecision,
    require_cloud_eligible,
)

# LOCKED generation config (plan decision 18). Hashed into the extract
# stage contract via workers.llm_provider.contract_identity — change it
# only with a new A/B record, and expect every document to re-extract.
GENERATION_CONFIG: dict = {
    "temperature": 0.0,
    "max_tokens": 2500,                 # per parent neighborhood (decision 18)
    "extra_tokens_per_neighborhood": 700,   # cloud multi-neighborhood calls
    "expected_output_tokens": 900,      # for batch-budget accounting only
    "local": {"repetition_penalty": 1.15, "repetition_context_size": 400,
              "enable_thinking": False},
    "cloud": {"reasoning_effort": "none"},
}

# Lane → limiter spec seeds (config/extraction_models/limiter.yaml is the
# editable source of truth; these are the code-level fallbacks).
_LANE_LIMITS = {
    "local": ProviderLimit(kind="concurrency", init=2, min=1, max=4,
                           adaptive=True),
    "cloud": ProviderLimit(kind="rate", rpm=120, tpm=200000, conc_cap=18,
                           min=2, max=18, adaptive=True, use_headers=True),
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
        return ProviderLimit.from_config(_LANE_LIMITS[lane], cfg)
    return _LANE_LIMITS[lane]


def _quarantine_class(s_res: SanitizeResult | None) -> str:
    """Receipt error class for a call whose packet did not survive
    sanitize: the sanitize disposition itself unless it was the generic
    unparseable case (SANITIZE_UNKNOWN_NEIGHBORHOOD must not be masked)."""
    if s_res is None or s_res.error_class in (None, "SANITIZE_UNPARSEABLE"):
        return "QUARANTINED_UNPARSEABLE"
    return s_res.error_class


def _retry_nudge(s_res: SanitizeResult | None) -> str:
    if s_res is not None and s_res.error_class == "SANITIZE_UNKNOWN_NEIGHBORHOOD":
        return ("\n\nYour previous reply referenced neighborhood ids that "
                "were not given. Use ONLY the neighborhood_id values "
                "provided, exactly as written, and answer again.")
    return ("\n\nYour previous reply was not valid JSON under the "
            "contract. Re-read the schema and answer again.")


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
8. Never derive an entity or relation from a question stem, quiz prompt, or answer-option list (e.g. "Which of the following…", lettered choices). Extract only from declarative statements and explanations.

LOCKED generation config (plan decision 18, config/extraction_models/qwen35-4b-extraction-v1.yaml):
the local lane sends repetition_penalty=1.15 with repetition_context_size=400 —
this kills exact-repeat degeneration while preserving the JSON-structural
repetition the contract requires."""

LEAN_SYSTEM_PROMPT = """You are an information extraction engine. You read source text and reply with ONE JSON object and nothing else — no prose, no markdown fences.

Output schema (contract polymath-extraction-v1, LEAN form — entities by index, quotes only on relations):
{"contract":"polymath-extraction-v1","profile":"volume","items":[{"id":"n1","e":[["surface","TYPE"],...],"r":[[0,"PREDICATE",1,"verbatim quote"],...],"digest":{"central_claim":"...","main_mechanism":"...","retrieval_uses":["..."]}}]}

Rules:
1. "e" is the entity array: [surface, TYPE] pairs. Surface MUST appear verbatim in the source text. TYPE is one of: Person, Organization, Location, Product, Technology, Concept, Method, Event, Document, Process, Measurement, TimeReference — or a more specific natural type.
2. "r" relations reference entity INDICES: [subject_idx, PREDICATE, object_idx, quote]. The quote MUST be copied VERBATIM from the source. PREDICATE must be exactly one of: IS_A, PART_OF, HAS_PROPERTY, SAME_AS, USES, REQUIRES, PRODUCES, CAUSES, REGULATES, CORRELATES_WITH, CONSTRAINED_BY, PRECEDES, MEASURES, LOCATED_IN, ALTERNATIVE_TO, OPPOSES, ACTS_ON. Use RELATED_TO only as a last resort.
3. Disambiguation (follow exactly): applying/imposing a rule on X = CONSTRAINED_BY, never PRODUCES (nothing new is created). "consists of/composed of/made up of" = PART_OF, not HAS_PROPERTY. PRODUCES = creates a NEW output that did not exist before. Supplying/offering something existing = USES or ACTS_ON. "not responsible for / not the root cause / prevents" = OPPOSES. RELATED_TO is the LAST RESORT — if any other id fits even loosely, use that id.
4. No output without input: extract only what the text states. Stay lean — no padding, no repetition. Entities without relations are fine.
5. digest: central_claim ≤ 1 sentence; main_mechanism ≤ 1 sentence; retrieval_uses ≤ 3 short strings.
6. One item only, with "id":"n1" exactly."""


def _lean_expand(obj: dict) -> dict:
    """Expand the LEAN index form into the standard flat packet shape so
    the shared gate/validation path is unchanged. Surfaces attest as their
    own quote (the gate locates them in the chunk verbatim); relation
    quotes carry through for attestation."""
    items_in = obj.get("items") or []
    items_out = []
    for it in items_in:
        ents = it.get("e") or []
        rels = it.get("r") or []
        entities = []
        for pair in ents:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2 \
                    and isinstance(pair[0], str) and isinstance(pair[1], str):
                entities.append({"surface": pair[0][:200], "type": pair[1][:80],
                                 "quote": pair[0][:2000]})
        relations = []
        for r in rels:
            if isinstance(r, (list, tuple)) and len(r) >= 4:
                si, pred, oi, quote = r[0], r[1], r[2], r[3]
                try:
                    si, oi = int(si), int(oi)
                except (TypeError, ValueError):
                    continue
                if not (0 <= si < len(entities) and 0 <= oi < len(entities)):
                    continue
                if not isinstance(pred, str) or not isinstance(quote, str):
                    continue
                relations.append({"subject": entities[si]["surface"],
                                  "predicate": pred[:120],
                                  "object": entities[oi]["surface"],
                                  "quote": quote[:2000]})
        items_out.append({"neighborhood_id": it.get("id") or it.get("neighborhood_id") or "",
                          "entities": entities, "relations": relations,
                          "digest": it.get("digest") or {}})
    return {"contract": "polymath-extraction-v1", "profile": "volume",
            "items": items_out}


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
    # Controller observability, captured AT THE CALL (not looked up later):
    # the lane's effective concurrency and, local lane, the batch-token
    # budget the call ran under — the climb is provable from receipts.
    limiter_effective: int | None = None
    batch_tokens_cap: int | None = None
    finish_reason: str | None = None    # "stop" | "length" (truncated) | None (unknown)
    # EXTRACTION-COVERAGE-V1: the REAL neighborhood ids this call carried,
    # in prompt order — the accounting authority for "sent vs returned".
    neighborhood_ids: list[str] = field(default_factory=list)
    reissue: bool = False               # second (single-neighborhood) pass


# Local batched lane: tokens per /infer_batch call. The ENV values are the
# SEED (known-clean with the fleet resident, measured 2026-08-29) and the
# CEILING; the AdaptiveBudget climbs from the persisted effective toward the
# ceiling and halves on GPU-OOM. 45K OOMed with the fleet resident.
LOCAL_BATCH_TOKENS_SEED_ENV = "POLYMATH_LLM_LOCAL_BATCH_TOKENS"
LOCAL_BATCH_TOKENS_MAX_ENV = "POLYMATH_LLM_LOCAL_BATCH_TOKENS_MAX"
LOCAL_BATCH_TOKENS_FLOOR = 4_000
LOCAL_BATCH_TOKENS_STEP = 2_000


def local_batch_budget():
    """The process-wide (and, with a store attached, fleet-wide) batch
    budget for the local lane."""
    seed = int(os.environ.get(LOCAL_BATCH_TOKENS_SEED_ENV, "28000"))
    ceiling = int(os.environ.get(LOCAL_BATCH_TOKENS_MAX_ENV, "72000"))
    return REGISTRY.budget("llm_local:batch_tokens", seed=seed,
                           floor=LOCAL_BATCH_TOKENS_FLOOR,
                           ceiling=max(seed, ceiling), step=LOCAL_BATCH_TOKENS_STEP)


class ExtractionTransportError(RuntimeError):
    """The endpoint was unreachable or repeatedly returned garbage."""


def output_budget_for(input_tokens: float, neighborhoods: int = 1) -> int:
    """Output cap per call = the LOCKED max_tokens (decision 18) per
    neighborhood, plus room for each additional neighborhood in the call.

    The former input-scaled budget (~400 tokens at an 800-token input)
    TRUNCATED the local lane: MEASURED 2026-08-30 on one Learning SQL
    parent — cap 484 → finish=length, salvaged JSON, 3 relations; cap
    2500 → self-terminated at 841 tokens, clean JSON, 9 relations. With
    repetition_penalty=1.15 the model self-terminates (config-fix report:
    ~600–840 tokens per parent), so the cap is a safety ceiling, never the
    working budget. `input_tokens` is kept for the signature; it no longer
    lowers the cap."""
    g = GENERATION_CONFIG
    return int(g["max_tokens"] + g["extra_tokens_per_neighborhood"] * max(0, neighborhoods - 1))


def estimate_input_tokens(user_prompt: str) -> int:
    return max(1, int(len(user_prompt) / 4.0))


def alias_neighborhoods(neighborhoods: list[tuple[str, list[tuple[str, str]]]]
                        ) -> tuple[list[tuple[str, list[tuple[str, str]]]], dict[str, str]]:
    """SHORT-ID CONTRACT (measured 2026-08-30): the local 4B model dropped
    the ':0' suffix of 70-char neighborhood ids in 5 of 25 calls, and every
    such packet was quarantined as SANITIZE_UNKNOWN_NEIGHBORHOOD. The model
    is never asked to echo a hash again: prompts carry `n1`, `n2`, … and the
    client maps them back to the real ids before the gate."""
    aliases = {f"n{i + 1}": nid for i, (nid, _) in enumerate(neighborhoods)}
    return [(alias, chunks) for alias, (_, chunks) in zip(aliases, neighborhoods)], aliases


def restore_neighborhood_ids(packet, aliases: dict[str, str]):
    """Map alias ids back to real neighborhood ids (in place)."""
    if packet is not None:
        for item in packet.items:
            item.neighborhood_id = aliases.get(item.neighborhood_id, item.neighborhood_id)
    return packet


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
                 timeout_s: float = 180.0, max_attempts: int = 2,
                 limiter_key: str = "default") -> None:
        if lane not in ("local", "cloud"):
            raise ValueError(f"unknown lane: {lane!r}")
        self.lane = lane
        # EXTRACTION-POOL-V1: each cloud endpoint throttles independently
        # (a slow provider must not drag the pool's AIMD budget down).
        self.limiter_key = limiter_key
        self.model = model
        self.base_url = url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        self._last_finish_reason: str | None = None

    # -- transport ---------------------------------------------------------

    def _chat(self, user_prompt: str, max_tokens: int) -> tuple[str, int, int]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": GENERATION_CONFIG["temperature"],
            "max_tokens": max_tokens,
            "stream": False,
        }
        if self.lane == "local":
            local = GENERATION_CONFIG["local"]
            # LOCKED (plan decision 18): kills exact-repeat degeneration
            # while preserving the JSON-structural repetition per object.
            payload["repetition_penalty"] = local["repetition_penalty"]
            payload["repetition_context_size"] = local["repetition_context_size"]
            # Qwen3.5 emits thinking into a separate `reasoning` field and
            # burns the output budget there; the chat template flag turns
            # it off (measured: 1600-token think → 38-token direct JSON).
            payload["chat_template_kwargs"] = {"enable_thinking": local["enable_thinking"]}
        else:
            # Cloud lane (Ollama daemon proxy): same thinking-burn failure
            # mode, different knob — measured 2026-08-29: without this the
            # 397B spends the entire output budget thinking (finish=length,
            # empty content); with it, direct JSON, finish=stop.
            payload["reasoning_effort"] = GENERATION_CONFIG["cloud"]["reasoning_effort"]
            # Structured output (measured 2026-08-30): json_object mode is
            # honored by the daemon (guaranteed-parseable JSON — the salvage
            # path should approach zero); json_schema strict:true is
            # SILENTLY IGNORED for this model — never rely on it.
            payload["response_format"] = {"type": "json_object"}
        resp = httpx.post(f"{self.base_url}/v1/chat/completions",
                          json=payload, timeout=self.timeout_s)
        resp.raise_for_status()
        body = resp.json()
        choice = (body.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        usage = body.get("usage") or {}
        self._last_finish_reason = choice.get("finish_reason")
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
                             self.limiter_key, _lane_limit(self.lane))

    def extract_batched(self, neighborhoods: list[tuple[str, list[tuple[str, str]]]],
                        *, source_bytes: int, threshold_bytes: int,
                        max_tokens: int = 2500) -> list[LLMCallResult]:
        """LOCAL batched transport: one neighborhood per prompt, decoded in
        a single batch_generate call (true batch parallelism, plan §4.2/§4.9).
        Falls back to per-neighborhood sequential calls when the endpoint
        does not advertise /infer_batch (older runtime)."""
        decision: LaneDecision | None = None
        if self.lane == "cloud":
            decision = require_cloud_eligible(source_bytes, threshold_bytes)
        limiter = self._lane_limiter()
        prompt_items = []
        for nid, chunks in neighborhoods:
            # one neighborhood per prompt → its alias is always "n1"
            user_prompt = build_user_prompt([("n1", chunks)])
            prompt_items.append((nid, user_prompt,
                                 output_budget_for(estimate_input_tokens(user_prompt))))
        if not prompt_items:
            return []
        # LEAN profile for the local lane: index-encoded contract cuts
        # output tokens (quotes only on relations; output tokens are the wall).
        # LEAN-COVERAGE-GATE (measured 2026-08-30 22:1x, first-hand): on real
        # book neighborhoods the 4B degenerates the index arrays
        # ([299,"PRODUCES",[300,...]] nesting, runaway indices) into invalid
        # JSON on ~50-90% of calls — rep-penalty on/off/soft all measured
        # non-causal (2/4, 2/4, 3/4 parse). The earlier "0 salvage" receipt
        # was survivorship (5 returned calls measured, 19 dropped ignored);
        # live corpus receipts: 40/40 and 19/24 neighborhoods DROPPED.
        # LEAN stays the default (owner's experiment continues via the JSON
        # grammar mask); POLYMATH_LEAN_LOCAL=off runs the proven flat
        # contract until the mask makes LEAN parse-safe.
        use_lean = (self.lane == "local"
                    and os.environ.get("POLYMATH_LEAN_LOCAL", "on").lower()
                    not in ("0", "off", "false"))
        # BATCH TOTAL-TOKEN CAP (measured 2026-08-29): a 45K-token batch
        # OOMs Metal when the fleet is resident on the shared GPU. Chunk
        # prompts so each HTTP call stays under the ADAPTIVE cap: clean
        # batches raise it (+step per K), a GPU-OOM 500 halves it AND the
        # call retries in halves — the budget persists across restarts.
        cap = local_batch_budget().effective
        sub_batches: list[list[tuple[str, str, int]]] = []
        cur: list[tuple[str, str, int]] = []
        cur_tokens = 0
        expected_out = GENERATION_CONFIG["expected_output_tokens"]
        for item in prompt_items:
            # budget by EXPECTED output (the model self-terminates), not
            # by the safety cap — otherwise a 2,500 cap would shrink every
            # batch to two prompts while ~850 tokens are actually produced
            itok = estimate_input_tokens(item[1]) + min(item[2], expected_out)
            if cur and cur_tokens + itok > cap:
                sub_batches.append(cur)
                cur, cur_tokens = [], 0
            cur.append(item)
            cur_tokens += itok
        if cur:
            sub_batches.append(cur)
        results: list[LLMCallResult] = []
        for sb in sub_batches:
            results.extend(self._infer_batch_call(sb, limiter, decision, cap, use_lean))
        return results

    def _infer_batch_call(self, prompt_items, limiter, decision,
                          cap: int | None = None,
                          use_lean: bool = False,
                          system_prompt: str | None = None) -> list[LLMCallResult]:
        """One /infer_batch call.

        GPU-OOM (500) halves the sub-batch and retries — AFTER the limiter
        slot is released (recursing while holding the slot deadlocks once
        record_failure halves the limit to 1) — and halves the persisted
        batch budget so the NEXT document starts below the OOM point; a
        clean batch feeds the budget's climb. 404 means an older runtime
        without /infer_batch: fall back to per-neighborhood calls through
        the OpenAI-compatible path (the documented fallback)."""
        budget = local_batch_budget() if self.lane == "local" else None
        if not limiter.acquire(est_tokens=sum(len(u) for _, u, _ in prompt_items) / 4.0):
            raise ExtractionTransportError(
                f"{self.lane} lane refused the batched call (breaker open "
                "or rate hold); stage must retry")
        t0 = time.perf_counter()
        total_est = sum(estimate_input_tokens(u) for _, u, _ in prompt_items) \
            + sum(mt for _, _, mt in prompt_items)
        batch_timeout = max(self.timeout_s, 60.0 + (total_est / 25.0) * 2.0)
        body: dict = {}
        status: int | None = None
        try:
            try:
                # BATCH-API-STABILIZATION-V1 (pre-refactor for
                # LATENT-TRANSFER-LAYER-V1 Phase B): an explicit
                # system_prompt overrides the profile selection so future
                # compilers (parent enrichment) reuse this transport
                # without re-threading a new flag through the recursion.
                sys_prompt = system_prompt or (
                    LEAN_SYSTEM_PROMPT if use_lean else SYSTEM_PROMPT)
                resp = httpx.post(
                    f"{self.base_url}/infer_batch",
                    json={"prompts": [{"system": sys_prompt, "user": u,
                                       "max_tokens": mt}
                                      for _, u, mt in prompt_items],
                          "max_tokens": max(mt for _, _, mt in prompt_items)},
                    timeout=batch_timeout)
                resp.raise_for_status()
                body = resp.json()
                if not isinstance(body, dict):
                    raise ExtractionTransportError(
                        f"{self.lane} batched transport returned a non-object body")
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                limiter.record_failure(
                    retry_after=exc.response.headers.get("retry-after"),
                    headers=dict(exc.response.headers))
                halve = status == 500 and len(prompt_items) > 1
                if not halve and status != 404:
                    raise ExtractionTransportError(
                        f"{self.lane} batched transport failed: "
                        f"HTTP {status}") from exc
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                limiter.record_failure()
                raise ExtractionTransportError(
                    f"{self.lane} batched transport failed: "
                    f"{type(exc).__name__}: {exc}") from exc
            else:
                limiter.record_success()
                if budget is not None:
                    budget.record_success()
        finally:
            limiter.release()
        if status == 500:
            if budget is not None:
                budget.record_oom()
            half = len(prompt_items) // 2
            out = self._infer_batch_call(prompt_items[:half], limiter, decision, cap,
                                         use_lean, system_prompt)
            out.extend(self._infer_batch_call(prompt_items[half:], limiter, decision, cap,
                                              use_lean, system_prompt))
            return out
        if status == 404:
            fallback: list[LLMCallResult] = []
            for nid, u, mt in prompt_items:
                one = self._extract_prompt(u, {nid}, mt, decision)
                one.neighborhood_ids = [nid]
                fallback.append(one)
            return fallback
        results = body.get("results")
        rows = [dict(x or {}) for x in results] if isinstance(results, list) else []
        if len(rows) != len(prompt_items):         # misaligned batch: refuse
            rows = (rows + [{}] * len(prompt_items))[:len(prompt_items)]
        out: list[LLMCallResult] = []
        wall_ms = int((time.perf_counter() - t0) * 1000)
        for (nid, user_prompt, mt), row in zip(prompt_items, rows):
            raw = str(row.get("content", ""))
            if use_lean and raw.lstrip().startswith("{"):
                import json as _json
                try:
                    loose = _json.loads(raw, strict=False)
                except Exception:
                    loose = None
                if isinstance(loose, dict) and loose.get("items") \
                        and isinstance(loose["items"][0], dict) \
                        and "e" in loose["items"][0]:
                    raw = _json.dumps(_lean_expand(loose))
            s_res, packet = sanitize(raw, {"n1"})
            packet = restore_neighborhood_ids(packet, {"n1": nid})
            out.append(LLMCallResult(
                lane=self.lane, model=self.model, raw_text=raw, packet=packet,
                sanitize=s_res, wall_ms=wall_ms,
                tokens_in=int(row.get("prompt_tokens") or 0),
                tokens_out=int(row.get("completion_tokens") or 0),
                attempts=1, raw_head=raw[:200],
                error_class=None if packet is not None else _quarantine_class(s_res),
                lane_decision=decision,
                limiter_effective=limiter.effective,
                batch_tokens_cap=cap,
                finish_reason=row.get("stop_reason"),
                neighborhood_ids=[nid]))
        return out

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
        aliased, aliases = alias_neighborhoods(neighborhoods)
        user_prompt = build_user_prompt(aliased)
        if max_tokens is None:
            max_tokens = output_budget_for(estimate_input_tokens(user_prompt), len(neighborhoods))
        result = self._extract_prompt(user_prompt, set(aliases), max_tokens, decision)
        restore_neighborhood_ids(result.packet, aliases)
        result.neighborhood_ids = [nid for nid, _ in neighborhoods]
        return result

    def complete_batched(self, items: list[tuple[str, str, str, int]],
                         ) -> list[tuple[str, str, str | None]]:
        """BATCH-API-STABILIZATION-V1 (the LATENT-TRANSFER-LAYER-V1
        Phase-B contract, built ahead of it): raw batched completion for
        non-extraction compilers. items = (id, system, user, max_tokens);
        returns (id, raw_text, error_class|None) in input order. Reuses
        the lane limiter, the adaptive batch-token budget, and GPU-OOM
        halving; performs NO sanitize/parse — the caller's gate owns the
        contract. Per-item system prompts ride the sidecar's native
        per-prompt `system` field."""
        budget = local_batch_budget() if self.lane == "local" else None
        limiter = self._lane_limiter()
        cap = budget.effective if budget is not None else None

        def run(batch: list[tuple[str, str, str, int]]
                ) -> list[tuple[str, str, str | None]]:
            if not limiter.acquire(
                    est_tokens=sum(len(u) for _, _, u, _ in batch) / 4.0):
                return [(i, "", "LIMITER_REFUSED") for i, _, _, _ in batch]
            status: int | None = None
            body: dict = {}
            try:
                try:
                    resp = httpx.post(
                        f"{self.base_url}/infer_batch",
                        json={"prompts": [
                            {"system": sys_p, "user": u, "max_tokens": mt}
                            for _, sys_p, u, mt in batch],
                            "max_tokens": max(mt for _, _, _, mt in batch)},
                        timeout=max(self.timeout_s, 120.0))
                    resp.raise_for_status()
                    body = resp.json()
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    limiter.record_failure(
                        retry_after=exc.response.headers.get("retry-after"),
                        headers=dict(exc.response.headers))
                    if not (status == 500 and len(batch) > 1):
                        return [(i, "", f"TRANSPORT_HTTP_{status}")
                                for i, _, _, _ in batch]
                except (httpx.HTTPError, json.JSONDecodeError) as exc:
                    limiter.record_failure()
                    return [(i, "", f"TRANSPORT_{type(exc).__name__}")
                            for i, _, _, _ in batch]
                else:
                    limiter.record_success()
                    if budget is not None:
                        budget.record_success()
            finally:
                limiter.release()
            if status == 500:                      # GPU OOM: halve and retry
                if budget is not None:
                    budget.record_oom()
                half = len(batch) // 2
                return run(batch[:half]) + run(batch[half:])
            rows = body.get("results")
            rows = list(rows) if isinstance(rows, list) else []
            rows = (rows + [{}] * len(batch))[:len(batch)]
            return [(i, str((r or {}).get("content", "")),
                     None if (r or {}).get("content") else "EMPTY_COMPLETION")
                    for (i, _, _, _), r in zip(batch, rows)]

        out: list[tuple[str, str, str | None]] = []
        cur: list[tuple[str, str, str, int]] = []
        cur_tokens = 0
        for item in items:
            itok = estimate_input_tokens(item[2]) + min(
                item[3], GENERATION_CONFIG["expected_output_tokens"])
            if cur and cap is not None and cur_tokens + itok > cap:
                out.extend(run(cur))
                cur, cur_tokens = [], 0
            cur.append(item)
            cur_tokens += itok
        if cur:
            out.extend(run(cur))
        return out

    def _extract_prompt(self, user_prompt: str, expected: set[str],
                        max_tokens: int, decision: LaneDecision | None) -> LLMCallResult:
        """The retry loop behind `extract`. Slot discipline: the limiter
        slot is released in a `finally` on EVERY exit (transport error,
        malformed body shape, retryable status), never leaked."""
        limiter = self._lane_limiter()
        est_tokens = estimate_input_tokens(user_prompt) + max_tokens / 2.0
        attempts = 0
        last_raw = ""
        last_sanitize: SanitizeResult | None = None
        tokens_in = tokens_out = 0
        nudge = ""
        t0 = time.perf_counter()
        while attempts < self.max_attempts:
            attempts += 1
            if not limiter.acquire(est_tokens=est_tokens):
                # breaker open / rate hold: no network I/O made. The caller
                # (run_proposals) turns this into a stage failure so the
                # ticket retries — it is never a completed extraction.
                return LLMCallResult(
                    lane=self.lane, model=self.model, raw_text="",
                    packet=None,
                    sanitize=SanitizeResult(ok=False, error_class="LIMITER_REFUSED"),
                    wall_ms=int((time.perf_counter() - t0) * 1000),
                    attempts=attempts, error_class="LIMITER_REFUSED",
                    lane_decision=decision, limiter_effective=limiter.effective)
            retry_delay: float | None = None
            try:
                try:
                    raw, tin, tout = self._chat(user_prompt + nudge, max_tokens)
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    limiter.record_failure(
                        retry_after=exc.response.headers.get("retry-after"),
                        headers=dict(exc.response.headers))
                    # TRANSPORT-RETRY-500-V1 (measured 2026-08-30): one
                    # transient Ollama 500 raised ExtractionTransportError
                    # and failed the ENTIRE extract stage — 6 minutes of
                    # cloud spend burned, the document re-run on the
                    # ticket's second attempt. A daemon-proxy 500 is as
                    # transient as 502/503; the limiter already recorded
                    # the failure (backoff), and a repeat still fails closed.
                    if status in (429, 500, 502, 503, 504) and attempts < self.max_attempts:
                        retry_delay = min(
                            parse_retry_after(exc.response.headers.get("retry-after")) or 1.5,
                            15.0)
                    else:
                        raise ExtractionTransportError(
                            f"{self.lane} transport failed: HTTP {status}") from exc
                except (httpx.HTTPError, json.JSONDecodeError, KeyError) as exc:
                    limiter.record_failure()
                    raise ExtractionTransportError(
                        f"{self.lane} transport failed: {type(exc).__name__}: {exc}") from exc
                except Exception as exc:
                    # malformed body SHAPE (non-numeric usage, non-dict
                    # choice, ...): a transport fault, not a model fault
                    limiter.record_failure()
                    raise ExtractionTransportError(
                        f"{self.lane} transport returned a malformed body: "
                        f"{type(exc).__name__}: {exc}") from exc
                else:
                    limiter.record_success()
            finally:
                limiter.release()
            if retry_delay is not None:
                time.sleep(retry_delay)         # slot already released
                continue
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
                    raw_head=raw[:200], lane_decision=decision,
                    limiter_effective=limiter.effective,
                    finish_reason=self._last_finish_reason)
            nudge = _retry_nudge(s_res)
        return LLMCallResult(
            lane=self.lane, model=self.model, raw_text=last_raw, packet=None,
            sanitize=last_sanitize or SanitizeResult(ok=False, error_class="SANITIZE_UNPARSEABLE"),
            wall_ms=int((time.perf_counter() - t0) * 1000),
            tokens_in=tokens_in, tokens_out=tokens_out, attempts=attempts,
            error_class=_quarantine_class(last_sanitize), raw_head=last_raw[:200],
            lane_decision=decision, limiter_effective=limiter.effective)
