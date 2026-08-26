"""ASK production route: knowledge-type-aware question answering.

QUERY-ROUTER-V1 classifies intent, then the route selects among STORED
knowledge objects only:

  FACT_QUERY      -> matching facts (predicate/surface) + their exact
                     evidence chunks + graph relationships
  PROCEDURE_QUERY -> procedure_artifacts (ordered steps + tools) +
                     source documents
  CONCEPT_QUERY   -> concept_artifacts + supporting document context
  POLYMATH_QUERY  -> corpus map neighborhoods + concept lanes + hybrid
                     evidence

Grounding by construction: every answer element is a persisted row and
carries its source ids. Nothing is generated; the response assembles.
Deterministic: fixed weights, ties broken by id.
"""
from __future__ import annotations

import json
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from polymath_shared.db import tx
from polymath_shared.query_router import (
    QUERY_ROUTER_VERSION,
    ROUTE_CONCEPT,
    ROUTE_FACT,
    ROUTE_POLYMATH,
    ROUTE_PROCEDURE,
    classify_query,
)

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    corpus_id: Optional[str] = None
    corpus_ids: Optional[list[str]] = None
    workspace: Optional[str] = None
    all_authorized: bool = False


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _terms(question: str) -> list[str]:
    stop = {"what", "which", "who", "how", "the", "a", "an", "is", "are",
            "was", "were", "of", "to", "for", "in", "on", "do", "does",
            "did", "and", "or", "by", "with", "this", "that", "i", "we"}
    return [t for t in _norm(question).split(" ") if t and t not in stop]


def _match_score(text: str, terms: list[str]) -> float:
    t = _norm(text)
    if not t:
        return 0.0
    hit = sum(1 for term in terms if term in t)
    return hit / max(len(terms), 1)


# ------------------------------------------------------------------ lanes

def _merge_terms(question: str, extra_terms=()) -> list[str]:
    """Query terms + CORPUS-MAP-PLANNING-V1 expansion terms. Expansion
    terms only ADD candidate matches against the same stored objects —
    authority and provenance are untouched."""
    terms = _terms(question)
    for t in extra_terms:
        tn = _norm(t)
        if tn and tn not in terms:
            terms.append(tn)
    return terms


def _procedures(conn, scope: "QueryScope", question: str,
                extra_terms=()) -> list[dict]:
    terms = _merge_terms(question, extra_terms)
    where = "WHERE corpus_id = ANY(%s)"
    args: list = [list(scope.corpus_ids)]
    rows = conn.execute(
        f"""SELECT procedure_id, document_id, corpus_id, title, goal,
                   steps_json, tools_json, confidence, source_chunk_ids
              FROM procedure_artifacts {where}""", args).fetchall()
    scored = []
    for pid, did, cid, title, goal, steps, tools, conf, chunks in rows:
        steps_l = steps if isinstance(steps, list) else json.loads(steps or "[]")
        blob = " ".join([title or "", goal or "", *map(str, steps_l)])
        match = _match_score(blob, terms)
        # candidacy requires an actual term match; confidence only
        # RANKS matches, it never makes an unmatched object a result
        score = round(match + 0.25 * float(conf or 0), 4)
        if match > 0:
            scored.append({
                "object_type": "procedure",
                "object_id": pid,
                "document_id": did,
                "corpus_id": cid,
                "title": title,
                "goal": goal,
                "steps": [{"order": i + 1, "action": str(s)}
                          for i, s in enumerate(steps_l)],
                "tools": tools if isinstance(tools, list) else [],
                "source_chunk_ids": chunks,
                "score": score,
            })
    return sorted(scored, key=lambda r: (-r["score"], r["object_id"]))[:5]


def _concepts(conn, scope: "QueryScope", question: str,
              extra_terms=()) -> list[dict]:
    terms = _merge_terms(question, extra_terms)
    where = "WHERE corpus_id = ANY(%s)"
    args: list = [list(scope.corpus_ids)]
    rows = conn.execute(
        f"""SELECT concept_id, document_id, corpus_id, name, description,
                   domain, confidence, supporting_chunks
              FROM concept_artifacts {where}""", args).fetchall()
    scored = []
    for cid_, did, cid, name, desc, domain, conf, chunks in rows:
        match = _match_score(f"{name} {desc}", terms)
        # candidacy requires an actual term match (confidence ranks,
        # never admits) — without this every stored concept scored > 0
        # for any query via the confidence bonus alone
        score = round(match + 0.2 * float(conf or 0), 4)
        if match > 0:
            scored.append({
                "object_type": "concept",
                "object_id": cid_,
                "document_id": did,
                "corpus_id": cid,
                "name": name,
                "description": desc,
                "domain": domain,
                "supporting_chunks": chunks,
                "score": score,
            })
    return sorted(scored, key=lambda r: (-r["score"], r["object_id"]))[:8]


def _facts(conn, scope: "QueryScope", question: str,
           extra_terms=()) -> list[dict]:
    terms = _merge_terms(question, extra_terms)
    args: list = [list(scope.corpus_ids)]
    where = ("WHERE f.decision='ACCEPT' AND d.corpus_id = ANY(%s)")
    like = [f"%{t}%" for t in terms]
    args = args + [like, like, like]
    rows = conn.execute(
        f"""SELECT DISTINCT f.fact_id, f.predicate, e1.normalized_surface,
                   e2.normalized_surface, ev.doc_id, ev.chunk_id,
                   d.corpus_id
              FROM facts f
              JOIN entities e1 ON e1.entity_id=f.subject_id
              JOIN entities e2 ON e2.entity_id=f.object_id
              JOIN evidence ev ON ev.fact_id::text=f.fact_id
              JOIN documents d ON d.doc_id=ev.doc_id
              {where}
                AND (e1.normalized_surface ILIKE ANY(%s)
                     OR e2.normalized_surface ILIKE ANY(%s)
                     OR f.predicate ILIKE ANY(%s))
              LIMIT 2000""", args).fetchall()
    seen: dict[str, dict] = {}
    for fid, pred, subj, obj, did, chunk, cid in rows:
        blob = f"{subj} {pred} {obj}"
        score = round(_match_score(blob, terms), 4)
        entry = seen.setdefault(fid, {
            "object_type": "fact", "object_id": fid,
            "predicate": pred, "subject": subj, "object": obj,
            "document_id": did, "corpus_id": cid,
            "evidence_chunk_ids": [], "score": 0.0})
        if chunk and chunk not in entry["evidence_chunk_ids"]:
            entry["evidence_chunk_ids"].append(chunk)
        entry["score"] = max(entry["score"], score)
    out = [r for r in seen.values() if r["score"] > 0]
    return sorted(out, key=lambda r: (-r["score"], r["object_id"]))[:8]


def _concept_graph(conn, scope: "QueryScope",
                   names: list[str]) -> list[dict]:
    """RELATED_CONCEPT edges from the vocabulary layer when present.
    Scope never widens: only the resolved corpus set is consulted."""
    if not names or not scope.corpus_ids:
        return []
    rows = conn.execute(
        """SELECT canonical_name, definition FROM concept_families
            WHERE corpus_id = ANY(%s)""" ,
        (list(scope.corpus_ids),)).fetchall()
    out = []
    lowered = {_norm(n) for n in names}
    for canon, definition in rows:
        words = set(_norm(definition or "").split())
        if lowered & words or any(_norm(n) in _norm(definition or "")
                                  for n in names if n):
            out.append({"canonical_concept": canon,
                        "definition": (definition or "")[:200]})
    return out[:6]


# ---------------------------------------------------------------- route

@router.post("/ask")
def ask(req: AskRequest):
    t0 = time.perf_counter()
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(422, "question required")

    with tx() as conn:
        # QUERY-SCOPE-V1: explicit, fail-closed. No scope → typed 422.
        # One canonical resolution path shared with /retrieve, /evidence
        # and /chat (never a second competing scope system).
        from orchestrator.api.retrieve import resolve_http_scope

        scope = resolve_http_scope(conn, req)

        routed = classify_query(question)
        route = routed["route"]

        # CORPUS-MAP-PLANNING-V1: the stored corpus map + vocabulary
        # families become scoped navigation priors. Expansion terms add
        # candidate matches; evidence stays authoritative.
        from polymath_shared.corpus_map_planning import plan_with_corpus_map

        map_plan = plan_with_corpus_map(conn, scope, question)
        extra = map_plan["expansion_terms"]

        procedures = concepts = facts = families = []
        if route == ROUTE_PROCEDURE:
            procedures = _procedures(conn, scope, question, extra)
        elif route == ROUTE_CONCEPT:
            concepts = _concepts(conn, scope, question, extra)
        elif route == ROUTE_FACT:
            facts = _facts(conn, scope, question, extra)
        else:  # POLYMATH
            concepts = _concepts(conn, scope, question, extra)[:6]
            facts = _facts(conn, scope, question, extra)[:6]
            families = _concept_graph(conn, scope,
                                      [c["name"] for c in concepts])

    objects = {
        "procedures": procedures, "concepts": concepts, "facts": facts,
        "related_concepts": families,
    }
    cited_documents = sorted({
        o.get("document_id") for lane in objects.values() for o in lane
        if isinstance(o, dict) and o.get("document_id")})
    grounded = all(
        bool(o.get("document_id") or o.get("source_chunk_ids")
             or o.get("evidence_chunk_ids"))
        for lane in objects.values() for o in lane if isinstance(o, dict))
    return {
        "question": question,
        "router": routed,
        "route": route,
        "objects": objects,
        "cited_document_ids": cited_documents,
        "grounded": grounded,
        "scope": scope.as_dict(),
        "map": map_plan,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        "contracts": {
            "query_router": QUERY_ROUTER_VERSION,
            "grounding": "stored-objects-only-v1",
            "corpus_map_planning": map_plan["contract"],
        },
    }
