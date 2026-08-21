"""V5 L1 — raw evidence capture (evidence plumbing, NOT a semantic authority).

This module records what the provider said; it decides nothing. It is
deliberately NOT in `_SEMANTIC_AUTHORITY_MODULES`: adding it must not move
the semantic bundle hash, and a qualification gate asserts exactly that.

    Filtering decides what becomes knowledge.
    Filtering never decides whether observed evidence survives.
"""
from __future__ import annotations

from typing import Any

from polymath_shared.identity import content_hash

RAW_EVIDENCE_CONTRACT = "raw-evidence-ledger-v1"


def provider_contract(*, provider: str, model_id: str, revision: str,
                      task: str, threshold: float, labels: list[str]) -> dict:
    return {
        "contract": RAW_EVIDENCE_CONTRACT,
        "provider": provider,
        "model_id": model_id,
        "revision": revision,
        "task": task,
        "threshold": threshold,
        "labels_sha256": content_hash({"labels": sorted(labels)}),
    }


def proposal_row(doc_id: str, chunk_id: str, item: dict, contract: dict) -> tuple:
    """One raw span exactly as the provider returned it. The id is
    content-addressed over everything that identifies the OBSERVATION —
    including the provider contract — so the same observation replayed lands
    on the same primary key, and a changed provider/labels/threshold yields
    new rows instead of silently overwriting history."""
    pid = "rawent_" + content_hash({
        "doc": doc_id, "chunk": chunk_id,
        "start": item["start"], "end": item["end"],
        "surface": item["text"], "label": item["label"],
        "score": round(float(item["score"]), 6),
        "provider": contract["labels_sha256"] + contract["revision"] + contract["task"],
    })
    import json
    return (pid, doc_id, chunk_id, int(item["start"]), int(item["end"]),
            item["text"], item["label"], float(item["score"]),
            json.dumps(contract, sort_keys=True))


def evidence_row(doc_id: str, chunk_id: str, item: dict, contract: dict) -> tuple:
    row = proposal_row(doc_id, chunk_id, item, contract)
    return ("rawev_" + row[0][len("rawent_"):],) + row[1:]


_INSERT = {
    "raw_entity_proposals":
        "INSERT INTO raw_entity_proposals (proposal_id, doc_id, chunk_id,"
        " char_start, char_end, surface, provider_label, provider_score,"
        " provider_contract) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        " ON CONFLICT (proposal_id) DO NOTHING",
    "raw_predicate_evidence":
        "INSERT INTO raw_predicate_evidence (evidence_id, doc_id, chunk_id,"
        " char_start, char_end, surface, provider_label, provider_score,"
        " provider_contract) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        " ON CONFLICT (evidence_id) DO NOTHING",
}


def bulk_write(conn: Any, table: str, rows: list[tuple]) -> int:
    """Idempotent bulk insert inside the caller's stage transaction, so raw
    evidence commits with the stage receipt and rolls back with the stage."""
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(_INSERT[table], rows)
    return len(rows)


def ledger_hash(conn: Any, doc_ids: list[str]) -> dict:
    """Deterministic content hash of a document set's L1 ledger, for
    replay/qualification comparison. Excludes created_at by construction."""
    out = {}
    for table, idcol in (("raw_entity_proposals", "proposal_id"),
                         ("raw_predicate_evidence", "evidence_id")):
        rows = conn.execute(
            f"SELECT {idcol} FROM {table} WHERE doc_id = ANY(%s) ORDER BY {idcol}",
            (doc_ids,)).fetchall()
        out[table] = {"count": len(rows),
                      "sha256": content_hash({"ids": [r[0] for r in rows]})}
    return out


def hypothesis_row(doc_id: str, h: dict) -> tuple:
    """One rescue decision as an L2 record. Ids are content-addressed over
    the decision's identifying content, so replays are idempotent."""
    import json
    hid = "hyp_" + content_hash({
        "doc": doc_id, "chunk": h["chunk_id"], "mechanism": h["mechanism"],
        "src": [h.get("source_char_start"), h.get("source_char_end")],
        "dst": [h["proposed_char_start"], h["proposed_char_end"]],
        "surface": h["proposed_surface"], "status": h["status"],
    })
    return (hid, doc_id, h["chunk_id"], h["mechanism"],
            h.get("source_char_start"), h.get("source_char_end"),
            h.get("source_surface"),
            h["proposed_char_start"], h["proposed_char_end"],
            h["proposed_surface"], h["status"], h["disposition"],
            json.dumps(h.get("evidence") or {}, sort_keys=True))


_INSERT["span_hypotheses"] = (
    "INSERT INTO span_hypotheses (hypothesis_id, doc_id, chunk_id, mechanism,"
    " source_char_start, source_char_end, source_surface, proposed_char_start,"
    " proposed_char_end, proposed_surface, status, disposition, evidence)"
    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    " ON CONFLICT (hypothesis_id) DO NOTHING")
