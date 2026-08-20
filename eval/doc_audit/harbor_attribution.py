"""PHASE 2C — Harbor authority wiring + attribution.

MEASUREMENT ONLY. No admission rules, tables, discourse rules, GLiNER,
canonicalization, binding or predicates are changed here.

Harbor decisions are built from QUALIFIED sources only:
  class A surface-determinable -> existing entity_admission signals
           (proper/acronym/version -> IDENTITY; bare generic -> GENERIC)
  class B context-determinable -> DISCOURSE-REFERENCE-V1 on real document text
  class C concept-dependent    -> ABSTAIN (UNKNOWN / CONTEXT_REQUIRED)

Nothing is inferred that PHASE 2B did not qualify.

Usage: .venv/bin/python eval/doc_audit/harbor_attribution.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

import psycopg  # noqa: E402

from polymath_shared.discourse_reference import resolve  # noqa: E402
from polymath_shared.entity_admission import GENERIC_HEAD, decide  # noqa: E402
from polymath_shared.referential_span import derive as derive_span  # noqa: E402
from polymath_shared.entity_harbor import (  # noqa: E402
    AnchorKind, DecisionStatus, HarborDecision, ReferenceBasis, Referentiality,
    canonical_fact_admissible, graph_eligible,
)

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "i4-fresh-acceptance-v1"
GOLD_V2 = {i["surface"].lower(): i for i in
           json.loads((ROOT / "eval/admission/admission_gold_v2.json").read_text())["items"]}
_DEF = ("the ", "this ", "that ", "these ", "those ", "our ", "its ", "their ")


def sentences(text: str) -> list[str]:
    from workers.summarizer import split_sentences
    return [s for s in split_sentences(text) if s.strip()]


_SYNTAX_CACHE: dict[str, list[dict]] = {}


def syntax_for(doc_name: str, sents: list[str]) -> list[dict]:
    """One syntax-evidence-v1 call per document (qualified spaCy contract)."""
    if doc_name not in _SYNTAX_CACHE:
        import httpx
        r = httpx.post("http://127.0.0.1:8744/infer", timeout=60, json={
            "sentences": [{"sentence_id": f"{doc_name}:{i}", "text": t}
                          for i, t in enumerate(sents)]})
        r.raise_for_status()
        _SYNTAX_CACHE[doc_name] = r.json()["results"]
    return _SYNTAX_CACHE[doc_name]


def referential(proposal: str, doc_name: str, sents: list[str]) -> tuple[str, str]:
    """PHASE 2C.1: recover the determiner-bearing envelope from SOURCE TEXT.

    GLiNER strips determiners; the discourse contract keys on them. Returns
    (referential_surface, note). proposal_surface is never rewritten."""
    syn = syntax_for(doc_name, sents)
    low = proposal.lower()
    for sent, sx in zip(sents, syn):
        idx = sent.lower().find(low)
        if idx < 0:
            continue
        rs = derive_span(proposal, idx, idx + len(proposal), sent, sx)
        if rs.expanded:
            return rs.referential_surface, f"envelope: {rs.reasons[0][:52]}"
        return rs.referential_surface, "no head-aligned envelope"
    return proposal, "surface not located in source text"


DECISIVE_IDENTITY_REASONS = frozenset({
    "acronym_identity", "versioned_identity_structure", "proper_name_identity",
})


def decisive_identity(proposal_surface: str, core_type: str) -> tuple[bool, str]:
    """PHASE 2C.2: the existing QUALIFIED identity rule, evaluated on the raw
    case-preserving proposal_surface.

    Deliberately NOT `named_anchor_present`, which REVISION 3b defined as
    structural evidence and explicitly not authority — using it would make
    "proper token somewhere in the envelope -> IDENTITY" and reopen the
    Qwen3-embedding-model problem. No signal is added or widened here.
    """
    d = decide(proposal_surface, core_type, 0.9)
    return (d.reference_class == "GLOBAL"
            and d.reasons[0] in DECISIVE_IDENTITY_REASONS), d.reasons[0]


def harbor_for(surface: str, core_type: str, doc_text: str,
               anchors: list[tuple[str, str]], stored_scope: str,
               raw_surface: str | None = None,
               doc_name: str = "") -> tuple[HarborDecision, str]:
    """Build a Harbor decision from qualified evidence only.

    Routing precedence (PHASE 2C.2):
      1. qualified gold_v2 annotation / explicit REVISION 3b ruling
      2. decisive identity evidence on the raw proposal_surface
      3. definite/deictic/possessive referential envelope -> discourse consumer
      4. bare or generic -> GENERIC
      5. otherwise ABSTAIN (concept status is PHASE 2D)

    Identity is tested BEFORE the determiner so that envelope recovery cannot
    demote an already-qualified identity-bearing mention. It is tested on the
    PROPOSAL, so a determiner picked up by the envelope is never itself
    identity evidence.

    INTEGRATION NOTE: admission is case-bearing; never recompute it from
    `normalized_surface` (see test_referential_span_v1).
    """
    proposal = raw_surface or surface
    scope = stored_scope
    env, env_note = referential(proposal, doc_name, sentences(doc_text))

    # (1) qualified annotation — outranks every derived signal, so the
    # REVISION 3b CONTEXT_REQUIRED rulings survive identity-first routing.
    for key in (env.lower(), proposal.lower()):
        g = GOLD_V2.get(key)
        if not g:
            continue
        if not (g.get("context_document") or g.get("ruling")):
            continue
        kind = AnchorKind(g["anchor_kind"])
        basis = ReferenceBasis(g["reference_basis"]) if g.get("reference_basis") else None
        return HarborDecision(env, kind, Referentiality(g["referentiality"]),
                              g["scope"], DecisionStatus(g["decision_status"]),
                              basis), f"gold_v2 qualified ruling ({env_note})"

    # (2) decisive identity on the raw proposal
    ident, why = decisive_identity(proposal, core_type)
    if ident:
        return HarborDecision(proposal, AnchorKind.IDENTITY, Referentiality.SPECIFIC,
                              scope), f"identity on proposal: {why} (envelope {env!r} kept as context)"

    # (3) referential envelope is a definite/deictic/possessive description
    if env.lower().startswith(_DEF):
        sents = sentences(doc_text)
        idx = next((i for i, x in enumerate(sents) if env.lower() in x.lower()), None)
        ctx = sents[:idx + 1] if idx is not None else sents
        r = resolve(env, ctx, admitted_anchors=anchors)
        settled = r.basis is not ReferenceBasis.AMBIGUOUS
        return HarborDecision(
            env, AnchorKind.LOCAL_REFERENCE, Referentiality.UNRESOLVED,
            scope if scope != "MENTION_ONLY" else "DOCUMENT_SCOPED",
            DecisionStatus.RESOLVED if settled else DecisionStatus.ABSTAINED,
            r.basis, resolves_to=r.resolves_to), f"discourse: {r.evidence[0][:56]}"

    # (4) bare / generic
    head = re.findall(r"[A-Za-z][A-Za-z0-9\-]*", proposal.lower())
    if scope == "MENTION_ONLY" or (head and head[-1] in GENERIC_HEAD and len(head) < 2):
        return HarborDecision(proposal, AnchorKind.GENERIC, Referentiality.GENERIC,
                              "MENTION_ONLY"), "surface: bare/generic"

    # (5) concept status needs an auditable source
    return HarborDecision(proposal, AnchorKind.UNKNOWN, Referentiality.UNRESOLVED,
                          scope, DecisionStatus.CONTEXT_REQUIRED), \
        "ABSTAIN: concept status needs an auditable source (PHASE 2D)"


def main() -> int:
    gold = json.loads((ROOT / "eval/i4/gold/fact_gold.json").read_text())["supported_positive"]["facts"]
    def n(s): return " ".join(str(s).lower().replace("-", " ").split())
    goldset = {(g["predicate"], n(g["subject"]), n(g["object"])) for g in gold}

    c = psycopg.connect(DSN)
    docs = {r[0]: r[1] for r in c.execute(
        "SELECT doc_id, source_name FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    # raw (case-bearing) surface per entity, from the mention that created it
    raw = {r[0]: r[1] for r in c.execute("""
        SELECT DISTINCT ON (entity_id) entity_id, surface FROM mentions
         WHERE corpus_id=%s AND entity_id IS NOT NULL
         ORDER BY entity_id, char_start""", (CORPUS,)).fetchall()}
    rows = c.execute("""
        SELECT f.predicate, s.normalized_surface, s.core_type, s.admission_class,
               o.normalized_surface, o.core_type, o.admission_class, ev.doc_id,
               f.subject_id, f.object_id
          FROM facts f
          JOIN entities s ON s.entity_id=f.subject_id
          JOIN entities o ON o.entity_id=f.object_id
          JOIN evidence ev ON ev.fact_id=f.fact_id
          JOIN documents d ON d.doc_id=ev.doc_id
         WHERE d.corpus_id=%s ORDER BY d.source_name, f.predicate""", (CORPUS,)).fetchall()
    anchors_by_doc: dict[str, list[tuple[str, str]]] = {}
    for doc_id in docs:
        anchors_by_doc[doc_id] = [
            (r[0], r[1]) for r in c.execute("""
                SELECT DISTINCT m.surface, m.core_type FROM mentions m
                 WHERE m.doc_id=%s AND m.admission_class='GLOBAL'""", (doc_id,)).fetchall()]
    c.close()

    out = []
    for pred, subj, st, sa, obj, ot, oa, doc_id, sid, oid in rows:
        name = docs[doc_id].split("/")[-1]
        text = (ROOT / "eval/i4/corpus" / name).read_text()
        anchors = anchors_by_doc[doc_id]
        sd, swhy = harbor_for(subj, st, text, anchors, sa, raw.get(sid), name)
        od, owhy = harbor_for(obj, ot, text, anchors, oa, raw.get(oid), name)
        admissible, reason = canonical_fact_admissible(sd, od)
        is_tp = (pred, n(subj), n(obj)) in goldset
        # A removal counts as REMOVED_BY_HARBOR only when a SETTLED Harbor
        # judgment caused it. A removal caused by ABSTENTION
        # (UNKNOWN / CONTEXT_REQUIRED) is a MASKED_ERROR: the fact may well be
        # false, but Harbor did not establish that — it declined to answer.
        # Masked errors must never be counted as precision repairs.
        def _judged(d):
            return (d.decision_status is DecisionStatus.RESOLVED
                    and d.anchor_kind is not AnchorKind.UNKNOWN)
        if admissible:
            cls = "PRESERVED"
        elif is_tp:
            cls = "NEW_LOSS"
        else:
            blocking = [d for d in (sd, od) if not graph_eligible(d)]
            cls = ("REMOVED_BY_HARBOR" if all(_judged(d) for d in blocking)
                   else "MASKED_ERROR")
        out.append({"fact": f"{pred}({subj} -> {obj})", "doc": name, "was_tp": is_tp,
                    "subject": {"surface": subj, "old": sa, "anchor_kind": sd.anchor_kind.value,
                                "status": sd.decision_status.value,
                                "basis": sd.reference_basis.value if sd.reference_basis else None,
                                "scope": sd.scope, "eligible": graph_eligible(sd), "why": swhy},
                    "object": {"surface": obj, "old": oa, "anchor_kind": od.anchor_kind.value,
                               "status": od.decision_status.value,
                               "basis": od.reference_basis.value if od.reference_basis else None,
                               "scope": od.scope, "eligible": graph_eligible(od), "why": owhy},
                    "retained": admissible, "classification": cls, "reason": reason})

    (ROOT / "eval/doc_audit/harbor_attribution.json").write_text(json.dumps(out, indent=1))
    print(f"{'fact':<58}{'was':<5}{'kept':<6}classification")
    print("-" * 96)
    for r in out:
        print(f"  {r['fact'][:56]:<56}{'TP' if r['was_tp'] else 'FP':<5}"
              f"{'yes' if r['retained'] else 'NO':<6}{r['classification']}")
    tp0 = sum(1 for r in out if r["was_tp"])
    fp0 = len(out) - tp0
    tp1 = sum(1 for r in out if r["was_tp"] and r["retained"])
    fp1 = sum(1 for r in out if not r["was_tp"] and r["retained"])
    masked = sum(1 for r in out if r["classification"] == "MASKED_ERROR")
    print(f"\n  before: TP {tp0}  FP {fp0}   P {tp0/(tp0+fp0):.3f}")
    print(f"  after : TP {tp1}  FP {fp1}   P {tp1/(tp1+fp1):.3f}" if tp1+fp1 else "  after : no facts")
    from collections import Counter
    print("  classes:", dict(Counter(r["classification"] for r in out)))
    if masked:
        print(f"\n  WARNING: {masked} MASKED_ERROR — removed by ABSTENTION, not by a")
        print("           Harbor judgment. These are NOT precision repairs.")
    genuine = sum(1 for r in out if r["classification"] == "REMOVED_BY_HARBOR")
    print(f"  genuine Harbor removals: {genuine} of {tp0 + fp0 - tp1 - fp1} removals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
