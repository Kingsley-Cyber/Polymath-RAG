"""GROQ-MODEL-CANARY-2026-09-23 — read-only qualification of Groq's current models on the PRODUCTION profile + pMAP prompts.

Owner-approved (2026-09-23: "Canary + mapping OK", ~40 calls). Writes NOTHING to the fleet: no DB write, no Qdrant, no limiter
state (raw HTTPS instead of the production client, whose limiter persists state). The payload is the production one
(`LLMExtractionClient._chat` for a Groq lane: model, [system, user], temperature, max_tokens, stream=false, reasoning_effort;
no response_format — the Groq lanes are `json_mode: false`). Outputs are parsed by the production compilers
(`map_compiler.compile_maps`, `document_profile.compiler.compile_llm_output` + `profile_valid`). Keys come from the environment
and are never printed. Usage: python groq_canary.py <out.json>"""
from __future__ import annotations

import json
import os
import sys
import time

import httpx

from polymath_shared.db import tx
from polymath_shared.document_profile import compiler as C
from polymath_shared.document_profile import context as CX
from polymath_shared.document_profile import map_compiler
from polymath_shared.document_profile.grounding import build_grounding_context
from polymath_shared.document_profile.map_prompt import build_map_prompt
from polymath_shared.document_profile.parent_skeleton import build_parent_skeletons
from polymath_shared.document_profile.prompt import SYSTEM, build_user_prompt
from polymath_shared.llm_extraction.client import GENERATION_CONFIG
from workers import doc_parent_map_stage_worker as MAPW
from workers import doc_profile_worker as PROW

URL = "https://api.groq.com/openai/v1/chat/completions"
EFFORT = {"openai/gpt-oss-120b": "low", "openai/gpt-oss-20b": "low", "qwen/qwen3.8-27b": "none", "groq/compound-mini": None}
CALLS = 0
CAP = 40


def call(key_env: str, model: str, system: str, user: str, max_tokens: int) -> dict:
    global CALLS
    if CALLS >= CAP:
        return {"status": "skipped", "error": "call cap reached"}
    CALLS += 1
    payload = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
               "temperature": GENERATION_CONFIG["temperature"], "max_tokens": max_tokens, "stream": False}
    if EFFORT.get(model) is not None:
        payload["reasoning_effort"] = EFFORT[model]
    t0 = time.perf_counter()
    try:
        r = httpx.post(URL, json=payload, headers={"Authorization": f"Bearer {os.environ[key_env]}"}, timeout=180)
    except Exception as exc:  # noqa: BLE001 — a transport failure is a finding
        return {"status": "transport", "error": f"{type(exc).__name__}: {str(exc)[:200]}", "ms": round((time.perf_counter() - t0) * 1000)}
    ms = round((time.perf_counter() - t0) * 1000)
    hdr = {k: v for k, v in r.headers.items() if k.lower().startswith(("x-ratelimit", "retry-after"))}
    if r.status_code != 200:
        return {"status": r.status_code, "error": r.text[:400], "ms": ms, "headers": hdr, "sent": {k: v for k, v in payload.items() if k != "messages"}}
    body = r.json()
    ch = (body.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    return {"status": 200, "content": msg.get("content") or "", "reasoning_chars": len(msg.get("reasoning") or ""),
            "finish": ch.get("finish_reason"), "usage": body.get("usage"), "ms": ms, "headers": hdr,
            "sent": {k: v for k, v in payload.items() if k != "messages"}}


def pick_docs(n: int) -> list[str]:
    with tx() as conn:
        rows = conn.execute("""SELECT d.doc_id FROM documents d JOIN chunks c ON c.doc_id = d.doc_id AND c.tier = 'parent'
                               WHERE d.corpus_id = 'cinema' GROUP BY d.doc_id HAVING count(*) BETWEEN 40 AND 400
                               ORDER BY d.doc_id LIMIT %s""", (n,)).fetchall()
    return [r[0] for r in rows]


def pmap_case(doc_id: str, model: str, key_env: str, batch: int) -> dict:
    with tx() as conn:
        document, parents = MAPW._load_inputs(conn, doc_id)
    manifest = build_parent_skeletons(parents)
    grounding = build_grounding_context(document, parents)
    skels = list(manifest.skeletons)[:batch]
    system, user = build_map_prompt(skels, grounding=grounding, is_combined=False)
    out = call(key_env, model, system, user, MAPW.MAX_MAP_TOKENS)
    rec = {"stage": "pmap", "doc": doc_id[:20], "model": model, "key": key_env, "batch": len(skels),
           "prompt_chars": len(system) + len(user), **{k: v for k, v in out.items() if k != "content"}}
    if out.get("status") == 200:
        res = map_compiler.compile_maps(out["content"], manifest, contract=map_compiler.MAP_COMPILER_VERSION)
        want = {s.alias for s in skels}
        got = {m.alias for m in res.maps} & want
        rec.update({"valid_maps": len(got), "expected": len(want), "rejected_lines": len(res.rejected),
                    "unknown_aliases": len(res.unknown_aliases), "sample": out["content"][:300]})
    return rec


def profile_case(doc_id: str, model: str, key_env: str) -> dict:
    with tx() as conn:
        document, parents, terms = PROW._load_inputs(conn, doc_id, want_terms=True)
    ctx = CX.build_context(document, parents, terms=terms, budget_tokens=PROW.CONTEXT_BUDGET_TOKENS)
    user = build_user_prompt(ctx.title, ctx.structure_block, ctx.excerpts_block)
    out = call(key_env, model, SYSTEM, user, PROW.MAX_OUTPUT_TOKENS)
    rec = {"stage": "profile", "doc": doc_id[:20], "model": model, "key": key_env, "prompt_chars": len(SYSTEM) + len(user),
           **{k: v for k, v in out.items() if k != "content"}}
    if out.get("status") == 200:
        source_text = "\n".join(p.get("text") or "" for p in parents)
        result = C.compile_llm_output(out["content"], source_text=source_text, grounding_mode="warn")
        valid, missing = C.profile_valid(result.record)
        counts = {}
        for f in ("topics", "terms", "questions", "searches", "theories", "concepts", "seealso"):
            v = getattr(result.record, f, None)
            if isinstance(v, (list, tuple)):
                counts[f] = len(v)
        rec.update({"profile_valid": bool(valid), "missing": list(missing)[:8], "field_counts": counts,
                    "has_one_liner": bool(result.record.one_liner), "has_summary": bool(result.record.summary),
                    "sample": out["content"][:300]})
    return rec


def main() -> int:
    out_path = sys.argv[1]
    docs = pick_docs(3)
    results: list[dict] = []

    def run(fn, *a):
        r = fn(*a)
        results.append(r)
        print(json.dumps({k: r.get(k) for k in ("stage", "model", "key", "batch", "status", "ms", "finish", "valid_maps", "expected",
                                                   "profile_valid", "field_counts", "reasoning_chars", "error")})[:400], flush=True)
        pathlib_write(out_path, results)

    # round 1 — every (key, model) pair used once, so no per-model TPM window is shared
    run(pmap_case, docs[0], "openai/gpt-oss-20b", "GROQ_API_KEY_2", 15)
    run(pmap_case, docs[0], "openai/gpt-oss-20b", "GROQ_API_KEY_3", 8)
    run(pmap_case, docs[0], "qwen/qwen3.8-27b", "GROQ_API_KEY_4", 15)
    run(pmap_case, docs[0], "qwen/qwen3.8-27b", "GROQ_API_KEY_5", 8)
    run(profile_case, docs[0], "openai/gpt-oss-120b", "GROQ_API_KEY_1")
    run(profile_case, docs[0], "qwen/qwen3.8-27b", "GROQ_API_KEY_1")
    run(profile_case, docs[0], "openai/gpt-oss-20b", "GROQ_API_KEY_1")
    run(pmap_case, docs[0], "groq/compound-mini", "GROQ_API_KEY_6", 8)      # is the legacy model really gone?
    time.sleep(65)                                                           # one TPM window per (key, model)
    # round 2 — a second and third book on the same pairs
    run(pmap_case, docs[1], "openai/gpt-oss-20b", "GROQ_API_KEY_2", 15)
    run(pmap_case, docs[1], "openai/gpt-oss-20b", "GROQ_API_KEY_3", 8)
    run(pmap_case, docs[1], "qwen/qwen3.8-27b", "GROQ_API_KEY_4", 15)
    run(pmap_case, docs[1], "qwen/qwen3.8-27b", "GROQ_API_KEY_5", 8)
    run(profile_case, docs[1], "openai/gpt-oss-120b", "GROQ_API_KEY_1")
    run(profile_case, docs[1], "qwen/qwen3.8-27b", "GROQ_API_KEY_1")
    time.sleep(65)
    run(profile_case, docs[2], "openai/gpt-oss-120b", "GROQ_API_KEY_1")
    run(pmap_case, docs[2], "openai/gpt-oss-20b", "GROQ_API_KEY_2", 15)
    run(pmap_case, docs[2], "qwen/qwen3.8-27b", "GROQ_API_KEY_4", 15)
    print(f"calls={CALLS}", flush=True)
    return 0


def pathlib_write(path: str, results: list) -> None:
    with open(path, "w") as f:
        json.dump({"canary": "GROQ-MODEL-CANARY-2026-09-23", "calls": CALLS, "results": results}, f, indent=1, default=str)


if __name__ == "__main__":
    sys.exit(main())
