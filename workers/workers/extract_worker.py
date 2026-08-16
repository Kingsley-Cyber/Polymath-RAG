"""extract worker: GLiNER pass 1 + pass 2 -> compiler -> facts. One durable stage.

Consumes `chunked.v1` outbox events. Flow per document:

  for each child chunk:
    pass 1: entity spans (chunk label set from the document profile)
    pass 2: evidence spans (18-class evidence inventory)
    per sentence: candidates (workers.candidates) -> compiler
    ACCEPT/QUALIFY -> facts + evidence rows; REJECT/AMBIGUOUS/UNSUPPORTED
    -> audit rows only (never invented edges, docx: silence is valid).

Entity, fact, and evidence rows commit in ONE Postgres transaction with
the receipt (AGENTS.md rule 5). GLiNER proposes; the compiler decides.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

import psycopg
from psycopg import Connection

from polymath_shared.clients import GlinerClient
from polymath_shared.contracts import (
    CoreType,
    EntitySpan,
    EvidenceSpan,
    ExtractionManifest,
)
from polymath_shared.db import tx
from polymath_shared.logging import configure_logging
from polymath_shared.receipts import (
    StageFailed,
    claim_events,
    stage_contract_hash,
    stage_transaction,
)
from polymath_shared.rulepack import compile_relation, load_rule_pack
from workers.candidates import SentenceSlice, build_candidates
from workers.evidence_proposer import EXTRACTOR_VERSION as EVIDENCE_EXTRACTOR_VERSION
from workers.profile_router import chunk_label_set
from workers.summarizer import split_sentences
from workers.syntax import parse_sentence, parser_identity

STAGE = "extract"
EVENT_TYPE = "chunked.v1"

EXTRACTOR_VERSION = "gliner-2pass-v1"
ONTOLOGY_VERSION = "core-v1"
RULE_PACK_VERSION = "1.0.0"
# Q1-R: the rule-pack release the extract stage compiles against.
# Packed into the stage contract so a pack promotion re-runs extraction.
_ACTIVE_PACK_VERSION = "1.0.1"  # overwritten at runtime from settings


def active_pack_version() -> str:
    from polymath_shared.settings import get_settings

    return get_settings().worker.rule_pack_version

ENTITY_THRESHOLD = 0.5
EVIDENCE_THRESHOLD = 0.4

log = logging.getLogger("extract")

_rule_pack = None


def _gliner_pin() -> dict:
    """I3R-R7: the actual immutable GLiNER identity from the sidecar's
    /manifest (canonical production configuration source) — never a
    template placeholder."""
    try:
        from polymath_shared.clients import GlinerClient

        client = GlinerClient()
        try:
            m = client.manifest()
            model = (m.get("identity") or {}).get("model") or {}
            model_id = model.get("id") or "unknown"
            revision = model.get("revision") or "unknown"
            if str(model_id).startswith("__PIN_") or str(revision).startswith("__PIN_"):
                raise RuntimeError("GLiNER sidecar manifest is unpinned")
            return {"model_id": model_id, "revision": revision}
        finally:
            client.close()
    except Exception:
        # Fail LOUD at artifact time instead of recording placeholders:
        # a run whose extractor cannot resolve the pin records nothing.
        raise RuntimeError("could not resolve the GLiNER pin from the sidecar manifest")


_GLINER_PIN = _gliner_pin()


def _pack() -> dict:
    global _rule_pack
    if _rule_pack is None:
        _rule_pack = load_rule_pack(pack_version=active_pack_version())
    return _rule_pack


def _core_type(label: str, pack: dict) -> str | None:
    for core in pack["core_types"]:
        if label == core:
            return core
    return None


@dataclass
class _Sentences:
    texts: list[str]
    offsets: list[tuple[int, int]]


def _sentences_of(chunk_text: str) -> _Sentences:
    texts = split_sentences(chunk_text)
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for sentence in texts:
        start = chunk_text.find(sentence, cursor)
        end = start + len(sentence)
        offsets.append((start, end))
        cursor = end
    return _Sentences(texts=texts, offsets=offsets)


def _map_label(label: str, pack: dict) -> str | None:
    """Pass-1 label -> core type. Domain labels map through the profile's
    label->core table (profile_router.MODULES); core labels pass through."""
    from workers.profile_router import MODULES

    if _core_type(label, pack):
        return label
    for module in MODULES.values():
        mapped = module.labels.get(label)
        if mapped:
            return mapped.value
    return None


def _entity_spans(
    gliner: GlinerClient,
    chunk_text: str,
    chunk_id: str,
    doc_id: str,
    profile: dict,
) -> tuple[list[EntitySpan], list[dict]]:
    from polymath_shared.contracts import DocumentProfile

    labels = DocumentProfile(**profile).label_set if profile.get("label_set") else []
    result = gliner.entity_pass(chunk_text, labels, threshold=ENTITY_THRESHOLD)
    spans: list[EntitySpan] = []
    rejected: list[dict] = []
    for item in result.get("spans", []):
        core_type = _map_label(item["label"], _pack())
        if core_type is None:
            rejected.append({"span": item, "reason": "no core mapping for label"})
            continue
        spans.append(EntitySpan(
            doc_id=doc_id,
            chunk_id=chunk_id,
            start=item["start"],
            end=item["end"],
            text=item["text"],
            core_type=CoreType(core_type),
            score=item["score"],
            extractor_version=EXTRACTOR_VERSION,
        ))
    return spans, rejected


def _evidence_spans(
    gliner: GlinerClient,
    chunk_text: str,
    chunk_id: str,
    pack: dict,
    mode: str,
) -> list[EvidenceSpan]:
    """ADR-0008: pass 2 = GLiNER coarse proposals (may abstain) +
    lexical trigger localization. The compiler decides either way."""
    from workers.evidence_proposer import (
        localize_trigger,
        merge_gliner_proposals,
        propose_evidence,
    )

    anchors = propose_evidence(chunk_text, chunk_id, pack)
    if mode == "hybrid":
        result = gliner.evidence_pass(chunk_text, threshold=EVIDENCE_THRESHOLD)
        proposals = merge_gliner_proposals(chunk_text, chunk_id, result.get("spans", []))
        # Localize each proposal to a compiled trigger; unlocalizable
        # proposals compile to UNSUPPORTED downstream.
        proposals = [localize_trigger(p, pack) for p in proposals]
        merged = {s.text: s for s in anchors}
        for p in proposals:
            key = p.text
            if key not in merged:
                merged[key] = p
        return sorted(merged.values(), key=lambda s: (s.start, s.end))
    return anchors


def _slices(
    sentences: _Sentences,
    entities: list[EntitySpan],
    evidence: list[EvidenceSpan],
    corpus_id: str = "eval",
) -> list[SentenceSlice]:
    slices: list[SentenceSlice] = []
    for sentence_idx, (text, (start, end)) in enumerate(zip(sentences.texts, sentences.offsets)):
        ent = [e for e in entities if e.start >= start and e.end <= end]
        ev = [v for v in evidence if v.start >= start and v.end <= end]
        if ent or ev:
            parse = parse_sentence(text)
            if parse is not None:
                parse["_sentence_offsets"] = [start, end]
                _fill_parse_entities(parse, ent, corpus_id)
            slices.append(SentenceSlice(
                text=text, sentence_start=start, sentence_end=end,
                entities=ent, evidence=ev, parse=parse,
            ))
    return slices


def _allocate_parse_entity(span, corpus_id: str, parse: dict) -> str:
    """Parse-record entity ids must use the SAME admission identity as
    candidates (the compiler compares them in _oriented_pair)."""
    from polymath_shared.entity_admission import allocate_entity_id

    sent_start = (parse.get("_sentence_offsets") or [0])[0]
    leading = len(parse.get("text", "")) - len(parse.get("text", "").lstrip())
    return allocate_entity_id(
        span.text, span.core_type.value,
        corpus_id=corpus_id, doc_id=span.doc_id, chunk_id=span.chunk_id,
        span_start=span.start, span_end=span.end,
        extraction_score=span.score,
        sentence_initial=span.start <= sent_start + leading,
    ).mention_id


def _fill_parse_entities(parse: dict, entities: list[EntitySpan], corpus_id: str = "eval") -> None:
    """Q1-R v1.1.0: link the syntactic record's subject/agent/object to
    pass-1 entity ids by deterministic surface match, so the compiler's
    voice normalization (_oriented_pair) can orient passive facts by
    semantic role. Without this link the passive path was dead in
    production (the frozen harness was the only supplier of entity_id)."""
    for slot in ("subject", "agent", "object"):
        record = parse.get(slot)
        if not record:
            continue
        token_text = (record.get("token_text") or "").strip()
        head_text = (record.get("head_text") or "").strip()
        if not token_text:
            continue
        match = None
        for span in entities:
            span_text = span.text.strip()
            if span_text == token_text or span_text == head_text:
                match = span
                break
        if match is None:
            for span in entities:
                if token_text.lower() in span.text.lower():
                    match = span
                    break
        if match is not None:
            record["entity_id"] = _allocate_parse_entity(match, corpus_id, parse)


def process_event(conn: Connection, event: dict) -> None:
    payload = event["payload"]
    run_id = event["run_id"]
    doc_id = payload["doc_id"]
    profile_dict = payload.get("profile", {})
    from polymath_shared.settings import get_settings

    proposal_mode = get_settings().worker.evidence_proposal_mode
    if proposal_mode not in ("lexical", "hybrid"):
        raise ValueError(f"unknown evidence proposal mode: {proposal_mode}")

    pack = _pack()
    parser_name, parser_version = parser_identity()
    manifest = ExtractionManifest(
        run_id=run_id,
        gliner_model=_GLINER_PIN["model_id"],
        gliner_revision=_GLINER_PIN["revision"],
        parser=parser_name,
        parser_version=parser_version,
        ontology_version=ONTOLOGY_VERSION,
        rule_pack_version=active_pack_version(),
        thresholds={"entity": ENTITY_THRESHOLD, "evidence": EVIDENCE_THRESHOLD},
    )

    contract = stage_contract_hash(STAGE, {
        "extractor_version": EXTRACTOR_VERSION,
        "evidence_proposer": EVIDENCE_EXTRACTOR_VERSION,
        "ontology_version": ONTOLOGY_VERSION,
        "rule_pack_version": RULE_PACK_VERSION,
        "active_pack_version": active_pack_version(),
        "parser_version": parser_version,
        "admission_policy": "entity-admission-v1.1",
        "identity_contract": "entity-identity-v2",
        "thresholds": {"entity": ENTITY_THRESHOLD, "evidence": EVIDENCE_THRESHOLD},
        "evidence_proposal_mode": proposal_mode,
        "binding_gates": "endpoint-binding-v1",
        "provenance_contract": "exact-evidence-v1",
        "gliner_pin": _GLINER_PIN,
    })

    corpus_row = conn.execute(
        "SELECT r.corpus_id FROM runs r WHERE r.run_id = %s", (run_id,)
    ).fetchone()
    corpus_id = corpus_row[0] if corpus_row else "unknown"

    with stage_transaction(
        conn, run_id=run_id, stage=STAGE, contract_hash=contract
    ) as writer:
        writer.artifact({"manifest": manifest.model_dump()})

        # Postgres is the authority: consume the chunks the intake stage
        # committed (materialized for native formats, I0/ADR 0010),
        # never re-derive text from event bytes.
        chunk_rows = conn.execute(
            """
            SELECT chunk_id, doc_id, parent_id, tier, text, summary,
                   char_start, char_end
              FROM chunks
             WHERE doc_id = %s
             ORDER BY chunk_index
            """,
            (doc_id,),
        ).fetchall()
        chunks = [
            {"chunk_id": r[0], "doc_id": r[1], "parent_id": r[2], "tier": r[3],
             "text": r[4], "summary": r[5], "char_start": r[6], "char_end": r[7]}
            for r in chunk_rows
        ]
        child_chunks = [row for row in chunks if row["tier"] == "child"]

        gliner = GlinerClient()
        gliner.verify_pin()
        audit: list[dict] = []

        # I3R-R3: two-pass extraction — pass A gathers the full document
        # entity stream (the bounded local-reference resolver needs
        # earlier-sentence history), pass B builds candidates with that
        # history. Extraction candidates remain derived from the current
        # document proposal stream only.
        try:
            ordered_slices: list[tuple[dict, SentenceSlice]] = []
            for row in child_chunks:
                entities, rejected = _entity_spans(
                    gliner, row["text"], row["chunk_id"], doc_id, profile_dict
                )
                audit.extend(rejected)
                if entities:
                    _persist_mentions(conn, corpus_id, doc_id, entities)
                evidence = _evidence_spans(
                    gliner, row["text"], row["chunk_id"], pack, proposal_mode
                )
                sentences = _sentences_of(row["text"])
                slices = _slices(sentences, entities, evidence, corpus_id)
                for sl in slices:
                    ordered_slices.append((row, sl))

            doc_entity_history: list[EntitySpan] = []
            for row, sl in ordered_slices:
                candidates = build_candidates(
                    [sl],
                    doc_id=doc_id,
                    corpus_id=corpus_id,
                    ontology_profile=profile_dict.get("profile_id", "core"),
                    extractor_version=EXTRACTOR_VERSION,
                    rule_pack=pack,
                    doc_entities_history=doc_entity_history,
                )
                doc_entity_history.extend(
                    sorted(sl.entities, key=lambda e: (e.start, e.end)))
                for candidate in candidates:
                    decision = compile_relation(candidate, sl.parse, pack)
                    if decision.decision in ("ACCEPT", "QUALIFY") and decision.fact:
                        _persist_decision(conn, row, candidate, decision)
                    else:
                        audit.append({
                            "decision": decision.decision,
                            "reason": decision.reason,
                            "alternatives": decision.alternatives,
                            "subject": candidate.subject.span.text,
                            "object": candidate.object.span.text,
                            "evidence_class": candidate.evidence.evidence_class,
                        })
        finally:
            gliner.close()

        writer.artifact({"audit": audit})
        # No outbox event: the control census schedules the projection
        # stages from the extract receipt (per-stage event types).
        writer.run_status("reconciling")


def _persist_mentions(conn: Connection, corpus_id: str, doc_id: str,
                      spans: list[EntitySpan]) -> None:
    """I3R-R4: persist every accepted GLiNER proposal as a durable
    mention with its admission decision; non-MENTION_ONLY spans also
    become durable referential entity rows. Graph topology remains
    fact-driven (project_neo4j/canonicalization keep their facts
    joins)."""
    import re as _re

    from polymath_shared.entity_admission import allocate_entity_id

    for span in spans:
        decision = allocate_entity_id(
            span.text, span.core_type.value,
            corpus_id=corpus_id, doc_id=span.doc_id or doc_id,
            chunk_id=span.chunk_id, span_start=span.start,
            span_end=span.end, extraction_score=span.score,
            sentence_initial=False,
        )
        norm_surface = _re.sub(r"\s+", " ", span.text).strip().lower()
        is_durable = decision.reference_class != "MENTION_ONLY"
        # non-MENTION_ONLY classes use their durable id as the mention
        # identity (entity_admission docstring); MENTION_ONLY mentions
        # carry no entities-row identity.
        entity_id = decision.mention_id if is_durable else None
        conn.execute(
            """
            INSERT INTO mentions (mention_id, corpus_id, doc_id, chunk_id,
                                  char_start, char_end, surface,
                                  normalized_surface, core_type,
                                  gliner_score, extractor_version,
                                  admission_class, entity_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (mention_id) DO NOTHING
            """,
            (decision.mention_id, corpus_id, span.doc_id or doc_id,
             span.chunk_id, span.start, span.end, span.text,
             norm_surface, span.core_type.value, span.score,
             span.extractor_version, decision.reference_class, entity_id),
        )
        if is_durable:
            conn.execute(
                """
                INSERT INTO entities (entity_id, core_type, normalized_surface,
                                      admission_class)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (entity_id) DO NOTHING
                """,
                (entity_id, span.core_type.value,
                 norm_surface, decision.reference_class),
            )


def _evidence_offsets(chunk_row: dict, candidate) -> dict:
    """I3R-R6 exact-evidence-v1 provenance record. All span offsets are
    CHUNK-RELATIVE so that chunk_text[start:end] == surface verifiably."""
    chunk_start = int(chunk_row.get("char_start") or 0)
    chunk_end = int(chunk_row.get("char_end") or 0)
    ev = candidate.evidence
    subj = candidate.subject.span
    obj = candidate.object.span
    # span offsets are CHUNK-RELATIVE (GLiNER spans are chunk-based);
    # chunk_char_start/end locate the chunk within the document.
    return {
        "provenance_contract": "exact-evidence-v1",
        "chunk_char_start": chunk_start,
        "chunk_char_end": chunk_end,
        "sentence_index": getattr(candidate, "sentence_index", 0),
        "evidence_surface": ev.text,
        "evidence_start": ev.start,
        "evidence_end": ev.end,
        "trigger_lemma": ev.trigger_lemma,
        "subject_surface": subj.text,
        "subject_start": subj.start,
        "subject_end": subj.end,
        "object_surface": obj.text,
        "object_start": obj.start,
        "object_end": obj.end,
    }


def _persist_decision(conn: Connection, chunk_row: dict, candidate, decision) -> None:
    from polymath_shared.entity_admission import decide as _admission_decide

    fact = decision.fact
    for entity_id, span in (
        (fact.subject_id, candidate.subject.span),
        (fact.object_id, candidate.object.span),
    ):
        admission = _admission_decide(
            span.text, span.core_type.value, span.score
        ).reference_class
        conn.execute(
            """
            INSERT INTO entities (entity_id, core_type, normalized_surface, admission_class)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (entity_id) DO NOTHING
            """,
            (entity_id, span.core_type.value, span.text, admission),
        )
    conn.execute(
        """
        INSERT INTO facts (fact_id, predicate, subject_id, object_id, qualifiers,
                           decision, rule_id, rule_version, provenance)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fact_id) DO NOTHING
        """,
        (fact.fact_id, fact.predicate, fact.subject_id, fact.object_id,
         json.dumps(fact.qualifiers), fact.decision, fact.rule_id,
         fact.rule_version, json.dumps(fact.provenance)),
    )

    from polymath_shared.identity import evidence_id

    ev_id = evidence_id(
        fact.fact_id, chunk_row["doc_id"], chunk_row["chunk_id"],
        {"chunk": chunk_row["char_start"]}, fact.rule_id,
    )
    offsets = _evidence_offsets(chunk_row, candidate)
    conn.execute(
        """
        INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id, span_offsets,
                              rule_id, gliner_scores, extractor_version, rule_version,
                              provenance_contract)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (evidence_id) DO NOTHING
        """,
        (ev_id, fact.fact_id, chunk_row["doc_id"], chunk_row["chunk_id"],
         json.dumps(offsets),
         fact.rule_id, json.dumps({}), EXTRACTOR_VERSION, fact.rule_version,
         "exact-evidence-v1"),
    )


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 4) -> None:
    configure_logging("worker-extract")
    while True:
        try:
            with tx() as conn:
                events = claim_events(conn, [EVENT_TYPE], batch_size)
                if events:
                    for event in events:
                        try:
                            process_event(conn, event)
                            log.info("extract event processed", extra={
                                "run_id": event["run_id"], "stage": STAGE,
                                "attempt_id": event["idempotency_key"][:16],
                            })
                        except StageFailed as exc:
                            log.error(str(exc), extra={
                                "run_id": event["run_id"], "stage": STAGE,
                                "error_code": "stage_failed",
                            })
        except psycopg.errors.OperationalError as exc:
            log.warning("postgres unavailable; backing off", extra={"error_code": "pg_unavailable"})
        except Exception as exc:
            log.exception("extract processing failed", extra={"error_code": type(exc).__name__})
        time.sleep(poll_interval_s)


if __name__ == "__main__":
    run_forever()
