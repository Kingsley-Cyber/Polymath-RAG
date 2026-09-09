#!/usr/bin/env python
"""SILICONFLOW-EXTRACTION-CANARY — verify the siliconflow1..3 graph-extraction lanes.

Run AFTER pasting SILICONFLOW_API_KEY_1/2/3 into .env (the assistant never writes keys).
For each ACTIVE SiliconFlow lane it: (1) probes auth/liveness, (2) runs one REAL extraction
call with the live extraction system prompt, (3) confirms the reply is NON-EMPTY valid JSON
(i.e. `enable_thinking:false` worked — a thinking-on Qwen3-8B burns the budget and returns
empty), and (4) counts the entities/relations proposed. Read-only; no DB, no fleet change.

    .venv/bin/python scripts/siliconflow_extraction_canary.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

SAMPLE = (
    "Christopher Nolan directed Inception, a film produced by Emma Thomas at Warner Bros. "
    "The cinematographer Wally Pfister shot it on 65mm film, and Hans Zimmer composed the score. "
    "Inception won the Academy Award for Best Cinematography."
)


def _count(obj) -> tuple[int, int]:
    """Walk the extraction packet (items/neighborhoods OR a flat object) and total
    entities + relations, whatever nesting the model returned."""
    ent = rel = 0
    def walk(o):
        nonlocal ent, rel
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "entities" and isinstance(v, list):
                    ent += len(v)
                elif k == "relations" and isinstance(v, list):
                    rel += len(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(obj)
    return ent, rel


def main() -> int:
    from polymath_shared.llm_extraction.client import LLMExtractionClient, SYSTEM_PROMPT
    from polymath_shared.llm_extraction.pool import cloud_endpoints

    lanes = [e for e in cloud_endpoints() if e.name.startswith("siliconflow")]
    if not lanes:
        print("NO SiliconFlow lanes ACTIVE. Paste the keys into .env first:")
        print("  SILICONFLOW_API_KEY_1=sk-...")
        print("  SILICONFLOW_API_KEY_2=sk-...")
        print("  SILICONFLOW_API_KEY_3=sk-...")
        print("(one per line, no inline comments — pydantic keeps them and crashes the orchestrator)")
        return 2

    ok_all = True
    rows = []
    for ep in lanes:
        row = {"lane": ep.name, "model": ep.model, "enable_thinking": ep.enable_thinking}
        client = LLMExtractionClient("cloud", url=ep.url, model=ep.model,
                                     limiter_key=ep.limiter_key, api_key=ep.api_key,
                                     cloud_opts=ep.cloud_opts, timeout_s=90.0, max_attempts=1)
        client.endpoint_name = ep.name
        try:
            row["probe"] = client.probe()
        except Exception as exc:  # noqa: BLE001
            row["probe_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
            ok_all = False
            rows.append(row)
            print(f"  {ep.name}: PROBE FAILED {row['probe_error']}")
            continue
        t0 = time.time()
        raw, err = client.complete_one(SAMPLE, system_prompt=SYSTEM_PROMPT, max_tokens=2000)
        row["wall_s"] = round(time.time() - t0, 1)
        row["raw_len"] = len(raw or "")
        row["error"] = err
        parsed = None
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                # strip any stray fences the model added
                s = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                try:
                    parsed = json.loads(s)
                except Exception:
                    parsed = None
        row["valid_json"] = parsed is not None
        row["entities"], row["relations"] = _count(parsed) if parsed is not None else (0, 0)
        # thinking-off works iff we got a non-empty parseable reply
        row["thinking_off_ok"] = bool(raw) and row["valid_json"] and (row["entities"] + row["relations"] > 0)
        ok_all = ok_all and not err and row["thinking_off_ok"]
        rows.append(row)
        print(f"  {ep.name}: probe {row['probe'].get('wall_ms')}ms | extract {row['wall_s']}s "
              f"raw={row['raw_len']} valid_json={row['valid_json']} "
              f"entities={row['entities']} relations={row['relations']} "
              f"thinking_off_ok={row['thinking_off_ok']} err={err}")

    verdict = {"gate": "siliconflow-extraction-canary-v1", "lanes": len(lanes),
               "PASS": ok_all, "rows": rows}
    print("\n" + json.dumps(verdict, indent=1, default=str))
    if not ok_all:
        print("\nFAIL. If raw_len is 0 / valid_json False, thinking is NOT off (empty reply) — "
              "check that enable_thinking:false reached SiliconFlow, or the key/model.")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
