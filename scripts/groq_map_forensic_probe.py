#!/usr/bin/env python
"""GROQ-MAP-FORENSIC-PROBE-V1 — the bounded, CINEMA-FREE live probe for U-2.

Owner-authorized bounded Groq Parent-MAP forensic probe (2026-09-10), under the existing forensic limits
(docs/wiki/reports/2026-09-08/GROQ-FORENSIC-AUDIT.md). It observes the 11.185 conservation chain against REAL
Groq WITHOUT touching cinema or any corpus: SYNTHETIC parents → build_parent_skeletons → build_map_prompt →
the production LLMExtractionClient.complete_one (admit → _chat → record_success(headers)) → compile_maps, reading
the lane limiter's state() before/after each call so provider RPD, local day_count, and dispatch/refusal are
observable per request. `max_attempts=1` — the probe never retries (no quota-burning loop).

Respects every hard prohibition: no cinema, no corpus write, no DB map persistence, plaintext DSL + compiler
only (no JSON mode), chunker untouched. Reversible by construction — it writes nothing but the evidence JSON.

    # offline validation (NO Groq call, NO spend):
    .venv/bin/python scripts/groq_map_forensic_probe.py --dry --batch-sizes 15,20,30,40,60
    # minimal live preflight (1 request, smallest bounded spend):
    .venv/bin/python scripts/groq_map_forensic_probe.py --live --batch-sizes 15 --repeats 1 --max-lanes 1
    # bounded benchmark (batch-size reliability across lanes):
    .venv/bin/python scripts/groq_map_forensic_probe.py --live --batch-sizes 15,20,30,40,60 --repeats 1
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "shared", ROOT / "workers", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

MINI_MODEL = "groq/compound-mini"
_LOREM = (
    "The kiln reaches its peak firing temperature during the final soak, when the glaze matures and the "
    "clay body vitrifies. Operators log the cone bending angle every fifteen minutes to confirm heat work. "
    "Cooling is controlled to avoid dunting; the damper stays cracked until the interior falls below quartz "
    "inversion. This section {n} documents the {n}-cycle baseline procedure and its tolerance envelope."
)


def _synthetic_parents(n: int) -> list[dict]:
    return [
        {"text": _LOREM.format(n=i), "heading_path": f"Chapter {i // 3 + 1} > Section {i}",
         "region_role": "body", "parent_id": f"synth-{i:04d}", "chunk_index": i}
        for i in range(n)
    ]


def _map_lane_endpoints(max_lanes: int | None):
    from polymath_shared.llm_extraction.pool import cloud_endpoints
    eps = [e for e in cloud_endpoints() if str(getattr(e, "name", "")).startswith("map_groq") and getattr(e, "api_key", None)]
    eps.sort(key=lambda e: e.name)
    return eps[:max_lanes] if max_lanes else eps


def _one_call(ep, manifest, system, user, *, dry: bool) -> dict:
    from polymath_shared.document_profile.map_compiler import compile_maps
    expected = len(manifest.skeletons)
    rec = {"lane": ep.name, "batch_size": expected, "model": MINI_MODEL,
           "prompt_chars": len(system) + len(user)}
    if dry:
        rec["dry"] = True
        return rec
    from polymath_shared.llm_extraction.client import LLMExtractionClient
    client = LLMExtractionClient("cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key,
                                 api_key=ep.api_key, cloud_opts=getattr(ep, "cloud_opts", {}) or {},
                                 max_attempts=1)   # NEVER retry — no quota-burning loop
    lim = client._lane_limiter()
    before = dict(lim.state())
    t0 = time.time()
    raw, err = client.complete_one(user, system_prompt=system, max_tokens=2400)
    dt = time.time() - t0
    after = dict(lim.state())
    result = compile_maps(raw or "", manifest)
    dispatched = err != "LIMITER_REFUSED"
    day_delta = (after.get("day_count") or 0) - (before.get("day_count") or 0)
    rec.update({
        "err": err, "dispatched_http": dispatched, "limiter_refused": err == "LIMITER_REFUSED",
        "day_count_before": before.get("day_count"), "day_count_after": after.get("day_count"),
        "day_count_delta": day_delta,
        "provider_rpd_limit": after.get("provider_rpd_limit"),
        "provider_rpd_remaining_before": before.get("provider_rpd_remaining"),
        "provider_rpd_remaining_after": after.get("provider_rpd_remaining"),
        "valid_maps": len(result.maps), "expected_aliases": expected,
        "yield": round(len(result.maps) / expected, 3) if expected else None,
        "raw_len": len(raw or ""), "latency_s": round(dt, 2),
    })
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-sizes", default="15,20,30,40,60")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--max-lanes", type=int, default=0, help="0 = all active map lanes")
    ap.add_argument("--dry", action="store_true", help="build prompts only; NO Groq call, NO spend")
    ap.add_argument("--live", action="store_true", help="send real bounded Groq requests")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    if not (args.dry or args.live):
        args.dry = True  # default-safe: never spend unless --live is explicit

    from polymath_shared.document_profile.parent_skeleton import build_parent_skeletons
    from polymath_shared.document_profile.map_prompt import build_map_prompt

    sizes = [int(s) for s in args.batch_sizes.split(",") if s.strip()]
    lanes = _map_lane_endpoints(args.max_lanes or None) if args.live else []
    if args.live and not lanes:
        print("[probe] NO active map_groq lanes (api keys unresolved) — cannot run live. Try --dry.")
        return 2

    rows = []
    for size in sizes:
        parents = _synthetic_parents(size)
        manifest = build_parent_skeletons(parents)
        system, user = build_map_prompt(manifest.skeletons)
        if args.dry:
            rows.append(_one_call(type("E", (), {"name": "dry", "url": "", "model": MINI_MODEL})(),
                                  manifest, system, user, dry=True))
            print(f"[dry] batch={size} skeletons={len(manifest.skeletons)} prompt_chars={len(system)+len(user)}")
            continue
        for rep in range(args.repeats):
            ep = lanes[(len(rows)) % len(lanes)]   # round-robin across active lanes
            rec = _one_call(ep, manifest, system, user, dry=False)
            rows.append(rec)
            print(f"[live] lane={rec['lane']} batch={size} rep={rep} err={rec.get('err')} "
                  f"refused={rec.get('limiter_refused')} day_delta={rec.get('day_count_delta')} "
                  f"prov_rpd_rem={rec.get('provider_rpd_remaining_after')} yield={rec.get('yield')} "
                  f"maps={rec.get('valid_maps')}/{rec.get('expected_aliases')} {rec.get('latency_s')}s")

    # conservation reconciliation (live only)
    live = [r for r in rows if not r.get("dry")]
    recon = {}
    if live:
        recon = {
            "requests": len(live),
            "dispatched_http": sum(1 for r in live if r.get("dispatched_http")),
            "limiter_refused": sum(1 for r in live if r.get("limiter_refused")),
            "refused_zero_http_ok": all((not r.get("dispatched_http")) for r in live if r.get("limiter_refused")),
            "day_count_total_delta": sum(r.get("day_count_delta") or 0 for r in live),
            "provider_rpd_observed": any(r.get("provider_rpd_limit") is not None for r in live),
            "yield_by_size": {},
        }
        by = {}
        for r in live:
            by.setdefault(r["batch_size"], []).append(r.get("yield"))
        recon["yield_by_size"] = {k: [y for y in v] for k, v in sorted(by.items())}
        # acceptance-gate observability (this probe's scope)
        recon["gate_provider_rpd_observable"] = recon["provider_rpd_observed"]
        recon["gate_refused_zero_http"] = recon["refused_zero_http_ok"]
        recon["gate_no_retry_loop"] = True  # max_attempts=1 by construction

    out = {"contract": "groq-map-forensic-probe-v1", "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "mode": "dry" if args.dry else "live", "batch_sizes": sizes, "repeats": args.repeats,
           "rows": rows, "reconciliation": recon}
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2, default=str))
        print(f"[probe] wrote {args.out}")
    if live:
        print(f"\n[probe] reconciliation: {json.dumps(recon, default=str)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
