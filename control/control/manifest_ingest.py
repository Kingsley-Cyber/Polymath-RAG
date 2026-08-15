"""I1 manifest ingestion orchestration: plan / execute / status.

- plan:    READ-ONLY. Derives per-source actions from authoritative
           Postgres state (documents by content identity, runs by
           content-derived run id, run status, stage attempts). Never
           mutates anything.
- execute: submits intake work through the ONE shared intake writer
           (outbox + receipts + census untouched); RETRY re-arms a
           terminal failed run's outbox events and re-enters it into
           the census candidate set. Never invokes workers directly.
- status:  READ-ONLY reconciliation report from authoritative run
           state, never subprocess exit codes.

Deterministic throughout: canonical source order, content-derived
identities, and explicit sort orders in every query.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

from psycopg import Connection

from polymath_shared.identity import document_id, normalize_document_bytes, run_id
from polymath_shared.intake_submission import canonical_intake_payload, submit_intake
from polymath_shared.manifest import ManifestError, ManifestSource, manifest_id, resolve_sources

ACTION_INGEST = "INGEST"
ACTION_NOOP = "NOOP"
ACTION_RETRY = "RETRY"
ACTION_SKIP_DISABLED = "SKIP_DISABLED"
ACTION_ERROR_MISSING = "ERROR_MISSING"
ACTION_ERROR_INVALID = "ERROR_INVALID"

_NORMALIZATION = {"strip_bom": True, "normalize_crlf": True}


@dataclass
class PlannedSource:
    locator: str
    action: str
    doc_id: str
    run_id: str | None
    run_status: str | None
    note: str = ""


def _payload_for(source: ManifestSource, corpus_id: str, content_b64: str) -> dict:
    return canonical_intake_payload(
        corpus_id=corpus_id,
        source_name=source.locator,
        media_type=source.media_type,
        content_b64=content_b64,
    )


def _run_state(conn: Connection, run_id: str) -> str | None:
    row = conn.execute("SELECT status FROM runs WHERE run_id = %s", (run_id,)).fetchone()
    return row[0] if row else None


def plan_manifest(conn: Connection, doc: dict, manifest_path: str) -> dict:
    """Read-only plan. Derives state from Postgres only."""
    corpus_id = doc["corpus"]["corpus_id"]
    mid = manifest_id(doc)
    sources = resolve_sources(doc, manifest_path)

    planned: list[dict] = []
    counts = {
        "new": 0, "already_ingested": 0, "changed_content": 0, "disabled": 0,
        "missing": 0, "invalid": 0, "currently_running": 0,
        "failed_retryable": 0, "query_ready": 0,
    }

    for source in sources:
        entry: dict = {"source": source.locator, "action": None}
        if not source.enabled:
            counts["disabled"] += 1
            entry["action"] = ACTION_SKIP_DISABLED
            planned.append(entry)
            continue
        path = source.resolved_path
        try:
            raw = open(path, "rb").read()
        except OSError:
            counts["missing"] += 1
            entry["action"] = ACTION_ERROR_MISSING
            entry["note"] = f"file not readable: {path}"
            planned.append(entry)
            continue
        try:
            media_type = source.media_type
        except ManifestError as exc:
            counts["invalid"] += 1
            entry["action"] = ACTION_ERROR_INVALID
            entry["note"] = str(exc)
            planned.append(entry)
            continue

        normalized = normalize_document_bytes(raw, **_NORMALIZATION)
        doc_id = document_id(normalized)
        content_b64 = base64.b64encode(raw).decode()
        payload = _payload_for(source, corpus_id, content_b64)
        rid = run_id(corpus_id, payload)

        doc_row = conn.execute(
            "SELECT corpus_id, source_name FROM documents WHERE doc_id = %s",
            (doc_id,),
        ).fetchone()
        run_status = _run_state(conn, rid)

        if run_status is not None and doc_row is not None and doc_row[0] == corpus_id:
            if run_status == "query_ready":
                counts["query_ready"] += 1
                counts["already_ingested"] += 1
                entry["action"] = ACTION_NOOP
            elif run_status == "failed":
                counts["failed_retryable"] += 1
                entry["action"] = ACTION_RETRY
                entry["note"] = "terminal failure; re-arm via outbox"
            else:
                counts["currently_running"] += 1
                entry["action"] = ACTION_NOOP
                entry["note"] = f"run in progress ({run_status})"
        elif run_status is not None:
            # Submitted (run row exists) but the document row is not
            # materialized yet — the intake stage has not completed.
            if run_status == "failed":
                counts["failed_retryable"] += 1
                entry["action"] = ACTION_RETRY
                entry["note"] = "terminal failure; re-arm via outbox"
            else:
                counts["currently_running"] += 1
                entry["action"] = ACTION_NOOP
                entry["note"] = f"run submitted, stage pipeline pending ({run_status})"
        elif doc_row is not None and doc_row[0] != corpus_id:
            counts["already_ingested"] += 1
            entry["action"] = ACTION_NOOP
            entry["note"] = f"content already ingested under corpus={doc_row[0]}"
        else:
            # content not ingested: new, or changed content at the same
            # source locator (lineage preserved via source_name).
            prior = conn.execute(
                "SELECT doc_id FROM documents WHERE corpus_id = %s AND source_name = %s",
                (corpus_id, source.locator),
            ).fetchone()
            if prior is not None:
                counts["changed_content"] += 1
                entry["action"] = ACTION_INGEST
                entry["note"] = f"changed content; previous doc {prior[0][:16]}…"
            else:
                counts["new"] += 1
                entry["action"] = ACTION_INGEST
        entry["doc_id"] = doc_id[:24] + "…"
        entry["run_id"] = rid
        entry["run_status"] = run_status
        planned.append(entry)

    return {
        "corpus_id": corpus_id,
        "manifest_id": mid,
        "documents_total": len(sources),
        "counts": counts,
        "sources": planned,
    }


def execute_manifest(
    conn: Connection,
    doc: dict,
    manifest_path: str,
    *,
    batch_size: int = 32,
    dry_run: bool = False,
) -> dict:
    """Submit only contractually required intake work.

    INGEST  -> one intake submission via the shared writer.
    RETRY   -> re-arm the failed run's outbox events (delivered_at
               NULL) and re-enter it into the census candidate set
               (status -> 'reconciling'). Stage history and receipts
               are never deleted; idempotency keys make re-delivery
               safe; the census promotes only when outcomes are ok.
    Batch size bounds submission bursts deterministically (canonical
    source order). Workers remain the only processors."""
    if batch_size < 1:
        raise ManifestError("batch_size must be >= 1")
    plan = plan_manifest(conn, doc, manifest_path)
    sources_by_locator = {s.locator: s for s in resolve_sources(doc, manifest_path)}

    submitted = 0
    retried = 0
    results: list[dict] = []
    for entry in plan["sources"]:
        action = entry["action"]
        if action == ACTION_INGEST and submitted >= batch_size:
            continue
        if action == ACTION_INGEST:
            source = sources_by_locator[entry["source"]]
            raw = open(source.resolved_path, "rb").read()
            content_b64 = base64.b64encode(raw).decode()
            payload = _payload_for(source, plan["corpus_id"], content_b64)
            if dry_run:
                results.append({"source": source.locator, "action": action, "dry_run": True})
                continue
            res = submit_intake(conn, payload)
            submitted += 1
            results.append({"source": source.locator, "action": action,
                            "run_id": res["run_id"], "already_exists": res["already_exists"]})
        elif action == ACTION_RETRY and not dry_run:
            conn.execute(
                "UPDATE outbox_events SET delivered_at = NULL WHERE run_id = %s",
                (entry["run_id"],),
            )
            conn.execute(
                "UPDATE runs SET status = 'reconciling', updated_at = now() WHERE run_id = %s",
                (entry["run_id"],),
            )
            retried += 1
            results.append({"source": entry["source"], "action": action,
                            "run_id": entry["run_id"]})

    return {
        "manifest_id": plan["manifest_id"],
        "corpus_id": plan["corpus_id"],
        "submitted": submitted,
        "retried": retried,
        "dry_run": dry_run,
        "results": results,
    }


def status_manifest(conn: Connection, doc: dict, manifest_path: str) -> dict:
    """Read-only reconciliation report from authoritative run state."""
    plan = plan_manifest(conn, doc, manifest_path)
    corpus_id = plan["corpus_id"]
    summary = {
        "manifest_id": plan["manifest_id"],
        "corpus_id": corpus_id,
        "TOTAL": plan["documents_total"],
        "QUERY_READY": plan["counts"]["query_ready"],
        "RUNNING": plan["counts"]["currently_running"],
        "RETRYABLE": plan["counts"]["failed_retryable"],
        "FAILED": plan["counts"]["failed_retryable"],
        "NOOP": plan["counts"]["already_ingested"],
        "DISABLED": plan["counts"]["disabled"],
        "MISSING": plan["counts"]["missing"],
        "INVALID": plan["counts"]["invalid"],
        "NEW": plan["counts"]["new"],
        "CHANGED": plan["counts"]["changed_content"],
    }

    stage_distribution: dict[str, int] = {}
    for entry in plan["sources"]:
        rid = entry.get("run_id")
        if not rid:
            continue
        status = entry.get("run_status")
        key = status if status in ("intake", "query_ready", "failed", "degraded") else "reconciling"
        stage_distribution[key] = stage_distribution.get(key, 0) + 1
    for stage in ("intake", "reconciling", "degraded", "query_ready", "failed"):
        stage_distribution.setdefault(stage, 0)

    return {"summary": summary, "stage_distribution": stage_distribution,
            "sources": plan["sources"]}
