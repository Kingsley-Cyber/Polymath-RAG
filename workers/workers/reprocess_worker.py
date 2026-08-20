"""S5 — SEMANTIC REPROCESSING (semantic-reprocess-v1).

A RE-DERIVATION, not another tuning phase. The persisted raw evidence is the
input authority; everything semantic downstream of it is recomputed:

    INPUT      persisted raw mentions
               persisted source chunks
               pinned syntax provider/model
               admission-harbor-v2 semantic bundle

    RECOMPUTE  syntax -> V2 admission -> canonical entity allocation
               -> antecedent inheritance -> concept convergence
               -> fact endpoint identities -> canonicalization
               -> Neo4j projection

    NEVER      GLiNER discovery (spans come from `mentions`, not the model)
               Qdrant text/chunk projections
               historical v1.1 replay state
               semantic rules

The stage imports no extractor client. Re-running discovery would make the
result depend on model availability rather than on persisted evidence, and
the whole point is that the same evidence in yields the same semantics out.
"""
from __future__ import annotations

import hashlib
import json

from psycopg import Connection

REPROCESS_CONTRACT = "semantic-reprocess-v1"


# --------------------------------------------------------------------------
# reconstruction — spans come from Postgres, never from a model
# --------------------------------------------------------------------------
def _child_chunks(conn: Connection, corpus_id: str) -> dict[str, list[dict]]:
    rows = conn.execute(
        """
        SELECT c.doc_id, c.chunk_id, c.text, c.chunk_index, c.layout_map
          FROM chunks c JOIN documents d ON d.doc_id = c.doc_id
         WHERE d.corpus_id = %s AND c.tier = 'child'
         ORDER BY c.doc_id, c.chunk_index
        """,
        (corpus_id,),
    ).fetchall()
    out: dict[str, list[dict]] = {}
    for doc_id, chunk_id, text, _idx, layout in rows:
        out.setdefault(doc_id, []).append(
            {"doc_id": doc_id, "chunk_id": chunk_id, "text": text,
             "layout_map": layout})
    return out


def _persisted_spans(conn: Connection, corpus_id: str) -> dict[str, list]:
    """Rebuild EntitySpan objects from the persisted mention rows.

    Ordered by span position so reconstruction is deterministic; two runs
    over the same rows must produce the same slice contents.
    """
    from polymath_shared.contracts import CoreType, EntitySpan

    rows = conn.execute(
        """
        SELECT doc_id, chunk_id, char_start, char_end, surface, core_type,
               gliner_score, extractor_version, raw_label, pass_kind
          FROM mentions
         WHERE corpus_id = %s
         ORDER BY doc_id, chunk_id, char_start, char_end, core_type
        """,
        (corpus_id,),
    ).fetchall()
    out: dict[str, list] = {}
    for r in rows:
        out.setdefault(r[1], []).append(EntitySpan(
            doc_id=r[0], chunk_id=r[1], start=r[2], end=r[3], text=r[4],
            core_type=CoreType(r[5]), score=r[6] or 0.0,
            extractor_version=r[7] or "reprocess", raw_label=r[8],
            pass_kind=r[9] or "discovery"))
    return out


class MissingSliceManifest(RuntimeError):
    """Raised when a document has no persisted interpreter view.

    Reprocessing without it would have to GUESS which slices extraction saw,
    and discourse resolution is context-sensitive: a narrower guess loses
    antecedents, a wider one invents them. Either way the re-derivation would
    no longer reproduce the interpretation, so it must refuse rather than
    approximate.
    """


def _slice_manifest(conn: Connection, doc_id: str) -> list[dict]:
    return [{"chunk_id": r[0], "chunk_start": r[1], "chunk_end": r[2]}
            for r in conn.execute(
                """
                SELECT chunk_id, chunk_start, chunk_end FROM sentence_slices
                 WHERE doc_id = %s AND in_context ORDER BY slice_index
                """, (doc_id,)).fetchall()]


def _ordered_slices_from_manifest(chunks: list[dict], manifest: list[dict],
                                  spans_by_chunk: dict[str, list]) -> list[tuple[dict, object]]:
    """SENTENCE-SLICE-MANIFEST-V1 — rebuild the EXACT interpreter view.

    Slice text is cut from the persisted chunk at the persisted offsets, so
    nothing is re-derived: not the sentence split, not slice membership, not
    the ordering the discourse consumer accumulated context in.
    """
    from workers.candidates import SentenceSlice

    by_id = {c["chunk_id"]: c for c in chunks}
    ordered: list[tuple[dict, object]] = []
    for idx, entry in enumerate(manifest):
        row = by_id.get(entry["chunk_id"])
        if row is None:
            continue
        start, end = entry["chunk_start"], entry["chunk_end"]
        spans = spans_by_chunk.get(entry["chunk_id"], [])
        ordered.append((row, SentenceSlice(
            text=row["text"][start:end], sentence_start=start, sentence_end=end,
            entities=[s for s in spans if s.start >= start and s.end <= end],
            evidence=[], parse=None, sentence_index=idx)))
    return ordered


def _ordered_slices_for_doc(chunks: list[dict], spans_by_chunk: dict[str, list],
                            corpus_id: str) -> list[tuple[dict, object]]:
    """LEGACY reconstruction, retained for documents with no manifest.

    Rebuild the document's sentences, keeping EVERY sentence.

    The extract stage builds slices only for sentences carrying a proposal or
    an evidence trigger, and those slices are what feed `discourse_context`.
    Reconstruction cannot reproduce that set — evidence-trigger placement is
    a GLiNER pass-2 result and is not persisted — and reconstructing only
    sentences that carry mentions produces a SMALLER context, which silently
    loses antecedents. Observed on i4: `The engineering group` resolved
    ANTECEDENT_RESOLVED during extraction and EXTERNAL_UNRESOLVED from a
    mentions-only reconstruction.

    Keeping every sentence is also the defensible reading on its own terms: a
    reference is resolved against what the document said before it, and what
    the document said does not depend on where an extractor happened to find
    trigger words in unrelated sentences.

    This is a SUPERSET of the extract stage's slice set, so it cannot be
    PROVEN identical in general. Making the two provably agree means
    persisting the slice set at extraction time, which is an extract-stage
    change and is not authorized inside S5.
    """
    from workers.candidates import SentenceSlice
    from workers.extract_worker import _sentences_of

    ordered: list[tuple[dict, object]] = []
    for row in chunks:
        spans = spans_by_chunk.get(row["chunk_id"], [])
        sentences = _sentences_of(row["text"])
        for idx, (text, (start, end)) in enumerate(
                zip(sentences.texts, sentences.offsets)):
            ordered.append((row, SentenceSlice(
                text=text, sentence_start=start, sentence_end=end,
                entities=[s for s in spans if s.start >= start and s.end <= end],
                evidence=[], parse=None, sentence_index=idx)))
    return ordered


# --------------------------------------------------------------------------
# authoritative semantic state — what invariant 10 compares
# --------------------------------------------------------------------------
def semantic_state_hash(conn: Connection, corpus_id: str) -> str:
    """Content hash of the AUTHORITATIVE semantic state for a corpus.

    Deliberately excludes anything a replay may legitimately vary (timestamps,
    receipt ids) and includes everything a replay must not: mention
    interpretation, identity, entity rows, fact endpoints, canonical
    membership.
    """
    h = hashlib.sha256()
    for sql, params in (
        ("""SELECT mention_id, COALESCE(entity_id,''), COALESCE(admission_class,''),
                   COALESCE(anchor_kind,''), COALESCE(decision_status,''),
                   COALESCE(reference_basis,''), COALESCE(referential_surface,''),
                   COALESCE(semantic_contract,'')
              FROM mentions WHERE corpus_id=%s ORDER BY mention_id""", (corpus_id,)),
        ("""SELECT DISTINCT e.entity_id, e.core_type, e.normalized_surface,
                   COALESCE(e.admission_class,'')
              FROM entities e JOIN mentions m ON m.entity_id = e.entity_id
             WHERE m.corpus_id=%s ORDER BY 1""", (corpus_id,)),
        ("""SELECT f.fact_id, f.predicate, f.subject_id, f.object_id
              FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id
              JOIN documents d ON d.doc_id=ev.doc_id
             WHERE d.corpus_id=%s ORDER BY f.fact_id""", (corpus_id,)),
        ("""SELECT canonical_id, local_entity_id, decision
              FROM canonical_memberships WHERE corpus_id=%s
             ORDER BY canonical_id, local_entity_id""", (corpus_id,)),
    ):
        for row in conn.execute(sql, params).fetchall():
            h.update(repr(row).encode())
            h.update(b"\x1e")
    return h.hexdigest()


def _fact_state(conn: Connection, corpus_id: str) -> dict:
    """Per fact: predicate, endpoints, and whether both endpoints are eligible."""
    rows = conn.execute(
        """
        SELECT f.fact_id, f.predicate, f.subject_id, f.object_id,
               s.admission_class, o.admission_class
          FROM facts f
          JOIN evidence ev ON ev.fact_id = f.fact_id
          JOIN documents d ON d.doc_id = ev.doc_id
          LEFT JOIN entities s ON s.entity_id = f.subject_id
          LEFT JOIN entities o ON o.entity_id = f.object_id
         WHERE d.corpus_id = %s
        """,
        (corpus_id,),
    ).fetchall()
    from polymath_shared.neo4j_eligibility import fact_eligible_from_classes

    return {r[0]: {"predicate": r[1], "subject_id": r[2], "object_id": r[3],
                   "eligible": fact_eligible_from_classes(r[4], r[5])}
            for r in rows}


# --------------------------------------------------------------------------
# old -> new fact classification. UNEXPLAINED must be zero.
# --------------------------------------------------------------------------
CLASSES = ("UNCHANGED_SEMANTICS", "ENDPOINT_REIDENTIFIED", "REMOVED_BY_HARBOR",
           "CANONICAL_MERGE", "NEWLY_ELIGIBLE", "PREDICATE_CHANGED",
           "UNEXPLAINED")


def classify_fact_deltas(before: dict, after: dict) -> dict:
    """Explain every fact's transition, or refuse to.

    UNEXPLAINED is not a catch-all bucket to be tolerated — it is the signal
    that the re-derivation did something the model of it does not cover, and
    a nonzero count means S5 must stop rather than be interpreted.
    """
    # A merge is a GLOBAL property: two distinct old endpoint identities
    # arriving at one new identity. It cannot be seen one fact at a time.
    collapsed: dict[str, set] = {}
    for fid, old in before.items():
        new = after.get(fid)
        if not new:
            continue
        for side in ("subject_id", "object_id"):
            collapsed.setdefault(new[side], set()).add(old[side])
    merged_targets = {nid for nid, olds in collapsed.items() if len(olds) > 1}

    counts = {c: 0 for c in CLASSES}
    detail: dict[str, list] = {c: [] for c in CLASSES}

    for fid, old in before.items():
        new = after.get(fid)
        if new is None:
            # the fact row itself is gone: only legitimate when Harbor made
            # it non-canonical, which the residue reconciler then removed
            counts["REMOVED_BY_HARBOR"] += 1
            detail["REMOVED_BY_HARBOR"].append({"fact_id": fid, "reason": "row removed"})
            continue

        moved = (old["subject_id"] != new["subject_id"]
                 or old["object_id"] != new["object_id"])
        if old["predicate"] != new["predicate"]:
            cls = "PREDICATE_CHANGED"
        elif old["eligible"] and not new["eligible"]:
            cls = "REMOVED_BY_HARBOR"
        elif not old["eligible"] and new["eligible"]:
            cls = "NEWLY_ELIGIBLE"
        elif not moved:
            cls = "UNCHANGED_SEMANTICS"
        elif (new["subject_id"] in merged_targets
              or new["object_id"] in merged_targets):
            cls = "CANONICAL_MERGE"
        elif moved:
            cls = "ENDPOINT_REIDENTIFIED"
        else:
            cls = "UNEXPLAINED"
        counts[cls] += 1
        if len(detail[cls]) < 12:
            detail[cls].append({
                "fact_id": fid, "predicate": new["predicate"],
                "subject": [old["subject_id"][:16], new["subject_id"][:16]],
                "object": [old["object_id"][:16], new["object_id"][:16]]})

    for fid in set(after) - set(before):
        counts["UNEXPLAINED"] += 1
        detail["UNEXPLAINED"].append({"fact_id": fid, "reason": "appeared during reprocessing"})

    return {"counts": counts, "detail": detail}


# --------------------------------------------------------------------------
# the reprocessing pass
# --------------------------------------------------------------------------
def reprocess_corpus(conn: Connection, corpus_id: str, *,
                     apply: bool = False) -> dict:
    """Re-derive the corpus's V2 semantic state from persisted raw evidence."""
    from polymath_shared.execution import SEMANTIC_CONTRACT_V2, semantic_authority_sha256
    from polymath_shared.identity_allocation import (
        normalized_for_lookup, span_identity_key,
    )
    from workers.extract_worker import _allocate_identities, _syntax_evidence

    report = {"contract": REPROCESS_CONTRACT, "corpus_id": corpus_id,
              "applied": apply,
              "semantic_bundle": semantic_authority_sha256(),
              "docs": 0, "mentions_reinterpreted": 0,
              "state_hash_before": semantic_state_hash(conn, corpus_id)}
    before = _fact_state(conn, corpus_id)

    chunks_by_doc = _child_chunks(conn, corpus_id)
    spans_by_chunk = _persisted_spans(conn, corpus_id)
    identities: dict = {}

    for doc_id in sorted(chunks_by_doc):
        manifest = _slice_manifest(conn, doc_id)
        if not manifest:
            raise MissingSliceManifest(
                f"{doc_id} has no sentence-slice manifest. Reprocessing must "
                "consume the view extraction recorded, not reconstruct one: "
                "discourse resolution is context-sensitive, so a guessed "
                "context changes the interpretation it is meant to reproduce. "
                "Re-ingest the document under sentence-slice-manifest-v1.")
        ordered = _ordered_slices_from_manifest(
            chunks_by_doc[doc_id], manifest, spans_by_chunk)
        if not ordered:
            continue
        # Syntax is REGENERATED, not read back: it is a pure function of the
        # pinned provider/model over the same sentence text, so regenerating
        # keeps the run reproducible without storing a parse per sentence.
        _syntax_evidence(ordered)
        identities.update(_allocate_identities(
            ordered, corpus_id, doc_id, contract_version=SEMANTIC_CONTRACT_V2))
        report["docs"] += 1

    report["mentions_reinterpreted"] = len(identities)
    if not apply:
        report["state_hash_after"] = report["state_hash_before"]
        return report

    # ---- rewrite mention interpretation + identity -------------------------
    for (c_id, doc_id, chunk_id, start, end, core), ident in identities.items():
        a = ident.admission
        conn.execute(
            """
            UPDATE mentions
               SET entity_id = %s, admission_class = %s, proposal_surface = %s,
                   referential_surface = %s, anchor_kind = %s,
                   decision_status = %s, reference_basis = %s,
                   admission_reason = %s, semantic_contract = %s
             WHERE corpus_id = %s AND doc_id = %s AND chunk_id = %s
               AND char_start = %s AND char_end = %s AND core_type = %s
            """,
            (ident.entity_id if ident.durable else None, ident.admission_class,
             a.proposal_surface, a.referential_surface, a.anchor_kind,
             a.decision_status, a.reference_basis, a.admission_reason,
             a.semantic_contract, c_id, doc_id, chunk_id, start, end, core),
        )
        # Only the ANCHOR that owns an identity may describe it. A resolved
        # reference inherits the anchor's entity_id (row 48) but keeps its own
        # DOCUMENT_SCOPED scope, so letting it write would restamp a GLOBAL
        # anchor as document-scoped — an `ent_` id describing itself as
        # something that could never have produced an `ent_` id.
        if ident.durable and a.reference_basis != "ANTECEDENT_RESOLVED":
            conn.execute(
                """
                INSERT INTO entities (entity_id, core_type, normalized_surface,
                                      admission_class)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (entity_id) DO UPDATE
                    SET admission_class = EXCLUDED.admission_class
                """,
                (ident.entity_id, core, normalized_for_lookup(a.proposal_surface),
                 ident.admission_class),
            )

    # ---- re-identify fact endpoints from their evidence spans --------------
    unresolved = _reidentify_fact_endpoints(conn, corpus_id, identities)
    report["fact_endpoints_unresolved"] = unresolved
    conn.commit()

    report["state_hash_after"] = semantic_state_hash(conn, corpus_id)
    report["fact_deltas"] = classify_fact_deltas(before, _fact_state(conn, corpus_id))
    return report


def _reidentify_fact_endpoints(conn: Connection, corpus_id: str,
                               identities: dict) -> list[dict]:
    """Point each fact at the identity its own evidence span now carries.

    The link is the persisted span, not the old id: `evidence.span_offsets`
    records exactly which characters the subject and object occupied, so the
    endpoint can be re-derived from the same evidence the fact was built on.
    Guessing from the OLD entity id would carry v1.1 identity forward, which
    invariant 4 forbids.
    """
    rows = conn.execute(
        """
        SELECT f.fact_id, f.subject_id, f.object_id, ev.doc_id, ev.chunk_id,
               ev.span_offsets
          FROM facts f
          JOIN evidence ev ON ev.fact_id = f.fact_id
          JOIN documents d ON d.doc_id = ev.doc_id
         WHERE d.corpus_id = %s
        """,
        (corpus_id,),
    ).fetchall()

    core_of = {}
    for r in conn.execute(
        "SELECT doc_id, chunk_id, char_start, char_end, core_type FROM mentions "
        "WHERE corpus_id = %s", (corpus_id,)).fetchall():
        core_of[(r[0], r[1], r[2], r[3])] = r[4]

    unresolved: list[dict] = []
    for fact_id, subj_old, obj_old, doc_id, chunk_id, offsets in rows:
        off = offsets if isinstance(offsets, dict) else json.loads(offsets or "{}")
        new_ids = {}
        for side, s_key, e_key in (("subject", "subject_start", "subject_end"),
                                   ("object", "object_start", "object_end")):
            s, e = off.get(s_key), off.get(e_key)
            core = core_of.get((doc_id, chunk_id, s, e))
            if core is None:
                unresolved.append({"fact_id": fact_id, "side": side,
                                   "span": [s, e], "chunk_id": chunk_id})
                continue
            ident = identities.get((corpus_id, doc_id, chunk_id, s, e, core))
            if ident is None:
                unresolved.append({"fact_id": fact_id, "side": side,
                                   "span": [s, e], "reason": "no admission"})
                continue
            new_ids[side] = ident.entity_id
        if len(new_ids) == 2:
            conn.execute(
                "UPDATE facts SET subject_id = %s, object_id = %s WHERE fact_id = %s",
                (new_ids["subject"], new_ids["object"], fact_id))
    return unresolved
