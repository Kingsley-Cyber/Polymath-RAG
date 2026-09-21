"""Product reality: plan per concept, join per concept (restoration reference §10). Pure; no I/O.

The supply lane already works this way (`supply.plan` -> research -> `supply.leads`). Product reality had neither half: the harness
received TrailSignal's four stage templates with `{product_territory}` unbound, the typed concepts arrived only as reading material,
and nothing linked a competitor back to the concept it tests. This module is the missing pair — it does NOT generate concepts, does
NOT reorder stages, scores nothing and decides nothing: TrailSignal governs roles, sources, freshness and budget, and qualification
and the only score stay TrailSignal's.

    plan   concept + its mechanism's `product_terms` + its hypothesis's activity / population / physical job
             -> one research job per (concept x TrailSignal template), one per variation, one substitute job — each job KNOWS its
                concept_id, variation_id, hypothesis_id, mechanism_id
    join   admitted observations -> existing products, linked to a concept ONLY through the explicit `concept:` tag the job asked
             the harness to record (the supply lane's convention). No tag, no link: ownership is never inferred from a name.
             A product the harness marks `relation: solves` (or TrailSignal admits as contradicting) CONTESTS that concept — and
             only that concept."""
from __future__ import annotations

from typing import Any, Mapping

import query_semantics as QS

RELATIONS = ("competitor", "substitute", "current_solution", "validates", "solves")
#: what an untagged observation's relation defaults to, by the evidence role TrailSignal admitted it under
ROLE_DEFAULT_RELATION = {"competition": "competitor", "price": "competitor"}
CONTEXT_CONVENTION = ("record in the observation context — `concept: {concept_id}`{variation} · `relation: competitor | substitute | current_solution | "
                      "validates | solves` (`solves` = an existing product ALREADY does what this concept would) · `product: <name as listed>` · "
                      "`price as listed: <text>` when shown · `intent: <this intent's id>`")


def variation_id(concept_id: str, index: int) -> str:
    """Variations carry no id of their own (`{name, twist}`); position inside the validated concept is their identity."""
    return f"{concept_id}.v{index + 1}"


def market_phrase(concept: Mapping[str, Any], mechanism: Mapping[str, Any] | None, *, extra: str = "") -> str:
    """What this concept is CALLED on a market: its form factor (what distinguishes it from its sibling concepts) plus its
    mechanism's first `product_terms` entry (the vocabulary buyers and listings use). Never a registry territory id."""
    terms = [str(t) for t in (mechanism or {}).get("product_terms") or [] if isinstance(t, str) and t.strip()]
    primary = terms[0] if terms else str(concept.get("name") or "")
    return " ".join(QS._merge(QS.keywords(extra, 3), QS.keywords(concept.get("form_factor"), 3), QS.keywords(primary, 4), cap=6))


def plan(concepts: list[Mapping[str, Any]], mechanisms: list[Mapping[str, Any]], views: Mapping[str, Mapping[str, Any]],
         trail_intents: list[Mapping[str, Any]]) -> tuple[list[list[dict[str, Any]]], list[dict[str, Any]]]:
    """-> (jobs grouped per concept in priority order, unresolved). Every job: {job_id, concept_id, variation_id, hypothesis_id,
    mechanism_id, job_class, query, host_intent_id, evidence_goal, evidence_roles}."""
    mech_by_id = {str(m.get("id")): m for m in mechanisms if isinstance(m, Mapping)}
    competition = next((ti for ti in trail_intents if "competition" in (ti.get("evidence_roles") or [])), None)
    per_concept: list[list[dict[str, Any]]] = []
    unresolved: list[dict[str, Any]] = []
    siblings: dict[str, list[str]] = {}
    for c in concepts:
        m_ = mech_by_id.get(str(c.get("mechanism_id"))) or {}
        siblings.setdefault(str(m_.get("hypothesis_id") or c.get("hypothesis_id") or ""), []).append(str(c.get("id")))
    substitute_planned: set[str] = set()
    for c in concepts:
        cid = str(c.get("id") or "")
        mech = mech_by_id.get(str(c.get("mechanism_id")))
        hid = str((mech or {}).get("hypothesis_id") or c.get("hypothesis_id") or "")
        if not cid or not hid:
            unresolved.append({"concept_id": cid or None, "missing": ["mechanism -> hypothesis"]})
            continue
        view = views.get(hid) or {}
        base = {"concept_id": cid, "variation_id": None, "hypothesis_id": hid, "mechanism_id": (mech or {}).get("id")}
        phrase = market_phrase(c, mech)
        jobs: list[dict[str, Any]] = []
        for ti in trail_intents:
            template = str(ti.get("template") or "")
            if not QS.has_unbound_slot(template):
                continue
            text, missing = QS.bind_template(template, view, overrides={"product_territory": phrase})
            if text is None:
                unresolved.append({"concept_id": cid, "intent_id": ti.get("intent_id"), "missing": missing})
                continue
            jobs.append({**base, "job_id": f"{ti['intent_id']}:{cid}", "job_class": str(ti.get("evidence_goal") or "competition"), "query": text,
                         "host_intent_id": ti["intent_id"], "evidence_goal": ti["evidence_goal"], "evidence_roles": list(ti.get("evidence_roles") or [])})
        if competition is not None:
            host = {"host_intent_id": competition["intent_id"], "evidence_goal": competition["evidence_goal"], "evidence_roles": ["competition"]}
            # the one job every concept always has, whatever TrailSignal's templates look like: who already sells THIS
            jobs.append({**base, **host, "job_id": f"{competition['intent_id']}:{cid}:direct", "job_class": "direct_competitor", "query": phrase})
            need = next((str(j.get("job")) for j in view.get("jobs") or [] if isinstance(j, Mapping) and j.get("job")), "") or str(view.get("task") or "")
            who = QS.keywords(view.get("population"), 2)
            if need and who and hid not in substitute_planned:    # how the JOB is solved today, whatever the product form: ONE search per hypothesis —
                substitute_planned.add(hid)                       # it would be word for word the same for every sibling concept
                jobs.append({**base, **host, "job_id": f"{competition['intent_id']}:{cid}:substitute", "job_class": "substitute",
                             "applies_to_concepts": list(siblings.get(hid) or [cid]), "query": " ".join(QS._merge(who, QS.keywords(need, 4), ["alternative"]))})
            for n, v in enumerate(c.get("variations") or []):
                if isinstance(v, Mapping) and v.get("name"):
                    vid = variation_id(cid, n)
                    jobs.append({**base, **host, "variation_id": vid, "job_id": f"{competition['intent_id']}:{vid}", "job_class": "direct_competitor",
                                 "query": market_phrase(c, mech, extra=str(v["name"]))})
        # every concept's strongest jobs first: a review / incumbent search, then price, then the rest
        rank = {"competition": 1, "price": 2, "substitute": 3, "direct_competitor": 4}
        jobs.sort(key=lambda j: 0 if j["job_id"].endswith(":direct") else rank.get(j["job_class"], 5))
        per_concept.append(jobs)
    seen: dict[str, str] = {}
    for jobs in per_concept:                                       # the same search for two concepts is said, not hidden
        for j in jobs:
            if j["query"] in seen and seen[j["query"]] != j["concept_id"]:
                j["same_query_as_concept"] = seen[j["query"]]
            seen.setdefault(j["query"], j["concept_id"])
    return per_concept, unresolved


def intent_for(job: Mapping[str, Any], concept_name: str) -> dict[str, Any]:
    variation = f" · `variation: {job['variation_id']}`" if job.get("variation_id") else ""
    convention = CONTEXT_CONVENTION.format(concept_id=job["concept_id"], variation=variation)
    return {"intent_id": str(job["job_id"])[:200], "evidence_goal": job["evidence_goal"], "evidence_roles": list(job["evidence_roles"]),
            "intent": f"{job['job_class']} for concept {job['concept_id']} ({concept_name}) — {convention}"[:500], "template": str(job["query"])[:500]}


def join(admitted: list[Mapping[str, Any]], observations: Mapping[str, Mapping[str, Any]], sources: Mapping[str, Mapping[str, Any]],
         concepts: list[Mapping[str, Any]], mechanisms: list[Mapping[str, Any]], jobs: list[Mapping[str, Any]], context_field) -> dict[str, Any]:
    """Admitted product-reality observations -> existing products per concept. `context_field(context, key)` is the binding's
    tolerant reader of `key: value · key: value`."""
    concept_by_id = {str(c.get("id")): c for c in concepts if isinstance(c, Mapping) and c.get("id")}
    mech_by_id = {str(m.get("id")): m for m in mechanisms if isinstance(m, Mapping)}
    variations = {variation_id(cid, n): str(v.get("name")) for cid, c in concept_by_id.items() for n, v in enumerate(c.get("variations") or []) if isinstance(v, Mapping)}
    products: list[dict[str, Any]] = []
    job_ids = {str(j.get("job_id")) for j in jobs if j.get("job_id")}
    stats = {"admitted": 0, "without_observation": 0, "without_concept_tag": 0, "unknown_concept": 0, "joined": 0}
    unjoined: list[dict[str, Any]] = []
    for a in admitted:
        stats["admitted"] += 1
        o = observations.get(a.get("observation_id"))
        if not o:
            stats["without_observation"] += 1
            continue
        ctx = str(o.get("context") or "")
        cid = context_field(ctx, "concept")
        if not cid or cid not in concept_by_id:
            stats["without_concept_tag" if not cid else "unknown_concept"] += 1
            unjoined.append({"admitted_evidence_id": a.get("admitted_evidence_id"), "reason": "NO_CONCEPT_TAG" if not cid else "UNKNOWN_CONCEPT", "claimed": cid,
                             "claim": str(o.get("claim") or "")[:200]})
            continue
        vid = context_field(ctx, "variation")
        relation = str(context_field(ctx, "relation") or "").lower().replace(" ", "_")
        if relation not in RELATIONS:
            relation = ROLE_DEFAULT_RELATION.get(str(a.get("evidence_role")), "competitor")
        src = sources.get(o.get("source_id")) or {}
        mech = mech_by_id.get(str(concept_by_id[cid].get("mechanism_id"))) or {}
        contests = relation == "solves" or a.get("polarity") == "contradicting"
        products.append({"id": a.get("admitted_evidence_id"), "concept_id": cid, "variation_id": vid if vid in variations else None,
                         "hypothesis_id": mech.get("hypothesis_id"), "hypothesis_ids": list(a.get("hypothesis_ids") or []), "mechanism_id": mech.get("id"),
                         "relation": relation, "contests_concept": contests, "product_name": context_field(ctx, "product"),
                         "price_raw": context_field(ctx, "price as listed"), "url": src.get("url"), "claim": str(o.get("claim") or "")[:400],
                         "evidence_role": a.get("evidence_role"), "polarity": a.get("polarity"), "metric": o.get("metric_if_present"),
                         "job_id": (context_field(ctx, "intent") if context_field(ctx, "intent") in job_ids else None)})   # PROVENANCE HOOK: the job that found it
        stats["joined"] += 1
    planned = {}
    for j in jobs:
        planned[j.get("concept_id")] = planned.get(j.get("concept_id"), 0) + 1
    reality = []
    for cid, c in concept_by_id.items():
        mine = [p for p in products if p["concept_id"] == cid]
        solved = [p["id"] for p in mine if p["contests_concept"]]
        status = "EXISTING_PRODUCT_CONTESTS" if solved else "EXISTING_PRODUCTS_FOUND" if mine else "NO_EXISTING_PRODUCT_JOINED" if planned.get(cid) else "NOT_RESEARCHED"
        by_relation: dict[str, int] = {}
        for p in mine:
            by_relation[p["relation"]] = by_relation.get(p["relation"], 0) + 1
        reality.append({"concept_id": cid, "concept": c.get("name"), "mechanism_id": c.get("mechanism_id"),
                        "hypothesis_id": (mech_by_id.get(str(c.get("mechanism_id"))) or {}).get("hypothesis_id"), "jobs_planned": planned.get(cid, 0),
                        "existing_products": len(mine), "by_relation": by_relation, "contested_by": solved, "status": status})
    return {"existing_products": products, "concept_reality": reality, "joined": stats, "unjoined": unjoined[:50]}
