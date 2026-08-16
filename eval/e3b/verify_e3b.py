"""E3B qualification: entity recall + surface_weak binding on the two
frozen documents. Raw GLiNER proposals, entity audit, surface_weak
gold, ablations (gates off/on + per-gate families), negative/positive
controls, metrics.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

import httpx  # noqa: E402
import psycopg  # noqa: E402

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.intake_submission import canonical_intake_payload, submit_intake  # noqa: E402

DOCS = ROOT / "eval" / "e3" / "corpus" / "docs"
PSYCH = DOCS / "metacognition.md"
CYBER = DOCS / "metacognition_copy.md"
CORPUS = "e3-qualification-corpus"
DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"

GLINER = "http://127.0.0.1:8740"
LABELS = ["Person", "Organization", "Location", "Product", "Technology",
          "Concept", "Method", "Event", "Document", "Process",
          "Measurement", "TimeReference"]

PSYCH_GOLD = [
    "metacognitive monitoring", "metacognitive control",
    "judgments of learning", "processing fluency", "familiarity effect",
    "illusion of competence", "working memory", "cognitive load",
    "retrieval practice", "corrective feedback",
    "self-regulated learning", "local regulation", "global regulation",
]
CYBER_GOLD = [
    "Northstar Digital", "Atlas Identity Gateway", "AWS", "CloudTrail",
    "OAuth 2.0", "Meridian Billing API", "Keycloak 26.2",
    "OpenID Connect", "HTTP Authorization header", "Fluent Bit",
    "Elasticsearch", "Daniel Ortiz", "site reliability engineer",
    "Red Ridge Systems", "bearer token", "mutual TLS", "DPoP", "STRIDE",
    "Amazon GuardDuty", "Security Architecture Council",
]

NEGATIVE_EDGES = [
    ("Daniel Ortiz", "Red Ridge Systems", "has_role"),
    ("Atlas", "identity team", "instance_of"),
    ("red team", "identity team", "instance_of"),
    ("red team", "identity team", "owns"),
    ("Zero-Day Response Handbook", "vendor", "instance_of"),
]

POSITIVE_CONTROLS = [
    # (subject-substring, predicate, object-substring, note)
    ("Keycloak 26.2", "associated_with", "OpenID Connect", "compiler may accept"),
    ("Daniel Ortiz", "has_role", "site reliability engineer", "only if role span proposed"),
]


def gliner_proposals(doc: Path) -> list[dict]:
    text = doc.read_text()
    r = httpx.post(f"{GLINER}/infer", json={
        "task": "entity", "text": text, "labels": LABELS, "threshold": 0.5}, timeout=300)
    r.raise_for_status()
    return r.json().get("spans", [])


def classify(gold_term: str, proposals: list[dict]) -> str:
    term = gold_term.lower()
    for p in proposals:
        pt = p["text"].lower()
        if pt == term:
            return "FOUND_EXACT"
        if term in pt or pt in term:
            return "FOUND_OVERLAP"
    return "MISSED"


def wipe(corpus: str) -> None:
    c = psycopg.connect(DSN)
    rids = [r[0] for r in c.execute("SELECT run_id FROM runs WHERE corpus_id=%s", (corpus,)).fetchall()]
    for rid in rids:
        for t in ("stage_attempts", "artifacts", "receipts", "outbox_events"):
            c.execute(f"DELETE FROM {t} WHERE run_id=%s", (rid,))
    docs = [r[0] for r in c.execute("SELECT doc_id FROM documents WHERE corpus_id=%s", (corpus,)).fetchall()]
    chunks = [r[0] for r in c.execute("SELECT ch.chunk_id FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s", (corpus,)).fetchall()]
    ev_ids = [r[0] for r in c.execute("SELECT evidence_id FROM evidence e JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s", (corpus,)).fetchall()]
    fact_ids = [r[0] for r in c.execute("SELECT DISTINCT f.fact_id FROM facts f JOIN evidence e ON e.fact_id=f.fact_id JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s", (corpus,)).fetchall()]
    ent_ids = [r[0] for r in c.execute("SELECT DISTINCT e.entity_id FROM entities e JOIN facts f ON f.subject_id=e.entity_id OR f.object_id=e.entity_id WHERE f.fact_id = ANY(%s)", (fact_ids,)).fetchall()]
    all_ids = docs + chunks + ev_ids + fact_ids + ent_ids
    if all_ids:
        c.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (all_ids,))
    c.execute("DELETE FROM retrieval_summaries WHERE corpus_id=%s", (corpus,))
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


def run_extraction(gates: str) -> list[dict]:
    from workers.intake_worker import process_event as intake_event
    from workers.extract_worker import process_event as extract_event
    from polymath_shared.identity import content_hash

    os.environ["POLYMATH_BINDING_GATES"] = gates
    wipe(CORPUS)
    facts = []
    for name in ("metacognition.md", "metacognition_copy.md"):
        payload = canonical_intake_payload(CORPUS, name, "text/markdown",
                                           base64.b64encode((DOCS / name).read_bytes()).decode())
        with tx() as c:
            res = submit_intake(c, payload)
        rid = res["run_id"]
        with tx() as c:
            intake_event(c, {"run_id": rid, "payload": payload,
                             "idempotency_key": content_hash({"i": rid})[:16]})
            chunked = c.execute(
                "SELECT payload FROM outbox_events WHERE run_id=%s AND event_type='chunked.v1' "
                "ORDER BY event_id DESC LIMIT 1", (rid,)).fetchone()
        with tx() as c:
            extract_event(c, {"run_id": rid, "payload": chunked[0],
                              "idempotency_key": content_hash({"r": rid})[:16]})
            for r in c.execute("""
                SELECT f.predicate, se.normalized_surface, so.normalized_surface,
                       f.provenance->>'orientation', d.source_name
                  FROM facts f
                  JOIN evidence ev ON ev.fact_id = f.fact_id
                  JOIN documents d ON d.doc_id = ev.doc_id
                  JOIN entities se ON se.entity_id = f.subject_id
                  JOIN entities so ON so.entity_id = f.object_id
                 WHERE d.corpus_id = %s ORDER BY f.predicate""", (CORPUS,)).fetchall():
                facts.append({"predicate": r[0], "subject": r[1], "object": r[2],
                              "orientation": r[3], "source": r[4]})
    return facts


def score_facts(facts: list[dict]) -> dict:
    wrong = 0
    for f in facts:
        for subj, obj, pred in NEGATIVE_EDGES:
            if (subj.lower() in f["subject"].lower() and obj.lower() in f["object"].lower()
                    and f["predicate"] == pred):
                wrong += 1
    return {
        "accepted": len(facts),
        "wrong_edges": wrong,
        "surface_weak": sum(1 for f in facts if f["orientation"] == "surface_weak"),
        "facts": facts,
    }


def main() -> int:
    out: dict = {"phases": {}}

    psych_props = gliner_proposals(PSYCH)
    cyber_props = gliner_proposals(CYBER)
    out["raw_proposals"] = {
        "psychology": [{"text": p["text"], "label": p["label"],
                        "score": round(p["score"], 3), "start": p["start"], "end": p["end"]}
                       for p in psych_props],
        "cybersecurity": [{"text": p["text"], "label": p["label"],
                           "score": round(p["score"], 3), "start": p["start"], "end": p["end"]}
                          for p in cyber_props],
    }
    out["entity_audit"] = {
        "psychology": {t: classify(t, psych_props) for t in PSYCH_GOLD},
        "cybersecurity": {t: classify(t, cyber_props) for t in CYBER_GOLD},
    }
    print("== psychology entity audit")
    for t, v in out["entity_audit"]["psychology"].items():
        print(f"  {t:28} {v}")
    print("== cybersecurity entity audit")
    for t, v in out["entity_audit"]["cybersecurity"].items():
        print(f"  {t:28} {v}")

    out["ablation_baseline"] = score_facts(run_extraction("0"))
    out["ablation_gates_on"] = score_facts(run_extraction("1"))
    print("\n== baseline (gates OFF)", json.dumps({k: v for k, v in out["ablation_baseline"].items() if k != "facts"}, default=str))
    print("== gates ON", json.dumps({k: v for k, v in out["ablation_gates_on"].items() if k != "facts"}, default=str))
    for f in out["ablation_baseline"]["facts"]:
        print("  OFF fact:", f)
    for f in out["ablation_gates_on"]["facts"]:
        print("  ON  fact:", f)

    (ROOT / "eval" / "e3b" / "evidence.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nwrote eval/e3b/evidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
