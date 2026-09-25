"""LLM-BACKEND L4a canary (register 11.468): one real call per owned Groq pair and per wired Cloudflare account, through the production client
(limiter admit -> call -> settle -> attempt ledger row tagged stage=l4_canary). Prints no secrets."""
import json
import time

from polymath_shared.llm_extraction.client import LLMExtractionClient
from polymath_shared.llm_extraction.pool import cloud_endpoints, lane_max_tokens

LANES = ([f"profile_groq{k}" for k in range(1, 7)] + [f"map_groq{k}" for k in range(1, 7)]
         + [f"map_groq{k}q" for k in range(1, 7)]
         + ["cloudflare_map1", "cloudflare_map2", "cloudflare3", "cloudflare4", "cloudflare5", "cloudflare6"])
SYSTEM = "You are a connectivity canary. Answer with exactly one word."
USER = "Reply with the word OK."
HDR_KEYS = ("x-ratelimit-limit-requests", "x-ratelimit-limit-tokens", "x-ratelimit-remaining-requests",
            "x-ratelimit-remaining-tokens")

eps = {e.name: e for e in cloud_endpoints()}
rows, auth_fail_streak = [], 0
for name in LANES:
    ep = eps.get(name)
    if ep is None:
        rows.append({"lane": name, "result": "PARKED (not in the active roster)"})
        continue
    client = LLMExtractionClient("cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key, api_key=ep.api_key,
                                 cloud_opts=ep.cloud_opts, timeout_s=60.0, max_attempts=1)
    client.endpoint_name = ep.name
    client.attempt_stage, client.attempt_function = "l4_canary", "CANARY"
    seen: dict = {}
    real_chat = client._chat

    def _chat(*a, _real=real_chat, _seen=seen, **k):
        text, ti, to, hdrs = _real(*a, **k)
        _seen.update({"tin": ti, "tout": to,
                      "hdrs": {h: hdrs.get(h) for h in HDR_KEYS if hdrs.get(h) is not None}})
        return text, ti, to, hdrs

    client._chat = _chat
    stage_max = 512 if "cloudflare" in name else 256
    t0 = time.monotonic()
    text, err = client.complete_one(USER, system_prompt=SYSTEM, max_tokens=lane_max_tokens(ep, stage_max))
    ms = int((time.monotonic() - t0) * 1000)
    ok = err is None and bool((text or "").strip())
    rows.append({"lane": name, "model": ep.model, "result": "OK" if ok else (err or "EMPTY_TEXT"),
                 "reply": (text or "").strip()[:24], "ms": ms, "tokens_in": seen.get("tin"),
                 "tokens_out": seen.get("tout"), "headers": seen.get("hdrs", {})})
    auth_fail_streak = auth_fail_streak + 1 if err in ("HTTP_401", "HTTP_403") else 0
    if auth_fail_streak >= 3:
        rows.append({"lane": "-", "result": "STOPPED: 3 auth failures in a row"})
        break
    time.sleep(0.5)

for r in rows:
    print(json.dumps(r))
json.dump(rows, open(__file__.replace("canary.py", "canary.json"), "w"),
          indent=1)
