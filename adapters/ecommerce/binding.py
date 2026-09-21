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
#: Registry source for population priors (AUTO_DECISIONS M-014). The engine's mirror is a STRICT SUPERSET of TrailSignal's tables: it defines ten
#: friction families that 236 of TrailSignal's own seed rows reference but TrailSignal's friction_library never defines, so TrailSignal's data alone
#: fails this engine's fail-closed compiler. Until the owner decides whether those rows go upstream, governed nomination reads the mirror and SAYS so
#: in its output; TrailSignal's registry stays the only GOVERNANCE registry (admission, judgement, qualification, score).
REGISTRY_SOURCE = "adapters/ecommerce/registry/trailsignal (engine mirror; superset of governance/trail/data — M-014)"
os.environ.pop("OPPORTUNITY_RESEARCH_REGISTRY_SRC", None)

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

    hyps = _ledger_hypotheses(req.get("inputs") or {})
    if not hyps:
        raise Refusal("HYPOTHESES_MISSING", "inputs.hypotheses must be a non-empty list of bridge hypotheses")
    ins = req.get("inputs") or {}
    known_rows = [r.get("id") for key in ("corpus_evidence", "field_records") for r in ins.get(key) or [] if isinstance(r, dict) and r.get("id")]
    known = set(known_rows) | set(ins.get("known_evidence_ids") or []) if (known_rows or isinstance(ins.get("known_evidence_ids"), list)) else None
    policies = graphmod.load_policies()
    bridge_errors = bridge.validate_all(hyps, policies, known)
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


#: a mechanism / concept may build on a hypothesis only while the ledger holds it in one of these states (TrailSignal's φ pressure
#: moves hypotheses between states; the domain never does). `weakened`, `contradicted`, `filtered`, `killed`, `merged` are not eligible.
ELIGIBLE_HYPOTHESIS_STATUSES = frozenset({"proposed", "retained", "revised", "split", "strengthened", "promoted"})


def _ledger_hypotheses(ins: dict[str, Any], key: str = "hypotheses") -> list[dict[str, Any]]:
    """A θ step's stored output keeps the agent's proposals (`hypotheses`) and, in parallel, the ledger ids the runtime minted
    (`hypothesis_ids`). The domain's extra fields (bridge path, evidence boundary, suspected friction, …) ride in the proposal; the
    ledger stays the only hypothesis STATE. Zip them so every domain hypothesis is addressed by its ledger id."""
    props = [dict(h) for h in ins.get(key) or [] if isinstance(h, dict)]
    ids = ins.get("hypothesis_ids")
    if isinstance(ids, list) and len(ids) == len(props):
        for h, hid in zip(props, ids):
            h["hypothesis_id"] = hid
    for h in props:
        if h.get("hypothesis_id"):
            h["id"] = h["hypothesis_id"]                  # one address for a hypothesis: its LEDGER id
    return props


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
    import registry as _registry
    snap = _registry.load_snapshot() or {}
    return {"population_leads": d.get("population_leads") or [], "community_leads": d.get("community_leads") or [], "ranked_lead_ids": ranked,
            "batch": batch, "communities": d.get("communities") or [], "note": note,
            "registry": {"source": REGISTRY_SOURCE, "build_id": snap.get("build_id"), "seeds": len(snap.get("seeds") or []), "friction_families": len(snap.get("friction_families") or {})}}


_CONTEXT_FIELD = r"(?:^|·|\||;|\n)\s*{key}\s*:\s*([^·|;\n]+)"


def _context_field(context: str, key: str) -> str | None:
    """The engine's receipt builder writes `community: … · activity: … · moment: …` into an observation's free-text context; any
    host may. Read it back tolerantly; absent stays absent."""
    import re
    m = re.search(_CONTEXT_FIELD.format(key=key), context or "", re.I)
    return m.group(1).strip() or None if m else None


def _intent_lineage(context: str) -> dict[str, Any]:
    """`intent: <search_intent_id>` in an observation's context -> {intent_id, gap_id}. A channel intent id ends with the gap it serves
    (`q-complaint:reddit:gap_a5423927_0`, `…:falsify_a5423927`); a bound TrailSignal template ends with the hypothesis id prefix."""
    intent = _context_field(context, "intent")
    if not intent:
        return {"intent_id": None, "gap_id": None}
    tail = intent.rsplit(":", 1)[-1]
    return {"intent_id": intent, "gap_id": tail if tail.startswith(("gap", "falsify")) else None}


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
    hyps = {h.get("hypothesis_id"): h for h in _ledger_hypotheses(ins)}
    # the CURRENT ledger state (the runtime's query projection) overrides the generation-time proposal: a REVISE moves the friction,
    # and a SPLIT child never existed in `C_hypotheses` — without this both clustered as `unassigned` (restoration reference §9.6)
    for v in ins.get("semantics") or []:
        if isinstance(v, dict) and v.get("hypothesis_id"):
            hyps[v["hypothesis_id"]] = {**hyps.get(v["hypothesis_id"], {}), **{k: v[k] for k in ("population", "activity", "task", "suspected_friction") if v.get(k)}}
    lead_names = {str(l.get("id")): str(l.get("name")) for key in ("population_leads", "community_leads") for l in ins.get(key) or [] if isinstance(l, dict) and l.get("id") and l.get("name")}
    out, stats = [], {"admitted": 0, "without_observation": 0, "without_community": 0}
    basis = {"lead": 0, "population": 0, "host": 0}                # how a record without a stated community got one
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
            linked = [hyps[h] for h in a.get("hypothesis_ids") or [] if h in hyps]
            if not community:
                # WHO this record is about, in the order the run knows it: the lead the harness researched, else the population of the
                # hypothesis it is linked to. The source HOST is a last resort and is said to be one — a host is a place, not a community
                stats["without_community"] += 1
                lead_name = lead_names.get(_context_field(str(o.get("context") or ""), "lead"))
                population = next((str(h["population"]) for h in linked if h.get("population")), "")
                community = lead_name or population
                basis["lead" if lead_name else "population" if population else "host"] += 1
            role = engine_role.get(a.get("evidence_role"))
            excerpt = str(o.get("paraphrase_or_excerpt") or "")
            out.append({"id": a["admitted_evidence_id"], "observation_id": a.get("observation_id"), "source": src.get("url") or o.get("source_id"),
                        "source_identity": {"platform": host.split(".")[0] if "." in host else host, "thread_key": src.get("url") or o.get("source_id")},
                        "community": community or host, "friction_family": next((str(h["suspected_friction"]) for h in linked if h.get("suspected_friction")), "unassigned"),
                        "evidence_roles": [role] if role else [], "problem": str(o.get("claim") or "")[:300], "quote_ref": excerpt[:300],
                        # the workaround is WHAT THE PERSON DOES (the claim); the excerpt is their quote and already rides in `quote_ref`
                        "workaround": str(o.get("claim") or "")[:200] if a.get("evidence_role") == "workaround" else "", "moment": _context_field(str(o.get("context") or ""), "moment"),
                        "freshness": {"class": a.get("freshness")}, "independence_group": a.get("independence_group"),
                        "hypothesis_ids": list(a.get("hypothesis_ids") or []), "contradicts": a.get("polarity") == "contradicting",
                        "lead_id": _context_field(str(o.get("context") or ""), "lead"),
                        # PROVENANCE HOOK: which compiled intent found this observation — and through the intent id, which gap of which
                        # hypothesis it answers. The receipt's tool_trace counts queries per intent but never says which observation
                        # came from which; without this tag that link is unrecoverable after the run.
                        **_intent_lineage(str(o.get("context") or ""))})
    return out, {**stats, "_community_basis": basis}


def _op_evidence_cards(req: dict[str, Any]) -> dict[str, Any]:
    """`lived_world.cards` over ADMITTED field evidence: participant cards, lived clusters (community × friction family) and each
    cluster's ANCHOR / THIN authority against the policy threshold — with TrailSignal's independence groups as the voice count."""
    import graph as graphmod
    import lived_world

    ins = _inputs(req)
    records, stats = _field_records_from_admissions(ins)
    community_basis = stats.pop("_community_basis")                # `joined` keeps its three counters; the basis is its own output key
    seen = {r["id"] for r in records}
    records = [r for r in ins.get("prior_field_records") or [] if isinstance(r, dict) and r.get("id") not in seen] + records      # research rounds accumulate
    rounds = int(ins.get("prior_round") or 0) + 1
    if not records:                                      # nothing admitted is a STATE TrailSignal still judges — never a dead run
        return {"field_records": [], "participant_cards": [], "lived_clusters": [], "anchors": [], "joined": stats, "round": rounds,
                "community_basis": community_basis, "note": "no admitted field evidence — no card, no cluster, nothing to anchor on"}
    state = _engine_state(field_records=records, population_leads=list(ins.get("population_leads") or []), community_leads=list(ins.get("community_leads") or []))
    note = lived_world.cards(state, graphmod.load_policies())
    d = state["data"]
    return {"field_records": records, "participant_cards": d["participant_cards"], "lived_clusters": d["lived_clusters"], "joined": stats, "note": note, "round": rounds,
            "community_basis": community_basis, "anchors": [c["id"] for c in d["lived_clusters"] if c["authority"] == "ANCHOR"]}


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
    if not state["data"].get("lived_clusters"):           # no cluster, no field-grounded question: the knowledge step falls back to its seed need
        return {"corpus_questions": [], "need": "", "note": "no lived cluster — no field-grounded corpus question"}
    note = lived_world.compile_corpus_questions(state, graphmod.load_policies())
    qs = state["data"]["corpus_questions"]
    return {"corpus_questions": qs, "need": " ".join(q["question"] for q in qs)[:2000], "note": note}


def _round_robin(per_subject: list[list[dict[str, Any] | None]], seen: set, room: int) -> tuple[list[dict[str, Any]], int, int]:
    """Every subject gets its first proposal before any gets its second. Returns (added, dropped_over_budget, unhostable)."""
    added, dropped, unserved = [], 0, 0
    for rank in range(max((len(c) for c in per_subject), default=0)):
        for props in per_subject:
            if rank >= len(props):
                continue
            intent = props[rank]
            if intent is None:
                unserved += 1
            elif intent["intent_id"] in seen:
                continue
            elif len(added) >= room:
                dropped += 1
            else:
                seen.add(intent["intent_id"])
                added.append(intent)
    return added, dropped, unserved


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
    views = {v.get("hypothesis_id"): v for v in ins.get("semantics") or [] if isinstance(v, dict) and v.get("hypothesis_id")}
    if views:
        return _semantic_research_plan(ins, directive, out, trail_intents, asked, cap, state, policies, views)
    compiled: list[list[dict[str, Any]]] = [executors.channel_queries(str(sid), text, state, policies) for _, sid, text in subjects]
    leads = {l.get("id"): l for key in ("leads", "population_leads", "community_leads") for l in ins.get(key) or [] if isinstance(l, dict)}
    for lid in ins.get("batch") or []:
        if leads.get(lid, {}).get("channel_queries"):
            compiled.append([dict(q, _lead=True) for q in leads[lid]["channel_queries"]])

    def _host(q: dict[str, Any]) -> dict[str, Any] | None:
        roles = sorted({adapter_receipt.ROLE_MAP.get(r) for r in q.get("expected_evidence_roles") or []} - {None})
        for ti in trail_intents:                                    # the first Trail intent this channel can serve
            served = [r for r in roles if r in (ti.get("evidence_roles") or [])]
            if served:
                return {"intent_id": f"{ti['intent_id']}:{q['channel']}:{q['gap_id']}"[:200], "evidence_goal": ti["evidence_goal"], "evidence_roles": served,
                        "intent": f"{q['channel']}: {q.get('why_this_source')} — {q.get('query')}"[:500], "template": str((q.get("tools") or [q.get("query")])[0])[:500]}
        return None

    added, dropped, unserved = _round_robin([[_host(q) for q in qs] for qs in compiled], {i.get("intent_id") for i in trail_intents}, cap - len(trail_intents))
    out["search_intents"] = trail_intents + added
    return {"research_directive": out, "planned": {"trail_intents": len(trail_intents), "channel_intents": len(added), "subjects": len(subjects),
                                                   "lead_batches": len(compiled) - len(subjects), "dropped_over_budget": dropped,
                                                   "channel_cannot_serve_roles": unserved, "roles_asked": asked, "intent_cap": cap},
            "governance_unchanged": all(out.get(k) == directive.get(k) for k in _DIRECTIVE_GOVERNANCE)}


def _semantic_research_plan(ins, directive, out, trail_intents, asked, cap, state, policies, views) -> dict[str, Any]:
    """The governed path once the runtime supplies `semantics` (the per-hypothesis query projection) — restoration reference §9:
      * every evidence gap is compiled THROUGH ITS OWN hypothesis: H1's gap -> H1's vocabulary -> an intent that carries H1's id;
      * a gate gap TrailSignal wrote ("corroborate from a second independent source") is served by that hypothesis's vocabulary —
        its governance text is never the search string (`research_gaps[].origin` says which gaps a reasoning step wrote);
      * TrailSignal's stage templates are BOUND per hypothesis (`{activity} {task} annoying` -> "landscape photography reach spare
        batteries annoying"); a template a hypothesis cannot bind is reported in `unresolved_slots`, never sent with a `{slot}`;
      * one falsifier search per hypothesis. Governance fields, budget and role routing are TrailSignal's, untouched."""
    import adapter_receipt
    import executors
    import query_semantics as QS

    origin = {g.get("gap_id"): g.get("origin") for key in ("knowledge_gaps", "open_gaps") for g in (ins.get("research_gaps") or {}).get(key) or [] if isinstance(g, dict)}
    statements = {h.get("hypothesis_id"): str(h.get("statement") or "") for h in ins.get("hypotheses") or [] if isinstance(h, dict)}
    index: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    bound: list[dict[str, Any]] = []
    for ti in trail_intents:
        if not QS.has_unbound_slot(ti.get("template")):
            bound.append(ti)
            continue
        for hid, view in views.items():
            text, missing = QS.bind_template(str(ti.get("template") or ""), view)
            if text is None:
                unresolved.append({"intent_id": ti.get("intent_id"), "hypothesis_id": hid, "missing_slots": missing})
                continue
            iid = f"{ti['intent_id']}:{str(hid)[4:12]}"[:200]
            bound.append({**ti, "intent_id": iid, "intent": f"{ti.get('intent')} — {text}"[:500], "template": text[:500]})
            index.append({"intent_id": iid, "hypothesis_id": hid, "gap_id": None, "origin": "trail_template", "query": text})

    compiled: list[list[dict[str, Any]]] = []
    meta: dict[str, dict[str, Any]] = {}
    for g in directive.get("evidence_gaps") or []:
        if not (isinstance(g, dict) and g.get("gap_id") and g.get("hypothesis_id")):
            continue
        hid, gid = g["hypothesis_id"], str(g["gap_id"])
        q = QS.gap_query(g, views.get(hid), origin=origin.get(gid), statement=statements.get(hid, ""))
        if not q["query"]:
            unresolved.append({"gap_id": gid, "hypothesis_id": hid, "missing_slots": ["semantic_state"]})
            continue
        meta[gid] = {"hypothesis_id": hid, "gap_id": gid, "origin": origin.get(gid) or "unknown", "query": q["query"], "basis": q["basis"]}
        compiled.append(executors.channel_queries(gid, str(g.get("question") or ""), state, policies, short=q["query"]))
    for hid, view in views.items():
        f = QS.falsifier_query(view)
        if f["query"]:
            gid = f"falsify_{str(hid)[4:12]}"
            meta[gid] = {"hypothesis_id": hid, "gap_id": gid, "origin": "falsifier", "query": f["query"], "basis": f["basis"]}
            compiled.append(executors.channel_queries(gid, f["falsifier"], state, policies, short=f["query"]))
    n_subjects = len(compiled)
    leads = {l.get("id"): l for key in ("leads", "population_leads", "community_leads") for l in ins.get(key) or [] if isinstance(l, dict)}
    for lid in ins.get("batch") or []:
        if leads.get(lid, {}).get("channel_queries"):
            compiled.append([dict(q, _lead=True) for q in leads[lid]["channel_queries"]])

    def _host(q: dict[str, Any]) -> dict[str, Any] | None:
        roles = sorted({adapter_receipt.ROLE_MAP.get(r) for r in q.get("expected_evidence_roles") or []} - {None})
        for ti in trail_intents:                                    # the first Trail intent this channel can serve
            served = [r for r in roles if r in (ti.get("evidence_roles") or [])]
            if served:
                return {"intent_id": f"{ti['intent_id']}:{q['channel']}:{q['gap_id']}"[:200], "evidence_goal": ti["evidence_goal"], "evidence_roles": served,
                        "intent": f"{q['channel']}: {q.get('why_this_source')} — {q.get('query')}"[:500], "template": str((q.get("tools") or [q.get("query")])[0])[:500]}
        return None

    cap = max(len(bound), cap)
    added, dropped, unserved = _round_robin([[_host(q) for q in qs] for qs in compiled], {i.get("intent_id") for i in bound}, cap - len(bound))
    for a in added:
        gid = a["intent_id"].rsplit(":", 1)[-1]
        if gid in meta:
            index.append({"intent_id": a["intent_id"], **meta[gid]})
    out["search_intents"] = bound + added
    if not out["search_intents"]:
        raise Refusal("RESEARCH_PLAN_UNBOUND", "no search intent could be bound from the hypotheses' semantic state: " + json.dumps(unresolved)[:600])
    leaked = [i["intent_id"] for i in out["search_intents"] if QS.has_unbound_slot(i.get("template")) or QS.has_unbound_slot(i.get("intent"))]
    if leaked:
        raise Refusal("RESEARCH_PLAN_UNBOUND_SLOT", f"an intent still carries an unbound slot: {leaked[:5]}")
    return {"research_directive": out,
            "planned": {"trail_intents": len(trail_intents), "bound_trail_intents": len(bound), "channel_intents": len(added), "subjects": n_subjects,
                        "lead_batches": len(compiled) - n_subjects, "dropped_over_budget": dropped, "channel_cannot_serve_roles": unserved,
                        "roles_asked": asked, "intent_cap": cap, "unresolved_slots": unresolved[:100], "compiler": "semantic.v1",
                        "refused_gaps": list((ins.get("research_gaps") or {}).get("refused") or [])[:50]},
            "intent_index": index[:200],
            "governance_unchanged": all(out.get(k) == directive.get(k) for k in _DIRECTIVE_GOVERNANCE)}


def _mechanisms(ins: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Mechanisms as the domain needs them, with `status` DERIVED from the ledger — never claimed by the agent: SUPPORTED only while
    the hypothesis a mechanism builds on is in an eligible ledger state."""
    status = {h.get("hypothesis_id"): h.get("status") for h in ins.get("live_hypotheses") or [] if isinstance(h, dict)}
    out, notes = [], []
    for i, m in enumerate(ins.get("mechanisms") or []):
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id") or m.get("mechanism_id") or f"mech_{i + 1}")
        st = status.get(m.get("hypothesis_id"))
        ok = st in ELIGIBLE_HYPOTHESIS_STATUSES
        if not ok:
            notes.append(f"{mid}: hypothesis {m.get('hypothesis_id')!r} is {st or 'not live'} in the ledger — not eligible")
        out.append({**m, "id": mid, "name": str(m.get("name") or m.get("mechanism") or mid), "status": "SUPPORTED" if ok else "UNSUPPORTED",
                    "supporting_observation_ids": list(m.get("supporting_observation_ids") or m.get("evidence_refs") or [])})
    return out, notes


def _op_validate_concepts(req: dict[str, Any]) -> dict[str, Any]:
    """The product-ideation portfolio law (`ideation.validate_concepts`) + the engine's concept schema: 3–6 DISTINCT product
    directions, each on a SUPPORTED mechanism, each with >= 2 distinct variations, each citing admitted field evidence. No scoring,
    no opinion about which concept is best. Invalid is an OUTPUT (the run can branch back to reasoning)."""
    import graph as graphmod
    import ideation
    import models

    ins = _inputs(req)
    concepts = ins.get("product_concepts")
    if not isinstance(concepts, list) or not concepts:
        raise Refusal("PRODUCT_CONCEPTS_MISSING", "inputs.product_concepts must be a non-empty list")
    mechs, notes = _mechanisms(ins)
    state = _engine_state(mechanisms=mechs, field_records=[{"id": i} for i in ins.get("field_evidence_ids") or []] + list(ins.get("field_records") or []))
    errors = [f"product_concepts[{i}]: {e}" for i, c in enumerate(concepts) for e in models.validate(c, "product_concept")]
    errors += ideation.validate_concepts([c for c in concepts if isinstance(c, dict)], state, graphmod.load_policies())
    return {"valid": not errors, "errors": errors, "mechanism_notes": notes, "concepts_checked": len(concepts),
            "variations_checked": sum(len(c.get("variations") or []) for c in concepts if isinstance(c, dict))}


def _op_supply_plan(req: dict[str, Any]) -> dict[str, Any]:
    """`executors.sourcing_plan_compiler`: one sourcing job PER CONCEPT per channel (no borrowing across concepts) — and, when
    TrailSignal's supply `research_directive` is supplied, the same WHAT / HOW enrichment as `research.plan`: governance untouched,
    Trail's intents first, one compiled intent per sourcing job for the roles Trail asked for, within the query budget."""
    import copy

    import executors
    import graph as graphmod

    ins = _inputs(req)
    concepts = [c for c in ins.get("product_concepts") or [] if isinstance(c, dict)]
    if not concepts:
        raise Refusal("PRODUCT_CONCEPTS_MISSING", "inputs.product_concepts must be the validated concepts")
    mechs, _ = _mechanisms(ins)
    policies = graphmod.load_policies()
    state = _engine_state(product_concepts=concepts, mechanisms=mechs, product_candidates=list(ins.get("product_candidates") or []))
    note = executors.sourcing_plan_compiler(state, policies)
    plan = state["data"]["sourcing_plan"]
    out: dict[str, Any] = {"sourcing_plan": plan, "note": note}
    directive = ins.get("research_directive")
    if (req.get("config") or {}).get("require_directive") and not (isinstance(directive, dict) and directive.get("search_intents")):
        # never let supplier research run under an OLDER directive compiled for another stage (external-review finding M1-07)
        raise Refusal("SUPPLY_DIRECTIVE_MISSING", "TrailSignal compiled no supply research directive for this stage")
    if isinstance(directive, dict) and directive.get("search_intents"):
        enriched = copy.deepcopy(directive)
        trail_intents = [i for i in enriched["search_intents"] if isinstance(i, dict)]
        host = next((ti for ti in trail_intents if set(ti.get("evidence_roles") or []) & {"supply", "price"}), None)
        cap = max(len(trail_intents), min(100, int((directive.get("budget") or {}).get("max_queries") or 24)))
        per_concept: dict[str, list[dict[str, Any] | None]] = {}
        for job in plan:
            terms = " ".join(job["search_terms"][:3])
            per_concept.setdefault(job["concept_id"], []).append(None if host is None else {
                "intent_id": f"{host['intent_id']}:{job['channel']}:{job['concept_id']}"[:200], "evidence_goal": host["evidence_goal"],
                "evidence_roles": [r for r in host["evidence_roles"] if r in ("supply", "price")],
                "intent": f"{job['channel']}: supplier listings for concept {job['concept']} — record concept: {job['concept_id']} in the observation context"[:500],
                "template": (job["tools"][-1] if job["tools"] else terms).replace("<term>", terms)[:500]})
        added, dropped, unserved = _round_robin(list(per_concept.values()), {i.get("intent_id") for i in trail_intents}, cap - len(trail_intents))
        enriched["search_intents"] = trail_intents + added
        out.update(research_directive=enriched, governance_unchanged=all(enriched.get(k) == directive.get(k) for k in _DIRECTIVE_GOVERNANCE),
                   planned={"trail_intents": len(trail_intents), "sourcing_intents": len(added), "jobs": len(plan), "dropped_over_budget": dropped,
                            "no_supply_intent_to_host": unserved, "intent_cap": cap})
    return out


def _op_supply_leads(req: dict[str, Any]) -> dict[str, Any]:
    """ADMITTED supply observations -> supplier candidates -> `executors.supplier` (the engine's own price / MOQ parsers, channel
    MOQ defaults, concept resolution, per-concept coverage) -> `executors.join_leads` (mechanism × supplier, fit required) ->
    `interleave_leads`. NO score and NO verdict: qualification and the only score are TrailSignal's. A listing without a supplier
    name keeps `supplier_name: null` and is counted — a name is never invented."""
    from urllib.parse import urlparse

    import executors
    import graph as graphmod

    ins = _inputs(req)
    concepts = [c for c in ins.get("product_concepts") or [] if isinstance(c, dict)]
    mechs, notes = _mechanisms(ins)
    obs, sources = {}, {}
    for rec in ins.get("receipts") or []:
        if isinstance(rec, dict):
            obs.update({o.get("observation_id"): o for o in rec.get("observations") or [] if isinstance(o, dict)})
            sources.update({s.get("source_id"): s for s in rec.get("sources") or [] if isinstance(s, dict)})
    cands, stats = [], {"admitted_supply": 0, "without_observation": 0, "without_supplier_name": 0, "without_listing": 0}
    for adm in ins.get("admissions") or []:
        for a in (adm or {}).get("admitted") or []:
            if a.get("evidence_role") not in ("supply", "price"):
                continue
            stats["admitted_supply"] += 1
            o = obs.get(a.get("observation_id"))
            if not o:
                stats["without_observation"] += 1
                continue
            ctx, src = str(o.get("context") or ""), sources.get(o.get("source_id")) or {}
            listing = _context_field(ctx, "listing")
            if not listing:
                stats["without_listing"] += 1
                continue
            name = _context_field(ctx, "supplier")
            if not name or name.lower() in ("none", "unknown", "unresolved"):
                name = None
                stats["without_supplier_name"] += 1
            host = (urlparse(str(src.get("url") or "")).hostname or "").removeprefix("www.")
            cands.append({"id": a["admitted_evidence_id"], "product_name": listing, "supplier_name": name or "", "price_raw": _context_field(ctx, "price as listed") or "",
                          "moq_raw": _context_field(ctx, "MOQ as listed") or "", "url": src.get("url"), "channel": _context_field(ctx, "channel") or host.split(".")[0],
                          "concept_id": _context_field(ctx, "concept"), "retrieved_at": src.get("retrieved_at"), "published_at_if_known": src.get("published_at_if_known"),
                          "hypothesis_ids": list(a.get("hypothesis_ids") or [])})
    if not cands:                                         # TrailSignal's qualification / score refusal is the verdict on missing supply, not a dead run
        return {"supplier_candidates": [], "leads": [], "sourcing_coverage": [{"concept_id": c.get("id"), "concept": c.get("name"), "status": "unsourced"} for c in concepts],
                "joined": stats, "mechanism_notes": notes, "note": "no admitted supply observation names a listing",
                "authority": "DOMAIN_JOIN_ONLY — qualification and score are TrailSignal's"}
    policies = graphmod.load_policies()
    state = _engine_state(supplier_candidates=cands, product_concepts=concepts, mechanisms=mechs, leads=[])
    note = executors.supplier(state, policies)
    d = state["data"]
    leads = [l for m in mechs if m["status"] == "SUPPORTED" for l in executors.join_leads(m, d, policies)]
    leads = executors.interleave_leads(leads)[: int(policies["supplier"]["max_leads"])]
    for l in leads:
        l["supplier_name"] = l["supplier_name"] or None
        l["admitted_evidence_id"] = next((s["id"] for s in d["supplier_candidates"] if s.get("url") == l.get("url") and s.get("product_name") == l.get("product_name")), None)
    d["leads"] = leads
    for s in d["supplier_candidates"]:
        s["supplier_name"] = s["supplier_name"] or None
    return {"supplier_candidates": d["supplier_candidates"], "leads": leads, "sourcing_coverage": executors.sourcing_coverage(state), "joined": stats,
            "mechanism_notes": notes, "note": note, "authority": "DOMAIN_JOIN_ONLY — qualification and score are TrailSignal's"}


def _op_product_reality_plan(req: dict[str, Any]) -> dict[str, Any]:
    """The product-reality half of `supply.plan` (restoration reference §10.2 / §10.3): TrailSignal's product-reality directive —
    every governance field untouched — with its stage templates BOUND PER CONCEPT from the concept's market vocabulary (form factor
    + the mechanism's `product_terms`) and its hypothesis's activity, one job per variation and one substitute job per concept.
    Each job names its concept / variation / hypothesis / mechanism and asks the harness to record `concept:` (the supply lane's
    convention) so the join never has to infer ownership. Every concept gets its first job before any gets its second; what did not
    fit the query budget is counted."""
    import copy

    import product_reality as PR

    ins = _inputs(req)
    directive = ins.get("research_directive")
    if not isinstance(directive, dict) or not directive.get("search_intents"):
        raise Refusal("REALITY_DIRECTIVE_MISSING", "inputs.research_directive must be the product-reality directive TrailSignal compiled (with search_intents)")
    concepts = [c for c in ins.get("product_concepts") or [] if isinstance(c, dict)]
    if not concepts:
        raise Refusal("PRODUCT_CONCEPTS_MISSING", "inputs.product_concepts must be the validated concepts")
    mechs, notes = _mechanisms(ins)
    views = {v.get("hypothesis_id"): v for v in ins.get("semantics") or [] if isinstance(v, dict) and v.get("hypothesis_id")}
    out = copy.deepcopy(directive)
    trail_intents = [i for i in out["search_intents"] if isinstance(i, dict)]
    per_concept, unresolved = PR.plan(concepts, mechs, views, trail_intents)
    names = {str(c.get("id")): str(c.get("name") or c.get("id")) for c in concepts}
    unslotted = [ti for ti in trail_intents if not PR.QS.has_unbound_slot(ti.get("template"))]
    cap = max(len(unslotted), min(100, int((directive.get("budget") or {}).get("max_queries") or 24)))
    added, dropped, _ = _round_robin([[PR.intent_for(j, names[j["concept_id"]]) for j in jobs] for jobs in per_concept], {i.get("intent_id") for i in unslotted}, cap - len(unslotted))
    issued = {i["intent_id"] for i in added}
    jobs = [j for group in per_concept for j in group if j["job_id"] in issued]
    out["search_intents"] = unslotted + added
    if not out["search_intents"]:
        raise Refusal("REALITY_PLAN_UNBOUND", "no product-reality job could be compiled: " + json.dumps(unresolved)[:600])
    return {"research_directive": out, "reality_plan": jobs, "mechanism_notes": notes,
            "planned": {"trail_intents": len(trail_intents), "concepts": len(concepts), "jobs": len(jobs), "dropped_over_budget": dropped,
                        "concepts_without_a_job": sorted(set(names) - {j["concept_id"] for j in jobs}), "unresolved": unresolved[:100], "intent_cap": cap},
            "governance_unchanged": all(out.get(k) == directive.get(k) for k in _DIRECTIVE_GOVERNANCE)}


def _op_product_reality_join(req: dict[str, Any]) -> dict[str, Any]:
    """The product-reality half of `supply.leads` (restoration reference §10.4 / §10.5): ADMITTED product-reality observations ->
    existing products joined to the concept (and variation) whose job found them, by the explicit `concept:` tag only. A product
    marked `relation: solves` — or admitted by TrailSignal as contradicting — CONTESTS that one concept; its siblings are untouched.
    NO score and NO verdict: qualification and the only score are TrailSignal's."""
    import product_reality as PR

    ins = _inputs(req)
    concepts = [c for c in ins.get("product_concepts") or [] if isinstance(c, dict)]
    mechs, notes = _mechanisms(ins)
    obs, sources = {}, {}
    for rec in ins.get("receipts") or []:
        if isinstance(rec, dict):
            obs.update({o.get("observation_id"): o for o in rec.get("observations") or [] if isinstance(o, dict)})
            sources.update({s.get("source_id"): s for s in rec.get("sources") or [] if isinstance(s, dict)})
    admitted = [a for adm in ins.get("admissions") or [] for a in (adm or {}).get("admitted") or [] if isinstance(a, dict)]
    joined = PR.join(admitted, obs, sources, concepts, mechs, [j for j in ins.get("reality_plan") or [] if isinstance(j, dict)], _context_field)
    return {**joined, "mechanism_notes": notes, "authority": "DOMAIN_JOIN_ONLY — qualification and score are TrailSignal's",
            "note": f"{joined['joined']['joined']} of {joined['joined']['admitted']} admitted observations joined to a concept by their `concept:` tag; "
                    f"{sum(1 for c in joined['concept_reality'] if c['status'] == 'EXISTING_PRODUCT_CONTESTS')} concept(s) contested by an existing product"}


def _op_refuse(req: dict[str, Any]) -> dict[str, Any]:
    """A law the agent could not satisfy within the loop budget ends the run HONESTLY: a typed gap carrying the law's own errors.
    A manifest routes here from a BRANCH; `config.code` names the refusal, `inputs.errors` (one list or several) says why."""
    cfg = req.get("config") or {}
    errors: list[str] = []
    for v in _inputs(req).values():
        for e in (v if isinstance(v, list) else [v]):
            errors += [str(x) for x in e] if isinstance(e, list) else ([str(e)] if e else [])
    raise Refusal(str(cfg.get("code") or "DOMAIN_LAW_UNSATISFIED"), "; ".join(errors[:6])[:1500] or "the domain law stayed unsatisfied within the loop budget")


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
    "products.validate_concepts": _op_validate_concepts,
    "product_reality.plan": _op_product_reality_plan,
    "product_reality.join": _op_product_reality_join,
    "supply.plan": _op_supply_plan,
    "supply.leads": _op_supply_leads,
    "law.refuse": _op_refuse,
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
