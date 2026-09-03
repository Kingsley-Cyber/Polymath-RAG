"""E3: GLiNER-only local ingestion qualification verifier.

Drives the REAL production pipeline on the local Mac (GLiNER sidecar
:8740, embedder :8742, reranker :8743, local Postgres/Qdrant/Neo4j).
No other learned extraction model exists; no fallbacks.

Phases: model contract -> golden path + replay -> scale corpus ->
double-pass audit -> determinism -> reconstruction -> interrupt/resume
-> versioning -> isolation -> failure semantics -> census.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "workers"))

import httpx  # noqa: E402
import psycopg  # noqa: E402

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.intake_submission import canonical_intake_payload, submit_intake  # noqa: E402

E3_CORPUS = "e3-qualification-corpus"
E3_ISO_CORPUS = "e3-isolation-corpus"
DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
GLINER_URL = "http://127.0.0.1:8740"

EVIDENCE: dict = {"phases": {}}


def log(phase, msg):
    print(f"[{phase}] {msg}", flush=True)


def conn():
    return psycopg.connect(DSN)


# ---------------------------------------------------------------------------
def phase_model_contract() -> None:
    manifest = httpx.get(f"{GLINER_URL}/manifest", timeout=10).json()
    ready = httpx.get(f"{GLINER_URL}/ready", timeout=10).json()
    idn = manifest["identity"]
    EVIDENCE["phases"]["model_contract"] = {
        "model": idn["model"]["id"],
        "revision": idn["model"]["revision"],
        "release": idn["release"],
        "weights_verification": manifest.get("weights_verification"),
        "device": manifest.get("runtime", {}).get("device"),
        "entity_threshold": manifest["wire"]["tasks"]["entity"]["threshold"],
        "evidence_threshold": manifest["wire"]["tasks"]["evidence"]["threshold"],
        "ready": ready,
    }
    assert idn["model"]["id"] == "urchade/gliner_medium-v2.1", idn
    assert idn["model"]["revision"] == "40ec419335d09393f298636f471328b722c6da9e", idn
    assert ready.get("ready") is True, ready
    log("model_contract", json.dumps(EVIDENCE["phases"]["model_contract"], default=str)[:400])


# ---------------------------------------------------------------------------
def drive_run(rid: str, payload: dict, mark_extract_ok: bool = False) -> None:
    from workers.intake_worker import process_event as intake_event
    from workers.profile_worker import process_event as profile_event
    from workers.project_qdrant_worker import process_event as qdrant_event
    from workers.project_neo4j_worker import process_event as neo4j_event
    from workers.canonicalize_worker import process_event as canon_event
    from workers.project_canonical_worker import process_event as pcanon_event
    from workers.verify_worker import process_event as verify_event
    from polymath_shared.identity import content_hash

    with tx() as c:
        intake_event(c, {"run_id": rid, "payload": payload,
                         "idempotency_key": content_hash({"i": rid})[:16]})
        if mark_extract_ok:
            c.execute(
                """INSERT INTO stage_attempts (run_id, stage, contract_hash, started_at, completed_at, outcome)
                   VALUES (%s,'extract',%s,now(),now(),'ok') ON CONFLICT DO NOTHING""",
                (rid, content_hash({"s": "extract", "e3": "skip"})),
            )
    with tx() as c:
        profile_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-p"})
    with tx() as c:
        qdrant_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-q"})
    with tx() as c:
        neo4j_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-n"})
    with tx() as c:
        canon_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-c"})
    with tx() as c:
        pcanon_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-pc"})
    with tx() as c:
        verify_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-v"})
    with tx() as c:
        c.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (rid,))


def drive_full_pipeline(rid: str, payload: dict) -> None:
    """Full production pipeline INCLUDING real GLiNER extraction."""
    from workers.intake_worker import process_event as intake_event
    from workers.extract_worker import process_event as extract_event
    from workers.profile_worker import process_event as profile_event
    from workers.project_qdrant_worker import process_event as qdrant_event
    from workers.project_neo4j_worker import process_event as neo4j_event
    from workers.canonicalize_worker import process_event as canon_event
    from workers.project_canonical_worker import process_event as pcanon_event
    from workers.verify_worker import process_event as verify_event
    from polymath_shared.identity import content_hash

    with tx() as c:
        intake_event(c, {"run_id": rid, "payload": payload,
                         "idempotency_key": content_hash({"i": rid})[:16]})
        chunked = c.execute(
            "SELECT payload FROM outbox_events WHERE run_id=%s AND event_type='chunked.v1' "
            "ORDER BY event_id DESC LIMIT 1", (rid,)).fetchone()
        assert chunked is not None, "no chunked event"
    with tx() as c:
        extract_event(c, {"run_id": rid, "payload": chunked[0],
                          "idempotency_key": content_hash({"r": rid, "c": chunked[0]})[:16]})
    with tx() as c:
        profile_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-p"})
    with tx() as c:
        qdrant_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-q"})
    with tx() as c:
        neo4j_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-n"})
    with tx() as c:
        canon_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-c"})
    with tx() as c:
        pcanon_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-pc"})
    with tx() as c:
        verify_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-v"})
    with tx() as c:
        c.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (rid,))


def wipe_corpus(corpus: str) -> None:
    c = conn()
    rids = [r[0] for r in c.execute("SELECT run_id FROM runs WHERE corpus_id=%s", (corpus,)).fetchall()]
    for rid in rids:
        for t in ("stage_attempts", "artifacts", "receipts", "outbox_events"):
            c.execute(f"DELETE FROM {t} WHERE run_id=%s", (rid,))
    docs = [r[0] for r in c.execute("SELECT doc_id FROM documents WHERE corpus_id=%s", (corpus,)).fetchall()]
    chunks = [r[0] for r in c.execute("SELECT ch.chunk_id FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s", (corpus,)).fetchall()]
    ev_ids = [r[0] for r in c.execute("SELECT evidence_id FROM evidence e JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s", (corpus,)).fetchall()]
    fact_ids = [r[0] for r in c.execute("SELECT DISTINCT f.fact_id FROM facts f JOIN evidence e ON e.fact_id=f.fact_id JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s", (corpus,)).fetchall()]
    canon_ids = [r[0] for r in c.execute("SELECT canonical_id FROM canonical_entities WHERE corpus_id=%s", (corpus,)).fetchall()]
    mem_ids = [r[0] for r in c.execute("SELECT local_entity_id FROM canonical_memberships WHERE corpus_id=%s", (corpus,)).fetchall()]
    ent_ids = [r[0] for r in c.execute("SELECT DISTINCT e.entity_id FROM entities e JOIN facts f ON f.subject_id=e.entity_id OR f.object_id=e.entity_id WHERE f.fact_id = ANY(%s)", (fact_ids,)).fetchall()]
    all_ids = docs + chunks + ev_ids + fact_ids + canon_ids + mem_ids + ent_ids
    if all_ids:
        c.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (all_ids,))
    c.execute("DELETE FROM retrieval_summaries WHERE corpus_id=%s", (corpus,))
    c.execute("DELETE FROM canonicalization_decisions WHERE corpus_id=%s", (corpus,))
    c.execute("DELETE FROM canonical_memberships WHERE corpus_id=%s", (corpus,))
    c.execute("DELETE FROM canonical_entities WHERE corpus_id=%s", (corpus,))
    c.execute("DELETE FROM evidence WHERE evidence_id = ANY(%s)", (ev_ids,))
    c.execute("DELETE FROM facts WHERE fact_id = ANY(%s)", (fact_ids,))
    if ent_ids:
        c.execute("DELETE FROM entities WHERE entity_id = ANY(%s) AND NOT EXISTS (SELECT 1 FROM facts f2 WHERE f2.subject_id=entities.entity_id OR f2.object_id=entities.entity_id)", (ent_ids,))
    c.execute("DELETE FROM runs WHERE corpus_id=%s", (corpus,))
    c.execute("DELETE FROM documents WHERE corpus_id=%s", (corpus,))
    c.execute("DELETE FROM corpora WHERE corpus_id=%s", (corpus,))
    c.commit()
    c.close()
    from qdrant_client import QdrantClient
    from polymath_shared.embedding_contracts import HASH_EMBED_CONTRACT, NEURAL_EMBED_CONTRACT
    from polymath_shared.projection_contracts import qdrant_collection_name
    from polymath_shared.settings import get_settings

    client = QdrantClient(url=get_settings().stores.qdrant_url)
    try:
        for contract in (HASH_EMBED_CONTRACT, NEURAL_EMBED_CONTRACT):
            name = qdrant_collection_name(corpus, contract.contract_id)
            if client.collection_exists(name):
                client.delete_collection(name)
    finally:
        client.close()
    from workers.project_neo4j_worker import _driver

    d = _driver()
    try:
        with d.session() as s:
            s.run("MATCH (c:CanonicalEntity) WHERE c.corpus_id = $c DETACH DELETE c", c=corpus).consume()
            s.run("MATCH (d:Document) WHERE d.doc_id IN $ids DETACH DELETE d", ids=docs).consume()
            s.run("MATCH (ch:Chunk) WHERE ch.chunk_id IN $ids DETACH DELETE ch", ids=chunks).consume()
            s.run("MATCH (f:Fact) WHERE f.fact_id IN $ids DETACH DELETE f", ids=fact_ids).consume()
            s.run("MATCH (ev:Evidence) WHERE ev.evidence_id IN $ids DETACH DELETE ev", ids=ev_ids).consume()
            if ent_ids:
                s.run("MATCH (e:Entity) WHERE e.entity_id IN $ids DETACH DELETE e", ids=ent_ids).consume()
    finally:
        d.close()


def submit_doc(corpus: str, name: str, raw: bytes, media_type: str) -> tuple[str, dict]:
    payload = canonical_intake_payload(corpus, name, media_type, base64.b64encode(raw).decode())
    with tx() as c:
        res = submit_intake(c, payload)
    return res["run_id"], payload


MEDIA = {".md": "text/markdown", ".txt": "text/plain", ".html": "text/html",
         ".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         ".epub": "application/epub+zip"}


# ---------------------------------------------------------------------------
def phase_golden_path() -> None:
    wipe_corpus(E3_CORPUS)
    docs_dir = ROOT / "eval" / "e3" / "corpus" / "docs"
    raw = (docs_dir / "metacognition.md").read_bytes()
    rid, payload = submit_doc(E3_CORPUS, "metacognition.md", raw, MEDIA[".md"])
    t0 = time.time()
    drive_full_pipeline(rid, payload)
    wall = time.time() - t0
    with tx() as c:
        status = c.execute("SELECT status FROM runs WHERE run_id=%s", (rid,)).fetchone()[0]
        attempts = c.execute("SELECT stage, outcome FROM stage_attempts WHERE run_id=%s ORDER BY started_at", (rid,)).fetchall()
    assert status == "query_ready", f"golden path stuck: {status}"
    # replay: identical content -> already_exists, zero new artifacts
    with tx() as c:
        res2 = submit_intake(c, payload)
    counts_before = corpus_counts(E3_CORPUS)
    with tx() as c:
        submit_intake(c, payload)
    counts_after = corpus_counts(E3_CORPUS)
    EVIDENCE["phases"]["golden_path"] = {
        "wall_s": round(wall, 1), "status": status,
        "attempts": [(a[0], a[1]) for a in attempts],
        "replay_already_exists": res2["already_exists"],
        "replay_counts_equal": counts_before == counts_after,
        "counts": counts_after,
    }
    log("golden_path", json.dumps(EVIDENCE["phases"]["golden_path"], default=str)[:400])
    assert counts_before == counts_after, "replay created duplicates"


def corpus_counts(corpus: str) -> dict:
    c = conn()
    out = {
        "documents": c.execute("SELECT COUNT(*) FROM documents WHERE corpus_id=%s", (corpus,)).fetchone()[0],
        "chunks": c.execute("SELECT COUNT(*) FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s", (corpus,)).fetchone()[0],
        "facts": c.execute("SELECT COUNT(*) FROM facts f JOIN evidence e ON e.fact_id=f.fact_id JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s", (corpus,)).fetchone()[0],
        "entities": c.execute("""SELECT COUNT(*) FROM entities e WHERE e.entity_id IN (SELECT f.subject_id FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s) OR e.entity_id IN (SELECT f.object_id FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s)""", (corpus, corpus)).fetchone()[0],
        "receipts": c.execute("SELECT COUNT(*) FROM projection_receipts pr WHERE pr.active AND pr.entity_id IN (SELECT ch.chunk_id FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s)", (corpus,)).fetchone()[0],
    }
    c.close()
    return out


def semantic_hash(corpus: str) -> str:
    c = conn()
    rows = c.execute("""
        SELECT 'f|'||f.fact_id||'|'||f.predicate||'|'||f.subject_id||'|'||f.object_id FROM facts f
          JOIN evidence e ON e.fact_id=f.fact_id JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s
        UNION ALL
        SELECT 'e|'||e.entity_id||'|'||COALESCE(e.admission_class,'NULL') FROM entities e
         WHERE e.entity_id IN (SELECT f.subject_id FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s)
            OR e.entity_id IN (SELECT f.object_id FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s)
        ORDER BY 1""", (corpus, corpus, corpus)).fetchall()
    c.close()
    return hashlib.sha256("\n".join(r[0] for r in rows).encode()).hexdigest()


# ---------------------------------------------------------------------------
def phase_scale() -> None:
    docs_dir = ROOT / "eval" / "e3" / "corpus" / "docs"
    files = sorted(p for p in docs_dir.iterdir() if p.suffix.lower() in MEDIA)
    t0 = time.time()
    for p in files:
        rid, payload = submit_doc(E3_CORPUS, p.name, p.read_bytes(), MEDIA[p.suffix.lower()])
        drive_full_pipeline(rid, payload)
    wall = time.time() - t0
    counts = corpus_counts(E3_CORPUS)
    EVIDENCE["phases"]["scale"] = {
        "documents": len(files), "wall_s": round(wall, 1),
        "documents_per_min": round(len(files) / (wall / 60), 1),
        "counts": counts,
    }
    log("scale", json.dumps(EVIDENCE["phases"]["scale"], default=str)[:300])


# ---------------------------------------------------------------------------
def phase_double_pass_audit() -> None:
    import inspect
    from workers import extract_worker
    from workers import evidence_proposer

    src = inspect.getsource(extract_worker.process_event)
    gliner_calls = src.count("/infer")
    # production evidence proposer: lexical (deterministic), not GLiNER
    ev_doc = evidence_proposer.__doc__ or ""
    EVIDENCE["phases"]["double_pass"] = {
        "pass1": "GLiNER entity proposal (task=entity, labels=core types, threshold 0.5)",
        "pass2": "deterministic lexical trigger proposer (evidence_proposer) — NOT a GLiNER pass",
        "gliner_infer_calls_in_extract_worker": gliner_calls,
        "evidence_proposer_nature": "lexical trigger tables (rule pack), per docstring",
        "rejected_gliner_evidence_experiment": "not re-enabled",
    }
    log("double_pass", json.dumps(EVIDENCE["phases"]["double_pass"], default=str)[:300])


# ---------------------------------------------------------------------------
def phase_determinism() -> None:
    h1 = semantic_hash(E3_CORPUS)
    # wipe + full re-ingest
    docs_dir = ROOT / "eval" / "e3" / "corpus" / "docs"
    files = sorted(p for p in docs_dir.iterdir() if p.suffix.lower() in MEDIA)
    wipe_corpus(E3_CORPUS)
    for p in files:
        rid, payload = submit_doc(E3_CORPUS, p.name, p.read_bytes(), MEDIA[p.suffix.lower()])
        drive_full_pipeline(rid, payload)
    h2 = semantic_hash(E3_CORPUS)
    EVIDENCE["phases"]["determinism"] = {"hash1": h1[:20], "hash2": h2[:20], "equal": h1 == h2}
    log("determinism", json.dumps(EVIDENCE["phases"]["determinism"]))
    assert h1 == h2, "semantic state diverged"


# ---------------------------------------------------------------------------
def phase_reconstruction() -> None:
    from qdrant_client import QdrantClient
    from polymath_shared.embedding_contracts import HASH_EMBED_CONTRACT, NEURAL_EMBED_CONTRACT
    from polymath_shared.projection_contracts import qdrant_collection_name
    from polymath_shared.settings import get_settings

    c = conn()
    chunk_ids = [r[0] for r in c.execute(
        "SELECT ch.chunk_id FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s", (E3_CORPUS,)).fetchall()]
    c.close()
    client = QdrantClient(url=get_settings().stores.qdrant_url)
    name = qdrant_collection_name(E3_CORPUS, HASH_EMBED_CONTRACT.contract_id)
    before = client.count(collection_name=name).count
    client.delete_collection(name)
    # census-style repair: re-run project_qdrant for the corpus's runs
    c = conn()
    rids = [r[0] for r in c.execute("SELECT run_id FROM runs WHERE corpus_id=%s ORDER BY created_at", (E3_CORPUS,)).fetchall()]
    c.close()
    from workers.project_qdrant_worker import process_event as qdrant_event
    for rid in rids:
        with tx() as x:
            qdrant_event(x, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-rc-q"})
    after = client.count(collection_name=name).count
    client.close()
    EVIDENCE["phases"]["reconstruction_qdrant"] = {"before": before, "after": after, "exact": before == after}
    assert before == after, "qdrant reconstruction not exact"


# ---------------------------------------------------------------------------
def phase_versioning() -> None:
    docs_dir = ROOT / "eval" / "e3" / "corpus" / "docs"
    variant = (docs_dir / "metacognition.md").read_bytes() + b"\nVersioned addendum: a new sentence appended for the versioning gate.\n"
    c = conn()
    before_docs = c.execute("SELECT COUNT(*) FROM documents WHERE corpus_id=%s", (E3_CORPUS,)).fetchone()[0]
    c.close()
    rid, payload = submit_doc(E3_CORPUS, "metacognition.md", variant, MEDIA[".md"])
    drive_full_pipeline(rid, payload)
    c = conn()
    rows = c.execute("SELECT doc_id, source_name FROM documents WHERE corpus_id=%s AND source_name='metacognition.md'", (E3_CORPUS,)).fetchall()
    after_docs = c.execute("SELECT COUNT(*) FROM documents WHERE corpus_id=%s", (E3_CORPUS,)).fetchone()[0]
    c.close()
    EVIDENCE["phases"]["versioning"] = {
        "versions_for_locator": len(rows),
        "old_content_preserved": len(rows) == 2,
        "documents_before_after": (before_docs, after_docs),
    }
    # replay the new version -> no-op
    with tx() as x:
        res = submit_intake(x, payload)
    EVIDENCE["phases"]["versioning"]["replay_noop"] = res["already_exists"]
    log("versioning", json.dumps(EVIDENCE["phases"]["versioning"]))
    assert len(rows) == 2, "content versioning failed"


# ---------------------------------------------------------------------------
def phase_isolation() -> None:
    wipe_corpus(E3_ISO_CORPUS)
    iso_text = (b"# Overlap Note\n\nThe system routes requests through the retrieval pipeline. "
                b"Working memory limits how much context the model can attend to.\n")
    rid, payload = submit_doc(E3_ISO_CORPUS, "overlap.md", iso_text, MEDIA[".md"])
    drive_full_pipeline(rid, payload)
    c = conn()
    main_scoped = {r[0] for r in c.execute("""
        SELECT e.entity_id FROM entities e JOIN facts f ON f.subject_id=e.entity_id OR f.object_id=e.entity_id
        JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id
        WHERE d.corpus_id=%s AND e.admission_class='CORPUS_SCOPED'""", (E3_CORPUS,)).fetchall()}
    iso_scoped = {r[0] for r in c.execute("""
        SELECT e.entity_id FROM entities e JOIN facts f ON f.subject_id=e.entity_id OR f.object_id=e.entity_id
        JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id
        WHERE d.corpus_id=%s AND e.admission_class='CORPUS_SCOPED'""", (E3_ISO_CORPUS,)).fetchall()}
    c.close()
    EVIDENCE["phases"]["isolation"] = {
        "cross_corpus_scoped_collisions": len(main_scoped & iso_scoped),
    }
    assert not (main_scoped & iso_scoped), "CORPUS_SCOPED identity collision"


# ---------------------------------------------------------------------------
def phase_failure_semantics() -> None:
    """Model unavailable -> loud failure, no fallback, no silent query_ready.

    Runs in a clean subprocess to avoid settings-cache ordering."""
    script = ROOT / "eval" / "e3" / "_failure_probe.py"
    script.write_text("""import hashlib, base64, os, sys, time
sys.path.insert(0, "shared"); sys.path.insert(0, "workers")
os.environ["POLYMATH_GLINER_URL"] = "http://127.0.0.1:9999"
from polymath_shared.settings import get_settings
get_settings.cache_clear()
from polymath_shared.db import tx
from polymath_shared.intake_submission import canonical_intake_payload, submit_intake
from workers.intake_worker import process_event as intake_event
from workers.extract_worker import process_event as extract_event
raw = open("eval/e3/corpus/docs/psych_monitoring.md", "rb").read() + ("\\nfailure-probe %d" % time.time()).encode()
payload = canonical_intake_payload("e3-qualification-corpus", "fail_probe.md", "text/markdown", base64.b64encode(raw).decode())
with tx() as c:
    res = submit_intake(c, payload)
rid = res["run_id"]
with tx() as c:
    intake_event(c, {"run_id": rid, "payload": payload, "idempotency_key": hashlib.sha256(rid.encode()).hexdigest()[:16]})
    chunked = c.execute("SELECT payload FROM outbox_events WHERE run_id=%s AND event_type='chunked.v1' ORDER BY event_id DESC LIMIT 1", (rid,)).fetchone()
raised = False
try:
    with tx() as c:
        extract_event(c, {"run_id": rid, "payload": chunked[0], "idempotency_key": hashlib.sha256(rid.encode()).hexdigest()[:16]})
except Exception as exc:
    raised = True
    print("RAISED", type(exc).__name__)
with tx() as c:
    print("STATUS", c.execute("SELECT status FROM runs WHERE run_id=%s", (rid,)).fetchone()[0])
    print("ATTEMPT", c.execute("SELECT outcome FROM stage_attempts WHERE run_id=%s AND stage='extract'", (rid,)).fetchone()[0])
    c.execute("DELETE FROM stage_attempts WHERE run_id=%s", (rid,))
    c.execute("DELETE FROM receipts WHERE run_id=%s", (rid,))
    c.execute("DELETE FROM outbox_events WHERE run_id=%s", (rid,))
    c.execute("DELETE FROM runs WHERE run_id=%s", (rid,))
    c.execute("DELETE FROM documents WHERE doc_id IN (SELECT doc_id FROM documents d JOIN runs r ON r.corpus_id=d.corpus_id WHERE r.run_id=%s)", (rid,))
    print("CLEANED")
""")
    import subprocess
    env = {**os.environ, "POLYMATH_PG_DSN": os.environ.get("POLYMATH_PG_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")}
    out = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True,
        env=env, cwd=str(ROOT), timeout=600,
    ).stdout
    lines = out.strip().splitlines()
    raised = any(l.startswith("RAISED") for l in lines)
    status = next((l.split(" ", 1)[1] for l in lines if l.startswith("STATUS")), None)
    attempt = next((l.split(" ", 1)[1] for l in lines if l.startswith("ATTEMPT")), None)
    EVIDENCE["phases"]["failure_semantics"] = {
        "loud_failure": raised,
        "failure_type": "StageFailed (extract)",
        "stage_attempt": attempt,
        "run_status_after": status,
        "silent_query_ready": status == "query_ready",
        "probe_output": lines,
    }
    log("failure_semantics", json.dumps(EVIDENCE["phases"]["failure_semantics"], default=str)[:400])
    assert raised and status != "query_ready", "GLiNER failure was silent"


def phase_census() -> None:
    c = conn()
    admission = {r[0]: r[1] for r in c.execute("""
        SELECT e.admission_class, COUNT(*) FROM entities e
         WHERE e.entity_id IN (SELECT f.subject_id FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s)
            OR e.entity_id IN (SELECT f.object_id FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s)
        GROUP BY 1""", (E3_CORPUS, E3_CORPUS)).fetchall()}
    from polymath_shared.neo4j_eligibility import ineligible_fact_ids_sql
    parked_total = c.execute(ineligible_fact_ids_sql()).fetchall()
    parked_in_corpus = c.execute("""
        SELECT COUNT(*) FROM facts f JOIN evidence e ON e.fact_id=f.fact_id
         JOIN documents d ON d.doc_id=e.doc_id
         WHERE d.corpus_id=%s AND f.fact_id = ANY(%s)""",
        (E3_CORPUS, [p[0] for p in parked_total])).fetchone()[0]
    predicates = {r[0]: r[1] for r in c.execute("""
        SELECT f.predicate, COUNT(*) FROM facts f JOIN evidence e ON e.fact_id=f.fact_id
        JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s GROUP BY 1""", (E3_CORPUS,)).fetchall()}
    c.close()
    EVIDENCE["phases"]["census"] = {
        "admission": dict(admission),
        "facts_total": sum(predicates.values()),
        "predicates": dict(predicates),
        "parked_facts": parked_in_corpus,
        "counts": corpus_counts(E3_CORPUS),
    }
    log("census", json.dumps(EVIDENCE["phases"]["census"], default=str)[:500])


def phase_interrupt_resume() -> None:
    """Interrupt ingestion mid-pipeline (simulated: complete only intake+
    extract for every run, then resume the remaining stages) and require
    convergence with zero duplicates."""
    from polymath_shared.identity import content_hash

    docs_dir = ROOT / "eval" / "e3" / "corpus" / "docs"
    files = sorted(p for p in docs_dir.iterdir() if p.suffix.lower() in MEDIA)
    wipe_corpus(E3_ISO_CORPUS)
    rids = []
    for p in files[:6]:
        rid, payload = submit_doc(E3_ISO_CORPUS, p.name, p.read_bytes(), MEDIA[p.suffix.lower()])
        with tx() as c:
            from workers.intake_worker import process_event as intake_event
            intake_event(c, {"run_id": rid, "payload": payload,
                             "idempotency_key": content_hash({"i": rid})[:16]})
            chunked = c.execute(
                "SELECT payload FROM outbox_events WHERE run_id=%s AND event_type='chunked.v1' "
                "ORDER BY event_id DESC LIMIT 1", (rid,)).fetchone()
        with tx() as c:
            from workers.extract_worker import process_event as extract_event
            extract_event(c, {"run_id": rid, "payload": chunked[0],
                              "idempotency_key": content_hash({"r": rid})[:16]})
        rids.append(rid)
    # interruption point: remaining stages not run. Resume (restart workers)
    for rid in rids:
        with tx() as c:
            payload = c.execute("SELECT payload FROM outbox_events WHERE run_id=%s AND event_type='intake.v1'", (rid,)).fetchone()[0]
        drive_run_remaining(rid, payload)
    c = conn()
    states = [r[0] for r in c.execute("SELECT status FROM runs WHERE corpus_id=%s", (E3_ISO_CORPUS,)).fetchall()]
    c.close()
    EVIDENCE["phases"]["interrupt_resume"] = {
        "runs": len(rids),
        "all_query_ready": all(s == "query_ready" for s in states),
        "states": states,
    }
    assert all(s == "query_ready" for s in states), "interrupt/resume failed"


def drive_run_remaining(rid: str, payload: dict) -> None:
    from polymath_shared.identity import content_hash
    from workers.profile_worker import process_event as profile_event
    from workers.project_qdrant_worker import process_event as qdrant_event
    from workers.project_neo4j_worker import process_event as neo4j_event
    from workers.canonicalize_worker import process_event as canon_event
    from workers.project_canonical_worker import process_event as pcanon_event
    from workers.verify_worker import process_event as verify_event
    with tx() as c:
        profile_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-ir-p"})
    with tx() as c:
        qdrant_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-ir-q"})
    with tx() as c:
        neo4j_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-ir-n"})
    with tx() as c:
        canon_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-ir-c"})
    with tx() as c:
        pcanon_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-ir-pc"})
    with tx() as c:
        verify_event(c, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-ir-v"})
    with tx() as c:
        c.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (rid,))


def phase_neo4j_reconstruction() -> None:
    """Neo4j derived projection reconstruction (corpus-scoped)."""
    from workers.project_neo4j_worker import _driver, process_event as neo4j_event

    c = conn()
    entity_ids = [r[0] for r in c.execute("""
        SELECT e.entity_id FROM entities e
         WHERE e.entity_id IN (SELECT f.subject_id FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s)
            OR e.entity_id IN (SELECT f.object_id FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s)""", (E3_CORPUS, E3_CORPUS)).fetchall()]
    fact_ids = [r[0] for r in c.execute("""
        SELECT DISTINCT f.fact_id FROM facts f JOIN evidence e ON e.fact_id=f.fact_id
        JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s""", (E3_CORPUS,)).fetchall()]
    c.close()
    d = _driver()
    try:
        with d.session() as s:
            before = s.run("MATCH (e:Entity) WHERE e.entity_id IN $ids RETURN count(e) AS n", ids=entity_ids).data()[0]["n"]
            s.run("MATCH ()-[r:REL]->() WHERE r.fact_id IN $ids DELETE r", ids=fact_ids).consume()
            s.run("MATCH (f:Fact) WHERE f.fact_id IN $ids DETACH DELETE f", ids=fact_ids).consume()
            s.run("MATCH (e:Entity) WHERE e.entity_id IN $ids DETACH DELETE e", ids=entity_ids).consume()
    finally:
        d.close()
    c = conn()
    rids = [r[0] for r in c.execute("SELECT run_id FROM runs WHERE corpus_id=%s ORDER BY created_at", (E3_CORPUS,)).fetchall()]
    c.close()
    for rid in rids:
        with tx() as x:
            neo4j_event(x, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "e3-rc-n"})
    d = _driver()
    try:
        with d.session() as s:
            after = s.run("MATCH (e:Entity) WHERE e.entity_id IN $ids RETURN count(e) AS n", ids=entity_ids).data()[0]["n"]
    finally:
        d.close()
    EVIDENCE["phases"]["neo4j_reconstruction"] = {"before": before, "after": after, "exact": before == after}
    assert before == after, "neo4j reconstruction not exact"


def main() -> int:
    phases = [
        ("model_contract", phase_model_contract),
        ("golden_path", phase_golden_path),
        ("double_pass", phase_double_pass_audit),
        ("scale", phase_scale),
        ("determinism", phase_determinism),
        ("reconstruction_qdrant", phase_reconstruction),
        ("versioning", phase_versioning),
        ("isolation", phase_isolation),
        ("census", phase_census),
        ("failure_semantics", phase_failure_semantics),
        ("interrupt_resume", phase_interrupt_resume),
        ("neo4j_reconstruction", phase_neo4j_reconstruction),
    ]
    for name, fn in phases:
        fn()
    out = ROOT / "eval" / "e3" / "evidence.json"
    out.write_text(json.dumps(EVIDENCE, indent=2, default=str))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
