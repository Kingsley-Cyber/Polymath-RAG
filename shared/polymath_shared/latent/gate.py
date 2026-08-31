"""parent-enrichment-v1 gate — deterministic acceptance (§1.2 as
amended by §1.7). The model may vary; parse → validate → sanitize →
canonicalize may not. Reject classes are durable dispositions:

  ENRICH_UNPARSEABLE       no JSON object after lenient repair
  ENRICH_UNKNOWN_REF       a gist ref not in the sent set, or duplicated
  ENRICH_EMPTY             summary or abstraction empty after strip
  ENRICH_GISTS_BELOW_FLOOR gist coverage under bounds.gist_coverage_floor
                           (missing gists are a COUNTED shortfall, not an
                           instant reject — the LEAN survivorship lesson)
  ENRICH_INPUT_OVER_CEILING raised by the COMPILER before any call

Over-cap lists/strings are TRIMMED (budget, not rejection) and the cut
is recorded. Mechanical sanitize only: NFC, strip, whitespace collapse,
control-char removal — representation cleaning, never rewriting."""
from __future__ import annotations

import re
import unicodedata

from polymath_shared.identity import content_hash
from polymath_shared.latent.contract import (
    COMPILER_CONTRACT,
    ChildGist,
    EnrichmentBounds,
    EnrichmentGateResult,
    EnrichmentOutput,
)
from polymath_shared.llm_extraction.gate import (
    _loads_lenient,
    strip_thinking,
)

#: SEMANTIC-FAILOVER-V1 (roadmap A3): reject classes another MODEL
#: might repair (model-specific output failures) vs conditions of the
#: SOURCE that no model can fix. "Retrying another model cannot repair
#: a bad source."
SEMANTIC_FAILOVER_ELIGIBLE = frozenset({
    "ENRICH_UNPARSEABLE",
    "ENRICH_UNKNOWN_REF",
    "ENRICH_GISTS_BELOW_FLOOR",
    "ENRICH_EMPTY",
    "ENRICH_NO_RESPONSE",
})
SEMANTIC_FAILOVER_INELIGIBLE = frozenset({
    "ENRICH_INPUT_OVER_CEILING",
})

_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_WS_RE = re.compile(r"\s+")


def _clean(value, cap: int) -> str:
    s = unicodedata.normalize("NFC", str(value or ""))
    s = _CTRL_RE.sub("", s)
    s = _WS_RE.sub(" ", s).strip()
    return s[:cap]


def _clean_list(values, cap_chars: int, cap_n: int) -> tuple[list[str], int]:
    out: list[str] = []
    seen: set[str] = set()
    for v in (values or []):
        s = _clean(v, cap_chars)
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out[:cap_n], max(0, len(out) - cap_n)


def source_hash(children: list[tuple[str, int, str]]) -> str:
    """Staleness identity (§1.3): ordered [chunk_id, chunk_index, text].
    Children + compiler contract ONLY — relations never drive staleness
    (§1.7)."""
    return content_hash({"compiler": COMPILER_CONTRACT,
                         "children": [list(c) for c in children]})


def transfer_text(output: EnrichmentOutput) -> str:
    """Deterministic latent_transfer surface text (§1.4)."""
    bits = []
    if output.mechanisms:
        bits.append("Mechanisms: " + "; ".join(output.mechanisms) + ".")
    if output.affordances:
        bits.append("Useful for: " + "; ".join(output.affordances) + ".")
    if output.questions:
        bits.append("Answers: " + " ".join(output.questions))
    return " ".join(bits).strip()


def sanitize_enrichment(
    raw: str,
    input_refs: list[int],
    bounds: EnrichmentBounds,
) -> tuple[EnrichmentGateResult, EnrichmentOutput | None]:
    text = strip_thinking(raw or "")
    obj = _loads_lenient(text)
    if not isinstance(obj, dict):
        return EnrichmentGateResult(
            ok=False, error_class="ENRICH_UNPARSEABLE",
            detail="no JSON object", raw_chars=len(raw or "")), None

    sent = set(input_refs)
    gists: list[ChildGist] = []
    seen_refs: set[int] = set()
    for row in (obj.get("children") or []):
        if not isinstance(row, dict):
            continue
        try:
            ref = int(row.get("ref"))
        except (TypeError, ValueError):
            return EnrichmentGateResult(
                ok=False, error_class="ENRICH_UNKNOWN_REF",
                detail=f"non-integer ref {row.get('ref')!r}",
                raw_chars=len(raw)), None
        if ref not in sent or ref in seen_refs:
            return EnrichmentGateResult(
                ok=False, error_class="ENRICH_UNKNOWN_REF",
                detail=f"ref {ref} {'duplicated' if ref in seen_refs else 'not sent'}",
                raw_chars=len(raw)), None
        gist = _clean(row.get("gist"), bounds.gist_chars)
        if gist:
            seen_refs.add(ref)
            gists.append(ChildGist(ref=ref, gist=gist))

    coverage = (len(seen_refs) / len(sent)) if sent else 1.0
    summary = _clean(obj.get("summary"), bounds.summary_chars)
    abstraction = _clean(obj.get("abstraction"), bounds.abstraction_chars)
    if not summary or not abstraction:
        return EnrichmentGateResult(
            ok=False, error_class="ENRICH_EMPTY",
            detail="summary or abstraction empty",
            gist_coverage=coverage, raw_chars=len(raw)), None
    if coverage < bounds.gist_coverage_floor:
        return EnrichmentGateResult(
            ok=False, error_class="ENRICH_GISTS_BELOW_FLOOR",
            detail=f"gist coverage {coverage:.2f} < "
                   f"{bounds.gist_coverage_floor}",
            gist_coverage=coverage, raw_chars=len(raw)), None

    mech, cut_m = _clean_list(obj.get("mechanisms"),
                              bounds.mechanism_chars, bounds.max_mechanisms)
    aff, cut_a = _clean_list(obj.get("affordances"),
                             bounds.affordance_chars, bounds.max_affordances)
    qs, cut_q = _clean_list(obj.get("questions"),
                            bounds.question_chars, bounds.max_questions)
    trimmed = {k: v for k, v in
               (("mechanisms", cut_m), ("affordances", cut_a),
                ("questions", cut_q)) if v}
    return EnrichmentGateResult(
        ok=True, gist_coverage=coverage,
        trimmed=trimmed or None, raw_chars=len(raw)), EnrichmentOutput(
            summary=summary,
            children=sorted(gists, key=lambda g: g.ref),
            abstraction=abstraction,
            mechanisms=mech, affordances=aff, questions=qs)
