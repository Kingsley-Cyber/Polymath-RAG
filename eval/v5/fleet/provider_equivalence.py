"""PROVIDER-EQUIVALENCE bench (EXTRACTION-FLEET-V3 item 1 — the one
the review called the most important). Same chunks, same contract,
one representative lane per provider FAMILY; compared AFTER the
deterministic gate — because what multi-provider extraction threatens
is recall consistency, and only accepted output counts.

    .venv/bin/python eval/v5/fleet/provider_equivalence.py \
        --corpus <corpus_id> [--chunks 60]

Exit 0 always — measurement, not judgment; tiering is the owner's.
Writes PROVIDER-EQUIVALENCE-RESULTS.md next to this file.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import time
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[3]
for sub in ("shared", "workers"):
    sys.path.insert(0, str(ROOT / sub))

HERE = pathlib.Path(__file__).parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--chunks", type=int, default=60)
    args = ap.parse_args()

    import psycopg

    from polymath_shared.llm_extraction.client import LLMExtractionClient
    from polymath_shared.llm_extraction.gate import (
        ChunkView,
        validate_and_normalize,
    )
    from polymath_shared.llm_extraction.pool import cloud_endpoints
    from polymath_shared.settings import get_settings

    with psycopg.connect(get_settings().postgres.dsn,
                         connect_timeout=5) as conn:
        rows = conn.execute(
            """SELECT ch.chunk_id, ch.text FROM chunks ch
                 JOIN documents d ON d.doc_id = ch.doc_id
                WHERE d.corpus_id = %s AND ch.tier = 'child'
                  AND coalesce(ch.region_role, 'body') = 'body'
                  AND ch.token_count >= 50""",
            (args.corpus,)).fetchall()
    # deterministic sample: order by content digest, take N
    rows.sort(key=lambda r: hashlib.blake2b(
        r[0].encode(), digest_size=8).digest())
    sample = rows[:args.chunks]
    if not sample:
        print("no eligible chunks"); return 0
    total_tokens = sum(len(t.split()) for _, t in sample)

    # one representative lane per provider family (distinct URL host)
    reps: dict[str, object] = {}
    for e in cloud_endpoints():
        host = urlparse(e.url).netloc or e.name
        reps.setdefault(host, e)
    print(f"sample: {len(sample)} chunks ({total_tokens} words) · "
          f"families: {[e.name for e in reps.values()]}")

    per_model: dict[str, dict] = {}
    for host, ep in reps.items():
        client = LLMExtractionClient(
            "cloud", url=ep.url, model=ep.model,
            limiter_key=ep.limiter_key, api_key=ep.api_key,
            cloud_opts=ep.cloud_opts if ep.name != "primary" else None)
        ents: set = set()
        facts: set = set()
        quarantined = rejected = 0
        walls = []
        for cid, text in sample:
            t0 = time.perf_counter()
            try:
                r = client.extract([(cid, [(cid, text)])],
                                   source_bytes=10**9, threshold_bytes=0)
            except Exception as exc:  # noqa: BLE001
                quarantined += 1
                continue
            walls.append(time.perf_counter() - t0)
            if r.packet is None:
                quarantined += 1
                continue
            norm = validate_and_normalize(
                r.packet, {cid: [ChunkView(cid, text)]})
            rejected += len(norm.rejections)
            for rows_ in norm.entities_by_chunk.values():
                for m in rows_:
                    ents.add((m.get("label") or m.get("raw_type") or "?",
                              (m.get("text") or "").lower()))
            for rows_ in norm.evidence_by_chunk.values():
                for ev in rows_:
                    if ev.get("evidence_class") == "llm_relation":
                        facts.add((ev.get("predicate"),
                                   (ev.get("subject") or "").lower(),
                                   (ev.get("object") or "").lower()))
        per_model[ep.name] = {
            "model": ep.model, "entities": ents, "facts": facts,
            "quarantined": quarantined, "rejected": rejected,
            "mean_wall": (sum(walls) / len(walls)) if walls else None,
        }
        print(f"  {ep.name}: facts {len(facts)} · entities {len(ents)} "
              f"· quarantined {quarantined}")

    names = list(per_model)
    lines = ["# PROVIDER EQUIVALENCE RESULTS", "",
             f"corpus: {args.corpus} · chunks: {len(sample)} · "
             f"words: {total_tokens}", "",
             "## Accepted density (post-gate)",
             "| lane | model | facts/1K words | entities/1K words | "
             "quarantined | rejections | mean wall s |",
             "|---|---|---|---|---|---|---|"]
    for n in names:
        d = per_model[n]
        lines.append(
            f"| {n} | {d['model']} | "
            f"{len(d['facts']) * 1000 / total_tokens:.1f} | "
            f"{len(d['entities']) * 1000 / total_tokens:.1f} | "
            f"{d['quarantined']} | {d['rejected']} | "
            f"{d['mean_wall']:.1f} |" if d['mean_wall'] else
            f"| {n} | {d['model']} | 0 | 0 | {d['quarantined']} | "
            f"{d['rejected']} | - |")
    lines += ["", "## Pairwise FACT agreement (Jaccard over accepted "
              "(pred, subj, obj))", "| A | B | agreement | A-only | "
              "B-only |", "|---|---|---|---|---|"]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            fa, fb = per_model[a]["facts"], per_model[b]["facts"]
            union = fa | fb
            j = len(fa & fb) / len(union) if union else 1.0
            lines.append(f"| {a} | {b} | {j:.2f} | {len(fa - fb)} | "
                         f"{len(fb - fa)} |")
    lines += ["", "## Owner gate",
              "Tiering is the owner's call: a lane far below the top "
              "density, or pairwise agreement far under ~0.6, is a "
              "quality-tier candidate (overflow-only), and family-"
              "interleaved slices become worth wiring. Comparable "
              "lanes = the fleet is interchangeable as configured."]
    out = HERE / "PROVIDER-EQUIVALENCE-RESULTS.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
