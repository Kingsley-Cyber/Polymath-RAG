"""PROVIDER-CANARY-V2 — production-shaped qualification of ONE model on
ONE OpenAI-compatible endpoint, judged only by the production gates.

    CANARY_MODEL=<slug> [CANARY_URL=https://openrouter.ai/api]
    [CANARY_KEY_ENV=OPENROUTER_API_KEY] [CANARY_STRUCTURED=schema|json]
    [CANARY_REASONING=low] [CANARY_BUDGET_S=180] [CANARY_N=8]
        .venv/bin/python eval/v5/fleet/provider_canary.py

Two verdicts the first canary conflated (owner correction 2026-09-01:
"429 is probably for concurrency and providers — there's a reason"):
  CAPACITY  429/5xx/transport events per call — a provider-pool
            property. Paced (2 s after a 429), never blindly retried,
            reported separately.
  QUALITY   extraction (validate_and_normalize) + enrichment
            (compile_parents_microbatched) over the calls that were
            actually answered.
Hard budget per model: a model that cannot answer N chunks + N parents
inside CANARY_BUDGET_S fails production regardless of quality.

URL is the endpoint BASE without /v1 — the client appends
/v1/chat/completions itself (the OpenRouter 404 trap).
Exit 0 always; the VERDICT line is the result.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import sys
import time
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[3]
for sub in ("shared", "workers"):
    sys.path.insert(0, str(ROOT / sub))


def main() -> int:
    import psycopg

    from polymath_shared.latent.compiler import (
        ParentInput,
        compile_parents_microbatched,
    )
    from polymath_shared.latent.contract import PRODUCTION_BOUNDS
    from polymath_shared.llm_extraction.client import LLMExtractionClient
    from polymath_shared.llm_extraction.gate import (
        ChunkView,
        validate_and_normalize,
    )
    from polymath_shared.settings import get_settings

    url = os.environ.get("CANARY_URL", "https://openrouter.ai/api")
    model = os.environ["CANARY_MODEL"]
    key = os.environ[os.environ.get("CANARY_KEY_ENV", "OPENROUTER_API_KEY")]
    budget_s = float(os.environ.get("CANARY_BUDGET_S", "180"))
    n = int(os.environ.get("CANARY_N", "8"))
    corpus = os.environ.get("CANARY_CORPUS", "ecom-meta-v1")
    opts: dict = {"structured": os.environ.get("CANARY_STRUCTURED", "schema")}
    if os.environ.get("CANARY_REASONING"):
        opts["reasoning_effort"] = os.environ["CANARY_REASONING"]

    with psycopg.connect(get_settings().postgres.dsn, connect_timeout=5) as conn:
        rows = conn.execute(
            """SELECT ch.chunk_id, ch.text FROM chunks ch
                 JOIN documents d ON d.doc_id = ch.doc_id
                WHERE d.corpus_id = %s AND ch.tier = 'child'
                  AND coalesce(ch.region_role,'body') = 'body'
                  AND ch.token_count >= 50""", (corpus,)).fetchall()
        pids = [r[0] for r in conn.execute(
            """SELECT p.chunk_id FROM chunks p
                 JOIN documents d ON d.doc_id = p.doc_id
                WHERE d.corpus_id = %s AND p.tier = 'parent'
                  AND coalesce(p.region_role,'body') = 'body'
                ORDER BY p.chunk_id LIMIT %s""", (corpus, n)).fetchall()]
        kids_by = {pid: conn.execute(
            "SELECT chunk_id, text FROM chunks WHERE parent_id=%s "
            "AND tier='child' ORDER BY chunk_id", (pid,)).fetchall()
            for pid in pids}
    rows.sort(key=lambda r: hashlib.blake2b(r[0].encode(), digest_size=8).digest())
    sample = rows[:n]
    if not sample:
        print("no eligible chunks"); return 0
    words = sum(len(t.split()) for _, t in sample)

    t0 = time.perf_counter()
    capacity: Counter = Counter()
    answered = 0
    ents: set = set()
    facts: set = set()
    rejected = 0
    walls: list[float] = []
    client = LLMExtractionClient("cloud", url=url, model=model,
                                 limiter_key="default", api_key=key,
                                 cloud_opts=opts)
    for cid, text in sample:
        if time.perf_counter() - t0 > budget_s:
            capacity["budget_exhausted"] += 1
            continue
        t = time.perf_counter()
        try:
            r = client.extract([(cid, [(cid, text)])],
                               source_bytes=10**9, threshold_bytes=0)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            kind = ("HTTP_429" if "429" in msg else
                    "HTTP_5xx" if "HTTP 5" in msg else
                    "HTTP_4xx" if "HTTP 4" in msg else "transport")
            capacity[kind] += 1
            if kind == "HTTP_429":
                time.sleep(2.0)
            continue
        walls.append(time.perf_counter() - t)
        if r.packet is None:
            capacity["quarantined_output"] += 1
            continue
        answered += 1
        norm = validate_and_normalize(r.packet, {cid: [ChunkView(cid, text)]})
        rejected += len(norm.rejections)
        for rr in norm.entities_by_chunk.values():
            for m in rr:
                ents.add(((m.get("label") or "?"),
                          (m.get("text") or "").lower()))
        for rr in norm.evidence_by_chunk.values():
            for ev in rr:
                if ev.get("evidence_class") == "llm_relation":
                    facts.add((ev.get("predicate"),
                               (ev.get("subject") or "").lower(),
                               (ev.get("object") or "").lower()))
    ans_words = words * answered / max(len(sample), 1)
    print(f"EXTRACT {model} answered={answered}/{len(sample)} "
          f"capacity={dict(capacity)} "
          f"facts/1Kw={len(facts) * 1000 / max(ans_words, 1):.1f} "
          f"entities/1Kw={len(ents) * 1000 / max(ans_words, 1):.1f} "
          f"rejections={rejected} "
          f"mean_wall={(sum(walls) / len(walls)) if walls else 0:.1f}s")

    e_opts = {"structured": "json"}
    if "reasoning_effort" in opts:
        e_opts["reasoning_effort"] = opts["reasoning_effort"]
    ec = LLMExtractionClient("cloud", url=url, model=model,
                             limiter_key="default", api_key=key,
                             cloud_opts=e_opts)
    ecap: Counter = Counter()

    def transport(items):
        out = []
        for item_id, system, user, max_tokens in items:
            if time.perf_counter() - t0 > budget_s:
                ecap["budget_exhausted"] += 1
                out.append((item_id, "", "BUDGET"))
                continue
            raw, err = ec.complete_one(user, system_prompt=system,
                                       max_tokens=max_tokens)
            if err:
                ecap[err] += 1
                if err == "HTTP_429":
                    time.sleep(2.0)
            out.append((item_id, raw, err))
        return out

    parents = [ParentInput(pid, [(cid, i, txt) for i, (cid, txt)
                                 in enumerate(k)])
               for pid, k in kids_by.items() if k]
    t = time.perf_counter()
    compiled = compile_parents_microbatched(
        transport, parents, PRODUCTION_BOUNDS, 6000, max_concurrency=2)
    st = Counter(cp.status for cp in compiled)
    er = Counter(cp.error_class for cp in compiled if cp.error_class)
    gc = [cp.gist_coverage for cp in compiled
          if cp.status == "READY" and cp.gist_coverage is not None]
    print(f"ENRICH  {model} ready={st.get('READY', 0)}/{len(parents)} "
          f"capacity={dict(ecap)} errors={dict(er)} "
          f"wall={time.perf_counter() - t:.1f}s "
          f"mean_gist={(sum(gc) / len(gc)) if gc else 0:.2f}")
    total = time.perf_counter() - t0
    floor = max(1, (3 * n) // 4)          # 6 of 8
    verdict = ("PASS" if answered >= floor and st.get("READY", 0) >= floor
               and total <= budget_s * 1.5 else "FAIL")
    print(f"VERDICT {model} {verdict} total={total:.0f}s budget={budget_s:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
