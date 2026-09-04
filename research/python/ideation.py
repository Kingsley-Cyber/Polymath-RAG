"""PRODUCT-IDEATION portfolio law (docs/19): φ constrains θ's product set.

A supported mechanism must become a SET of distinct product directions with
variations — the user asked for "3–4 different products with multiple
variations", not six suppliers of the same organiser. Deterministic checks
only; no scoring, no opinion about which concept is best.
"""
from __future__ import annotations

import re


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def validate_concepts(concepts: list[dict], state: dict, policies: dict) -> list[str]:
    pol = policies.get("ideation") or {}
    lo, hi = int(pol.get("min_concepts", 3)), int(pol.get("max_concepts", 6))
    min_var = int(pol.get("min_variations", 2))
    errors: list[str] = []
    if not (lo <= len(concepts) <= hi):
        errors.append(f"portfolio law: {lo}–{hi} distinct product concepts required, got {len(concepts)}")
    supported = {m["id"] for m in state["data"].get("mechanisms") or [] if m.get("status") == "SUPPORTED"}
    obs_ids = {o["id"] for o in state["data"].get("observations") or []}
    seen_ff: dict[str, str] = {}
    for c in concepts:
        cid = c.get("id", "?")
        if c.get("mechanism_id") not in supported:
            errors.append(f"{cid}: mechanism_id {c.get('mechanism_id')!r} is not a SUPPORTED mechanism")
        ff = _norm(c.get("form_factor"))
        if ff in seen_ff:
            errors.append(f"{cid}: form_factor {c.get('form_factor')!r} duplicates {seen_ff[ff]} — distinct directions, not variants")
        seen_ff.setdefault(ff, cid)
        vs = c.get("variations") or []
        if len(vs) < min_var:
            errors.append(f"{cid}: at least {min_var} variations required")
        names = {_norm(v.get("name") if isinstance(v, dict) else str(v)) for v in vs}
        if len(names) < len(vs):
            errors.append(f"{cid}: variations must be distinct")
        refs = c.get("evidence_refs") or []
        missing = [r for r in refs if r not in obs_ids]
        if not refs or missing:
            errors.append(f"{cid}: evidence_refs must name observation ids in state (unknown: {missing[:3]})")
    return errors
