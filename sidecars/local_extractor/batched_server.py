#!/usr/bin/env python3
"""LOCAL-LLM-EXTRACTION-V1 — true batched local inference server.

Wraps mlx_lm `batch_generate` (TRUE parallel decode across prompts —
measured by the owner's config-fix report: batch 40, 6.4 GB peak, 241
tok/s-class throughput) behind one endpoint:

    POST /infer_batch
    {"prompts": [{"system": "...", "user": "...", "max_tokens": 400}, ...],
     "max_tokens": 2500}
    -> {"results": [{"content": "...", "stop_reason": "stop|length",
                     "completion_tokens": N}, ...]}

plus GET /v1/models for compatibility with the OpenAI-compatible health
probe. Generation config is LOCKED per plan decision 18 /
config/extraction_models/qwen35-4b-extraction-v1.yaml:
    repetition_penalty=1.15, repetition_context_size=400,
    enable_thinking off via the chat template flag.

Runtime guarantees (audit 2026-08-29):
  * ONE generation at a time on the device (`_GEN_LOCK`): /infer_batch and
    the /v1 micro-batcher never decode concurrently.
  * Every queued /v1 request is answered exactly once, including when
    generation raises (error body, HTTP 500) — nothing waits out the gate.
  * Per-item output budget: the batch decodes to the LARGEST budget, each
    item is cut to ITS OWN budget, and `finish_reason`/`stop_reason`
    reports "length" honestly. completion_tokens are real token counts.
  * `max_tokens` is clamped to POLYMATH_LLM_LOCAL_MAX_TOKENS (default 4096).

Usage: sidecars/local_extractor/batched_server.py [port]   (default 8755)
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

PIN_SNAPSHOT = "32f3e8ecf65426fc3306969496342d504bfa13f3"
HF_DIR = os.path.expanduser(
    "~/.cache/huggingface/hub/models--mlx-community--Qwen3.5-4B-MLX-4bit")
MODEL_PATH = f"{HF_DIR}/snapshots/{PIN_SNAPSHOT}"
MODEL_ID = "mlx-community/Qwen3.5-4B-MLX-4bit"
MAX_BATCH = int(os.environ.get("POLYMATH_LLM_LOCAL_BATCH", "40"))
SERVER_MAX_TOKENS = int(os.environ.get("POLYMATH_LLM_LOCAL_MAX_TOKENS", "4096"))
DEFAULT_MAX_TOKENS = 2500
CACHE_LIMIT_BYTES = int(float(os.environ.get("POLYMATH_LLM_LOCAL_CACHE_GB", "1.0")) * 2**30)
MEMORY_LIMIT_BYTES = int(float(os.environ.get("POLYMATH_LLM_LOCAL_MEMORY_GB", "12.0")) * 2**30)
GATE_WAIT_S = 1800.0

from flask import Flask, jsonify, request

app = Flask(__name__)
_state: dict = {}
_GEN_LOCK = threading.Lock()          # one decode on the device at a time
_LOAD_LOCK = threading.Lock()


def load_model() -> None:
    with _LOAD_LOCK:
        if _state.get("model") is not None:
            return
        import mlx.core as mx
        from mlx_lm import load
        from mlx_lm.sample_utils import make_logits_processors
        _state["mx"] = mx
        # MEMORY DISCIPLINE (measured 2026-08-30): MLX's buffer cache keeps
        # every past allocation peak — the idle server sat at 24 GB wired
        # on a 32 GB machine (7% free, 16.8 GB swap) and the next batch
        # OOMed Metal (33 × HTTP 500). Cap the cache, cap total Metal
        # memory (an over-limit allocation raises → 500 → the client's
        # batch-budget AIMD halves, instead of the whole machine swapping),
        # and give the cache back after every batch.
        try:
            mx.set_cache_limit(CACHE_LIMIT_BYTES)
            mx.set_memory_limit(MEMORY_LIMIT_BYTES)
        except Exception as exc:  # noqa: BLE001 — older mlx: best effort
            print(f"mlx memory limits unavailable: {exc}", file=sys.stderr)
        _state["model"], _state["tok"] = load(MODEL_PATH)
        processors = make_logits_processors(
            repetition_penalty=1.15, repetition_context_size=400)
        # JSON-GRAMMAR-MASK-V1: structurally-illegal tokens (prose outside
        # JSON, markdown fences, stray punctuation) masked to -inf at every
        # decode step. Fail-open: if the mask cannot compile, generation
        # proceeds with prompt+gate enforcement only (measured 2026-08-30:
        # 37% of local calls needed salvage repair without it).
        import os as _os
        if _os.environ.get("POLYMATH_JSON_MASK", "on").lower() in ("0", "off", "false"):
            print("json grammar mask: DISABLED by env (PERF 2026-08-30: "
                  "per-step prefix re-decode cost quadratic at batch scale "
                  "— pending incremental-state fix)", file=sys.stderr)
        else:
            try:
                from json_mask import make_json_mask
                _mask = make_json_mask(_state["tok"])
                if _mask is not None:
                    processors = processors + [_mask]
                    print("json grammar mask: ON", file=sys.stderr)
                else:
                    print("json grammar mask: unavailable (fail-open)", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                print(f"json grammar mask failed to load: {exc} (fail-open)", file=sys.stderr)
        _state["logits_processors"] = processors
        try:
            from mlx_lm.generate import batch_generate
            _state["batch_generate"] = batch_generate
        except ImportError:  # older mlx_lm: batched steps API
            _state["batch_generate"] = None


def _render_prompt(system: str, user: str) -> str:
    tok = _state["tok"]
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": user}]
    try:
        out = tok.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False,
            enable_thinking=False)
    except TypeError:
        out = tok.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False)
    if isinstance(out, list):        # tokenizer returned ids directly
        out = tok.decode(out)
    return out


def _clamp_tokens(value, default: int = DEFAULT_MAX_TOKENS) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, SERVER_MAX_TOKENS))


def _finalize(tok, text: str, budget: int) -> dict:
    """Cut one decoded item to its own budget and report the truth."""
    ids = tok.encode(text)
    if len(ids) > budget:
        return {"content": tok.decode(ids[:budget]), "finish_reason": "length",
                "completion_tokens": budget}
    return {"content": text,
            "finish_reason": "length" if len(ids) >= budget else "stop",
            "completion_tokens": len(ids)}


def _generate(token_lists: list[list[int]], budgets: list[int]) -> list[dict]:
    """ONE serialized generation over the model for a batch of prompts."""
    load_model()
    tok = _state["tok"]
    bg = _state.get("batch_generate")
    with _GEN_LOCK:
        if bg is not None:
            response = bg(_state["model"], tok, token_lists,
                          max_tokens=max(budgets),
                          logits_processors=_state["logits_processors"])
            texts = getattr(response, "texts", None) or (
                response if isinstance(response, list) else [str(response)])
        else:
            from mlx_lm import generate
            texts = [generate(_state["model"], tok, prompt=tl, max_tokens=b,
                              logits_processors=_state["logits_processors"])
                     for tl, b in zip(token_lists, budgets)]
    try:
        _state["mx"].clear_cache()      # return the batch's buffers to the OS
    except Exception:  # noqa: BLE001
        pass
    if len(texts) != len(token_lists):
        raise RuntimeError(
            f"batch_generate returned {len(texts)} texts for {len(token_lists)} prompts")
    return [_finalize(tok, str(t), b) for t, b in zip(texts, budgets)]


@app.post("/infer_batch")
def infer_batch():
    body = request.get_json(force=True, silent=True) or {}
    prompts = body.get("prompts") or []
    if (not isinstance(prompts, list) or not prompts or len(prompts) > MAX_BATCH
            or not all(isinstance(p, dict) for p in prompts)):
        return jsonify({"error": f"prompts must be 1..{MAX_BATCH} objects"}), 400
    default_budget = _clamp_tokens(body.get("max_tokens", DEFAULT_MAX_TOKENS))
    budgets = [_clamp_tokens(p.get("max_tokens", default_budget), default_budget)
               for p in prompts]
    t0 = time.perf_counter()
    try:
        load_model()
        tok = _state["tok"]
        token_lists = [
            tok.encode(_render_prompt(str(p.get("system", "")), str(p.get("user", ""))))
            for p in prompts]
        results = _generate(token_lists, budgets)
    except Exception as exc:  # noqa: BLE001 — contained: the caller gets a typed failure
        return jsonify({"error": f"{type(exc).__name__}: {exc}",
                        "type": "generation_failed"}), 500
    outs = [{"content": r["content"], "stop_reason": r["finish_reason"],
             "completion_tokens": r["completion_tokens"],
             "prompt_tokens": len(tl)}
            for r, tl in zip(results, token_lists)]
    wall = time.perf_counter() - t0
    return jsonify({"results": outs, "wall_s": round(wall, 2),
                    "batch": len(outs)})


@app.get("/v1/models")
def models():
    return jsonify({"object": "list", "data": [
        {"id": MODEL_ID, "object": "model"}]})


@app.get("/ready")
def ready():
    mem = {}
    try:
        mx = _state.get("mx")
        if mx is not None:
            mem = {"active_gb": round(mx.get_active_memory() / 2**30, 2),
                   "cache_gb": round(mx.get_cache_memory() / 2**30, 2),
                   "peak_gb": round(mx.get_peak_memory() / 2**30, 2)}
    except Exception:  # noqa: BLE001
        pass
    return jsonify({"ready": True, "batched": True, "max_batch": MAX_BATCH,
                    "max_tokens": SERVER_MAX_TOKENS, "memory": mem,
                    "limits_gb": {"cache": CACHE_LIMIT_BYTES / 2**30,
                                  "memory": MEMORY_LIMIT_BYTES / 2**30}})


# ---------------------------------------------------------------------------
# OpenAI-compatible micro-batching: concurrent single chat requests are
# queued for MICRO_BATCH_WINDOW_S and decoded as ONE batch — the fleet's
# existing OpenAI-compatible client gets batch-40 throughput with no
# client change.
# ---------------------------------------------------------------------------
_MICRO_QUEUE: list = []
_MICRO_LOCK = threading.Lock()
MICRO_BATCH_WINDOW_S = 0.30
MICRO_BATCH_MAX = min(8, MAX_BATCH)


def _split_messages(messages) -> tuple[str, str]:
    """(system, user) from an OpenAI messages list; raises ValueError on a
    shape that cannot be rendered (checked BEFORE enqueue, so a bad request
    is a 400 and never poisons a batch)."""
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    if not all(isinstance(m, dict) and isinstance(m.get("content"), str)
               for m in messages):
        raise ValueError("every message needs a string content")
    system = messages[0]["content"] if messages[0].get("role") == "system" else ""
    return system, messages[-1]["content"]


def _error_body(exc: BaseException) -> str:
    return json.dumps({"error": {"message": f"{type(exc).__name__}: {exc}",
                                 "type": "generation_failed"}})


def _run_micro_batch():
    with _MICRO_LOCK:
        items, _MICRO_QUEUE[:] = _MICRO_QUEUE[:], []
    if not items:
        return
    try:
        load_model()
        tok = _state["tok"]
        token_lists = [tok.encode(_render_prompt(it["system"], it["user"]))
                       for it in items]
        results = _generate(token_lists, [it["max_tokens"] for it in items])
        for it, r, tl in zip(items, results, token_lists):
            it["out"] = json.dumps({
                "id": "chatcmpl-batch", "object": "chat.completion",
                "model": MODEL_ID,
                "choices": [{"index": 0, "finish_reason": r["finish_reason"],
                             "message": {"role": "assistant", "content": r["content"]}}],
                "usage": {"prompt_tokens": len(tl),
                          "completion_tokens": r["completion_tokens"],
                          "total_tokens": len(tl) + r["completion_tokens"]}})
            it["status"] = 200
    except Exception as exc:  # noqa: BLE001 — every queued item is answered
        body = _error_body(exc)
        for it in items:
            if it.get("out") is None:
                it["out"], it["status"] = body, 500
    finally:
        for it in items:        # answered exactly once, whatever happened
            it["gate"].set()


@app.post("/v1/chat/completions")
def chat_completions():
    body = request.get_json(force=True, silent=True) or {}
    try:
        system, user = _split_messages(body.get("messages"))
    except ValueError as exc:
        return jsonify({"error": {"message": str(exc), "type": "invalid_request"}}), 400
    gate = threading.Event()
    item = {"system": system, "user": user,
            "max_tokens": _clamp_tokens(body.get("max_tokens", DEFAULT_MAX_TOKENS)),
            "gate": gate, "out": None, "status": None}
    with _MICRO_LOCK:
        _MICRO_QUEUE.append(item)
        full = len(_MICRO_QUEUE) >= MICRO_BATCH_MAX
    if full:
        threading.Thread(target=_run_micro_batch, daemon=True).start()
    else:
        # window flush (also covers an app imported without the collector
        # thread); drains are idempotent — an empty queue returns at once —
        # and generation itself is serialized by _GEN_LOCK
        def _flush():
            time.sleep(MICRO_BATCH_WINDOW_S)
            _run_micro_batch()
        threading.Thread(target=_flush, daemon=True).start()
    if not gate.wait(timeout=GATE_WAIT_S):
        return app.response_class(
            json.dumps({"error": {"message": "generation did not complete",
                                  "type": "timeout"}}),
            status=504, mimetype="application/json")
    return app.response_class(item["out"], status=item["status"] or 200,
                              mimetype="application/json")


def _queue_collector():
    while True:
        time.sleep(MICRO_BATCH_WINDOW_S)
        with _MICRO_LOCK:
            pending = len(_MICRO_QUEUE)
        if pending:
            _run_micro_batch()      # in-line: one drainer, serialized by _GEN_LOCK anyway


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8755
    load_model()
    threading.Thread(target=_queue_collector, daemon=True).start()
    app.run(host="127.0.0.1", port=port, threaded=True)
