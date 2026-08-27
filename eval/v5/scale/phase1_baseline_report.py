"""PHASE-1 reliability baseline package (owner-specified schema).

Run at drain convergence (and safe to run mid-drain for validation).
Emits JSON + Markdown covering:

  reliability : documents/tickets/retries/dead letters/queue depth/
                drain time
  pipeline    : per-stage throughput, latency (p50/p95), failures
  integrity   : duplicate facts/entities, receipt-vs-store parity,
                recovery-determinism pointers

Queue-depth curves come from the continuous sampler JSONL
(drain_metrics.jsonl); coverage window is stated honestly in output.
"""
from __future__ import annotations

import datetime as dt
import json
import statistics
import sys
from pathlib import Path

import psycopg

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = sys.argv[1] if len(sys.argv) > 1 else "scale-10k-v1"
SAMPLER = Path("/tmp/polymath_fleet/drain_metrics.jsonl")

STAGES = ["intake", "extract", "profile_document", "project_qdrant",
          "project_neo4j", "canonicalize", "project_canonical",
          "verify_projections", "parent_summary", "document_summary",
          "corpus_summary", "vocabulary"]


def q(cur, sql, args=()):
    cur.execute(sql, args)
    return cur.fetchall()


def collect() -> dict:
    out: dict = {"generated_at": dt.datetime.now(dt.UTC).isoformat(),
                 "corpus": CORPUS}
    with psycopg.connect(DSN, connect_timeout=5) as conn, conn.cursor() as cur:
        # ---- reliability -------------------------------------------------
        docs = q(cur, "SELECT count(*) FROM documents WHERE corpus_id=%s",
                 (CORPUS,))[0][0]
        tickets = dict(q(cur,
            "SELECT status, count(*) FROM stage_tickets GROUP BY 1"))
        retried = q(cur, "SELECT count(*), COALESCE(sum(attempt),0) "
                         "FROM stage_tickets WHERE attempt>0")[0]
        # corpus-scoped ticket accounting
        ctickets = dict(q(cur, """
            SELECT t.status, count(*) FROM stage_tickets t
             JOIN runs r ON r.run_id=t.run_id
            WHERE r.corpus_id=%s GROUP BY 1""", (CORPUS,)))
        first = q(cur, "SELECT min(created_at) FROM runs WHERE corpus_id=%s",
                  (CORPUS,))[0][0]
        last_activity = q(cur, """
            SELECT max(completed_at) FROM stage_attempts sa
              JOIN runs r ON r.run_id=sa.run_id
             WHERE r.corpus_id=%s AND sa.outcome='ok'""", (CORPUS,))[0][0]
        lineage = q(cur, """SELECT count(*) FROM runs
                             WHERE corpus_id=%s AND supersedes_run_id IS NOT NULL""",
                     (CORPUS,))[0][0]
        out["reliability"] = {
            "documents_processed": docs,
            "tickets_created_total": sum(tickets.values()),
            "tickets_completed_total": tickets.get("done", 0),
            "tickets_corpus": {"completed": ctickets.get("done", 0),
                               "superseded_history": ctickets.get("superseded", 0),
                               "open": sum(v for k, v in ctickets.items()
                                           if k not in ("done", "superseded"))},
            "tickets_retried": int(retried[0]),
            "retry_attempts_total": int(retried[1]),
            "dead_letters": tickets.get("failed", 0),
            "successor_runs_via_reconciliation": lineage,
            "drain_window": {"first_run_created": str(first),
                             "last_ok_completion": str(last_activity)},
        }

        # ---- pipeline per-stage ------------------------------------------
        pipeline = {}
        for stage in STAGES:
            rows = q(cur, """
                SELECT EXTRACT(EPOCH FROM (sa.completed_at-sa.started_at))
                  FROM stage_attempts sa
                  JOIN runs r ON r.run_id=sa.run_id
                 WHERE sa.stage=%s AND sa.outcome='ok'
                   AND sa.completed_at IS NOT NULL
                   AND r.corpus_id=%s
                 ORDER BY sa.completed_at DESC LIMIT 2000""",
                (stage, CORPUS))
            durs = [float(r[0]) for r in rows if r[0] is not None]
            fails = q(cur, """
                SELECT count(*) FROM stage_attempts sa
                  JOIN runs r ON r.run_id=sa.run_id
                 WHERE sa.stage=%s AND sa.outcome='failed' AND r.corpus_id=%s""",
                (stage, CORPUS))[0][0]
            if rows:
                span_min = 1.0
                pipeline[stage] = {
                    "completions_sampled": len(rows),
                    "latency_p50_s": round(statistics.median(durs), 2),
                    "latency_p95_s": round(
                        sorted(durs)[int(0.95 * (len(durs) - 1))], 2),
                    "failures_cumulative": int(fails),
                }
            else:
                pipeline[stage] = {"completions_sampled": 0,
                                   "failures_cumulative": int(fails)}
        out["pipeline"] = pipeline

        # ---- integrity -----------------------------------------------------
        # duplicate FACTS: same semantic tuple appearing in distinct fact
        # rows (fact_id is content-derived; key collisions impossible,
        # so this measures semantic re-derivation)
        dup_facts = q(cur, """
            SELECT count(*) - count(DISTINCT (f.predicate, f.subject_id,
                              f.object_id)) FROM facts f
              JOIN evidence ev ON ev.fact_id=f.fact_id
              JOIN documents d ON d.doc_id=ev.doc_id
             WHERE d.corpus_id=%s""", (CORPUS,))[0][0]
        # duplicate ENTITIES: one canonical identity fragmenting into
        # MULTIPLE entity_ids for the same (normalized surface, type)
        # within corpus-scoped admissions. Many mentions sharing ONE
        # entity_id is correct dedup, not duplication.
        fragmented = q(cur, """
            SELECT count(*) FROM (
              SELECT m.normalized_surface, m.core_type
                FROM mentions m
                JOIN documents d ON d.doc_id=m.doc_id
               WHERE d.corpus_id=%s AND m.admission_class='CORPUS_SCOPED'
               GROUP BY m.normalized_surface, m.core_type
              HAVING count(DISTINCT m.entity_id) > 1) x""",
            (CORPUS,))[0][0]
        receipts = dict(q(cur, """
            SELECT pr.projection, count(*) FROM projection_receipts pr
             WHERE pr.active GROUP BY 1"""))
        out["integrity"] = {
            "duplicate_fact_tuples": int(dup_facts),
            "entity_identity_fragments": int(fragmented),
            "active_projection_receipts": receipts,
            "note": ("fact/entity ids are content-derived; duplicates above "
                     "measure semantic re-derivation, not key collisions"),
        }

    # ---- queue-depth curve from sampler ---------------------------------
    curve = {"coverage": None, "max_ready": None, "avg_pending": None}
    if SAMPLER.exists():
        pend, readys, times = [], [], []
        for line in SAMPLER.read_text().splitlines():
            try:
                d = json.loads(line)
                t = d["tickets_by_status"]
                pend.append(t.get("pending", 0))
                readys.append(t.get("ready", 0))
                times.append(d["captured_at"])
            except Exception:
                continue
        if times:
            curve = {"coverage": [times[0], times[-1]],
                     "samples": len(times),
                     "max_ready": max(readys), "avg_pending": round(
                         statistics.mean(pend), 1),
                     "pending_first": pend[0], "pending_last": pend[-1]}
    out["queue_curve"] = curve
    return out


def render(out: dict) -> str:
    r, pl, i = out["reliability"], out["pipeline"], out["integrity"]
    lines = [
        "# PHASE-1 RELIABILITY BASELINE (draft)",
        f"generated {out['generated_at']} · corpus {out['corpus']}",
        "",
        "## Reliability",
        f"- documents_processed: {r['documents_processed']}",
        f"- tickets_created: {r['tickets_created_total']} "
        f"(corpus: {r['tickets_corpus']})",
        f"- tickets_completed: {r['tickets_completed_total']}",
        f"- tickets_retried: {r['tickets_retried']} "
        f"({r['retry_attempts_total']} attempts)",
        f"- dead_letters: {r['dead_letters']}",
        f"- reconciliation successors: "
        f"{r['successor_runs_via_reconciliation']}",
        "",
        "## Pipeline (per stage)",
        "| stage | completions | p50 s | p95 s | failures |",
        "|---|---|---|---|---|",
    ]
    for stage, s in pl.items():
        lines.append(
            f"| {stage} | {s['completions_sampled']} | "
            f"{s.get('latency_p50_s','-')} | {s.get('latency_p95_s','-')} | "
            f"{s['failures_cumulative']} |")
    lines += ["", "## Integrity",
              f"- duplicate fact tuples: {i['duplicate_fact_tuples']}",
              f"- entity identity fragments (same surface+type, "
              f"multiple ids): {i['entity_identity_fragments']}",
              f"- active receipts: {i['active_projection_receipts']}",
              "", f"## Queue curve\n- {out['queue_curve']}"]
    return "\n".join(lines)


if __name__ == "__main__":
    data = collect()
    print(json.dumps(data, indent=1))
    Path("/tmp/polymath_fleet/phase1_package.json").write_text(
        json.dumps(data, indent=1))
    Path("/tmp/polymath_fleet/phase1_package.md").write_text(render(data))
