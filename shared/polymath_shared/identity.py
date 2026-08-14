"""Content-hash identity. The single source of truth for IDs.

The rule: every durable identifier in Polymath v4 is a content hash of
its canonicalized input. Re-running the same input produces the same
ID. There are no UUIDs in the durable layer.

Use the functions in this module. Do not call hashlib.sha256 directly.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonicalize(obj: Any) -> bytes:
    """Serialize obj in a deterministic way.

    Rules:
      - JSON with sort_keys=True
      - UTF-8
      - No trailing whitespace
      - separators=(",", ":") for compactness
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_hash(obj: Any) -> str:
    """Return sha256(canonicalize(obj)) as a hex string."""
    return hashlib.sha256(canonicalize(obj)).hexdigest()


def fact_id(predicate: str, subject_id: str, object_id: str, qualifiers: dict) -> str:
    """The canonical fact identity. See ADR-0001 §17."""
    return f"fact_{content_hash({'p': predicate, 's': subject_id, 'o': object_id, 'q': qualifiers})}"


def evidence_id(fact_id: str, doc_id: str, chunk_id: str, span_offsets: dict, rule_id: str) -> str:
    """The canonical evidence identity. Re-derived, never duplicated."""
    return f"ev_{content_hash({'f': fact_id, 'd': doc_id, 'c': chunk_id, 'o': span_offsets, 'r': rule_id})}"


def entity_id(core_type: str, normalized_surface: str, kb_id: str | None = None) -> str:
    """The canonical entity identity. Two-tier: KB-linked or surface-derived."""
    if kb_id:
        return f"ent_{content_hash({'core': core_type, 'kb': kb_id})}"
    return f"ent_{content_hash({'core': core_type, 'surface': normalized_surface.lower()})}"


def document_id(normalized_bytes: bytes) -> str:
    """sha256 of the normalized source bytes. Identical re-uploads map to one document."""
    return f"doc_{hashlib.sha256(normalized_bytes).hexdigest()}"


def chunk_id(doc_id: str, chunk_index: int, chunk_text: str) -> str:
    return f"chunk_{content_hash({'d': doc_id, 'i': chunk_index, 't': chunk_text})}"


def run_id(corpus_id: str, intake_payload: dict) -> str:
    """Run identity. Replaying the same intake over a corpus yields the
    same run id, so re-intake is a no-op at the Postgres level."""
    return f"run_{content_hash({'corpus': corpus_id, 'intake': intake_payload})}"


def receipt_id(run: str, stage: str, contract_hash: str) -> str:
    """Receipt identity = the idempotency key of one stage attempt."""
    return content_hash({'run': run, 'stage': stage, 'contract': contract_hash})


def attempt_id(run: str, stage: str, contract_hash: str) -> str:
    return receipt_id(run, stage, contract_hash)[:16]


def owner_id(hostname: str, role: str, started_at_iso: str) -> str:
    """Persistent control-plane owner identity (ISSUES_REPORT §1.1 fix).

    Keyed on (hostname, role, start timestamp) instead of a process-local
    UUID, so a restarted controller/worker with the same role on the same
    host reclaims its own leases deterministically.
    """
    return content_hash({'host': hostname, 'role': role, 'started': started_at_iso})


def lease_key(*parts: str) -> str:
    return ":".join(parts)


def contract_hash(schema_version: str, frozen_params: dict) -> str:
    """Stage contract identity: the schema version plus every frozen
    parameter that changes the stage's output. Wall-clock fields never
    enter the contract."""
    return content_hash({'schema': schema_version, 'frozen': frozen_params})


def normalize_document_bytes(raw: bytes, *, strip_bom: bool = True, normalize_crlf: bool = True) -> bytes:
    """Canonical byte normalization for document identity.

    UTF-8 decode + NFC normalize + re-encode, so identical text with
    different byte encodings maps to one document. Non-decodable bytes
    pass through raw so binary payloads still hash stably.
    """
    try:
        text = raw.decode("utf-8-sig" if strip_bom else "utf-8")
        if normalize_crlf:
            text = text.replace("\r\n", "\n").replace("\r", "\n")
        import unicodedata

        text = unicodedata.normalize("NFC", text)
        return text.encode("utf-8")
    except UnicodeDecodeError:
        return raw
