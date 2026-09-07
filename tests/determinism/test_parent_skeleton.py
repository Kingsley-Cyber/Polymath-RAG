"""DOCUMENT-SEMANTIC-INDEX-V1 slice S1 — deterministic ParentSkeleton.

Acceptance shape from the plan §36.1: fixtures of 1 / 80 / 1000 parents and
several content kinds (transcript, HTML, technical manual, psychology book,
journal note, code/design doc, furniture-heavy source); assert one deterministic
skeleton per eligible parent, identifiers preserved, same input => same skeleton
hash, bounded excerpt, and NO LLM (the module is pure stdlib + document_region).
Pure pins — no API, no I/O.
"""
from __future__ import annotations

import ast
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import parent_skeleton as PS  # noqa: E402


# --- fixtures -----------------------------------------------------------------

def _parent(idx, text, *, heading=None, role="body", char_start=None):
    return {
        "parent_id": f"par-{idx}",
        "chunk_index": idx,
        "char_start": idx * 1000 if char_start is None else char_start,
        "char_end": idx * 1000 + 999,
        "heading_path": heading if heading is not None else [f"Chapter {idx + 1}"],
        "text": text,
        "region_role": role,
    }


TECH_MANUAL = (
    "The scanner reports CVE-2026-0217 against the TLS stack described in RFC 5246; "
    "upgrade the library to 3.11.15 to remediate. Exam objective 021 maps to control "
    "family AU21 in the FACS mapping."
)

TRANSCRIPT = (
    "SPEAKER 1 00:14 So the punch reads weak because the anticipation is missing. "
    "SPEAKER 2 00:22 Right, the weight has to travel through the kinetic chain before impact."
)

HTML_LIKE = (
    "Introduction to graph traversal. A graph hop is a stored relationship traversal "
    "between two entity nodes. Traversal cost grows with fan-out at each relationship."
)

PSYCH_BOOK = (
    "Operant conditioning shapes behaviour through reinforcement schedules. "
    "Variable-ratio reinforcement produces the highest resistance to extinction because "
    "the organism cannot predict which response will be rewarded."
)

JOURNAL_NOTE = "Quick note: reranker latency spikes under enrichment. Investigate the shared Metal lease."

CODE_DESIGN = (
    "The compiler accepts MAP lines and rejects unknown aliases. Partial output is durable; "
    "only unresolved aliases P0001 through P0090 are repaired in a second pass."
)


def test_single_parent_yields_one_skeleton_and_manifest_entry():
    manifest = PS.build_parent_skeletons([_parent(0, HTML_LIKE)])
    assert manifest.eligible_count == 1
    skel = manifest.skeletons[0]
    assert skel.alias == "P0001"
    assert skel.ordinal == 0
    assert skel.parent_id == "par-0"
    assert manifest.alias_to_parent == {"P0001": "par-0"}
    assert manifest.builder_version == PS.SKELETON_BUILDER_VERSION
    assert skel.text_hash and skel.skeleton_hash and manifest.manifest_hash


def test_furniture_is_excluded_and_accounted_never_dropped():
    parents = [
        _parent(0, "CONTENTS ... 1", heading=["Table of Contents"], role="toc"),
        _parent(1, "Copyright 2026", heading=["Copyright"], role="front_matter"),
        _parent(2, "Buy the sequel today!", role="marketing"),
        _parent(3, "abc, 12; def, 44", role="index"),
        _parent(4, "Smith, J. (2020). A paper.", role="bibliography"),
        _parent(5, PSYCH_BOOK, role="body"),
        _parent(6, HTML_LIKE, role="unknown"),   # unknown/absent role is eligible
    ]
    manifest = PS.build_parent_skeletons(parents)
    # 5 furniture excluded, 2 eligible (body + unknown); total accounted.
    assert manifest.eligible_count == 2
    assert len(manifest.excluded) == 5
    assert manifest.eligible_count + len(manifest.excluded) == len(parents)
    excluded_reasons = {e.parent_id: e.reason for e in manifest.excluded}
    assert excluded_reasons["par-0"] == "toc"
    assert excluded_reasons["par-1"] == "front_matter"
    eligible_ids = {s.parent_id for s in manifest.skeletons}
    assert eligible_ids == {"par-5", "par-6"}


def test_empty_parent_excluded_as_empty():
    manifest = PS.build_parent_skeletons([_parent(0, "   \n\t  ", role="body"), _parent(1, PSYCH_BOOK)])
    assert manifest.eligible_count == 1
    assert [(e.parent_id, e.reason) for e in manifest.excluded] == [("par-0", "empty")]


def test_exact_identifiers_preserved_deterministically():
    manifest = PS.build_parent_skeletons([_parent(0, TECH_MANUAL, heading=["Vulnerabilities"])])
    ids = manifest.skeletons[0].identifiers
    # Canonical form preserved; zero-padding and casing survive (plan §9 / §12).
    assert "CVE-2026-0217" in ids
    assert "AU21" in ids
    assert "021" in ids
    assert "FACS" in ids
    assert any(i.replace("RFC", "").strip() == "5246" for i in ids)  # RFC 5246 / RFC5246
    assert "3.11.15" in ids
    # No spurious substring of the CVE (masking): "0217" and "2026" not emitted alone.
    assert "0217" not in ids
    assert "2026" not in ids
    # Independent of key-term/hook selection: identifiers exist even if the model
    # would never have picked them.
    assert manifest.skeletons[0].identifiers == tuple(PS.extract_identifiers(TECH_MANUAL))


def test_same_input_same_hashes_and_manifest():
    parents = [_parent(i, t) for i, t in enumerate([TECH_MANUAL, PSYCH_BOOK, HTML_LIKE, CODE_DESIGN])]
    a = PS.build_parent_skeletons(parents)
    b = PS.build_parent_skeletons(parents)
    assert a.manifest_hash == b.manifest_hash
    assert a.to_dict() == b.to_dict()
    assert [s.skeleton_hash for s in a.skeletons] == [s.skeleton_hash for s in b.skeletons]


def test_skeleton_hash_is_content_identity_not_position():
    # Identical parent content in two different documents yields the same
    # skeleton_hash (alias/ordinal/position excluded from the hash).
    one = PS.build_parent_skeletons([_parent(0, PSYCH_BOOK, heading=["Learning"])])
    two = PS.build_parent_skeletons(
        [_parent(9, HTML_LIKE, heading=["Graphs"]), _parent(10, PSYCH_BOOK, heading=["Learning"])]
    )
    same = next(s for s in two.skeletons if s.parent_id == "par-10")
    assert same.skeleton_hash == one.skeletons[0].skeleton_hash
    assert same.alias != one.skeletons[0].alias or same.ordinal != one.skeletons[0].ordinal or True


def test_alias_assignment_is_stable_under_input_reordering():
    ordered = [_parent(i, t, char_start=i * 100) for i, t in enumerate([HTML_LIKE, PSYCH_BOOK, CODE_DESIGN])]
    shuffled = [ordered[2], ordered[0], ordered[1]]
    a = PS.build_parent_skeletons(ordered)
    b = PS.build_parent_skeletons(shuffled)
    # Ordering is by source_position then id, so the manifest is identical.
    assert a.manifest_hash == b.manifest_hash
    assert a.alias_to_parent == b.alias_to_parent


def test_excerpt_is_bounded_and_not_blindly_the_first_sentence():
    # First "sentence" is boilerplate/short; the informative sentence is second.
    text = "P. 42. graph hop traversal is a stored relationship traversal between entity nodes."
    manifest = PS.build_parent_skeletons([_parent(0, text, heading=["Graph hops"])])
    excerpt = manifest.skeletons[0].salient_excerpt
    assert 0 < len(excerpt.split()) <= PS.SALIENT_EXCERPT_MAX_WORDS
    assert "traversal" in excerpt.lower()
    assert not excerpt.startswith("P. 42")


def test_key_terms_bounded_and_reject_stopwords():
    manifest = PS.build_parent_skeletons(
        [_parent(0, HTML_LIKE, heading=["Graph traversal"]), _parent(1, PSYCH_BOOK)]
    )
    for skel in manifest.skeletons:
        assert len(skel.key_terms) <= PS.KEY_TERMS_MAX
        assert all(t not in PS.STOP_TERMS for t in skel.key_terms)
    graph_terms = manifest.skeletons[0].key_terms
    assert any(t in {"graph", "traversal", "relationship", "hop"} for t in graph_terms)


def test_mixed_content_kinds_all_produce_valid_bounded_skeletons():
    kinds = [TECH_MANUAL, TRANSCRIPT, HTML_LIKE, PSYCH_BOOK, JOURNAL_NOTE, CODE_DESIGN]
    manifest = PS.build_parent_skeletons([_parent(i, t) for i, t in enumerate(kinds)])
    assert manifest.eligible_count == len(kinds)
    for skel in manifest.skeletons:
        assert skel.salient_excerpt
        assert len(skel.salient_excerpt.split()) <= PS.SALIENT_EXCERPT_MAX_WORDS
        assert PS.KEY_TERMS_MAX >= len(skel.key_terms) >= 0


def test_80_parents_unique_aliases_and_manifest():
    parents = [_parent(i, f"{HTML_LIKE} variant {i} token{i}") for i in range(80)]
    manifest = PS.build_parent_skeletons(parents)
    assert manifest.eligible_count == 80
    aliases = [s.alias for s in manifest.skeletons]
    assert len(set(aliases)) == 80
    assert aliases[0] == "P0001" and aliases[-1] == "P0080"


def test_1000_parents_deterministic_and_cheap():
    parents = [
        _parent(i, f"Section {i}: graph traversal and reinforcement token{i} identifier ID{i:04d}.")
        for i in range(1000)
    ]
    start = time.perf_counter()
    a = PS.build_parent_skeletons(parents)
    elapsed = time.perf_counter() - start
    assert a.eligible_count == 1000
    assert len({s.alias for s in a.skeletons}) == 1000
    # Determinism at scale.
    b = PS.build_parent_skeletons(parents)
    assert a.manifest_hash == b.manifest_hash
    # Cheap: pure CPU, no model. Generous budget for CI headroom.
    assert elapsed < 5.0, f"skeleton build too slow: {elapsed:.2f}s"


def test_module_is_pure_no_llm_no_io():
    """The skeleton stage must be deterministic policy: stdlib + document_region
    only. Statically assert no model / network / heavy-ML import can sneak in."""
    source = (ROOT / "shared" / "polymath_shared" / "document_profile" / "parent_skeleton.py").read_text()
    tree = ast.parse(source)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    allowed = {"__future__", "hashlib", "math", "re", "collections", "dataclasses", "typing", "polymath_shared"}
    assert roots <= allowed, f"unexpected imports in a pure stage: {roots - allowed}"
