"""FACET-RETRIEVAL-V1 F4 — the stored shape of a section profile is what the profile lanes read.

Through the SAME primitives the dualread door, the scout's probes, the see-also blend and the fan-out call
(`projection.profile_nominate`, `profile_atom_projection.search_atoms`, `profile_scout.*`,
`parent_map_projection.search_parent_maps`), against an in-memory index: a giant document reached only through
its section points is nominated ONCE (its sections collapse onto the document and cannot crowd other documents
out of the top-k); its section atoms route to the document; the scout fuses both; the parent-map search
filtered to the nominated document lands on the section's parents. A collection with one point per document
nominates exactly as before F4.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from polymath_shared.document_profile import parent_map_projection as PMP
from polymath_shared.document_profile import profile_atom as PA
from polymath_shared.document_profile import profile_atom_projection as PAP
from polymath_shared.document_profile import profile_scout as PS
from polymath_shared.document_profile import projection as PJ
from polymath_shared.surface_registry import BY_KIND

RRF_K = 60


def _match(flt, payload) -> bool:
    if flt is None:
        return True

    def ok(c):
        v = payload.get(c.key)
        m = c.match
        return (v in list(m.any)) if hasattr(m, "any") else (v == m.value)
    return all(ok(c) for c in (flt.must or [])) and not any(ok(c) for c in (flt.must_not or []))


def _dot(a, b) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


class FakeIndex:
    """An in-memory Qdrant double: named vectors per point, payload filters, RRF fusion over prefetches."""

    def __init__(self):
        self.points: dict[tuple[str, str], dict] = {}
        self.collections: set[str] = set()
        self.seen_limits: list[int] = []

    def add(self, collection: str, pid: str, vectors: dict, payload: dict) -> None:
        self.collections.add(collection)
        self.points[(collection, pid)] = {"vector": vectors, "payload": payload}

    def collection_exists(self, name):
        return name in self.collections

    def create_collection(self, collection_name, vectors_config):
        self.collections.add(collection_name)

    def upsert(self, collection_name, points, wait=True):
        for p in points:
            self.add(collection_name, str(p.id), p.vector, dict(p.payload or {}))

    def _rank(self, collection, using, query, flt, limit):
        q = query[0] if query and isinstance(query[0], list) else query
        rows = []
        for (coll, pid), rec in self.points.items():
            if coll != collection or not _match(flt, rec["payload"]):
                continue
            v = rec["vector"].get(using)
            if v is None:
                continue
            vs = v if isinstance(v[0], list) else [v]
            rows.append((max(_dot(x, q) for x in vs), pid))
        rows.sort(key=lambda r: (-r[0], r[1]))
        return rows[:limit]

    def query_points(self, collection, prefetch=None, query=None, using=None, query_filter=None, limit=10, with_payload=None):
        self.seen_limits.append(limit)
        if prefetch:
            fused: dict[str, float] = {}
            for pre in prefetch:
                for rank, (_s, pid) in enumerate(self._rank(collection, pre.using, pre.query, pre.filter, pre.limit), start=1):
                    fused[pid] = fused.get(pid, 0.0) + 1.0 / (RRF_K + rank)
            ranked = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
        else:
            ranked = [(pid, s) for s, pid in self._rank(collection, using, query, query_filter, limit)]
        pts = []
        for pid, score in ranked:
            payload = self.points[(collection, pid)]["payload"]
            pts.append(type("Pt", (), {"id": pid, "score": score,
                                        "payload": {k: v for k, v in payload.items() if not with_payload or k in with_payload}})())
        return type("Res", (), {"points": pts})()

    def retrieve(self, collection_name, ids, with_payload=None, with_vectors=False):
        return [type("Pt", (), {"id": i, "payload": self.points[(collection_name, i)]["payload"]})()
                for i in ids if (collection_name, i) in self.points]

    def scroll(self, collection_name, scroll_filter=None, limit=256, with_payload=None, with_vectors=False, offset=None):
        pts = [type("Pt", (), {"id": pid, "payload": rec["payload"]})()
               for (coll, pid), rec in self.points.items() if coll == collection_name and _match(scroll_filter, rec["payload"])]
        return pts, None

    def count(self, collection_name, count_filter=None, exact=True):
        return type("C", (), {"count": sum(1 for (c, _p), r in self.points.items()
                                           if c == collection_name and _match(count_filter, r["payload"]))})()

    def delete(self, collection_name, points_selector, wait=True):
        for key in [k for k, r in self.points.items() if k[0] == collection_name and _match(points_selector.filter, r["payload"])]:
            del self.points[key]


CID = "embed_test"
PROFILES = PJ.collection_name(CID)
ATOMS = PAP.collection_name(CID)
MAPS = PMP.collection_name(CID)
Q_MOTION = [1.0, 0.0, 0.0]          # "granular motion control for a video model"
Q_COPY = [0.0, 1.0, 0.0]


def _profile_vectors(v):
    return {"title": v, "identity": v, "theme": v, "questions": [v], "searches": [v]}


def _index() -> FakeIndex:
    ix = FakeIndex()
    # the giant: its DOCUMENT point is about "CPCS / YAML" (the pre-F4 blank door), its SECTION points about motion
    ix.add(PROFILES, PJ.point_id("doc_hand"), _profile_vectors([0.05, 0.05, 1.0]),
           {"doc_id": "doc_hand", "corpus_id": "cinema", "scope": "document"})
    for i in range(12):
        key = f"sec{i:02d}"
        ix.add(PROFILES, PJ.section_point_id("doc_hand", key), _profile_vectors([1.0 - i * 0.01, 0.0, 0.0]),
               {"doc_id": "doc_hand", "corpus_id": "cinema", "scope": "section", "section_key": key,
                "parent_ids": [f"hand_p{i}_{j}" for j in range(3)]})
    # two ordinary documents with one point each
    ix.add(PROFILES, PJ.point_id("doc_adweek"), _profile_vectors([0.2, 1.0, 0.0]), {"doc_id": "doc_adweek", "corpus_id": "cinema", "scope": "document"})
    ix.add(PROFILES, PJ.point_id("doc_block"), _profile_vectors([0.6, 0.3, 0.0]), {"doc_id": "doc_block", "corpus_id": "cinema", "scope": "document"})
    # another corpus's point, never nominated for cinema
    ix.add(PROFILES, PJ.point_id("doc_other"), _profile_vectors([1.0, 0.0, 0.0]), {"doc_id": "doc_other", "corpus_id": "ecom", "scope": "document"})
    # section atoms of the giant (the DOCUMENT's doc_id) + a document atom of another book
    for i, text in enumerate(["control dialects differ per video model", "camera moves are a grammar", "emotion maps to motion"]):
        atom = PA.ProfileAtom(PA.atom_id("doc_hand", "rag-profile-v3", "CONCEPT", text, "sec03"), "doc_hand", "cinema",
                              "rag-profile-v3", "CONCEPT", text, i, scope="section", section_key="sec03", parent_ids=("hand_p3_0",))
        ix.add(ATOMS, PAP.point_id(atom.atom_id), {"atom": [1.0, 0.0, 0.0]}, PAP.build_payload(atom))
    ix.add(ATOMS, PAP.point_id("atom_block"), {"atom": [0.5, 0.5, 0.0]},
           {"doc_id": "doc_block", "corpus_id": "cinema", "atom_kind": "CONCEPT", "text": "contrast drives intensity", "ordinal": 0, "atom_id": "atom_block"})
    # parent maps: every section's parents of the giant, and the other books' parents
    for i in range(12):
        for j in range(3):
            ix.add(MAPS, PMP.point_id("doc_hand", f"hand_p{i}_{j}", "map-v1"), {PMP.VECTOR_NAME: [1.0 if i == 3 else 0.2, 0.0, 0.0]},
                   {"doc_id": "doc_hand", "parent_id": f"hand_p{i}_{j}", "alias": f"H{i}.{j}", "corpus_id": "cinema"})
    ix.add(MAPS, PMP.point_id("doc_block", "block_p0", "map-v1"), {PMP.VECTOR_NAME: [0.9, 0.0, 0.0]},
           {"doc_id": "doc_block", "parent_id": "block_p0", "alias": "B0", "corpus_id": "cinema"})
    return ix


def test_section_points_nominate_their_document_once_without_crowding_other_documents_out():
    ix = _index()
    docs = PJ.profile_nominate(ix, PROFILES, Q_MOTION, "cinema", k=3)
    assert set(docs) == {"doc_hand", "doc_block", "doc_adweek"} and len(docs) == 3   # 3 distinct documents
    assert docs.index("doc_hand") <= 1 and docs[-1] == "doc_adweek"          # the giant reaches the top through its sections
    assert "doc_other" not in docs
    assert ix.seen_limits[-2:] == [3, 3 * PJ.NOMINATE_OVERFETCH]                # the pre-F4 query, then the section pool
    # with the section points removed the giant's document point (about CPCS) no longer reaches the motion question
    for key in [k for k in ix.points if k[0] == PROFILES and ix.points[k]["payload"].get("scope") == "section"]:
        del ix.points[key]
    assert PJ.profile_nominate(ix, PROFILES, Q_MOTION, "cinema", k=3)[0] != "doc_hand"


def test_one_point_per_document_nominates_exactly_as_before_f4():
    ix = _index()
    for key in [k for k in ix.points if k[0] == PROFILES and ix.points[k]["payload"].get("scope") == "section"]:
        del ix.points[key]
    ix.seen_limits.clear()
    after = PJ.profile_nominate(ix, PROFILES, Q_COPY, "cinema", k=2)
    assert after == ["doc_adweek", "doc_block"] and ix.seen_limits[0] == 2       # the document query is the old query
    # the pre-F4 single query over the same index gives the same documents in the same order
    from qdrant_client.http import models as qm
    flt = qm.Filter(must=[qm.FieldCondition(key="corpus_id", match=qm.MatchValue(value="cinema"))])
    pre = [qm.Prefetch(query=([Q_COPY] if s in PJ.MULTI_SURFACES else Q_COPY), using=s, limit=2, filter=flt) for s in PJ.ANSWER_SURFACES]
    old = [p.payload["doc_id"] for p in ix.query_points(PROFILES, prefetch=pre, query=qm.FusionQuery(fusion=qm.Fusion.RRF), limit=2, with_payload=["doc_id"]).points]
    assert old == after


def test_section_atoms_route_to_their_document_and_the_scout_fuses_both_projections():
    ix = _index()
    rows = PAP.search_atoms(ix, ATOMS, Q_MOTION, ("CONCEPT",), k=4, corpus_ids=["cinema"])
    assert [r["doc_id"] for r in rows][:3] == ["doc_hand"] * 3 and rows[0]["text"] and rows[0]["atom_id"]
    profile_hits = PS.profile_hits_from_doc_ids(PJ.profile_nominate(ix, PROFILES, Q_MOTION, "cinema", k=3))
    atom_hits = PS.atom_hits_from_search(rows, group_of=lambda k: BY_KIND[k].group if k in BY_KIND else None)
    result = PS.fuse_profile_scout_hits(profile_hits, atom_hits)
    top = result.nominations[0]
    assert top.doc_id == "doc_hand" and {c.source for c in top.contributions} == {"profile", "atom"}
    assert top.representative_text and "CONCEPT" in top.matched_surfaces
    # the see-also blend reads the atoms OF the question's documents: the giant's section atoms are its atoms
    own = PAP.search_atoms(ix, ATOMS, Q_MOTION, ("CONCEPT",), k=8, corpus_ids=["cinema"], doc_ids=["doc_hand"])
    assert own and all(r["doc_id"] == "doc_hand" for r in own)


def test_the_parent_map_search_filtered_to_the_nominated_document_lands_on_the_section():
    ix = _index()
    docs = PJ.profile_nominate(ix, PROFILES, Q_MOTION, "cinema", k=2)
    maps = PMP.search_parent_maps(ix, MAPS, Q_MOTION, docs, k=3)
    assert [m["doc_id"] for m in maps] == ["doc_hand"] * 3
    section = ix.points[(PROFILES, PJ.section_point_id("doc_hand", "sec03"))]["payload"]
    assert {m["parent_id"] for m in maps} == set(section["parent_ids"])       # the document AND its section


def test_project_profile_writes_the_section_shape_and_the_section_helpers_read_it():
    ix = FakeIndex()
    reps = {"identity": "Motion core\nTopics: motion, control", "theme": "How control dialects differ per model.",
            "questions": ["How do I direct camera motion?"], "searches": ["granular motion control"], "theories": [], "concepts": [], "seealso": []}
    section = {"key": "abc123", "title": "04. Motion core", "heading_path": ("04. Motion core",), "parent_ids": ("p1", "p2"), "parent_count": 2, "ordinal": 4}
    r = PJ.project_profile(ix, embed=lambda ts: [[0.1, 0.2, 0.3] for _ in ts], embedding_contract_id=CID, dim=3, doc_id="doc_hand",
                           corpus_id="cinema", title="handbook › 04. Motion core", representations=reps,
                           source_doc_hash="sha_section", schema_version="rag-profile-v3", prompt_version="doc-profile-v3.2",
                           compiled_hash="c1", section=section, input_hash="in1", payload_extra={"compiled": {"one": "x"}})
    assert r["point_id"] == PJ.section_point_id("doc_hand", "abc123") != PJ.point_id("doc_hand") and r["scope"] == "section"
    payload = ix.points[(PROFILES, r["point_id"])]["payload"]
    assert payload["scope"] == "section" and payload["doc_id"] == "doc_hand" and payload["parent_ids"] == ["p1", "p2"]
    assert payload["section_key"] == "abc123" and payload["section_title"] == "04. Motion core" and payload["input_hash"] == "in1"
    assert payload["section_ordinal"] == 4 and payload["heading_path"] == ["04. Motion core"] and payload["compiled"] == {"one": "x"}
    # a document point carries the document scope; the section helpers see only section points
    rd = PJ.project_profile(ix, embed=lambda ts: [[0.1, 0.2, 0.3] for _ in ts], embedding_contract_id=CID, dim=3, doc_id="doc_hand",
                            corpus_id="cinema", title="handbook", representations=reps, source_doc_hash="sha_doc",
                            schema_version="rag-profile-v3", prompt_version="doc-profile-v3.2", compiled_hash="c0")
    assert rd["scope"] == "document" and ix.points[(PROFILES, PJ.point_id("doc_hand"))]["payload"]["scope"] == "document"
    listed = PJ.list_section_points(ix, CID, "doc_hand")
    assert set(listed) == {"abc123"} and listed["abc123"]["input_hash"] == "in1" and listed["abc123"]["point_id"] == r["point_id"]
    assert PJ.fetch_existing_surfaces(ix, CID, "doc_hand", section_key="abc123") == {"title": 1, "identity": 1, "theme": 1, "questions": 1, "searches": 1}
    assert PJ.fetch_existing_point(ix, CID, "doc_hand")["scope"] == "document"
    assert PJ.purge_section_points(ix, CID, "doc_hand", keep_keys=["abc123"]) == 0
    assert PJ.purge_section_points(ix, CID, "doc_hand") == 1 and PJ.list_section_points(ix, CID, "doc_hand") == {}
    assert (PROFILES, PJ.point_id("doc_hand")) in ix.points                   # the document point stands


def test_section_atoms_have_their_own_ids_family_and_payload():
    compiled = {"concepts": ["reaction timing"], "seealso": ["animation timing"], "questions": ["ignored"]}
    doc_atoms = PA.extract_atoms(compiled, doc_id="d", corpus_id="c", profile_contract="p")
    sec_atoms = PA.extract_atoms(compiled, doc_id="d", corpus_id="c", profile_contract="p", section_key="k1", parent_ids=("p1",))
    assert [a.atom_id for a in doc_atoms] != [a.atom_id for a in sec_atoms]
    assert all(a.scope == "section" and a.section_key == "k1" and a.parent_ids == ("p1",) and a.doc_id == "d" for a in sec_atoms)
    assert all(a.scope == "document" and a.section_key is None for a in doc_atoms)
    assert PA.atom_id("d", "p", "CONCEPT", "reaction timing") == doc_atoms[0].atom_id     # pre-F4 ids unchanged
    tag = PA.source_tag("section", "hash9", "k1")
    assert tag == "section:k1:hash9" and PA.family_of(tag) == "section" and PA.section_key_of(tag) == "k1"
    assert PA.section_key_of("base:hash") is None and PA.family_of("vnext:h") == "vnext"
    with __import__("pytest").raises(ValueError):
        PA.source_tag("section", "h")
    payload = PAP.build_payload(sec_atoms[0])
    assert payload["scope"] == "section" and payload["section_key"] == "k1" and payload["parent_ids"] == ["p1"] and payload["doc_id"] == "d"
    assert "scope" not in PAP.build_payload(doc_atoms[0])                     # document atoms: the pre-F4 payload
