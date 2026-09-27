"""FACET-RETRIEVAL-V1 F3 — WILDCARD's mapped subqueries (register 11.545; plan §3.3, §4 F3). The owner (2026-09-27):
"wildcard should use its lanes to create better mapped subqueries".

Proof on fake lanes (the embedder, the judge, Qdrant, the atom / map projections and the Postgres joins are faked on
`orchestrator.api.chat_retrieval` the way tests/determinism/test_chat_modes.py does):
  * the sweep's findings (atoms, see-also blends, latent parents) become short mapped subqueries per facet, ≤ 2 per facet
    and ≤ 6 in total, origin WILDCARD, `facet_id` set, never a raw chunk;
  * the gate against the ORIGINAL question drops a low one and counts it; a raising gate keeps them all (fail-open);
  * the second pass's evidence reaches the one judged pool with its `facet_id`, fused exactly like a plan subquery (the
    union and the evidence of a plan that carried the same subqueries are byte-identical);
  * a sweep still out at the deadline skips the pass (`mapped_pass.skipped: deadline`), the first pass stands;
  * `POLYMATH_WILDCARD_MAPPED=0` reproduces the HEAD outputs pinned before the change (wildcard_mapped_head_pins.json),
    and HYBRID never runs the pass.
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
import time as _time
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)
HERE = str(pathlib.Path(__file__).resolve().parent)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from orchestrator.api import chat_retrieval as cr
from polymath_shared import candidate_engine as ce
from polymath_shared import wildcard_mapped as wm

PINS = json.loads((pathlib.Path(__file__).with_name("wildcard_mapped_head_pins.json")).read_text())

QUERY = "emotional storytelling for ecommerce video ads"                  # q0, the compact retrieval text
QUESTION = "create an ecommerce story prompt and direction for an AI video ad that plays on emotions"
SUBS = (("q1", "MECHANISM", "directing the AI video model camera motion", 0.8, "USER", ""),)
FACETS = (("f1", ("q0",)), ("f2", ("q1",)))
PLAN_TEXTS = {QUERY, SUBS[0][2]}
ATOMS = [{"doc_id": "docA", "atom_kind": "CONCEPT", "text": "Character stability in AI video stories", "score": 0.7},
         {"doc_id": "docB", "atom_kind": "THEORY", "text": "Balancing logical and emotional appeals", "score": 0.6},
         {"doc_id": "docC", "atom_kind": "SEEALSO", "text": "Granular motion control per video model", "score": 0.5}]
#: latent frontier fixtures: (parent_id, doc_id, hop1, kid chunk ids, abstraction text)
LATENT = [("pfar0", "dfar", 0.9, ["pfar0-k0", "pfar0-k1"], "Preserve emotion before continuity in ads"),
          ("pfar1", "dfar", 0.85, ["pfar1-k0"], "Camera motion dialects differ per video model"),
          ("pfar2", "dfar2", 0.8, ["pfar2-k0"], "Withheld information builds suspense")]


class _Harness:
    """chat_retrieve_mode with every sidecar and store faked. The dense child search keys on the VECTOR's text: a text the
    plan never searched (a mapped subquery, a blend item) returns its own passages (`m<k>-c<i>` in document `dm<k>`), so the
    second pass's evidence is distinguishable from pass 1's (`d1` / `d2` chunks)."""

    def __init__(self, monkeypatch, *, atoms=ATOMS, latent=LATENT, gate_scores=None, gate_raises=False, latent_sleep=0.0,
                 blend_items=None):
        self.embed_calls: list[list[str]] = []
        self.gate_calls: list[list[str]] = []
        self.judge_calls: int = 0
        self.pair_calls: int = 0
        self.text_of_vec: dict[tuple, str] = {}
        self.mapped_index: dict[str, int] = {}
        self.release = threading.Event()
        gate_scores = dict(gate_scores or {})
        h = self

        def fake_embed(texts):
            h.embed_calls.append(list(texts))
            vecs = []
            for t in texts:
                v = (round(0.0001 * (sum(ord(c) * (i + 1) for i, c in enumerate(t)) % 9973), 6), 0.2)
                h.text_of_vec[v] = t
                vecs.append(list(v))
            return vecs

        def fake_rerank(q, rows):
            if q == QUESTION:                                          # the mapped gate (the original question)
                h.gate_calls.append([r["chunk_id"] for r in rows])
                if gate_raises:
                    raise RuntimeError("reranker parked")
                return [dict(r, rerank_score=gate_scores.get(r["text"], 4.0)) for r in rows]
            if q == QUERY:                                             # the ONE judge of the turn
                h.judge_calls += 1
                out = [dict(r, rerank_score=(3.0 - i * 0.001) if str(r["chunk_id"]).startswith("m") else 1.0 - i * 0.01)
                       for i, r in enumerate(rows)]
                return sorted(out, key=lambda r: -r["rerank_score"])
            h.pair_calls += 1                                          # the finish's two-hop validation
            return [dict(r, rerank_score=1.0 - i * 0.01) for i, r in enumerate(rows)]

        class FakeSearcher:
            def __init__(self, client, collections, query=None):
                self.latency = {}
                self._hidden_cache = {}

            def _hidden_for(self, cid):
                return list(self._hidden_cache.get(cid) or [])

            def _search(self, collection, vector, filters, limit):
                kind = filters["representation_kind"]
                if kind in ("latent_abstraction", "latent_transfer"):
                    if latent_sleep:
                        h.release.wait(latent_sleep)
                    if kind == "latent_transfer":
                        return []
                    return [{"payload": {"parent_id": pid, "doc_id": doc, "source_name": f"{doc}.md", "text": text, "corpus_id": "cinema"},
                             "score": score} for pid, doc, score, _kids, text in latent][:limit]
                if kind == "routing_child":
                    parent = filters.get("parent_id")
                    if parent and "doc_id" not in filters:            # WILDCARD children_of
                        spec = next((x for x in latent if x[0] == parent), None)
                        return [{"payload": {"chunk_id": k, "doc_id": spec[1], "parent_id": parent, "text": f"grounding text of {k} mechanism",
                                             "source_name": "far.md"}, "score": 0.5} for k in (spec[3] if spec else [])]
                    text = h.text_of_vec.get(tuple(vector), "")
                    if text and text not in PLAN_TEXTS:                 # a mapped subquery (or a blend item): its own passages
                        k = h.mapped_index.setdefault(text, len(h.mapped_index))
                        return [{"payload": {"chunk_id": f"m{k}-c{i}", "doc_id": f"dm{k}", "parent_id": f"pm{k}",
                                             "text": f"mapped passage {i} about {text}", "corpus_id": "cinema"}, "score": 0.9 - i * 0.01}
                                for i in range(min(limit, 3))]
                    docs = (filters["doc_id"],) if parent else ("d1", "d2")
                    return [{"payload": {"chunk_id": f"{d}-{parent or 'g'}-c{i}", "doc_id": d, "parent_id": parent or f"{d}-p",
                                         "text": "reward models shape prompt optimization", "corpus_id": "cinema"},
                             "score": 1 - i * 0.01} for i in range(min(limit, 3)) for d in docs]
                if kind == "routing_document_summary":
                    return [{"payload": {"doc_id": d, "summary_id": f"s-{d}", "text": "doc", "corpus_id": "cinema"}, "score": 0.9 - i * 0.1}
                            for i, d in enumerate(("d1", "d2"))]
                if kind == "routing_section_summary":
                    return [{"payload": {"doc_id": d, "parent_id": f"{d}-p", "summary_id": f"sec-{d}", "text": "sec", "corpus_id": "cinema"},
                             "score": 0.9 - i * 0.1} for i, d in enumerate(("d1", "d2"))]
                return []

            def sparse_search(self, collection, sparse_query, filters, limit):
                key = "-".join(str(i) for i in sparse_query[0])
                return [{"payload": {"chunk_id": f"sp-{key}", "doc_id": "d3", "parent_id": "d3-p", "text": "sparse hit", "corpus_id": "cinema"}, "score": 12.0}]

        class FakeQdrant:
            def __init__(self, *a, **k): pass
            def close(self): pass

        from polymath_shared import embedding_contracts
        from polymath_shared.document_profile import parent_map_projection as pmp
        from polymath_shared.document_profile import profile_atom_projection as pap
        from polymath_shared.document_profile import projection as proj
        monkeypatch.setattr(embedding_contracts, "active_contract", lambda: SimpleNamespace(contract_id="c"))

        def fake_atoms(client, coll, qvec, kinds, k=12, *, corpus_ids, doc_ids=None, scope=None):
            if doc_ids is not None:                                     # SEEALSO-BLEND: the question's documents' lines
                return list(blend_items or [])
            return list(atoms)

        monkeypatch.setattr(pap, "search_atoms", fake_atoms)
        monkeypatch.setattr(pmp, "search_parent_maps", lambda *a, **k: [{"parent_id": f"p-{a_['doc_id']}", "doc_id": a_["doc_id"], "score": 0.5}
                                                                          for a_ in atoms])
        monkeypatch.setattr(proj, "profile_nominate", lambda *a, **k: ["d1"])
        monkeypatch.setattr(cr, "_embed_queries", fake_embed)
        monkeypatch.setattr(cr, "_rerank_children", fake_rerank)
        monkeypatch.setattr(cr, "FastSearcher", FakeSearcher)
        monkeypatch.setattr(cr, "QdrantClient", FakeQdrant)
        monkeypatch.setattr(cr, "_ensure_fast_ready", lambda cid: None)
        monkeypatch.setattr(cr, "_corpus_collections", lambda ids: {i: f"coll-{i}" for i in ids})
        monkeypatch.setattr(cr, "_region_lookup", lambda ids: {})
        monkeypatch.setattr(cr, "_neighbor_lookup", lambda want, d: [])
        monkeypatch.setattr(cr, "_presentation_joins", lambda cids, dids: {})

    def mode(self, mode="WILDCARD", **kw):
        kw.setdefault("subqueries", SUBS)
        kw.setdefault("facets", FACETS)
        if mode == "WILDCARD":
            kw.setdefault("question", QUESTION)
        return cr.chat_retrieve_mode(mode, QUERY, "cinema", exact_terms=("ecommerce",), **kw)

    def v2(self, **kw):
        return cr.chat_retrieve_v2(QUERY, "cinema", exact_terms=("ecommerce",), **kw)


def _ids(out):
    return [e["chunk_id"] for e in out["evidence"]]


def _mapped(out):
    return out["meta"]["wildcard"]["mapped_subqueries"], out["meta"]["wildcard"]["mapped_pass"]


# ---------------------------------------------------------------- the builder (pure)

def test_short_query_is_a_short_natural_query_never_a_raw_chunk():
    assert wm.short_query("AI video generation techniques") == "AI video generation techniques"
    assert wm.short_query("Preserve emotion before continuity.") == "Preserve emotion before continuity"
    long = ("The key principle is that editors preserve the emotional truth of a scene and hide continuity errors with a "
            "cutaway. This transfers to advertising where the emotional beat matters more than product continuity.")
    q = wm.short_query(long)
    assert q == "editors preserve the emotional truth of a scene and hide continuity errors"          # first sentence, lead stripped
    assert len(q) <= wm.MAPPED_QUERY_MAX_CHARS and len(q.split()) <= wm.MAPPED_QUERY_MAX_WORDS
    assert wm.short_query("In short: information asymmetry drives tension") == "information asymmetry drives tension"
    chunk = "word " * 300                                                                            # a raw chunk-sized text
    assert len(wm.short_query(chunk + "camera motion")) <= wm.MAPPED_QUERY_MAX_CHARS
    assert wm.short_query("ok") == "" and wm.short_query("") == ""                                 # < 2 content words
    assert wm.short_query("write a summary of the story in bullet points") == ""                    # an instruction, never a query


def test_atoms_blends_and_latent_parents_become_mapped_subqueries_per_facet_with_the_caps():
    facets = [("f1", [QUERY]), ("f2", [SUBS[0][2]]), ("f3", ["psychological responses narrative structure pacing"])]
    seealso = [{"text": "Storytelling in AI-generated videos", "kind": "SEEALSO", "doc_id": "d3d"},
               {"text": "AI narrative structure", "kind": "SEEALSO", "doc_id": "d3d"},
               {"text": "Storytelling in Marketing", "kind": "SEEALSO", "doc_id": "d2c"}]
    latent = [{"parent_id": "p1", "doc_id": "dh", "abstraction": "Granular motion control dialects differ per video model", "hop1": 0.8},
              {"parent_id": "p2", "doc_id": "db", "abstraction": "", "transfer": "Preserve emotion before continuity", "hop1": 0.7}]
    atoms = ATOMS + [{"doc_id": "dx", "atom_kind": "CONCEPT", "text": QUERY, "score": 0.9}]           # a plan query again
    rows, rec = wm.build_mapped_subqueries(seealso=seealso, atoms=atoms, latent=latent, facets=facets, plan_queries=[QUERY])
    by_id = {r["id"]: r for r in rows}
    assert [r["id"] for r in rows] == [f"w{i}" for i in range(len(rows))] and all(r["kept"] is True for r in rows)
    assert all(r["facet_id"] in {"f1", "f2", "f3"} and r["query"] and len(r["query"]) <= wm.MAPPED_QUERY_MAX_CHARS for r in rows)
    per_facet = {f: [r["query"] for r in rows if r["facet_id"] == f] for f in ("f1", "f2", "f3")}
    assert all(len(v) <= wm.MAPPED_PER_FACET for v in per_facet.values()) and len(rows) <= wm.MAPPED_TOTAL
    # attachment by overlap (stems match: `emotion` ~ `emotional`, `video` ~ `videos`): the motion query sits with the model facet,
    # the narrative one with the psychology facet, the story ones with the core
    assert "Granular motion control dialects differ per video model" in per_facet["f2"]
    assert "AI narrative structure" in per_facet["f3"] and "Storytelling in AI-generated videos" in per_facet["f1"]
    assert {r["from"] for r in rows} >= {"seealso", "atom", "latent"}                                  # the sources interleave
    assert rows[0]["facet_id"] == "f1" and rows[1]["facet_id"] == "f2" and rows[2]["facet_id"] == "f3"  # round-robin: every facet's first
    # two duplicates: the plan query offered again as an atom, and the atom "Granular motion control per video model" (Jaccard 0.75
    # with the latent principle already seated — the same search twice)
    assert rec["dropped_duplicate"] == 2 and rec["candidates"] == {"seealso": 3, "atom": 4, "latent": 2} and rec["built"] == len(rows)
    assert all(r["attach"] == "overlap" for r in rows) and by_id["w0"]["source"] == {"kind": "SEEALSO", "doc_id": "d3d"}
    # the caps bind: nine atoms for one facet → 2; six facets × 2 → 6 in total, the first of every facet before any second
    topics = ("testimonial", "unboxing", "founder", "comparison", "tutorial", "lifestyle", "countdown", "giveaway", "recap")
    many = [{"doc_id": "d", "atom_kind": "CONCEPT", "text": f"{t} video ads", "score": 1 - i * 0.01} for i, t in enumerate(topics)]
    rows2, rec2 = wm.build_mapped_subqueries(atoms=many, facets=[("f1", [QUERY])])
    assert len(rows2) == 2 and rec2["dropped_no_room"] == 7 and rec2["dropped_duplicate"] == 0
    places = ("kitchen", "garden", "studio", "street", "desert", "harbour")
    six = [(f"f{i}", [f"{t} lighting setup"]) for i, t in enumerate(places, 1)]
    atoms6 = [{"doc_id": "d", "atom_kind": "CONCEPT", "text": f"{t} {tail}", "score": 1.0} for t in places for tail in ("lighting rig", "shadows mood")]
    rows3, rec3 = wm.build_mapped_subqueries(atoms=atoms6, facets=six)
    assert len(rows3) == 6 and [r["facet_id"] for r in rows3] == [f"f{i}" for i in range(1, 7)] and rec3["dropped_duplicate"] == 0
    # no facets (no plan: /retrieve, POLYMATH_CHAT_FACETS=0): rows carry facet_id None under the total cap alone
    rows4, rec4 = wm.build_mapped_subqueries(atoms=many, facets=())
    assert len(rows4) == wm.MAPPED_TOTAL and all(r["facet_id"] is None and r["attach"] == "none" for r in rows4) and rec4["facets"] == 0
    # a candidate without any overlap goes to the core facet while it has a seat, never to another facet's seats
    rows5, _rec5 = wm.build_mapped_subqueries(atoms=[{"doc_id": "d", "atom_kind": "CONCEPT", "text": "unrelated concept entirely", "score": 1.0}],
                                             facets=[("f1", [QUERY]), ("f2", [SUBS[0][2]])])
    assert rows5[0]["facet_id"] == "f1" and rows5[0]["attach"] == "primary"


def test_the_gate_drops_a_low_row_counts_it_and_fails_open():
    rows = [{"id": "w0", "query": "Storytelling in Marketing"}, {"id": "w1", "query": "Camera motion dialects per video model"}]

    def judge(q, rs):
        assert q == QUESTION
        return [dict(r, rerank_score=(-3.0 if "Marketing" in r["text"] else 4.0)) for r in rs]

    rec = wm.gate_mapped(QUESTION, rows, judge)
    assert rec == {"version": "probe-gate-v1", "floor": 0.2, "scored": 2, "dropped": ["w0"], "kept_unscored": 0}
    assert rows[0]["kept"] is False and rows[0]["gate_score"] == 0.0474 and rows[1]["kept"] is True and rows[1]["gate_score"] > 0.9

    def broken(q, rs):
        raise ConnectionError("reranker parked")

    rec2 = wm.gate_mapped(QUESTION, rows, broken)
    assert rec2["error"] == "ConnectionError" and rec2["dropped"] == [] and rec2["kept_unscored"] == 2
    assert all(r["kept"] is True and r["gate_score"] is None for r in rows)                          # fail-open: every row kept

    def slow(q, rs):
        _time.sleep(0.4)
        return judge(q, rs)

    rec3 = wm.gate_mapped(QUESTION, rows, slow, timeout_s=0.05)
    assert rec3["error"] == "TimeoutError" and all(r["kept"] for r in rows)


def test_the_flag_defaults_on_and_the_facet_texts_come_from_the_engine_kwargs(monkeypatch):
    monkeypatch.delenv(wm.MAPPED_FLAG, raising=False)
    assert wm.mapped_enabled() is True
    for off in ("0", "false", "off", "no"):
        assert wm.mapped_enabled({wm.MAPPED_FLAG: off}) is False
    assert wm.mapped_enabled({wm.MAPPED_FLAG: "1"}) is True
    kw = {"subqueries": SUBS, "facets": (("f1", ("q0", "p9")), ("f2", ("q1",)))}                       # p9: a probe the gate dropped
    assert cr._facet_query_texts(QUERY, kw) == [("f1", [QUERY]), ("f2", [SUBS[0][2]])]
    assert cr._facet_query_texts(QUERY, {}) == []


# ---------------------------------------------------------------- the composition (fake lanes)

def test_mapped_subqueries_reach_the_one_judged_pool_with_their_facet_ids(monkeypatch):
    monkeypatch.delenv(wm.MAPPED_FLAG, raising=False)
    h = _Harness(monkeypatch)
    out = h.mode("WILDCARD")
    rows, rec = _mapped(out)
    assert out["meta"]["mode"] == "WILDCARD" and rec["skipped"] is None and rec["contract"] == "wildcard-mapped-v1"
    # ≤ 2 per facet, facet ids set, short queries from the atom / latent texts, all kept and all searched
    assert [(r["id"], r["facet_id"], r["from"]) for r in rows] == [("w0", "f1", "atom"), ("w1", "f2", "bridge"), ("w2", "f1", "bridge"), ("w3", "f2", "atom")]
    assert [r["query"] for r in rows] == ["Character stability in AI video stories", "Camera motion dialects differ per video model",
                                          "Preserve emotion before continuity in ads", "Granular motion control per video model"]
    assert all(r["kept"] is True and r["gate_score"] > 0.9 and r["union"] > 0 for r in rows)
    assert rec["built"] == rec["kept"] == rec["searched"] == 4 and rec["per_facet"] == {"f1": 2, "f2": 2} and rec["with_evidence"] == 4
    # the atom frontier folds its atoms into the sweep as parents too (abstraction = the atom text): those repeat the atom
    # candidates (duplicates), and the rows a full facet cannot seat are counted, never moved to another facet
    assert rec["build"]["candidates"] == {"seealso": 0, "atom": 3, "latent": 6}
    assert rec["build"]["dropped_duplicate"] == 2 and rec["build"]["dropped_no_room"] == 3
    assert rec["gate"] == {"version": "probe-gate-v1", "floor": 0.2, "scored": 4, "dropped": [], "kept_unscored": 0}
    # the gate scored the rows against the ORIGINAL question, once; the turn's judge ran once; one extra embedding call for the texts
    assert h.gate_calls == [["w0", "w1", "w2", "w3"]] and h.judge_calls == 1
    assert h.embed_calls == [[QUERY, SUBS[0][2]], [r["query"] for r in rows]]
    # the second pass's evidence is in the union with its mapped id and origin, and reached the FINAL evidence
    aspects = out["meta"]["aspects"]
    assert {q for q in aspects if q.startswith("w")} == {"w0", "w1", "w2", "w3"}
    assert all(aspects[w]["origin"] == "WILDCARD" and aspects[w]["union"] > 0 and aspects[w]["type"] == "ENTITY" and aspects[w]["weight"] == 0.55
               for w in ("w0", "w1", "w2", "w3"))
    mapped_final = [d for d in out["meta"]["final_detail"] if d["chunk_id"].startswith("m")]
    assert mapped_final and all(any(q.startswith("w") for q in d["query_ids"]) for d in mapped_final)
    assert rec["added"] >= 4 and any(c.startswith("m") for c in out["trace"]["funnel_union"])
    # the counts ride the trace (→ the receipt's retrieval_trace); the facets handed to the composer include the mapped ids
    assert out["trace"]["mapped_subqueries"]["n"] == 4 and out["trace"]["mapped_subqueries"]["built"] == 4
    seats = {s["facet_id"]: s for s in out["meta"]["composition"]["facet_seats"]}
    assert set(seats) == {"f1", "f2"}
    assert isinstance(out["trace"]["latency_ms"]["mapped_pass"], float) and out["meta"]["wildcard"]["mapped_pass_ms"] == out["trace"]["latency_ms"]["mapped_pass"]
    # the bridges still ride their own lane, verified, outside the evidence — and a latent row whose parent became a bridge says so
    assert out["wildcard"] and all(b["verified"] for b in out["wildcard"]) and out["meta"]["wildcard"]["degraded"] is None
    assert {b["parent_id"] for b in out["wildcard"]} >= {"pfar0", "pfar1"}
    assert all(b["source_evidence"]["chunk_id"] not in set(_ids(out)) for b in out["wildcard"])


def test_the_second_pass_is_fused_exactly_like_a_plan_subquery(monkeypatch):
    """The union, the fused scores and the FINAL evidence of a turn whose plan carried the two subqueries equal those of a
    turn that added them through the seam — the merge is the engine's own union rule, not a second fusion."""
    monkeypatch.delenv(wm.MAPPED_FLAG, raising=False)
    extra = (("w0", "ENTITY", "Character stability in AI video stories", 0.55, "WILDCARD", ""),
             ("w1", "ENTITY", "Camera motion dialects differ per video model", 0.55, "WILDCARD", ""))
    facets_all = (("f1", ("q0", "w0")), ("f2", ("q1", "w1")))
    ha = _Harness(monkeypatch)
    a = ha.v2(subqueries=SUBS + extra, facets=facets_all)

    def seam(ctx, pool, result):
        rows = [{"id": i, "facet_id": f, "query": t, "from": "atom", "kept": True} for (i, _, t, _, _, _), f in zip(extra, ("f1", "f2"))]
        return rows, {"skipped": None}, None

    hb = _Harness(monkeypatch)
    b = hb.v2(subqueries=SUBS, facets=FACETS, second_pass=seam)
    assert a["trace"]["funnel_union"] == b["trace"]["funnel_union"] and a["trace"]["final"] == b["trace"]["final"]
    assert _ids(a) == _ids(b)
    fa = {d["chunk_id"]: d for d in a["meta"]["final_detail"]}
    fb = {d["chunk_id"]: d for d in b["meta"]["final_detail"]}
    assert fa == fb
    ea = {e["chunk_id"]: (e["fused_score"], e["query_scores"], sorted(e["query_ids"]), sorted(e["arrivals"])) for e in a["evidence"]}
    eb = {e["chunk_id"]: (e["fused_score"], e["query_scores"], sorted(e["query_ids"]), sorted(e["arrivals"])) for e in b["evidence"]}
    assert ea == eb
    assert a["meta"]["composition"]["facet_seats"] == b["meta"]["composition"]["facet_seats"]
    assert {q: (v["union"], v["lanes"]) for q, v in a["meta"]["aspects"].items()} == {q: (v["union"], v["lanes"]) for q, v in b["meta"]["aspects"].items()}
    assert b["trace"]["mapped_subqueries"]["n"] == 2 and ha.judge_calls == hb.judge_calls == 1
    assert len(ha.embed_calls) == 1 and len(hb.embed_calls) == 2                                      # the seam's texts: one more call


def test_the_gate_drops_a_low_mapped_subquery_before_it_is_searched_and_counts_it(monkeypatch):
    monkeypatch.delenv(wm.MAPPED_FLAG, raising=False)
    h = _Harness(monkeypatch, gate_scores={"Character stability in AI video stories": -3.0})
    out = h.mode("WILDCARD")
    rows, rec = _mapped(out)
    dropped = [r for r in rows if not r["kept"]]
    assert [r["id"] for r in dropped] == ["w0"] and dropped[0]["gate_score"] == 0.0474 and dropped[0]["union"] == 0
    assert rec["gate"]["dropped"] == ["w0"] and rec["kept"] == rec["searched"] == 3 and rec["built"] == 4
    assert "Character stability in AI video stories" not in h.embed_calls[1]                          # never embedded, never searched
    assert "w0" not in out["meta"]["aspects"] and all(w in out["meta"]["aspects"] for w in ("w1", "w2", "w3"))


def test_a_raising_gate_keeps_every_mapped_subquery_and_counts_it(monkeypatch):
    monkeypatch.delenv(wm.MAPPED_FLAG, raising=False)
    h = _Harness(monkeypatch, gate_raises=True)
    out = h.mode("WILDCARD")
    rows, rec = _mapped(out)
    assert len(rows) == 4 and all(r["kept"] is True and r["gate_score"] is None and r["union"] > 0 for r in rows)
    assert rec["gate"]["error"] == "RuntimeError" and rec["gate"]["kept_unscored"] == 4 and rec["gate"]["dropped"] == []
    assert rec["searched"] == 4 and len(h.gate_calls) == 1


def test_a_sweep_still_out_at_the_deadline_skips_the_pass_and_the_first_pass_stands(monkeypatch):
    monkeypatch.delenv(wm.MAPPED_FLAG, raising=False)
    h = _Harness(monkeypatch, latent_sleep=1.5)
    t0 = _time.perf_counter()
    out = h.mode("WILDCARD", budget=ce.CandidateBudget(wildcard_deadline_s=0.2))
    wall = _time.perf_counter() - t0
    rows, rec = _mapped(out)
    assert rows == [] and rec["skipped"] == "deadline" and rec["built"] == rec["kept"] == rec["searched"] == 0
    assert h.gate_calls == [] and len(h.embed_calls) == 1 and h.judge_calls == 1                     # nothing was gated or searched
    assert out["trace"]["mapped_subqueries"]["skipped"] == "deadline" and "mapped_pass" in out["trace"]["latency_ms"]
    assert not any(q.startswith("w") for q in out["meta"]["aspects"])
    assert out["meta"]["wildcard"]["degraded"] == "wildcard_timeout:sweep" and out["wildcard"] == []
    hh = _Harness(monkeypatch)
    assert _ids(out) == _ids(hh.mode("HYBRID"))                                                      # the core answer is intact
    assert wall < 1.2, wall
    h.release.set()


def test_the_flag_off_is_the_pre_f3_composition_byte_for_byte_and_hybrid_never_runs_the_pass(monkeypatch):
    """The HEAD outputs of tests/determinism/test_chat_modes.py's harness were pinned BEFORE the change (clock readings
    stripped); with POLYMATH_WILDCARD_MAPPED=0 every pinned configuration reproduces, and HYBRID reproduces with the flag on."""
    import test_chat_modes as tcm

    clock = {"latency_ms", "timings_ms", "sweep_done_before_core", "lane_ms", "ms"}

    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if not (str(k).endswith("_ms") or k in clock)}
        if isinstance(x, (list, tuple)):
            return [strip(v) for v in x]
        return x

    subs = (("q1", "MECHANISM", "reward models for prompts", 0.8, "USER", ""), ("p0", "ENTITY", "prompt optimisation with reward models", 0.6, "PROFILE", "doc_x"))
    facets = (("f1", ("q0", "q1")), ("f2", ("p0",)))
    monkeypatch.setenv(wm.MAPPED_FLAG, "0")
    assert strip(tcm._ModeHarness(monkeypatch, latent=tcm.FAR_FIVE + [tcm.OBVIOUS]).mode("WILDCARD")) == PINS["wildcard_plain"]
    assert strip(tcm._ModeHarness(monkeypatch, latent=tcm.FAR_FIVE + [tcm.OBVIOUS]).mode("WILDCARD", subqueries=subs, facets=facets)) == PINS["wildcard_subs_facets"]
    assert strip(tcm._ModeHarness(monkeypatch, latent=tcm.FAR_FIVE[:2] + [tcm.PNEAR]).mode("WILDCARD", subqueries=subs)) == PINS["wildcard_pnear"]
    from polymath_shared import embedding_contracts
    from polymath_shared.document_profile import parent_map_projection as pmp
    from polymath_shared.document_profile import profile_atom_projection as pap
    monkeypatch.setattr(embedding_contracts, "active_contract", lambda: SimpleNamespace(contract_id="c"))
    monkeypatch.setattr(pap, "search_atoms", lambda *a, **k: [
        {"doc_id": "docA", "atom_kind": "CONCEPT", "text": "withheld information", "score": 0.61},
        {"doc_id": "docB", "atom_kind": "SEEALSO", "text": "suspense and anticipation", "score": 0.55}])
    monkeypatch.setattr(pmp, "search_parent_maps", lambda *a, **k: [
        {"parent_id": "pA1", "doc_id": "docA", "score": 0.5}, {"parent_id": "pB1", "doc_id": "docB", "score": 0.4}])
    off = tcm._ModeHarness(monkeypatch, latent=tcm.FAR_FIVE).mode("WILDCARD", subqueries=subs, facets=facets)
    assert strip(off) == PINS["wildcard_atoms_subs_facets"] and "mapped_subqueries" not in off["meta"]["wildcard"]
    # the flag on: the same atoms now map (the receipt keys appear); HYBRID is untouched either way
    monkeypatch.delenv(wm.MAPPED_FLAG, raising=False)
    on = tcm._ModeHarness(monkeypatch, latent=tcm.FAR_FIVE).mode("WILDCARD", subqueries=subs, facets=facets)
    assert on["meta"]["wildcard"]["mapped_pass"]["built"] >= 1 and "mapped_subqueries" in on["meta"]["wildcard"]
    assert strip(tcm._ModeHarness(monkeypatch).mode("HYBRID", subqueries=subs, facets=facets)) == PINS["hybrid_subs_facets"]


def test_the_seam_is_the_compositions_and_the_question_never_reaches_another_mode(monkeypatch):
    monkeypatch.delenv(wm.MAPPED_FLAG, raising=False)
    h = _Harness(monkeypatch)
    with pytest.raises(TypeError):
        h.mode("HYBRID", second_pass=lambda *a: ([], {}, None))
    hyb = h.mode("HYBRID", question=QUESTION)                                                         # dropped, never an error
    assert "mapped_subqueries" not in hyb["trace"] and h.gate_calls == [] and "wildcard" not in hyb
    seen = {}

    def record(query, corpus_id, **kw):
        seen.update(kw)
        return {"meta": {}, "evidence": [], "trace": {}}

    monkeypatch.setattr(cr, "chat_retrieve_v2", record)
    cr.chat_retrieve_mode("GRAPH", QUERY, "cinema", question=QUESTION)
    assert "question" not in seen and "second_pass" not in seen


def test_the_turn_receipt_keeps_the_counts_in_retrieval_trace_and_the_rows_under_wildcard():
    """ui._turn_receipt_extras (S1a): the second pass's counts ride `retrieval_trace.mapped_subqueries`; the rows and the
    pass receipt ride `wildcard`; every clock reading (`mapped_pass_ms`, `mapped_wait_ms`, `mapped_gate_ms`) lands under
    `trace_ms.wildcard` only."""
    from orchestrator.api.ui import _turn_receipt_extras
    trace = {"aspects": {"w0": {"origin": "WILDCARD", "union": 4}}, "mapped_subqueries": {"n": 2, "built": 3, "dropped": 1, "skipped": None},
             "timings_ms": {"sub_w0_dense": 12.0}, "latency_ms": {"mapped_pass": 210.5}}
    wildcard = {"returned": 1, "mapped_subqueries": [{"id": "w0", "facet_id": "f1", "query": "camera motion dialects", "from": "atom",
                                                      "gate_score": 0.98, "union": 4, "kept": True}],
                "mapped_pass": {"skipped": None, "built": 3, "kept": 2, "searched": 2, "gate": {"floor": 0.2, "scored": 3, "dropped": ["w2"]}},
                "mapped_pass_ms": 210.5, "mapped_wait_ms": 0.3, "mapped_gate_ms": 40.0, "sweep_ms": 300.0}
    out = _turn_receipt_extras(trace, None, wildcard)
    assert out["retrieval_trace"]["mapped_subqueries"] == {"n": 2, "built": 3, "dropped": 1, "skipped": None}
    assert out["wildcard"]["mapped_subqueries"][0]["facet_id"] == "f1" and out["wildcard"]["mapped_pass"]["gate"]["dropped"] == ["w2"]
    assert not any(k.endswith("_ms") for k in out["wildcard"])
    assert out["trace_ms"]["wildcard"] == {"mapped_pass_ms": 210.5, "mapped_wait_ms": 0.3, "mapped_gate_ms": 40.0, "sweep_ms": 300.0}
    assert out["trace_ms"]["retrieval"]["mapped_pass"] == 210.5
