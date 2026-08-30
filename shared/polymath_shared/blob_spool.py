"""SPOOL-CLAIM-CHECK-V1: durable byte spool behind intake.

The v3.3 lesson, kept: the HTTP request is transport, never pipeline
state. Upload bytes stream to a content-addressed spool file on a
host-visible volume; the canonical intake payload carries a REFERENCE
({store, key, sha256, bytes}) instead of the bytes themselves; the
intake worker resolves the reference and fail-closes on any mismatch.

Why a reference and not content_b64: the inline variant stores the
full base64 body in Postgres jsonb (runs.metadata + the outbox event),
which triples a 20 MB book into ~54 MB of database rows and caps
uploads at what an HTTP body round-trip tolerates. The spool bounds
memory at the streaming chunk size and leaves Postgres holding ~200
bytes per document.

The reference shape maps 1:1 onto S3-compatible object storage
(key = object key), so moving the spool to Cloudflare R2 later is a
backend swap behind the same claim check, not a payload change.

Layout is content-addressed (<sha256[:2]>/<sha256>): identical bytes
dedup to one file, writes are atomic (tmp + rename), and a spool file
can never disagree with its own name without the read check catching it.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import BinaryIO

SPOOL_STORE = "local"
_CHUNK = 1024 * 1024  # 1 MiB — the streaming bound, never the file size


class SpoolError(RuntimeError):
    """Base: a content_ref that cannot be honored. Fail-loud."""


class SpoolMissingError(SpoolError):
    """CONTENT_REF_MISSING: the referenced spool object does not exist."""


class SpoolIntegrityError(SpoolError):
    """SPOOL_INTEGRITY_MISMATCH: bytes on disk do not hash to the
    sha256 the reference claims. Never process mismatched bytes."""


def spool_dir() -> Path:
    root = os.environ.get(
        "POLYMATH_SPOOL_DIR",
        str(Path.home() / "PolymathRuntime" / "polymath-v4" / "spool"),
    )
    p = Path(root)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _path_for(sha256: str) -> Path:
    return spool_dir() / sha256[:2] / sha256


def spool_write(stream: BinaryIO) -> dict:
    """Stream to the spool in bounded chunks, hashing in flight.

    Returns the claim-check reference:
    {"store": "local", "key": "<aa>/<sha256>", "sha256": ..., "bytes": n}
    """
    h = hashlib.sha256()
    n = 0
    tmp = spool_dir() / f".tmp-{os.getpid()}-{id(stream)}"
    with tmp.open("wb") as out:
        while True:
            chunk = stream.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
            n += len(chunk)
            out.write(chunk)
    sha = h.hexdigest()
    final = _path_for(sha)
    final.parent.mkdir(parents=True, exist_ok=True)
    if final.exists():
        tmp.unlink()  # identical bytes already spooled — dedup
    else:
        tmp.rename(final)
    return {"store": SPOOL_STORE, "key": f"{sha[:2]}/{sha}",
            "sha256": sha, "bytes": n}


def spool_read(ref: dict) -> bytes:
    """Resolve a claim-check reference to bytes, verifying integrity.

    The sha256 in the reference participates in run identity, so this
    check is what makes the reference as trustworthy as inline bytes:
    substituted or corrupted spool content is refused, never processed.
    """
    store = ref.get("store")
    if store != SPOOL_STORE:
        raise SpoolError(f"unsupported content_ref store: {store!r}")
    sha = ref.get("sha256") or ""
    path = _path_for(sha)
    if not path.exists():
        raise SpoolMissingError(
            f"CONTENT_REF_MISSING: spool object {ref.get('key')!r} not found")
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != sha:
        raise SpoolIntegrityError(
            f"SPOOL_INTEGRITY_MISMATCH: {ref.get('key')!r} hashes to "
            f"{actual}, reference claims {sha}")
    if ref.get("bytes") is not None and ref["bytes"] != len(raw):
        raise SpoolIntegrityError(
            f"SPOOL_INTEGRITY_MISMATCH: {ref.get('key')!r} is {len(raw)} "
            f"bytes, reference claims {ref['bytes']}")
    return raw


# ======================================================================
# SOURCE-RECOVERY-KEY-V1 (P5, 2026-08-28)
#
# A `documents` row carries TWO hashes and only one of them addresses a
# spool object:
#
#   source_hash   sha256 of the ORIGINAL uploaded bytes. This is the
#                 spool key. The blob exists.
#   content_hash  sha256 of the MATERIALIZED text produced from those
#                 bytes. Nothing ever wrote a spool object under it.
#
# MEASURED on cysa-study-v1: 0 of 12 documents resolve via content_hash;
# 12 of 12 resolve via source_hash. Reaching for content_hash returns
# "not found" for every document at once, which does not read like a
# lookup bug — it reads like the retained corpus is gone. That is a
# recoverable rebuild misreported as a data-loss event, and it is
# exactly the mistake to not make while performing the ONE production
# rebuild.
#
# So recovery goes through one function rather than through whichever
# hash a caller happens to have in scope.

SOURCE_RECOVERY_KEY = "source_hash"


def document_source_ref(document) -> dict:
    """Claim-check reference for a document's retained ORIGINAL bytes.

    `document` is a mapping from the `documents` table (a psycopg dict
    row or any Mapping). The key is ALWAYS source_hash — see
    SOURCE-RECOVERY-KEY-V1 above for why content_hash is not a spool
    address.
    """
    sha = str(document.get(SOURCE_RECOVERY_KEY) or "").strip()
    if not sha:
        raise SpoolMissingError(
            "SOURCE_HASH_MISSING: document "
            f"{document.get('doc_id')!r} has no {SOURCE_RECOVERY_KEY}; its "
            "original bytes cannot be recovered from the spool. Do NOT "
            "fall back to content_hash — that hash addresses the "
            "materialized text and has no spool object.")
    return {"store": SPOOL_STORE, "key": f"{sha[:2]}/{sha}", "sha256": sha}


def read_document_source(document) -> bytes:
    """The retained original bytes for `document`, integrity-checked."""
    return spool_read(document_source_ref(document))
