"""DOCUMENT-SEMANTIC-INDEX-V1 slice S5 — the vNext deterministic DocumentFingerprint.

Acceptance shape (plan §18, §31, §S7 / GAP-04): an ADAPTIVE 500-2,000-token
fingerprint with six surfaces (identity / structure / framing / coverage /
synthesis / vocabulary), coverage the LARGEST and sampled across the WHOLE document
(no first-400 bias), a SELF-SUFFICIENT source-derived vocabulary (no
``document_summaries.major_concepts`` input), identifiers preserved, same input =>
same hash, bounded to the budget, and NO LLM (pure stdlib + document_region + the
context/parent_skeleton helpers). Pure pins — no API, no I/O.
"""
from __future__ import annotations

import ast
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import document_region  # noqa: E402
from polymath_shared.document_profile import fingerprint as FP  # noqa: E402


# --- fixtures -----------------------------------------------------------------

def _parent(idx, text, *, heading=None, role="body", char_start=None):
    return {
        "chunk_index": idx,
        "char_start": idx * 1000 if char_start is None else char_start,
        "char_end": idx * 1000 + 999,
        "heading_path": heading if heading is not None else [f"Chapter {idx + 1}"],
        "text": text,
        "region_role": role,
    }


def _book(n=12):
    """A structured book: n body parents, each with a unique ZZMARK<i> token in its
    opening sentence so surface coverage across the document is checkable."""
    parents = []
    for i in range(n):
        text = (
            f"Section {i} introduces ZZMARK{i:02d} as a distinct idea in the broader "
            f"framework of adaptive control and feedback. The mechanism couples "
            f"delayed signals to stability across the whole domain of study."
        )
        parents.append(_parent(i, text, heading=[f"Chapter {i + 1}"]))
    return parents


DOC = {"source_name": "Adaptive Control Systems.pdf", "media_type": "application/pdf",
       "frontmatter": {"title": "Adaptive Control Systems", "author": "A. Author"},
       "content_hash": "c0ffee"}

TECH = (
    "The scanner reports CVE-2026-0217 against the TLS stack described in the manual; "
    "upgrade to remediate. Exam objective 021 maps to control family AU21 in the mapping. "
    "The remediation workflow is validated end to end."
)


# --- pins ---------------------------------------------------------------------

def test_six_surfaces_present():
    fp = FP.build_fingerprint(DOC, _book(12), budget_tokens=2000)
    assert fp.identity and "Adaptive Control Systems" in fp.identity
    assert fp.structure                       # heading paths
    assert fp.framing                         # opening orientation
    assert fp.coverage                        # whole-document samples
    assert fp.synthesis                       # closing content
    assert fp.vocabulary                      # source-derived terms
    assert fp.builder_version == "fingerprint-v1"
    block = fp.render_block
    for label in ("IDENTITY:", "STRUCTURE:", "FRAMING:", "COVERAGE:", "SYNTHESIS:", "VOCABULARY:"):
        assert label in block


def test_budget_clamped_and_within_budget():
    for b in (100, 500, 1000, 1500, 2000, 9000):
        fp = FP.build_fingerprint(DOC, _book(12), budget_tokens=b)
        assert FP.PROFILE_CONTEXT_BUDGET_MIN <= fp.budget_tokens <= FP.PROFILE_CONTEXT_BUDGET_MAX
        # coverage absorbs slack and is computed last, so the total never exceeds budget
        assert fp.used_total <= fp.budget_tokens, (b, fp.used_total, fp.budget_tokens)


def test_coverage_samples_non_decreasing_with_budget():
    counts = [FP.build_fingerprint(DOC, _book(30), budget_tokens=b).sources["coverage_samples"]
              for b in (500, 1000, 1500, 2000)]
    assert counts == sorted(counts)          # monotonic non-decreasing
    assert counts[-1] > counts[0]            # a bigger budget really samples more


def test_coverage_is_the_largest_surface():
    fp = FP.build_fingerprint(DOC, _book(20), budget_tokens=2000)
    cov = fp.used_tokens["coverage"]
    for k, v in fp.used_tokens.items():
        if k != "coverage":
            assert cov >= v, (k, v, cov)


def test_no_first_400_bias_late_content_represented():
    # At the ceiling budget, the whole 12-section document is represented: the FIRST,
    # a LATE (~75%), and the LAST section markers all appear in the rendered block.
    fp = FP.build_fingerprint(DOC, _book(12), budget_tokens=2000)
    block = fp.render_block
    assert "ZZMARK00" in block               # opening — framing/coverage
    assert "ZZMARK09" in block               # ~75% through — coverage (not first-400)
    assert "ZZMARK11" in block               # the very last section — synthesis/coverage


def test_vocabulary_is_self_sufficient_without_major_concepts():
    # GAP-04: no `terms`/major_concepts input is passed, yet vocabulary is derived.
    fp = FP.build_fingerprint(DOC, _book(12), budget_tokens=1000)
    assert fp.vocabulary
    joined = " ".join(fp.vocabulary).lower()
    assert "adaptive" in joined or "feedback" in joined or "control" in joined


def test_identifiers_preserved_in_vocabulary():
    parents = [_parent(0, TECH, heading=["Findings"]),
               _parent(1, "A second section of ordinary prose about the process and its outcome.")]
    fp = FP.build_fingerprint({"source_name": "scan.md"}, parents, budget_tokens=1500)
    for ident in ("CVE-2026-0217", "021", "AU21"):
        assert ident in fp.vocabulary, (ident, fp.vocabulary)
    assert "CVE-2026-0217" in fp.render_block


def test_determinism_same_input_same_hash():
    a = FP.build_fingerprint(DOC, _book(12), budget_tokens=1500)
    b = FP.build_fingerprint(DOC, _book(12), budget_tokens=1500)
    assert a.to_dict() == b.to_dict()
    assert a.input_hash("c0ffee") == b.input_hash("c0ffee")


def test_order_independent():
    parents = _book(12)
    fwd = FP.build_fingerprint(DOC, parents, budget_tokens=1500)
    rev = FP.build_fingerprint(DOC, list(reversed(parents)), budget_tokens=1500)
    assert fwd.to_dict() == rev.to_dict()


def test_input_hash_changes_with_content_and_budget():
    base = FP.build_fingerprint(DOC, _book(12), budget_tokens=1000)
    diff_content = FP.build_fingerprint(DOC, _book(11), budget_tokens=1000)
    diff_budget = FP.build_fingerprint(DOC, _book(12), budget_tokens=2000)
    assert base.input_hash("h") != diff_content.input_hash("h")
    assert base.input_hash("h") != diff_budget.input_hash("h")
    assert base.input_hash("h1") != base.input_hash("h2")


def test_adaptive_small_document_is_not_padded():
    # A tiny one-parent document must yield a small fingerprint, never padded to 2000.
    parents = [_parent(0, "A short standalone note about one narrow topic.", heading=["Note"])]
    fp = FP.build_fingerprint({"source_name": "note.md"}, parents, budget_tokens=2000)
    assert fp.used_total < fp.budget_tokens
    assert fp.used_total < 200


def test_scale_1000_parents_fast_and_bounded():
    parents = _book(1000)
    t0 = time.time()
    fp = FP.build_fingerprint(DOC, parents, budget_tokens=2000)
    assert time.time() - t0 < 5.0
    assert fp.used_total <= 2000
    block = fp.render_block
    assert "ZZMARK00" in block               # first section reached
    assert "ZZMARK999" in block              # last section reached — whole-span


def test_headingless_framing_uses_opening_thesis():
    text = ("This chapter opens with a general orientation about the material ahead. "
            "It sets the context before any specifics are introduced to the reader. "
            "Finally it explains ZZDEEP, the mechanism that dominates retrieval scoring in practice.")
    parents = [_parent(0, text, heading=[]),
               _parent(1, "A following segment continues the discussion with further detail.", heading=[])]
    fp = FP.build_fingerprint({"source_name": "flat.txt"}, parents, budget_tokens=1500)
    # framing is the OPENING (first two sentences), not the highest-scoring sentence
    # from anywhere in the parent (which here would be the ZZDEEP sentence).
    assert fp.framing.startswith("This chapter opens with a general orientation")
    assert "ZZDEEP" not in fp.framing
    assert fp.sources["structure_mode"] == "positions"


def test_furniture_parents_excluded():
    assert document_region.is_noisy("toc")
    parents = [
        _parent(0, "Table of contents FURNMARK chapter one chapter two chapter three.", heading=["Contents"], role="toc"),
        _parent(1, "Real body BODYMARK content discussing the actual subject in depth here.", heading=["Chapter 1"], role="body"),
    ]
    fp = FP.build_fingerprint({"source_name": "b.pdf"}, parents, budget_tokens=1000)
    block = fp.render_block
    assert "BODYMARK" in block
    assert "FURNMARK" not in block
    assert fp.sources["body_parents"] == 1


def test_default_budget_is_canary_selected_floor():
    # S5 canary (2026-09-07) selected the 500-token floor as the quality plateau.
    assert FP.DEFAULT_BUDGET_TOKENS == 500 == FP.PROFILE_CONTEXT_BUDGET_MIN


def test_research_index_tag_vocabulary():
    assert FP.RESEARCH_INDEX_TAGS == (
        "LATENT-PATTERN", "ANCHOR", "RECALLQ", "TENSION", "BRIDGE", "INVERSION", "BOUNDARY")
    assert "LATENT-PATTERN" in FP.RESEARCH_INDEX_TAGS          # distinct hyphenated label (plan §18)
    assert set(FP.RESEARCH_INDEX_TAGS).issubset(set(FP.ROUTING_INFERRED_FIELDS))
    # routing-inferred and source-anchored fields are disjoint (§18 authority split)
    assert not (set(FP.ROUTING_INFERRED_FIELDS) & set(FP.SOURCE_ANCHORED_FIELDS))


def test_empty_and_furniture_only_documents_do_not_crash():
    assert FP.build_fingerprint({"source_name": "x"}, []).used_total >= 0
    only_furniture = [_parent(0, "Copyright page.", heading=["Copyright"], role="front_matter")]
    fp = FP.build_fingerprint({"source_name": "x"}, only_furniture)
    assert fp.sources["body_parents"] == 0
    assert not fp.coverage and not fp.framing


def test_module_is_pure_no_io_no_model():
    src = (ROOT / "shared" / "polymath_shared" / "document_profile" / "fingerprint.py").read_text()
    tree = ast.parse(src)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    allowed = {"__future__", "hashlib", "json", "collections", "dataclasses", "typing", "polymath_shared"}
    assert roots.issubset(allowed), roots - allowed
    for banned in ("requests", "httpx", "psycopg", "psycopg2", "socket", "urllib", "aiohttp", "openai", "groq"):
        assert banned not in src
