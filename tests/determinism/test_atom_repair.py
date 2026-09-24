"""ATOM-REPAIR-V1 (owner 2026-09-24, decision D4 "alongside"): a document keeps its base-profile atoms (~10 theories /
concepts / seealso) AND its vNext atoms (one per kind, incl. the latent kinds). Supersession is scoped to one profile family
by the `source` tag, so neither family can deactivate the other again (the 2026-09-08 regression), and the repair script
re-derives both families from each book's own artifacts. In-memory table + Qdrant fakes; no database."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import profile_atom as PA
from polymath_shared.document_profile import (
    profile_atom_projection as PAP,
)

_spec = importlib.util.spec_from_file_location("repair_profile_atoms", ROOT / "scripts" / "repair_profile_atoms.py")
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)                                    # type: ignore[union-attr]

CONTRACT = "rag-profile-v3"
BASE = {"theories": [f"base theory {i}" for i in range(10)], "concepts": [f"base concept {i}" for i in range(10)],
        "seealso": [f"base seealso {i}" for i in range(10)], "questions": ["not an atom surface"]}
VNEXT = {"theories": ["vnext theory"], "concepts": ["vnext concept"], "latent_pattern": ["a pattern recurs"],
         "anchor": ["the anchor book"], "recallq": ["which book anchors this?"]}


class _Rows:
    def __init__(self, rows): self._rows = rows; self.rowcount = len(rows)
    def fetchall(self): return list(self._rows)


class TableConn:
    """`document_profile_atoms` in memory — just the statements profile_atom issues."""
    def __init__(self): self.rows: dict[str, dict] = {}

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("SELECT atom_id, source_profile_hash"):
            doc, contract = params
            return _Rows([(aid, r["src"]) for aid, r in self.rows.items()
                          if r["doc"] == doc and r["contract"] == contract and r["active"]])
        if s.startswith("UPDATE document_profile_atoms SET active=FALSE") and "ANY" in s:
            for aid in params[0]:
                self.rows[aid]["active"] = False
            return _Rows(params[0])
        if s.startswith("UPDATE document_profile_atoms SET active=FALSE"):
            doc, contract = params
            hit = [aid for aid, r in self.rows.items() if r["doc"] == doc and r["contract"] == contract and r["active"]]
            for aid in hit:
                self.rows[aid]["active"] = False
            return _Rows(hit)
        if s.startswith("INSERT INTO document_profile_atoms"):
            aid, doc, corpus, contract, kind, text, ordinal = params[:7]
            src = params[7] if len(params) > 7 else self.rows.get(aid, {}).get("src")
            self.rows[aid] = {"doc": doc, "corpus": corpus, "contract": contract, "kind": kind, "text": text,
                              "ordinal": ordinal, "src": src, "active": True}
            return _Rows([])
        if s.startswith("SELECT atom_id, doc_id, corpus_id"):
            doc = params[-1]
            return _Rows([(aid, r["doc"], r["corpus"], r["contract"], r["kind"], r["text"], r["ordinal"])
                          for aid, r in sorted(self.rows.items()) if r["active"] and r["doc"] == doc])
        raise AssertionError(f"unexpected SQL: {s[:80]}")

    def active(self, doc="d1"):
        return {r["text"] for r in self.rows.values() if r["active"] and r["doc"] == doc}


def _persist(conn, compiled, family, h):
    atoms = PA.extract_atoms(compiled, doc_id="d1", corpus_id="cinema", profile_contract=CONTRACT)
    return PA.persist_atoms(conn, doc_id="d1", profile_contract=CONTRACT, atoms=atoms, source=PA.source_tag(family, h))


def test_a_vnext_profile_never_deactivates_the_base_atoms_and_vice_versa():
    conn = TableConn()
    _persist(conn, BASE, "base", "b1")
    _persist(conn, VNEXT, "vnext", "v1")                        # the 2026-09-08 event, now family-scoped
    assert len(conn.active()) == 30 + 5                         # base 30 + vNext 5, side by side
    _persist(conn, {"theories": ["fresh base theory"]}, "base", "b2")
    assert "fresh base theory" in conn.active() and "base theory 3" not in conn.active()
    assert {"vnext theory", "a pattern recurs"} <= conn.active()            # a base regen keeps the vNext family
    assert {r["src"] for r in conn.rows.values() if r["active"]} == {"base:b2", "vnext:v1"}


def test_untagged_legacy_rows_are_superseded_by_the_first_tagged_persist_and_retagged_if_unchanged():
    conn = TableConn()
    legacy = PA.extract_atoms(VNEXT, doc_id="d1", corpus_id="cinema", profile_contract=CONTRACT)
    PA.persist_atoms(conn, doc_id="d1", profile_contract=CONTRACT, atoms=legacy)          # no source: the old path
    assert all(r["src"] is None for r in conn.rows.values())
    r = _persist(conn, VNEXT, "vnext", "v1")
    assert r["deactivated"] == 5 and r["family"] == "vnext" and len(conn.active()) == 5  # same ids → re-activated, tagged
    assert {x["src"] for x in conn.rows.values()} == {"vnext:v1"}


def test_the_source_must_name_a_known_family():
    with pytest.raises(ValueError):
        PA.persist_atoms(TableConn(), doc_id="d1", profile_contract=CONTRACT, atoms=[], source="d41d8cd9")
    with pytest.raises(ValueError):
        PA.source_tag("summary", "h")
    assert PA.family_of("base:abc") == "base" and PA.family_of("vnext:") == "vnext"
    assert PA.family_of(None) is None and PA.family_of("abc123") is None and PA.family_of("other:x") is None


class _Count:
    def __init__(self, n): self.count = n


class FakeQdrant:
    def __init__(self): self.upserts = []; self.deletes = 0
    def collection_exists(self, name): return True
    def create_collection(self, collection_name, vectors_config): pass
    def upsert(self, collection_name, points, wait=True): self.upserts.append(list(points))
    def count(self, name, count_filter=None, exact=True): return _Count(0)
    def delete(self, collection_name, points_selector, wait=True): self.deletes += 1


def test_family_scoped_ingest_rebuilds_the_docs_points_from_both_families():
    conn, q = TableConn(), FakeQdrant()
    embed = lambda texts: [[0.1, 0.2] for _ in texts]
    PAP.ingest_document_atoms(conn, q, embed=embed, embedding_contract_id="e", dim=2, doc_id="d1", corpus_id="cinema",
                              compiled=BASE, profile_contract=CONTRACT, source=PA.source_tag("base", "b1"))
    r = PAP.ingest_document_atoms(conn, q, embed=embed, embedding_contract_id="e", dim=2, doc_id="d1", corpus_id="cinema",
                                  compiled=VNEXT, profile_contract=CONTRACT, source=PA.source_tag("vnext", "v1"))
    assert r["active"] == 5 and r["projected_points"] == 35     # the doc's points == ALL its active rows
    assert {p.payload["text"] for p in q.upserts[-1]} == conn.active()


def test_the_repair_takes_each_books_latest_artifact_per_family_and_persists_vnext_then_base():
    rows = [("a1", 1, {"doc_profile": {"doc_id": "d1", "compiled": {"theories": ["old base"]}, "compiled_hash": "b0"}}),
            ("a2", 2, {"doc_profile": {"doc_id": "d1", "compiled": BASE, "compiled_hash": "b1", "prompt_version": "v3.2"}}),
            ("a3", 3, {"doc_profile": {"doc_id": "d1", "compiled": VNEXT, "compiled_hash": "v1", "vnext": True}}),
            ("a4", 4, {"doc_profile": {"doc_id": "d2", "compiled": {}, "compiled_hash": "x"}}),     # empty: ignored
            ("a5", 5, {"other": {}})]
    profiles = R.family_profiles(rows)
    assert set(profiles) == {"d1"} and profiles["d1"]["base"]["compiled_hash"] == "b1"      # the latest base wins
    steps = R.plan(profiles, corpus_id="cinema", profile_contract=CONTRACT)
    assert [src for src, _ in steps["d1"]] == ["vnext:v1", "base:b1"]
    assert [len(a) for _, a in steps["d1"]] == [5, 30]
    conn = TableConn()
    for src, atoms in steps["d1"]:
        PA.persist_atoms(conn, doc_id="d1", profile_contract=CONTRACT, atoms=atoms, source=src)
    assert len(conn.active()) == 35 and "old base" not in conn.active()


def test_the_worker_embeds_atoms_in_the_collections_query_mode(monkeypatch):
    sys.path.insert(0, str(ROOT / "workers"))
    from polymath_shared import clients

    from workers import doc_profile_worker as W
    kinds: list[str] = []

    class FakeEmbedder:
        def embed(self, texts, representation_kind):
            kinds.append(representation_kind)
            return {"vectors": [[0.0] for _ in texts]}
        def close(self): pass

    monkeypatch.setattr(clients, "EmbedderClient", FakeEmbedder)
    assert len(W._embed_atom_texts(["a", "b", "c"])) == 3 and set(kinds) == {"query"}
    src = (ROOT / "workers" / "workers" / "doc_profile_worker.py").read_text()
    assert 'source=PA.source_tag("vnext" if vnext else "base", compiled_hash)' in src   # the ingest is family-scoped
