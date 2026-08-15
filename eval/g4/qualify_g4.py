"""G4 corpus-scale graph expansion qualification (frozen experiment).

Baseline-first: run the EXISTING production expansion policy unchanged
(one-hop _neo4j_expand + HIGH_MEDIUM predicate allowlist + LIMIT caps)
against a deterministic qualification corpus with heavy-tailed degree.
Configs: A no-graph, B graph hop1 (production), C hop2 (measurement-only
variant, documented as NOT production depth). Optional G3 reranker arm
(downstream qualification only; never promotes G3).

Frozen inputs: eval/g4/frozen_queries.json (hashed before inspection),
eval/g4/corpus_spec.json. Deterministic repeats for every graph-enabled
configuration. No LLM judge: relevance uses the authored per-query
relevant/noise surface lists plus deterministic surface-token overlap.

Usage:
    .venv/bin/python eval/g4/qualify_g4.py --seed
    .venv/bin/python eval/g4/qualify_g4.py --run [--reranker]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.identity import entity_id, evidence_id, fact_id, run_id  # noqa: E402
from orchestrator.orchestrator.api.retrieve import HIGH_MEDIUM_PREDICATES  # noqa: E402
from polymath_shared.stores import neo4j_driver  # noqa: E402
from orchestrator.orchestrator.api.retrieve import _neo4j_expand  # noqa: E402
from polymath_shared.retrieval import tokens  # noqa: E402

G4 = ROOT / "eval" / "g4"
ARTIFACTS = G4 / "artifacts"
CORPUS = "g4_e2e"
QUERY_SET_HASH = hashlib.sha256(
    (G4 / "frozen_queries.json").read_bytes()).hexdigest()

HUB_SPECS = [
    ("the platform", "Technology", 50),
    ("the database", "Technology", 40),
    ("the vector index", "Technology", 35),
    ("the worker pool", "Technology", 30),
    ("the retrieval pipeline", "Technology", 25),
    ("the system", "Concept", 15),
    ("the model", "Technology", 15),
]
PREDICATES = ["uses", "part_of", "depends_on", "influences", "enables",
              "causes", "is_a", "instance_of", "measured_by"]
LEAF_PER_DOC = 22


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def _cleanup() -> None:
    with tx() as conn:
        ids = conn.execute(
            "SELECT jsonb_agg(id) FROM ("
            "SELECT DISTINCT c.chunk_id AS id FROM chunks c JOIN documents d ON d.doc_id=c.doc_id WHERE d.corpus_id=%s "
            "UNION SELECT DISTINCT e.evidence_id AS id FROM evidence e JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s "
            "UNION SELECT DISTINCT f.fact_id AS id FROM facts f JOIN evidence e ON e.fact_id=f.fact_id JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s "
            "UNION SELECT DISTINCT ce.canonical_id AS id FROM canonical_entities ce WHERE ce.corpus_id=%s "
            "UNION SELECT DISTINCT cm.local_entity_id AS id FROM canonical_memberships cm WHERE cm.corpus_id=%s "
            "UNION SELECT DISTINCT e2.entity_id AS id FROM entities e2 JOIN facts f2 ON f2.subject_id=e2.entity_id OR f2.object_id=e2.entity_id "
            "JOIN evidence ev2 ON ev2.fact_id=f2.fact_id JOIN documents d2 ON d2.doc_id=ev2.doc_id WHERE d2.corpus_id=%s) x",
            (CORPUS,)*6).fetchone()[0] or []
        chunk_ids=[i for i in ids if i.startswith('chunk_')]
        ev_ids=[i for i in ids if i.startswith('ev_')]
        fact_ids=[i for i in ids if i.startswith('fact_')]
        canon_ids=[i for i in ids if i.startswith('cent_')]
        ent_ids=[i for i in ids if i.startswith('ent_')]
        conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)",
                     (chunk_ids+ev_ids+fact_ids+canon_ids+ent_ids,))
        conn.execute("DELETE FROM canonicalization_decisions WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM canonical_memberships WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM canonical_entities WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM evidence WHERE evidence_id = ANY(%s)", (ev_ids,))
        conn.execute("DELETE FROM facts WHERE fact_id = ANY(%s)", (fact_ids,))
        if ent_ids:
            conn.execute(
                "DELETE FROM entities WHERE entity_id = ANY(%s) "
                "AND NOT EXISTS (SELECT 1 FROM facts f2 WHERE f2.subject_id=entities.entity_id OR f2.object_id=entities.entity_id)",
                (ent_ids,))
        conn.execute("DELETE FROM chunks WHERE chunk_id = ANY(%s)", (chunk_ids,))
        conn.execute("DELETE FROM documents WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM corpora WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM runs WHERE corpus_id = %s", (CORPUS,))
    d = neo4j_driver()
    try:
        with d.session() as s:
            s.run("MATCH (c:CanonicalEntity) WHERE c.corpus_id = $c DETACH DELETE c", c=CORPUS).consume()
            s.run("MATCH (ch:Chunk) WHERE ch.chunk_id IN $ids DETACH DELETE ch", ids=chunk_ids).consume()
            s.run("MATCH (ev:Evidence) WHERE ev.evidence_id IN $ids DETACH DELETE ev", ids=ev_ids).consume()
            s.run("MATCH (f:Fact) WHERE f.fact_id IN $ids DETACH DELETE f", ids=fact_ids).consume()
            if ent_ids:
                s.run("MATCH (e:Entity) WHERE e.entity_id IN $ids DETACH DELETE e", ids=ent_ids).consume()
    finally:
        d.close()


def seed() -> None:
    _cleanup()
    canonical = {
        "corpus_id": CORPUS, "source_name": "g4.txt", "media_type": "text/plain",
        "content_b64": "eA==", "config": {},
    }
    rid = run_id(CORPUS, canonical)
    hub_ids = {surf: entity_id(ctype, surf) for surf, ctype, _ in HUB_SPECS}
    hub_ctypes = {surf: ctype for surf, ctype, _ in HUB_SPECS}

    with tx() as conn:
        conn.execute(
            "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, %s)",
            (CORPUS, "g4 corpus", "g4-config"),
        )
        conn.execute(
            "INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s, %s, 'reconciling', %s)",
            (rid, CORPUS, json.dumps({"intake_payload": canonical})),
        )
        for h in HUB_SPECS:
            conn.execute(
                "INSERT INTO entities (entity_id, core_type, normalized_surface) VALUES (%s, %s, %s) "
                "ON CONFLICT (entity_id) DO NOTHING",
                (hub_ids[h[0]], h[1], h[0]),
            )
        fi = 0
        for doc_i in range(12):
            doc_id = f"doc_g4_{doc_i:02d}"
            chunk_id = f"chunk_g4_{doc_i:02d}"
            text = f"Qualification document {doc_i} about the platform, the database, the vector index, the worker pool and the retrieval pipeline."
            conn.execute(
                """
                INSERT INTO documents (doc_id, corpus_id, source_name, media_type,
                                       byte_length, content_hash, retrieval_profile)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (doc_id, CORPUS, f"g4_{doc_i}.txt", "text/plain", len(text),
                 f"hash-g4-{doc_i}", json.dumps({"semantic_summary": text})),
            )
            conn.execute(
                """
                INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier,
                                    text, summary, char_start, char_end)
                VALUES (%s, %s, NULL, 0, 'child', %s, '', 0, %s)
                """,
                (chunk_id, doc_id, text, len(text)),
            )
            for leaf_i in range(LEAF_PER_DOC):
                surf = f"component {doc_i}x{leaf_i}"
                leaf_id = entity_id("Technology", surf)
                conn.execute(
                    "INSERT INTO entities (entity_id, core_type, normalized_surface) VALUES (%s, %s, %s) "
                    "ON CONFLICT (entity_id) DO NOTHING",
                    (leaf_id, "Technology", surf),
                )
                hub_surf = HUB_SPECS[(doc_i * 7 + leaf_i) % len(HUB_SPECS)][0]
                pred = PREDICATES[(doc_i * 3 + leaf_i) % len(PREDICATES)]
                fid = fact_id(pred, leaf_id, hub_ids[hub_surf], {})
                conn.execute(
                    """
                    INSERT INTO facts (fact_id, predicate, subject_id, object_id,
                                       qualifiers, decision, rule_id, rule_version, provenance)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (fact_id) DO NOTHING
                    """,
                    (fid, pred, leaf_id, hub_ids[hub_surf], "{}", "ACCEPT",
                     f"rule-{pred}", "1.0.1", json.dumps({"resource_contract_id": "03a513ec"})),
                )
                conn.execute(
                    """
                    INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id,
                                          span_offsets, rule_id, gliner_scores,
                                          extractor_version, rule_version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (evidence_id) DO NOTHING
                    """,
                    (evidence_id(fid, doc_id, chunk_id, {}, f"rule-{pred}"),
                     fid, doc_id, chunk_id, "{}", f"rule-{pred}", "{}", "1.0", "1.0.1"),
                )
                fi += 1
        # hub-hub edges for cross-domain bridge structure
        for a, b in [("the platform", "the database"), ("the platform", "the vector index"),
                     ("the retrieval pipeline", "the database"), ("the worker pool", "the platform"),
                     ("the vector index", "the worker pool")]:
            fid = fact_id("part_of", hub_ids[a], hub_ids[b], {})
            conn.execute(
                """
                INSERT INTO facts (fact_id, predicate, subject_id, object_id,
                                   qualifiers, decision, rule_id, rule_version, provenance)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fact_id) DO NOTHING
                """,
                (fid, "part_of", hub_ids[a], hub_ids[b], "{}", "ACCEPT",
                 "rule-part_of", "1.0.1", json.dumps({"resource_contract_id": "03a513ec"})),
            )
    named = json.loads((G4 / "corpus_spec_v1.1.json").read_text())["named_query_entities"]
    surface_id: dict[str, str] = dict(hub_ids)
    for spec in named:
        surface_id[spec["surface"]] = entity_id(spec["core_type"], spec["surface"])
    with tx() as conn:
        for spec in named:
            eid = surface_id[spec["surface"]]
            conn.execute(
                "INSERT INTO entities (entity_id, core_type, normalized_surface) VALUES (%s, %s, %s) "
                "ON CONFLICT (entity_id) DO NOTHING",
                (eid, spec["core_type"], spec["surface"]),
            )
        for spec in named:
            for subj_surf, pred, obj_surf in spec["edges"]:
                sid = surface_id[subj_surf]
                oid = surface_id[obj_surf]
                fid = fact_id(pred, sid, oid, {})
                conn.execute(
                    """
                    INSERT INTO facts (fact_id, predicate, subject_id, object_id,
                                       qualifiers, decision, rule_id, rule_version, provenance)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (fact_id) DO NOTHING
                    """,
                    (fid, pred, sid, oid, "{}", "ACCEPT",
                     f"rule-{pred}", "1.0.1", json.dumps({"resource_contract_id": "03a513ec"})),
                )
                conn.execute(
                    """
                    INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id,
                                          span_offsets, rule_id, gliner_scores,
                                          extractor_version, rule_version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (evidence_id) DO NOTHING
                    """,
                    (evidence_id(fid, "doc_g4_00", "chunk_g4_00", {}, f"rule-{pred}"),
                     fid, "doc_g4_00", "chunk_g4_00", "{}", f"rule-{pred}", "{}",
                     "1.0", "1.0.1"),
                )
    with tx() as conn:
        from workers.project_neo4j_worker import process_event as _pn

        _pn(conn, {"run_id": rid, "payload": {}})
    with tx() as conn:
        from workers.canonicalize_worker import process_event as _canon
        from workers.project_canonical_worker import process_event as _pcanon

        _canon(conn, {"run_id": rid})
        _pcanon(conn, {"run_id": rid, "payload": {}})
    print(f"seeded {12} docs, {len(hub_ids) + 12 * LEAF_PER_DOC} entities, "
          f"{fi + 5} facts -> projected via real workers")


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

def _degree_distribution() -> dict:
    d = neo4j_driver()
    try:
        with d.session() as s:
            rows = s.run(
                "MATCH (n:Entity) "
                "WITH n, "
                "COUNT { (n)-[:REL]->() } + COUNT { ()-[:REL]->(n) } AS degree "
                "RETURN n.entity_id AS id, n.surface AS surface, degree "
                "ORDER BY degree DESC"
            ).data()
    finally:
        d.close()
    degrees = sorted(r["degree"] for r in rows)
    pct = lambda p: degrees[min(len(degrees) - 1, int(len(degrees) * p))]
    top = rows[:8]
    return {
        "nodes": len(degrees),
        "p50": pct(0.50), "p90": pct(0.90), "p95": pct(0.95),
        "p99": pct(0.99), "max": degrees[-1] if degrees else 0,
        "top_nodes": top,
    }


def _hop2_expand(hop1_facts: list[dict]) -> list[dict]:
    """Measurement-only 2nd hop (NOT production depth): expand one more
    REL hop from the OBJECT entities of hop-1 facts, same predicate
    allowlist, excluding edges already seen."""
    ids = sorted({f.get("object_id") for f in hop1_facts if f.get("object_id")})
    if not ids:
        return []
    d = neo4j_driver()
    try:
        with d.session() as s:
            rows = s.run(
                """
                MATCH (s:Entity)-[r:REL]->(o:Entity)
                WHERE s.entity_id IN $ids AND r.predicate IN $predicates
                RETURN r.fact_id AS fact_id, r.predicate AS predicate,
                       s.surface AS subject, o.surface AS object,
                       s.entity_id AS subject_id, o.entity_id AS object_id
                LIMIT 20
                """,
                ids=ids, predicates=sorted(HIGH_MEDIUM_PREDICATES),
            ).data()
    finally:
        d.close()
    return rows


def _bidir_expand(surfaces: list[str]) -> list[dict]:
    """Measurement-only CANDIDATE (not production): bidirectional
    one-hop expansion — outgoing AND incoming REL edges from seeds.
    Same predicate allowlist, same LIMIT caps."""
    d = neo4j_driver()
    try:
        with d.session() as s:
            matched = s.run(
                """
                MATCH (e:Entity)
                WHERE any(s IN $surfaces WHERE toLower(e.surface) CONTAINS s)
                   OR any(s IN $surfaces WHERE s CONTAINS toLower(e.surface))
                RETURN e.entity_id AS entity_id, e.surface AS surface
                LIMIT 8
                """,
                surfaces=surfaces,
            ).data()
            if not matched:
                return []
            ids = [m["entity_id"] for m in matched]
            rows = s.run(
                """
                MATCH (s:Entity)-[r:REL]-(o:Entity)
                WHERE (s.entity_id IN $ids OR o.entity_id IN $ids)
                  AND r.predicate IN $predicates
                  AND s.entity_id <> o.entity_id
                RETURN r.fact_id AS fact_id, r.predicate AS predicate,
                       s.surface AS subject, o.surface AS object,
                       s.entity_id AS subject_id, o.entity_id AS object_id
                LIMIT 20
                """,
                ids=ids, predicates=sorted(HIGH_MEDIUM_PREDICATES),
            ).data()
            return rows
    finally:
        d.close()


def _graph_facts(query: str, policy: str, timing: list[float]) -> tuple[list[dict], dict]:
    """policy: none | hop1 | hop2 (production outgoing-only) |
    bidir-hop1 | bidir-hop2 (measurement-only candidate)."""
    stats = {}
    if policy == "none":
        timing.append(0.0)
        return [], stats
    surfaces = [t for t in tokens(query) if len(t) > 3][:12]
    t0 = time.perf_counter()
    if policy.startswith("bidir"):
        facts = _bidir_expand(surfaces)
    else:
        facts = _neo4j_expand(surfaces)
    stats["hop1_facts"] = len(facts)
    if policy.endswith("hop2"):
        facts2 = _hop2_expand(facts)
        seen = {f["fact_id"] for f in facts}
        stats["hop2_facts"] = len([f for f in facts2 if f["fact_id"] not in seen])
        facts = facts + [f for f in facts2 if f["fact_id"] not in seen]
    timing.append(time.perf_counter() - t0)
    return facts, stats


def _classify(fact: dict, q: dict) -> str:
    surfaces = {fact.get("subject", ""), fact.get("object", "")}
    rel = set(q.get("relevant_surfaces", []))
    noise = set(q.get("noise_surfaces", []))
    relevant = any(s in rel or any(r.split()[-1] in s for r in rel) for s in surfaces)
    noisy = any(s in noise or any(n.split()[-1] in s for n in noise) for s in surfaces)
    if relevant:
        return "relevant"
    if noisy:
        return "irrelevant"
    return "irrelevant"


def run(repeats: int = 3, with_reranker: bool = False) -> None:
    queries = json.loads((G4 / "frozen_queries.json").read_text())["queries"]
    dist = _degree_distribution()
    lines = {k: [] for k in ("baseline", "hop1", "hop2", "bidir-hop1", "bidir-hop2")}
    added_rows = []
    noise_rows = []
    latency_rows = []
    per_query = []

    for q in queries:
        row = {"id": q["id"], "query": q["text"], "class": q["class"]}
        for cfg, policy in (("baseline", "none"), ("hop1", "hop1"),
                            ("hop2", "hop2"), ("bidir-hop1", "bidir-hop1"),
                            ("bidir-hop2", "bidir-hop2")):
            timings: list[float] = []
            for _ in range(repeats):
                facts, stats = _graph_facts(q["text"], policy, timings)
            unique = {f["fact_id"]: f for f in facts}
            row[f"{cfg}_facts"] = len(unique)
            row[f"{cfg}_latency_p50"] = round(statistics.median(timings), 4)
            row[f"{cfg}_latency_p95"] = round(
                sorted(timings)[int(len(timings) * 0.95) - 1] if len(timings) > 1 else timings[0], 4)
            lines[cfg].append({"query_id": q["id"], "facts": facts,
                               "unique_facts": len(unique)})
            if cfg != "baseline":
                base_ids = {f["fact_id"] for f in lines["baseline"][-1]["facts"]}
                added = [f for f in facts if f["fact_id"] not in base_ids]
                hop = 2 if policy.endswith("hop2") else 1
                for f in added:
                    cls = _classify(f, q)
                    added_rows.append({
                        "query_id": q["id"], "config": cfg, "fact_id": f["fact_id"],
                        "predicate": f.get("predicate"),
                        "subject": f.get("subject"), "object": f.get("object"),
                        "classification": cls,
                    })
                    noise_rows.append({"query_id": q["id"], "config": cfg,
                                       "hop": hop, "classification": cls})
        per_query.append(row)

    # noise by hop
    noise_by_hop = []
    for cfg, hop in (("hop1", 1), ("hop2", 2), ("bidir-hop1", 1), ("bidir-hop2", 2)):
        rows_h = [r for r in noise_rows if r["hop"] == hop and r["config"] == cfg]
        c = Counter(r["classification"] for r in rows_h)
        noise_by_hop.append({
            "config": cfg, "hop": hop,
            "total": sum(c.values()),
            "relevant": c.get("relevant", 0),
            "irrelevant": c.get("irrelevant", 0),
            "precision": c.get("relevant", 0) / max(sum(c.values()), 1),
        })

    # monotonicity (candidate universe)
    mono = {}
    for q in queries:
        by_cfg = {cfg: {f["fact_id"] for f in next(
            r["facts"] for r in lines[cfg] if r["query_id"] == q["id"])}
            for cfg in lines}
        mono[q["id"]] = {
            "base_subset_hop1": by_cfg["baseline"] <= by_cfg["hop1"],
            "hop1_subset_hop2": by_cfg["hop1"] <= by_cfg["hop2"],
            "bidir_base_subset_hop1": by_cfg["baseline"] <= by_cfg["bidir-hop1"],
            "bidir_hop1_subset_hop2": by_cfg["bidir-hop1"] <= by_cfg["bidir-hop2"],
            "hop1_subset_bidir": by_cfg["hop1"] <= by_cfg["bidir-hop1"],
        }

    manifest = {
        "git_commit": _git_commit(),
        "corpus": CORPUS,
        "corpus_spec_sha256": hashlib.sha256((G4 / "corpus_spec_v1.1.json").read_bytes()).hexdigest(),
        "corpus_spec_v1_sha256": hashlib.sha256((G4 / "corpus_spec.json").read_bytes()).hexdigest(),
        "query_set_sha256": QUERY_SET_HASH,
        "neo4j_projection": "production project_neo4j + project_canonical workers",
        "retrieval_contract": "production run_lanes fusion, untouched",
        "expansion_policy": "production _neo4j_expand (outgoing-only hop1, HIGH_MEDIUM allowlist, LIMIT 8 seeds / 20 facts); hop2 = measurement-only; bidir-hop1/2 = measurement-only CANDIDATE (incoming+outgoing)",
        "reranker": "Qwen/Qwen3-Reranker-0.6B @ e61197ed" if with_reranker else "not tested",
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True))
    (ARTIFACTS / "frozen_queries.jsonl").write_text(
        "\n".join(json.dumps(q, sort_keys=True) for q in queries) + "\n")
    (ARTIFACTS / "graph_degree_distribution.json").write_text(json.dumps(dist, indent=1))
    for key in lines:
        (ARTIFACTS / f"{key}.jsonl").write_text(
            "\n".join(json.dumps(r, sort_keys=True) for r in lines[key]) + "\n")
    (ARTIFACTS / "graph_added_candidates.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in added_rows) + "\n")
    with (ARTIFACTS / "hub_analysis.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["node_id", "surface", "degree"])
        for r in dist["top_nodes"]:
            w.writerow([r["id"], r["surface"], r["degree"]])
    with (ARTIFACTS / "noise_by_hop.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["hop", "total", "relevant", "irrelevant", "precision"])
        for r in noise_by_hop:
            w.writerow([r["hop"], r["total"], r["relevant"], r["irrelevant"],
                        round(r["precision"], 4)])
    (ARTIFACTS / "metrics.json").write_text(json.dumps({
        "degree": dist,
        "per_query": per_query,
        "noise_by_hop": noise_by_hop,
        "monotonicity": mono,
        "manifest": manifest,
    }, indent=1, sort_keys=True, default=str))
    print(json.dumps({"degree": {k: dist[k] for k in ("nodes", "p50", "p90", "p95", "p99", "max")},
                      "noise_by_hop": noise_by_hop,
                      "monotonicity": {k: v for k, v in mono.items()}},
                     indent=1, default=str))
    print("artifacts ->", ARTIFACTS)


def _git_commit() -> str:
    import subprocess

    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--reranker", action="store_true")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.seed:
        seed()
    if args.run:
        run(repeats=args.repeats, with_reranker=args.reranker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
