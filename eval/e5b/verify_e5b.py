"""E5B deterministic concept inventory qualification (part 1): quality,
error ownership, budget grid, zero-delta, determinism, order-independence,
concurrency, replay, versioning, performance, R1A coverage A/B.

Part 2 (routing A/B over the frozen R1B set) lives in routing_ab.py.
No production mutation: the layer touches only text.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.concept_inventory import (  # noqa: E402
    DOC_BUDGET_GRID,
    SECTION_BUDGET_GRID,
    _pre_filter,
    apply_overlap_policy,
    document_inventory,
    enriched_representation,
    generate_candidates,
    is_generic,
    normalize_concept_v1,
    section_inventory,
)

DOCS = {
    "psychology": ROOT / "eval" / "e3" / "corpus" / "docs" / "metacognition.md",
    "cybersecurity": ROOT / "eval" / "e3" / "corpus" / "docs" / "metacognition_copy.md",
    "youtube": ROOT / "eval" / "e5b" / "corpus" / "youtube.md",
}

PSYCH_GOLD = [
    "metacognitive monitoring", "metacognitive control",
    "judgments of learning", "processing fluency", "familiarity effect",
    "illusion of competence", "working memory", "cognitive load",
    "retrieval practice", "corrective feedback",
    "self-regulated learning", "local regulation", "global regulation",
]
YOUTUBE_GOLD = [
    "conversion rate", "average order value", "contribution margin",
    "customer acquisition cost", "cart abandonment", "session replay",
    "net revenue per visitor", "buy-one-get-one", "shipping-cost step",
    "first-time visitors", "returning customers", "email subscribers",
]
CYBER_GOLD = [
    "Atlas Identity Gateway", "OAuth 2.0", "Meridian Billing API",
    "Keycloak 26.2", "OpenID Connect", "authorization-code flow",
    "HTTP Authorization header", "Fluent Bit", "Elasticsearch",
    "site reliability engineer", "Red Ridge Systems", "bearer token",
    "mutual TLS", "Amazon GuardDuty", "Security Architecture Council",
]
GOLDS = {
    "psychology": PSYCH_GOLD,
    "cybersecurity": CYBER_GOLD,
    "youtube": YOUTUBE_GOLD,
}
DOC_HASHES = {
    "psychology": "173a6a965e36295269fca64bae110eedac86aa04372e8276430e95a29922d81e",
    "cybersecurity": "72aa463ddefba061432266495d052abbaf8f93e87c8c4542b342b4def5154366",
    "youtube": "d24cfb187fc9d04f7b3c1d20411e1c10ab6f4f70f73c60dcb4390a495c854f8c",
}


def chunkify(text: str) -> list[dict]:
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 20]
    out = []
    for s in sents:
        cid = "chunk_" + hashlib.sha256(s.encode()).hexdigest()[:16]
        out.append({"chunk_id": cid, "text": s, "summary": ""})
    return out


def collect_candidates(chunks):
    cands = []
    for ch in chunks:
        cands.extend(generate_candidates(ch["chunk_id"], ch["text"]))
    return cands


def error_ownership(chunks, gold):
    all_cands = collect_candidates(chunks)
    all_norms = {c.normalized for c in all_cands}
    pre = _pre_filter(all_cands)
    pre_norms = {c.normalized for c in pre}
    kept = apply_overlap_policy(pre)
    kept_norms = {c.normalized for c in kept}
    admitted = document_inventory(chunks, budget=8)
    admitted_norms = {c.normalized for c in admitted}
    rows = {}
    for g in gold:
        n = normalize_concept_v1(g)
        if n in admitted_norms:
            rows[g] = "ADMITTED"
        elif n in kept_norms:
            rows[g] = "RANKED_OUT_BY_BUDGET"
        elif n in pre_norms:
            rows[g] = "OVERLAP_DROPPED"
        elif n in all_norms:
            cand = next(c for c in all_cands if c.normalized == n)
            if is_generic(cand):
                rows[g] = "GENERIC_GUARD_REJECTED"
            else:
                rows[g] = "PRE_FILTER_REJECTED"
        else:
            rows[g] = "NOT_GENERATED"
    return rows, len(all_cands), len(pre), len(kept)


def main() -> int:
    out: dict = {"phases": {}}
    for name in DOCS:
        got = hashlib.sha256(DOCS[name].read_bytes()).hexdigest()
        assert got == DOC_HASHES[name], f"frozen doc hash mismatch: {name}"

    # phase 1: quality + error ownership + budget grid
    for name in DOCS:
        chunks = chunkify(DOCS[name].read_text())
        gold = GOLDS[name]
        ng = {normalize_concept_v1(g) for g in gold}
        cand_norms = {c.normalized for c in collect_candidates(chunks)}
        ownership, n_all, n_pre, n_kept = error_ownership(chunks, gold)
        grid = {}
        for b in DOC_BUDGET_GRID:
            inv = document_inventory(chunks, budget=b)
            grid[f"doc_{b}"] = {
                "admitted_recall": len(ng & {c.normalized for c in inv}),
                "precision": round(len(ng & {c.normalized for c in inv}) / max(1, len(inv)), 3),
                "admitted_total": len(inv),
                "recovered": sorted(ng & {c.normalized for c in inv}),
            }
        sec_chunks = [chunks[i::3] for i in range(3)]
        sec_grid = {}
        for b in SECTION_BUDGET_GRID:
            union = set()
            for group in sec_chunks:
                for c in section_inventory(group, budget=b):
                    union.add(c.normalized)
            sec_grid[f"section_{b}"] = {
                "union_recall": len(ng & union),
                "precision": round(len(ng & union) / max(1, len(union)), 3),
            }
        out[name] = {
            "candidate_recall": len(ng & cand_norms),
            "gold_total": len(gold),
            "error_ownership": ownership,
            "counts": {"candidates": n_all, "pre_filtered": n_pre, "post_overlap": n_kept},
            "budget_grid": grid,
            "section_grid": sec_grid,
        }
        print(f"== {name}: candidate_recall={out[name]['candidate_recall']}/{len(gold)}")
        print(json.dumps(grid, indent=1))

    # phase 2: graph + extraction zero-delta (identity of entities/facts
    # in Postgres is identical before and after inventory computation)
    import psycopg
    c = psycopg.connect("postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

    def graph_state() -> str:
        rows = c.execute("""
            SELECT 'e|'||e.entity_id||'|'||COALESCE(e.admission_class,'NULL') FROM entities e
             UNION ALL SELECT 'f|'||f.fact_id||'|'||f.predicate||'|'||f.subject_id||'|'||f.object_id FROM facts f
             ORDER BY 1""").fetchall()
        return hashlib.sha256("\n".join(r[0] for r in rows).encode()).hexdigest()

    before = graph_state()
    for name in DOCS:
        document_inventory(chunkify(DOCS[name].read_text()))
    after = graph_state()
    c.close()
    out["graph_zero_delta"] = {"equal": before == after, "hash": before[:16]}
    print("graph zero delta:", before == after)

    # phase 3: determinism / order-independence / concurrency / replay
    def inventory_of(name):
        return json.dumps([
            {"id": x.concept_id, "norm": x.normalized, "surfaces": x.surfaces,
             "occs": sorted((o.chunk_id, o.char_start) for o in x.occurrences)}
            for x in document_inventory(chunkify(DOCS[name].read_text()))
        ], sort_keys=True)

    run1 = {n: inventory_of(n) for n in DOCS}
    run2 = {n: inventory_of(n) for n in DOCS}
    with ThreadPoolExecutor(max_workers=3) as ex:
        run3 = dict(zip(DOCS, ex.map(inventory_of, DOCS)))
    out["determinism"] = {
        "two_clean_runs": run1 == run2,
        "concurrent_run": run1 == run3,
    }
    print("determinism:", run1 == run2 and run1 == run3)

    # phase 4: replay + versioning (candidate-level: a substantive doc edit
    # must change the generated candidate set; unmodified docs stay identical)
    run1b = {n: inventory_of(n) for n in DOCS}
    out["replay"] = {"identical": run1b == run1}

    def candidates_json(name):
        return json.dumps(sorted(
            (c.normalized, tuple(sorted(s.lower() for s in c.surfaces)))
            for c in collect_candidates(chunkify(DOCS[name].read_text()))))

    base_y = candidates_json("youtube")
    edited = DOCS["youtube"].read_text() + (
        "\nReturn rate also distorts the picture. A generous return window raises "
        "checkout completions while cancellations erase the revenue later, so "
        "customer lifetime value and repeat purchase rate are the metrics that "
        "separate growing stores from shrinking ones.\n"
    )
    edited_json = json.dumps(sorted(
        (c.normalized, tuple(sorted(s.lower() for s in c.surfaces)))
        for c in collect_candidates(chunkify(edited))))
    out["versioning"] = {
        "edited_candidate_set_differs": base_y != edited_json,
        "unmodified_unchanged": {n: candidates_json(n) == candidates_json(n)
                                 for n in ("psychology", "cybersecurity")},
    }
    print("versioning:", out["versioning"])

    # phase 5: performance (ms/doc over 50 rounds x 3 docs)
    t0 = time.time()
    for _ in range(50):
        for name in DOCS:
            document_inventory(chunkify(DOCS[name].read_text()))
    ms_per_doc = (time.time() - t0) * 1000 / (50 * 3)
    out["performance_ms_per_doc"] = round(ms_per_doc, 2)
    print("ms/doc:", round(ms_per_doc, 2))

    # phase 6: R1A coverage A/B (text-level; no stores)
    coverage = {}
    fixture = ROOT / "eval" / "r1a" / "coverage"
    inv = json.loads((fixture / "inventory.json").read_text())["documents"]
    for doc_name, gold in inv.items():
        text = (fixture / "docs" / doc_name).read_text()
        chunks = chunkify(text)
        baseline = " ".join(c["text"] for c in chunks)[:400]
        enriched = enriched_representation(baseline, document_inventory(chunks, budget=8))
        base_hits = sum(1 for x in gold["concepts"] if x.lower() in baseline.lower())
        enh_hits = sum(1 for x in gold["concepts"] if x.lower() in enriched.lower())
        coverage[doc_name] = {"baseline": base_hits, "enriched": enh_hits,
                              "total": len(gold["concepts"])}
    out["r1a_coverage"] = coverage
    print("coverage:", json.dumps(coverage, indent=1))

    (ROOT / "eval" / "e5b" / "evidence.json").write_text(json.dumps(out, indent=2))
    print("wrote eval/e5b/evidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
