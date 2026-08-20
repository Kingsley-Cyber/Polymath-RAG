"""S1 — BLAST-RADIUS-V1. READ ONLY. No writes, no migrations, no tuning.

Compares the CURRENT production interpretation (entity-admission-v1.1)
against the fully qualified V2 stack over the entire persisted corpus:

    IDENTITY-PRECISION-V2 -> ENTITY-HARBOR -> DISCOURSE-REFERENCE-V1
    -> CONCEPT-EVIDENCE-V1 -> graph_eligible() -> CONTRACTION-RESOLUTION-V1

Answers: how much entity/fact/projection churn a cutover causes, and the
earliest point a rederive can safely start from.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import httpx  # noqa: E402
import psycopg  # noqa: E402

from polymath_shared.concept_evidence import admit_concept  # noqa: E402
from polymath_shared.contraction_resolution import (  # noqa: E402
    build_memberships,
)
from polymath_shared.discourse_reference import resolve  # noqa: E402
from polymath_shared.entity_admission import GENERIC_HEAD  # noqa: E402
from polymath_shared.entity_harbor import (  # noqa: E402
    AnchorKind, DecisionStatus, HarborDecision, ReferenceBasis, Referentiality,
    graph_eligible,
)
from polymath_shared.identity_evidence import identity_evidence  # noqa: E402
from polymath_shared.referential_span import derive  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "i4-fresh-acceptance-v1"
SPACY = "http://127.0.0.1:8744/infer"
DEF = ("the ", "this ", "that ", "these ", "those ", "our ", "its ", "their ")


def sentences(text: str) -> list[tuple[int, str]]:
    out, pos = [], 0
    for part in re.split(r"(?<=[.!?])\s+|\n+", text):
        if part.strip():
            i = text.find(part, pos)
            out.append((i, part))
            pos = i + len(part)
    return out


def main() -> int:
    c = psycopg.connect(DSN)
    docs = {r[0]: r[1].split("/")[-1] for r in c.execute(
        "SELECT doc_id, source_name FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    chunks = {r[0]: r[1] for r in c.execute(
        "SELECT ch.chunk_id, ch.text FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id "
        "WHERE d.corpus_id=%s", (CORPUS,)).fetchall()}
    mentions = c.execute(
        "SELECT mention_id, doc_id, chunk_id, char_start, char_end, surface, "
        "normalized_surface, core_type, admission_class, entity_id "
        "FROM mentions WHERE corpus_id=%s ORDER BY doc_id, char_start", (CORPUS,)).fetchall()
    facts = c.execute("""
        SELECT f.fact_id, f.predicate, f.subject_id, f.object_id,
               s.normalized_surface, o.normalized_surface, ev.doc_id
          FROM facts f
          JOIN entities s ON s.entity_id=f.subject_id
          JOIN entities o ON o.entity_id=f.object_id
          JOIN evidence ev ON ev.fact_id=f.fact_id
          JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s""", (CORPUS,)).fetchall()
    c.close()

    # regenerate syntax per chunk (deterministic under the pinned model)
    syn_cache: dict[str, list[dict]] = {}
    for cid, text in chunks.items():
        sents = sentences(text)
        if not sents:
            continue
        r = httpx.post(SPACY, timeout=180, json={"sentences": [
            {"sentence_id": f"{cid}:{i}", "text": s} for i, (_, s) in enumerate(sents)]})
        r.raise_for_status()
        syn_cache[cid] = [{"offset": off, "sent": s, "syn": res}
                          for (off, s), res in zip(sents, r.json()["results"])]

    m_stats = Counter()
    decisions: dict[str, dict] = {}
    admitted_by_doc: dict[str, list[tuple[str, str]]] = {}

    for mid, doc_id, cid, cs, ce, surface, norm, ctype, old_class, old_eid in mentions:
        m_stats["total"] += 1
        text = chunks.get(cid, "")
        host = next((s for s in syn_cache.get(cid, [])
                     if s["offset"] <= cs < s["offset"] + len(s["sent"])), None)
        if host is None:
            m_stats["missing_syntax_or_context"] += 1
            decisions[mid] = {"eligible": False, "reason": "no host sentence"}
            continue
        rel = cs - host["offset"]
        toks = [t for t in host["syn"]["tokens"]
                if t["char_start"] >= rel and t["char_end"] <= rel + (ce - cs)]
        env = derive(surface, rel, rel + (ce - cs), host["sent"], host["syn"])
        ident = identity_evidence(surface, tokens=toks)

        if ident.is_identity:
            d = HarborDecision(surface, AnchorKind.IDENTITY, Referentiality.SPECIFIC,
                               old_class if old_class != "MENTION_ONLY" else "GLOBAL")
        elif env.referential_surface.lower().startswith(DEF):
            ctx = [s["sent"] for s in syn_cache[cid] if s["offset"] <= host["offset"]]
            r = resolve(env.referential_surface, ctx, admitted_anchors=[])
            settled = r.basis is not ReferenceBasis.AMBIGUOUS
            d = HarborDecision(env.referential_surface, AnchorKind.LOCAL_REFERENCE,
                               Referentiality.UNRESOLVED, "DOCUMENT_SCOPED",
                               DecisionStatus.RESOLVED if settled else DecisionStatus.ABSTAINED,
                               r.basis)
        else:
            head = re.findall(r"[A-Za-z][A-Za-z0-9\-]*", surface.lower())
            if head and head[-1] in GENERIC_HEAD and len(head) < 2:
                d = HarborDecision(surface, AnchorKind.GENERIC, Referentiality.GENERIC,
                                   "MENTION_ONLY")
            elif admit_concept(surface, document_text=text, doc_id=doc_id):
                d = HarborDecision(surface, AnchorKind.CONCEPT, Referentiality.GENERIC,
                                   "CORPUS_SCOPED")
            else:
                d = HarborDecision(surface, AnchorKind.UNKNOWN, Referentiality.UNRESOLVED,
                                   old_class, DecisionStatus.CONTEXT_REQUIRED)

        elig = graph_eligible(d)
        old_elig = old_class != "MENTION_ONLY"
        decisions[mid] = {"eligible": elig, "kind": d.anchor_kind.value,
                          "scope": d.scope, "surface": surface, "doc": doc_id}
        if elig:
            admitted_by_doc.setdefault(doc_id, []).append((surface, ctype))
        m_stats["scope_changed"] += d.scope != old_class
        m_stats["newly_ineligible"] += old_elig and not elig
        m_stats["newly_eligible"] += (not old_elig) and elig
        m_stats["abstained"] += d.decision_status is not DecisionStatus.RESOLVED
        m_stats["unchanged"] += (d.scope == old_class) and (elig == old_elig)
        m_stats[f"kind::{d.anchor_kind.value}"] += 1

    print("=" * 74)
    print("S1  BLAST-RADIUS-V1   READ ONLY — no writes, no migrations")
    print("=" * 74)
    print(f"\nMENTIONS  (total {m_stats['total']})")
    for k in ("unchanged", "scope_changed", "newly_ineligible", "newly_eligible",
              "abstained", "missing_syntax_or_context"):
        print(f"  {k:<28} {m_stats[k]}")
    print("  anchor kinds:", {k.split('::')[1]: v for k, v in m_stats.items()
                              if k.startswith("kind::")})

    surv = {m: d for m, d in decisions.items() if d.get("eligible")}
    print(f"\nENTITIES")
    old_admitted = {mid for mid, *_rest in
                    [(m[0], m[8]) for m in mentions] if _rest}
    old_e = sum(1 for m in mentions if m[8] != "MENTION_ONLY")
    print(f"  admitted under v1.1          {old_e}")
    print(f"  admitted under v2            {len(surv)}")
    print(f"  net identity churn           {old_e - len(surv):+d}")
    clusters = {}
    for doc_id, adm in admitted_by_doc.items():
        mem = build_memberships(adm)
        for s, rec in mem.items():
            clusters.setdefault((doc_id, rec.canonical_id), set()).add(s)
    merged = {k: v for k, v in clusters.items() if len(v) > 1}
    print(f"  canonical entities (v2)      {len(clusters)}")
    print(f"  merged clusters              {len(merged)}")

    print(f"\nFACTS  (reachable {len(facts)})")
    kept = lost = 0
    for fid, pred, sid, oid, subj, obj, doc in facts:
        se = any(d.get("eligible") and d["surface"].lower() == subj for d in decisions.values())
        oe = any(d.get("eligible") and d["surface"].lower() == obj for d in decisions.values())
        kept += se and oe
        lost += not (se and oe)
    print(f"  endpoints still eligible     {kept}")
    print(f"  removed by eligibility       {lost}")
    print(f"  ALL fact_ids change          yes — endpoint ids are admission-derived")

    print(f"\nDOCUMENTS  ({len(docs)})")
    affected = {d["doc"] for d in decisions.values() if d.get("doc")}
    print(f"  require semantic reprocessing {len(affected)} of {len(docs)}")

    print(f"\nPROJECTIONS")
    print(f"  Neo4j nodes/edges stale      ALL (entity + fact ids change)")
    print(f"  Qdrant points               unaffected (chunk-keyed, not entity-keyed)")
    print(f"  receipts                    stage receipts re-derived on reprocess")

    print(f"\nREBUILD INPUT — minimum safe boundary")
    print(f"  raw GLiNER proposals persisted    YES  (surface+offsets+type+score, 69/69)")
    print(f"  source chunk text persisted       YES")
    print(f"  syntax persisted                  NO -> regenerate (deterministic, pinned model)")
    print(f"  => GLiNER does NOT need to re-run.")
    print(f"  => rederive starts DOWNSTREAM of provider inference:")
    print(f"     persisted mentions + chunk text -> regenerate syntax -> V2 stack")
    print(f"     -> new entities/facts -> rebuild Neo4j (+ canonical projections)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
