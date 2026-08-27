"""Corpus wipe that also clears V5 evidence tables.

The frozen wipe (eval/i4/verify_i4.py::wipe_corpus) predates the V5
evidence layer; span_hypotheses / raw_* / sentence_slices etc. carry no
FK cascade from documents, so rows survive it. Content-addressed ids
made that invisible (re-ingest collides on ON CONFLICT) until a
recorder fix changed row content and stale rows coexisted with
corrected ones, breaking ledger replay.

This wrapper deletes from EVERY table that carries a doc_id column
(discovered by introspection, so future doc-scoped tables are covered
automatically), then delegates to the frozen wipe for runs/documents/
corpora/mentions/projections.

Deliberately NOT wiped: entities and facts. Their ids are content
addressed (ent_* are corpus-independent by design) and shared across
corpora; rows are idempotent under re-ingest. See
docs/KNOWN_LIMITATIONS.md.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import sys

import psycopg

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Frozen wipe owns these (directly or via FK cascade); doc_id
# introspection must not double-delete or fight its ordering.
FROZEN_OWNED = {"documents", "chunks", "mentions", "evidence",
                "document_layout", "projection_receipts"}


def _frozen_wipe():
    spec = importlib.util.spec_from_file_location(
        "vi4", ROOT / "eval/i4/verify_i4.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.wipe_corpus


def wipe_corpus_v5(corpus: str, dsn: str | None = None) -> dict:
    dsn = dsn or os.environ["POLYMATH_PG_DSN"]
    deleted = {}
    with psycopg.connect(dsn) as c:
        docs = [r[0] for r in c.execute(
            "SELECT doc_id FROM documents WHERE corpus_id=%s",
            (corpus,)).fetchall()]
        if docs:
            tables = [r[0] for r in c.execute(
                """SELECT table_name FROM information_schema.columns
                   WHERE table_schema='public' AND column_name='doc_id'
                   ORDER BY table_name""").fetchall()]
            for t in tables:
                if t in FROZEN_OWNED:
                    continue
                cur = c.execute(
                    f"DELETE FROM {t} WHERE doc_id = ANY(%s)", (docs,))
                deleted[t] = cur.rowcount
        c.commit()
    _frozen_wipe()(corpus)
    return deleted


if __name__ == "__main__":
    corpus = sys.argv[1]
    out = wipe_corpus_v5(corpus)
    for t, n in sorted(out.items()):
        print(f"  {t}: {n}")
    print(f"wiped {corpus} (v5-aware)")
