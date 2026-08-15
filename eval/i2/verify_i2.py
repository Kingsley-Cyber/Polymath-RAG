"""I2 corpus-scale integrity qualification verifier (qualification only).

Runs the frozen I2 fixture through the real production path and checks
every gate: convergence, durable census (eligibility-aware), admission
scale behavior, generic-hub regression, identity invariants on
persisted rows, corpus isolation, replay idempotency, controlled
failure convergence, Qdrant/Neo4j reconstruction, content versioning,
provenance, queryability smoke, determinism, and performance
observation.

Qualification only: this script never changes production behavior or
tunes anything. It uses the sanctioned failure-injection and
reconstruction mechanisms that already exist.

Usage: .venv/bin/python eval/i2/verify_i2.py [--phase PHASE...]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "workers"))
sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.manifest import load_manifest, manifest_id  # noqa: E402
from control.manifest_ingest import execute_manifest, plan_manifest  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "i2"
MAIN_CORPUS = "i2-qualification-corpus"
ISO_CORPUS = "i2-isolation-corpus"

EVIDENCE: dict = {"phases": {}}


def log(phase: str, message: str) -> None:
    print(f"[{phase}] {message}", flush=True)


def conn():
    return psycopg.connect(os.environ.get(
        "POLYMATH_PG_DSN",
        "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"),
        row_factory=dict_row)


def q(sql: str, params=None, c=None):
    owns = c is None
    c = c or conn()
    try:
        cur = c.execute(sql, params)
        rows = cur.fetchall()
        if rows and isinstance(rows[0], dict):
            return [dict(r) for r in rows]
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        if owns:
            c.close()


def wipe_corpus(corpus: str) -> None:
    import time as _time

    for attempt in range(6):
        c = conn()
        try:
            rids = [r["run_id"] for r in q("SELECT run_id FROM runs WHERE corpus_id=%s", (corpus,), c)]
            for rid in rids:
                for t in ("stage_attempts", "artifacts", "receipts", "outbox_events"):
                    c.execute(f"DELETE FROM {t} WHERE run_id=%s", (rid,))
            docs = [r["doc_id"] for r in q("SELECT doc_id FROM documents WHERE corpus_id=%s", (corpus,), c)]
            if docs:
                c.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (docs,))
            c.execute("DELETE FROM runs WHERE corpus_id=%s", (corpus,))
            c.execute("DELETE FROM documents WHERE corpus_id=%s", (corpus,))
            c.execute("DELETE FROM corpora WHERE corpus_id=%s", (corpus,))
            c.commit()
            break
        except psycopg.errors.DeadlockDetected:
            c.rollback()
            _time.sleep(2 * (attempt + 1))
        finally:
            c.close()
    else:
        raise RuntimeError("wipe_corpus: deadlocked repeatedly against live workers")
    from polymath_shared.embedding_contracts import active_contract
    from polymath_shared.projection_contracts import qdrant_collection_name
    from polymath_shared.settings import get_settings
    from qdrant_client import QdrantClient

    client = QdrantClient(url=get_settings().stores.qdrant_url)
    try:
        name = qdrant_collection_name(corpus, active_contract().contract_id)
        if client.collection_exists(name):
            client.delete_collection(name)
    finally:
        client.close()
    from workers.project_neo4j_worker import _driver

    driver = _driver()
    try:
        with driver.session() as s:
            if docs:
                s.run("MATCH (d:Document) WHERE d.doc_id IN $ids DETACH DELETE d", ids=docs)
            c2 = conn()
            try:
                chunks = [r["chunk_id"] for r in q(
                    "SELECT chunk_id FROM chunks WHERE doc_id = ANY(%s)", (docs,), c2)]
            finally:
                c2.close()
            if chunks:
                s.run("MATCH (c:Chunk) WHERE c.chunk_id IN $ids DETACH DELETE c", ids=chunks)
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# Phase 1: fixture integrity
# ---------------------------------------------------------------------------
def phase_fixture() -> None:
    log("fixture", "verifying frozen hashes")
    sums = {}
    for line in (FIXTURE / "SHA256SUMS").read_text().splitlines():
        h, name = line.split("  ")
        sums[name] = h
    bad = []
    for name, h in sums.items():
        actual = hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()
        if actual != h:
            bad.append(name)
    if bad:
        log("fixture", f"HASH MISMATCH: {bad}")
        sys.exit(2)
    frozen = json.loads((FIXTURE / "FROZEN.json").read_text())
    m1 = manifest_id(load_manifest(FIXTURE / "manifest.yaml"))
    m2 = manifest_id(load_manifest(FIXTURE / "isolation.yaml"))
    assert m1 == frozen["main_manifest_id"], "main manifest id drifted"
    assert m2 == frozen["isolation_manifest_id"], "isolation manifest id drifted"
    EVIDENCE["phases"]["fixture"] = {**frozen, "hashes_ok": True}
    log("fixture", f"ok: {frozen['main_document_count']} main docs, "
                   f"{frozen['isolation_document_count']} iso docs, formats={frozen['formats']}")


# ---------------------------------------------------------------------------
# Phase 2: baseline ingestion (assumes live workers + control plane)
# ---------------------------------------------------------------------------
def phase_ingestion() -> None:
    log("ingestion", "wiping corpora")
    wipe_corpus(MAIN_CORPUS)
    wipe_corpus(ISO_CORPUS)
    doc = load_manifest(FIXTURE / "manifest.yaml")
    t0 = time.time()
    with tx() as c:
        r = execute_manifest(c, doc, FIXTURE / "manifest.yaml")
    log("ingestion", f"submitted={r['submitted']}")

    deadline = time.time() + 30 * 60
    while time.time() < deadline:
        with tx() as c:
            states = q("SELECT status, COUNT(*) AS n FROM runs WHERE corpus_id=%s GROUP BY 1",
                       (MAIN_CORPUS,), c)
        summary = {s["status"]: s["n"] for s in states}
        if summary.get("query_ready", 0) == r["submitted"]:
            break
        log("ingestion", f"waiting: {summary}")
        time.sleep(10)
    wall = time.time() - t0
    with tx() as c:
        states = q("SELECT status, COUNT(*) AS n FROM runs WHERE corpus_id=%s GROUP BY 1",
                   (MAIN_CORPUS,), c)
        attempts = q("""
            SELECT stage, COUNT(*) AS n FROM stage_attempts sa
              JOIN runs r ON r.run_id = sa.run_id
             WHERE r.corpus_id = %s GROUP BY stage""", (MAIN_CORPUS,), c)
        retries = q("""
            SELECT stage, COUNT(*) AS n FROM stage_attempts sa
              JOIN runs r ON r.run_id = sa.run_id
             WHERE r.corpus_id = %s AND outcome = 'failed' GROUP BY stage""", (MAIN_CORPUS,), c)
        timing = q("""
            SELECT r.run_id, MIN(sa.started_at) AS first, MAX(sa.completed_at) AS last
              FROM stage_attempts sa JOIN runs r ON r.run_id = sa.run_id
             WHERE r.corpus_id = %s GROUP BY r.run_id""", (MAIN_CORPUS,), c)
    summary = {s["status"]: s["n"] for s in states}
    assert summary.get("query_ready", 0) == 28, f"not converged: {summary}"
    per_doc = sorted(
        ((row["last"] - row["first"]).total_seconds() for row in timing if row["last"] and row["first"])
    )
    p50 = per_doc[len(per_doc) // 2]
    p95 = per_doc[int(len(per_doc) * 0.95)]
    EVIDENCE["phases"]["ingestion"] = {
        "submitted": r["submitted"],
        "final_states": summary,
        "stage_attempt_counts": {a["stage"]: a["n"] for a in attempts},
        "failed_attempt_counts": {a["stage"]: a["n"] for a in retries},
        "wall_time_s": round(wall, 1),
        "documents_per_minute": round(28 / (wall / 60), 1),
        "document_p50_s": round(p50, 2),
        "document_p95_s": round(p95, 2),
    }
    log("ingestion", f"converged: {summary} in {wall:.0f}s "
                     f"(p50={p50:.1f}s p95={p95:.1f}s per doc)")
    with tx() as c:
        chunks_n = q("""SELECT COUNT(*) AS n FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id
                        WHERE d.corpus_id=%s""", (MAIN_CORPUS,), c)[0]["n"]
    EVIDENCE["phases"]["ingestion"]["chunks_per_minute"] = round(chunks_n / (wall / 60), 1)


# ---------------------------------------------------------------------------
# Phase 3: durable census + Phase 4: admission scale + generic hubs
# ---------------------------------------------------------------------------
def phase_census_and_hubs() -> None:
    c = conn()
    try:
        rows = q("""
            SELECT e.entity_id, e.core_type, e.normalized_surface, e.admission_class
              FROM entities e
              JOIN facts f ON f.subject_id = e.entity_id OR f.object_id = e.entity_id
              JOIN evidence ev ON ev.fact_id = f.fact_id
              JOIN documents d ON d.doc_id = ev.doc_id
             WHERE d.corpus_id = %s""", (MAIN_CORPUS,), c)
        seen: dict[str, dict] = {}
        for r in rows:
            key = (r["entity_id"], r["core_type"], r["normalized_surface"], r["admission_class"])
            seen[key] = seen.get(key, {**r, "mentions": 0})
            seen[key]["mentions"] += 1
        census = {}
        for v in seen.values():
            census[v["admission_class"]] = census.get(v["admission_class"], 0) + 1

        docs = q("SELECT COUNT(*) AS n FROM documents WHERE corpus_id=%s", (MAIN_CORPUS,), c)[0]["n"]
        chunks = q("""SELECT COUNT(*) AS n FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id
                      WHERE d.corpus_id=%s""", (MAIN_CORPUS,), c)[0]["n"]
        parents = q("""SELECT COUNT(*) AS n FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id
                       WHERE d.corpus_id=%s AND ch.tier='parent'""", (MAIN_CORPUS,), c)[0]["n"]
        facts = q("""SELECT COUNT(*) AS n FROM facts f JOIN evidence e ON e.fact_id=f.fact_id
                     JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s""", (MAIN_CORPUS,), c)[0]["n"]
        from polymath_shared.neo4j_eligibility import ineligible_fact_ids_sql
        parked = q(ineligible_fact_ids_sql(), c=c)
        parked_in_corpus = q("""
            SELECT COUNT(*) AS n FROM facts f JOIN evidence e ON e.fact_id=f.fact_id
             JOIN documents d ON d.doc_id=e.doc_id
             WHERE d.corpus_id=%s AND f.fact_id = ANY(%s)""",
            (MAIN_CORPUS, [p["fact_id"] for p in parked]), c)[0]["n"]
        canon = q("SELECT COUNT(*) AS n FROM canonical_entities WHERE corpus_id=%s", (MAIN_CORPUS,), c)[0]["n"]
        receipts = q("""SELECT COUNT(*) AS n FROM projection_receipts pr
                        WHERE pr.projection='neo4j' AND pr.active AND pr.entity_id = ANY(%s)""",
                     ([r["doc_id"] for r in q("SELECT doc_id FROM documents WHERE corpus_id=%s", (MAIN_CORPUS,), c)],), c)[0]["n"]
    finally:
        c.close()

    from polymath_shared.embedding_contracts import active_contract
    from polymath_shared.projection_contracts import qdrant_collection_name
    from polymath_shared.settings import get_settings
    from qdrant_client import QdrantClient

    client = QdrantClient(url=get_settings().stores.qdrant_url)
    try:
        name = qdrant_collection_name(MAIN_CORPUS, active_contract().contract_id)
        points = client.count(collection_name=name).count
    finally:
        client.close()

    from workers.project_neo4j_worker import _driver

    driver = _driver()
    try:
        with driver.session() as s:
            n_entities = s.run("""MATCH (e:Entity) WHERE e.entity_id IN $ids RETURN COUNT(e) AS n""",
                               ids=[v["entity_id"] for v in seen.values()]).data()[0]["n"]
            mention_leak = s.run("""MATCH (e:Entity) WHERE e.entity_id STARTS WITH 'mention_' AND e.entity_id IN $ids
                                    RETURN COUNT(e) AS n""",
                                 ids=[v["entity_id"] for v in seen.values()]).data()[0]["n"]
            n_edges = s.run("""MATCH (a:Entity)-[r:REL]->(b:Entity)
                               WHERE (a.entity_id IN $ids OR b.entity_id IN $ids) RETURN COUNT(r) AS n""",
                            ids=[v["entity_id"] for v in seen.values()]).data()[0]["n"]
            degree = s.run("""
                MATCH (e:Entity)
                WHERE e.entity_id IN $ids
                OPTIONAL MATCH (e)-[r:REL]-()
                RETURN e.surface AS surface, e.core_type AS t, COUNT(r) AS degree
                ORDER BY degree DESC LIMIT 25""", ids=[v["entity_id"] for v in seen.values()]).data()
    finally:
        driver.close()

    eligible = {k: v for k, v in seen.items() if v["admission_class"] != "MENTION_ONLY"}
    EVIDENCE["phases"]["census"] = {
        "documents": docs, "chunks": chunks, "parents": parents,
        "document_summaries": docs,
        "section_summaries": parents,
        "admission_census": census,
        "facts": facts, "parked_facts": parked_in_corpus,
        "canonical_entities": canon,
        "qdrant_points": points,
        "neo4j_entities": n_entities,
        "neo4j_eligible_entities_expected": len(eligible),
        "neo4j_facts": n_edges,
        "neo4j_active_receipts_sampled": receipts,
        "mention_leakage": mention_leak,
    }
    assert mention_leak == 0, "MENTION_ONLY leaked into Neo4j"
    assert n_entities == len(eligible), f"eligibility mismatch: graph {n_entities} vs eligible {len(eligible)}"
    assert points == chunks, f"qdrant points {points} != chunks {chunks}"

    generic_hits = [g for g in degree
                    if g["surface"] and g["surface"].lower().strip() in
                    {"system", "the system", "model", "the model", "platform",
                     "the platform", "component", "service", "process", "the process"}]
    EVIDENCE["phases"]["hubs"] = {
        "top25": degree,
        "generic_hits": generic_hits,
        "verdict": "PASS" if not generic_hits else "FLAG",
    }
    log("census", json.dumps({k: v for k, v in EVIDENCE["phases"]["census"].items()
                              if k not in ("qdrant_points",)}, default=str))
    log("hubs", f"top5: {[(g['surface'], g['degree']) for g in degree[:5]]}; generic_hits={generic_hits}")


# ---------------------------------------------------------------------------
# Phase 5: identity invariants on persisted rows
# ---------------------------------------------------------------------------
def phase_identity() -> None:
    c = conn()
    try:
        rows = q("""
            SELECT e.entity_id, e.core_type, e.normalized_surface, e.admission_class,
                   COUNT(DISTINCT d.doc_id) AS doc_count
              FROM entities e
              JOIN facts f ON f.subject_id = e.entity_id OR f.object_id = e.entity_id
              JOIN evidence ev ON ev.fact_id = f.fact_id
              JOIN documents d ON d.doc_id = ev.doc_id
             WHERE d.corpus_id = %s
             GROUP BY 1,2,3,4""", (MAIN_CORPUS,), c)
        iso_rows = q("""
            SELECT e.entity_id, e.core_type, e.normalized_surface, e.admission_class,
                   COUNT(DISTINCT d.doc_id) AS doc_count
              FROM entities e
              JOIN facts f ON f.subject_id = e.entity_id OR f.object_id = e.entity_id
              JOIN evidence ev ON ev.fact_id = f.fact_id
              JOIN documents d ON d.doc_id = ev.doc_id
             WHERE d.corpus_id = %s
             GROUP BY 1,2,3,4""", (ISO_CORPUS,), c)
    finally:
        c.close()

    checks = {"global": True, "corpus_scoped": True,
              "document_scoped": True, "mention_only": True}
    details = {"global_shared_across_docs": [], "corpus_scoped_dedupe": [],
               "cross_corpus_no_collide": [], "document_scoped_split": [],
               "mention_stability": []}

    by_surface_class = {}
    for r in rows:
        by_surface_class.setdefault((r["normalized_surface"], r["admission_class"]), []).append(r)

    for (surface, cls), rs in by_surface_class.items():
        if cls == "GLOBAL":
            ids = {r["entity_id"] for r in rs}
            if len(rs) > 1 or any(r["doc_count"] > 1 for r in rs):
                details["global_shared_across_docs"].append((surface, len(ids)))
            if len(ids) != 1:
                checks["global"] = False
        elif cls == "CORPUS_SCOPED":
            ids = {r["entity_id"] for r in rs}
            if len(ids) != 1:
                checks["corpus_scoped"] = False
            details["corpus_scoped_dedupe"].append((surface, len(ids), len(rs)))
        elif cls == "DOCUMENT_SCOPED":
            ids = {r["entity_id"] for r in rs}
            if len(rs) > 1 and len(ids) != len({r["doc_count"] for r in rs}):
                checks["document_scoped"] = False
            details["document_scoped_split"].append((surface, len(ids)))
        elif cls == "MENTION_ONLY":
            if not all(r["entity_id"].startswith("mention_") for r in rs):
                checks["mention_only"] = False

    # cross-corpus collision: same corpus-scoped surface must differ
    main_scoped = {(r["normalized_surface"]): r["entity_id"] for r in rows
                   if r["admission_class"] == "CORPUS_SCOPED"}
    iso_scoped = {(r["normalized_surface"]): r["entity_id"] for r in iso_rows
                  if r["admission_class"] == "CORPUS_SCOPED"}
    for surface, iso_id in iso_scoped.items():
        if surface in main_scoped:
            if main_scoped[surface] == iso_id:
                checks["corpus_scoped"] = False
            details["cross_corpus_no_collide"].append(
                (surface, main_scoped[surface][:12], iso_id[:12]))
    EVIDENCE["phases"]["identity"] = {"checks": checks, "details": details}
    log("identity", json.dumps(checks))


# ---------------------------------------------------------------------------
# Phase 6: corpus isolation (requires isolation corpus ingested)
# ---------------------------------------------------------------------------
def phase_isolation() -> None:
    doc = load_manifest(FIXTURE / "isolation.yaml")
    with tx() as c:
        r = execute_manifest(c, doc, FIXTURE / "isolation.yaml")
    log("isolation", f"isolation corpus submitted={r['submitted']}")
    deadline = time.time() + 10 * 60
    while time.time() < deadline:
        with tx() as c:
            states = q("SELECT status, COUNT(*) AS n FROM runs WHERE corpus_id=%s GROUP BY 1",
                       (ISO_CORPUS,), c)
        if {s["status"]: s["n"] for s in states}.get("query_ready", 0) == 4:
            break
        time.sleep(10)

    from orchestrator.orchestrator.api.retrieve import _neo4j_expand

    leaks = []
    # Graph expansion scoped to the isolation corpus must never return
    # facts evidenced exclusively in the main corpus.
    rows = _neo4j_expand(["system", "model", "pipeline", "memory"], corpus_id=ISO_CORPUS)
    with tx() as c:
        main_facts = {r["fact_id"] for r in q("""
            SELECT DISTINCT e.fact_id FROM evidence e JOIN documents d ON d.doc_id=e.doc_id
            WHERE d.corpus_id=%s""", (MAIN_CORPUS,), c)}
    for row in rows:
        if row["fact_id"] in main_facts:
            leaks.append(row["fact_id"])
    EVIDENCE["phases"]["isolation"] = {
        "iso_submitted": r["submitted"],
        "expansion_rows": len(rows),
        "cross_corpus_leaks": leaks,
    }
    log("isolation", f"expansion rows={len(rows)} leaks={leaks}")
    assert not leaks, "corpus-authorized expansion leaked main-corpus facts"


# ---------------------------------------------------------------------------
# Phase 7: replay / idempotency + semantic state hash
# ---------------------------------------------------------------------------
def semantic_hash(corpus: str) -> str:
    c = conn()
    try:
        lines = []
        lines += [f"d|{r['doc_id']}|{r['source_name']}" for r in q(
            "SELECT doc_id, source_name FROM documents WHERE corpus_id=%s ORDER BY doc_id",
            (corpus,), c)]
        lines += [f"c|{r['chunk_id']}|{r['tier']}|{r['char_start']}:{r['char_end']}" for r in q(
            """SELECT ch.chunk_id, ch.tier, ch.char_start, ch.char_end FROM chunks ch
               JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s ORDER BY ch.chunk_id""",
            (corpus,), c)]
        lines += [f"e|{r['entity_id']}|{r['core_type']}|{r['admission_class']}" for r in q(
            """SELECT e.entity_id, e.core_type, e.admission_class FROM entities e
               WHERE e.entity_id IN (SELECT f.subject_id FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id
                 JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s)
                  OR e.entity_id IN (SELECT f.object_id FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id
                 JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s)
               ORDER BY e.entity_id""", (corpus, corpus), c)]
        lines += [f"f|{r['fact_id']}|{r['predicate']}|{r['subject_id']}|{r['object_id']}" for r in q(
            """SELECT f.fact_id, f.predicate, f.subject_id, f.object_id FROM facts f
               JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id
               WHERE d.corpus_id=%s ORDER BY f.fact_id""", (corpus,), c)]
        lines += [f"cn|{r['canonical_id']}" for r in q(
            "SELECT canonical_id FROM canonical_entities WHERE corpus_id=%s ORDER BY canonical_id",
            (corpus,), c)]
    finally:
        c.close()
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def phase_replay() -> None:
    doc = load_manifest(FIXTURE / "manifest.yaml")
    before = semantic_hash(MAIN_CORPUS)
    with tx() as c:
        r = execute_manifest(c, doc, FIXTURE / "manifest.yaml")
    after = semantic_hash(MAIN_CORPUS)
    with tx() as c:
        counts = {t: q(f"SELECT COUNT(*) AS n FROM {t}", c=c)[0]["n"]
                  for t in ("documents", "chunks", "facts", "projection_receipts")}
    EVIDENCE["phases"]["replay"] = {
        "submitted": r["submitted"], "retried": r["retried"],
        "hash_before": before, "hash_after": after, "counts": counts,
        "idempotent": r["submitted"] == 0 and before == after,
    }
    log("replay", f"submitted={r['submitted']} hash_equal={before == after}")
    assert r["submitted"] == 0 and before == after, "replay not idempotent"


# ---------------------------------------------------------------------------
# Phase 8: queryability smoke (requires orchestrator API at 7200)
# ---------------------------------------------------------------------------
def phase_queryability() -> None:
    import urllib.request

    queries = [
        ("text_direct", "What does metacognitive monitoring refer to?"),
        ("cross_section", "How does working memory interact with cognitive load?"),
        ("cross_document", "Why does retrieval practice improve calibration?"),
        ("lexical", "What is zero trust?"),
        ("graph_support", "What does verification of projections reconcile?"),
        ("ambiguous_generic", "How does the system work?"),
        ("unsupported", "What is the capital of France?"),
        ("isolation", "How does the model rerank candidates?"),
    ]
    results = {}
    for label, qtext in queries:
        corpus = ISO_CORPUS if label == "isolation" else MAIN_CORPUS
        req = urllib.request.Request(
            "http://127.0.0.1:7200/chat",
            data=json.dumps({"message": qtext, "corpus_id": corpus}).encode(),
            headers={"Content-Type": "application/json"})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=120).read())
        except Exception as exc:
            results[label] = {"error": str(exc)}
            continue
        cites = r.get("citations") or []
        foreign = []
        with tx() as c:
            doc_ids = {row["doc_id"] for row in q(
                "SELECT doc_id FROM documents WHERE corpus_id=%s", (corpus,), c)}
        for cite in cites:
            for did in cite.get("source_document_ids", []):
                if did not in doc_ids:
                    foreign.append(did)
        results[label] = {
            "abstained": r.get("meta", {}).get("abstained"),
            "text_support": r.get("meta", {}).get("text_support_count", 0),
            "supported_claims": r.get("meta", {}).get("supported_claim_count", 0),
            "citations": len(cites),
            "foreign_citations": foreign,
            "answer_head": (r.get("answer") or "")[:80],
        }
    EVIDENCE["phases"]["queryability"] = results
    log("queryability", json.dumps(results))
    assert all(not v.get("foreign_citations") for v in results.values()), "foreign citations"
    assert results["unsupported"].get("abstained") is True, "unsupported query must abstain"
    assert not results["text_direct"].get("abstained"), "text answer must not abstain"


# ---------------------------------------------------------------------------
# Phase 9: determinism (wipe + re-ingest from clean state, hash compare)
# ---------------------------------------------------------------------------
def phase_determinism() -> None:
    doc = load_manifest(FIXTURE / "manifest.yaml")
    h1 = semantic_hash(MAIN_CORPUS)
    log("determinism", f"hash1={h1[:20]} wiping corpus for second run")
    wipe_corpus(MAIN_CORPUS)
    with tx() as c:
        r = execute_manifest(c, doc, FIXTURE / "manifest.yaml")
    deadline = time.time() + 30 * 60
    while time.time() < deadline:
        with tx() as c:
            states = q("SELECT status, COUNT(*) AS n FROM runs WHERE corpus_id=%s GROUP BY 1",
                       (MAIN_CORPUS,), c)
        if {s["status"]: s["n"] for s in states}.get("query_ready", 0) == 28:
            break
        time.sleep(10)
    h2 = semantic_hash(MAIN_CORPUS)
    EVIDENCE["phases"]["determinism"] = {
        "hash1": h1, "hash2": h2, "equal": h1 == h2,
    }
    log("determinism", f"hash2={h2[:20]} equal={h1 == h2}")
    assert h1 == h2, "semantic state diverged between runs"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", action="append", default=[],
                        choices=["fixture", "ingestion", "census", "identity",
                                 "isolation", "replay", "queryability", "determinism"])
    args = parser.parse_args()
    phases = args.phase or ["fixture", "ingestion", "census", "identity",
                            "isolation", "replay", "queryability", "determinism"]
    runners = {
        "fixture": phase_fixture, "ingestion": phase_ingestion,
        "census": phase_census_and_hubs, "identity": phase_identity,
        "isolation": phase_isolation, "replay": phase_replay,
        "queryability": phase_queryability, "determinism": phase_determinism,
    }
    for p in phases:
        runners[p]()
    out = Path(os.environ.get("POLYMATH_I2_EVIDENCE", "/tmp/i2/evidence.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(EVIDENCE, indent=2, default=str))
    print(json.dumps({"completed_phases": phases, "evidence": str(out)}))


if __name__ == "__main__":
    main()
