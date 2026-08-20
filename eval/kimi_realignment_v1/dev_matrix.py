"""KIMI real-spacy development matrix (Step 3).

Submits a small corpus of mechanical examples through the live production
path with POLYMATH_RELATION_PIPELINE=kimi_v1 + POLYMATH_SYNTAX_PROVIDER=spacy,
waits for convergence, then reports the Kimi invariant matrix and per-class
results.

Usage:
    POLYMATH_RELATION_PIPELINE=kimi_v1 \
    POLYMATH_SYNTAX_PROVIDER=spacy \
    POLYMATH_EXTRACTION_TRACE=full \
    POLYMATH_WORKER_RULE_PACK_VERSION=1.0.1 \
    .venv/bin/python eval/kimi_realignment_v1/dev_matrix.py
"""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))

from control.manifest_ingest import execute_manifest  # noqa: E402
from polymath_shared.db import tx  # noqa: E402
from polymath_shared.execution import _build_sha  # noqa: E402
from polymath_shared.manifest import load_manifest  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402

CORPUS = "kimi-dev-matrix-v1"
# Fixture files are generated at runtime in /tmp so they do not become
# undeclared repository artifacts.
FIXTURE = Path("/tmp/kimi_dev_matrix_fixture")
DSN = get_settings().postgres.dsn

CASES: list[tuple[str, str]] = [
    ("active_passive_a", "John founded Acme."),
    ("active_passive_b", "Acme was founded by John."),
    ("simple_uses", "The application uses PostgreSQL."),
    ("coordination_obj", "The implementation uses bounded leases, deterministic stage contracts, and transactional claim operations."),
    ("coordination_subj", "Alice and Bob joined Acme."),
    ("prep_argument", "The team relies on PostgreSQL for storage."),
    ("negation", "John did not found Acme."),
    ("modality", "John might found Acme."),
    ("multiple_triggers", "John founded Acme and later joined Beta."),
    ("generic_mention", "The company uses the software."),
    ("unsupported_sense", "John founded his argument on weak evidence."),
]


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _build_fixture() -> Path:
    FIXTURE.mkdir(parents=True, exist_ok=True)
    docs = []
    for doc_id, text in CASES:
        path = FIXTURE / f"{doc_id}.md"
        path.write_text(text + "\n")
        docs.append({"source": str(path.name)})
    manifest = {
        "version": 1,
        "corpus": {
            "corpus_id": CORPUS,
            "title": "Kimi development matrix",
            "description": "real-spacy architectural mechanics check",
        },
        "defaults": {"language": "en", "source_tier": "primary", "enabled": True},
        "documents": docs,
    }
    manifest_path = FIXTURE / "manifest.yaml"
    # manifest_ingest expects YAML or JSON text
    import yaml
    manifest_path.write_text(yaml.safe_dump(manifest))
    return manifest_path


def _wipe_corpus() -> None:
    import psycopg
    from psycopg.rows import dict_row

    c = psycopg.connect(DSN, row_factory=dict_row)
    try:
        # Discover existing tables once so missing schema variants do not
        # abort the wipe transaction.
        existing = {
            row["table_name"]
            for row in c.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            ).fetchall()
        }

        def _del(table: str, where: str, params: tuple) -> None:
            if table not in existing:
                return
            c.execute(f"DELETE FROM {table} WHERE {where}", params)

        # Do not let stale registrations from older fleets claim new work.
        if "worker_registrations" in existing:
            c.execute(
                "UPDATE worker_registrations SET status='stale' WHERE build_sha != %s",
                (_build_sha() or "unknown",),
            )
        rids = [r["run_id"] for r in c.execute("SELECT run_id FROM runs WHERE corpus_id=%s", (CORPUS,)).fetchall()]
        for rid in rids:
            for t in ("stage_attempts", "artifacts", "receipts", "outbox_events", "stage_tickets"):
                _del(t, "run_id=%s", (rid,))
        docs = [r["doc_id"] for r in c.execute("SELECT doc_id FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()]
        if docs:
            _del("projection_receipts", "entity_id = ANY(%s)", (docs,))
            _del("mentions", "doc_id = ANY(%s)", (docs,))
        _del("facts", "fact_id IN (SELECT fact_id FROM evidence e JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s)", (CORPUS,))
        _del("evidence", "fact_id NOT IN (SELECT fact_id FROM facts)", ())
        _del("relation_candidates", "doc_id IN (SELECT doc_id FROM documents WHERE corpus_id=%s)", (CORPUS,))
        _del("chunks", "doc_id IN (SELECT doc_id FROM documents WHERE corpus_id=%s)", (CORPUS,))
        c.execute("DELETE FROM documents WHERE corpus_id=%s", (CORPUS,))
        c.execute("DELETE FROM runs WHERE corpus_id=%s", (CORPUS,))
        c.execute("DELETE FROM corpora WHERE corpus_id=%s", (CORPUS,))
        c.commit()
    finally:
        c.close()


def _wait_convergence(target: int, deadline_s: int = 300) -> dict:
    import psycopg
    from psycopg.rows import dict_row
    deadline = time.time() + deadline_s
    while time.time() < deadline:
        c = psycopg.connect(DSN, row_factory=dict_row)
        try:
            states = {s["status"]: s["n"] for s in c.execute(
                "SELECT status, COUNT(*) AS n FROM runs WHERE corpus_id=%s GROUP BY 1",
                (CORPUS,),
            ).fetchall()}
        finally:
            c.close()
        if states.get("query_ready", 0) == target and not states.get("retrying", 0):
            return states
        print("waiting:", states, flush=True)
        time.sleep(5)
    raise TimeoutError(f"did not converge: {states}")


def _facts_for_corpus() -> list[dict]:
    with tx() as c:
        rows = c.execute(
            """SELECT f.fact_id, f.predicate, f.subject_id, f.object_id, f.decision,
                      f.provenance, d.source_name, e.span_offsets
                 FROM facts f
                 JOIN evidence e ON e.fact_id = f.fact_id
                 JOIN documents d ON d.doc_id = e.doc_id
                WHERE d.corpus_id=%s
             ORDER BY d.source_name, f.fact_id""",
            (CORPUS,),
        ).fetchall()
    return [
        {
            "source": r[6],
            "fact_id": r[0],
            "predicate": r[1],
            "subject_id": r[2],
            "object_id": r[3],
            "decision": r[4],
            "provenance": r[5],
            "span_offsets": r[7],
        }
        for r in rows
    ]


def _traces_for_corpus() -> list[dict]:
    with tx() as c:
        rows = c.execute(
            """                 SELECT d.source_name, a.payload
                 FROM artifacts a
                 JOIN runs r ON r.run_id = a.run_id
                 JOIN documents d ON d.doc_id = (
                     SELECT e.doc_id FROM evidence e
                     WHERE e.fact_id IN (
                         SELECT f.fact_id FROM facts f
                         JOIN evidence ev ON ev.fact_id = f.fact_id
                         WHERE ev.doc_id IN (
                             SELECT doc_id FROM documents WHERE corpus_id = r.corpus_id
                         )
                         LIMIT 1
                     )
                     LIMIT 1
                 )
                WHERE r.corpus_id = %s
                  AND a.stage = 'extract'
                  AND a.payload ? 'events'
             ORDER BY d.source_name""",
            (CORPUS,),
        ).fetchall()
    traces = []
    for r in rows:
        artifact = r[2]
        if isinstance(artifact, str):
            artifact = json.loads(artifact)
        traces.append({"source": r[1], "events": artifact.get("events", [])})
    return traces


def main():
    print("building fixture...")
    manifest_path = _build_fixture()
    print("wiping previous corpus...")
    _wipe_corpus()
    print("submitting manifest...")
    doc = load_manifest(manifest_path)
    with tx() as c:
        result = execute_manifest(c, doc, manifest_path)
    print("submitted:", result)
    print("waiting for convergence...")
    states = _wait_convergence(len(CASES))
    print("converged:", states)

    facts = _facts_for_corpus()
    traces = _traces_for_corpus()

    outdir = ROOT / "eval" / "kimi_realignment_v1" / "dev_matrix_results"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "facts.json").write_text(json.dumps(facts, indent=2, default=str))
    (outdir / "traces.json").write_text(json.dumps(traces, indent=2, default=str))

    # simple per-case report (source names in facts carry the .md suffix)
    by_source: dict[str, list[dict]] = {src: [] for src, _ in CASES}
    for f in facts:
        key = f["source"].removesuffix(".md")
        by_source.setdefault(key, []).append(f)

    print("\n=== DEV MATRIX RESULTS ===")
    for src, text in CASES:
        print(f"\n{src}: {text!r}")
        case_facts = by_source.get(src, [])
        if not case_facts:
            print("  (no facts)")
        for f in case_facts:
            prov = f.get("provenance") or {}
            print(f"  {f['decision']} {f['predicate']} ({f['subject_id'][:16]}... -> {f['object_id'][:16]}...)")
            print(f"    orientation={prov.get('orientation')} roles={prov.get('assigned_roles')}")

    summary = {
        "corpus": CORPUS,
        "total_facts": len(facts),
        "per_case": {
            src: len(by_source.get(src, [])) for src, _ in CASES
        },
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nresults written to {outdir}")


if __name__ == "__main__":
    main()
