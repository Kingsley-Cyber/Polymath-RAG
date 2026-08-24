"""POLYMATH-VALIDATION-V1 — mixed-corpus end-to-end validation."""
import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

os.environ["POLYMATH_RELATION_PIPELINE"] = "kimi_v1"
os.environ["POLYMATH_PREDICATE_V2"] = "shadow"
os.environ["POLYMATH_SYNTAX_PROVIDER"] = "spacy"
os.environ.setdefault(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

CORPUS = "polymath-validation-v1"

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

DOCS = [
 {"kind": "SCIENTIFIC", "name": "attention-research-paper.md", "text":
  "# Attention Mechanisms in Transformer Models\n\nAbstract. We "
  "evaluate the transformer architecture on multiple benchmark "
  "datasets. The methodology uses controlled experiments where each "
  "model was trained on a curated corpus and evaluated on held-out "
  "results. The BERT baseline was compared against newer architectures. "
  "Results show consistent improvements in evaluation scores.\n\n"
  "Methodology. Each dataset was preprocessed identically. We propose "
  "an evaluation protocol where models were evaluated on identical "
  "splits."},
 {"kind": "SCIENTIFIC", "name": "embedding-benchmarks-article.md", "text":
  "# Benchmarking Text Embedding Models\n\nAbstract. This article "
  "evaluates sentence embedding models on retrieval benchmarks. Every "
  "model was trained on large corpora and evaluated on standard "
  "datasets. Results indicate that domain-adaptive pretraining "
  "improves benchmark performance across datasets."},
 {"kind": "PROCEDURAL", "name": "ga4-addtocart-tutorial.md", "text":
  "# How to create an add to cart report in Google Analytics\n\n"
  "First open GA4 Explore. Select Free Form. Add item added to cart "
  "metric. Add item ID and item name dimensions. Run the report and "
  "analyze products by add to cart count. Configure Shopify to send "
  "commerce events to Google Analytics."},
 {"kind": "PROCEDURAL", "name": "cybersecurity-siem-walkthrough.md", "text":
  "# SIEM Correlation Walkthrough\n\nStep 1: Install the sensor on the "
  "perimeter network. Step 2: Configure the SIEM to run correlation "
  "rules. Step 3: Deploy agents to all endpoints. Step 4: Execute a "
  "baseline scan and review alert results."},
 {"kind": "PROCEDURAL", "name": "kubernetes-deployment-guide.md", "text":
  "# Kubernetes Deployment Guide\n\nFirst deploy the cluster using "
  "kubeadm. Next configure the ingress controller. Then select a pod "
  "network. Finally run the smoke test suite and verify workloads."},
 {"kind": "PROCEDURAL", "name": "military-defensive-sop.md", "text":
  "# Defensive Operations SOP\n\nStep 1: Establish the defensive "
  "perimeter. Step 2: Assign sectors to each squad. Step 3: Report "
  "contact to command. Step 4: Reinforce engaged sectors."},
 {"kind": "CONCEPTUAL", "name": "stoicism-philosophy-lecture.md", "text":
  "# Stoicism Lecture\n\nStoicism teaches focusing on what is within "
  "our control. A threat model describes assumptions about attackers "
  "and assets. The dichotomy of control is defined as focusing "
  "attention only on controllable actions. Virtue is the only true "
  "good according to the doctrine."},
 {"kind": "CONCEPTUAL", "name": "platform-business-framework.md", "text":
  "# Platform Business Frameworks\n\nA platform business framework "
  "describes how network effects create value. The framework argues "
  "that definitions of moats depend on switching costs. Concepts like "
  "flywheel dynamics represent compounding growth loops."},
 {"kind": "REFERENCE", "name": "api-gateway-technical-manual.md", "text":
  "# API Gateway Technical Manual\n\nThe gateway routes requests to "
  "upstream services. Rate limiting protects upstream services from "
  "abuse. Authentication validates credentials before routing. "
  "Configure timeouts per route. Retries follow exponential backoff."},
]


def main() -> dict:
    base64_ = __import__("base64")
    from polymath_shared.intake_submission import submit_intake
    from workers.intake_worker import process_event as intake_process
    from workers.extract_worker import process_event as extract_process
    from polymath_shared.summary_runtime import run_parent_summary_ticket
    from polymath_shared.summary_workers import build_document_summary
    from polymath_shared.corpus_mapping import build_corpus_map
    from polymath_shared.vocabulary_mapping import build_concept_families
    from polymath_shared.knowledge_objects.procedure import compile_procedure
    from polymath_shared.knowledge_objects.concept import compile_concepts

    wconn = psycopg.connect(os.environ["POLYMATH_PG_DSN"], autocommit=False)
    conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"], autocommit=False,
                           row_factory=dict_row)
    rcur = conn.cursor(row_factory=dict_row)

    per_doc, all_procedures = [], []
    for spec in DOCS:
        canonical = {"corpus_id": CORPUS, "source_name": spec["name"],
                     "media_type": "text/markdown",
                     "content_b64": base64_.b64encode(
                         spec["text"].encode()).decode(), "config": {}}
        r = submit_intake(wconn, canonical)
        run_id = r["run_id"]
        intake_process(wconn, {"run_id": run_id, "event_type": "intake.v1",
                               "payload": canonical,
                               "idempotency_key": "pv1"})
        wconn.commit()
        doc_id = rcur.execute("""
            SELECT doc_id FROM documents WHERE corpus_id=%s AND
            source_name=%s""", (CORPUS, spec["name"])).fetchone()["doc_id"]
        evp = rcur.execute("""
            SELECT payload::text FROM outbox_events WHERE run_id=%s AND
            event_type='chunked.v1' ORDER BY event_id LIMIT 1""",
            (run_id,)).fetchone()["payload"]
        extract_process(wconn, {"run_id": run_id, "event_type": "chunked.v1",
                                "payload": json.loads(evp),
                                "idempotency_key": "pv1"})
        wconn.commit()

        facts = rcur.execute("""
            SELECT DISTINCT f.fact_id, f.predicate,
                   sn.normalized_surface AS subject_surface,
                   no.normalized_surface AS object_surface
              FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id
              JOIN entities sn ON sn.entity_id=f.subject_id
              JOIN entities no ON no.entity_id=f.object_id
             WHERE ev.doc_id=%s""", (doc_id,)).fetchall()
        facts = [dict(f) for f in facts]
        ents = [x["surface"] for x in rcur.execute("""
            SELECT DISTINCT surface FROM mentions WHERE doc_id=%s AND
            admission_class IN ('GLOBAL','CORPUS_SCOPED',
                                'DOCUMENT_SCOPED')""",
            (doc_id,)).fetchall()]

        proc = None
        concepts = []
        if spec["kind"] == "PROCEDURAL":
            proc = compile_procedure(
                document_id=doc_id, corpus_id=CORPUS, text=spec["text"],
                title=spec["name"], admitted_entities=ents)
            if proc:
                all_procedures.append(proc | {"doc": doc_id})
        if spec["kind"] == "CONCEPTUAL":
            sents = [x.strip() + "." for x in spec["text"].split(".")
                     if len(x.strip()) > 15]
            concepts = compile_concepts(
                document_id=doc_id, corpus_id=CORPUS, sentences=sents,
                domain="general", admitted_entities=ents)

        parents = rcur.execute("""
            SELECT chunk_id, text FROM chunks WHERE doc_id=%s AND
            tier='parent' ORDER BY chunk_index LIMIT 6""",
            (doc_id,)).fetchall()
        parent_payloads = []
        for p in parents:
            pid, ptext = p["chunk_id"], p["text"]
            kids = rcur.execute("""
                SELECT chunk_id FROM chunks WHERE parent_id=%s AND
                tier='child'""", (pid,)).fetchall()
            kid_ids = [k["chunk_id"] for k in kids]
            ticket = "pv1_ps_" + pid[-12:]
            conn.execute("""
                INSERT INTO summary_jobs (ticket_id, stage, corpus_id,
                  parent_id, input_hash, contract_version)
                VALUES (%s,'PARENT_SUMMARY',%s,%s,%s,'pv1')
                ON CONFLICT (ticket_id) DO NOTHING""",
                (ticket, CORPUS, pid, "pv1_" + pid[-16:]))
            rr = run_parent_summary_ticket(
                conn, ticket_id=ticket, corpus_id=CORPUS, parent_id=pid,
                input_hash="pv1_" + pid[-16:], contract_version="pv1",
                worker_id="polymath-validate", parent_text=ptext,
                children=[{"id": k, "text": ""} for k in kid_ids],
                facts=facts,
                entities=[{"surface": s} for s in ents],
                source_ids=kid_ids or [pid])
            if rr.get("status") in ("COMPLETE", "EXISTING"):
                row = rcur.execute("""
                    SELECT entities, concepts, summary FROM parent_summaries
                     WHERE summary_id=%s""", (rr["summary_id"],)).fetchone()
                parent_payloads.append({
                    "payload": {"parent_id": pid,
                                "entities": row["entities"],
                                "concepts": row["concepts"],
                                "summary": row["summary"]},
                    "artifact_id": rr["summary_id"]})

        ds_env = build_document_summary(
            document_id=doc_id, title=spec["name"],
            parent_summaries=parent_payloads,
            procedures=[proc] if proc else [], concepts=concepts)
        ds = {"summary_id": "dsum_" + doc_id[-12:], "document_id": doc_id,
              **ds_env["payload"], "evidence_density": min(len(facts)/5, 1),
              "methods": sorted({f["predicate"] for f in facts})}
        per_doc.append({"kind": spec["kind"], "doc_id": doc_id,
                        "facts": len(facts), "entities": len(ents),
                        "procedure_steps": len((proc or {}).get("steps", [])),
                        "concepts": len(concepts),
                        "parents_summarized": len(parent_payloads),
                        "doc": ds})

    map_docs = [{"summary_id": d["doc"]["summary_id"],
                 "major_entities": d["doc"]["major_entities"],
                 "major_concepts": d["doc"]["major_concepts"],
                 "methods": d["doc"]["methods"],
                 "evidence_density": d["doc"]["evidence_density"]}
                for d in per_doc]
    cmap = build_corpus_map(corpus_id=CORPUS, document_summaries=map_docs,
                            procedures=all_procedures)

    canonical0 = {"corpus_id": CORPUS, "source_name": DOCS[0]["name"],
                  "media_type": "text/markdown",
                  "content_b64": base64_.b64encode(
                      DOCS[0]["text"].encode()).decode(), "config": {}}
    before = rcur.execute("SELECT count(*) FROM documents WHERE corpus_id=%s",
                          (CORPUS,)).fetchone()["count"]
    rr = submit_intake(wconn, canonical0)
    wconn.commit()
    after = rcur.execute("SELECT count(*) FROM documents WHERE corpus_id=%s",
                         (CORPUS,)).fetchone()["count"]

    report = {
        "documents_ingested": len(per_doc),
        "per_document": [{k: v for k, v in d.items() if k != "doc"}
                         for d in per_doc],
        "corpus_map": {
            "entities": [e["item"] for e in cmap.get("entities", [])][:14],
            "predicates": [p["item"] for p in cmap.get("predicates", [])][:10],
            "procedures": [p["item"] for p in cmap.get("procedures", [])],
            "typed_relations": cmap.get("typed_relations", [])[:8],
        },
        "dedup_idempotent": bool(rr["already_exists"]) and before == after,
        "total_facts": sum(d["facts"] for d in per_doc),
        "total_procedures": sum(d["procedure_steps"] > 0 for d in per_doc),
        "total_concepts": sum(d["concepts"] for d in per_doc),
    }
    conn.commit()
    conn.close()
    wconn.close()
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
