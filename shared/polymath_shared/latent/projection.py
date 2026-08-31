"""Latent projection rows (plan §1.4): exactly two routing points per
READY enrichment — latent_abstraction and latent_transfer — into the
EXISTING routing collection, payload-filtered like every other kind.
chunk_id=None by design (CHUNK-SWEEP-SCOPE-V1 dependency, C5)."""
from __future__ import annotations

import json

from polymath_shared.latent.contract import (
    LATENT_KIND_ABSTRACTION,
    LATENT_KIND_TRANSFER,
)


def latent_point_id(enrichment_id: str, kind: str) -> str:
    return f"{enrichment_id}:{kind}"


def latent_rows(conn, run_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT pe.enrichment_id, pe.parent_id, pe.corpus_id, pe.doc_id,
               pe.abstraction, pe.mechanisms, pe.affordances, pe.questions,
               pe.source_hash, d.source_name
          FROM parent_enrichments pe
          JOIN runs r ON r.corpus_id = pe.corpus_id
          LEFT JOIN documents d ON d.doc_id = pe.doc_id
         WHERE r.run_id = %s AND pe.status = 'READY'
         ORDER BY pe.enrichment_id
        """,
        (run_id,),
    ).fetchall()
    out: list[dict] = []
    for (eid, pid, corpus, doc, abstraction, mech, aff, qs,
         shash, sname) in rows:
        mech = mech if isinstance(mech, list) else json.loads(mech or "[]")
        aff = aff if isinstance(aff, list) else json.loads(aff or "[]")
        qs = qs if isinstance(qs, list) else json.loads(qs or "[]")
        transfer_bits = []
        if mech:
            transfer_bits.append("Mechanisms: " + "; ".join(mech) + ".")
        if aff:
            transfer_bits.append("Useful for: " + "; ".join(aff) + ".")
        if qs:
            transfer_bits.append("Answers: " + " ".join(qs))
        for kind, text in ((LATENT_KIND_ABSTRACTION, abstraction),
                           (LATENT_KIND_TRANSFER,
                            " ".join(transfer_bits).strip())):
            if not text:
                continue
            out.append({
                "summary_id": latent_point_id(eid, kind),
                "representation_kind": kind,
                "text": text,
                "corpus_id": corpus,
                "doc_id": doc,
                "parent_id": pid,
                "source_name": sname or "",
                "enrichment_id": eid,
                "source_hash": shash,
            })
    return out


def stale_point_ids(conn, corpus_id: str) -> list[tuple[str, str]]:
    """(enrichment_id, point summary_id) for every STALE enrichment of
    the corpus — the projector deletes the points then flips the row to
    INVALID (history retained, store clean)."""
    rows = conn.execute(
        "SELECT enrichment_id FROM parent_enrichments "
        "WHERE corpus_id = %s AND status = 'STALE'",
        (corpus_id,)).fetchall()
    out = []
    for (eid,) in rows:
        for kind in (LATENT_KIND_ABSTRACTION, LATENT_KIND_TRANSFER):
            out.append((eid, latent_point_id(eid, kind)))
    return out
