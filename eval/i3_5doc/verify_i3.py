"""I3 — five-document E2E ingestion/extraction acceptance verifier.

Runs the frozen I3 corpus through the REAL production path (manifest ->
control plane -> workers -> stores) and measures every gate in the I3
plan: control-plane chain, entity/fact accuracy vs frozen gold,
negative controls, generic-hygiene, provenance, Qdrant/Neo4j parity,
replay, order independence, concurrency, interrupt/resume, store
reconstruction, versioning, retrieval smoke (FAST/HYBRID/GRAPH), and
corpus isolation.

Qualification only: this script never changes production behavior and
never repairs failures.

Usage: .venv/bin/python eval/i3_5doc/verify_i3.py [--phase PHASE...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "workers"))
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.manifest import load_manifest, manifest_id, resolve_sources  # noqa: E402
from polymath_shared.intake_submission import canonical_intake_payload, submit_intake  # noqa: E402
from control.manifest_ingest import execute_manifest, plan_manifest  # noqa: E402
from polymath_shared.embedding_contracts import active_contract  # noqa: E402
from polymath_shared.projection_contracts import qdrant_collection_name  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402

FIXTURE = ROOT / "eval" / "i3_5doc"
CORPUS = "i3-five-doc-v1"
DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
ORCHESTRATOR = "http://127.0.0.1:7200"

EVIDENCE: dict = {"phases": {}}
LOG_PATH = FIXTURE / "evidence" / "verify_i3.log"


def log(phase: str, message: str) -> None:
    line = f"[{phase}] {message}"
    print(line, flush=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def conn():
    return psycopg.connect(DSN, row_factory=dict_row)


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


def wait_convergence(corpus: str, target: int, deadline_s: int = 1800) -> dict:
    deadline = time.time() + deadline_s
    while time.time() < deadline:
        with tx() as c:
            states = {s["status"]: s["n"] for s in q(
                "SELECT status, COUNT(*) AS n FROM runs WHERE corpus_id=%s GROUP BY 1",
                (corpus,), c)}
        if states.get("query_ready", 0) == target and not states.get("retrying", 0):
            return states
        log("wait", f"{corpus}: {states}")
        time.sleep(10)
    raise TimeoutError(f"{corpus} did not converge: {states}")


def wipe_corpus(corpus: str) -> None:
    import time as _time
    from qdrant_client import QdrantClient
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
        raise RuntimeError("wipe_corpus: deadlocked against live workers")
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


def semantic_hash(corpus: str) -> str:
    c = conn()
    try:
        lines = []
        lines += [f"d|{r['doc_id']}|{r['source_name']}|{r['content_hash']}" for r in q(
            "SELECT doc_id, source_name, content_hash FROM documents WHERE corpus_id=%s ORDER BY doc_id",
            (corpus,), c)]
        lines += [f"c|{r['chunk_id']}|{r['tier']}|{r['char_start']}:{r['char_end']}|{r['chunk_index']}" for r in q(
            """SELECT ch.chunk_id, ch.tier, ch.char_start, ch.char_end, ch.chunk_index FROM chunks ch
               JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s ORDER BY ch.chunk_id""",
            (corpus,), c)]
        lines += [f"e|{r['entity_id']}|{r['core_type']}|{r['admission_class']}|{r['normalized_surface']}" for r in q(
            """SELECT e.entity_id, e.core_type, e.admission_class, e.normalized_surface FROM entities e
               JOIN documents d ON d.doc_id=e.first_seen_doc WHERE d.corpus_id=%s ORDER BY e.entity_id""",
            (corpus,), c)]
        lines += [f"f|{r['fact_id']}|{r['predicate']}|{r['subject_id']}|{r['object_id']}|{r['decision']}" for r in q(
            """SELECT f.fact_id, f.predicate, f.subject_id, f.object_id, f.decision FROM facts f
               JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id
               WHERE d.corpus_id=%s ORDER BY f.fact_id""", (corpus,), c)]
        lines += [f"cn|{r['canonical_id']}|{r['canonical_type']}" for r in q(
            "SELECT canonical_id, canonical_type FROM canonical_entities WHERE corpus_id=%s ORDER BY canonical_id",
            (corpus,), c)]
        lines += [f"rs|{r['summary_id']}|{r['kind']}|{r['summary_text']}" for r in q(
            "SELECT summary_id, kind, summary_text FROM retrieval_summaries WHERE corpus_id=%s ORDER BY summary_id",
            (corpus,), c)]
    finally:
        c.close()
    from qdrant_client import QdrantClient
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=120)
    try:
        name = qdrant_collection_name(corpus, active_contract().contract_id)
        points = []
        if client.collection_exists(name):
            off = None
            while True:
                batch, off = client.scroll(collection_name=name, limit=256, offset=off, with_payload=True)
                for p in batch:
                    pl = p.payload or {}
                    points.append(f"pt|{p.id}|{pl.get('representation_kind')}|{pl.get('chunk_id') or pl.get('summary_id')}")
                if off is None:
                    break
        lines += sorted(points)
    finally:
        client.close()
    from workers.project_neo4j_worker import _driver
    driver = _driver()
    try:
        with driver.session() as s:
            for rec in s.run("MATCH (n) WHERE n.corpus_id=$cid RETURN n.doc_id, n.tier, n.chunk_index, n.fact_id ORDER BY n.doc_id, n.tier, n.chunk_index, n.fact_id", cid=corpus):
                lines.append(f"g|{rec.values()}")
            for rec in s.run("MATCH ()-[r]->() WHERE r.corpus_id=$cid RETURN type(r), r.fact_id ORDER BY type(r), r.fact_id", cid=corpus):
                lines.append(f"gr|{rec.values()}")
    finally:
        driver.close()
    return hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()


def submit_manifest(path: Path) -> dict:
    doc = load_manifest(path)
    with tx() as c:
        return execute_manifest(c, doc, path)


# ---------------------------------------------------------------------------
# Phase 0: freeze check
# ---------------------------------------------------------------------------
def phase_freeze() -> None:
    log("freeze", "verifying corpus + gold hashes")
    sums = {}
    for line in (FIXTURE / "corpus" / "SHA256SUMS").read_text().splitlines():
        h, name = line.split("  ")
        sums[name] = h
    for name, h in sums.items():
        actual = hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()
        assert actual == h, f"corpus hash drift: {name}"
    gsums = {}
    for line in (FIXTURE / "gold" / "GOLD_SHA256SUMS").read_text().splitlines():
        h, name = line.split("  ")
        gsums[name] = h
    for name, h in gsums.items():
        actual = hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()
        assert actual == h, f"gold hash drift: {name}"
    manifest = load_manifest(FIXTURE / "manifest.yaml")
    mid = manifest_id(manifest)
    EVIDENCE["phases"]["freeze"] = {
        "corpus_hashes": sums,
        "gold_hashes": gsums,
        "manifest_id": mid,
        "manifest_sha256": hashlib.sha256((FIXTURE / "manifest.yaml").read_bytes()).hexdigest(),
        "documents": len(sums),
    }
    log("freeze", f"ok: 5 docs, manifest {mid[:20]}")

    # contract hashes
    contracts = {}
    for rel in ["shared/polymath_shared/rulepack/core-predicates-v1.1.0.yaml",
                "shared/polymath_shared/entity_admission.py",
                "shared/polymath_shared/endpoint_binding.py",
                "shared/polymath_shared/neo4j_eligibility.py",
                "shared/polymath_shared/retrieval_summaries.py",
                "shared/polymath_shared/rulepack/compiler.py",
                "shared/polymath_shared/rulepack/negation.py",
                "workers/workers/profile_router.py",
                "workers/workers/document_profile_builder.py",
                "shared/polymath_shared/manifest.py",
                "shared/polymath_shared/pass1.py",
                "shared/polymath_shared/hybrid.py",
                "shared/polymath_shared/retrieval_modes.py"]:
        p = ROOT / rel
        contracts[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    from polymath_shared.rulepack import load_rule_pack
    rp = load_rule_pack()
    contracts["compiled_lexical_sha256"] = rp["compiled_lexical_sha256"]
    contracts["resource_contract_id"] = rp["resource_contract_id"]
    contracts["rule_pack_version"] = rp.get("pack", {}).get("version", "1.1.0")
    EVIDENCE["phases"]["freeze"]["contracts"] = contracts
    log("freeze", f"contracts hashed: {len(contracts)} entries")


# ---------------------------------------------------------------------------
# Phase 1: clean-state ingestion
# ---------------------------------------------------------------------------
def phase_ingestion() -> None:
    log("ingestion", f"wiping {CORPUS}")
    wipe_corpus(CORPUS)
    t0 = time.time()
    r = submit_manifest(FIXTURE / "manifest.yaml")
    log("ingestion", f"submitted={r['submitted']}")
    states = wait_convergence(CORPUS, 5)
    wall = time.time() - t0
    assert states.get("query_ready", 0) == 5, f"not converged: {states}"
    with tx() as c:
        runs = q("SELECT * FROM runs WHERE corpus_id=%s ORDER BY created_at", (CORPUS,), c)
        docs = q("SELECT doc_id, source_name, content_hash, byte_length FROM documents WHERE corpus_id=%s ORDER BY source_name", (CORPUS,), c)
        events = q("""SELECT e.event_id, e.event_type, e.run_id FROM outbox_events e
                      JOIN runs r ON r.run_id=e.run_id WHERE r.corpus_id=%s ORDER BY e.event_id""", (CORPUS,), c)
        artifacts = q("""SELECT a.artifact_id, a.stage, a.run_id FROM artifacts a
                         JOIN runs r ON r.run_id=a.run_id WHERE r.corpus_id=%s ORDER BY a.artifact_id""", (CORPUS,), c)
    EVIDENCE["phases"]["ingestion"] = {
        "submitted": r["submitted"],
        "terminal_states": states,
        "wall_time_s": round(wall, 1),
        "docs_per_min": round(5 / (wall / 60), 1),
        "runs": [{"run_id": x["run_id"], "status": x["status"], "created_at": str(x["created_at"])} for x in runs],
        "documents": docs,
        "outbox_events": [{"event_id": x["event_id"], "event_type": x["event_type"], "run_id": x["run_id"]} for x in events],
        "artifacts": [{"artifact_id": x["artifact_id"], "stage": x["stage"], "run_id": x["run_id"]} for x in artifacts],
    }
    log("ingestion", f"converged: {states} in {wall:.0f}s")


# ---------------------------------------------------------------------------
# Phase 2: control-plane stage-chain validation
# ---------------------------------------------------------------------------
EXPECTED_STAGES = ["intake", "extract", "profile_document", "project_qdrant",
                   "project_neo4j", "canonicalize", "project_canonical",
                   "verify_projections"]


def phase_control_chain() -> None:
    with tx() as c:
        attempts = q("""SELECT sa.run_id, sa.stage, sa.outcome, sa.started_at, sa.completed_at
                        FROM stage_attempts sa JOIN runs r ON r.run_id=sa.run_id
                        WHERE r.corpus_id=%s ORDER BY sa.run_id, sa.started_at, sa.stage""", (CORPUS,), c)
    per_run: dict[str, list[dict]] = {}
    for a in attempts:
        per_run.setdefault(a["run_id"], []).append(a)
    report = {}
    all_ok = True
    for run_id, seq in sorted(per_run.items()):
        stages = [a["stage"] for a in seq]
        ok = all(s in stages for s in EXPECTED_STAGES)
        duplicate = len(stages) != len(set(stages))
        outcomes = {a["stage"]: a["outcome"] for a in seq}
        query_ready = q("SELECT status FROM runs WHERE run_id=%s", (run_id,))[0]["status"]
        receipt_ok = True
        with tx() as c:
            rec = q("SELECT stage, status FROM receipts WHERE run_id=%s", (run_id,), c)
            if len(rec) < len(EXPECTED_STAGES):
                receipt_ok = False
        ok = ok and not duplicate and query_ready == "query_ready" and receipt_ok
        all_ok = all_ok and ok
        report[run_id[:12]] = {
            "stages": stages,
            "expected_present": all(s in stages for s in EXPECTED_STAGES),
            "duplicate_stage_attempts": duplicate,
            "outcomes": outcomes,
            "receipt_count": len(rec),
            "query_ready_only_after_full_chain": ok,
        }
    EVIDENCE["phases"]["control_chain"] = {"all_ok": all_ok, "per_run": report}
    log("control_chain", f"ok={all_ok} across {len(per_run)} runs")


# ---------------------------------------------------------------------------
# Phase 3: entity accuracy
# ---------------------------------------------------------------------------
def norm(s: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", t).strip().lower()


def phase_entities() -> None:
    gold = json.loads((FIXTURE / "gold" / "entity_gold.json").read_text())["documents"]
    with tx() as c:
        rows = q("""SELECT DISTINCT e.entity_id, e.core_type, e.normalized_surface, e.admission_class,
                           d.source_name
                      FROM entities e
                      JOIN facts f ON e.entity_id IN (f.subject_id, f.object_id)
                      JOIN evidence ev ON ev.fact_id=f.fact_id
                      JOIN documents d ON d.doc_id=ev.doc_id
                     WHERE d.corpus_id=%s ORDER BY d.source_name, e.normalized_surface""", (CORPUS,), c)
        canon = q("""SELECT ce.canonical_id, ce.canonical_type, ce.normalized_name AS normalized_surface,
                            cm.local_entity_id
                       FROM canonical_entities ce
                       LEFT JOIN canonical_memberships cm ON cm.canonical_id=ce.canonical_id
                      WHERE ce.corpus_id=%s ORDER BY ce.canonical_type""", (CORPUS,), c)
        gliner_span_count = q("""SELECT COUNT(*) AS n FROM artifacts a JOIN runs r ON r.run_id=a.run_id
                                 WHERE r.corpus_id=%s AND a.stage='extract'""", (CORPUS,), c)
    graph_surfaces = {norm(r["normalized_surface"]) for r in canon}
    per_doc = {}
    totals = {"tp": 0, "boundary": 0, "wrong_type": 0, "fp": 0, "fn": 0, "gold": 0,
              "ownership": {"DISCOVERY": 0, "BOUNDARY": 0, "TYPING": 0, "ADMISSION": 0,
                            "CANONICALIZATION": 0, "EPHEMERAL_NO_FACT": 0}}
    for doc_name, gd in gold.items():
        g_entities = gd["entities"]
        got = [r for r in rows if r["source_name"].endswith(doc_name)]
        got_norms = {norm(r["normalized_surface"]): r for r in got}
        tp = boundary = wrong_type = fn = 0
        fp = 0
        details = []
        for ge in g_entities:
            gn = norm(ge["surface"])
            hit = got_norms.get(gn) or next((r for n, r in got_norms.items()
                                             if gn in n or n in gn), None)
            if hit is None:
                fn += 1
                totals["ownership"]["DISCOVERY"] += 1
                details.append({"gold": ge["surface"], "result": "FN", "owner": "DISCOVERY"})
                continue
            labels = ge["label"] if isinstance(ge["label"], list) else [ge["label"]]
            if hit["core_type"] not in labels:
                wrong_type += 1
                totals["ownership"]["TYPING"] += 1
                details.append({"gold": ge["surface"], "result": "WRONG_TYPE",
                                "got_type": hit["core_type"], "allowed": labels})
                continue
            if hit["admission_class"] == "MENTION_ONLY" and ge["admission"] != "MENTION_ONLY":
                totals["ownership"]["ADMISSION"] += 1
                details.append({"gold": ge["surface"], "result": "ADMISSION_DOWNGRADED",
                                "got_class": hit["admission_class"], "expected": ge["admission"]})
            elif hit["normalized_surface"] != ge["surface"]:
                boundary += 1
                details.append({"gold": ge["surface"], "result": "BOUNDARY",
                                "got_surface": hit["normalized_surface"]})
            else:
                tp += 1
                details.append({"gold": ge["surface"], "result": "TP",
                                "type": hit["core_type"], "class": hit["admission_class"]})
        for gs in [ge["surface"] for ge in g_entities]:
            for n, r in got_norms.items():
                if r["normalized_surface"] == gs:
                    continue
                if norm(gs) == n:
                    continue
        gold_norms = {norm(ge["surface"]) for ge in g_entities}
        matched_extra = 0
        for n, r in got_norms.items():
            if n not in gold_norms:
                fp += 1
                details.append({"got": r["normalized_surface"], "type": r["core_type"],
                                "class": r["admission_class"], "result": "FP"})
        per_doc[doc_name] = {
            "tp": tp, "fp": fp, "fn": fn, "wrong_type": wrong_type,
            "boundary": boundary,
            "precision": round(tp / max(1, tp + fp + wrong_type), 3),
            "recall": round(tp / max(1, tp + fn), 3),
            "f1": round(2 * tp / max(1, 2 * tp + fp + fn + wrong_type), 3),
            "details": details,
        }
        totals["tp"] += tp
        totals["fp"] += fp
        totals["fn"] += fn
        totals["wrong_type"] += wrong_type
        totals["boundary"] += boundary
        totals["gold"] += len(g_entities)
    totals["precision"] = round(totals["tp"] / max(1, totals["tp"] + totals["fp"] + totals["wrong_type"]), 3)
    totals["recall"] = round(totals["tp"] / max(1, totals["tp"] + totals["fn"]), 3)
    totals["f1"] = round(2 * totals["tp"] / max(1, 2 * totals["tp"] + totals["fp"] + totals["fn"] + totals["wrong_type"]), 3)
    EVIDENCE["phases"]["entities"] = {
        "aggregate": totals,
        "per_document": per_doc,
        "durable_universe": {
            "note": "production persists entities ONLY as fact endpoints; GLiNER proposals without an accepted fact are ephemeral by design",
            "fact_endpoint_rows": len(rows),
            "canonical_entities": canon,
        },
    }
    log("entities", f"P={totals['precision']} R={totals['recall']} F1={totals['f1']} "
                    f"(tp={totals['tp']} fp={totals['fp']} fn={totals['fn']} wrong_type={totals['wrong_type']})")


# ---------------------------------------------------------------------------
# Phase 4: fact accuracy
# ---------------------------------------------------------------------------
def phase_facts() -> None:
    gold = json.loads((FIXTURE / "gold" / "fact_gold.json").read_text())["documents"]
    with tx() as c:
        rows = q("""SELECT f.fact_id, f.predicate, f.decision,
                           s.normalized_surface AS subj, s.core_type AS subj_type,
                           o.normalized_surface AS obj, o.core_type AS obj_type,
                           d.source_name, ev.span_offsets, f.qualifiers, f.provenance
                      FROM facts f
                      JOIN entities s ON s.entity_id=f.subject_id
                      JOIN entities o ON o.entity_id=f.object_id
                      JOIN evidence ev ON ev.fact_id=f.fact_id
                      JOIN documents d ON d.doc_id=ev.doc_id
                     WHERE d.corpus_id=%s ORDER BY d.source_name, f.predicate""", (CORPUS,), c)
    per_doc = {}
    agg = {"tp": 0, "fp": 0, "fn": 0, "wrong_pred": 0, "wrong_dir": 0,
           "ownership": {}}
    for doc_name, gd in gold.items():
        g_facts = gd["facts"]
        got = [r for r in rows if r["source_name"].endswith(doc_name)]
        tp = fn = 0
        fp = 0
        details = []
        matched = set()
        for gf in g_facts:
            hits = [r for i, r in enumerate(got)
                    if r["predicate"] == gf["predicate"]
                    and norm(r["subj"]) == norm(gf["subject"])
                    and norm(r["obj"]) == norm(gf["object"])]
            if hits:
                tp += 1
                matched.update(hits[0]["fact_id"])
                details.append({"gold": f"{gf['subject']} {gf['predicate']} {gf['object']}",
                                "result": "TP", "decision": hits[0]["decision"]})
            else:
                fn += 1
                # classify the miss
                subj_hit = any(norm(r["subj"]) == norm(gf["subject"]) for r in got)
                obj_hit = any(norm(r["obj"]) == norm(gf["object"]) for r in got)
                pred_hit = any(r["predicate"] == gf["predicate"] for r in got)
                if not subj_hit or not obj_hit:
                    owner = "NO_ENDPOINT"
                elif not pred_hit:
                    owner = "PREDICATE_TRIGGER"
                else:
                    owner = "OTHER"
                agg["ownership"][owner] = agg["ownership"].get(owner, 0) + 1
                details.append({"gold": f"{gf['subject']} {gf['predicate']} {gf['object']}",
                                "result": "FN", "owner": owner})
        for r in got:
            if r["fact_id"] in matched:
                continue
            is_gold = any(
                r["predicate"] == gf["predicate"]
                and norm(r["subj"]) == norm(gf["subject"])
                and norm(r["obj"]) == norm(gf["object"])
                for gf in g_facts)
            if not is_gold:
                fp += 1
                details.append({"got": f"{r['subj']} {r['predicate']} {r['obj']}",
                                "result": "FP", "decision": r["decision"],
                                "predicate": r["predicate"]})
        n = max(1, tp + fp)
        per_doc[doc_name] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(tp / n, 3),
            "recall": round(tp / max(1, tp + fn), 3),
            "f1": round(2 * tp / max(1, 2 * tp + fp + fn), 3),
            "details": details,
            "graph_facts_found": len(got),
        }
        agg["tp"] += tp
        agg["fp"] += fp
        agg["fn"] += fn
    agg["precision"] = round(agg["tp"] / max(1, agg["tp"] + agg["fp"]), 3)
    agg["recall"] = round(agg["tp"] / max(1, agg["tp"] + agg["fn"]), 3)
    agg["f1"] = round(2 * agg["tp"] / max(1, 2 * agg["tp"] + agg["fp"] + agg["fn"]), 3)
    EVIDENCE["phases"]["facts"] = {"aggregate": agg, "per_document": per_doc}
    log("facts", f"P={agg['precision']} R={agg['recall']} F1={agg['f1']} "
                 f"(tp={agg['tp']} fp={agg['fp']} fn={agg['fn']}) ownership={agg['ownership']}")


# ---------------------------------------------------------------------------
# Phase 5: negative controls
# ---------------------------------------------------------------------------
def phase_negatives() -> None:
    must_not = json.loads((FIXTURE / "gold" / "must_not_gold.json").read_text())["fixtures"]
    with tx() as c:
        facts = q("""SELECT f.predicate, f.subject_id, f.object_id,
                            s.normalized_surface AS subj, o.normalized_surface AS obj,
                            d.source_name, f.provenance
                       FROM facts f
                       JOIN entities s ON s.entity_id=f.subject_id
                       JOIN entities o ON o.entity_id=f.object_id
                       JOIN evidence ev ON ev.fact_id=f.fact_id
                       JOIN documents d ON d.doc_id=ev.doc_id
                      WHERE d.corpus_id=%s""", (CORPUS,), c)
        neo4j_facts = q("""SELECT DISTINCT f.fact_id FROM facts f
                           JOIN evidence ev ON ev.fact_id=f.fact_id
                           JOIN documents d ON d.doc_id=ev.doc_id
                           WHERE d.corpus_id=%s""", (CORPUS,), c)
    results = []
    for fx in must_not:
        doc = fx["doc"]
        got = [r for r in facts if r["source_name"].endswith(doc)]
        failed = False
        reason = ""
        if fx["id"] == "N01":
            failed = any(r["predicate"] == "has_role" and norm(r["obj"]) == "harborpay" for r in got)
            reason = "has_role with object HarborPay"
        elif fx["id"] == "N02":
            failed = any("okta workforce identity" in norm(r["obj"]) or "okta workforce identity" in norm(r["subj"])
                         for r in got if r["predicate"] in ("causes", "transforms_into", "acquired"))
            reason = "compromise-style fact on Okta Workforce Identity"
        elif fx["id"] == "N03":
            failed = any(r["predicate"] == "uses" and norm(r["obj"]) == "dpop" for r in got)
            reason = "uses/DPoP deployment fact"
        elif fx["id"] == "N04":
            failed = any(r["predicate"] in ("associated_with", "similar_to", "part_of")
                         and {norm(r["subj"]), norm(r["obj"])} == {"meridian api gateway", "settlement api"}
                         for r in got)
            reason = "arbitrary relation between Meridian API Gateway and Settlement API"
        elif fx["id"] == "N05":
            failed = any(r["predicate"] == "has_role" and norm(r["subj"]) == "priya raman"
                         and norm(r["obj"]) == "northwind outfitters" for r in got)
            reason = "Priya Raman has_role Northwind Outfitters"
        elif fx["id"] in ("N06", "N07", "N08", "N09"):
            plat = {"N06": "apache kafka", "N07": "postgresql", "N08": "redis", "N09": "kubernetes"}[fx["id"]]
            failed = any(r["predicate"] == "causes" and norm(r["subj"]) == plat for r in got)
            reason = f"causes with subject {plat}"
        elif fx["id"] == "N10":
            failed = any(r["predicate"] == "causes" and ("robot" in norm(r["subj"]))
                         and ("inventory" in norm(r["obj"]) or "error" in norm(r["obj"])) for r in got)
            reason = "robots caused inventory errors"
        elif fx["id"] == "N11":
            failed = any("locus robotics" in norm(r["subj"]) and r["predicate"] in ("transforms_into",)
                         for r in got)
            reason = "Locus Robotics removal fact"
        elif fx["id"] == "N12":
            failed = any(r["predicate"] == "has_role" and norm(r["subj"]) == "elena torres"
                         and norm(r["obj"]) == "summit fulfillment" for r in got)
            reason = "Elena Torres has_role Summit Fulfillment"
        elif fx["id"] == "N13":
            failed = any(r["predicate"] in ("causes", "enables", "influences") for r in got)
            reason = "speculative concept relation in psych prose"
        results.append({"id": fx["id"], "doc": doc, "passed": not failed,
                        "description": fx["description"], "failure_detail": reason if failed else None})
    passed = sum(1 for r in results if r["passed"])
    EVIDENCE["phases"]["negatives"] = {"passed": passed, "total": len(results), "fixtures": results}
    log("negatives", f"{passed}/{len(results)} passed")


# ---------------------------------------------------------------------------
# Phase 6: generic graph hygiene
# ---------------------------------------------------------------------------
def phase_hygiene() -> None:
    with tx() as c:
        nodes = q("""SELECT e.entity_id, e.core_type, e.normalized_surface, e.admission_class,
                            d.source_name
                       FROM entities e JOIN documents d ON d.doc_id=e.first_seen_doc
                      WHERE d.corpus_id=%s
                      ORDER BY d.source_name, e.normalized_surface""", (CORPUS,), c)
        projected = q("""SELECT DISTINCT e.entity_id FROM facts f
                         JOIN entities e ON e.entity_id IN (f.subject_id, f.object_id)
                         JOIN evidence ev ON ev.fact_id=f.fact_id
                         JOIN documents d ON d.doc_id=ev.doc_id
                        WHERE d.corpus_id=%s""", (CORPUS,), c)
    proj_ids = {r["entity_id"] for r in projected}
    suspect_terms = ("team", "robot", "pilot", "system", "service", "worker", "platform",
                     "component", "process", "customer", "attacker", "learner", "gateway")
    generic_nodes = []
    mention_projected = []
    for n in nodes:
        surf = norm(n["normalized_surface"])
        if n["admission_class"] == "MENTION_ONLY" and n["entity_id"] in proj_ids:
            mention_projected.append(n)
        for t in suspect_terms:
            if t in surf.split():
                generic_nodes.append({**n, "suspect_term": t,
                                      "projected": n["entity_id"] in proj_ids})
                break
    EVIDENCE["phases"]["hygiene"] = {
        "generic_looking_nodes": generic_nodes,
        "mention_only_projected_violations": [
            {"surface": x["normalized_surface"], "class": x["admission_class"],
             "doc": x["source_name"]} for x in mention_projected],
        "mention_only_projected": len(mention_projected),
    }
    log("hygiene", f"generic-looking nodes={len(generic_nodes)} "
                   f"mention-only-projected={len(mention_projected)}")


# ---------------------------------------------------------------------------
# Phase 7: provenance
# ---------------------------------------------------------------------------
def phase_provenance() -> None:
    with tx() as c:
        facts = q("""SELECT f.fact_id, f.predicate,
                            s.normalized_surface AS subj, o.normalized_surface AS obj,
                            ev.chunk_id, ev.span_offsets, ch.text AS chunk_text,
                            ch.parent_id, d.source_name, d.doc_id
                       FROM facts f
                       JOIN entities s ON s.entity_id=f.subject_id
                       JOIN entities o ON o.entity_id=f.object_id
                       JOIN evidence ev ON ev.fact_id=f.fact_id
                       JOIN chunks ch ON ch.chunk_id=ev.chunk_id
                       JOIN documents d ON d.doc_id=ev.doc_id
                      WHERE d.corpus_id=%s ORDER BY d.source_name, f.predicate""", (CORPUS,), c)
    by_doc: dict[str, list] = {}
    for f in facts:
        by_doc.setdefault(f["source_name"], []).append(f)
    sampled = []
    ok = 0
    for doc_name, fs in by_doc.items():
        for f in fs[:3]:
            span = f["span_offsets"]
            text = f["chunk_text"] or ""
            start = end = 0
            exact = False
            if isinstance(span, dict):
                start = int(span.get("chunk_char_start", 0) or 0)
                end = int(span.get("chunk_char_end", 0) or 0)
                exact = "chunk_char_end" in span and end <= len(text)
            elif isinstance(span, list) and len(span) >= 2:
                start, end = span[0], span[-1]
                exact = end <= len(text)
            subj_in = norm(f["subj"]) in norm(text)
            obj_in = norm(f["obj"]) in norm(text)
            if exact and subj_in and obj_in:
                ok += 1
            sampled.append({
                "doc": doc_name,
                "predicate": f["predicate"],
                "subj": f["subj"], "obj": f["obj"],
                "chunk_id": f["chunk_id"], "parent_id": f["parent_id"],
                "span_offsets": span,
                "evidence_excerpt": text[max(0, start - 40):end + 40] if exact else text[:120],
                "subj_in_evidence": subj_in, "obj_in_evidence": obj_in,
                "offsets_in_bounds": exact,
            })
    EVIDENCE["phases"]["provenance"] = {"sampled_facts": sampled, "exact_matches": ok,
                                        "sampled": len(sampled)}
    log("provenance", f"{ok}/{len(sampled)} sampled facts exact-match evidence")


# ---------------------------------------------------------------------------
# Phase 8: Qdrant validation
# ---------------------------------------------------------------------------
def phase_qdrant() -> None:
    from qdrant_client import QdrantClient
    from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=120)
    chunk_name = qdrant_collection_name(CORPUS, active_contract().contract_id)
    routing_name = qdrant_collection_name(CORPUS, NEURAL_EMBED_CONTRACT.contract_id)

    def scroll_all(name):
        out = []
        if client.collection_exists(name):
            off = None
            while True:
                batch, off = client.scroll(collection_name=name, limit=256, offset=off, with_payload=True)
                out.extend(batch)
                if off is None:
                    break
        return out

    chunk_points = scroll_all(chunk_name)
    routing_points = scroll_all(routing_name)
    client.close()
    kinds: dict[str, int] = {}
    foreign = []
    with tx() as c:
        doc_ids = {r["doc_id"] for r in q("SELECT doc_id FROM documents WHERE corpus_id=%s", (CORPUS,), c)}
        chunk_ids = {r["chunk_id"] for r in q(
            "SELECT chunk_id FROM chunks WHERE doc_id IN (SELECT doc_id FROM documents WHERE corpus_id=%s)",
            (CORPUS,), c)}
        summary_ids = {r["summary_id"] for r in q(
            "SELECT summary_id FROM retrieval_summaries WHERE corpus_id=%s", (CORPUS,), c)}

    def dupes_in(points):
        seen = set()
        dup = set()
        for p in points:
            key = str(p.id)
            if key in seen:
                dup.add(key)
            seen.add(key)
        return len(dup)

    for p in routing_points:
        pl = p.payload or {}
        kinds[pl.get("representation_kind", "?")] = kinds.get(pl.get("representation_kind", "?"), 0) + 1
        if pl.get("doc_id") and pl["doc_id"] not in doc_ids:
            foreign.append(pl.get("doc_id"))
    for p in chunk_points:
        pl = p.payload or {}
        if pl.get("doc_id") and pl["doc_id"] not in doc_ids:
            foreign.append(pl.get("doc_id"))
    expected_kinds = {"routing_document_summary", "routing_section_summary", "routing_child"}
    EVIDENCE["phases"]["qdrant"] = {
        "chunk_collection_points": len(chunk_points),
        "routing_collection_points": len(routing_points),
        "routing_kinds": kinds,
        "expected_routing_kinds_present": expected_kinds.issubset(set(kinds.keys())),
        "foreign_doc_points": foreign,
        "duplicate_point_ids_within_routing": dupes_in(routing_points),
        "duplicate_point_ids_within_chunks": dupes_in(chunk_points),
        "note": "the same chunk id legitimately appears in the chunk collection and as a routing_child point; cross-collection identity is by design",
        "expected_chunk_points": len(chunk_ids),
        "expected_routing_points": len(summary_ids) + len(chunk_ids),
    }
    log("qdrant", f"chunk_pts={len(chunk_points)} routing_pts={len(routing_points)} "
                  f"kinds={kinds} foreign={len(foreign)}")


# ---------------------------------------------------------------------------
# Phase 9: Neo4j validation
# ---------------------------------------------------------------------------
def phase_neo4j() -> None:
    from workers.project_neo4j_worker import _driver
    with tx() as c:
        eligible = q("""SELECT f.fact_id, f.predicate FROM facts f
                        JOIN entities s ON s.entity_id=f.subject_id
                        JOIN entities o ON o.entity_id=f.object_id
                        JOIN evidence ev ON ev.fact_id=f.fact_id
                        JOIN documents d ON d.doc_id=ev.doc_id
                       WHERE d.corpus_id=%s AND f.decision='ACCEPT'
                         AND s.admission_class != 'MENTION_ONLY'
                         AND o.admission_class != 'MENTION_ONLY'
                       ORDER BY f.fact_id""", (CORPUS,), c)
        foreign_facts = q("""SELECT COUNT(*) AS n FROM facts f
                             JOIN evidence ev ON ev.fact_id=f.fact_id
                             JOIN documents d ON d.doc_id=ev.doc_id
                            WHERE d.corpus_id != %s""", (CORPUS,), c)
    with tx() as c:
        corpus_docs = {r["doc_id"] for r in q(
            "SELECT doc_id FROM documents WHERE corpus_id=%s", (CORPUS,), c)}
    driver = _driver()
    try:
        with driver.session() as s:
            all_graph_facts = {rec["f"] for rec in s.run(
                "MATCH ()-[r:REL]->() WHERE r.fact_id IS NOT NULL RETURN r.fact_id AS f")}
            graph_docs = {rec["d"] for rec in s.run(
                "MATCH (n:Document) RETURN n.doc_id AS d")} & corpus_docs
            # orphan check restricted to this corpus's own fact universe:
            # any of the corpus's fact ids in Neo4j that are NOT eligible
            with tx() as c2:
                corpus_fact_ids = {r["fact_id"] for r in q(
                    """SELECT DISTINCT ev.fact_id FROM evidence ev
                       JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s""",
                    (CORPUS,), c2)}
            eligible_ids = {x["fact_id"] for x in eligible}
            orphan = sorted(corpus_fact_ids & all_graph_facts - eligible_ids)
    finally:
        driver.close()
    missing = [f["fact_id"] for f in eligible if f["fact_id"] not in all_graph_facts]
    dupes = [f for i, f in enumerate(sorted(all_graph_facts))
             if i > 0 and sorted(all_graph_facts)[i - 1] == f]
    EVIDENCE["phases"]["neo4j"] = {
        "eligible_facts": len(eligible),
        "graph_fact_rels": len(all_graph_facts),
        "missing_eligible": missing,
        "orphan_rels": orphan,
        "duplicate_rels": list(set(dupes)),
        "graph_docs": sorted(graph_docs),
        "note": "all_graph_facts is the SHARED Neo4j graph across corpora; missing/orphan computed only for this corpus's own fact universe",
        "foreign_fact_rows_elsewhere": foreign_facts[0]["n"] if foreign_facts else -1,
    }
    log("neo4j", f"eligible={len(eligible)} graph_rels={len(all_graph_facts)} "
                 f"missing={len(missing)} orphan={len(orphan)} dup={len(set(dupes))}")


# ---------------------------------------------------------------------------
# Phase 10: replay
# ---------------------------------------------------------------------------
def phase_replay() -> None:
    with tx() as c:
        before = q("""SELECT COUNT(*) AS n FROM documents WHERE corpus_id=%s""", (CORPUS,), c)[0]["n"]
        f_before = q("""SELECT COUNT(*) AS n FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id
                        JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s""", (CORPUS,), c)[0]["n"]
        e_before = q("""SELECT COUNT(*) AS n FROM entities e JOIN documents d ON d.doc_id=e.first_seen_doc
                        WHERE d.corpus_id=%s""", (CORPUS,), c)[0]["n"]
    h_before = semantic_hash(CORPUS)
    r = submit_manifest(FIXTURE / "manifest.yaml")
    time.sleep(15)
    with tx() as c:
        after = q("""SELECT COUNT(*) AS n FROM documents WHERE corpus_id=%s""", (CORPUS,), c)[0]["n"]
        f_after = q("""SELECT COUNT(*) AS n FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id
                       JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s""", (CORPUS,), c)[0]["n"]
        e_after = q("""SELECT COUNT(*) AS n FROM entities e JOIN documents d ON d.doc_id=e.first_seen_doc
                       WHERE d.corpus_id=%s""", (CORPUS,), c)[0]["n"]
        new_runs = q("""SELECT COUNT(*) AS n FROM runs WHERE corpus_id=%s AND status='intake'""", (CORPUS,), c)[0]["n"]
    h_after = semantic_hash(CORPUS)
    ok = (r["submitted"] == 0 and before == after and f_before == f_after
          and e_before == e_after and h_before == h_after)
    EVIDENCE["phases"]["replay"] = {
        "resubmitted": r["submitted"],
        "documents_before_after": [before, after],
        "facts_before_after": [f_before, f_after],
        "entities_before_after": [e_before, e_after],
        "semantic_hash_equal": h_before == h_after,
        "new_intake_runs": new_runs,
        "pass": ok,
    }
    log("replay", f"submitted={r['submitted']} docs {before}->{after} facts {f_before}->{f_after} "
                  f"hash_equal={h_before == h_after}")


# ---------------------------------------------------------------------------
# Phase 11: order independence
# ---------------------------------------------------------------------------
def phase_order() -> None:
    h_before = semantic_hash(CORPUS)
    wipe_corpus(CORPUS)
    rev = FIXTURE / "manifest_reversed.yaml"
    r = submit_manifest(rev)
    wait_convergence(CORPUS, 5)
    h_after = semantic_hash(CORPUS)
    ok = h_before == h_after
    EVIDENCE["phases"]["order"] = {
        "submitted": r["submitted"],
        "semantic_hash_equal": ok,
        "hash": h_after[:24],
    }
    log("order", f"reversed-order ingest hash_equal={ok}")


# ---------------------------------------------------------------------------
# Phase 12: concurrent ingestion
# ---------------------------------------------------------------------------
def phase_concurrency() -> None:
    import base64
    h_before = semantic_hash(CORPUS)
    wipe_corpus(CORPUS)
    manifest = load_manifest(FIXTURE / "manifest.yaml")
    sources = resolve_sources(manifest, FIXTURE / "manifest.yaml")
    payloads = []
    for src in sources:
        raw = open(src.resolved_path, "rb").read()
        payloads.append(canonical_intake_payload(
            corpus_id=CORPUS,
            source_name=src.locator,
            media_type=src.media_type,
            content_b64=base64.b64encode(raw).decode(),
        ))

    def submit(p):
        with tx() as c:
            return submit_intake(c, p)

    with ThreadPoolExecutor(max_workers=5) as ex:
        results = list(ex.map(submit, payloads))
    wait_convergence(CORPUS, 5)
    h_after = semantic_hash(CORPUS)
    ok = h_before == h_after
    EVIDENCE["phases"]["concurrency"] = {
        "submitted": len(results),
        "run_ids": sorted({r.get("run_id", "") for r in results if isinstance(r, dict)}),
        "semantic_hash_equal": ok,
        "hash": h_after[:24],
    }
    log("concurrency", f"5 concurrent intakes hash_equal={ok}")


# ---------------------------------------------------------------------------
# Phase 13: interrupt / resume
# ---------------------------------------------------------------------------
def phase_interrupt() -> None:
    import subprocess
    h_before = semantic_hash(CORPUS)
    wipe_corpus(CORPUS)
    # restart the qdrant projector with fault injection enabled
    subprocess.run(["pkill", "-f", "project_qdrant_worker"], check=False)
    time.sleep(2)
    env = dict(os.environ)
    env["POLYMATH_TEST_CRASH_AFTER_POINTS"] = "1"
    with open(ROOT / "var" / "log" / "qdrant_crash_worker.log", "a") as f:
        subprocess.Popen([str(ROOT / ".venv" / "bin" / "python"), "-m",
                          "workers.project_qdrant_worker"],
                         cwd=ROOT, env=env, stdout=f, stderr=f)
    submit_manifest(FIXTURE / "manifest.yaml")
    time.sleep(60)
    with tx() as c:
        failed = q("""SELECT COUNT(*) AS n FROM stage_attempts sa JOIN runs r ON r.run_id=sa.run_id
                      WHERE r.corpus_id=%s AND sa.stage='project_qdrant' AND sa.outcome='failed'""",
                   (CORPUS,), c)[0]["n"]
    log("interrupt", f"crash-injected failed qdrant attempts={failed}")
    # recover: kill crash worker, start clean worker, re-arm via manifest RETRY
    subprocess.run(["pkill", "-f", "project_qdrant_worker"], check=False)
    time.sleep(2)
    with open(ROOT / "var" / "log" / "project_qdrant_worker.log", "a") as f:
        subprocess.Popen([str(ROOT / ".venv" / "bin" / "python"), "-m",
                          "workers.project_qdrant_worker"],
                         cwd=ROOT, stdout=f, stderr=f)
    time.sleep(5)
    submit_manifest(FIXTURE / "manifest.yaml")  # RETRY re-arms failed runs
    states = wait_convergence(CORPUS, 5)
    h_after = semantic_hash(CORPUS)
    ok = states.get("query_ready") == 5 and h_before == h_after
    EVIDENCE["phases"]["interrupt"] = {
        "injected_failures": failed,
        "terminal_states": states,
        "semantic_hash_equal": h_before == h_after,
        "pass": ok,
    }
    log("interrupt", f"recovered 5/5 hash_equal={h_before == h_after}")


# ---------------------------------------------------------------------------
# Phase 14: derived store reconstruction
# ---------------------------------------------------------------------------
def phase_reconstruction() -> None:
    import subprocess
    from qdrant_client import QdrantClient
    from polymath_shared.receipts import supersede_projection_claims
    from workers.project_neo4j_worker import _driver
    h_before = semantic_hash(CORPUS)
    with tx() as c:
        docs = [r["doc_id"] for r in q("SELECT doc_id FROM documents WHERE corpus_id=%s", (CORPUS,), c)]
        chunk_ids = [r["chunk_id"] for r in q(
            "SELECT chunk_id FROM chunks WHERE doc_id = ANY(%s)", (docs,), c)]
        summary_ids = [r["summary_id"] for r in q(
            "SELECT summary_id FROM retrieval_summaries WHERE corpus_id=%s", (CORPUS,), c)]
    client = QdrantClient(url=get_settings().stores.qdrant_url)
    name = qdrant_collection_name(CORPUS, active_contract().contract_id)
    if client.collection_exists(name):
        client.delete_collection(name)
    client.close()
    driver = _driver()
    try:
        with driver.session() as s:
            s.run("MATCH (d:Document) WHERE d.doc_id IN $ids DETACH DELETE d", ids=docs)
            s.run("MATCH (c:Chunk) WHERE c.chunk_id IN $ids DETACH DELETE c", ids=chunk_ids)
    finally:
        driver.close()
    with tx() as c:
        supersede_projection_claims(c, projection="qdrant", entity_ids=chunk_ids + summary_ids)
        supersede_projection_claims(c, projection="neo4j", entity_ids=docs)
    log("reconstruction", "stores destroyed + claims superseded; waiting for census reschedule")
    states = wait_convergence(CORPUS, 5, deadline_s=2400)
    h_after = semantic_hash(CORPUS)
    ok = states.get("query_ready") == 5 and h_before == h_after
    EVIDENCE["phases"]["reconstruction"] = {
        "terminal_states": states,
        "semantic_hash_equal": h_before == h_after,
        "pass": ok,
    }
    log("reconstruction", f"reconverged hash_equal={h_before == h_after}")


# ---------------------------------------------------------------------------
# Phase 15: versioning
# ---------------------------------------------------------------------------
def phase_versioning() -> None:
    v2 = FIXTURE / "versioned"
    v2.mkdir(exist_ok=True)
    src_text = (FIXTURE / "corpus" / "03_northwind_growth_review.md").read_text()
    modified = src_text.replace(
        "Northwind Outfitters kept Shopify Plus, Stripe, and Klaviyo in the existing commerce stack.",
        "Northwind Outfitters kept Shopify Plus, Stripe, and Klaviyo in the existing commerce stack. The company paused poorly performing Meta Ads campaigns.")
    (v2 / "03_northwind_growth_review.md").write_text(modified)
    # the plan's exact single-sentence variant:
    modified2 = src_text.replace(
        "Northwind Outfitters reduced spending on poorly performing Meta Ads campaigns.",
        "Northwind Outfitters paused poorly performing Meta Ads campaigns.")
    (v2 / "03_northwind_growth_review.md").write_text(modified2)
    manifest = {
        "version": 1,
        "corpus": {"corpus_id": CORPUS, "title": "I3 versioning controlled copy",
                   "description": "single-document versioning check"},
        "defaults": {"language": "en", "source_tier": "primary", "enabled": True},
        "documents": [{"source": "./03_northwind_growth_review.md"}],
    }
    (v2 / "manifest.yaml").write_text(json.dumps(manifest))
    # manifest is YAML in this repo; write as yaml-compatible json (yaml superset)
    with tx() as c:
        docs_before = q("SELECT COUNT(*) AS n FROM documents WHERE corpus_id=%s", (CORPUS,), c)[0]["n"]
    r = submit_manifest(v2 / "manifest.yaml")
    wait_convergence(CORPUS, 6)
    with tx() as c:
        rows = q("""SELECT doc_id, source_name, content_hash, created_at FROM documents
                    WHERE corpus_id=%s AND source_name LIKE '%%03_northwind%%'
                    ORDER BY created_at""", (CORPUS,), c)
        docs_after = q("SELECT COUNT(*) AS n FROM documents WHERE corpus_id=%s", (CORPUS,), c)[0]["n"]
    # replay of changed version -> no-op
    r2 = submit_manifest(v2 / "manifest.yaml")
    time.sleep(10)
    with tx() as c:
        docs_after_replay = q("SELECT COUNT(*) AS n FROM documents WHERE corpus_id=%s", (CORPUS,), c)[0]["n"]
    EVIDENCE["phases"]["versioning"] = {
        "submitted": r["submitted"],
        "docs_before": docs_before,
        "docs_after": docs_after,
        "new_versions": len(rows),
        "doc_versions": [{"doc_id": x["doc_id"][:20], "source_name": x["source_name"],
                          "content_hash": x["content_hash"][:20],
                          "created_at": str(x["created_at"])} for x in rows],
        "replay_of_changed_noop": r2["submitted"] == 0,
        "docs_after_replay": docs_after_replay,
    }
    log("versioning", f"new versions={len(rows)} replay_noop={r2['submitted'] == 0}")


# ---------------------------------------------------------------------------
# Phase 16: retrieval smoke
# ---------------------------------------------------------------------------
def phase_retrieval() -> None:
    gold = json.loads((FIXTURE / "gold" / "text_concept_gold.json").read_text())
    questions = gold["frozen_retrieval_questions"]
    table = []
    for doc_key, qs in questions.items():
        doc = qs["doc"]
        for qk in ("q1", "q2"):
            query_text = qs[qk]
            for mode in ("FAST", "HYBRID", "GRAPH"):
                try:
                    r = httpx.post(f"{ORCHESTRATOR}/retrieve",
                                   json={"query": query_text, "corpus_id": CORPUS,
                                         "limit": 10, "mode": mode},
                                   timeout=120)
                    body = r.json()
                except Exception as e:
                    table.append({"query": query_text, "mode": mode, "error": str(e)})
                    continue
                docs = body.get("documents") or body.get("selected_documents") or []
                doc_ids = []
                if isinstance(docs, list):
                    doc_ids = [d.get("doc_id") if isinstance(d, dict) else d for d in docs]
                sections = body.get("sections") or body.get("selected_sections") or []
                sec_parents = [s.get("parent_id") if isinstance(s, dict) else s for s in sections]
                evidence = body.get("evidence") or body.get("final_evidence") or []
                children = [e.get("chunk_id") if isinstance(e, dict) else e for e in evidence]
                graph_rels = body.get("graph_relationships") or []
                graph_fact_ids = [r.get("fact_id") for r in graph_rels if isinstance(r, dict)]
                if not evidence and body.get("documents"):
                    for d in body["documents"]:
                        for s in (d.get("sections") or []):
                            evidence.extend(s.get("evidence") or [])
                if not sections and body.get("documents"):
                    for d in body["documents"]:
                        sections.extend(s.get("sections") or [])
                doc_rank = None
                gold_doc_id = None
                with tx() as c:
                    row = q("SELECT doc_id FROM documents WHERE corpus_id=%s AND source_name LIKE %s",
                            (CORPUS, f"%{doc}"), c)
                    gold_doc_id = row[0]["doc_id"] if row else None
                if gold_doc_id:
                    try:
                        doc_rank = doc_ids.index(gold_doc_id) + 1
                    except ValueError:
                        doc_rank = 99
                # section rank: position of the gold doc's parent among selected sections
                sec_rank = None
                if gold_doc_id and sections:
                    try:
                        sec_rank = next(
                            i + 1 for i, s in enumerate(sections)
                            if (s.get("doc_id") if isinstance(s, dict) else None) == gold_doc_id
                        )
                    except StopIteration:
                        sec_rank = 99
                table.append({
                    "query": query_text, "mode": mode,
                    "gold_doc": doc,
                    "doc_rank": doc_rank,
                    "sec_rank": sec_rank,
                    "child_count": len(children),
                    "graph_evidence_facts": len(graph_rels),
                    "graph_fact_ids": graph_fact_ids,
                    "top_docs": [d[:40] for d in doc_ids[:3]],
                })
    ok = all(row.get("doc_rank") and row["doc_rank"] <= 5 for row in table)
    EVIDENCE["phases"]["retrieval"] = {"all_gold_docs_top5": ok, "table": table}
    log("retrieval", f"{sum(1 for r in table if r.get('doc_rank') and r['doc_rank'] <= 5)}/{len(table)} rows gold-doc top-5")


# ---------------------------------------------------------------------------
# Phase 17: corpus isolation
# ---------------------------------------------------------------------------
def phase_isolation() -> None:
    with tx() as c:
        i3_docs = {r["doc_id"] for r in q("SELECT doc_id FROM documents WHERE corpus_id=%s", (CORPUS,), c)}
        iso_docs = {r["doc_id"] for r in q("SELECT doc_id FROM documents WHERE corpus_id=%s", ("i2-isolation-corpus",), c)}
        iso_facts = {r["fact_id"] for r in q(
            """SELECT DISTINCT ev.fact_id FROM evidence ev JOIN documents d ON d.doc_id=ev.doc_id
               WHERE d.corpus_id=%s""", ("i2-isolation-corpus",), c)}
        i3_facts = {r["fact_id"] for r in q(
            """SELECT DISTINCT ev.fact_id FROM evidence ev JOIN documents d ON d.doc_id=ev.doc_id
               WHERE d.corpus_id=%s""", (CORPUS,), c)}
    foreign = {"docs": [], "chunks": [], "facts": [], "citations": []}
    for mode in ("FAST", "HYBRID", "GRAPH"):
        r = httpx.post(f"{ORCHESTRATOR}/retrieve",
                       json={"query": "What are the controls after the incident?",
                             "corpus_id": CORPUS, "limit": 10, "mode": mode},
                       timeout=120)
        body = r.json()
        docs = body.get("documents") or []
        doc_ids = [d.get("doc_id") if isinstance(d, dict) else d for d in docs]
        for did in doc_ids:
            if did and did not in i3_docs:
                foreign["docs"].append({"mode": mode, "doc_id": did})
        evidence = body.get("evidence") or body.get("final_evidence") or []
        for e in evidence:
            if isinstance(e, dict):
                if e.get("doc_id") and e["doc_id"] not in i3_docs:
                    foreign["chunks"].append({"mode": mode, "chunk_id": e.get("chunk_id")})
                if e.get("fact_id") and e["fact_id"] in iso_facts:
                    foreign["facts"].append({"mode": mode, "fact_id": e["fact_id"]})
    EVIDENCE["phases"]["isolation"] = {
        "foreign_documents": foreign["docs"],
        "foreign_chunks": foreign["chunks"],
        "foreign_facts": foreign["facts"],
        "pass": not any(foreign.values()),
        "iso_corpus_present": len(iso_docs) > 0,
    }
    log("isolation", f"foreign docs={len(foreign['docs'])} chunks={len(foreign['chunks'])} "
                     f"facts={len(foreign['facts'])}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", action="append", default=[])
    args = parser.parse_args()
    phases = args.phase or ["freeze", "ingestion", "control_chain", "entities", "facts",
                            "negatives", "hygiene", "provenance", "qdrant", "neo4j",
                            "replay", "order", "concurrency", "interrupt",
                            "reconstruction", "retrieval", "isolation", "versioning"]
    runners = {
        "freeze": phase_freeze, "ingestion": phase_ingestion,
        "control_chain": phase_control_chain, "entities": phase_entities,
        "facts": phase_facts, "negatives": phase_negatives,
        "hygiene": phase_hygiene, "provenance": phase_provenance,
        "qdrant": phase_qdrant, "neo4j": phase_neo4j,
        "replay": phase_replay, "order": phase_order,
        "concurrency": phase_concurrency, "interrupt": phase_interrupt,
        "reconstruction": phase_reconstruction, "retrieval": phase_retrieval,
        "isolation": phase_isolation, "versioning": phase_versioning,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        LOG_PATH.write_text("")
    for p in phases:
        try:
            runners[p]()
        except Exception as e:
            EVIDENCE["phases"][p] = {"error": str(e)}
            log(p, f"ERROR: {e}")
            print(f"[{p}] ERROR: {e}")
    out = FIXTURE / "evidence" / "evidence.json"
    out.write_text(json.dumps(EVIDENCE, indent=2, default=str))
    print(json.dumps({"completed_phases": phases, "evidence": str(out)}))


if __name__ == "__main__":
    main()
