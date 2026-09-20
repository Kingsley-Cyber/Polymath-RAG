"""CORPUS-EXPLORER-V1 CE2 — explorer expansion (pure except the injected `generate`).

Turns concept-keyed `ActivationCandidate`s (from `corpus_activation`, the NEW non-generative substrate)
into `CORPUS_EXPLORE`-origin subqueries by REUSING the EXISTING WLK2C bridge compiler
(`compile_bridges` / `parse_and_validate` / `compiler_eligible`). This is NOT a second compiler — it is the
same generation machinery, grounded on a DIFFERENT (concept-level, Scout-independent) activation set and
emitted under a distinct, separately-observable origin. Additive + q0-first + fail-open; the fusion weight
and all C4/C5/CA4 authority are unchanged (CORPUS_EXPLORE rides the BRIDGE fusion class). Mirrors
`bridge_integration.plan_bridge_expansion` (Scout-nomination grounded) but sourced from activation.
"""
from __future__ import annotations

from polymath_shared.bridge_compiler import (
    BridgeCompilerInput,
    Concept,
    compile_bridges,
    compiler_eligible,
)
from polymath_shared.bridge_integration import bridges_to_subqueries
from polymath_shared.retrieval_lineage import primary_text

CORPUS_EXPLORE_ORIGIN = "CORPUS_EXPLORE"
CORPUS_EXPLORE_WEIGHT = 0.55       # == BRIDGE_SUBQUERY_WEIGHT (below a USER aspect; C5 decides admission)
MAX_CORPUS_EXPLORE_BRIDGES = 4
MAX_CONCEPTS = 8


def activations_to_concepts(activations, *, max_concepts: int = MAX_CONCEPTS) -> list:
    """`ActivationCandidate[]` → `bridge_compiler.Concept[]` (the grounding set the compiler may derive
    from). key = concept_id (stable slug), label = concept text, source = representative source document
    (rides into `inspired_by_profile`). Deterministic, deduped, bounded."""
    out: list[Concept] = []
    seen: set[str] = set()
    for a in (activations or ()):
        key = str(getattr(a, "concept_id", "") or "").strip()
        if not key or key in seen:
            continue
        label = getattr(a, "concept", "") or key
        docs = list(getattr(a, "source_document_ids", ()) or ())
        out.append(Concept(key=key, label=" ".join(str(label).split())[:200], source=(docs[0] if docs else "")))
        seen.add(key)
        if len(out) >= max_concepts:
            break
    return out


def plan_corpus_explore_expansion(plan, activations, *, generate,
                                  max_add: int = MAX_CORPUS_EXPLORE_BRIDGES,
                                  weight: float = CORPUS_EXPLORE_WEIGHT) -> dict:
    """Pure orchestration (the ONE model call is the injected `generate`). Build concepts from the
    activation set, check INTENT eligibility (reuse `compiler_eligible` / `LATENT_INTENTS`), compile
    bounded bridges, and append them to `plan.queries` as CORPUS_EXPLORE subqueries. Additive: q0 and all
    existing subqueries (including Scout BRIDGE subqueries) are untouched; a plan with no PRIMARY gets no
    expansion (q0 authority); text-dedups against every existing query; never raises. Returns a diag (also
    stashed on `plan.compiler['corpus_explore_expansion']`). Whether a candidate survives is decided
    downstream by C4 (semantic bridge↔q0 + chunk↔bridge) and C5/CA4 — identical to a BRIDGE candidate."""
    queries = list(getattr(plan, "queries", None) or [])
    if not any(getattr(q, "type", "") == "PRIMARY" for q in queries):
        diag = {"added": 0, "eligible": False, "reason": "no_primary"}    # q0 authority: no PRIMARY → nothing
        _stash(plan, diag)
        return diag
    concepts = activations_to_concepts(activations)
    intent = getattr(plan, "intent", "") or ""
    # Concept keys are activation slugs — a distinct key space from Scout doc-ids — so no doc-level
    # coverage subtraction applies here; eligibility is intent-gated + requires ≥1 activated concept.
    eligible, reason = compiler_eligible(intent, concepts, admissible_existing_bridge_concepts=())
    if not eligible:
        diag = {"added": 0, "eligible": False, "reason": reason, "intent": intent, "concepts": len(concepts)}
        _stash(plan, diag)
        return diag
    root = primary_text(queries)
    inp = BridgeCompilerInput(q0=root, intent=intent, concepts=concepts,
                              existing_subqueries=[getattr(q, "query", "") for q in queries
                                                   if getattr(q, "type", "") != "PRIMARY"],
                              graph_relations=[])
    bridges, cdiag = compile_bridges(inp, generate=generate, max_bridges=max_add)
    subqs = bridges_to_subqueries(bridges, {c.key: c for c in concepts}, weight=weight,
                                  origin=CORPUS_EXPLORE_ORIGIN, id_prefix="ce")
    existing_lower = {(getattr(q, "query", "") or "").strip().lower() for q in queries}
    added = 0
    for sq in subqs:
        low = (sq.query or "").strip().lower()
        if low in existing_lower:
            continue
        plan.queries.append(sq)
        existing_lower.add(low)
        added += 1
    diag = {"added": added, "eligible": True, "reason": reason, "intent": intent, "origin": CORPUS_EXPLORE_ORIGIN,
            "concepts": len(concepts), "generated": cdiag.get("generated"), "admitted": cdiag.get("admitted"),
            "dropped_invented": cdiag.get("dropped_invented"), "dropped_structural": cdiag.get("dropped_structural")}
    _stash(plan, diag)
    return diag


def _stash(plan, diag: dict) -> None:
    try:
        comp = getattr(plan, "compiler", None)
        if isinstance(comp, dict):
            comp["corpus_explore_expansion"] = diag
    except Exception:  # noqa: BLE001
        pass
