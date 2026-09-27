"""FACET-RETRIEVAL-V1 F4 — profiles that match giant documents (plan §3.4).

Pure policy: the section plan of a synthetic 900-section document covers every eligible parent exactly once
(big headings split, tiny ones folded, furniture excluded); the stratified document sampler represents EVERY
section; a section's input is built from that section's own text; a small document gets no sections.
The worker's section loop (fakes for the pool, the embedder, Qdrant and Postgres): one point per section with
`scope: section` + `parent_ids`, atoms family-scoped to the section, resumable (unchanged sections skipped),
bounded per pass (the rest pending → the ticket is held), transient pool errors reported, `force` rebuilds.
The audit scorer: a blank profile scores 0, a profile naming the document's terms and titles scores high.
"""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT / "control", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from polymath_shared.document_profile import giant_profile as GP
from polymath_shared.document_profile import profile_atom as PA
from polymath_shared.document_profile import profile_coverage as PC
from polymath_shared.document_profile import projection as PJ

FULL = (ROOT / "tests/determinism/test_document_profile_compiler.py").read_text().split('FULL = """')[1].split('"""')[0]

NOUNS = ("camera", "lighting", "gesture", "tempo", "blade", "posture", "rhythm", "breath", "stance", "impact",
         "lens", "shadow", "silence", "weight", "guard", "framing", "editing", "sound", "colour", "texture",
         "motion", "prompt", "affect", "contact", "physics", "continuity", "grammar", "reasoning", "repair", "style")


def _text(word: str, i: int) -> str:
    return (f"The {word} chapter explains how {word} governs the scene in part {i}. A director reads the {word} "
            f"before the take. Every {word} decision is written down as a rule about {word} and timing. "
            f"Practitioners measure {word} against the reference footage and adjust the {word} again.")


def synthetic_document(*, sections: int = 30, per_section: int = 30, huge_section: int = 4, huge_parents: int = 200,
                       tiny_section: int = 7, furniture: int = 6) -> list[dict]:
    """A 900-section-ish document: `sections` top-level headings × `per_section` parents; heading #huge_section
    carries `huge_parents` parents under 5 sub-headings (a split candidate); heading #tiny_section carries one
    parent (a fold candidate); `furniture` leading parents are a table of contents (noisy)."""
    parents: list[dict] = []
    idx = 0
    for f in range(furniture):
        parents.append({"chunk_id": f"p{idx}", "chunk_index": idx, "char_start": idx * 500, "heading_path": ["Contents"],
                        "text": f"Contents line {f} ..... {f + 1}", "region_role": "toc"})
        idx += 1
    for s in range(sections):
        word = NOUNS[s % len(NOUNS)]
        top = f"{s + 1:02d}. {word.title()} core"
        n = huge_parents if s == huge_section else (1 if s == tiny_section else per_section)
        for i in range(n):
            hp = [top]
            if s == huge_section:
                hp = [top, f"Sub {i // (huge_parents // 5) + 1} of {word}"]
            elif i % 3 == 1:
                hp = [top, f"{word} detail {i // 3}"]
            parents.append({"chunk_id": f"p{idx}", "chunk_index": idx, "char_start": idx * 500, "heading_path": hp,
                            "text": _text(word, i), "region_role": "body"})
            idx += 1
    return parents


DOC = {"doc_id": "doc_giant", "corpus_id": "cinema", "source_name": "giant-handbook.html", "media_type": "text/html",
       "frontmatter": {"title": "Giant Handbook"}, "content_hash": "sha_giant"}


# ── the section plan ─────────────────────────────────────────────────────────────

def test_section_groups_cover_every_eligible_parent_of_a_900_section_document_exactly_once():
    parents = synthetic_document()
    assert len(parents) > 900 and GP.is_giant(len(parents))
    groups = GP.section_groups(parents)
    eligible = {p["chunk_id"] for p in parents if p["region_role"] != "toc"}
    seen: list[str] = [pid for g in groups for pid in g.parent_ids]
    assert set(seen) == eligible and len(seen) == len(eligible)            # every eligible parent, exactly once
    assert [g.ordinal for g in groups] == list(range(1, len(groups) + 1))
    assert len({g.key for g in groups}) == len(groups) and all(len(g.key) == 16 for g in groups)
    assert all(g.parent_count >= GP.MIN_SECTION_PARENTS for g in groups)  # the tiny heading folded away
    split = [g for g in groups if g.title.startswith("05. Blade core ›")]
    assert len(split) == 5 and all(g.parent_count == 40 for g in split)    # the huge heading split at level 2
    assert not any("Contents" in g.title for g in groups)                  # furniture never becomes a section
    assert len(groups) <= GP.MAX_SECTION_PROFILES
    # the fold: heading 08 (one parent) joined its predecessor, whose parents are contiguous in document order
    prev = next(g for g in groups if g.title.startswith("07."))
    assert prev.parent_count == 31 and prev.parent_ids == tuple(sorted(prev.parent_ids, key=lambda x: int(x[1:])))


def test_section_keys_are_stable_across_rebuilds_and_titles_name_the_heading():
    a = GP.section_groups(synthetic_document())
    b = GP.section_groups(synthetic_document())
    assert [g.key for g in a] == [g.key for g in b] and [g.title for g in a] == [g.title for g in b]
    assert a[0].title == "01. Camera core" and a[0].heading_path == ("01. Camera core",)
    assert GP.section_key(("A", "B")) == GP.section_key(("a", "b")) != GP.section_key(("A",))
    assert GP.heading_key_path(["[**ACQUISITION**](x.html#ch3)", "[LIGHTING DATA", "pages 3-4"]) == ("ACQUISITION", "LIGHTING DATA")
    assert GP.heading_key_path(["Table of contents", "book.epub"]) == ()


def test_a_small_document_is_not_a_giant_and_gets_no_sections():
    small = synthetic_document(sections=10, per_section=30, huge_section=-1, tiny_section=-1, furniture=0)
    assert len(small) == 300 and not GP.is_giant(len(small)) and GP.section_groups(small) == []
    plan = GP.plan_sections(small)
    assert plan["giant"] is False and plan["sections"] == []
    just_over = small + [{"chunk_id": "px", "chunk_index": 300, "char_start": 150000, "heading_path": ["10. Impact core"],
                          "text": _text("impact", 99), "region_role": "body"}]
    assert GP.is_giant(len(just_over)) and len(GP.section_groups(just_over)) == 10


def test_a_flat_giant_without_headings_is_cut_into_positional_parts():
    flat = [{"chunk_id": f"p{i}", "chunk_index": i, "char_start": i * 500, "heading_path": [],
             "text": _text(NOUNS[i % 30], i), "region_role": "body"} for i in range(423)]
    groups = GP.section_groups(flat)
    assert len(groups) == 3 and [g.parent_count for g in groups] == [141, 141, 141]
    assert [g.title for g in groups] == ["(untitled) › part 1 of 3", "(untitled) › part 2 of 3", "(untitled) › part 3 of 3"]
    assert groups[0].parent_ids[0] == "p0" and groups[-1].parent_ids[-1] == "p422"
    # two flat chapters of 200: each chapter is cut into parts of its own
    two = [{"chunk_id": f"p{i}", "chunk_index": i, "char_start": i * 500, "heading_path": ["Upper face" if i < 200 else "Lower face"],
            "text": _text(NOUNS[i % 30], i), "region_role": "body"} for i in range(400)]
    g2 = GP.section_groups(two)
    assert [g.title for g in g2] == ["Upper face › part 1 of 2", "Upper face › part 2 of 2", "Lower face › part 1 of 2", "Lower face › part 2 of 2"]


def test_the_cap_merges_neighbours_instead_of_dropping_sections():
    parents = synthetic_document(sections=30, per_section=4, huge_section=-1, tiny_section=-1, furniture=0)
    parents = parents + synthetic_document(sections=30, per_section=4, huge_section=-1, tiny_section=-1, furniture=0)
    for i, p in enumerate(parents):                                        # 240 parents → pad to a giant
        p["chunk_id"], p["chunk_index"], p["char_start"] = f"p{i}", i, i * 500
    while len(parents) <= GP.GIANT_PARENT_THRESHOLD:
        i = len(parents)
        parents.append({"chunk_id": f"p{i}", "chunk_index": i, "char_start": i * 500, "heading_path": [f"X{i}"],
                        "text": _text("style", i), "region_role": "body"})
    groups = GP.section_groups(parents, max_profiles=12)
    assert len(groups) == 12
    assert sum(g.parent_count for g in groups) == len(parents)             # nothing dropped
    assert any(" + " in g.title for g in groups)                            # merged neighbours are named


# ── the inputs ───────────────────────────────────────────────────────────────────

def test_the_stratified_document_sample_represents_every_section():
    parents = synthetic_document()
    groups = GP.section_groups(parents)
    fp = GP.build_giant_fingerprint(DOC, parents, groups)
    assert fp.builder_version == "fingerprint-giant-v1" and fp.used_total <= fp.budget_tokens == GP.GIANT_DOCUMENT_BUDGET_TOKENS
    assert fp.sources["sections_sampled"] == len(groups) == fp.sources["sections"]
    labels = {c.split("]")[0] + "]" for c in fp.coverage}
    assert labels == {f"[{g.ordinal}]" for g in groups}                     # one ordinal label per section
    assert all(f"{g.ordinal}. {g.title}" in "\n".join(fp.structure) for g in groups)   # the structure maps ordinals → titles
    assert "Contents" not in fp.framing and fp.framing                      # never the front matter
    # every section's own vocabulary reached the sample (each section is about ONE noun)
    for g in groups:
        word = g.title.split(". ")[1].split(" ")[0].lower()
        sample = next(c for c in fp.coverage if c.startswith(f"[{g.ordinal}]"))
        assert word in sample.lower()
    assert "COVERAGE" in fp.render_block and "STRUCTURE" in fp.render_block
    structure, excerpts = GP.base_prompt_blocks(fp)
    assert structure == fp.structure_block and "SAMPLE 1:" in excerpts and "KNOWN TERMS:" in excerpts


def test_the_stratified_sampler_still_covers_every_section_on_a_tight_budget():
    parents = synthetic_document()
    groups = GP.section_groups(parents)
    signals = [GP._group_signals(g) for g in groups]
    samples = GP.stratified_samples(groups, signals, 40 * len(groups))
    assert {gi for gi, _ in samples} == set(range(len(groups)))
    assert [gi for gi, _ in samples[:len(groups)]] == list(range(len(groups)))   # pass 1 walks the document in order


def test_a_section_input_is_built_from_that_sections_own_text():
    parents = synthetic_document()
    groups = GP.section_groups(parents)
    g = next(x for x in groups if x.title.startswith("03. Gesture core"))
    fp = GP.build_section_fingerprint(DOC, g, ordinal=g.ordinal, total=len(groups))
    assert fp.title == "Giant Handbook › 03. Gesture core" and "section 3 of" in fp.identity
    body = fp.render_block.lower()
    assert "gesture" in body and "camera chapter" not in body and "lighting chapter" not in body
    assert fp.used_total <= GP.SECTION_BUDGET_TOKENS and fp.sources["section_key"] == g.key
    assert fp.input_hash(g.content_hash()) != GP.build_section_fingerprint(DOC, groups[0], ordinal=1, total=len(groups)).input_hash(groups[0].content_hash())


# ── the worker's section loop (fakes) ───────────────────────────────────────────

class FakeCursor:
    def __init__(self, rows=None, rowcount=0):
        self._rows = rows or []
        self.rowcount = rowcount

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    """A Postgres double with an in-memory `document_profile_atoms` table (enough for persist / active / supersede)."""

    def __init__(self, store: dict | None = None, answers=None):
        self.sql: list[tuple[str, tuple | None]] = []
        self.atoms: dict[str, dict] = store if store is not None else {}
        self.answers = answers or (lambda sql, params: None)

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        head = " ".join(sql.split())
        custom = self.answers(head, params)
        if custom is not None:
            return custom
        if head.startswith("SELECT atom_id, source_profile_hash FROM document_profile_atoms"):
            doc_id, contract = params
            return FakeCursor([(a["atom_id"], a["source"]) for a in self.atoms.values()
                               if a["doc_id"] == doc_id and a["contract"] == contract and a["active"]])
        if head.startswith("UPDATE document_profile_atoms SET active=FALSE, updated_at=now() WHERE atom_id = ANY"):
            n = 0
            for aid in params[0]:
                if aid in self.atoms:
                    self.atoms[aid]["active"] = False
                    n += 1
            return FakeCursor(rowcount=n)
        if head.startswith("INSERT INTO document_profile_atoms"):
            aid, doc_id, corpus_id, contract, kind, text, ordinal = params[:7]
            source = params[7] if len(params) > 7 else None
            self.atoms[aid] = {"atom_id": aid, "doc_id": doc_id, "corpus_id": corpus_id, "contract": contract, "kind": kind,
                               "text": text, "ordinal": ordinal, "source": source, "active": True}
            return FakeCursor(rowcount=1)
        if head.startswith("SELECT atom_id, doc_id, corpus_id, profile_contract, atom_kind, atom_text, ordinal, source_profile_hash"):
            return FakeCursor([(a["atom_id"], a["doc_id"], a["corpus_id"], a["contract"], a["kind"], a["text"], a["ordinal"],
                                a["source"]) for a in self.atoms.values() if a["active"]])
        return FakeCursor()

    def commit(self):
        pass


def _match(flt, payload) -> bool:
    if flt is None:
        return True

    def cond_ok(c):
        v = payload.get(c.key)
        m = c.match
        if hasattr(m, "any"):
            return v in list(m.any)
        return v == m.value
    return all(cond_ok(c) for c in (flt.must or [])) and not any(cond_ok(c) for c in (flt.must_not or []))


class FakeQdrant:
    """An in-memory Qdrant double: points by id with payload; filters on payload equality / any."""

    def __init__(self):
        self.collections: set[str] = set()
        self.points: dict[str, dict] = {}          # (collection, id) → {"payload", "vector"}
        self.calls: list[str] = []

    def collection_exists(self, name):
        return name in self.collections

    def create_collection(self, collection_name, vectors_config):
        self.collections.add(collection_name)

    def upsert(self, collection_name, points, wait=True):
        self.collections.add(collection_name)
        for p in points:
            self.points[(collection_name, str(p.id))] = {"payload": dict(p.payload or {}), "vector": p.vector}

    def retrieve(self, collection_name, ids, with_payload=None, with_vectors=False):
        out = []
        for i in ids:
            rec = self.points.get((collection_name, str(i)))
            if rec:
                payload = {k: v for k, v in rec["payload"].items() if not with_payload or k in with_payload}
                out.append(type("Pt", (), {"id": str(i), "payload": payload})())
        return out

    def scroll(self, collection_name, scroll_filter=None, limit=256, with_payload=None, with_vectors=False, offset=None):
        rows = [(pid, rec) for (coll, pid), rec in self.points.items() if coll == collection_name and _match(scroll_filter, rec["payload"])]
        pts = [type("Pt", (), {"id": pid, "payload": {k: v for k, v in rec["payload"].items() if not with_payload or k in with_payload}})()
               for pid, rec in rows]
        return pts, None

    def count(self, collection_name, count_filter=None, exact=True):
        n = sum(1 for (coll, _pid), rec in self.points.items() if coll == collection_name and _match(count_filter, rec["payload"]))
        return type("C", (), {"count": n})()

    def delete(self, collection_name, points_selector, wait=True):
        flt = points_selector.filter
        for key in [k for k, rec in self.points.items() if k[0] == collection_name and _match(flt, rec["payload"])]:
            del self.points[key]

    def close(self):
        self.calls.append("close")


def _dim():
    from polymath_shared.embedding_contracts import active_contract
    return active_contract().dimension


def _tx_factory(conn):
    @contextmanager
    def tx():
        yield conn
    return tx


def _install_hooks(monkeypatch, W, q, calls, *, fail_with=None, transient=False):
    def fake_complete(system_prompt, user_prompt, max_tokens):
        calls.append(user_prompt)
        if fail_with:
            return "", fail_with, {"attempts": [{"lane": "fake", "error": fail_with}]}
        return FULL, None, {"lane": "fake_lane", "model": "fake:model", "attempts": [{"lane": "fake_lane", "error": None, "ms": 1.0}]}
    dim = _dim()
    monkeypatch.setitem(W.HOOKS, "complete", fake_complete)
    monkeypatch.setitem(W.HOOKS, "embed", lambda texts: [[float((len(t) + i) % 7) / 7.0] * dim for i, t in enumerate(texts)])
    monkeypatch.setitem(W.HOOKS, "qdrant", q)
    monkeypatch.delenv("POLYMATH_DOC_PROFILE_VNEXT", raising=False)
    monkeypatch.delenv("POLYMATH_DOC_PROFILE_SECTIONS_PER_PASS", raising=False)
    monkeypatch.delenv("POLYMATH_DOC_PROFILE_FORCE_SECTIONS", raising=False)


def test_build_section_profiles_stores_one_point_per_section_with_scope_and_parent_ids_and_resumes(monkeypatch):
    from workers import doc_profile_worker as W
    parents = synthetic_document(sections=8, per_section=40, huge_section=-1, tiny_section=-1, furniture=0)
    groups = GP.section_groups(parents)
    assert len(groups) == 8
    q, calls, conn = FakeQdrant(), [], FakeConn()
    _install_hooks(monkeypatch, W, q, calls)
    rec = W.build_section_profiles(_tx_factory(conn), run_id="run_1", doc_id="doc_giant", corpus_id="cinema", document=DOC,
                                   groups=groups, vnext=False, per_pass=100)
    assert len(calls) == 8 and len(rec["built"]) == 8 and not rec["skipped"] and not rec["failed"] and not rec["pending"]
    assert all(g.title in c for g, c in zip(groups, calls))                 # each call carries its own section's title
    from polymath_shared.embedding_contracts import active_contract
    coll = PJ.collection_name(active_contract().contract_id)
    pts = [rec_ for (c, _pid), rec_ in q.points.items() if c == coll]
    assert len(pts) == 8
    for g in groups:
        rec_ = q.points[(coll, PJ.section_point_id("doc_giant", g.key))]
        p = rec_["payload"]
        assert p["scope"] == "section" and p["doc_id"] == "doc_giant" and p["corpus_id"] == "cinema"
        assert p["section_key"] == g.key and tuple(p["parent_ids"]) == g.parent_ids and p["parent_count"] == g.parent_count
        assert p["title"] == f"Giant Handbook › {g.title}" and p["input_hash"] and p["compiled"]["one"]
        assert set(rec_["vector"]) >= {"identity", "theme", "questions", "searches"}
    # section atoms: rows keyed by the section, the DOCUMENT's doc_id, family-scoped sources
    rows = [a for a in conn.atoms.values() if a["active"]]
    assert rows and all(a["doc_id"] == "doc_giant" and a["source"].startswith("section:") for a in rows)
    assert {PA.section_key_of(a["source"]) for a in rows} == {g.key for g in groups}
    atom_coll = [c for (c, _p) in q.points if c.startswith("polymath_document_profile_atoms_")]
    assert atom_coll
    atom_payloads = [r["payload"] for (c, _p), r in q.points.items() if c.startswith("polymath_document_profile_atoms_")]
    assert all(pl["scope"] == "section" and pl["doc_id"] == "doc_giant" and pl["parent_ids"] for pl in atom_payloads)
    built = rec["built"][0]
    assert built["valid"] and built["compiled"]["questions"] and built["projection"]["point_id"] == PJ.section_point_id("doc_giant", groups[0].key)
    assert built["atoms"]["ok"] and built["atoms"]["section_key"] == groups[0].key and built["lane"] == "fake_lane"
    # resume: nothing changed → every section skipped, no LLM call, the skipped entries still carry their surfaces
    calls.clear()
    rec2 = W.build_section_profiles(_tx_factory(conn), run_id="run_1", doc_id="doc_giant", corpus_id="cinema", document=DOC,
                                    groups=groups, vnext=False, per_pass=100)
    assert calls == [] and len(rec2["skipped"]) == 8 and not rec2["built"]
    assert all(s["reason"] == "unchanged" and s["compiled"]["one"] for s in rec2["skipped"])
    # force: rebuilt, and section 1's atoms are superseded WITHOUT touching section 2's
    before = {a["atom_id"] for a in conn.atoms.values() if PA.section_key_of(a["source"]) == groups[1].key and a["active"]}
    rec3 = W.build_section_profiles(_tx_factory(conn), run_id="run_1", doc_id="doc_giant", corpus_id="cinema", document=DOC,
                                    groups=groups[:1], vnext=False, per_pass=100, force=True)
    assert len(calls) == 1 and len(rec3["built"]) == 1
    after = {a["atom_id"] for a in conn.atoms.values() if PA.section_key_of(a["source"]) == groups[1].key and a["active"]}
    assert after == before and rec3["built"][0]["atoms"]["persisted"]["deactivated"] > 0


def test_a_pass_is_bounded_and_a_transient_pool_error_leaves_the_rest_pending(monkeypatch):
    from workers import doc_profile_worker as W
    parents = synthetic_document(sections=6, per_section=60, huge_section=-1, tiny_section=-1, furniture=0)
    groups = GP.section_groups(parents)
    q, calls, conn = FakeQdrant(), [], FakeConn()
    _install_hooks(monkeypatch, W, q, calls)
    rec = W.build_section_profiles(_tx_factory(conn), run_id="run_2", doc_id="doc_giant", corpus_id="cinema", document=DOC,
                                   groups=groups, vnext=False, per_pass=2)
    assert len(calls) == 2 and len(rec["built"]) == 2 and rec["pending"] == [g.key for g in groups[2:]]
    assert rec["orphans_purged"] == 0                                        # never purged while sections are pending
    calls.clear()
    _install_hooks(monkeypatch, W, q, calls, fail_with="HTTP_429")
    rec2 = W.build_section_profiles(_tx_factory(conn), run_id="run_2", doc_id="doc_giant", corpus_id="cinema", document=DOC,
                                    groups=groups, vnext=False, per_pass=10)
    assert len(rec2["skipped"]) == 2 and len(calls) == 1                     # the first unbuilt section hit the dark pool
    assert rec2["transient_error"].startswith("HTTP_429") and rec2["pending"] == [g.key for g in groups[2:]] and not rec2["failed"]
    calls.clear()
    _install_hooks(monkeypatch, W, q, calls, fail_with="HTTP_400")           # a hard error is a failed section, the pass goes on
    rec3 = W.build_section_profiles(_tx_factory(conn), run_id="run_2", doc_id="doc_giant", corpus_id="cinema", document=DOC,
                                    groups=groups, vnext=False, per_pass=10)
    assert len(rec3["failed"]) == 4 and not rec3["pending"] and len(calls) == 4


def test_a_re_cut_document_purges_its_orphan_section_points(monkeypatch):
    from workers import doc_profile_worker as W
    parents = synthetic_document(sections=5, per_section=70, huge_section=-1, tiny_section=-1, furniture=0)
    groups = GP.section_groups(parents)
    q, calls, conn = FakeQdrant(), [], FakeConn()
    _install_hooks(monkeypatch, W, q, calls)
    W.build_section_profiles(_tx_factory(conn), run_id="r", doc_id="doc_giant", corpus_id="cinema", document=DOC,
                             groups=groups, vnext=False, per_pass=100)
    from polymath_shared.embedding_contracts import active_contract
    cid = active_contract().contract_id
    assert len(PJ.list_section_points(q, cid, "doc_giant")) == 5
    rec = W.build_section_profiles(_tx_factory(conn), run_id="r", doc_id="doc_giant", corpus_id="cinema", document=DOC,
                                   groups=groups[:3], vnext=False, per_pass=100)
    assert rec["orphans_purged"] == 2 and set(PJ.list_section_points(q, cid, "doc_giant")) == {g.key for g in groups[:3]}


def _fake_db_for_process_event(parents: list[dict]):
    """A FakeConn answering the worker's resolve / load queries for DOC."""
    def answers(head, params):
        if head.startswith("SELECT payload FROM outbox_events"):
            return FakeCursor([({"doc_id": DOC["doc_id"], "corpus_id": DOC["corpus_id"]},)])
        if head.startswith("SELECT doc_id, corpus_id, source_name, media_type, frontmatter, content_hash FROM documents"):
            return FakeCursor([(DOC["doc_id"], DOC["corpus_id"], DOC["source_name"], DOC["media_type"], DOC["frontmatter"], DOC["content_hash"])])
        if head.startswith("SELECT chunk_index, char_start, char_end, heading_path, text, region_role, chunk_id FROM chunks"):
            return FakeCursor([(p["chunk_index"], p["char_start"], p["char_start"] + 400, p["heading_path"], p["text"], p["region_role"], p["chunk_id"])
                               for p in parents])
        return None
    return FakeConn(answers=answers)


def test_process_event_holds_the_ticket_while_sections_are_pending_then_profiles_the_giant_from_all_sections(monkeypatch):
    from polymath_shared.worker_runtime import TransientStageHold

    from workers import doc_profile_worker as W
    parents = synthetic_document(sections=5, per_section=70, huge_section=-1, tiny_section=-1, furniture=0)
    q, calls = FakeQdrant(), []
    _install_hooks(monkeypatch, W, q, calls)
    conn = _fake_db_for_process_event(parents)
    monkeypatch.setitem(W.HOOKS, "tx", _tx_factory(conn))
    monkeypatch.setenv("POLYMATH_DOC_PROFILE_SECTIONS_PER_PASS", "2")
    with pytest.raises(TransientStageHold) as ei:
        W.process_event(conn, {"run_id": "run_x", "payload": {"run_id": "run_x"}})
    assert "DOC_PROFILE_SECTIONS_PENDING: 2/5 done, 3 pending" in str(ei.value)
    assert len(calls) == 2 and not any("INSERT INTO artifacts" in s for s, _ in conn.sql)   # no document call, no artifact yet
    # the next passes finish the sections, then the document profile is built from the stratified sample
    calls.clear()
    monkeypatch.setenv("POLYMATH_DOC_PROFILE_SECTIONS_PER_PASS", "10")
    W.process_event(conn, {"run_id": "run_x", "payload": {"run_id": "run_x"}})
    assert len(calls) == 4                                                    # 3 remaining sections + 1 document profile
    doc_call = calls[-1]
    assert "SAMPLE 1:" in doc_call and "[1] " in doc_call and "[5] " in doc_call and "5 sections" in doc_call
    arts = [json.loads(p[4]) for s, p in conn.sql if s.strip().startswith("INSERT INTO artifacts")]
    merged = {}
    for a in arts:
        merged.update(a)
    dp, sec = merged["doc_profile"], merged["doc_profile_sections"]
    assert dp["giant"] is True and dp["sections"] == 5 and dp["builder_version"] == "fingerprint-giant-v1" and dp["valid"]
    assert dp["context"]["sources"]["sections_sampled"] == 5
    assert len(sec["built"]) == 3 and len(sec["skipped"]) == 2 and sec["sections_total"] == 5 and not sec["pending"]
    assert merged["doc_profile_qdrant"]["valid"] is True and merged["doc_profile_qdrant"]["scope"] == "document"
    from polymath_shared.embedding_contracts import active_contract
    cid = active_contract().contract_id
    doc_pt = q.points[(PJ.collection_name(cid), PJ.point_id("doc_giant"))]["payload"]
    assert doc_pt["scope"] == "document" and doc_pt["input_hash"] and len(PJ.list_section_points(q, cid, "doc_giant")) == 5


def test_the_giant_switch_off_and_a_small_document_keep_the_stage_byte_identical(monkeypatch):
    from workers import doc_profile_worker as W
    small = synthetic_document(sections=3, per_section=20, huge_section=-1, tiny_section=-1, furniture=0)
    q, calls = FakeQdrant(), []
    _install_hooks(monkeypatch, W, q, calls)
    conn = _fake_db_for_process_event(small)
    W.process_event(conn, {"run_id": "run_s", "payload": {"run_id": "run_s"}})
    assert len(calls) == 1 and "TITLE:\nGiant Handbook" in calls[0]
    arts = {k: v for s, p in conn.sql if s.strip().startswith("INSERT INTO artifacts") for k, v in json.loads(p[4]).items()}
    assert "doc_profile_sections" not in arts and "giant" not in arts["doc_profile"]
    monkeypatch.setenv("POLYMATH_DOC_PROFILE_GIANT", "0")
    off = W.contract()
    monkeypatch.delenv("POLYMATH_DOC_PROFILE_GIANT")
    assert off != W.contract()                                               # the switch is part of the stage contract
    giant = synthetic_document(sections=5, per_section=70, huge_section=-1, tiny_section=-1, furniture=0)
    calls.clear()
    monkeypatch.setenv("POLYMATH_DOC_PROFILE_GIANT", "0")
    conn2 = _fake_db_for_process_event(giant)
    W.process_event(conn2, {"run_id": "run_g", "payload": {"run_id": "run_g"}})
    assert len(calls) == 1 and "SAMPLE" not in calls[0].split("DOCUMENT EVIDENCE")[0]
    arts2 = {k: v for s, p in conn2.sql if s.strip().startswith("INSERT INTO artifacts") for k, v in json.loads(p[4]).items()}
    assert "doc_profile_sections" not in arts2 and arts2["doc_profile"]["builder_version"] == "lean-context-v1"


# ── the audit scorer ─────────────────────────────────────────────────────────────

def test_the_audit_scores_a_blank_profile_low_and_a_good_one_high():
    parents = synthetic_document(sections=12, per_section=30, huge_section=-1, tiny_section=-1, furniture=2)
    texts = [p["text"] for p in parents]
    terms = PC.document_terms(texts, top=50)
    titles = PC.section_titles(parents)
    assert 20 <= len(terms) <= 50 and len(titles) == 12 and titles[0] == "01. Camera core"   # the synthetic vocabulary is small
    blank = PC.coverage(terms, titles, "")
    assert blank.score == 0.0 and blank.term_share == 0.0 and blank.title_share == 0.0
    wrong = PC.coverage(terms, titles, "CPCS YAML JSON compiler how to HAS PROPERTY")
    assert wrong.score < 0.1
    good_text = "\n".join([*(t for t, _w in terms), *titles])
    good = PC.coverage(terms, titles, good_text)
    assert good.score >= 0.95 and good.term_share == 1.0 and good.title_share == 1.0
    partial = PC.coverage(terms, titles, "\n".join(t for t, _w in terms[:len(terms) // 2]))
    assert 0.25 <= partial.score <= 0.35 and partial.missing_titles == titles
    # stems: plural / -ing forms cover the base term
    assert PC.coverage(["camera", "light"], [], "cameras and lighting").term_share == 1.0


def test_audit_document_flags_a_giant_without_section_profiles_and_worst_orders_by_score():
    giant = synthetic_document(sections=12, per_section=30, huge_section=-1, tiny_section=-1, furniture=0)
    row = PC.audit_document(giant, profile_texts={"llm": "", "det": "camera lighting"}, section_profiles=0)
    assert row["giant"] and row["giant_without_sections"] and row["reports"]["llm"]["score"] == 0.0
    assert row["score"] == row["reports"]["det"]["score"] > 0
    ok = PC.audit_document(giant, profile_texts={"llm": " ".join(t for t, _ in row["top_terms"])}, section_profiles=12)
    assert not ok["giant_without_sections"] and ok["reports"]["llm"]["term_share"] == 1.0
    rows = [{"score": 0.9, "parents": 10, "source_name": "a"}, {"score": 0.1, "parents": 900, "source_name": "b"},
            {"score": 0.1, "parents": 50, "source_name": "c"}]
    assert [r["source_name"] for r in PC.worst(rows, n=2)] == ["b", "c"]
    assert PC.flatten_compiled({"one": "x", "questions": ["q1", "q2"], "quality": None}) == "x\nq1\nq2"
    assert "cpcs" in PC.flatten_retrieval_profile({"core_concepts": ["cpcs"], "semantic_summary": "s"})
