"""parent-enrichment persistence (plan §2.1, mirrors summary_runtime).

Receipts-as-commit-points: the artifact row + READY row + job COMPLETE
all commit in the caller's stage transaction. Staleness: a previous
READY row for the parent is marked STALE explicitly (history retained);
the projector deletes its points and flips STALE → INVALID."""
from __future__ import annotations

import json

from polymath_shared.identity import content_hash
from polymath_shared.latent.compiler import CompiledParent
from polymath_shared.latent.contract import COMPILER_CONTRACT
from polymath_shared.latent.prompt import PROMPT_VERSION, prompt_hash


def input_hash_for(source_hash: str, model_contract: str) -> str:
    return content_hash({"source": source_hash,
                         "prompt": prompt_hash(),
                         "model": model_contract})


def persist_compiled_parent(conn, *, corpus_id: str, doc_id: str,
                            compiled: CompiledParent, input_hash: str,
                            provider: str, model: str) -> dict:
    """Persist ONE compiled parent. Idempotent on input_hash: an
    existing row for the same logical work is EXISTING, no new row."""
    existing = conn.execute(
        "SELECT enrichment_id, status FROM parent_enrichments "
        "WHERE input_hash=%s AND status = 'READY'",
        (input_hash,)).fetchone()
    if existing:
        return {"status": "EXISTING", "enrichment_id": existing[0]}
    # an INVALID row with this input_hash does NOT block a retry — a
    # transient transport failure (429 storm, measured 2026-08-31) must
    # be recoverable by re-clicking the button; a successful retry
    # UPGRADES the same content-addressed row in place.

    enrichment_id = "penr_" + content_hash({"in": input_hash})[:32]
    if compiled.status == "READY" and compiled.output is not None:
        out = compiled.output
        # gists persist keyed by REAL chunk ids (the worker owns the map)
        children = [{"chunk_id": compiled.child_ref_map.get(g.ref, ""),
                     "ref": g.ref, "gist": g.gist}
                    for g in out.children]
        conn.execute(
            """UPDATE parent_enrichments SET status='STALE',
                      superseded_at=now()
                WHERE parent_id=%s AND status='READY'""",
            (compiled.parent_id,))
        conn.execute(
            """INSERT INTO parent_enrichments
               (enrichment_id, parent_id, corpus_id, doc_id,
                source_child_ids, source_hash, input_hash,
                compiler_contract, provider, model, prompt_version,
                summary, children, abstraction, mechanisms, affordances,
                questions, gist_coverage, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       'READY')
               ON CONFLICT (enrichment_id) DO UPDATE SET
                   summary=EXCLUDED.summary, children=EXCLUDED.children,
                   abstraction=EXCLUDED.abstraction,
                   mechanisms=EXCLUDED.mechanisms,
                   affordances=EXCLUDED.affordances,
                   questions=EXCLUDED.questions,
                   gist_coverage=EXCLUDED.gist_coverage,
                   provider=EXCLUDED.provider, model=EXCLUDED.model,
                   error_class=NULL, status='READY', superseded_at=NULL
               WHERE parent_enrichments.status='INVALID'""",
            (enrichment_id, compiled.parent_id, corpus_id, doc_id,
             compiled.source_child_ids, compiled.source_hash, input_hash,
             COMPILER_CONTRACT, provider, model, PROMPT_VERSION,
             out.summary, json.dumps(children), out.abstraction,
             json.dumps(out.mechanisms), json.dumps(out.affordances),
             json.dumps(out.questions), compiled.gist_coverage))
        return {"status": "READY", "enrichment_id": enrichment_id}

    conn.execute(
        """INSERT INTO parent_enrichments
           (enrichment_id, parent_id, corpus_id, doc_id, source_child_ids,
            source_hash, input_hash, compiler_contract, provider, model,
            prompt_version, gist_coverage, error_class, status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'INVALID')
           ON CONFLICT (enrichment_id) DO NOTHING""",
        (enrichment_id, compiled.parent_id, corpus_id, doc_id,
         compiled.source_child_ids, compiled.source_hash, input_hash,
         COMPILER_CONTRACT, provider, model, PROMPT_VERSION,
         compiled.gist_coverage, compiled.error_class))
    return {"status": "INVALID", "enrichment_id": enrichment_id,
            "error_class": compiled.error_class}
