"""P1.e part 2 — ui.py mode dispatch onto chat_retrieve_mode (FAST/VECTOR, GRAPH, WILDCARD on the v2 engine),
graph facts + wildcard lane consumed from the v2-shaped result; /chat too. Apply after p1e_patch.py."""
import pathlib
ROOT = pathlib.Path("/Users/king/Documents/polymath-rebuild/polymath-v4")
p = ROOT / "orchestrator/orchestrator/api/ui.py"; s = p.read_text(encoding="utf-8")
# 1. GRAPH branch: v2 engine + bounded graph (fallback to v1 only under latent / retrieval=v1)
old_start = s.index('            elif ui_mode == "GRAPH":')
old_end = s.index('            else:\n                yield _phase("retrieve", f"{ui_mode} retrieval over "')
new_graph = '''            elif ui_mode == "GRAPH":
                yield _phase("retrieve", f"{ui_mode} retrieval over "
                                         f"{corpus_id}…", mode=ui_mode, query=_retrieval_text[:160])
                from orchestrator.api.chat_retrieval import chat_retrieval_flag, chat_retrieve_mode
                _rflag = chat_retrieval_flag(getattr(req, "retrieval", None))
                if _rflag in ("v2", "v2-single") and not req.latent:
                    # P1.e: GRAPH = HYBRID candidates → bounded hop-1 over the FINAL evidence (§3.18);
                    # a plan that says the question is not relational expands ≤ 2 seeds (§5 #14)
                    fast = chat_retrieve_mode(
                        "GRAPH", _retrieval_text, corpus_id, graph_useful=(bool(getattr(_plan, "graph_useful", True)) if _plan is not None else True),
                        exact_terms=tuple(_plan.exact_terms) if (_flag == "on" and _plan is not None) else (),
                        subqueries=tuple((q.id, q.type, q.query, q.weight) for q in _plan.queries if q.type != "PRIMARY")
                        if (_flag == "on" and _plan is not None and _rflag == "v2") else ())
                    _trace = fast.get("trace") or {}
                    latent_meta = None
                    evidence_rows = [{"chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "parent_id": c["parent_id"]} for c in fast["evidence"]]
                    _arrivals = {c["chunk_id"]: c.get("arrivals") or [] for c in fast["evidence"]}
                    _aspects = (fast.get("meta") or {}).get("aspects") or {}
                    _weak = (fast.get("meta") or {}).get("weak_aspects") or []
                    yield _phase("retrieve_done", "Evidence selected", evidence_count=len(evidence_rows),
                                 lane_sizes=_trace.get("lane_sizes"), plan=(fast.get("meta") or {}).get("plan_version"),
                                 degraded=[d.get("component") for d in ((fast.get("meta") or {}).get("degraded") or [])] or None)
                    yield _phase("graph", "Expanding the canonical fact graph (hop-1, bounded)…",
                                 bounds=(fast.get("meta") or {}).get("graph_bounds"))
                    graph_facts = [{"fact_id": f["fact_id"], "predicate": f["predicate"], "subject": f["subject"], "object": f["object"]}
                                   for f in (fast.get("graph_relationships") or [])]
                    yield _phase("graph_done", f"{len(graph_facts)} canonical relationship(s)",
                                 graph_fact_count=len(graph_facts), relationships=graph_facts[:8],
                                 seeds=(fast.get("meta") or {}).get("graph_seeds"))
                    document_summaries = [{"doc_id": d["doc_id"], "summary": (d.get("document_summary") or {}).get("text", "")}
                                          for d in fast["selected_documents"] if d.get("document_summary")]
                    parent_ids = [s_["parent_id"] for s_ in fast["selected_sections"]]
                    with tx() as conn:
                        rows = conn.execute("SELECT chunk_id, doc_id, summary FROM chunks WHERE chunk_id = ANY(%s)", (parent_ids,)).fetchall()
                    section_summaries = [{"chunk_id": r[0], "doc_id": r[1], "summary": r[2] or ""} for r in rows]
                else:
                    from orchestrator.api.graph import graph_retrieve
                    g = graph_retrieve(_retrieval_text, corpus_id, latent=req.latent)
                    fast = {"meta": g.get("meta") or {}, "trace": g.get("trace") or {}, "evidence": []}
                    _trace = g.get("trace") or {}
                    latent_meta = (g.get("meta") or {}).get("latent")
                    evidence_rows = [
                        {"chunk_id": c["chunk_id"], "doc_id": d["doc_id"],
                         "parent_id": s["parent_id"]}
                        for d in g["documents"]
                        for s in d["sections"]
                        for c in s["evidence"]
                    ]
                    yield _phase("retrieve_done", "Dense + lexical evidence "
                                 "selected",
                                 evidence_count=len(evidence_rows),
                                 lane_sizes=g["trace"].get("lane_sizes"))
                    yield _phase("graph", "Expanding the canonical fact "
                                          "graph (hop-1)…")
                    graph_facts = [
                        {"fact_id": f["fact_id"], "predicate": f["predicate"],
                         "subject": f["subject"], "object": f["object"]}
                        for f in g["graph_relationships"]
                    ]
                    yield _phase("graph_done",
                                 f"{len(graph_facts)} canonical relationship(s)",
                                 graph_fact_count=len(graph_facts),
                                 relationships=graph_facts[:8])
                    document_summaries = [
                        {"doc_id": d["doc_id"],
                         "summary": d["document_summary"] or ""}
                        for d in g["documents"] if d["document_summary"]
                    ]
                    section_summaries = [
                        {"chunk_id": s["parent_id"], "doc_id": d["doc_id"],
                         "summary": s["summary"] or ""}
                        for d in g["documents"] for s in d["sections"]
                    ]
'''
s = s[:old_start] + new_graph + s[old_end:]
# 2. FAST / WILDCARD branches: v2 engine compositions (v1 kept behind retrieval=v1 / latent)
old = '''                wildcard_lane = None
                if ui_mode == "FAST":
                    from orchestrator.api.fast import fast_retrieve
                    fast = fast_retrieve(_retrieval_text, corpus_id)
                elif ui_mode == "WILDCARD":'''
new = '''                wildcard_lane = None
                from orchestrator.api.chat_retrieval import chat_retrieval_flag as _crf, chat_retrieve_mode as _crm
                _rflag_mode = _crf(getattr(req, "retrieval", None))
                _v2_mode = _rflag_mode in ("v2", "v2-single") and not req.latent
                _subq = (tuple((q.id, q.type, q.query, q.weight) for q in _plan.queries if q.type != "PRIMARY")
                         if (_flag == "on" and _plan is not None and _rflag_mode == "v2") else ())
                _exact = tuple(_plan.exact_terms) if (_flag == "on" and _plan is not None) else ()
                if ui_mode == "FAST" and _v2_mode:
                    # P1.e: VECTOR = lanes A + B on the v2 engine (no sparse lane)
                    fast = _crm("VECTOR", _retrieval_text, corpus_id, exact_terms=_exact, subqueries=_subq)
                elif ui_mode == "WILDCARD" and _v2_mode:
                    # P1.e: WILDCARD = HYBRID core ∥ latent sweep; bridges never enter the evidence list
                    fast = _crm("WILDCARD", _retrieval_text, corpus_id, exact_terms=_exact, subqueries=_subq)
                    wildcard_lane = fast.get("wildcard") or []
                elif ui_mode == "FAST":
                    from orchestrator.api.fast import fast_retrieve
                    fast = fast_retrieve(_retrieval_text, corpus_id)
                elif ui_mode == "WILDCARD":'''
assert s.count(old) == 1; s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
import ast; ast.parse(s); print("ui.py: modes on the v2 engine")
# 3. answer event: strip the private _qvec if it leaked into meta (it is on the result root, not in retrieval) — nothing to do
# 4. /chat FAST → VECTOR on v2 as well
p = ROOT / "orchestrator/orchestrator/api/chat.py"; s = p.read_text(encoding="utf-8")
old = '''        if mode == MODE_FAST:
            from orchestrator.api.fast import fast_retrieve

            fast = fast_retrieve(query, list(scope.corpus_ids))  # F8: multi-corpus'''
new = '''        from orchestrator.api.chat_retrieval import chat_retrieval_flag as _crf
        if mode == MODE_FAST and _crf(getattr(req, "retrieval", None)) in ("v2", "v2-single") and len(list(scope.corpus_ids)) == 1 \\
                and not getattr(req, "latent", None) and not getattr(req, "utility", None):
            from orchestrator.api.chat_retrieval import chat_retrieve_mode
            fast = chat_retrieve_mode("VECTOR", query, list(scope.corpus_ids)[0])      # P1.e: VECTOR = A + B on v2
        elif mode == MODE_FAST:
            from orchestrator.api.fast import fast_retrieve

            fast = fast_retrieve(query, list(scope.corpus_ids))  # F8: multi-corpus'''
assert s.count(old) == 1; s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); ast.parse(s); print("chat.py: FAST → VECTOR on v2 (single corpus)")
