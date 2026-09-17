"""PROFILE-ATOM ingest wiring (P4a part 2) — the atom lane is pipeline-maintained: a compiled
profile's atom surfaces are extracted, persisted (Postgres authority), the doc's stale points
purged, and the new set projected. Fakes for the connection + Qdrant client."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import profile_atom_projection as PAP  # noqa: E402

COMPILED = {
    "theories": ["perceived force is inferred from the receiver's reaction", "editing hides the pull"],
    "concepts": ["reaction timing"],
    "seealso": ["animation timing of impacts"],
    "bridge": ["editing decision hierarchy informs choreography"],
    "tension": ["spectacle vs emotional continuity"],
    "questions": ["these are not atom surfaces"],   # ignored by extract_atoms
}


class _Cur:
    rowcount = 0


class FakeConn:
    def __init__(self): self.sql = []
    def execute(self, sql, params=None):
        self.sql.append((sql.split()[0], params)); return _Cur()


class _Count:
    def __init__(self, n): self.count = n


class FakeQdrant:
    def __init__(self, exists=False, existing=0):
        self.exists = exists; self.existing = existing
        self.created = []; self.upserts = []; self.deletes = []
    def collection_exists(self, name): return self.exists
    def create_collection(self, collection_name, vectors_config): self.created.append(collection_name); self.exists = True
    def upsert(self, collection_name, points, wait=True): self.upserts.append((collection_name, list(points)))
    def count(self, name, count_filter=None, exact=True): return _Count(self.existing)
    def delete(self, collection_name, points_selector, wait=True): self.deletes.append(collection_name)


def stub_embed(texts): return [[0.1, 0.2, 0.3, 0.4, 0.5] for _ in texts]


def test_ingest_extracts_persists_and_projects_the_atom_surfaces():
    conn = FakeConn(); q = FakeQdrant(exists=False)
    r = PAP.ingest_document_atoms(conn, q, embed=stub_embed, embedding_contract_id="embed_abc", dim=5,
                                  doc_id="doc_1", corpus_id="cinema", compiled=COMPILED, profile_contract="rag-profile-v3")
    # 6 atom items across THEORY(2)/CONCEPT(1)/SEEALSO(1)/BRIDGE(1)/TENSION(1); "questions" ignored
    assert r["ok"] is True and r["active"] == 6
    assert r["by_kind"] == {"THEORY": 2, "CONCEPT": 1, "SEEALSO": 1, "BRIDGE": 1, "TENSION": 1}
    assert r["projected_points"] == 6 and r["collection"] == "polymath_document_profile_atoms_embed_abc"
    inserts = [c for c in conn.sql if c[0] == "INSERT"]
    assert len(inserts) == 6 and conn.sql[0][0] == "UPDATE"          # supersede-then-insert
    assert len(q.upserts) == 1 and len(q.upserts[0][1]) == 6         # one atom point per surface item


def test_ingest_is_per_doc_purge_then_project_for_a_clean_rebuild():
    conn = FakeConn(); q = FakeQdrant(exists=True, existing=9)       # 9 stale points for this doc
    r = PAP.ingest_document_atoms(conn, q, embed=stub_embed, embedding_contract_id="e", dim=5,
                                  doc_id="doc_1", corpus_id="cinema", compiled=COMPILED, profile_contract="c")
    assert r["purged_points"] == 9 and q.deletes == ["polymath_document_profile_atoms_e"]
    assert r["projected_points"] == 6                                # the doc's points now == active atoms


def test_purge_doc_is_a_noop_when_the_collection_is_absent():
    assert PAP.purge_doc(FakeQdrant(exists=False), "e", "doc_1") == 0
    q = FakeQdrant(exists=True, existing=4)
    assert PAP.purge_doc(q, "e", "doc_1") == 4 and q.deletes == ["polymath_document_profile_atoms_e"]


def test_empty_profile_projects_nothing_but_still_supersedes():
    conn = FakeConn(); q = FakeQdrant(exists=True, existing=0)
    r = PAP.ingest_document_atoms(conn, q, embed=stub_embed, embedding_contract_id="e", dim=5,
                                  doc_id="d", corpus_id="c", compiled={"questions": ["x"]}, profile_contract="c")
    assert r["active"] == 0 and r["projected_points"] == 0
    assert conn.sql[0][0] == "UPDATE" and q.upserts == []            # supersede ran, nothing projected
