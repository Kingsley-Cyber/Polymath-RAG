"""FAMILY-INTERLEAVE-V1: the shard ring spreads provider families so
every contiguous rank slice carries a family mix, deterministically.

Owner-blessed on the equivalence bench (pairwise fact agreement
0.01–0.10 across families): a document confined to one family forfeits
the facts the others would have found.
"""
from polymath_shared.llm_extraction.pool import (
    CloudEndpoint,
    _family_of,
    interleave_by_family,
)


def _ep(name, host):
    return CloudEndpoint(name=name, url=f"https://{host}/v1", model="m")


def _fleet():
    eps = [_ep(f"gemini{i}", "generativelanguage.googleapis.com") for i in range(1, 5)]
    eps += [_ep(f"gemini{i}b", "generativelanguage.googleapis.com") for i in range(1, 5)]
    eps += [_ep("nvidia2", "integrate.api.nvidia.com"),
            _ep("primary", "ollama.local"),
            _ep("openrouter1", "openrouter.ai"),
            _ep("openrouter2", "openrouter.ai")]
    return eps


def test_ring_is_a_permutation_and_deterministic():
    fleet = _fleet()
    a = interleave_by_family(fleet)
    b = interleave_by_family(list(reversed(fleet)))
    assert [e.name for e in a] == [e.name for e in b]
    assert sorted(e.name for e in a) == sorted(e.name for e in fleet)


def test_every_half_slice_mixes_families():
    """Two active docs → two slices of 6; each must see >=2 families
    (the sorted-ring bug gave one doc an all-groq slice)."""
    ring = interleave_by_family(_fleet())
    half = len(ring) // 2
    for base in (0, half):
        fams = {_family_of(e) for e in ring[base:base + half]}
        assert len(fams) >= 2, [e.name for e in ring[base:base + half]]


def test_minority_families_are_spread_not_clumped():
    ring = [e.name for e in interleave_by_family(_fleet())]
    pos = {n: ring.index(n) for n in ("nvidia2", "primary", "openrouter1", "openrouter2")}
    # no two minority lanes adjacent AND none pushed to the tail block
    vals = sorted(pos.values())
    assert all(b - a >= 2 for a, b in zip(vals, vals[1:])), pos
    assert max(vals) < len(ring) - 1, pos


def test_single_family_ring_is_plain_sorted():
    eps = [_ep(f"g{i}", "one.host") for i in (3, 1, 2)]
    assert [e.name for e in interleave_by_family(eps)] == ["g1", "g2", "g3"]


def test_family_key_is_the_url_host():
    assert _family_of(_ep("x", "openrouter.ai")) == "openrouter.ai"
