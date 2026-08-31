"""SPARSE-BM25-V1 (§11 L1): deterministic sparse lexical vectors for the
routing collection.

Design (v3.3 port, 2026-08-30): every routing point carries a named
sparse vector `bm25` holding {token_index: term_frequency}; Qdrant's
server-side IDF modifier turns dot-product scoring into BM25-family
lexical relevance. The tokenizer is the CONTRACT — index-side and
query-side must import THIS function; any drift silently zeroes recall.

Deterministic: lowercase, split on non-alphanumerics (underscores and
hyphens split too — "cross-site" indexes as both parts), drop tokens
shorter than 2 chars, index = blake2b-64 of the token mod 2^31 (stable
across processes and machines; no vocabulary state to persist).
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter

SPARSE_VECTOR_NAME = "bm25"
SPARSE_CONTRACT_VERSION = "sparse-bm25-v1"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def token_index(token: str) -> int:
    h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "big") % (2 ** 31)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) >= 2]


def sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """(indices, values) = {token_index: tf} for one text. Collisions in
    the 2^31 space are astronomically unlikely at corpus vocabulary
    sizes and, when they happen, only merge two terms' tf — never an
    error."""
    counts = Counter(token_index(t) for t in tokenize(text))
    if not counts:
        return [], []
    items = sorted(counts.items())
    return [i for i, _ in items], [float(v) for _, v in items]
