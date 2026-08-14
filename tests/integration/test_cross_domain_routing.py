"""G1 acceptance: cross-domain document routing.

The validation query cannot be answered by one document/domain. The
system must independently discover the conceptually complementary
sources — document routing does conceptual work; it never reduces to
"the most literal phrase wins", and it is never a recall gate (a child
hit survives even when its document scores zero).

Requires live stores: POLYMATH_INTEGRATION=1 (make db-up).
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("POLYMATH_INTEGRATION") != "1",
        reason="set POLYMATH_INTEGRATION=1 with live stores (make db-up)",
    ),
]

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.identity import content_hash, run_id  # noqa: E402
from polymath_shared.retrieval import lexical_score, run_lanes, score_profile  # noqa: E402
from workers.document_profile_builder import build_profile  # noqa: E402
from orchestrator.orchestrator.api.retrieve import _qdrant_search  # noqa: E402

VALIDATION_QUERY = (
    "How should a deterministic knowledge system combine linguistic "
    "predicate compilation, explicit prompt-graph structure, and "
    "generator/evaluator loops to build an autonomous agent that can "
    "retrieve cross-domain evidence, act on it, verify its own work "
    "without self-approval, and preserve auditable provenance?"
)

SOURCES = {
    "predicate-compiler": {
        "parents": [
            "Deterministic relation extraction uses GLiNER span proposal "
            "plus lexical semantic resources: VerbNet, PropBank, FrameNet, "
            "and SemLink feed a compiled predicate rule system. Linguistic "
            "predicate compilation maps evidence spans onto canonical "
            "predicates with ontology validation and idempotent persistence.",
            "Argument orientation normalizes active and passive voice "
            "through dependency structure. Evidence carries provenance and "
            "rule identifiers so every graph assertion is auditable.",
        ],
        "facts": [("compiler", "uses", "VerbNet"), ("GLiNER", "part_of", "pipeline")],
    },
    "loop-engineering": {
        "parents": [
            "Autonomous agents run generator and evaluator loops. The "
            "generator proposes work and the evaluator verifies it "
            "independently; self-approval is forbidden. Verification "
            "results persist to durable state before the next loop.",
            "Discovery hands off to verification, then persistence, then "
            "scheduling. Each loop is bounded and auditable.",
        ],
        "facts": [("evaluator", "causes", "verification"), ("agent", "uses", "loop")],
    },
    "prompt-graph": {
        "parents": [
            "Prompt graph engineering treats the workflow as an explicit "
            "graph artifact with executable semantics. Structure is "
            "separated from prompt content; routing is first-class "
            "orchestration, not buried in prose.",
        ],
        "facts": [("prompt graph", "is_a", "artifact")],
    },
    "closed-loop-quality": {
        "parents": [
            "Closed loop quality engineering models downstream feedback "
            "signals feeding later decisions. Verification signals are "
            "bounded feedback architecture: measure, decide, apply, repeat.",
        ],
        "facts": [("feedback", "influences", "decisions")],
    },
    "unrelated-cooking": {
        "parents": [
            "This cookbook covers baking techniques for sourdough bread, "
            "croissants, and pastry lamination. Fermentation times and "
            "oven temperatures are documented per recipe.",
        ],
        "facts": [("sourdough", "uses", "flour")],
    },
    "unrelated-gardening": {
        "parents": [
            "Seasonal gardening covers soil preparation, irrigation "
            "schedules, and pruning calendars for temperate climates.",
        ],
        "facts": [("garden", "located_in", "backyard")],
    },
}

# G2 harder-validation sources. Kept OUT of the frozen G1 fixture: the
# golden trace must not change when the adversarial set grows.
G2_EXTRA_SOURCES = {
    "hidden-evidence": {
        "parents": [
            "Tomato plants need consistent watering and support. "
            "Compost improves soil structure over several seasons. "
            "Pruning herbs encourages bushy growth. "
            "Raised beds drain better than clay soil. "
            "Mulch keeps moisture in during hot weeks. "
            "The system runs generator and evaluator loops for verification.",
        ],
        "facts": [("garden", "located_in", "backyard")],
    },
    "surface-noise": {
        "parents": [
            "This cooking show features a knowledge system for recipe "
            "retrieval. Its linguistic garnish combines predicate sauces "
            "with generator gadgets, but the recipes themselves verify "
            "nothing: it is entertainment about kitchens, loops of "
            "batter, and agent-less baking.",
        ],
        "facts": [("recipe", "uses", "flour")],
    },
}


def _profile_for_query(query: str, profiles: list[dict]) -> list[str]:
    return run_lanes(
        query,
        fetch_profiles=lambda: profiles,
        fetch_parents=lambda: parents_for_profiles(profiles),
        fetch_children=lambda limit: children_for_profiles(profiles)[:limit],
        child_search=lambda limit: children_for_profiles(profiles)[:limit],
    )


def parents_for_profiles(profiles: list[dict]) -> list[dict]:
    with tx() as conn:
        return [
            {"chunk_id": r[0], "doc_id": r[1], "summary": r[2]}
            for r in conn.execute(
                "SELECT chunk_id, doc_id, summary FROM chunks WHERE tier = 'parent'"
            ).fetchall()
        ]


def children_for_profiles(profiles: list[dict]) -> list[dict]:
    with tx() as conn:
        return [
            {"chunk_id": r[0], "doc_id": r[1], "parent_id": r[2] or "", "text": r[3]}
            for r in conn.execute(
                "SELECT chunk_id, doc_id, parent_id, text FROM chunks WHERE tier = 'child'"
            ).fetchall()
        ]


def _make_run(corpus_id: str, text: str) -> str:
    # Content marker keeps the content-hashed document identity unique per
    # corpus (the same source text otherwise maps to one doc id).
    text = text + f" Corpus marker: {corpus_id}."
    canonical = {
        "corpus_id": corpus_id,
        "source_name": f"{corpus_id}.txt",
        "media_type": "text/plain",
        "content_b64": base64.b64encode(text.encode()).decode(),
        "config": {},
    }
    rid = run_id(corpus_id, canonical)
    with tx() as conn:
        conn.execute(
            "DELETE FROM runs WHERE corpus_id = %s", (corpus_id,)
        )
        conn.execute(
            "DELETE FROM documents WHERE corpus_id = %s", (corpus_id,)
        )
        conn.execute(
            "DELETE FROM corpora WHERE corpus_id = %s", (corpus_id,)
        )
        conn.execute(
            "INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s, %s, 'intake', %s)",
            (rid, corpus_id, json.dumps({"intake_payload": canonical})),
        )
        conn.execute(
            """
            INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key)
            VALUES (%s, 'intake.v1', %s, %s)
            """,
            (rid, json.dumps(canonical), content_hash({"run": rid, "intake": corpus_id})),
        )
    return rid


def _run_intake(run: str, text: str) -> None:
    from workers.intake_worker import process_event

    with tx() as conn:
        payload = conn.execute(
            "SELECT metadata->'intake_payload' FROM runs WHERE run_id = %s", (run,)
        ).fetchone()[0]
        process_event(conn, {"run_id": run, "payload": payload, "idempotency_key": "t"})


def _build_profiles(run: str, text: str, facts: list[tuple[str, str, str]]) -> None:
    from workers.profile_worker import process_event

    with tx() as conn:
        corpus = conn.execute(
            "SELECT corpus_id FROM runs WHERE run_id = %s", (run,)
        ).fetchone()[0]
        doc_id = conn.execute(
            "SELECT doc_id FROM documents WHERE corpus_id = %s", (corpus,)
        ).fetchone()[0]
        # Deterministic entity rows for the profile builder (surface only).
        for subj, _, obj in facts:
            for surface, core in ((subj, "Technology"), (obj, "Technology")):
                from polymath_shared.identity import entity_id

                conn.execute(
                    "INSERT INTO entities (entity_id, core_type, normalized_surface) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                    (entity_id(core, surface), core, surface),
                )
        process_event(conn, {"run_id": run, "payload": {"run_id": run}, "idempotency_key": "t"})


class TestCrossDomainRouting:
    def test_router_discovers_complementary_sources(self) -> None:
        # One document per source, each built through the REAL intake +
        # profile workers, so the routing lane is production-shaped.
        # Wipe stale cd-* state first: the golden fixture must contain
        # exactly the frozen sources.
        with tx() as conn:
            for (cid,) in conn.execute(
                "SELECT DISTINCT corpus_id FROM runs WHERE corpus_id LIKE 'cd-%'"
            ).fetchall():
                conn.execute("DELETE FROM runs WHERE corpus_id = %s", (cid,))
                conn.execute("DELETE FROM documents WHERE corpus_id = %s", (cid,))
                conn.execute("DELETE FROM corpora WHERE corpus_id = %s", (cid,))
        for source, spec in SOURCES.items():
            src_run = _make_run(f"cd-{source}", spec["parents"][0] + ". " + spec["parents"][-1])
            _run_intake(src_run, spec["parents"][0] + ". " + spec["parents"][-1])
            _build_profiles(src_run, spec["parents"][0], spec["facts"])

        with tx() as conn:
            profiles = [
                {"doc_id": r[0], "retrieval_profile": r[1]}
                for r in conn.execute(
                    """
                    SELECT d.doc_id, d.retrieval_profile FROM documents d
                     WHERE d.corpus_id LIKE 'cd-%' AND d.retrieval_profile IS NOT NULL
                    """
                ).fetchall()
            ]
            parents = [
                {"chunk_id": r[0], "doc_id": r[1], "summary": r[2]}
                for r in conn.execute(
                    """
                    SELECT c.chunk_id, c.doc_id, c.summary FROM chunks c
                      JOIN documents d ON d.doc_id = c.doc_id
                     WHERE c.tier = 'parent' AND d.corpus_id LIKE 'cd-%'
                    """
                ).fetchall()
            ]
            children = [
                {"chunk_id": r[0], "doc_id": r[1], "parent_id": r[2] or "",
                 "text": r[3]}
                for r in conn.execute(
                    """
                    SELECT c.chunk_id, c.doc_id, c.parent_id, c.text FROM chunks c
                      JOIN documents d ON d.doc_id = c.doc_id
                     WHERE c.tier = 'child' AND d.corpus_id LIKE 'cd-%'
                    """
                ).fetchall()
            ]

        result = run_lanes(
            VALIDATION_QUERY,
            fetch_profiles=lambda: profiles,
            fetch_parents=lambda: parents,
            fetch_children=lambda limit: children[:limit],
            child_search=lambda limit: children[:limit],
        )

        ranked_docs = [d["doc_id"] for d in result.selected_documents]

        def source_of(doc_id: str) -> str:
            with tx() as conn:
                row = conn.execute(
                    "SELECT source_name FROM documents WHERE doc_id = %s", (doc_id,)
                ).fetchone()
            return (row[0] or "").split(".")[0].removeprefix("cd-")

        ranked_sources = [source_of(d) for d in ranked_docs]

        # ── GOLDEN TRACE (frozen G1 behavior) ─────────────────────────
        # Loop Engineering rank 0, Predicate Compiler rank 1, Prompt
        # Graph rank 2. G2+ may improve ordering but must never destroy
        # the multi-source discovery behavior; unrelated filler must
        # stay out of the top ranks.
        assert ranked_sources[:3] == [
            "loop-engineering",
            "predicate-compiler",
            "prompt-graph",
        ], f"golden trace broken; ranked: {ranked_sources}"

        unrelated = {"unrelated-cooking", "unrelated-gardening"}
        top_half = ranked_sources[:4]
        assert not (set(top_half) & unrelated), (
            f"unrelated sources leaked into the top ranks: {top_half}"
        )

    def test_document_routing_is_not_a_recall_gate(self) -> None:
        """A child hit survives even when its document scores zero."""
        profiles = [{
            "doc_id": "doc_zero",
            "retrieval_profile": {
                "semantic_summary": "nothing relevant to the query",
                "core_concepts": ["unrelated"],
                "primary_domains": ["unrelated_domain"],
            },
        }]
        children = [
            {"chunk_id": "c1", "doc_id": "doc_zero", "parent_id": "p1",
             "text": "exact evidence about linguistic predicate compilation"}
        ]
        result = run_lanes(
            "linguistic predicate compilation",
            fetch_profiles=lambda: profiles,
            fetch_parents=lambda: [],
            fetch_children=lambda limit: children[:limit],
            child_search=lambda limit: children[:limit],
        )
        assert result.document_ranking == []  # the document scored zero...
        assert [c["chunk_id"] for c in result.selected_children] == ["c1"]  # ...yet the child survives


class TestG2HarderValidation:
    def _setup_sources(self, extra_sources: dict) -> tuple[list[dict], list[dict], list[dict]]:
        for source, spec in {**SOURCES, **extra_sources}.items():
            text = spec["parents"][0] + ". " + spec["parents"][-1]
            src_run = _make_run(f"g2-{source}", text)
            _run_intake(src_run, text)
            _build_profiles(src_run, spec["parents"][0], spec["facts"])
        with tx() as conn:
            profiles = [
                {"doc_id": r[0], "retrieval_profile": r[1]}
                for r in conn.execute(
                    "SELECT d.doc_id, d.retrieval_profile FROM documents d WHERE d.corpus_id LIKE 'g2-%' AND d.retrieval_profile IS NOT NULL"
                ).fetchall()
            ]
            parents = [
                {"chunk_id": r[0], "doc_id": r[1], "summary": r[2]}
                for r in conn.execute(
                    "SELECT c.chunk_id, c.doc_id, c.summary FROM chunks c JOIN documents d ON d.doc_id = c.doc_id WHERE c.tier = 'parent' AND d.corpus_id LIKE 'g2-%'"
                ).fetchall()
            ]
            children = [
                {"chunk_id": r[0], "doc_id": r[1], "parent_id": r[2] or "", "text": r[3]}
                for r in conn.execute(
                    "SELECT c.chunk_id, c.doc_id, c.parent_id, c.text FROM chunks c JOIN documents d ON d.doc_id = c.doc_id WHERE c.tier = 'child' AND d.corpus_id LIKE 'g2-%'"
                ).fetchall()
            ]
        return profiles, parents, children

    def _source_of(self, doc_id: str) -> str:
        with tx() as conn:
            row = conn.execute(
                "SELECT source_name FROM documents WHERE doc_id = %s", (doc_id,)
            ).fetchone()
        name = (row[0] or "").split(".")[0]
        for prefix in ("g2-", "cd-"):
            name = name.removeprefix(prefix)
        return name

    def test_query_without_headline_terminology(self) -> None:
        """Gate 7a: the query names none of the document's headline
        concepts, yet routing finds it from supporting vocabulary."""
        profiles, parents, children = self._setup_sources({})
        query = "How can span detection and ontology validation turn sentences into graph triples?"
        result = run_lanes(
            query,
            fetch_profiles=lambda: profiles,
            fetch_parents=lambda: parents,
            fetch_children=lambda limit: children[:limit],
            child_search=lambda limit: children[:limit],
        )
        top = [self._source_of(d["doc_id"]) for d in result.selected_documents[:2]]
        assert "predicate-compiler" in top, f"expected predicate-compiler in top 2; got {top}"

    def test_child_conflicts_with_document_routing(self) -> None:
        """Gate 7b: the evidence child belongs to a document whose
        PROFILE points elsewhere. The child must survive, and the
        document semantic lane must not rank the hiding document."""
        profiles, parents, children = self._setup_sources(G2_EXTRA_SOURCES)
        query = "generator evaluator verification loops"
        result = run_lanes(
            query,
            fetch_profiles=lambda: profiles,
            fetch_parents=lambda: parents,
            fetch_children=lambda limit: children[:limit],
            child_search=lambda limit: children[:limit],
        )
        evidence_texts = [c.get("text", "") for c in result.selected_children]
        assert any("generator and evaluator loops" in t for t in evidence_texts), (
            "hidden child evidence must survive child routing"
        )
        lane_docs = [self._source_of(h.document_id) for h in result.document_ranking]
        assert "hidden-evidence" not in lane_docs, (
            f"document semantic lane must not rank the hiding document: {lane_docs}"
        )

    def test_two_domains_required_simultaneously(self) -> None:
        """Gate 7c: the validation query needs Loop + Compiler + Prompt
        Graph at once. On the adversarial fixture the trio must all
        appear in the top ranks; the exact ordering golden lives in the
        frozen G1 fixture (cd- corpora)."""
        profiles, parents, children = self._setup_sources(G2_EXTRA_SOURCES)
        result = run_lanes(
            VALIDATION_QUERY,
            fetch_profiles=lambda: profiles,
            fetch_parents=lambda: parents,
            fetch_children=lambda limit: children[:limit],
            child_search=lambda limit: children[:limit],
        )
        ranked = [self._source_of(d["doc_id"]) for d in result.selected_documents]
        assert {
            "loop-engineering", "predicate-compiler", "prompt-graph"
        } <= set(ranked[:4]), f"complementary trio missing from top ranks: {ranked[:4]}"

    @pytest.mark.skipif(
        os.environ.get("POLYMATH_G3_RERANKER") != "1",
        reason="cross-representation noise discrimination belongs to the G3 reranker (fusion is rank-based, no score normalization)",
    )
    def test_surface_vocabulary_noise_stays_out(self) -> None:
        """Gate 7f: a document sharing query vocabulary in irrelevant
        contexts must not outrank the conceptually matching sources.
        The lexical lanes promote it on surface overlap; the G3 reranker
        over the FUSED candidates is where cross-representation
        discrimination happens (G2 fusion is rank-based by design)."""
        profiles, parents, children = self._setup_sources(G2_EXTRA_SOURCES)
        result = run_lanes(
            VALIDATION_QUERY,
            fetch_profiles=lambda: profiles,
            fetch_parents=lambda: parents,
            fetch_children=lambda limit: children[:limit],
            child_search=lambda limit: _qdrant_search(VALIDATION_QUERY, None, limit),
        )
        ranked = [self._source_of(d["doc_id"]) for d in result.selected_documents]
        assert "surface-noise" not in ranked[:3], (
            f"surface-vocabulary noise outranked the complementary sources: {ranked[:3]}"
        )

    @pytest.mark.skipif(
        os.environ.get("POLYMATH_NEURAL_EMBEDDER") != "1",
        reason="requires the neural embedder sidecar (G2 dense lane)",
    )
    def test_dense_finds_conceptual_evidence_lexical_misses(self) -> None:
        """Gate 7e: conceptual evidence with ZERO shared vocabulary is a
        dense-lane property. The lexical lanes must find nothing; the
        dense lane must find the conceptually matching sources."""
        profiles, parents, children = self._setup_sources(G2_EXTRA_SOURCES)
        query = "How should machines turn words into structured knowledge?"
        result = run_lanes(
            query,
            fetch_profiles=lambda: profiles,
            fetch_parents=lambda: parents,
            fetch_children=lambda limit: children[:limit],
            child_search=lambda limit: _qdrant_search(query, None, limit),
        )
        # Lexical lanes: the conceptual sources must NOT match — the
        # query shares no vocabulary with them by construction (a stray
        # single-token hit on a noise doc is acceptable lexical noise).
        lexical_docs = {self._source_of(h.document_id) for h in result.document_ranking}
        assert not ({"predicate-compiler", "loop-engineering", "prompt-graph"} & lexical_docs), (
            f"lexical lane matched a conceptual source: {lexical_docs}"
        )
        lexical_child_docs = {
            self._source_of(h.document_id) for h in result.child_lexical_ranking
        }
        assert not ({"predicate-compiler", "loop-engineering", "prompt-graph"} & lexical_child_docs)
        # Dense lane: the conceptually matching sources rise.
        assert result.child_dense_ranking, "neural dense lane returned no hits"
        dense_docs = {h.document_id for h in result.child_dense_ranking}
        matched_sources = {self._source_of(d) for d in dense_docs}
        assert {"predicate-compiler", "loop-engineering"} & matched_sources, (
            f"dense lane missed the conceptual sources: {matched_sources}"
        )
