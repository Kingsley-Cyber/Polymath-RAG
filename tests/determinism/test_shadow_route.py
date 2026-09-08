"""S8 shadow route — pure-logic unit tests (no store, no network).

Proves the profile → parent-map → child shadow pipeline: ordering/dedup, the §17
single-filtered-map-search contract, pair localization into the child lane, graceful
degradation (a shadow never raises), and the coverage math the canary reports.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from polymath_shared.document_profile.shadow_route import (  # noqa: E402
    ShadowReceipt,
    doc_nomination_hit,
    gold_hit,
    overlap_with_final,
    shadow_route,
)

QV = [0.1, 0.2, 0.3]


def _profile(rows):
    calls = []

    def f(vec, k):
        calls.append(("profile", vec, k))
        return rows[:k]

    f.calls = calls
    return f


def _map(rows):
    seen = {}

    def f(vec, doc_ids, k):
        seen["doc_ids"] = list(doc_ids)
        seen["k"] = k
        # a faithful fake filters to the nominated docs, like the real filtered search.
        return [r for r in rows if r["doc_id"] in set(doc_ids)][:k]

    f.seen = seen
    return f


def _child(rows):
    seen = {}

    def f(vec, pairs, k):
        seen["pairs"] = list(pairs)
        seen["k"] = k
        keep = set(pairs)
        return [r for r in rows if (r["doc_id"], r["parent_id"]) in keep][:k]

    f.seen = seen
    return f


def test_happy_path_pipeline_and_receipt_shape():
    prof = _profile([{"doc_id": "D1", "score": 0.9}, {"doc_id": "D2", "score": 0.8}])
    mp = _map([
        {"doc_id": "D1", "parent_id": "P1", "alias": "a", "score": 0.7},
        {"doc_id": "D2", "parent_id": "P2", "alias": "b", "score": 0.6},
    ])
    ch = _child([
        {"chunk_id": "C1", "doc_id": "D1", "parent_id": "P1", "score": 0.5},
        {"chunk_id": "C2", "doc_id": "D2", "parent_id": "P2", "score": 0.4},
    ])
    r = shadow_route(QV, profile_search=prof, map_search=mp, child_search=ch)

    assert isinstance(r, ShadowReceipt)
    assert r.profile_doc_candidates == ("D1", "D2")
    assert r.resolved_parent_ids == ("P1", "P2")
    assert r.shadow_child_candidates == ("C1", "C2")
    assert r.degraded == ()
    # §17 performance rule: ONE filtered parent-map search over ALL nominated docs.
    assert mp.seen["doc_ids"] == ["D1", "D2"]
    # child lane localizes to the resolved (doc, parent) pairs.
    assert ch.seen["pairs"] == [("D1", "P1"), ("D2", "P2")]
    # latency keys present and numeric.
    assert set(r.latency_ms) == {"profile", "map", "child", "total"}
    assert all(isinstance(v, (int, float)) for v in r.latency_ms.values())
    rec = r.as_receipt()
    assert rec["resolved_parent_ids"] == ["P1", "P2"]
    assert rec["parent_map_candidates"][0]["parent_id"] == "P1"


def test_dedupe_preserves_first_seen_order():
    prof = _profile([{"doc_id": "D1"}, {"doc_id": "D1"}, {"doc_id": "D2"}])
    mp = _map([
        {"doc_id": "D1", "parent_id": "P1"},
        {"doc_id": "D1", "parent_id": "P1"},  # duplicate parent
        {"doc_id": "D2", "parent_id": "P2"},
    ])
    ch = _child([
        {"chunk_id": "C1", "doc_id": "D1", "parent_id": "P1"},
        {"chunk_id": "C1", "doc_id": "D1", "parent_id": "P1"},  # duplicate child
        {"chunk_id": "C9", "doc_id": "D2", "parent_id": "P2"},
    ])
    r = shadow_route(QV, profile_search=prof, map_search=mp, child_search=ch)
    assert r.profile_doc_candidates == ("D1", "D2")
    assert r.resolved_parent_ids == ("P1", "P2")
    assert r.shadow_child_candidates == ("C1", "C9")
    # the fake still received the deduped pair once.
    assert ch.seen["pairs"] == [("D1", "P1"), ("D2", "P2")]


def test_no_nominated_docs_short_circuits():
    prof = _profile([])
    mp = _map([{"doc_id": "D1", "parent_id": "P1"}])
    ch = _child([{"chunk_id": "C1", "doc_id": "D1", "parent_id": "P1"}])
    r = shadow_route(QV, profile_search=prof, map_search=mp, child_search=ch)
    assert r.profile_doc_candidates == ()
    assert r.resolved_parent_ids == ()
    assert r.shadow_child_candidates == ()
    assert "no_nominated_docs" in r.degraded
    # downstream stages were never queried.
    assert "doc_ids" not in mp.seen
    assert "pairs" not in ch.seen


def test_nominated_but_unmapped_records_no_resolved_parents():
    # the localization MISS the plan asks us to record: doc nominated, no map yet.
    prof = _profile([{"doc_id": "D1"}])
    mp = _map([])  # D1 has no projected parent map (unmapped-in-cohort)
    ch = _child([{"chunk_id": "C1", "doc_id": "D1", "parent_id": "P1"}])
    r = shadow_route(QV, profile_search=prof, map_search=mp, child_search=ch)
    assert r.profile_doc_candidates == ("D1",)
    assert r.resolved_parent_ids == ()
    assert r.shadow_child_candidates == ()
    assert "no_resolved_parents" in r.degraded
    assert "pairs" not in ch.seen  # child lane not queried without parents


def test_search_exception_degrades_never_raises():
    def boom(*a, **k):
        raise RuntimeError("qdrant down")

    r = shadow_route(QV, profile_search=boom, map_search=_map([]), child_search=_child([]))
    assert r.profile_doc_candidates == ()
    assert "profile_search_error" in r.degraded
    assert r.shadow_child_candidates == ()

    prof = _profile([{"doc_id": "D1"}])
    r2 = shadow_route(QV, profile_search=prof, map_search=boom, child_search=_child([]))
    assert "map_search_error" in r2.degraded
    assert r2.resolved_parent_ids == ()


def test_coverage_math():
    # overlap = fraction of the CURRENT final set the shadow recovered.
    assert overlap_with_final(["C1", "C2", "C3"], ["C1", "C2"]) == 1.0
    assert overlap_with_final(["C1"], ["C1", "C2"]) == 0.5
    assert overlap_with_final([], ["C1"]) == 0.0
    assert overlap_with_final(["C1"], []) == 0.0  # no final → no coverage claim
    # gold / nomination hits.
    assert gold_hit(["C1", "C2"], ["C2"]) is True
    assert gold_hit(["C1"], ["C9"]) is False
    assert gold_hit(["C1"], []) is False
    assert doc_nomination_hit(["D1", "D2"], ["D2"]) is True
    assert doc_nomination_hit(["D1"], ["D9"]) is False


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
