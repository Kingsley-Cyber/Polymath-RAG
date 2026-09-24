"""C0 decision 6: profile / pMAP capacity for a code corpus (CODE-KNOWLEDGE-V1 C0, register 11.458).

Arithmetic only (no network, no database, no model call). Inputs, each with its source:
- per-file tokens and parents: `census.json` (this directory; stdlib ast + tiktoken cl100k proxy);
- prompt overheads: the live prompt modules (`doc-profile-v3.2` SYSTEM, `map-prompt-v2` MAP_SYSTEM), counted here;
- output sizes: the 2026-09-23 Groq canary (`docs/wiki/experiments/groq-model-canary-2026-09-23/results.json`):
  gpt-oss-120b profile completions, gpt-oss-20b pMAP completions per parent;
- lane pins, batch caps and char budgets: `config/cloud_providers.json`;
- Groq limits per key per model: 30 RPM / 1K RPD / 8K TPM / 200K TPD (the owner, 2026-09-23, recorded in
  `docs/wiki/work-log/2026-09-23-groq-model-swap.md` L17).

Assumptions are named in the output (`assumptions`); the code-prompt overheads are ESTIMATES until C6 / C7 build the
prompts and a canary measures them.

Run from the repository root:
    .venv/bin/python docs/wiki/experiments/code-knowledge-c0-2026-09-24/capacity.py > capacity.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import tiktoken
from polymath_shared.document_profile import map_prompt, prompt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ENC = tiktoken.get_encoding("cl100k_base")

GROQ = {"rpm": 30, "rpd": 1000, "tpm": 8000, "tpd": 200_000}          # per key per model (owner 2026-09-23)
PRODUCT_AREAS = ("shared", "orchestrator", "workers", "control", "mcp_server", "sidecars")


def canary_outputs() -> dict:
    d = json.loads((ROOT / "docs/wiki/experiments/groq-model-canary-2026-09-23/results.json").read_text())
    prof = [r["usage"]["completion_tokens"] for r in d["results"]
            if r.get("stage") == "profile" and r.get("model") == "openai/gpt-oss-120b" and r.get("usage")]
    per_parent = [r["usage"]["completion_tokens"] / r["expected"] for r in d["results"]
                  if r.get("stage") == "pmap" and r.get("model") == "openai/gpt-oss-20b" and r.get("usage")
                  and r.get("expected")]
    return {"profile_completion_tokens_mean": round(sum(prof) / len(prof)), "profile_samples": len(prof),
            "pmap_completion_tokens_per_parent_mean": round(sum(per_parent) / len(per_parent), 1),
            "pmap_samples": len(per_parent)}


def lanes() -> dict:
    cfg = json.loads((ROOT / "config/cloud_providers.json").read_text())
    by = {e["name"]: e for e in cfg["providers"]}
    pins = cfg.get("stage_pins") or {}
    prof_all = sorted(n for n in by if n.startswith("profile_groq"))
    return {
        "doc_profile_pin": pins.get("doc_profile"),
        "doc_parent_map_pin": pins.get("doc_parent_map"),
        "profile_groq_lanes_in_config": {n: {"enabled": by[n].get("enabled", True), "model": by[n].get("model")}
                                         for n in prof_all},
        "profile_request_char_budget": by["profile_groq1"].get("request_char_budget"),
        "pmap_batch_cap": by["map_groq2"].get("map_batch_cap"),
        "groq_pmap_lanes_pinned": sum(1 for n in pins.get("doc_parent_map") or [] if n.startswith("map_groq")),
    }


def profile_requests(file_tokens: int, source_budget: int) -> tuple[int, int]:
    """(requests, tokens_in_total) for one file under spec §12: one request when the file fits; otherwise one request
    per syntax section, then roll-ups (a group level when there are more than 8 sections, then the file)."""
    if file_tokens <= source_budget:
        return 1, file_tokens
    sections = math.ceil(file_tokens / source_budget)
    groups = math.ceil(sections / 8) if sections > 8 else 0
    return sections + groups + 1, file_tokens + (groups + 1) * 2400    # roll-ups read ~8 x 300-token descriptions


def scope_numbers(files: list[dict], a: dict) -> dict:
    reqs = tin_src = parents = batches = map_tokens = 0
    for f in files:
        r, t = profile_requests(f["tokens"], a["profile_source_budget_tokens"])
        reqs += r
        tin_src += t
        ps = f.get("parents", [])
        parents += len(ps)
        n_batches = math.ceil(len(ps) / a["pmap_batch_size"]) if ps else 0
        batches += n_batches
        map_tokens += (n_batches * a["pmap_system_tokens"]
                       + sum(min(p["tokens"], a["pmap_code_per_parent_tokens"]) + a["pmap_context_per_parent_tokens"]
                             + a["pmap_output_per_parent_tokens"] for p in ps))
    prof_tokens = (reqs * (a["profile_system_tokens"] + a["code_rules_addendum_tokens"] + a["structure_context_tokens"]
                           + a["profile_output_tokens"]) + tin_src)
    per_key_day = GROQ["tpd"]
    out = {"files": len(files), "parents": parents,
           "profile_requests": reqs, "profile_tokens": prof_tokens,
           "profile_tokens_per_request_mean": round(prof_tokens / max(reqs, 1)),
           "pmap_batches": batches, "pmap_tokens": round(map_tokens),
           "pmap_tokens_per_batch_mean": round(map_tokens / max(batches, 1))}
    for keys in (1, 6):
        out[f"profile_days_on_{keys}_key"] = round(prof_tokens / (per_key_day * keys), 1)
    out["pmap_days_on_10_groq_lanes"] = round(map_tokens / (per_key_day * 10), 2)
    return out


def main() -> dict:
    census_py = json.loads((HERE / "census.json").read_text())["python"]
    # census.json keeps aggregates; per-file detail is recomputed from the census module (same tokenizer, same rules)
    import importlib.util
    spec = importlib.util.spec_from_file_location("census", HERE / "census.py")
    census = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(census)
    per_file = []
    for p in census.tracked_files(ROOT):
        if not p.endswith((".py", ".pyi")):
            continue
        text = (ROOT / p).read_text(encoding="utf-8", errors="replace")
        if census.skip_reason(p, text):
            continue
        per_file.append(census.python_file(p, text))
    assert len(per_file) == census_py["files"], "census.json is stale: re-run census.py first"

    out_obs = canary_outputs()
    lane = lanes()
    assumptions = {
        "profile_system_tokens": len(ENC.encode(prompt.SYSTEM)),
        "code_rules_addendum_tokens": 350,        # ESTIMATE: spec §11 code rules + one language addendum
        "structure_context_tokens": 600,          # ESTIMATE: STRUCTURE + RESOLVED RELATIONSHIPS + UNKNOWN blocks
        "profile_output_tokens": out_obs["profile_completion_tokens_mean"],
        "profile_max_output_tokens_reserved": 2400,   # doc_profile_worker.MAX_OUTPUT_TOKENS
        "pmap_system_tokens": len(ENC.encode(map_prompt.MAP_SYSTEM)),
        "pmap_code_per_parent_tokens": 300,       # ESTIMATE: the bounded exact code a parent carries into its batch
        "pmap_context_per_parent_tokens": 120,    # ESTIMATE: signature line, children signatures, 1-hop links
        "pmap_output_per_parent_tokens": out_obs["pmap_completion_tokens_per_parent_mean"],
    }
    # §12.4 sizing by tokens: the request must fit the 8K TPM of one Groq key; reserve the full max output
    assumptions["profile_source_budget_tokens"] = (GROQ["tpm"] - assumptions["profile_system_tokens"]
                                                   - assumptions["code_rules_addendum_tokens"]
                                                   - assumptions["structure_context_tokens"]
                                                   - assumptions["profile_max_output_tokens_reserved"])
    per_parent = (assumptions["pmap_code_per_parent_tokens"] + assumptions["pmap_context_per_parent_tokens"]
                  + assumptions["pmap_output_per_parent_tokens"])
    assumptions["pmap_batch_size"] = min(lane["pmap_batch_cap"] or 15,
                                         int((GROQ["tpm"] - assumptions["pmap_system_tokens"]) // per_parent))

    def area(f):
        return census.area_of(f["path"])

    scopes = {
        "whole_repository": per_file,
        "product_code": [f for f in per_file if area(f) in PRODUCT_AREAS],
        "product_code_plus_scripts": [f for f in per_file if area(f) in PRODUCT_AREAS + ("scripts",)],
        "tests_only": [f for f in per_file if f.get("is_test")],
    }
    return {
        "capacity": "CODE-KNOWLEDGE-V1 C0 decision 6",
        "groq_limits_per_key_per_model": GROQ,
        "canary_observed": out_obs,
        "lanes_today": lane,
        "assumptions": assumptions,
        "scopes": {k: scope_numbers(v, assumptions) for k, v in scopes.items()},
        "reading": [
            "profile days = profile tokens / (200K TPD x keys); the TPD, not latency, binds (a call is ~2.5-3 s)",
            ("pMAP days assume all 10 Groq pMAP lanes (5 keys x 2 models) are free for code; Cloudflare / OpenRouter "
             "fallbacks are not counted"),
            "document ingestion shares the same lanes; these numbers assume no document ingestion runs meanwhile",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
