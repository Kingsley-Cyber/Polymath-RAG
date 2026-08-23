"""SUMMARY RUNTIME D4: corpus mapping worker (the navigation map).

Answers "what does this corpus contain?" — never "what is true?"
(truth remains Evidence -> Fact Admission -> Fact Ledger).

Input contract: document_summaries ONLY. Batch-triggered by refresh
policy — never one rebuild per document. Weighted composition:
concept weight = document spread + occurrences (+ evidence density);
entity importance adds fact_degree. Every field carries
source_document_summary_ids provenance.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from polymath_shared.identity import content_hash
from polymath_shared.summary_layer import build_envelope


def _claim(conn, ticket_id: str, worker_id: str) -> bool:
    cur = conn.execute(
        "UPDATE summary_jobs SET state='RUNNING', worker_id=%s "
        "WHERE ticket_id=%s AND state IN ('READY','RETRY_WAIT')",
        (worker_id, ticket_id))
    return cur.rowcount == 1

CORPUS_MAPPING_THRESHOLD_DOCS = 100
CORPUS_MAPPING_DEBOUNCE_MINUTES = 30


def corpus_refresh_policy(*, completed_documents: int, last_run_at,
                          now, threshold: int =
                          CORPUS_MAPPING_THRESHOLD_DOCS,
                          debounce_minutes: int =
                          CORPUS_MAPPING_DEBOUNCE_MINUTES,
                          force: bool = False) -> tuple[bool, str]:
    if force:
        return True, "manual_rebuild"
    if completed_documents >= threshold:
        return True, "document_count_threshold"
    if completed_documents > 0 and last_run_at is not None:
        elapsed = (now - last_run_at).total_seconds() / 60.0
        if elapsed >= debounce_minutes:
            return True, "scheduled_refresh"
    return False, "policy_deferred"


def _weighted(per_doc, fact_degrees, top_n):
    docs = defaultdict(set)
    count = Counter()
    for dsid, items in per_doc:
        for item in items or []:
            docs[item].add(dsid)
            count[item] += 1
    ranked = []
    for item, c in count.most_common():
        spread = len(docs[item])
        score = round(2 * spread + c + (fact_degrees or {}).get(item, 0), 3)
        ranked.append({"item": item, "weight": score,
                       "document_spread": spread, "occurrences": c,
                       "source_document_summary_ids": sorted(docs[item])})
    return ranked[:top_n]


def build_corpus_map(*, corpus_id: str, document_summaries: list[dict],
                     fact_degrees: dict | None = None,
                     top_n: int = 10) -> dict:
    ent_per_doc = [(r["summary_id"], r.get("major_entities") or [])
                   for r in document_summaries]
    cpt_per_doc = [(r["summary_id"], r.get("major_concepts") or [])
                   for r in document_summaries]
    pred_per_doc = [(r["summary_id"], r.get("methods") or [])
                    for r in document_summaries]

    entities = _weighted(ent_per_doc, fact_degrees, top_n)
    concepts = _weighted(cpt_per_doc, None, top_n)
    predicates = _weighted(pred_per_doc, None, 8)

    clusters = defaultdict(list)
    for r in document_summaries:
        cpts = r.get("major_concepts") or []
        if cpts:
            clusters[f"{cpts[0]} cluster"].append(r["summary_id"])

    return {
        "corpus_id": corpus_id,
        "concepts": concepts,
        "entities": entities,
        "predicates": [{"item": p["item"], "count": p["occurrences"],
                        "source_document_summary_ids":
                            p["source_document_summary_ids"]}
                       for p in predicates],
        "document_clusters": [{"label": label,
                               "document_summary_ids": ids}
                              for label, ids in sorted(clusters.items())],
    }

# --- worker (appended below by D4 wiring) ---

def run_corpus_mapping_ticket(conn, *, ticket_id: str, corpus_id: str,
                              input_hash: str, contract_version: str,
                              worker_id: str,
                              fact_degrees: dict | None = None):
    if not _claim(conn, ticket_id, worker_id):
        return {"status": "SKIPPED_NOT_CLAIMABLE"}
    existing = conn.execute(
        "SELECT artifact_id FROM summary_artifacts WHERE input_hash=%s",
        (input_hash,)).fetchone()
    if existing:
        conn.execute("UPDATE summary_jobs SET state='COMPLETE', "
                     "completed_at=now() WHERE ticket_id=%s", (ticket_id,))
        return {"status": "EXISTING", "artifact_id": existing[0]}
    rows = [dict(zip(("summary_id", "major_entities", "major_concepts",
                      "methods"), r)) for r in conn.execute(
        """SELECT summary_id, major_entities, major_concepts, methods
           FROM document_summaries WHERE corpus_id=%s""",
        (corpus_id,)).fetchall()]
    cmap = build_corpus_map(corpus_id=corpus_id, document_summaries=rows,
                            fact_degrees=fact_degrees)
    payload = {"summary_type": "corpus", **cmap}
    from polymath_shared.summary_layer import build_envelope
    env = build_envelope(derived_from=[r["summary_id"] for r in rows],
                         payload=payload)
    artifact_id = "csa_" + content_hash({"in": input_hash})[:32]
    conn.execute(
        """INSERT INTO summary_artifacts (artifact_id, input_hash,
           output_hash, stage, corpus_id, contract_version,
           created_by_worker, source_ids, payload)
           VALUES (%s,%s,%s,'CORPUS_MAPPING',%s,%s,%s,%s,%s)
           ON CONFLICT (input_hash) DO NOTHING""",
        (artifact_id, input_hash, env["output_hash"], corpus_id,
         contract_version, worker_id,
         [r["summary_id"] for r in rows],
         __import__("json").dumps({"envelope": env})))
    conn.execute(
        """INSERT INTO corpus_summaries (summary_id, corpus_id,
           artifact_hash, contract_version, created_by_worker, source_ids,
           important_entities, dominant_concepts, common_predicates,
           document_clusters)
           VALUES (%s,%s,%s,%s,%s,%s,%s::text[],%s::text[],%s::text[],%s)""",
        (env["artifact_id"], corpus_id, env["output_hash"],
         contract_version, worker_id,
         [r["summary_id"] for r in rows],
         [e["item"] for e in cmap["entities"]][:10],
         [c["item"] for c in cmap["concepts"]][:10],
         [p["item"] for p in cmap["predicates"]],
         __import__("json").dumps(cmap["document_clusters"])))
    conn.execute("UPDATE summary_jobs SET state='COMPLETE', "
                 "completed_at=now() WHERE ticket_id=%s", (ticket_id,))
    return {"status": "COMPLETE", "artifact_id": artifact_id,
            "output_hash": env["output_hash"]}
