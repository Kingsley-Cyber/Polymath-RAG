"""R1A retrieval-summary substrate — v3: canonical deterministic routing
summaries compiled by `summary_compiler` (SUMMARY-COMPILER-V1).

SUMMARIES ROUTE / CHILDREN PROVE. One canonical DOCUMENT_RETRIEVAL_
SUMMARY and one SECTION_RETRIEVAL_SUMMARY per parent are the routing
representations; child chunks remain the exact evidence.

Rules:
  - deterministic, non-generative, source-derived (verbatim sentences
    with chunk offsets); triple-aware; coverage-preserving (every
    non-noise child contributes before any child contributes twice);
  - bounded; explainable provenance per selected sentence;
  - versioned content-derived identity over the EMBEDDED text;
  - dual slot: the deterministic card always exists; the extractor's
    digest (LLM abstract) may be the ACTIVE variant (`digest_variant`).

The v2 entry points keep their signatures and return the PLAIN summary
plus sentence provenance; `compile_section` / `compile_document` return
the full `CompiledSummary` (summary, relations, keywords, coverage,
embed_text) the profile stage persists. MEASURED 2026-08-30: v2 was
called without `background`, so its salience degenerated to "longest
sentence per child"; the background is now built from the caller's
units when not supplied.
"""
from __future__ import annotations

from polymath_shared.identity import content_hash
from polymath_shared.summary_compiler import (  # noqa: F401  (re-exported API)
    COMPILER_CONTRACT,
    DOC_MAX_CHARS,
    DOC_MAX_SENTENCES,
    SECTION_MAX_CHARS,
    SECTION_MAX_SENTENCES,
    CompiledSummary,
    build_background,
    compile_document,
    compile_section,
    digest_variant,
    serialize,
)

CONTRACT = "retrieval-summary-v3"

DOC_SUMMARY_KIND = "document_retrieval_summary"
SECTION_SUMMARY_KIND = "section_retrieval_summary"
DOC_MIN_PER_PARENT = 1
DEDUPE_JACCARD = 0.8


def section_retrieval_summary(
    children: list[dict],
    *,
    parent_id: str,
    background: dict[str, int] | None = None,
    facts: list[dict] | None = None,
) -> tuple[str, list[dict]]:
    """Plain compiled summary + per-sentence provenance for one parent."""
    compiled = compile_section(children, parent_id=parent_id,
                               background=background, facts=facts)
    return compiled.summary, compiled.sentences


def document_retrieval_summary(
    parents: list[dict],
    *,
    doc_id: str,
    profile: dict | None = None,
    facts: list[dict] | None = None,
) -> tuple[str, list[dict]]:
    """Plain compiled document summary over the ordered parents
    (`summary` when compiled, else `text`) + provenance carrying
    `parent_id` per selected sentence."""
    compiled = compile_document(parents, doc_id=doc_id, facts=facts)
    prov = [{**p, "parent_id": p["chunk_id"], "doc_id": doc_id,
             "section_position": p["child_index"]} for p in compiled.sentences]
    return compiled.summary, prov


def summary_id(kind: str, source_id: str, summary_text: str) -> str:
    """Deterministic versioned identity (no wall-clock metadata)."""
    return "summ_" + content_hash({
        "kind": kind,
        "source": source_id,
        "contract": CONTRACT,
        "text": summary_text,
    })
