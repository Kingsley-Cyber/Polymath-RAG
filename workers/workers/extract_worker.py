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

import base64
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
from workers.chunker import materialize_chunks, plan_document
from workers.evidence_proposer import EXTRACTOR_VERSION as EVIDENCE_EXTRACTOR_VERSION
from workers.evidence_proposer import propose_evidence
from workers.profile_router import chunk_label_set
from workers.summarizer import split_sentences
from workers.syntax import parse_sentence, parser_identity

STAGE = "extract"
EVENT_TYPE = "chunked.v1"
NEXT_EVENT_TYPE = "extracted.v1"

EXTRACTOR_VERSION = "gliner-2pass-v1"
ONTOLOGY_VERSION = "core-v1"
RULE_PACK_VERSION = "1.0.0"

ENTITY_THRESHOLD = 0.5
EVIDENCE_THRESHOLD = 0.4

log = logging.getLogger("extract")

_rule_pack = None


def _pack() -> dict:
    global _rule_pack
    if _rule_pack is None:
        _rule_pack = load_rule_pack()
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
    chunk_text: str,
    chunk_id: str,
    pack: dict,
) -> list[EvidenceSpan]:
    """Evidence proposal = the deterministic lexical lane. GLiNER never
    decides evidence classes (experiments/0001-gliner-evidence-pass.md)."""
    return propose_evidence(chunk_text, chunk_id, pack)


def _slices(
    sentences: _Sentences,
    entities: list[EntitySpan],
    evidence: list[EvidenceSpan],
) -> list[SentenceSlice]:
    slices: list[SentenceSlice] = []
    for text, (start, end) in zip(sentences.texts, sentences.offsets):
        ent = [e for e in entities if e.start >= start and e.end <= end]
        ev = [v for v in evidence if v.start >= start and v.end <= end]
        if ent or ev:
            parse = parse_sentence(text)
            if parse is not None:
                parse["_sentence_offsets"] = [start, end]
            slices.append(SentenceSlice(
                text=text, sentence_start=start, sentence_end=end,
                entities=ent, evidence=ev, parse=parse,
            ))
    return slices


def process_event(conn: Connection, event: dict) -> None:
    payload = event["payload"]
    run_id = event["run_id"]
    doc_id = payload["doc_id"]
    profile_dict = payload.get("profile", {})
    raw = base64.b64decode(payload["doc_content"]).decode("utf-8", errors="replace")

    pack = _pack()
    parser_name, parser_version = parser_identity()
    manifest = ExtractionManifest(
        run_id=run_id,
        gliner_model="__PIN_MODEL__",
        gliner_revision="__PIN_REVISION__",
        parser=parser_name,
        parser_version=parser_version,
        ontology_version=ONTOLOGY_VERSION,
        rule_pack_version=RULE_PACK_VERSION,
        thresholds={"entity": ENTITY_THRESHOLD, "evidence": EVIDENCE_THRESHOLD},
    )

    contract = stage_contract_hash(STAGE, {
        "extractor_version": EXTRACTOR_VERSION,
        "evidence_proposer": EVIDENCE_EXTRACTOR_VERSION,
        "ontology_version": ONTOLOGY_VERSION,
        "rule_pack_version": RULE_PACK_VERSION,
        "thresholds": {"entity": ENTITY_THRESHOLD, "evidence": EVIDENCE_THRESHOLD},
    })

    with stage_transaction(
        conn, run_id=run_id, stage=STAGE, contract_hash=contract
    ) as writer:
        writer.artifact({"manifest": manifest.model_dump()})

        plan = plan_document(raw, doc_id)
        chunks = materialize_chunks(plan)
        child_chunks = [row for row in chunks if row["tier"] == "child"]

        gliner = GlinerClient()
        gliner.verify_pin()
        audit: list[dict] = []

        try:
            for row in child_chunks:
                entities, rejected = _entity_spans(
                    gliner, row["text"], row["chunk_id"], doc_id, profile_dict
                )
                audit.extend(rejected)
                evidence = _evidence_spans(row["text"], row["chunk_id"], pack)
                sentences = _sentences_of(row["text"])
                slices = _slices(sentences, entities, evidence)
                for sl in slices:
                    candidates = build_candidates(
                        [sl],
                        doc_id=doc_id,
                        ontology_profile=profile_dict.get("profile_id", "core"),
                        extractor_version=EXTRACTOR_VERSION,
                        rule_pack=pack,
                    )
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
        writer.outbox(NEXT_EVENT_TYPE, {"run_id": run_id, "doc_id": doc_id})
        writer.run_status("reconciling")


def _persist_decision(conn: Connection, chunk_row: dict, candidate, decision) -> None:
    fact = decision.fact
    conn.execute(
        """
        INSERT INTO entities (entity_id, core_type, normalized_surface)
        VALUES (%s, %s, %s)
        ON CONFLICT (entity_id) DO NOTHING
        """,
        (fact.subject_id, candidate.subject.span.core_type.value, candidate.subject.span.text),
    )
    conn.execute(
        """
        INSERT INTO entities (entity_id, core_type, normalized_surface)
        VALUES (%s, %s, %s)
        ON CONFLICT (entity_id) DO NOTHING
        """,
        (fact.object_id, candidate.object.span.core_type.value, candidate.object.span.text),
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
    conn.execute(
        """
        INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id, span_offsets,
                              rule_id, gliner_scores, extractor_version, rule_version)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (evidence_id) DO NOTHING
        """,
        (ev_id, fact.fact_id, chunk_row["doc_id"], chunk_row["chunk_id"],
         json.dumps({"chunk_char_start": chunk_row["char_start"]}),
         fact.rule_id, json.dumps({}), EXTRACTOR_VERSION, fact.rule_version),
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
