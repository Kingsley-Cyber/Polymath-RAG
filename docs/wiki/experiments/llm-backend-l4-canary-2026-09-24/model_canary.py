"""Every-model canary (register 11.470): one real call per untested provider lane (production client: limiter + ledger) and per chat
answer model (the chat path's credentials + reasoning policy + output bound). Every call is recorded in
llm_provider_attempts with stage=model_canary. Prints no secrets."""
import json
import time

import httpx
from polymath_shared.conformance.attempts import Attempt, attempt_context, record
from polymath_shared.llm_extraction.client import LLMExtractionClient
from polymath_shared.llm_extraction.pool import cloud_endpoints, lane_max_tokens
from polymath_shared.reasoning_policy import CHAT_SYNTHESIS, apply_litellm, ollama_think

OUT = __file__.replace("model_canary.py", "model_canary.json")
SYSTEM = "You are a connectivity canary. Answer with exactly one word. If you must answer in JSON, use {\"answer\": \"OK\"}."
USER = "Reply with the word OK."
done = {r["lane"] for r in json.load(open("docs/wiki/experiments/llm-backend-l4-canary-2026-09-24/canary.json"))
        if r.get("result") == "OK"}
rows = []

# ---- provider lanes (production client)
for ep in cloud_endpoints():
    if ep.name in done:
        continue
    c = LLMExtractionClient("cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key, api_key=ep.api_key,
                            cloud_opts=ep.cloud_opts, timeout_s=60.0, max_attempts=1)
    c.endpoint_name = ep.name
    c.attempt_stage, c.attempt_function = "model_canary", "CANARY"
    t0 = time.monotonic()
    text, err = c.complete_one(USER, system_prompt=SYSTEM, max_tokens=lane_max_tokens(ep, 256))
    rows.append({"kind": "lane", "name": ep.name, "model": ep.model,
                 "result": "OK" if (err is None and (text or "").strip()) else (err or "EMPTY_TEXT"),
                 "reply": (text or "").strip()[:30], "ms": int((time.monotonic() - t0) * 1000)})
    time.sleep(0.3)

# ---- chat answer models (the chat path's request shape)
from orchestrator.api import ui  # noqa: E402

offered = ui.synthesizers()["synthesizers"]
for e in offered:
    sid = e["id"]
    kind, model = sid.split(":", 1)
    t0 = time.monotonic()
    base = dict(lane=f"chat_synth:{model.split('/')[0]}" if "/" in model else "chat_synth", model=model,
                provider=(model.split("/")[0] if "/" in model else "ollama"), limiter_admitted=False,
                limiter_bypassed=True, http_dispatched=True)
    try:
        if kind == "litellm":
            import litellm
            kwargs = dict(model=model, messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}],
                          stream=False, timeout=90, **ui._litellm_credentials(model))
            apply_litellm(kwargs, CHAT_SYNTHESIS, model)
            bound = ui._chat_max_tokens()
            out = litellm.completion(**kwargs, **({"max_tokens": bound} if bound else {}))
            text = (out.choices[0].message.content or "").strip()
        else:
            r = httpx.post(f"{ui.OLLAMA_URL}/api/chat", timeout=120,
                           json={"model": model, "messages": [{"role": "system", "content": SYSTEM},
                                                              {"role": "user", "content": USER}],
                                 "stream": False, "think": ollama_think(model)})
            r.raise_for_status()
            text = ((r.json().get("message") or {}).get("content") or "").strip()
        ok = bool(text)
        with attempt_context(function="CHAT", stage="model_canary"):
            record(Attempt(success=ok, http_status=200, latency_ms=int((time.monotonic() - t0) * 1000), **base))
        rows.append({"kind": "chat", "name": sid, "model": model, "result": "OK" if ok else "EMPTY_TEXT",
                     "reply": text[:30], "ms": int((time.monotonic() - t0) * 1000)})
    except Exception as exc:  # noqa: BLE001 — a failure is the finding
        with attempt_context(function="CHAT", stage="model_canary"):
            record(Attempt(success=False, error_class=type(exc).__name__,
                           latency_ms=int((time.monotonic() - t0) * 1000), **base))
        rows.append({"kind": "chat", "name": sid, "model": model, "result": f"{type(exc).__name__}",
                     "reply": str(exc)[:120], "ms": int((time.monotonic() - t0) * 1000)})
    time.sleep(0.3)

for r in rows:
    print(json.dumps(r))
json.dump(rows, open(OUT, "w"), indent=1)
