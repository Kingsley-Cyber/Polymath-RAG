"""One tiny request per chat model through the (fixed) synthesis transport: does it answer, how fast, does thinking come back?
Prints no credentials. usage: PYTHONPATH=<tree>/shared:<tree>/orchestrator:<tree>/workers python model_canary.py <out.json>"""
import json
import os
import sys
import time

import httpx
import litellm

from orchestrator.api import ui
from polymath_shared.reasoning_policy import CHAT_SYNTHESIS, apply_litellm, ollama_think

OUT = sys.argv[1]
PROMPT = [{"role": "user", "content": "Reply with exactly the single word OK and nothing else."}]
results = []

for e in ui._litellm_models():
    sid = e["id"]
    model = sid.split(":", 1)[1]
    kw = dict(model=model, messages=PROMPT, stream=True, timeout=90, **ui._litellm_credentials(model))
    applied = apply_litellm(kw, CHAT_SYNTHESIS, model)
    t0 = time.perf_counter(); first = None; content = ""; reasoning = 0; err = None
    try:
        for chunk in litellm.completion(**kw, max_tokens=512):
            try:
                d = chunk.choices[0].delta
            except Exception:  # noqa: BLE001
                continue
            r = getattr(d, "reasoning_content", None) or ""
            reasoning += len(r)
            c = d.content or ""
            if c and first is None:
                first = time.perf_counter() - t0
            content += c
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {str(exc)[:160]}".replace("\n", " ")
    row = {"id": sid, "route": "litellm", "ok": err is None and bool(content.strip()), "seconds": round(time.perf_counter() - t0, 1),
           "first_token_s": round(first, 1) if first else None, "answer": content.strip()[:40], "reasoning_chars": reasoning,
           "control_sent": {**applied.get("top_level", {}), **applied.get("extra_body", {})}, "error": err}
    results.append(row)
    print(json.dumps(row), flush=True)

for e in ui._ollama_models():
    model = e["model"]
    think = ollama_think(model)
    t0 = time.perf_counter(); err = None; content = ""; thinking = ""; fallback = False
    try:
        r = httpx.post(f"{ui.OLLAMA_URL}/api/chat", json={"model": model, "messages": PROMPT, "stream": False, "think": think},
                       timeout=httpx.Timeout(120, connect=10))
        if r.status_code != 200 and "think" in r.text.lower():
            fallback = True
            r = httpx.post(f"{ui.OLLAMA_URL}/api/chat", json={"model": model, "messages": PROMPT, "stream": False},
                           timeout=httpx.Timeout(120, connect=10))
        if r.status_code != 200:
            err = f"HTTP {r.status_code}: {r.text[:160]}".replace("\n", " ")
        else:
            m = (r.json() or {}).get("message") or {}
            content, thinking = m.get("content") or "", m.get("thinking") or ""
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {str(exc)[:160]}".replace("\n", " ")
    row = {"id": e["id"], "route": "ollama", "ok": err is None and bool(content.strip()), "seconds": round(time.perf_counter() - t0, 1),
           "answer": content.strip()[:40], "reasoning_chars": len(thinking), "control_sent": {"think": think},
           "think_rejected_fell_back_to_default": fallback, "available_in_daemon": e.get("available"), "error": err}
    results.append(row)
    print(json.dumps(row), flush=True)

json.dump(results, open(OUT, "w"), indent=1)
