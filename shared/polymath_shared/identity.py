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
