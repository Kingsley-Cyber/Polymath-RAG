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


def enrichment_contract_id(bounds) -> str:
    """ENRICH-IDENTITY-V2: the contract half of an enrichment's identity —
    compiler contract + output bounds. NEVER the lane: the lane is
    provenance (provider/model columns). With the lane inside the hash,
    every pin-group change re-sharded parents and re-enriched the whole
    corpus (measured 2026-09-02: 1,309 rows/day for 1,374 parents).
    scripts/migrate_enrichment_identity.py re-keys existing rows; keep its
    formula identical to this one."""
    # ENRICH-BUDGET-V2 (2026-09-02): the OUTPUT SHAPE is the contract; the
    # token budget is a serving knob (qualification 700 / production 900
    # produce the same valid object), so switching profiles must not
    # re-enrich a corpus either.
    shape = "/".join(str(getattr(bounds, f)) for f in (
        "summary_chars", "gist_chars", "abstraction_chars", "mechanism_chars",
        "affordance_chars", "question_chars", "max_mechanisms",
        "max_affordances", "max_questions", "gist_coverage_floor"))
    return f"{COMPILER_CONTRACT}|shape={shape}"


def input_hash_for(source_hash: str, contract_id: str) -> str:
    """Identity of one parent's enrichment: source content + prompt +
    contract id (see enrichment_contract_id). Same inputs, same contract,
    same answer — regardless of which lane produced it."""
    return content_hash({"source": source_hash,
                         "prompt": prompt_hash(),
                         "model": contract_id})


def persist_compiled_parent(conn, *, corpus_id: str, doc_id: str,
                            compiled: CompiledParent, input_hash: str,
                            provider: str, model: str) -> dict:
    """Persist ONE compiled parent. Idempotent on input_hash: an
    existing row for the same logical work is EXISTING, no new row.

    ENRICHMENT-ROW-TRUTH-V2 (measured 2026-09-05): a row whose parent
    chunk no longer exists (the document was deleted and re-ingested
    while a corpus sweep still held the old parents in memory — 184 rows
    landed 3 minutes AFTER the delete, 922 such orphans corpus-wide) is
    not evidence of anything: its gists point at dead child ids and no
    projection can reach it. An orphan never answers EXISTING; it is
    removed and the new parent's row takes its enrichment_id."""
    existing = conn.execute(
        """SELECT pe.enrichment_id, pe.status, pe.parent_id,
                  EXISTS (SELECT 1 FROM chunks c WHERE c.chunk_id = pe.parent_id) AS live
             FROM parent_enrichments pe
            WHERE pe.input_hash=%s AND pe.status = 'READY'""",
        (input_hash,)).fetchone()
    if existing and existing[3]:
        return {"status": "EXISTING", "enrichment_id": existing[0]}
    # an orphan row (READY or INVALID) under this identity gives way
    conn.execute(
        """DELETE FROM parent_enrichments pe
            WHERE pe.input_hash=%s
              AND NOT EXISTS (SELECT 1 FROM chunks c WHERE c.chunk_id = pe.parent_id)""",
        (input_hash,))
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
                   parent_id=EXCLUDED.parent_id, doc_id=EXCLUDED.doc_id,
                   corpus_id=EXCLUDED.corpus_id,
                   source_child_ids=EXCLUDED.source_child_ids,
                   summary=EXCLUDED.summary, children=EXCLUDED.children,
                   abstraction=EXCLUDED.abstraction,
                   mechanisms=EXCLUDED.mechanisms,
                   affordances=EXCLUDED.affordances,
                   questions=EXCLUDED.questions,
                   gist_coverage=EXCLUDED.gist_coverage,
                   provider=EXCLUDED.provider, model=EXCLUDED.model,
                   compiler_contract=EXCLUDED.compiler_contract,
                   prompt_version=EXCLUDED.prompt_version,
                   error_class=NULL, status='READY', superseded_at=NULL
               WHERE parent_enrichments.status='INVALID'""",
            (enrichment_id, compiled.parent_id, corpus_id, doc_id,
             compiled.source_child_ids, compiled.source_hash, input_hash,
             getattr(compiled, 'contract', None) or COMPILER_CONTRACT,
             provider, model,
             getattr(compiled, 'prompt_version', None) or PROMPT_VERSION,
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
           ON CONFLICT (enrichment_id) DO UPDATE SET
               parent_id=EXCLUDED.parent_id, doc_id=EXCLUDED.doc_id,
               corpus_id=EXCLUDED.corpus_id,
               source_child_ids=EXCLUDED.source_child_ids,
               error_class=EXCLUDED.error_class,
               provider=EXCLUDED.provider, model=EXCLUDED.model
             WHERE parent_enrichments.status='INVALID'""",
        (enrichment_id, compiled.parent_id, corpus_id, doc_id,
         compiled.source_child_ids, compiled.source_hash, input_hash,
         getattr(compiled, 'contract', None) or COMPILER_CONTRACT,
             provider, model,
             getattr(compiled, 'prompt_version', None) or PROMPT_VERSION,
         compiled.gist_coverage, compiled.error_class))
    return {"status": "INVALID", "enrichment_id": enrichment_id,
            "error_class": compiled.error_class}
