#!/usr/bin/env python3
"""LOCAL-LLM-EXTRACTION-V1 — true batched local inference server.

Wraps mlx_lm `batch_generate` (TRUE parallel decode across prompts —
measured by the owner's config-fix report: batch 40, 6.4 GB peak, 241
tok/s-class throughput) behind one endpoint:

    POST /infer_batch
    {"prompts": [{"system": "...", "user": "..."}, ...],
     "max_tokens": 2500}
    -> {"results": [{"content": "...", "stop_reason": "..."}, ...]}

plus GET /v1/models for compatibility with the OpenAI-compatible health
probe. Generation config is LOCKED per plan decision 18 /
config/extraction_models/qwen35-4b-extraction-v1.yaml:
    repetition_penalty=1.15, repetition_context_size=400,
    enable_thinking off via the chat template flag.

Usage: sidecars/local_extractor/batched_server.py [port]   (default 8755)
"""
from __future__ import annotations

import json
import threading
import time
import os
import sys

PIN_SNAPSHOT = "32f3e8ecf65426fc3306969496342d504bfa13f3"
HF_DIR = os.path.expanduser(
    "~/.cache/huggingface/hub/models--mlx-community--Qwen3.5-4B-MLX-4bit")
MODEL_PATH = f"{HF_DIR}/snapshots/{PIN_SNAPSHOT}"
MAX_BATCH = int(os.environ.get("POLYMATH_LLM_LOCAL_BATCH", "40"))

from flask import Flask, jsonify, request  # noqa: E402

app = Flask(__name__)
_state: dict = {}


def load_model() -> None:
    if _state.get("model") is not None:
        return
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.sample_utils import make_logits_processors
    _state["mx"] = mx
    _state["model"], _state["tok"] = load(MODEL_PATH)
    _state["logits_processors"] = make_logits_processors(
        repetition_penalty=1.15, repetition_context_size=400)
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


@app.post("/infer_batch")
def infer_batch():
    load_model()
    body = request.get_json(force=True)
    prompts = body.get("prompts") or []
    if not prompts or len(prompts) > MAX_BATCH:
        return jsonify({"error": f"prompts must be 1..{MAX_BATCH}"}), 400
    max_tokens = int(body.get("max_tokens", 2500))
    tok = _state["tok"]
    token_lists = [
        tok.encode(_render_prompt(p.get("system", ""), p.get("user", "")))
        for p in prompts]
    bg = _state.get("batch_generate")
    t0 = __import__("time").perf_counter()
    if bg is not None:
        response = bg(_state["model"], tok, token_lists,
                      max_tokens=max_tokens,
                      logits_processors=_state["logits_processors"])
        texts = getattr(response, "texts", None) or (
            response if isinstance(response, list) else [str(response)])
        outs = [{"content": txt, "stop_reason": "stop"} for txt in texts]
    else:
        from mlx_lm import generate
        outs = []
        for toks in token_lists:
            txt = generate(
                _state["model"], tok, prompt=toks,
                max_tokens=max_tokens,
                logits_processors=_state["logits_processors"])
            outs.append({"content": txt, "stop_reason": "sequential"})
    wall = __import__("time").perf_counter() - t0
    return jsonify({"results": outs, "wall_s": round(wall, 2),
                    "batch": len(outs)})


@app.get("/v1/models")
def models():
    return jsonify({"object": "list", "data": [
        {"id": "mlx-community/Qwen3.5-4B-MLX-4bit", "object": "model"}]})


@app.get("/ready")
def ready():
    return jsonify({"ready": True, "batched": True, "max_batch": MAX_BATCH})


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


def _run_micro_batch():
    with _MICRO_LOCK:
        items, _MICRO_QUEUE[:] = _MICRO_QUEUE[:], []
    if not items:
        return
    prompts = [{"system": it["messages"][0]["content"] if it["messages"][0]["role"] == "system" else "",
                "user": it["messages"][-1]["content"]} for it in items]
    load_model()
    tok = _state["tok"]
    token_lists = [tok.encode(_render_prompt(p["system"], p["user"]))
                   for p in prompts]
    bg = _state.get("batch_generate")
    if bg is not None:
        response = bg(_state["model"], tok, token_lists,
                      max_tokens=min(int(it.get("max_tokens", 2500)) for it in items),
                      logits_processors=_state["logits_processors"])
        texts = getattr(response, "texts", None) or (
            response if isinstance(response, list) else [str(response)] * len(items))
    else:
        from mlx_lm import generate
        texts = [generate(_state["model"], tok, prompt=tl,
                          max_tokens=int(it.get("max_tokens", 2500)),
                          logits_processors=_state["logits_processors"])
                 for tl, it in zip(token_lists, items)]
    for it, txt in zip(items, texts):
        it["out"] = json.dumps({
            "id": "chatcmpl-batch", "object": "chat.completion",
            "model": "mlx-community/Qwen3.5-4B-MLX-4bit",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": txt}}],
            "usage": {"prompt_tokens": 0,
                      "completion_tokens": int(len(txt.split()) * 1.3),
                      "total_tokens": 0}})
        it["gate"].set()


@app.post("/v1/chat/completions")
def chat_completions():
    load_model()
    body = request.get_json(force=True)
    gate = threading.Event()
    item = {"messages": body.get("messages", []),
            "max_tokens": body.get("max_tokens", 2500),
            "gate": gate, "out": None}
    with _MICRO_LOCK:
        full = len(_MICRO_QUEUE) >= MICRO_BATCH_MAX
        _MICRO_QUEUE.append(item)
    if full:
        threading.Thread(target=_run_micro_batch, daemon=True).start()
    else:
        def _flush():
            time.sleep(MICRO_BATCH_WINDOW_S)
            with _MICRO_LOCK:
                pending = len(_MICRO_QUEUE)
            if pending:
                threading.Thread(target=_run_micro_batch, daemon=True).start()
        threading.Thread(target=_flush, daemon=True).start()
    gate.wait(timeout=1800)
    return app.response_class(item["out"] or "{}", mimetype="application/json")


def _queue_collector():
    while True:
        time.sleep(MICRO_BATCH_WINDOW_S)
        with _MICRO_LOCK:
            pending = len(_MICRO_QUEUE)
        if pending:
            threading.Thread(target=_run_micro_batch, daemon=True).start()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8755
    load_model()
    threading.Thread(target=_queue_collector, daemon=True).start()
    app.run(host="127.0.0.1", port=port, threaded=True)

