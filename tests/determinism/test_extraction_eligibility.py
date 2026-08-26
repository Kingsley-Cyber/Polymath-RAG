"""EXTRACTION-ELIGIBILITY-V1: classification may PRIORITIZE; evidence
determines ELIGIBILITY.

Regression for the 2026-08-26 SMART verification P0: the document-level
Knowledge Router primary classification hard-vetoed the relational
lane (PROCEDURAL 4→0, CONCEPTUAL 6→0, NARRATIVE 2→0 eligible relation
spans measured before vs after routing). The owner invariant:

    ANY CONTENT THAT MEETS THE REQUIREMENTS OF AN EXISTING KNOWLEDGE
    EXTRACTOR MUST BE ALLOWED TO REACH THAT EXTRACTOR.

The six-case mixed-content matrix (A–F) asserts LANE EXECUTION at the
production extraction boundary — normal admission still governs what
becomes knowledge (nothing here weakens Predicate Compiler v2, entity
admission, or F1–F8).

Needs the GLiNER sidecar's /manifest (module-import pin resolution)
but NO inference — skipped cleanly when the sidecar is down.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def _gliner_manifest_reachable() -> bool:
    import httpx

    try:
        httpx.get("http://127.0.0.1:8740/manifest", timeout=3)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gliner_manifest_reachable(),
    reason="extract_worker import resolves the GLiNER pin from the "
           "sidecar manifest (boot any profile with sidecar_gliner)",
)

# One explicit relational statement embedded in every non-scientific
# primary. Trigger lemmas (developed/acquired/uses) are in the frozen
# rule pack; anchors prove candidate DISCOVERY runs — admission decides
# the rest downstream, exactly as for scientific documents.
RELATIONAL = ("As background: GoogleBrain developed TensorFlow. "
              "Acme acquired Initech. The pipeline uses Redis for caching.")

CASE_A_PROCEDURAL = (
    "Step 1. Install the toolkit.\n"
    "Step 2. Configure the runtime.\n"
    "Step 3. Run the setup script.\n"
    "Step 4. Deploy the service.\n" + RELATIONAL + "\n")

CASE_B_CONCEPTUAL = (
    "The principle of least privilege argues for minimal access. "
    "This philosophy teaches restraint. The doctrine has deep meaning. "
    "A framework represents structure. " + RELATIONAL + "\n")

CASE_C_NARRATIVE = (
    "hey guys, in this video I tell a story about my journey. "
    "The story continues through many chapters. " + RELATIONAL + "\n")

CASE_D_SCIENTIFIC_WITH_PROCEDURE = (
    "## Abstract\nWe evaluate the benchmark against a strong baseline.\n"
    "## Methodology\nOur experiment uses a pretrained corpus.\n"
    "To reproduce: Install the evaluation toolkit. "
    "Configure the dataset paths. Run the benchmark suite.\n")

CASE_E_SCIENTIFIC_WITH_CONCEPT = (
    "## Abstract\nWe evaluate the benchmark against a strong baseline.\n"
    "## Methodology\nOur experiment uses a pretrained corpus.\n"
    "A threat model is defined as the set of assumptions an analysis "
    "makes about adversary capabilities.\n")

CASE_F_MIXED_TRANSCRIPT = (
    "hey guys, in this video we set up a retrieval pipeline.\n"
    "**[00:12]** First, install the vector database. "
    "**[00:45]** Next, configure the embedding service. "
    "**[01:30]** Then, run the ingestion script.\n"
    "**[02:10]** Quick background: LangChain uses Redis for caching, "
    "and Anthropic developed Claude.\n"
    "**[03:00]** Retrieval augmented generation is defined as a "
    "technique that grounds model outputs in retrieved documents.\n")


def _anchors(text: str, prioritized: bool):
    from workers.extract_worker import _evidence_spans, _pack

    return _evidence_spans(
        None, text, "chunk_fixture", _pack(), "lexical",
        scientific_lane_prioritized=prioritized)


def _profile(text: str) -> dict:
    from polymath_shared.knowledge_router.classifier import classify_document

    return classify_document(text)


@pytest.mark.parametrize("case_name, text, expected_primary", [
    ("A", CASE_A_PROCEDURAL, "PROCEDURAL"),
    ("B", CASE_B_CONCEPTUAL, "CONCEPTUAL"),
    ("C", CASE_C_NARRATIVE, "NARRATIVE"),
])
def test_deprioritized_primaries_still_discover_relational_evidence(
        case_name, text, expected_primary):
    """Cases A–C: the exact censorship class. The fixture PROVES the
    router deprioritizes the lane for this document, then PROVES local
    relational evidence still reaches candidate discovery."""
    prof = _profile(text)
    assert prof["primary_mode"] == expected_primary, prof
    assert "scientific_predicate" in prof["routing"]["disabled"], (
        f"fixture {case_name} no longer exercises the deprioritized "
        f"path: {prof['routing']}")

    prioritized = "scientific_predicate" not in prof["routing"]["disabled"]
    spans = _anchors(text, prioritized)
    assert len(spans) >= 1, (
        f"case {case_name}: locally eligible relational evidence was "
        f"vetoed by document classification")
    surfaces = {s.text.lower() for s in spans}
    assert surfaces & {"developed", "acquired", "uses"}, surfaces


def test_case_a_no_evidence_chunks_still_skip():
    """The router's PRIORITY role is real: under a deprioritized
    primary, a chunk with NO local relational evidence yields no
    spans (the cost optimization the router is allowed to be)."""
    spans = _anchors("Step 1. Open the panel.\nStep 2. Click save.\n",
                     False)
    assert spans == []


def test_case_d_scientific_primary_still_compiles_procedures():
    from polymath_shared.knowledge_objects.procedure import compile_procedure

    prof = _profile(CASE_D_SCIENTIFIC_WITH_PROCEDURE)
    assert prof["primary_mode"] == "SCIENTIFIC_RELATIONAL", prof
    proc = compile_procedure(
        document_id="doc_fixture", corpus_id="fixture",
        text=CASE_D_SCIENTIFIC_WITH_PROCEDURE,
        admitted_entities=[], source_chunk_ids=["chunk_fixture"])
    assert proc is not None and len(proc["steps"]) >= 2, proc


def test_case_e_scientific_primary_still_compiles_concepts():
    from polymath_shared.knowledge_objects.concept import compile_concepts
    from workers.summarizer import split_sentences

    prof = _profile(CASE_E_SCIENTIFIC_WITH_CONCEPT)
    assert prof["primary_mode"] == "SCIENTIFIC_RELATIONAL", prof
    concepts = compile_concepts(
        document_id="doc_fixture", corpus_id="fixture",
        sentences=split_sentences(CASE_E_SCIENTIFIC_WITH_CONCEPT),
        admitted_entities=[], source_chunk_ids=["chunk_fixture"])
    assert len(concepts) >= 1, concepts


def test_case_f_mixed_transcript_executes_all_three_lanes():
    from polymath_shared.knowledge_objects.concept import compile_concepts
    from polymath_shared.knowledge_objects.procedure import compile_procedure
    from workers.summarizer import split_sentences

    prof = _profile(CASE_F_MIXED_TRANSCRIPT)
    prioritized = "scientific_predicate" not in prof["routing"]["disabled"]

    spans = _anchors(CASE_F_MIXED_TRANSCRIPT, prioritized)
    assert len(spans) >= 1, "transcript relational lane did not execute"

    proc = compile_procedure(
        document_id="doc_fixture", corpus_id="fixture",
        text=CASE_F_MIXED_TRANSCRIPT,
        admitted_entities=[], source_chunk_ids=["chunk_fixture"])
    assert proc is not None, "transcript procedure lane did not execute"

    concepts = compile_concepts(
        document_id="doc_fixture", corpus_id="fixture",
        sentences=split_sentences(CASE_F_MIXED_TRANSCRIPT),
        admitted_entities=[], source_chunk_ids=["chunk_fixture"])
    assert len(concepts) >= 1, "transcript concept lane did not execute"


class _RecordingConn:
    """Records INSERT targets so lane EXECUTION is observable without a
    database."""

    def __init__(self):
        self.tables: list[str] = []

    def execute(self, sql, args=None):
        head = " ".join(str(sql).split())[:80].lower()
        if head.startswith("insert into"):
            self.tables.append(head.split()[2])


def test_artifact_persistence_ignores_router_disabled(monkeypatch):
    """Adversarial: even a classifier verdict disabling EVERY lane
    cannot stop the self-gating compilers from evaluating eligible
    content (classification is priority metadata, not authorization)."""
    import polymath_shared.knowledge_router.classifier as clf
    from workers import extract_worker

    monkeypatch.setattr(
        clf, "classify_document",
        lambda text, metadata=None: {
            "router_version": "test", "primary_mode": "NARRATIVE",
            "modes": [],
            "routing": {"always": [], "preferred": [], "optional": [],
                        "disabled": ["scientific_predicate", "procedure",
                                      "concept"]},
            "enabled_extractors": [], "signals": {},
        })

    conn = _RecordingConn()
    counts = extract_worker._persist_knowledge_artifacts(
        conn, corpus_id="fixture", doc_id="doc_fixture",
        doc_text=CASE_F_MIXED_TRANSCRIPT,
        chunk_ids=["chunk_fixture"], durable_surfaces=["Redis"])
    assert counts["procedures"] >= 1, counts
    assert counts["concepts"] >= 1, counts
    assert "procedure_artifacts" in conn.tables
    assert "concept_artifacts" in conn.tables
    # The verdict that would have censored is preserved as metadata.
    assert counts["routing_disabled"] == [
        "concept", "procedure", "scientific_predicate"]
