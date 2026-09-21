"""Deterministic evidence-authority verification (L1/L2 of the ladder).

Relevance != authority. These checks decide what an evidence item is ALLOWED
to establish — role validity, source suitability, claim-relative freshness,
independence grouping. Every check can emit a typed receipt so policy changes
can be recomputed against original metrics later. No LLM calls, ever.
"""
from __future__ import annotations

from models import now


def receipt(check_type: str, level: str, status: str, metrics: dict, reasons: list[str]) -> dict:
    return {"check_type": check_type, "level": level, "status": status,
            "metrics": metrics, "reason_codes": reasons, "at": now()}


def evidence_admissibility(obs: dict, policies: dict) -> list[str]:
    """L1/L2 violations for one observation's evidence contract."""
    errors: list[str] = []
    oid = obs.get("id", "?")
    valid_roles = set((policies.get("evidence_roles") or {}).get("valid") or [])
    roles = obs.get("evidence_roles") or []
    if not roles:
        errors.append(f"{oid}: evidence_roles required — evidence must declare what it establishes")
    for r in roles:
        if r not in valid_roles:
            errors.append(f"{oid}: unknown evidence role {r!r}")

    ident = obs.get("source_identity") or {}
    family = ident.get("source_family")
    suit = policies.get("source_suitability") or {}
    if not family:
        errors.append(f"{oid}: source_identity.source_family required")
    elif family not in suit:
        errors.append(f"{oid}: unknown source_family {family!r} (known: {sorted(suit)})")
    else:
        allowed = set(suit[family].get("may_support") or [])
        for r in roles:
            if r in valid_roles and r not in allowed:
                errors.append(
                    f"{oid}: source_family {family!r} may not establish {r} — "
                    f"a source proves only what it is qualified to prove")

    fresh = (obs.get("freshness") or {}).get("class")
    classes = policies.get("freshness_classes") or []
    if not fresh:
        errors.append(f"{oid}: freshness.class required")
    elif fresh not in classes:
        errors.append(f"{oid}: unknown freshness class {fresh!r}")
    else:
        req = policies.get("freshness_requirements") or {}
        for r in roles:
            allowed_fresh = req.get(r)
            if allowed_fresh and fresh not in allowed_fresh:
                errors.append(
                    f"{oid}: freshness {fresh} cannot establish {r} "
                    f"(claim requires {allowed_fresh}) — freshness is claim-relative")
    return errors


def independence_groups(observations: list[dict]) -> dict:
    """Group field evidence by independent origin. 20 comments from one
    thread/author are ONE voice, not twenty.

    THE definition of independence for the whole skill (gap closure in
    executors.comments and coverage in satisfaction both call this): two
    observations are dependent when they share a (platform, author) OR a
    (platform, thread) — connected components over both dimensions
    (docs/04 §16). Three authors in one viral thread = one voice; one author
    across three threads = one voice. Without a source_identity the URL
    stands in for both author and thread (the legacy rule)."""
    parent: dict = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    families = set()
    nodes = []
    for o in observations:
        ident = o.get("source_identity") or {}
        platform = ident.get("platform") or o.get("source") or "?"
        author = ident.get("author_key") or o.get("source") or o.get("id")
        thread = ident.get("thread_key") or o.get("source") or o.get("id")
        node = ("obs", id(o))
        nodes.append(node)
        union(node, ("author", platform, author))
        union(node, ("thread", platform, thread))
        families.add(ident.get("source_family") or "?")
    groups = {find(n) for n in nodes}
    return {"independent_groups": len(groups), "source_families": len(families)}


def admit_observations(observations: list[dict], policies: dict) -> tuple[list[dict], list[str]]:
    """Split into (admissible, violation_list). Called at submit time so
    inadmissible evidence never enters state."""
    all_errors: list[str] = []
    ok: list[dict] = []
    for o in observations:
        errs = evidence_admissibility(o, policies)
        if errs:
            all_errors.extend(errs)
        else:
            ok.append(o)
    return ok, all_errors
