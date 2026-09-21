#!/usr/bin/env python3
"""Domain binding: the ONE door between the Polymath adapter runtime and this engine (DOMAIN_OPERATION, ADR-0020).

The adapter worker runs this file out of process — one JSON request on stdin, one JSON object on stdout — so the engine's flat
module names (`transitions`, `graph`, `store`, `models`, …) never enter the worker's namespace and an engine crash is a typed
step failure, not a dead worker.

    request   {"schema_version": "domain_operation_request.v1", "domain", "operation", "run_id", "step_id",
               "input": {…run input…}, "inputs": {…values the manifest step selected…}, "config": {…step config…}}
    response  {"ok": true,  "output": {…}}                      the step output
              {"ok": false, "code": "UPPER_SNAKE", "message"}   a typed domain refusal (the run stops with this gap code)
    exit != 0 / anything else on stdout                          a crash — the runtime records STEP_EXECUTOR_ERROR

`OPERATIONS` WRAPS existing engine functions. Nothing here re-implements domain logic, reads or writes run state, or touches a
ledger: the runtime owns state, this file only computes. Anything the engine prints goes to stderr, never into the response.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from typing import Any, Callable

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "python"))
#: governed operations never read or write the engine's registry build cache (AUTO_DECISIONS M-009 §4)
os.environ["OPPORTUNITY_RESEARCH_REGISTRY"] = "compile"

REQUEST_VERSION = "domain_operation_request.v1"


class Refusal(Exception):
    """A typed domain refusal: the request is well-formed but the engine declines it."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def _op_validate_bridge(req: dict[str, Any]) -> dict[str, Any]:
    """φ constraining θ: bridge admissibility (evidence boundary, bounded inference hops, a researchable gap) and the portfolio
    diversity law, exactly as `python/bridge.py` enforces them standalone. Inadmissible is an OUTPUT (the run can branch back
    to reasoning), not a refusal."""
    import bridge
    import graph as graphmod

    hyps = (req.get("inputs") or {}).get("hypotheses")
    if not isinstance(hyps, list) or not hyps or not all(isinstance(h, dict) for h in hyps):
        raise Refusal("HYPOTHESES_MISSING", "inputs.hypotheses must be a non-empty list of bridge hypotheses")
    known = (req.get("inputs") or {}).get("known_evidence_ids")
    policies = graphmod.load_policies()
    bridge_errors = bridge.validate_all(hyps, policies, set(known) if isinstance(known, list) else None)
    portfolio_errors = bridge.validate_portfolio(hyps, policies)
    anchor_errors: list[str] = []
    clusters = (req.get("inputs") or {}).get("lived_clusters")
    if isinstance(clusters, list):                 # after admission: a hypothesis names ANCHOR clusters or declares CORPUS_ONLY
        import lived_world
        state = _engine_state(lived_clusters=clusters)
        anchor_errors = lived_world.validate_hypothesis_anchors(hyps, state, policies) + lived_world.validate_portfolio_anchors(hyps, state, policies)
    return {"admissible": not bridge_errors and not portfolio_errors and not anchor_errors, "bridge_errors": bridge_errors,
            "portfolio_errors": portfolio_errors, "anchor_errors": anchor_errors, "hypotheses_checked": len(hyps)}


def _inputs(req: dict[str, Any]) -> dict[str, Any]:
    ins = req.get("inputs")
    return ins if isinstance(ins, dict) else {}


def _engine_state(**data: Any) -> dict[str, Any]:
    """The engine's functions take `(state, policies)` and read / write `state["data"][key]`. A governed operation gets a
    THROWAWAY state holding only what the manifest selected; the keys the function wrote are returned as the step output."""
    return {"data": {k: v for k, v in data.items() if v is not None}}


def _corpus_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    if not rows or not all(isinstance(r, dict) and r.get("id") for r in rows):
        raise Refusal("CORPUS_EVIDENCE_MISSING", "inputs.corpus_evidence must be the non-empty row list `knowledge.corpus_evidence` produced")
    return rows


def _op_corpus_evidence(req: dict[str, Any]) -> dict[str, Any]:
    """Governed knowledge rows (the adapter runtime's evidence-boundary output: chunk id, text, utility role, CA4 grade, origin)
    become the engine's corpus rows through the engine's OWN EvidencePacket mapping (`corpus_polymath.rows_from_packet`) — the
    one place a row gets its `polymath:chunk:<id>` identity, its authority hints and its role / grade tags. No HTTP here: the
    runtime already retrieved. `row_sets` is a list of row lists (one per knowledge step); the first occurrence of an id wins."""
    import corpus_polymath as cp

    sets = _inputs(req).get("row_sets")
    if not isinstance(sets, list) or not any(isinstance(s, list) and s for s in sets):
        raise Refusal("KNOWLEDGE_ROWS_MISSING", "inputs.row_sets must hold at least one non-empty list of governed evidence rows")
    by_corpus: dict[str, list[dict[str, Any]]] = {}
    skipped = 0
    for rows in sets:
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict) or r.get("kind", "chunk") != "chunk" or not r.get("id") or not str(r.get("text") or "").strip() or not r.get("corpus_id"):
                skipped += 1                    # graph facts / rows without text or corpus carry nothing the engine can cite
                continue
            by_corpus.setdefault(str(r["corpus_id"]), []).append(
                {"chunk_id": r["id"], "text": r["text"], "source": r.get("source"), "document_id": r.get("doc_id"),
                 "utility_role": r.get("utility_role"), "synthesis_role": r.get("synthesis_role"), "ca4_grade": r.get("ca4_grade"),
                 "c4_valid": r.get("c4_valid"), "origin": r.get("origin"), "query_ids": r.get("query_ids") or [],
                 "text_truncated": r.get("text_truncated"), "text_chars": r.get("text_chars"),
                 "provenance": {"relation_to_q0": r["relation_to_q0"]} if r.get("relation_to_q0") else {}})
    out, seen = [], set()
    for corpus, items in by_corpus.items():
        for row in cp.rows_from_packet({"evidence": items}, corpus):
            # ONE id space in governed mode: the adapter runtime's evidence id (what `context.evidence_refs` shows the agent and
            # what Polymath's citation check enforces). The standalone `polymath:chunk:` prefix is dropped at this boundary.
            row["id"] = row["id"].split("polymath:chunk:", 1)[-1]
            if row["id"] not in seen:
                seen.add(row["id"])
                out.append(row)
    if not out:
        raise Refusal("KNOWLEDGE_ROWS_UNUSABLE", f"none of the {skipped} governed rows carries a chunk id, text and corpus")
    return {"corpus_evidence": out, "row_count": len(out), "skipped": skipped, "corpora": sorted(by_corpus)}


def _op_lenses(req: dict[str, Any]) -> dict[str, Any]:
    """`executors.lens_gate`: the lenses whose keywords appear in the seed signal + corpus evidence (never lens-less)."""
    import executors
    import graph as graphmod

    ins = _inputs(req)
    signal = str(ins.get("signal") or "").strip()
    if not signal:
        raise Refusal("SIGNAL_MISSING", "inputs.signal must be the seed / niche signal text")
    state = _engine_state(signal=signal, corpus_evidence=_corpus_rows(ins.get("corpus_evidence")))
    note = executors.lens_gate(state, graphmod.load_policies())
    return {"lenses": state["data"]["lenses"], "note": note}


def _op_validate_primitives(req: dict[str, Any]) -> dict[str, Any]:
    """The lineage law on a primitives submission (`lived_world.validate_primitives`, the same function the controller's submit
    path calls): interpretation objects are schema-valid and cite only corpus rows that exist, are CLASSIFIED and are not
    IRRELEVANT. Invalid is an OUTPUT (the run can branch back to reasoning), not a refusal."""
    import graph as graphmod
    import lived_world

    ins = _inputs(req)
    prim = ins.get("primitives")
    if not isinstance(prim, dict):
        raise Refusal("PRIMITIVES_MISSING", "inputs.primitives must be the primitives object")
    state = _engine_state(corpus_evidence=_corpus_rows(ins.get("corpus_evidence")), row_relevance=ins.get("row_relevance"))
    errors = lived_world.validate_primitives(prim, state, graphmod.load_policies())
    out: dict[str, Any] = {"valid": not errors, "errors": errors}
    if not errors:
        lived_world.merge_relevance(state, prim.get("row_relevance") or {})
        out.update(row_relevance=state["data"]["row_relevance"], latent_structures=list(prim.get("latent_structures") or []),
                   corpus_observations=list(prim.get("corpus_observations") or []))
    return out


def _op_population_nominate(req: dict[str, Any]) -> dict[str, Any]:
    """`lived_world.nominate` + VOI ranking: populations worth looking at, from the seed signal, the populations and latent
    structures the agent read out of the knowledge, registry situations and prior field rows — each with its compiled channel
    queries. Leads are places to look, never demand. The engine's `queue` (status mutation + wall-clock stamps) is NOT used:
    the batch is the top `batch_size` eligible leads in VOI order, a pure function of the inputs."""
    import graph as graphmod
    import lived_world

    ins = _inputs(req)
    signal = str(ins.get("signal") or "").strip()
    prim = ins.get("primitives")
    if not signal or not isinstance(prim, dict):
        raise Refusal("POPULATION_INPUT_MISSING", "inputs.signal and inputs.primitives are required")
    policies = graphmod.load_policies()
    state = _engine_state(signal=signal, primitives=prim, communities=ins.get("communities") or prim.get("communities") or [],
                          latent_structures=ins.get("latent_structures") or prim.get("latent_structures") or [],
                          corpus_evidence=ins.get("corpus_evidence") or [], population_leads=list(ins.get("population_leads") or []),
                          community_leads=list(ins.get("community_leads") or []))
    note = lived_world.nominate(state, policies)
    ranked = lived_world.rank_leads(state, policies)
    if not ranked:
        raise Refusal("POPULATION_NOT_FOUND", "no population could be nominated from the signal, the primitives, the registry or prior field rows")
    batch = lived_world.eligible_leads(state, policies)[: int((policies.get("lived_world") or {}).get("batch_size", 4))]
    d = state["data"]
    return {"population_leads": d.get("population_leads") or [], "community_leads": d.get("community_leads") or [], "ranked_lead_ids": ranked,
            "batch": batch, "communities": d.get("communities") or [], "note": note}


_CONTEXT_FIELD = r"(?:^|·|\||;|\n)\s*{key}\s*:\s*([^·|;\n]+)"


def _context_field(context: str, key: str) -> str | None:
    """The engine's receipt builder writes `community: … · activity: … · moment: …` into an observation's free-text context; any
    host may. Read it back tolerantly; absent stays absent."""
    import re
    m = re.search(_CONTEXT_FIELD.format(key=key), context or "", re.I)
    return m.group(1).strip() or None if m else None


def _field_records_from_admissions(ins: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """ADMITTED observations -> the engine's field records (AUTO_DECISIONS M-009 §3). Only what TrailSignal admitted exists here.
    The record id is the admitted-evidence id (the `field_evidence` id the agent can cite — one id space). TrailSignal's
    independence group, freshness, role and polarity are taken AS GIVEN. A receipt carries no author (privacy by design), so the
    source URL stands in for author and thread — the engine's own legacy identity rule."""
    from urllib.parse import urlparse

    import adapter_receipt

    engine_role = {}
    for skill_role, trail_role in adapter_receipt.ROLE_MAP.items():
        engine_role.setdefault(trail_role, skill_role)               # first declared skill role per TrailSignal role
    obs, sources = {}, {}
    for rec in ins.get("receipts") or []:
        if isinstance(rec, dict):
            obs.update({o.get("observation_id"): o for o in rec.get("observations") or [] if isinstance(o, dict)})
            sources.update({s.get("source_id"): s for s in rec.get("sources") or [] if isinstance(s, dict)})
    hyps = {h.get("hypothesis_id"): h for h in ins.get("hypotheses") or [] if isinstance(h, dict)}
    out, stats = [], {"admitted": 0, "without_observation": 0, "without_community": 0}
    for adm in ins.get("admissions") or []:
        for a in (adm or {}).get("admitted") or []:
            stats["admitted"] += 1
            o = obs.get(a.get("observation_id"))
            if not o:
                stats["without_observation"] += 1
                continue
            src = sources.get(o.get("source_id")) or {}
            host = (urlparse(str(src.get("url") or "")).hostname or "").removeprefix("www.") or str(a.get("source_class") or "?")
            community = _context_field(str(o.get("context") or ""), "community")
            if not community:
                stats["without_community"] += 1
            linked = [hyps[h] for h in a.get("hypothesis_ids") or [] if h in hyps]
            role = engine_role.get(a.get("evidence_role"))
            excerpt = str(o.get("paraphrase_or_excerpt") or "")
            out.append({"id": a["admitted_evidence_id"], "observation_id": a.get("observation_id"), "source": src.get("url") or o.get("source_id"),
                        "source_identity": {"platform": host.split(".")[0] if "." in host else host, "thread_key": src.get("url") or o.get("source_id")},
                        "community": community or host, "friction_family": next((str(h["suspected_friction"]) for h in linked if h.get("suspected_friction")), "unassigned"),
                        "evidence_roles": [role] if role else [], "problem": str(o.get("claim") or "")[:300], "quote_ref": excerpt[:300],
                        "workaround": excerpt[:200] if a.get("evidence_role") == "workaround" else "", "moment": _context_field(str(o.get("context") or ""), "moment"),
                        "freshness": {"class": a.get("freshness")}, "independence_group": a.get("independence_group"),
                        "hypothesis_ids": list(a.get("hypothesis_ids") or []), "contradicts": a.get("polarity") == "contradicting",
                        "lead_id": _context_field(str(o.get("context") or ""), "lead")})
    return out, stats


def _op_evidence_cards(req: dict[str, Any]) -> dict[str, Any]:
    """`lived_world.cards` over ADMITTED field evidence: participant cards, lived clusters (community × friction family) and each
    cluster's ANCHOR / THIN authority against the policy threshold — with TrailSignal's independence groups as the voice count."""
    import graph as graphmod
    import lived_world

    ins = _inputs(req)
    records, stats = _field_records_from_admissions(ins)
    if not records:
        raise Refusal("ADMITTED_EVIDENCE_MISSING", f"no admitted observation could be joined to a receipt ({stats})")
    state = _engine_state(field_records=records, population_leads=list(ins.get("population_leads") or []), community_leads=list(ins.get("community_leads") or []))
    note = lived_world.cards(state, graphmod.load_policies())
    d = state["data"]
    return {"field_records": records, "participant_cards": d["participant_cards"], "lived_clusters": d["lived_clusters"], "joined": stats, "note": note,
            "anchors": [c["id"] for c in d["lived_clusters"] if c["authority"] == "ANCHOR"]}


def _op_validate_situations(req: dict[str, Any]) -> dict[str, Any]:
    """`lived_world.validate_situations`: a FIELD_ANCHORED situation needs an ANCHOR cluster and cited field records; a
    RECONSTRUCTED one lists its unknowns; a situation on a cluster is never SIMULATED. Invalid is an OUTPUT."""
    import graph as graphmod
    import lived_world
    import models

    ins = _inputs(req)
    items = ins.get("lived_situations")
    if not isinstance(items, list) or not items:
        raise Refusal("LIVED_SITUATIONS_MISSING", "inputs.lived_situations must be a non-empty list")
    state = _engine_state(lived_clusters=ins.get("lived_clusters") or [], field_records=ins.get("field_records") or [])
    errors = [f"lived_situations[{i}]: {e}" for i, x in enumerate(items) for e in models.validate(x, "lived_situation")]
    errors += lived_world.validate_situations(items, state, graphmod.load_policies())
    return {"valid": not errors, "errors": errors, "situations_checked": len(items)}


def _op_corpus_questions(req: dict[str, Any]) -> dict[str, Any]:
    """`lived_world.compile_corpus_questions`: what to ask the knowledge base, at friction / mechanism level, from the lived
    clusters (ANCHOR first) — never a hypothesis statement, never a person."""
    import graph as graphmod
    import lived_world

    ins = _inputs(req)
    state = _engine_state(lived_clusters=ins.get("lived_clusters") or [], field_records=ins.get("field_records") or [])
    if not state["data"].get("lived_clusters"):
        raise Refusal("LIVED_CLUSTERS_MISSING", "inputs.lived_clusters must be the clusters `population.evidence_cards` produced")
    note = lived_world.compile_corpus_questions(state, graphmod.load_policies())
    qs = state["data"]["corpus_questions"]
    return {"corpus_questions": qs, "need": " ".join(q["question"] for q in qs)[:2000], "note": note}


_DIRECTIVE_GOVERNANCE = ("objective", "hypothesis_ids", "evidence_gaps", "preferred_source_roles", "disallowed_source_roles", "freshness_requirement",
                         "geography", "language", "minimum_independent_sources", "success_condition", "falsification_condition", "budget")


def _op_research_plan(req: dict[str, Any]) -> dict[str, Any]:
    """Trail says WHAT, the engine says HOW. Input: the `research_directive` TrailSignal compiled (gaps, intents, roles, freshness,
    budget). Output: the SAME directive — every governance field untouched, every Trail intent kept first and in order — plus
    channel-specific intents compiled by `executors.channel_queries` from the evidence gaps (else the live hypothesis statements)
    and from the top population leads. A channel serves an intent only when the evidence roles it can yield (mapped by the ONE
    static `adapter_receipt.ROLE_MAP`) overlap the roles Trail asked for. Total intents stay within the directive's query budget;
    what did not fit is counted, never silently dropped."""
    import copy

    import adapter_receipt
    import executors
    import graph as graphmod

    ins = _inputs(req)
    directive = ins.get("research_directive")
    if not isinstance(directive, dict) or not directive.get("search_intents"):
        raise Refusal("RESEARCH_DIRECTIVE_MISSING", "inputs.research_directive must be the directive TrailSignal compiled (with search_intents)")
    policies = graphmod.load_policies()
    out = copy.deepcopy(directive)
    trail_intents = [i for i in out["search_intents"] if isinstance(i, dict)]
    asked = sorted({r for i in trail_intents for r in i.get("evidence_roles") or []})
    cap = max(len(trail_intents), min(100, int((directive.get("budget") or {}).get("max_queries") or 24)))
    state = _engine_state(communities=ins.get("communities") or [])

    subjects = [("gap", g.get("gap_id"), str(g.get("question") or "")) for g in directive.get("evidence_gaps") or [] if isinstance(g, dict) and g.get("question")]
    if not subjects:
        subjects = [("hyp", h.get("hypothesis_id"), str(h.get("statement") or "")) for h in ins.get("hypotheses") or [] if isinstance(h, dict) and h.get("statement")]
    compiled: list[list[dict[str, Any]]] = [executors.channel_queries(str(sid), text, state, policies) for _, sid, text in subjects]
    leads = {l.get("id"): l for l in ins.get("leads") or [] if isinstance(l, dict)}
    for lid in ins.get("batch") or []:
        if leads.get(lid, {}).get("channel_queries"):
            compiled.append([dict(q, _lead=True) for q in leads[lid]["channel_queries"]])

    def _host(q: dict[str, Any]) -> dict[str, Any] | None:
        roles = sorted({adapter_receipt.ROLE_MAP.get(r) for r in q.get("expected_evidence_roles") or []} - {None})
        for ti in trail_intents:                                    # the first Trail intent this channel can serve
            served = [r for r in roles if r in (ti.get("evidence_roles") or [])]
            if served:
                return {"intent_id": f"{ti['intent_id']}~{q['channel']}~{q['gap_id']}"[:200], "evidence_goal": ti["evidence_goal"], "evidence_roles": served,
                        "intent": f"{q['channel']}: {q.get('why_this_source')} — {q.get('query')}"[:500], "template": str((q.get("tools") or [q.get("query")])[0])[:500]}
        return None

    added, dropped, unserved, seen = [], 0, 0, {i.get("intent_id") for i in trail_intents}
    for rank in range(max((len(c) for c in compiled), default=0)):   # round-robin: every subject gets its best channel before any gets its second
        for qs in compiled:
            if rank >= len(qs):
                continue
            intent = _host(qs[rank])
            if intent is None:
                unserved += 1
            elif intent["intent_id"] in seen:
                continue
            elif len(trail_intents) + len(added) >= cap:
                dropped += 1
            else:
                seen.add(intent["intent_id"])
                added.append(intent)
    out["search_intents"] = trail_intents + added
    return {"research_directive": out, "planned": {"trail_intents": len(trail_intents), "channel_intents": len(added), "subjects": len(subjects),
                                                   "lead_batches": len(compiled) - len(subjects), "dropped_over_budget": dropped,
                                                   "channel_cannot_serve_roles": unserved, "roles_asked": asked, "intent_cap": cap},
            "governance_unchanged": all(out.get(k) == directive.get(k) for k in _DIRECTIVE_GOVERNANCE)}


#: operation id -> wrapper. One table; an id not listed here is a typed refusal.
OPERATIONS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "knowledge.corpus_evidence": _op_corpus_evidence,
    "understanding.lenses": _op_lenses,
    "understanding.validate_primitives": _op_validate_primitives,
    "population.nominate": _op_population_nominate,
    "population.evidence_cards": _op_evidence_cards,
    "population.validate_situations": _op_validate_situations,
    "knowledge.corpus_questions": _op_corpus_questions,
    "hypotheses.validate_bridge": _op_validate_bridge,
    "research.plan": _op_research_plan,
}


def handle(req: Any) -> dict[str, Any]:
    if not isinstance(req, dict) or req.get("schema_version") != REQUEST_VERSION:
        return {"ok": False, "code": "DOMAIN_REQUEST_INVALID", "message": f"expected a {REQUEST_VERSION} object"}
    op = OPERATIONS.get(str(req.get("operation")))
    if op is None:
        return {"ok": False, "code": "DOMAIN_OPERATION_UNKNOWN", "message": f"{req.get('operation')!r} is not an operation of this domain"}
    try:
        with contextlib.redirect_stdout(sys.stderr):
            output = op(req)
    except Refusal as exc:
        return {"ok": False, "code": exc.code, "message": exc.message}
    return {"ok": True, "output": output}


def main() -> int:
    try:
        req = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "code": "DOMAIN_REQUEST_INVALID", "message": f"request is not JSON: {exc}"}))
        return 0
    print(json.dumps(handle(req), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
