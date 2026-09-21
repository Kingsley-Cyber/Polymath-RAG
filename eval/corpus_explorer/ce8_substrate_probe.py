"""CORPUS-EXPLORE-FIRING-V1 Phase A.2 — $0 substrate probe: embed q0 -> search_atoms ->
build_activation_candidates, x10 per query, NO LLM. Answers: is the activation substrate deterministic, and
does it ever return empty / error? Run from the MAIN checkout with `.env` sourced; writes the JSON artifact
named by argv[1]."""
import hashlib, json, statistics, sys, time
from polymath_shared.corpus_activation import CONCEPT_ATOM_KINDS, build_activation_candidates
from polymath_shared.document_profile import profile_atom_projection as pap
from polymath_shared.embedding_contracts import active_contract
from polymath_shared.settings import get_settings
from orchestrator.api.fast import _embed_queries
from qdrant_client import QdrantClient

QUERIES = {
    "physical_weight__f2": "the movement should feel grounded and forceful rather than weightless and flashy",
    "suppressed_grief": "make a character's suppressed grief visible while they try hard to hide it",
    "nonverbal_authority__f0": "a character commands a room the moment she enters, without saying a word",
    "neg_cooking": "create an upbeat step-by-step cooking tutorial for a simple pasta dish",
}
N = 10
CORPUS = sys.argv[2] if len(sys.argv) > 2 else "cinema"      # Item 2/D: the atom lookup is corpus-scoped by contract
coll = pap.collection_name(active_contract().contract_id)
out = {"collection": coll, "corpus_id": CORPUS, "n_repeats": N, "queries": {}}
for key, q in QUERIES.items():
    rows = []
    for i in range(N):
        rec = {"i": i}
        try:
            t0 = time.perf_counter()
            qv = list(_embed_queries([q])[0])
            rec["embed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            rec["vec_sha"] = hashlib.sha1(json.dumps([round(x, 6) for x in qv]).encode()).hexdigest()[:10]
            c = QdrantClient(url=get_settings().stores.qdrant_url, timeout=10)   # fresh client each time = the live path
            try:
                t1 = time.perf_counter()
                hits = pap.search_atoms(c, coll, qv, CONCEPT_ATOM_KINDS, k=12, corpus_ids=[CORPUS])
                rec["search_ms"] = round((time.perf_counter() - t1) * 1000, 1)
            finally:
                c.close()
            cands = build_activation_candidates(hits, max_activations=8, min_grounding=1)
            rec["n_hits"] = len(hits)
            rec["n_cands"] = len(cands)
            rec["hit_ids"] = [h["atom_id"] for h in hits]
            rec["cand_ids"] = [x.concept_id for x in cands]
            rec["top_score"] = round(hits[0]["score"], 4) if hits else None
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        rows.append(rec)
    ok = [r for r in rows if "error" not in r]
    out["queries"][key] = {
        "q": q, "errors": [r["error"] for r in rows if "error" in r],
        "empties": sum(1 for r in ok if r["n_hits"] == 0),
        "distinct_vectors": len({r["vec_sha"] for r in ok}),
        "distinct_hit_lists": len({tuple(r["hit_ids"]) for r in ok}),
        "distinct_cand_lists": len({tuple(r["cand_ids"]) for r in ok}),
        "n_cands": sorted({r["n_cands"] for r in ok}),
        "top_score": sorted({r["top_score"] for r in ok}),
        "embed_ms_first": rows[0].get("embed_ms"), "embed_ms_p50_rest": round(statistics.median([r["embed_ms"] for r in ok[1:]]), 1) if len(ok) > 1 else None,
        "search_ms_first": rows[0].get("search_ms"), "search_ms_p50_rest": round(statistics.median([r["search_ms"] for r in ok[1:]]), 1) if len(ok) > 1 else None,
        "search_ms_max": max((r["search_ms"] for r in ok), default=None),
        "cand_ids": ok[0]["cand_ids"] if ok else [],
    }
json.dump(out, open(sys.argv[1], "w"), indent=1)
for k, v in out["queries"].items():
    print(k, {kk: vv for kk, vv in v.items() if kk not in ("q", "cand_ids")})
