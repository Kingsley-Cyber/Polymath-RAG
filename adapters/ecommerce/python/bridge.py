"""Bridge admissibility validator (φ constraining θ).

The model generates bridge hypotheses; this module decides whether they are
ADMISSIBLE. Enforces the policies the schema alone cannot express:

1. evidence_boundary.first_inference_at must be a hop that exists in path[]
   (a boundary pointing nowhere is an unaccountable bridge).
2. The number of hops AT OR PAST the inference boundary may not exceed
   policies.bridge.max_inference_hops_without_evidence + 1 (the boundary hop
   itself plus the allowed speculative extensions). This is the structural
   guard against `storytelling → microphone` style opaque jumps: you may
   speculate, but only a bounded distance past your evidence.
3. Every hypothesis must carry at least one researchable gap while it is a
   WORKING_HYPOTHESIS — a bridge with no testable unknowns is either already
   SUPPORTED (needs observations) or unfalsifiable (inadmissible).
"""
from __future__ import annotations


def validate_bridge(hyp: dict, policies: dict) -> list[str]:
    errors: list[str] = []
    pol = policies.get("bridge") or {}
    path = hyp.get("path") or []
    boundary = ((hyp.get("evidence_boundary") or {}).get("first_inference_at") or "").strip()

    if pol.get("require_evidence_boundary", True):
        if not boundary:
            errors.append(f"{hyp.get('id')}: evidence_boundary.first_inference_at missing")
        elif boundary not in path:
            errors.append(
                f"{hyp.get('id')}: first_inference_at {boundary!r} is not a hop in path {path}")

    # Speculation is allowed only when covered by researchable gaps: every
    # inference hop beyond the free budget must be matched by a gap that can
    # test it. The doc's flagship bridge (5 speculative hops, 3 gaps, max=2)
    # is admissible; the same path with 1 gap is not — that is untested leap.
    max_hops = int(pol.get("max_inference_hops_without_evidence", 2))
    if boundary in path:
        speculative = len(path) - path.index(boundary)
        required_gaps = max(1, speculative - max_hops)
        if len(hyp.get("gaps") or []) < required_gaps:
            errors.append(
                f"{hyp.get('id')}: {speculative} inference hops past the evidence "
                f"boundary need >= {required_gaps} researchable gaps to cover them "
                f"(has {len(hyp.get('gaps') or [])}) — add gaps or shorten the bridge")

    if hyp.get("status") in ("WORKING_HYPOTHESIS", "WORKING_ANALOGY") and not hyp.get("gaps"):
        errors.append(f"{hyp.get('id')}: WORKING_HYPOTHESIS with no researchable gaps is unfalsifiable")

    # docs/02-loop-plane.txt "required deterministic checks", added 2026-08-09:
    # no direct source-concept -> product jump: the path needs intermediate
    # reasoning (>= 3 hops total), else it IS the opaque leap this skill bans.
    if len(path) < 3:
        errors.append(
            f"{hyp.get('id')}: path has {len(path)} hops — a bridge needs at least "
            f"one intermediate mechanism between source concept and target")
    # at least one competing explanation must be entertained (anti nodding-loop)
    if hyp.get("status") in ("WORKING_HYPOTHESIS", "WORKING_ANALOGY") and not hyp.get("alternatives"):
        errors.append(f"{hyp.get('id')}: no alternatives[] — at least one competing explanation is required")
    # every working bridge must name what observation would kill it
    if hyp.get("status") in ("WORKING_HYPOTHESIS", "WORKING_ANALOGY") and not hyp.get("falsifiers"):
        errors.append(f"{hyp.get('id')}: no falsifiers[] — name the observation that would kill this bridge")
    return errors


def validate_hop_refs(hyp: dict, policies: dict, known_ids: set | None) -> list[str]:
    """docs/19: evidence-side hops (before the boundary) must cite corpus /
    observation ids when policy `bridge.require_hop_refs` is on — so the
    'evidence-backed' hops the report shows are machine-checkable."""
    if not (policies.get("bridge") or {}).get("require_hop_refs"):
        return []
    path = hyp.get("path") or []
    boundary = (hyp.get("evidence_boundary") or {}).get("first_inference_at")
    try:
        b = path.index(boundary)
    except ValueError:
        return []  # validate_bridge already rejects a boundary that is not a hop
    refs = hyp.get("hop_refs") or {}
    errs = []
    for i in range(b):
        ids = refs.get(str(i)) or refs.get(i) or []
        if not ids:
            errs.append(f"{hyp.get('id', '?')}: hop {i + 1} is before the evidence boundary but cites no corpus/observation id (hop_refs)")
        elif known_ids is not None:
            bad = [r for r in ids if r not in known_ids]
            if bad:
                errs.append(f"{hyp.get('id', '?')}: hop {i + 1} cites unknown ids {bad[:3]}")
    return errs


def validate_all(hypotheses: list[dict], policies: dict, known_ids: set | None = None) -> list[str]:
    _hop_errs = [e for h in hypotheses for e in validate_hop_refs(h, policies, known_ids)]
    errors: list[str] = []
    for h in hypotheses:
        if isinstance(h, dict):
            errors.extend(validate_bridge(h, policies))
    return (errors) + _hop_errs


def validate_portfolio(hypotheses: list[dict], policies: dict) -> list[str]:
    """Portfolio diversity law (docs/07): cover mechanism FAMILIES. Five
    magnetic clips are one hypothesis. Applied at the hypothesize node only."""
    pp = policies.get("portfolio") or {}
    errors: list[str] = []
    working = [h for h in hypotheses if isinstance(h, dict)]
    lo, hi = pp.get("min_hypotheses", 3), pp.get("max_hypotheses", 6)
    if not lo <= len(working) <= hi:
        errors.append(f"portfolio: {len(working)} hypotheses — need {lo}-{hi} across "
                      f"distinct mechanism families")
    if pp.get("distinct_target_mechanisms", True):
        mechs = [str(h.get("target_mechanism", "")).strip().lower() for h in working]
        dupes = {m for m in mechs if mechs.count(m) > 1}
        if dupes:
            errors.append(f"portfolio: duplicate mechanism families {sorted(dupes)} — "
                          f"variants of one mechanism are ONE hypothesis")
    wild = [h for h in working if h.get("exploratory")]
    if len(wild) > pp.get("max_exploratory", 1):
        errors.append(f"portfolio: {len(wild)} exploratory transfers (max "
                      f"{pp.get('max_exploratory', 1)})")
    for h in wild:
        if h.get("status") != "WORKING_ANALOGY":
            errors.append(f"{h.get('id')}: exploratory transfer must carry status "
                          f"WORKING_ANALOGY — novelty gets no evidentiary privilege")
    return errors
