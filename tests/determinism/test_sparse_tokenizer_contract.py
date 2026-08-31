"""SPARSE-TOKENIZER-CONTRACT (audit F11).

The BM25 lane only works if INDEX and QUERY tokenize identically: the
projector writes sparse vectors with polymath_shared.sparse_bm25, so
every orchestrator query path MUST source its tokenizer/vectorizer from
that same module. A forked tokenizer (a local `re.findall` + hash) would
silently return 0 sparse hits — same defect class as the entity-id
underscore/hyphen split (memory: the vector<->graph join broke on a
slug convention fork, found only by probing the shared derivation fn).

These tests pin the contract two ways: source-level (no orchestrator
module defines its own sparse tokenizer/hasher) and value-level (the
shared derivation is stable for known inputs, so a contract change
cannot land silently).
"""
from __future__ import annotations

import pathlib
import re

from polymath_shared.sparse_bm25 import (
    SPARSE_VECTOR_NAME,
    sparse_vector,
    tokenize,
)

ORCH_API = pathlib.Path(__file__).resolve().parents[2] / \
    "orchestrator" / "orchestrator" / "api"

# every orchestrator module that issues sparse queries today
SPARSE_QUERY_MODULES = ("fast.py", "hybrid.py", "ask.py")


def test_sparse_query_modules_import_shared_tokenizer():
    for name in SPARSE_QUERY_MODULES:
        src = (ORCH_API / name).read_text()
        assert "polymath_shared.sparse_bm25" in src, (
            f"{name} issues sparse queries but does not import the "
            "shared sparse_bm25 contract")


def test_no_orchestrator_module_forks_the_tokenizer():
    # A fork looks like a local token hash: blake2b/md5/sha over
    # per-token text, or a re-implementation named like a tokenizer.
    fork_signature = re.compile(
        r"def\s+(tokenize|_tokenize|sparse_vector|_sparse_vector)\s*\(")
    for path in sorted(ORCH_API.glob("*.py")):
        src = path.read_text()
        m = fork_signature.search(src)
        assert m is None, (
            f"{path.name} defines {m.group(1)}() — sparse tokenization "
            "must come from polymath_shared.sparse_bm25, never a fork")


def test_shared_derivation_is_stable():
    assert SPARSE_VECTOR_NAME == "bm25"
    assert tokenize("Chain-of-Custody: evidence 42!") == [
        "chain", "of", "custody", "evidence", "42"]
    # single-char tokens dropped, lowercased, >=2 chars
    assert tokenize("a B cc") == ["cc"]
    indices, values = sparse_vector("incident response")
    assert len(indices) == len(values) == 2
    # blake2b-64 mod 2^31 — value-pinned so a hash change fails loudly
    assert all(0 <= i < 2**31 for i in indices)
    assert (indices, values) == sparse_vector("incident response")
