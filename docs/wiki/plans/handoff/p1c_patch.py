"""P1.c — judge + composition (re-anchored on the P1.b aspect-seat code). Apply after the P1.b commit."""
import pathlib, re
ROOT = pathlib.Path("/Users/king/Documents/polymath-rebuild/polymath-v4")

# ------------------------------------------------------------------ engine
p = ROOT / "shared/polymath_shared/candidate_engine.py"; s = p.read_text(encoding="utf-8")
old = '''    aspect_prefix_seats: int = 3
    aspect_weak_floor: float = 0.5
    aspect_final_seats: int = 1
'''
new = old + '''    #: P1.c EVIDENCE COMPOSER (§3.17): deterministic, metadata only. Slots
    #: over the judged prefix: pure relevance → source diversity (soft max
    #: per document unless the score gap to the best unrepresented document
    #: is large) → sparse winners (lane C arrivals) → aspect coverage (one
    #: seat per non-weak compiled query not yet represented) → fill. Scores
    #: are compared on a sigmoid of the raw judge logit so "gap 0.1" means
    #: the same thing on every reranker model.
    compose_relevance_slots: int = 8
    compose_doc_soft_max: int = 3
    compose_sparse_slots: int = 3
    compose_aspect_slots: int = 3
    compose_score_gap: float = 0.1
    #: bounded multi-lane agreement: +boost per extra lane, capped, applied to
    #: the sigmoid score for ORDERING inside composition only — never enough
    #: to pass a candidate with a clearly higher judge score (§5 #10c)
    compose_agreement_boost: float = 0.02
    compose_agreement_cap: float = 0.05
'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''def select_evidence(result: CandidateResult, budget: CandidateBudget, *,'''
new = '''def _sig(x: Optional[float]) -> float:
    import math
    if x is None:
        return 0.0
    x = max(-30.0, min(30.0, float(x)))
    return 1.0 / (1.0 + math.exp(-x))


def judged_score(c: CandidateEvidence, budget: CandidateBudget) -> float:
    """Sigmoid of the judge's logit plus the bounded agreement bonus (ordering only)."""
    base = _sig(c.rerank_score) if c.rerank_score is not None else 0.0
    extra = max(0, len(c.arrivals) - 1)
    return base + min(budget.compose_agreement_cap, budget.compose_agreement_boost * extra)


def compose_evidence(judged: list[CandidateEvidence], budget: CandidateBudget, *, weak_aspects: Iterable[str] = (),
                     primary_id: str = "q0") -> tuple[list[CandidateEvidence], dict]:
    """EVIDENCE-COMPOSER-V1 (§3.17). `judged` = the reranked prefix in judge
    order (rerank_score set, or fusion order when the judge degraded).
    Returns (final, composition trace). A chunk may satisfy several slots;
    the final list is deduped and may therefore be shorter than the cap."""
    cap = budget.synthesis_max
    weak = set(weak_aspects or ())
    if not judged:
        return [], {"slots": {}, "doc_counts": {}, "doc_share_top": 0.0, "docs_within_gap": 0, "dominance": False, "aspect_seats": [], "agreement_reordered": 0}
    order = sorted(range(len(judged)), key=lambda i: (-judged_score(judged[i], budget), i))
    order = [judged[i] for i in order]
    final: list[CandidateEvidence] = []
    seen: set[str] = set()
    slots = {"relevance": 0, "diversity": 0, "sparse": 0, "aspect": 0, "fill": 0}
    doc_count: dict[str, int] = {}
    aspect_seats: list[dict] = []

    def admit(c: CandidateEvidence, slot: str) -> bool:
        if c.chunk_id in seen or len(final) >= cap:
            return False
        seen.add(c.chunk_id); final.append(c); doc_count[c.doc_id] = doc_count.get(c.doc_id, 0) + 1; slots[slot] += 1
        return True

    def best_unrepresented() -> Optional[float]:
        return next((judged_score(c, budget) for c in order if c.doc_id not in doc_count), None)

    # 1. pure relevance
    for c in order[:budget.compose_relevance_slots]:
        admit(c, "relevance")
    # 2. source diversity: soft max per document unless the score gap to the best unrepresented document is large
    for c in order:
        if len(final) >= cap:
            break
        if c.chunk_id in seen:
            continue
        bu = best_unrepresented()
        under_cap = doc_count.get(c.doc_id, 0) < budget.compose_doc_soft_max
        big_gap = bu is None or (judged_score(c, budget) - bu) >= budget.compose_score_gap
        if under_cap or big_gap:
            admit(c, "diversity")
    # 3. sparse winners (exact-match lane arrivals) not yet seated
    n = 0
    for c in order:
        if n >= budget.compose_sparse_slots or len(final) >= cap:
            break
        if LANE_C in c.arrivals and c.chunk_id not in seen and admit(c, "sparse"):
            n += 1
    # 4. aspect coverage: one seat per non-weak compiled query not yet represented (displacing the lowest
    #    item that is not another aspect's only representative when the set is full)
    represented = {q for c in final for q in c.query_ids}
    aspects = []
    for c in order:
        for q in c.query_ids:
            if q != primary_id and q not in weak and q not in aspects:
                aspects.append(q)
    for q in aspects[:budget.compose_aspect_slots]:
        if q in represented:
            continue
        best_c = next((c for c in order if q in c.query_ids), None)
        if best_c is None or best_c.chunk_id in seen:
            continue
        displaced = None
        if len(final) >= cap:
            for c in reversed(final):
                others = [x for x in c.query_ids if x != primary_id]
                if not others or all(sum(1 for f in final if x in f.query_ids) > 1 for x in others):
                    displaced = c; break
            if displaced is None:
                continue
            final.remove(displaced); seen.discard(displaced.chunk_id); doc_count[displaced.doc_id] -= 1
        admit(best_c, "aspect"); represented.update(best_c.query_ids)
        aspect_seats.append({"query_id": q, "chunk_id": best_c.chunk_id, "displaced": (displaced.chunk_id if displaced else None)})
    # 5. fill remaining seats in judge order
    for c in order:
        if len(final) >= cap:
            break
        if c.chunk_id not in seen:
            admit(c, "fill")
    # dominance receipt (gate: no final set with > 60 % from one document when ≥ 3 documents score within 0.1 of the top)
    top = judged_score(order[0], budget)
    docs_within = len({c.doc_id for c in order if top - judged_score(c, budget) <= budget.compose_score_gap})
    share_top = (max(doc_count.values()) / len(final)) if final else 0.0
    trace = {"slots": slots, "doc_counts": dict(sorted(doc_count.items(), key=lambda kv: -kv[1])), "doc_share_top": round(share_top, 3),
             "docs_within_gap": docs_within, "dominance": bool(share_top > 0.6 and docs_within >= 3), "aspect_seats": aspect_seats,
             "agreement_reordered": sum(1 for i, c in enumerate(order) if c is not judged[i])}
    return final, trace


def select_evidence(result: CandidateResult, budget: CandidateBudget, *,'''
assert s.count(old) == 1; s = s.replace(old, new)
# replace the P1.b top-k + one-seat block with the composer
start = s.index("    final = list(prefix[:budget.synthesis_max])\n    seated: list[dict] = []")
end = s.index("    added = 0\n    if budget.neighbor_expansion > 0")
s = s[:start] + '''    final, composition = compose_evidence(prefix, budget, weak_aspects=set(weak_reason), primary_id=primary_id)
    seated = composition["aspect_seats"]
''' + s[end:]
old = '''             "aspect_prefix": aspect_prefix, "aspect_best": aspect_best, "aspect_seated": seated,'''
new = '''             "aspect_prefix": aspect_prefix, "aspect_best": aspect_best, "aspect_seated": seated, "composition": composition,'''
assert s.count(old) == 1; s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
import ast; ast.parse(s); print("engine: composer")

# ------------------------------------------------------------------ route meta
p = ROOT / "orchestrator/orchestrator/api/chat_retrieval.py"; s = p.read_text(encoding="utf-8")
old = '''            "aspect_seated": trace.get("aspect_seated"), "aspect_best": trace.get("aspect_best"), "final_detail": trace.get("final_detail"),'''
new = '''            "aspect_seated": trace.get("aspect_seated"), "aspect_best": trace.get("aspect_best"), "final_detail": trace.get("final_detail"),
            "composition": trace.get("composition"),'''
assert s.count(old) == 1; s = s.replace(old, new); p.write_text(s, encoding="utf-8"); ast.parse(s); print("route: composition meta")

# ------------------------------------------------------------------ ui.py answer event + receipt
p = ROOT / "orchestrator/orchestrator/api/ui.py"; s = p.read_text(encoding="utf-8")
old = '''                "final_detail": (fast.get("meta") or {}).get("final_detail"),'''
new = '''                "final_detail": (fast.get("meta") or {}).get("final_detail"),
                # P1.c EVIDENCE-COMPOSER-V1: slot fills, per-document counts, dominance flag
                "composition": (fast.get("meta") or {}).get("composition"),'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''                          "chat_plan": _plan_receipt or None, "prompt": _prompt_meta or None, "carry": _carry_meta})'''
new = '''                          "chat_plan": _plan_receipt or None, "prompt": _prompt_meta or None, "carry": _carry_meta,
                          "composition": retrieval.get("composition")})'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''                      "plan": (_trace or {}).get("plan"), "chat_plan": _plan_receipt or None, "carry": _carry_meta})'''
new = '''                      "plan": (_trace or {}).get("plan"), "chat_plan": _plan_receipt or None, "carry": _carry_meta,
                      "composition": retrieval.get("composition")})'''
assert s.count(old) == 1; s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); ast.parse(s)
p = ROOT / "shared/polymath_shared/query_receipts.py"; s = p.read_text(encoding="utf-8")
old = '''                          # CARRY-ACCOUNTING-V1 (P0.e)
                          "prompt", "carry")}'''
new = '''                          # CARRY-ACCOUNTING-V1 (P0.e); EVIDENCE-COMPOSER-V1 (P1.c)
                          "prompt", "carry", "composition")}'''
assert s.count(old) == 1; s = s.replace(old, new); p.write_text(s, encoding="utf-8"); print("ui + receipts: composition")

# ------------------------------------------------------------------ chat_baseline: survival + dominance
p = ROOT / "scripts/chat_baseline.py"; s = p.read_text(encoding="utf-8")
old = '''    lat = ret.get("latency_ms") or {}
    ph = (rec.get("meta") or {}).get("phase_ms") or {}
    return {"engine": ret.get("engine"), "arrivals_n": len(arrivals),'''
new = '''    lat = ret.get("latency_ms") or {}
    ph = (rec.get("meta") or {}).get("phase_ms") or {}
    comp = ret.get("composition") or {}
    return {"engine": ret.get("engine"), "arrivals_n": len(arrivals),
            "doc_share_top": comp.get("doc_share_top"), "docs_within_gap": comp.get("docs_within_gap"), "dominance": comp.get("dominance"),
            "composition_slots": comp.get("slots"),'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''        "compiled_queries_mean": round(sum(r.get("compiled_queries") or 0 for r in ok) / max(1, len(ok)), 2),'''
new = '''        "compiled_queries_mean": round(sum(r.get("compiled_queries") or 0 for r in ok) / max(1, len(ok)), 2),
        # P1.c: gold survives selection where it was in the union; document dominance under the gate's condition
        "survival_selected_given_union": round(sum(1 for r in ok if r.get("gold_in_union") and r.get("gold_selected_rank")) / max(1, sum(1 for r in ok if r.get("gold_in_union"))), 3),
        "dominance_violations": sum(1 for r in ok if r.get("dominance")),
        "dominance_eligible_turns": sum(1 for r in ok if (r.get("docs_within_gap") or 0) >= 3),
        "doc_share_top_mean": (round(sum(r.get("doc_share_top") or 0 for r in ok if r.get("doc_share_top") is not None) / max(1, sum(1 for r in ok if r.get("doc_share_top") is not None)), 3)
                              if any(r.get("doc_share_top") is not None for r in ok) else None),'''
assert s.count(old) == 1; s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); ast.parse(s); print("baseline: survival + dominance")

# ------------------------------------------------------------------ tests
p = ROOT / "tests/determinism/test_candidate_engine.py"; t = p.read_text(encoding="utf-8")
t += '''

def _cand(cid, doc, score, arrivals=(ce.LANE_B,), qids=("q0",)):
    return ce.CandidateEvidence(chunk_id=cid, doc_id=doc, parent_id=f"{doc}-p", source_name=doc, text=cid,
                                arrivals=list(arrivals), query_ids=list(qids), rerank_score=score)


def test_composer_slots_relevance_then_diversity_then_sparse_then_aspects():
    judged = [_cand(f"d1-{i}", "d1", 6.0 - i * 0.1) for i in range(10)]
    judged += [_cand("d2-a", "d2", 4.0), _cand("d3-a", "d3", 3.5), _cand("d1-x", "d1", 3.4),
               _cand("sp-1", "d4", -1.0, arrivals=(ce.LANE_C,)), _cand("asp-q2", "d5", -2.0, qids=("q2",)), _cand("d1-y", "d1", -3.0)]
    b = ce.CandidateBudget(synthesis_max=15, compose_relevance_slots=8, compose_doc_soft_max=3, compose_sparse_slots=3, compose_aspect_slots=3)
    final, tr = ce.compose_evidence(judged, b)
    ids = [c.chunk_id for c in final]
    assert ids[:8] == [f"d1-{i}" for i in range(8)]                                    # pure relevance first, untouched
    assert "d2-a" in ids and "d3-a" in ids                                              # diversity seats other documents
    assert "sp-1" in ids and tr["slots"]["sparse"] >= 1                                 # the exact-match winner is seated
    assert "asp-q2" in ids and tr["slots"]["aspect"] >= 1 and tr["aspect_seats"][0]["query_id"] == "q2"
    assert len(ids) == len(set(ids)) <= 15
    assert tr["doc_counts"]["d1"] >= 8 and tr["doc_share_top"] > 0.5
    assert tr["dominance"] is False                                                     # d2/d3 are far below the top: no 3 docs within 0.1
    # a weak aspect is never seated
    final2, tr2 = ce.compose_evidence(judged, b, weak_aspects={"q2"})
    assert "asp-q2" not in [c.chunk_id for c in final2] and tr2["aspect_seats"] == []


def test_composer_flags_dominance_only_when_three_documents_are_close():
    judged = [_cand(f"d1-{i}", "d1", 2.0) for i in range(12)] + [_cand("d2-a", "d2", 1.95), _cand("d3-a", "d3", 1.9)]
    final, tr = ce.compose_evidence(judged, ce.CandidateBudget(synthesis_max=15))
    assert tr["docs_within_gap"] >= 3
    assert "d2-a" in [c.chunk_id for c in final] and "d3-a" in [c.chunk_id for c in final]
    assert tr["doc_share_top"] <= 0.6 + 1e-9 or tr["dominance"] is True                # the flag is honest either way
    judged2 = [_cand(f"d1-{i}", "d1", 5.0) for i in range(12)] + [_cand("d2-a", "d2", -4.0)]
    final2, tr2 = ce.compose_evidence(judged2, ce.CandidateBudget(synthesis_max=15))
    assert tr2["docs_within_gap"] == 1 and tr2["dominance"] is False and sum(1 for c in final2 if c.doc_id == "d1") == 12   # gap rule: one document may keep the set


def test_agreement_bonus_never_passes_a_clearly_higher_judge_score():
    single = _cand("s", "d1", 2.0)                                                       # sigmoid 0.88
    triple = _cand("t", "d2", 1.9, arrivals=(ce.LANE_A, ce.LANE_B, ce.LANE_C))           # sigmoid 0.87 + 0.04 bonus → passes a near-tie
    far = _cand("f", "d3", 0.5, arrivals=(ce.LANE_A, ce.LANE_B, ce.LANE_C))              # sigmoid 0.62 + 0.04 → never passes 0.88
    b = ce.CandidateBudget()
    assert ce.judged_score(triple, b) > ce.judged_score(single, b) > ce.judged_score(far, b)
    final, _ = ce.compose_evidence([single, triple, far], b)
    assert [c.chunk_id for c in final][:2] == ["t", "s"]
    a, c2 = _cand("a", "d1", None), _cand("c", "d2", None, arrivals=(ce.LANE_A, ce.LANE_B))
    assert ce.judged_score(c2, b) - ce.judged_score(a, b) <= b.compose_agreement_cap    # degraded judge: bonus stays bounded


def test_select_evidence_composes_and_receipts_the_composition():
    fake = Fake()
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake.dense, sparse_search=fake.sparse)
    final, tr = ce.select_evidence(res, ce.CandidateBudget(rerank_max=8, synthesis_max=5),
                                   rerank_children=lambda q, rows: sorted([dict(r, rerank_score=1.0 - i * 0.1) for i, r in enumerate(rows)], key=lambda r: -r["rerank_score"]))
    assert len(final) <= 5 and tr["composition"]["slots"]["relevance"] == 5 and len(tr["final_detail"]) == len(final)
    assert all(d["arrivals"] and d["chunk_id"] for d in tr["final_detail"]) and "doc_share_top" in tr["composition"]
'''
p.write_text(t, encoding="utf-8")
# scaffold + README
p = ROOT / "scripts/scaffold_polymath_v4.py"; s = p.read_text(encoding="utf-8")
anchor = '    ("docs/wiki/experiments/chat-baseline-p1b-B-after.md", "md", None),\n'; assert s.count(anchor) == 1
add = ''.join(f'    ("{f}", "{f.rsplit(".",1)[1]}", None),\n' for f in [
    "docs/wiki/work-log/2026-09-05-p1c-composition.md",
    "docs/wiki/experiments/chat-baseline-p1c-B-after.json", "docs/wiki/experiments/chat-baseline-p1c-B-after.md",
    "docs/wiki/experiments/chat-baseline-p1c-B-llm-after.json", "docs/wiki/experiments/chat-baseline-p1c-B-llm-after.md",
    "docs/wiki/experiments/chat-baseline-p1c-M-after.json", "docs/wiki/experiments/chat-baseline-p1c-M-after.md"])
p.write_text(s.replace(anchor, anchor + add), encoding="utf-8")
p = ROOT / "scripts/README.md"; s = p.read_text(encoding="utf-8")
line = [l for l in s.split("\n") if l.startswith("| `scripts/chat_baseline.py`")][0]
if "survival_selected_given_union" not in line:
    s = s.replace(line, line.rstrip(" |") + " P1.c: `survival_selected_given_union`, `dominance_violations` / `dominance_eligible_turns`, `doc_share_top_mean` from the composer receipt. |")
    p.write_text(s, encoding="utf-8")
print("P1.c patch applied")
