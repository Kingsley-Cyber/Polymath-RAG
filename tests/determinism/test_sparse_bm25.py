"""SPARSE-BM25-V1 — the tokenizer IS the contract (§11 L1, 11.3).

Index side and query side must produce identical indices for the same
term or lexical recall silently zeroes. These values are pinned: a
change to the tokenizer or the hash is a breaking contract change and
must re-index every sparse vector.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.sparse_bm25 import (  # noqa: E402
    sparse_vector,
    token_index,
    tokenize,
)


def test_tokenize_deterministic_and_case_folded() -> None:
    assert tokenize("FortiGate firewalls REQUIRE IPsec-tunnels!") == \
        ["fortigate", "firewalls", "require", "ipsec", "tunnels"]
    assert tokenize("") == [] and tokenize(None) == []
    assert tokenize("a x 7") == []          # <2-char tokens dropped ('7' too)


def test_token_index_stable_across_calls() -> None:
    a = token_index("fortigate")
    assert a == token_index("fortigate")
    assert 0 <= a < 2 ** 31
    assert token_index("fortigate") != token_index("fortinet")


def test_sparse_vector_tf_and_order() -> None:
    idx, vals = sparse_vector("splunk splunk elastic")
    assert len(idx) == 2 and idx == sorted(idx)
    tf = dict(zip(idx, vals))
    assert tf[token_index("splunk")] == 2.0
    assert tf[token_index("elastic")] == 1.0
    assert sparse_vector("") == ([], [])


def test_query_side_matches_index_side() -> None:
    """The whole point: a query term hits the indexed term's index."""
    idx, _ = sparse_vector("The CVSS score measures vulnerabilities.")
    assert token_index("cvss") in idx
    assert token_index("vulnerabilities") in idx
