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
    return {"admissible": not bridge_errors and not portfolio_errors, "bridge_errors": bridge_errors,
            "portfolio_errors": portfolio_errors, "hypotheses_checked": len(hyps)}


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
