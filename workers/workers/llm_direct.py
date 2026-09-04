"""LLM-DIRECT-FACTS-V1 — gated LLM relations become facts (owner 2026-08-30).

The predicate compiler / admission-harbor chain was built to adjudicate
GLiNER + spaCy proposals. LLM extraction is a one-shot process: every
relation that reaches this module is already (a) verbatim-attested by the
gate (subject, object and quote are exact source substrings) and (b)
typed with one of the 17 ontology predicates (+RELATED_TO). Running a
second authority over it only discarded it — MEASURED on the 2026-08-30
re-ingest: 283 gated relations → 3 admitted facts.

What this module does, deterministically, in the same tables the
projections already consume (no downstream change):

  entities   entity_id = identity.entity_id(core_type, normalized surface)
             — the same identity every other writer uses, so a surface
             seen in two documents of a corpus lands on ONE entity row;
             `core_type` is part of the key, which is what keeps two
             different things with the same name apart. Cross-corpus and
             alias merging stay the canonicalize stage's job.
  mentions   one row per attested entity mention (exact offsets), carrying
             corpus_id + doc_id — the per-document provenance the owner
             asked for.
  facts      fact_id = identity.fact_id(predicate, subject_id, object_id, {})
             — the SAME fact extracted from three documents is one row with
             three evidence rows (cross-document aggregation by identity).
             Symmetric predicates (CORRELATES_WITH, ALTERNATIVE_TO,
             SAME_AS, RELATED_TO) are endpoint-ordered so A↔B and B↔A
             aggregate.
  evidence   exact-evidence-v1 span offsets (quote + endpoint offsets,
             chunk-relative), one per (fact, document, chunk, quote).

Nothing here is a filter: the gate decides what is attested; this module
persists everything the gate passed. Rejections stay in the artifact.
"""
from __future__ import annotations

import json
from typing import Callable

from polymath_shared.identity import content_hash, entity_id as _entity_id
from polymath_shared.identity import evidence_id as _evidence_id
from polymath_shared.identity import fact_id as _fact_id
from polymath_shared.identity_allocation import normalized_for_lookup
from polymath_shared.llm_extraction.gate import (
    ChunkView,
    NormalizedExtraction,
    _find_exact,
    _locate,
    map_core_type,
)
from polymath_shared.llm_extraction.ontology import RELATION_ONTOLOGY
from polymath_shared.query_policy import QUERY_POLICY_VERSION

CONTRACT = "llm-direct-facts-v1"
# GENERATION-STAMPING-V1 (§11 L0): the indexable generation id on
# entities.extractor_version / facts.extractor_version. The provenance
# JSON keeps the full stamp (contract, lane, model, bundle hash).
from polymath_shared.entity_admission import is_unresolved_pronoun

EXTRACTOR_VERSION = "llm-direct-v1"
RULE_ID = "llm-relation-v1"
RULE_VERSION = "relation-ontology-v1"
ADMISSION_CLASS = "CORPUS_SCOPED"
ENTITY_VERSION = "polymath-extraction-v1-entity"
EVIDENCE_VERSION = "polymath-extraction-v1-evidence"
PROVENANCE_CONTRACT = "exact-evidence-v1"
SYMMETRIC_PREDICATES = frozenset({"CORRELATES_WITH", "ALTERNATIVE_TO", "SAME_AS", "RELATED_TO"})


def _mention_id(doc_id: str, chunk_id: str, core: str, start: int, end: int) -> str:
    return "mention_" + content_hash({"doc": doc_id, "chunk": chunk_id, "type": core,
                                      "start": start, "end": end})


def _endpoint_offsets(surface: str, view: ChunkView, quote: tuple[int, int]) -> tuple[int, int]:
    """Endpoint offsets INSIDE the attested quote when present there,
    else the first attested occurrence in the chunk (the gate already
    guaranteed one exists)."""
    inside = _find_exact(surface, view.text[quote[0]:quote[1]])
    if inside:
        return quote[0] + inside[0], quote[0] + inside[1]
    hit = _locate(surface, view)
    return hit if hit else (quote[0], quote[1])


def materialize(conn, *, corpus_id: str, doc_id: str, chunk_rows: dict[str, dict],
                merged: NormalizedExtraction, lane: str, model: str,
                stamp: Callable[[dict], dict] | None = None) -> dict:
    """Persist gated entities/relations for ONE document. Idempotent: every
    id is content-derived and every insert is ON CONFLICT DO NOTHING, so a
    replay writes zero rows. Returns counts for the stage artifact."""
    stamp = stamp or (lambda p: p)
    bundle_hash = stamp({}).get("generated_by_bundle_hash")
    ent_rows: dict[str, tuple] = {}
    raw_types_by_eid: dict[str, set[str]] = {}
    mention_rows: dict[str, tuple] = {}
    fact_rows: dict[str, tuple] = {}
    evidence_rows: dict[str, tuple] = {}
    type_by_surface: dict[str, str] = {}
    type_by_norm: dict[str, str] = {}
    unknown_predicates = 0
    endpoint_levels: dict[str, int] = {}
    # LLM-DIRECT-PRONOUN-GATE-V1 (2026-09-02): an unresolved closed-class
    # pronoun is evidence, never durable knowledge (fact_admission R-pronoun).
    # The GLiNER-era path enforced it in entity admission; the llm-direct
    # path wrote 13 ACCEPT facts with 'me'/'we'/'you'/'i' endpoints.
    pronoun_entities_dropped = 0
    pronoun_endpoints_dropped = 0

    # -- entities + mentions -------------------------------------------------
    for cid, items in merged.entities_by_chunk.items():
        row = chunk_rows.get(cid)
        if row is None:
            continue
        for e in items:
            core = e["label"]
            surface = e["text"]
            if is_unresolved_pronoun(surface):
                pronoun_entities_dropped += 1
                continue
            type_by_surface.setdefault(surface, core)
            norm = normalized_for_lookup(surface)
            type_by_norm.setdefault(norm, core)
            eid = _entity_id(core, norm)
            ent_rows.setdefault(eid, (eid, core, norm, ADMISSION_CLASS, doc_id))
            if e.get("raw_type"):
                raw_types_by_eid.setdefault(eid, set()).add(str(e["raw_type"]))
            mid = _mention_id(doc_id, cid, core, e["start"], e["end"])
            mention_rows.setdefault(mid, (
                mid, corpus_id, doc_id, cid, int(e["start"]), int(e["end"]), surface, norm,
                core, float(e.get("score", 1.0)), ENTITY_VERSION, ADMISSION_CLASS, eid,
                e.get("raw_type"), QUERY_POLICY_VERSION, "llm", surface, surface,
                "ATTESTED_QUOTE", "ADMITTED", "ATTESTED_QUOTE", CONTRACT, CONTRACT))

    # -- facts + evidence ----------------------------------------------------
    views: dict[str, ChunkView] = {}
    for cid, items in merged.evidence_by_chunk.items():
        row = chunk_rows.get(cid)
        if row is None:
            continue
        view = views.setdefault(cid, ChunkView(cid, row["text"]))
        for ev in items:
            pred = str(ev["predicate"]).upper()
            if pred not in RELATION_ONTOLOGY:
                unknown_predicates += 1      # the gate normalizes; this is a guard, never expected
                continue
            subj_s, obj_s = ev["subject"], ev["object"]
            if is_unresolved_pronoun(subj_s) or is_unresolved_pronoun(obj_s):
                pronoun_endpoints_dropped += 1
                continue
            # ATTESTATION-LEVELS-V1: an endpoint that was never placed as an
            # entity (cross-chunk / abstract) takes the type of the same
            # surface wherever it WAS placed; otherwise Concept. (The old
            # fallback routed the SURFACE through the TYPE mapper.)
            subj_core = (type_by_surface.get(subj_s)
                         or type_by_norm.get(normalized_for_lookup(subj_s)) or "Concept")
            obj_core = (type_by_surface.get(obj_s)
                        or type_by_norm.get(normalized_for_lookup(obj_s)) or "Concept")
            att = ev.get("attestation") or {}
            for lvl in att.values():
                if lvl:
                    endpoint_levels[lvl] = endpoint_levels.get(lvl, 0) + 1
            sid = _entity_id(subj_core, normalized_for_lookup(subj_s))
            oid = _entity_id(obj_core, normalized_for_lookup(obj_s))
            if pred in SYMMETRIC_PREDICATES and oid < sid:
                sid, oid = oid, sid
                subj_s, obj_s = obj_s, subj_s
                subj_core, obj_core = obj_core, subj_core
            for eid, core, surface in ((sid, subj_core, subj_s), (oid, obj_core, obj_s)):
                ent_rows.setdefault(eid, (eid, core, normalized_for_lookup(surface),
                                          ADMISSION_CLASS, doc_id))
            fid = _fact_id(pred, sid, oid, {})
            provenance = stamp({
                "contract": CONTRACT, "lane": lane, "model": model,
                "predicate_raw": ev.get("predicate_raw"),
                "predicate_method": ev.get("predicate_method"),
                "gate": "polymath-extraction-v1",
                "gate_version": "attestation-levels-v1",
                "endpoint_attestation": att or None,
            })
            # TYPED-CLAIMS-V1: the claim kind lives in qualifiers (jsonb); the
            # fact id ignores it, so a typed re-extraction enriches the same fact.
            qualifiers = json.dumps({"claim_kind": ev["claim_kind"]}) if ev.get("claim_kind") else "{}"
            fact_rows.setdefault(fid, (
                fid, pred, sid, oid, qualifiers, "ACCEPT", RULE_ID, RULE_VERSION,
                json.dumps(provenance, sort_keys=True), EXTRACTOR_VERSION))
            quote = (int(ev["start"]), int(ev["end"]))
            s_off = _endpoint_offsets(subj_s, view, quote)
            o_off = _endpoint_offsets(obj_s, view, quote)
            offsets = {
                "provenance_contract": PROVENANCE_CONTRACT,
                "chunk_char_start": int(row.get("char_start") or 0),
                "chunk_char_end": int(row.get("char_end") or 0),
                "sentence_index": 0,
                "evidence_surface": ev["text"],
                "evidence_start": quote[0], "evidence_end": quote[1],
                "trigger_lemma": None,
                "subject_surface": subj_s, "subject_start": s_off[0], "subject_end": s_off[1],
                "object_surface": obj_s, "object_start": o_off[0], "object_end": o_off[1],
                "predicate_raw": ev.get("predicate_raw"),
                "predicate_method": ev.get("predicate_method"),
                "endpoint_attestation": att or None,
            }
            evid = _evidence_id(fid, doc_id, cid,
                                {"chunk": int(row.get("char_start") or 0), "quote": list(quote)},
                                RULE_ID)
            evidence_rows.setdefault(evid, (
                evid, fid, doc_id, cid, json.dumps(offsets, sort_keys=True), RULE_ID, "{}",
                EVIDENCE_VERSION, RULE_VERSION, PROVENANCE_CONTRACT))

    # -- writes (entities first: facts carry FKs to them) --------------------
    written = {"entities": 0, "mentions": 0, "facts": 0, "evidence": 0}
    with conn.cursor() as cur:
        for eid_row in ent_rows.values():
            eid = eid_row[0]
            raw_types = json.dumps(sorted(raw_types_by_eid.get(eid, ())))
            # GENERATION-STAMPING-V1: raw_types is a deterministic SET
            # UNION (the open vocabulary is preserved, never flattened);
            # the containment guard keeps replays at rowcount 0 so
            # idempotency stays observable in `written`.
            cur.execute(
                """INSERT INTO entities (entity_id, core_type, normalized_surface,
                                         admission_class, first_seen_doc,
                                         extractor_version, generated_by_bundle_hash,
                                         raw_types)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (entity_id) DO UPDATE SET
                       raw_types = (
                           SELECT coalesce(jsonb_agg(DISTINCT t.v ORDER BY t.v),
                                           '[]'::jsonb)
                             FROM jsonb_array_elements_text(
                                      entities.raw_types || EXCLUDED.raw_types)
                                  AS t(v)),
                       extractor_version = coalesce(entities.extractor_version,
                                                    EXCLUDED.extractor_version),
                       generated_by_bundle_hash = coalesce(
                           entities.generated_by_bundle_hash,
                           EXCLUDED.generated_by_bundle_hash)
                   WHERE NOT entities.raw_types @> EXCLUDED.raw_types
                      OR entities.extractor_version IS NULL""",
                eid_row + (EXTRACTOR_VERSION, bundle_hash, raw_types))
            written["entities"] += cur.rowcount
        for m in mention_rows.values():
            cur.execute(
                """INSERT INTO mentions (mention_id, corpus_id, doc_id, chunk_id, char_start,
                       char_end, surface, normalized_surface, core_type, gliner_score,
                       extractor_version, admission_class, entity_id, raw_label,
                       query_policy_version, pass_kind, proposal_surface, referential_surface,
                       anchor_kind, decision_status, reference_basis, admission_reason,
                       semantic_contract)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (mention_id) DO NOTHING""", m)
            written["mentions"] += cur.rowcount
        for f in fact_rows.values():
            cur.execute(
                """INSERT INTO facts (fact_id, predicate, subject_id, object_id, qualifiers,
                                      decision, rule_id, rule_version, provenance,
                                      extractor_version)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
                   ON CONFLICT (fact_id) DO UPDATE
                       SET qualifiers = facts.qualifiers || EXCLUDED.qualifiers
                     WHERE (EXCLUDED.qualifiers ? 'claim_kind')
                       AND NOT (facts.qualifiers ? 'claim_kind')""", f)
            written["facts"] += cur.rowcount
        for e in evidence_rows.values():
            cur.execute(
                """INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id, span_offsets,
                                         rule_id, gliner_scores, extractor_version, rule_version,
                                         provenance_contract)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (evidence_id) DO NOTHING""", e)
            written["evidence"] += cur.rowcount
    return {
        "contract": CONTRACT, "lane": lane, "model": model,
        "seen": {"entities": len(ent_rows), "mentions": len(mention_rows),
                 "facts": len(fact_rows), "evidence": len(evidence_rows)},
        "written": written,
        "unknown_predicates": unknown_predicates,
        "pronoun_entities_dropped": pronoun_entities_dropped,
        "pronoun_endpoints_dropped": pronoun_endpoints_dropped,
        "endpoint_attestation": endpoint_levels,
        "predicates": sorted({f[1] for f in fact_rows.values()}),
    }
