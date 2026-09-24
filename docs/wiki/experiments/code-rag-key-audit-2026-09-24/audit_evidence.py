"""Evidence for the 2026-09-24 code-RAG + provider-key audit (register 11.459). Read-only.

Reproduces the numbers the report cites:
- the Groq account x model matrix (config/cloud_providers.json) and the idle pairs;
- traffic on the post-swap Groq models (llm_provider_attempts) and the saved limiter state (llm_controller_state);
- which Cloudflare account ids are set (booleans only; values are never read into the output);
- the limiter families (config/extraction_models/limiter.yaml): which lanes share one family;
- per-lane attempts, successes, provider 429s and local refusals;
- the HYBRID / GRAPH funnel of the owner's UI turns (last 5 days): union -> judged -> selected -> cited;
- what today's document chunker (tier_v3) does to code: source lines left outside every child chunk.

No writes (the SQL session is READ ONLY), no model call, no sidecar call. Run from the fleet checkout with .env loaded:
    set -a; . ./.env; set +a
    .venv/bin/python docs/wiki/experiments/code-rag-key-audit-2026-09-24/audit_evidence.py > audit_evidence.json
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from pathlib import Path

import psycopg
import yaml
from workers.tier_chunker import tier_chunk_layout

ROOT = Path(__file__).resolve().parents[4]
GROQ_MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b")
GROQ_TPD = 200_000                        # per key per model (owner 2026-09-23, work-log 2026-09-23-groq-model-swap L17)
CHUNKER_PROBES = ("config/runtime_budget.yaml", "workers/workers/doc_profile_worker.py",
                  ".github/workflows/determinism.yml")


def pct(values: list[float], ps=(10, 50, 90)) -> dict:
    v = sorted(values)
    if not v:
        return {}
    out = {}
    for p in ps:
        k = (len(v) - 1) * p / 100
        f, c = math.floor(k), math.ceil(k)
        out[f"p{p}"] = round(v[f] + (v[c] - v[f]) * (k - f), 1)
    return out


def groq_matrix() -> dict:
    cfg = json.loads((ROOT / "config/cloud_providers.json").read_text())
    pins = cfg.get("stage_pins") or {}
    pinned = {lane: stage for stage, lanes in pins.items() for lane in (lanes if isinstance(lanes, list) else [lanes])}
    matrix: dict[str, dict] = {f"GROQ_API_KEY_{n}": {m: None for m in GROQ_MODELS} for n in range(1, 7)}
    for e in cfg["providers"]:
        key, model = e.get("api_key_env"), e.get("model")
        if key in matrix and model in GROQ_MODELS:
            on = e.get("enabled", True) is not False
            matrix[key][model] = {"lane": e["name"], "enabled": on, "stage": pinned.get(e["name"]) if on else None}
    active = sum(1 for k in matrix.values() for v in k.values() if v and v["enabled"] and v["stage"])
    return {"matrix": matrix, "pairs_total": 18, "pairs_active": active, "pairs_idle": 18 - active,
            "idle_tokens_per_day": (18 - active) * GROQ_TPD}


def limiter_families() -> dict:
    spec = yaml.safe_load((ROOT / "config/extraction_models/limiter.yaml").read_text())
    fam = defaultdict(list)

    def walk(node, name=None):
        if isinstance(node, dict):
            if "family" in node and name:
                fam[str(node["family"])].append(name)
            for k, v in node.items():
                walk(v, k if isinstance(v, dict) else name)
        elif isinstance(node, list):
            for x in node:
                walk(x, name)
    walk(spec)
    shared = {f: sorted(set(lanes)) for f, lanes in fam.items() if len(set(lanes)) > 1}
    return {"families_with_more_than_one_lane": shared}


def chunker_coverage() -> list[dict]:
    out = []
    for rel in CHUNKER_PROBES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        rows, layout = tier_chunk_layout(text, doc_id="audit-probe")
        children = [r for r in rows if r.get("parent_id")]
        covered = bytearray(len(text))
        for r in children:
            covered[r["char_start"]:r["char_end"]] = b"\x01" * (r["char_end"] - r["char_start"])
        lost, pos = [], 0
        for n, line in enumerate(text.split("\n"), 1):
            s, e = pos, pos + len(line)
            pos = e + 1
            if line.strip() and not any(covered[s:e]):
                lost.append((n, line.strip()[:80]))
        kinds: dict[str, int] = defaultdict(int)
        for reg in layout:
            kinds[str(reg.get("kind"))] += 1
        not_comment = [x for x in lost if not x[1].startswith("#")]
        out.append({"file": rel, "non_blank_lines": sum(1 for x in text.split("\n") if x.strip()),
                    "parents": len(rows) - len(children), "children": len(children),
                    "layout_regions": dict(kinds), "lines_outside_every_child": len(lost),
                    "non_comment_lines_outside_every_child": len(not_comment),
                    "examples": not_comment[:10]})
    return out


def main() -> dict:
    conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"])
    conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
    cur = conn.cursor()
    cur.execute("select model, count(*), max(created_at) from llm_provider_attempts where model = any(%s) group by 1",
                (list(GROQ_MODELS),))
    post_swap = cur.fetchall()
    cur.execute("select max(created_at) from llm_provider_attempts where provider ilike '%groq%'")
    last_groq = cur.fetchone()[0]
    cur.execute("select key, state from llm_controller_state where key ilike 'llm_cloud[%groq%'")
    saved = {k: {x: (s if isinstance(s, dict) else json.loads(s)).get(x)
                 for x in ("ceiling", "adopted_tpm", "adopted_rpm", "provider_rpd_limit")}
             for k, s in cur.fetchall()}
    cur.execute("""
        select coalesce(lane, '-'), count(*), sum(success::int), sum((http_status = 429)::int),
               sum((error_class = 'LIMITER_REFUSED')::int),
               percentile_cont(0.5) within group (order by latency_ms)::int
        from llm_provider_attempts group by 1 order by 2 desc""")
    lanes = [dict(zip(("lane", "attempts", "ok", "http_429", "local_refusals", "p50_ms"), r)) for r in cur.fetchall()]
    cur.execute("""
        select mode, meta from query_receipts
        where kind = 'chat_stream' and client = 'ui-stream' and status = 'ok' and mode in ('HYBRID', 'GRAPH')
          and received_at > now() - interval '5 days'""")
    funnel: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for mode, meta in cur.fetchall():
        counts = ((meta or {}).get("funnel") or {}).get("counts") or {}
        for k in ("retrieved", "union", "pre_rerank", "post_rerank", "selected", "cited"):
            if counts.get(k) is not None:
                funnel[mode][k].append(counts[k])
    conn.close()
    return {
        "audit": "code-RAG + provider-key audit 2026-09-24 (register 11.459)",
        "groq": groq_matrix(),
        "post_swap_groq_attempts": [[m, n, str(t)] for m, n, t in post_swap],
        "last_groq_attempt_at": str(last_groq),
        "saved_limiter_state_groq": saved,
        "cloudflare_account_ids_set": {k: bool(v.strip()) for k, v in sorted(os.environ.items())
                                       if k.startswith("CLOUDFLARE_ACCOUNT_ID")},
        "limiter": limiter_families(),
        "lanes_all_time": lanes,
        "ui_funnel_last_5_days": {m: {k: {"n": len(v), **pct(v)} for k, v in d.items()} for m, d in funnel.items()},
        "tier_v3_on_code": chunker_coverage(),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
