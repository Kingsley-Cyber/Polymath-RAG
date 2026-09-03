"""extract worker — LLM-direct only (LLM-DIRECT-CANON, ADR-0017, 2026-09-03).

Consumes `chunked.v1` outbox events. Flow per document: build neighborhoods
from the child chunks → `llm_provider.run_proposals` (cloud ring / local
batched lane, receipt-cached) → the gate (`llm_extraction.gate`) validates
and normalizes → `llm_direct.materialize` writes entities, mentions, facts
and evidence in the stage transaction → the raw ledger + evidence bundle are
written → the run goes back to `reconciling` for the census.

History: until 2026-09-03 this module also carried the GLiNER two-pass +
spaCy syntax + rule-pack compiler path (~1,900 lines) behind
`extraction_provider=gliner`. Under the canon that path is deleted; the
extract contract below is the LLM-direct contract only.
"""
from __future__ import annotations

import json
import logging
import os
import time

from psycopg import Connection

from polymath_shared.contracts import ExtractionManifest
from polymath_shared.logging import configure_logging
from polymath_shared.query_policy import QUERY_POLICY_VERSION, policy_identity
from polymath_shared.receipts import stage_contract_hash, stage_transaction

STAGE = "extract"
EVENT_TYPE = "chunked.v1"
#: the worker's own contract version (facts carry llm_direct.EXTRACTOR_VERSION)
EXTRACTOR_VERSION = "llm-direct-worker-v2"
ONTOLOGY_VERSION = "core-v1"
#: manifest values for the retired span-tagger fields (schema kept stable)
_RETIRED = "retired"

configure_logging("worker-extract")
log = logging.getLogger("worker-extract")

_BUNDLE_STAMP: str | None = None


def _bundle_hash() -> str:
    global _BUNDLE_STAMP
    if _BUNDLE_STAMP is None:
        from polymath_shared.execution_bundle import (
            bundle_id, compute_execution_bundle)
        _BUNDLE_STAMP = bundle_id(compute_execution_bundle())
    return _BUNDLE_STAMP


def _stamped_provenance(provenance: dict) -> dict:
    """EXECUTION-BUNDLE-FENCE-V1: every accepted fact records the exact
    code+configuration bundle that produced it. Computed once per
    process; the claim gate guarantees it cannot go stale mid-flight."""
    out = dict(provenance or {})
    out.setdefault("generated_by_bundle_hash", _bundle_hash())
    return out


def _llm_contract_identity() -> dict:
    from workers import llm_provider
    return llm_provider.contract_identity()


def process_event(conn: Connection, event: dict) -> None:
    payload = event["payload"]
    run_id = event["run_id"]
    doc_id = payload["doc_id"]
    profile_dict = payload.get("profile", {})
    from polymath_shared.settings import get_settings
    from polymath_shared.observability import (
        TraceCollector, extraction_contracts, trace_mode,
    )
    trace = TraceCollector(trace_mode(), run_id, extraction_contracts())

    provider_mode = get_settings().worker.extraction_provider
    if provider_mode != "llm_live":
        raise ValueError(
            f"extraction provider {provider_mode!r} is retired; "
            "LLM-DIRECT-CANON (ADR-0017) supports 'llm_live' only")

    manifest = ExtractionManifest(
        run_id=run_id,
        gliner_model=_RETIRED, gliner_revision="",
        parser="none", parser_version="",
        ontology_version=ONTOLOGY_VERSION,
        rule_pack_version=_RETIRED,
        thresholds={},
        query_policy=QUERY_POLICY_VERSION,
    )
    contract_payload = {
        "extractor_version": EXTRACTOR_VERSION,
        "ontology_version": ONTOLOGY_VERSION,
        "identity_contract": "entity-identity-v2",
        "provenance_contract": "exact-evidence-v1",
        "extraction_provider": provider_mode,
        "llm_extraction_contract": _llm_contract_identity(),
        "query_policy": policy_identity(),
    }
    contract = stage_contract_hash(STAGE, contract_payload)
    corpus_row = conn.execute(
        "SELECT r.corpus_id FROM runs r WHERE r.run_id = %s", (run_id,)
    ).fetchone()
    corpus_id = corpus_row[0] if corpus_row else "unknown"

    with stage_transaction(
        conn, run_id=run_id, stage=STAGE, contract_hash=contract
    ) as writer:
        writer.artifact({"manifest": manifest.model_dump()})
        chunk_rows = conn.execute(
            """
            SELECT chunk_id, doc_id, parent_id, tier, text, summary,
                   char_start, char_end, layout_map, region_role
              FROM chunks
             WHERE doc_id = %s
             ORDER BY chunk_index
            """,
            (doc_id,),
        ).fetchall()
        chunks = [
            {"chunk_id": r[0], "doc_id": r[1], "parent_id": r[2], "tier": r[3],
             "text": r[4], "summary": r[5], "char_start": r[6], "char_end": r[7],
             "layout_map": r[8], "region_role": r[9]}
            for r in chunk_rows
        ]
        child_chunks = [row for row in chunks if row["tier"] == "child"]
        audit: list[dict] = []
        _t = time
        _perf: dict = {"provider_calls": 0, "stage_t0": _t.perf_counter()}
        _counts: dict = {}
        _raw_rows_entity: list = []
        _raw_rows_predicate: list = []
        from polymath_shared import raw_evidence as _raw
        _llm_model_id = ""
        _llm_revision = "polymath-extraction-v1"
        _llm_lane = ""
        _contract_cache: dict = {}

        def _raw_contract(labels, task):
            key = (tuple(labels), task)
            if key not in _contract_cache:
                _contract_cache[key] = _raw.provider_contract(
                    provider=f"llm:{_llm_lane}",
                    model_id=_llm_model_id,
                    revision=_llm_revision,
                    task=task,
                    threshold=1.0,
                    labels=list(labels))
            return _contract_cache[key]

        from workers import llm_provider as _llm
        from polymath_shared.query_policy import provider_passes as _pp
        from polymath_shared.contracts import DocumentProfile as _DP
        _base = _DP(**profile_dict).label_set if profile_dict.get("label_set") else []
        _compositions = [
            tuple(_labels) for _labels in
            (list(dict.fromkeys(list(_base) + list(_pl))) for _pl in _pp())
            if _labels]
        _src = conn.execute(
            "SELECT byte_length FROM documents WHERE doc_id=%s",
            (doc_id,)).fetchone()
        source_bytes = int(_src[0]) if _src and _src[0] is not None else 0
        _affinity = os.environ.get(
            "POLYMATH_EXTRACT_AFFINITY", "").strip() or None
        _decision = _llm.select_lane(source_bytes, affinity=_affinity)
        _lane_decision = {"lane": _decision.lane,
                          "source_bytes": _decision.source_bytes,
                          "threshold": _decision.threshold,
                          "reason": _decision.reason}
        _t_llm = _t.perf_counter()
        _neighborhoods = _llm.build_neighborhoods(child_chunks)
        _qdepth = _rank = _active = None
        _cache = None
        if _decision.lane == "cloud":
            _qdepth = conn.execute(
                "SELECT count(*) FROM stage_tickets "
                "WHERE stage='extract' "
                "AND status IN ('pending','ready')").fetchone()[0]
            _open = [r[0] for r in conn.execute(
                "SELECT t.ticket_id FROM stage_tickets t "
                "JOIN runs r ON r.run_id = t.run_id "
                "WHERE t.stage='extract' "
                "AND t.status IN ('pending','ready','leased') "
                "AND r.superseded_by_run_id IS NULL "
                "ORDER BY t.ticket_id")]
            _tid = event.get("ticket_id")
            _rank = (_open.index(_tid)
                     if _tid in _open else 0)
            _active = max(1, len(_open))
            from polymath_shared.db import tx as _tx

            def _cache_get(key):
                with _tx() as _c:
                    row = _c.execute(
                        "SELECT raw_text FROM "
                        "extraction_call_receipts "
                        "WHERE receipt_id=%s", (key,)).fetchone()
                return row[0] if row else None

            def _cache_put(key, did, lane_name, model, raw,
                           accepted=None, finish_reason=None,
                           contract_ident=None):
                with _tx() as _c:
                    _c.execute(
                        "INSERT INTO extraction_call_receipts "
                        "(receipt_id, doc_id, lane, model, "
                        "raw_text, accepted_count, finish_reason, "
                        "contract_ident) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (receipt_id) DO NOTHING",
                        (key, did, lane_name, model, raw,
                         accepted, finish_reason, contract_ident))
            _cache = (_cache_get, _cache_put)
        try:
            _results, _merged = _llm.run_proposals(
                _neighborhoods, lane=_decision.lane,
                source_bytes=source_bytes, doc_id=doc_id,
                assist=_decision.assist, queue_depth=_qdepth,
                active_rank=_rank, active_docs=_active,
                call_cache=_cache)
        except TypeError:   # narrowed test double: old signature
            _results, _merged = _llm.run_proposals(
                _neighborhoods, lane=_decision.lane,
                source_bytes=source_bytes, doc_id=doc_id,
                assist=_decision.assist)
        if _decision.lane == "cloud":
            from polymath_shared.llm_extraction.pool import (
                select_cloud_endpoint as _sel_ep,
            )
            _lane_decision["endpoint"] = _sel_ep(doc_id).name
        _perf["llm_extract_s"] = _t.perf_counter() - _t_llm
        _llm_receipts = _llm.call_receipts(_results)
        _llm_model_id = _results[0].model if _results else ""
        _llm_lane = _decision.lane
        _llm_entity_items, _llm_evidence_items = _llm.ledger_items(_merged)
        _raw_rows_entity.extend(
            _raw.proposal_row(doc_id, cid, item,
                              _raw_contract((), "entity"))
            for cid, item in _llm_entity_items)
        _raw_rows_predicate.extend(
            _raw.evidence_row(doc_id, cid, item,
                              _raw_contract((), "evidence"))
            for cid, item in _llm_evidence_items)
        _counts["llm_entities"] = _merged.stats.get("entities", 0)
        _counts["llm_relations"] = _merged.stats.get("relations", 0)
        _counts["llm_rejected"] = len(_merged.rejections)
        _counts["llm_type_coercions"] = len(_merged.coercions)
        _rej_by_class: dict = {}
        for _rj in _merged.rejections:
            _k = _rj.get("error_class", "UNKNOWN")
            _rej_by_class[_k] = _rej_by_class.get(_k, 0) + 1
        _merged.stats["rejections_by_class"] = _rej_by_class
        _llm_artifact = {
            "provider": provider_mode,
            "lane_decision": _lane_decision,
            "calls": _llm_receipts,
            "stats": _merged.stats,
            "rejections_preview": _merged.rejections[:200],
            "coercions_preview": _merged.coercions[:200],
            "digests": _merged.digests,   # SUMMARY-COMPILER-V1 reads every one
            "neighborhoods": len(_neighborhoods),
            "neighborhood_dispositions": _merged.dispositions,
        }
        for _k in ("neighborhoods_sent", "neighborhoods_returned",
                   "neighborhoods_dropped", "neighborhoods_unaccounted",
                   "parents_total", "parents_with_extraction"):
            _counts[_k] = _merged.stats.get(_k, 0)
        writer.artifact({"llm_extraction": _llm_artifact,
                         "llm_rejections": _merged.rejections,
                         "llm_coercions": _merged.coercions})
        _perf["provider_calls"] += len(_results)

        from workers import llm_direct as _direct
        _raw.bulk_write(conn, "raw_entity_proposals", _raw_rows_entity)
        _raw.bulk_write(conn, "raw_predicate_evidence", _raw_rows_predicate)
        _pt = _t.perf_counter()
        _direct_stats = _direct.materialize(
            conn, corpus_id=corpus_id, doc_id=doc_id,
            chunk_rows={r["chunk_id"]: r for r in child_chunks},
            merged=_merged, lane=_decision.lane, model=_llm_model_id,
            stamp=_stamped_provenance)
        _perf["l1_l4_writes_s"] = _t.perf_counter() - _pt
        _bundle = _raw.write_bundle(conn, doc_id, require_slices=False)
        _perf["total_s"] = _t.perf_counter() - _perf.pop("stage_t0")
        _perf["chunks"] = len(child_chunks)
        _counts["facts_direct"] = _direct_stats["written"]["facts"]
        _counts["mentions_direct"] = _direct_stats["written"]["mentions"]
        writer.artifact({
            "llm_direct": _direct_stats,
            "counts": _counts,
            "perf": {k: (round(v, 2) if isinstance(v, float) else v)
                     for k, v in _perf.items()},
            "audit": audit,
            "evidence_bundle": _bundle,
        })
        if trace.enabled:
            trace.count("chunks", len(child_chunks))
            trace.count("llm_direct_facts", _direct_stats["seen"]["facts"])
            _fun = trace.funnel()
            _wr = trace.flush(conn)
            writer.artifact({"trace": {"mode": trace.mode,
                                       "events_written": _wr, "funnel": _fun}})
        log.info("extract llm-direct %s", json.dumps(_direct_stats["seen"]),
                 extra={"run_id": run_id, "stage": "extract", "detail": None})
        writer.run_status("reconciling")


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 1) -> None:
    """LONG-STAGE-LEASE-CORRECTNESS-V1: claim depth 1.

    A worker executes tickets serially, so claiming ahead bought nothing
    but made "held" differ from "being processed" -- and a stage running
    past claim_ttl_s let the reaper expire the queued ones. Parallelism
    comes from running several workers of a type.
    """
    from polymath_shared.worker_runtime import run_worker

    run_worker('extract', [EVENT_TYPE], process_event,
               poll_interval_s=poll_interval_s, batch_size=batch_size)


if __name__ == "__main__":
    run_forever()
