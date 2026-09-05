"""SOURCE-RECOVERY-KEY-V1 — pinned BEFORE the one production rebuild.

A `documents` row carries two hashes and only one addresses a spool
object:

    source_hash    sha256 of the ORIGINAL uploaded bytes — the spool key
    content_hash   sha256 of the MATERIALIZED text — never spooled

MEASURED on cysa-study-v1: 0 of 12 documents resolve via content_hash,
12 of 12 via source_hash.

Why this is worth a permanent gate rather than a comment: reaching for
content_hash does not fail like a lookup bug. It returns "not found" for
every document simultaneously, which reads as "the retained corpus is
gone". That turns a fully recoverable rebuild into an apparent
data-loss event — the single worst way to be wrong during P14, which
rebuilds production exactly once.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.blob_spool import (  # noqa: E402
    SOURCE_RECOVERY_KEY,
    SpoolMissingError,
    document_source_ref,
    read_document_source,
    spool_read,
)

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
REBUILD_CORPUS = "cysa-study-v1"


def _pg():
    try:
        import psycopg
        return psycopg.connect(DSN, connect_timeout=3,
                               row_factory=psycopg.rows.dict_row)
    except Exception:
        return None


pg_required = pytest.mark.skipif(_pg() is None, reason="postgres unavailable")


# ==================================================== THE KEY ITSELF
def test_recovery_key_is_source_hash():
    assert SOURCE_RECOVERY_KEY == "source_hash"


def test_ref_is_built_from_source_hash_not_content_hash():
    doc = {"doc_id": "doc_x",
           "source_hash": "aa" * 32,
           "content_hash": "bb" * 32}
    ref = document_source_ref(doc)
    assert ref["sha256"] == "aa" * 32, (
        "source recovery reached for content_hash — every document in "
        "the corpus would report CONTENT_REF_MISSING at once")
    assert ref["key"] == f"aa/{'aa' * 32}"
    assert "bb" not in ref["key"]


def test_missing_source_hash_fails_loud_and_forbids_the_fallback():
    """A document with no source_hash is unrecoverable. It must say so
    rather than silently trying the hash that never resolves."""
    with pytest.raises(SpoolMissingError) as exc:
        document_source_ref({"doc_id": "doc_x", "content_hash": "bb" * 32})
    msg = str(exc.value)
    assert "SOURCE_HASH_MISSING" in msg
    assert "content_hash" in msg, (
        "the error must name the wrong key explicitly — that is the "
        "whole point of the gate")


# ================================================= LIVE SPOOL STATE
@pg_required
def test_every_rebuildable_document_resolves_via_source_hash():
    """P14 PRECONDITION. If this fails, the one production rebuild has
    no source material and must not start."""
    conn = _pg()
    with conn:
        rows = conn.execute(
            "SELECT doc_id, source_name, source_hash, content_hash "
            "FROM documents WHERE corpus_id = %s",
            (REBUILD_CORPUS,)).fetchall()
    if not rows:
        # data-dependent: the rebuild corpus lives only on the dev machine; an empty store
        # (CI service database, fresh checkout) has nothing to prove here — skip, never fail
        pytest.skip(f"no documents in {REBUILD_CORPUS} on this store")

    unrecoverable = []
    for row in rows:
        try:
            data = read_document_source(row)
        except Exception as exc:                       # noqa: BLE001
            unrecoverable.append((row["source_name"], type(exc).__name__))
            continue
        assert data, f"{row['source_name']} resolved to empty bytes"
    assert not unrecoverable, (
        f"{len(unrecoverable)} of {len(rows)} documents cannot be "
        f"recovered from the spool: {unrecoverable}")


@pg_required
def test_content_hash_resolves_for_nothing():
    """The trap, pinned as an observation. content_hash is not a spool
    address; if this ever starts resolving, the two hashes have been
    conflated somewhere and the gate above stops proving anything."""
    conn = _pg()
    with conn:
        rows = conn.execute(
            "SELECT content_hash FROM documents WHERE corpus_id = %s",
            (REBUILD_CORPUS,)).fetchall()
    resolved = 0
    for row in rows:
        h = row["content_hash"]
        try:
            spool_read({"store": "local", "key": f"{h[:2]}/{h}",
                        "sha256": h})
            resolved += 1
        except SpoolMissingError:
            pass
    assert resolved == 0, (
        f"content_hash resolved for {resolved} documents — the two "
        "hashes are being conflated")


@pg_required
def test_source_and_content_hash_are_actually_different_values():
    """Guards the premise. If they were equal the whole distinction
    would be moot and this gate would be theatre."""
    conn = _pg()
    with conn:
        rows = conn.execute(
            "SELECT source_hash, content_hash FROM documents "
            "WHERE corpus_id = %s AND source_hash IS NOT NULL",
            (REBUILD_CORPUS,)).fetchall()
    same = [r for r in rows if r["source_hash"] == r["content_hash"]]
    assert not same, f"{len(same)} documents have identical hashes"
