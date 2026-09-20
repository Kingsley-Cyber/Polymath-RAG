"""WLK2C C3 — bridge integration (pure except the injected `generate`; the live gemma call + this
function's invocation live in the orchestrator, flag-gated, proven at C7).

Turns admitted concept-bridges into BRIDGE-origin subqueries on the compiled plan so they retrieve and
deepen against their `origin_query` (the bridge). This mirrors PROFILE-EXPANSION-V1 (`_add_profile_
expansion`) but sources the subqueries from the C2 compiler under the tiered policy:

  1. reuse — a nominated concept already covered by a C1-admissible existing subquery is NOT re-compiled;
  2. (graph-path bridges — future);
  3. the bounded compiler runs (one injected call) only for the UNCOVERED concepts, and only when the
     plan's INTENT permits latent expansion (never mode-based).

Additive and q0-first: q0 and its existing aspect subqueries are untouched; a plan with no PRIMARY gets
no expansion (q0 authority); every added subquery carries full lineage (`origin='BRIDGE'`, `role=
'bridge'`, `inspired_by_profile=[concept source]`, `target=concept key`, a `reason` tying it to q0).
Whether a bridge candidate actually survives is decided downstream: C4 (semantic bridge↔q0 + chunk↔
bridge) and C5 (authoritative role/portfolio).
"""
from __future__ import annotations

from polymath_shared.bridge_admission import structural_bridge_admissibility
from polymath_shared.bridge_compiler import (
    MAX_BRIDGES,
    BridgeCompilerInput,
    Concept,
    compile_bridges,
    compiler_eligible,
)
from polymath_shared.retrieval_lineage import DiscoveryPath, primary_text

BRIDGE_SUBQUERY_WEIGHT = 0.55            # below a USER aspect (q0 stays primary; C5 decides admission)
MAX_CONCEPTS = 8


def concepts_from_nominations(nominations, *, max_concepts: int = MAX_CONCEPTS) -> list:
    """Scout nominations → the grounded concept set (key=doc_id; label=representative surface/text/title).
    Deterministic, deduped, bounded. Duck-typed over a nomination object or a dict."""
    def _g(n, a):
        return (n.get(a) if isinstance(n, dict) else getattr(n, a, None))
    out: list[Concept] = []
    seen: set[str] = set()
    for nom in (nominations or ()):
        did = str(_g(nom, "doc_id") or "").strip()
        if not did or did in seen:
            continue
        label = (_g(nom, "representative_surface") or _g(nom, "representative_text")
                 or _g(nom, "title") or _g(nom, "source_name") or did)
        out.append(Concept(key=did, label=" ".join(str(label).split())[:200], source=did))
        seen.add(did)
        if len(out) >= max_concepts:
            break
    return out


def covered_concept_keys(plan_queries, root_query: str) -> set:
    """Concept keys already covered by a C1-admissible EXISTING (non-bridge) subquery (tier-1 reuse):
    the concept is grounded into that subquery's `inspired_by_profile` and the subquery is a structurally
    valid bridge. Such concepts are NOT re-compiled — the compiler runs only for the uncovered rest."""
    covered: set[str] = set()
    for q in (plan_queries or ()):
        if getattr(q, "type", "") == "PRIMARY" or getattr(q, "origin", "") == "BRIDGE":
            continue
        inspired = list(getattr(q, "inspired_by_profile", []) or [])
        if not inspired:
            continue
        path = DiscoveryPath(origin_query=getattr(q, "query", "") or "",
                             origin=getattr(q, "origin", "USER") or "USER",
                             query_id=str(getattr(q, "id", "")), bridge_id=str(getattr(q, "id", "")),
                             inspired_by_profile=inspired)
        if structural_bridge_admissibility(path, root_query).admissible:
            covered.update(str(d) for d in inspired)
    return covered


def bridges_to_subqueries(bridges, concepts_by_key, *, start_index: int = 0,
                          weight: float = BRIDGE_SUBQUERY_WEIGHT,
                          origin: str = "BRIDGE", id_prefix: str = "br") -> list:
    """Admitted CompiledBridges → latent-origin `CompiledQuery` subqueries (deterministic). Each carries
    full lineage: origin (default BRIDGE), role=bridge, inspired_by_profile=[concept source], target=concept
    key, and a `reason` naming the concept + relation_to_q0. proposed_role rides in the reason (C5
    authoritative). CORPUS-EXPLORER-V1 reuses this with origin="CORPUS_EXPLORE"/id_prefix="ce" (distinct ids
    so both expansions can coexist); the BRIDGE defaults keep the existing WLK2C path byte-identical."""
    from polymath_shared.chat_plan import MAX_QUERY_WORDS, CompiledQuery
    out = []
    for i, b in enumerate(bridges):
        concept = concepts_by_key.get(b.derived_from)
        q = " ".join((b.bridge_query or "").split()[:MAX_QUERY_WORDS]).strip()
        if not q:
            continue
        out.append(CompiledQuery(
            id=f"{id_prefix}{start_index + i}", type="ENTITY", query=q, weight=weight,
            role="bridge", origin=origin,
            inspired_by_profile=([concept.source] if (concept and concept.source) else []),
            profile_surface=(concept.label if concept else None),
            target=(concept.key if concept else b.derived_from),
            reason=(f"bridge/{b.proposed_role.lower()} <- {b.derived_from}: {b.relation_to_q0}")[:200]))
    return out


def plan_bridge_expansion(plan, nominations, *, generate, max_add: int = MAX_BRIDGES,
                          weight: float = BRIDGE_SUBQUERY_WEIGHT) -> dict:
    """Pure orchestration (the ONE model call is the injected `generate`). Build concepts from the scout
    nominations, subtract the tier-1-covered ones, check INTENT eligibility, compile bounded bridges for
    the uncovered concepts, and append them to `plan.queries` as BRIDGE subqueries. Additive; q0 and
    existing subqueries untouched; never raises. Returns a diag (also stashed on `plan.compiler`)."""
    queries = list(getattr(plan, "queries", None) or [])
    diag: dict
    if not any(getattr(q, "type", "") == "PRIMARY" for q in queries):
        diag = {"added": 0, "eligible": False, "reason": "no_primary"}       # q0 authority: no PRIMARY → no expansion
        _stash(plan, diag); return diag
    intent = getattr(plan, "intent", "") or ""
    root = primary_text(queries)
    concepts = concepts_from_nominations(nominations)
    covered = covered_concept_keys(queries, root)
    eligible, reason = compiler_eligible(intent, concepts, covered)
    if not eligible:
        diag = {"added": 0, "eligible": False, "reason": reason, "intent": intent,
                "concepts": len(concepts), "covered": len(covered)}
        _stash(plan, diag); return diag
    uncovered = [c for c in concepts if c.key not in covered]
    inp = BridgeCompilerInput(q0=root, intent=intent, concepts=uncovered,
                              existing_subqueries=[getattr(q, "query", "") for q in queries
                                                   if getattr(q, "type", "") != "PRIMARY"],
                              graph_relations=[])
    bridges, cdiag = compile_bridges(inp, generate=generate, max_bridges=max_add)
    subqs = bridges_to_subqueries(bridges, {c.key: c for c in uncovered}, weight=weight)
    existing_lower = {(getattr(q, "query", "") or "").strip().lower() for q in queries}
    added = 0
    for sq in subqs:
        low = (sq.query or "").strip().lower()
        if low in existing_lower:
            continue
        plan.queries.append(sq); existing_lower.add(low); added += 1
    diag = {"added": added, "eligible": True, "reason": reason, "intent": intent,
            "concepts": len(concepts), "uncovered": len(uncovered),
            "generated": cdiag.get("generated"), "admitted": cdiag.get("admitted"),
            "dropped_invented": cdiag.get("dropped_invented"), "dropped_structural": cdiag.get("dropped_structural")}
    _stash(plan, diag); return diag


def _stash(plan, diag: dict) -> None:
    try:
        comp = getattr(plan, "compiler", None)
        if isinstance(comp, dict):
            comp["bridge_expansion"] = diag
    except Exception:  # noqa: BLE001
        pass
