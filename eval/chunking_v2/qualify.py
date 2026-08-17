"""CHUNKING-V2-QUALIFICATION harness (SEMANTIC-CHUNKING-V2 §13-15).

Compares legacy_v1 vs semantic_v2 on the frozen qualification set:
structural correctness (zero hard-boundary violations), semantic
boundary quality vs the frozen gold (dev subset drives the parameter
matrix; sealed subset is scored ONCE after selection), offset
roundtrip, determinism (5 runs), size distribution, throughput.
The frozen I4 scorer is untouched; no retrieval ranking changes here.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

QUAL = Path(__file__).parent / "qualification"

_HEADING_LINE = re.compile(r"^#{1,6}\s+")


def load_corpus():
    return {p.name: p.read_text() for p in sorted((QUAL / "corpus").glob("*.md"))}


def heading_offsets(text: str) -> list[tuple[int, int]]:
    """(start, end) char spans of every heading line."""
    out = []
    offset = 0
    for line in text.splitlines(keepends=True):
        if _HEADING_LINE.match(line.strip()):
            out.append((offset, offset + len(line)))
        offset += len(line)
    return out


def legacy_children(text: str) -> list[dict]:
    from workers.chunker import materialize_chunks, plan_document

    plan = plan_document(text, "doc", child_target_chars=1200, parent_fanout=4)
    rows = materialize_chunks(plan)
    return [r for r in rows if r["tier"] == "child"]


def semantic_children(text: str, cache, params: dict) -> list[dict]:
    from workers.semantic_chunker import semantic_chunk_rows

    rows = semantic_chunk_rows(text, "doc", cache=cache, params=params)
    return [r for r in rows if r["tier"] == "child"]


def structural_report(text: str, children: list[dict]) -> dict:
    headings = heading_offsets(text)
    contamination = cross_section = offset_fail = 0
    for c in children:
        for hs, he in headings:
            if hs < c["char_end"] and he > c["char_start"]:
                cross_section += 1
                break
        if any(c["text"].strip().startswith("#" * h + " ") for h in range(1, 7)):
            contamination += 1
        if text[c["char_start"]:c["char_end"]] != c["text"]:
            offset_fail += 1
    return {
        "chunks": len(children),
        "heading_contamination": contamination,
        "cross_section": cross_section,
        "offset_failures": offset_fail,
    }


def _chunk_of(children, pos):
    for c in children:
        if c["char_start"] <= pos < c["char_end"]:
            return c
    return None


def boundary_eval(children: list[dict], text: str, gold: dict) -> dict:
    by_doc_required = [g for g in gold["required_breaks"]]
    required_hit = 0
    for g in by_doc_required:
        b = text.find(g["before"][:40])
        a = text.find(g["after"][:40])
        if b < 0 or a < 0:
            continue
        cb, ca = _chunk_of(children, b), _chunk_of(children, a)
        if cb is not None and ca is not None and cb["chunk_id"] != ca["chunk_id"]:
            required_hit += 1
    forbidden_violations = 0
    for g in gold["forbidden_breaks"]:
        b = text.find(g["within"][0][:40])
        a = text.find(g["within"][1][:40])
        if b < 0 or a < 0:
            continue
        a_end = a + len(g["within"][1][:40])
        for c in children:
            if c["char_start"] > b and c["char_start"] < a_end:
                forbidden_violations += 1
                break
    n_required = len(gold["required_breaks"])
    return {
        "required_recall": round(required_hit / n_required, 3) if n_required else None,
        "forbidden_violations": forbidden_violations,
        "n_required": n_required,
    }


def size_distribution(children: list[dict]) -> dict:
    sizes = sorted(len(c["text"].split()) for c in children)
    if not sizes:
        return {}
    def pct(p):
        return sizes[min(len(sizes) - 1, int(p * len(sizes)))]
    return {
        "p10": pct(0.10), "p50": pct(0.50), "p90": pct(0.90), "p99": pct(0.99),
        "tiny_rate": round(sum(1 for s in sizes if s < 8) / len(sizes), 3),
        "oversize_rate": round(sum(1 for s in sizes if s > 512) / len(sizes), 3),
    }


def manifest_hash(children: list[dict]) -> str:
    payload = [{"s": c["char_start"], "e": c["char_end"], "t": hashlib.sha256(c["text"].encode()).hexdigest()}
               for c in children]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def run_provider(name, corpus, produce, gold, runs=5) -> dict:
    per_doc, total_time = {}, 0.0
    all_children = {}
    for doc, text in corpus.items():
        t0 = time.perf_counter()
        children = produce(text)
        total_time += time.perf_counter() - t0
        per_doc[doc] = structural_report(text, children)
        all_children[doc] = children
    # determinism: rerun manifest hashes (5x)
    manifests = []
    for _ in range(runs):
        run_hashes = {}
        for doc, text in corpus.items():
            children = produce(text)
            run_hashes[doc] = manifest_hash(children)
        manifests.append(run_hashes)
    deterministic = all(m == manifests[0] for m in manifests)
    boundary = {}
    for doc, children in all_children.items():
        doc_gold = {
            "required_breaks": [g for g in gold["required_breaks"] if g["doc"] == doc],
            "forbidden_breaks": [g for g in gold["forbidden_breaks"] if g["doc"] == doc],
        }
        if doc_gold["required_breaks"] or doc_gold["forbidden_breaks"]:
            boundary[doc] = boundary_eval(children, corpus[doc], doc_gold)
    sizes = size_distribution([c for ch in all_children.values() for c in ch])
    agg = {
        "provider": name,
        "structural": {
            "chunks": sum(v["chunks"] for v in per_doc.values()),
            "heading_contamination": sum(v["heading_contamination"] for v in per_doc.values()),
            "cross_section": sum(v["cross_section"] for v in per_doc.values()),
            "offset_failures": sum(v["offset_failures"] for v in per_doc.values()),
        },
        "boundary": boundary,
        "boundary_totals": {
            "required_recall": round(
                sum(b["required_recall"] * b["n_required"] for b in boundary.values()) /
                max(1, sum(b["n_required"] for b in boundary.values())), 3),
            "forbidden_violations": sum(b["forbidden_violations"] for b in boundary.values()),
        },
        "sizes": sizes,
        "deterministic": deterministic,
        "wall_s": round(total_time, 3),
    }
    return agg


def main():
    corpus = load_corpus()
    dev_gold = json.loads((QUAL / "gold" / "boundary_gold_dev.json").read_text())
    # sealed gold is scored only after parameter selection (see score_sealed)
    dev_corpus = {d: corpus[d] for d in dev_gold["docs"]}

    from workers.semantic_chunker import SEMANTIC_V2_DEFAULTS, SemanticEmbeddingCache

    results = {"legacy_v1": run_provider(
        "legacy_v1", dev_corpus, legacy_children, dev_gold)}

    matrix = {}
    for threshold in (0.55, 0.65, 0.75, 0.85):
        for window in (1, 3):
            params = {"threshold": threshold, "similarity_window": window}
            cache = SemanticEmbeddingCache()
            r = run_provider(
                f"semantic_v2@t{threshold}/w{window}", dev_corpus,
                lambda t, p=params, c=cache: semantic_children(t, c, p),
                dev_gold)
            r["cache"] = {"hits": cache.hits, "misses": cache.misses, "requests": cache.requests}
            matrix[f"t{threshold}/w{window}"] = r

    out = {"legacy_v1": results["legacy_v1"], "matrix": matrix}
    Path(__file__).parent.joinpath("artifacts").mkdir(exist_ok=True)
    (Path(__file__).parent / "artifacts" / "dev_matrix.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps({
        "legacy": {k: results["legacy_v1"][k] for k in ("structural", "boundary_totals", "deterministic")},
        "matrix_summary": {k: {"boundary": v["boundary_totals"], "chunks": v["structural"]["chunks"],
                               "cross_section": v["structural"]["cross_section"],
                               "offset_failures": v["structural"]["offset_failures"],
                               "deterministic": v["deterministic"]}
                           for k, v in matrix.items()},
    }, indent=2, default=str))


if __name__ == "__main__":
    main()


def score_sealed(params: dict | None = None):
    """Score the SEALED subset ONCE with the selected parameters."""
    corpus = load_corpus()
    sealed_gold = json.loads((QUAL / "gold" / "boundary_gold_sealed.json").read_text())
    sealed_corpus = {d: corpus[d] for d in sealed_gold["docs"]}
    from workers.semantic_chunker import SemanticEmbeddingCache

    cache = SemanticEmbeddingCache()
    r = run_provider("semantic_v2-sealed", sealed_corpus,
                     lambda t: semantic_children(t, cache, params or {}), sealed_gold)
    r["cache"] = {"hits": cache.hits, "misses": cache.misses}
    legacy = run_provider("legacy_v1-sealed", sealed_corpus, legacy_children, sealed_gold)
    out = {"semantic_v2": r, "legacy_v1": legacy, "params": params or "defaults"}
    (Path(__file__).parent / "artifacts" / "sealed_score.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps({k: out[k]["boundary_totals"] for k in ("semantic_v2", "legacy_v1")},
                     indent=2, default=str))


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "sealed":
    import json as _json

    prm = _json.loads(sys.argv[2]) if len(sys.argv) > 2 else None
    score_sealed(prm)
